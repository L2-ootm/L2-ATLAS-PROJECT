"""Shared non-visual ownership contract used by CLI/gateway surface adapters."""

from __future__ import annotations

from atlas_core.schemas.control_plane import PermissionConfig
from atlas_core.schemas.tool import ToolManifest, ToolResult
from atlas_runtime import permission_broker, tool_service


def _pending(db, lock, monkeypatch, session_id: str):
    from atlas_runtime.tools import registry

    manifest = ToolManifest(name="writer", risk_level="write")

    def adapter(args, ctx):  # noqa: ANN001
        return ToolResult(ok=True, tool_name="writer", output="done")

    class _Registry:
        def resolve(self, name):  # noqa: ANN001
            return manifest, adapter

    monkeypatch.setattr(registry, "get_registry", lambda: _Registry())
    return tool_service.invoke(
        db,
        lock,
        tool_name="writer",
        args={"path": "note.md"},
        ctx={
            "permission_config": PermissionConfig(preset="manual"),
            "workspace_root": "/tmp/atlas",
        },
        surface_session_id=session_id,
        surface_kind="cli",
    )


def test_actionable_queue_and_claim_share_the_same_owner_anchor(
    db,
    lock,
    monkeypatch,
    make_active_session,
) -> None:
    owner = make_active_session()
    approval = _pending(db, lock, monkeypatch, owner)

    assert [
        row.id
        for row in permission_broker.list_actionable(
            db,
            surface_session_id=owner,
        )
    ] == [approval.id]
    terminal = permission_broker.claim(
        db,
        lock,
        approval_id=approval.id,
        surface_session_id=owner,
        decision="reject",
        nonce=approval.nonce,
        reason="operator denied",
    )

    assert terminal.status == "rejected"
    assert permission_broker.list_actionable(db, surface_session_id=owner) == []
    assert permission_broker.get_outcome(db, approval.id).status == "rejected"


def test_foreign_or_stale_claims_fail_closed(
    db,
    lock,
    monkeypatch,
    make_active_session,
) -> None:
    owner = make_active_session()
    approval = _pending(db, lock, monkeypatch, owner)

    try:
        permission_broker.claim(
            db,
            lock,
            approval_id=approval.id,
            surface_session_id="foreign",
            decision="approve",
            nonce=approval.nonce,
        )
    except permission_broker.WrongSessionError:
        pass
    else:
        raise AssertionError("foreign claim must fail closed")

    try:
        permission_broker.claim(
            db,
            lock,
            approval_id=approval.id,
            surface_session_id=owner,
            decision="approve",
            nonce="stale",
        )
    except permission_broker.StaleApprovalError:
        pass
    else:
        raise AssertionError("stale nonce must fail closed")

    assert tool_service.get_approval(db, approval.id).status == "pending"
