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
from atlas_runtime import focus_service, project_service
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
