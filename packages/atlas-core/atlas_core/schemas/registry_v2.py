"""Provider / ModelV2 / RoutePolicy Pydantic v2 schemas for the v1.1 registry.

DDL in infra/migrations/0004_registry_v2.sql mirrors these fields 1:1 (D-012).

CREDENTIAL BOUNDARY (SEC-01): none of these models carry secret material.
auth_status on ModelV2 is a DERIVED Literal field computed at discovery time
by inspecting the file auth store (~/.atlas/auth.json). Only provider_id and
the derived auth_status appear here; raw API keys / tokens live solely in the
auth store and are never written to SQLite or returned by any status command.
"""
from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer

# ---------------------------------------------------------------------------
# Provider — one row per known provider identity (PROV-01).
# Distinct from credential (auth store), runtime, model, and route.
# ---------------------------------------------------------------------------

class Provider(BaseModel):
    """Registry entry for a single provider identity.

    provider_id is a natural string key (e.g. "openai", "anthropic",
    "lm-studio") — NOT an auto-generated UUID.  Mirrors the
    provider_registry table in 0004_registry_v2.sql field-for-field.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    provider_id: str
    display_name: str | None = None
    auth_type: str | None = None
    default_base_url: str | None = None
    # JSON string (never dict) per D-013; mirrors TEXT NOT NULL DEFAULT '{}'
    api_modes_json: str = "{}"
    source: str | None = None
    status: str | None = None
    last_checked: datetime.datetime | None = None
    last_error: str | None = None

    @field_serializer("last_checked")
    def serialize_last_checked(self, dt: datetime.datetime | None) -> str | None:
        """Return ISO 8601 string so model_dump() is JSON-safe."""
        return None if dt is None else dt.isoformat()


# ---------------------------------------------------------------------------
# ModelV2 — one row per (model_id, provider_id, source) triple (MOD-03/04/05).
# ---------------------------------------------------------------------------

class ModelV2(BaseModel):
    """Registry row for a discovered model (composite natural key).

    Identity is the composite (model_id, provider_id, source) — do NOT
    auto-generate a UUID id.  Mirrors model_registry_v2 in
    0004_registry_v2.sql field-for-field.

    status and auth_status are DISTINCT columns (MOD-05):
      status      — model reachability/lifecycle
      auth_status — credential state derived at discovery time from the file
                    auth store; never a stored secret (SEC-01 credential
                    boundary).  A future executor must not interpret this
                    field as a secret; it is derived and carries no key
                    material.

    deactivated_at is a nullable ISO-8601 timestamp for source-scoped
    soft-delete (MOD-04): setting deactivated_at for source=X never affects
    rows with source=Y.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    model_id: str
    provider_id: str
    source: str
    api_mode: str | None = None
    status: Literal[
        "available",
        "offline",
        "unsupported",
        "unknown",
    ] = "unknown"
    # auth_status is DERIVED — never a stored secret; computed at discovery
    # time by inspecting ~/.atlas/auth.json (SEC-01 credential boundary).
    auth_status: Literal[
        "available",
        "auth_present",
        "needs_api_key",
        "needs_login",
        "offline",
        "rate_limited",
        "expired",
        "unknown",
    ] = "unknown"
    context_window: int = 0
    # JSON string (never dict) per D-013; mirrors TEXT NOT NULL DEFAULT '{}'
    metadata_json: str = "{}"
    first_seen: datetime.datetime
    last_seen: datetime.datetime
    deactivated_at: datetime.datetime | None = None

    @field_serializer("first_seen", "last_seen", "deactivated_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        """Return ISO 8601 string so model_dump() is JSON-safe."""
        return None if dt is None else dt.isoformat()


# ---------------------------------------------------------------------------
# RoutePolicy — task-class → provider/model routing map.
#
# SCHEMA-ONLY IN v1.1 — no reader/writer is wired in this milestone.
# Routing enforcement and the `atlas route` CLI are v1.2+ (ROUTE-01/02,
# deferred).  Mirrors route_policy in 0004_registry_v2.sql field-for-field.
# ---------------------------------------------------------------------------

class RoutePolicy(BaseModel):
    """Task-class routing policy entry.

    task_class is a natural string key (e.g. "code", "summarise", "default").
    This model mirrors route_policy in 0004_registry_v2.sql.

    NOTE: schema-only in v1.1; no v1.1 code reads or writes this table.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    task_class: str
    provider_id: str | None = None
    model_id: str | None = None
    # JSON string (never dict) per D-013; mirrors TEXT NOT NULL DEFAULT '{}'
    fallback_policy_json: str = "{}"
    updated_at: datetime.datetime | None = None

    @field_serializer("updated_at")
    def serialize_updated_at(self, dt: datetime.datetime | None) -> str | None:
        """Return ISO 8601 string so model_dump() is JSON-safe."""
        return None if dt is None else dt.isoformat()


__all__ = [
    "ModelV2",
    "Provider",
    "RoutePolicy",
]
