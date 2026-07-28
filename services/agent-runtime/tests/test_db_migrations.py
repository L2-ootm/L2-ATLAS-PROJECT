"""Tests for the migration runner (atlas_runtime.db) against real temp-file DBs.

Covers the three real scenarios the runner must handle: a fresh DB, a partially
drifted DB, and a fully hand-patched DB with an empty tracker. Uses a temp FILE
(not :memory:) so the reopen/persistence behaviour is exercised.
"""
from __future__ import annotations

import sqlite3
import threading
import time

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


def test_discord_approvals_table_created(db_path) -> None:
    # 0012 creates the gated-write queue table mirroring DiscordApproval.
    conn = db.connect(db_path)
    db.apply_migrations(conn)
    cols = _cols(conn, "discord_approvals")
    assert {"id", "action", "guild_id", "status", "params", "requested_at"} <= cols
    conn.close()


def test_retention_policy_classifies_every_live_owned_foreign_key(db_path) -> None:
    """New retention-owned FKs must declare preservation/deletion semantics."""
    from atlas_runtime.mission_service import (
        RETENTION_FK_POLICY,
        RETENTION_FK_ROOTS,
        RETENTION_SOFT_OWNERSHIP_POLICY,
    )

    conn = db.connect(db_path)
    db.apply_migrations(conn)
    live_edges = set()
    tables = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for (table,) in tables:
        for fk in conn.execute(f'PRAGMA foreign_key_list("{table}")'):
            parent_table = fk[2]
            if parent_table in RETENTION_FK_ROOTS:
                live_edges.add((table, fk[3], parent_table))

    assert live_edges == set(RETENTION_FK_POLICY)
    assert set(RETENTION_FK_POLICY.values()) == {
        "cascade",
        "explicit-delete",
        "retained",
        "set-null",
    }
    assert RETENTION_SOFT_OWNERSHIP_POLICY == {
        ("actors", "child_run_id", "runs"): "recursive-delete"
    }
    conn.close()


def test_migration_status_reflects_applied_and_pending(db_path) -> None:
    conn = db.connect(db_path)
    before = db.migration_status(conn)
    assert before and all(applied is False for _, applied in before)

    db.apply_migrations(conn)
    after = db.migration_status(conn)
    assert after and all(applied is True for _, applied in after)
    conn.close()


def test_failed_migration_file_rolls_back_schema_and_tracker_together(db_path, tmp_path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_broken.sql").write_text(
        "CREATE TABLE must_not_survive (id TEXT PRIMARY KEY);\n"
        "INSERT INTO table_that_does_not_exist(value) VALUES ('boom');\n",
        encoding="utf-8",
    )
    conn = db.connect(db_path)

    with pytest.raises(sqlite3.OperationalError):
        db.apply_migrations(conn, migrations)

    assert (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'must_not_survive'"
        ).fetchone()
        is None
    )
    assert conn.execute("SELECT version FROM schema_migrations").fetchall() == []
    assert conn.in_transaction is False
    conn.close()


def test_existing_add_column_does_not_skip_later_statements_or_stamp_early(
    db_path, tmp_path
) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_base.sql").write_text(
        "CREATE TABLE sample (id TEXT PRIMARY KEY, adopted TEXT);\n",
        encoding="utf-8",
    )
    (migrations / "0002_adopt.sql").write_text(
        "ALTER TABLE sample ADD COLUMN adopted TEXT;\n"
        "CREATE INDEX sample_adopted_idx ON sample(adopted);\n",
        encoding="utf-8",
    )
    conn = db.connect(db_path)

    assert db.apply_migrations(conn, migrations) == ["0001_base.sql", "0002_adopt.sql"]
    assert (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'sample_adopted_idx'"
        ).fetchone()
        == (1,)
    )
    assert conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall() == [("0001_base.sql",), ("0002_adopt.sql",)]
    conn.close()


def test_concurrent_connections_recheck_tracker_after_writer_lock(
    db_path, tmp_path, monkeypatch
) -> None:
    migrations = tmp_path / "concurrent-migrations"
    migrations.mkdir()
    (migrations / "0001_concurrent.sql").write_text(
        "CREATE TABLE concurrent_value (id TEXT PRIMARY KEY);\n"
        "CREATE TRIGGER concurrent_value_audit AFTER INSERT ON concurrent_value\n"
        "BEGIN\n"
        "  UPDATE concurrent_value SET id = NEW.id WHERE id = NEW.id;\n"
        "END;\n",
        encoding="utf-8",
    )
    connections = [db.connect(db_path), db.connect(db_path)]
    first_has_writer_lock = threading.Event()
    release_first = threading.Event()
    prepare_lock = threading.Lock()
    original_prepare = db._prepare_migration_sql
    first_prepare = True

    def hold_first_writer(conn, sql):
        nonlocal first_prepare
        prepared = original_prepare(conn, sql)
        with prepare_lock:
            should_hold = first_prepare
            first_prepare = False
        if should_hold:
            first_has_writer_lock.set()
            assert release_first.wait(timeout=5)
        return prepared

    monkeypatch.setattr(db, "_prepare_migration_sql", hold_first_writer)
    barrier = threading.Barrier(2)
    results: list[list[str]] = []
    failures: list[BaseException] = []

    def apply(conn):
        try:
            barrier.wait(timeout=5)
            results.append(db.apply_migrations(conn, migrations))
        except BaseException as exc:  # noqa: BLE001 — surfaced below
            failures.append(exc)

    workers = [threading.Thread(target=apply, args=(conn,)) for conn in connections]
    for worker in workers:
        worker.start()
    assert first_has_writer_lock.wait(timeout=5)
    time.sleep(0.05)
    assert any(worker.is_alive() for worker in workers)
    release_first.set()
    for worker in workers:
        worker.join(timeout=5)
    for conn in connections:
        conn.close()

    assert not failures, failures
    assert sorted(results, key=len) == [[], ["0001_concurrent.sql"]]
    verifier = db.connect(db_path)
    try:
        assert verifier.execute(
            "SELECT version FROM schema_migrations"
        ).fetchall() == [("0001_concurrent.sql",)]
        assert verifier.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' "
            "AND name='concurrent_value_audit'"
        ).fetchone() == ("concurrent_value_audit",)
    finally:
        verifier.close()
