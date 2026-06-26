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

from atlas_core.schemas.tool import (
    ApprovalChannel,
    SessionAllowRule,
    SessionAllowRuleKind,
    ToolApproval,
)

from atlas_runtime import audit_service, mission_service, tool_service

# PERM-07 scope-guard hard rule (do NOT regress):
#   Session allow-rules are a per-claim CONVENIENCE for the initiating active
#   session ONLY. They live exclusively on the `session_allow_rules` table keyed by
#   surface_session_id and bounded to the (workspace_root, surface_kind, tool_name,
#   arg_pattern) 4-tuple. They are NEVER written to policy.py or config.yaml and can
#   NEVER widen what policy.decide() returns for any other session or globally. There
#   is intentionally NO import of a config-write API (config_service.patch_config /
#   policy mutation) in this module — a session rule that escaped into global policy
#   would be an elevation-of-privilege bug (T-10.5-05-WIDEN / T-10.5-05-WILDCARD).

# Closed set of accepted allow-rule kinds (mirrors the SessionAllowRuleKind Literal).
_VALID_RULE_KINDS = ("allow_once", "allow_session", "allow_always")


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


class ApprovalChannelMissingError(ValueError):
    """A headless ('api') surface has no unrevoked approval channel registered.

    Raised/used as the PERM-05 fail-closed signal: an `ask` decision for a headless
    surface with no open approval channel must DENY rather than queue a pending row.
    The denial provenance lives ENTIRELY in the emitted `approval` audit event (no
    tool_approvals row is persisted), by design (PERM-05; not a PERM-01 record gap)."""


class StaleApprovalError(ValueError):
    """A claim is stale/replayed/malformed and must fail closed (SEC-02).

    Covers a mismatched nonce (replay/forgery), an expired approval (now >
    expiry_at), and a malformed claim contract (blank/unknown decision label or a
    blank nonce) — all rejected as a typed error BEFORE the at-most-once UPDATE, so a
    stale claim can never win the race."""


# Closed set of accepted claim decision labels (SEC-02 V5 input validation). An
# unknown label is a malformed contract -> StaleApprovalError before any SQL.
_VALID_CLAIM_DECISIONS = ("approve", "reject")


# ---------------------------------------------------------------------------
# Approval-channel registration (PERM-05 fail-closed gate)
# ---------------------------------------------------------------------------


def has_open_channel(conn: sqlite3.Connection, surface_session_id: str) -> bool:
    """True iff an unrevoked approval_channels row exists for ``surface_session_id``.

    Presence of an unrevoked row is the PERM-05 fail-closed gate: a headless ('api')
    surface may only queue a pending approval when this returns True. Pure read."""
    row = conn.execute(
        "SELECT 1 FROM approval_channels "
        "WHERE surface_session_id = ? AND revoked_at IS NULL LIMIT 1",
        (surface_session_id,),
    ).fetchone()
    return row is not None


def register_channel(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    surface_session_id: str,
    surface_kind: str,
) -> ApprovalChannel:
    """Register (or re-activate) an unrevoked approval channel for a surface session.

    Construct-validate-then-write: build the frozen ``ApprovalChannel`` model first
    (registered_at=now, revoked_at=None) so a malformed input is rejected before any
    SQL, then UPSERT the row (TEXT PK on surface_session_id) inside the lock so a
    re-register clears any prior ``revoked_at`` and re-opens the gate. Returns the
    model."""
    channel = ApprovalChannel(
        surface_session_id=surface_session_id,
        surface_kind=surface_kind,
        registered_at=datetime.datetime.now(datetime.timezone.utc),
        revoked_at=None,
    )
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO approval_channels "
                "(surface_session_id, surface_kind, registered_at, revoked_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(surface_session_id) DO UPDATE SET "
                "surface_kind = excluded.surface_kind, "
                "registered_at = excluded.registered_at, "
                "revoked_at = NULL",
                (
                    channel.surface_session_id,
                    channel.surface_kind,
                    channel.registered_at.isoformat(),
                    None,
                ),
            )
    return channel


def revoke_channel(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    surface_session_id: str,
) -> bool:
    """Revoke the approval channel for ``surface_session_id`` (set revoked_at=now).

    Closes the PERM-05 gate so a subsequent headless ask fails closed again. Returns
    True if an unrevoked row was revoked, False if none was open (idempotent)."""
    now = _now_iso()
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE approval_channels SET revoked_at = ? "
                "WHERE surface_session_id = ? AND revoked_at IS NULL",
                (now, surface_session_id),
            )
            return cur.rowcount > 0


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


def list_outcomes(
    conn: sqlite3.Connection, *, limit: Optional[int] = None
) -> List[ToolApproval]:
    """Cross-surface read-only projection of terminal approval outcomes (AUD-02).

    This is the cross-surface VISIBILITY mechanism (D-022: no pub/sub bus — audit IS
    the mechanism). An observer can see every terminal outcome (executed | rejected |
    failed) with its surface provenance, newest decided first, but gains NO decision
    authority: there is no ``lock`` parameter, no INSERT/UPDATE, and no call into
    claim/approve/reject. A non-owning surface cannot act via this projection — the
    actionable claim path stays strictly session-scoped (``list_actionable``/``claim``).
    Pending rows are intentionally excluded so an observer cannot mistake the read for a
    claimable queue. ``limit`` optionally caps the rows returned. Pure SELECT
    (T-10.5-05-OBSERVER)."""
    sql = (
        f"SELECT {tool_service._COLS} FROM tool_approvals "
        "WHERE status IN ('executed', 'rejected', 'failed') "
        "ORDER BY decided_at DESC"
    )
    params: tuple = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (int(limit),)
    cur = conn.execute(sql, params)
    return [tool_service._row_to_approval(r) for r in cur.fetchall()]


def get_outcome(
    conn: sqlite3.Connection, approval_id: str
) -> Optional[ToolApproval]:
    """Read-only single terminal-outcome view for ``approval_id`` (AUD-02).

    Returns the terminal ToolApproval (executed | rejected | failed) for the id, or
    None if the approval does not exist or is still pending/executing. Pure read: no
    ``lock``, no mutation, no claim/approve/reject call — an observer gains no decision
    authority from it. The returned view carries the redacted args/result the emit
    boundary already produced; the live nonce is part of the persisted row but the
    projection grants no claim handle, so possessing the view cannot resolve anything
    (the claim path enforces ownership + active session independently)."""
    row = conn.execute(
        f"SELECT {tool_service._COLS} FROM tool_approvals "
        "WHERE id = ? AND status IN ('executed', 'rejected', 'failed')",
        (approval_id,),
    ).fetchone()
    if row is None:
        return None
    return tool_service._row_to_approval(row)


# ---------------------------------------------------------------------------
# Session-scoped allow-rule store + consume (PERM-07, hard scope bound)
# ---------------------------------------------------------------------------


def record_allow_rule(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    surface_session_id: str,
    workspace_root: str,
    surface_kind: str,
    tool_name: str,
    arg_pattern: str,
    rule_kind: SessionAllowRuleKind,
) -> SessionAllowRule:
    """Store a scope-bound allow-rule on ``session_allow_rules`` (PERM-07).

    The rule is anchored to one ``surface_session_id`` and bounded to the
    (workspace_root, surface_kind, tool_name, arg_pattern) 4-tuple — there is NO
    global/cross-session row and NO wildcard. Construct-validate-then-write: build the
    frozen ``SessionAllowRule`` first (rejecting a malformed ``rule_kind`` before any
    SQL), then INSERT inside ``with lock: with conn:``.

    CRITICAL (Warning-5 cross-path parity): ``arg_pattern`` MUST be produced by the
    SAME shared normalization helper ``tool_service._normalize_args(args)`` that the
    ``invoke()`` insert path uses for the approval's ``args_normalized`` column, so a
    rule's ``arg_pattern`` is byte-identical to a real approval's ``args_normalized``
    and the ``==`` match in ``match_allow_rule`` is reliable. Callers pass the already
    normalized string here; do NOT hand-roll a second normalization. (See
    ``allow_pattern_for_args`` for the convenience wrapper that calls the shared
    helper.)

    HARD GUARD: this function writes ONLY to ``session_allow_rules``. It never touches
    policy.py or config.yaml and never calls ``policy.decide`` (which stays the global
    read-only authority, unchanged for every other session). A rule recorded for
    session A is invisible to session B's authority (different ``surface_session_id``).
    """
    rule = SessionAllowRule(
        surface_session_id=surface_session_id,
        workspace_root=workspace_root,
        surface_kind=surface_kind,
        tool_name=tool_name,
        arg_pattern=arg_pattern,
        rule_kind=rule_kind,
    )
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO session_allow_rules "
                "(id, surface_session_id, workspace_root, surface_kind, tool_name, "
                " arg_pattern, rule_kind, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rule.id,
                    rule.surface_session_id,
                    rule.workspace_root,
                    rule.surface_kind,
                    rule.tool_name,
                    rule.arg_pattern,
                    rule.rule_kind,
                    rule.created_at.isoformat(),
                ),
            )
    return rule


def allow_pattern_for_args(args: Optional[dict]) -> str:
    """The arg_pattern for an allow-rule covering ``args`` (Warning-5 parity).

    Delegates to ``tool_service._normalize_args`` — the SINGLE source of truth the
    ``invoke()`` insert path uses for ``args_normalized`` — so a rule recorded with
    ``record_allow_rule(arg_pattern=allow_pattern_for_args(args), ...)`` produces a
    byte-identical key to the approval ``invoke({...args})`` persists. Do not
    re-implement json.dumps/redaction here; that would risk a non-matching pattern."""
    return tool_service._normalize_args(args or {})


def match_allow_rule(
    conn: sqlite3.Connection,
    *,
    surface_session_id: str,
    workspace_root: str,
    surface_kind: str,
    tool_name: str,
    args_normalized: str,
) -> Optional[SessionAllowRule]:
    """Return a session-scoped allow-rule that EXACTLY matches the 4-tuple, or None.

    Session-scoped: SELECTs rules for ``surface_session_id`` ONLY — a rule on session
    A can never match a query for session B. Exact 4-tuple match: every one of
    workspace_root, surface_kind, tool_name, and ``arg_pattern == args_normalized``
    must hold — no wildcard widening across workspace, surface, tool, or arg pattern
    (T-10.5-05-WILDCARD). Pure read (no lock, no mutation). Newest rule first so an
    allow_once recorded most recently is the first candidate to consume."""
    row = conn.execute(
        "SELECT id, surface_session_id, workspace_root, surface_kind, tool_name, "
        "arg_pattern, rule_kind, created_at FROM session_allow_rules "
        "WHERE surface_session_id = ? AND workspace_root = ? AND surface_kind = ? "
        "AND tool_name = ? AND arg_pattern = ? "
        "ORDER BY created_at DESC LIMIT 1",
        (
            surface_session_id,
            workspace_root,
            surface_kind,
            tool_name,
            args_normalized,
        ),
    ).fetchone()
    if row is None:
        return None
    return SessionAllowRule(
        id=row[0],
        surface_session_id=row[1],
        workspace_root=row[2],
        surface_kind=row[3],
        tool_name=row[4],
        arg_pattern=row[5],
        rule_kind=row[6],
        created_at=row[7],
    )


def _consume_allow_once(
    conn: sqlite3.Connection, lock: threading.Lock, rule_id: str
) -> None:
    """Delete a matched allow_once rule (consumed on first use). Bounded to the rule
    id, so it can never affect another session's rules. Idempotent."""
    with lock:
        with conn:
            conn.execute(
                "DELETE FROM session_allow_rules WHERE id = ? AND rule_kind = 'allow_once'",
                (rule_id,),
            )


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
    record_rule: Optional[SessionAllowRuleKind] = None,
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

    SEC-02 replay/stale defenses run AFTER ownership + active-session authority but
    BEFORE the at-most-once UPDATE, so a stale/replayed claim can never win the race:
      * malformed contract — a blank/unknown ``decision`` label or a blank ``nonce``
        raises ``StaleApprovalError`` before any DB read;
      * nonce mismatch — ``approval.nonce != nonce`` raises ``StaleApprovalError`` with
        no row mutation;
      * expiry — ``now > approval.expiry_at`` emits a deny ``approval`` audit event
        (reason 'expired') AFTER the lock and raises ``StaleApprovalError``.

    Returns the terminal ToolApproval for the winner."""
    # Malformed-claim guard (SEC-02 V5 input validation) — fail closed BEFORE any SQL.
    if not decision or decision not in _VALID_CLAIM_DECISIONS:
        raise StaleApprovalError(f"unknown claim decision {decision!r}")
    if not nonce or not str(nonce).strip():
        raise StaleApprovalError("claim nonce must be a non-blank string")

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

    # (c) SEC-02 nonce echo — a replayed/forged nonce that does not match the stored
    # per-row nonce is rejected with NO row mutation (runs before the UPDATE).
    if approval.nonce is not None and approval.nonce != nonce:
        raise StaleApprovalError(
            f"nonce mismatch for approval {approval_id!r} (replay/stale)"
        )

    # (d) SEC-02 expiry — a claim after expiry_at is denied before the UPDATE. Emit a
    # deny audit event AFTER releasing any lock (we hold none here) then fail closed.
    if approval.expiry_at is not None:
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        expiry_dt = approval.expiry_at
        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=datetime.timezone.utc)
        if now_dt > expiry_dt:
            run_id = mission_service.ensure_operator_run(conn, lock)
            audit_service.emit(
                conn,
                lock,
                run_id=run_id,
                event_type="approval",
                session_id=surface_session_id,
                tool_name=approval.tool_name,
                data={
                    "approval_id": approval_id,
                    "tool_name": approval.tool_name,
                    "status": "rejected",
                    "decision": decision,
                    "reason": "expired",
                    "surface_kind": approval.surface_kind,
                    "workspace_root": approval.workspace_root,
                },
            )
            raise StaleApprovalError(
                f"approval {approval_id!r} expired at {approval.expiry_at!r}"
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

    # PERM-07 consume path: if the caller requested an allow-rule alongside an
    # approve, record it BOUND to this approval's exact 4-tuple for THIS session only.
    # allow_once is recorded then consumed immediately (it covered this single claim);
    # allow_session/allow_always persist for the session, bounded to the 4-tuple. The
    # rule lives ONLY on session_allow_rules — it never widens global policy/config and
    # cannot match another session/workspace/tool/arg-pattern. arg_pattern reuses the
    # SAME shared normalization helper as the approval's args_normalized (byte-identical
    # match), so a recorded rule actually matches a real re-invocation.
    if (
        decision == "approve"
        and record_rule is not None
        and record_rule in _VALID_RULE_KINDS
    ):
        rule = record_allow_rule(
            conn,
            lock,
            surface_session_id=surface_session_id,
            workspace_root=terminal.workspace_root,
            surface_kind=terminal.surface_kind,
            tool_name=terminal.tool_name,
            arg_pattern=terminal.args_normalized,
            rule_kind=record_rule,
        )
        if record_rule == "allow_once":
            _consume_allow_once(conn, lock, rule.id)

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
    "ApprovalChannelMissingError",
    "StaleApprovalError",
    "has_open_channel",
    "register_channel",
    "revoke_channel",
    "list_actionable",
    "list_outcomes",
    "get_outcome",
    "record_allow_rule",
    "allow_pattern_for_args",
    "match_allow_rule",
    "claim",
    "reconcile_executing_orphans",
]
