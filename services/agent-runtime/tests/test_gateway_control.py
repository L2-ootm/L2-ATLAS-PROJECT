"""Tests for gateway_control stop() PID-reuse guard and the cold-start reaper.

stop() must never kill a PID that is dead or that belongs to a non-gateway
process (PID reuse after a crash). reap_orphan_runs() is the fail-open wrapper
that gives the subprocess-execution mode the same startup reconciliation the
runtime daemon already had.
"""

from __future__ import annotations

import os
import sqlite3

import pytest

from atlas_runtime import gateway_control, service_supervision


@pytest.fixture()
def pid_file(tmp_path, monkeypatch):
    """Redirect the PID file by pointing ATLAS_HOME at a tmp dir.

    Drives the same env var operators set rather than patching a module
    attribute, so these tests also prove `pid_file()` honors ATLAS_HOME —
    the defect that made `start` and `stop` disagree about which home owns
    the gateway.
    """
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    return tmp_path / "gateway.pid"


def test_stop_without_pid_file(pid_file) -> None:
    ok, message = gateway_control.stop()
    assert not ok
    assert "no pid file" in message


def test_stop_invalid_pid_file_removed(pid_file) -> None:
    pid_file.write_text("not-a-pid")
    ok, message = gateway_control.stop()
    assert not ok
    assert "invalid pid file" in message
    assert not pid_file.exists()


def _record(tmp_path, *, pid: int = 12345):
    record = service_supervision.create_launch_record(
        service="gateway",
        pid=pid,
        executable_path="C:/atlas/atlas-gateway.exe",
        process_creation_time=99,
        argv=["C:/atlas/atlas-gateway.exe"],
        host="127.0.0.1",
        port=8484,
        sensitive_log_path=tmp_path / "logs" / "gateway.log",
    )
    service_supervision.write_launch_record(record, tmp_path / "gateway.service.json")
    (tmp_path / "gateway.pid").write_text(str(pid))
    return record


def _observation(record, *, exists=True, executable=None, creation=None):
    return service_supervision.ProcessObservation(
        pid=record.pid,
        exists=exists,
        identity_available=exists,
        executable_path=executable or record.executable_path if exists else None,
        process_creation_time=creation or record.process_creation_time
        if exists
        else None,
    )


def test_stop_dead_pid_removes_stale_file(pid_file, monkeypatch) -> None:
    record = _record(pid_file.parent, pid=4_194_304)
    monkeypatch.setattr(
        service_supervision,
        "observe_process",
        lambda pid: _observation(record, exists=False),
    )
    ok, message = gateway_control.stop()
    assert not ok
    assert "not running" in message
    assert not pid_file.exists()
    assert not (pid_file.parent / "gateway.service.json").exists()


def test_stop_refuses_reused_pid(pid_file, monkeypatch) -> None:
    record = _record(pid_file.parent, pid=os.getpid())
    monkeypatch.setattr(
        service_supervision,
        "observe_process",
        lambda pid: _observation(record, executable="C:/Python/python.exe"),
    )
    killed: list[int] = []
    monkeypatch.setattr(gateway_control.os, "kill", lambda pid, sig: killed.append(pid))
    monkeypatch.setattr(
        gateway_control.subprocess, "run", lambda *a, **k: killed.append(-1)
    )
    ok, message = gateway_control.stop()
    assert not ok
    assert "refusing to kill" in message
    assert killed == []
    assert pid_file.exists()
    assert (pid_file.parent / "gateway.service.json").exists()


def test_stop_kills_matching_gateway_pid(pid_file, monkeypatch) -> None:
    record = _record(pid_file.parent)
    observations = iter([_observation(record), _observation(record, exists=False)])
    monkeypatch.setattr(
        service_supervision, "observe_process", lambda pid: next(observations)
    )
    killed: list[int] = []
    monkeypatch.setattr(gateway_control.os, "kill", lambda pid, sig: killed.append(pid))
    monkeypatch.setattr(
        gateway_control.subprocess,
        "run",
        lambda cmd, **k: killed.append(int(cmd[2])) if cmd[0] == "taskkill" else None,
    )
    ok, message = gateway_control.stop()
    assert ok
    assert "stopped (pid 12345)" in message
    assert killed == [12345]
    assert not pid_file.exists()
    assert not (pid_file.parent / "gateway.service.json").exists()


def test_stop_retains_state_when_termination_cannot_be_verified(
    pid_file, monkeypatch
) -> None:
    record = _record(pid_file.parent)
    monkeypatch.setattr(
        service_supervision, "observe_process", lambda pid: _observation(record)
    )
    monkeypatch.setattr(
        gateway_control.time, "monotonic", iter([0.0, 0.0, 6.0]).__next__
    )
    monkeypatch.setattr(gateway_control.os, "kill", lambda *args: None)
    monkeypatch.setattr(gateway_control.subprocess, "run", lambda *args, **kwargs: None)
    ok, message = gateway_control.stop()
    assert not ok
    assert "did not terminate" in message
    assert pid_file.exists()
    assert (pid_file.parent / "gateway.service.json").exists()


def test_health_rejects_wrong_http_service(monkeypatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def getcode(self):
            return 200

        def read(self, _limit):
            return b'{"service":"not-atlas"}'

    monkeypatch.setattr(
        gateway_control.urllib.request, "urlopen", lambda *a, **k: Response()
    )
    assert not gateway_control.health_ok()
    assert gateway_control.status()["state"] == "wrong_service"


def test_start_preflight_blocks_wrong_listener_before_reaping(monkeypatch) -> None:
    reaped: list[bool] = []
    monkeypatch.setattr(
        gateway_control,
        "status",
        lambda: {
            "running": False,
            "state": "wrong_service",
            "managed": False,
            "remediation": "another service owns the endpoint",
        },
    )
    monkeypatch.setattr(
        gateway_control, "reap_orphan_runs", lambda: reaped.append(True)
    )
    ok, message = gateway_control.start()
    assert not ok
    assert "preflight failed" in message
    assert reaped == []


def test_start_detects_child_exit_before_recording_identity(
    pid_file, monkeypatch
) -> None:
    class ExitedProcess:
        pid = 4242

        def poll(self):
            return 7

    monkeypatch.setattr(
        gateway_control,
        "status",
        lambda: {
            "running": False,
            "state": "stopped",
            "managed": False,
            "remediation": None,
        },
    )
    monkeypatch.setattr(gateway_control, "gateway_binary", lambda: __file__)
    monkeypatch.setattr(
        service_supervision,
        "observe_port",
        lambda *a, **k: service_supervision.PortObservation("127.0.0.1", 8484, False),
    )
    monkeypatch.setattr(
        service_supervision,
        "observe_process",
        lambda pid: service_supervision.ProcessObservation(
            pid, False, False, error="process_dead"
        ),
    )
    monkeypatch.setattr(
        gateway_control.subprocess, "Popen", lambda *a, **k: ExitedProcess()
    )
    ok, message = gateway_control.start(poll_seconds=0.1)
    assert not ok
    assert "exited before its identity" in message
    assert not (pid_file.parent / "gateway.service.json").exists()


def test_recover_removes_only_proven_dead_state(pid_file, monkeypatch) -> None:
    record = _record(pid_file.parent)
    monkeypatch.setattr(
        service_supervision,
        "observe_process",
        lambda pid: _observation(record, exists=False),
    )
    ok, message = gateway_control.recover()
    assert ok
    assert "dead pid" in message
    assert not pid_file.exists()


def test_pid_process_name_resolves_current_process() -> None:
    name = gateway_control._pid_process_name(os.getpid())
    assert name is not None
    assert "python" in name.lower()


def test_reap_orphan_runs_fail_open(monkeypatch) -> None:
    from atlas_runtime import db

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "connect", boom)
    assert gateway_control.reap_orphan_runs() == 0


def test_reap_orphan_runs_reclaims_crash_left_run(tmp_path, monkeypatch) -> None:
    """End-to-end against a real temp DB: a running run bound to a session with a
    stale heartbeat is cancelled and its session reclaimed by the sweep."""
    import datetime
    import uuid

    from atlas_runtime import db

    db_path = tmp_path / "atlas-test.db"
    conn = db.connect(db_path)
    db.apply_migrations(conn)

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    stale = "2020-01-01T00:00:00+00:00"
    sid, mid, rid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    conn.execute(
        "INSERT INTO surface_sessions"
        "(id, surface_kind, surface_session_id, workspace_kind, workspace_root, run_id, "
        "agent, model_provider, model_id, permission_mode, prompt_version, "
        "tool_catalog_version, context_policy_version, state, heartbeat_at, "
        "created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            sid,
            "tui",
            "surf",
            "global",
            "/tmp/atlas",
            None,
            "atlas",
            "anthropic",
            "claude-opus-4",
            "ask",
            "1.0.0",
            "1.0.0",
            "1.0.0",
            "active",
            stale,
            now,
            now,
        ),
    )
    conn.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (mid, "orphan", "", "running", "", now, now),
    )
    conn.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?,?,?,?,?,?,?)",
        (rid, mid, sid, "running", now, None, ""),
    )
    conn.commit()
    conn.close()

    original_connect = db.connect
    monkeypatch.setattr(db, "connect", lambda path=None: original_connect(db_path))

    reclaimed = gateway_control.reap_orphan_runs(ttl_seconds=90.0)
    assert reclaimed == 1

    check = original_connect(db_path)
    status = check.execute("SELECT status FROM runs WHERE id=?", (rid,)).fetchone()[0]
    assert status == "cancelled"
    check.close()
