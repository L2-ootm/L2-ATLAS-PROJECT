"""Tests for `atlas tui` — the terminal UI launcher wrapper.

The foundation launcher is patched via `_resolve_launcher` so these run without
the vendored foundation being importable.
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
    result = runner.invoke(app, ["tui"])
    assert result.exit_code == 0, result.output
    launcher.assert_called_once_with(model=None, provider=None, tui_dev=False)


def test_tui_forwards_overrides(monkeypatch):
    launcher = MagicMock()
    monkeypatch.setattr(tui_mod, "_resolve_launcher", lambda: launcher)
    result = runner.invoke(
        app, ["tui", "--model", "anthropic/claude-opus-4", "--provider", "anthropic", "--dev"]
    )
    assert result.exit_code == 0, result.output
    launcher.assert_called_once_with(
        model="anthropic/claude-opus-4", provider="anthropic", tui_dev=True
    )


def test_tui_reports_unavailable(monkeypatch):
    def _boom() -> object:
        raise RuntimeError("foundation/atlas-hermes not found")

    monkeypatch.setattr(tui_mod, "_resolve_launcher", _boom)
    result = runner.invoke(app, ["tui"])
    assert result.exit_code == 1
    assert "terminal UI unavailable" in result.output


def test_foundation_dir_resolves_in_repo():
    # Running from within the repo, the foundation tree must be locatable.
    found = tui_mod._foundation_dir()
    assert found is not None
    assert (found / "ui-tui").is_dir()
