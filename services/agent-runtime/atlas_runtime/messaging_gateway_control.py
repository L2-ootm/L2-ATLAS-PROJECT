"""Messaging-gateway lifecycle control — start/stop/status the foundation
(Hermes-derived) messaging gateway from the cockpit.

The foundation ships 22+ messaging adapters behind its own CLI
(`atlas-agent gateway run`). ATLAS owns no foundation code (D-001); it only
spawns that gateway detached and tracks it via its own state file
(`~/.atlas/gateway-messaging.json`), mirroring gateway_control.py (the Rust
gateway) and cashflow_control.py (the Next.js module).

Unlike the Rust gateway, the foundation messaging gateway exposes no HTTP
`/health`, so "running" is determined by PID-file liveness (a dependency-free,
cross-platform process check). Channel config/writes stay in the foundation CLI
(D-022); this module only manages the process lifecycle.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys

STATE_FILE = pathlib.Path.home() / ".atlas" / "gateway-messaging.json"


def messaging_cli() -> list[str] | None:
    """Resolve how to invoke the foundation messaging gateway CLI.

    Order: ``ATLAS_MESSAGING_CLI`` override (whitespace-split) -> ``atlas-agent``
    on PATH -> ``hermes`` on PATH -> ``<python> -m hermes_cli.main`` when the
    module is importable (the Hermes venv). Returns the argv prefix (without the
    ``gateway`` subcommand), or None when the foundation CLI cannot be located.
    """
    env = os.environ.get("ATLAS_MESSAGING_CLI", "").strip()
    if env:
        return env.split()
    for name in ("atlas-agent", "hermes"):
        found = shutil.which(name)
        if found:
            return [found]
    try:
        if importlib.util.find_spec("hermes_cli.main") is not None:
            return [sys.executable, "-m", "hermes_cli.main"]
    except Exception:
        pass
    return None


def _read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def _pid_alive(pid: int) -> bool:
    """Cross-platform 'is this PID running' check, dependency-free."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                check=False,
            )
            stdout = (out.stdout or b"").decode("utf-8", errors="replace")
            return str(pid) in stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def read_pid() -> int | None:
    pid = _read_state().get("pid")
    try:
        return int(pid) if pid else None
    except (TypeError, ValueError):
        return None


def is_running() -> bool:
    pid = read_pid()
    return bool(pid and _pid_alive(pid))


def status() -> dict:
    """Serializable status for the CLI/gateway: {running, pid}."""
    pid = read_pid()
    running = bool(pid and _pid_alive(pid))
    return {"running": running, "pid": pid if running else None}


def start() -> tuple[bool, str]:
    """Spawn the foundation messaging gateway detached; track its PID.

    Idempotent: a no-op when already running. Returns once spawned (the gateway
    has no first-compile delay, but we do not block on adapter handshakes); the
    UI polls status. Side-effecting, so the testable surface (cli resolution,
    state, liveness) is factored out above.
    """
    if is_running():
        return True, f"messaging gateway already running (pid {read_pid()})"
    cli = messaging_cli()
    if not cli:
        return (
            False,
            "foundation messaging CLI not found; set ATLAS_MESSAGING_CLI or put "
            "atlas-agent on PATH",
        )
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        )
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        [*cli, "gateway", "run"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )
    _write_state({"pid": proc.pid})
    return True, f"messaging gateway starting (pid {proc.pid})"


def stop() -> tuple[bool, str]:
    """Stop a messaging gateway started by this primitive (via its state file).

    Idempotent: "stop" means "ensure stopped", so a gateway that is not tracked
    here is already in the desired state and reports success — the cockpit can
    call stop without first checking status.
    """
    pid = read_pid()
    if not pid:
        return True, "messaging gateway not running"
    try:
        if os.name == "nt":
            # /T kills the child tree (the actual gateway worker under the launcher).
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        else:
            os.kill(int(pid), 15)
    finally:
        state = _read_state()
        state.pop("pid", None)
        _write_state(state)
    return True, f"stopped (pid {pid})"
