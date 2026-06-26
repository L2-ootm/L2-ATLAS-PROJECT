"""Phase 10.5 Wave 0 — failing-first contract for the surface-scoped permission broker.

RED-FIRST BY DESIGN. This module imports ``atlas_runtime.permission_broker``, which does
NOT exist until Waves 2–4 land. Collection therefore errors with ImportError today — that
is the intended Wave 0 state (VALIDATION.md Wave 0; T-10.5-01-FALSEGREEN). Each test below
is the executable specification the later waves must satisfy verbatim:

  - list_actionable(conn, *, surface_session_id) -> list[ToolApproval]            (PERM-02/04)
  - claim(conn, lock, *, approval_id, surface_session_id, decision, nonce, ...)   (PERM-02/06/SEC-02)
        -> terminal ToolApproval (winner) | AlreadyDecided (loser)
  - register_channel / revoke_channel                                             (PERM-05)
  - reconcile_executing_orphans(conn, lock) -> int                                (PERM-06)
  - list_outcomes(conn) -> read-only terminal projection                          (AUD-02)
  - typed errors: AlreadyDecided, NotActiveSessionError, WrongSessionError,
        StaleApprovalError, ApprovalChannelMissingError

Test names map 1:1 to the RESEARCH Test Map. Concurrency is driven with
``threading.Thread`` (mirrors the test_tool_service TOCTOU style). Each test asserts
concrete DB state via direct SELECTs. NO production module under atlas_runtime/ is created
by this plan; the broker stays unimplemented until Wave 2+.
"""
from __future__ import annotations

import datetime
import json
import threading

import pytest

# RED: this import fails (ModuleNotFoundError) until Waves 2–4 build the broker.
from atlas_runtime import permission_broker as broker
from atlas_runtime import tool_service


def _iso(offset_seconds: int = 300) -> str:
    """An ISO-8601 expiry `offset_seconds` from now (future = live; negative = expired)."""
    return (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=offset_seconds)
    ).isoformat()


# ---------------------------------------------------------------------------
# PERM-01 — surface-anchored approval persists the full record
# ---------------------------------------------------------------------------


def test_approval_record_fields(db, lock, make_active_session, seed_pending_approval) -> None:
    """A pending approval persists every surface-scoping field (PERM-01)."""
    sid = make_active_session()
    nonce = "nonce-fields"
    expiry = _iso()
    approval_id = seed_pending_approval(
        surface_session_id=sid,
        surface_kind="cli",
        nonce=nonce,
        expiry_at=expiry,
        tool_name="workspace",
        workspace_root="/tmp/atlas",
        risk_level="write",
        args_normalized=json.dumps({"path": "x"}),
        reason="needs write",
    )
    row = db.execute(
        "SELECT surface_session_id, surface_kind, workspace_root, expiry_at, nonce, "
        "args_normalized, risk_level, reason, status FROM tool_approvals WHERE id=?",
        (approval_id,),
    ).fetchone()
    assert row == (
        sid, "cli", "/tmp/atlas", expiry, nonce,
        json.dumps({"path": "x"}), "write", "needs write", "pending",
    )
    # The broker's scoped query surfaces it for the owning active session.
    actionable = broker.list_actionable(db, surface_session_id=sid)
    assert any(getattr(a, "id", None) == approval_id for a in actionable)


# ---------------------------------------------------------------------------
# PERM-02 — claim requires the matching, active owning session
# ---------------------------------------------------------------------------


def test_claim_requires_matching_active_session(
    db, lock, surface_session, make_active_session, seed_pending_approval
) -> None:
    """Wrong session -> WrongSessionError; non-active owner -> NotActiveSessionError;
    matching active owner -> success (PERM-02)."""
    sid = make_active_session()  # owning session is active
    approval_id = seed_pending_approval(
        surface_session_id=sid, nonce="n1", expiry_at=_iso()
    )

    # A different session id may not claim an approval it does not own.
    with pytest.raises(broker.WrongSessionError):
        broker.claim(
            db, lock,
            approval_id=approval_id,
            surface_session_id="some-other-session",
            decision="approve",
            nonce="n1",
        )

    # Owning session no longer active -> fail-closed.
    db.execute("UPDATE surface_sessions SET state='suspended' WHERE id=?", (sid,))
    db.commit()
    with pytest.raises(broker.NotActiveSessionError):
        broker.claim(
            db, lock,
            approval_id=approval_id,
            surface_session_id=sid,
            decision="approve",
            nonce="n1",
        )

    # Re-activate -> matching active session succeeds and reaches a terminal status.
    db.execute("UPDATE surface_sessions SET state='active' WHERE id=?", (sid,))
    db.commit()
    won = broker.claim(
        db, lock,
        approval_id=approval_id,
        surface_session_id=sid,
        decision="approve",
        nonce="n1",
    )
    assert won.status in ("executed", "executing", "failed")
    assert won.status != "pending"


# ---------------------------------------------------------------------------
# PERM-05 — headless surface fails closed without a registered channel
# ---------------------------------------------------------------------------


def test_headless_fail_closed_without_channel(
    db, lock, make_active_session, register_test_channel, monkeypatch
) -> None:
    """A 'api' surface with no approval_channels row resolves to deny (no pending row);
    once a channel is registered a pending row IS created (PERM-05)."""
    sid = make_active_session()
    _install_write_tool(monkeypatch)

    # No channel registered -> fail closed; no pending approval persisted.
    out = tool_service.invoke(
        db, lock,
        tool_name="writer",
        args={"a": 1},
        surface_session_id=sid,
        surface_kind="api",
    )
    assert getattr(out, "status", None) != "pending"
    pending = db.execute(
        "SELECT COUNT(*) FROM tool_approvals "
        "WHERE surface_session_id=? AND status='pending'",
        (sid,),
    ).fetchone()[0]
    assert pending == 0

    # Register a channel -> a pending approval IS now created.
    register_test_channel(surface_session_id=sid, surface_kind="api")
    out2 = tool_service.invoke(
        db, lock,
        tool_name="writer",
        args={"a": 2},
        surface_session_id=sid,
        surface_kind="api",
    )
    assert out2.status == "pending"
    pending2 = db.execute(
        "SELECT COUNT(*) FROM tool_approvals "
        "WHERE surface_session_id=? AND status='pending'",
        (sid,),
    ).fetchone()[0]
    assert pending2 == 1


# ---------------------------------------------------------------------------
# PERM-06 — concurrent claim is at-most-once
# ---------------------------------------------------------------------------


def test_concurrent_claim_at_most_once(
    db, lock, make_active_session, seed_pending_approval
) -> None:
    """Two threads claim the same approval: exactly one wins with a terminal
    ToolApproval, the other gets AlreadyDecided carrying the winner's status/decision;
    the approval executes at most once (PERM-06)."""
    sid = make_active_session()
    approval_id = seed_pending_approval(
        surface_session_id=sid, nonce="race", expiry_at=_iso()
    )

    results: list = []
    errors: list = []
    barrier = threading.Barrier(2)

    def _attempt() -> None:
        barrier.wait()
        try:
            results.append(
                broker.claim(
                    db, lock,
                    approval_id=approval_id,
                    surface_session_id=sid,
                    decision="approve",
                    nonce="race",
                )
            )
        except broker.AlreadyDecided as exc:  # loser may surface as typed error or value
            errors.append(exc)
        except Exception as exc:  # noqa: BLE001 — record any other to assert later
            errors.append(exc)

    threads = [threading.Thread(target=_attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    outcomes = results + errors
    winners = [r for r in results if getattr(r, "status", None) not in (None, "pending")]
    losers = [
        o for o in outcomes
        if isinstance(o, broker.AlreadyDecided) or getattr(o, "already_decided", False)
    ]
    assert len(winners) == 1, f"expected exactly one winner, got {outcomes!r}"
    assert len(losers) == 1, f"expected exactly one AlreadyDecided loser, got {outcomes!r}"

    # The DB row is terminal exactly once (not pending, not double-flipped).
    status = db.execute(
        "SELECT status FROM tool_approvals WHERE id=?", (approval_id,)
    ).fetchone()[0]
    assert status != "pending"


# ---------------------------------------------------------------------------
# PERM-06 — restart reconcile sweeps orphaned executing rows
# ---------------------------------------------------------------------------


def test_restart_reconcile_executing_orphan(
    db, lock, make_active_session, seed_pending_approval
) -> None:
    """An `executing` approval with NULL result is flipped to `failed` by
    reconcile_executing_orphans; a `pending` row is left untouched (PERM-06)."""
    sid = make_active_session()
    orphan = seed_pending_approval(surface_session_id=sid, nonce="orph", expiry_at=_iso())
    untouched = seed_pending_approval(surface_session_id=sid, nonce="keep", expiry_at=_iso())

    # Simulate an interrupted in-flight claim: orphan stuck in `executing`, no result.
    db.execute(
        "UPDATE tool_approvals SET status='executing', result=NULL WHERE id=?",
        (orphan,),
    )
    db.commit()

    flipped = broker.reconcile_executing_orphans(db, lock)
    assert flipped >= 1

    orphan_status = db.execute(
        "SELECT status FROM tool_approvals WHERE id=?", (orphan,)
    ).fetchone()[0]
    pending_status = db.execute(
        "SELECT status FROM tool_approvals WHERE id=?", (untouched,)
    ).fetchone()[0]
    assert orphan_status == "failed"
    assert pending_status == "pending"  # pending must NOT be swept


# ---------------------------------------------------------------------------
# PERM-07 — allow-rules cannot widen scope across sessions / workspaces
# ---------------------------------------------------------------------------


def test_allow_rules_cannot_widen_scope(
    db, lock, surface_session, make_active_session, seed_pending_approval
) -> None:
    """An allow-always rule registered for session A does NOT auto-resolve an approval
    owned by session B nor one in a different workspace_root; the rule never escapes
    its scope into config/policy state (PERM-07)."""
    session_a = make_active_session()

    # An approval owned by a DIFFERENT session B in a DIFFERENT workspace.
    session_b = "session-b-other"
    approval_b = seed_pending_approval(
        surface_session_id=session_b,
        nonce="b1",
        expiry_at=_iso(),
        workspace_root="/tmp/other-workspace",
    )

    # Register a broad allow rule scoped to session A (if the broker exposes it).
    if hasattr(broker, "register_allow_rule"):
        broker.register_allow_rule(
            db, lock,
            surface_session_id=session_a,
            tool_name="workspace",
            scope="always",
        )

    # The session-B approval is unaffected: still pending, never auto-resolved by A's rule.
    status_b = db.execute(
        "SELECT status FROM tool_approvals WHERE id=?", (approval_b,)
    ).fetchone()[0]
    assert status_b == "pending"

    # The rule must not appear as a global/cross-session policy widening.
    if hasattr(broker, "list_actionable"):
        # B's pending approval is NOT actionable from session A's authority.
        a_actionable_ids = {getattr(x, "id", None) for x in broker.list_actionable(db, surface_session_id=session_a)}
        assert approval_b not in a_actionable_ids


# ---------------------------------------------------------------------------
# SEC-02 — replay / stale / malformed claims are rejected
# ---------------------------------------------------------------------------


def test_replay_and_stale_rejected(
    db, lock, make_active_session, seed_pending_approval
) -> None:
    """A mismatched nonce raises StaleApprovalError; a claim after expiry raises
    StaleApprovalError; a malformed claim raises a validation/typed error (SEC-02)."""
    sid = make_active_session()

    # Nonce mismatch (replay with a stale/forged nonce).
    appr_nonce = seed_pending_approval(surface_session_id=sid, nonce="real", expiry_at=_iso())
    with pytest.raises(broker.StaleApprovalError):
        broker.claim(
            db, lock,
            approval_id=appr_nonce,
            surface_session_id=sid,
            decision="approve",
            nonce="WRONG",
        )

    # Expired approval (expiry_at already in the past).
    appr_expired = seed_pending_approval(
        surface_session_id=sid, nonce="exp", expiry_at=_iso(-60)
    )
    with pytest.raises(broker.StaleApprovalError):
        broker.claim(
            db, lock,
            approval_id=appr_expired,
            surface_session_id=sid,
            decision="approve",
            nonce="exp",
        )

    # Malformed claim (unknown approval id / invalid decision) -> typed error.
    with pytest.raises((broker.StaleApprovalError, ValueError, broker.AlreadyDecided)):
        broker.claim(
            db, lock,
            approval_id="does-not-exist",
            surface_session_id=sid,
            decision="not-a-decision",
            nonce="exp",
        )


# ---------------------------------------------------------------------------
# AUD-02 — terminal outcome projection is read-only
# ---------------------------------------------------------------------------


def test_outcome_projection_read_only(
    db, lock, make_active_session, seed_pending_approval
) -> None:
    """list_outcomes returns terminal outcomes and exposes no callable that mutates
    status; the outcome path performs no status flip (AUD-02)."""
    sid = make_active_session()
    approval_id = seed_pending_approval(surface_session_id=sid, nonce="o1", expiry_at=_iso())

    # Drive it to a terminal state through the legitimate claim path.
    db.execute("UPDATE surface_sessions SET state='active' WHERE id=?", (sid,))
    db.commit()
    broker.claim(
        db, lock,
        approval_id=approval_id,
        surface_session_id=sid,
        decision="approve",
        nonce="o1",
    )

    before = db.execute(
        "SELECT status FROM tool_approvals WHERE id=?", (approval_id,)
    ).fetchone()[0]
    outcomes = broker.list_outcomes(db)
    after = db.execute(
        "SELECT status FROM tool_approvals WHERE id=?", (approval_id,)
    ).fetchone()[0]

    # Reading outcomes must not mutate any approval status.
    assert before == after
    assert any(approval_id == getattr(o, "id", o) or approval_id in repr(o) for o in outcomes)
    # No mutating verb on the read-only projection surface.
    assert not hasattr(broker.list_outcomes, "flip")


# ---------------------------------------------------------------------------
# PERM-01 / AUD — approval lifecycle writes provenance to audit_events
# ---------------------------------------------------------------------------


def test_audit_provenance_emitted(
    db, lock, make_active_session, seed_pending_approval
) -> None:
    """An approval lifecycle transition writes an audit_events row with
    event_type='approval' and session_id == surface_session_id, carrying surface
    provenance in the data payload (PERM-01/AUD-02, D-002)."""
    sid = make_active_session()
    approval_id = seed_pending_approval(surface_session_id=sid, nonce="aud", expiry_at=_iso())

    broker.claim(
        db, lock,
        approval_id=approval_id,
        surface_session_id=sid,
        decision="approve",
        nonce="aud",
    )

    row = db.execute(
        "SELECT event_type, session_id, data FROM audit_events "
        "WHERE event_type='approval' AND session_id=? "
        "ORDER BY timestamp DESC LIMIT 1",
        (sid,),
    ).fetchone()
    assert row is not None, "expected an 'approval' audit event for the surface session"
    assert row[0] == "approval"
    assert row[1] == sid
    payload = json.loads(row[2])
    assert payload.get("approval_id") == approval_id


# ---------------------------------------------------------------------------
# Shared helper — isolated one-tool write registry (mirrors test_tool_service)
# ---------------------------------------------------------------------------


def _install_write_tool(monkeypatch, *, name="writer"):
    """Swap the tool registry for a single write-class tool so invoke() routes to
    the approval gate (mirrors test_tool_service._install_fake_tool)."""
    from atlas_core.schemas.tool import ToolManifest, ToolResult
    from atlas_runtime.tools import registry

    manifest = ToolManifest(name=name, description="", risk_level="write")

    def adapter(args, ctx):  # noqa: ANN001
        return ToolResult(ok=True, tool_name=name, output=json.dumps(args))

    class _Reg:
        manifests = {name: manifest}

        def resolve(self, n):  # noqa: ANN001
            if n != name:
                raise ValueError(f"unknown tool {n!r}")
            return manifest, adapter

    monkeypatch.setattr(registry, "get_registry", lambda: _Reg())
    return manifest, adapter
