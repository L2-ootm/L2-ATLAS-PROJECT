"""Compact identity/status header rendering (TUI-03).

RED until atlas_runtime.tui.header exists (Wave 1+).
"""
from __future__ import annotations

from atlas_runtime.tui.header import render_status_header


def _fake_snapshot(surface_session_id: str) -> dict:
    return {
        "surface_session_id": surface_session_id,
        "model_id": "claude-opus-4",
        "model_provider": "anthropic",
        "resolved_api_key": "sk-ant-super-secret-do-not-leak",
        "permission_mode": "ask",
        "context_budget_used": 1200,
        "context_budget_total": 200000,
        "focus_title": "Ship the terminal workbench",
        "state": "active",
    }


def test_header_shows_masked_model_no_secrets(surface_session, forced_console):
    """TUI-03: header shows model identity but never the resolved secret."""
    console = forced_console(width=120)
    snapshot = _fake_snapshot(surface_session)
    render_status_header(console, snapshot)
    output = console.file.getvalue()
    assert "claude-opus-4" in output
    assert "sk-ant-super-secret-do-not-leak" not in output


def test_header_includes_permission_mode_and_context_budget(surface_session, forced_console):
    """TUI-03: header surfaces permission mode + context budget for operator awareness."""
    console = forced_console(width=120)
    snapshot = _fake_snapshot(surface_session)
    render_status_header(console, snapshot)
    output = console.file.getvalue()
    assert "ask" in output
    assert "1200" in output or "1.2" in output


def test_header_never_contains_resolved_api_key(surface_session, forced_console):
    """TUI-03: redundant explicit secrecy assertion — no resolved API key leaks ever."""
    console = forced_console(width=80, no_color=True)
    snapshot = _fake_snapshot(surface_session)
    render_status_header(console, snapshot)
    assert "super-secret" not in console.file.getvalue()
