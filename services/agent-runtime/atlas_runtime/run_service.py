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
import uuid
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
    """Create a Run row, update mission to running, emit task.started AuditEvent.

    Raises:
        ValueError: If the mission does not exist or is not in pending state.
        NotImplementedError: Stub — implement in Wave 1.
    """
    raise NotImplementedError("not implemented")


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
        NotImplementedError: Stub — implement in Wave 1.
    """
    raise NotImplementedError("not implemented")


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
        NotImplementedError: Stub — implement in Wave 1.
    """
    raise NotImplementedError("not implemented")


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
        NotImplementedError: Stub — implement in Wave 1.
    """
    raise NotImplementedError("not implemented")
