"""Canonical masked configuration control-plane projection and mutations."""
from __future__ import annotations

import json

from atlas_core.schemas.control_plane import (
    AtlasConfig,
    ControlPlaneSnapshot,
    SettingStatus,
)

from atlas_runtime import config_service

_SETTING_METADATA: tuple[tuple[str, bool], ...] = (
    ("provider.name", False),
    ("provider.model", False),
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
    data = config.model_dump()
    data.update(
        {
            "settings": settings,
            "auth": (),
            "effective": None,
            "mock_mode": not bool(
                config_service.resolve_provider(
                    config,
                    focus_framework=focus_framework,
                )["api_key"]
            ),
        }
    )
    return ControlPlaneSnapshot.model_validate(data)


__all__ = ["get_config_snapshot"]
