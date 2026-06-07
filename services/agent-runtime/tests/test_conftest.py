"""Smoke tests for conftest fixtures — always collected, no external deps."""

import sqlite3
import threading


def test_db_fixture_returns_connection(db):
    """db fixture provides a sqlite3.Connection with audit_events table."""
    assert isinstance(db, sqlite3.Connection)
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE name='audit_events'"
    ).fetchone()
    assert row is not None, "audit_events table not found — check MIGRATION_PATH"


def test_run_id_fixture_is_uuid_string(run_id):
    """run_id fixture returns a non-empty string."""
    assert isinstance(run_id, str)
    assert len(run_id) > 0


def test_lock_fixture_is_threading_lock(lock):
    """lock fixture returns a threading.Lock."""
    assert isinstance(lock, type(threading.Lock()))
