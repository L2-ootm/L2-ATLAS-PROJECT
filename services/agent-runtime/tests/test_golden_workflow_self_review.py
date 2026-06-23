"""RED-first tests for the Self-Review golden workflow (Phase 10.0.5-03).

Self-Review is the approval-gated golden workflow (D-1): its proposed write
routes through `tool_service.invoke(tool_name="golden_review_write", ...)` — a
write-class tool — and MUST yield a pending `ToolApproval`, never an inline
file write. These tests prove the gate holds end-to-end: propose -> pending ->
approve (executes) / reject (never executes).
"""
from __future__ import annotations

import pathlib

from atlas_runtime import tool_service
from atlas_runtime.golden_workflows import self_review
from atlas_runtime.tools.adapters import golden_review_write
from atlas_runtime.tools.registry import get_registry


# ---------------------------------------------------------------------------
# Adapter unit tests
# ---------------------------------------------------------------------------


def test_golden_review_write_adapter_writes_within_workspace(tmp_path):
    from atlas_core.schemas.tool import ToolResult

    result = golden_review_write.run(
        {"path": "review-note.md", "content": "hello"}, {"workspace_root": str(tmp_path)}
    )
    assert isinstance(result, ToolResult)
    assert result.ok is True
    written = tmp_path / "review-note.md"
    assert written.read_text(encoding="utf-8") == "hello"


def test_golden_review_write_adapter_rejects_path_escape(tmp_path):
    result = golden_review_write.run(
        {"path": "../escape.md", "content": "hello"}, {"workspace_root": str(tmp_path)}
    )
    assert result.ok is False
    assert not (tmp_path.parent / "escape.md").exists()


def test_golden_review_write_registered_as_write_tool():
    manifest, run = get_registry().resolve("golden_review_write")
    assert manifest.risk_level == "write"
    assert callable(run)


# ---------------------------------------------------------------------------
# self_review orchestrator tests — the load-bearing approval-gate proof
# ---------------------------------------------------------------------------


def test_run_self_review_returns_pending_approval_no_write(db, lock, tmp_path):
    wiki_dir = tmp_path / "wiki"

    approval = self_review.run_self_review(
        db, lock, workspace_root=str(tmp_path), wiki_dir=wiki_dir
    )

    assert approval.status == "pending"
    # Nothing executed: no file exists anywhere under tmp_path yet.
    written_files = list(tmp_path.rglob("*.md"))
    assert written_files == []
    pending = tool_service.list_approvals(db, status="pending")
    assert len(pending) >= 1


def test_run_self_review_three_times_creates_three_pending_approvals(db, lock, tmp_path):
    wiki_dir = tmp_path / "wiki"

    for _ in range(3):
        approval = self_review.run_self_review(
            db, lock, workspace_root=str(tmp_path), wiki_dir=wiki_dir
        )
        assert approval.status == "pending"

    pending = tool_service.list_approvals(db, status="pending")
    assert len(pending) == 3  # no de-dup: every call is a fresh, distinct proposal


def test_approving_self_review_executes_the_proposed_write(db, lock, tmp_path):
    wiki_dir = tmp_path / "wiki"

    approval = self_review.run_self_review(
        db, lock, workspace_root=str(tmp_path), wiki_dir=wiki_dir
    )
    done = tool_service.approve(
        db, lock, approval_id=approval.id, ctx={"workspace_root": str(tmp_path)}
    )

    assert done.status == "executed"
    written_files = list(tmp_path.rglob("*.md"))
    assert len(written_files) == 1

    from atlas_runtime.audit_service import get_events_for_run

    events = get_events_for_run(db, "operator")
    completed = [
        e for e in events if e.event_type == "tool_completed" and e.tool_name == "golden_review_write"
    ]
    assert completed


def test_rejecting_self_review_never_writes(db, lock, tmp_path):
    wiki_dir = tmp_path / "wiki"

    approval = self_review.run_self_review(
        db, lock, workspace_root=str(tmp_path), wiki_dir=wiki_dir
    )
    rejected = tool_service.reject(db, lock, approval_id=approval.id, reason="not needed")

    assert rejected.status == "rejected"
    written_files = list(tmp_path.rglob("*.md"))
    assert written_files == []
