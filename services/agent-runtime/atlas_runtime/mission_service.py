"""ATLAS mission service — create_mission, get_mission, list_missions.

Implements the mission CRUD layer for the Phase 5 mission state machine.
References:
  - D-002: Audit-first runtime — every state transition emits an AuditEvent.
  - D-003: SQLite/WAL is the datastore — all mission state persisted there.

All mutations go through the service layer. No raw SQL from CLI or tests.
Lock injection pattern follows Phase 4 audit_service.py conventions.
"""
from __future__ import annotations

import datetime
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


def archive_mission(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
    delete_after_days: int,
) -> Mission:
    """Archive a succeeded/completed mission and stamp its retention deadline.

    Archived missions remain readable until a purge sweep. Only successful
    terminal missions can be archived; pending/running/failed/cancelled missions
    keep their explicit lifecycle status.
    """
    if delete_after_days < 1:
        raise ValueError("delete_after_days must be >= 1")

    archived_at = datetime.datetime.now(datetime.timezone.utc)
    delete_after = archived_at + datetime.timedelta(days=delete_after_days)

    with lock:
        with conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id=?", (mission_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Mission {mission_id!r} not found")
            status = str(row[0]).lower()
            if status not in {"succeeded", "completed"}:
                raise ValueError(
                    f"Cannot archive mission in state {row[0]!r}"
                )
            conn.execute(
                "UPDATE missions SET status='archived', updated_at=? WHERE id=?",
                (archived_at.isoformat(), mission_id),
            )
            conn.execute(
                "INSERT INTO mission_archive(mission_id, archived_at, delete_after) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(mission_id) DO UPDATE SET "
                "archived_at=excluded.archived_at, delete_after=excluded.delete_after",
                (mission_id, archived_at.isoformat(), delete_after.isoformat()),
            )

    mission = get_mission(conn, mission_id)
    if mission is None:
        raise ValueError(f"Mission {mission_id!r} not found after archive")
    return mission


def purge_expired_archives(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    now: Optional[str] = None,
) -> int:
    """Delete archived missions whose retention deadline has passed.

    SQLite foreign keys in the early schema do not cascade from missions to runs,
    so dependent rows are removed explicitly. The purge is scoped only to rows
    present in mission_archive and status='archived'.
    """
    now_iso = now or datetime.datetime.now(datetime.timezone.utc).isoformat()

    with lock:
        with conn:
            rows = conn.execute(
                "SELECT mission_id FROM mission_archive "
                "WHERE delete_after <= ? "
                "AND mission_id IN (SELECT id FROM missions WHERE status='archived')",
                (now_iso,),
            ).fetchall()
            mission_ids = [row[0] for row in rows]
            for mission_id in mission_ids:
                run_ids = [
                    row[0]
                    for row in conn.execute(
                        "SELECT id FROM runs WHERE mission_id=?", (mission_id,)
                    ).fetchall()
                ]
                for run_id in run_ids:
                    conn.execute("DELETE FROM tool_calls WHERE run_id=?", (run_id,))
                    conn.execute("DELETE FROM artifacts WHERE run_id=?", (run_id,))
                    conn.execute("DELETE FROM audit_events WHERE run_id=?", (run_id,))
                conn.execute("DELETE FROM runs WHERE mission_id=?", (mission_id,))
                conn.execute(
                    "DELETE FROM mission_archive WHERE mission_id=?", (mission_id,)
                )
                conn.execute("DELETE FROM missions WHERE id=?", (mission_id,))
    return len(mission_ids)
