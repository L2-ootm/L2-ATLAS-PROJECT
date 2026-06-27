"""Native permission prompt: approve once / scoped allow / reject / cancel (TUI-06).

RED until atlas_runtime.tui.permission_ui exists (Wave 1+).
"""
from __future__ import annotations

import datetime
import uuid

import pytest

from atlas_runtime import permission_broker
from atlas_runtime.tui.permission_ui import resolve_approval_choice


def _seed(db, seed_pending_approval, make_active_session, surface_session) -> tuple[str, str]:
    session_id = make_active_session()
    nonce = str(uuid.uuid4())
    expiry = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
    ).isoformat()
    approval_id = seed_pending_approval(
        surface_session_id=session_id, nonce=nonce, expiry_at=expiry
    )
    return session_id, approval_id


def test_approve_once_calls_claim_without_allow_rule(
    db, seed_pending_approval, make_active_session, surface_session, monkeypatch
):
    """TUI-06: 'approve once' calls permission_broker.claim, never record_allow_rule."""
    session_id, approval_id = _seed(db, seed_pending_approval, make_active_session, surface_session)
    calls = {"claim": [], "record_allow_rule": []}
    monkeypatch.setattr(
        "atlas_runtime.tui.permission_ui.permission_broker.claim",
        lambda *a, **kw: calls["claim"].append(kw),
    )
    monkeypatch.setattr(
        "atlas_runtime.tui.permission_ui.permission_broker.record_allow_rule",
        lambda *a, **kw: calls["record_allow_rule"].append(kw),
    )
    resolve_approval_choice(
        db, approval_id=approval_id, surface_session_id=session_id, choice="approve_once"
    )
    assert len(calls["claim"]) == 1
    assert calls["record_allow_rule"] == []


def test_scoped_allow_calls_claim_then_record_allow_rule(
    db, seed_pending_approval, make_active_session, surface_session, monkeypatch
):
    """TUI-06: 'scoped allow' calls claim AND record_allow_rule (in that order)."""
    session_id, approval_id = _seed(db, seed_pending_approval, make_active_session, surface_session)
    order = []
    monkeypatch.setattr(
        "atlas_runtime.tui.permission_ui.permission_broker.claim",
        lambda *a, **kw: order.append("claim"),
    )
    monkeypatch.setattr(
        "atlas_runtime.tui.permission_ui.permission_broker.record_allow_rule",
        lambda *a, **kw: order.append("record_allow_rule"),
    )
    resolve_approval_choice(
        db, approval_id=approval_id, surface_session_id=session_id, choice="allow_scoped"
    )
    assert order == ["claim", "record_allow_rule"]


def test_reject_calls_claim_reject(
    db, seed_pending_approval, make_active_session, surface_session, monkeypatch
):
    """TUI-06: 'reject' calls claim with decision='reject'."""
    session_id, approval_id = _seed(db, seed_pending_approval, make_active_session, surface_session)
    calls = []
    monkeypatch.setattr(
        "atlas_runtime.tui.permission_ui.permission_broker.claim",
        lambda *a, **kw: calls.append(kw),
    )
    resolve_approval_choice(
        db, approval_id=approval_id, surface_session_id=session_id, choice="reject"
    )
    assert calls[0]["decision"] == "reject"


def test_cancel_does_not_call_claim(
    db, seed_pending_approval, make_active_session, surface_session, monkeypatch
):
    """TUI-06: 'cancel' is a TUI-local dismissal — never calls the broker."""
    session_id, approval_id = _seed(db, seed_pending_approval, make_active_session, surface_session)
    calls = []
    monkeypatch.setattr(
        "atlas_runtime.tui.permission_ui.permission_broker.claim",
        lambda *a, **kw: calls.append(kw),
    )
    resolve_approval_choice(
        db, approval_id=approval_id, surface_session_id=session_id, choice="cancel"
    )
    assert calls == []


def test_headless_missing_channel_fails_closed(
    db, seed_pending_approval, make_active_session, surface_session
):
    """TUI-06: a headless surface with no registered approval_channels row fails closed."""
    session_id, approval_id = _seed(db, seed_pending_approval, make_active_session, surface_session)
    with pytest.raises(permission_broker.ApprovalChannelMissingError):
        resolve_approval_choice(
            db,
            approval_id=approval_id,
            surface_session_id=session_id,
            choice="approve_once",
            headless=True,
        )
