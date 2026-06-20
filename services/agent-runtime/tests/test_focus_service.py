"""Tests for the Command Center focus service (WP-2).

Uses the shared `db` fixture (:memory: with all migrations, incl. 0009_focus).
Covers the single-Current-Focus invariant, CRUD, JSON list encode/decode, and
not-found errors.
"""
from __future__ import annotations

import threading

import pytest

from atlas_runtime import focus_service as fs


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    return threading.Lock()


def test_create_focus_becomes_current(db, lock):
    focus = fs.create_focus(
        db, lock, title="Ship the autonomous loop",
        framework="GSD", priorities=["WP-1", "WP-2"], drivers=["operator wedge"],
    )
    current = fs.get_current_focus(db)
    assert current is not None
    assert current.id == focus.id
    assert current.status == "active"
    assert fs.decode_list(current.priorities) == ["WP-1", "WP-2"]
    assert fs.decode_list(current.drivers) == ["operator wedge"]


def test_new_focus_archives_previous(db, lock):
    first = fs.create_focus(db, lock, title="First focus")
    second = fs.create_focus(db, lock, title="Second focus")
    current = fs.get_current_focus(db)
    assert current is not None and current.id == second.id
    assert fs.get_focus(db, first.id).status == "archived"
    # Only the newest is active.
    active = fs.list_focus(db)
    assert [f.id for f in active] == [second.id]


def test_create_not_current_is_not_returned_as_current(db, lock):
    fs.create_focus(db, lock, title="Side note", make_current=False)
    assert fs.get_current_focus(db) is None


def test_update_focus_patches_provided_fields(db, lock):
    focus = fs.create_focus(db, lock, title="Original", framework="old", priorities=["a"])
    updated = fs.update_focus(
        db, lock, focus.id, title="Renamed", priorities=["a", "b", "c"],
    )
    assert updated.title == "Renamed"
    assert updated.framework == "old"  # untouched
    assert fs.decode_list(updated.priorities) == ["a", "b", "c"]
    assert updated.updated_at >= focus.updated_at


def test_update_focus_unknown_raises(db, lock):
    with pytest.raises(fs.FocusError):
        fs.update_focus(db, lock, "no-such-id", title="x")


def test_archive_focus_clears_current(db, lock):
    focus = fs.create_focus(db, lock, title="Transient")
    fs.archive_focus(db, lock, focus.id)
    assert fs.get_current_focus(db) is None
    assert fs.get_focus(db, focus.id).status == "archived"


def test_archive_unknown_raises(db, lock):
    with pytest.raises(fs.FocusError):
        fs.archive_focus(db, lock, "no-such-id")


def test_create_empty_title_raises(db, lock):
    with pytest.raises(fs.FocusError):
        fs.create_focus(db, lock, title="   ")


def test_focus_model_dump_is_json_safe(db, lock):
    focus = fs.create_focus(db, lock, title="JSON-safe", priorities=["x"])
    dumped = focus.model_dump()
    assert isinstance(dumped["created_at"], str)
    assert isinstance(dumped["priorities"], str)  # JSON-array string column
