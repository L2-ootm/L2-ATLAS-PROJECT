"""Regression tests for durable, bounded conversation replay."""
from __future__ import annotations

import datetime
import threading
import uuid

from atlas_core.schemas import provenance
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


def test_a_failed_run_still_contributes_the_operator_question(
    db, lock, surface_session
):
    """A run's status says whether ATLAS finished the work, not whether the
    operator spoke. The question is recorded before execution, so filtering
    history by run status deleted the operator's own words whenever a run
    failed — and the next turn read the follow-up with the question missing."""
    mission_id = _mission_row(db, lock)
    failed = _run_row(
        db,
        lock,
        mission_id=mission_id,
        session_id=surface_session,
        status="failed",
        started_at="2026-01-01T00:00:00Z",
    )
    succeeded = _run_row(
        db,
        lock,
        mission_id=mission_id,
        session_id=surface_session,
        status="succeeded",
        started_at="2026-01-01T00:02:00Z",
    )
    _message(db, surface_session, failed, "user", "port the parser to v2")
    _message(db, surface_session, succeeded, "user", "why did that not work?")
    _message(db, surface_session, succeeded, "assistant", "the harness timed out")

    snippets = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=surface_session)
    )
    assert [snippet.text for snippet in snippets] == [
        "port the parser to v2",
        "why did that not work?",
        "the harness timed out",
    ]


def test_the_current_run_is_excluded_from_its_own_history(
    db, lock, surface_session
):
    """The operator's message is persisted before the turn is driven, so the
    live run's own prompt is already in `session_messages` when history is
    assembled. Replaying it would show the model the same ask twice."""
    mission_id = _mission_row(db, lock)
    previous = _run_row(
        db, lock, mission_id=mission_id, session_id=surface_session,
        started_at="2026-01-01T00:00:00Z",
    )
    current = _run_row(
        db, lock, mission_id=mission_id, session_id=surface_session,
        status="running", started_at="2026-01-01T00:01:00Z",
    )
    _message(db, surface_session, previous, "user", "first ask")
    _message(db, surface_session, previous, "assistant", "first answer")
    _message(db, surface_session, current, "user", "second ask")

    snippets = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=surface_session, exclude_run_id=current)
    )
    assert [snippet.text for snippet in snippets] == ["first ask", "first answer"]


def test_budget_pressure_drops_the_oldest_turns_not_the_newest(
    db, lock, surface_session
):
    """The regression this rewrite exists for. History was accumulated
    oldest-first and returned the moment the budget would be exceeded, so a
    long session kept its opening turns and silently dropped the exchange
    that had just happened — the model answered every follow-up without the
    message it was following up on."""
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
        _message(db, surface_session, run_id, "user", f"ask {index} " + "x" * 2000)
        _message(db, surface_session, run_id, "assistant", f"answer {index}")

    snippets = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=surface_session, max_runs=30)
    )
    texts = [snippet.text for snippet in snippets]

    assert texts, "history must never come back empty under budget pressure"
    assert texts[-1] == "answer 29"
    assert any(text.startswith("ask 29 ") for text in texts)
    assert not any(text.startswith("ask 0 ") for text in texts)


def test_a_single_oversized_turn_is_truncated_rather_than_dropped(
    db, lock, surface_session
):
    """One pasted stack trace must not cost the model the whole conversation."""
    mission_id = _mission_row(db, lock)
    run_id = _run_row(db, lock, mission_id=mission_id, session_id=surface_session)
    _message(db, surface_session, run_id, "user", "y" * 400_000)

    snippets = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=surface_session)
    )
    assert len(snippets) == 1
    assert snippets[0].approx_tokens <= mr.conversation_token_budget()
    assert snippets[0].text.endswith(mr._TRUNCATION_MARKER)


def test_consecutive_same_role_turns_are_merged_for_the_provider(db):
    """A failed run leaves a user turn with no answer after it. Two user
    messages in a row is a 400 on strict providers, so the message projection
    merges them instead of handing the harness an invalid conversation."""
    snippets = [
        mr.MemorySnippet(
            text="first ask", score=0.0, source="session_user:a", approx_tokens=2,
            grade=provenance.STATED,
        ),
        mr.MemorySnippet(
            text="second ask", score=-1.0, source="session_user:b", approx_tokens=2,
            grade=provenance.STATED,
        ),
        mr.MemorySnippet(
            text="the answer", score=-2.0, source="session_assistant:b", approx_tokens=2,
            grade=provenance.REPORTED,
        ),
    ]
    assert mr.history_snippets_to_messages(snippets) == [
        {"role": "user", "content": "first ask\n\nsecond ask"},
        {"role": "assistant", "content": "the answer"},
    ]


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
    """Sized against the live budget, not a number that silently stopped
    overflowing the day the budget was raised."""
    mission_id = _mission_row(db, lock)
    base = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    turn_tokens = 200
    turns = (mr.conversation_token_budget() // turn_tokens) * 3
    for index in range(turns):
        run_id = _run_row(
            db,
            lock,
            mission_id=mission_id,
            session_id=surface_session,
            started_at=(base + datetime.timedelta(minutes=index)).isoformat(),
        )
        _message(
            db, surface_session, run_id, "assistant", str(index) + "x" * (turn_tokens * 4)
        )

    snippets = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=surface_session, max_runs=turns)
    )
    assert sum(item.approx_tokens for item in snippets) <= (
        mr.conversation_token_budget() + 300
    )
    assert len(snippets) < turns


def test_budget_is_operator_configurable(db, lock, surface_session, monkeypatch):
    """The right amount of replayed conversation depends on the context window
    the active provider gives a run, which this module cannot know."""
    mission_id = _mission_row(db, lock)
    base = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    for index in range(20):
        run_id = _run_row(
            db, lock, mission_id=mission_id, session_id=surface_session,
            started_at=(base + datetime.timedelta(minutes=index)).isoformat(),
        )
        _message(db, surface_session, run_id, "assistant", f"answer {index} " + "x" * 400)

    monkeypatch.setenv(mr._CONVERSATION_TOKEN_BUDGET_ENV, "200")
    narrow = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=surface_session, max_runs=20)
    )
    monkeypatch.setenv(mr._CONVERSATION_TOKEN_BUDGET_ENV, "20000")
    wide = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=surface_session, max_runs=20)
    )

    assert len(narrow) < len(wide) == 20
    # Whatever the budget, the most recent turn is the one that survives.
    assert narrow[-1].text == wide[-1].text


def test_a_garbage_budget_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv(mr._CONVERSATION_TOKEN_BUDGET_ENV, "not-a-number")
    assert mr.conversation_token_budget() == mr._CONVERSATION_TOKEN_BUDGET
    monkeypatch.setenv(mr._CONVERSATION_TOKEN_BUDGET_ENV, "0")
    assert mr.conversation_token_budget() == mr._CONVERSATION_TOKEN_BUDGET


def test_history_conversion_redacts_secrets():
    snippets = [
        mr.MemorySnippet(
            text="use api_key=sk-leakhistory123",
            score=0.0,
            source="session_assistant:run",
            approx_tokens=8,
            grade=provenance.REPORTED,
        )
    ]
    messages = mr.history_snippets_to_messages(snippets)
    assert "sk-leakhistory123" not in messages[0]["content"]
    assert "[REDACTED]" in messages[0]["content"]


def test_default_router_includes_conversation_history_first():
    router = mr.default_router()
    assert isinstance(router.retrievers[0], mr.ConversationHistoryRetriever)
