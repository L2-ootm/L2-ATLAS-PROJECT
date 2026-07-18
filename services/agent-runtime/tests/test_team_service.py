"""Tests for team_service.py: agent presets and team roster CRUD."""
from __future__ import annotations

import sqlite3
import threading

import pytest

from atlas_runtime import team_service


def _make_preset(db: sqlite3.Connection, lock: threading.Lock, name: str = "researcher"):
    return team_service.create_preset(
        db, lock,
        name=name,
        role_label="researcher",
        goal_template="Research {topic} and report findings.",
    )


def test_create_and_get_preset(db: sqlite3.Connection, lock: threading.Lock) -> None:
    preset = _make_preset(db, lock)
    assert preset["name"] == "researcher"
    assert preset["mode"] == "joined"
    fetched = team_service.get_preset(db, preset["id"])
    assert fetched == preset


def test_create_preset_rejects_empty_fields(db: sqlite3.Connection, lock: threading.Lock) -> None:
    with pytest.raises(ValueError):
        team_service.create_preset(db, lock, name="", role_label="x", goal_template="y")
    with pytest.raises(ValueError):
        team_service.create_preset(db, lock, name="x", role_label="", goal_template="y")
    with pytest.raises(ValueError):
        team_service.create_preset(db, lock, name="x", role_label="y", goal_template="")


def test_create_preset_rejects_duplicate_name(db: sqlite3.Connection, lock: threading.Lock) -> None:
    _make_preset(db, lock, name="dup")
    with pytest.raises(ValueError):
        _make_preset(db, lock, name="dup")


def test_create_preset_rejects_invalid_mode(db: sqlite3.Connection, lock: threading.Lock) -> None:
    with pytest.raises(ValueError):
        team_service.create_preset(
            db, lock, name="x", role_label="y", goal_template="z", mode="bogus"
        )


def test_update_preset(db: sqlite3.Connection, lock: threading.Lock) -> None:
    preset = _make_preset(db, lock)
    updated = team_service.update_preset(db, lock, preset["id"], model="gpt-5")
    assert updated["model"] == "gpt-5"
    assert updated["updated_at"] >= preset["updated_at"]


def test_update_preset_rejects_unknown_field(db: sqlite3.Connection, lock: threading.Lock) -> None:
    preset = _make_preset(db, lock)
    with pytest.raises(ValueError):
        team_service.update_preset(db, lock, preset["id"], bogus_field="x")


def test_update_preset_missing_raises(db: sqlite3.Connection, lock: threading.Lock) -> None:
    with pytest.raises(ValueError):
        team_service.update_preset(db, lock, "preset-missing", model="x")


def test_delete_preset(db: sqlite3.Connection, lock: threading.Lock) -> None:
    preset = _make_preset(db, lock)
    assert team_service.delete_preset(db, lock, preset["id"]) is True
    assert team_service.get_preset(db, preset["id"]) is None


def test_delete_preset_in_use_raises(db: sqlite3.Connection, lock: threading.Lock) -> None:
    preset = _make_preset(db, lock)
    team = team_service.create_team(db, lock, name="team-a")
    team_service.set_team_members(db, lock, team["id"], [preset["id"]])
    with pytest.raises(ValueError):
        team_service.delete_preset(db, lock, preset["id"])


def test_create_team_and_members(db: sqlite3.Connection, lock: threading.Lock) -> None:
    p1 = _make_preset(db, lock, name="researcher")
    p2 = _make_preset(db, lock, name="writer")
    team = team_service.create_team(db, lock, name="content-team", description="writes docs")
    assert team["members"] == []
    updated = team_service.set_team_members(db, lock, team["id"], [p2["id"], p1["id"]])
    assert [m["name"] for m in updated["members"]] == ["writer", "researcher"]


def test_create_team_rejects_duplicate_name(db: sqlite3.Connection, lock: threading.Lock) -> None:
    team_service.create_team(db, lock, name="dup-team")
    with pytest.raises(ValueError):
        team_service.create_team(db, lock, name="dup-team")


def test_set_team_members_rejects_empty_roster(db: sqlite3.Connection, lock: threading.Lock) -> None:
    team = team_service.create_team(db, lock, name="empty-roster")
    with pytest.raises(ValueError):
        team_service.set_team_members(db, lock, team["id"], [])


def test_set_team_members_rejects_duplicate_preset(db: sqlite3.Connection, lock: threading.Lock) -> None:
    preset = _make_preset(db, lock)
    team = team_service.create_team(db, lock, name="dup-member")
    with pytest.raises(ValueError):
        team_service.set_team_members(db, lock, team["id"], [preset["id"], preset["id"]])


def test_set_team_members_rejects_unknown_preset(db: sqlite3.Connection, lock: threading.Lock) -> None:
    team = team_service.create_team(db, lock, name="unknown-member")
    with pytest.raises(ValueError):
        team_service.set_team_members(db, lock, team["id"], ["preset-missing"])


def test_list_teams_includes_members(db: sqlite3.Connection, lock: threading.Lock) -> None:
    preset = _make_preset(db, lock)
    team = team_service.create_team(db, lock, name="listed-team")
    team_service.set_team_members(db, lock, team["id"], [preset["id"]])
    teams = team_service.list_teams(db)
    assert any(t["id"] == team["id"] and len(t["members"]) == 1 for t in teams)


def test_delete_team_removes_members(db: sqlite3.Connection, lock: threading.Lock) -> None:
    preset = _make_preset(db, lock)
    team = team_service.create_team(db, lock, name="removable-team")
    team_service.set_team_members(db, lock, team["id"], [preset["id"]])
    assert team_service.delete_team(db, lock, team["id"]) is True
    assert team_service.get_team(db, team["id"]) is None
    # The preset itself survives — deleting a team must not delete its presets.
    assert team_service.get_preset(db, preset["id"]) is not None
