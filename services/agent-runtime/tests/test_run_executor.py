"""Tests for the async run executor (WP-1, autonomous loop).

Covers the synchronous core (`execute_run`) for success / agent-failure /
unhandled-exception / cancelled-mid-flight, and the background path
(`start_and_execute_async` + `await_run`). Uses a temp FILE DB (not :memory:)
because the worker opens its own connection — a real cross-connection scenario.
"""
from __future__ import annotations

import datetime
import threading
import uuid

import pytest

from atlas_runtime import db as db_module
from atlas_runtime import run_executor
from atlas_runtime.agents.base import AgentRuntime, RunOutcome
from atlas_runtime.run_service import cancel_run, start_run


class _FakeAgent(AgentRuntime):
    name = "fake"

    def __init__(self, *, status: str = "succeeded", summary: str = "ok", raises: bool = False) -> None:
        self._status = status
        self._summary = summary
        self._raises = raises

    def execute(self, conn, lock, *, mission_id, run_id, prompt, cancel_token=None):  # type: ignore[override]
        if self._raises:
            raise RuntimeError("boom")
        return RunOutcome(status=self._status, summary=self._summary)  # type: ignore[arg-type]


@pytest.fixture(name="file_db")
def file_db_fixture(tmp_path):
    path = tmp_path / "atlas.db"
    conn = db_module.connect(path)
    db_module.apply_migrations(conn)
    try:
        yield path, conn
    finally:
        conn.close()


def _new_mission(conn, lock, status: str = "pending") -> str:
    mid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (mid, "executor test", "", status, "", now, now),
            )
    return mid


def _run_status(conn, run_id: str) -> str:
    return conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()[0]


def _mission_status(conn, mid: str) -> str:
    return conn.execute("SELECT status FROM missions WHERE id=?", (mid,)).fetchone()[0]


def test_execute_run_success(file_db):
    _, conn = file_db
    lock = threading.Lock()
    mid = _new_mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)
    outcome = run_executor.execute_run(
        conn, lock, agent=_FakeAgent(status="succeeded", summary="done"),
        mission_id=mid, run_id=run.id, prompt="hi",
    )
    assert outcome.status == "succeeded"
    assert _run_status(conn, run.id) == "succeeded"
    assert _mission_status(conn, mid) == "succeeded"


def test_execute_run_agent_failure(file_db):
    _, conn = file_db
    lock = threading.Lock()
    mid = _new_mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)
    outcome = run_executor.execute_run(
        conn, lock, agent=_FakeAgent(status="failed", summary="nope"),
        mission_id=mid, run_id=run.id, prompt="hi",
    )
    assert outcome.status == "failed"
    assert _run_status(conn, run.id) == "failed"
    assert _mission_status(conn, mid) == "failed"


def test_execute_run_unhandled_exception_fails_run(file_db):
    _, conn = file_db
    lock = threading.Lock()
    mid = _new_mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)
    outcome = run_executor.execute_run(
        conn, lock, agent=_FakeAgent(raises=True), mission_id=mid, run_id=run.id, prompt="hi",
    )
    assert outcome.status == "failed"
    assert "executor" in outcome.summary
    assert _run_status(conn, run.id) == "failed"


def test_execute_run_records_compounding_observation(file_db):
    _, conn = file_db
    lock = threading.Lock()
    mid = _new_mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)
    run_executor.execute_run(
        conn, lock, agent=_FakeAgent(status="succeeded", summary="shipped it"),
        mission_id=mid, run_id=run.id, prompt="hi",
    )
    from atlas_runtime import goal_service

    obs = goal_service.list_observations(conn, run_id=run.id)
    assert len(obs) == 1
    assert obs[0].source == "compounding-loop"
    assert "shipped it" in obs[0].body


def test_cancelled_run_writes_no_compounding_observation(file_db):
    _, conn = file_db
    lock = threading.Lock()
    mid = _new_mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)
    cancel_run(conn, lock, run_id=run.id, mission_id=mid)
    run_executor.execute_run(
        conn, lock, agent=_FakeAgent(status="succeeded"), mission_id=mid, run_id=run.id, prompt="hi",
    )
    from atlas_runtime import goal_service

    # Cancellation wins → the compounding write is skipped.
    assert goal_service.list_observations(conn, run_id=run.id) == []


def test_execute_run_respects_cancellation(file_db):
    _, conn = file_db
    lock = threading.Lock()
    mid = _new_mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)
    cancel_run(conn, lock, run_id=run.id, mission_id=mid)
    # Agent "succeeds", but the run was already cancelled — cancellation wins.
    run_executor.execute_run(
        conn, lock, agent=_FakeAgent(status="succeeded"), mission_id=mid, run_id=run.id, prompt="hi",
    )
    assert _run_status(conn, run.id) == "cancelled"
    assert _mission_status(conn, mid) == "cancelled"


def test_start_and_execute_async_returns_then_completes(file_db):
    path, conn = file_db
    lock = threading.Lock()
    mid = _new_mission(conn, lock)
    run = run_executor.start_and_execute_async(
        conn, lock, mission_id=mid, agent_name="native",
        agent=_FakeAgent(status="succeeded", summary="async done"), prompt="hi",
        conn_factory=lambda: db_module.connect(path),
    )
    # run_id available immediately, without waiting for execution.
    assert run.id
    # Worker drives it to terminal; await the thread then assert.
    assert run_executor.await_run(run.id, timeout=5) is True
    assert _run_status(conn, run.id) == "succeeded"
    assert run.id not in run_executor.active_run_ids()


def test_execute_run_writes_brain_graph(file_db):
    _, conn = file_db
    lock = threading.Lock()
    mid = _new_mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)
    run_executor.execute_run(
        conn, lock, agent=_FakeAgent(status="succeeded", summary="brain evidence"),
        mission_id=mid, run_id=run.id, prompt="hi",
    )
    from atlas_runtime import brain_service

    mission_node = brain_service.explain(conn, f"mission:{mid}")
    run_node = brain_service.explain(conn, f"run:{run.id}")
    assert mission_node is not None and mission_node.entity_type == "mission"
    assert run_node is not None and run_node.entity_type == "run"
    assert "brain evidence" in run_node.label
    edge = conn.execute(
        "SELECT relation FROM brain_edges WHERE source_id=? AND target_id=?",
        (f"mission:{mid}", f"run:{run.id}"),
    ).fetchone()
    assert edge == ("produced",)


def test_brain_nodes_a_run_writes_still_reach_a_brief(file_db):
    """Every writer must state its grade, or its own output disappears.

    `BrainNode.grade` floors an unstated grade at `asserted`, and `asserted` sits
    below the retrieval floor. A writer that forgets to declare therefore keeps
    writing rows that no run will ever be shown — silently, since the write
    succeeds. That is what happened here: the run/mission mirror declared no
    grade, so every terminal run was quietly filing itself out of the graph.
    """
    from atlas_core.schemas import provenance
    from atlas_runtime import brain_service, memory_router as mr

    _, conn = file_db
    lock = threading.Lock()
    mid = _new_mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)
    run_executor.execute_run(
        conn, lock, agent=_FakeAgent(status="succeeded", summary="gateway cors fixed"),
        mission_id=mid, run_id=run.id, prompt="hi",
    )

    assert brain_service.explain(conn, f"run:{run.id}").grade == provenance.OBSERVED
    assert brain_service.explain(conn, f"mission:{mid}").grade == provenance.OBSERVED

    envelope = mr.MemoryRouter(retrievers=[mr.BrainRetriever()]).assemble_envelope(
        conn, mr.RouterQuery(terms=("gateway",))
    )
    assert f"brain:run:{run.id}" not in envelope.rejected_source_ids
    assert "gateway cors fixed" in envelope.markdown


def test_execute_run_brain_labels_are_redacted(file_db):
    _, conn = file_db
    lock = threading.Lock()
    mid = _new_mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)
    run_executor.execute_run(
        conn, lock,
        agent=_FakeAgent(status="succeeded", summary="done api_key=sk-brainleak99"),
        mission_id=mid, run_id=run.id, prompt="hi",
    )
    from atlas_runtime import brain_service

    run_node = brain_service.explain(conn, f"run:{run.id}")
    assert run_node is not None
    assert "sk-brainleak99" not in run_node.label
    assert "[REDACTED]" in run_node.label


def test_cancelled_run_writes_no_brain_graph(file_db):
    _, conn = file_db
    lock = threading.Lock()
    mid = _new_mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)
    cancel_run(conn, lock, run_id=run.id, mission_id=mid)
    run_executor.execute_run(
        conn, lock, agent=_FakeAgent(status="succeeded"), mission_id=mid, run_id=run.id, prompt="hi",
    )
    from atlas_runtime import brain_service

    assert brain_service.explain(conn, f"run:{run.id}") is None
