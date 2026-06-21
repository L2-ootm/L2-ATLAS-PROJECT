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


# ---------------------------------------------------------------------------
# Gated writes — propose / approvals / approve / reject (Phase C)
# ---------------------------------------------------------------------------


def _isolate_db(monkeypatch):
    """Point the discord CLI at an in-memory DB with all migrations applied."""
    import sqlite3
    import threading

    from atlas_runtime import db as dbmod
    from atlas_runtime.cli import discord as cli_discord

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    for sql_path in sorted(dbmod.MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(sql_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(cli_discord, "_get_connection", lambda: conn)
    monkeypatch.setattr(cli_discord, "_get_lock", lambda: threading.Lock())
    return conn


def test_propose_then_approvals_json(monkeypatch):
    _isolate_db(monkeypatch)
    result = runner.invoke(
        app,
        ["discord", "propose", "create_channel", "--guild", "g1", "--name", "ops", "--json"],
    )
    assert result.exit_code == 0
    approval = json.loads(result.output)
    assert approval["status"] == "pending" and approval["action"] == "create_channel"

    listed = runner.invoke(app, ["discord", "approvals", "--json"])
    ids = [a["id"] for a in json.loads(listed.output)["approvals"]]
    assert approval["id"] in ids


def test_propose_invalid_action_exits_1(monkeypatch):
    _isolate_db(monkeypatch)
    result = runner.invoke(app, ["discord", "propose", "nuke", "--guild", "g1", "--json"])
    assert result.exit_code == 1
    assert "unknown discord action" in result.output


def test_approve_executes(monkeypatch):
    _isolate_db(monkeypatch)
    from atlas_runtime import discord_api

    monkeypatch.setattr(discord_api, "create_channel", lambda g, **kw: {"id": "1", "name": kw["name"]})
    proposed = runner.invoke(
        app, ["discord", "propose", "create_channel", "--guild", "g1", "--name", "ops", "--json"]
    )
    aid = json.loads(proposed.output)["id"]
    approved = runner.invoke(app, ["discord", "approve", aid, "--json"])
    assert approved.exit_code == 0
    assert json.loads(approved.output)["status"] == "executed"


def test_reject_marks_rejected(monkeypatch):
    _isolate_db(monkeypatch)
    proposed = runner.invoke(
        app, ["discord", "propose", "create_role", "--guild", "g1", "--name", "mod", "--json"]
    )
    aid = json.loads(proposed.output)["id"]
    rejected = runner.invoke(app, ["discord", "reject", aid, "--reason", "no", "--json"])
    assert rejected.exit_code == 0
    assert json.loads(rejected.output)["status"] == "rejected"
