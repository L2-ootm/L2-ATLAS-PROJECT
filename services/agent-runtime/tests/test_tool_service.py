"""Phase 10.0.4 SC1/SC4 — tool_service: policy chokepoint + approval state machine.

RED until Plan 03 adds `atlas_runtime.tool_service`. This is the single chokepoint
every tool call flows through: read-class tools run immediately and emit
tool_requested -> tool_completed (or tool_failed); write/shell tools short-circuit
to a pending `tool_approvals` row and only execute on explicit approve. Generalizes
the Phase C discord_service pipeline (atomic claim, redact-once, operator-run FK).

Reuses the top-level `db`/`lock` fixtures exactly as test_discord_service does.
"""
from __future__ import annotations

import json

import pytest

from atlas_runtime.audit_service import get_events_for_run


def _install_fake_tool(monkeypatch, *, name="echo", risk_level="read", adapter=None):
    """Swap the tool registry for a one-tool stub so service tests are isolated."""
    from atlas_core.schemas.tool import ToolManifest, ToolResult
    from atlas_runtime.tools import registry

    manifest = ToolManifest(name=name, description="", risk_level=risk_level)
    if adapter is None:
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


def test_invoke_read_emits_requested_then_completed(db, lock, monkeypatch):
    from atlas_runtime import tool_service

    _install_fake_tool(monkeypatch, risk_level="read")
    result = tool_service.invoke(db, lock, tool_name="echo", args={"x": 1})
    assert result.ok
    types = [e.event_type for e in get_events_for_run(db, "operator")]
    assert "tool_requested" in types
    assert "tool_completed" in types


def test_invoke_adapter_error_emits_failed(db, lock, monkeypatch):
    from atlas_runtime import tool_service

    def boom(args, ctx):  # noqa: ANN001
        raise RuntimeError("kaboom")

    _install_fake_tool(monkeypatch, risk_level="read", adapter=boom)
    result = tool_service.invoke(db, lock, tool_name="echo", args={})
    assert not result.ok
    assert any(e.event_type == "tool_failed" for e in get_events_for_run(db, "operator"))


def test_invoke_write_creates_pending_no_exec(db, lock, monkeypatch):
    from atlas_runtime import tool_service

    calls: list = []

    def adapter(args, ctx):  # noqa: ANN001
        calls.append(args)
        from atlas_core.schemas.tool import ToolResult

        return ToolResult(ok=True, tool_name="writer", output="x")

    _install_fake_tool(monkeypatch, name="writer", risk_level="write", adapter=adapter)
    out = tool_service.invoke(db, lock, tool_name="writer", args={"a": 1})
    assert out.status == "pending"
    assert calls == []  # NOT executed inline
    assert len(tool_service.list_approvals(db, status="pending")) == 1


def test_approve_executes_and_emits_completed(db, lock, monkeypatch):
    from atlas_core.schemas.tool import ToolResult
    from atlas_runtime import tool_service

    ran: list = []

    def adapter(args, ctx):  # noqa: ANN001
        ran.append(args)
        return ToolResult(ok=True, tool_name="writer", output="done")

    _install_fake_tool(monkeypatch, name="writer", risk_level="write", adapter=adapter)
    appr = tool_service.invoke(db, lock, tool_name="writer", args={"a": 1})
    done = tool_service.approve(db, lock, approval_id=appr.id)
    assert done.status == "executed"
    assert ran == [{"a": 1}]
    assert any(e.event_type == "tool_completed" for e in get_events_for_run(db, "operator"))


def test_approve_non_pending_raises_atomic_claim(db, lock, monkeypatch):
    """Once terminal, a second approve raises — the atomic claim guard (TOCTOU)."""
    from atlas_runtime import tool_service

    _install_fake_tool(monkeypatch, name="writer", risk_level="write")
    appr = tool_service.invoke(db, lock, tool_name="writer", args={})
    tool_service.approve(db, lock, approval_id=appr.id)
    with pytest.raises(tool_service.ToolApprovalError):
        tool_service.approve(db, lock, approval_id=appr.id)


def test_reject_marks_rejected(db, lock, monkeypatch):
    from atlas_runtime import tool_service

    _install_fake_tool(monkeypatch, name="writer", risk_level="write")
    appr = tool_service.invoke(db, lock, tool_name="writer", args={})
    r = tool_service.reject(db, lock, approval_id=appr.id, reason="no")
    assert r.status == "rejected"


def test_write_args_secret_is_redacted(db, lock, monkeypatch):
    from atlas_runtime import tool_service

    _install_fake_tool(monkeypatch, name="writer", risk_level="write")
    appr = tool_service.invoke(
        db, lock, tool_name="writer", args={"api_key": "sk-supersecretvalue1234567890"}
    )
    stored = tool_service.get_approval(db, appr.id)
    assert "sk-supersecretvalue1234567890" not in (stored.args or "")
