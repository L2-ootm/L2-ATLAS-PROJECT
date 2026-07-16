"""FreeLLMAPI sidecar process control — start/stop the external OpenAI-compatible
gateway so the operator can bring the freellmapi provider mode up from the CLI,
cockpit, or TUI.

Mirrors cashflow_control.py: detached spawn + PID/state file + health probe.
Per D-015 the sidecar stays an external checkout (never vendored). Its default
home is inside the ATLAS install home (`sidecar_home()`, ATLAS_DB/ATLAS_HOME-
aware) so `atlas freellmapi install` gives a fresh install somewhere real to put
it — a dev checkout of this monorepo also has two sibling-path fallbacks for
back-compat. Resolution order: ATLAS_FREELLMAPI_DIR env > remembered state file
> sidecar_home() > monorepo sibling paths. start() does not block by default —
callers poll status().
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import time
import urllib.request

from atlas_runtime import db as db_module

STATE_FILE = pathlib.Path.home() / ".atlas" / "freellmapi.json"
DEFAULT_PORT = 3001
# Matches model_registry.DEFAULT_GATEWAY_URL ("http://127.0.0.1:3001/v1").
BASE_URL = os.environ.get("ATLAS_LLM_GATEWAY_URL", f"http://127.0.0.1:{DEFAULT_PORT}/v1").rstrip("/")
REPO_URL = "https://github.com/tashfeenahmed/freellmapi"
CLONE_HINT = f"run 'atlas freellmapi install', or manually: git clone {REPO_URL} && cd freellmapi && npm install && npm run build"

# repo root: freellmapi_control.py -> atlas_runtime -> agent-runtime -> services -> repo
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def sidecar_home() -> pathlib.Path:
    """Default install target: <ATLAS home>/sidecars/freellmapi.

    Derived from `db.default_db_path()` (not a frozen constant) so it honors
    ATLAS_DB/ATLAS_HOME at call time and follows the same install the rest of
    ATLAS uses — never the dev-repo checkout, so a fresh npm/pip install of
    `atlas` (no git repo on disk at all) still has somewhere real to install
    the sidecar, and `atlas` retains full control of its lifecycle.
    """
    return pathlib.Path(db_module.default_db_path()).parent / "sidecars" / "freellmapi"


def _candidate_dirs() -> tuple[pathlib.Path, ...]:
    return (
        sidecar_home(),
        # Dev-checkout fallbacks (monorepo sibling paths) — back-compat only.
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
    """Locate the external freellmapi checkout (env > state file > sidecar_home > siblings)."""
    env_dir = os.environ.get("ATLAS_FREELLMAPI_DIR")
    if env_dir:
        p = pathlib.Path(env_dir)
        return p if p.exists() else None
    remembered = _read_state().get("dir")
    if remembered and pathlib.Path(remembered).exists():
        return pathlib.Path(remembered)
    for cand in _candidate_dirs():
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
        "remediation": None if d else f"not installed — {CLONE_HINT}",
    }


def install(target: pathlib.Path | None = None, *, force: bool = False) -> tuple[bool, str]:
    """Clone + build the freellmapi sidecar into `target` (default `sidecar_home()`).

    Idempotent: if `target` already looks like a freellmapi git checkout, this
    re-runs npm install/build (picks up upstream updates) instead of re-cloning.
    Pass force=True to wipe and re-clone a non-checkout directory in the way.
    Remembers the install dir in the state file, same as a manual
    ATLAS_FREELLMAPI_DIR checkout would once `start()` succeeds against it.
    """
    dest = target or sidecar_home()
    git = shutil.which("git") or shutil.which("git.exe")
    if not git:
        return False, "git not found on PATH"
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        return False, "npm not found on PATH"

    is_checkout = (dest / ".git").exists()
    if dest.exists() and not is_checkout:
        if not force:
            return False, f"{dest} already exists and isn't a freellmapi checkout; pass force=True to overwrite"
        shutil.rmtree(dest)

    if not (dest.exists() and is_checkout):
        dest.parent.mkdir(parents=True, exist_ok=True)
        clone = subprocess.run(
            [git, "clone", "--depth", "1", REPO_URL, str(dest)],
            capture_output=True, text=True,
        )
        if clone.returncode != 0:
            return False, f"git clone failed: {clone.stderr.strip()[:400]}"

    npm_kwargs: dict = {"cwd": str(dest), "capture_output": True, "text": True}
    if os.name == "nt":
        npm_kwargs["shell"] = True  # resolve npm.cmd via cmd.exe, same as cashflow_control
    npm_install = subprocess.run(f'"{npm}" install' if os.name == "nt" else [npm, "install"], **npm_kwargs)
    if npm_install.returncode != 0:
        return False, f"npm install failed: {npm_install.stderr.strip()[:400]}"
    npm_build = subprocess.run(f'"{npm}" run build' if os.name == "nt" else [npm, "run", "build"], **npm_kwargs)
    if npm_build.returncode != 0:
        return False, f"npm run build failed: {npm_build.stderr.strip()[:400]}"

    state = _read_state()
    state["dir"] = str(dest)
    _write_state(state)
    return True, f"freellmapi installed at {dest}"


def start(poll_seconds: float = 0.0) -> tuple[bool, str]:
    """Start the freellmapi sidecar. Returns (ok, message)."""
    if health_ok():
        return True, f"freellmapi already running on {BASE_URL}"
    root = resolve_dir()
    if root is None:
        return False, (
            f"freellmapi not installed — {CLONE_HINT} "
            "(or point at an existing checkout with ATLAS_FREELLMAPI_DIR)"
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
