"""Tests for `atlas discord` — sidecar lifecycle + read browse.

The sidecar HTTP client (discord_api) and lifecycle (discord_control) are
monkeypatched so nothing is spawned or networked. Mirrors test_channels_cli.py.
"""
from __future__ import annotations

import json

from typer.testing import CliRunner

from atlas_runtime.cli.main import app

runner = CliRunner()


def test_status_json_stopped(monkeypatch, tmp_path):
    from atlas_runtime import discord_control as dc

    monkeypatch.setattr(dc, "STATE_FILE", tmp_path / "d.json")
    monkeypatch.setattr(dc, "_health_payload", lambda timeout=1.0: None)
    result = runner.invoke(app, ["discord", "status", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"running": False, "pid": None, "ready": False, "guild_count": 0}


def test_guilds_json(monkeypatch):
    from atlas_runtime import discord_api

    monkeypatch.setattr(discord_api, "list_guilds", lambda: [{"id": "111", "name": "L2 HQ"}])
    result = runner.invoke(app, ["discord", "guilds", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["guilds"][0]["name"] == "L2 HQ"


def test_guilds_sidecar_down_exits_1(monkeypatch):
    from atlas_runtime import discord_api

    def _raise():
        raise discord_api.DiscordSidecarError("discord sidecar unreachable")

    monkeypatch.setattr(discord_api, "list_guilds", _raise)
    result = runner.invoke(app, ["discord", "guilds", "--json"])
    assert result.exit_code == 1
    assert "unreachable" in result.output


def test_structure_json(monkeypatch):
    from atlas_runtime import discord_api

    payload = {"guild": {"id": "111", "name": "L2 HQ", "member_count": 9}, "categories": [], "uncategorized": [], "roles": []}
    monkeypatch.setattr(discord_api, "get_structure", lambda gid: payload)
    result = runner.invoke(app, ["discord", "structure", "--json", "111"])
    assert result.exit_code == 0
    assert json.loads(result.output)["guild"]["name"] == "L2 HQ"


def test_start_json_reports_status(monkeypatch):
    from atlas_runtime import discord_control as dc

    monkeypatch.setattr(dc, "start", lambda: (True, "discord bot starting (pid 8200)"))
    monkeypatch.setattr(dc, "status", lambda: {"running": True, "pid": 8200, "ready": False, "guild_count": 0})
    result = runner.invoke(app, ["discord", "start", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True and data["pid"] == 8200
