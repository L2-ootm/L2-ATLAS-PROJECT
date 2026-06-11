"""Tests for atlas channels status — read-only channel inspection."""
from __future__ import annotations

import pathlib

from typer.testing import CliRunner

from atlas_runtime.cli import channels as channels_cli
from atlas_runtime.cli.main import app

runner = CliRunner()


def _set_home(monkeypatch, tmp_path: pathlib.Path) -> pathlib.Path:
    monkeypatch.setattr(channels_cli, "_hermes_home", lambda: tmp_path)
    return tmp_path / "config.yaml"


def test_status_no_config(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    result = runner.invoke(app, ["channels", "status"])
    assert result.exit_code == 1
    assert "config not found" in result.output
    assert "atlas-agent setup" in result.output


def test_status_empty_platforms(monkeypatch, tmp_path):
    config = _set_home(monkeypatch, tmp_path)
    config.write_text("gateway:\n  platforms: {}\n", encoding="utf-8")
    result = runner.invoke(app, ["channels", "status"])
    assert result.exit_code == 0
    assert "no channels configured" in result.output


def test_status_lists_channels_without_leaking_secrets(monkeypatch, tmp_path):
    config = _set_home(monkeypatch, tmp_path)
    config.write_text(
        "gateway:\n"
        "  platforms:\n"
        "    telegram:\n"
        "      enabled: true\n"
        "      token: super-secret-token\n"
        "    discord:\n"
        "      enabled: false\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["channels", "status"])
    assert result.exit_code == 0
    assert "ENABLED" in result.output and "telegram" in result.output
    assert "disabled" in result.output and "discord" in result.output
    assert "credential: set" in result.output
    assert "super-secret-token" not in result.output
