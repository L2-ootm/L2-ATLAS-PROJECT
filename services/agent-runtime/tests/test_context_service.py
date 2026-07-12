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
    goal_service.create_goal(
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


def test_operator_context_opt_out_param(db, lock):
    # Explicit include_operator_context=False suppresses Focus/Goals/Contract
    # even when a Current Focus exists.
    focus_service.create_focus(db, lock, title="Command Center Loop")
    md = cs.assemble_context(db, include_operator_context=False).markdown
    assert "Current Focus" not in md
    assert "Command Center Loop" not in md
    assert "## Operating Contract" not in md


def test_operator_context_opt_out_env(db, lock, monkeypatch):
    # ATLAS_SKIP_CONTEXT=1 suppresses the operator context when the caller
    # does not pass include_operator_context.
    focus_service.create_focus(db, lock, title="Command Center Loop")
    monkeypatch.setenv("ATLAS_SKIP_CONTEXT", "1")
    md = cs.assemble_context(db).markdown
    assert "## Operating Contract" not in md
    monkeypatch.setenv("ATLAS_SKIP_CONTEXT", "")
    assert "## Operating Contract" in cs.assemble_context(db).markdown


# ---------------------------------------------------------------------------
# Memory router — FTS5 wiki retrieval into the context brief (item #1)
# ---------------------------------------------------------------------------


def _wiki_page(conn, lock, *, slug, title, body) -> str:
    """Seed a wiki page; the FTS5 insert trigger auto-indexes it."""
    pid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO wiki_pages(id,slug,title,body,created_at,updated_at,version) "
                "VALUES (?,?,?,?,?,?,1)",
                (pid, slug, title, body, now, now),
            )
    return pid


def test_assemble_injects_relevant_wiki_knowledge(db, lock):
    focus = focus_service.create_focus(db, lock, title="Ship the executor loop")
    goal_service.create_goal(db, lock, title="Wire the run executor", focus_id=focus.id)
    pid = _wiki_page(
        db, lock,
        slug="executor-notes",
        title="Executor wiring",
        body="How to wire the run executor subprocess and stop conditions.",
    )
    # An unrelated page must not surface for this query.
    _wiki_page(db, lock, slug="lunch", title="Lunch menu", body="tacos and salad")

    ctx = cs.assemble_context(db)
    md = ctx.markdown
    assert "## Relevant Knowledge" in md
    assert "Executor wiring" in md
    assert "Lunch menu" not in md
    assert f"wiki:{pid}" in ctx.sources


def test_relevant_knowledge_redacts_secrets(db, lock):
    focus_service.create_focus(db, lock, title="executor work")
    _wiki_page(
        db, lock,
        slug="creds",
        title="Executor config",
        body="set api_key=sk-leakwiki999 before running the executor",
    )
    md = cs.assemble_context(db).markdown
    assert "## Relevant Knowledge" in md
    assert "sk-leakwiki999" not in md
    assert "[REDACTED]" in md


def test_relevant_knowledge_respects_page_budget(db, lock):
    focus_service.create_focus(db, lock, title="executor")
    for i in range(8):
        _wiki_page(
            db, lock,
            slug=f"executor-{i}",
            title=f"Executor topic {i}",
            body="executor executor executor wiring details",
        )
    ctx = cs.assemble_context(db)
    injected = [s for s in ctx.sources if s.startswith("wiki:")]
    assert 0 < len(injected) <= 5  # capped, not all 8


def test_relevant_knowledge_truncates_long_body(db, lock):
    focus_service.create_focus(db, lock, title="executor")
    _wiki_page(
        db, lock,
        slug="long",
        title="Executor long",
        body=("executor wiring details " * 60) + " ZZTAILMARKER",
    )
    md = cs.assemble_context(db).markdown
    assert "Executor long" in md
    assert "ZZTAILMARKER" not in md  # snippet truncated before the tail


def test_no_knowledge_section_when_wiki_empty(db, lock):
    focus_service.create_focus(db, lock, title="executor work")
    assert "## Relevant Knowledge" not in cs.assemble_context(db).markdown


def test_no_knowledge_section_without_focus(db, lock):
    # No focus → no query terms → no retrieval.
    _wiki_page(db, lock, slug="x", title="Executor", body="executor notes here")
    assert "## Relevant Knowledge" not in cs.assemble_context(db).markdown
