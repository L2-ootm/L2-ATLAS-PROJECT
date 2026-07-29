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
import json
import logging
import os
import pathlib
import shutil
import sqlite3
import subprocess
import threading
from typing import Literal, Optional

from atlas_core.schemas.core import SECRET_PATTERNS, Run
import uuid

from atlas_runtime.audit_service import emit, get_events_for_run
from atlas_runtime.run_summary_service import generate_run_summary

logger = logging.getLogger(__name__)
FULL_RESULT_PREVIEW = 2000


def _redacted_preview(content: str, limit: int) -> str:
    redacted = content
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(
            lambda match: f"{match.group(1)}=[REDACTED]"
            if match.lastindex and match.lastindex >= 1
            else "[REDACTED]",
            redacted,
        )
    return redacted[:limit]


def _evidence_binary() -> str | None:
    configured = os.environ.get("ATLAS_EVIDENCE_BIN", "").strip()
    if configured:
        return configured
    installed = shutil.which("atlas-evidence")
    if installed:
        return installed
    suffix = ".exe" if os.name == "nt" else ""
    root = pathlib.Path(__file__).resolve().parents[3]
    for profile in ("release", "debug"):
        candidate = (
            root
            / "native"
            / "atlas-core-rs"
            / "target"
            / profile
            / f"atlas-evidence{suffix}"
        )
        if candidate.is_file():
            return str(candidate)
    return None


def persist_full_result_reference(
    conn: sqlite3.Connection,
    *,
    owner_kind: str,
    owner_id: str,
    content: str,
    preview_limit: int,
    run_id: str | None = None,
    team_run_id: str | None = None,
    tool_call_id: str | None = None,
    media_type: str = "text/plain",
) -> dict[str, object]:
    """Call the canonical Rust NDJSON authority or return typed unavailable.

    No Python persistence/hash fallback exists. The preview remains bounded and
    redacted even when the process/database is unavailable.
    """
    preview = _redacted_preview(content, preview_limit)
    unavailable: dict[str, object] = {
        "evidence_id": "",
        "owner_kind": owner_kind,
        "owner_id": owner_id,
        "availability": "unavailable",
        "preview": preview,
        "preview_bytes": len(preview.encode("utf-8")),
        "full_bytes": len(content.encode("utf-8")),
        "sha256": None,
        "media_type": media_type,
        "redaction_count": int(preview != content[:preview_limit]),
    }
    db_rows = conn.execute("PRAGMA database_list").fetchall()
    db_path = next((row[2] for row in db_rows if row[1] == "main" and row[2]), "")
    evidence_bin = _evidence_binary()
    if not db_path or not evidence_bin:
        logger.warning(
            "full-result evidence unavailable owner=%s:%s db_file=%s binary=%s",
            owner_kind,
            owner_id,
            bool(db_path),
            bool(evidence_bin),
        )
        return unavailable
    request = {
        "protocol": "atlas-evidence/v1",
        "db_path": db_path,
        "owner_kind": owner_kind,
        "owner_id": owner_id,
        "run_id": run_id,
        "team_run_id": team_run_id,
        "tool_call_id": tool_call_id,
        "content": content,
        "media_type": media_type,
        "preview_limit": preview_limit,
    }
    try:
        result = subprocess.run(  # noqa: S603
            [evidence_bin],
            input=json.dumps(request, ensure_ascii=False) + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        response = json.loads(result.stdout.splitlines()[-1]) if result.stdout else {}
        reference = response.get("reference")
        if result.returncode == 0 and response.get("ok") is True and isinstance(reference, dict):
            return reference
        logger.error(
            "Rust evidence persistence failed owner=%s:%s rc=%s error=%s",
            owner_kind,
            owner_id,
            result.returncode,
            response.get("error") or result.stderr[-500:],
        )
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
        logger.error(
            "Rust evidence process unavailable owner=%s:%s: %s",
            owner_kind,
            owner_id,
            exc,
        )
    return unavailable


def _result_envelope(reference: dict[str, object]) -> str:
    return json.dumps(
        {"preview": reference["preview"], "full_result": reference},
        ensure_ascii=False,
        sort_keys=True,
    )


def start_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
    session_id: Optional[str] = None,
    agent_runtime: Literal["native", "claude_code", "codex"] = "native",
    run_id: Optional[str] = None,
) -> Run:
    """Create a Run row, update mission to running, emit tool_call AuditEvent.

    `agent_runtime` records which AgentRuntime will execute the run (P4).

    Raises:
        ValueError: If the mission does not exist or is not in pending state.
    """
    # Auto-generate session_id so the agent always receives prior context.
    # Without this, native.py's ConversationHistoryRetriever gate fails
    # because session_id is NULL and no history is injected.
    if session_id is None:
        session_id = f"cli-{uuid.uuid4().hex[:12]}"
    # Pydantic-first: construct Run model before any SQL
    run_kwargs = {
        "mission_id": mission_id,
        "session_id": session_id,
        "agent_runtime": agent_runtime,
    }
    if run_id is not None:
        run_kwargs["id"] = run_id
    run = Run(**run_kwargs)
    run_row = run.model_dump()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Atomic: SELECT + INSERT + UPDATE in same lock+conn block (prevents TOCTOU)
    with lock:
        with conn:
            existing_cur = conn.execute("SELECT * FROM runs WHERE id=?", (run.id,))
            existing_row = existing_cur.fetchone()
            if existing_row is not None:
                existing = Run(
                    **dict(zip((d[0] for d in existing_cur.description), existing_row))
                )
                if run_id is None or (
                    existing.mission_id != run.mission_id
                    or existing.session_id != run.session_id
                    or existing.agent_runtime != run.agent_runtime
                ):
                    raise ValueError(f"Run id collision for {run.id!r}")
                return existing
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
    delivery_actor_id: Optional[str] = None,
    delivery_claim_token: Optional[str] = None,
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
    if (delivery_actor_id is None) != (delivery_claim_token is None):
        raise ValueError(
            "delivery_actor_id and delivery_claim_token must be provided together"
        )

    stored_summary = summary
    full_result_reference = None
    if len(summary) > FULL_RESULT_PREVIEW:
        full_result_reference = persist_full_result_reference(
            conn,
            owner_kind="run",
            owner_id=run_id,
            content=summary,
            preview_limit=FULL_RESULT_PREVIEW,
            run_id=run_id,
        )
        stored_summary = _result_envelope(full_result_reference)
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
                    outcome = (
                        str(full_result_reference["preview"])
                        if full_result_reference is not None
                        else summary
                    )
                    run_summary = dataclasses.replace(run_summary, outcome=outcome)
                stored_summary = run_summary.to_json()
                if full_result_reference is not None:
                    summary_payload = json.loads(stored_summary)
                    summary_payload["full_result"] = full_result_reference
                    stored_summary = json.dumps(
                        summary_payload, ensure_ascii=False, sort_keys=True
                    )
            except Exception as exc:  # noqa: BLE001 — fall back to plain text, never block
                logger.warning("complete_run: structured summary generation failed for %s: %s", run_id, exc)
                stored_summary = (
                    _result_envelope(full_result_reference)
                    if full_result_reference is not None
                    else summary
                )

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
            if delivery_actor_id is not None:
                consumed = conn.execute(
                    "UPDATE actor_deliveries SET status='consumed', delivered_at=?, "
                    "updated_at=? WHERE actor_id=? AND status='claimed' "
                    "AND claim_token=?",
                    (
                        now,
                        now,
                        delivery_actor_id,
                        delivery_claim_token,
                    ),
                )
                if consumed.rowcount != 1:
                    raise ValueError(
                        f"Delivery claim for actor {delivery_actor_id!r} is not owned"
                    )
    # Lock released — now safe to emit

    emit(
        conn,
        lock,
        run_id=run_id,
        event_type="tool_call",
        data={"transition": status, "summary": stored_summary},
    )
    if delivery_actor_id is not None and delivery_claim_token is not None:
        # Import lazily to keep the ordinary run-service dependency surface
        # unchanged. The terminal run/mission write and delivery consume above
        # are already durable in one transaction; this audit is fail-open.
        from atlas_runtime import actor_service  # noqa: PLC0415

        actor_service._emit_delivery_transition(
            conn,
            lock,
            actor_id=delivery_actor_id,
            transition="consumed",
            followup_run_id=run_id,
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
