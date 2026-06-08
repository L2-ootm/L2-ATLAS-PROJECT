"""ATLAS run service — start_run, complete_run, fail_run, cancel_run.

Implements the run lifecycle state machine for Phase 5.
References:
  - D-001: Hermes runtime used directly — mission execution goes through
    the enhanced Hermes runtime loop.
  - D-002: Audit-first runtime — every state transition emits an AuditEvent
    via audit_service.emit().

Valid run/mission status transitions:
  pending   -> running    (start_run)
  running   -> succeeded  (complete_run, status="succeeded")
  running   -> failed     (complete_run, status="failed" / fail_run)
  running   -> cancelled  (cancel_run)
  Terminal states: succeeded, failed, cancelled — no transitions out.

Lock injection pattern follows Phase 4 audit_service.py conventions.
Emit-after-lock pattern prevents deadlock (emit() re-acquires lock internally).
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
from typing import Literal, Optional

from atlas_core.schemas.core import Run
from atlas_runtime.audit_service import emit


def start_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
    session_id: Optional[str] = None,
) -> Run:
    """Create a Run row, update mission to running, emit tool_call AuditEvent.

    Raises:
        ValueError: If the mission does not exist or is not in pending state.
    """
    # Validate mission exists and is in pending state
    row = conn.execute(
        "SELECT status FROM missions WHERE id=?", (mission_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Mission {mission_id!r} not found")
    if row[0] != "pending":
        raise ValueError(
            f"Cannot start run for mission in state {row[0]!r}"
        )

    # Pydantic-first: construct Run model before any SQL
    run = Run(mission_id=mission_id, session_id=session_id)
    run_row = run.model_dump()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Atomic: INSERT run + UPDATE mission in same transaction
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO runs"
                "(id, mission_id, session_id, status, started_at, finished_at, summary) "
                "VALUES (:id, :mission_id, :session_id, :status, :started_at, :finished_at, :summary)",
                run_row,
            )
            conn.execute(
                "UPDATE missions SET status='running', updated_at=? WHERE id=?",
                (now, mission_id),
            )
    # Lock released — now safe to call emit() (which acquires lock internally)

    # Wire atlas_audit plugin for Hermes session tracking
    import atlas_audit
    atlas_audit.set_connection(conn)
    atlas_audit.on_session_start(session_id=session_id or run.id, run_id=run.id)

    # Emit transition audit event
    emit(
        conn,
        lock,
        run_id=run.id,
        event_type="tool_call",
        session_id=session_id,
        data={"transition": "started", "mission_id": mission_id},
    )

    return run


def complete_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: str,
    mission_id: str,
    status: Literal["succeeded", "failed"],
    summary: str = "",
) -> None:
    """Transition run to terminal state (succeeded or failed) and emit AuditEvent.

    Updates both runs.status and missions.status atomically.

    Raises:
        ValueError: If the run does not exist or is not in running state.
    """
    row = conn.execute(
        "SELECT status FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Run {run_id!r} not found")
    if row[0] != "running":
        raise ValueError(
            f"Cannot complete run in state {row[0]!r}"
        )

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Atomic dual-table update
    with lock:
        with conn:
            conn.execute(
                "UPDATE runs SET status=?, finished_at=?, summary=? WHERE id=?",
                (status, now, summary, run_id),
            )
            conn.execute(
                "UPDATE missions SET status=?, updated_at=? WHERE id=?",
                (status, now, mission_id),
            )
    # Lock released — now safe to emit

    emit(
        conn,
        lock,
        run_id=run_id,
        event_type="tool_call",
        data={"transition": status, "summary": summary},
    )


def fail_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: str,
    mission_id: str,
    summary: str = "",
) -> None:
    """Transition run to failed state — convenience wrapper around complete_run.

    Raises:
        ValueError: If the run does not exist or is not in running state.
    """
    complete_run(conn, lock, run_id=run_id, mission_id=mission_id, status="failed", summary=summary)


def cancel_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: str,
    mission_id: str,
) -> None:
    """Transition run to cancelled state; preserve existing audit trail.

    Raises:
        ValueError: If the run does not exist or is already in a terminal state.
    """
    row = conn.execute(
        "SELECT status FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Run {run_id!r} not found")
    if row[0] != "running":
        raise ValueError(
            f"Cannot cancel run in state {row[0]!r}"
        )

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Atomic dual-table update — existing audit_events rows are NEVER deleted
    with lock:
        with conn:
            conn.execute(
                "UPDATE runs SET status='cancelled', finished_at=? WHERE id=?",
                (now, run_id),
            )
            conn.execute(
                "UPDATE missions SET status='cancelled', updated_at=? WHERE id=?",
                (now, mission_id),
            )
    # Lock released — now safe to emit

    emit(
        conn,
        lock,
        run_id=run_id,
        event_type="tool_call",
        data={"transition": "cancelled"},
    )
