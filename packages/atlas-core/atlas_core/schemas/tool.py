"""Tool layer schemas — the extensible-harness contract (Phase 10.0.4).

A `ToolManifest` is the declarative description of an integration: its name,
human description, `risk_level` (read | write | shell), declared permissions,
inputs/outputs, and the audit events it emits. Adding a tool to ATLAS means
shipping a manifest + an adapter `run(args, ctx) -> ToolResult` — no core changes.

`ToolApproval` is the gated record for write/shell tools: it mirrors the Phase C
`DiscordApproval` lifecycle column-for-column against
`infra/migrations/0013_tool_approvals.sql`. Read-class tools never become approvals.

D-012/013: frozen Pydantic v2; `args`/`result`/`output` are JSON *strings* (not
dicts) and `args` is secret-redacted before persistence (tool_service). Datetimes
serialize to ISO 8601.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# Risk taxonomy maps 1:1 to SC1: read = default-allowed; write/shell = approval-gated.
ToolRiskLevel = Literal["read", "write", "shell"]

# pending -> executing -> executed | failed ;  pending -> rejected.
# Reuses the exact 5-value set from DiscordApprovalStatus (Phase C). `executing`
# is the transient atomic-claim state so two concurrent approvers cannot both run.
ToolApprovalStatus = Literal["pending", "executing", "executed", "rejected", "failed"]


class ToolInput(BaseModel):
    """One declared input parameter of a tool (manifest-level documentation)."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    name: str
    required: bool = False
    description: str = ""


class ToolManifest(BaseModel):
    """Declarative tool contract loaded from a YAML manifest (SC2).

    Validation is fail-fast: an unknown `risk_level` or a missing required field
    raises a ValidationError at load time rather than degrading to an unsafe
    default.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    name: str
    description: str = ""
    risk_level: ToolRiskLevel
    permissions: list[str] = Field(default_factory=list)
    inputs: list[ToolInput] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    audit_events: list[str] = Field(
        default_factory=lambda: ["tool_requested", "tool_completed", "tool_failed"]
    )


class ToolResult(BaseModel):
    """The outcome of a single adapter run. `output` is a JSON or text string
    (D-013); it is secret-redacted at the audit boundary before persistence."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    tool_name: str = ""
    ok: bool
    output: str = ""
    error: Optional[str] = None
    exit_code: Optional[int] = None


class ToolApproval(BaseModel):
    """One gated write/shell tool request and its lifecycle. Mirrors the
    0013_tool_approvals DDL 1:1."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    risk_level: ToolRiskLevel
    args: str = "{}"  # JSON string, secret-redacted before persistence (D-013)
    summary: str = ""  # human-readable, e.g. "webhook_notify POST https://…"
    status: ToolApprovalStatus = "pending"
    reason: Optional[str] = None  # operator note (propose or reject)
    result: Optional[str] = None  # JSON string: adapter output on success, error on failure
    run_id: str = "operator"
    requested_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    decided_at: Optional[datetime.datetime] = None
    # Phase 10.5 surface-scoped broker (PERM-01). All Optional so legacy NULL rows
    # load; mirrors migration 0017 additive columns 1:1 (Pitfall 2 lockstep).
    surface_session_id: Optional[str] = None  # soft anchor to surface_sessions.id
    surface_kind: Optional[str] = None  # cli | tui | webui | api
    workspace_root: Optional[str] = None  # resolved workspace for scope binding
    expiry_at: Optional[datetime.datetime] = None  # TTL deadline (SEC-02 stale gate)
    decision: Optional[str] = None  # claim outcome (allow/deny cause)
    nonce: Optional[str] = None  # replay guard (SEC-02)
    args_normalized: Optional[str] = None  # redacted canonical args = policy match key

    @field_serializer("requested_at", "decided_at", "expiry_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        return None if dt is None else dt.isoformat()


class ApprovalChannel(BaseModel):
    """A registered approval delivery channel for a surface session (PERM-05).

    Presence of an unrevoked row is the fail-closed gate for headless ('api')
    surfaces. Mirrors the 0017 approval_channels table."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    surface_session_id: str
    surface_kind: str
    registered_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    revoked_at: Optional[datetime.datetime] = None

    @field_serializer("registered_at", "revoked_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        return None if dt is None else dt.isoformat()


# allow_once: this approval only; allow_session: rest of the session; allow_always:
# persists across sessions (still scope-bound to workspace + surface + tool).
SessionAllowRuleKind = Literal["allow_once", "allow_session", "allow_always"]


class SessionAllowRule(BaseModel):
    """A scope-bound allow rule (PERM-07). Anchored to one surface session +
    workspace + surface kind + tool + arg pattern — never a global policy.
    Mirrors the 0017 session_allow_rules table."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    surface_session_id: str
    workspace_root: str
    surface_kind: str
    tool_name: str
    arg_pattern: str
    rule_kind: SessionAllowRuleKind
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    @field_serializer("created_at")
    def serialize_dt(self, dt: datetime.datetime) -> str:
        return dt.isoformat()


__all__ = [
    "ToolRiskLevel",
    "ToolApprovalStatus",
    "ToolInput",
    "ToolManifest",
    "ToolResult",
    "ToolApproval",
    "ApprovalChannel",
    "SessionAllowRuleKind",
    "SessionAllowRule",
]
