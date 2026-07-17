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
from atlas_runtime.agents.native import (
    NativeAtlasAgent,
    _DeltaBuffer,
    _repair_cumulative_final,
)
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
    assert known_agents() == ["claude_code", "codex", "native"]


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


def test_native_final_surface_event_is_not_capped_to_run_summary(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    final_response = "A" * 2_400 + "\nCOMPLETE_ENDING"
    agent = _native_with(
        {
            "final_response": final_response,
            "api_calls": 1,
            "completed": True,
            "failed": False,
            "error": None,
        }
    )

    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="long answer")

    # Durable run metadata remains compact for list/retrieval surfaces.
    assert len(outcome.summary) == 2_000
    # The llm_call text is the authoritative chat reconcile and must remain whole.
    final_event = next(e for e in get_events_for_run(db, rid) if e.event_type == "llm_call")
    payload = json.loads(final_event.data)
    assert payload["text"] == final_response
    assert payload["text_length"] == len(final_response)
    assert payload["text"].endswith("COMPLETE_ENDING")


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
    assert "## Core Operating Policy" in system_message
    assert "You are ATLAS" in system_message
    assert "verified-live" in system_message
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


def test_native_streams_deltas_into_llm_delta_events(
    db: sqlite3.Connection, lock: threading.Lock, monkeypatch
) -> None:
    """execute()'s real-provider branch must thread stream_delta_callback into
    _default_factory, and the foundation's chunk/None protocol must coalesce
    into llm_delta audit events without duplicating the final llm_call text."""
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    captured: dict = {}

    def fake_default_factory(session_id, max_iterations, *, stream_delta_callback=None, **kw):
        captured["callback"] = stream_delta_callback

        class _StreamingHarness:
            def run_conversation(self, user_message, system_message=None):  # noqa: ANN001
                stream_delta_callback("Hello")
                stream_delta_callback(", world")
                stream_delta_callback(None)
                return {
                    "final_response": "Hello, world",
                    "api_calls": 1,
                    "completed": True,
                    "failed": False,
                    "error": None,
                }

        return _StreamingHarness()

    monkeypatch.setattr("atlas_runtime.agents.native._default_factory", fake_default_factory)
    monkeypatch.setattr(
        NativeAtlasAgent, "_resolve_provider", lambda self, conn, run_id=None: ("m", "p", None, "sk-real", "api_key")
    )
    outcome = NativeAtlasAgent().execute(db, lock, mission_id=mid, run_id=rid, prompt="hi")

    assert outcome.status == "succeeded"
    assert captured["callback"] is not None
    events = get_events_for_run(db, rid)
    deltas = [e for e in events if e.event_type == "llm_delta"]
    assert len(deltas) == 1  # fast synchronous chunks coalesce into one flush-on-None
    payload = json.loads(deltas[0].data)
    assert payload["delta"] == "Hello, world"
    assert payload["end_of_turn"] is True
    llm_calls = [e for e in events if e.event_type == "llm_call"]
    assert any(json.loads(e.data).get("text") == "Hello, world" for e in llm_calls)


def test_native_flushes_delta_buffer_when_foundation_never_signals_end_of_turn(
    db: sqlite3.Connection, lock: threading.Lock, monkeypatch
) -> None:
    """The vendored foundation only calls stream_delta_callback(None) at tool
    boundaries — never after a final, no-tool-call response (ULTRAREVIEW-
    streaming-duplication-DEEP finding 1). execute() must flush the buffer
    itself once run_conversation() returns so short/simple turns still emit
    a closing llm_delta(end_of_turn=True) instead of dropping the remainder."""
    mid = _pending_mission(db)
    rid = _running_run(db, mid)

    def fake_default_factory(session_id, max_iterations, *, stream_delta_callback=None, **kw):
        class _NoNoneHarness:
            def run_conversation(self, user_message, system_message=None):  # noqa: ANN001
                stream_delta_callback("Hey")
                stream_delta_callback(" there")
                # deliberately NOT calling stream_delta_callback(None) — mirrors
                # the real foundation's final-response gap.
                return {
                    "final_response": "Hey there",
                    "api_calls": 1,
                    "completed": True,
                    "failed": False,
                    "error": None,
                }

        return _NoNoneHarness()

    monkeypatch.setattr("atlas_runtime.agents.native._default_factory", fake_default_factory)
    monkeypatch.setattr(
        NativeAtlasAgent, "_resolve_provider", lambda self, conn, run_id=None: ("m", "p", None, "sk-real", "api_key")
    )
    outcome = NativeAtlasAgent().execute(db, lock, mission_id=mid, run_id=rid, prompt="hi")

    assert outcome.status == "succeeded"
    events = get_events_for_run(db, rid)
    deltas = [e for e in events if e.event_type == "llm_delta"]
    assert len(deltas) == 1
    payload = json.loads(deltas[0].data)
    assert payload["delta"] == "Hey there"
    assert payload["end_of_turn"] is True


def test_delta_buffer_flushes_on_char_threshold() -> None:
    flushes: list[tuple[str, bool]] = []
    buf = _DeltaBuffer(lambda text, final: flushes.append((text, final)), interval_s=999, max_chars=5)
    buf.push("ab")
    assert flushes == []
    buf.push("cd")
    assert flushes == []
    buf.push("ef")  # accumulated 6 chars >= max_chars(5)
    assert flushes == [("abcdef", False)]
    buf.push(None)
    assert flushes == [("abcdef", False), ("", True)]


def test_delta_buffer_flushes_on_interval_threshold(monkeypatch) -> None:
    flushes: list[tuple[str, bool]] = []
    clock = {"t": 0.0}
    monkeypatch.setattr("atlas_runtime.agents.native.time.monotonic", lambda: clock["t"])
    buf = _DeltaBuffer(lambda text, final: flushes.append((text, final)), interval_s=0.1, max_chars=999)
    buf.push("a")
    assert flushes == []
    clock["t"] = 0.2
    buf.push("b")
    assert flushes == [("ab", False)]


def test_delta_buffer_none_without_prior_push_is_noop() -> None:
    flushes: list[tuple[str, bool]] = []
    buf = _DeltaBuffer(lambda text, final: flushes.append((text, final)))
    buf.push(None)
    assert flushes == []


def test_delta_buffer_splits_on_mid_tool_call_retry_marker() -> None:
    """R3 fix: the foundation's mid-tool-call silent stream retry
    (chat_completion_helpers.py ~2144-2186) re-streams a turn's preamble from
    scratch after a transient connection drop, firing the "Connection dropped
    mid tool-call" marker through stream_delta_callback with no end-of-turn
    signal in between — without the split, the pre-drop and retried preambles
    would concatenate into one seamless, garbled-looking duplicate part.
    """
    flushes: list[tuple[str, bool]] = []
    buf = _DeltaBuffer(lambda text, final: flushes.append((text, final)), interval_s=999, max_chars=999)
    buf.push("Let me check that for you")
    assert flushes == []
    buf.push("\n\n⚠ Connection dropped mid tool-call; reconnecting…\n\n")
    # The pre-drop segment closes as its own final part...
    assert flushes == [("Let me check that for you", True)]
    buf.push("Let me check that for you again")
    buf.push(None)
    # ...and the marker + regenerated text form a distinct second part.
    assert flushes == [
        ("Let me check that for you", True),
        ("\n\n⚠ Connection dropped mid tool-call; reconnecting…\n\nLet me check that for you again", True),
    ]


def test_delta_buffer_retry_marker_without_open_turn_is_not_split() -> None:
    """A marker-shaped chunk arriving as the FIRST chunk of a turn (no prior
    open segment) is just normal text — nothing to split."""
    flushes: list[tuple[str, bool]] = []
    buf = _DeltaBuffer(lambda text, final: flushes.append((text, final)), interval_s=999, max_chars=999)
    buf.push("\n\n⚠ Connection dropped mid tool-call; reconnecting…\n\n")
    buf.push(None)
    assert flushes == [("\n\n⚠ Connection dropped mid tool-call; reconnecting…\n\n", True)]


def test_delta_buffer_diffs_cumulative_chunk_to_new_suffix() -> None:
    """ULTRAREVIEW R4: some upstream providers (observed: Gemini via
    freellmapi) resend the full text accumulated so far in a chunk instead
    of just the new fragment. ATLAS's _DeltaBuffer is the single choke point
    every streaming surface consumes through — it must not trust the
    provider mesh to always honor the incremental-delta contract, since a
    fix on one sidecar (freellmapi) doesn't protect against a different
    misbehaving upstream in the future.
    """
    flushes: list[tuple[str, bool]] = []
    buf = _DeltaBuffer(lambda text, final: flushes.append((text, final)), interval_s=999, max_chars=999)
    buf.push("Qual deles")
    buf.push("Qual deles você quer atacar?")
    buf.push(None)
    assert flushes == [("Qual deles você quer atacar?", True)]


def test_delta_buffer_drops_exact_repeat_chunk() -> None:
    flushes: list[tuple[str, bool]] = []
    buf = _DeltaBuffer(lambda text, final: flushes.append((text, final)), interval_s=999, max_chars=999)
    buf.push("hello")
    buf.push("hello")  # stray exact repeat — no new content
    buf.push(None)
    assert flushes == [("hello", True)]


def test_delta_buffer_resets_cumulative_tracking_across_turns() -> None:
    """A closed turn's accumulated text must not be diffed against the next
    turn's chunks — a coincidental prefix match across turns should not
    silently eat the next turn's opening text."""
    flushes: list[tuple[str, bool]] = []
    buf = _DeltaBuffer(lambda text, final: flushes.append((text, final)), interval_s=999, max_chars=999)
    buf.push("Sure, one moment")
    buf.push(None)
    buf.push("Sure, one moment please")  # new turn; happens to share a prefix
    buf.push(None)
    assert flushes == [
        ("Sure, one moment", True),
        ("Sure, one moment please", True),
    ]


def test_delta_buffer_records_last_turn_text() -> None:
    buf = _DeltaBuffer(lambda text, final: None, interval_s=999, max_chars=999)
    buf.push("Qual deles")
    buf.push("Qual deles você quer atacar?")  # cumulative resend
    buf.push(None)
    assert buf.last_turn_text == "Qual deles você quer atacar?"
    buf.push(None)  # redundant close (no open turn) must not clobber it
    assert buf.last_turn_text == "Qual deles você quer atacar?"


def test_repair_cumulative_final_strips_prefix_concatenation() -> None:
    truth = "Qual deles você quer atacar?"
    corrupted = "Qual deles" + truth  # foundation joined raw cumulative chunks
    assert _repair_cumulative_final(corrupted, truth) == truth


def test_repair_cumulative_final_multi_piece_head() -> None:
    truth = "ABC"
    corrupted = "A" + "AB" + truth  # p1 + p2 + full text
    assert _repair_cumulative_final(corrupted, truth) == truth


def test_repair_cumulative_final_leaves_honest_text_alone() -> None:
    assert _repair_cumulative_final("hello world", "hello world") == "hello world"
    # Legitimately different final (footer appended, think-block stripped,
    # non-stream path) must pass through untouched.
    assert _repair_cumulative_final("hello world\n\n-- footer", "hello world") == "hello world\n\n-- footer"
    assert _repair_cumulative_final("something else entirely", "hello world") == "something else entirely"
    # No streamed truth available (non-streaming factory) — no-op.
    assert _repair_cumulative_final("hello world", "") == "hello world"


def test_repair_cumulative_final_rejects_non_prefix_head() -> None:
    truth = "you want to attack?"
    # Ends with truth but the head is real content, not stale prefixes.
    legit = "Which one do " + truth
    assert _repair_cumulative_final(legit, truth) == legit


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


def test_json_safe_preview_caps_and_roundtrips() -> None:
    from atlas_runtime.agents.native import _json_safe_preview

    assert _json_safe_preview("x" * 50, 10) == "x" * 10
    assert _json_safe_preview({"cmd": "ls", "n": 3}, 2000) == {"cmd": "ls", "n": 3}
    # Non-serializable values degrade to strings instead of failing the run.
    class Weird:
        def __str__(self) -> str:
            return "weird"
    assert "weird" in json.dumps(_json_safe_preview({"o": Weird()}, 2000))
    # Oversized structures degrade to a capped JSON string.
    big = _json_safe_preview({"k": "y" * 5000}, 100)
    assert isinstance(big, str) and len(big) == 100
