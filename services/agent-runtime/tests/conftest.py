"""Pytest configuration and shared fixtures for agent-runtime tests."""

# MIGRATION_PATH depth explanation:
# conftest.py lives at: services/agent-runtime/tests/conftest.py
# .parent        = services/agent-runtime/tests/
# .parent.parent = services/agent-runtime/
# .parent x3     = services/
# .parent x4     = <project root>
# So 4 parents up from __file__ = project root
# Then / "infra" / "migrations" / "0001_core.sql"
# Note: plan spec said 3 hops but was counting directory transitions, not .parent calls.
# Correct value is 4 (verified: migration exists at 4-hop path).

import pathlib
import sqlite3
import threading
import uuid

import pytest

MIGRATIONS_DIR = (
    pathlib.Path(__file__).parent.parent.parent.parent / "infra" / "migrations"
)


@pytest.fixture(name="db")
def db_fixture() -> sqlite3.Connection:  # type: ignore[return]
    """In-memory SQLite with WAL mode, FK enforcement, and ALL migrations applied.

    Applies every infra/migrations/*.sql in sorted order so the fixture reflects
    the current schema (project_id, provenance, registry, …) — the same path the
    fresh-machine bootstrap uses. Raises pytest.fail if no migrations are found,
    rather than silently returning an empty database (which would cause downstream
    tests to fail with misleading 'no such table' errors instead of a clear cause).
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migrations:
        pytest.fail(
            f"No migrations found in: {MIGRATIONS_DIR}\n"
            "Ensure infra/migrations/*.sql exist before running tests."
        )
    for sql_path in migrations:
        conn.executescript(sql_path.read_text(encoding="utf-8"))
    yield conn
    conn.close()


@pytest.fixture(name="run_id")
def run_id_fixture(db: sqlite3.Connection) -> str:
    """A stable run_id for test isolation.

    Inserts a minimal mission + run row into the in-memory DB so that
    FK constraints on audit_events.run_id and tool_calls.run_id are satisfied
    when PRAGMA foreign_keys = ON is active.
    """
    import datetime

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
    """A threading.Lock for audit_service concurrency tests."""
    return threading.Lock()
