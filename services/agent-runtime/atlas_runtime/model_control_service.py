"""Pure provider/model/auth/registry/fallback status projection."""
from __future__ import annotations

import json
import sqlite3

from atlas_core.schemas.agent_contract import ModelIdentity
from atlas_core.schemas.control_plane import AtlasConfig, ProviderModelStatus

from atlas_runtime import auth_service, model_registry


def _fallback_status(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute(
            "SELECT data FROM audit_events "
            "WHERE event_type='provider_fallback' "
            "ORDER BY timestamp DESC,rowid DESC LIMIT 1"
        ).fetchone()
    except sqlite3.DatabaseError:
        return "unknown"
    if row is None:
        return "not_used"
    try:
        payload = json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return "unknown"
    return "used" if isinstance(payload, dict) else "unknown"


def _auth_status(
    config: AtlasConfig,
    effective_provider: str,
    registry_row: dict[str, object] | None,
) -> str:
    statuses = auth_service.list_auth_status(config=config)
    for status in statuses:
        if status.provider == effective_provider:
            return status.status
    if registry_row is not None:
        derived = str(registry_row.get("auth_status") or "unknown")
        if derived != "unknown":
            return derived
    return "missing_auth"


def get_provider_model_status(
    conn: sqlite3.Connection,
    config: AtlasConfig,
    *,
    focus_framework: str | None = None,
    session_model: ModelIdentity | None = None,
) -> ProviderModelStatus:
    """Explain configured and effective provider/model state without mutation."""
    configured_provider = config.provider.name
    configured_model = config.provider.model
    effective_provider = configured_provider
    effective_model = configured_model
    source = "config"
    if (focus_framework or "").strip():
        effective_model = focus_framework.strip()
        source = "focus"
    if session_model is not None:
        effective_provider = session_model.provider
        effective_model = session_model.model_id
        source = "session"

    rows = model_registry.list_models_control_plane(conn, active_only=False)
    matching = [
        row
        for row in rows
        if row["model_id"] == effective_model
        and row["provider_id"] == effective_provider
    ]
    active = [
        row
        for row in matching
        if row.get("deactivated_at") is None and row.get("status") == "available"
    ]
    registry_row = active[0] if active else (matching[0] if matching else None)
    if active:
        model_health = "available"
    elif matching:
        model_health = "offline"
    else:
        model_health = "unknown"

    provider_row = conn.execute(
        "SELECT status FROM provider_registry WHERE provider_id=?",
        (effective_provider,),
    ).fetchone()
    if provider_row is not None and provider_row[0]:
        provider_health = str(provider_row[0])
    elif active:
        provider_health = "available"
    elif matching:
        provider_health = "offline"
    else:
        provider_health = "unknown"

    auth_status = _auth_status(config, effective_provider, registry_row)
    remediation_parts: list[str] = []
    if auth_status in {
        "missing_auth",
        "installed_no_auth",
        "needs_api_key",
        "needs_login",
        "expired",
    }:
        remediation_parts.append(
            f"run `atlas auth add {effective_provider}` or configure its env reference"
        )
    if model_health != "available":
        remediation_parts.append(
            f"model {effective_model} is {model_health}; run `atlas models refresh` "
            "or patch provider.model"
        )

    return ProviderModelStatus(
        configured_provider=configured_provider,
        effective_provider=effective_provider,
        configured_model=configured_model,
        effective_model=effective_model,
        source=source,
        auth_status=auth_status,
        provider_health=provider_health,
        model_health=model_health,
        fallback_status=_fallback_status(conn),
        remediation="; ".join(remediation_parts) or None,
    )


__all__ = ["get_provider_model_status"]
