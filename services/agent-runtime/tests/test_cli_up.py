"""Tests for `atlas up` — boots gateway + cockpit together (idempotent).

Uses typer.testing.CliRunner, matching the project's existing CLI test harness
convention (tests/test_cli.py, tests/test_tui_cli.py).
"""
from __future__ import annotations

from typer.testing import CliRunner

from atlas_runtime import (
    cashflow_control,
    cockpit_control,
    discord_control,
    freellmapi_control,
    gateway_control,
)
from atlas_runtime.cli.main import app

runner = CliRunner()


def _patch_no_op_sidecar(monkeypatch):
    """Stub the paths `_up_cmd` added this session (staleness probe + freellmapi
    boot) so pre-existing tests stay pure unit tests instead of doing real
    filesystem/network I/O they don't assert on."""
    monkeypatch.setattr(gateway_control, "binary_stale", lambda: False)
    monkeypatch.setattr(freellmapi_control, "start", lambda: (True, "freellmapi already running"))


def test_up_exits_zero_and_echoes_both_messages(monkeypatch):
    monkeypatch.setattr(gateway_control, "start", lambda: (True, "gateway started"))
    monkeypatch.setattr(cockpit_control, "start", lambda: (True, "cockpit started"))
    _patch_no_op_sidecar(monkeypatch)
    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0, result.output
    assert "gateway started" in result.output
    assert "cockpit started" in result.output


def test_up_exits_nonzero_on_partial_failure(monkeypatch):
    monkeypatch.setattr(gateway_control, "start", lambda: (False, "gateway failed"))
    monkeypatch.setattr(cockpit_control, "start", lambda: (True, "cockpit started"))
    _patch_no_op_sidecar(monkeypatch)
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
    _patch_no_op_sidecar(monkeypatch)
    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    assert call_order == ["gateway", "cockpit"]


def test_up_starts_freellmapi_after_gateway_and_cockpit_healthy(monkeypatch):
    monkeypatch.setattr(gateway_control, "start", lambda: (True, "gateway started"))
    monkeypatch.setattr(cockpit_control, "start", lambda: (True, "cockpit started"))
    monkeypatch.setattr(gateway_control, "binary_stale", lambda: False)
    monkeypatch.setattr(freellmapi_control, "start", lambda: (True, "freellmapi started (pid 123)"))
    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0, result.output
    assert "freellmapi: freellmapi started (pid 123)" in result.output


def test_up_skips_freellmapi_when_gateway_unhealthy(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(gateway_control, "start", lambda: (False, "gateway failed"))
    monkeypatch.setattr(cockpit_control, "start", lambda: (True, "cockpit started"))
    monkeypatch.setattr(gateway_control, "binary_stale", lambda: False)
    monkeypatch.setattr(freellmapi_control, "start", lambda: calls.append("freellmapi") or (True, "should not run"))
    result = runner.invoke(app, ["up"])
    assert result.exit_code == 1
    assert calls == [], "freellmapi must not start when the gateway failed to come up healthy"


def test_up_warns_on_stale_gateway_binary(monkeypatch):
    monkeypatch.setattr(gateway_control, "start", lambda: (True, "gateway started"))
    monkeypatch.setattr(cockpit_control, "start", lambda: (True, "cockpit started"))
    monkeypatch.setattr(gateway_control, "binary_stale", lambda: True)
    monkeypatch.setattr(freellmapi_control, "start", lambda: (True, "freellmapi already running"))
    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    assert "WARNING binary predates its Rust sources" in result.output


def test_down_stops_sidecars_then_cockpit_then_gateway(monkeypatch):
    call_order: list[str] = []

    monkeypatch.setattr(
        freellmapi_control,
        "stop",
        lambda: call_order.append("freellmapi") or (True, "freellmapi stopped"),
    )
    monkeypatch.setattr(
        cashflow_control,
        "stop",
        lambda: call_order.append("cashflow") or (True, "cashflow stopped"),
    )
    monkeypatch.setattr(
        discord_control,
        "stop",
        lambda: call_order.append("discord") or (True, "discord stopped"),
    )
    monkeypatch.setattr(
        cockpit_control,
        "stop",
        lambda: call_order.append("cockpit") or (True, "cockpit stopped"),
    )
    monkeypatch.setattr(
        gateway_control,
        "stop",
        lambda: call_order.append("gateway") or (True, "gateway stopped"),
    )

    result = runner.invoke(app, ["down"])

    assert result.exit_code == 0, result.output
    assert call_order == ["freellmapi", "cashflow", "discord", "cockpit", "gateway"]
    assert "gateway: gateway stopped" in result.output


def test_down_json_reports_each_component(monkeypatch):
    monkeypatch.setattr(freellmapi_control, "stop", lambda: (True, "not running"))
    monkeypatch.setattr(cashflow_control, "stop", lambda: (True, "not running"))
    monkeypatch.setattr(discord_control, "stop", lambda: (True, "not running"))
    monkeypatch.setattr(cockpit_control, "stop", lambda: (True, "not running"))
    monkeypatch.setattr(gateway_control, "stop", lambda: (True, "not running"))

    result = runner.invoke(app, ["down", "--json"])

    assert result.exit_code == 0, result.output
    assert result.output.strip().startswith("{")
    assert '"ok": true' in result.output
    assert '"component": "gateway"' in result.output
