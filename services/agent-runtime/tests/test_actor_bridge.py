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


def test_a_completion_states_its_verification_position(bound) -> None:
    """A child's own account of its work is a claim. Silence about whether
    anything checked that claim reads to the parent as confirmation, which is
    how one agent ends up building on what another only asserted."""
    agent, run_id = bound
    conn = atlas_audit.get_connection()
    lock = atlas_audit.get_lock()
    actor, _ = actor_service.spawn_actor(
        conn, lock, parent_run_id=run_id, goal="migrate the schema", mode="detached"
    )
    actor_service.mark_running(conn, lock, actor["id"])
    actor_service.complete_actor(
        conn, lock, actor["id"], result_preview="migration applied cleanly"
    )

    injected = actor_bridge.on_pre_llm_call(session_id="sess-1")
    assert injected is not None
    context = injected["context"]
    assert "migration applied cleanly" in context
    assert "verification:" in context
    # No child run was classified, so the parent is told exactly that rather
    # than being left to read the absence as a pass.
    assert "unchecked claim" in context


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


# ---------------------------------------------------------------------------
# CASE-04: steering, log tailing, join liveness, opt-in wakeup
# ---------------------------------------------------------------------------


def test_steer_queues_a_message_for_a_running_actor(bound, monkeypatch) -> None:
    agent, _ = bound
    _launched(monkeypatch)
    spawned = json.loads(
        actor_bridge.atlas_actor_tool(op="spawn", goal="long job", parent_agent=agent)
    )
    conn, lock = atlas_audit.get_connection(), atlas_audit.get_lock()
    actor_service.mark_running(conn, lock, spawned["actor_id"], pid=1)

    out = json.loads(
        actor_bridge.atlas_actor_tool(
            op="steer", actor_id=spawned["actor_id"], message="use the cached index",
            parent_agent=agent,
        )
    )
    assert out["ok"] is True
    assert out["seq"] == 1
    assert actor_service.pending_steering(conn, spawned["actor_id"]) == 1


def test_steer_requires_a_message(bound, monkeypatch) -> None:
    agent, _ = bound
    _launched(monkeypatch)
    spawned = json.loads(
        actor_bridge.atlas_actor_tool(op="spawn", goal="g", parent_agent=agent)
    )
    out = json.loads(
        actor_bridge.atlas_actor_tool(
            op="steer", actor_id=spawned["actor_id"], parent_agent=agent
        )
    )
    assert out["ok"] is False
    assert "message" in out["error"]


def test_steering_a_terminal_actor_is_a_named_failure(bound, monkeypatch) -> None:
    """Silently accepting a steer nothing will ever read is worse than failing."""
    agent, _ = bound
    _launched(monkeypatch)
    spawned = json.loads(
        actor_bridge.atlas_actor_tool(op="spawn", goal="g", parent_agent=agent)
    )
    conn, lock = atlas_audit.get_connection(), atlas_audit.get_lock()
    actor_service.mark_running(conn, lock, spawned["actor_id"], pid=1)
    actor_service.complete_actor(conn, lock, spawned["actor_id"], result_preview="done")

    out = json.loads(
        actor_bridge.atlas_actor_tool(
            op="steer", actor_id=spawned["actor_id"], message="too late",
            parent_agent=agent,
        )
    )
    assert out["ok"] is False
    assert "already completed" in out["error"]


def test_child_drains_its_own_steering_at_the_next_model_call(
    bound, monkeypatch
) -> None:
    """The child recognizes messages for itself via ATLAS_ACTOR_ID — no IPC."""
    agent, _ = bound
    _launched(monkeypatch)
    spawned = json.loads(
        actor_bridge.atlas_actor_tool(op="spawn", goal="g", parent_agent=agent)
    )
    conn, lock = atlas_audit.get_connection(), atlas_audit.get_lock()
    actor_service.mark_running(conn, lock, spawned["actor_id"], pid=1)
    actor_service.enqueue_steering(
        conn, lock, spawned["actor_id"], message="prefer the smaller model",
    )

    monkeypatch.setenv("ATLAS_ACTOR_ID", spawned["actor_id"])
    injected = actor_bridge.on_pre_llm_call(session_id="")
    assert injected is not None
    assert "prefer the smaller model" in injected["context"]

    # At-most-once: the second boundary has nothing left to deliver.
    assert actor_bridge.on_pre_llm_call(session_id="") is None


def test_a_process_that_is_not_an_actor_drains_nothing(bound, monkeypatch) -> None:
    monkeypatch.delenv("ATLAS_ACTOR_ID", raising=False)
    assert actor_bridge.on_pre_llm_call(session_id="") is None


def test_logs_before_the_child_run_exists_says_so(bound, monkeypatch) -> None:
    agent, _ = bound
    _launched(monkeypatch)
    spawned = json.loads(
        actor_bridge.atlas_actor_tool(op="spawn", goal="g", parent_agent=agent)
    )
    out = json.loads(
        actor_bridge.atlas_actor_tool(
            op="logs", actor_id=spawned["actor_id"], parent_agent=agent
        )
    )
    assert out["ok"] is True
    assert out["events"] == []
    assert "has not started" in out["note"]


def test_logs_tails_the_child_runs_audit_trail(bound, monkeypatch, run_id) -> None:
    """op=logs reads the audit trail rather than inventing a second log path."""
    agent, _ = bound
    _launched(monkeypatch)
    spawned = json.loads(
        actor_bridge.atlas_actor_tool(op="spawn", goal="g", parent_agent=agent)
    )
    conn, lock = atlas_audit.get_connection(), atlas_audit.get_lock()
    actor_service.mark_running(conn, lock, spawned["actor_id"], pid=1)
    actor_service.attach_child_run(conn, lock, spawned["actor_id"], run_id)
    from atlas_runtime.audit_service import emit

    emit(conn, lock, run_id=run_id, event_type="tool_completed", tool_name="workspace",
         data={"text": "wrote 3 files"})

    out = json.loads(
        actor_bridge.atlas_actor_tool(
            op="logs", actor_id=spawned["actor_id"], parent_agent=agent
        )
    )
    assert out["ok"] is True
    assert out["child_run_id"] == run_id
    assert any(e.get("text") == "wrote 3 files" for e in out["events"])


def test_join_publishes_liveness_while_it_waits(bound, monkeypatch) -> None:
    """A silent 120s join was indistinguishable from a hung agent."""
    agent, _ = bound
    _launched(monkeypatch)
    spawned = json.loads(
        actor_bridge.atlas_actor_tool(op="spawn", goal="g", parent_agent=agent)
    )
    conn, lock = atlas_audit.get_connection(), atlas_audit.get_lock()
    actor_service.mark_running(conn, lock, spawned["actor_id"], pid=1)

    touched: list[str] = []
    agent._touch_activity = touched.append  # the harness's own idle-timer reset

    actor_bridge.atlas_actor_tool(
        op="wait", actor_id=spawned["actor_id"], timeout_seconds=0.4,
        parent_agent=agent,
    )
    assert touched, "no activity touch was issued during the join"

    waiting = conn.execute(
        "SELECT COUNT(*) FROM audit_events WHERE event_type='subagent_run'"
        " AND data LIKE '%\"phase\": \"waiting\"%'"
    ).fetchone()[0]
    assert waiting >= 1, "the first poll must publish a waiting heartbeat"


def test_wakeup_is_off_unless_asked_for(bound, monkeypatch) -> None:
    agent, _ = bound
    _launched(monkeypatch)
    spawned = json.loads(
        actor_bridge.atlas_actor_tool(op="spawn", goal="g", parent_agent=agent)
    )
    stored = actor_service.get_actor(atlas_audit.get_connection(), spawned["actor_id"])
    assert stored["wakeup_parent"] == 0


def test_wakeup_is_recorded_when_requested_on_a_detached_spawn(
    bound, monkeypatch
) -> None:
    agent, _ = bound
    _launched(monkeypatch)
    spawned = json.loads(
        actor_bridge.atlas_actor_tool(
            op="spawn", goal="unattended job", wakeup=True, parent_agent=agent
        )
    )
    stored = actor_service.get_actor(atlas_audit.get_connection(), spawned["actor_id"])
    assert stored["wakeup_parent"] == 1


def test_joined_run_never_requests_a_wakeup(bound, monkeypatch) -> None:
    """op=run is already being waited on; a wakeup would duplicate the result."""
    agent, _ = bound
    conn, lock = atlas_audit.get_connection(), atlas_audit.get_lock()

    def _fake_launch(c, l, actor_id, **kw):  # noqa: ANN001, E741
        actor_service.mark_running(conn, lock, actor_id, pid=1)
        actor_service.complete_actor(conn, lock, actor_id, result_preview="r")
        return 1

    monkeypatch.setattr("atlas_runtime.actor_worker.launch_actor_worker", _fake_launch)
    out = json.loads(
        actor_bridge.atlas_actor_tool(
            op="run", goal="joined job", wakeup=True, timeout_seconds=5,
            parent_agent=agent,
        )
    )
    stored = actor_service.get_actor(conn, out["actor_id"])
    assert stored["wakeup_parent"] == 0
