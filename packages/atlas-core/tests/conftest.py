"""Pytest configuration and shared fixtures for atlas-core tests."""

# MIGRATION_PATH depth explanation:
# conftest.py lives at: packages/atlas-core/tests/conftest.py
# .parent   = packages/atlas-core/tests/
# .parent   = packages/atlas-core/
# .parent   = packages/
# .parent   = <project root>
# So 4 parents up from __file__ = project root
# Then / "infra" / "migrations" / "0001_core.sql"

import pathlib
import sqlite3

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
    This fixture does not raise FileNotFoundError when the migration file is absent —
    it is written in plan 02-03. Tests that require the migration must check for
    the file themselves or be skipped via pytest.importorskip / pytest.mark.skipif.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    if MIGRATION_PATH.exists():
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        conn.executescript(sql)
    yield conn
    conn.close()
