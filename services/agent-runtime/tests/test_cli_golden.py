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


# ---------------------------------------------------------------------------
# Demo-reset (Phase 10.0.5-04) — scoped, dry-run-by-default
# ---------------------------------------------------------------------------


def _seed_golden_and_non_golden(db_path, tmp_path):
    """Seed golden-tagged rows (via real dispatch) PLUS a co-existing non-golden
    artifact / wiki page / tool_approval that demo-reset must leave untouched.
    Returns the operator run_id used for the non-golden artifact FK."""
    from atlas_runtime import mission_service, golden_workflow_service, tool_service
    from atlas_wiki import wiki_service

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    lock = threading.Lock()
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"

    # golden rows
    golden_workflow_registry.dispatch(
        "repo_triage", conn=conn, lock=lock, workspace_root=str(workspace), wiki_dir=wiki_dir
    )
    golden_workflow_registry.dispatch(
        "self_review", conn=conn, lock=lock, workspace_root=str(workspace), wiki_dir=wiki_dir
    )

    # non-golden rows that MUST survive a reset
    run_id = mission_service.ensure_operator_run(conn, lock)
    golden_workflow_service.record_artifact(
        conn, lock, run_id=run_id, path="keep/important.md",
        artifact_type="file_write", content=b"operator data",
    )
    wiki_service.update_wiki_page(
        conn, lock, slug="operator-notes", title="Operator Notes",
        body="keep me", run_id=run_id, wiki_dir=wiki_dir,
    )
    # a non-golden pending approval (different reason tag)
    tool_service.invoke(
        conn, lock, tool_name="golden_review_write",
        args={"path": "keep/manual-note.md", "content": "manual"},
        ctx={"workspace_root": str(workspace)}, reason="manual:operator",
    )
    conn.commit()
    conn.close()


def _counts(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        golden_art = conn.execute("SELECT COUNT(*) FROM artifacts WHERE path LIKE 'golden/%'").fetchone()[0]
        keep_art = conn.execute("SELECT COUNT(*) FROM artifacts WHERE path='keep/important.md'").fetchone()[0]
        golden_wiki = conn.execute(
            "SELECT COUNT(*) FROM wiki_pages WHERE slug LIKE 'repo-triage-%' OR slug LIKE 'self-review-%'"
        ).fetchone()[0]
        keep_wiki = conn.execute("SELECT COUNT(*) FROM wiki_pages WHERE slug='operator-notes'").fetchone()[0]
        golden_appr = conn.execute("SELECT COUNT(*) FROM tool_approvals WHERE reason LIKE 'golden_workflow:%'").fetchone()[0]
        keep_appr = conn.execute("SELECT COUNT(*) FROM tool_approvals WHERE reason='manual:operator'").fetchone()[0]
        return golden_art, keep_art, golden_wiki, keep_wiki, golden_appr, keep_appr
    finally:
        conn.close()


def test_cli_golden_reset_dry_run_deletes_nothing(patched_db, tmp_path):
    _seed_golden_and_non_golden(patched_db, tmp_path)
    before = _counts(patched_db)
    result = runner.invoke(golden_cli.golden_app, ["reset", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["artifacts_deleted"] >= 1  # reports would-delete counts
    # nothing actually removed
    assert _counts(patched_db) == before


def test_cli_golden_reset_confirm_is_scoped(patched_db, tmp_path):
    _seed_golden_and_non_golden(patched_db, tmp_path)
    g_art, k_art, g_wiki, k_wiki, g_appr, k_appr = _counts(patched_db)
    assert g_art >= 1 and g_wiki >= 1 and g_appr >= 1  # golden rows present pre-reset
    assert k_art == 1 and k_wiki == 1 and k_appr == 1  # non-golden present pre-reset

    result = runner.invoke(golden_cli.golden_app, ["reset", "--confirm", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is False
    assert payload["artifacts_deleted"] == g_art
    assert payload["tool_approvals_deleted"] == g_appr

    # golden rows gone, non-golden rows survive
    ng_art, nk_art, ng_wiki, nk_wiki, ng_appr, nk_appr = _counts(patched_db)
    assert ng_art == 0 and ng_wiki == 0 and ng_appr == 0
    assert nk_art == 1 and nk_wiki == 1 and nk_appr == 1
