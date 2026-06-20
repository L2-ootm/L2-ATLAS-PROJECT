"""Tests for atlas config + atlas setup CLI."""
from __future__ import annotations

from typer.testing import CliRunner

from atlas_runtime import config_service as cfgsvc
from atlas_runtime.cli.main import app

runner = CliRunner()


def _home(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    return tmp_path / "config.yaml"


def test_config_show_defaults(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "provider:" in result.output
    assert "openrouter" in result.output


def test_config_set_then_get(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    r1 = runner.invoke(app, ["config", "set", "runtime.iteration_budget", "42"])
    assert r1.exit_code == 0
    r2 = runner.invoke(app, ["config", "get", "runtime.iteration_budget"])
    assert r2.exit_code == 0
    assert "42" in r2.output
    # Persisted to disk.
    assert cfgsvc.load_config(tmp_path / "config.yaml").runtime.iteration_budget == 42


def test_config_set_inline_secret_rejected(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    result = runner.invoke(app, ["config", "set", "provider.api_key", "sk-leak123"])
    assert result.exit_code == 1
    assert "invalid value" in result.output


def test_config_get_unknown_key(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    result = runner.invoke(app, ["config", "get", "provider.nope"])
    assert result.exit_code == 1
    assert "unknown key" in result.output


def test_setup_writes_config_accepting_defaults(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    # Accept every default; decline the DB init prompt (final 'n').
    answers = "\n\n\n\n\n\n\n\nn\n"
    result = runner.invoke(app, ["setup"], input=answers)
    assert result.exit_code == 0, result.output
    assert "setup complete" in result.output
    cfg = cfgsvc.load_config(tmp_path / "config.yaml")
    assert cfg.provider.name == "openrouter"
    assert (tmp_path / "config.yaml").is_file()
