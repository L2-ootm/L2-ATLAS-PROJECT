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
from typing import Any, Optional

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
        "child_run_id": actor.get("child_run_id"),
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
) -> tuple[dict[str, Any], bool]:
    """Idempotently insert a queued actor. Returns (actor, created).

    Duplicate delivery of the same spawn mutation (same idempotency key)
    returns the existing actor instead of starting another child.
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
    # The parent run is the authority for surface projection. Hermes' internal
    # session id is a different namespace and must never detach child telemetry
    # from the ATLAS surface session.
    parent = conn.execute(
        "SELECT session_id FROM runs WHERE id=?", (parent_run_id,)
    ).fetchone()
    if parent is not None and parent[0]:
        session_id = str(parent[0])
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
                " depth, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,'queued',?,?,?,?)",
                (
                    actor_id, parent_run_id, parent_actor_id, session_id,
                    key, role, goal, model, mode, workspace_root,
                    depth, now, now,
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


def bind_child_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    child_run_id: str,
) -> bool:
    """Attach a live child run before execution so its stream is discoverable."""
    now = _now()
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE actors SET child_run_id=?, updated_at=?"
                " WHERE id=? AND status='running' AND child_run_id IS NULL",
                (child_run_id, now, actor_id),
            )
            changed = cur.rowcount == 1
    if changed:
        actor = _fetch_actor(conn, actor_id)
        if actor:
            _emit_lifecycle(
                conn, lock, actor, "working", child_run_id=child_run_id
            )
    return changed


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


def wait_for_actor(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    timeout_seconds: float = 120.0,
    poll_interval: float = 0.25,
    consume: bool = True,
) -> Optional[dict[str, Any]]:
    """Join an existing actor with a bounded timeout.

    Rechecks immediately after the initial read to close the completion race,
    then polls. On terminal state, consumes the pending delivery (when
    `consume`) so a later pre-model inbox claim cannot inject a duplicate.
    Returns the actor row (with `delivery` payload when one was consumed) or
    None when the timeout elapsed with the actor still active.
    """
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while True:
        actor = _fetch_actor(conn, actor_id)
        if actor is None:
            return None
        if actor["status"] in TERMINAL_STATUSES:
            if consume:
                actor["delivery"] = consume_delivery(conn, lock, actor_id)
            return actor
        if time.monotonic() >= deadline:
            return None
        time.sleep(poll_interval)


# ---------------------------------------------------------------------------
# Completion inbox (durable delivery with claim lease)
# ---------------------------------------------------------------------------


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
            if status == "consumed":
                return None
            conn.execute(
                "UPDATE actor_deliveries SET status='consumed', updated_at=?"
                " WHERE actor_id=?",
                (now, actor_id),
            )
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
    "spawn_actor",
    "mark_running",
    "heartbeat_actor",
    "complete_actor",
    "fail_actor",
    "cancel_actor",
    "get_actor",
    "list_actors",
    "wait_for_actor",
    "claim_deliveries",
    "acknowledge_deliveries",
    "consume_delivery",
    "reconcile_orphan_actors",
    "default_idempotency_key",
]
