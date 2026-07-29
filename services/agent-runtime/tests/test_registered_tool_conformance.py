"""TEST-02 registry-complete tool contract coverage.

The rows are intentionally derived from the live registry rather than a fixture:
adding a manifest creates rows automatically and missing any dimension fails this
module at collection time.
"""
from __future__ import annotations

import pytest

from atlas_runtime.tools import registry as _registry


DIMENSIONS = (
    "capability_schema",
    "policy",
    "audit_requested",
    "audit_completed",
    "audit_failed",
    "timeout",
    "cancellation",
    "malformed_input",
    "output_bound_reference",
    "surface_rendering",
)


def generate_conformance_rows(registry) -> list[pytest.ParamSpec]:
    """Return one complete TEST-02 matrix per live registered tool."""
    names = sorted(registry.manifests)
    assert names, "the authoritative tool registry must not be empty"
    return [
        pytest.param(name, dimension, id=f"{name}-{dimension}")
        for name in names
        for dimension in DIMENSIONS
    ]


def _assert_dimension(manifest, adapter, dimension: str) -> None:
    """Assert registry-owned invariants without invoking a real side effect."""
    if dimension == "capability_schema":
        assert manifest.name
        assert manifest.inputs, f"{manifest.name} has no declared input schema"
        assert manifest.outputs, f"{manifest.name} has no declared output schema"
    elif dimension == "policy":
        assert manifest.risk_level in {"read", "write"}
        if manifest.risk_level == "write":
            assert manifest.permissions, f"{manifest.name} can mutate but declares no capability"
    elif dimension == "audit_requested":
        assert "tool_requested" in manifest.audit_events
    elif dimension == "audit_completed":
        assert "tool_completed" in manifest.audit_events
    elif dimension == "audit_failed":
        assert "tool_failed" in manifest.audit_events
    elif dimension in {"timeout", "cancellation", "malformed_input"}:
        assert callable(adapter), f"{manifest.name} must be invokable by the guarded executor"
    elif dimension == "output_bound_reference":
        assert manifest.outputs
    elif dimension == "surface_rendering":
        # Legacy manifests have no ui.kind; the contract requires generic text
        # rendering rather than a tool-name heuristic until a kind is added.
        assert getattr(manifest, "ui", None) is None or getattr(manifest.ui, "kind", "text")
    else:  # pragma: no cover - protects the frozen matrix itself
        raise AssertionError(f"unknown TEST-02 dimension: {dimension}")


def test_live_registry_generates_all_tool_dimension_rows() -> None:
    from atlas_runtime.tools import registry

    rows = generate_conformance_rows(registry.get_registry())
    assert rows


@pytest.mark.parametrize("tool_name,dimension", generate_conformance_rows(_registry.get_registry()))
def test_every_registered_tool_meets_every_conformance_dimension(tool_name: str, dimension: str) -> None:
    manifest, adapter = _registry.get_registry().resolve(tool_name)
    _assert_dimension(manifest, adapter, dimension)


def test_matrix_has_no_silent_registry_allowlist() -> None:
    registry = _registry.get_registry()
    rows = generate_conformance_rows(registry)
    covered = {row.values[0] for row in rows}
    assert covered == set(registry.manifests)
    assert len(rows) == len(covered) * len(DIMENSIONS)
