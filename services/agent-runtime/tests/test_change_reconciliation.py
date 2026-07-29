from __future__ import annotations

import hashlib
import subprocess

from atlas_runtime.change_reconciliation import (
    capture_git_baseline,
    persist_reference_aggregation,
    reconcile_git_changes,
)
from atlas_runtime.evidence_bridge import AggregationReceipt


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "atlas@example.invalid")
    _git(root, "config", "user.name", "ATLAS Test")
    (root / ".gitignore").write_text("node_modules/\nignored.log\n", encoding="utf-8")
    (root / "edit.txt").write_text("old\n", encoding="utf-8")
    (root / "delete.txt").write_text("delete\n", encoding="utf-8")
    (root / "rename.txt").write_text("rename\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    return root


def test_shell_git_reconciliation_captures_create_edit_delete_and_rename(tmp_path):
    root = _repo(tmp_path)
    baseline = capture_git_baseline(root)

    (root / "edit.txt").write_text("new\n", encoding="utf-8")
    (root / "delete.txt").unlink()
    (root / "rename.txt").rename(root / "renamed.txt")
    (root / "created.txt").write_text("created\n", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
    (root / "ignored.log").write_text("ignored", encoding="utf-8")

    result = reconcile_git_changes(root, baseline, native_receipts=[])

    assert result.coverage == "complete"
    operations = {(item.operation, item.path, item.old_path) for item in result.files}
    assert ("edit", "edit.txt", None) in operations
    assert ("delete", "delete.txt", None) in operations
    assert ("rename", "renamed.txt", "rename.txt") in operations
    assert ("create", "created.txt", None) in operations
    assert all("node_modules" not in item.path for item in result.files)
    assert all(item.path != "ignored.log" for item in result.files)
    assert all(item.attribution == "unattributed" for item in result.files)


def test_git_reconciliation_matches_native_receipt_by_path_and_hash(tmp_path):
    root = _repo(tmp_path)
    baseline = capture_git_baseline(root)
    content = "native edit\n"
    (root / "edit.txt").write_text(content, encoding="utf-8")
    after_hash = hashlib.sha256((root / "edit.txt").read_bytes()).hexdigest()

    result = reconcile_git_changes(
        root,
        baseline,
        native_receipts=[
            {
                "change_set_id": "native-change",
                "path": "edit.txt",
                "after_sha256": after_hash,
            }
        ],
    )

    assert result.matched_change_set_ids == ["native-change"]
    assert [item.path for item in result.files] == []


def test_git_reconciliation_leaves_hash_mismatch_unattributed(tmp_path):
    root = _repo(tmp_path)
    baseline = capture_git_baseline(root)
    (root / "edit.txt").write_text("shell won\n", encoding="utf-8")

    result = reconcile_git_changes(
        root,
        baseline,
        native_receipts=[
            {
                "change_set_id": "stale-native",
                "path": "edit.txt",
                "after_sha256": "0" * 64,
            }
        ],
    )

    assert result.matched_change_set_ids == []
    assert len(result.files) == 1
    assert result.files[0].attribution == "unattributed"
    assert result.files[0].capture_status == "captured"


def test_git_coverage_excludes_unchanged_preexisting_untracked_file(tmp_path):
    root = _repo(tmp_path)
    (root / "preexisting.txt").write_text("before\n", encoding="utf-8")
    baseline = capture_git_baseline(root)
    (root / "new.txt").write_text("after\n", encoding="utf-8")

    result = reconcile_git_changes(root, baseline, native_receipts=[])

    assert [item.path for item in result.files] == ["new.txt"]


def test_non_git_workspace_reports_tool_only_coverage(tmp_path):
    result = reconcile_git_changes(
        tmp_path,
        capture_git_baseline(tmp_path),
        native_receipts=[{"change_set_id": "native-only", "path": "x.txt"}],
    )

    assert result.coverage == "tool_only"
    assert result.files == []
    assert result.matched_change_set_ids == []


def test_aggregate_deduplicates_child_ids_before_rust_boundary(monkeypatch, tmp_path):
    observed = {}

    def persist_change_aggregation(**kwargs):
        observed.update(kwargs)
        return AggregationReceipt(
            change_set_id="aggregate-1",
            coverage="complete",
            status="captured",
            child_count=2,
            file_count=3,
            additions=4,
            deletions=1,
            redaction_count=0,
        )

    monkeypatch.setattr(
        "atlas_runtime.change_reconciliation.evidence_bridge.persist_change_aggregation",
        persist_change_aggregation,
    )
    receipt = persist_reference_aggregation(
        db_path=tmp_path / "atlas.db",
        provenance={"run_id": "run-1", "actor_id": "actor-parent"},
        child_change_set_ids=["child-b", "child-a", "child-b"],
    )

    assert observed["child_change_set_ids"] == ["child-a", "child-b"]
    assert receipt.child_count == 2
