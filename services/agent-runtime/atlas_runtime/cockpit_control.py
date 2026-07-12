"""Cockpit lifecycle primitive — locate, start, health-check, stop the React cockpit.

The cockpit's twin of `gateway_control.py`. Triggered from `atlas up` (boots gateway +
cockpit together) and any future Tauri/login auto-start surface.

Idempotent: start is a no-op when the cockpit is already serving. Side-effecting
(spawns a detached `npm run preview` process), so the testable pieces (health probe,
port parsing) are factored out and the CLI command stays thin.

Port-authority decision (matches gateway_control.py's precedent): the env var
ATLAS_COCKPIT_URL is authoritative for the spawn/health-check URL, NOT
config.yaml's CockpitConfig.port (which nothing currently wires into a spawn
command — see 10.0.2-PATTERNS.md "Port Authority Reconciliation"). Default
http://127.0.0.1:5173 matches Vite's actual served default (package.json has no
--port flag on any script), not the unused CockpitConfig.port=3000 default.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import time
import urllib.parse
import urllib.request

# Windows creationflags, with literal fallbacks (values are stable Win32 API
# constants) so the Windows spawn path stays importable and unit-testable on
# POSIX, where the subprocess module does not define these attributes.
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

# services/agent-runtime/atlas_runtime/cockpit_control.py -> agent-runtime -> services -> repo root
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_COCKPIT_DIR = _REPO_ROOT / "services" / "web-ui-react"

COCKPIT_URL = os.environ.get("ATLAS_COCKPIT_URL", "http://127.0.0.1:5173")
PID_FILE = pathlib.Path.home() / ".atlas" / "cockpit.pid"


def _parse_port(url: str) -> int:
    """Extract the port from COCKPIT_URL so the npm --port flag always matches.

    A portless URL (e.g. no ``:port`` segment) is a legitimate default and
    still falls back to 5173. An UNPARSABLE port (e.g. a typo like
    ``http://127.0.0.1:abc``) raises instead of silently defaulting — masking
    that misconfiguration would route npm to spawn on 5173 while health_ok()
    polls the broken original URL, producing a confusing timeout with no hint
    of the real cause.
    """
    parsed = urllib.parse.urlparse(url)
    try:
        return parsed.port or 5173
    except ValueError as exc:
        raise ValueError(f"ATLAS_COCKPIT_URL has an invalid port: {url!r}") from exc


def _parse_host(url: str) -> str:
    """Extract the host from COCKPIT_URL so Vite binds the interface we probe.

    The port-authority rule extends to the host: COCKPIT_URL is authoritative
    for BOTH. Without an explicit ``--host`` Vite preview binds its own default,
    which on Windows resolves ``localhost`` to IPv6 ``::1`` only — so a probe of
    ``127.0.0.1`` (IPv4) is refused and ``atlas up``/``atlas doctor`` report the
    cockpit "down" while it is in fact serving. Forcing ``--host 127.0.0.1``
    makes the bind match the probe (loopback-only, no LAN exposure)."""
    parsed = urllib.parse.urlparse(url)
    return parsed.hostname or "127.0.0.1"


def health_ok(timeout: float = 1.0) -> bool:
    """Probe the cockpit root URL. Vite has no /health route — per RESEARCH.md
    Pitfall 3, any non-exception response (even a 404) means something is
    listening and serving HTTP, which is all this primitive needs to know."""
    try:
        with urllib.request.urlopen(f"{COCKPIT_URL}/", timeout=timeout):
            return True
    except Exception:
        return False


def start(poll_seconds: float = 15.0) -> tuple[bool, str]:
    """Start the cockpit if not already healthy. Returns (ok, message)."""
    if health_ok():
        return True, "cockpit already running"
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    port = _parse_port(COCKPIT_URL)
    host = _parse_host(COCKPIT_URL)
    cmd = [npm_cmd, "run", "preview", "--", "--port", str(port), "--host", host]
    kwargs: dict = {}
    if os.name == "nt":
        # CREATE_NO_WINDOW is the extra flag beyond gateway_control's two-flag set:
        # npm is a .cmd shell shim (not a native .exe), so DETACHED_PROCESS +
        # CREATE_NEW_PROCESS_GROUP alone still flashes the shim's own console
        # (commit 62e9456's regression class, extended here per RESEARCH.md Pitfall 4).
        kwargs["creationflags"] = (
            DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        )
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        cmd,
        cwd=str(_COCKPIT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(proc.pid))
    deadline = time.monotonic() + poll_seconds
    while time.monotonic() < deadline:
        if health_ok():
            return True, f"cockpit started (pid {proc.pid}) on {COCKPIT_URL}"
        time.sleep(0.5)
    return False, "cockpit did not become healthy in time"


def _pid_alive(pid: int) -> bool:
    """Liveness check with no new dependency (psutil is not a project dep).

    POSIX: ``os.kill(pid, 0)`` raises ``ProcessLookupError`` for a dead PID
    without sending a real signal. Windows: shell out to ``tasklist`` filtered
    on the PID and check whether it reports the PID back — this does not
    verify process *identity* (a recycled PID reporting a different program
    would still read as "alive"), only that something currently holds that
    PID. That is the best stdlib-only signal available; full identity
    verification would require psutil or a stored process fingerprint.
    """
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return True  # can't determine; don't risk a false "already gone"
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # e.g. PermissionError — process exists, just not ours
    return True


def stop() -> tuple[bool, str]:
    """Stop a cockpit started by this primitive (via its PID file)."""
    if not PID_FILE.exists():
        return False, "no pid file; cockpit not managed here"
    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        PID_FILE.unlink(missing_ok=True)
        return False, "invalid pid file (removed)"
    if not _pid_alive(pid):
        PID_FILE.unlink(missing_ok=True)
        return False, f"cockpit process already gone (pid {pid}, removed)"
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
        else:
            os.kill(pid, 15)
    finally:
        PID_FILE.unlink(missing_ok=True)
    return True, f"stopped (pid {pid})"
