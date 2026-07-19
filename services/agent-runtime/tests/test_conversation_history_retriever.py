"""Tests for atlas_runtime.memory_router.ConversationHistoryRetriever — the
budget-aware, cross-run session-history section that replaces native.py's raw
audit_events replay (Phase 2 Track A).

Covers: no-session-id no-op, summary-present, summary-absent tool-fingerprint
fallback, max_runs cap, and token-budget enforcement — plus the
history_snippets_to_messages conversion boundary (assistant vs. tool roles,
redaction).
"""
from __future__ import annotations

import datetime
import uuid

from atlas_runtime import memory_router as mr


def _mission_row(conn, lock) -> str:
    mid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (mid, "m", "", "pending", "", now, now),
            )
    return mid


def _run_row(
    conn,
    lock,
    *,
    mission_id: str,
    session_id: str,
    summary: str = "",
    status: str = "succeeded",
    started_at: str | None = None,
) -> str:
    """Insert a minimal completed run row belonging to `session_id`."""
    rid = uuid.uuid4().hex
    now = started_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO runs(id,mission_id,session_id,status,started_at,finished_at,summary) "
                "VALUES (?,?,?,?,?,?,?)",
                (rid, mission_id, session_id, status, now, now, summary),
            )
    return rid


def _audit_event_row(conn, lock, *, run_id: str) -> str:
    """Insert a minimal audit_events row so tool_calls.audit_event_id FK is satisfied."""
    aid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO audit_events(id,run_id,event_type,timestamp,data) "
                "VALUES (?,?,?,?,?)",
                (aid, run_id, "tool_call", now, "{}"),
            )
    return aid


def _tool_call_row(
    conn, lock, *, run_id: str, tool_name: str, args: str = "{}", exit_code: int | None = 0
) -> None:
    aid = _audit_event_row(conn, lock, run_id=run_id)
    tid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO tool_calls(id,audit_event_id,run_id,tool_name,args,exit_code,timestamp) "
                "VALUES (?,?,?,?,?,?,?)",
                (tid, aid, run_id, tool_name, args, exit_code, now),
            )


# ---------------------------------------------------------------------------


def test_no_session_id_returns_empty(db):
    snippets = mr.ConversationHistoryRetriever().retrieve(db, mr.RouterQuery(session_id=None))
    assert snippets == []


def test_single_prior_run_with_summary(db, lock):
    mid = _mission_row(db, lock)
    sid = uuid.uuid4().hex
    run_id = _run_row(db, lock, mission_id=mid, session_id=sid, summary="fixed the bug in parser")

    snippets = mr.ConversationHistoryRetriever().retrieve(db, mr.RouterQuery(session_id=sid))
    assert len(snippets) == 1
    assert snippets[0].source == f"run_summary:{run_id}"
    assert "fixed the bug in parser" in snippets[0].text


def test_single_prior_run_without_summary_falls_back_to_tool_fingerprint(db, lock):
    mid = _mission_row(db, lock)
    sid = uuid.uuid4().hex
    run_id = _run_row(db, lock, mission_id=mid, session_id=sid, summary="")
    _tool_call_row(db, lock, run_id=run_id, tool_name="Read", args='{"path":"foo.py"}', exit_code=0)
    _tool_call_row(db, lock, run_id=run_id, tool_name="Bash", args='{"command":"pytest"}', exit_code=1)

    snippets = mr.ConversationHistoryRetriever().retrieve(db, mr.RouterQuery(session_id=sid))
    assert len(snippets) == 1
    assert snippets[0].source == f"run_tools:{run_id}"
    assert "Read(" in snippets[0].text
    assert "Bash(" in snippets[0].text
    assert "exit 1" in snippets[0].text


def test_run_without_summary_or_tool_calls_is_skipped(db, lock):
    mid = _mission_row(db, lock)
    sid = uuid.uuid4().hex
    _run_row(db, lock, mission_id=mid, session_id=sid, summary="")

    snippets = mr.ConversationHistoryRetriever().retrieve(db, mr.RouterQuery(session_id=sid))
    assert snippets == []


def test_only_succeeded_or_completed_runs_are_considered(db, lock):
    mid = _mission_row(db, lock)
    sid = uuid.uuid4().hex
    _run_row(db, lock, mission_id=mid, session_id=sid, summary="failed attempt", status="failed")
    ok_run = _run_row(db, lock, mission_id=mid, session_id=sid, summary="succeeded attempt", status="succeeded")

    snippets = mr.ConversationHistoryRetriever().retrieve(db, mr.RouterQuery(session_id=sid))
    assert [s.source for s in snippets] == [f"run_summary:{ok_run}"]


def test_multiple_runs_capped_at_max_runs(db, lock):
    mid = _mission_row(db, lock)
    sid = uuid.uuid4().hex
    base = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    run_ids = []
    for i in range(8):
        started = (base + datetime.timedelta(minutes=i)).isoformat()
        run_ids.append(
            _run_row(
                db, lock, mission_id=mid, session_id=sid,
                summary=f"run {i} summary", started_at=started,
            )
        )

    snippets = mr.ConversationHistoryRetriever().retrieve(db, mr.RouterQuery(session_id=sid, max_runs=3))
    assert len(snippets) == 3
    # Oldest-first order preserved, capped to the first 3 chronologically.
    assert [s.source for s in snippets] == [f"run_summary:{rid}" for rid in run_ids[:3]]


def test_token_budget_cap_enforced_with_many_runs(db, lock):
    mid = _mission_row(db, lock)
    sid = uuid.uuid4().hex
    base = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    # Each summary is long enough that many of them together would blow past
    # ~2000 tokens; max_runs is set high so the budget (not max_runs) is the
    # limiting factor here.
    long_summary = "x" * 800  # ~200 tokens per snippet at the 4-chars/token estimate
    for i in range(30):
        started = (base + datetime.timedelta(minutes=i)).isoformat()
        _run_row(
            db, lock, mission_id=mid, session_id=sid,
            summary=long_summary, started_at=started,
        )

    query = mr.RouterQuery(session_id=sid, max_runs=30)
    snippets = mr.ConversationHistoryRetriever().retrieve(db, query)
    total_tokens = sum(s.approx_tokens for s in snippets)
    # Budget is ~2000 tokens; well under what 30 unbounded snippets would cost.
    assert total_tokens <= mr._CONVERSATION_TOKEN_BUDGET + 300  # slack for the one over-budget entry kept
    assert len(snippets) < 30


def test_history_snippets_to_messages_summary_becomes_assistant_turn(db, lock):
    mid = _mission_row(db, lock)
    sid = uuid.uuid4().hex
    _run_row(db, lock, mission_id=mid, session_id=sid, summary="did the thing")

    snippets = mr.ConversationHistoryRetriever().retrieve(db, mr.RouterQuery(session_id=sid))
    messages = mr.history_snippets_to_messages(snippets)
    assert len(messages) == 1
    assert messages[0]["role"] == "assistant"
    assert "did the thing" in messages[0]["content"]


def test_history_snippets_to_messages_tool_fingerprint_becomes_tool_turn(db, lock):
    mid = _mission_row(db, lock)
    sid = uuid.uuid4().hex
    run_id = _run_row(db, lock, mission_id=mid, session_id=sid, summary="")
    _tool_call_row(db, lock, run_id=run_id, tool_name="Grep", args="{}", exit_code=0)

    snippets = mr.ConversationHistoryRetriever().retrieve(db, mr.RouterQuery(session_id=sid))
    messages = mr.history_snippets_to_messages(snippets)
    assert len(messages) == 1
    assert messages[0]["role"] == "tool"
    assert "tool_call_id" in messages[0]
    assert messages[0]["tool_call_id"]


def test_history_snippets_to_messages_redacts_secrets(db, lock):
    mid = _mission_row(db, lock)
    sid = uuid.uuid4().hex
    _run_row(db, lock, mission_id=mid, session_id=sid, summary="used api_key=sk-leakhistory123 to auth")

    snippets = mr.ConversationHistoryRetriever().retrieve(db, mr.RouterQuery(session_id=sid))
    messages = mr.history_snippets_to_messages(snippets)
    assert "sk-leakhistory123" not in messages[0]["content"]
    assert "[REDACTED]" in messages[0]["content"]


def test_default_router_includes_conversation_history_first(db):
    router = mr.default_router()
    assert isinstance(router.retrievers[0], mr.ConversationHistoryRetriever)
