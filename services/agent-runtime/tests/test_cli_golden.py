"""golden_workflow_registry + `atlas golden list|run` CLI (Phase 10.0.5-03).

Uses Typer's CliRunner with `_get_connection` monkeypatched to an injected temp
DB — NEVER the live ~/.atlas/atlas.db (memory cli-db-path-not-atlas-home).
"""
from __future__ import annotations

import json
import sqlite3
import threading

import pytest
from typer.testing import CliRunner

from atlas_runtime import db, golden_workflow_registry
from atlas_runtime.cli import golden as golden_cli

runner = CliRunner()


# ---------------------------------------------------------------------------
# Registry unit tests (no CLI, no DB)
# ---------------------------------------------------------------------------


def test_list_workflows_returns_exactly_three():
    workflows = golden_workflow_registry.list_workflows()
    ids = {w.id for w in workflows}
    assert ids == {"repo_triage", "research_brief", "self_review"}


def test_dispatch_unknown_id_raises(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    db.apply_migrations(conn)
    lock = threading.Lock()
    with pytest.raises(golden_workflow_registry.GoldenWorkflowError):
        golden_workflow_registry.dispatch(
            "unknown_id",
            conn=conn,
            lock=lock,
            workspace_root=str(tmp_path),
            wiki_dir=tmp_path / "wiki",
        )


def test_dispatch_repo_triage_matches_direct_call(tmp_path):
    from atlas_runtime.golden_workflows import repo_triage

    conn = db.connect(tmp_path / "registry2.db")
    db.apply_migrations(conn)
    lock = threading.Lock()
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    direct = repo_triage.run_repo_triage(
        conn, lock, workspace_root=str(tmp_path), wiki_dir=tmp_path / "wiki"
    )
    via_dispatch = golden_workflow_registry.dispatch(
        "repo_triage",
        conn=conn,
        lock=lock,
        workspace_root=str(tmp_path),
        wiki_dir=tmp_path / "wiki",
    )
    assert set(direct.keys()) == set(via_dispatch.keys())


def test_dispatch_self_review_returns_dict_with_pending_status(tmp_path):
    conn = db.connect(tmp_path / "registry3.db")
    db.apply_migrations(conn)
    lock = threading.Lock()

    result = golden_workflow_registry.dispatch(
        "self_review",
        conn=conn,
        lock=lock,
        workspace_root=str(tmp_path),
        wiki_dir=tmp_path / "wiki",
    )
    assert isinstance(result, dict)
    assert result["status"] == "pending"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


@pytest.fixture(name="patched_db")
def patched_db_fixture(tmp_path, monkeypatch):
    """Point the golden CLI at a temp DB with all migrations applied."""
    db_path = tmp_path / "cli-golden.db"
    seed = db.connect(db_path)
    db.apply_migrations(seed)
    seed.close()

    def _conn() -> sqlite3.Connection:
        c = sqlite3.connect(str(db_path), check_same_thread=False)
        c.execute("PRAGMA foreign_keys = ON")
        return c

    monkeypatch.setattr(golden_cli, "_get_connection", _conn)
    monkeypatch.setattr(golden_cli, "_get_lock", lambda: threading.Lock())
    return db_path


def test_cli_golden_list_json(patched_db):
    result = runner.invoke(golden_cli.golden_app, ["list", "--json"])
    assert result.exit_code == 0, result.output
    ids = json.loads(result.output)
    assert set(ids) == {"repo_triage", "research_brief", "self_review"}


def test_cli_golden_run_self_review_json(patched_db, tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    result = runner.invoke(
        golden_cli.golden_app,
        ["run", "self_review", "--workspace", str(workspace), "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "pending"


def test_cli_golden_run_unknown_id_exits_nonzero(patched_db, tmp_path):
    result = runner.invoke(
        golden_cli.golden_app,
        ["run", "does_not_exist", "--workspace", str(tmp_path), "--json"],
    )
    assert result.exit_code != 0
    assert "Error" in result.output or "unknown" in result.output
