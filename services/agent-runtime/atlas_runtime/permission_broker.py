"""Surface-scoped permission broker core (Phase 10.5, plan 10.5-03).

Routes deferred tool approvals to the surface session that initiated them and
exposes the authority-checked, at-most-once ``claim`` the TUI (10.6) and WebUI
(10.7) consume.

Invariants (do NOT regress):

* SINGLE AT-MOST-ONCE AUTHORITY. ``claim`` NEVER runs its own status-flip UPDATE.
  Its only direct UPDATE is the non-status ``decision`` column write (which cannot
  race the at-most-once guard because it leaves ``status='pending'``). The atomic
  ``UPDATE … WHERE id=? AND status='pending'`` (rowcount==1) lives ONLY inside
  ``tool_service.approve()`` / ``tool_service.reject()``; the broker delegates to
  them. The winner's deferred adapter executes exactly once; concurrent losers see
  ``tool_service.ToolApprovalError`` (rowcount==0), re-read the row, and raise a
  typed ``AlreadyDecided`` carrying the winning outcome.

* AUTHORITY READS A COLUMN, NEVER A PID. ``claim`` requires (a) the approval's
  ``surface_session_id`` equals the caller and (b) the owning ``surface_sessions``
  row is ``state='active'`` — read straight off the column. PID/``os.kill`` liveness
  probing is forbidden (broken on Windows; RESEARCH anti-pattern).

* EMIT AFTER THE LOCK. ``audit_service.emit`` re-acquires the lock internally; the
  broker's routing/claim-provenance event is emitted only AFTER any ``with lock:``
  block is released (Pitfall 6 — emitting inside it deadlocks).

* FAIL-CLOSED RECONCILE. ``reconcile_executing_orphans`` flips ``executing`` rows
  with a NULL result to ``failed`` and leaves ``pending`` rows intact; idempotent.

Construct-validate-then-write order and single-redaction (D-002) are inherited from
``tool_service`` — the broker adds no second redaction path.

Scope note: PERM-03/PERM-04 are satisfied here at the CONTRACT level only —
``list_actionable`` is the strictly session-scoped queue the WebUI sidebar will
consume and ``claim`` is the API the TUI prompt will consume. No UI is built in this
phase. The nonce/expiry replay guard (SEC-02) and the PERM-05 fail-closed channel
gate land in Plans 04/05; ``claim`` accepts the ``nonce`` param now and threads it
through without enforcing a mismatch yet.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
from typing import List, Optional

from atlas_core.schemas.tool import ToolApproval

from atlas_runtime import audit_service, mission_service, tool_service


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Typed outcomes / errors
# ---------------------------------------------------------------------------


class AlreadyDecided(Exception):
    """A claim lost the at-most-once race: the approval was already resolved.

    Raised to the losing caller carrying the WINNING outcome (status + decision +
    reason) so the surface can render the resolution without a second DB read. It is
    an Exception subclass (the concurrent-claim contract catches it) and also exposes
    ``already_decided=True`` plus the winning fields as attributes."""

    already_decided: bool = True

    def __init__(
        self,
        status: Optional[str],
        decision: Optional[str],
        reason: Optional[str] = None,
    ) -> None:
        self.status = status
        self.decision = decision
        self.reason = reason
        super().__init__(
            f"approval already decided: status={status!r} decision={decision!r}"
        )


class WrongSessionError(ValueError):
    """The caller does not own the approval (approval.surface_session_id mismatch)."""


class NotActiveSessionError(ValueError):
    """The owning surface session is missing or not in state 'active' (fail-closed)."""


# ---------------------------------------------------------------------------
# Scoped actionable queue (PERM-02/04)
# ---------------------------------------------------------------------------


def list_actionable(
    conn: sqlite3.Connection, *, surface_session_id: str
) -> List[ToolApproval]:
    """Pending, non-expired approvals owned by ``surface_session_id`` — and only
    those. Never another session's rows (strict scope, PERM-02/04). Newest first."""
    cur = conn.execute(
        f"SELECT {tool_service._COLS} FROM tool_approvals "
        "WHERE surface_session_id = ? AND status = 'pending' AND expiry_at > ? "
        "ORDER BY requested_at DESC",
        (surface_session_id, _now_iso()),
    )
    return [tool_service._row_to_approval(r) for r in cur.fetchall()]


def list_outcomes(conn: sqlite3.Connection) -> List[ToolApproval]:
    """Read-only projection of terminal approval outcomes (AUD-02).

    Pure read: performs NO status flip and exposes no mutating verb. Returns every
    approval that has reached a terminal status (executed | rejected | failed),
    newest decided first."""
    cur = conn.execute(
        f"SELECT {tool_service._COLS} FROM tool_approvals "
        "WHERE status IN ('executed', 'rejected', 'failed') "
        "ORDER BY decided_at DESC"
    )
    return [tool_service._row_to_approval(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Authority-checked at-most-once claim (PERM-02 / PERM-06)
# ---------------------------------------------------------------------------


def claim(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    approval_id: str,
    surface_session_id: str,
    decision: str,
    nonce: str,
    ctx: Optional[dict] = None,
    reason: Optional[str] = None,
) -> ToolApproval:
    """Resolve a pending approval for its owning active surface session.

    Authority (fail-closed, before any write):
      (a) the approval must exist and be owned by ``surface_session_id`` else
          ``WrongSessionError``;
      (b) the owning ``surface_sessions`` row must be ``state='active'`` else
          ``NotActiveSessionError`` (column read only — never a PID probe).

    The ``nonce`` is threaded through for the Plan-04 replay guard but not enforced
    here. Resolution delegates the atomic pending→terminal transition to
    ``tool_service.approve()`` (decision='approve') or ``tool_service.reject()``
    (decision='reject') — the SINGLE at-most-once authority. The broker's only direct
    UPDATE is the non-status ``decision`` column write. On a lost race the delegate
    raises ``ToolApprovalError`` (rowcount==0); the loser re-reads the row and raises
    ``AlreadyDecided`` carrying the winning outcome.

    Returns the terminal ToolApproval for the winner. Raises ``ValueError`` for an
    unknown decision label."""
    if decision not in ("approve", "reject"):
        raise ValueError(f"unknown claim decision {decision!r}")

    # (a) ownership — load the approval (raises ToolApprovalError on unknown id).
    approval = tool_service._load(conn, approval_id)
    if approval.surface_session_id != surface_session_id:
        raise WrongSessionError(
            f"approval {approval_id!r} is owned by "
            f"{approval.surface_session_id!r}, not {surface_session_id!r}"
        )

    # (b) active-state authority — read the column, never probe a PID.
    row = conn.execute(
        "SELECT state FROM surface_sessions WHERE id = ?", (surface_session_id,)
    ).fetchone()
    if row is None or row[0] != "active":
        raise NotActiveSessionError(
            f"surface session {surface_session_id!r} is not active "
            f"(state={None if row is None else row[0]!r})"
        )

    # Persist the decision label on the still-pending row. This is a NON-status
    # UPDATE (decision column only), so it cannot race the at-most-once guard.
    with lock:
        with conn:
            conn.execute(
                "UPDATE tool_approvals SET decision = ? "
                "WHERE id = ? AND status = 'pending'",
                (decision, approval_id),
            )

    # Delegate the atomic claim+execute to the single at-most-once authority.
    try:
        if decision == "approve":
            terminal = tool_service.approve(
                conn, lock, approval_id=approval_id, ctx=ctx, reason=reason
            )
        else:
            terminal = tool_service.reject(
                conn, lock, approval_id=approval_id, reason=reason
            )
    except tool_service.ToolApprovalError:
        # Lost the race: the winner already flipped the row out of 'pending'.
        current = tool_service._load(conn, approval_id)
        raise AlreadyDecided(
            status=current.status,
            decision=current.decision,
            reason=current.reason,
        )

    # Winner: emit the broker's routing/claim provenance AFTER the lock is released
    # (approve()/reject() already emitted their terminal tool_completed/approval
    # event; this is the surface-provenance record, not a duplicate terminal emit).
    run_id = mission_service.ensure_operator_run(conn, lock)
    audit_service.emit(
        conn,
        lock,
        run_id=run_id,
        event_type="approval",
        session_id=surface_session_id,
        tool_name=terminal.tool_name,
        data={
            "approval_id": approval_id,
            "tool_name": terminal.tool_name,
            "status": terminal.status,
            "decision": decision,
            "surface_kind": terminal.surface_kind,
            "workspace_root": terminal.workspace_root,
        },
    )
    return terminal


# ---------------------------------------------------------------------------
# Restart reconciliation (PERM-06, fail-closed)
# ---------------------------------------------------------------------------


def reconcile_executing_orphans(
    conn: sqlite3.Connection, lock: threading.Lock
) -> int:
    """Fail-closed startup sweep: flip orphaned ``executing`` approvals to ``failed``.

    An ``executing`` row with a NULL ``result`` is an interrupted in-flight claim (the
    process died between the atomic claim and ``_set_terminal``). Reconcile it to
    ``failed`` with reason 'reconciled_fail_closed'. ``pending`` rows are NEVER swept
    (a fresh restart must still be able to resolve them). Idempotent: a second sweep
    finds no orphans and returns 0. Returns the number of rows flipped."""
    now = _now_iso()
    orphans = conn.execute(
        "SELECT id FROM tool_approvals WHERE status = 'executing' AND result IS NULL"
    ).fetchall()
    if not orphans:
        return 0

    flipped = 0
    ids = [oid for (oid,) in orphans]
    with lock:
        with conn:
            for oid in ids:
                cur = conn.execute(
                    "UPDATE tool_approvals "
                    "SET status = 'failed', reason = ?, decided_at = ? "
                    "WHERE id = ? AND status = 'executing' AND result IS NULL",
                    ("reconciled_fail_closed", now, oid),
                )
                flipped += cur.rowcount

    # Emit provenance AFTER releasing the lock (Pitfall 6).
    if flipped:
        run_id = mission_service.ensure_operator_run(conn, lock)
        audit_service.emit(
            conn,
            lock,
            run_id=run_id,
            event_type="approval",
            data={
                "reconciled": flipped,
                "reason": "reconciled_fail_closed",
                "status": "failed",
            },
        )
    return flipped


__all__ = [
    "AlreadyDecided",
    "WrongSessionError",
    "NotActiveSessionError",
    "list_actionable",
    "list_outcomes",
    "claim",
    "reconcile_executing_orphans",
]
