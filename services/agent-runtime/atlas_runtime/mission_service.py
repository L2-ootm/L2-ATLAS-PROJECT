"""ATLAS mission service — create_mission, get_mission, list_missions.

Implements the mission CRUD layer for the Phase 5 mission state machine.
References:
  - D-002: Audit-first runtime — every state transition emits an AuditEvent.
  - D-003: SQLite/WAL is the datastore — all mission state persisted there.

All mutations go through the service layer. No raw SQL from CLI or tests.
Lock injection pattern follows Phase 4 audit_service.py conventions.
"""
from __future__ import annotations

import sqlite3
import threading
from typing import Optional

from atlas_core.schemas.core import Mission


def create_mission(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    title: str,
    intent: str = "",
    project: str = "",
    project_id: Optional[str] = None,
) -> Mission:
    """Insert a new Mission row and return the constructed Mission.

    Pydantic-first write guard: constructs Mission model before any SQL.
    ValidationError propagates before any DB write if inputs are invalid.

    If project_id is given it must reference an existing project (folder-backed
    working directory); a ValueError is raised before any write otherwise.
    """
    # Pydantic-first: construct and validate before any SQL
    mission = Mission(title=title, intent=intent, project=project, project_id=project_id)
    row = mission.model_dump()

    with lock:
        with conn:
            if mission.project_id is not None:
                exists = conn.execute(
                    "SELECT 1 FROM projects WHERE id=?", (mission.project_id,)
                ).fetchone()
                if exists is None:
                    raise ValueError(f"unknown project_id: {mission.project_id}")
            conn.execute(
                "INSERT INTO missions"
                "(id, title, intent, status, project, project_id, created_at, updated_at) "
                "VALUES (:id, :title, :intent, :status, :project, :project_id, "
                ":created_at, :updated_at)",
                row,
            )

    return mission


def get_mission(
    conn: sqlite3.Connection,
    mission_id: str,
) -> Optional[Mission]:
    """Return the Mission for the given id, or None if not found."""
    cursor = conn.execute(
        "SELECT * FROM missions WHERE id=?",
        (mission_id,),
    )
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    if row is None:
        return None
    return Mission(**dict(zip(cols, row)))


def list_missions(
    conn: sqlite3.Connection,
) -> list[Mission]:
    """Return all Mission rows ordered by created_at ASC."""
    cursor = conn.execute(
        "SELECT * FROM missions ORDER BY created_at ASC",
    )
    cols = [d[0] for d in cursor.description]
    return [Mission(**dict(zip(cols, row))) for row in cursor]
