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

OPERATOR_RUN_ID = "operator"


def ensure_operator_run(conn: sqlite3.Connection, lock: threading.Lock) -> str:
    """Idempotently create the synthetic operator mission/run pair; return its id.

    Operator-initiated writes (wiki edits, gated Discord actions, …) carry
    run_id="operator", but audit_events.run_id is NOT NULL REFERENCES runs(id).
    On a fresh database no such run exists, so the write would fail the FK check.
    Bootstrap the pseudo-run lazily rather than relaxing the schema — the audit
    chain stays referentially intact. Mirrors the wiki-runtime precedent.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO missions"
                    "(id, title, intent, status, project, origin, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        OPERATOR_RUN_ID,
                        "Operator console",
                        "Synthetic mission for operator-initiated writes outside agent runs",
                        "archived",
                        "",
                        "system",
                        now,
                        now,
                    ),
                )
            except sqlite3.OperationalError as exc:
                # Pre-0024 DB pending migration: write without origin rather than
                # failing the operator action (0024 backfills it later).
                if "origin" not in str(exc):
                    raise
                conn.execute(
                    "INSERT OR IGNORE INTO missions"
                    "(id, title, intent, status, project, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        OPERATOR_RUN_ID,
                        "Operator console",
                        "Synthetic mission for operator-initiated writes outside agent runs",
                        "archived",
                        "",
                        now,
                        now,
                    ),
                )
            conn.execute(
                "INSERT OR IGNORE INTO runs(id, mission_id, session_id, status, started_at, summary) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    OPERATOR_RUN_ID,
                    OPERATOR_RUN_ID,
                    OPERATOR_RUN_ID,
                    "completed",
                    now,
                    "Synthetic run recording operator-initiated writes",
                ),
            )
    return OPERATOR_RUN_ID


def create_mission(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    title: str,
    intent: str = "",
    project: str = "",
    project_id: Optional[str] = None,
    origin: str = "operator",
) -> Mission:
    """Insert a new Mission row and return the constructed Mission.

    Pydantic-first write guard: constructs Mission model before any SQL.
    ValidationError propagates before any DB write if inputs are invalid.

    If project_id is given it must reference an existing project (folder-backed
    working directory); a ValueError is raised before any write otherwise.

    `origin` records authorship: 'operator' for deliberate missions, 'chat' for
    per-prompt wrappers, 'system' for machine-created internals (0024).
    """
    # Pydantic-first: construct and validate before any SQL
    mission = Mission(
        title=title, intent=intent, project=project, project_id=project_id, origin=origin
    )
    row = mission.model_dump()

    with lock:
        with conn:
            if mission.project_id is not None:
                exists = conn.execute(
                    "SELECT 1 FROM projects WHERE id=?", (mission.project_id,)
                ).fetchone()
                if exists is None:
                    raise ValueError(f"unknown project_id: {mission.project_id}")
            try:
                conn.execute(
                    "INSERT INTO missions"
                    "(id, title, intent, status, project, project_id, origin, created_at, updated_at) "
                    "VALUES (:id, :title, :intent, :status, :project, :project_id, :origin, "
                    ":created_at, :updated_at)",
                    row,
                )
            except sqlite3.OperationalError as exc:
                # Pre-0024 DB pending migration: insert without origin so the
                # mission is not lost; the 0024 backfill classifies it later.
                if "origin" not in str(exc):
                    raise
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


def retry_mission(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
) -> Mission:
    """Reopen a failed/cancelled mission so it can be run again, in place.

    A mission whose last run failed (or was cancelled) is otherwise terminal:
    ``start_run`` requires a ``pending`` mission. This reopens it by cycling the
    status ``failed|cancelled -> pending`` so the normal run path applies again.

    Prior ``runs`` rows are left untouched — they remain attached as attempt
    history (the compounding-loop provenance of earlier failures). No audit is
    emitted here; the subsequent ``start_run`` records the ``started`` transition.
    Mirrors ``archive_mission``'s atomic guarded-UPDATE shape.
    """
    with lock:
        with conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id=?", (mission_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Mission {mission_id!r} not found")
            status = str(row[0]).lower()
            if status not in {"failed", "cancelled"}:
                raise ValueError(
                    f"Cannot retry mission in state {row[0]!r} "
                    "(only failed or cancelled missions can be retried)"
                )
            updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute(
                "UPDATE missions SET status='pending', updated_at=? WHERE id=?",
                (updated_at, mission_id),
            )

    mission = get_mission(conn, mission_id)
    if mission is None:
        raise ValueError(f"Mission {mission_id!r} not found after retry")
    return mission


def purge_expired_archives(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    now: Optional[str] = None,
) -> int:
    """Delete archived missions whose retention deadline has passed.

    SQLite foreign keys in the early schema do not cascade from missions to runs,
    so dependent raw evidence is removed explicitly and compact knowledge records
    are detached from the deleted run. The purge is scoped only to rows present
    in mission_archive and status='archived'.
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
                    # Preserve compiled knowledge while removing soft references
                    # to history that is about to disappear.
                    conn.execute("UPDATE observations SET run_id=NULL WHERE run_id=?", (run_id,))
                    conn.execute(
                        "UPDATE sources SET ingested_by_run_id=NULL WHERE ingested_by_run_id=?",
                        (run_id,),
                    )
                    conn.execute(
                        "UPDATE memory_provenance SET run_id=NULL, audit_event_id=NULL "
                        "WHERE run_id=? OR audit_event_id IN "
                        "(SELECT id FROM audit_events WHERE run_id=?)",
                        (run_id, run_id),
                    )
                    conn.execute("DELETE FROM tool_approvals WHERE run_id=?", (run_id,))
                    conn.execute("DELETE FROM discord_approvals WHERE run_id=?", (run_id,))
                    conn.execute("DELETE FROM tool_calls WHERE run_id=?", (run_id,))
                    conn.execute("DELETE FROM artifacts WHERE run_id=?", (run_id,))
                    conn.execute("DELETE FROM run_judgements WHERE run_id=?", (run_id,))
                    # Migration 0020 permits retention deletion while retaining
                    # the no-UPDATE immutability guarantee for live snapshots.
                    conn.execute("DELETE FROM agent_contract_snapshots WHERE run_id=?", (run_id,))
                    conn.execute("DELETE FROM audit_events WHERE run_id=?", (run_id,))

                    session_row = conn.execute(
                        "SELECT session_id FROM runs WHERE id=?", (run_id,)
                    ).fetchone()
                    session_id = session_row[0] if session_row else None
                    if session_id:
                        has_other_runs = conn.execute(
                            "SELECT 1 FROM runs WHERE session_id=? AND id<>? LIMIT 1",
                            (session_id, run_id),
                        ).fetchone()
                        if has_other_runs is None:
                            conn.execute(
                                "DELETE FROM approval_channels WHERE surface_session_id=?",
                                (session_id,),
                            )
                            conn.execute(
                                "DELETE FROM session_allow_rules WHERE surface_session_id=?",
                                (session_id,),
                            )
                            conn.execute("DELETE FROM surface_sessions WHERE id=?", (session_id,))
                conn.execute("DELETE FROM runs WHERE mission_id=?", (mission_id,))
                conn.execute("DELETE FROM mission_loops WHERE mission_id=?", (mission_id,))
                conn.execute(
                    "DELETE FROM mission_archive WHERE mission_id=?", (mission_id,)
                )
                conn.execute("DELETE FROM missions WHERE id=?", (mission_id,))
    return len(mission_ids)
