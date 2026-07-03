"""FreeLLMAPI sidecar process control — start/stop the external OpenAI-compatible
gateway so the operator can bring the freellmapi provider mode up from the CLI,
cockpit, or TUI.

Mirrors cashflow_control.py: detached spawn + PID/state file + health probe.
Per D-015 the sidecar stays an external checkout (never vendored); its location
resolves from ATLAS_FREELLMAPI_DIR, then the remembered state file, then common
sibling paths. start() does not block by default — callers poll status().
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import time
import urllib.request

STATE_FILE = pathlib.Path.home() / ".atlas" / "freellmapi.json"
DEFAULT_PORT = 3001
# Matches model_registry.DEFAULT_GATEWAY_URL ("http://127.0.0.1:3001/v1").
BASE_URL = os.environ.get("ATLAS_LLM_GATEWAY_URL", f"http://127.0.0.1:{DEFAULT_PORT}/v1").rstrip("/")
CLONE_HINT = "git clone https://github.com/tashfeenahmed/freellmapi && cd freellmapi && npm install && npm run build"

# repo root: freellmapi_control.py -> atlas_runtime -> agent-runtime -> services -> repo
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_CANDIDATE_DIRS = (
    _REPO_ROOT / "_EXTERNAL_REPOS" / "freellmapi",
    _REPO_ROOT.parent / "freellmapi",
)


def _read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def resolve_dir() -> pathlib.Path | None:
    """Locate the external freellmapi checkout (env > state file > siblings)."""
    env_dir = os.environ.get("ATLAS_FREELLMAPI_DIR")
    if env_dir:
        p = pathlib.Path(env_dir)
        return p if p.exists() else None
    remembered = _read_state().get("dir")
    if remembered and pathlib.Path(remembered).exists():
        return pathlib.Path(remembered)
    for cand in _CANDIDATE_DIRS:
        if cand.exists():
            return cand
    return None


def health_ok(timeout: float = 1.0) -> bool:
    """Any HTTP response (even 401) proves the sidecar is listening."""
    try:
        req = urllib.request.Request(f"{BASE_URL}/models")
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def get_api_key() -> str | None:
    root = resolve_dir()
    if not root:
        return None
    db_path = root / "server" / "data" / "freeapi.db"
    if not db_path.exists():
        return None
    try:
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'unified_api_key'").fetchone()
            return row[0] if row else None
    except Exception:
        return None


def status() -> dict:
    d = resolve_dir()
    return {
        "running": health_ok(),
        "base_url": BASE_URL,
        "dir": str(d) if d else None,
        "installed": d is not None,
        "api_key": get_api_key(),
        "remediation": None if d else f"clone the sidecar first: {CLONE_HINT}",
    }


def start(poll_seconds: float = 0.0) -> tuple[bool, str]:
    """Start the freellmapi sidecar. Returns (ok, message)."""
    if health_ok():
        return True, f"freellmapi already running on {BASE_URL}"
    root = resolve_dir()
    if root is None:
        return False, (
            "freellmapi checkout not found — set ATLAS_FREELLMAPI_DIR or "
            f"clone it next to the repo: {CLONE_HINT}"
        )
    entry = root / "server" / "dist" / "index.js"
    if not entry.exists():
        return False, f"freellmapi not built at {entry}; run: cd {root} && npm install && npm run build"
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return False, "node not found on PATH"

    env = os.environ.copy()
    env.setdefault("HOST", "127.0.0.1")
    env.setdefault("PORT", str(DEFAULT_PORT))
    # Never force NODE_ENV=production: the sidecar then hard-requires an
    # ENCRYPTION_KEY and exits at boot. Local sidecars use their own .env;
    # outside production the server auto-generates a DB-stored key.
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        )
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        [node, str(entry)],
        cwd=str(root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        **kwargs,
    )
    _write_state({"pid": proc.pid, "dir": str(root)})

    if poll_seconds > 0:
        deadline = time.monotonic() + poll_seconds
        while time.monotonic() < deadline:
            if health_ok():
                return True, f"freellmapi started (pid {proc.pid}) on {BASE_URL}"
            time.sleep(0.5)
    return True, f"freellmapi starting (pid {proc.pid}); {BASE_URL} shortly"


def stop() -> tuple[bool, str]:
    state = _read_state()
    pid = state.get("pid")
    if not pid:
        return False, "no pid recorded; freellmapi not managed here"
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        else:
            os.kill(int(pid), 15)
    finally:
        state.pop("pid", None)
        _write_state(state)
    return True, f"stopped (pid {pid})"
