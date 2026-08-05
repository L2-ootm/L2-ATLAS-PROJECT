"""Identity-safe lifecycle control for the ATLAS React cockpit."""
from __future__ import annotations

import contextlib
import json
import os
import pathlib
import shutil
import signal
import subprocess
import time
import urllib.parse
import urllib.request

from atlas_runtime import service_supervision as supervision

DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_COCKPIT_DIR = _REPO_ROOT / "services" / "web-ui-react"
_DIST_INDEX = _COCKPIT_DIR / "dist" / "index.html"
_DIST_SERVER = _COCKPIT_DIR / "scripts" / "serve-dist.mjs"
_SERVICE = "cockpit"
_HEALTH_SERVICE = "atlas-cockpit"
_DEV_HTML_MARKER = "ATLAS — Cockpit"

COCKPIT_URL = os.environ.get("ATLAS_COCKPIT_URL", "http://127.0.0.1:5173")


def _is_windows() -> bool:
    return os.name == "nt"


def pid_file() -> pathlib.Path:
    """Legacy PID projection, resolved at call time for ATLAS_HOME isolation."""
    return supervision.legacy_pid_path(_SERVICE)


def state_file() -> pathlib.Path:
    return supervision.state_path(_SERVICE)


def _parse_port(url: str) -> int:
    parsed = urllib.parse.urlparse(url)
    try:
        return parsed.port or 5173
    except ValueError as exc:
        raise ValueError(f"ATLAS_COCKPIT_URL has an invalid port: {url!r}") from exc


def _parse_host(url: str) -> str:
    return urllib.parse.urlparse(url).hostname or "127.0.0.1"


def _using_dist_server() -> bool:
    return _DIST_INDEX.is_file() and _DIST_SERVER.is_file()


def _health_payload(timeout: float = 1.0) -> dict[str, object] | None:
    """Return only the production server's typed identity response."""
    try:
        request = urllib.request.Request(
            f"{COCKPIT_URL.rstrip('/')}/health",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            if status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("service") != _HEALTH_SERVICE:
        return None
    return payload


def _dev_marker_ok(timeout: float = 1.0) -> bool:
    """Recognize Vite preview without accepting an arbitrary HTTP listener."""
    try:
        with urllib.request.urlopen(f"{COCKPIT_URL.rstrip('/')}/", timeout=timeout) as response:
            if getattr(response, "status", response.getcode()) != 200:
                return False
            body = response.read(256 * 1024).decode("utf-8", errors="replace")
    except Exception:
        return False
    return _DEV_HTML_MARKER in body


def health_ok(timeout: float = 1.0) -> bool:
    """Fail closed on wrong listeners; production requires a service identity."""
    if _health_payload(timeout) is not None:
        return True
    return not _using_dist_server() and _dev_marker_ok(timeout)


def _command(host: str, port: int) -> list[str]:
    if _using_dist_server():
        node = shutil.which("node") or "node"
        return [node, str(_DIST_SERVER), "--port", str(port), "--host", host]
    npm = "npm.cmd" if _is_windows() else "npm"
    return [npm, "run", "preview", "--", "--port", str(port), "--host", host]


def _load_record() -> supervision.ServiceLaunchRecord | None:
    return supervision.load_launch_record(state_file())


def _remove_state() -> None:
    state_file().unlink(missing_ok=True)
    pid_file().unlink(missing_ok=True)


def _health_kind(timeout: float = 0.35) -> str:
    if _health_payload(timeout) is not None:
        return "production"
    if not _using_dist_server() and _dev_marker_ok(timeout):
        return "development"
    return "none"


def status() -> dict[str, object]:
    """Return a JSON-stable process, endpoint, and ownership status."""
    host, port = _parse_host(COCKPIT_URL), _parse_port(COCKPIT_URL)
    health = _health_kind()
    try:
        record = _load_record()
    except supervision.ServiceStateError as exc:
        return {
            "schema_version": supervision.SCHEMA_VERSION,
            "service": _HEALTH_SERVICE,
            "state": "invalid_state",
            "running": False,
            "ready": False,
            "pid": None,
            "health": health,
            "remediation": f"inspect the retained service record: {exc}",
        }
    if record is None:
        legacy_pid = supervision.read_legacy_pid(pid_file())
        port_observation = supervision.observe_port(host, port)
        if health != "none":
            state = "unmanaged_ready"
        elif port_observation.listening:
            state = "wrong_listener"
        elif legacy_pid is not None:
            observed = supervision.observe_process(legacy_pid)
            state = "legacy_unverifiable" if observed.exists else "stale_legacy_state"
        else:
            state = "stopped"
        return {
            "schema_version": supervision.SCHEMA_VERSION,
            "service": _HEALTH_SERVICE,
            "state": state,
            "running": health != "none",
            "ready": health != "none",
            "pid": legacy_pid,
            "health": health,
            "port": port_observation.to_dict(),
            "remediation": (
                "stop the listener or choose another ATLAS_COCKPIT_URL"
                if state == "wrong_listener"
                else None
            ),
        }
    observed = supervision.observe_service(
        record,
        process_observer=supervision.observe_process,
        port_observer=supervision.observe_port,
    )
    state = observed.state
    if observed.identity and observed.identity.matches:
        if health != "none":
            state = "ready"
        elif observed.port and observed.port.listening:
            state = "wrong_listener"
        else:
            state = "starting"
    result = observed.to_dict()
    result.update(
        {
            "service": _HEALTH_SERVICE,
            "state": state,
            "running": state in {"ready", "starting"},
            "ready": state == "ready",
            "health": health,
        }
    )
    return result


def _observe_spawn(pid: int, timeout: float = 1.5) -> supervision.ProcessObservation:
    deadline = time.monotonic() + timeout
    observation = supervision.observe_process(pid)
    while observation.exists and not observation.identity_available and time.monotonic() < deadline:
        time.sleep(0.025)
        observation = supervision.observe_process(pid)
    return observation


def _terminate_spawn(proc: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(OSError):
        if _is_windows():
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        else:
            _signal_posix_process_tree(proc.pid)


def _signal_posix_process_tree(pid: int) -> None:
    """Signal the detached POSIX process group (kept patchable on Windows CI)."""
    killpg = getattr(os, "killpg", None)
    if killpg is None:  # pragma: no cover - a POSIX-only production branch
        raise OSError("process-group signalling is unavailable")
    killpg(pid, signal.SIGTERM)


def start(poll_seconds: float = 15.0) -> tuple[bool, str]:
    """Start a uniquely identified cockpit process under a bounded lock."""
    host, port = _parse_host(COCKPIT_URL), _parse_port(COCKPIT_URL)
    if health_ok():
        return True, "cockpit already running"
    try:
        with supervision.service_lock(_SERVICE):
            current = status()
            if current["ready"]:
                return True, "cockpit already running"
            if current["state"] in {
                "wrong_listener",
                "identity_mismatch",
                "unverifiable",
                "invalid_state",
                "legacy_unverifiable",
            }:
                return False, f"cockpit start blocked: {current['state']}"
            if current["state"] in {"stopped", "stale_legacy_state"}:
                recover()

            command = _command(host, port)
            kwargs: dict[str, object] = {}
            if _is_windows():
                kwargs["creationflags"] = (
                    DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
                )
            else:
                kwargs["start_new_session"] = True
            log = supervision.open_sensitive_log(supervision.log_path(_SERVICE))
            try:
                proc = subprocess.Popen(
                    command,
                    cwd=str(_COCKPIT_DIR),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    **kwargs,
                )
            finally:
                log.close()

            observation = _observe_spawn(proc.pid)
            if proc.poll() is not None or not observation.exists:
                tail = supervision.sanitized_log_tail(supervision.log_path(_SERVICE))
                detail = f": {tail.text}" if tail.text else ""
                return False, f"cockpit exited during startup{detail}"
            if (
                not observation.identity_available
                or observation.executable_path is None
                or observation.process_creation_time is None
            ):
                _terminate_spawn(proc)
                return False, "cockpit process identity could not be recorded safely"

            record = supervision.create_launch_record(
                service=_SERVICE,
                pid=proc.pid,
                executable_path=observation.executable_path,
                process_creation_time=observation.process_creation_time,
                argv=command,
                host=host,
                port=port,
                sensitive_log_path=supervision.log_path(_SERVICE),
            )
            supervision.write_launch_record(record, state_file())
            pid_file().write_text(str(proc.pid), encoding="utf-8")

            deadline = time.monotonic() + poll_seconds
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    _remove_state()
                    tail = supervision.sanitized_log_tail(supervision.log_path(_SERVICE))
                    detail = f": {tail.text}" if tail.text else ""
                    return False, f"cockpit exited during startup{detail}"
                if health_ok():
                    return True, f"cockpit started (pid {proc.pid}) on {COCKPIT_URL}"
                time.sleep(min(0.5, max(0.01, deadline - time.monotonic())))
            return False, "cockpit did not become healthy in time; service state retained"
    except supervision.ServiceLockBusy:
        return False, "cockpit lifecycle operation already in progress"


def _wait_for_record_exit(record: supervision.ServiceLaunchRecord, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not supervision.observe_process(record.pid).exists:
            return True
        time.sleep(0.1)
    return not supervision.observe_process(record.pid).exists


def stop() -> tuple[bool, str]:
    """Stop only the exact process instance recorded by start()."""
    try:
        with supervision.service_lock(_SERVICE):
            try:
                record = _load_record()
            except supervision.ServiceStateError as exc:
                return False, f"invalid service state retained; refusing to stop: {exc}"
            if record is None:
                legacy_pid = supervision.read_legacy_pid(pid_file())
                if legacy_pid is None:
                    if pid_file().exists():
                        pid_file().unlink(missing_ok=True)
                        return False, "invalid pid file (removed)"
                    return False, "no pid file; cockpit not managed here"
                if not supervision.observe_process(legacy_pid).exists:
                    pid_file().unlink(missing_ok=True)
                    return False, f"cockpit process already gone (pid {legacy_pid}, removed)"
                return False, "legacy pid has no process identity; refusing to stop (state retained)"

            observation = supervision.observe_process(record.pid)
            identity = supervision.compare_process_identity(record, observation)
            if not observation.exists:
                _remove_state()
                return False, f"cockpit process already gone (pid {record.pid}, removed)"
            if not identity.matches:
                return False, (
                    f"cockpit process identity {identity.reason}; refusing to stop "
                    "(state retained)"
                )
            try:
                if _is_windows():
                    result = subprocess.run(
                        ["taskkill", "/PID", str(record.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                    )
                    if result.returncode != 0:
                        return False, (
                            f"failed to stop cockpit process tree (pid {record.pid}); "
                            "service state retained"
                        )
                else:
                    _signal_posix_process_tree(record.pid)
            except OSError as exc:
                return False, f"failed to stop cockpit process tree (pid {record.pid}): {exc}"
            if not _wait_for_record_exit(record):
                return False, (
                    f"cockpit process tree still running (pid {record.pid}); "
                    "service state retained"
                )
            _remove_state()
            return True, f"stopped (pid {record.pid})"
    except supervision.ServiceLockBusy:
        return False, "cockpit lifecycle operation already in progress"


def recover() -> dict[str, object]:
    """Remove state only when it cannot refer to a live process instance."""
    try:
        record = _load_record()
    except supervision.ServiceStateError as exc:
        return {"recovered": False, "reason": "invalid_state", "detail": str(exc)}
    if record is not None:
        observation = supervision.observe_process(record.pid)
        if observation.exists:
            return {"recovered": False, "reason": "process_exists", "pid": record.pid}
        _remove_state()
        return {"recovered": True, "reason": "stale_state_removed", "pid": record.pid}
    legacy_pid = supervision.read_legacy_pid(pid_file())
    if legacy_pid is None:
        pid_file().unlink(missing_ok=True)
        return {"recovered": False, "reason": "no_state"}
    if supervision.observe_process(legacy_pid).exists:
        return {"recovered": False, "reason": "legacy_process_exists", "pid": legacy_pid}
    pid_file().unlink(missing_ok=True)
    return {"recovered": True, "reason": "stale_legacy_state_removed", "pid": legacy_pid}
