"""Pytest configuration and shared fixtures for wiki-runtime tests."""

# MIGRATION_PATH depth explanation:
# conftest.py lives at: services/wiki-runtime/tests/conftest.py
# .parent        = services/wiki-runtime/tests/
# .parent.parent = services/wiki-runtime/
# .parent x3     = services/
# .parent x4     = <project root>
# So 4 parents up from __file__ = project root
# Then / "infra" / "migrations" / "0001_core.sql"

import datetime
import pathlib
import sqlite3
import threading
import uuid

import pytest

MIGRATION_0001 = (
    pathlib.Path(__file__).parent.parent.parent.parent
    / "infra"
    / "migrations"
    / "0001_core.sql"
)

MIGRATION_0002 = (
    pathlib.Path(__file__).parent.parent.parent.parent
    / "infra"
    / "migrations"
    / "0002_wiki_provenance.sql"
)


@pytest.fixture(name="db")
def db_fixture() -> sqlite3.Connection:  # type: ignore[return]
    """In-memory SQLite with WAL mode, FK enforcement, and both migrations applied.

    Applies 0001_core.sql then 0002_wiki_provenance.sql in order.
    Raises pytest.fail if either migration file does not exist.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")

    for migration_path in (MIGRATION_0001, MIGRATION_0002):
        if not migration_path.exists():
            pytest.fail(
                f"Required migration not found: {migration_path}\n"
                "Ensure infra/migrations/ files exist before running tests."
            )
        sql = migration_path.read_text(encoding="utf-8")
        conn.executescript(sql)

    yield conn
    conn.close()


@pytest.fixture(name="run_id")
def run_id_fixture(db: sqlite3.Connection) -> str:
    """A stable run_id for test isolation.

    Inserts a minimal mission + run row so FK constraints on audit_events.run_id
    and wiki operations are satisfied when PRAGMA foreign_keys = ON is active.
    """
    mission_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (mission_id, "test-mission", "", "pending", "", now, now),
    )
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, mission_id, None, "running", now, None, ""),
    )
    db.commit()

    return run_id


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    """A threading.Lock for wiki_service concurrency control."""
    return threading.Lock()


@pytest.fixture(name="wiki_dir")
def wiki_dir_fixture(tmp_path: pathlib.Path) -> pathlib.Path:
    """A temporary wiki directory with raw/, index.md, and log.md stubs.

    Mirrors the expected wiki directory layout used by ingest_source,
    update_wiki_page, _update_index, and _append_log.
    """
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (tmp_path / "index.md").write_text("# ATLAS Wiki Index\n", encoding="utf-8")
    (tmp_path / "log.md").write_text("# ATLAS Wiki Log\n", encoding="utf-8")
    return tmp_path
