"""Tests for atlas_runtime.run_service.

Fixtures from conftest.py (injected by name — do NOT import):
  db   — in-memory SQLite, WAL + FK ON + 0001_core.sql applied
  lock — threading.Lock()

Local mission_id fixture inserts a minimal missions row with status="pending"
so FK constraints on runs.mission_id are satisfied. This is separate from the
conftest.py run_id fixture (which inserts a mission + run in "running" state).
"""
import datetime
import uuid

import pytest

from atlas_runtime import run_service


@pytest.fixture(name="mission_id")
def mission_id_fixture(db):
    """Insert a minimal missions row with status='pending' and return the id.

    Follows the conftest.py run_id_fixture pattern exactly so FK constraints
    on runs.mission_id are satisfied when PRAGMA foreign_keys = ON.
    """
    mid = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (mid, "test-mission", "", "pending", "", now, now),
    )
    db.commit()
    return mid


def test_start_run_creates_run_row(db, lock, mission_id):
    """start_run() inserts a row into the runs table."""
    run = run_service.start_run(db, lock, mission_id=mission_id)
    count = db.execute(
        "SELECT COUNT(*) FROM runs WHERE id=?", (run.id,)
    ).fetchone()[0]
    assert count == 1


def test_start_run_emits_audit_event(db, lock, mission_id):
    """start_run() emits at least one AuditEvent."""
    run = run_service.start_run(db, lock, mission_id=mission_id)
    count = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=?", (run.id,)
    ).fetchone()[0]
    assert count >= 1


def test_start_run_updates_mission_status_to_running(db, lock, mission_id):
    """start_run() transitions the parent mission from pending to running."""
    run = run_service.start_run(db, lock, mission_id=mission_id)
    status = db.execute(
        "SELECT status FROM missions WHERE id=?", (mission_id,)
    ).fetchone()[0]
    assert status == "running"


def test_complete_run_succeeded(db, lock, mission_id):
    """complete_run(status='succeeded') sets run + mission to succeeded with finish timestamp."""
    run = run_service.start_run(db, lock, mission_id=mission_id)
    run_service.complete_run(
        db, lock, run_id=run.id, mission_id=mission_id, status="succeeded"
    )
    row = db.execute(
        "SELECT status, finished_at FROM runs WHERE id=?", (run.id,)
    ).fetchone()
    assert row[0] == "succeeded"
    assert row[1] is not None
    mission_status = db.execute(
        "SELECT status FROM missions WHERE id=?", (mission_id,)
    ).fetchone()[0]
    assert mission_status == "succeeded"


def test_complete_run_failed(db, lock, mission_id):
    """complete_run(status='failed') sets run + mission to failed with finish timestamp."""
    run = run_service.start_run(db, lock, mission_id=mission_id)
    run_service.complete_run(
        db, lock, run_id=run.id, mission_id=mission_id, status="failed"
    )
    row = db.execute(
        "SELECT status, finished_at FROM runs WHERE id=?", (run.id,)
    ).fetchone()
    assert row[0] == "failed"
    assert row[1] is not None
    mission_status = db.execute(
        "SELECT status FROM missions WHERE id=?", (mission_id,)
    ).fetchone()[0]
    assert mission_status == "failed"


def test_cancel_run_sets_cancelled(db, lock, mission_id):
    """cancel_run() transitions run to cancelled and emits at least 2 audit events."""
    run = run_service.start_run(db, lock, mission_id=mission_id)
    run_service.cancel_run(db, lock, run_id=run.id, mission_id=mission_id)
    run_status = db.execute(
        "SELECT status FROM runs WHERE id=?", (run.id,)
    ).fetchone()[0]
    assert run_status == "cancelled"
    count = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=?", (run.id,)
    ).fetchone()[0]
    assert count >= 2


def test_cancel_preserves_existing_audit_events(db, lock, mission_id):
    """cancel_run() does not delete existing audit_events rows."""
    from atlas_runtime.audit_service import emit

    run = run_service.start_run(db, lock, mission_id=mission_id)
    # Emit a manual tool_call event (simulating partial execution)
    emit(db, lock, run_id=run.id, event_type="tool_call", data={"tool": "Read"})
    count_before = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=?", (run.id,)
    ).fetchone()[0]
    run_service.cancel_run(db, lock, run_id=run.id, mission_id=mission_id)
    count_after = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=?", (run.id,)
    ).fetchone()[0]
    assert count_after >= count_before
    assert count_after >= 2


def test_cancel_already_terminal_raises(db, lock, mission_id):
    """cancel_run() on an already-succeeded run raises ValueError."""
    run = run_service.start_run(db, lock, mission_id=mission_id)
    run_service.complete_run(
        db, lock, run_id=run.id, mission_id=mission_id, status="succeeded"
    )
    with pytest.raises(ValueError):
        run_service.cancel_run(db, lock, run_id=run.id, mission_id=mission_id)


def test_fail_run_sets_failed(db, lock, mission_id):
    """fail_run() transitions run and mission to failed state."""
    run = run_service.start_run(db, lock, mission_id=mission_id)
    run_service.fail_run(db, lock, run_id=run.id, mission_id=mission_id, summary="error msg")
    run_row = db.execute(
        "SELECT status FROM runs WHERE id=?", (run.id,)
    ).fetchone()
    assert run_row[0] == "failed"
    mission_status = db.execute(
        "SELECT status FROM missions WHERE id=?", (mission_id,)
    ).fetchone()[0]
    assert mission_status == "failed"


def test_dispatch_subagent_emits_subagent_run(db, lock, mission_id):
    """dispatch_subagent() emits a subagent_run AuditEvent (RUNTIME-06)."""
    from atlas_runtime import subagent_service

    run = run_service.start_run(db, lock, mission_id=mission_id)
    subagent_service.dispatch_subagent(
        db, lock, run_id=run.id, role="researcher"
    )
    count = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=? AND event_type='subagent_run'",
        (run.id,),
    ).fetchone()[0]
    assert count >= 1
