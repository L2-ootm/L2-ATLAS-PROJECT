"""Ctrl-C / cancel unwind: clean cancel without corrupting session state (TUI-08).

RED until atlas_runtime.tui.app exists (Wave 1+).
"""
from __future__ import annotations

from atlas_runtime.tui.app import handle_cancel


def test_ctrl_c_calls_transition_session_cancelling(
    db, surface_session, make_active_session, monkeypatch
):
    """TUI-08: Ctrl-C drives the owning session to 'cancelling' via the service layer."""
    session_id = make_active_session()
    calls = []
    monkeypatch.setattr(
        "atlas_runtime.tui.app.surface_session_service.transition_session",
        lambda conn, lock, sid, target, **kw: calls.append((sid, target)),
    )
    handle_cancel(db, session_id=session_id)
    assert (session_id, "cancelling") in calls


def test_cancel_does_not_leave_session_non_terminal(
    db, surface_session, make_active_session, monkeypatch
):
    """TUI-08: cancel never leaves a non-terminal write half-applied — exactly one
    transition call, no partial state."""
    session_id = make_active_session()
    calls = []
    monkeypatch.setattr(
        "atlas_runtime.tui.app.surface_session_service.transition_session",
        lambda conn, lock, sid, target, **kw: calls.append((sid, target)),
    )
    handle_cancel(db, session_id=session_id)
    assert len(calls) == 1
