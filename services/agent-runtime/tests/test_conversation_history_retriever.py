"""Regression tests for durable, bounded conversation replay."""
from __future__ import annotations

import datetime
import threading
import uuid

from atlas_runtime import memory_router as mr
from atlas_runtime import session_message_service


def _mission_row(conn, lock) -> str:
    mission_id = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (mission_id, "m", "", "pending", "", now, now),
            )
    return mission_id


def _run_row(
    conn,
    lock,
    *,
    mission_id: str,
    session_id: str,
    status: str = "succeeded",
    started_at: str | None = None,
    summary: str = "",
) -> str:
    run_id = uuid.uuid4().hex
    now = started_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO runs(id,mission_id,session_id,status,started_at,finished_at,summary) "
                "VALUES (?,?,?,?,?,?,?)",
                (run_id, mission_id, session_id, status, now, now, summary),
            )
    return run_id


def _message(conn, session_id: str, run_id: str, role: str, content: str) -> None:
    session_message_service.append_message(
        conn,
        threading.Lock(),
        surface_session_id=session_id,
        run_id=run_id,
        role=role,
        content=content,
    )


def test_no_session_id_returns_empty(db):
    snippets = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=None)
    )
    assert snippets == []


def test_replays_actual_user_and_assistant_turns(db, lock, surface_session):
    mission_id = _mission_row(db, lock)
    run_id = _run_row(
        db,
        lock,
        mission_id=mission_id,
        session_id=surface_session,
        summary='{"files_touched":["invented.md"]}',
    )
    _message(db, surface_session, run_id, "user", "fix the parser")
    _message(db, surface_session, run_id, "assistant", "The parser is fixed.")

    snippets = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=surface_session)
    )
    messages = mr.history_snippets_to_messages(snippets)

    assert messages == [
        {"role": "user", "content": "fix the parser"},
        {"role": "assistant", "content": "The parser is fixed."},
    ]
    assert all("invented.md" not in item["content"] for item in messages)


def test_summary_without_durable_messages_is_not_replayed(
    db, lock, surface_session
):
    mission_id = _mission_row(db, lock)
    _run_row(
        db,
        lock,
        mission_id=mission_id,
        session_id=surface_session,
        summary='{"outcome":"hallucinated"}',
    )

    snippets = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=surface_session)
    )
    assert snippets == []


def test_only_terminal_successful_runs_are_considered(
    db, lock, surface_session
):
    mission_id = _mission_row(db, lock)
    failed = _run_row(
        db,
        lock,
        mission_id=mission_id,
        session_id=surface_session,
        status="failed",
        started_at="2026-01-01T00:00:00Z",
    )
    running = _run_row(
        db,
        lock,
        mission_id=mission_id,
        session_id=surface_session,
        status="running",
        started_at="2026-01-01T00:01:00Z",
    )
    succeeded = _run_row(
        db,
        lock,
        mission_id=mission_id,
        session_id=surface_session,
        status="succeeded",
        started_at="2026-01-01T00:02:00Z",
    )
    _message(db, surface_session, failed, "assistant", "failed output")
    _message(db, surface_session, running, "assistant", "partial output")
    _message(db, surface_session, succeeded, "assistant", "verified output")

    snippets = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=surface_session)
    )
    assert [snippet.text for snippet in snippets] == ["verified output"]


def test_max_runs_selects_newest_then_replays_chronologically(
    db, lock, surface_session
):
    mission_id = _mission_row(db, lock)
    base = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    for index in range(8):
        run_id = _run_row(
            db,
            lock,
            mission_id=mission_id,
            session_id=surface_session,
            started_at=(base + datetime.timedelta(minutes=index)).isoformat(),
        )
        _message(db, surface_session, run_id, "user", f"question {index}")
        _message(db, surface_session, run_id, "assistant", f"answer {index}")

    snippets = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=surface_session, max_runs=3)
    )
    messages = mr.history_snippets_to_messages(snippets)

    assert [item["content"] for item in messages] == [
        "question 5",
        "answer 5",
        "question 6",
        "answer 6",
        "question 7",
        "answer 7",
    ]


def test_token_budget_caps_durable_history(db, lock, surface_session):
    mission_id = _mission_row(db, lock)
    base = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    for index in range(30):
        run_id = _run_row(
            db,
            lock,
            mission_id=mission_id,
            session_id=surface_session,
            started_at=(base + datetime.timedelta(minutes=index)).isoformat(),
        )
        _message(db, surface_session, run_id, "assistant", str(index) + "x" * 800)

    snippets = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=surface_session, max_runs=30)
    )
    assert sum(item.approx_tokens for item in snippets) <= (
        mr._CONVERSATION_TOKEN_BUDGET + 300
    )
    assert len(snippets) < 30


def test_history_conversion_redacts_secrets():
    snippets = [
        mr.MemorySnippet(
            text="use api_key=sk-leakhistory123",
            score=0.0,
            source="session_assistant:run",
            approx_tokens=8,
        )
    ]
    messages = mr.history_snippets_to_messages(snippets)
    assert "sk-leakhistory123" not in messages[0]["content"]
    assert "[REDACTED]" in messages[0]["content"]


def test_default_router_includes_conversation_history_first():
    router = mr.default_router()
    assert isinstance(router.retrievers[0], mr.ConversationHistoryRetriever)
