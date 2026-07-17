"""Tests for the project service — rename and unregister (Projects QoL).

Uses the shared `db` fixture (:memory: with all migrations). Covers the folder
lifecycle guarantees: rename never touches the folder, unregister detaches
bound missions/focus (history preserved) and never deletes the folder on disk.
"""
from __future__ import annotations

import threading

import pytest

from atlas_runtime import focus_service, mission_service, project_service as ps


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    return threading.Lock()


def test_rename_updates_name_keeps_path(db, lock, tmp_path):
    project = ps.register_project(db, lock, name="Old", root_path=str(tmp_path))
    renamed = ps.rename_project(db, lock, project_id=project.id, name="New Name")
    assert renamed.name == "New Name"
    assert renamed.root_path == project.root_path  # folder is fixed
    assert renamed.updated_at >= project.updated_at
    # Folder on disk is untouched.
    assert tmp_path.is_dir()


def test_rename_empty_name_raises(db, lock, tmp_path):
    project = ps.register_project(db, lock, name="Keep", root_path=str(tmp_path))
    with pytest.raises(ps.ProjectError):
        ps.rename_project(db, lock, project_id=project.id, name="   ")


def test_rename_unknown_raises(db, lock):
    with pytest.raises(ps.ProjectError):
        ps.rename_project(db, lock, project_id="no-such-id", name="x")


def test_unregister_detaches_missions_and_keeps_folder(db, lock, tmp_path):
    project = ps.register_project(db, lock, name="Bound", root_path=str(tmp_path))
    m1 = mission_service.create_mission(db, lock, title="A", project_id=project.id)
    m2 = mission_service.create_mission(db, lock, title="B", project_id=project.id)

    detached = ps.unregister_project(db, lock, project_id=project.id)
    assert detached == 2

    # Project row is gone; folder survives.
    assert ps.get_project(db, project.id) is None
    assert tmp_path.is_dir()

    # Missions survive with project_id cleared (history preserved).
    for mid in (m1.id, m2.id):
        row = db.execute("SELECT project_id FROM missions WHERE id=?", (mid,)).fetchone()
        assert row is not None
        assert row[0] is None


def test_unregister_detaches_focus(db, lock, tmp_path):
    project = ps.register_project(db, lock, name="Focused", root_path=str(tmp_path))
    focus = focus_service.create_focus(db, lock, title="Set", project_id=project.id)
    assert focus.project_id == project.id

    ps.unregister_project(db, lock, project_id=project.id)

    reloaded = focus_service.get_focus(db, focus.id)
    assert reloaded.project_id is None


def test_unregister_unknown_raises(db, lock):
    with pytest.raises(ps.ProjectError):
        ps.unregister_project(db, lock, project_id="no-such-id")


def test_unregister_returns_zero_when_no_missions(db, lock, tmp_path):
    project = ps.register_project(db, lock, name="Lonely", root_path=str(tmp_path))
    assert ps.unregister_project(db, lock, project_id=project.id) == 0
