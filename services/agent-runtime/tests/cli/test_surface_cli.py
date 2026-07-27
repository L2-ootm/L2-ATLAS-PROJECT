"""Machine-readable CLI contract for shared surface-session lifecycle."""

from __future__ import annotations

import json
import pathlib
import sqlite3
import threading

import pytest
from typer.testing import CliRunner

from atlas_runtime import db, project_service, session_message_service
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


def test_events_replay_is_normalized_and_strictly_after_sequence(
    patched_surface_db,
) -> None:
    created = _invoke(
        "create",
        "--surface-kind",
        "tui",
        "--surface-id",
        "event-reader",
        "--global",
    )
    conn = sqlite3.connect(str(patched_surface_db["path"]))
    conn.execute(
        "INSERT INTO missions "
        "(id,title,intent,status,project,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "mission-events",
            "Events",
            "verify replay",
            "completed",
            "test",
            "2026-06-29T00:00:00+00:00",
            "2026-06-29T00:00:00+00:00",
        ),
    )
    conn.execute(
        "INSERT INTO runs "
        "(id,mission_id,session_id,status,started_at,finished_at,summary,agent_runtime) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            "run-events",
            "mission-events",
            created["id"],
            "succeeded",
            "2026-06-29T00:00:00+00:00",
            "2026-06-29T00:00:02+00:00",
            "done",
            "native",
        ),
    )
    conn.execute(
        "INSERT INTO audit_events "
        "(id,run_id,event_type,tool_name,timestamp,duration_ms,data) "
        "VALUES (?,?,?,?,?,?,?), (?,?,?,?,?,?,?)",
        (
            "event-1",
            "run-events",
            "llm_call",
            None,
            "2026-06-29T00:00:00+00:00",
            None,
            '{"text":"hello"}',
            "event-2",
            "run-events",
            "tool_call",
            "read_file",
            "2026-06-29T00:00:01+00:00",
            None,
            '{"tool":"read_file"}',
        ),
    )
    conn.commit()
    conn.close()

    payload = _invoke("events", created["id"], "--after-seq", "0")

    assert [event["seq"] for event in payload["events"]] == [1]
    assert payload["events"][0]["kind"] == "tool_call"
    assert payload["session_id"] == created["id"]


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


def _seed_messages(patched_surface_db, session_id, contents):
    """Append conversation history through the service the CLI reads back."""
    conn = sqlite3.connect(str(patched_surface_db["path"]), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    lock = threading.Lock()
    for role, content in contents:
        session_message_service.append_message(
            conn, lock, surface_session_id=session_id, role=role, content=content
        )
    conn.close()


def test_messages_returns_the_newest_window_oldest_first(patched_surface_db) -> None:
    created = _invoke("create", "--surface-kind", "webui", "--global")
    _seed_messages(
        patched_surface_db,
        created["id"],
        [("user", "first ask"), ("assistant", "first answer"), ("user", "second ask")],
    )

    page = _invoke("messages", created["id"], "--limit", "2")

    assert [m["content"] for m in page["messages"]] == ["first answer", "second ask"]
    assert page["total"] == 3
    assert page["has_more"] is True


def test_messages_pages_forward_with_after_seq(patched_surface_db) -> None:
    created = _invoke("create", "--surface-kind", "webui", "--global")
    _seed_messages(
        patched_surface_db,
        created["id"],
        [("user", "a"), ("assistant", "b"), ("user", "c")],
    )

    page = _invoke("messages", created["id"], "--after-seq", "2")

    assert [m["seq"] for m in page["messages"]] == [3]
    assert page["has_more"] is False


def test_messages_on_an_unknown_session_fails_with_a_named_error() -> None:
    result = runner.invoke(surface_cli.surface_app, ["messages", "nope", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.output)["error"]["code"] == "surface_not_found"


def test_search_finds_history_across_sessions(patched_surface_db) -> None:
    first = _invoke("create", "--surface-kind", "webui", "--surface-id", "t1", "--global")
    second = _invoke("create", "--surface-kind", "webui", "--surface-id", "t2", "--global")
    _seed_messages(patched_surface_db, first["id"], [("user", "the migration wedged")])
    _seed_messages(patched_surface_db, second["id"], [("user", "unrelated chatter")])

    everywhere = _invoke("search", "migration")
    scoped = _invoke("search", "migration", "--session-id", second["id"])

    assert [m["surface_session_id"] for m in everywhere["messages"]] == [first["id"]]
    assert scoped["messages"] == []
