"""ATLAS module service — list/get/activate/deactivate optional modules.

A Module is an optional capability (e.g. cashflow) the operator turns on from the
System page (Decision 3b). Off by default so the base install stays lean. DDL +
seed in 0007_modules.sql; schema in atlas_core.schemas.core.Module.

Conventions follow project_service.py:
  - Pydantic-first reads (rows hydrate the frozen model).
  - All mutations go through the service layer with lock injection.
  - Toggling is idempotent (activating an active module is a no-op).
"""
from __future__ import annotations

import datetime
import sqlite3
import threading

from atlas_core.schemas.core import Module


class ModuleError(ValueError):
    """Raised for unknown module ids or invalid status transitions."""


def list_modules(conn: sqlite3.Connection) -> list[Module]:
    """Return all modules ordered by id ASC."""
    cursor = conn.execute("SELECT * FROM modules ORDER BY id ASC")
    cols = [d[0] for d in cursor.description]
    return [Module(**dict(zip(cols, row))) for row in cursor]


def get_module(conn: sqlite3.Connection, module_id: str) -> Module | None:
    """Return the Module for the given id, or None if not found."""
    cursor = conn.execute("SELECT * FROM modules WHERE id=?", (module_id,))
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    return None if row is None else Module(**dict(zip(cols, row)))


def set_active(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    module_id: str,
    active: bool,
) -> Module:
    """Activate or deactivate a module. Idempotent. Returns the updated Module."""
    status = "active" if active else "inactive"
    activated_at = datetime.datetime.now(datetime.timezone.utc).isoformat() if active else None
    with lock:
        with conn:
            existing = conn.execute(
                "SELECT id FROM modules WHERE id=?", (module_id,)
            ).fetchone()
            if existing is None:
                raise ModuleError(f"unknown module: {module_id!r}")
            conn.execute(
                "UPDATE modules SET status=?, activated_at=? WHERE id=?",
                (status, activated_at, module_id),
            )
    updated = get_module(conn, module_id)
    assert updated is not None  # just updated it
    return updated
