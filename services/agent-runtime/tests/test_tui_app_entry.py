"""Bare `atlas` / `atlas tui` launch the sole canonical Go terminal surface.

The vendored Hermes wrapper remains separate behind dev-foundation-tui (D-001).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from atlas_runtime.cli.main import app

runner = CliRunner()


def test_bare_atlas_invokes_go_workbench(monkeypatch):
    """P8: invoking `atlas` with no subcommand launches the Go sidecar."""
    import atlas_runtime.cli.go_tui as go_tui_mod

    launch = MagicMock(return_value=0)
    monkeypatch.setattr(go_tui_mod, "launch", launch)
    result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output
    launch.assert_called_once()


def test_atlas_tui_subcommand_invokes_same_go_workbench(monkeypatch):
    """P8: `atlas tui` resolves to the same Go sidecar entry point."""
    import atlas_runtime.cli.go_tui as go_tui_mod

    launch = MagicMock(return_value=0)
    monkeypatch.setattr(go_tui_mod, "launch", launch)
    result = runner.invoke(app, ["tui", "--gateway", "http://127.0.0.1:9494"])
    assert result.exit_code == 0, result.output
    launch.assert_called_once_with("http://127.0.0.1:9494")


def test_no_rich_or_hermes_launcher_on_default_path(monkeypatch):
    """Neither default Go entry point reaches the Python or Hermes clients."""
    import atlas_runtime.cli.go_tui as go_tui_mod
    from atlas_runtime.cli import tui as tui_mod

    monkeypatch.setattr(go_tui_mod, "launch", MagicMock(return_value=0))
    monkeypatch.setattr(
        tui_mod,
        "_resolve_launcher",
        MagicMock(side_effect=AssertionError("Hermes launcher reached")),
    )

    assert runner.invoke(app, []).exit_code == 0
    assert runner.invoke(app, ["tui"]).exit_code == 0


def test_retired_rich_command_is_absent():
    result = runner.invoke(app, ["dev-rich-tui"])
    assert result.exit_code != 0
