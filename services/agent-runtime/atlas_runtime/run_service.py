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

import dataclasses
import datetime
import logging
import sqlite3
import threading
from typing import Literal, Optional

from atlas_core.schemas.core import Run
from atlas_runtime.audit_service import emit, get_events_for_run
from atlas_runtime.run_summary_service import generate_run_summary

logger = logging.getLogger(__name__)


def start_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
    session_id: Optional[str] = None,
    agent_runtime: Literal["native", "claude_code", "codex"] = "native",
) -> Run:
    """Create a Run row, update mission to running, emit tool_call AuditEvent.

    `agent_runtime` records which AgentRuntime will execute the run (P4).

    Raises:
        ValueError: If the mission does not exist or is not in pending state.
    """
    # Pydantic-first: construct Run model before any SQL
    run = Run(mission_id=mission_id, session_id=session_id, agent_runtime=agent_runtime)
    run_row = run.model_dump()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Atomic: SELECT + INSERT + UPDATE in same lock+conn block (prevents TOCTOU)
    with lock:
        with conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id=?", (mission_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Mission {mission_id!r} not found")
            if row[0] != "pending":
                raise ValueError(
                    f"Cannot start run for mission in state {row[0]!r}"
                )
            conn.execute(
                "INSERT INTO runs"
                "(id, mission_id, session_id, status, started_at, finished_at, summary, agent_runtime) "
                "VALUES (:id, :mission_id, :session_id, :status, :started_at, :finished_at, :summary, :agent_runtime)",
                run_row,
            )
            conn.execute(
                "UPDATE missions SET status='running', updated_at=? WHERE id=?",
                (now, mission_id),
            )
    # Lock released — now safe to call emit() (which acquires lock internally)

    # Wire atlas_audit plugin for Hermes session tracking (optional — not present in all envs)
    try:
        import atlas_audit  # noqa: PLC0415
        atlas_audit.set_connection(conn)
        # Map the harness session key (run.id — NativeAtlasAgent constructs the
        # harness with session_id=run_id) AND any ATLAS surface session id, so
        # hooks fired with either key attribute to this run.
        atlas_audit.on_session_start(session_id=run.id, run_id=run.id)
        if session_id and session_id != run.id:
            atlas_audit.on_session_start(session_id=session_id, run_id=run.id)
    except ImportError:
        pass

    # Actor bridge surface-session map: the Hermes harness session key is
    # always run.id (native.py constructs it with session_id=run_id), so the
    # atlas_actor tool can't recover the real surface session id from
    # parent_agent.session_id alone. Record it here — the earliest point the
    # real id is known, and always before ensure_actor_bridge()/the harness
    # run for this run_id — so actor spawns get stamped with the caller's
    # session instead of the internal run id. Best-effort/fail-open: this
    # must never block run creation.
    try:
        from atlas_runtime import actor_bridge  # noqa: PLC0415
        actor_bridge.record_surface_session(session_id=session_id, run_id=run.id)
    except ImportError:
        pass

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
    generate_summary: bool = True,
) -> None:
    """Transition run to terminal state (succeeded or failed) and emit AuditEvent.

    Updates both runs.status and missions.status atomically.

    `summary` is now a fallback/seed, not the stored value verbatim (F8,
    Phase 3 Track A): when the run has audit_events, `runs.summary` becomes a
    structured `RunSummary` JSON payload (see `run_summary_service`), and the
    caller-supplied `summary` text is only used to fill the structured
    `outcome` field when nothing else determined one. A run with no events
    (or a generation failure) stores the plain `summary` text unchanged —
    the exact legacy behavior — so this never regresses a caller that has no
    audit trail to summarize. `generate_summary=False` skips structured
    generation entirely (tests / callers that want the old passthrough).

    Raises:
        ValueError: If the run does not exist or is not in running state.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    stored_summary = summary
    if generate_summary:
        try:
            events = get_events_for_run(conn, run_id)
        except Exception as exc:  # noqa: BLE001 — never block completion on a read error
            logger.debug("complete_run: could not load audit_events for %s: %s", run_id, exc)
            events = []
        if events:
            try:
                run_summary = generate_run_summary(events)
                if not run_summary.outcome and summary:
                    run_summary = dataclasses.replace(run_summary, outcome=summary[:2000])
                stored_summary = run_summary.to_json()
            except Exception as exc:  # noqa: BLE001 — fall back to plain text, never block
                logger.warning("complete_run: structured summary generation failed for %s: %s", run_id, exc)
                stored_summary = summary

    # Atomic dual-table update with pre-condition check inside lock (prevents TOCTOU)
    with lock:
        with conn:
            row = conn.execute(
                "SELECT status FROM runs WHERE id=?", (run_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Run {run_id!r} not found")
            if row[0] != "running":
                raise ValueError(
                    f"Cannot complete run in state {row[0]!r}"
                )
            conn.execute(
                "UPDATE runs SET status=?, finished_at=?, summary=? WHERE id=?",
                (status, now, stored_summary, run_id),
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
        data={"transition": status, "summary": stored_summary},
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
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Atomic dual-table update with pre-condition check inside lock (prevents TOCTOU)
    # Existing audit_events rows are NEVER deleted
    with lock:
        with conn:
            row = conn.execute(
                "SELECT status FROM runs WHERE id=?", (run_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Run {run_id!r} not found")
            if row[0] != "running":
                raise ValueError(
                    f"Cannot cancel run in state {row[0]!r}"
                )
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
