"""Frozen, JSON-stable contracts for the ATLAS control plane."""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas_core.schemas.agent_contract import PermissionMode

_ENV_REFERENCE = re.compile(r"^env:[A-Za-z_][A-Za-z0-9_]*$")


class _FrozenControlPlaneModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        extra="forbid",
    )


class ProviderConfig(_FrozenControlPlaneModel):
    name: str = "openrouter"
    model: str = "anthropic/claude-sonnet-4"
    # How this provider's credentials are sourced (multi-mode provider mesh).
    # api_key: direct key (env:VAR or ATLAS auth store) — the back-compat default.
    # oauth_import: import an external OAuth login (e.g. Codex/ChatGPT ~/.codex).
    # claude_code: run on the local Claude Code subscription session (no key).
    # freellmapi: free OpenAI-compatible endpoint via base_url (privacy-cost).
    auth_mode: Literal["api_key", "oauth_import", "claude_code", "freellmapi"] = (
        "api_key"
    )
    api_key: str = ""
    base_url: str | None = None

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key_reference(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if value != value.strip():
            raise ValueError("provider.api_key reference must not contain outer whitespace")
        if value and not _ENV_REFERENCE.fullmatch(value):
            raise ValueError(
                "provider.api_key must be empty or an env:VAR_NAME reference"
            )
        return value


class RuntimeConfig(_FrozenControlPlaneModel):
    default_agent: str = "native"
    iteration_budget: int = Field(default=90, ge=1)
    compression: str = "auto"


class GatewayConfig(_FrozenControlPlaneModel):
    rust_port: int = Field(default=8484, ge=1, le=65535)
    messaging_enabled: bool = False
    messaging_port: int = Field(default=8585, ge=1, le=65535)


class CockpitConfig(_FrozenControlPlaneModel):
    port: int = Field(default=3000, ge=1, le=65535)
    branding: str = "atlas"


class ContextConfig(_FrozenControlPlaneModel):
    token_budget: int = Field(default=8000, ge=1)
    enable_semantic: bool = True
    enable_skills: bool = True


class PermissionConfig(_FrozenControlPlaneModel):
    mode: PermissionMode = "ask"
    # Phase 10.5 surface-scoped broker defaults (PERM-01/SEC-02). Bounded ints via
    # Field(ge=...) matching the RuntimeConfig/GatewayConfig convention. Defaults
    # apply to existing config.yaml automatically via model_validate.
    approval_ttl_seconds: int = Field(default=300, ge=1)
    fail_closed_on_disconnect: bool = True


class ModulesConfig(_FrozenControlPlaneModel):
    wiki: bool = True
    graph: bool = True
    cashflow: bool = False

    def __getitem__(self, key: str) -> bool:
        """Keep the established ``config.modules["wiki"]`` read interface."""
        try:
            value = getattr(self, key)
        except AttributeError as exc:
            raise KeyError(key) from exc
        if not isinstance(value, bool):
            raise KeyError(key)
        return value


class AtlasConfig(_FrozenControlPlaneModel):
    schema_version: Literal[1] = 1
    revision: int = Field(default=0, ge=0)
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    cockpit: CockpitConfig = Field(default_factory=CockpitConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    permission: PermissionConfig = Field(default_factory=PermissionConfig)
    modules: ModulesConfig = Field(default_factory=ModulesConfig)


class ConfigPatchRequest(_FrozenControlPlaneModel):
    expected_revision: int = Field(ge=0)
    changes_json: str
    source_surface: str | None = None
    source_session_id: str | None = None

    @field_validator("changes_json")
    @classmethod
    def validate_changes_json(cls, value: str) -> str:
        try:
            changes = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("changes_json must contain valid JSON") from exc
        if not isinstance(changes, dict):
            raise ValueError("changes_json must contain a JSON object")
        return value

    def changes(self) -> dict[str, object]:
        return json.loads(self.changes_json)


class SettingStatus(_FrozenControlPlaneModel):
    path: str
    configured_json: str
    effective_json: str
    source: str
    validation_status: str
    restart_required: bool
    remediation: str | None = None


class AuthStatus(_FrozenControlPlaneModel):
    provider: str
    auth_type: str
    status: str
    source: str
    health: str
    updated_at: str | None = None
    redacted_hint: str = ""
    remediation: str | None = None


class ProviderModelStatus(_FrozenControlPlaneModel):
    configured_provider: str
    effective_provider: str
    configured_model: str
    effective_model: str
    source: str
    auth_status: str
    provider_health: str
    model_health: str
    fallback_status: str
    remediation: str | None = None


class ControlPlaneSnapshot(AtlasConfig):
    settings: tuple[SettingStatus, ...] = ()
    auth: tuple[AuthStatus, ...] = ()
    effective: ProviderModelStatus | None = None
    mock_mode: bool = True


class ControlPlaneError(ValueError):
    """Expected control-plane failure with a stable, secret-safe payload."""

    def __init__(
        self,
        code: str,
        message: str,
        remediation: str,
        *,
        current_revision: int | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation
        self.current_revision = current_revision
        self.field = field

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "message": self.message,
            "remediation": self.remediation,
        }
        if self.current_revision is not None:
            payload["current_revision"] = self.current_revision
        if self.field is not None:
            payload["field"] = self.field
        return payload


__all__ = [
    "AtlasConfig",
    "AuthStatus",
    "CockpitConfig",
    "ConfigPatchRequest",
    "ContextConfig",
    "ControlPlaneError",
    "ControlPlaneSnapshot",
    "GatewayConfig",
    "ModulesConfig",
    "PermissionConfig",
    "ProviderConfig",
    "ProviderModelStatus",
    "RuntimeConfig",
    "SettingStatus",
]
