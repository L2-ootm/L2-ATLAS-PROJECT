"""Machine-readable CLI contract for shared surface-session lifecycle."""

from __future__ import annotations

import json
import pathlib
import sqlite3
import threading

import pytest
from typer.testing import CliRunner

from atlas_runtime import db, project_service
from atlas_runtime.cli import surface as surface_cli

runner = CliRunner()


@pytest.fixture(name="patched_surface_db")
def patched_surface_db_fixture(tmp_path, monkeypatch):
    db_path = tmp_path / "surface-cli.db"
    conn = db.connect(db_path)
    db.apply_migrations(conn)
    project_root = tmp_path / "project"
    project_root.mkdir()
    project = project_service.register_project(
        conn,
        threading.Lock(),
        name="CLI project",
        root_path=str(project_root),
    )
    conn.close()

    def _conn() -> sqlite3.Connection:
        connection = sqlite3.connect(str(db_path), check_same_thread=False)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    monkeypatch.setattr(surface_cli, "_get_connection", _conn)
    monkeypatch.setattr(surface_cli, "_get_lock", lambda: threading.Lock())
    monkeypatch.setattr(
        surface_cli.workspace_service,
        "global_root",
        lambda: pathlib.Path(tmp_path / "global"),
    )
    return {"path": db_path, "project": project, "project_root": project_root}


def _invoke(*args: str):
    result = runner.invoke(surface_cli.surface_app, [*args, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_create_global_session_uses_shared_contract(patched_surface_db) -> None:
    payload = _invoke(
        "create",
        "--surface-kind",
        "webui",
        "--surface-id",
        "browser-tab-1",
        "--global",
    )

    assert payload["surface"]["kind"] == "webui"
    assert payload["surface"]["session_id"] == "browser-tab-1"
    assert payload["workspace"]["kind"] == "global"
    assert payload["state"] == "active"
    assert payload["permission_mode"] == "ask"
    assert payload["prompt_version"]
    assert payload["tool_catalog_version"]
    assert payload["context_policy_version"]


def test_create_project_session_preserves_registered_identity(
    patched_surface_db,
) -> None:
    project = patched_surface_db["project"]
    payload = _invoke(
        "create",
        "--surface-kind",
        "cli",
        "--surface-id",
        "cli-process-1",
        "--project",
        project.id,
    )

    assert payload["workspace"] == {
        "kind": "project",
        "root": str(patched_surface_db["project_root"].resolve()),
        "project_id": project.id,
    }
    assert payload["agent"]
    assert payload["model"]["provider"]
    assert payload["model"]["model_id"]


def test_get_list_suspend_heartbeat_and_close_roundtrip(patched_surface_db) -> None:
    created = _invoke(
        "create",
        "--surface-kind",
        "webui",
        "--surface-id",
        "browser-tab-2",
        "--global",
    )
    session_id = created["id"]
    owner_token = created["owner_token"]

    assert _invoke("get", session_id)["id"] == session_id
    assert session_id in {row["id"] for row in _invoke("list")["sessions"]}
    assert (
        _invoke("heartbeat", session_id, "--owner-token", owner_token)["state"]
        == "active"
    )
    assert (
        _invoke("suspend", session_id, "--owner-token", owner_token)["state"]
        == "suspended"
    )
    assert (
        _invoke("close", session_id, "--owner-token", owner_token)["state"]
        == "completed"
    )


def test_cancel_drives_active_session_to_clean_terminal(patched_surface_db) -> None:
    created = _invoke(
        "create",
        "--surface-kind",
        "webui",
        "--surface-id",
        "browser-tab-3",
        "--global",
    )

    terminal = _invoke(
        "cancel",
        created["id"],
        "--owner-token",
        created["owner_token"],
    )

    assert terminal["state"] == "completed"


def test_unknown_project_returns_typed_json_error(patched_surface_db) -> None:
    result = runner.invoke(
        surface_cli.surface_app,
        [
            "create",
            "--surface-kind",
            "webui",
            "--surface-id",
            "bad-project",
            "--project",
            "missing",
            "--json",
        ],
    )

    assert result.exit_code == 1
    error = json.loads(result.output)
    assert error["error"]["code"] == "workspace_unregistered"
    assert error["error"]["remediation"]


def test_missing_session_returns_typed_json_error(patched_surface_db) -> None:
    result = runner.invoke(surface_cli.surface_app, ["get", "missing", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.output)["error"]["code"] == "surface_not_found"


def test_mutation_rejects_stale_owner_token(patched_surface_db) -> None:
    created = _invoke(
        "create",
        "--surface-kind",
        "webui",
        "--surface-id",
        "browser-owner",
        "--global",
    )
    result = runner.invoke(
        surface_cli.surface_app,
        [
            "cancel",
            created["id"],
            "--owner-token",
            "stale",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.output)["error"]["code"] == "surface_owner_mismatch"


def test_resume_rotates_owner_token_and_reopens_channel(
    patched_surface_db,
    monkeypatch,
) -> None:
    created = _invoke(
        "create",
        "--surface-kind",
        "webui",
        "--surface-id",
        "browser-resume",
        "--global",
    )
    _invoke(
        "suspend",
        created["id"],
        "--owner-token",
        created["owner_token"],
    )
    captured: dict[str, str] = {}

    def fake_resume(conn, lock, session_id, *, owner_token, owner_pid):  # noqa: ANN001
        captured["owner_token"] = owner_token
        session = surface_cli.surface_session_service.get_session(conn, session_id)
        conn.execute(
            "UPDATE surface_sessions SET state='active', owner_token=? WHERE id=?",
            (owner_token, session_id),
        )
        conn.commit()
        return session.model_copy(
            update={"state": "active", "owner_token": owner_token}
        )

    monkeypatch.setattr(
        surface_cli.surface_session_service,
        "resume_session",
        fake_resume,
    )
    resumed = _invoke(
        "resume",
        created["id"],
        "--owner-token",
        created["owner_token"],
    )

    assert resumed["state"] == "active"
    assert resumed["owner_token"] == captured["owner_token"]
    assert resumed["owner_token"] != created["owner_token"]
    conn = sqlite3.connect(str(patched_surface_db["path"]))
    assert (
        conn.execute(
            "SELECT revoked_at FROM approval_channels WHERE surface_session_id=?",
            (created["id"],),
        ).fetchone()[0]
        is None
    )
    conn.close()
