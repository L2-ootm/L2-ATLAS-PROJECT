"""Transcript polling + append-only rendering (TUI-04).

RED until atlas_runtime.tui.transcript exists (Wave 1+).
"""
from __future__ import annotations

from atlas_runtime.tui.transcript import poll_and_render


def _seed_events(db, session_id: str) -> None:
    import datetime
    import uuid

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for seq, kind in ((1, "text"), (2, "tool_call")):
        db.execute(
            "INSERT INTO surface_events"
            "(id, session_id, seq, kind, run_id, occurred_at, payload_json) "
            "VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), session_id, seq, kind, None, now, "{}"),
        )
    db.commit()


def test_replay_since_dedup_on_second_poll(db, surface_session, forced_console):
    """TUI-04: polling twice with the same last_seq never re-renders already-seen events."""
    _seed_events(db, surface_session)
    console = forced_console()
    first = poll_and_render(db, console, session_id=surface_session, last_seq=0)
    assert len(first) == 2
    second = poll_and_render(db, console, session_id=surface_session, last_seq=first[-1].seq)
    assert second == []


def test_append_only_no_full_redraw_call(db, surface_session, forced_console, monkeypatch):
    """TUI-04: poll_and_render appends new lines; it must never call console.clear()."""
    _seed_events(db, surface_session)
    console = forced_console()
    cleared = {"called": False}
    monkeypatch.setattr(console, "clear", lambda *a, **k: cleared.__setitem__("called", True))
    poll_and_render(db, console, session_id=surface_session, last_seq=0)
    assert cleared["called"] is False
