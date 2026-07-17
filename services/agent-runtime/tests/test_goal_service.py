"""Tests for the Command Center goal service (loop-engineering slice).

Uses the shared `db` fixture (:memory: with all migrations, incl. 0010_goal_model).
Covers goal/task/observation CRUD, sub-goal nesting, tree assembly, archive
cascade, and not-found errors.
"""
from __future__ import annotations

import threading

import pytest

from atlas_runtime import goal_service as gs


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    return threading.Lock()


def test_create_and_get_goal(db, lock):
    g = gs.create_goal(db, lock, title="Ship the loop", description="full slice", focus_id="f1")
    fetched = gs.get_goal(db, g.id)
    assert fetched is not None
    assert fetched.title == "Ship the loop"
    assert fetched.description == "full slice"
    assert fetched.focus_id == "f1"
    assert fetched.status == "open"


def test_empty_title_rejected(db, lock):
    with pytest.raises(gs.GoalError):
        gs.create_goal(db, lock, title="   ")


def test_list_goals_scoped_by_focus_and_parent(db, lock):
    root = gs.create_goal(db, lock, title="root", focus_id="f1", position=0)
    gs.create_goal(db, lock, title="other-focus", focus_id="f2")
    sub = gs.create_goal(db, lock, title="sub", focus_id="f1", parent_goal_id=root.id)

    f1_goals = gs.list_goals(db, focus_id="f1")
    assert {g.id for g in f1_goals} == {root.id, sub.id}

    top = gs.list_goals(db, focus_id="f1", parent_goal_id=None)
    assert [g.id for g in top] == [root.id]

    children = gs.list_goals(db, parent_goal_id=root.id)
    assert [g.id for g in children] == [sub.id]


def test_archive_cascades_to_subgoals(db, lock):
    root = gs.create_goal(db, lock, title="root", focus_id="f1")
    sub = gs.create_goal(db, lock, title="sub", focus_id="f1", parent_goal_id=root.id)
    grand = gs.create_goal(db, lock, title="grand", focus_id="f1", parent_goal_id=sub.id)

    gs.archive_goal(db, lock, root.id)
    assert gs.get_goal(db, root.id).status == "archived"
    assert gs.get_goal(db, sub.id).status == "archived"
    assert gs.get_goal(db, grand.id).status == "archived"
    # Archived goals drop out of the default list.
    assert gs.list_goals(db, focus_id="f1") == []


def test_archive_unknown_raises(db, lock):
    with pytest.raises(gs.GoalError):
        gs.archive_goal(db, lock, "nope")


def test_update_goal_status_and_validation(db, lock):
    g = gs.create_goal(db, lock, title="x", focus_id="f1")
    updated = gs.update_goal(db, lock, g.id, status="active", description="now active")
    assert updated.status == "active"
    assert updated.description == "now active"
    with pytest.raises(gs.GoalError):
        gs.update_goal(db, lock, g.id, status="bogus")


def test_tasks_crud(db, lock):
    g = gs.create_goal(db, lock, title="x", focus_id="f1")
    t1 = gs.create_task(db, lock, goal_id=g.id, title="write migration", position=0)
    gs.create_task(db, lock, goal_id=g.id, title="write service", position=1)
    tasks = gs.list_tasks(db, goal_id=g.id)
    assert [t.title for t in tasks] == ["write migration", "write service"]

    done = gs.set_task_status(db, lock, t1.id, "done")
    assert done.status == "done"
    with pytest.raises(gs.GoalError):
        gs.set_task_status(db, lock, t1.id, "bogus")
    with pytest.raises(gs.GoalError):
        gs.set_task_status(db, lock, "nope", "done")


def test_observations_attach_and_list(db, lock):
    g = gs.create_goal(db, lock, title="x", focus_id="f1")
    gs.add_observation(db, lock, body="tests green", goal_id=g.id, run_id="r1", source="run:r1")
    gs.add_observation(db, lock, body="operator note", goal_id=g.id)
    by_goal = gs.list_observations(db, goal_id=g.id)
    assert {o.body for o in by_goal} == {"tests green", "operator note"}
    by_run = gs.list_observations(db, run_id="r1")
    assert [o.body for o in by_run] == ["tests green"]
    with pytest.raises(gs.GoalError):
        gs.add_observation(db, lock, body="  ")


def test_build_goal_tree_nests_children_tasks_observations(db, lock):
    root = gs.create_goal(db, lock, title="root", focus_id="f1", position=0)
    sub = gs.create_goal(db, lock, title="sub", focus_id="f1", parent_goal_id=root.id)
    gs.create_task(db, lock, goal_id=root.id, title="t-root")
    gs.create_task(db, lock, goal_id=sub.id, title="t-sub")
    gs.add_observation(db, lock, body="obs-root", goal_id=root.id)

    tree = gs.build_goal_tree(db, focus_id="f1")
    assert len(tree) == 1
    node = tree[0]
    assert node["id"] == root.id
    assert [t["title"] for t in node["tasks"]] == ["t-root"]
    assert [o["body"] for o in node["observations"]] == ["obs-root"]
    assert len(node["children"]) == 1
    child = node["children"][0]
    assert child["id"] == sub.id
    assert [t["title"] for t in child["tasks"]] == ["t-sub"]


def test_paused_status_roundtrip(db, lock):
    g = gs.create_goal(db, lock, title="pausable", focus_id="f1")
    gs.update_goal(db, lock, g.id, status="paused")
    assert gs.get_goal(db, g.id).status == "paused"
    # Paused goals stay visible in the default (non-archived) list.
    assert g.id in {x.id for x in gs.list_goals(db, focus_id="f1")}
    gs.update_goal(db, lock, g.id, status="active")
    assert gs.get_goal(db, g.id).status == "active"


def test_delete_goal_cascades_and_detaches_observations(db, lock):
    root = gs.create_goal(db, lock, title="root", focus_id="f1")
    sub = gs.create_goal(db, lock, title="sub", focus_id="f1", parent_goal_id=root.id)
    task = gs.create_task(db, lock, goal_id=sub.id, title="t")
    obs = gs.add_observation(db, lock, body="learned", goal_id=sub.id)

    deleted = gs.delete_goal(db, lock, root.id)
    assert deleted == 2
    assert gs.get_goal(db, root.id) is None
    assert gs.get_goal(db, sub.id) is None
    assert db.execute("SELECT COUNT(*) FROM tasks WHERE id=?", (task.id,)).fetchone()[0] == 0
    row = db.execute("SELECT goal_id FROM observations WHERE id=?", (obs.id,)).fetchone()
    assert row is not None and row[0] is None


def test_delete_goal_unknown_raises(db, lock):
    with pytest.raises(gs.GoalError):
        gs.delete_goal(db, lock, "no-such-goal")
