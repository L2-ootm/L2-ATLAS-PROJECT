"""Golden-workflow quality gate (Phase 10.0.5-04) — the SC1/SC2 smoke test.

Runs each of the three golden workflows 3x under deterministic, offline,
mock-equivalent conditions (no network, no LLM) and asserts D-2's STRUCTURAL
contract — never byte-equality:
  - repo_triage / research_brief leave a committed Artifact row + a wiki page on
    every call, with the golden_workflow lifecycle audit bookends;
  - self_review NEVER auto-writes: each call yields exactly one new PENDING
    ToolApproval and the proposed file never lands on disk until an explicit
    approve() (which this test deliberately never calls).

Service layer + the in-memory `db`/`lock` conftest fixtures only — NEVER the
live `atlas` CLI / ~/.atlas/atlas.db (memory cli-db-path-not-atlas-home). CLI
surface coverage lives in test_cli_golden.py.
"""
from __future__ import annotations

import datetime

from atlas_runtime import golden_workflow_registry, tool_service
from atlas_runtime.audit_service import get_events_for_run


def _artifact_count(db, run_id: str, path: str) -> int:
    return len(
        db.execute(
            "SELECT 1 FROM artifacts WHERE run_id=? AND path=?", (run_id, path)
        ).fetchall()
    )


def _wiki_exists(db, slug: str) -> bool:
    return db.execute("SELECT 1 FROM wiki_pages WHERE slug=?", (slug,)).fetchone() is not None


def test_each_golden_workflow_runs_three_times_with_consistent_structure(db, lock, tmp_path):
    """The quality gate: 3x each for repo_triage + research_brief, asserting the
    artifact/audit/wiki structure on every call and structural consistency across
    the three reps (same artifact_type, a present non-null sha256 each time — NOT
    equal sha values, since per-run timestamps make content differ)."""
    wiki_dir = tmp_path / "wiki"
    repo_types: list[str] = []
    repo_shas: list[str] = []
    brief_types: list[str] = []

    for rep in range(1, 4):
        # --- repo_triage: workspace read-scan -> artifact + wiki + tool audit ---
        r = golden_workflow_registry.dispatch(
            "repo_triage",
            conn=db,
            lock=lock,
            workspace_root=str(tmp_path),
            wiki_dir=wiki_dir,
        )
        run_id = r["run_id"]
        # append-only: exactly one new artifact row for this path per call
        assert _artifact_count(db, run_id, r["artifact_path"]) == rep
        assert _wiki_exists(db, r["wiki_slug"])
        etypes = {e.event_type for e in get_events_for_run(db, run_id)}
        assert "golden_workflow_started" in etypes
        assert "golden_workflow_completed" in etypes
        # repo_triage touches the workspace through the tool_service chokepoint
        assert "tool_requested" in etypes
        assert "tool_completed" in etypes
        atype, sha = db.execute(
            "SELECT artifact_type, sha256 FROM artifacts WHERE run_id=? AND path=? "
            "ORDER BY created_at DESC LIMIT 1",
            (run_id, r["artifact_path"]),
        ).fetchone()
        repo_types.append(atype)
        repo_shas.append(sha)

        # --- research_brief: offline codex search -> artifact + wiki ---
        rb = golden_workflow_registry.dispatch(
            "research_brief",
            conn=db,
            lock=lock,
            workspace_root=str(tmp_path),
            wiki_dir=wiki_dir,
            topic="atlas",
        )
        assert _artifact_count(db, rb["run_id"], rb["artifact_path"]) == rep
        assert _wiki_exists(db, rb["wiki_slug"])
        btype = db.execute(
            "SELECT artifact_type FROM artifacts WHERE run_id=? AND path=? "
            "ORDER BY created_at DESC LIMIT 1",
            (rb["run_id"], rb["artifact_path"]),
        ).fetchone()[0]
        brief_types.append(btype)

    # structure (not byte-equality): same artifact_type each rep, sha256 present every time
    assert repo_types == ["file_write", "file_write", "file_write"]
    assert all(s for s in repo_shas)  # non-null/non-empty hash recorded each run
    assert brief_types == ["file_write", "file_write", "file_write"]


def test_self_review_three_runs_never_auto_writes(db, lock, tmp_path):
    """The single most important assertion in the phase (D-1/D-2): self_review
    proposes a write 3x and yields EXACTLY 3 pending approvals, never executing —
    the proposed file must never appear on disk. Exact equality (==3), not >=1, so
    a regression that silently auto-executes the gated write fails the count."""
    date_str = datetime.date.today().isoformat()
    proposed = tmp_path / "golden" / f"self-review-{date_str}.md"

    for rep in range(1, 4):
        result = golden_workflow_registry.dispatch(
            "self_review",
            conn=db,
            lock=lock,
            workspace_root=str(tmp_path),
            wiki_dir=tmp_path / "wiki",
        )
        assert result["status"] == "pending"
        assert not proposed.exists()  # gated — never written inline
        pending = tool_service.list_approvals(db, status="pending")
        assert len(pending) == rep  # exactly one new pending approval per call

    assert len(tool_service.list_approvals(db, status="pending")) == 3
    assert not proposed.exists()


def test_full_3x3_sequence_raises_no_exceptions(db, lock, tmp_path):
    """'Repeated failures fixed' means the gate is green, not merely present: run
    the full 9-dispatch sequence (3 workflows x 3 reps) and assert nothing raises,
    and self_review still produced exactly 3 gated approvals with no inline write."""
    wiki_dir = tmp_path / "wiki"
    date_str = datetime.date.today().isoformat()
    proposed = tmp_path / "golden" / f"self-review-{date_str}.md"

    for _ in range(3):
        for wf in ("repo_triage", "research_brief", "self_review"):
            golden_workflow_registry.dispatch(
                wf,
                conn=db,
                lock=lock,
                workspace_root=str(tmp_path),
                wiki_dir=wiki_dir,
                topic="atlas",
            )

    assert len(tool_service.list_approvals(db, status="pending")) == 3
    assert not proposed.exists()
