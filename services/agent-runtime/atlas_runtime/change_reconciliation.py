"""Git turn-boundary mutation reconciliation.

The baseline records Git metadata for clean tracked files and reads only dirty
or untracked files. Final reconciliation uses Git's own ignore/path semantics,
matches native receipts only by canonical path plus SHA-256, and leaves every
residual mutation explicitly unattributed.
"""

from __future__ import annotations

import base64
import hashlib
import pathlib
import subprocess
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas_runtime import evidence_bridge
from atlas_runtime.evidence_bridge import AggregationReceipt

GIT_TIMEOUT_SECONDS = 5.0
MAX_FILE_BYTES = 32 * 1024 * 1024


class FileSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    token: str
    sha256: str | None = None
    content: str | None = None
    mode: str | None = None
    binary: bool = False
    availability: Literal["available", "too_large", "unavailable"] = "available"


class GitBaseline(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace_root: str
    git_available: bool
    head: str | None = None
    files: dict[str, FileSnapshot] = Field(default_factory=dict)
    error_code: str | None = None


class ReconciledFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    old_path: str | None = None
    operation: Literal["create", "edit", "delete", "rename", "mode", "binary"]
    before: str = ""
    after: str = ""
    before_sha256: str | None = None
    after_sha256: str | None = None
    mode_before: str | None = None
    mode_after: str | None = None
    binary: bool = False
    generated: bool = False
    availability: Literal["available", "too_large", "unavailable"] = "available"
    attribution: Literal["unattributed"] = "unattributed"
    capture_status: Literal["captured", "partial", "unavailable"] = "captured"


class ReconciliationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    coverage: Literal["complete", "tool_only", "partial", "unavailable"]
    files: list[ReconciledFile] = Field(default_factory=list)
    matched_change_set_ids: list[str] = Field(default_factory=list)
    baseline_head: str | None = None
    final_head: str | None = None
    error_code: str | None = None


def persist_reference_aggregation(
    *,
    db_path: pathlib.Path | None,
    provenance: dict[str, object],
    child_change_set_ids: list[str],
) -> AggregationReceipt:
    """Deduplicate child identities before crossing the Rust boundary."""

    unique_ids = sorted(
        {value.strip() for value in child_change_set_ids if value.strip()}
    )
    if not unique_ids:
        return evidence_bridge.unavailable_aggregation_receipt("no_children")
    return evidence_bridge.persist_change_aggregation(
        db_path=db_path,
        provenance=provenance,
        child_change_set_ids=unique_ids,
    )


def _git(root: pathlib.Path, *args: str) -> bytes:
    result = subprocess.run(  # noqa: S603
        ["git", "-C", str(root), *args],
        capture_output=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-500:])
    return result.stdout


def _nul_paths(value: bytes) -> set[str]:
    return {
        item.decode("utf-8", errors="replace").replace("\\", "/")
        for item in value.split(b"\0")
        if item
    }


def _tracked_entries(root: pathlib.Path) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for item in _git(root, "ls-files", "-s", "-z").split(b"\0"):
        if not item:
            continue
        metadata, raw_path = item.split(b"\t", 1)
        mode, object_id, _stage = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8", errors="replace").replace("\\", "/")
        entries[path] = (mode, object_id)
    return entries


def _dirty_paths(root: pathlib.Path) -> set[str]:
    unstaged = _nul_paths(_git(root, "diff", "--name-only", "-z", "--", "."))
    staged = _nul_paths(
        _git(root, "diff", "--cached", "--name-only", "-z", "--", ".")
    )
    return unstaged | staged


def _read_snapshot(root: pathlib.Path, path: str, mode: str | None) -> FileSnapshot:
    absolute = (root / pathlib.PurePosixPath(path)).resolve(strict=False)
    try:
        absolute.relative_to(root)
    except ValueError:
        return FileSnapshot(
            path=path,
            token="unavailable",
            mode=mode,
            availability="unavailable",
        )
    try:
        size = absolute.stat().st_size
        if not absolute.is_file():
            raise OSError("not a regular file")
        digest = hashlib.sha256()
        chunks: list[bytes] = []
        with absolute.open("rb") as handle:
            while chunk := handle.read(64 * 1024):
                digest.update(chunk)
                if size <= MAX_FILE_BYTES:
                    chunks.append(chunk)
        sha = digest.hexdigest()
        if size > MAX_FILE_BYTES:
            return FileSnapshot(
                path=path,
                token=f"sha256:{sha}",
                sha256=sha,
                mode=mode,
                availability="too_large",
            )
        raw = b"".join(chunks)
        binary = b"\0" in raw
        content = (
            "base64:" + base64.b64encode(raw).decode("ascii")
            if binary
            else raw.decode("utf-8", errors="replace")
        )
        return FileSnapshot(
            path=path,
            token=f"sha256:{sha}",
            sha256=sha,
            content=content,
            mode=mode,
            binary=binary,
        )
    except OSError:
        return FileSnapshot(
            path=path,
            token="unavailable",
            mode=mode,
            availability="unavailable",
        )


def _snapshot(root: pathlib.Path) -> tuple[str, dict[str, FileSnapshot]]:
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    tracked = _tracked_entries(root)
    dirty = _dirty_paths(root)
    files: dict[str, FileSnapshot] = {}
    for path, (mode, object_id) in tracked.items():
        absolute = root / pathlib.PurePosixPath(path)
        if path in dirty or not absolute.is_file():
            if absolute.is_file():
                files[path] = _read_snapshot(root, path, mode)
            continue
        files[path] = FileSnapshot(
            path=path,
            token=f"git:{object_id}",
            mode=mode,
        )
    for path in sorted(
        _nul_paths(_git(root, "ls-files", "--others", "--exclude-standard", "-z"))
    ):
        files[path] = _read_snapshot(root, path, None)
    return head, files


def capture_git_baseline(workspace_root: str | pathlib.Path) -> GitBaseline:
    root = pathlib.Path(workspace_root).resolve(strict=False)
    try:
        top = pathlib.Path(
            _git(root, "rev-parse", "--show-toplevel")
            .decode("utf-8", errors="replace")
            .strip()
        ).resolve(strict=False)
        if top != root:
            return GitBaseline(
                workspace_root=str(root),
                git_available=False,
                error_code="workspace_not_git_root",
            )
        head, files = _snapshot(root)
        return GitBaseline(
            workspace_root=str(root),
            git_available=True,
            head=head,
            files=files,
        )
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return GitBaseline(
            workspace_root=str(root),
            git_available=False,
            error_code="not_git_workspace",
        )


def _materialize_baseline(
    root: pathlib.Path,
    baseline: GitBaseline,
    path: str,
) -> FileSnapshot | None:
    snapshot = baseline.files.get(path)
    if snapshot is None or snapshot.content is not None or not snapshot.token.startswith("git:"):
        return snapshot
    if baseline.head is None:
        return snapshot
    try:
        raw = _git(root, "show", f"{baseline.head}:{path}")
    except RuntimeError:
        return snapshot.model_copy(
            update={"availability": "unavailable", "token": "unavailable"}
        )
    binary = b"\0" in raw
    content = (
        "base64:" + base64.b64encode(raw).decode("ascii")
        if binary
        else raw.decode("utf-8", errors="replace")
    )
    sha = hashlib.sha256(raw).hexdigest()
    return snapshot.model_copy(
        update={
            "sha256": sha,
            "content": content,
            "binary": binary,
        }
    )


def _native_match(
    path: str,
    after_sha256: str | None,
    native_receipts: list[dict[str, object]],
) -> str | None:
    for receipt in native_receipts:
        receipt_path = str(receipt.get("path", "")).replace("\\", "/")
        receipt_sha = receipt.get("after_sha256")
        if receipt_path == path and receipt_sha == after_sha256:
            change_set_id = receipt.get("change_set_id")
            return str(change_set_id) if change_set_id else None
    return None


def _rename_fingerprint(snapshot: FileSnapshot) -> str | None:
    if snapshot.binary or snapshot.content is None:
        return snapshot.sha256
    normalized = snapshot.content.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def reconcile_git_changes(
    workspace_root: str | pathlib.Path,
    baseline: GitBaseline,
    *,
    native_receipts: list[dict[str, object]],
) -> ReconciliationResult:
    root = pathlib.Path(workspace_root).resolve(strict=False)
    if not baseline.git_available:
        return ReconciliationResult(
            coverage="tool_only",
            baseline_head=baseline.head,
            error_code=baseline.error_code,
        )
    if root != pathlib.Path(baseline.workspace_root):
        return ReconciliationResult(
            coverage="unavailable",
            baseline_head=baseline.head,
            error_code="workspace_mismatch",
        )
    try:
        final_head, final_files = _snapshot(root)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return ReconciliationResult(
            coverage="partial",
            baseline_head=baseline.head,
            error_code="git_reconciliation_failed",
        )

    deleted: list[tuple[str, FileSnapshot]] = []
    created: list[tuple[str, FileSnapshot]] = []
    changed: list[ReconciledFile] = []
    matched: list[str] = []
    paths = sorted(set(baseline.files) | set(final_files))
    for path in paths:
        before = baseline.files.get(path)
        after = final_files.get(path)
        if before is not None and after is not None and before.token == after.token:
            continue
        before = _materialize_baseline(root, baseline, path)
        if before is None and after is not None:
            created.append((path, after))
            continue
        if before is not None and after is None:
            deleted.append((path, before))
            continue
        if before is None or after is None:
            continue
        change_set_id = _native_match(path, after.sha256, native_receipts)
        if change_set_id:
            matched.append(change_set_id)
            continue
        binary = before.binary or after.binary
        operation: Literal["edit", "mode", "binary"]
        if binary:
            operation = "binary"
        elif before.sha256 == after.sha256 and before.mode != after.mode:
            operation = "mode"
        else:
            operation = "edit"
        availability = (
            "too_large"
            if "too_large" in {before.availability, after.availability}
            else (
                "unavailable"
                if "unavailable" in {before.availability, after.availability}
                else "available"
            )
        )
        changed.append(
            ReconciledFile(
                path=path,
                operation=operation,
                before=before.content or "",
                after=after.content or "",
                before_sha256=before.sha256,
                after_sha256=after.sha256,
                mode_before=before.mode,
                mode_after=after.mode,
                binary=binary,
                availability=availability,
                capture_status="captured"
                if availability == "available"
                else "partial",
            )
        )

    used_created: set[str] = set()
    used_deleted: set[str] = set()
    for old_path, before in deleted:
        candidates = [
            (new_path, after)
            for new_path, after in created
            if new_path not in used_created
            and _rename_fingerprint(before) is not None
            and _rename_fingerprint(before) == _rename_fingerprint(after)
        ]
        if len(candidates) != 1:
            continue
        new_path, after = candidates[0]
        used_deleted.add(old_path)
        used_created.add(new_path)
        change_set_id = _native_match(new_path, after.sha256, native_receipts)
        if change_set_id:
            matched.append(change_set_id)
            continue
        changed.append(
            ReconciledFile(
                path=new_path,
                old_path=old_path,
                operation="rename",
                before=before.content or "",
                after=after.content or "",
                before_sha256=before.sha256,
                after_sha256=after.sha256,
                mode_before=before.mode,
                mode_after=after.mode,
                binary=before.binary or after.binary,
            )
        )

    for path, before in deleted:
        if path in used_deleted:
            continue
        changed.append(
            ReconciledFile(
                path=path,
                operation="delete",
                before=before.content or "",
                before_sha256=before.sha256,
                mode_before=before.mode,
                binary=before.binary,
                availability=before.availability,
                capture_status="captured"
                if before.availability == "available"
                else "partial",
            )
        )
    for path, after in created:
        if path in used_created:
            continue
        change_set_id = _native_match(path, after.sha256, native_receipts)
        if change_set_id:
            matched.append(change_set_id)
            continue
        changed.append(
            ReconciledFile(
                path=path,
                operation="binary" if after.binary else "create",
                after=after.content or "",
                after_sha256=after.sha256,
                mode_after=after.mode,
                binary=after.binary,
                availability=after.availability,
                capture_status="captured"
                if after.availability == "available"
                else "partial",
            )
        )

    return ReconciliationResult(
        coverage="complete"
        if all(item.capture_status == "captured" for item in changed)
        else "partial",
        files=sorted(changed, key=lambda item: (item.path, item.operation)),
        matched_change_set_ids=list(dict.fromkeys(matched)),
        baseline_head=baseline.head,
        final_head=final_head,
    )
