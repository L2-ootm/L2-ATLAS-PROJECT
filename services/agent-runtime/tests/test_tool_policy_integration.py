"""Tool-service integration with the shared Phase 10.7 policy authority."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from atlas_core.schemas.control_plane import PermissionConfig
from atlas_core.schemas.tool import ToolManifest, ToolResult
from atlas_runtime import permission_broker, tool_service


def _install(
    monkeypatch,
    calls: list[dict],
    *,
    name: str = "writer",
    risk: str = "write",
    capability: str = "filesystem.write",
) -> None:
    from atlas_runtime.tools import registry

    manifest = ToolManifest(
        name=name,
        risk_level=risk,
        permissions=[capability],
    )

    def adapter(args, ctx):  # noqa: ANN001
        calls.append(args)
        return ToolResult(ok=True, tool_name=name, output="done")

    class _Registry:
        def resolve(self, tool_name):  # noqa: ANN001
            if tool_name != name:
                raise ValueError(tool_name)
            return manifest, adapter

    monkeypatch.setattr(registry, "get_registry", lambda: _Registry())


def test_manual_ask_persists_policy_receipt_without_execution(
    db,
    lock,
    monkeypatch,
) -> None:
    calls: list[dict] = []
    _install(monkeypatch, calls)

    approval = tool_service.invoke(
        db,
        lock,
        tool_name="writer",
        args={"path": "notes.md"},
        ctx={"permission_config": PermissionConfig(preset="manual")},
        surface_session_id="surface-policy",
        surface_kind="webui",
    )

    assert approval.status == "pending"
    assert calls == []
    receipt = json.loads(approval.policy_receipt)
    assert receipt["decision"] == "ask"
    assert receipt["reason_code"] == "manual_approval_required"
    stored = tool_service.get_approval(db, approval.id)
    assert stored.policy_receipt == approval.policy_receipt


def test_pre_migration_approval_row_loads_with_nullable_receipt(db) -> None:
    from atlas_core.schemas.tool import ToolApproval

    legacy = ToolApproval(tool_name="legacy-writer", risk_level="write")
    db.execute(
        "INSERT INTO tool_approvals "
        "(id, tool_name, risk_level, args, summary, status, reason, result, run_id, "
        "requested_at, decided_at, surface_session_id, surface_kind, workspace_root, "
        "expiry_at, decision, nonce, args_normalized) "
        "VALUES (:id, :tool_name, :risk_level, :args, :summary, :status, :reason, "
        ":result, :run_id, :requested_at, :decided_at, :surface_session_id, "
        ":surface_kind, :workspace_root, :expiry_at, :decision, :nonce, "
        ":args_normalized)",
        legacy.model_dump(),
    )
    db.commit()

    assert tool_service.get_approval(db, legacy.id).policy_receipt is None


def test_runtime_remains_safe_while_existing_db_is_pending_migration_0018(
    monkeypatch,
) -> None:
    from atlas_runtime import db as db_service
    from atlas_runtime.tools import registry

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    migrations = sorted(
        path for path in db_service.MIGRATIONS_DIR.glob("*.sql") if path.name < "0018"
    )
    for path in migrations:
        conn.executescript(Path(path).read_text(encoding="utf-8"))

    manifest = ToolManifest(
        name="legacy-writer",
        risk_level="write",
        permissions=["filesystem.write"],
    )

    def adapter(args, ctx):  # noqa: ANN001
        return ToolResult(ok=True, tool_name="legacy-writer", output="done")

    class _Registry:
        def resolve(self, name):  # noqa: ANN001
            return manifest, adapter

    monkeypatch.setattr(registry, "get_registry", lambda: _Registry())
    approval = tool_service.invoke(
        conn,
        threading.Lock(),
        tool_name="legacy-writer",
        args={"path": "note.md"},
        ctx={"permission_config": PermissionConfig(preset="manual")},
    )

    assert approval.policy_receipt is not None
    assert tool_service.get_approval(conn, approval.id).policy_receipt is None
    audit = conn.execute(
        "SELECT data FROM audit_events WHERE event_type='approval' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()[0]
    assert '"policy_receipt"' in audit
    conn.close()


def test_full_autonomy_executes_non_hardline_action_inline(
    db,
    lock,
    monkeypatch,
) -> None:
    calls: list[dict] = []
    _install(monkeypatch, calls)

    result = tool_service.invoke(
        db,
        lock,
        tool_name="writer",
        args={"path": "notes.md"},
        ctx={"permission_config": PermissionConfig(preset="full_autonomy")},
    )

    assert result.ok is True
    assert calls == [{"path": "notes.md"}]
    assert tool_service.list_approvals(db, status="pending") == []


def test_explicit_policy_deny_never_creates_executable_approval(
    db,
    lock,
    monkeypatch,
) -> None:
    calls: list[dict] = []
    _install(monkeypatch, calls)

    result = tool_service.invoke(
        db,
        lock,
        tool_name="writer",
        args={"path": "notes.md"},
        ctx={
            "permission_config": PermissionConfig.model_validate(
                {
                    "preset": "full_autonomy",
                    "rules": [
                        {
                            "id": "deny-writes",
                            "effect": "deny",
                            "selector": {"risks": ["write"]},
                        }
                    ],
                }
            )
        },
    )

    assert result.ok is False
    assert result.error == "master_rule_denied"
    assert calls == []
    assert tool_service.list_approvals(db, status="all") == []


def test_hardline_deny_beats_full_autonomy_and_forged_scoped_allow(
    db,
    lock,
    monkeypatch,
) -> None:
    calls: list[dict] = []
    _install(
        monkeypatch,
        calls,
        name="shell",
        risk="shell",
        capability="command.execute",
    )

    result = tool_service.invoke(
        db,
        lock,
        tool_name="shell",
        args={"command": "format C: /Q"},
        ctx={
            "permission_config": PermissionConfig(preset="full_autonomy"),
            "scoped_allow_rule_id": "forged-rule",
        },
    )

    assert result.ok is False
    assert result.error == "hardline_block_device"
    assert calls == []


def test_exact_session_allow_rule_resolves_manual_ask(
    db,
    lock,
    monkeypatch,
    surface_session,
    make_active_session,
) -> None:
    calls: list[dict] = []
    _install(monkeypatch, calls)
    session_id = make_active_session()
    args = {"path": "notes.md"}
    permission_broker.record_allow_rule(
        db,
        lock,
        surface_session_id=session_id,
        workspace_root="/tmp/atlas",
        surface_kind="cli",
        tool_name="writer",
        arg_pattern=permission_broker.allow_pattern_for_args(args),
        rule_kind="allow_once",
    )

    result = tool_service.invoke(
        db,
        lock,
        tool_name="writer",
        args=args,
        ctx={
            "permission_config": PermissionConfig(preset="manual"),
            "workspace_root": "/tmp/atlas",
        },
        surface_session_id=session_id,
        surface_kind="cli",
    )

    assert result.ok is True
    assert calls == [args]
    assert (
        permission_broker.match_allow_rule(
            db,
            surface_session_id=session_id,
            workspace_root="/tmp/atlas",
            surface_kind="cli",
            tool_name="writer",
            args_normalized=permission_broker.allow_pattern_for_args(args),
        )
        is None
    )
