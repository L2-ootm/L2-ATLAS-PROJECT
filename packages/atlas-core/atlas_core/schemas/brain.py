"""Frozen JSON-stable contracts for the durable ATLAS Brain graph."""
from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BrainNode(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True, extra="forbid")

    id: str
    entity_type: str
    label: str
    project_id: str | None = None
    source_id: str
    source_version: str
    updated_at: str
    confidence: float = Field(ge=0.0, le=1.0)
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
