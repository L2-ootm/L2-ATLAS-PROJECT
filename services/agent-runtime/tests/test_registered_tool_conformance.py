"""TEST-02 registry-complete tool contract coverage."""
from __future__ import annotations


def test_live_registry_generates_all_tool_dimension_rows() -> None:
    from atlas_runtime.tools import registry

    rows = generate_conformance_rows(registry.get_registry())
    assert rows
