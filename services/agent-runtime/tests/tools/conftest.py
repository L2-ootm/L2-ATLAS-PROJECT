"""Tool-layer test fixtures (Phase 10.0.4).

Canonical home for the temp-DB tool fixture per the phase plan. The tool-service
tests in ``tests/`` reuse the top-level ``db``/``lock`` fixtures (in-memory, all
migrations applied) exactly as the Phase C ``test_discord_service`` tests do; this
module provides a file-backed ``tool_db`` built via ``db.connect`` +
``db.apply_migrations`` for any test that needs the real migration runner (e.g.
asserting ``0013_tool_approvals`` applied through ``schema_migrations``).

NEVER use the live ``atlas`` CLI connection here — it hardcodes ``~/.atlas/atlas.db``
and ignores ATLAS_HOME (project-memory gotcha ``cli-db-path-not-atlas-home``).
"""
from __future__ import annotations

import threading

import pytest

from atlas_runtime import db


@pytest.fixture(name="tool_db")
def tool_db_fixture(tmp_path):
    """A file-backed temp DB with every migration applied via the real runner.

    Returns ``(conn, lock)``. Uses ``db.connect`` + ``db.apply_migrations`` so the
    fixture exercises the same bootstrap path a fresh machine uses, including
    ``0013_tool_approvals.sql`` once it exists.
    """
    conn = db.connect(tmp_path / "tool-test.db")
    db.apply_migrations(conn)
    lock = threading.Lock()
    yield conn, lock
    conn.close()
