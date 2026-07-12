"""Atlas-core domain schemas — 7 Pydantic v2 frozen models + SECRET_PATTERNS.

D-012: Single source of truth for domain contracts. model_json_schema() is the
JSON Schema bridge to TS/Rust consumers. DDL in infra/migrations/0001_core.sql
mirrors these fields 1:1.

D-013: All models are frozen=True. model_dump() produces JSON-serializable output
(no datetime objects, no Path objects, no dict[str, Any] in public fields).
"""
from __future__ import annotations

import datetime
import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# ---------------------------------------------------------------------------
# Secret-redaction constant — copied verbatim from
# L2-Atlas/src/atlas_core/logging/jsonl_logger.py.
# Phase 4 applies these patterns before writing AuditEvent.data to SQLite.
# ---------------------------------------------------------------------------

SECRET_PATTERNS = (
    re.compile(r"(?i)\b(token|api[_-]?key|secret|password)=([^\s&]+)"),
    re.compile(r'(?i)"(token|api[_-]?key|secret|password)"\s*:\s*("[^"]*"|\d+|null|true|false)'),
    re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._~+/=-]+)"),
)


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class Mission(BaseModel):
    """Top-level unit of intent — a goal the agent is working toward."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    intent: str = ""
    status: Literal[
        "pending",
        "running",
        "succeeded",
        "completed",
        "failed",
        "cancelled",
        "archived",
    ] = "pending"
    project: str = ""
    project_id: str | None = None
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        """Return ISO 8601 string so model_dump() is JSON-safe."""
        return None if dt is None else dt.isoformat()


class Project(BaseModel):
    """A folder-backed working directory. Missions linked to a project execute
    with root_path as their working directory (P3 — DDL in 0005_projects.sql)."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    root_path: str
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        """Return ISO 8601 string so model_dump() is JSON-safe."""
        return None if dt is None else dt.isoformat()


class Focus(BaseModel):
    """The operator's current working focus for the Command Center (CC-1).

    A single Focus is 'active' at a time (the Current Focus); promoting a new one
    archives the prior. `priorities` and `drivers` are JSON-array strings (str),
    mirroring AuditEvent.data, so model_dump() stays JSON-safe and the DDL in
    0009_focus.sql is 1:1. Feeds the Intelligence-Layer context-assembly step
    (phase 10.0.3-command-center)."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    framework: str = ""
    priorities: str = "[]"  # JSON array of strings
    drivers: str = "[]"  # JSON array of strings
    project_id: str | None = None
    status: Literal["active", "archived"] = "active"
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        """Return ISO 8601 string so model_dump() is JSON-safe."""
        return None if dt is None else dt.isoformat()


class Goal(BaseModel):
    """A concrete objective under a Focus (Command Center loop-engineering slice).

    Goals form a tree via `parent_goal_id` (self-nesting → sub-goals) and are
    served by a Focus via `focus_id`. `description` is the rich brief the
    context-assembly step synthesizes loop instructions from. DDL in
    0010_goal_model.sql mirrors these fields 1:1."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    focus_id: str | None = None
    parent_goal_id: str | None = None
    title: str
    description: str = ""
    status: Literal["open", "active", "done", "archived"] = "open"
    position: int = 0
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        """Return ISO 8601 string so model_dump() is JSON-safe."""
        return None if dt is None else dt.isoformat()


class Task(BaseModel):
    """A small actionable unit under a Goal. The leaf of the goal tree; the
    operator (or the loop) checks these off. DDL in 0010_goal_model.sql."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str
    title: str
    status: Literal["todo", "doing", "done"] = "todo"
    position: int = 0
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        """Return ISO 8601 string so model_dump() is JSON-safe."""
        return None if dt is None else dt.isoformat()


class Observation(BaseModel):
    """A timestamped finding attached to a Goal and/or Run. The unit the
    compounding loop appends on run completion (provenance via `source`), so the
    next context assembly inherits what was learned. Never mutates operator-owned
    Goals. DDL in 0010_goal_model.sql."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str | None = None
    run_id: str | None = None
    body: str
    source: str = "operator"  # "operator" | "run:<id>" | "compounding-loop"
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @field_serializer("created_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        """Return ISO 8601 string so model_dump() is JSON-safe."""
        return None if dt is None else dt.isoformat()


class Module(BaseModel):
    """An optional, activatable ATLAS module (e.g. cashflow). Off by default;
    toggled from the System page (DDL in 0007_modules.sql — Decision 3b). `id` is
    a stable slug (not a uuid) so seeds and code can reference it by name."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str
    name: str
    description: str = ""
    status: Literal["active", "inactive"] = "inactive"
    activated_at: datetime.datetime | None = None

    @field_serializer("activated_at")
    def serialize_activated_at(self, dt: datetime.datetime | None) -> str | None:
        """Return ISO 8601 string so model_dump() is JSON-safe."""
        return None if dt is None else dt.isoformat()


class Run(BaseModel):
    """One execution attempt of a Mission by the agent runtime."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mission_id: str
    session_id: str | None = None
    status: Literal["running", "succeeded", "failed", "cancelled"] = "running"
    started_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    finished_at: datetime.datetime | None = None
    summary: str = ""
    # Which AgentRuntime executed this run (P4 — migration 0006).
    agent_runtime: Literal["native", "claude_code"] = "native"

    @field_serializer("started_at", "finished_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        return None if dt is None else dt.isoformat()


class AuditEvent(BaseModel):
    """Immutable record of a single observable event during a Run.

    The data field is a JSON string (str, not dict) to satisfy D-013 and
    avoid dict[str, Any] in the public schema. Phase 4 redacts secrets via
    SECRET_PATTERNS before populating this field.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    task_id: str | None = None
    session_id: str | None = None
    tool_call_id: str | None = None
    event_type: Literal[
        "llm_call",
        # Streaming token/chunk delta for a llm_call in progress — a
        # coalesced fragment of the response, not the completed snapshot.
        # `data.end_of_turn=True` marks the last delta for one assistant turn.
        "llm_delta",
        "tool_call",
        "subagent_run",
        "approval",
        "artifact",
        "wiki_update",
        "memory_change",
        "failure",
        "discord_action",
        # Phase 10.0.4 tool layer (SC4). Snake_case to match the existing
        # convention; the success-criterion's dotted form
        # (tool.requested/.completed/.failed) is the external label only.
        "tool_requested",
        "tool_completed",
        "tool_failed",
        # Phase 10.0.5 golden workflows — lifecycle bookkeeping events.
        "golden_workflow_started",
        "golden_workflow_completed",
        # Phase 10.3 — surface session lifecycle / cancellation / permission.
        # Column is TEXT; enum enforced only by this Literal (no migration, AUD-01).
        "surface_session_started",
        "surface_session_suspended",
        "surface_session_resumed",
        "surface_session_reclaimed",
        "surface_session_completed",
        "surface_session_failed",
        "run_cancelled",
        "permission_transition",
        # Phase 10.4 — configuration, auth, and model control plane.
        "config_change",
        "auth_change",
        "model_call_start",
        "model_call_end",
        "provider_fallback",
    ]
    tool_name: str | None = None
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    duration_ms: int | None = None
    data: str = "{}"
    policy_result: str | None = None

    @field_serializer("timestamp")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        return None if dt is None else dt.isoformat()


class ToolCall(BaseModel):
    """Detailed record of a single tool invocation, linked to an AuditEvent.

    args and result are JSON strings (str, not dict) per D-013.
    policy_allowed and requires_approval derive from PolicyDecision.allowed and
    PolicyDecision.requires_approval respectively.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_event_id: str
    run_id: str
    tool_name: str
    args: str = "{}"
    result: str | None = None
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    duration_ms: int | None = None
    policy_allowed: bool | None = None
    requires_approval: bool | None = None
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @field_serializer("timestamp")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        return None if dt is None else dt.isoformat()


class Artifact(BaseModel):
    """File-system artifact produced or modified during a Run.

    path is stored as str (not pathlib.Path) per D-013 cross-platform rule.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    audit_event_id: str | None = None
    path: str
    artifact_type: Literal["file_write", "file_edit", "file_delete", "unknown"]
    sha256: str | None = None
    size_bytes: int | None = None
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @field_serializer("created_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        return None if dt is None else dt.isoformat()


class Source(BaseModel):
    """Immutable raw-content record stamped with SHA-256 at ingest time (WIKI-01).

    path is stored as str (not pathlib.Path) per D-013.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    path: str
    sha256: str
    size_bytes: int
    mime_type: str = "text/plain"
    ingested_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    title: str = ""
    untrusted: bool = False
    ingested_by_run_id: str | None = None

    @field_serializer("ingested_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        return None if dt is None else dt.isoformat()


class WikiPage(BaseModel):
    """Structured knowledge page backed by the wiki_pages SQLite table (WIKI-02..04).

    The wiki_fts FTS5 virtual table indexes title and body from this table.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slug: str
    title: str
    body: str = ""
    source_id: str | None = None
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    version: int = 1

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        return None if dt is None else dt.isoformat()


class MemoryProvenance(BaseModel):
    """Provenance record for every write to any ATLAS memory layer (D-019)."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    layer: Literal["WIKI", "PROFILE", "GRAPH", "SKILL", "AUDIT"]
    item_id: str
    run_id: str | None = None
    source_id: str | None = None
    audit_event_id: str | None = None
    operator_id: str | None = None
    sensitivity: Literal["public", "internal", "private", "restricted"] = "internal"
    untrusted: bool = False
    written_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @field_serializer("written_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        """Return ISO 8601 string so model_dump() is JSON-safe."""
        return None if dt is None else dt.isoformat()


__all__ = [
    "Mission",
    "Project",
    "Focus",
    "Module",
    "Run",
    "AuditEvent",
    "ToolCall",
    "Artifact",
    "Source",
    "WikiPage",
    "MemoryProvenance",
    "SECRET_PATTERNS",
]
