"""Surface session lifecycle state-machine service (SURF-01, AUD-01, plan 10.3-01).

Mirrors ``run_service`` exactly: construct + validate the frozen ``SurfaceSession``
BEFORE any SQL, perform the guarded write inside ``with lock: with conn:`` against a
SELECT-status precondition, then emit the audit event AFTER releasing the lock
(``audit_service.emit`` re-acquires the lock internally — emitting inside it deadlocks;
PATTERNS Pitfall 6).

No new runtime/provider/tool-executor/memory backend is introduced (AGNT-01); the audit
trail rides the existing ``audit_service.emit`` bus.

Lifecycle vocabulary (aligns plan 01 <-> plan 04 so SURF-06's "terminal audited outcome"
is testable at the session level): terminal session states are exactly
``{completed, failed, reclaimed}``. There is intentionally NO ``cancelled`` session state —
a cooperative cancel emits the RUN-level ``run_cancelled`` (plan 04) and drives the owning
session ``cancelling -> completed`` for a clean stop (``cancelling -> failed`` only if an
error occurs during cancel).
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
from typing import List, Optional

from atlas_core.schemas.agent_contract import (
    ModelIdentity,
    PermissionMode,
    SurfaceIdentity,
    WorkspaceIdentity,
)
from atlas_core.schemas.surface_session import SessionState, SurfaceSession

from atlas_runtime import audit_service

# Outgoing-transition table, pinned deterministically. A target is reachable from a
# state iff it is a member of that state's frozenset. Terminal states have an empty
# outgoing set, so any attempt to leave them raises ValueError before a DB write is
# even attempted (the DB trigger is the belt-and-suspenders backstop, T-10.3-01-IMMUT).
_ALLOWED_FROM: dict[SessionState, frozenset] = {
    # `reclaimed` is reachable from EVERY non-terminal live state: the startup
    # reconciliation sweep (plan 04) must be able to reclaim an orphaned session
    # regardless of whether it died active, suspended, or mid-resume.
    "starting": frozenset({"active", "failed", "reclaimed"}),
    "active": frozenset({"suspended", "cancelling", "completed", "failed", "reclaimed"}),
    "suspended": frozenset({"resuming", "cancelling", "reclaimed", "failed"}),
    "resuming": frozenset({"active", "failed", "reclaimed"}),
    "cancelling": frozenset({"completed", "failed", "reclaimed"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "reclaimed": frozenset(),
}

# Audit event_type emitted when a session enters each state. Every member is a valid
# AuditEvent.event_type Literal; the precise target/source states alse ride the audit
# ``data`` payload, so AUD-01 records the full transition regardless of the label.
_EVENT_FOR_STATE: dict[SessionState, str] = {
    "active": "surface_session_resumed",
    "resuming": "surface_session_resumed",
    "suspended": "surface_session_suspended",
    "cancelling": "run_cancelled",
    "completed": "surface_session_completed",
    "failed": "surface_session_failed",
    "reclaimed": "surface_session_reclaimed",
}

# Sentinel run for connection-level (run-less) session audit events. audit_events.run_id
# is FK-enforced (NOT NULL REFERENCES runs(id)); a surface session can exist before any
# run, so its lifecycle events are anchored to an operator sentinel run — consistent with
# the DEFAULT 'operator' convention already used by tool_approvals/discord_approvals.
_OPERATOR_RUN_ID = "operator"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _ensure_operator_run(conn: sqlite3.Connection) -> None:
    """Idempotently seed the operator sentinel mission + run (run-less audit FK target).

    Called only when a session lifecycle event is anchored to the operator sentinel
    (i.e. the session has no real run). INSERT OR IGNORE keeps it a no-op once present.
    Must run inside the caller's write transaction so the FK target exists before emit.
    """
    now = _now_iso()
    conn.execute(
        "INSERT OR IGNORE INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES(?, ?, ?, ?, ?, ?, ?)",
        (_OPERATOR_RUN_ID, "operator", "", "running", "", now, now),
    )
    conn.execute(
        "INSERT OR IGNORE INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES(?, ?, ?, ?, ?, ?, ?)",
        (_OPERATOR_RUN_ID, _OPERATOR_RUN_ID, None, "running", now, None, ""),
    )


def _row_to_session(row: sqlite3.Row | tuple) -> SurfaceSession:
    """Reconstruct a frozen SurfaceSession from a surface_sessions row (column order
    matches the INSERT in create_session)."""
    (
        sid,
        surface_kind,
        surface_session_id,
        workspace_kind,
        workspace_root,
        project_id,
        mission_id,
        run_id,
        agent,
        model_provider,
        model_id,
        permission_mode,
        prompt_version,
        tool_catalog_version,
        context_policy_version,
        state,
        owner_token,
        owner_pid,
        heartbeat_at,
        created_at,
        updated_at,
    ) = row
    return SurfaceSession(
        id=sid,
        surface=SurfaceIdentity(kind=surface_kind, session_id=surface_session_id),
        workspace=WorkspaceIdentity(
            kind=workspace_kind, root=workspace_root, project_id=project_id
        ),
        agent=agent,
        model=ModelIdentity(provider=model_provider, model_id=model_id),
        permission_mode=permission_mode,
        prompt_version=prompt_version,
        tool_catalog_version=tool_catalog_version,
        context_policy_version=context_policy_version,
        state=state,
        owner_token=owner_token,
        owner_pid=owner_pid,
        mission_id=mission_id,
        run_id=run_id,
        heartbeat_at=heartbeat_at,
        created_at=created_at,
        updated_at=updated_at,
    )


_SELECT_COLUMNS = (
    "id, surface_kind, surface_session_id, workspace_kind, workspace_root, project_id, "
    "mission_id, run_id, agent, model_provider, model_id, permission_mode, prompt_version, "
    "tool_catalog_version, context_policy_version, state, owner_token, owner_pid, "
    "heartbeat_at, created_at, updated_at"
)


def create_session(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    surface: SurfaceIdentity,
    workspace: WorkspaceIdentity,
    agent: str,
    model: ModelIdentity,
    permission_mode: PermissionMode,
    prompt_version: str,
    tool_catalog_version: str,
    context_policy_version: str,
    mission_id: Optional[str] = None,
    run_id: Optional[str] = None,
    owner_token: str = "",
    owner_pid: Optional[int] = None,
) -> SurfaceSession:
    """Persist a new surface session (state 'starting') and audit its start (SURF-01, AUD-01)."""
    session = SurfaceSession(
        surface=surface,
        workspace=workspace,
        agent=agent,
        model=model,
        permission_mode=permission_mode,
        prompt_version=prompt_version,
        tool_catalog_version=tool_catalog_version,
        context_policy_version=context_policy_version,
        mission_id=mission_id,
        run_id=run_id,
        owner_token=owner_token,
        owner_pid=owner_pid,
    )
    dumped = session.model_dump()
    eff_run = run_id or _OPERATOR_RUN_ID

    with lock:
        with conn:
            if eff_run == _OPERATOR_RUN_ID:
                _ensure_operator_run(conn)
            conn.execute(
                "INSERT INTO surface_sessions("
                "id, surface_kind, surface_session_id, workspace_kind, workspace_root, "
                "project_id, mission_id, run_id, agent, model_provider, model_id, "
                "permission_mode, prompt_version, tool_catalog_version, context_policy_version, "
                "state, owner_token, owner_pid, heartbeat_at, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    session.id,
                    session.surface.kind,
                    session.surface.session_id,
                    session.workspace.kind,
                    session.workspace.root,
                    session.workspace.project_id,
                    session.mission_id,
                    session.run_id,
                    session.agent,
                    session.model.provider,
                    session.model.model_id,
                    session.permission_mode,
                    session.prompt_version,
                    session.tool_catalog_version,
                    session.context_policy_version,
                    session.state,
                    session.owner_token,
                    session.owner_pid,
                    dumped["heartbeat_at"],
                    dumped["created_at"],
                    dumped["updated_at"],
                ),
            )

    # Emit AFTER the lock is released — emit() re-acquires it (Pitfall 6).
    audit_service.emit(
        conn,
        lock,
        run_id=eff_run,
        event_type="surface_session_started",
        session_id=session.id,
        data={
            "state": session.state,
            "surface": session.surface.kind,
            "workspace": session.workspace.kind,
        },
    )
    return session


def get_session(conn: sqlite3.Connection, session_id: str) -> Optional[SurfaceSession]:
    """Return the persisted session as a frozen model, or None if absent."""
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM surface_sessions WHERE id=?", (session_id,)
    ).fetchone()
    return None if row is None else _row_to_session(row)


def list_sessions(conn: sqlite3.Connection) -> List[SurfaceSession]:
    """Return all persisted surface sessions (creation order)."""
    rows = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM surface_sessions ORDER BY created_at ASC"
    ).fetchall()
    return [_row_to_session(r) for r in rows]


# ---------------------------------------------------------------------------
# Dashboard listing (F11 — sessions/subagent dashboard UI, Phase 3 Track B).
#
# `list_sessions` above stays a plain unfiltered read (existing callers/tests
# depend on that shape); this is a separate, additive read path for the
# cockpit's multi-session dashboard: pagination + actor/mission enrichment +
# server-computed heartbeat health, none of which the plain list needs.
# ---------------------------------------------------------------------------

_LIVE_STATES: tuple = ("starting", "active", "suspended", "resuming", "cancelling")
_MISSION_INTENT_BRIEF_CHARS = 120

# Default heartbeat TTL for BOTH sessions and actors — mirrors the single
# `_HEARTBEAT_TTL_SECONDS = 90.0` constant `cli/main.py` already uses for both
# `surface_session_service.reconcile_orphans` and
# `actor_service.reconcile_orphan_actors`. F11's research doc speculated
# session TTL might be "per-platform"; the actual codebase uses one shared
# constant for both, so this mirrors reality rather than the speculation.
_DEFAULT_HEARTBEAT_TTL_SECONDS = 90.0


def _health_from_age(age_seconds: Optional[float], ttl_seconds: float) -> str:
    """healthy (age < ttl) / stale (age >= ttl) / unknown (no heartbeat data)."""
    if age_seconds is None:
        return "unknown"
    return "healthy" if age_seconds < ttl_seconds else "stale"


def _session_health(
    session: SurfaceSession, now: datetime.datetime, ttl_seconds: float
) -> tuple:
    """Server-computed (heartbeat_age_seconds, health) for one session.

    `reclaimed` IS the orphan outcome (the reconciliation sweep already fired
    for this row), so it maps straight to 'orphaned' regardless of heartbeat
    math. `completed`/`failed` ended on purpose — heartbeat liveness no longer
    applies, so health is 'unknown'. Every other (live) state compares
    heartbeat_at (NOT NULL on this table) against `now`: 'stale' is the
    pre-reconciliation window where a sweep would reclaim the session but
    hasn't run yet.
    """
    if session.state == "reclaimed":
        return None, "orphaned"
    if session.state in ("completed", "failed"):
        return None, "unknown"
    age = (now - session.heartbeat_at).total_seconds()
    return age, _health_from_age(age, ttl_seconds)


def _actor_health(actor: dict, now: datetime.datetime, ttl_seconds: float) -> tuple:
    """Mirrors `_session_health` for one actor row (dict from actor_service)."""
    status = actor.get("status")
    if status == "orphaned":
        return None, "orphaned"
    if status in ("completed", "failed", "cancelled"):
        return None, "unknown"
    # reconcile_orphan_actors treats a null heartbeat as "still on created_at's
    # clock" (COALESCE(heartbeat_at, created_at)) — mirror that here so a
    # freshly queued actor isn't reported 'unknown' the instant it's listed.
    heartbeat_raw = actor.get("heartbeat_at") or actor.get("created_at")
    if not heartbeat_raw:
        return None, "unknown"
    age = (now - datetime.datetime.fromisoformat(heartbeat_raw)).total_seconds()
    return age, _health_from_age(age, ttl_seconds)


def _actor_brief(actor: dict, now: datetime.datetime, ttl_seconds: float) -> dict:
    age, health = _actor_health(actor, now, ttl_seconds)
    return {
        "id": actor["id"],
        "parent_id": actor.get("parent_actor_id"),
        "goal": actor.get("goal") or "",
        "status": actor.get("status"),
        "model": actor.get("model"),
        "mode": actor.get("mode"),
        "depth": actor.get("depth"),
        "heartbeat_age_seconds": age,
        "health": health,
        "created_at": actor.get("created_at"),
    }


def list_sessions_dashboard(
    conn: sqlite3.Connection,
    *,
    active_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    session_ttl_seconds: float = _DEFAULT_HEARTBEAT_TTL_SECONDS,
    actor_ttl_seconds: float = _DEFAULT_HEARTBEAT_TTL_SECONDS,
) -> dict:
    """Paginated, actor-enriched session list for the sessions dashboard (F11).

    Sort: live (non-terminal) sessions first, then heartbeat_at DESC (most
    recently active first) within each bucket — matches F11 section 2's
    "active sessions first, then by last_active" recommendation.

    `active_only=True` restricts to the live/non-terminal states, not the
    literal `state == 'active'` value — a `starting` or `suspended` session is
    still "live" for dashboard purposes.

    Batches actor aggregation into two page-wide queries (a GROUP BY count and
    an IN(...) top-level-actor fetch, both keyed off `idx_actors_session`)
    instead of calling `actor_service.list_actors` once per session, so a
    50-session page costs a constant handful of queries instead of 50+.
    Heartbeat staleness is computed here against server time so the client
    never needs clock-skew-sensitive logic.
    """
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

    where = ""
    params: list = []
    if active_only:
        placeholders = ",".join("?" for _ in _LIVE_STATES)
        where = f"WHERE state IN ({placeholders})"
        params = list(_LIVE_STATES)

    total = conn.execute(
        f"SELECT COUNT(*) FROM surface_sessions {where}",  # noqa: S608
        params,
    ).fetchone()[0]

    live_placeholders = ",".join("?" for _ in _LIVE_STATES)
    order_case = f"CASE WHEN state IN ({live_placeholders}) THEN 0 ELSE 1 END"
    rows = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM surface_sessions {where} "
        f"ORDER BY {order_case} ASC, heartbeat_at DESC LIMIT ? OFFSET ?",  # noqa: S608
        (*params, *_LIVE_STATES, limit, offset),
    ).fetchall()
    sessions = [_row_to_session(r) for r in rows]

    now = datetime.datetime.now(datetime.timezone.utc)
    session_ids = [s.id for s in sessions]
    mission_ids = sorted({s.mission_id for s in sessions if s.mission_id})

    missions: dict = {}
    if mission_ids:
        mplaceholders = ",".join("?" for _ in mission_ids)
        for mid, title, intent in conn.execute(
            f"SELECT id, title, intent FROM missions WHERE id IN ({mplaceholders})",  # noqa: S608
            mission_ids,
        ):
            missions[mid] = {"title": title, "intent": intent}

    actor_counts: dict = {}
    top_level_actors: dict = {}
    if session_ids:
        from atlas_runtime import actor_service  # local import: no top-level cycle risk

        splaceholders = ",".join("?" for _ in session_ids)
        for sid, status, count in conn.execute(
            "SELECT session_id, status, COUNT(*) FROM actors "
            f"WHERE session_id IN ({splaceholders}) GROUP BY session_id, status",  # noqa: S608
            session_ids,
        ):
            bucket = actor_counts.setdefault(sid, {"total": 0, "active": 0})
            bucket["total"] += count
            if status in actor_service.ACTIVE_STATUSES:
                bucket["active"] += count

        cur = conn.execute(
            "SELECT * FROM actors "
            f"WHERE session_id IN ({splaceholders}) AND parent_actor_id IS NULL "  # noqa: S608
            "ORDER BY created_at ASC",
            session_ids,
        )
        cols = [d[0] for d in cur.description]
        for raw in cur.fetchall():
            actor = dict(zip(cols, raw))
            top_level_actors.setdefault(actor["session_id"], []).append(actor)

    entries: list = []
    for session in sessions:
        age, health = _session_health(session, now, session_ttl_seconds)
        mission = missions.get(session.mission_id) if session.mission_id else None
        counts = actor_counts.get(session.id, {"total": 0, "active": 0})
        entry = session.model_dump(mode="json")
        entry["mission_title"] = mission["title"] if mission else None
        entry["mission_intent"] = (
            (mission["intent"] or "")[:_MISSION_INTENT_BRIEF_CHARS] if mission else None
        )
        entry["heartbeat_age_seconds"] = age
        entry["health"] = health
        entry["actor_count"] = counts["total"]
        entry["active_actor_count"] = counts["active"]
        entry["actors"] = [
            _actor_brief(a, now, actor_ttl_seconds)
            for a in top_level_actors.get(session.id, [])
        ]
        entries.append(entry)

    return {"sessions": entries, "total": total, "limit": limit, "offset": offset}


def transition_session(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    session_id: str,
    target_state: SessionState,
    *,
    run_id: Optional[str] = None,
) -> None:
    """Guarded lifecycle transition + audit (SURF-01, AUD-01).

    Raises ValueError if the session is missing or the transition is not reachable from
    the current state per ``_ALLOWED_FROM`` (terminal states have no outgoing edges).
    """
    with lock:
        with conn:
            row = conn.execute(
                "SELECT state, run_id FROM surface_sessions WHERE id=?", (session_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"no surface session {session_id}")
            current: SessionState = row[0]
            session_run_id = row[1]
            if target_state not in _ALLOWED_FROM.get(current, frozenset()):
                raise ValueError(
                    f"illegal surface session transition {current} -> {target_state}"
                )
            conn.execute(
                "UPDATE surface_sessions SET state=?, updated_at=? WHERE id=?",
                (target_state, _now_iso(), session_id),
            )
            eff_run = run_id or session_run_id or _OPERATOR_RUN_ID
            if eff_run == _OPERATOR_RUN_ID:
                _ensure_operator_run(conn)

    # Emit AFTER the lock is released (Pitfall 6).
    audit_service.emit(
        conn,
        lock,
        run_id=eff_run,
        event_type=_EVENT_FOR_STATE[target_state],
        session_id=session_id,
        data={"from": current, "state": target_state},
    )


def heartbeat(conn: sqlite3.Connection, lock: threading.Lock, session_id: str) -> None:
    """Refresh an active session's `heartbeat_at` to now (liveness, no transition, no audit).

    Owner-token + heartbeat-TTL liveness (stdlib only; never the POSIX kill(pid, 0) liveness
    probe, which is broken on Windows — RESEARCH Pitfall 2). A session whose heartbeat goes
    stale beyond the TTL is treated as orphaned by `reconcile_orphans`.
    """
    with lock:
        with conn:
            conn.execute(
                "UPDATE surface_sessions SET heartbeat_at=? WHERE id=? AND state='active'",
                (_now_iso(), session_id),
            )


def reconcile_orphans(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    ttl_seconds: float,
) -> list[str]:
    """Startup sweep: leave no unowned running session or run (SURF-05, AUD-01).

    Reads DB state (NOT the in-process `_active_threads` dict, which is lost on restart —
    RESEARCH Runtime State Inventory). Any non-terminal session whose heartbeat is null or
    older than the TTL is reclaimed and its running runs cancelled; any run still left
    `running` whose session is absent or already reclaimed (a crash-left orphan at startup)
    is cancelled too. All transitions/cancellations are audited. Idempotent: a second sweep
    over already-reclaimed sessions and cancelled runs is a no-op.

    Returns the list of reclaimed session ids.
    """
    from atlas_runtime import run_service

    cutoff = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(seconds=ttl_seconds)
    ).isoformat()
    reclaimed: list[str] = []

    stale = conn.execute(
        "SELECT id FROM surface_sessions "
        "WHERE state IN ('active','suspended','resuming') "
        "AND (heartbeat_at IS NULL OR heartbeat_at < ?)",
        (cutoff,),
    ).fetchall()
    for (sid,) in stale:
        run_rows = conn.execute(
            "SELECT id, mission_id FROM runs WHERE session_id=? AND status='running'",
            (sid,),
        ).fetchall()
        transition_session(conn, lock, sid, "reclaimed")
        for rid, mid in run_rows:
            try:
                run_service.cancel_run(conn, lock, run_id=rid, mission_id=mid)
            except ValueError:
                pass  # already terminal — idempotent
        reclaimed.append(sid)

    # Crash-left running runs whose owning session is absent or reclaimed.
    orphan_runs = conn.execute(
        "SELECT r.id, r.mission_id FROM runs r "
        "LEFT JOIN surface_sessions s ON r.session_id = s.id "
        "WHERE r.status='running' AND (s.id IS NULL OR s.state='reclaimed')"
    ).fetchall()
    for rid, mid in orphan_runs:
        try:
            run_service.cancel_run(conn, lock, run_id=rid, mission_id=mid)
        except ValueError:
            pass

    return reclaimed


def resume_session(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    session_id: str,
    *,
    owner_token: str,
    owner_pid: Optional[int] = None,
) -> SurfaceSession:
    """Re-bind a suspended session to a live owner and rebuild its context (SURF-05).

    Replays the immutable Phase 10.2 RunContractSnapshot for the session's run via
    `agent_contract_service.replay_contract`, asserting the stored prompt/tool-catalog/
    context-policy versions still match — a mismatch raises `ContractCompatibilityError`
    and NO resume happens (fail closed; authority cannot widen across a version change).
    Then drives `suspended -> resuming -> active` (guarded by `_ALLOWED_FROM`), mints a
    fresh `owner_token`, and refreshes `heartbeat_at` so the plan-04 reconciliation sweep
    treats the session as owned-alive. The transition into `active` emits the audited
    `surface_session_resumed` event. Reuses the existing contract replay — no new runtime,
    no new snapshot format (AGNT-01 / locked CONTEXT decision).

    Surface/workspace/mission-run-session identity is preserved (only state/ownership/
    heartbeat change). Raises ValueError if the session is missing or not in a resumable
    state; `ContractCompatibilityError`/`LookupError` propagate on contract drift/absence.
    """
    from atlas_runtime import agent_contract_service

    session = get_session(conn, session_id)
    if session is None:
        raise ValueError(f"no surface session {session_id}")

    # Fail-closed contract replay BEFORE any transition (no resume on drift/missing snapshot).
    agent_contract_service.replay_contract(
        conn,
        session.run_id,
        expected_prompt_version=session.prompt_version,
        expected_catalog_version=session.tool_catalog_version,
        expected_context_policy_version=session.context_policy_version,
    )

    transition_session(conn, lock, session_id, "resuming")
    with lock:
        with conn:
            conn.execute(
                "UPDATE surface_sessions SET owner_token=?, owner_pid=?, heartbeat_at=? WHERE id=?",
                (owner_token, owner_pid, _now_iso(), session_id),
            )
    transition_session(conn, lock, session_id, "active")  # emits surface_session_resumed
    return get_session(conn, session_id)


__all__ = [
    "create_session",
    "get_session",
    "heartbeat",
    "list_sessions",
    "list_sessions_dashboard",
    "reconcile_orphans",
    "resume_session",
    "transition_session",
]
