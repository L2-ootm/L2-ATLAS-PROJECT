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
    "starting": frozenset({"active", "failed"}),
    "active": frozenset({"suspended", "cancelling", "completed", "failed"}),
    "suspended": frozenset({"resuming", "cancelling", "reclaimed", "failed"}),
    "resuming": frozenset({"active", "failed"}),
    "cancelling": frozenset({"completed", "failed"}),
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


__all__ = [
    "create_session",
    "get_session",
    "list_sessions",
    "transition_session",
]
