"""Phase 10.0.4 — `atlas tools` CLI surface (SC1/SC2/SC4 reachable via CLI).

Uses Typer's CliRunner with `_get_connection` monkeypatched to an injected temp DB
— NEVER the live ~/.atlas/atlas.db (Pitfall 2 / memory cli-db-path-not-atlas-home).
"""
from __future__ import annotations

import json
import sqlite3
import threading

import pytest
from typer.testing import CliRunner

from atlas_runtime import db
from atlas_runtime.cli import tools as tools_cli

runner = CliRunner()


@pytest.fixture(name="patched_db")
def patched_db_fixture(tmp_path, monkeypatch):
    """Point the tools CLI at a temp DB with all migrations applied."""
    db_path = tmp_path / "cli-tools.db"
    seed = db.connect(db_path)
    db.apply_migrations(seed)
    seed.close()

    def _conn() -> sqlite3.Connection:
        c = sqlite3.connect(str(db_path), check_same_thread=False)
        c.execute("PRAGMA foreign_keys = ON")
        return c

    monkeypatch.setattr(tools_cli, "_get_connection", _conn)
    monkeypatch.setattr(tools_cli, "_get_lock", lambda: threading.Lock())
    return db_path


def test_manifests_json_lists_four_tools(patched_db):
    result = runner.invoke(tools_cli.tools_app, ["manifests", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    names = {m["name"] for m in payload["manifests"]}
    assert {"workspace", "github", "web_fetch", "webhook_notify"} <= names


def test_list_json(patched_db):
    result = runner.invoke(tools_cli.tools_app, ["list", "--json"])
    assert result.exit_code == 0
    assert "webhook_notify" in json.loads(result.output)["tools"]


def test_call_write_tool_short_circuits_to_pending(patched_db):
    # webhook_notify is write-class → invoke must return a pending approval, not run.
    args = json.dumps({"url": "https://example.com/hook", "payload": {"x": 1}})
    result = runner.invoke(
        tools_cli.tools_app, ["call", "--json", "--args", args, "--", "webhook_notify"]
    )
    assert result.exit_code == 0, result.output
    out = json.loads(result.output)
    assert out["status"] == "pending"
    assert out["tool_name"] == "webhook_notify"


def test_call_unknown_tool_exits_nonzero(patched_db):
    result = runner.invoke(tools_cli.tools_app, ["call", "--json", "--", "does_not_exist"])
    assert result.exit_code != 0
    assert "Unknown tool" in result.output or "Error" in result.output


def test_approvals_roundtrip_reject(patched_db):
    args = json.dumps({"url": "https://example.com/hook", "payload": {}})
    created = runner.invoke(
        tools_cli.tools_app, ["call", "--json", "--args", args, "--", "webhook_notify"]
    )
    approval_id = json.loads(created.output)["id"]
    rejected = runner.invoke(
        tools_cli.tools_app, ["reject", approval_id, "--reason", "no", "--json"]
    )
    assert rejected.exit_code == 0, rejected.output
    assert json.loads(rejected.output)["status"] == "rejected"
