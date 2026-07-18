"""Tests for atlas_runtime.retention_service — data lifecycle management."""
import json
import sqlite3
import threading
import pytest

from atlas_runtime import retention_service


@pytest.fixture
def conn():
    """In-memory SQLite connection with required tables."""
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript("""
        CREATE TABLE missions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            intent TEXT DEFAULT '',
            status TEXT NOT NULL,
            project TEXT DEFAULT '',
            project_id TEXT,
            origin TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived_at TEXT,
            delete_after TEXT,
            priority INTEGER DEFAULT 0
        );
        CREATE TABLE runs (
            id TEXT PRIMARY KEY,
            mission_id TEXT NOT NULL,
            session_id TEXT,
            status TEXT NOT NULL,
            started_at TEXT,
            summary TEXT
        );
        CREATE TABLE tool_calls (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            tool_name TEXT,
            status TEXT
        );
        CREATE TABLE audit_events (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            event_type TEXT
        );
        CREATE TABLE artifacts (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            path TEXT
        );
        CREATE TABLE mission_archive (
            mission_id TEXT PRIMARY KEY,
            archived_at TEXT NOT NULL,
            delete_after TEXT NOT NULL
        );
        CREATE TABLE mission_compressions (
            mission_id TEXT PRIMARY KEY,
            compressed_at TEXT NOT NULL,
            tool_call_count INTEGER DEFAULT 0,
            audit_event_count INTEGER DEFAULT 0,
            artifact_count INTEGER DEFAULT 0,
            summary_json TEXT DEFAULT '{}'
        );
    """)
    yield c
    c.close()


@pytest.fixture
def lock():
    return threading.Lock()


class TestCompressMissionData:
    def test_compresses_old_archived_mission(self, conn, lock):
        # Create an old archived mission
        conn.execute(
            "INSERT INTO missions (id, title, status, created_at, updated_at) "
            "VALUES ('m1', 'Old Mission', 'archived', '2026-01-01', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO mission_archive (mission_id, archived_at, delete_after) "
            "VALUES ('m1', '2026-01-01', '2099-01-01')"
        )
        conn.execute(
            "INSERT INTO runs (id, mission_id, status, started_at) "
            "VALUES ('r1', 'm1', 'completed', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO tool_calls (id, run_id, tool_name, status) "
            "VALUES ('tc1', 'r1', 'web_search', 'success')"
        )
        conn.execute(
            "INSERT INTO tool_calls (id, run_id, tool_name, status) "
            "VALUES ('tc2', 'r1', 'web_search', 'success')"
        )
        conn.execute(
            "INSERT INTO audit_events (id, run_id, event_type) "
            "VALUES ('ae1', 'r1', 'tool_call')"
        )
        conn.commit()

        count = retention_service.compress_mission_data(conn, lock, after_archive_days=0)

        assert count == 1
        # Verify compression record exists
        row = conn.execute(
            "SELECT tool_call_count, audit_event_count FROM mission_compressions WHERE mission_id='m1'"
        ).fetchone()
        assert row is not None
        assert row[0] == 2  # 2 tool calls
        assert row[1] == 1  # 1 audit event

        # Verify raw data was deleted
        tc = conn.execute("SELECT COUNT(*) FROM tool_calls WHERE run_id='r1'").fetchone()[0]
        ae = conn.execute("SELECT COUNT(*) FROM audit_events WHERE run_id='r1'").fetchone()[0]
        assert tc == 0
        assert ae == 0

    def test_skips_already_compressed(self, conn, lock):
        conn.execute(
            "INSERT INTO missions (id, title, status, created_at, updated_at) "
            "VALUES ('m1', 'Mission', 'archived', '2026-01-01', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO mission_archive (mission_id, archived_at, delete_after) "
            "VALUES ('m1', '2026-01-01', '2099-01-01')"
        )
        conn.execute(
            "INSERT INTO mission_compressions (mission_id, compressed_at) "
            "VALUES ('m1', '2026-01-01')"
        )
        conn.commit()

        count = retention_service.compress_mission_data(conn, lock, after_archive_days=0)
        assert count == 0

    def test_skips_non_archived_missions(self, conn, lock):
        conn.execute(
            "INSERT INTO missions (id, title, status, created_at, updated_at) "
            "VALUES ('m1', 'Active', 'running', '2026-01-01', '2026-01-01')"
        )
        conn.commit()

        count = retention_service.compress_mission_data(conn, lock, after_archive_days=0)
        assert count == 0


class TestGetStorageUsage:
    def test_counts_missions_by_status(self, conn):
        conn.execute("INSERT INTO missions (id, title, status, created_at, updated_at) VALUES ('m1', 'A', 'pending', '2026-01-01', '2026-01-01')")
        conn.execute("INSERT INTO missions (id, title, status, created_at, updated_at) VALUES ('m2', 'B', 'running', '2026-01-01', '2026-01-01')")
        conn.execute("INSERT INTO missions (id, title, status, created_at, updated_at) VALUES ('m3', 'C', 'archived', '2026-01-01', '2026-01-01')")
        conn.commit()

        usage = retention_service.get_storage_usage(conn)

        assert usage["missions"]["pending"] == 1
        assert usage["missions"]["running"] == 1
        assert usage["missions"]["archived"] == 1
        assert usage["missions_total"] == 3

    def test_counts_compressed_missions(self, conn):
        conn.execute("INSERT INTO mission_compressions (mission_id, compressed_at) VALUES ('m1', '2026-01-01')")
        conn.commit()

        usage = retention_service.get_storage_usage(conn)
        assert usage["compressed"] == 1


class TestGetPurgePreview:
    def test_lists_expired_archives(self, conn):
        conn.execute(
            "INSERT INTO missions (id, title, status, created_at, updated_at) "
            "VALUES ('m1', 'Old', 'archived', '2026-01-01', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO mission_archive (mission_id, archived_at, delete_after) "
            "VALUES ('m1', '2026-01-01', '2026-06-01')"
        )
        conn.commit()

        preview = retention_service.get_purge_preview(conn, now="2026-12-01")

        assert len(preview) == 1
        assert preview[0]["id"] == "m1"
        assert preview[0]["title"] == "Old"

    def test_excludes_non_expired(self, conn):
        conn.execute(
            "INSERT INTO missions (id, title, status, created_at, updated_at) "
            "VALUES ('m1', 'Future', 'archived', '2026-01-01', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO mission_archive (mission_id, archived_at, delete_after) "
            "VALUES ('m1', '2026-01-01', '2099-01-01')"
        )
        conn.commit()

        preview = retention_service.get_purge_preview(conn, now="2026-06-01")
        assert len(preview) == 0
