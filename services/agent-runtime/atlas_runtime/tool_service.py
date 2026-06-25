"""ATLAS tool service — the single policy chokepoint + approval state machine (Phase 10.0.4).

Generalizes the Phase C discord_service pipeline to all tools. Every tool call
flows through `invoke`:

    invoke(tool_name, args)  -> emits tool_requested; policy.decide(manifest).
        read-class            -> run the adapter now; emit tool_completed (or
                                 tool_failed); return ToolResult.
        write/shell           -> insert a `pending` tool_approvals row; emit
                                 `approval`; return ToolApproval. NOTHING runs.
    approve(approval_id)     -> atomically claim the pending row, run the deferred
                                 adapter, flip to executed/failed, emit
                                 tool_completed/tool_failed.
    reject(approval_id)      -> flip to rejected; no execution.

State lives here in SQLite, never in the Rust gateway (D-022). args/results are
secret-redacted ONCE at the audit boundary (D-002). Operator calls carry
run_id="operator"; mission_service.ensure_operator_run bootstraps the synthetic
run so the audit FK holds on a fresh DB. The atomic `UPDATE … WHERE status='pending'`
claim (rowcount==1) is the TOCTOU guard copied verbatim from discord_service.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading
from typing import Optional

from atlas_core.schemas.tool import ToolApproval, ToolResult

from atlas_runtime import mission_service, policy
from atlas_runtime.audit_service import _redact, emit
from atlas_runtime.tools import registry

_COLS = (
    "id, tool_name, risk_level, args, summary, status, reason, result, "
    "run_id, requested_at, decided_at"
)


class ToolApprovalError(ValueError):
    """A tool approval could not be loaded/transitioned (unknown id or wrong status)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_approval(row: sqlite3.Row | tuple) -> ToolApproval:
    keys = [c.strip() for c in _COLS.split(",")]
    return ToolApproval(**dict(zip(keys, row)))


def _load(conn: sqlite3.Connection, approval_id: str) -> ToolApproval:
    cur = conn.execute(f"SELECT {_COLS} FROM tool_approvals WHERE id = ?", (approval_id,))
    row = cur.fetchone()
    if row is None:
        raise ToolApprovalError(f"no tool approval {approval_id!r}")
    return _row_to_approval(row)


def _set_terminal(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    approval_id: str,
    status: str,
    result_json: Optional[str],
    when: datetime.datetime,
) -> None:
    with lock:
        with conn:
            conn.execute(
                "UPDATE tool_approvals SET status = ?, result = ?, decided_at = ? WHERE id = ?",
                (status, result_json, when.isoformat(), approval_id),
            )


def _summarize(tool_name: str, risk_level: str, args: dict) -> str:
    if tool_name == "webhook_notify":
        return f"webhook_notify POST {args.get('url', '')}".strip()
    if tool_name == "workspace":
        return f"workspace {args.get('op', '')} {args.get('path', '')}".strip()
    return f"{tool_name} ({risk_level})"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def invoke(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    tool_name: str,
    args: Optional[dict] = None,
    mode: str = "read_only",
    ctx: Optional[dict] = None,
    reason: Optional[str] = None,
) -> ToolResult | ToolApproval:
    """The single chokepoint. Returns a ToolResult (read-class executed) or a
    pending ToolApproval (write/shell short-circuited). Raises ValueError if the
    tool is unknown — an unclassified tool never auto-runs."""
    manifest, adapter = registry.get_registry().resolve(tool_name)  # ValueError on unknown
    args = args or {}
    ctx = ctx or {}

    run_id = mission_service.ensure_operator_run(conn, lock)
    args_json = _redact(json.dumps(args))  # redact ONCE at the boundary

    # Cancel gate (SURF-06, Pattern 7c): if cancellation was requested, a tool/subprocess
    # must NOT start. The token rides the internal `ctx` carrier (not a persisted public
    # model, so D-013-safe); the public signature is unchanged. Any adapter that spawns a
    # subprocess must additionally poll `ctx["cancel_token"]` and call proc.terminate()
    # then proc.kill() on cancel (Pattern 7d) — subprocesses ARE killable, unlike the
    # in-process model call.
    cancel_token = ctx.get("cancel_token")
    if cancel_token is not None and cancel_token.is_set():
        emit(
            conn, lock, run_id=run_id, event_type="tool_failed", tool_name=tool_name,
            data={"tool_name": tool_name, "stop_reason": "cancelled"},
            policy_result="cancelled",
        )
        return ToolResult(tool_name=tool_name, ok=False, error="cancelled")

    emit(
        conn, lock, run_id=run_id, event_type="tool_requested", tool_name=tool_name,
        data={"tool_name": tool_name, "risk_level": manifest.risk_level},
    )

    decision = policy.decide(manifest, mode)
    if decision.requires_approval:
        approval = ToolApproval(
            tool_name=tool_name,
            risk_level=manifest.risk_level,
            args=args_json,
            summary=_summarize(tool_name, manifest.risk_level, args),
            reason=reason,
        )
        with lock:
            with conn:
                conn.execute(
                    "INSERT INTO tool_approvals "
                    "(id, tool_name, risk_level, args, summary, status, reason, result, "
                    " run_id, requested_at, decided_at) "
                    "VALUES (:id, :tool_name, :risk_level, :args, :summary, :status, :reason, "
                    ":result, :run_id, :requested_at, :decided_at)",
                    approval.model_dump(),
                )
        emit(
            conn, lock, run_id=run_id, event_type="approval", tool_name=tool_name,
            data={
                "approval_id": approval.id, "tool_name": tool_name,
                "risk_level": manifest.risk_level, "status": "pending",
                "reason": decision.reason,
            },
        )
        return approval

    # Read-class: run now.
    return _run_and_emit(conn, lock, run_id, tool_name, adapter, args, args_json, ctx)


def _run_and_emit(conn, lock, run_id, tool_name, adapter, args, args_json, ctx) -> ToolResult:
    """Run an authorized adapter and emit tool_completed/tool_failed + a ToolCall."""
    try:
        result = adapter(args, ctx)
    except Exception as exc:  # noqa: BLE001 - adapter failure is an honest tool_failed
        emit(
            conn, lock, run_id=run_id, event_type="tool_failed", tool_name=tool_name,
            data={"tool_name": tool_name, "error": str(exc)},
            policy_result="tool_failed",
            tool_call_kwargs={
                "tool_name": tool_name, "args": args_json, "result": json.dumps({"error": str(exc)}),
                "policy_allowed": True, "requires_approval": False, "exit_code": 1,
            },
        )
        return ToolResult(tool_name=tool_name, ok=False, error=str(exc))

    event_type = "tool_completed" if result.ok else "tool_failed"
    emit(
        conn, lock, run_id=run_id, event_type=event_type, tool_name=tool_name,
        data={"tool_name": tool_name, "ok": result.ok},
        policy_result=None if result.ok else "tool_failed",
        tool_call_kwargs={
            "tool_name": tool_name, "args": args_json, "result": result.output or result.error or "",
            "policy_allowed": True, "requires_approval": False, "exit_code": result.exit_code,
        },
    )
    return result


def list_approvals(
    conn: sqlite3.Connection, *, status: Optional[str] = None
) -> list[ToolApproval]:
    """List tool approvals, newest first. status=None returns every row."""
    if status is None:
        cur = conn.execute(f"SELECT {_COLS} FROM tool_approvals ORDER BY requested_at DESC")
    else:
        cur = conn.execute(
            f"SELECT {_COLS} FROM tool_approvals WHERE status = ? ORDER BY requested_at DESC",
            (status,),
        )
    return [_row_to_approval(r) for r in cur.fetchall()]


def get_approval(conn: sqlite3.Connection, approval_id: str) -> ToolApproval:
    return _load(conn, approval_id)


def approve(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    approval_id: str,
    ctx: Optional[dict] = None,
    reason: Optional[str] = None,
) -> ToolApproval:
    """Execute a pending write/shell tool; flip to executed/failed; emit audit.

    Concurrency-safe: the pending->executing transition is a single atomic UPDATE
    guarded on status='pending'. A second concurrent approver sees rowcount 0 and
    raises, so the deferred adapter runs at most once (TOCTOU guard)."""
    approval = _load(conn, approval_id)  # raises if unknown
    manifest, adapter = registry.get_registry().resolve(approval.tool_name)
    run_id = mission_service.ensure_operator_run(conn, lock)
    now = datetime.datetime.now(datetime.timezone.utc)
    ctx = ctx or {}

    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE tool_approvals SET status = 'executing' "
                "WHERE id = ? AND status = 'pending'",
                (approval_id,),
            )
            claimed = cur.rowcount == 1
    if not claimed:
        current = _load(conn, approval_id)
        raise ToolApprovalError(
            f"approval {approval_id!r} is {current.status!r}, not pending"
        )

    args = json.loads(approval.args or "{}")
    try:
        result = adapter(args, ctx)
    except Exception as exc:  # noqa: BLE001
        result_json = _redact(json.dumps({"error": str(exc)}))
        _set_terminal(conn, lock, approval_id, "failed", result_json, now)
        emit(
            conn, lock, run_id=run_id, event_type="tool_failed", tool_name=approval.tool_name,
            data={"approval_id": approval_id, "tool_name": approval.tool_name, "error": str(exc)},
            policy_result="tool_failed",
        )
        return _load(conn, approval_id)

    status = "executed" if result.ok else "failed"
    result_json = _redact(json.dumps({"ok": result.ok, "output": result.output, "error": result.error}))
    _set_terminal(conn, lock, approval_id, status, result_json, now)
    emit(
        conn, lock, run_id=run_id,
        event_type="tool_completed" if result.ok else "tool_failed",
        tool_name=approval.tool_name,
        data={"approval_id": approval_id, "tool_name": approval.tool_name, "ok": result.ok},
        policy_result=None if result.ok else "tool_failed",
        tool_call_kwargs={
            "tool_name": approval.tool_name, "args": approval.args,
            "result": result.output or result.error or "",
            "policy_allowed": True, "requires_approval": True, "exit_code": result.exit_code,
        },
    )
    return _load(conn, approval_id)


def reject(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    approval_id: str,
    reason: Optional[str] = None,
) -> ToolApproval:
    """Mark a pending approval rejected (atomic claim); emit an audit event. No exec."""
    approval = _load(conn, approval_id)
    run_id = mission_service.ensure_operator_run(conn, lock)
    now = datetime.datetime.now(datetime.timezone.utc)
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE tool_approvals SET status = 'rejected', reason = ?, decided_at = ? "
                "WHERE id = ? AND status = 'pending'",
                (reason, now.isoformat(), approval_id),
            )
            claimed = cur.rowcount == 1
    if not claimed:
        current = _load(conn, approval_id)
        raise ToolApprovalError(
            f"approval {approval_id!r} is {current.status!r}, not pending"
        )
    emit(
        conn, lock, run_id=run_id, event_type="approval", tool_name=approval.tool_name,
        data={"approval_id": approval_id, "tool_name": approval.tool_name,
              "status": "rejected", "reason": reason},
    )
    return _load(conn, approval_id)
