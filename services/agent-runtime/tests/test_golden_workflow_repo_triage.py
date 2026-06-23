"""RED-first tests for the Repo Triage golden workflow (Phase 10.0.5-02).

Repo Triage is an internal-risk (auto-run) deterministic orchestrator: a real
workspace read-scan via the 10.0.4 tool_service chokepoint -> markdown
artifact + wiki page, independent of any LLM output (mock provider produces
no structural output — see 10.0.5-CONTEXT.md).
"""
from __future__ import annotations

from atlas_runtime.audit_service import get_events_for_run
from atlas_runtime.golden_workflows import repo_triage


def test_run_repo_triage_returns_expected_keys(db, lock, tmp_path):
    (tmp_path / "README.md").write_text("# Demo Repo\n\nThis is the demo repo.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"

    result = repo_triage.run_repo_triage(
        db, lock, workspace_root=str(tmp_path), wiki_dir=wiki_dir
    )

    assert set(["artifact_path", "wiki_slug", "run_id"]).issubset(result.keys())
    assert result["artifact_path"]
    assert result["wiki_slug"]
    assert result["run_id"]


def test_run_repo_triage_inserts_one_artifact_row(db, lock, tmp_path):
    (tmp_path / "README.md").write_text("# Demo Repo\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"

    result = repo_triage.run_repo_triage(
        db, lock, workspace_root=str(tmp_path), wiki_dir=wiki_dir
    )

    rows = db.execute(
        "SELECT path, artifact_type FROM artifacts WHERE run_id=?",
        (result["run_id"],),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "file_write"
    assert rows[0][0].endswith(".md")


def test_run_repo_triage_emits_full_audit_trail(db, lock, tmp_path):
    (tmp_path / "README.md").write_text("# Demo Repo\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"

    result = repo_triage.run_repo_triage(
        db, lock, workspace_root=str(tmp_path), wiki_dir=wiki_dir
    )

    types = [e.event_type for e in get_events_for_run(db, result["run_id"])]
    assert "golden_workflow_started" in types
    assert "tool_requested" in types
    assert "tool_completed" in types
    assert "artifact" in types
    assert "wiki_update" in types
    assert "golden_workflow_completed" in types


def test_run_repo_triage_three_times_does_not_raise(db, lock, tmp_path):
    (tmp_path / "README.md").write_text("# Demo Repo\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"

    for _ in range(3):
        result = repo_triage.run_repo_triage(
            db, lock, workspace_root=str(tmp_path), wiki_dir=wiki_dir
        )
        assert result["artifact_path"]


def test_run_repo_triage_no_readme_degrades_gracefully(db, lock, tmp_path):
    wiki_dir = tmp_path / "wiki"

    result = repo_triage.run_repo_triage(
        db, lock, workspace_root=str(tmp_path), wiki_dir=wiki_dir
    )

    assert result["artifact_path"]
    artifact_row = db.execute(
        "SELECT path FROM artifacts WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
        (result["run_id"],),
    ).fetchone()
    assert artifact_row is not None
