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

MIGRATION_PATH = (
    pathlib.Path(__file__).parent.parent.parent.parent
    / "infra"
    / "migrations"
    / "0001_core.sql"
)


@pytest.fixture(name="db")
def db_fixture() -> sqlite3.Connection:  # type: ignore[return]
    """In-memory SQLite with WAL mode, FK enforcement, and core migration applied.

    Raises pytest.fail if infra/migrations/0001_core.sql does not exist, rather
    than silently returning an empty database (which would cause all downstream
    tests to fail with misleading 'no such table' errors instead of a clear cause).
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    if not MIGRATION_PATH.exists():
        pytest.fail(
            f"Required migration not found: {MIGRATION_PATH}\n"
            "Ensure infra/migrations/0001_core.sql exists before running tests."
        )
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
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
