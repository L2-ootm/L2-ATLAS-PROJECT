"""CodexAgent unit tests — injected normalized event stream (no SDK needed).

Mirrors the ClaudeCodeAgent test approach in test_agents.py: the runner is
injected so no `codex` binary, login, or subprocess is involved. Event shapes
follow the adapter's stable ATLAS normalization contract.
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from types import SimpleNamespace

import pytest

from atlas_runtime.agents.codex import CodexAgent, _resolve_binary, _sdk_notification_to_event
from atlas_runtime.agents.registry import get_agent
from atlas_runtime.audit_service import get_events_for_run


def _make_runner(events: list[dict]):
    def _run(prompt: str, cancel_token):  # noqa: ANN001
        yield from events
    return _run


class _Dump:
    def __init__(self, **data) -> None:  # noqa: ANN003
        self.data = data

    def model_dump(self, **_kwargs) -> dict:  # noqa: ANN003
        return dict(self.data)


def test_sdk_notifications_normalize_without_importing_sdk() -> None:
    usage: dict = {}
    item = SimpleNamespace(root=_Dump(type="agentMessage", id="m1", text="hello"))
    notification = SimpleNamespace(
        method="item/completed", payload=SimpleNamespace(item=item)
    )
    assert _sdk_notification_to_event(notification, usage) == {
        "type": "item.completed",
        "item": {
            "type": "agentMessage",
            "id": "m1",
            "text": "hello",
            "item_type": "agent_message",
        },
    }

    token_event = SimpleNamespace(
        method="thread/tokenUsage/updated",
        payload=SimpleNamespace(
            token_usage=SimpleNamespace(
                last=_Dump(input_tokens=10, output_tokens=5, total_tokens=15)
            )
        ),
    )
    assert _sdk_notification_to_event(token_event, usage) is None
    done = SimpleNamespace(
        method="turn/completed",
        payload=SimpleNamespace(turn=_Dump(status="completed", error=None)),
    )
    assert _sdk_notification_to_event(done, usage) == {
        "type": "turn.completed",
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }


def _mission_run(db: sqlite3.Connection) -> tuple[str, str]:
    import datetime

    mid, rid = str(uuid.uuid4()), str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, 't', 'i', 'pending', '', ?, ?)",
        (mid, now, now),
    )
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, NULL, 'running', ?, NULL, '')",
        (rid, mid, now),
    )
    db.commit()
    return mid, rid


def test_codex_registered() -> None:
    assert isinstance(get_agent("codex"), CodexAgent)


def test_codex_maps_stream_to_audit(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid, rid = _mission_run(db)
    events = [
        {"type": "thread.started", "thread_id": "t1"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"id": "item_0", "item_type": "agent_message", "text": "hello from codex"}},
        {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}},
    ]
    outcome = CodexAgent(runner_fn=_make_runner(events)).execute(
        db, lock, mission_id=mid, run_id=rid, prompt="hi"
    )
    assert outcome.status == "succeeded"
    assert "hello from codex" in outcome.summary
    rows = get_events_for_run(db, rid)
    llm = [e for e in rows if e.event_type == "llm_call"]
    assert any("hello from codex" in (e.data or "") for e in llm)
    assert any('"usage"' in (e.data or "") for e in llm)


def test_codex_tool_items_pair_calls_and_results(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid, rid = _mission_run(db)
    events = [
        {"type": "item.started", "item": {"id": "item_1", "item_type": "command_execution", "command": "ls"}},
        {
            "type": "item.completed",
            "item": {
                "id": "item_1",
                "item_type": "command_execution",
                "command": "ls",
                "aggregated_output": "README.md",
                "exit_code": 0,
                "status": "completed",
            },
        },
        {"type": "item.completed", "item": {"id": "item_2", "item_type": "agent_message", "text": "done"}},
        {"type": "turn.completed", "usage": {}},
    ]
    outcome = CodexAgent(runner_fn=_make_runner(events)).execute(
        db, lock, mission_id=mid, run_id=rid, prompt="list files"
    )
    assert outcome.status == "succeeded"
    rows = get_events_for_run(db, rid)
    calls = [e for e in rows if e.event_type == "tool_call"]
    completed = [e for e in rows if e.event_type == "tool_completed"]
    assert len(calls) == 1 and len(completed) == 1
    assert calls[0].tool_call_id == "item_1"
    assert completed[0].tool_call_id == "item_1"
    assert "README.md" in (completed[0].data or "")


def test_codex_failed_command_emits_tool_failed(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid, rid = _mission_run(db)
    events = [
        {"type": "item.started", "item": {"id": "item_1", "item_type": "command_execution", "command": "boom"}},
        {
            "type": "item.completed",
            "item": {"id": "item_1", "item_type": "command_execution", "exit_code": 1, "status": "failed"},
        },
        {"type": "turn.completed", "usage": {}},
    ]
    CodexAgent(runner_fn=_make_runner(events)).execute(
        db, lock, mission_id=mid, run_id=rid, prompt="x"
    )
    rows = get_events_for_run(db, rid)
    assert any(e.event_type == "tool_failed" and e.tool_call_id == "item_1" for e in rows)


def test_codex_turn_failed_marks_failed(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid, rid = _mission_run(db)
    events = [
        {"type": "turn.failed", "error": {"message": "rate limit"}},
    ]
    outcome = CodexAgent(runner_fn=_make_runner(events)).execute(
        db, lock, mission_id=mid, run_id=rid, prompt="x"
    )
    assert outcome.status == "failed"
    rows = get_events_for_run(db, rid)
    assert any(e.event_type == "failure" and "rate limit" in (e.data or "") for e in rows)


def test_codex_runner_exception_is_failsafe(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid, rid = _mission_run(db)

    def _boom(prompt: str, cancel_token):  # noqa: ANN001
        raise RuntimeError("codex CLI not found on PATH")
        yield  # pragma: no cover

    outcome = CodexAgent(runner_fn=_boom).execute(
        db, lock, mission_id=mid, run_id=rid, prompt="x"
    )
    assert outcome.status == "failed"
    assert "codex" in outcome.summary
    rows = get_events_for_run(db, rid)
    assert any(e.event_type == "failure" for e in rows)


def test_codex_precancelled_short_circuits(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid, rid = _mission_run(db)
    token = threading.Event()
    token.set()
    outcome = CodexAgent(runner_fn=_make_runner([])).execute(
        db, lock, mission_id=mid, run_id=rid, prompt="x", cancel_token=token
    )
    assert outcome.status == "failed"
    assert outcome.stop_reason == "cancelled"
    rows = get_events_for_run(db, rid)
    assert any(e.event_type == "run_cancelled" for e in rows)


def test_codex_mid_stream_cancel_stops_consumption(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid, rid = _mission_run(db)
    token = threading.Event()
    seen: list[str] = []

    def _runner(prompt: str, cancel_token):  # noqa: ANN001
        seen.append("first")
        yield {"type": "item.completed", "item": {"id": "i", "item_type": "agent_message", "text": "part"}}
        token.set()
        seen.append("second")
        yield {"type": "item.completed", "item": {"id": "j", "item_type": "agent_message", "text": "never"}}
        seen.append("third")

    outcome = CodexAgent(runner_fn=_runner).execute(
        db, lock, mission_id=mid, run_id=rid, prompt="x", cancel_token=token
    )
    assert outcome.status == "failed"
    assert outcome.stop_reason == "cancelled"
    assert "third" not in seen


def test_codex_unknown_events_are_skipped(db: sqlite3.Connection, lock: threading.Lock) -> None:
    mid, rid = _mission_run(db)
    events = [
        {"type": "something.new", "payload": {"x": 1}},
        {"type": "item.completed", "item": {"id": "i", "item_type": "todo_list", "items": []}},
        {"type": "item.completed", "item": {"id": "m", "item_type": "agent_message", "text": "ok"}},
        {"type": "turn.completed", "usage": {}},
    ]
    outcome = CodexAgent(runner_fn=_make_runner(events)).execute(
        db, lock, mission_id=mid, run_id=rid, prompt="x"
    )
    assert outcome.status == "succeeded"
    assert outcome.summary == "ok"


def test_codex_binary_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_CODEX_BIN", r"C:\tools\codex.exe")
    assert _resolve_binary() == r"C:\tools\codex.exe"


def test_codex_missing_binary_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLAS_CODEX_BIN", raising=False)
    monkeypatch.setattr("atlas_runtime.agents.codex.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="codex CLI not found"):
        _resolve_binary()
