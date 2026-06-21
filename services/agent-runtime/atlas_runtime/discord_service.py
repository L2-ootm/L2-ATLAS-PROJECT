"""ATLAS Discord write service — the gated approval state machine (Phase C).

Two-phase, audit-first (D-002), SQLite-backed (D-003):

    propose(action, …)  -> inserts a `pending` discord_approvals row,
                            emits event_type="approval". Nothing touches Discord.
    approve(approval_id) -> executes the write via discord_api (the sidecar),
                            flips the row to `executed` (or `failed`), and emits
                            event_type="discord_action" (or "failure").
    reject(approval_id)  -> flips the row to `rejected`, emits "approval".

State lives here in SQLite, never in the Rust gateway (D-022): the gateway only
dispatches the `atlas discord` CLI, which calls this service.

Security posture: `params` is secret-redacted ONCE at propose time and is the
single source of truth for both the audit trail and execution — so a smuggled
secret is redacted before it can persist OR reach Discord (operating-model rule:
"Never store secrets in generated artifacts"). Operator writes carry
run_id="operator"; mission_service.ensure_operator_run bootstraps the synthetic
run so the audit FK holds on a fresh DB.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading
from typing import Optional

from atlas_core.schemas.discord import DiscordApproval

from atlas_runtime import discord_api, mission_service
from atlas_runtime.audit_service import _redact, emit

# Required params per action (beyond guild_id / target_id, which are columns).
_REQUIRES_TARGET = frozenset(
    {"edit_channel", "delete_channel", "edit_role", "delete_role", "send_message", "set_permissions"}
)
_REQUIRED_PARAMS: dict[str, tuple[str, ...]] = {
    "create_channel": ("name",),
    "edit_channel": (),
    "delete_channel": (),
    "create_role": ("name",),
    "edit_role": (),
    "delete_role": (),
    "send_message": ("embed",),
    "set_permissions": ("role_id",),
}

_COLS = (
    "id, action, guild_id, target_id, params, summary, status, reason, result, "
    "run_id, requested_at, decided_at"
)


class DiscordApprovalError(ValueError):
    """An approval could not be proposed/loaded/transitioned (bad action, missing
    params, unknown id, or wrong status). Distinct from a sidecar/network error."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate(action: str, target_id: Optional[str], params: dict) -> None:
    if action not in _REQUIRED_PARAMS:
        raise DiscordApprovalError(f"unknown discord action {action!r}")
    if action in _REQUIRES_TARGET and not target_id:
        raise DiscordApprovalError(f"action {action!r} requires a target id")
    missing = [k for k in _REQUIRED_PARAMS[action] if not params.get(k)]
    if missing:
        raise DiscordApprovalError(
            f"action {action!r} missing required param(s): {', '.join(missing)}"
        )


def _summarize(action: str, target_id: Optional[str], params: dict) -> str:
    name = params.get("name") or params.get("role_id") or target_id or ""
    verb = action.replace("_", " ")
    if action == "create_channel":
        return f"create {params.get('type', 'text')} channel #{name}".strip()
    if action == "send_message":
        title = (params.get("embed") or {}).get("title", "")
        return f"send embed to channel {target_id}" + (f" — {title}" if title else "")
    if action == "set_permissions":
        return f"set permissions for role {params.get('role_id')} on channel {target_id}"
    return f"{verb} {name}".strip()


def _row_to_approval(row: sqlite3.Row | tuple) -> DiscordApproval:
    keys = [c.strip() for c in _COLS.split(",")]
    data = dict(zip(keys, row))
    return DiscordApproval(**data)


def _load(conn: sqlite3.Connection, approval_id: str) -> DiscordApproval:
    cur = conn.execute(
        f"SELECT {_COLS} FROM discord_approvals WHERE id = ?", (approval_id,)
    )
    row = cur.fetchone()
    if row is None:
        raise DiscordApprovalError(f"no discord approval {approval_id!r}")
    return _row_to_approval(row)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def propose(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    action: str,
    guild_id: str,
    target_id: Optional[str] = None,
    params: Optional[dict] = None,
    reason: Optional[str] = None,
) -> DiscordApproval:
    """Validate + record a pending Discord write. No Discord call happens here."""
    params = params or {}
    _validate(action, target_id, params)

    # Redact ONCE: stored + audited + executed copy are all this redacted JSON.
    params_json = _redact(json.dumps(params))
    summary = _summarize(action, target_id, params)

    approval = DiscordApproval(
        action=action,  # type: ignore[arg-type]  (validated above)
        guild_id=guild_id,
        target_id=target_id,
        params=params_json,
        summary=summary,
        reason=reason,
    )
    run_id = mission_service.ensure_operator_run(conn, lock)
    row = approval.model_dump()

    with lock:
        with conn:
            conn.execute(
                "INSERT INTO discord_approvals "
                "(id, action, guild_id, target_id, params, summary, status, reason, "
                " result, run_id, requested_at, decided_at) "
                "VALUES (:id, :action, :guild_id, :target_id, :params, :summary, :status, "
                ":reason, :result, :run_id, :requested_at, :decided_at)",
                row,
            )

    emit(
        conn,
        lock,
        run_id=run_id,
        event_type="approval",
        tool_name=f"discord.{action}",
        data={
            "approval_id": approval.id,
            "action": action,
            "guild_id": guild_id,
            "target_id": target_id,
            "summary": summary,
            "status": "pending",
        },
    )
    return approval


def list_approvals(
    conn: sqlite3.Connection, *, status: Optional[str] = "pending"
) -> list[DiscordApproval]:
    """List approvals, newest first. status=None returns every row."""
    if status is None:
        cur = conn.execute(
            f"SELECT {_COLS} FROM discord_approvals ORDER BY requested_at DESC"
        )
    else:
        cur = conn.execute(
            f"SELECT {_COLS} FROM discord_approvals WHERE status = ? "
            "ORDER BY requested_at DESC",
            (status,),
        )
    return [_row_to_approval(r) for r in cur.fetchall()]


def get_approval(conn: sqlite3.Connection, approval_id: str) -> DiscordApproval:
    return _load(conn, approval_id)


def _execute(approval: DiscordApproval, reason: str) -> dict:
    """Dispatch the matching discord_api write. Raises DiscordSidecarError on failure."""
    p = json.loads(approval.params or "{}")
    g, t = approval.guild_id, approval.target_id
    a = approval.action
    if a == "create_channel":
        return discord_api.create_channel(
            g, name=p["name"], type=p.get("type", "text"),
            category_id=p.get("category_id"), topic=p.get("topic", ""), reason=reason,
        )
    if a == "edit_channel":
        return discord_api.edit_channel(
            g, t, name=p.get("name"), category_id=p.get("category_id"),
            topic=p.get("topic"), reason=reason,
        )
    if a == "delete_channel":
        return discord_api.delete_channel(g, t, reason=reason)
    if a == "create_role":
        return discord_api.create_role(
            g, name=p["name"], color_hex=p.get("color_hex", ""),
            hoist=bool(p.get("hoist", False)), permissions=p.get("permissions"), reason=reason,
        )
    if a == "edit_role":
        return discord_api.edit_role(
            g, t, name=p.get("name"), color_hex=p.get("color_hex"),
            hoist=p.get("hoist"), permissions=p.get("permissions"), reason=reason,
        )
    if a == "delete_role":
        return discord_api.delete_role(g, t, reason=reason)
    if a == "send_message":
        return discord_api.send_message(t, embed=p["embed"], reason=reason)
    if a == "set_permissions":
        return discord_api.set_permissions(
            g, t, role_id=p["role_id"], allow=p.get("allow"), deny=p.get("deny"), reason=reason,
        )
    raise DiscordApprovalError(f"unknown discord action {a!r}")  # pragma: no cover


def approve(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    approval_id: str,
    reason: Optional[str] = None,
) -> DiscordApproval:
    """Execute a pending write via the sidecar; flip to executed/failed; emit audit.

    Concurrency-safe: the pending->executing transition is a single atomic UPDATE
    guarded on `status='pending'`. Only the approver whose UPDATE affects one row
    proceeds to execute, so two concurrent `approve` calls cannot double-execute
    the same write (TOCTOU guard)."""
    approval = _load(conn, approval_id)  # raises if the id is unknown

    run_id = mission_service.ensure_operator_run(conn, lock)
    now = datetime.datetime.now(datetime.timezone.utc)

    # Atomically claim the row. A second concurrent approver sees rowcount 0.
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE discord_approvals SET status = 'executing' "
                "WHERE id = ? AND status = 'pending'",
                (approval_id,),
            )
            claimed = cur.rowcount == 1
    if not claimed:
        current = _load(conn, approval_id)
        raise DiscordApprovalError(
            f"approval {approval_id!r} is {current.status!r}, not pending"
        )

    audit_reason = reason or f"ATLAS operator approved {approval.action}"

    try:
        result = _execute(approval, audit_reason)
    except discord_api.DiscordSidecarError as exc:
        result_json = json.dumps({"error": str(exc)})
        _set_terminal(conn, lock, approval_id, "failed", result_json, now)
        emit(
            conn, lock, run_id=run_id, event_type="failure",
            tool_name=f"discord.{approval.action}",
            data={"approval_id": approval_id, "action": approval.action, "error": str(exc)},
            policy_result="discord_write_failed",
        )
        return _load(conn, approval_id)

    result_json = _redact(json.dumps(result))
    _set_terminal(conn, lock, approval_id, "executed", result_json, now)
    emit(
        conn, lock, run_id=run_id, event_type="discord_action",
        tool_name=f"discord.{approval.action}",
        data={
            "approval_id": approval_id,
            "action": approval.action,
            "guild_id": approval.guild_id,
            "target_id": approval.target_id,
            "result": result,
        },
    )
    return _load(conn, approval_id)


def reject(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    approval_id: str,
    reason: Optional[str] = None,
) -> DiscordApproval:
    """Mark a pending approval rejected; emit an approval audit event."""
    approval = _load(conn, approval_id)
    if approval.status != "pending":
        raise DiscordApprovalError(
            f"approval {approval_id!r} is {approval.status!r}, not pending"
        )

    run_id = mission_service.ensure_operator_run(conn, lock)
    now = datetime.datetime.now(datetime.timezone.utc)
    with lock:
        with conn:
            conn.execute(
                "UPDATE discord_approvals SET status = 'rejected', reason = ?, decided_at = ? "
                "WHERE id = ?",
                (reason, now.isoformat(), approval_id),
            )
    emit(
        conn, lock, run_id=run_id, event_type="approval",
        tool_name=f"discord.{approval.action}",
        data={
            "approval_id": approval_id,
            "action": approval.action,
            "status": "rejected",
            "reason": reason,
        },
    )
    return _load(conn, approval_id)


def _set_terminal(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    approval_id: str,
    status: str,
    result_json: str,
    when: datetime.datetime,
) -> None:
    with lock:
        with conn:
            conn.execute(
                "UPDATE discord_approvals SET status = ?, result = ?, decided_at = ? "
                "WHERE id = ?",
                (status, result_json, when.isoformat(), approval_id),
            )
