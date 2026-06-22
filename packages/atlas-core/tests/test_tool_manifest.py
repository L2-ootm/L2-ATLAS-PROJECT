"""Phase 10.0.4 SC2 — Tool Manifest v0 schema validation.

RED until Plan 01 adds `atlas_core.schemas.tool`. The manifest is the contract
that makes ATLAS an extensible harness: adding a tool = writing a manifest +
adapter. Validation is fail-fast (an unknown risk_level or a missing required
field raises at load, never silently degrades to an unsafe default).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def _valid_manifest_dict() -> dict:
    return {
        "name": "workspace",
        "description": "Read files within the workspace boundary.",
        "risk_level": "read",
        "permissions": ["fs:read"],
        "inputs": [{"name": "path", "required": True, "description": "file or dir"}],
        "outputs": ["content"],
        "audit_events": ["tool_requested", "tool_completed", "tool_failed"],
    }


def test_tool_manifest_accepts_valid_dict():
    from atlas_core.schemas.tool import ToolManifest

    m = ToolManifest(**_valid_manifest_dict())
    assert m.name == "workspace"
    assert m.risk_level == "read"
    assert m.inputs[0].name == "path"


def test_tool_manifest_rejects_unknown_risk_level():
    from atlas_core.schemas.tool import ToolManifest

    bad = _valid_manifest_dict()
    bad["risk_level"] = "nuke"
    with pytest.raises(ValidationError):
        ToolManifest(**bad)


def test_tool_manifest_rejects_missing_name():
    from atlas_core.schemas.tool import ToolManifest

    bad = _valid_manifest_dict()
    del bad["name"]
    with pytest.raises(ValidationError):
        ToolManifest(**bad)


def test_tool_manifest_rejects_missing_risk_level():
    from atlas_core.schemas.tool import ToolManifest

    bad = _valid_manifest_dict()
    del bad["risk_level"]
    with pytest.raises(ValidationError):
        ToolManifest(**bad)


def test_tool_manifest_is_frozen():
    from atlas_core.schemas.tool import ToolManifest

    m = ToolManifest(**_valid_manifest_dict())
    with pytest.raises(ValidationError):
        m.name = "other"  # type: ignore[misc]
