"""Cashflow module process control — provision, start, and stop the vendored
Next.js app with a chosen DB backend, so the operator can run it from the
cockpit System page or the CLI.

Mirrors gateway_control.py: detached spawn + PID/state file + health probe. The
chosen backend is passed as ATLAS_CASHFLOW_DB (local|supabase) and remembered in
~/.atlas/cashflow.json.

Cashflow ships as SOURCE (see infra/release/payload.manifest): a prebuilt bundle
would be ~1.3 GB of node_modules + .next against 1.18 MB of tracked source, and
`next start` needs node_modules present at runtime. Dependencies are therefore
installed and the production bundle built on the operator's machine the first
time cashflow is started, by atlas_runtime.provisioning.

That first build takes minutes, and `start()` is reached through
`dispatch_atlas(&["cashflow", "start"])` in the Rust gateway, which awaits the
reply. So `start()` never provisions inline: when real work is needed it hands
the job to a detached bootstrap process, marks the state file
`phase="provisioning"`, and returns immediately. Callers poll `status()` exactly
as they already did for the old dev-server compile. Progress is appended to
`<ATLAS home>/sidecars/cashflow.provision.log`.

The app is served with `npm run start` (`next start`) against that prebuilt
bundle rather than `npm run dev` (`next dev`), which compiled every route on
demand and cost multi-second first-hit latency plus ~300MB of extra RAM.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

from . import provisioning

# cashflow_control.py -> atlas_runtime -> agent-runtime -> services ; /cashflow
CASHFLOW_DIR = pathlib.Path(__file__).resolve().parents[2] / "cashflow"
CASHFLOW_URL = os.environ.get("ATLAS_CASHFLOW_URL", "http://localhost:3000")
STATE_FILE = pathlib.Path.home() / ".atlas" / "cashflow.json"
VALID_BACKENDS = ("local", "supabase")

PHASE_IDLE = "idle"
PHASE_PROVISIONING = "provisioning"
PHASE_RUNNING = "running"


def _component() -> provisioning.Component:
    return provisioning.cashflow_component()


def provision_log_path() -> pathlib.Path:
    return provisioning.sidecars_home() / "cashflow.provision.log"


def runtime_dir() -> pathlib.Path:
    """Directory the app is actually installed, built, and served from.

    This is the checkout itself in a dev tree, and `<ATLAS home>/sidecars/cashflow`
    when cashflow was shipped inside an immutable release bundle.
    """
    workspace, _mirrored = provisioning.resolve_workspace(_component())
    return workspace


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


def _pid_alive(pid: object) -> bool:
    try:
        pid_int = int(pid)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    if pid_int <= 0:
        return False
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid_int}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid_int) in (out.stdout or "")
    try:
        os.kill(pid_int, 0)
    except OSError:
        return False
    return True


def _log_tail(limit: int = 1) -> str:
    try:
        lines = [
            line.strip()
            for line in provision_log_path().read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            if line.strip()
        ]
    except OSError:
        return ""
    return " | ".join(lines[-limit:])


def status() -> dict:
    """Report liveness plus provisioning phase, so a UI can show real progress."""
    state = _read_state()
    running = health_ok()
    phase = state.get("phase", PHASE_IDLE)
    if running:
        phase = PHASE_RUNNING
    elif phase == PHASE_PROVISIONING and not _pid_alive(state.get("bootstrap_pid")):
        # The bootstrap died without reaching a healthy server. Surface the
        # failure instead of reporting "provisioning" forever.
        phase = PHASE_IDLE
    result = {
        "running": running,
        "backend": state.get("backend", "local"),
        "url": CASHFLOW_URL,
        "phase": phase,
        "runtime_dir": str(runtime_dir()),
    }
    if phase != PHASE_RUNNING:
        detail = _log_tail()
        if detail:
            result["detail"] = detail
    return result


def _npm_available() -> bool:
    import shutil

    return bool(shutil.which("npm") or shutil.which("npm.cmd"))


def provision(force: bool = False, log=None) -> tuple[bool, str]:
    """Install dependencies and build the production bundle, synchronously.

    Idempotent and content-addressed: a second call with an unchanged source
    tree and lockfile only fingerprints and returns. Intended for
    `atlas cashflow provision`, where blocking is the point.
    """
    result = provisioning.ensure_provisioned(_component(), force=force, log=log)
    return result.ok, result.message


def _spawn_server(backend: str, workdir: pathlib.Path) -> int:
    """Detach `next start` and return its pid."""
    env = os.environ.copy()
    env["ATLAS_CASHFLOW_DB"] = backend
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        )
        args: object = "npm run start"
        kwargs["shell"] = True  # resolve npm.cmd via cmd.exe
    else:
        kwargs["start_new_session"] = True
        args = ["npm", "run", "start"]

    proc = subprocess.Popen(
        args,
        cwd=str(workdir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        **kwargs,
    )
    return proc.pid


def _spawn_bootstrap(backend: str) -> tuple[bool, str]:
    """Detach provisioning + start so the caller's dispatch does not block."""
    log_path = provision_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["ATLAS_CASHFLOW_DB"] = backend
    # Fixed argv, no shell: nothing here is re-parsed. sys.executable is the
    # embedded interpreter in a release and the venv interpreter in a checkout,
    # so `-c` resolves atlas_runtime in both without a PYTHONPATH dance.
    argv = [
        sys.executable,
        "-c",
        "from atlas_runtime import cashflow_control as c; c.provision_then_start()",
    ]
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        )
    else:
        kwargs["start_new_session"] = True
    try:
        handle = open(log_path, "a", encoding="utf-8")
    except OSError as exc:
        return False, f"cannot open provisioning log {log_path}: {exc}"
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(pathlib.Path.home()),
            stdout=handle,
            stderr=subprocess.STDOUT,
            env=env,
            **kwargs,
        )
    except OSError as exc:
        handle.close()
        return False, f"cannot start cashflow provisioning: {exc}"
    finally:
        # The child inherits the descriptor; the parent must not hold it open.
        handle.close()
    _write_state(
        {"backend": backend, "phase": PHASE_PROVISIONING, "bootstrap_pid": proc.pid}
    )
    return True, (
        f"cashflow provisioning started (pid {proc.pid}, backend={backend}); "
        f"first run installs dependencies and builds the bundle. "
        f"Poll `atlas cashflow status`; log: {log_path}"
    )


def provision_then_start() -> int:
    """Detached bootstrap entrypoint: provision, then serve. Returns exit code.

    stdout/stderr are already redirected to the provisioning log by the parent,
    so plain prints are the progress feed that `status()` tails.
    """
    backend = os.environ.get("ATLAS_CASHFLOW_DB", "local")
    if backend not in VALID_BACKENDS:
        backend = "local"

    def emit(message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        print(f"[{stamp}] {message}", flush=True)

    emit(f"provisioning cashflow (backend={backend})")
    result = provisioning.ensure_provisioned(_component(), log=emit)
    if not result.ok:
        emit(f"FAILED: {result.message}")
        _write_state({"backend": backend, "phase": PHASE_IDLE})
        return 1
    emit(result.message)
    try:
        pid = _spawn_server(backend, result.workspace)
    except OSError as exc:
        emit(f"FAILED to start server: {exc}")
        _write_state({"backend": backend, "phase": PHASE_IDLE})
        return 1
    emit(f"started next start (pid {pid}) on {CASHFLOW_URL}")
    _write_state({"backend": backend, "phase": PHASE_RUNNING, "pid": pid})
    return 0


def start(backend: str = "local", poll_seconds: float = 0.0) -> tuple[bool, str]:
    """Start the cashflow app with the chosen backend. Returns (ok, message).

    Never blocks on a package install or a bundler. If provisioning work is
    outstanding it is handed to a detached bootstrap and this returns
    immediately with `phase="provisioning"` recorded; otherwise the prebuilt
    server is spawned directly. The state file records the backend + pid.
    """
    if backend not in VALID_BACKENDS:
        return False, f"unknown backend {backend!r}; valid: {list(VALID_BACKENDS)}"
    component = _component()
    if not component.source_dir.is_dir():
        return False, f"cashflow module not found at {component.source_dir}"
    if health_ok():
        state = _read_state()
        state["backend"] = backend
        state["phase"] = PHASE_RUNNING
        _write_state(state)
        return True, "cashflow already running"
    if not _npm_available():
        return False, "npm not found on PATH"

    state = _read_state()
    if state.get("phase") == PHASE_PROVISIONING and _pid_alive(
        state.get("bootstrap_pid")
    ):
        return True, (
            f"cashflow provisioning already in progress "
            f"(pid {state.get('bootstrap_pid')}); poll `atlas cashflow status`"
        )

    plan = provisioning.plan_provisioning(component)
    if plan.is_expensive:
        return _spawn_bootstrap(backend)

    # Cheap path: nothing to install or build. A pending mirror is a file copy.
    result = provisioning.ensure_provisioned(component)
    if not result.ok:
        return False, f"cashflow provisioning failed: {result.message}"
    try:
        pid = _spawn_server(backend, result.workspace)
    except OSError as exc:
        return False, f"cannot start cashflow: {exc}"
    _write_state({"backend": backend, "phase": PHASE_RUNNING, "pid": pid})

    if poll_seconds > 0:
        deadline = time.monotonic() + poll_seconds
        while time.monotonic() < deadline:
            if health_ok():
                return True, f"cashflow started (pid {pid}, {backend}) on {CASHFLOW_URL}"
            time.sleep(0.5)
    return True, f"cashflow starting (pid {pid}, backend={backend}); {CASHFLOW_URL} shortly"


def stop() -> tuple[bool, str]:
    state = _read_state()
    pid = state.get("pid")
    bootstrap_pid = state.get("bootstrap_pid")
    targets = [p for p in (pid, bootstrap_pid) if p]
    if not targets:
        return False, "no pid recorded; cashflow not managed here"
    try:
        for target in targets:
            if os.name == "nt":
                # /T kills the child tree (npm's actual next/node process).
                subprocess.run(
                    ["taskkill", "/PID", str(target), "/T", "/F"], check=False
                )
            else:
                try:
                    os.kill(int(target), 15)
                except (OSError, ValueError):
                    pass
    finally:
        state.pop("pid", None)
        state.pop("bootstrap_pid", None)
        state["phase"] = PHASE_IDLE
        _write_state(state)
    return True, f"stopped ({', '.join(str(t) for t in targets)})"
