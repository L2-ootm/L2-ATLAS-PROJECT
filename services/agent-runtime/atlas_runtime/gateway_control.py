"""Gateway lifecycle primitive — locate, start, health-check, stop the Rust gateway.

The one canonical "start the gateway" implementation. Triggered from three surfaces
(see .planning/prep/gateway-control-tauri-cashflow-decisions-2026-06-18.md):
  1. any terminal (`atlas gateway start`, once `atlas` is on PATH) — also the
     browser-offline fallback the cockpit shows as a copy-command,
  2. the future Tauri shell (`invoke('start_gateway')` shells out to this),
  3. an optional login auto-start task.

Idempotent: start is a no-op when /health already passes. Side-effecting (spawns a
detached process), so the testable pieces (binary resolution, health probe) are
factored out and the CLI commands stay thin.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request

from atlas_runtime.db import MIGRATIONS_DIR

# services/agent-runtime (so the gateway's spawned CLI can import atlas_runtime).
_AGENT_RUNTIME_DIR = pathlib.Path(__file__).resolve().parents[1]

GATEWAY_URL = os.environ.get("ATLAS_GATEWAY_URL", "http://127.0.0.1:8484")
PID_FILE = pathlib.Path.home() / ".atlas" / "gateway.pid"


def gateway_binary() -> str | None:
    """Resolve the atlas-gateway binary: env override -> PATH -> known release path."""
    env = os.environ.get("ATLAS_GATEWAY_BIN")
    if env and pathlib.Path(env).exists():
        return env
    found = shutil.which("atlas-gateway")
    if found:
        return found
    root = MIGRATIONS_DIR.parent.parent  # infra/migrations -> infra -> repo root
    name = "atlas-gateway.exe" if os.name == "nt" else "atlas-gateway"
    candidate = root / "native" / "atlas-core-rs" / "target" / "release" / name
    return str(candidate) if candidate.exists() else None


def health_ok(timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(f"{GATEWAY_URL}/health", timeout=timeout) as resp:
            return getattr(resp, "status", resp.getcode()) == 200
    except Exception:
        return False


def _crate_root() -> pathlib.Path | None:
    root = MIGRATIONS_DIR.parent.parent  # infra/migrations -> infra -> repo root
    candidate = root / "native" / "atlas-core-rs" / "crates" / "atlas-gateway"
    return candidate if candidate.is_dir() else None


def binary_stale() -> bool | None:
    """True if the resolved binary predates its own Rust sources.

    Mirrors go_tui._checkout_binary_stale's mtime comparison so both native
    sidecars use the same staleness contract. Returns None when the binary or
    the source crate can't be resolved (nothing to compare).
    """
    binary = gateway_binary()
    crate = _crate_root()
    if not binary or not crate:
        return None
    binary_path = pathlib.Path(binary)
    if not binary_path.is_file():
        return None
    sources = [p for p in crate.rglob("*.rs") if p.is_file()]
    if not sources:
        return None
    return max(p.stat().st_mtime for p in sources) > binary_path.stat().st_mtime


def _child_env() -> dict[str, str]:
    """Env for the spawned gateway. When the operator hasn't set ATLAS_CLI and the
    interpreter path has no spaces, inject a working multi-token ATLAS_CLI (the
    gateway splits it on whitespace) + PYTHONPATH so the gateway can dispatch
    writes (mission/module/etc.) without `atlas` being installed on PATH yet.
    A spaced interpreter path falls back to the installed `atlas` on PATH.
    """
    env = os.environ.copy()
    root = MIGRATIONS_DIR.parent.parent  # infra/migrations -> infra -> repo root
    env.setdefault("ATLAS_REPO_ROOT", str(root))
    env.setdefault("ATLAS_CASHFLOW_DB_PATH", str(root / "services" / "cashflow" / "dev.db"))
    if "ATLAS_CLI" not in env and " " not in sys.executable:
        env["ATLAS_CLI"] = f"{sys.executable} -m atlas_runtime.cli.main"
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{_AGENT_RUNTIME_DIR}{os.pathsep}{existing}" if existing else str(_AGENT_RUNTIME_DIR)
        )
    return env


def start_command_hint() -> str:
    """The exact terminal command to start the gateway (shown in the offline UI)."""
    return "atlas gateway start"


def start(poll_seconds: float = 15.0) -> tuple[bool, str]:
    """Start the gateway if not already healthy. Returns (ok, message)."""
    if health_ok():
        return True, "gateway already running"
    binary = gateway_binary()
    if not binary:
        return (
            False,
            "atlas-gateway binary not found; set ATLAS_GATEWAY_BIN or build it "
            "(cd native/atlas-core-rs && cargo build --release)",
        )
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        )
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        [binary],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=_child_env(),
        **kwargs,
    )
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(proc.pid))
    deadline = time.monotonic() + poll_seconds
    while time.monotonic() < deadline:
        if health_ok():
            return True, f"gateway started (pid {proc.pid}) on {GATEWAY_URL}"
        time.sleep(0.5)
    return False, "gateway did not become healthy in time"


def stop() -> tuple[bool, str]:
    """Stop a gateway started by this primitive (via its PID file)."""
    if not PID_FILE.exists():
        return False, "no pid file; gateway not managed here"
    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        PID_FILE.unlink(missing_ok=True)
        return False, "invalid pid file (removed)"
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
        else:
            os.kill(pid, 15)
    finally:
        PID_FILE.unlink(missing_ok=True)
    return True, f"stopped (pid {pid})"
