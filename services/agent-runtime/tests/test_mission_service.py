"""Tests for atlas_runtime.mission_service.

Fixtures from conftest.py (injected by name — do NOT import):
  db   — in-memory SQLite, WAL + FK ON + 0001_core.sql applied
  lock — threading.Lock()
"""
import pytest

from atlas_runtime import mission_service


def test_create_mission_persists_row(db, lock):
    """create_mission() inserts exactly one row in the missions table."""
    from atlas_runtime.mission_service import create_mission

    mission = create_mission(db, lock, title="Test")
    count = db.execute(
        "SELECT COUNT(*) FROM missions WHERE id=?", (mission.id,)
    ).fetchone()[0]
    assert count == 1


def test_create_mission_returns_mission_model(db, lock):
    """create_mission() returns a Mission instance with the correct title."""
    from atlas_core.schemas.core import Mission
    from atlas_runtime.mission_service import create_mission

    mission = create_mission(db, lock, title="My Mission")
    assert isinstance(mission, Mission)
    assert mission.title == "My Mission"


def test_get_mission_returns_none_for_missing(db):
    """get_mission() returns None when the mission_id does not exist."""
    import uuid
    from atlas_runtime.mission_service import get_mission

    result = get_mission(db, str(uuid.uuid4()))
    assert result is None


def test_list_missions_empty(db):
    """list_missions() returns an empty list when no missions exist."""
    from atlas_runtime.mission_service import list_missions

    result = list_missions(db)
    assert result == []


def test_create_mission_status_is_pending(db, lock):
    """create_mission() creates the mission in pending status."""
    from atlas_runtime.mission_service import create_mission

    mission = create_mission(db, lock, title="Status Test")
    assert mission.status == "pending"


def test_archive_mission_marks_succeeded_and_sets_retention(db, lock):
    from atlas_runtime.mission_service import archive_mission, create_mission

    mission = create_mission(db, lock, title="Archive Test")
    db.execute("UPDATE missions SET status='succeeded' WHERE id=?", (mission.id,))
    db.commit()

    archived = archive_mission(db, lock, mission_id=mission.id, delete_after_days=7)

    row = db.execute(
        "SELECT archived_at, delete_after FROM mission_archive WHERE mission_id=?",
        (mission.id,),
    ).fetchone()
    assert archived.status == "archived"
    assert row is not None
    assert row[0] < row[1]


def test_archive_mission_rejects_pending(db, lock):
    from atlas_runtime.mission_service import archive_mission, create_mission

    mission = create_mission(db, lock, title="Pending Archive")

    with pytest.raises(ValueError, match="Cannot archive"):
        archive_mission(db, lock, mission_id=mission.id, delete_after_days=7)


@pytest.mark.parametrize("terminal", ["failed", "cancelled"])
def test_retry_mission_reopens_terminal_state(db, lock, terminal):
    """retry_mission() cycles a failed/cancelled mission back to pending."""
    from atlas_runtime.mission_service import create_mission, retry_mission

    mission = create_mission(db, lock, title="Retry Test")
    db.execute("UPDATE missions SET status=? WHERE id=?", (terminal, mission.id))
    db.commit()

    reopened = retry_mission(db, lock, mission_id=mission.id)
    assert reopened.status == "pending"
    row = db.execute("SELECT status FROM missions WHERE id=?", (mission.id,)).fetchone()
    assert row[0] == "pending"


@pytest.mark.parametrize("state", ["pending", "running", "succeeded"])
def test_retry_mission_rejects_non_terminal(db, lock, state):
    """retry_mission() refuses any mission not failed/cancelled."""
    from atlas_runtime.mission_service import create_mission, retry_mission

    mission = create_mission(db, lock, title="Bad Retry")
    db.execute("UPDATE missions SET status=? WHERE id=?", (state, mission.id))
    db.commit()

    with pytest.raises(ValueError, match="Cannot retry"):
        retry_mission(db, lock, mission_id=mission.id)


def test_retry_mission_preserves_prior_runs(db, lock):
    """Reopening a mission leaves its earlier run rows attached as history."""
    from atlas_runtime.mission_service import create_mission, retry_mission
    from atlas_runtime import run_service

    mission = create_mission(db, lock, title="History Test")
    run = run_service.start_run(db, lock, mission_id=mission.id)
    run_service.complete_run(
        db, lock, run_id=run.id, mission_id=mission.id, status="failed"
    )

    retry_mission(db, lock, mission_id=mission.id)

    assert db.execute("SELECT 1 FROM runs WHERE id=?", (run.id,)).fetchone() is not None
    # After reopen, start_run's pending precondition is satisfied again.
    new_run = run_service.start_run(db, lock, mission_id=mission.id)
    assert new_run.id != run.id


def test_purge_expired_archives_deletes_dependents(db, lock):
    from atlas_runtime.mission_service import archive_mission, create_mission, purge_expired_archives
    from atlas_runtime import run_service

    mission = create_mission(db, lock, title="Purge Test")
    run = run_service.start_run(db, lock, mission_id=mission.id)
    run_service.complete_run(
        db, lock, run_id=run.id, mission_id=mission.id, status="succeeded"
    )
    archive_mission(db, lock, mission_id=mission.id, delete_after_days=1)
    db.execute(
        "UPDATE mission_archive SET delete_after='2000-01-01T00:00:00+00:00' WHERE mission_id=?",
        (mission.id,),
    )
    db.commit()

    assert purge_expired_archives(db, lock, now="2026-01-01T00:00:00+00:00") == 1
    assert db.execute("SELECT 1 FROM missions WHERE id=?", (mission.id,)).fetchone() is None
    assert db.execute("SELECT 1 FROM runs WHERE id=?", (run.id,)).fetchone() is None
