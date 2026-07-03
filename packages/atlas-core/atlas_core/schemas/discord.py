"""Discord write-surface schemas — the gated approval record (Phase C).

A DiscordApproval is a two-phase write request against the vendored Discord
sidecar: an operator (or the cockpit) *proposes* a mutating action, it lands as
a `pending` row, and a second explicit *approve* step executes it via the sidecar
and emits an `event_type="discord_action"` audit event. Reject leaves the row in
a terminal `rejected` state. This satisfies the operating-model non-negotiable:
"Destructive Discord actions require explicit policy approval and audit trail."

D-012/013: frozen Pydantic v2; model_dump() is JSON-safe (datetimes serialized to
ISO 8601). The DDL in infra/migrations/0012_discord_approvals.sql mirrors these
fields 1:1. `params` is a JSON *string* (not a dict) per D-013 and is
secret-redacted before the row is written (discord_service.propose).
"""
from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# The mutating actions the sidecar exposes (bot/api.py write routes). Read/lifecycle
# actions are not gated and never become approvals.
DiscordAction = Literal[
    "create_channel",
    "edit_channel",
    "delete_channel",
    "create_role",
    "edit_role",
    "delete_role",
    "send_message",
    "set_permissions",
]

# pending -> executing -> executed | failed ;  pending -> rejected.
# `executing` is a transient claim state set atomically by approve() so two
# concurrent approvers cannot both execute the same write (TOCTOU guard).
DiscordApprovalStatus = Literal["pending", "executing", "executed", "rejected", "failed"]


class DiscordApproval(BaseModel):
    """One gated Discord write request and its lifecycle."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: DiscordAction
    guild_id: str
    target_id: str | None = None  # channel/role id for edit/delete/permissions; None for create
    params: str = "{}"  # JSON string, secret-redacted before persistence (D-013)
    summary: str = ""  # human-readable, e.g. "create text channel #general"
    status: DiscordApprovalStatus = "pending"
    reason: str | None = None  # operator note (propose or reject)
    result: str | None = None  # JSON string: created id/name on success, error on failure
    run_id: str = "operator"
    requested_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    decided_at: datetime.datetime | None = None

    @field_serializer("requested_at", "decided_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        return None if dt is None else dt.isoformat()


__all__ = [
    "DiscordAction",
    "DiscordApprovalStatus",
    "DiscordApproval",
]
