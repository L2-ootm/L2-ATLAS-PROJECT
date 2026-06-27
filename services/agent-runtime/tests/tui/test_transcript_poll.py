"""Transcript polling + append-only rendering (TUI-04).

Drives the LOCKED design: audit_events -> normalize_surface_events ->
replay_since. No persisted surface_events table exists (CR-01 fix) — every
poll re-derives the projection from the immutable audit_events ledger via
audit_service.get_events_for_session.
"""
from __future__ import annotations

import datetime
import uuid

from atlas_runtime import audit_service
from atlas_runtime.tui.transcript import poll_and_render


def _seed_run_for_session(db, session_id: str) -> str:
    """Insert a minimal mission+run row linked to session_id (FK target for audit_events)."""
    mission_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (mission_id, "test-mission", "", "pending", "", now, now),
    )
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, mission_id, session_id, "running", now, None, ""),
    )
    db.commit()
    return run_id


def _emit_events(db, lock, run_id: str, session_id: str) -> None:
    audit_service.emit(
        db,
        lock,
        run_id=run_id,
        event_type="llm_call",
        session_id=session_id,
        data={"text": "hello"},
    )
    audit_service.emit(
        db,
        lock,
        run_id=run_id,
        event_type="tool_call",
        session_id=session_id,
        data={"tool": "workspace"},
    )


def test_replay_since_dedup_on_second_poll(db, surface_session, forced_console, lock):
    """TUI-04: polling twice with the same last_seq never re-renders already-seen events.

    Drives the real audit_events -> normalize_surface_events -> replay_since path
    (not a seeded surface_events shortcut — that table no longer exists, CR-01).
    """
    run_id = _seed_run_for_session(db, surface_session)
    _emit_events(db, lock, run_id, surface_session)
    console = forced_console()

    first = poll_and_render(db, console, session_id=surface_session, last_seq=-1)
    assert len(first) == 2
    assert [e.kind for e in first] == ["text", "tool_call"]

    second = poll_and_render(db, console, session_id=surface_session, last_seq=first[-1].seq)
    assert second == []

    # A new audit event appended after the first poll must be the ONLY thing a
    # second poll (with the previous last_seq) returns — proves the gap-free
    # append-only contract, not just dedup-to-empty.
    audit_service.emit(
        db,
        lock,
        run_id=run_id,
        event_type="tool_completed",
        session_id=surface_session,
        data={"tool": "workspace", "success": True},
    )
    third = poll_and_render(db, console, session_id=surface_session, last_seq=first[-1].seq)
    assert len(third) == 1
    assert third[0].kind == "tool_result"


def test_append_only_no_full_redraw_call(db, surface_session, forced_console, monkeypatch, lock):
    """TUI-04: poll_and_render appends new lines; it must never call console.clear()."""
    run_id = _seed_run_for_session(db, surface_session)
    _emit_events(db, lock, run_id, surface_session)
    console = forced_console()
    cleared = {"called": False}
    monkeypatch.setattr(console, "clear", lambda *a, **k: cleared.__setitem__("called", True))
    poll_and_render(db, console, session_id=surface_session, last_seq=-1)
    assert cleared["called"] is False
