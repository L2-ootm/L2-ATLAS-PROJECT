"""Command palette dispatch: core-first, deferred-with-seams (TUI-07).

RED until atlas_runtime.tui.command_dispatch exists (Wave 1+).
"""
from __future__ import annotations

from atlas_runtime.tui.command_dispatch import dispatch_command

_SID = "test-surface-session-id"


def test_project_list_dispatches_to_project_service(db, monkeypatch):
    """TUI-07: /project list dispatches to project_service.list_projects."""
    calls = []
    monkeypatch.setattr(
        "atlas_runtime.tui.command_dispatch.project_service.list_projects",
        lambda conn: calls.append(conn) or [],
    )
    dispatch_command(db, "/project list", surface_session_id=_SID)
    assert calls == [db]


def test_focus_show_dispatches_to_focus_service(db, monkeypatch):
    """TUI-07: /focus show dispatches to focus_service.get_current_focus."""
    calls = []
    monkeypatch.setattr(
        "atlas_runtime.tui.command_dispatch.focus_service.get_current_focus",
        lambda conn: calls.append(conn) or None,
    )
    dispatch_command(db, "/focus show", surface_session_id=_SID)
    assert calls == [db]


def test_config_get_dispatches_to_config_service(db, monkeypatch):
    """TUI-07: /config get <key> dispatches to the config service layer."""
    calls = []
    monkeypatch.setattr(
        "atlas_runtime.tui.command_dispatch.config_service.get_value",
        lambda conn, key: calls.append((conn, key)) or None,
    )
    dispatch_command(db, "/config get model", surface_session_id=_SID)
    assert calls == [(db, "model")]


def test_unknown_command_returns_error_card_not_exception(db):
    """TUI-07: an unrecognized command returns a renderable error card, never raises."""
    result = dispatch_command(db, "/this-command-does-not-exist", surface_session_id=_SID)
    assert result is not None
    assert getattr(result, "is_error", True) is True


def test_deferred_group_wiki_returns_extension_seam_not_opaque_error(db):
    """TUI-07: deferred command groups (wiki/Brain) return an explicit extension-seam
    marker, not an opaque generic error — operators see 'not yet wired', not a crash."""
    result = dispatch_command(db, "/wiki search foo", surface_session_id=_SID)
    assert result is not None
    assert getattr(result, "deferred", False) is True


def test_deferred_group_mission_returns_extension_seam_not_silent_failure(db):
    """WR-02: 'mission' is registered as a deferred extension seam (not a 'core'
    handler that unconditionally fails) until the real list/show wiring lands."""
    result = dispatch_command(db, "/mission list", surface_session_id=_SID)
    assert result is not None
    assert getattr(result, "deferred", False) is True


def test_permission_list_scopes_to_threaded_session_id(db, monkeypatch):
    """CR-03: /permission list passes the REAL threaded surface_session_id to
    permission_broker.list_actionable — never an empty-string placeholder."""
    calls = []
    monkeypatch.setattr(
        "atlas_runtime.tui.command_dispatch.permission_broker.list_actionable",
        lambda conn, *, surface_session_id: calls.append(surface_session_id) or [],
    )
    dispatch_command(db, "/permission list", surface_session_id=_SID)
    assert calls == [_SID]


def test_permission_list_only_returns_owning_session_rows(
    db, seed_pending_approval, make_active_session, surface_session
):
    """CR-03 integration: a seeded approval owned by the active session is
    returned by /permission list; an approval owned by a DIFFERENT session is
    not — proves strict session-scoping, not just that a value was passed."""
    import datetime
    import uuid

    session_id = make_active_session(surface_session_id=surface_session)
    other_session_id = str(uuid.uuid4())
    expiry = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
    ).isoformat()

    seed_pending_approval(
        surface_session_id=session_id,
        nonce=str(uuid.uuid4()),
        expiry_at=expiry,
        tool_name="owned-tool",
    )
    seed_pending_approval(
        surface_session_id=other_session_id,
        nonce=str(uuid.uuid4()),
        expiry_at=expiry,
        tool_name="other-session-tool",
    )

    result = dispatch_command(db, "/permission list", surface_session_id=session_id)
    assert result.ok is True
    assert "owned-tool" in result.text
    assert "other-session-tool" not in result.text
