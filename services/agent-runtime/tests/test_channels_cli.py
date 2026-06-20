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


def _seed(config, body: str):
    config.write_text(body, encoding="utf-8")


def test_json_lists_channels_without_secrets(monkeypatch, tmp_path):
    import json

    config = _set_home(monkeypatch, tmp_path)
    _seed(
        config,
        "gateway:\n"
        "  platforms:\n"
        "    discord:\n"
        "      enabled: true\n"
        "      token: super-secret-token\n"
        "    slack:\n"
        "      enabled: false\n",
    )
    result = runner.invoke(app, ["channels", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    names = {c["name"]: c for c in data["channels"]}
    assert names["discord"]["enabled"] is True
    assert names["discord"]["credential_present"] is True
    assert names["slack"]["enabled"] is False
    assert "super-secret-token" not in result.output


def test_enable_disable_round_trip_preserves_other_keys(monkeypatch, tmp_path):
    config = _set_home(monkeypatch, tmp_path)
    _seed(
        config,
        "gateway:\n"
        "  platforms:\n"
        "    discord:\n"
        "      enabled: false\n"
        "      token: keepme\n"
        "agent:\n"
        "  model: keep-this-too\n",
    )
    assert runner.invoke(app, ["channels", "enable", "discord"]).exit_code == 0
    plats = channels_cli._load_platforms(config)
    assert plats["discord"]["enabled"] is True
    assert plats["discord"]["token"] == "keepme"  # other keys preserved
    # Unrelated top-level config preserved across the round-trip.
    import yaml

    full = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert full["agent"]["model"] == "keep-this-too"

    assert runner.invoke(app, ["channels", "disable", "discord"]).exit_code == 0
    assert channels_cli._load_platforms(config)["discord"]["enabled"] is False


def test_enable_creates_entry_when_missing(monkeypatch, tmp_path):
    config = _set_home(monkeypatch, tmp_path)
    _seed(config, "gateway:\n  platforms: {}\n")
    assert runner.invoke(app, ["channels", "enable", "telegram"]).exit_code == 0
    assert channels_cli._load_platforms(config)["telegram"]["enabled"] is True


# --- messaging-gateway process lifecycle (atlas channels gateway ...) ---------


def test_gateway_status_json_stopped(monkeypatch, tmp_path):
    import json

    from atlas_runtime import messaging_gateway_control as mgc

    monkeypatch.setattr(mgc, "STATE_FILE", tmp_path / "gw.json")
    result = runner.invoke(app, ["channels", "gateway", "status", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"running": False, "pid": None}


def test_gateway_start_json_reports_pid(monkeypatch, tmp_path):
    import json

    from atlas_runtime import messaging_gateway_control as mgc

    monkeypatch.setattr(mgc, "STATE_FILE", tmp_path / "gw.json")
    monkeypatch.setattr(mgc, "messaging_cli", lambda: ["atlas-agent"])
    monkeypatch.setattr(mgc, "_pid_alive", lambda pid: True)

    class _P:
        pid = 8200

    monkeypatch.setattr(mgc.subprocess, "Popen", lambda *a, **k: _P())
    result = runner.invoke(app, ["channels", "gateway", "start", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True and data["pid"] == 8200


def test_gateway_stop_json_without_pid_is_idempotent(monkeypatch, tmp_path):
    import json

    from atlas_runtime import messaging_gateway_control as mgc

    monkeypatch.setattr(mgc, "STATE_FILE", tmp_path / "gw.json")
    result = runner.invoke(app, ["channels", "gateway", "stop", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["ok"] is True
