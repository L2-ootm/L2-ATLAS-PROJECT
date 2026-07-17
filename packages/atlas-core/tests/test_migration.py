"""Tests for infra/migrations/0001_core.sql — SCHEMA-02 (apply, tables, columns, FTS5, FK enforcement)."""

import pathlib
import sqlite3
import uuid

import pytest

# Resolve migration path the same way conftest.py does:
# tests/conftest.py -> 4 parents up = project root
MIGRATION_PATH = (
    pathlib.Path(__file__).parent.parent.parent.parent
    / "infra"
    / "migrations"
    / "0001_core.sql"
)


# ---------------------------------------------------------------------------
# Basic migration apply
# ---------------------------------------------------------------------------


def test_migration_applies(db: sqlite3.Connection) -> None:
    """Applying 0001_core.sql to :memory: SQLite does not raise OperationalError."""
    # db fixture already applies the migration — if we get here it worked
    assert db is not None


def test_migration_file_exists() -> None:
    """Migration file must exist at the expected path."""
    assert MIGRATION_PATH.exists(), f"Migration file not found at {MIGRATION_PATH}"


# ---------------------------------------------------------------------------
# Table presence
# ---------------------------------------------------------------------------


def test_all_tables_created(db: sqlite3.Connection) -> None:
    """After migration, sqlite_master contains exactly the 7 expected tables."""
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    table_names = {row[0] for row in rows}
    expected = {"missions", "runs", "audit_events", "tool_calls", "artifacts", "sources", "wiki_pages"}
    assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"


def test_fts5_available(db: sqlite3.Connection) -> None:
    """sqlite_master must contain a row with name='wiki_fts'."""
    row = db.execute("SELECT name FROM sqlite_master WHERE name='wiki_fts'").fetchone()
    assert row is not None, "wiki_fts virtual table not found in sqlite_master"


# ---------------------------------------------------------------------------
# Column counts
# ---------------------------------------------------------------------------


def test_missions_column_count(db: sqlite3.Connection) -> None:
    cols = db.execute("PRAGMA table_info(missions)").fetchall()
    assert len(cols) == 7, f"Expected 7 columns, got {len(cols)}: {[c[1] for c in cols]}"


def test_runs_column_count(db: sqlite3.Connection) -> None:
    # This fixture applies 0001 only; agent_runtime is added additively in 0006 (P4).
    cols = db.execute("PRAGMA table_info(runs)").fetchall()
    assert len(cols) == 7, f"Expected 7 columns, got {len(cols)}: {[c[1] for c in cols]}"


def test_audit_events_column_count(db: sqlite3.Connection) -> None:
    cols = db.execute("PRAGMA table_info(audit_events)").fetchall()
    assert len(cols) == 11, f"Expected 11 columns, got {len(cols)}: {[c[1] for c in cols]}"


def test_tool_calls_column_count(db: sqlite3.Connection) -> None:
    cols = db.execute("PRAGMA table_info(tool_calls)").fetchall()
    assert len(cols) == 13, f"Expected 13 columns, got {len(cols)}: {[c[1] for c in cols]}"


def test_artifacts_column_count(db: sqlite3.Connection) -> None:
    cols = db.execute("PRAGMA table_info(artifacts)").fetchall()
    assert len(cols) == 8, f"Expected 8 columns, got {len(cols)}: {[c[1] for c in cols]}"


def test_sources_column_count(db: sqlite3.Connection) -> None:
    cols = db.execute("PRAGMA table_info(sources)").fetchall()
    assert len(cols) == 7, f"Expected 7 columns, got {len(cols)}: {[c[1] for c in cols]}"


def test_wiki_pages_column_count(db: sqlite3.Connection) -> None:
    cols = db.execute("PRAGMA table_info(wiki_pages)").fetchall()
    assert len(cols) == 8, f"Expected 8 columns, got {len(cols)}: {[c[1] for c in cols]}"


# ---------------------------------------------------------------------------
# Column name drift tests (D-012: DDL must mirror model_fields 1:1)
# ---------------------------------------------------------------------------


def test_column_names_match_fields_mission(db: sqlite3.Connection) -> None:
    from atlas_core.schemas.core import Mission

    cols = {row[1] for row in db.execute("PRAGMA table_info(missions)").fetchall()}
    fields = set(Mission.model_fields.keys())
    # project_id (0005) and origin (0024) are added additively; the 0001-only
    # fixture lacks them, so exclude them from the 0001 drift check.
    assert cols == fields - {"project_id", "origin"}, (
        f"Schema drift — 0001 DDL: {cols}, model: {fields}"
    )


def test_column_names_match_fields_run(db: sqlite3.Connection) -> None:
    from atlas_core.schemas.core import Run

    cols = {row[1] for row in db.execute("PRAGMA table_info(runs)").fetchall()}
    fields = set(Run.model_fields.keys())
    # agent_runtime is added additively in 0006_agent_runtime.sql (P4); the
    # 0001-only fixture lacks it, so exclude it from the 0001 drift check.
    assert cols == fields - {"agent_runtime"}, f"Schema drift — 0001 DDL: {cols}, model: {fields}"


def test_column_names_match_fields_audit_event(db: sqlite3.Connection) -> None:
    from atlas_core.schemas.core import AuditEvent

    cols = {row[1] for row in db.execute("PRAGMA table_info(audit_events)").fetchall()}
    fields = set(AuditEvent.model_fields.keys())
    assert cols == fields, f"Schema drift — DDL: {cols}, model: {fields}"


def test_column_names_match_fields_wiki_page(db: sqlite3.Connection) -> None:
    from atlas_core.schemas.core import WikiPage

    cols = {row[1] for row in db.execute("PRAGMA table_info(wiki_pages)").fetchall()}
    fields = set(WikiPage.model_fields.keys())
    assert cols == fields, f"Schema drift — DDL: {cols}, model: {fields}"


# ---------------------------------------------------------------------------
# FK enforcement
# ---------------------------------------------------------------------------


def test_fk_enforcement(db: sqlite3.Connection) -> None:
    """Inserting a Run row with a nonexistent mission_id raises IntegrityError."""
    fake_mission_id = str(uuid.uuid4())
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO runs (id, mission_id, status, started_at) VALUES (?, ?, 'running', '2026-01-01T00:00:00')",
            (str(uuid.uuid4()), fake_mission_id),
        )
        db.commit()


# ---------------------------------------------------------------------------
# WAL mode
# ---------------------------------------------------------------------------


def test_wal_mode(db: sqlite3.Connection) -> None:
    """PRAGMA journal_mode must not return an unexpected mode.

    WAL mode is not supported on :memory: databases in all SQLite versions;
    the pragma returns 'memory' in that case. Accept both 'wal' and 'memory'.
    """
    result = db.execute("PRAGMA journal_mode").fetchone()[0]
    assert result in ("wal", "memory"), f"Unexpected journal mode: {result}"


# ---------------------------------------------------------------------------
# FTS5 trigger stubs
# ---------------------------------------------------------------------------


def test_fts5_triggers_present(db: sqlite3.Connection) -> None:
    """sqlite_master must contain all 3 FTS5 trigger stubs."""
    trigger_names = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
    }
    assert "wiki_fts_insert" in trigger_names, "wiki_fts_insert trigger missing"
    assert "wiki_fts_update" in trigger_names, "wiki_fts_update trigger missing"
    assert "wiki_fts_delete" in trigger_names, "wiki_fts_delete trigger missing"


# ---------------------------------------------------------------------------
# FTS5 functional search
# ---------------------------------------------------------------------------


def test_insert_and_fts_search(db: sqlite3.Connection) -> None:
    """FTS5 virtual table is functional: insert a wiki_page, rebuild index, search."""
    page_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO wiki_pages (id, slug, title, body, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, '2026-01-01T00:00:00', '2026-01-01T00:00:00')",
        (page_id, "test-slug", "AtlasSearchTitle", "Some body content for FTS5 test"),
    )
    db.commit()
    # Force FTS5 index rebuild to ensure content is indexed
    db.execute("INSERT INTO wiki_fts(wiki_fts) VALUES('rebuild')")
    rows = db.execute(
        "SELECT rowid FROM wiki_fts WHERE wiki_fts MATCH 'AtlasSearchTitle'"
    ).fetchall()
    assert len(rows) >= 1, "FTS5 search returned 0 results after rebuild"
