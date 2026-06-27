"""CR-02/CR-03 integration: run_workbench's composer loop routes '/'-prefixed
lines to command_dispatch.dispatch_command (threading the real session id) and
non-'/' lines to _submit_to_agent — driving the ASSEMBLED entrypoint, not the
units in isolation, which is exactly the integration gap CR-02 found.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from atlas_runtime.tui import app as app_module


class _FakePromptSession:
    """Stand-in for prompt_toolkit.PromptSession: yields scripted lines, then EOFError."""

    def __init__(self, lines):
        self._lines = list(lines)

    def __call__(self, *_a, **_kw):
        return self

    async def prompt_async(self, *_a, **_kw):
        if self._lines:
            return self._lines.pop(0)
        raise EOFError


@pytest.fixture(autouse=True)
def _patch_workspace_and_session(monkeypatch, db):
    """Stub session_select + surface_session_service.create_session so
    run_workbench can construct a real session row without an interactive
    workspace picker, while still exercising the real create_session insert."""
    monkeypatch.setattr(
        "atlas_runtime.tui.app.session_select_module.select_workspace",
        lambda conn, *, project_id=None, use_global=False: {
            "kind": "global", "project_id": None, "root_path": "/tmp/atlas",
        },
    )


def _patch_prompt_toolkit(monkeypatch, lines):
    import sys
    import types

    fake_ptk = types.ModuleType("prompt_toolkit")
    fake_ptk.PromptSession = _FakePromptSession(lines)

    fake_patch_stdout_mod = types.ModuleType("prompt_toolkit.patch_stdout")

    class _NullAsyncCtx:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *exc):
            return False

    fake_patch_stdout_mod.patch_stdout = lambda: _NullAsyncCtx()

    monkeypatch.setitem(sys.modules, "prompt_toolkit", fake_ptk)
    monkeypatch.setitem(sys.modules, "prompt_toolkit.patch_stdout", fake_patch_stdout_mod)


def test_slash_line_routes_to_dispatch_command_with_session_id(db, lock, monkeypatch):
    """CR-02/CR-03: a '/'-prefixed composer line invokes dispatch_command with
    the REAL active session.id, not an empty placeholder."""
    dispatch_calls = []
    monkeypatch.setattr(
        app_module.command_dispatch_module,
        "dispatch_command",
        lambda conn, text, *, surface_session_id: (
            dispatch_calls.append((text, surface_session_id))
            or app_module.command_dispatch_module.CommandResult(ok=True, text="ok")
        ),
    )
    submit_calls = []
    monkeypatch.setattr(
        app_module, "_submit_to_agent",
        lambda conn, lock, *, session_id, line: submit_calls.append(line),
    )
    _patch_prompt_toolkit(monkeypatch, ["/project list"])

    app_module.run_workbench(conn=db, lock=lock)

    assert len(dispatch_calls) == 1
    text, sid = dispatch_calls[0]
    assert text == "/project list"
    assert sid  # non-empty real session id
    assert submit_calls == []


def test_non_slash_line_routes_to_submit_to_agent(db, lock, monkeypatch):
    """CR-02: a non-'/' composer line is routed to the agent-submit path, not
    the command dispatcher."""
    dispatch_calls = []
    monkeypatch.setattr(
        app_module.command_dispatch_module,
        "dispatch_command",
        lambda conn, text, *, surface_session_id: dispatch_calls.append(text),
    )
    submit_calls = []
    monkeypatch.setattr(
        app_module, "_submit_to_agent",
        lambda conn, lock, *, session_id, line: submit_calls.append((session_id, line)),
    )
    _patch_prompt_toolkit(monkeypatch, ["hello agent"])

    app_module.run_workbench(conn=db, lock=lock)

    assert dispatch_calls == []
    assert len(submit_calls) == 1
    sid, line = submit_calls[0]
    assert line == "hello agent"
    assert sid
