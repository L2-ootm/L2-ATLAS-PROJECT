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
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from atlas_runtime import config_service, provisioning, service_supervision
from atlas_runtime.db import MIGRATIONS_DIR

# services/agent-runtime (so the gateway's spawned CLI can import atlas_runtime).
_AGENT_RUNTIME_DIR = pathlib.Path(__file__).resolve().parents[1]

GATEWAY_URL = os.environ.get("ATLAS_GATEWAY_URL", "http://127.0.0.1:8484")
SERVICE_KEY = "gateway"
HEALTH_SERVICE = "atlas-gateway"


def pid_file() -> pathlib.Path:
    """`<ATLAS home>/gateway.pid`, resolved at CALL time.

    This was `PID_FILE = pathlib.Path.home() / ".atlas" / "gateway.pid"`
    evaluated at import time, which ignored ATLAS_HOME entirely and froze the
    answer at the first import. Anything that set ATLAS_HOME afterwards — a
    test, a spawned subprocess, an operator with state on another volume — still
    had its PID file written into the real `~/.atlas`, so `atlas gateway stop`
    looked in one home while `start` had recorded the PID in another.

    Deliberately a function and not a module constant: the whole defect was a
    path answered once instead of on demand.
    """
    return config_service.atlas_home() / "gateway.pid"


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


def _health_probe(timeout: float = 1.0) -> tuple[bool, str | None, str | None]:
    """Return health, advertised service identity, and a bounded error code."""
    try:
        with urllib.request.urlopen(f"{GATEWAY_URL}/health", timeout=timeout) as resp:
            if getattr(resp, "status", resp.getcode()) != 200:
                return False, None, "http_status"
            payload = json.loads(resp.read(16_385))
            if not isinstance(payload, dict):
                return False, None, "invalid_payload"
            service = payload.get("service")
            if not isinstance(service, str):
                return False, None, "missing_service_identity"
            if service != HEALTH_SERVICE:
                return False, service, "wrong_service_identity"
            return True, service, None
    except Exception as exc:
        return False, None, type(exc).__name__


def health_ok(timeout: float = 1.0) -> bool:
    return _health_probe(timeout)[0]


def _endpoint() -> tuple[str, int]:
    parsed = urllib.parse.urlparse(GATEWAY_URL)
    return parsed.hostname or "127.0.0.1", parsed.port or 8484


def _remove_state() -> None:
    service_supervision.state_path(SERVICE_KEY).unlink(missing_ok=True)
    pid_file().unlink(missing_ok=True)


def status() -> dict[str, object]:
    """Return a JSON-stable, identity-aware gateway status."""
    health, advertised_service, health_error = _health_probe()
    health_status = {
        "ok": health,
        "service": advertised_service,
        "error": health_error,
    }
    state_file = service_supervision.state_path(SERVICE_KEY)
    try:
        record = service_supervision.load_launch_record(state_file)
    except service_supervision.ServiceStateError as exc:
        return {
            "schema_version": service_supervision.SCHEMA_VERSION,
            "service": SERVICE_KEY,
            "state": "corrupt_state",
            "running": False,
            "managed": True,
            "pid": service_supervision.read_legacy_pid(pid_file()),
            "health": health_status,
            "supervision": None,
            "remediation": f"inspect {state_file}: {exc}",
        }
    if record is None:
        legacy_pid = service_supervision.read_legacy_pid(pid_file())
        if health:
            state, remediation = (
                "unmanaged",
                "healthy gateway is not owned by this launcher",
            )
        elif advertised_service is not None:
            state, remediation = (
                "wrong_service",
                "another HTTP service owns the gateway endpoint",
            )
        elif legacy_pid is not None:
            state, remediation = (
                "legacy_unverifiable",
                "run `atlas gateway recover` after inspecting the PID",
            )
        else:
            state, remediation = "stopped", None
        return {
            "schema_version": service_supervision.SCHEMA_VERSION,
            "service": SERVICE_KEY,
            "state": state,
            "running": health,
            "managed": False,
            "pid": legacy_pid,
            "health": health_status,
            "supervision": None,
            "remediation": remediation,
        }

    observed = service_supervision.observe_service(record)
    if advertised_service is not None and not health:
        state = "wrong_service"
    elif observed.state == "running" and health:
        state = "running"
    elif observed.state == "running":
        state = (
            "starting"
            if not observed.port or not observed.port.listening
            else "unhealthy"
        )
    else:
        state = observed.state
    return {
        "schema_version": service_supervision.SCHEMA_VERSION,
        "service": SERVICE_KEY,
        "state": state,
        "running": state == "running",
        "managed": True,
        "pid": record.pid,
        "health": health_status,
        "supervision": observed.to_dict(),
        "remediation": observed.remediation,
    }


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
    # The cashflow DB default must be the directory the cashflow app actually
    # runs from, resolved by the SAME resolver the sidecar uses. This used to be
    # `<root>/services/cashflow/dev.db`, which in a release install is
    # `versions/<version>/services/cashflow/dev.db` — inside the immutable
    # release directory. The app never writes there (provisioning mirrors it to
    # `<ATLAS home>/sidecars/cashflow` precisely so nothing is built inside a
    # release), so the gateway read an absent or stale file while the data sat
    # under ATLAS_HOME. It is also the one path that would put live state
    # somewhere the next update and `atlas versions prune` delete without
    # warning. `lib/db/index.ts` opens `path.join(process.cwd(), 'dev.db')`,
    # and cwd is the workspace — so workspace/dev.db is the real file.
    workspace, _mirrored = provisioning.resolve_workspace(
        provisioning.cashflow_component()
    )
    env.setdefault("ATLAS_CASHFLOW_DB_PATH", str(workspace / "dev.db"))
    if "ATLAS_CLI" not in env and " " not in sys.executable:
        env["ATLAS_CLI"] = f"{sys.executable} -m atlas_runtime.cli.main"
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{_AGENT_RUNTIME_DIR}{os.pathsep}{existing}"
            if existing
            else str(_AGENT_RUNTIME_DIR)
        )
    return env


def start_command_hint() -> str:
    """The exact terminal command to start the gateway (shown in the offline UI)."""
    return "atlas gateway start"


def reap_orphan_runs(ttl_seconds: float = 90.0) -> int:
    """Cold-start sweep (SURF-05): reclaim crash-left sessions and running runs.

    The daemon path (`atlas runtime serve`) already reconciles at startup, but the
    default gateway/subprocess execution mode never did — a process kill mid-run
    left the run stuck in 'running' forever. Called from start() only when the
    gateway was actually down (so nothing can be legitimately executing under a
    healthy gateway). Fail-open: startup must not break on a locked/absent DB.
    Returns the number of reclaimed sessions (0 on any failure).
    """
    import threading

    from atlas_runtime import db, surface_session_service

    try:
        conn = db.connect()
        try:
            reclaimed = surface_session_service.reconcile_orphans(
                conn, threading.Lock(), ttl_seconds=ttl_seconds
            )
            return len(reclaimed)
        finally:
            conn.close()
    except Exception:
        return 0


def start(poll_seconds: float = 15.0) -> tuple[bool, str]:
    """Start the gateway if not already healthy. Returns (ok, message)."""
    try:
        with service_supervision.service_lock(SERVICE_KEY):
            preflight = status()
            if preflight["running"]:
                return True, "gateway already running"
            if preflight["state"] in {
                "wrong_service",
                "corrupt_state",
                "identity_mismatch",
                "unverifiable",
                "legacy_unverifiable",
                "unhealthy",
                "starting",
            }:
                return False, (
                    f"gateway preflight failed ({preflight['state']}); "
                    f"{preflight.get('remediation') or 'inspect gateway status'}"
                )
            if preflight["state"] == "stopped" and preflight["managed"]:
                _remove_state()

            binary = gateway_binary()
            if not binary:
                return (
                    False,
                    "atlas-gateway binary not found; set ATLAS_GATEWAY_BIN or build it "
                    "(cd native/atlas-core-rs && cargo build --release)",
                )
            host, port = _endpoint()
            if service_supervision.observe_port(host, port).listening:
                return (
                    False,
                    f"gateway preflight failed; {host}:{port} is already listening",
                )

            # Only after ownership, binary and endpoint preflight is it safe to
            # mutate run state left by the previous gateway.
            reap_orphan_runs()
            argv = [str(pathlib.Path(binary).resolve())]
            kwargs: dict = {}
            if os.name == "nt":
                kwargs["creationflags"] = (
                    subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
                )
            else:
                kwargs["start_new_session"] = True
            log = service_supervision.open_sensitive_log(
                service_supervision.log_path(SERVICE_KEY)
            )
            try:
                proc = subprocess.Popen(
                    argv, stdout=log, stderr=log, env=_child_env(), **kwargs
                )
            finally:
                log.close()

            observation = service_supervision.observe_process(proc.pid)
            identity_deadline = time.monotonic() + min(2.0, max(0.1, poll_seconds))
            while (
                not observation.identity_available
                and proc.poll() is None
                and time.monotonic() < identity_deadline
            ):
                time.sleep(0.025)
                observation = service_supervision.observe_process(proc.pid)
            if proc.poll() is not None or not observation.identity_available:
                if proc.poll() is None:
                    proc.terminate()
                tail = service_supervision.sanitized_log_tail(
                    service_supervision.log_path(SERVICE_KEY)
                )
                detail = f": {tail.text}" if tail.text else ""
                return (
                    False,
                    f"gateway exited before its identity could be recorded{detail}",
                )

            record = service_supervision.create_launch_record(
                service=SERVICE_KEY,
                pid=proc.pid,
                executable_path=argv[0],
                process_creation_time=observation.process_creation_time or 0,
                argv=argv,
                host=host,
                port=port,
                sensitive_log_path=service_supervision.log_path(SERVICE_KEY),
            )
            initial_identity = service_supervision.compare_process_identity(
                record, observation
            )
            if not initial_identity.matches:
                proc.terminate()
                return (
                    False,
                    "gateway child identity did not match the requested binary "
                    f"({initial_identity.reason})",
                )
            service_supervision.write_launch_record(
                record, service_supervision.state_path(SERVICE_KEY)
            )
            pid_path = pid_file()
            pid_path.write_text(str(proc.pid), encoding="utf-8")

            deadline = time.monotonic() + poll_seconds
            while time.monotonic() < deadline:
                exit_code = proc.poll()
                if exit_code is not None:
                    _remove_state()
                    tail = service_supervision.sanitized_log_tail(record.log_path)
                    detail = f": {tail.text}" if tail.text else ""
                    return False, f"gateway exited early (code {exit_code}){detail}"
                probe_ok, advertised, error = _health_probe()
                if probe_ok:
                    return True, f"gateway started (pid {proc.pid}) on {GATEWAY_URL}"
                if advertised is not None:
                    return (
                        False,
                        f"gateway endpoint advertised {advertised!r}, not {HEALTH_SERVICE!r}",
                    )
                time.sleep(0.1)
            tail = service_supervision.sanitized_log_tail(record.log_path)
            detail = f"; log tail: {tail.text}" if tail.text else ""
            return False, f"gateway did not become healthy in time{detail}"
    except service_supervision.ServiceLockBusy:
        return False, "gateway lifecycle is busy; retry shortly"
    except (OSError, service_supervision.ServiceStateError) as exc:
        return False, f"gateway start failed: {type(exc).__name__}: {exc}"


def _pid_process_name(pid: int) -> str | None:
    """Best-effort image/command name for a live PID; None when not resolvable.

    Guards stop() against PID reuse: after a crash the recorded PID may now
    belong to an unrelated process, and killing it blind is destructive.
    """
    try:
        if os.name == "nt":
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                check=False,
                timeout=10,
            )
            out = (out.stdout or b"").decode("utf-8", errors="replace").strip()
            # CSV row: "image.exe","pid",... ; "INFO: No tasks..." when dead.
            if out.startswith('"'):
                return out.split('","')[0].strip('"')
            return None
        comm = pathlib.Path(f"/proc/{pid}/comm")
        if comm.exists():
            return comm.read_text().strip()
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        ).stdout.strip()
        return out or None
    except Exception:
        return None


def stop() -> tuple[bool, str]:
    """Stop only the exact process instance recorded by this launcher."""
    try:
        with service_supervision.service_lock(SERVICE_KEY):
            state_file = service_supervision.state_path(SERVICE_KEY)
            try:
                record = service_supervision.load_launch_record(state_file)
            except service_supervision.ServiceStateError as exc:
                return False, f"invalid gateway service state; refusing to kill: {exc}"
            if record is None:
                if pid_file().exists():
                    if service_supervision.read_legacy_pid(pid_file()) is None:
                        pid_file().unlink(missing_ok=True)
                        return False, "invalid pid file (removed)"
                    return (
                        False,
                        "legacy pid has no process identity; refusing to kill (state retained)",
                    )
                return False, "no pid file; gateway not managed here"

            observation = service_supervision.observe_process(record.pid)
            identity = service_supervision.compare_process_identity(record, observation)
            if not observation.exists:
                _remove_state()
                return False, f"pid {record.pid} not running (stale state removed)"
            if not identity.matches:
                return False, (
                    f"pid {record.pid} identity check failed ({identity.reason}) — "
                    "refusing to kill (state retained)"
                )
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(record.pid), "/F"],
                        check=False,
                        capture_output=True,
                        timeout=10,
                    )
                else:
                    os.kill(record.pid, 15)
            except (OSError, subprocess.SubprocessError) as exc:
                return False, (
                    f"failed to terminate pid {record.pid}: {type(exc).__name__}; "
                    "state retained"
                )

            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if not service_supervision.observe_process(record.pid).exists:
                    _remove_state()
                    return True, f"stopped (pid {record.pid})"
                time.sleep(0.05)
            return False, (
                f"pid {record.pid} did not terminate; refusing to remove state "
                "until termination is verified"
            )
    except service_supervision.ServiceLockBusy:
        return False, "gateway lifecycle is busy; retry shortly"


def recover() -> tuple[bool, str]:
    """Remove only state proven stale; never terminate a process."""
    try:
        with service_supervision.service_lock(SERVICE_KEY):
            state_file = service_supervision.state_path(SERVICE_KEY)
            try:
                record = service_supervision.load_launch_record(state_file)
            except service_supervision.ServiceStateError as exc:
                return False, f"gateway state is corrupt and was retained: {exc}"
            if record is not None:
                observation = service_supervision.observe_process(record.pid)
                if observation.exists:
                    return False, "gateway process may still exist; state retained"
                _remove_state()
                return True, f"removed stale gateway state for dead pid {record.pid}"
            legacy = service_supervision.read_legacy_pid(pid_file())
            if legacy is None:
                existed = pid_file().exists()
                pid_file().unlink(missing_ok=True)
                return (
                    True,
                    "removed invalid pid file"
                    if existed
                    else "gateway state already clean",
                )
            observation = service_supervision.observe_process(legacy)
            if observation.exists:
                return False, "legacy pid may still exist; state retained"
            pid_file().unlink(missing_ok=True)
            return True, f"removed stale legacy pid {legacy}"
    except service_supervision.ServiceLockBusy:
        return False, "gateway lifecycle is busy; retry shortly"
