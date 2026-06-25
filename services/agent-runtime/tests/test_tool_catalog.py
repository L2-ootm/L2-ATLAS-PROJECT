"""Deterministic normalization tests for the unified tool catalog."""
from __future__ import annotations

import json

import pytest

from atlas_core.schemas.tool import ToolInput, ToolManifest
from atlas_runtime.tool_catalog import (
    build_tool_catalog,
    capability_from_atlas,
    capability_from_hermes,
    capability_from_mcp,
)


def _atlas(name: str = "workspace"):
    return capability_from_atlas(
        ToolManifest(
            name=name,
            description="Read workspace files.",
            risk_level="read",
            permissions=["fs:read"],
            inputs=[ToolInput(name="path", required=True)],
            outputs=["content"],
        )
    )


def test_normalizes_atlas_hermes_and_mcp_sources():
    atlas = _atlas()
    hermes = capability_from_hermes(
        {
            "name": "terminal",
            "description": "Run a command.",
            "toolset": "terminal",
            "schema": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
            "risk_level": "shell",
            "side_effects": ["process"],
            "timeout_ms": 300_000,
            "max_result_bytes": 1_000_000,
        }
    )
    mcp = capability_from_mcp(
        {
            "name": "search",
            "description": "Search a remote index.",
            "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
            "annotations": {"readOnlyHint": True},
            "server": "docs",
        }
    )

    catalog = build_tool_catalog((hermes, mcp, atlas))
    assert [item.name for item in catalog.capabilities] == ["search", "terminal", "workspace"]
    assert {item.source for item in catalog.capabilities} == {"atlas", "hermes", "mcp"}
    assert len(catalog.catalog_sha256) == 64


def test_catalog_is_deterministic_and_metadata_sensitive():
    first = build_tool_catalog((_atlas("z"), _atlas("a")))
    second = build_tool_catalog((_atlas("a"), _atlas("z")))
    changed = build_tool_catalog((_atlas("a"),))
    assert first.model_dump_json() == second.model_dump_json()
    assert first.catalog_sha256 == second.catalog_sha256
    assert first.catalog_sha256 != changed.catalog_sha256


def test_duplicate_names_and_aliases_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        build_tool_catalog((_atlas("same"), _atlas("same")))


def test_incomplete_risk_metadata_fails_closed():
    with pytest.raises(ValueError):
        capability_from_hermes(
            {
                "name": "mystery",
                "description": "Unknown behavior.",
                "schema": {"type": "object", "properties": {}},
            }
        )


def test_schema_is_canonical_json():
    capability = _atlas()
    assert json.loads(capability.input_schema_json)["type"] == "object"
    assert capability.approval_policy == "allow"
    assert capability.workspace_scope == "current"
