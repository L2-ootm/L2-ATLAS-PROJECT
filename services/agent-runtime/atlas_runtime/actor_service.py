"""Durable actor supervisor — persistent subagent state, inbox, orphan sweep.

Implements the state model from docs/plans/2026-07-16-subagent-orchestration-design.md:

    queued -> running -> completed | failed | cancelled | orphaned

Every mutation is queryable and auditable. Spawn is idempotent (keyed by an
idempotency key), terminal transitions are monotonic compare-and-set UPDATEs
(the 0022 trigger backstops any path that forgets), and completion delivery is
a separate durable inbox record with a short claim lease so a parent receives
each detached result exactly once even across crashes between claim and
acknowledge.

This module owns the `actors` and `actor_deliveries` tables and is DB-pure:
process launch/kill lives in actor_worker.py; the Hermes-facing tool lives in
actor_bridge.py. Lifecycle changes are projected onto the audit bus as
`subagent_run` events with the same payload shape NativeAtlasAgent's live
progress projection uses, so the existing WebUI orchestration rail renders
durable actors with no UI changes.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from atlas_runtime import change_reconciliation
from atlas_runtime.audit_service import emit

logger = logging.getLogger(__name__)

MAX_DEPTH = 3
RESULT_PREVIEW_CAP = 16 * 1024  # bytes of result kept on the actor row
ERROR_CAP = 2 * 1024
GOAL_CAP = 4000
ACTIVE_STATUSES = ("queued", "running")
TERMINAL_STATUSES = ("completed", "failed", "cancelled", "orphaned")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    return {d[0]: row[i] for i, d in enumerate(cursor.description)}


def _fetch_actor(conn: sqlite3.Connection, actor_id: str) -> Optional[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM actors WHERE id=?", (actor_id,))
    row = cur.fetchone()
    return _row_to_dict(cur, row) if row else None


def default_idempotency_key(
    parent_run_id: str, goal: str, mode: str, model: Optional[str], role: str
) -> str:
    """Deterministic spawn key: retried tool delivery of the same request maps
    to the same actor. Callers wanting intentional duplicates pass their own key."""
    basis = "|".join((parent_run_id, goal, mode, model or "", role))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _emit_lifecycle(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor: dict[str, Any],
    phase: str,
    **extra: Any,
) -> None:
    """Project one actor lifecycle change as a subagent_run audit event.

    Payload shape matches NativeAtlasAgent._emit_subagent_progress so surface
    projections and the WebUI rail fold durable actors identically (last-write-
    wins by subagent_id). Fail-open: auditing never blocks a transition.
    """
    payload = {
        "runtime": "native",
        "surface_kind": "task",
        "orchestration": "subagent",
        "actor": True,
        "phase": phase,
        "subagent_id": actor["id"],
        "parent_id": actor.get("parent_actor_id") or actor["parent_run_id"],
        "depth": int(actor.get("depth") or 1),
        "goal": str(actor.get("goal") or "")[:1000],
        "model": str(actor.get("model") or ""),
        "tool": "",
        "tool_count": 0,
        "background": actor.get("mode") == "detached",
        "mode": actor.get("mode"),
        "role": actor.get("role"),
    }
    payload.update(extra)
    try:
        emit(
            conn, lock,
            run_id=actor["parent_run_id"],
            event_type="subagent_run",
            task_id=actor["id"],
            session_id=actor.get("session_id"),
            data=payload,
        )
    except Exception as exc:  # noqa: BLE001 — fail-open audit
        logger.warning("actor lifecycle audit emit failed: %s", exc)


# ---------------------------------------------------------------------------
# Spawn / transitions
# ---------------------------------------------------------------------------


def spawn_actor(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    parent_run_id: str,
    goal: str,
    mode: str = "joined",
    role: str = "worker",
    model: Optional[str] = None,
    parent_actor_id: Optional[str] = None,
    session_id: Optional[str] = None,
    workspace_root: Optional[str] = None,
    depth: int = 1,
    idempotency_key: Optional[str] = None,
    wakeup_parent: bool = False,
) -> tuple[dict[str, Any], bool]:
    """Idempotently insert a queued actor. Returns (actor, created).

    Duplicate delivery of the same spawn mutation (same idempotency key)
    returns the existing actor instead of starting another child.

    `wakeup_parent` asks the worker to start a follow-up run in the parent's
    session when this actor finishes, instead of leaving the completion in the
    inbox until the parent happens to take another turn. Off by default: it
    starts agent execution nobody typed a prompt for.
    """
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("actor goal must be non-empty")
    if mode not in ("joined", "detached"):
        raise ValueError(f"invalid actor mode: {mode!r}")
    if depth > MAX_DEPTH:
        raise ValueError(f"actor depth {depth} exceeds MAX_DEPTH={MAX_DEPTH}")
    goal = goal[:GOAL_CAP]
    key = idempotency_key or default_idempotency_key(
        parent_run_id, goal, mode, model, role
    )
    now = _now()
    actor_id = f"actor-{uuid.uuid4()}"
    with lock:
        with conn:
            cur = conn.execute("SELECT * FROM actors WHERE idempotency_key=?", (key,))
            row = cur.fetchone()
            if row is not None:
                return _row_to_dict(cur, row), False
            conn.execute(
                "INSERT INTO actors(id, parent_run_id, parent_actor_id, session_id,"
                " idempotency_key, role, goal, model, mode, status, workspace_root,"
                " depth, wakeup_parent, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,'queued',?,?,?,?,?)",
                (
                    actor_id, parent_run_id, parent_actor_id, session_id,
                    key, role, goal, model, mode, workspace_root,
                    depth, 1 if wakeup_parent else 0, now, now,
                ),
            )
    actor = _fetch_actor(conn, actor_id)
    assert actor is not None
    _emit_lifecycle(conn, lock, actor, "queued")
    return actor, True


def mark_running(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    pid: Optional[int] = None,
    owner_token: Optional[str] = None,
) -> bool:
    """CAS queued -> running. Returns False when the actor is not queued."""
    now = _now()
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE actors SET status='running', pid=?, owner_token=?,"
                " heartbeat_at=?, started_at=?, updated_at=?"
                " WHERE id=? AND status='queued'",
                (pid, owner_token, now, now, now, actor_id),
            )
            changed = cur.rowcount == 1
    if changed:
        actor = _fetch_actor(conn, actor_id)
        if actor:
            _emit_lifecycle(conn, lock, actor, "running")
    return changed


def heartbeat_actor(
    conn: sqlite3.Connection, lock: threading.Lock, actor_id: str
) -> bool:
    """Refresh the worker heartbeat; only running actors accept one."""
    now = _now()
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE actors SET heartbeat_at=?, updated_at=?"
                " WHERE id=? AND status='running'",
                (now, now, actor_id),
            )
            return cur.rowcount == 1


def _finish(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    status: str,
    result_preview: str = "",
    error: str = "",
    child_run_id: Optional[str] = None,
) -> bool:
    """Monotonic terminal transition + atomic pending delivery insert."""
    now = _now()
    with lock:
        with conn:
            cur = conn.execute("SELECT * FROM actors WHERE id=?", (actor_id,))
            row = cur.fetchone()
            if row is None:
                return False
            actor = _row_to_dict(cur, row)
            if actor["status"] in TERMINAL_STATUSES:
                return False  # repeated completion/cancellation is a no-op
            conn.execute(
                "UPDATE actors SET status=?, result_preview=?, error=?,"
                " child_run_id=COALESCE(?, child_run_id), finished_at=?, updated_at=?"
                " WHERE id=? AND status IN ('queued','running')",
                (
                    status,
                    result_preview[:RESULT_PREVIEW_CAP],
                    error[:ERROR_CAP],
                    child_run_id,
                    now,
                    now,
                    actor_id,
                ),
            )
            payload = json.dumps(
                {
                    "actor_id": actor_id,
                    "status": status,
                    "goal": actor["goal"][:500],
                    "mode": actor["mode"],
                    "result_preview": result_preview[:RESULT_PREVIEW_CAP],
                    "error": error[:ERROR_CAP],
                    "child_run_id": child_run_id or actor.get("child_run_id"),
                    "finished_at": now,
                }
            )
            conn.execute(
                "INSERT OR IGNORE INTO actor_deliveries"
                "(actor_id, parent_run_id, session_id, status, payload,"
                " created_at, updated_at)"
                " VALUES (?,?,?,'pending',?,?,?)",
                (
                    actor_id,
                    actor["parent_run_id"],
                    actor.get("session_id"),
                    payload,
                    now,
                    now,
                ),
            )
    refreshed = _fetch_actor(conn, actor_id)
    if refreshed:
        phase = "completed" if status == "completed" else "failed"
        _emit_lifecycle(
            conn, lock, refreshed, phase,
            status="succeeded" if status == "completed" else status,
        )
    return True


def complete_actor(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    result_preview: str = "",
    child_run_id: Optional[str] = None,
) -> bool:
    actor = _fetch_actor(conn, actor_id)
    if actor is None or actor["status"] not in ("queued", "running"):
        return False
    effective_run_id = child_run_id or actor.get("child_run_id") or actor["parent_run_id"]
    mutation_ids = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT ecs.id FROM evidence_change_sets ecs"
            " JOIN evidence_file_changes efc ON efc.change_set_id=ecs.id"
            " WHERE ecs.actor_id=? ORDER BY ecs.id",
            (actor_id,),
        ).fetchall()
    ]
    permission = None
    if actor.get("session_id"):
        row = conn.execute(
            "SELECT permission_mode FROM surface_sessions WHERE id=?",
            (actor["session_id"],),
        ).fetchone()
        permission = row[0] if row else None
    if permission == "read_only" and mutation_ids:
        error = "read-only mutation incident: actor produced file changes"
        emit(
            conn,
            lock,
            run_id=effective_run_id,
            event_type="failure",
            task_id=actor_id,
            session_id=actor.get("session_id"),
            policy_result="denied",
            data={
                "status": "failed",
                "reason": error,
                "change_set_ids": mutation_ids,
            },
        )
        return _finish(
            conn,
            lock,
            actor_id,
            status="failed",
            error=error,
            child_run_id=child_run_id,
        )

    descendant_ids = [
        row[0]
        for row in conn.execute(
            "WITH RECURSIVE descendants(id) AS ("
            " SELECT id FROM actors WHERE parent_actor_id=?"
            " UNION ALL"
            " SELECT actor.id FROM actors actor"
            " JOIN descendants parent ON actor.parent_actor_id=parent.id"
            ")"
            " SELECT DISTINCT ecs.id FROM evidence_change_sets ecs"
            " JOIN descendants ON descendants.id=ecs.actor_id"
            " ORDER BY ecs.id",
            (actor_id,),
        ).fetchall()
    ]
    if descendant_ids:
        db_row = conn.execute("PRAGMA database_list").fetchone()
        db_path = Path(db_row[2]) if db_row and db_row[2] else None
        receipt = change_reconciliation.persist_reference_aggregation(
            db_path=db_path,
            provenance={
                "run_id": effective_run_id,
                "session_id": actor.get("session_id"),
                "actor_id": actor_id,
                "parent_actor_id": actor.get("parent_actor_id"),
            },
            child_change_set_ids=descendant_ids,
        )
        if receipt.status != "captured":
            logger.error(
                "actor %s evidence aggregation unavailable: %s",
                actor_id,
                receipt.error_code,
            )
    return _finish(
        conn, lock, actor_id,
        status="completed", result_preview=result_preview, child_run_id=child_run_id,
    )


def fail_actor(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    error: str,
    child_run_id: Optional[str] = None,
) -> bool:
    return _finish(
        conn, lock, actor_id,
        status="failed", error=error, child_run_id=child_run_id,
    )


def cancel_actor(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
) -> list[dict[str, Any]]:
    """Idempotently cancel one actor and all its live descendants.

    Returns the rows that were actually transitioned (with their pids so a
    process-owning caller can terminate workers). Repeat calls return [].
    Cancelled actors' undelivered completions are consumed so a cancelled
    child never injects a completion notice later.
    """
    cancelled: list[dict[str, Any]] = []
    to_visit = [actor_id]
    now = _now()
    with lock:
        with conn:
            while to_visit:
                current = to_visit.pop()
                cur = conn.execute("SELECT * FROM actors WHERE id=?", (current,))
                row = cur.fetchone()
                if row is None:
                    continue
                actor = _row_to_dict(cur, row)
                children = conn.execute(
                    "SELECT id FROM actors WHERE parent_actor_id=?", (current,)
                ).fetchall()
                to_visit.extend(c[0] for c in children)
                if actor["status"] in TERMINAL_STATUSES:
                    continue
                conn.execute(
                    "UPDATE actors SET status='cancelled', finished_at=?, updated_at=?"
                    " WHERE id=? AND status IN ('queued','running')",
                    (now, now, current),
                )
                conn.execute(
                    "UPDATE actor_deliveries SET status='consumed', updated_at=?"
                    " WHERE actor_id=? AND status IN ('pending','claimed')",
                    (now, current),
                )
                cancelled.append(actor)
    for actor in cancelled:
        refreshed = _fetch_actor(conn, actor["id"])
        if refreshed:
            _emit_lifecycle(conn, lock, refreshed, "failed", status="cancelled")
    return cancelled


# ---------------------------------------------------------------------------
# Reads / wait
# ---------------------------------------------------------------------------


def get_actor(
    conn: sqlite3.Connection, actor_id: str
) -> Optional[dict[str, Any]]:
    return _fetch_actor(conn, actor_id)


def list_actors(
    conn: sqlite3.Connection,
    *,
    parent_run_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses, params = [], []
    if parent_run_id:
        clauses.append("parent_run_id=?")
        params.append(parent_run_id)
    if session_id:
        clauses.append("session_id=?")
        params.append(session_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    cur = conn.execute(
        f"SELECT * FROM actors {where} ORDER BY created_at DESC LIMIT ?",  # noqa: S608
        (*params, max(1, min(limit, 100))),
    )
    return [_row_to_dict(cur, row) for row in cur.fetchall()]


def load_actor_history(
    conn: sqlite3.Connection,
    *,
    session_id: Optional[str] = None,
    parent_run_id: Optional[str] = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Restore a stable actor topology from SQLite after process restart.

    At least one durable scope is required so callers cannot accidentally turn
    actor history into an unbounded cross-session disclosure. Rows are ordered
    oldest-first, which guarantees parents precede descendants and lets a UI
    hydrate the persisted topology before applying last-write-wins live events.

    This read deliberately preserves terminal and ``orphaned`` statuses exactly
    as stored. Startup reconciliation remains owned by
    :func:`reconcile_orphan_actors`; history loading never invents a new state.
    """
    if not session_id and not parent_run_id:
        raise ValueError("actor history requires session_id or parent_run_id")
    clauses: list[str] = []
    params: list[Any] = []
    if session_id:
        clauses.append("session_id=?")
        params.append(session_id)
    if parent_run_id:
        clauses.append("parent_run_id=?")
        params.append(parent_run_id)
    where = " AND ".join(clauses)
    cur = conn.execute(
        f"SELECT * FROM actors WHERE {where}"  # noqa: S608
        " ORDER BY created_at ASC, id ASC LIMIT ?",
        (*params, max(1, min(int(limit), 500))),
    )
    return [_row_to_dict(cur, row) for row in cur.fetchall()]


def wait_for_actor(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    timeout_seconds: float = 120.0,
    poll_interval: float = 0.25,
    consume: bool = True,
    on_tick: Optional[Any] = None,
) -> Optional[dict[str, Any]]:
    """Join an existing actor with a bounded timeout.

    Rechecks immediately after the initial read to close the completion race,
    then polls. On terminal state, consumes the pending delivery (when
    `consume`) so a later pre-model inbox claim cannot inject a duplicate.
    Returns the actor row (with `delivery` payload when one was consumed) or
    None when the timeout elapsed with the actor still active.

    `on_tick(actor, waited_seconds)` is called once per poll while the actor is
    still active. This loop occupies the harness thread for as long as the join
    lasts and emitted nothing while it did, so a two-minute join looked
    indistinguishable from a hung agent: no stream output, no activity touch,
    and gateway/client inactivity timeouts firing on a run that was working
    fine. The callback is where liveness is published (see actor_bridge); it is
    called inside the loop but never holds the lock, and an exception in it is
    swallowed — a failed heartbeat must not abort a healthy join.
    """
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    started = time.monotonic()
    while True:
        # Serialize the poll read on the shared write lock: the actor may be
        # completed concurrently on the same sqlite3 connection from a worker
        # thread, and two interleaved conn.execute calls on one connection
        # raise `InterfaceError: bad parameter or other API misuse`.
        with lock:
            actor = _fetch_actor(conn, actor_id)
        if actor is None:
            return None
        if actor["status"] in TERMINAL_STATUSES:
            if consume:
                actor["delivery"] = consume_delivery(conn, lock, actor_id)
            return actor
        if time.monotonic() >= deadline:
            return None
        if on_tick is not None:
            try:
                on_tick(actor, time.monotonic() - started)
            except Exception as exc:  # noqa: BLE001 — liveness is not the join
                logger.debug("actor wait tick failed: %s", exc)
        time.sleep(poll_interval)


def attach_child_run(
    conn: sqlite3.Connection, lock: threading.Lock, actor_id: str, child_run_id: str
) -> bool:
    """Record the child run id while the actor is still running.

    `_finish` also writes child_run_id, but only at terminal transition — which
    meant that for the entire time an actor was actually working, nothing linked
    it to the run carrying its audit trail, so there was no way to tail a live
    actor's activity. Written here at run creation instead. Only running actors
    accept it (the 0022 trigger makes terminal rows immutable).
    """
    now = _now()
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE actors SET child_run_id=?, updated_at=?"
                " WHERE id=? AND status IN ('queued','running')",
                (child_run_id, now, actor_id),
            )
            return cur.rowcount == 1


# ---------------------------------------------------------------------------
# Steering (mid-flight correction) and log tailing
# ---------------------------------------------------------------------------


def enqueue_steering(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    message: str,
    origin: str = "agent",
) -> dict[str, Any]:
    """Queue a steering message for a still-active actor.

    Delivery is pull-based: the child drains its own queue at its next model
    call boundary (`actor_bridge.on_pre_llm_call`), so this needs no live
    process handle and a message survives a worker restart. Raises ValueError
    for an unknown or already-terminal actor — steering something that has
    finished is a caller mistake worth reporting, not a silent no-op.
    """
    message = (message or "").strip()
    if not message:
        raise ValueError("steering message must be non-empty")
    message = message[:GOAL_CAP]
    now = _now()
    with lock:
        with conn:
            actor = _fetch_actor(conn, actor_id)
            if actor is None:
                raise ValueError(f"unknown actor: {actor_id}")
            if actor["status"] in TERMINAL_STATUSES:
                raise ValueError(
                    f"actor {actor_id} is already {actor['status']}; nothing to steer"
                )
            seq = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM actor_steering WHERE actor_id=?",
                (actor_id,),
            ).fetchone()[0]
            steering_id = f"steer-{uuid.uuid4()}"
            conn.execute(
                "INSERT INTO actor_steering(id, actor_id, seq, message, origin,"
                " status, created_at) VALUES (?,?,?,?,?,'pending',?)",
                (steering_id, actor_id, seq, message, origin, now),
            )
    return {"id": steering_id, "actor_id": actor_id, "seq": seq, "message": message}


def drain_steering(
    conn: sqlite3.Connection, lock: threading.Lock, actor_id: str, *, limit: int = 10
) -> list[dict[str, Any]]:
    """Claim and mark delivered every pending steering message for one actor.

    At-most-once by design: a message is latched delivered in the same
    transaction that reads it, so a crash after the drain but before the model
    sees it loses that steer rather than replaying it into a later turn where
    it would arrive without its context. Rows are kept (not deleted) so what
    was injected into a child stays auditable.
    """
    now = _now()
    drained: list[dict[str, Any]] = []
    with lock:
        with conn:
            rows = conn.execute(
                "SELECT id, seq, message, origin FROM actor_steering"
                " WHERE actor_id=? AND status='pending' ORDER BY seq ASC LIMIT ?",
                (actor_id, max(1, limit)),
            ).fetchall()
            for steering_id, seq, message, origin in rows:
                cur = conn.execute(
                    "UPDATE actor_steering SET status='delivered', delivered_at=?"
                    " WHERE id=? AND status='pending'",
                    (now, steering_id),
                )
                if cur.rowcount == 1:
                    drained.append(
                        {"id": steering_id, "seq": seq, "message": message, "origin": origin}
                    )
    return drained


def pending_steering(conn: sqlite3.Connection, actor_id: str) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM actor_steering WHERE actor_id=? AND status='pending'",
            (actor_id,),
        ).fetchone()[0]
    )


def actor_logs(
    conn: sqlite3.Connection, actor_id: str, *, limit: int = 30
) -> dict[str, Any]:
    """Tail an actor's child-run audit trail, newest last.

    There is no separate log stream to tail: the worker runs the child as an
    ordinary mission+run, so its activity is already the audit_events of
    `actors.child_run_id`. This projects the tail of that trail into a compact,
    model-readable shape rather than inventing a second logging path that could
    disagree with the audit trail.
    """
    actor = _fetch_actor(conn, actor_id)
    if actor is None:
        raise ValueError(f"unknown actor: {actor_id}")
    child_run_id = actor.get("child_run_id")
    if not child_run_id:
        return {
            "actor_id": actor_id,
            "status": actor["status"],
            "child_run_id": None,
            "events": [],
            "note": "the actor has not started its child run yet",
        }
    limit = max(1, min(int(limit), 200))
    rows = conn.execute(
        "SELECT event_type, tool_name, timestamp, data FROM audit_events"
        " WHERE run_id=? ORDER BY timestamp DESC, id DESC LIMIT ?",
        (child_run_id, limit),
    ).fetchall()
    events = []
    for event_type, tool_name, timestamp, data in reversed(rows):
        entry: dict[str, Any] = {
            "at": timestamp,
            "event": event_type,
            "tool": tool_name or "",
        }
        try:
            payload = json.loads(data or "{}")
        except (TypeError, ValueError):
            payload = {}
        text = payload.get("text") or payload.get("delta") or payload.get("error")
        if isinstance(text, str) and text.strip():
            entry["text"] = text[:1000]
        events.append(entry)
    return {
        "actor_id": actor_id,
        "status": actor["status"],
        "child_run_id": child_run_id,
        "events": events,
    }


# ---------------------------------------------------------------------------
# Completion inbox (durable delivery with claim lease)
# ---------------------------------------------------------------------------


def _emit_delivery_transition(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    actor_id: str,
    transition: str,
    followup_run_id: Optional[str] = None,
) -> None:
    """Audit a delivery transition without ever exposing its payload."""
    actor = _fetch_actor(conn, actor_id)
    if actor is None:
        return
    try:
        emit(
            conn,
            lock,
            run_id=actor["parent_run_id"],
            task_id=actor_id,
            session_id=actor.get("session_id"),
            event_type="subagent_run",
            data={
                "transition": transition,
                "actor_id": actor_id,
                "followup_run_id": followup_run_id,
            },
        )
    except Exception as exc:  # noqa: BLE001 — delivery correctness is primary
        logger.warning("actor delivery audit emit failed: %s", exc)


def claim_delivery(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    claim_token: str,
    lease_seconds: float = 60.0,
) -> Optional[dict[str, Any]]:
    """CAS-claim one actor delivery, reclaiming an expired lease.

    The actor-specific API is used by proactive parent wakeups so two workers
    cannot both create follow-up work for the same completion.
    """
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now = now_dt.isoformat()
    stale_before = (
        now_dt - datetime.timedelta(seconds=max(0.0, lease_seconds))
    ).isoformat()
    payload: Optional[str] = None
    with lock:
        with conn:
            row = conn.execute(
                "SELECT payload FROM actor_deliveries WHERE actor_id=? AND "
                "(status='pending' OR "
                "(status='claimed' AND claimed_at<?))",
                (actor_id, stale_before),
            ).fetchone()
            if row is not None:
                cur = conn.execute(
                    "UPDATE actor_deliveries SET status='claimed', claim_token=?, "
                    "claimed_at=?, updated_at=? WHERE actor_id=? AND "
                    "(status='pending' OR "
                    "(status='claimed' AND claimed_at<?))",
                    (claim_token, now, now, actor_id, stale_before),
                )
                if cur.rowcount == 1:
                    payload = row[0]
    if payload is None:
        return None
    _emit_delivery_transition(
        conn,
        lock,
        actor_id=actor_id,
        transition="claimed",
    )
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {"actor_id": actor_id, "payload": payload}


def renew_delivery_claim(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    claim_token: str,
) -> bool:
    """Refresh a claim lease only while the caller still owns it."""
    now = _now()
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE actor_deliveries SET claimed_at=?, updated_at=? "
                "WHERE actor_id=? AND status='claimed' AND claim_token=?",
                (now, now, actor_id, claim_token),
            )
            changed = cur.rowcount == 1
    if changed:
        _emit_delivery_transition(
            conn,
            lock,
            actor_id=actor_id,
            transition="lease_renewed",
        )
    return changed


def release_delivery_claim(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    claim_token: str,
) -> bool:
    """Return a caller-owned claim to pending after a retryable failure."""
    now = _now()
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE actor_deliveries SET status='pending', claim_token=NULL, "
                "claimed_at=NULL, updated_at=? WHERE actor_id=? "
                "AND status='claimed' AND claim_token=?",
                (now, actor_id, claim_token),
            )
            changed = cur.rowcount == 1
    if changed:
        _emit_delivery_transition(
            conn,
            lock,
            actor_id=actor_id,
            transition="released",
        )
    return changed


def consume_claimed_delivery(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    claim_token: str,
    followup_run_id: Optional[str] = None,
) -> bool:
    """Consume one delivery only when the caller still owns its live claim."""
    now = _now()
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE actor_deliveries SET status='consumed', delivered_at=?, "
                "updated_at=? WHERE actor_id=? AND status='claimed' "
                "AND claim_token=?",
                (now, now, actor_id, claim_token),
            )
            changed = cur.rowcount == 1
    if changed:
        _emit_delivery_transition(
            conn,
            lock,
            actor_id=actor_id,
            transition="consumed",
            followup_run_id=followup_run_id,
        )
    return changed


def claim_deliveries(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    parent_run_id: str,
    claim_token: str,
    lease_seconds: float = 60.0,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Claim pending deliveries for a parent run (pre-model hook path).

    A claim whose lease expired without acknowledgement is reclaimable — a
    crash between claim and acknowledge retries on the next boundary. Returns
    the claimed payloads (parsed).
    """
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now = now_dt.isoformat()
    stale_before = (now_dt - datetime.timedelta(seconds=lease_seconds)).isoformat()
    claimed: list[dict[str, Any]] = []
    with lock:
        with conn:
            rows = conn.execute(
                "SELECT actor_id, payload FROM actor_deliveries"
                " WHERE parent_run_id=? AND"
                " (status='pending' OR (status='claimed' AND claimed_at<?))"
                " ORDER BY created_at LIMIT ?",
                (parent_run_id, stale_before, max(1, limit)),
            ).fetchall()
            for actor_id, payload in rows:
                cur = conn.execute(
                    "UPDATE actor_deliveries SET status='claimed', claim_token=?,"
                    " claimed_at=?, updated_at=?"
                    " WHERE actor_id=? AND"
                    " (status='pending' OR (status='claimed' AND claimed_at<?))",
                    (claim_token, now, now, actor_id, stale_before),
                )
                if cur.rowcount == 1:
                    try:
                        claimed.append(json.loads(payload))
                    except json.JSONDecodeError:
                        claimed.append({"actor_id": actor_id, "payload": payload})
    return claimed


def acknowledge_deliveries(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    claim_token: str,
) -> int:
    """Mark all deliveries under a claim token delivered (post-model hook)."""
    now = _now()
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE actor_deliveries SET status='delivered', delivered_at=?,"
                " updated_at=? WHERE claim_token=? AND status='claimed'",
                (now, now, claim_token),
            )
            return cur.rowcount


def consume_delivery(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
) -> Optional[dict[str, Any]]:
    """Explicit wait consumes the delivery, preventing later duplicate injection."""
    now = _now()
    with lock:
        with conn:
            row = conn.execute(
                "SELECT payload, status FROM actor_deliveries WHERE actor_id=?",
                (actor_id,),
            ).fetchone()
            if row is None:
                return None
            payload, status = row
            if status in ("claimed", "consumed"):
                return None
            cur = conn.execute(
                "UPDATE actor_deliveries SET status='consumed', updated_at=?"
                " WHERE actor_id=? AND status IN ('pending','delivered')",
                (now, actor_id),
            )
            if cur.rowcount != 1:
                return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {"actor_id": actor_id, "payload": payload}


# ---------------------------------------------------------------------------
# Orphan recovery
# ---------------------------------------------------------------------------


def reconcile_orphan_actors(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    ttl_seconds: float = 90.0,
) -> list[str]:
    """Startup sweep: stale queued/running actors become orphaned.

    Reads DB state only (never in-process thread registries). An actor is
    stale when its heartbeat (or, before any heartbeat, its creation time) is
    older than the TTL. Orphaned actors are never silently reported as
    successful — a delivery carrying status=orphaned is written so the parent
    learns at its next boundary.
    """
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now = now_dt.isoformat()
    stale_before = (now_dt - datetime.timedelta(seconds=ttl_seconds)).isoformat()
    orphaned: list[str] = []
    with lock:
        with conn:
            rows = conn.execute(
                "SELECT * FROM actors WHERE status IN ('queued','running')"
                " AND COALESCE(heartbeat_at, created_at) < ?",
                (stale_before,),
            ).fetchall()
            cur = conn.execute("SELECT * FROM actors LIMIT 0")
            cols = [d[0] for d in cur.description]
            for raw in rows:
                actor = dict(zip(cols, raw))
                conn.execute(
                    "UPDATE actors SET status='orphaned', finished_at=?, updated_at=?"
                    " WHERE id=? AND status IN ('queued','running')",
                    (now, now, actor["id"]),
                )
                payload = json.dumps(
                    {
                        "actor_id": actor["id"],
                        "status": "orphaned",
                        "goal": (actor.get("goal") or "")[:500],
                        "mode": actor.get("mode"),
                        "error": "worker disappeared (no heartbeat within TTL)",
                        "finished_at": now,
                    }
                )
                conn.execute(
                    "INSERT OR IGNORE INTO actor_deliveries"
                    "(actor_id, parent_run_id, session_id, status, payload,"
                    " created_at, updated_at)"
                    " VALUES (?,?,?,'pending',?,?,?)",
                    (
                        actor["id"],
                        actor["parent_run_id"],
                        actor.get("session_id"),
                        payload,
                        now,
                        now,
                    ),
                )
                orphaned.append(actor["id"])
    for actor_id in orphaned:
        refreshed = _fetch_actor(conn, actor_id)
        if refreshed:
            _emit_lifecycle(conn, lock, refreshed, "failed", status="orphaned")
    if orphaned:
        logger.info("reconciled %d orphaned actor(s)", len(orphaned))
    return orphaned


__all__ = [
    "MAX_DEPTH",
    "actor_logs",
    "attach_child_run",
    "drain_steering",
    "enqueue_steering",
    "pending_steering",
    "spawn_actor",
    "mark_running",
    "heartbeat_actor",
    "complete_actor",
    "fail_actor",
    "cancel_actor",
    "get_actor",
    "list_actors",
    "load_actor_history",
    "wait_for_actor",
    "claim_deliveries",
    "acknowledge_deliveries",
    "consume_delivery",
    "reconcile_orphan_actors",
    "default_idempotency_key",
]
