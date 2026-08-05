"""Frozen, JSON-stable contracts for the ATLAS control plane."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from atlas_core.schemas.agent_contract import PermissionMode

_ENV_REFERENCE = re.compile(r"^env:[A-Za-z_][A-Za-z0-9_]*$")
_CONTROL_PLANE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,95}$")
_CONFIG_PATH_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_MAX_CONFIG_RECEIPT_CHANGES = 64
_MAX_CONFIG_RECEIPT_PATH_LENGTH = 128
_MAX_CONFIG_RECEIPT_VALUE_LENGTH = 512
_SECRET_VALUE_RE = re.compile(
    r"(?:\bBearer\s+\S+|\bsk-[A-Za-z0-9_-]{8,}|\bgh[oprsu]_[A-Za-z0-9]{8,})",
    re.IGNORECASE,
)
_SECRET_PATH_SEGMENTS = frozenset(
    {"api_key", "credential", "credentials", "owner_token", "password", "secret", "token"}
)


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
    auth_mode: Literal["api_key", "oauth_import", "claude_code", "freellmapi"] = "api_key"
    api_key: str = ""
    base_url: str | None = None
    # Reasoning effort forwarded to providers that support it (the foundation
    # clamps per provider). Empty = provider default.
    reasoning_effort: Literal["", "minimal", "low", "medium", "high"] = ""

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key_reference(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if value != value.strip():
            raise ValueError("provider.api_key reference must not contain outer whitespace")
        if value and not _ENV_REFERENCE.fullmatch(value):
            raise ValueError("provider.api_key must be empty or an env:VAR_NAME reference")
        return value


class FunctionsConfig(_FrozenControlPlaneModel):
    """Function-slot model routing for foundation side tasks.

    With autoconfig on, the curator and auxiliary slots bind to the lightest
    model available on the active provider mesh (e.g. Codex -> gpt-5.4-mini).
    Overrides use "provider/model" form and always win over autoconfig.
    """

    autoconfig: bool = True
    curator_model: str = ""
    auxiliary_model: str = ""
    # Empty deliberately means inherit the initiating chat session model.
    # Completion judgement is a correctness role, not a light auxiliary role.
    judge_model: str = ""


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
    enable_brain: bool = True
    # Inject the operator context (Current Focus, goal tree, Operating Contract)
    # into agent runs. Off = runs start from the bare prompt; per-run override
    # via ATLAS_SKIP_CONTEXT=1 or `atlas --no-context`.
    inject_operator_context: bool = True


PermissionPreset = Literal["manual", "smart", "full_autonomy"]
PermissionEffect = Literal["allow", "ask", "deny"]
PermissionDecision = Literal["allow", "ask", "deny"]
PermissionRuleScope = Literal["once", "session", "durable"]
PermissionRisk = Literal["read", "write", "shell"]
PermissionSourceLayer = Literal[
    "hardline",
    "master",
    "profile",
    "scoped_allow",
    "default",
]

_POLICY_ID_RE = _CONTROL_PLANE_ID_RE
_PRESET_RANK: dict[str, int] = {
    "manual": 0,
    "smart": 1,
    "full_autonomy": 2,
}


class PermissionRuleSelector(_FrozenControlPlaneModel):
    """Typed, data-only facts used by one ordered permission rule."""

    tools: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    risks: tuple[PermissionRisk, ...] = ()
    command_patterns: tuple[str, ...] = ()
    path_patterns: tuple[str, ...] = ()
    surfaces: tuple[str, ...] = ()
    agents: tuple[str, ...] = ()
    workspaces: tuple[str, ...] = ()
    projects: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()


class PermissionPolicyRule(_FrozenControlPlaneModel):
    """One deterministic master/profile policy rule."""

    id: str
    effect: PermissionEffect
    selector: PermissionRuleSelector = Field(default_factory=PermissionRuleSelector)
    scope: PermissionRuleScope = "durable"
    description: str = ""
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def validate_rule_id(cls, value: str) -> str:
        if not _POLICY_ID_RE.fullmatch(value):
            raise ValueError(
                "policy rule id must be lowercase and contain only letters, "
                "digits, dot, underscore, colon, or hyphen"
            )
        return value


class PermissionPolicyProfile(_FrozenControlPlaneModel):
    """A context selector whose policy may only narrow the master ceiling."""

    id: str
    preset: PermissionPreset = "manual"
    surfaces: tuple[str, ...] = ()
    workspaces: tuple[str, ...] = ()
    projects: tuple[str, ...] = ()
    agents: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()
    rules: tuple[PermissionPolicyRule, ...] = ()
    workspace_only: bool | None = None
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def validate_profile_id(cls, value: str) -> str:
        if not _POLICY_ID_RE.fullmatch(value):
            raise ValueError(
                "policy profile id must be lowercase and contain only letters, "
                "digits, dot, underscore, colon, or hyphen"
            )
        return value


class PermissionExplainReceipt(_FrozenControlPlaneModel):
    """Secret-safe deterministic explanation returned to every surface."""

    schema_version: Literal[1] = 1
    decision: PermissionDecision
    reason_code: str
    matched_rule_id: str | None = None
    source_layer: PermissionSourceLayer
    effective_preset: PermissionPreset
    effective_profile_id: str | None = None
    tool: str
    capability: str | None = None
    risk: PermissionRisk
    workspace_root: str | None = None
    target_paths: tuple[str, ...] = ()
    maintenance_scope_used: bool = False


class PermissionConfig(_FrozenControlPlaneModel):
    mode: PermissionMode = "ask"
    preset: PermissionPreset = "manual"
    rules: tuple[PermissionPolicyRule, ...] = ()
    profiles: tuple[PermissionPolicyProfile, ...] = ()
    workspace_only: bool = False
    atlas_maintenance_enabled: bool = True
    maintenance_roots: tuple[str, ...] = ()
    hardline_version: Literal["2026-06-29"] = "2026-06-29"
    approval_ttl_seconds: int = Field(default=300, ge=1)
    decision_timeout_seconds: int = Field(default=300, ge=1)
    heartbeat_interval_seconds: int = Field(default=1, ge=1, le=30)
    fail_closed_on_disconnect: bool = True

    @model_validator(mode="after")
    def validate_profiles_only_narrow(self) -> PermissionConfig:
        master_rank = _PRESET_RANK[self.preset]
        master_allow_keys = {
            (
                rule.selector,
                rule.scope,
            )
            for rule in self.rules
            if rule.enabled and rule.effect == "allow"
        }
        for profile in self.profiles:
            if not profile.enabled:
                continue
            if _PRESET_RANK[profile.preset] > master_rank:
                raise ValueError(f"profile {profile.id!r} may only narrow the master preset")
            if profile.workspace_only is False and self.workspace_only:
                raise ValueError(f"profile {profile.id!r} may only narrow workspace_only")
            if self.preset == "full_autonomy":
                continue
            for rule in profile.rules:
                if (
                    rule.enabled
                    and rule.effect == "allow"
                    and (rule.selector, rule.scope) not in master_allow_keys
                ):
                    raise ValueError(
                        f"profile {profile.id!r} allow rule {rule.id!r} "
                        "may only narrow existing master authority"
                    )
        return self


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


class RetentionConfig(_FrozenControlPlaneModel):
    """Data lifecycle and cleanup configuration."""

    # Mission lifecycle
    auto_archive_enabled: bool = False
    auto_archive_after_days: int = Field(default=7, ge=1, le=365)
    default_delete_after_days: int = Field(default=30, ge=1, le=3650)
    max_delete_after_days: int = Field(default=365, ge=30, le=3650)

    # Automatic purge
    auto_purge_enabled: bool = False
    auto_purge_interval_hours: int = Field(default=24, ge=1, le=168)

    # Compression
    compress_enabled: bool = False
    compress_after_archive_days: int = Field(default=14, ge=1, le=365)

    # Non-mission data
    archive_completed_goals_after_days: int = Field(default=90, ge=7, le=365)
    archive_stale_focus_after_days: int = Field(default=30, ge=7, le=365)
    cleanup_old_logs_enabled: bool = False
    max_log_age_days: int = Field(default=30, ge=1, le=365)

    # Database maintenance
    vacuum_after_purge: bool = True
    checkpoint_wal_hours: int = Field(default=6, ge=1, le=72)

    # Protection
    min_missions_keep: int = Field(default=5, ge=0, le=100)


class AtlasConfig(_FrozenControlPlaneModel):
    schema_version: Literal[2] = 2
    revision: int = Field(default=0, ge=0)
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    functions: FunctionsConfig = Field(default_factory=FunctionsConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    cockpit: CockpitConfig = Field(default_factory=CockpitConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    permission: PermissionConfig = Field(default_factory=PermissionConfig)
    modules: ModulesConfig = Field(default_factory=ModulesConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)


class ConfigPatchRequest(_FrozenControlPlaneModel):
    expected_revision: int = Field(ge=0)
    changes_json: str
    reason: str = Field(default="configuration update", min_length=1, max_length=240)
    # These values are caller assertions until the gateway authenticates session
    # ownership. Receipts deliberately keep them separate from authenticated_actor.
    source_surface: str | None = Field(default=None, min_length=1, max_length=96)
    source_session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=96,
        pattern=_CONTROL_PLANE_ID_RE.pattern,
    )

    @field_validator("reason", "source_surface")
    @classmethod
    def reject_multiline_audit_text(cls, value: str | None) -> str | None:
        if value is not None and ("\n" in value or "\r" in value):
            raise ValueError("config patch audit text must be single-line")
        return value

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


ConfigReceiptValue = bool | int | float | str | None


class ConfigReloadMetadata(_FrozenControlPlaneModel):
    """When one committed config value becomes observable."""

    restart_required: bool
    visibility: Literal["restart", "next_read_or_new_execution"]


class ConfigChangeReceipt(_FrozenControlPlaneModel):
    """Bounded, secret-safe receipt for one committed configuration mutation.

    ``before`` and ``after`` contain typed config leaf values after the audit
    boundary has masked secrets. Credential storage and model-registry refresh
    are intentionally not represented by this reversible receipt.
    """

    schema_version: Literal[1] = 1
    kind: Literal["config_change"] = "config_change"
    event_id: str = Field(
        min_length=1,
        max_length=96,
        pattern=_CONTROL_PLANE_ID_RE.pattern,
    )
    committed_revision: int = Field(ge=1)
    changed_paths: tuple[str, ...] = Field(
        min_length=1,
        max_length=_MAX_CONFIG_RECEIPT_CHANGES,
    )
    before: dict[str, ConfigReceiptValue] = Field(
        min_length=1,
        max_length=_MAX_CONFIG_RECEIPT_CHANGES,
    )
    after: dict[str, ConfigReceiptValue] = Field(
        min_length=1,
        max_length=_MAX_CONFIG_RECEIPT_CHANGES,
    )
    reload: dict[str, ConfigReloadMetadata] = Field(
        min_length=1,
        max_length=_MAX_CONFIG_RECEIPT_CHANGES,
    )
    authenticated_actor: str = Field(
        min_length=1,
        max_length=96,
        pattern=_CONTROL_PLANE_ID_RE.pattern,
    )
    asserted_source_surface: str = Field(min_length=1, max_length=96)
    asserted_source_session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=96,
        pattern=_CONTROL_PLANE_ID_RE.pattern,
    )
    reason: str = Field(min_length=1, max_length=240)
    timestamp: str
    credential_status: Literal["not_in_scope"] = "not_in_scope"
    config_status: Literal["committed"] = "committed"

    @field_validator("reason", "asserted_source_surface")
    @classmethod
    def reject_multiline_receipt_text(cls, value: str) -> str:
        if "\n" in value or "\r" in value:
            raise ValueError("config receipt audit text must be single-line")
        return value

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp must be ISO 8601") from exc
        if parsed.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_bounded_masked_diff(self) -> ConfigChangeReceipt:
        if len(set(self.changed_paths)) != len(self.changed_paths):
            raise ValueError("changed_paths must not contain duplicates")
        path_set = set(self.changed_paths)
        if any(
            len(path) > _MAX_CONFIG_RECEIPT_PATH_LENGTH
            or not _CONFIG_PATH_RE.fullmatch(path)
            for path in path_set
        ):
            raise ValueError("changed_paths must contain dotted config paths")
        if set(self.before) != path_set or set(self.after) != path_set:
            raise ValueError("before and after keys must exactly match changed_paths")
        if set(self.reload) != path_set:
            raise ValueError("reload keys must exactly match changed_paths")
        for values in (self.before, self.after):
            for path, value in values.items():
                if isinstance(value, str) and len(value) > _MAX_CONFIG_RECEIPT_VALUE_LENGTH:
                    raise ValueError(
                        "config receipt string values must be at most "
                        f"{_MAX_CONFIG_RECEIPT_VALUE_LENGTH} characters"
                    )
                if isinstance(value, str) and _SECRET_VALUE_RE.search(value):
                    raise ValueError("config receipt values must be secret-masked")
                if path.rsplit(".", 1)[-1] in _SECRET_PATH_SEGMENTS and value not in {
                    None,
                    "",
                    "[REDACTED]",
                } and not (isinstance(value, str) and _ENV_REFERENCE.fullmatch(value)):
                    raise ValueError("sensitive config receipt paths must be secret-masked")
        return self


class ConfigPatchResult(ControlPlaneSnapshot):
    """Additive PATCH response; legacy snapshot fields remain at top level."""

    receipt: ConfigChangeReceipt | None = None


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
    "ConfigChangeReceipt",
    "ConfigPatchRequest",
    "ConfigPatchResult",
    "ConfigReceiptValue",
    "ConfigReloadMetadata",
    "ContextConfig",
    "ControlPlaneError",
    "ControlPlaneSnapshot",
    "GatewayConfig",
    "ModulesConfig",
    "PermissionDecision",
    "PermissionEffect",
    "PermissionExplainReceipt",
    "PermissionConfig",
    "PermissionPolicyProfile",
    "PermissionPolicyRule",
    "PermissionPreset",
    "PermissionRisk",
    "PermissionRuleScope",
    "PermissionRuleSelector",
    "PermissionSourceLayer",
    "ProviderConfig",
    "ProviderModelStatus",
    "RetentionConfig",
    "RuntimeConfig",
    "SettingStatus",
]
