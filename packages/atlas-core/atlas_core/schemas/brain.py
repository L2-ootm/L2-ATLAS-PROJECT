"""Frozen JSON-stable contracts for the durable ATLAS Brain graph."""
from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas_core.schemas.provenance import ASSERTED, Grade


class BrainNode(BaseModel):
    """One durable fact in the graph, with where it came from attached.

    `grade` is the origin of the claim and is assigned by the writer that knows
    that origin — never by the agent proposing the node. It defaults to
    `asserted` so that a caller which supplies nothing lands on the floor rather
    than in the middle of the ladder: forgetting to state provenance must cost a
    node its standing, not silently grant it some.

    `confidence` remains, but it now ranks nodes *within* a grade rather than
    standing in for one. It used to be the only quality signal on the row and was
    set by the agent itself, defaulting to 0.8.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True, extra="forbid")

    id: str
    entity_type: str
    label: str
    project_id: str | None = None
    source_id: str
    source_version: str
    updated_at: str
    confidence: float = Field(ge=0.0, le=1.0)
    grade: Grade = ASSERTED
    metadata_json: str = "{}"

    @field_validator("id", "entity_type", "label", "source_id", "source_version", "updated_at")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("metadata_json")
    @classmethod
    def valid_json(cls, value: str) -> str:
        if not isinstance(json.loads(value), dict):
            raise ValueError("metadata_json must encode an object")
        return value


class BrainEdge(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True, extra="forbid")

    source_id: str
    target_id: str
    relation: str
    project_id: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata_json: str = "{}"

    @field_validator("source_id", "target_id", "relation")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("metadata_json")
    @classmethod
    def valid_json(cls, value: str) -> str:
        if not isinstance(json.loads(value), dict):
            raise ValueError("metadata_json must encode an object")
        return value


__all__ = ["BrainEdge", "BrainNode"]
