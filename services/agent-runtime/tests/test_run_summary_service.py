"""Tests for atlas_runtime.run_summary_service.generate_run_summary and
atlas_core.schemas.run_summary.RunSummary (Phase 3 Track A, F8).

Deterministic extraction (tools_used/completed_actions/files_touched/
blockers/duration_ms/outcome fallback) is tested WITHOUT any LLM — it never
calls one. The narrative fields (goal/outcome override/key_decisions/
next_actions) are tested with an injected `synthesize` stub, per the task's
explicit instruction to test deterministic extraction without a real LLM
call and to mock the synthesis step.
"""
from __future__ import annotations

import datetime
import json

from atlas_core.schemas.core import AuditEvent
from atlas_core.schemas.run_summary import RunSummary
from atlas_runtime import run_summary_service


def _event(
    run_id: str,
    event_type: str,
    *,
    tool_name: str | None = None,
    data: dict | None = None,
    offset_seconds: float = 0.0,
) -> AuditEvent:
    base = datetime.datetime(2026, 7, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
    return AuditEvent(
        run_id=run_id,
        event_type=event_type,
        tool_name=tool_name,
        data=json.dumps(data or {}),
        timestamp=base + datetime.timedelta(seconds=offset_seconds),
    )


# ---------------------------------------------------------------------------
# RunSummary schema
# ---------------------------------------------------------------------------


def test_run_summary_json_round_trips():
    summary = RunSummary(
        goal="ship the thing",
        outcome="succeeded",
        completed_actions=["terminal", "read_file"],
        key_decisions=["used sqlite for storage"],
        files_touched=["a.py", "b.py"],
        blockers=[],
        tools_used={"terminal": 2, "read_file": 1},
        duration_ms=1500,
        next_actions=["write tests"],
    )
    restored = RunSummary.from_json(summary.to_json())
    assert restored == summary


def test_run_summary_from_json_rejects_legacy_free_text():
    assert RunSummary.from_json("agent finished the task successfully") is None


def test_run_summary_from_json_rejects_empty_and_malformed():
    assert RunSummary.from_json("") is None
    assert RunSummary.from_json(None) is None
    assert RunSummary.from_json("{not valid json") is None
    assert RunSummary.from_json("[1, 2, 3]") is None  # valid JSON, not an object


def test_run_summary_from_json_tolerates_partial_payload():
    """A structured payload missing newer fields still parses (forward compat)."""
    restored = RunSummary.from_json(json.dumps({"goal": "x", "outcome": "succeeded"}))
    assert restored is not None
    assert restored.goal == "x"
    assert restored.outcome == "succeeded"
    assert restored.blockers == []
    assert restored.tools_used == {}


# ---------------------------------------------------------------------------
# Deterministic extraction — no LLM involved
# ---------------------------------------------------------------------------


def test_deterministic_tools_used_and_completed_actions():
    events = [
        _event("r1", "tool_requested", tool_name="terminal", offset_seconds=0),
        _event("r1", "tool_completed", tool_name="terminal", offset_seconds=1),
        _event("r1", "tool_requested", tool_name="read_file", offset_seconds=2),
        _event("r1", "tool_completed", tool_name="read_file", offset_seconds=3),
        _event("r1", "tool_completed", tool_name="terminal", offset_seconds=4),
    ]
    summary = run_summary_service.generate_run_summary(events, synthesize=lambda *_a, **_kw: {})
    assert summary.tools_used == {"terminal": 2, "read_file": 1}
    assert summary.completed_actions == ["terminal", "read_file", "terminal"]


def test_deterministic_excludes_bookkeeping_tools():
    events = [
        _event("r1", "tool_call", tool_name="native_runtime", offset_seconds=0),
        _event("r1", "tool_completed", tool_name="mock", offset_seconds=1),
        _event("r1", "tool_completed", tool_name="terminal", offset_seconds=2),
    ]
    summary = run_summary_service.generate_run_summary(events, synthesize=lambda *_a, **_kw: {})
    assert summary.tools_used == {"terminal": 1}
    assert "mock" not in summary.tools_used
    assert "native_runtime" not in summary.tools_used


def test_deterministic_files_touched_from_tool_requested_arguments():
    events = [
        _event(
            "r1", "tool_requested", tool_name="read_file",
            data={"tool": "read_file", "arguments": {"path": "src/main.py", "offset": 1}},
        ),
        _event("r1", "tool_completed", tool_name="read_file", offset_seconds=1),
        _event(
            "r1", "tool_requested", tool_name="write_file",
            data={"tool": "write_file", "arguments": {"path": "src/main.py"}},
            offset_seconds=2,
        ),
    ]
    summary = run_summary_service.generate_run_summary(events, synthesize=lambda *_a, **_kw: {})
    # Deduplicated — same path referenced twice.
    assert summary.files_touched == ["src/main.py"]


def test_deterministic_blockers_from_tool_failed_and_failure_events():
    events = [
        _event(
            "r1", "tool_failed", tool_name="terminal",
            data={"error": "command exited 1"},
        ),
        _event(
            "r1", "failure",
            data={"runtime": "native", "error": "secret detected in prompt"},
            offset_seconds=1,
        ),
    ]
    summary = run_summary_service.generate_run_summary(events, synthesize=lambda *_a, **_kw: {})
    assert "command exited 1" in summary.blockers
    assert "secret detected in prompt" in summary.blockers
    # A tool_failed event still counts toward tools_used (it was attempted).
    assert summary.tools_used == {"terminal": 1}


def test_deterministic_outcome_fallback_succeeded_from_goal_judgement():
    events = [
        _event("r1", "tool_completed", tool_name="terminal", offset_seconds=0),
        _event(
            "r1", "goal_judgement",
            data={"verdict": "done", "reason": "objective met"},
            offset_seconds=1,
        ),
    ]
    summary = run_summary_service.generate_run_summary(events, synthesize=lambda *_a, **_kw: {})
    assert summary.outcome == "succeeded"
    assert any("judged: done" in a for a in summary.completed_actions)


def test_deterministic_outcome_fallback_failed_when_blockers_present_no_judgement():
    events = [
        _event("r1", "tool_failed", tool_name="terminal", data={"error": "boom"}),
    ]
    summary = run_summary_service.generate_run_summary(events, synthesize=lambda *_a, **_kw: {})
    assert summary.outcome == "failed"


def test_deterministic_duration_ms_from_first_and_last_event_timestamps():
    events = [
        _event("r1", "tool_completed", tool_name="terminal", offset_seconds=0),
        _event("r1", "tool_completed", tool_name="read_file", offset_seconds=2.5),
    ]
    summary = run_summary_service.generate_run_summary(events, synthesize=lambda *_a, **_kw: {})
    assert summary.duration_ms == 2500


def test_deterministic_duration_ms_zero_for_single_event():
    events = [_event("r1", "tool_completed", tool_name="terminal")]
    summary = run_summary_service.generate_run_summary(events, synthesize=lambda *_a, **_kw: {})
    assert summary.duration_ms == 0


def test_deterministic_subagent_run_completed_and_stub_shapes():
    events = [
        # native.py's rich shape: terminal record with phase="completed".
        _event(
            "r1", "subagent_run",
            data={"phase": "completed", "goal": "research X", "status": "succeeded"},
        ),
        # subagent_service.dispatch_subagent's stub shape: no "phase" key at all.
        _event(
            "r1", "subagent_run",
            data={"role": "researcher", "model_tier": "sonnet"},
            offset_seconds=1,
        ),
    ]
    summary = run_summary_service.generate_run_summary(events, synthesize=lambda *_a, **_kw: {})
    assert any("research X" in a for a in summary.completed_actions)
    assert any("delegated to researcher" in a for a in summary.completed_actions)


def test_empty_events_produce_empty_summary():
    summary = run_summary_service.generate_run_summary([], synthesize=lambda *_a, **_kw: {})
    assert summary == RunSummary()


# ---------------------------------------------------------------------------
# Narrative synthesis — injected stub, never a real LLM call
# ---------------------------------------------------------------------------


def test_synthesize_stub_fills_narrative_fields():
    events = [_event("r1", "tool_completed", tool_name="terminal")]

    def stub(_events, _deterministic):
        return {
            "goal": "ship the RTK/F8 track",
            "outcome": "succeeded: all tests pass",
            "key_decisions": ["used dataclasses for RunSummary"],
            "next_actions": ["wire retrievers"],
        }

    summary = run_summary_service.generate_run_summary(events, synthesize=stub)
    assert summary.goal == "ship the RTK/F8 track"
    assert summary.outcome == "succeeded: all tests pass"
    assert summary.key_decisions == ["used dataclasses for RunSummary"]
    assert summary.next_actions == ["wire retrievers"]


def test_synthesize_failure_falls_back_to_deterministic_outcome():
    events = [_event("r1", "tool_failed", tool_name="terminal", data={"error": "boom"})]

    def broken_stub(_events, _deterministic):
        raise RuntimeError("provider unreachable")

    summary = run_summary_service.generate_run_summary(events, synthesize=broken_stub)
    # Deterministic outcome fallback ("failed", from the blocker) survives a
    # synthesis failure — generate_run_summary never raises or blocks.
    assert summary.outcome == "failed"
    assert summary.goal == ""


def test_synthesize_empty_result_preserves_deterministic_outcome():
    events = [
        _event("r1", "tool_completed", tool_name="terminal"),
        _event("r1", "goal_judgement", data={"verdict": "done"}, offset_seconds=1),
    ]
    summary = run_summary_service.generate_run_summary(events, synthesize=lambda *_a, **_kw: {})
    assert summary.outcome == "succeeded"  # deterministic fallback, not overwritten by ""
