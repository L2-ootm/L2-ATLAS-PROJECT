"""Tool registry — manifest load + name->adapter binding (Phase 10.0.4, SC2).

Mirrors the agents/registry.py resolve-or-raise pattern. Eagerly loads every
``manifests/*.yaml``, validates each into a frozen ``ToolManifest`` (a
ValidationError is a fail-fast load error), and binds each manifest name to its
adapter module's ``run`` callable. Adding a tool = drop a manifest + adapter and
register the binding here. Registry load never probes ``gh`` — the github adapter
only touches the CLI at call time.
"""
from __future__ import annotations

import pathlib

import yaml

from atlas_core.schemas.tool import ToolManifest

from atlas_runtime.tools.adapters import github, web_fetch, webhook_notify, workspace

_MANIFESTS_DIR = pathlib.Path(__file__).resolve().parent / "manifests"

# name -> adapter run(args, ctx) -> ToolResult. The manifest `name` MUST match a key.
_ADAPTERS = {
    "workspace": workspace.run,
    "github": github.run,
    "web_fetch": web_fetch.run,
    "webhook_notify": webhook_notify.run,
}


def load_manifests(directory: pathlib.Path | str = _MANIFESTS_DIR) -> dict[str, ToolManifest]:
    """Load + validate every *.yaml manifest in `directory`. Fail-fast on invalid."""
    directory = pathlib.Path(directory)
    out: dict[str, ToolManifest] = {}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        manifest = ToolManifest.model_validate(data)  # ValidationError propagates (fail-fast)
        out[manifest.name] = manifest
    return out


class ToolRegistry:
    """Immutable view over {name: (ToolManifest, adapter_run)}."""

    def __init__(self, bindings: dict) -> None:
        self._bindings = bindings

    @property
    def manifests(self) -> dict[str, ToolManifest]:
        return {name: manifest for name, (manifest, _run) in self._bindings.items()}

    def known_tools(self) -> list[str]:
        return sorted(self._bindings)

    def resolve(self, name: str):
        """Return (ToolManifest, run_callable) or raise ValueError on unknown name."""
        if name not in self._bindings:
            raise ValueError(
                f"Unknown tool {name!r}. Known: {', '.join(self.known_tools())}"
            )
        return self._bindings[name]


def _build_registry() -> ToolRegistry:
    manifests = load_manifests(_MANIFESTS_DIR)
    bindings: dict = {}
    for name, manifest in manifests.items():
        adapter = _ADAPTERS.get(name)
        if adapter is None:
            raise ValueError(f"manifest {name!r} has no bound adapter")
        bindings[name] = (manifest, adapter)
    return ToolRegistry(bindings)


_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Process-wide singleton registry (built on first use)."""
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry
