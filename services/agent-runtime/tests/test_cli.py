"""Tests for atlas_runtime.cli.main — Typer CLI subcommands.

All tests are marked xfail(strict=True) because the service functions are stubs
in Wave 0. Wave 1 executors must implement the service layer to make these pass.

Uses typer.testing.CliRunner for CLI invocation without requiring the atlas
console script to be installed. _get_connection and _get_lock are monkeypatched
to inject the test in-memory database.

Fixtures from conftest.py (injected by name — do NOT import):
  db      — in-memory SQLite, WAL + FK ON + 0001_core.sql applied
  lock    — threading.Lock()
"""
import pytest
from typer.testing import CliRunner

from atlas_runtime.cli.main import app

runner = CliRunner()


def test_create_command_exits_zero(db, monkeypatch):
    """atlas mission create exits 0 and prints a 36-character UUID."""
    import atlas_runtime.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    result = runner.invoke(app, ["mission", "create", "--title", "Test", "--intent", "do X"])
    assert result.exit_code == 0
    assert len(result.output.strip()) == 36


def test_run_command_exits_zero(db, lock, monkeypatch):
    """atlas mission run <id> exits 0 after successfully starting a run."""
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import mission_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    mission = mission_service.create_mission(db, lock, title="Run Test")
    result = runner.invoke(app, ["mission", "run", mission.id])
    assert result.exit_code == 0


def test_cancel_command_exits_zero(db, lock, monkeypatch):
    """atlas mission cancel <id> exits 0 after cancelling an active run."""
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import mission_service, run_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    mission = mission_service.create_mission(db, lock, title="Cancel Test")
    run_service.start_run(db, lock, mission_id=mission.id)
    result = runner.invoke(app, ["mission", "cancel", mission.id])
    assert result.exit_code == 0


def test_status_command_exits_zero(db, monkeypatch):
    """atlas mission status <id> exits 0 and prints 'pending' for a new mission."""
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import mission_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    mission = mission_service.create_mission(db, cli_main._get_lock(), title="Status Test")
    result = runner.invoke(app, ["mission", "status", mission.id])
    assert result.exit_code == 0
    assert "pending" in result.output


def test_status_unknown_id_exits_one(db, monkeypatch):
    """atlas mission status <nonexistent-id> exits 1.

    This test is NOT marked xfail because the status command queries the DB
    directly (no service stub involved) and correctly returns exit code 1
    for an unknown mission ID without invoking any Wave 1 stub.
    """
    import atlas_runtime.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    result = runner.invoke(app, ["mission", "status", "nonexistent-uuid"])
    assert result.exit_code == 1
