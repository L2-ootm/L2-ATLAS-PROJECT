"""Tests for the context-assembly service (WP-3, Intelligence Layer).

Uses the shared `db` fixture (:memory: with all migrations). Covers redaction,
provenance sources, project resolution via the mission, and the empty case.
"""
from __future__ import annotations

import datetime
import threading
import uuid

import pytest

from atlas_runtime import context_service as cs
from atlas_runtime import focus_service, goal_service, project_service
from atlas_runtime.run_service import start_run


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    return threading.Lock()


def _mission(conn, lock, *, project_id=None, status="pending") -> str:
    mid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO missions(id,title,intent,status,project,project_id,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (mid, "ctx mission", "", status, "", project_id, now, now),
            )
    return mid


def test_redact_handles_all_secret_patterns():
    assert "[REDACTED]" in cs.redact("api_key=sk-abc123")
    assert "sk-abc123" not in cs.redact("api_key=sk-abc123")
    assert "[REDACTED]" in cs.redact('{"password": "hunter2"}')
    assert "[REDACTED]" in cs.redact("Authorization: Bearer abc.def.ghi")


def test_assemble_includes_focus_and_redacts(db, lock):
    focus_service.create_focus(
        db, lock, title="Ship loop", framework="GSD",
        priorities=["wire executor", "token=leakme123"],
    )
    ctx = cs.assemble_context(db)
    assert "Current Focus" in ctx.markdown
    assert "Ship loop" in ctx.markdown
    assert "wire executor" in ctx.markdown
    # The secret embedded in a priority is redacted.
    assert "leakme123" not in ctx.markdown
    assert "[REDACTED]" in ctx.markdown
    assert any(s.startswith("focus:") for s in ctx.sources)


def test_assemble_resolves_project_via_mission(db, lock, tmp_path):
    project = project_service.register_project(db, lock, name="Demo", root_path=str(tmp_path))
    mid = _mission(db, lock, project_id=project.id)
    ctx = cs.assemble_context(db, mission_id=mid)
    assert "## Project" in ctx.markdown
    assert "Demo" in ctx.markdown
    assert f"project:{project.id}" in ctx.sources


def test_assemble_includes_recent_runs(db, lock):
    mid = _mission(db, lock)
    run = start_run(db, lock, mission_id=mid)
    ctx = cs.assemble_context(db, mission_id=mid)
    assert "Recent Runs" in ctx.markdown
    assert f"run:{run.id}" in ctx.sources


def test_assemble_empty_is_safe(db):
    ctx = cs.assemble_context(db)
    assert ctx.markdown.startswith("# ATLAS Operator Context")
    assert ctx.sources == ()


def test_assemble_synthesizes_goal_tree_and_contract(db, lock):
    focus = focus_service.create_focus(db, lock, title="Ship loop", framework="GSD")
    root = goal_service.create_goal(
        db, lock, title="Wire execution", description="harness + safety", focus_id=focus.id
    )
    sub = goal_service.create_goal(
        db, lock, title="Stop conditions", focus_id=focus.id, parent_goal_id=root.id
    )
    goal_service.create_task(db, lock, goal_id=root.id, title="map result dict")
    goal_service.add_observation(db, lock, body="403 without creds", goal_id=root.id, source="run:r1")

    ctx = cs.assemble_context(db)
    md = ctx.markdown
    # Goals + nesting + tasks + observations render.
    assert "## Goals" in md
    assert "Wire execution" in md
    assert "Stop conditions" in md  # sub-goal
    assert "map result dict" in md  # task
    assert "403 without creds" in md  # observation
    # Loop-engineering contract synthesized (not just the focus title).
    assert "## Operating Contract" in md
    assert "VERIFIED" in md and "UNCERTAIN" in md
    # Provenance covers goals + observations.
    assert any(s.startswith("goal:") for s in ctx.sources)
    assert any(s.startswith("observation:") for s in ctx.sources)


def test_goal_tree_observation_secret_is_redacted(db, lock):
    focus = focus_service.create_focus(db, lock, title="F")
    g = goal_service.create_goal(db, lock, title="G", focus_id=focus.id)
    goal_service.add_observation(db, lock, body="leaked token=zzz999secret", goal_id=g.id)
    md = cs.assemble_context(db).markdown
    assert "zzz999secret" not in md
    assert "[REDACTED]" in md


def test_no_operating_contract_without_focus(db):
    # Without a Current Focus there is nothing to act on — no contract section.
    assert "## Operating Contract" not in cs.assemble_context(db).markdown
