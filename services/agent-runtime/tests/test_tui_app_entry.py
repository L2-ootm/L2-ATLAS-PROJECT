"""Bare `atlas` / `atlas tui` must launch the native workbench, not the Hermes wrapper (TUI-01).

RED until atlas_runtime.tui.app exists AND cli/main.py wires a root
invoke_without_command callback to atlas_runtime.tui.app.run_workbench (Wave 1+/Wave 4).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from atlas_runtime.cli.main import app

runner = CliRunner()


def test_bare_atlas_invokes_run_workbench(monkeypatch):
    """TUI-01: invoking `atlas` with no subcommand launches the native workbench."""
    import atlas_runtime.tui.app as tui_app_mod  # noqa: PLC0415 — does not exist yet (RED)

    run_workbench = MagicMock()
    monkeypatch.setattr(tui_app_mod, "run_workbench", run_workbench)
    result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output
    run_workbench.assert_called_once()


def test_atlas_tui_subcommand_invokes_same_run_workbench(monkeypatch):
    """TUI-01: `atlas tui` resolves to the same native workbench entry point."""
    import atlas_runtime.tui.app as tui_app_mod  # noqa: PLC0415 — does not exist yet (RED)

    run_workbench = MagicMock()
    monkeypatch.setattr(tui_app_mod, "run_workbench", run_workbench)
    result = runner.invoke(app, ["tui"])
    assert result.exit_code == 0, result.output
    run_workbench.assert_called_once()


def test_no_hermes_wrapper_on_default_path(monkeypatch):
    """TUI-01: neither bare `atlas` nor `atlas tui` reaches the Hermes Ink launcher."""
    from atlas_runtime.cli import tui as tui_mod

    def _boom(*_a, **_kw):
        raise AssertionError("Hermes launcher must not be reached on the native path")

    monkeypatch.setattr(tui_mod, "_resolve_launcher", _boom)
    monkeypatch.setattr(tui_mod, "_foundation_dir", _boom)

    runner.invoke(app, [])
    runner.invoke(app, ["tui"])
