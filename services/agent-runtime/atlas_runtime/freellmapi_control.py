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
import urllib.error
import urllib.request
import contextlib
from dataclasses import dataclass

from atlas_runtime import db as db_module
from atlas_runtime import service_supervision as supervision

# Compatibility seam for older tests/integrations.  ``None`` means resolve the
# metadata path from ATLAS_HOME at call time; callers may still monkeypatch a
# concrete path without freezing the real runtime at import time.
STATE_FILE: pathlib.Path | None = None
SERVICE = "freellmapi"
DEFAULT_PORT = 3001
# Matches model_registry.DEFAULT_GATEWAY_URL ("http://127.0.0.1:3001/v1").
BASE_URL = os.environ.get(
    "ATLAS_LLM_GATEWAY_URL", f"http://127.0.0.1:{DEFAULT_PORT}/v1"
).rstrip("/")
REPO_URL = "https://github.com/tashfeenahmed/freellmapi"
CLONE_HINT = f"run 'atlas freellmapi install', or manually: git clone {REPO_URL} && cd freellmapi && npm install && npm run build"

# repo root: freellmapi_control.py -> atlas_runtime -> agent-runtime -> services -> repo
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def _metadata_path() -> pathlib.Path:
    return (
        pathlib.Path(STATE_FILE)
        if STATE_FILE is not None
        else supervision.atlas_home() / "freellmapi.json"
    )


def _service_state_path() -> pathlib.Path:
    return supervision.state_path(SERVICE)


def _legacy_pid_path() -> pathlib.Path:
    return supervision.legacy_pid_path(SERVICE)


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
        return json.loads(_metadata_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    path = _metadata_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


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


@dataclass(frozen=True, slots=True)
class ModelsProbe:
    reachable: bool
    identity_valid: bool
    error: str | None = None


def _models_probe(timeout: float = 1.0) -> ModelsProbe:
    """Validate an OpenAI-compatible models document, not merely an HTTP listener."""
    try:
        headers: dict[str, str] = {"Accept": "application/json"}
        api_key = get_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(f"{BASE_URL}/models", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = json.loads(response.read(1_048_577))
        valid = (
            isinstance(raw, dict)
            and isinstance(raw.get("data"), list)
            and all(
                isinstance(item, dict) and isinstance(item.get("id"), str)
                for item in raw["data"]
            )
        )
        return ModelsProbe(True, valid, None if valid else "invalid_models_document")
    except urllib.error.HTTPError as exc:
        return ModelsProbe(True, False, f"http_{exc.code}")
    except (json.JSONDecodeError, UnicodeError):
        return ModelsProbe(True, False, "invalid_json")
    except Exception as exc:
        return ModelsProbe(False, False, type(exc).__name__)


def health_ok(timeout: float = 1.0) -> bool:
    """Return true only for a validated FreeLLMAPI-compatible models response."""
    return _models_probe(timeout).identity_valid


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
            row = conn.execute(
                "SELECT value FROM settings WHERE key = 'unified_api_key'"
            ).fetchone()
            return row[0] if row else None
    except Exception:
        return None


def _load_launch_record() -> tuple[supervision.ServiceLaunchRecord | None, str | None]:
    try:
        return supervision.load_launch_record(_service_state_path()), None
    except supervision.ServiceStateError as exc:
        return None, str(exc)


def status() -> dict:
    """Return a JSON-stable, ownership-aware lifecycle status."""
    directory = resolve_dir()
    probe = _models_probe()
    record, record_error = _load_launch_record()
    pid: int | None = None
    identity: dict | None = None
    process: dict | None = None
    port: dict | None = None

    if record_error:
        state = "invalid_state"
        remediation = "retain the state file and inspect it before lifecycle actions"
    elif record is None:
        legacy_pid = supervision.read_legacy_pid(
            _legacy_pid_path()
        ) or _read_state().get("pid")
        pid = (
            legacy_pid
            if isinstance(legacy_pid, int) and not isinstance(legacy_pid, bool)
            else None
        )
        if pid:
            state = "legacy_unverifiable"
            remediation = "legacy PID has no process-instance identity; inspect it before recovery"
        elif probe.identity_valid:
            state = "unmanaged_listener"
            remediation = (
                "the models endpoint is live but is not owned by this ATLAS instance"
            )
        else:
            state = "stopped"
            remediation = None if directory else f"not installed — {CLONE_HINT}"
    else:
        observed = supervision.observe_service(
            record,
            process_observer=supervision.observe_process,
            port_observer=supervision.observe_port,
        )
        pid = record.pid
        identity = observed.identity.to_dict() if observed.identity else None
        process = observed.process.to_dict() if observed.process else None
        port = observed.port.to_dict() if observed.port else None
        if observed.state == "running" and probe.identity_valid:
            state, remediation = "ready", None
        elif observed.state == "running" and probe.reachable:
            state = "endpoint_identity_mismatch"
            remediation = "retain state; another or malformed HTTP service answered the models probe"
        elif observed.state == "running":
            state = "starting"
            remediation = (
                "the owned process is alive but its models endpoint is not ready"
            )
        else:
            state, remediation = observed.state, observed.remediation

    return {
        # Backward-compatible keys.
        "running": state == "ready",
        "base_url": BASE_URL,
        "dir": str(directory) if directory else None,
        "installed": directory is not None,
        "api_key_configured": bool(get_api_key()),
        "remediation": remediation,
        # Structured lifecycle contract.
        "service": SERVICE,
        "state": state,
        "ready": state == "ready",
        "pid": pid,
        "owned": record is not None,
        "endpoint_reachable": probe.reachable,
        "endpoint_identity_valid": probe.identity_valid,
        "probe_error": probe.error,
        "identity": identity,
        "process": process,
        "port": port,
    }


def install(
    target: pathlib.Path | None = None, *, force: bool = False
) -> tuple[bool, str]:
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
            return (
                False,
                f"{dest} already exists and isn't a freellmapi checkout; pass force=True to overwrite",
            )
        shutil.rmtree(dest)

    if not (dest.exists() and is_checkout):
        dest.parent.mkdir(parents=True, exist_ok=True)
        clone = subprocess.run(
            [git, "clone", "--depth", "1", REPO_URL, str(dest)],
            capture_output=True,
            text=True,
        )
        if clone.returncode != 0:
            return False, f"git clone failed: {clone.stderr.strip()[:400]}"

    npm_kwargs: dict = {"cwd": str(dest), "capture_output": True, "text": True}
    if os.name == "nt":
        npm_kwargs["shell"] = (
            True  # resolve npm.cmd via cmd.exe, same as cashflow_control
        )
    npm_install = subprocess.run(
        f'"{npm}" install' if os.name == "nt" else [npm, "install"], **npm_kwargs
    )
    if npm_install.returncode != 0:
        return False, f"npm install failed: {npm_install.stderr.strip()[:400]}"
    npm_build = subprocess.run(
        f'"{npm}" run build' if os.name == "nt" else [npm, "run", "build"], **npm_kwargs
    )
    if npm_build.returncode != 0:
        return False, f"npm run build failed: {npm_build.stderr.strip()[:400]}"

    state = _read_state()
    state["dir"] = str(dest)
    _write_state(state)
    return True, f"freellmapi installed at {dest}"


def _remove_runtime_projection(*, clear_metadata_pid: bool = True) -> None:
    with contextlib.suppress(FileNotFoundError):
        _service_state_path().unlink()
    with contextlib.suppress(FileNotFoundError):
        _legacy_pid_path().unlink()
    if clear_metadata_pid:
        metadata = _read_state()
        if "pid" in metadata:
            metadata.pop("pid", None)
            _write_state(metadata)


def _wait_for_process_identity(
    pid: int, timeout: float = 1.0
) -> supervision.ProcessObservation:
    deadline = time.monotonic() + timeout
    observation = supervision.observe_process(pid)
    while (
        observation.exists
        and not observation.identity_available
        and time.monotonic() < deadline
    ):
        time.sleep(0.025)
        observation = supervision.observe_process(pid)
    return observation


def _terminate_pid(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
        )
    else:
        os.kill(pid, 15)


def _wait_until_dead(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not supervision.observe_process(pid).exists:
            return True
        time.sleep(0.05)
    return not supervision.observe_process(pid).exists


def start(poll_seconds: float = 0.0) -> tuple[bool, str]:
    """Start the freellmapi sidecar. Returns (ok, message)."""
    try:
        with supervision.service_lock(SERVICE):
            current = status()
            if current["state"] == "ready":
                return True, f"freellmapi already running on {BASE_URL}"
            if current["state"] == "starting":
                return True, f"freellmapi already starting (pid {current['pid']})"
            if current["state"] == "stopped" and current["owned"]:
                _remove_runtime_projection()
            elif current["state"] not in {"stopped"}:
                return (
                    False,
                    f"freellmapi start refused: {current['state']} — {current['remediation']}",
                )

            root = resolve_dir()
            if root is None:
                return False, (
                    f"freellmapi not installed — {CLONE_HINT} "
                    "(or point at an existing checkout with ATLAS_FREELLMAPI_DIR)"
                )
            entry = root / "server" / "dist" / "index.js"
            if not entry.exists():
                return (
                    False,
                    f"freellmapi not built at {entry}; run: cd {root} && npm install && npm run build",
                )
            node = shutil.which("node") or shutil.which("node.exe")
            if not node:
                return False, "node not found on PATH"

            argv = [node, str(entry)]
            env = os.environ.copy()
            env.setdefault("HOST", "127.0.0.1")
            env.setdefault("PORT", str(DEFAULT_PORT))
            kwargs: dict = {}
            if os.name == "nt":
                kwargs["creationflags"] = (
                    subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
                )
            else:
                kwargs["start_new_session"] = True

            log = supervision.open_sensitive_log(supervision.log_path(SERVICE))
            try:
                proc = subprocess.Popen(
                    argv,
                    cwd=str(root),
                    stdout=log,
                    stderr=log,
                    env=env,
                    **kwargs,
                )
            finally:
                log.close()

            observation = _wait_for_process_identity(proc.pid)
            if proc.poll() is not None or not observation.exists:
                tail = supervision.sanitized_log_tail(supervision.log_path(SERVICE))
                detail = f": {tail.text}" if tail.text else ""
                return False, f"freellmapi exited during startup{detail}"
            if (
                not observation.identity_available
                or not observation.executable_path
                or not observation.process_creation_time
            ):
                _terminate_pid(proc.pid)
                _wait_until_dead(proc.pid)
                return (
                    False,
                    "freellmapi identity unavailable after launch; child terminated without recording unsafe state",
                )

            record = supervision.create_launch_record(
                service=SERVICE,
                pid=proc.pid,
                executable_path=observation.executable_path,
                process_creation_time=observation.process_creation_time,
                argv=argv,
                host="127.0.0.1",
                port=DEFAULT_PORT,
                sensitive_log_path=supervision.log_path(SERVICE),
            )
            try:
                supervision.write_launch_record(record, _service_state_path())
                pid_path = _legacy_pid_path()
                pid_path.parent.mkdir(parents=True, exist_ok=True)
                pid_path.write_text(f"{proc.pid}\n", encoding="ascii")
                metadata = _read_state()
                metadata.update({"pid": proc.pid, "dir": str(root)})
                _write_state(metadata)
            except Exception as exc:
                with contextlib.suppress(OSError):
                    _terminate_pid(proc.pid)
                    _wait_until_dead(proc.pid)
                with contextlib.suppress(OSError):
                    _remove_runtime_projection()
                return (
                    False,
                    "freellmapi supervision state could not be persisted "
                    f"({type(exc).__name__}); child termination attempted",
                )

            if poll_seconds > 0:
                deadline = time.monotonic() + poll_seconds
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        tail = supervision.sanitized_log_tail(
                            supervision.log_path(SERVICE)
                        )
                        detail = f": {tail.text}" if tail.text else ""
                        return False, f"freellmapi exited during startup{detail}"
                    if health_ok(
                        timeout=min(1.0, max(0.1, deadline - time.monotonic()))
                    ):
                        return (
                            True,
                            f"freellmapi started (pid {proc.pid}) on {BASE_URL}",
                        )
                    time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
                return (
                    False,
                    f"freellmapi readiness timed out after {poll_seconds:g}s; process remains supervised",
                )
            return True, f"freellmapi starting (pid {proc.pid}); {BASE_URL} shortly"
    except supervision.ServiceLockBusy as exc:
        return False, str(exc)
    except OSError as exc:
        return False, f"freellmapi launch failed: {type(exc).__name__}"


def stop() -> tuple[bool, str]:
    try:
        with supervision.service_lock(SERVICE):
            record, record_error = _load_launch_record()
            if record_error:
                return (
                    False,
                    f"service state invalid; refusing unsafe stop: {record_error}",
                )
            if record is None:
                legacy_pid = supervision.read_legacy_pid(
                    _legacy_pid_path()
                ) or _read_state().get("pid")
                if legacy_pid:
                    return (
                        False,
                        "legacy pid recorded without process identity; refusing unsafe stop",
                    )
                return False, "no pid recorded; freellmapi not managed here"

            observed = supervision.observe_service(
                record,
                process_observer=supervision.observe_process,
                port_observer=supervision.observe_port,
            )
            if observed.state == "stopped":
                _remove_runtime_projection()
                return False, f"already gone (pid {record.pid}); stale state removed"
            if observed.state != "running":
                return (
                    False,
                    f"refusing unsafe stop: {observed.state} — {observed.remediation}",
                )

            try:
                _terminate_pid(record.pid)
            except OSError as exc:
                return (
                    False,
                    f"stop failed for pid {record.pid}: {type(exc).__name__}; state retained",
                )
            if not _wait_until_dead(record.pid):
                return False, f"stop unverified for pid {record.pid}; state retained"
            _remove_runtime_projection()
            return True, f"stopped (pid {record.pid})"
    except supervision.ServiceLockBusy as exc:
        return False, str(exc)
    except OSError as exc:
        return False, f"freellmapi stop bookkeeping failed: {type(exc).__name__}"
