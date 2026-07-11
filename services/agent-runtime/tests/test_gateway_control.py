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

from atlas_runtime import gateway_control


@pytest.fixture()
def pid_file(tmp_path, monkeypatch):
    path = tmp_path / "gateway.pid"
    monkeypatch.setattr(gateway_control, "PID_FILE", path)
    return path


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


def test_stop_dead_pid_removes_stale_file(pid_file, monkeypatch) -> None:
    pid_file.write_text("4194304")  # far beyond default pid ranges
    monkeypatch.setattr(gateway_control, "_pid_process_name", lambda pid: None)
    ok, message = gateway_control.stop()
    assert not ok
    assert "not running" in message
    assert not pid_file.exists()


def test_stop_refuses_reused_pid(pid_file, monkeypatch) -> None:
    # PID is alive but belongs to another process — must refuse to kill.
    pid_file.write_text(str(os.getpid()))
    monkeypatch.setattr(gateway_control, "_pid_process_name", lambda pid: "python.exe")
    killed: list[int] = []
    monkeypatch.setattr(gateway_control.os, "kill", lambda pid, sig: killed.append(pid))
    monkeypatch.setattr(
        gateway_control.subprocess, "run", lambda *a, **k: killed.append(-1)
    )
    ok, message = gateway_control.stop()
    assert not ok
    assert "refusing to kill" in message
    assert killed == []
    assert not pid_file.exists()


def test_stop_kills_matching_gateway_pid(pid_file, monkeypatch) -> None:
    pid_file.write_text("12345")
    monkeypatch.setattr(
        gateway_control, "_pid_process_name", lambda pid: "atlas-gateway.exe"
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
            sid, "tui", "surf", "global", "/tmp/atlas", None,
            "atlas", "anthropic", "claude-opus-4", "ask", "1.0.0",
            "1.0.0", "1.0.0", "active", stale, now, now,
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
