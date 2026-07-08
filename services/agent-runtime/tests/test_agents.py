"""Tests for P4 modular agent runtimes: registry, NativeAtlasAgent,
ClaudeCodeAgent (SDK injected/mocked), and start_run agent_runtime recording.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import sys
import threading
import uuid

import pytest

from atlas_runtime import focus_service, goal_service, run_service
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
        self.system_messages: list[str | None] = []

    def run_conversation(self, user_message: str, system_message=None):  # noqa: ANN001
        self.calls.append(user_message)
        self.system_messages.append(system_message)
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


def test_native_passes_goal_context_to_harness_system_message(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    focus = focus_service.create_focus(db, lock, title="Ship Command Center", framework="GSD")
    goal = goal_service.create_goal(
        db, lock, title="Wire NativeAtlasAgent to the harness", focus_id=focus.id
    )
    goal_service.create_task(db, lock, goal_id=goal.id, title="pass context as system_message")
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    harness = _FakeHarness(
        {"final_response": "ok", "api_calls": 1, "completed": True, "failed": False, "error": None}
    )

    outcome = NativeAtlasAgent(agent_factory=lambda session_id: harness).execute(
        db, lock, mission_id=mid, run_id=rid, prompt="advance the focus"
    )

    assert outcome.status == "succeeded"
    assert harness.calls == ["advance the focus"]
    assert len(harness.system_messages) == 1
    system_message = harness.system_messages[0] or ""
    assert "# ATLAS Run Contract" in system_message
    assert "Ship Command Center" in system_message
    assert "Wire NativeAtlasAgent to the harness" in system_message
    assert "pass context as system_message" in system_message
    assert "## Operating Contract" in system_message


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


def test_native_collapses_html_error(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    html = "<!DOCTYPE html><html><head></head><body>403 Forbidden</body></html>"
    agent = _native_with(
        {"final_response": "", "api_calls": 1, "completed": False, "failed": True, "error": html}
    )
    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="x")
    assert outcome.status == "failed"
    assert "<html" not in outcome.summary.lower()
    assert "HTML error page" in outcome.summary


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


class ToolResultBlock:
    def __init__(self, tool_use_id: str, content, is_error: bool = False) -> None:  # noqa: ANN001
        self.tool_use_id = tool_use_id
        self.content = content
        self.is_error = is_error


class UserMessage:
    def __init__(self, content: list) -> None:
        self.content = content


def test_claude_code_tool_results_pair_with_calls(db: sqlite3.Connection, lock: threading.Lock) -> None:
    """Tool results must emit tool_completed with the pairing id inside data —
    the surface projection only carries the data payload, so web/TUI tool cards
    need tool_call_id there to flip RUNNING -> DONE."""
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    msgs = [
        AssistantMessage([ToolUseBlock("grep", "tu1", {"q": "x"})]),
        UserMessage([ToolResultBlock("tu1", [{"type": "text", "text": "3 matches"}])]),
        ResultMessage(is_error=False),
    ]
    agent = ClaudeCodeAgent(query_fn=_make_query(msgs))
    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="do x")
    assert outcome.status == "succeeded"
    events = get_events_for_run(db, rid)
    calls = [e for e in events if e.event_type == "tool_call"]
    results = [e for e in events if e.event_type == "tool_completed"]
    assert len(calls) == 1 and len(results) == 1
    call_data = json.loads(calls[0].data)
    result_data = json.loads(results[0].data)
    assert call_data["tool_name"] == "grep"
    assert call_data["tool_call_id"] == "tu1"
    assert result_data["tool_call_id"] == "tu1"
    assert "3 matches" in result_data["summary"]


def test_claude_code_failed_tool_result_emits_tool_failed(
    db: sqlite3.Connection,
    lock: threading.Lock,
) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    msgs = [
        AssistantMessage([ToolUseBlock("grep", "tu1", {"q": "x"})]),
        UserMessage([ToolResultBlock("tu1", "permission denied", is_error=True)]),
        ResultMessage(is_error=False),
    ]
    agent = ClaudeCodeAgent(query_fn=_make_query(msgs))

    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="do x")

    assert outcome.status == "succeeded"
    events = get_events_for_run(db, rid)
    failures = [event for event in events if event.event_type == "tool_failed"]
    assert len(failures) == 1
    assert not [event for event in events if event.event_type == "tool_completed"]
    failure_data = json.loads(failures[0].data)
    assert failure_data["tool_call_id"] == "tu1"
    assert failure_data["is_error"] is True
    assert failure_data["summary"] == "permission denied"


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


def test_claude_code_missing_sdk_raises(monkeypatch) -> None:
    """_resolve() must fail closed with a clear remediation when the optional
    claude-agent-sdk is absent. Forced deterministically (the SDK may or may not
    be installed in a given venv) by making its import fail."""
    import pytest

    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
    agent = ClaudeCodeAgent()
    with pytest.raises(RuntimeError, match="claude-agent-sdk is not installed"):
        agent._resolve()


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
