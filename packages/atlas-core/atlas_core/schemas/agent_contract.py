"""Frozen public contracts for ATLAS prompt, bootstrap, and context assembly.

The models deliberately use only JSON-stable strings, tuples, numeric
primitives, booleans, and nested frozen models. They are the Python surface
that later Rust modules can consume without inheriting Python-specific types.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

InstructionTrust = Literal["platform", "operator", "project", "evidence", "untrusted"]
PermissionMode = Literal["allow", "ask", "deny"]
SurfaceKind = Literal["cli", "tui", "webui", "api", "native", "test"]
WorkspaceKind = Literal["project", "directory", "global"]
ContextSourceType = Literal[
    "brain",
    "wiki",
    "run",
    "observation",
    "artifact",
    "failure",
    "skill",
    "repository",
    "tool",
    "web",
    "memory",
]


def _require_text(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True, extra="forbid")


class ContractVersion(_FrozenContract):
    """Version and content digest for one immutable contract artifact."""

    version: str
    sha256: str

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not _SEMVER_RE.fullmatch(value):
            raise ValueError("version must be semantic version text")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not _SHA256_RE.fullmatch(value):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        return value


class InstructionSource(_FrozenContract):
    """A captured instruction source accepted at session creation."""

    source_id: str
    path: str
    sha256: str
    trust: InstructionTrust

    @field_validator("source_id", "path")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _require_text(value)

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        return ContractVersion.validate_sha256(value)


class SurfaceIdentity(_FrozenContract):
    kind: SurfaceKind
    session_id: str

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        return _require_text(value)


class WorkspaceIdentity(_FrozenContract):
    kind: WorkspaceKind
    root: str
    project_id: str | None = None

    @field_validator("root")
    @classmethod
    def validate_root(cls, value: str) -> str:
        return _require_text(value)

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str | None) -> str | None:
        return None if value is None else _require_text(value)

    @model_validator(mode="after")
    def require_project_id(self) -> "WorkspaceIdentity":
        if self.kind == "project" and self.project_id is None:
            raise ValueError("project workspaces require project_id")
        return self


class ModelIdentity(_FrozenContract):
    provider: str
    model_id: str

    @field_validator("provider", "model_id")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _require_text(value)


class ContextSource(_FrozenContract):
    """One selected evidence item in the generated dynamic context envelope."""

    source_id: str
    source_type: ContextSourceType
    project_id: str | None = None
    retrieved_at: str
    source_updated_at: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    relevance: float = Field(ge=0.0, le=1.0)
    trust: InstructionTrust = "evidence"
    content: str
    truncated: bool = False

    @field_validator("source_id", "retrieved_at", "content")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _require_text(value)

    @field_validator("project_id", "source_updated_at")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else _require_text(value)


class SessionBootstrap(_FrozenContract):
    """Generated session identity and policy state; never prose-authored."""

    surface: SurfaceIdentity
    workspace: WorkspaceIdentity
    focus_id: str | None = None
    focus_title: str | None = None
    mission_id: str | None = None
    run_id: str
    agent: str
    model: ModelIdentity
    permission_mode: PermissionMode
    capabilities: tuple[str, ...] = ()
    instruction_sources: tuple[InstructionSource, ...] = ()
    prompt: ContractVersion
    tool_catalog: ContractVersion
    context_policy: ContractVersion
    context_budget_tokens: int = Field(default=8000, ge=1, le=100_000)

    @field_validator("run_id", "agent")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _require_text(value)

    @field_validator("focus_id", "focus_title", "mission_id")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else _require_text(value)

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(_require_text(value) for value in values)
        if len(set(normalized)) != len(normalized):
            raise ValueError("capabilities must be unique")
        return normalized


class ContextEnvelope(_FrozenContract):
    """Generated dynamic evidence separated from the stable prompt prefix."""

    policy: ContractVersion
    budget_tokens: int = Field(default=8000, ge=1, le=100_000)
    estimated_tokens: int = Field(default=0, ge=0, le=100_000)
    sources: tuple[ContextSource, ...] = ()
    rejected_source_ids: tuple[str, ...] = ()

    @field_validator("rejected_source_ids")
    @classmethod
    def validate_rejected_sources(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_require_text(value) for value in values)

    @model_validator(mode="after")
    def enforce_budget(self) -> "ContextEnvelope":
        if self.estimated_tokens > self.budget_tokens:
            raise ValueError("estimated_tokens must not exceed budget_tokens")
        return self


__all__ = [
    "ContextEnvelope",
    "ContextSource",
    "ContextSourceType",
    "ContractVersion",
    "InstructionSource",
    "InstructionTrust",
    "ModelIdentity",
    "PermissionMode",
    "SessionBootstrap",
    "SurfaceIdentity",
    "SurfaceKind",
    "WorkspaceIdentity",
    "WorkspaceKind",
]
