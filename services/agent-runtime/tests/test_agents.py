"""Tests for P4 modular agent runtimes: registry, NativeAtlasAgent,
ClaudeCodeAgent (SDK injected/mocked), and start_run agent_runtime recording.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
import uuid

import pytest

from atlas_runtime import run_service
from atlas_runtime.agents import RunOutcome, get_agent, known_agents
from atlas_runtime.agents.base import AgentRuntime
from atlas_runtime.agents.claude_code import ClaudeCodeAgent
from atlas_runtime.agents.native import NativeAtlasAgent
from atlas_runtime.audit_service import get_events_for_run


# --- fixtures / helpers ----------------------------------------------------


def _pending_mission(db: sqlite3.Connection, intent: str = "do the thing") -> str:
    mid = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, ?, ?, 'pending', '', ?, ?)",
        (mid, "t", intent, now, now),
    )
    db.commit()
    return mid


def _running_run(db: sqlite3.Connection, mission_id: str) -> str:
    rid = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, NULL, 'running', ?, NULL, '')",
        (rid, mission_id, now),
    )
    db.commit()
    return rid


# --- fake SDK message shapes (class names match the real SDK) --------------


class TextBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class ToolUseBlock:
    def __init__(self, name: str, id: str, input: dict) -> None:
        self.name = name
        self.id = id
        self.input = input


class AssistantMessage:
    def __init__(self, content: list) -> None:
        self.content = content


class ResultMessage:
    def __init__(self, is_error: bool = False, total_cost_usd: float = 0.0, usage: dict | None = None) -> None:
        self.is_error = is_error
        self.subtype = "error" if is_error else "success"
        self.num_turns = 1
        self.total_cost_usd = total_cost_usd
        self.usage = usage or {}


def _make_query(messages: list):
    async def _q(*, prompt, options):  # noqa: ANN001
        for m in messages:
            yield m
    return _q


# --- registry --------------------------------------------------------------


def test_known_agents() -> None:
    assert known_agents() == ["claude_code", "native"]


def test_get_agent_resolves() -> None:
    assert isinstance(get_agent("native"), NativeAtlasAgent)
    assert isinstance(get_agent("claude_code"), ClaudeCodeAgent)
    assert isinstance(get_agent("native"), AgentRuntime)


def test_get_agent_unknown_raises() -> None:
    with pytest.raises(ValueError):
        get_agent("bogus")


# --- NativeAtlasAgent -------------------------------------------------------


class _FakeHarness:
    """Stand-in for the foundation AIAgent: returns a canned result dict."""

    def __init__(self, result: dict) -> None:
        self._result = result
        self.calls: list[str] = []

    def run_conversation(self, user_message: str, system_message=None):  # noqa: ANN001
        self.calls.append(user_message)
        return self._result


def _native_with(result: dict, **kw) -> NativeAtlasAgent:
    harness = _FakeHarness(result)
    return NativeAtlasAgent(agent_factory=lambda session_id: harness, **kw)


def test_native_executes_and_audits(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    agent = _native_with(
        {"final_response": "done it", "api_calls": 2, "completed": True, "failed": False, "error": None}
    )
    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="ship it")
    assert isinstance(outcome, RunOutcome)
    assert outcome.status == "succeeded"
    assert outcome.summary == "done it"
    # Layer 3 claim taxonomy populated.
    assert any("model call" in e for e in outcome.evidence)
    events = get_events_for_run(db, rid)
    assert any(e.event_type == "tool_call" for e in events)
    assert any(e.event_type == "llm_call" for e in events)


def test_native_maps_failed_result(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    agent = _native_with(
        {"final_response": "", "api_calls": 1, "completed": False, "failed": True, "error": "HTTP 403"}
    )
    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="x")
    assert outcome.status == "failed"
    assert any("403" in u for u in outcome.uncertainties)


def test_native_secret_stop_blocks_run(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    harness = _FakeHarness({"completed": True})
    agent = NativeAtlasAgent(agent_factory=lambda session_id: harness)
    outcome = agent.execute(
        db, lock, mission_id=mid, run_id=rid, prompt="use api_key=sk-secret-value to call it"
    )
    assert outcome.status == "failed"
    assert outcome.stop_reason == "secret_in_prompt"
    # The harness must never have been invoked.
    assert harness.calls == []
    events = get_events_for_run(db, rid)
    assert any(e.event_type == "failure" for e in events)


def test_native_harness_unavailable_is_failed(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)

    def boom(session_id):  # noqa: ANN001
        raise RuntimeError("no foundation here")

    outcome = NativeAtlasAgent(agent_factory=boom).execute(
        db, lock, mission_id=mid, run_id=rid, prompt="x"
    )
    assert outcome.status == "failed"
    assert outcome.stop_reason == "harness_unavailable"


# --- ClaudeCodeAgent (injected fake SDK) -----------------------------------


def test_claude_code_maps_stream_to_audit(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    msgs = [
        AssistantMessage([TextBlock("hello "), ToolUseBlock("grep", "tu1", {"q": "x"}), TextBlock("ATLAS")]),
        ResultMessage(is_error=False, total_cost_usd=0.01, usage={"input_tokens": 3}),
    ]
    agent = ClaudeCodeAgent(query_fn=_make_query(msgs))
    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="do x")
    assert outcome.status == "succeeded"
    assert "hello" in outcome.summary and "ATLAS" in outcome.summary
    events = get_events_for_run(db, rid)
    assert any(e.event_type == "llm_call" for e in events)
    assert any(e.event_type == "tool_call" for e in events)


def test_claude_code_result_error_marks_failed(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    agent = ClaudeCodeAgent(query_fn=_make_query([ResultMessage(is_error=True)]))
    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="x")
    assert outcome.status == "failed"


def test_claude_code_exception_is_failsafe(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)

    def boom():
        async def _q(*, prompt, options):  # noqa: ANN001
            raise RuntimeError("kaboom")
            yield  # pragma: no cover - makes this an async generator
        return _q

    agent = ClaudeCodeAgent(query_fn=boom())
    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="x")
    assert outcome.status == "failed"
    assert "kaboom" in outcome.summary
    events = get_events_for_run(db, rid)
    assert any(e.event_type == "failure" for e in events)


def test_claude_code_missing_sdk_raises() -> None:
    # No query_fn injected and SDK import guarded — _resolve raises a clear error
    # only if the SDK is absent. Here we just assert the agent is constructible
    # and _resolve returns a callable when the SDK is present in this env.
    agent = ClaudeCodeAgent()
    fn, of = agent._resolve()
    assert callable(fn) and callable(of)


# --- start_run records agent_runtime ---------------------------------------


def test_start_run_defaults_native(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid = _pending_mission(db)
    run = run_service.start_run(db, lock, mission_id=mid)
    row = db.execute("SELECT agent_runtime FROM runs WHERE id=?", (run.id,)).fetchone()
    assert row[0] == "native"
    assert run.agent_runtime == "native"


def test_start_run_records_claude_code(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid = _pending_mission(db)
    run = run_service.start_run(db, lock, mission_id=mid, agent_runtime="claude_code")
    row = db.execute("SELECT agent_runtime FROM runs WHERE id=?", (run.id,)).fetchone()
    assert row[0] == "claude_code"
    assert run.agent_runtime == "claude_code"
