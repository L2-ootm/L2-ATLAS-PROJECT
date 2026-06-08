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
