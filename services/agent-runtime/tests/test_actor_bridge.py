"""Actor bridge tests — the atlas_actor tool contract + completion inbox hooks.

atlas_audit's connection/session state is injected directly (its documented
test path); the worker launch is monkeypatched so no subprocess spawns.
"""
from __future__ import annotations

import json
import sqlite3
import threading

import pytest

import atlas_audit
from atlas_runtime import actor_bridge, actor_service


class _Agent:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id


@pytest.fixture()
def bound(db: sqlite3.Connection, lock: threading.Lock, run_id: str):
    """Bind atlas_audit state the way ensure_foundation_bridge does at run start."""
    # the bridge shares atlas_audit's lock; tests use the fixture lock only for
    # direct actor_service calls, which is safe (same connection, sequential).
    atlas_audit.set_connection(db)
    atlas_audit.on_session_start(session_id="sess-1", run_id=run_id)
    yield _Agent("sess-1"), run_id
    atlas_audit.set_connection(None)


def _launched(monkeypatch) -> list[str]:
    launched: list[str] = []

    def _fake_launch(conn, lock, actor_id, **kw):  # noqa: ANN001
        launched.append(actor_id)
        return 4242

    monkeypatch.setattr(
        "atlas_runtime.actor_worker.launch_actor_worker", _fake_launch
    )
    return launched


def test_tool_spawn_returns_immediately(bound, monkeypatch) -> None:
    agent, run_id = bound
    launched = _launched(monkeypatch)
    out = json.loads(
        actor_bridge.atlas_actor_tool(op="spawn", goal="index the docs", parent_agent=agent)
    )
    assert out["ok"] is True
    assert out["status"] == "queued"
    assert out["mode"] == "detached"
    assert launched == [out["actor_id"]]


def test_tool_spawn_duplicate_returns_same_actor_without_relaunch(bound, monkeypatch) -> None:
    agent, _ = bound
    launched = _launched(monkeypatch)
    first = json.loads(actor_bridge.atlas_actor_tool(op="spawn", goal="g", parent_agent=agent))
    second = json.loads(actor_bridge.atlas_actor_tool(op="spawn", goal="g", parent_agent=agent))
    assert first["actor_id"] == second["actor_id"]
    assert len(launched) == 1


def test_tool_run_joins_completed_actor(bound, monkeypatch) -> None:
    agent, run_id = bound
    conn = atlas_audit.get_connection()
    lock = atlas_audit.get_lock()

    def _fake_launch(c, l, actor_id, **kw):  # noqa: ANN001, E741
        actor_service.mark_running(conn, lock, actor_id, pid=1)
        actor_service.complete_actor(conn, lock, actor_id, result_preview="joined result")
        return 1

    monkeypatch.setattr("atlas_runtime.actor_worker.launch_actor_worker", _fake_launch)
    out = json.loads(
        actor_bridge.atlas_actor_tool(
            op="run", goal="quick job", timeout_seconds=2, parent_agent=agent
        )
    )
    assert out["ok"] is True
    assert out["status"] == "completed"
    assert out["result"] == "joined result"


def test_tool_status_and_wait_and_cancel(bound, monkeypatch) -> None:
    agent, run_id = bound
    _launched(monkeypatch)
    spawned = json.loads(
        actor_bridge.atlas_actor_tool(op="spawn", goal="long job", parent_agent=agent)
    )
    actor_id = spawned["actor_id"]

    status = json.loads(
        actor_bridge.atlas_actor_tool(op="status", actor_id=actor_id, parent_agent=agent)
    )
    assert status["ok"] and status["status"] == "queued"

    waited = json.loads(
        actor_bridge.atlas_actor_tool(
            op="wait", actor_id=actor_id, timeout_seconds=0.05, parent_agent=agent
        )
    )
    assert waited["ok"] and "not terminal" in waited["note"]

    cancelled = json.loads(
        actor_bridge.atlas_actor_tool(op="cancel", actor_id=actor_id, parent_agent=agent)
    )
    assert cancelled["ok"] and cancelled["cancelled"] == [actor_id]
    # idempotent
    again = json.loads(
        actor_bridge.atlas_actor_tool(op="cancel", actor_id=actor_id, parent_agent=agent)
    )
    assert again["cancelled"] == []


def test_tool_errors_are_json_not_exceptions(bound) -> None:
    agent, _ = bound
    assert json.loads(actor_bridge.atlas_actor_tool(op="run", parent_agent=agent))["ok"] is False
    assert json.loads(actor_bridge.atlas_actor_tool(op="status", parent_agent=agent))["ok"] is False
    assert json.loads(actor_bridge.atlas_actor_tool(op="nope", parent_agent=agent))["ok"] is False
    assert (
        json.loads(actor_bridge.atlas_actor_tool(op="status", actor_id="ghost", parent_agent=agent))["ok"]
        is False
    )


def test_tool_without_bound_connection_degrades() -> None:
    atlas_audit.set_connection(None)
    out = json.loads(actor_bridge.atlas_actor_tool(op="status", parent_agent=_Agent("s")))
    assert out["ok"] is False and "unavailable" in out["error"]


def test_hermes_registry_dispatch_uses_task_id_context(bound, monkeypatch) -> None:
    """Regression: exercise the real plugin ABI that direct tests once skipped."""
    _agent, _run_id = bound
    launched = _launched(monkeypatch)
    from atlas_runtime.subagent_service import _foundation_on_path

    assert _foundation_on_path()
    from tools.registry import registry

    registry.register(
        name="atlas_actor",
        toolset="atlas",
        schema=actor_bridge.TOOL_SCHEMA,
        handler=actor_bridge.atlas_actor_tool,
    )
    out = json.loads(
        registry.dispatch(
            "atlas_actor",
            {"op": "spawn", "goal": "registry boundary"},
            task_id="sess-1",
            user_task="ignored framework context",
        )
    )
    assert out["ok"] is True
    assert out["status"] == "queued"
    assert launched == [out["actor_id"]]


def test_tool_schema_uses_hermes_plugin_shape() -> None:
    assert actor_bridge.TOOL_SCHEMA["name"] == "atlas_actor"
    assert actor_bridge.TOOL_SCHEMA["parameters"]["required"] == ["op"]
    assert "function" not in actor_bridge.TOOL_SCHEMA


def test_inbox_pre_claims_and_post_acknowledges(bound) -> None:
    agent, run_id = bound
    conn = atlas_audit.get_connection()
    lock = atlas_audit.get_lock()
    actor, _ = actor_service.spawn_actor(
        conn, lock, parent_run_id=run_id, goal="bg job", mode="detached"
    )
    actor_service.mark_running(conn, lock, actor["id"])
    actor_service.complete_actor(conn, lock, actor["id"], result_preview="bg result")

    injected = actor_bridge.on_pre_llm_call(session_id="sess-1")
    assert injected is not None
    assert "ATLAS actor completions" in injected["context"]
    assert "bg result" in injected["context"]

    # same turn: nothing more to claim (lease held)
    assert actor_bridge.on_pre_llm_call(session_id="sess-1") is None

    actor_bridge.on_post_llm_call(session_id="sess-1")
    row = conn.execute(
        "SELECT status FROM actor_deliveries WHERE actor_id=?", (actor["id"],)
    ).fetchone()
    assert row[0] == "delivered"
    # acknowledged: never re-injected
    assert actor_bridge.on_pre_llm_call(session_id="sess-1") is None


def test_inbox_noop_without_completions(bound) -> None:
    assert actor_bridge.on_pre_llm_call(session_id="sess-1") is None
    actor_bridge.on_post_llm_call(session_id="sess-1")  # must not raise


def test_inbox_unknown_session_noop() -> None:
    assert actor_bridge.on_pre_llm_call(session_id="unknown") is None


# ---------------------------------------------------------------------------
# Surface-session resolution (regression: actors got run_id, not the real
# surface session id, causing cross-session contamination in the UI)
# ---------------------------------------------------------------------------


def test_spawn_uses_surface_session_when_mapped(db, lock, run_id, monkeypatch) -> None:
    """run_service.start_run() maps the harness session key (always run_id —
    native.py constructs the harness with factory(session_id=run_id)) plus
    the real surface session id via two atlas_audit.on_session_start() calls,
    then calls record_surface_session() with the same two ids. parent_agent
    .session_id here mirrors the real production shape: it equals run_id,
    not the surface session. The spawned actor must be stamped with the real
    surface session id, not the run id, or actors from different browser
    sessions look cross-contaminated in the UI.
    """
    atlas_audit.set_connection(db)
    surface_session_id = "surface-sess-42"
    # Mirrors run_service.start_run(): harness key -> run_id, then the
    # distinct caller-supplied surface session_id -> run_id.
    atlas_audit.on_session_start(session_id=run_id, run_id=run_id)
    atlas_audit.on_session_start(session_id=surface_session_id, run_id=run_id)
    actor_bridge.record_surface_session(session_id=surface_session_id, run_id=run_id)
    try:
        agent = _Agent(run_id)  # parent_agent.session_id == run_id, like native.py
        launched = _launched(monkeypatch)
        out = json.loads(
            actor_bridge.atlas_actor_tool(op="spawn", goal="scoped job", parent_agent=agent)
        )
        assert out["ok"] is True
        assert launched == [out["actor_id"]]

        stored = actor_service.get_actor(db, out["actor_id"])
        assert stored["session_id"] == surface_session_id
        assert stored["session_id"] != run_id
    finally:
        actor_bridge._SURFACE_SESSION_BY_RUN.pop(run_id, None)
        atlas_audit.set_connection(None)


def test_spawn_falls_back_to_parent_agent_session_without_mapping(
    bound, monkeypatch
) -> None:
    """No record_surface_session() entry for this run_id (e.g. a run created
    outside start_run(), or before the fix populated the map): the old
    behavior — pass parent_agent.session_id through unchanged — must still
    work, so nothing regresses.
    """
    agent, run_id = bound
    assert run_id not in actor_bridge._SURFACE_SESSION_BY_RUN
    launched = _launched(monkeypatch)
    out = json.loads(
        actor_bridge.atlas_actor_tool(op="spawn", goal="unscoped job", parent_agent=agent)
    )
    assert out["ok"] is True
    assert launched == [out["actor_id"]]

    conn = atlas_audit.get_connection()
    stored = actor_service.get_actor(conn, out["actor_id"])
    assert stored["session_id"] == agent.session_id


def test_record_surface_session_ignores_equal_or_missing_ids() -> None:
    actor_bridge._SURFACE_SESSION_BY_RUN.clear()
    actor_bridge.record_surface_session(session_id="run-x", run_id="run-x")
    actor_bridge.record_surface_session(session_id=None, run_id="run-y")
    actor_bridge.record_surface_session(session_id="sess-z", run_id=None)
    assert actor_bridge._SURFACE_SESSION_BY_RUN == {}
