"""Command palette dispatch: core-first, deferred-with-seams (TUI-07).

RED until atlas_runtime.tui.command_dispatch exists (Wave 1+).
"""
from __future__ import annotations

from atlas_runtime.tui.command_dispatch import dispatch_command


def test_project_list_dispatches_to_project_service(db, monkeypatch):
    """TUI-07: /project list dispatches to project_service.list_projects."""
    calls = []
    monkeypatch.setattr(
        "atlas_runtime.tui.command_dispatch.project_service.list_projects",
        lambda conn: calls.append(conn) or [],
    )
    dispatch_command(db, "/project list")
    assert calls == [db]


def test_focus_show_dispatches_to_focus_service(db, monkeypatch):
    """TUI-07: /focus show dispatches to focus_service.get_current_focus."""
    calls = []
    monkeypatch.setattr(
        "atlas_runtime.tui.command_dispatch.focus_service.get_current_focus",
        lambda conn: calls.append(conn) or None,
    )
    dispatch_command(db, "/focus show")
    assert calls == [db]


def test_config_get_dispatches_to_config_service(db, monkeypatch):
    """TUI-07: /config get <key> dispatches to the config service layer."""
    calls = []
    monkeypatch.setattr(
        "atlas_runtime.tui.command_dispatch.config_service.get_value",
        lambda conn, key: calls.append((conn, key)) or None,
    )
    dispatch_command(db, "/config get model")
    assert calls == [(db, "model")]


def test_unknown_command_returns_error_card_not_exception(db):
    """TUI-07: an unrecognized command returns a renderable error card, never raises."""
    result = dispatch_command(db, "/this-command-does-not-exist")
    assert result is not None
    assert getattr(result, "is_error", True) is True


def test_deferred_group_wiki_returns_extension_seam_not_opaque_error(db):
    """TUI-07: deferred command groups (wiki/Brain) return an explicit extension-seam
    marker, not an opaque generic error — operators see 'not yet wired', not a crash."""
    result = dispatch_command(db, "/wiki search foo")
    assert result is not None
    assert getattr(result, "deferred", False) is True
