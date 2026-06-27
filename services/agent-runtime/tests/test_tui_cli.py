"""Tests for `atlas dev-foundation-tui` — the legacy vendored TUI launcher wrapper.

Retargeted in Wave 4: the legacy launcher was renamed from `tui` to
`legacy_foundation_tui` and is reachable only via the hidden
`dev-foundation-tui` command (the `tui` command now launches the native
workbench). The legacy launcher is patched via `_resolve_launcher` so these
run without the vendored foundation being importable.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from atlas_runtime.cli import tui as tui_mod
from atlas_runtime.cli.main import app

runner = CliRunner()


def test_tui_forwards_defaults(monkeypatch):
    launcher = MagicMock()
    monkeypatch.setattr(tui_mod, "_resolve_launcher", lambda: launcher)
    result = runner.invoke(app, ["dev-foundation-tui"])
    assert result.exit_code == 0, result.output
    launcher.assert_called_once_with(model=None, provider=None, tui_dev=False)


def test_tui_forwards_overrides(monkeypatch):
    launcher = MagicMock()
    monkeypatch.setattr(tui_mod, "_resolve_launcher", lambda: launcher)
    result = runner.invoke(
        app,
        ["dev-foundation-tui", "--model", "anthropic/claude-opus-4", "--provider", "anthropic", "--dev"],
    )
    assert result.exit_code == 0, result.output
    launcher.assert_called_once_with(
        model="anthropic/claude-opus-4", provider="anthropic", tui_dev=True
    )


def test_tui_reports_unavailable(monkeypatch):
    def _boom() -> object:
        raise RuntimeError("legacy vendored TUI source tree not found")

    monkeypatch.setattr(tui_mod, "_resolve_launcher", _boom)
    result = runner.invoke(app, ["dev-foundation-tui"])
    assert result.exit_code == 1
    assert "terminal UI unavailable" in result.output


def test_foundation_dir_resolves_in_repo():
    # Running from within the repo, the legacy vendored tree must be locatable.
    found = tui_mod._foundation_dir()
    assert found is not None
    assert (found / "ui-tui").is_dir()
