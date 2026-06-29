"""Phase 10.0.4 — `atlas tools` CLI surface (SC1/SC2/SC4 reachable via CLI).

Uses Typer's CliRunner with `_get_connection` monkeypatched to an injected temp DB
— NEVER the live ~/.atlas/atlas.db (Pitfall 2 / memory cli-db-path-not-atlas-home).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import datetime
import uuid

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
    session_id = _active_session(patched_db)
    args = json.dumps({"url": "https://example.com/hook", "payload": {"x": 1}})
    result = runner.invoke(
        tools_cli.tools_app,
        [
            "call",
            "--json",
            "--args",
            args,
            "--surface-session-id",
            session_id,
            "--surface-kind",
            "cli",
            "--workspace-root",
            "/tmp/atlas",
            "--",
            "webhook_notify",
        ],
    )
    assert result.exit_code == 0, result.output
    out = json.loads(result.output)
    assert out["status"] == "pending"
    assert out["tool_name"] == "webhook_notify"


def test_call_unknown_tool_exits_nonzero(patched_db):
    result = runner.invoke(
        tools_cli.tools_app, ["call", "--json", "--", "does_not_exist"]
    )
    assert result.exit_code != 0
    assert "Unknown tool" in result.output or "Error" in result.output


def test_guarded_call_without_surface_scope_is_rejected(patched_db):
    args = json.dumps({"url": "https://example.com/hook", "payload": {}})
    result = runner.invoke(
        tools_cli.tools_app,
        ["call", "--json", "--args", args, "--", "webhook_notify"],
    )

    assert result.exit_code == 1
    assert json.loads(result.output)["error"]["code"] == "surface_scope_required"


def test_approvals_roundtrip_reject(patched_db):
    session_id = _active_session(patched_db)
    args = json.dumps({"url": "https://example.com/hook", "payload": {}})
    created = runner.invoke(
        tools_cli.tools_app,
        [
            "call",
            "--json",
            "--args",
            args,
            "--surface-session-id",
            session_id,
            "--surface-kind",
            "cli",
            "--workspace-root",
            "/tmp/atlas",
            "--",
            "webhook_notify",
        ],
    )
    pending = json.loads(created.output)
    rejected = runner.invoke(
        tools_cli.tools_app,
        [
            "reject",
            pending["id"],
            "--surface-session-id",
            session_id,
            "--nonce",
            pending["nonce"],
            "--reason",
            "no",
            "--json",
        ],
    )
    assert rejected.exit_code == 0, rejected.output
    assert json.loads(rejected.output)["status"] == "rejected"


def _active_session(db_path) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO surface_sessions"
        "(id, surface_kind, surface_session_id, workspace_kind, workspace_root, "
        "agent, model_provider, model_id, permission_mode, prompt_version, "
        "tool_catalog_version, context_policy_version, state, heartbeat_at, "
        "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            session_id,
            "cli",
            f"client-{session_id}",
            "global",
            "/tmp/atlas",
            "atlas",
            "test",
            "model",
            "ask",
            "1.0.0",
            "1.0.0",
            "1.0.0",
            "active",
            now,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return session_id


def test_unscoped_mutation_is_rejected_with_typed_error(patched_db):
    result = runner.invoke(
        tools_cli.tools_app,
        ["reject", "approval-id", "--json"],
    )

    assert result.exit_code == 1
    assert json.loads(result.output)["error"]["code"] == "approval_scope_required"


def test_owned_queue_excludes_foreign_pending_rows(patched_db):
    owner = _active_session(patched_db)
    foreign = _active_session(patched_db)
    args = json.dumps({"url": "https://example.com/hook", "payload": {}})
    created = runner.invoke(
        tools_cli.tools_app,
        [
            "call",
            "--json",
            "--args",
            args,
            "--surface-session-id",
            owner,
            "--surface-kind",
            "cli",
            "--workspace-root",
            "/tmp/atlas",
            "--",
            "webhook_notify",
        ],
    )
    pending_id = json.loads(created.output)["id"]

    owner_rows = runner.invoke(
        tools_cli.tools_app,
        ["approvals", "--surface-session-id", owner, "--json"],
    )
    foreign_rows = runner.invoke(
        tools_cli.tools_app,
        ["approvals", "--surface-session-id", foreign, "--json"],
    )

    assert pending_id in {
        row["id"] for row in json.loads(owner_rows.output)["approvals"]
    }
    assert json.loads(foreign_rows.output)["approvals"] == []
