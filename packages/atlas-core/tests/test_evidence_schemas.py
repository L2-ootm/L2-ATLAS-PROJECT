"""Frozen Evidence Plane contracts and additive storage schema."""

from __future__ import annotations

import json
import pathlib
import sqlite3

import pytest
from pydantic import ValidationError


def test_evidence_contracts_are_frozen_and_json_stable() -> None:
    from atlas_core.schemas.core import (
        ChangeSet,
        DiffHunk,
        EvidenceProvenance,
        FileChange,
        FullResultReference,
    )

    provenance = EvidenceProvenance(
        run_id="run-1",
        session_id="session-1",
        actor_id="actor-1",
        tool_call_id="tool-1",
    )
    hunk = DiffHunk(
        id="hunk-1",
        file_change_id="file-1",
        old_start=1,
        old_lines=1,
        new_start=1,
        new_lines=2,
        patch="@@ -1,1 +1,2 @@\n-old\n+new\n+line\n",
    )
    file_change = FileChange(
        id="file-1",
        change_set_id="change-1",
        path="src/example.py",
        operation="edit",
        before_sha256="a" * 64,
        after_sha256="b" * 64,
        additions=2,
        deletions=1,
        hunks=(hunk,),
    )
    change_set = ChangeSet(
        id="change-1",
        provenance=provenance,
        coverage="complete",
        files=(file_change,),
    )
    reference = FullResultReference(
        evidence_id="result-1",
        owner_kind="run",
        owner_id="run-1",
        availability="available",
        preview="bounded",
        preview_bytes=7,
        full_bytes=12,
        sha256="c" * 64,
    )

    payload = {
        "change_set": change_set.model_dump(),
        "full_result": reference.model_dump(),
    }
    assert json.loads(json.dumps(payload)) == payload
    assert payload["change_set"]["files"][0]["operation"] == "edit"
    with pytest.raises(ValidationError):
        reference.preview = "mutated"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("model_name", "field", "expected"),
    [
        (
            "FileChange",
            "operation",
            {"create", "edit", "delete", "rename", "mode", "binary"},
        ),
        (
            "FileChange",
            "availability",
            {"available", "redacted", "partial", "unavailable", "too_large"},
        ),
        (
            "ChangeSet",
            "coverage",
            {"complete", "tool_only", "partial", "unavailable"},
        ),
        (
            "FullResultReference",
            "availability",
            {"available", "redacted", "unavailable", "too_large"},
        ),
    ],
)
def test_evidence_enums_are_explicit(
    model_name: str, field: str, expected: set[str]
) -> None:
    from atlas_core.schemas import core

    schema = getattr(core, model_name).model_json_schema()
    field_schema = schema["properties"][field]
    enum_values = set(field_schema.get("enum", []))
    assert enum_values == expected


def test_evidence_migration_is_idempotent_and_indexed() -> None:
    root = pathlib.Path(__file__).parents[3]
    core_sql = (root / "infra/migrations/0001_core.sql").read_text(encoding="utf-8")
    evidence_sql = (root / "infra/migrations/0033_evidence_plane.sql").read_text(
        encoding="utf-8"
    )
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(core_sql)
    conn.executescript(evidence_sql)
    conn.executescript(evidence_sql)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {
        "evidence_change_sets",
        "evidence_file_changes",
        "evidence_hunks",
        "evidence_blobs",
        "evidence_blob_chunks",
        "evidence_child_refs",
        "evidence_full_results",
    } <= tables
    indexes = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    assert {
        "idx_evidence_change_sets_run_cursor",
        "idx_evidence_file_changes_set_cursor",
        "idx_evidence_hunks_file_cursor",
        "idx_evidence_full_results_owner_cursor",
    } <= indexes
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_every_evidence_cursor_query_uses_its_declared_index() -> None:
    root = pathlib.Path(__file__).parents[3]
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    for migration in sorted((root / "infra/migrations").glob("*.sql")):
        conn.executescript(migration.read_text(encoding="utf-8"))
    # Second application proves the additive evidence migration itself remains
    # safe after a fully upgraded database has converged.
    conn.executescript(
        (root / "infra/migrations/0033_evidence_plane.sql").read_text(
            encoding="utf-8"
        )
    )
    assertions = [
        (
            "idx_evidence_change_sets_run_cursor",
            "SELECT id FROM evidence_change_sets"
            " WHERE run_id=? ORDER BY created_at,id LIMIT 10",
            ("run-1",),
        ),
        (
            "idx_evidence_change_sets_session_cursor",
            "SELECT id FROM evidence_change_sets"
            " WHERE session_id=? ORDER BY created_at,id LIMIT 10",
            ("session-1",),
        ),
        (
            "idx_evidence_change_sets_team_cursor",
            "SELECT id FROM evidence_change_sets"
            " WHERE team_run_id=? ORDER BY created_at,id LIMIT 10",
            ("team-1",),
        ),
        (
            "idx_evidence_file_changes_set_cursor",
            "SELECT id FROM evidence_file_changes"
            " WHERE change_set_id=? ORDER BY id LIMIT 10",
            ("change-1",),
        ),
        (
            "idx_evidence_hunks_file_cursor",
            "SELECT id FROM evidence_hunks"
            " WHERE file_change_id=? ORDER BY hunk_index LIMIT 10",
            ("file-1",),
        ),
        (
            "idx_evidence_full_results_owner_cursor",
            "SELECT id FROM evidence_full_results"
            " WHERE owner_kind=? AND owner_id=? ORDER BY created_at,id LIMIT 10",
            ("run", "run-1"),
        ),
    ]
    for index, query, params in assertions:
        plan = " ".join(
            str(column)
            for row in conn.execute(f"EXPLAIN QUERY PLAN {query}", params)
            for column in row
        )
        assert index in plan, f"{index} missing from query plan: {plan}"
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
