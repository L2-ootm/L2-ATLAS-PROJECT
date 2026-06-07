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

    The migration is applied only when infra/migrations/0001_core.sql exists.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    if MIGRATION_PATH.exists():
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        conn.executescript(sql)
    yield conn
    conn.close()


@pytest.fixture(name="run_id")
def run_id_fixture() -> str:
    """A stable run_id for test isolation."""
    return str(uuid.uuid4())


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    """A threading.Lock for audit_service concurrency tests."""
    return threading.Lock()
