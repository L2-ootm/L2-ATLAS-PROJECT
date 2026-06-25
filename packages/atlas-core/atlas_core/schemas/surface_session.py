"""Frozen public contracts for the Phase 10.3 shared surface session protocol.

This is the persisted-session spine consumed by the rest of phase 10.3:
plan 03 imports `SurfaceEvent` / `EventKind`; plan 04 extends the lifecycle with
reconciliation/cancellation; plan 05 adds resume.

Honors D-013 (JSON-stable: only str/number/bool and nested frozen models; payloads
are JSON strings; datetimes serialize via field_serializer) and reuses the frozen
identity contracts from agent_contract.py rather than redefining them (AGNT-01).
"""
from __future__ import annotations

import datetime
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from atlas_core.schemas.agent_contract import (
    ModelIdentity,
    PermissionMode,
    SurfaceIdentity,
    WorkspaceIdentity,
    _FrozenContract,
)

# Lifecycle states. There is intentionally NO `cancelled` session state: a
# cooperative cancel emits the RUN-level run_cancelled and drives the owning
# session cancelling→completed for a clean stop (see surface_session_service).
SessionState = Literal[
    "starting",
    "active",
    "suspended",
    "resuming",
    "cancelling",
    "completed",
    "failed",
    "reclaimed",
]

# Normalized surface event kinds (the read-projection vocabulary, plan 03).
EventKind = Literal[
    "text",
    "reasoning",
    "tool_call",
    "tool_result",
    "task",
    "retry",
    "retrieval",
    "approval",
    "error",
    "completion",
]


class SurfaceSession(BaseModel):
    """Persisted identity + lifecycle state for one surface-attached session (SURF-01).

    Composes the frozen `SurfaceIdentity` / `WorkspaceIdentity` / `ModelIdentity`
    contracts directly. The `id` default_factory and datetime field_serializer mirror
    `core.Run` verbatim (D-038: match Mission/Run id-gen).
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    surface: SurfaceIdentity
    workspace: WorkspaceIdentity
    agent: str
    model: ModelIdentity
    permission_mode: PermissionMode
    prompt_version: str
    tool_catalog_version: str
    context_policy_version: str
    state: SessionState = "starting"
    owner_token: str = ""
    owner_pid: Optional[int] = None
    mission_id: Optional[str] = None
    run_id: Optional[str] = None
    heartbeat_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    @field_serializer("heartbeat_at", "created_at", "updated_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        return None if dt is None else dt.isoformat()


class SurfaceEvent(_FrozenContract):
    """A normalized, ordered projection of one observable surface event (D-013).

    `payload_json` is a JSON string (never a dict); `occurred_at` is an ISO-8601
    string. `seq` is assigned in iteration order so SSE and in-process transports
    number identically (plan 03).
    """

    session_id: str
    seq: int
    kind: EventKind
    run_id: Optional[str] = None
    occurred_at: str
    payload_json: str = "{}"


__all__ = [
    "EventKind",
    "SessionState",
    "SurfaceEvent",
    "SurfaceSession",
]
