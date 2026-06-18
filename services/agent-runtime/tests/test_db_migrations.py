"""Tests for the migration runner (atlas_runtime.db) against real temp-file DBs.

Covers the three real scenarios the runner must handle: a fresh DB, a partially
drifted DB, and a fully hand-patched DB with an empty tracker. Uses a temp FILE
(not :memory:) so the reopen/persistence behaviour is exercised.
"""
from __future__ import annotations

import sqlite3

import pytest

from atlas_runtime import db


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "atlas-test.db"


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_fresh_db_applies_all_and_is_idempotent(db_path) -> None:
    conn = db.connect(db_path)
    applied = db.apply_migrations(conn)
    files = [p.name for p in sorted(db.MIGRATIONS_DIR.glob("*.sql"))]
    assert applied == files
    assert applied, "expected at least one migration file"

    # Schema reflects all migrations.
    assert "project_id" in _cols(conn, "missions")  # 0005
    assert "agent_runtime" in _cols(conn, "runs")  # 0006

    # Tracker has one row per file.
    tracked = {r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    assert tracked == set(files)

    # Second call is a no-op.
    assert db.apply_migrations(conn) == []
    conn.close()


def test_drifted_db_applies_only_pending(db_path) -> None:
    # Simulate a DB previously migrated *through the runner* to 0004 (tracker has
    # 0001..0004 stamped), then newer migrations arrive.
    import datetime

    conn = db.connect(db_path)
    db.ensure_migrations_table(conn)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    early = [p for p in sorted(db.MIGRATIONS_DIR.glob("*.sql")) if p.name < "0005"]
    for p in early:
        conn.executescript(p.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)", (p.name, now)
        )
    conn.commit()
    assert "project_id" not in _cols(conn, "missions")

    applied = db.apply_migrations(conn)
    expected_pending = [
        p.name for p in sorted(db.MIGRATIONS_DIR.glob("*.sql")) if p.name >= "0005"
    ]
    assert applied == expected_pending
    assert "project_id" in _cols(conn, "missions")
    assert "agent_runtime" in _cols(conn, "runs")
    conn.close()


def test_drifted_db_without_tracker_re_runs_idempotent_and_stamps(db_path) -> None:
    # A pre-runner DB (tables exist, tracker empty): the runner re-runs the
    # idempotent CREATE...IF NOT EXISTS files (harmless), applies the missing
    # ALTERs, and stamps everything. applied == all files.
    conn = db.connect(db_path)
    early = [p for p in sorted(db.MIGRATIONS_DIR.glob("*.sql")) if p.name < "0005"]
    for p in early:
        conn.executescript(p.read_text(encoding="utf-8"))
    conn.commit()

    applied = db.apply_migrations(conn)
    assert applied == [p.name for p in sorted(db.MIGRATIONS_DIR.glob("*.sql"))]
    assert "project_id" in _cols(conn, "missions")
    assert "agent_runtime" in _cols(conn, "runs")
    conn.close()


def test_fully_patched_no_tracker_is_adopted_without_error(db_path) -> None:
    # DB already at full schema (all files applied raw) but tracker empty:
    # the runner must swallow duplicate-column, stamp all, and not raise.
    conn = db.connect(db_path)
    for p in sorted(db.MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(p.read_text(encoding="utf-8"))
    conn.commit()

    applied = db.apply_migrations(conn)  # must not raise on the bare ALTERs
    files = [p.name for p in sorted(db.MIGRATIONS_DIR.glob("*.sql"))]
    assert applied == files  # all stamped
    assert "project_id" in _cols(conn, "missions")
    assert "agent_runtime" in _cols(conn, "runs")
    assert db.apply_migrations(conn) == []
    conn.close()


def test_migration_status_reflects_applied_and_pending(db_path) -> None:
    conn = db.connect(db_path)
    before = db.migration_status(conn)
    assert before and all(applied is False for _, applied in before)

    db.apply_migrations(conn)
    after = db.migration_status(conn)
    assert after and all(applied is True for _, applied in after)
    conn.close()
