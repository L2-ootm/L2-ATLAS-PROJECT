"""Tests for `atlas doctor` — aggregates db/config/gateway/cockpit/provider health.

Uses typer.testing.CliRunner, matching the project's existing CLI test harness
convention (tests/test_cli.py, tests/test_cli_up.py).
"""
from __future__ import annotations

import json
import shutil

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


def test_doctor_reports_claude_code_mode(monkeypatch):
    """P3: doctor surfaces claude_code (SDK + claude CLI) availability so the
    operator can see whether the local-subscription runtime is wired."""
    _patch_all_healthy(monkeypatch)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "claude_code:" in result.output


def test_doctor_provider_live_for_keyless_claude_code(monkeypatch):
    """P3: a credential-less mode (claude_code/freellmapi) is a LIVE run, not
    mock. The provider line must reflect that rather than falsely saying mock."""
    _patch_all_healthy(monkeypatch)
    monkeypatch.setattr(
        config_service,
        "resolve_provider",
        lambda cfg=None, **kw: {
            "provider": "anthropic",
            "model": "x",
            "base_url": "",
            "api_key": "",
            "auth_mode": "claude_code",
        },
    )
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "provider: live" in result.output
    assert "provider: mock" not in result.output


def test_doctor_invalid_config_exits_nonzero_without_raising(monkeypatch):
    _patch_all_healthy(monkeypatch)

    def _raise():
        raise ValueError("bad yaml: provider.api_key looks like an inline secret")

    monkeypatch.setattr(config_service, "load_config", _raise)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "config: invalid" in result.output


def test_doctor_db_schema_reports_applied_and_pending_counts(monkeypatch):
    """db_schema supplements check #1 with counts, without double-failing all_ok."""
    _patch_all_healthy(monkeypatch)
    monkeypatch.setattr(db, "applied_versions", lambda conn: {"0001_core.sql"})
    monkeypatch.setattr(db, "MIGRATIONS_DIR", db.MIGRATIONS_DIR)  # real dir, has real files
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "db_schema:" in result.output


def test_doctor_config_schema_reports_no_file_when_absent(monkeypatch, tmp_path):
    _patch_all_healthy(monkeypatch)
    monkeypatch.setattr(config_service, "default_config_path", lambda: tmp_path / "missing-config.yaml")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "config_schema: no config file" in result.output


def test_doctor_toolchain_reports_python_and_node(monkeypatch):
    _patch_all_healthy(monkeypatch)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "toolchain:" in result.output


def test_doctor_toolchain_missing_python_and_node_fails(monkeypatch):
    _patch_all_healthy(monkeypatch)
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "toolchain: missing: python, node" in result.output


def test_doctor_gateway_process_check_runs(monkeypatch):
    _patch_all_healthy(monkeypatch)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "gateway_process:" in result.output


def test_doctor_version_reports_env_passed_by_launcher(monkeypatch):
    _patch_all_healthy(monkeypatch)
    monkeypatch.setenv("ATLAS_RUNTIME_VERSION", "0.1.1")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "version: 0.1.1" in result.output


def test_doctor_version_reports_unknown_when_env_unset(monkeypatch):
    _patch_all_healthy(monkeypatch)
    monkeypatch.delenv("ATLAS_RUNTIME_VERSION", raising=False)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "version: unknown" in result.output


def test_doctor_json_output_includes_new_checks(monkeypatch):
    _patch_all_healthy(monkeypatch)
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    for key in ("db_schema", "config_schema", "gateway_process", "toolchain", "version"):
        assert key in report, f"missing key: {key}"
        assert "ok" in report[key], f"missing ok in {key}"
        assert "status" in report[key], f"missing status in {key}"
