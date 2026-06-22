"""Tests for `atlas doctor` — aggregates db/config/gateway/cockpit/provider health.

Uses typer.testing.CliRunner, matching the project's existing CLI test harness
convention (tests/test_cli.py, tests/test_cli_up.py).
"""
from __future__ import annotations

from typer.testing import CliRunner

from atlas_runtime import cockpit_control, config_service, db, gateway_control
from atlas_runtime.cli.main import app

runner = CliRunner()

_ALL_APPLIED = [("0001_core.sql", True), ("0002_x.sql", True)]
_HEALTHY_PROVIDER = {
    "provider": "openrouter",
    "model": "anthropic/claude-sonnet-4",
    "base_url": "",
    "api_key": "sk-resolved-secret-value",
}


def _patch_all_healthy(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda: object())
    monkeypatch.setattr(db, "migration_status", lambda conn: _ALL_APPLIED)
    monkeypatch.setattr(config_service, "load_config", lambda: object())
    monkeypatch.setattr(gateway_control, "health_ok", lambda: True)
    monkeypatch.setattr(cockpit_control, "health_ok", lambda: True)
    monkeypatch.setattr(
        config_service, "resolve_provider", lambda cfg=None, **kw: dict(_HEALTHY_PROVIDER)
    )


def test_doctor_all_healthy_exits_zero(monkeypatch):
    _patch_all_healthy(monkeypatch)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "db: ok" in result.output
    assert "config: ok" in result.output
    assert "gateway: ok" in result.output
    assert "cockpit: ok" in result.output
    assert "provider: configured" in result.output


def test_doctor_gateway_down_exits_nonzero(monkeypatch):
    _patch_all_healthy(monkeypatch)
    monkeypatch.setattr(gateway_control, "health_ok", lambda: False)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "gateway: down" in result.output


def test_doctor_pending_migration_exits_nonzero_and_identifies_version(monkeypatch):
    _patch_all_healthy(monkeypatch)
    monkeypatch.setattr(
        db, "migration_status", lambda conn: [("0001_core.sql", True), ("0003_pending.sql", False)]
    )
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "0003_pending.sql" in result.output


def test_doctor_mock_provider_exits_zero_and_never_leaks_api_key(monkeypatch):
    _patch_all_healthy(monkeypatch)
    fake_secret = "sk-FAKE-INJECTED-SECRET-VALUE-12345"
    monkeypatch.setattr(
        config_service,
        "resolve_provider",
        lambda cfg=None, **kw: {
            "provider": "openrouter",
            "model": "anthropic/claude-sonnet-4",
            "base_url": "",
            "api_key": "",
            "_test_injected_secret": fake_secret,
        },
    )
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "provider: mock" in result.output
    assert fake_secret not in result.output


def test_doctor_invalid_config_exits_nonzero_without_raising(monkeypatch):
    _patch_all_healthy(monkeypatch)

    def _raise():
        raise ValueError("bad yaml: provider.api_key looks like an inline secret")

    monkeypatch.setattr(config_service, "load_config", _raise)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "config: invalid" in result.output
