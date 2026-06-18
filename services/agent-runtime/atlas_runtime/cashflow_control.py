"""Cashflow module process control — start/stop the vendored Next.js app with a
chosen DB backend, so the operator can run it from the cockpit System page.

Mirrors gateway_control.py: detached spawn + PID/state file + health probe. The
chosen backend is passed as ATLAS_CASHFLOW_DB (local|supabase) and remembered in
~/.atlas/cashflow.json. start() does NOT block on the Next dev compile (which can
exceed a dispatch timeout) — it returns once spawned; the UI polls status.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import time
import urllib.request

# cashflow_control.py -> atlas_runtime -> agent-runtime -> services ; /cashflow
CASHFLOW_DIR = pathlib.Path(__file__).resolve().parents[2] / "cashflow"
CASHFLOW_URL = os.environ.get("ATLAS_CASHFLOW_URL", "http://localhost:3000")
STATE_FILE = pathlib.Path.home() / ".atlas" / "cashflow.json"
VALID_BACKENDS = ("local", "supabase")


def _read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def current_backend() -> str:
    return _read_state().get("backend", "local")


def health_ok(timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(CASHFLOW_URL, timeout=timeout) as resp:
            return getattr(resp, "status", resp.getcode()) < 500
    except Exception:
        return False


def status() -> dict:
    return {"running": health_ok(), "backend": current_backend(), "url": CASHFLOW_URL}


def _npm_available() -> bool:
    return bool(shutil.which("npm") or shutil.which("npm.cmd"))


def start(backend: str = "local", poll_seconds: float = 0.0) -> tuple[bool, str]:
    """Start the cashflow Next.js app with the chosen backend. Returns (ok, message).

    Does not block on first compile by default (poll_seconds=0) — returns once the
    process is spawned. The state file records the backend + pid.
    """
    if backend not in VALID_BACKENDS:
        return False, f"unknown backend {backend!r}; valid: {list(VALID_BACKENDS)}"
    if not CASHFLOW_DIR.exists():
        return False, f"cashflow module not found at {CASHFLOW_DIR}"
    if health_ok():
        state = _read_state()
        state["backend"] = backend
        _write_state(state)
        return True, "cashflow already running"
    if not _npm_available():
        return False, "npm not found on PATH"
    if not (CASHFLOW_DIR / "node_modules").exists():
        return False, "cashflow deps not installed; run: cd services/cashflow && npm install"

    env = os.environ.copy()
    env["ATLAS_CASHFLOW_DB"] = backend
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        )
        args: object = "npm run dev"
        kwargs["shell"] = True  # resolve npm.cmd via cmd.exe
    else:
        kwargs["start_new_session"] = True
        args = ["npm", "run", "dev"]

    proc = subprocess.Popen(
        args,
        cwd=str(CASHFLOW_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        **kwargs,
    )
    _write_state({"backend": backend, "pid": proc.pid})

    if poll_seconds > 0:
        deadline = time.monotonic() + poll_seconds
        while time.monotonic() < deadline:
            if health_ok():
                return True, f"cashflow started (pid {proc.pid}, {backend}) on {CASHFLOW_URL}"
            time.sleep(0.5)
    return True, f"cashflow starting (pid {proc.pid}, backend={backend}); {CASHFLOW_URL} shortly"


def stop() -> tuple[bool, str]:
    state = _read_state()
    pid = state.get("pid")
    if not pid:
        return False, "no pid recorded; cashflow not managed here"
    try:
        if os.name == "nt":
            # /T kills the npm child tree (the actual next/node process).
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        else:
            os.kill(int(pid), 15)
    finally:
        state.pop("pid", None)
        _write_state(state)
    return True, f"stopped (pid {pid})"
