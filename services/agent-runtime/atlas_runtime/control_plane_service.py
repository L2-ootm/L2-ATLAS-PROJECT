"""Canonical masked configuration control-plane projection and mutations."""
from __future__ import annotations

import json
import pathlib
import sqlite3
import threading
from collections.abc import Mapping

from atlas_core.schemas.control_plane import (
    AtlasConfig,
    ControlPlaneError,
    ControlPlaneSnapshot,
    SettingStatus,
)

from atlas_runtime import (
    audit_service,
    auth_service,
    config_service,
    mission_service,
    model_control_service,
)

_SETTING_METADATA: tuple[tuple[str, bool], ...] = (
    ("provider.name", False),
    ("provider.model", False),
    ("provider.auth_mode", False),
    ("provider.api_key", False),
    ("provider.base_url", False),
    ("runtime.default_agent", False),
    ("runtime.iteration_budget", False),
    ("runtime.compression", False),
    ("gateway.rust_port", True),
    ("gateway.messaging_enabled", True),
    ("gateway.messaging_port", True),
    ("cockpit.port", True),
    ("cockpit.branding", False),
    ("context.token_budget", False),
    ("context.enable_semantic", False),
    ("context.enable_skills", False),
    ("permission.mode", False),
    ("permission.preset", False),
    ("permission.rules", False),
    ("permission.profiles", False),
    ("permission.workspace_only", False),
    ("permission.atlas_maintenance_enabled", False),
    ("permission.maintenance_roots", False),
    ("permission.approval_ttl_seconds", False),
    ("permission.decision_timeout_seconds", False),
    ("permission.heartbeat_interval_seconds", False),
    ("permission.fail_closed_on_disconnect", False),
    ("modules.wiki", False),
    ("modules.graph", False),
    ("modules.cashflow", False),
)


def _json_value(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _setting_status(
    config: AtlasConfig,
    path: str,
    *,
    restart_required: bool,
    focus_framework: str | None,
) -> SettingStatus:
    configured = config_service.get_value(config, path)
    effective = configured
    source = "config"
    remediation: str | None = None

    if path == "provider.model" and (focus_framework or "").strip():
        effective = focus_framework.strip()
        source = "focus"
    elif path == "provider.name":
        effective = config_service.resolve_provider(
            config,
            focus_framework=focus_framework,
        )["provider"]
    elif path == "provider.api_key":
        effective = bool(config_service.resolve_provider(config)["api_key"])
        if configured:
            source = "env"
            if not effective:
                remediation = (
                    f"set {str(configured)[len('env:') :]} before starting ATLAS"
                )
        else:
            source = "default"
            remediation = "configure an env:VAR reference or use `atlas auth add`"

    return SettingStatus(
        path=path,
        configured_json=_json_value(configured),
        effective_json=_json_value(effective),
        source=source,
        validation_status="valid",
        restart_required=restart_required,
        remediation=remediation,
    )


def get_config_snapshot(
    config: AtlasConfig | None = None,
    *,
    focus_framework: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> ControlPlaneSnapshot:
    """Return one backward-compatible, self-explaining masked config snapshot."""
    config = config or config_service.load_config()
    settings = tuple(
        _setting_status(
            config,
            path,
            restart_required=restart_required,
            focus_framework=focus_framework,
        )
        for path, restart_required in _SETTING_METADATA
    )
    auth = auth_service.list_auth_status(config=config)
    ephemeral = conn is None
    status_conn = conn or sqlite3.connect(":memory:")
    try:
        effective = model_control_service.get_provider_model_status(
            status_conn,
            config,
            focus_framework=focus_framework,
        )
    finally:
        if ephemeral:
            status_conn.close()
    data = config.model_dump()
    data.update(
        {
            "settings": settings,
            "auth": auth,
            "effective": effective,
            "mock_mode": not bool(
                config_service.resolve_provider(
                    config,
                    focus_framework=focus_framework,
                )["api_key"]
            ),
        }
    )
    return ControlPlaneSnapshot.model_validate(data)


def _restart_required(path: str) -> bool:
    return dict(_SETTING_METADATA).get(path, False)


def patch(
    conn: sqlite3.Connection,
    audit_lock: threading.Lock,
    *,
    expected_revision: int,
    changes: Mapping[str, object],
    source_surface: str | None = None,
    source_session_id: str | None = None,
    path: pathlib.Path | None = None,
    focus_framework: str | None = None,
) -> ControlPlaneSnapshot:
    """Commit one optimistic config patch, then emit its masked audit event."""
    before = config_service.load_config(path)
    try:
        updated = config_service.patch_config(
            expected_revision=expected_revision,
            changes=changes,
            path=path,
        )
    except ControlPlaneError as exc:
        if exc.code == "permission_profile_widening":
            run_id = mission_service.ensure_operator_run(conn, audit_lock)
            audit_service.emit(
                conn,
                audit_lock,
                run_id=run_id,
                event_type="failure",
                session_id=source_session_id,
                data={
                    "reason": exc.code,
                    "changed_paths": sorted(changes),
                    "source_surface": source_surface or "service",
                    "source_session_id": source_session_id,
                },
                policy_result=exc.code,
            )
        raise
    changed_paths = sorted(changes)
    before_values = {
        changed_path: config_service.get_value(before, changed_path)
        for changed_path in changed_paths
    }
    after_values = {
        changed_path: config_service.get_value(updated, changed_path)
        for changed_path in changed_paths
    }
    reload_metadata = {
        changed_path: {
            "restart_required": _restart_required(changed_path),
            "visibility": (
                "restart"
                if _restart_required(changed_path)
                else "next_read_or_new_execution"
            ),
        }
        for changed_path in changed_paths
    }
    try:
        run_id = mission_service.ensure_operator_run(conn, audit_lock)
        audit_service.emit(
            conn,
            audit_lock,
            run_id=run_id,
            event_type="config_change",
            session_id=source_session_id,
            data={
                "revision": updated.revision,
                "changed_paths": changed_paths,
                "before": before_values,
                "after": after_values,
                "reload": reload_metadata,
                "source_surface": source_surface or "service",
                "source_session_id": source_session_id,
            },
        )
    except Exception as exc:
        raise ControlPlaneError(
            "config_audit_failed",
            (
                f"config revision {updated.revision} committed but its "
                "audit event failed"
            ),
            (
                f"revision {updated.revision} is committed; inspect the audit "
                "database and reconcile this change before retrying"
            ),
            current_revision=updated.revision,
        ) from exc
    return get_config_snapshot(
        updated,
        focus_framework=focus_framework,
        conn=conn,
    )


__all__ = ["get_config_snapshot", "patch"]
