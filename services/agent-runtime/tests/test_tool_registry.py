"""Phase 10.0.4 SC2 — tool registry: manifest load + name->adapter binding.

RED until Plan 03 adds `atlas_runtime.tools.registry`. The registry discovers the
shipped YAML manifests, validates each into a `ToolManifest`, and binds each tool
name to its Python adapter `run(args, ctx) -> ToolResult`. Mirrors the
`agents/registry.py` pattern. An unknown name or an invalid manifest fails fast.
"""
from __future__ import annotations

import pytest


def test_registry_loads_shipped_manifests():
    from atlas_runtime.tools import registry

    reg = registry.get_registry()
    names = set(reg.manifests.keys())
    # The four SC1 integrations ship as manifests in v0.
    assert {"workspace", "github", "web_fetch", "webhook_notify"} <= names


def test_registry_binds_name_to_adapter():
    from atlas_runtime.tools import registry

    reg = registry.get_registry()
    manifest, adapter = reg.resolve("workspace")
    assert manifest.name == "workspace"
    assert callable(adapter)


def test_registry_resolve_unknown_raises():
    from atlas_runtime.tools import registry

    reg = registry.get_registry()
    with pytest.raises(ValueError):
        reg.resolve("does_not_exist")


def test_registry_invalid_manifest_fails_at_load(tmp_path):
    from atlas_runtime.tools import registry

    bad = tmp_path / "broken.yaml"
    bad.write_text("name: broken\nrisk_level: nuke\n", encoding="utf-8")
    with pytest.raises(Exception):
        registry.load_manifests(tmp_path)


def test_registry_every_manifest_has_an_adapter():
    from atlas_runtime.tools import registry

    reg = registry.get_registry()
    for name in reg.manifests:
        _manifest, adapter = reg.resolve(name)
        assert callable(adapter), f"{name} has no bound adapter"
