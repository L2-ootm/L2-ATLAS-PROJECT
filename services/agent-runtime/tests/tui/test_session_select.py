"""Workspace picker: global vs registered Project selection + cwd resolution (TUI-02).

RED until atlas_runtime.tui.session_select exists (Wave 1+).
"""
from __future__ import annotations

import pytest

from atlas_runtime.tui.session_select import select_workspace


def test_explicit_project_flag_skips_picker(db, monkeypatch):
    """TUI-02: an explicit --project flag resolves directly, no interactive picker."""
    called = {"resolve": False}

    def _fake_resolve(conn, *, project_id=None, **_kw):
        called["resolve"] = True
        return {"kind": "project", "project_id": project_id, "root_path": "/tmp/proj"}

    monkeypatch.setattr(
        "atlas_runtime.tui.session_select.workspace_service.resolve_workspace",
        _fake_resolve,
    )
    result = select_workspace(db, project_id="proj-123", use_global=False)
    assert called["resolve"] is True
    assert result["kind"] == "project"


def test_global_flag_resolves_via_workspace_service(db, monkeypatch):
    """TUI-02: --global resolves the global workspace via workspace_service."""
    def _fake_resolve(conn, *, project_id=None, use_global=False, **_kw):
        assert use_global is True
        return {"kind": "global", "project_id": None, "root_path": "/"}

    monkeypatch.setattr(
        "atlas_runtime.tui.session_select.workspace_service.resolve_workspace",
        _fake_resolve,
    )
    result = select_workspace(db, use_global=True)
    assert result["kind"] == "global"


def test_no_flags_and_no_tty_raises_clean_error(db, monkeypatch):
    """TUI-02: no explicit flags + non-interactive (no TTY) must fail closed, not hang."""
    monkeypatch.setattr(
        "atlas_runtime.tui.session_select._stdin_is_tty", lambda: False
    )
    with pytest.raises(RuntimeError):
        select_workspace(db, project_id=None, use_global=False)
