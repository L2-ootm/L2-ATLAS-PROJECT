"""Tests for discord_service — the gated Discord write approval state machine (C-WP4).

discord_api (the sidecar HTTP client) is monkeypatched so nothing is networked.
The `db` fixture applies all migrations (incl. 0012); `lock` is a real Lock.
"""
from __future__ import annotations

import json

import pytest

from atlas_runtime import discord_api, discord_service
from atlas_runtime.audit_service import get_events_for_run


# ---------------------------------------------------------------------------
# propose
# ---------------------------------------------------------------------------


def test_propose_creates_pending_and_audit(db, lock):
    a = discord_service.propose(
        db, lock, action="create_channel", guild_id="g1",
        params={"name": "general", "type": "text"},
    )
    assert a.status == "pending"
    assert a.summary == "create text channel #general"

    pending = discord_service.list_approvals(db, status="pending")
    assert [p.id for p in pending] == [a.id]

    # An approval audit event was emitted on the operator run.
    events = get_events_for_run(db, "operator")
    assert any(e.event_type == "approval" for e in events)


def test_propose_unknown_action_raises(db, lock):
    with pytest.raises(discord_service.DiscordApprovalError):
        discord_service.propose(db, lock, action="nuke", guild_id="g1", params={})


def test_propose_missing_required_param_raises(db, lock):
    with pytest.raises(discord_service.DiscordApprovalError):
        discord_service.propose(db, lock, action="create_channel", guild_id="g1", params={})


def test_propose_edit_requires_target(db, lock):
    with pytest.raises(discord_service.DiscordApprovalError):
        discord_service.propose(db, lock, action="delete_channel", guild_id="g1", params={})


def test_propose_redacts_secret_in_params(db, lock):
    a = discord_service.propose(
        db, lock, action="send_message", guild_id="g1", target_id="c1",
        params={"embed": {"title": "hi", "url": "https://x?token=supersecret"}},
    )
    stored = discord_service.get_approval(db, a.id)
    assert "supersecret" not in stored.params
    assert "REDACTED" in stored.params


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------


def test_approve_executes_and_emits_discord_action(db, lock, monkeypatch):
    calls = {}

    def _create(guild_id, **kw):
        calls["guild_id"] = guild_id
        calls.update(kw)
        return {"id": "555", "name": kw["name"]}

    monkeypatch.setattr(discord_api, "create_channel", _create)

    a = discord_service.propose(
        db, lock, action="create_channel", guild_id="g1", params={"name": "ops"}
    )
    done = discord_service.approve(db, lock, approval_id=a.id)

    assert done.status == "executed"
    assert json.loads(done.result)["id"] == "555"
    assert calls["reason"] == "ATLAS operator approved create_channel"

    events = get_events_for_run(db, "operator")
    assert any(e.event_type == "discord_action" for e in events)


def test_approve_sidecar_error_marks_failed_and_emits_failure(db, lock, monkeypatch):
    def _boom(guild_id, channel_id, **kw):
        raise discord_api.DiscordSidecarError("discord sidecar 403 for /…: Forbidden")

    monkeypatch.setattr(discord_api, "delete_channel", _boom)

    a = discord_service.propose(
        db, lock, action="delete_channel", guild_id="g1", target_id="c9", params={}
    )
    done = discord_service.approve(db, lock, approval_id=a.id)

    assert done.status == "failed"
    assert "Forbidden" in done.result

    events = get_events_for_run(db, "operator")
    assert any(e.event_type == "failure" for e in events)


def test_approve_non_pending_raises(db, lock, monkeypatch):
    monkeypatch.setattr(discord_api, "delete_role", lambda *a, **k: {"success": True})
    a = discord_service.propose(
        db, lock, action="delete_role", guild_id="g1", target_id="r1", params={}
    )
    discord_service.approve(db, lock, approval_id=a.id)
    with pytest.raises(discord_service.DiscordApprovalError):
        discord_service.approve(db, lock, approval_id=a.id)


def test_approve_unknown_id_raises(db, lock):
    with pytest.raises(discord_service.DiscordApprovalError):
        discord_service.approve(db, lock, approval_id="does-not-exist")


def test_approve_claim_guard_blocks_already_claimed(db, lock, monkeypatch):
    # Simulate a concurrent approver having already claimed the row (status set to
    # 'executing'): the atomic UPDATE ... WHERE status='pending' affects 0 rows,
    # so this approver must refuse rather than double-execute.
    monkeypatch.setattr(discord_api, "delete_channel", lambda *a, **k: {"success": True})
    a = discord_service.propose(
        db, lock, action="delete_channel", guild_id="g1", target_id="c1", params={}
    )
    db.execute("UPDATE discord_approvals SET status='executing' WHERE id=?", (a.id,))
    db.commit()
    with pytest.raises(discord_service.DiscordApprovalError):
        discord_service.approve(db, lock, approval_id=a.id)


def test_approve_reason_override_reaches_sidecar(db, lock, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        discord_api, "create_channel",
        lambda g, **kw: seen.update(kw) or {"id": "1", "name": kw["name"]},
    )
    a = discord_service.propose(
        db, lock, action="create_channel", guild_id="g1", params={"name": "ops"}
    )
    discord_service.approve(db, lock, approval_id=a.id, reason="ticket-42 cleanup")
    assert seen["reason"] == "ticket-42 cleanup"


# ---------------------------------------------------------------------------
# reject
# ---------------------------------------------------------------------------


def test_reject_marks_rejected_and_emits(db, lock):
    a = discord_service.propose(
        db, lock, action="create_role", guild_id="g1", params={"name": "mod"}
    )
    done = discord_service.reject(db, lock, approval_id=a.id, reason="not now")
    assert done.status == "rejected"
    assert done.reason == "not now"
    assert discord_service.list_approvals(db, status="pending") == []


def test_reject_non_pending_raises(db, lock):
    a = discord_service.propose(
        db, lock, action="create_role", guild_id="g1", params={"name": "mod"}
    )
    discord_service.reject(db, lock, approval_id=a.id)
    with pytest.raises(discord_service.DiscordApprovalError):
        discord_service.reject(db, lock, approval_id=a.id)


def test_execute_routes_target_and_params(db, lock, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        discord_api, "set_permissions",
        lambda g, c, **kw: seen.update({"g": g, "c": c, **kw}) or {"success": True},
    )
    a = discord_service.propose(
        db, lock, action="set_permissions", guild_id="g1", target_id="c1",
        params={"role_id": "r1", "allow": ["view_channel"], "deny": ["send_messages"]},
    )
    discord_service.approve(db, lock, approval_id=a.id)
    assert seen["g"] == "g1" and seen["c"] == "c1"
    assert seen["role_id"] == "r1"
    assert seen["allow"] == ["view_channel"]
