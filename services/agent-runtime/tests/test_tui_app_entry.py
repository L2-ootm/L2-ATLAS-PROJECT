"""Bare `atlas` / `atlas tui` launch the atlas-terminal (Bun/donor) surface.

The legacy Go TUI stays reachable behind hidden dev-go-tui until UAT retires
it; the vendored Hermes wrapper remains separate behind dev-foundation-tui
(D-001).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from atlas_runtime.cli.main import app

runner = CliRunner()


def test_bare_atlas_invokes_atlas_terminal(monkeypatch):
    """Invoking `atlas` with no subcommand launches atlas-terminal."""
    import atlas_runtime.cli.atlas_terminal as terminal_mod

    launch = MagicMock(return_value=0)
    monkeypatch.setattr(terminal_mod, "launch", launch)
    result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output
    launch.assert_called_once()


def test_atlas_tui_subcommand_invokes_same_atlas_terminal(monkeypatch):
    """`atlas tui` resolves to the same atlas-terminal entry point."""
    import atlas_runtime.cli.atlas_terminal as terminal_mod

    launch = MagicMock(return_value=0)
    monkeypatch.setattr(terminal_mod, "launch", launch)
    result = runner.invoke(app, ["tui", "--gateway", "http://127.0.0.1:9494"])
    assert result.exit_code == 0, result.output
    # work_dir=None: no ATLAS_WORK_DIR override and no TTY to prompt for scope,
    # so the launcher captures the operator cwd itself.
    launch.assert_called_once_with("http://127.0.0.1:9494", work_dir=None)


def test_default_path_never_reaches_go_or_hermes_launchers(monkeypatch):
    """Neither default entry point reaches the Go sidecar or Hermes clients."""
    import atlas_runtime.cli.atlas_terminal as terminal_mod
    import atlas_runtime.cli.go_tui as go_tui_mod
    from atlas_runtime.cli import tui as tui_mod

    monkeypatch.setattr(terminal_mod, "launch", MagicMock(return_value=0))
    monkeypatch.setattr(
        go_tui_mod,
        "launch",
        MagicMock(side_effect=AssertionError("Go TUI launcher reached")),
    )
    monkeypatch.setattr(
        tui_mod,
        "_resolve_launcher",
        MagicMock(side_effect=AssertionError("Hermes launcher reached")),
    )

    assert runner.invoke(app, []).exit_code == 0
    assert runner.invoke(app, ["tui"]).exit_code == 0


def test_dev_go_tui_fallback_invokes_go_workbench(monkeypatch):
    """Hidden dev-go-tui keeps the legacy Go sidecar launchable until UAT."""
    import atlas_runtime.cli.go_tui as go_tui_mod

    launch = MagicMock(return_value=0)
    monkeypatch.setattr(go_tui_mod, "launch", launch)
    result = runner.invoke(app, ["dev-go-tui", "--gateway", "http://127.0.0.1:9494"])
    assert result.exit_code == 0, result.output
    launch.assert_called_once_with("http://127.0.0.1:9494")


def test_launch_failure_exits_nonzero(monkeypatch):
    """A TerminalLaunchError surfaces as exit 1 with remediation text."""
    import atlas_runtime.cli.atlas_terminal as terminal_mod

    monkeypatch.setattr(
        terminal_mod,
        "launch",
        MagicMock(side_effect=terminal_mod.TerminalLaunchError("bun not found")),
    )
    result = runner.invoke(app, ["tui"])
    assert result.exit_code == 1
    assert "terminal UI unavailable" in result.output


def test_retired_rich_command_is_absent():
    result = runner.invoke(app, ["dev-rich-tui"])
    assert result.exit_code != 0
