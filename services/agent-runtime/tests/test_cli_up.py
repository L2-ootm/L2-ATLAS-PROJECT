"""Tests for `atlas up` — boots gateway + cockpit together (idempotent).

Uses typer.testing.CliRunner, matching the project's existing CLI test harness
convention (tests/test_cli.py, tests/test_tui_cli.py).
"""
from __future__ import annotations

from typer.testing import CliRunner

from atlas_runtime import cockpit_control, gateway_control
from atlas_runtime.cli.main import app

runner = CliRunner()


def test_up_exits_zero_and_echoes_both_messages(monkeypatch):
    monkeypatch.setattr(gateway_control, "start", lambda: (True, "gateway started"))
    monkeypatch.setattr(cockpit_control, "start", lambda: (True, "cockpit started"))
    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0, result.output
    assert "gateway started" in result.output
    assert "cockpit started" in result.output


def test_up_exits_nonzero_on_partial_failure(monkeypatch):
    monkeypatch.setattr(gateway_control, "start", lambda: (False, "gateway failed"))
    monkeypatch.setattr(cockpit_control, "start", lambda: (True, "cockpit started"))
    result = runner.invoke(app, ["up"])
    assert result.exit_code == 1
    assert "gateway failed" in result.output


def test_up_calls_gateway_then_cockpit_in_order(monkeypatch):
    call_order: list[str] = []

    def _gateway_start():
        call_order.append("gateway")
        return True, "gateway started"

    def _cockpit_start():
        call_order.append("cockpit")
        return True, "cockpit started"

    monkeypatch.setattr(gateway_control, "start", _gateway_start)
    monkeypatch.setattr(cockpit_control, "start", _cockpit_start)
    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    assert call_order == ["gateway", "cockpit"]
