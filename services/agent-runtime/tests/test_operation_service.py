"""Tests for the operation service (WP-6 — premade autonomous operations)."""
from __future__ import annotations

import pytest

from atlas_core.schemas.core import Focus, Goal

from atlas_runtime import operation_service as ops


def test_list_and_get_operations():
    listed = ops.list_operations()
    ids = {o.id for o in listed}
    assert ids == {"elaborate", "recon", "blockers", "decompose"}
    assert ops.get_operation("elaborate").label == "Elaborate Goal"
    assert ops.get_operation("nope") is None
    # All shipped ops are internal/reversible (auto-runnable).
    assert all(o.risk == "internal" for o in listed)


def test_build_intent_elaborate_includes_goal_and_writeback():
    goal = Goal(title="Ship the loop", description="full slice", focus_id="f1")
    focus = Focus(title="F", project_id="p1")
    intent = ops.build_intent("elaborate", goal=goal, focus=focus)
    assert "Ship the loop" in intent
    assert "full slice" in intent
    assert "Tasks" in intent and "Constraints" in intent and "Blockers" in intent
    # Write-back references the goal id and the atlas CLI commands.
    assert goal.id in intent
    assert "task add --goal" in intent
    assert "observe add --goal" in intent
    assert "operation:elaborate" in intent


def test_build_intent_decompose_uses_focus_for_subgoals():
    goal = Goal(title="Big goal", focus_id="f-goal")
    intent = ops.build_intent("decompose", goal=goal, focus=Focus(title="F"))
    # Sub-goal creation must carry the goal's own focus + parent.
    assert f"--focus f-goal --parent {goal.id}" in intent
    assert "goal create" in intent


def test_build_intent_unknown_raises():
    with pytest.raises(ops.OperationError):
        ops.build_intent("bogus", goal=Goal(title="x"), focus=None)


def test_each_operation_renders():
    goal = Goal(title="G", focus_id="f1")
    for op in ops.list_operations():
        intent = ops.build_intent(op.id, goal=goal, focus=None)
        assert intent.startswith(f"# Operation: {op.label}")
        assert goal.id in intent
