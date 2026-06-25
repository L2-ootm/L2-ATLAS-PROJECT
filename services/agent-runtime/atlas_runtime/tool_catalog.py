"""Unified deterministic catalog for ATLAS, Hermes, and MCP capabilities."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from atlas_core.schemas.agent_contract import ToolCapability, ToolCatalog
from atlas_core.schemas.tool import ToolManifest

_AUDIT = ("tool_requested", "tool_completed", "tool_failed")
_SCOPE_RANK = {"none": 0, "current": 1, "project": 2, "global": 3}
_APPROVAL_RANK = {"deny": 0, "ask": 1, "allow": 2}
_ERROR_CODES = {
    "unknown": "unknown_tool",
    "unavailable": "unavailable",
    "disallowed": "disallowed",
    "wrong_workspace": "wrong_workspace",
    "stale": "stale_catalog",
    "malformed": "malformed_arguments",
    "timeout": "timeout",
    "cancelled": "cancelled",
}
_ROLE_TAG = re.compile(r"</?(?:system|assistant|user|tool|tool_call)>", re.IGNORECASE)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _object_schema(properties: dict[str, object], required: Iterable[str] = ()) -> str:
    schema: dict[str, object] = {
        "additionalProperties": False,
        "properties": properties,
        "type": "object",
    }
    required_values = sorted(set(required))
    if required_values:
        schema["required"] = required_values
    return _json(schema)


def capability_from_atlas(manifest: ToolManifest) -> ToolCapability:
    properties = {
        item.name: {"description": item.description, "type": "string"}
        for item in manifest.inputs
    }
    required = (item.name for item in manifest.inputs if item.required)
    output = {name: {"type": "string"} for name in manifest.outputs}
    network = tuple(sorted(p for p in manifest.permissions if p.startswith("net:")))
    workspace_scope = "current" if any(p.startswith("fs:") for p in manifest.permissions) else "none"
    side_effects = ("none",) if manifest.risk_level == "read" else (manifest.risk_level,)
    return ToolCapability(
        name=manifest.name,
        description=manifest.description or manifest.name,
        category=manifest.risk_level,
        input_schema_json=_object_schema(properties, required),
        output_schema_json=_object_schema(output),
        permissions=tuple(sorted(manifest.permissions)),
        workspace_scope=workspace_scope,
        network_scope=network,
        side_effects=side_effects,
        timeout_ms=30_000,
        cancellable=False,
        idempotency="idempotent" if manifest.risk_level == "read" else "non_idempotent",
        max_result_bytes=1_000_000,
        approval_policy="allow" if manifest.risk_level == "read" else "ask",
        audit_events=tuple(manifest.audit_events),
        renderer="text",
        source="atlas",
    )


def capability_from_hermes(descriptor: dict[str, object]) -> ToolCapability:
    required = ("name", "description", "schema", "risk_level", "side_effects")
    missing = [key for key in required if not descriptor.get(key)]
    if missing:
        raise ValueError(f"Hermes capability missing required metadata: {', '.join(missing)}")
    schema = descriptor["schema"]
    if not isinstance(schema, dict):
        raise ValueError("Hermes schema must be an object")
    risk = str(descriptor["risk_level"])
    permissions = tuple(sorted(str(v) for v in descriptor.get("permissions", ())))
    return ToolCapability(
        name=str(descriptor["name"]),
        aliases=tuple(sorted(str(v) for v in descriptor.get("aliases", ()))),
        description=str(descriptor["description"]),
        category=risk,
        input_schema_json=_json(schema),
        output_schema_json=_object_schema({"content": {"type": "string"}}),
        permissions=permissions,
        workspace_scope=str(descriptor.get("workspace_scope", "current" if risk != "network" else "none")),
        network_scope=tuple(sorted(str(v) for v in descriptor.get("network_scope", ()))),
        side_effects=tuple(sorted(str(v) for v in descriptor["side_effects"])),
        timeout_ms=int(descriptor.get("timeout_ms", 30_000)),
        cancellable=bool(descriptor.get("cancellable", True)),
        idempotency=str(descriptor.get("idempotency", "non_idempotent" if risk != "read" else "idempotent")),
        max_result_bytes=int(descriptor.get("max_result_bytes", 1_000_000)),
        approval_policy=str(descriptor.get("approval_policy", "ask" if risk in {"write", "shell"} else "allow")),
        audit_events=tuple(sorted(str(v) for v in descriptor.get("audit_events", _AUDIT))),
        renderer=str(descriptor.get("renderer", "text")),
        source="hermes",
        available=bool(descriptor.get("available", True)),
    )


def capability_from_mcp(descriptor: dict[str, object]) -> ToolCapability:
    annotations = descriptor.get("annotations") or {}
    if not isinstance(annotations, dict):
        raise ValueError("MCP annotations must be an object")
    read_only = annotations.get("readOnlyHint") is True
    risk = "read" if read_only else "write"
    schema = descriptor.get("inputSchema")
    if not isinstance(schema, dict):
        raise ValueError("MCP inputSchema must be an object")
    server = str(descriptor.get("server", "")).strip()
    if not server:
        raise ValueError("MCP descriptor requires server identity")
    return ToolCapability(
        name=str(descriptor.get("name", "")),
        description=str(descriptor.get("description", "")),
        category=risk,
        input_schema_json=_json(schema),
        output_schema_json=_object_schema({"content": {"type": "string"}}),
        permissions=(f"mcp:{server}",),
        workspace_scope="none",
        network_scope=(server,),
        side_effects=("none",) if read_only else ("remote_write",),
        timeout_ms=int(descriptor.get("timeout_ms", 30_000)),
        cancellable=True,
        idempotency="idempotent" if read_only else "non_idempotent",
        max_result_bytes=int(descriptor.get("max_result_bytes", 1_000_000)),
        approval_policy="allow" if read_only else "ask",
        audit_events=_AUDIT,
        renderer="text",
        source="mcp",
    )


def _hermes_risk(name: str, toolset: str) -> tuple[str, tuple[str, ...], str]:
    lowered = f"{toolset}:{name}".lower()
    if name in {"read_file", "search_files", "web_search", "web_extract"}:
        return "read", ("none",), "allow"
    if any(token in lowered for token in ("terminal", "shell", "execute", "code")):
        return "shell", ("process",), "ask"
    if any(token in lowered for token in ("write", "patch", "browser", "cron", "memory")):
        return "write", ("state_change",), "ask"
    raise ValueError(f"Hermes capability {name!r} lacks an explicit risk classification")


def catalog_from_hermes_registry(registry: object) -> tuple[ToolCapability, ...]:
    """Read registry metadata only; never invoke check_fn or dynamic discovery."""

    snapshot = getattr(registry, "_snapshot_entries", None)
    if not callable(snapshot):
        raise ValueError("Hermes registry does not expose a stable metadata snapshot")
    capabilities: list[ToolCapability] = []
    for entry in snapshot():
        name = str(entry.name)
        toolset = str(entry.toolset)
        risk, effects, approval = _hermes_risk(name, toolset)
        max_chars = getattr(entry, "max_result_size_chars", None) or 250_000
        capabilities.append(
            capability_from_hermes(
                {
                    "name": name,
                    "description": str(entry.description or name),
                    "toolset": toolset,
                    "schema": entry.schema,
                    "risk_level": risk,
                    "side_effects": effects,
                    "approval_policy": approval,
                    "permissions": (f"hermes:{toolset}",),
                    "max_result_bytes": int(max_chars) * 4,
                    "available": True,
                }
            )
        )
    return tuple(sorted(capabilities, key=lambda item: item.name))


def build_shipped_catalog() -> ToolCatalog:
    """Build the no-probe catalog from the shipped ATLAS manifest registry."""

    from atlas_runtime.tools.registry import load_manifests

    capabilities = tuple(
        capability_from_atlas(manifest)
        for manifest in load_manifests().values()
    )
    return build_tool_catalog(capabilities)


def write_catalog_artifact(catalog: ToolCatalog, path: Path | str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(catalog.model_dump_json(indent=2) + "\n", encoding="utf-8")


def build_tool_catalog(
    capabilities: Iterable[ToolCapability],
    *,
    catalog_version: str = "1.0.0",
) -> ToolCatalog:
    ordered = tuple(sorted(capabilities, key=lambda item: item.name))
    occupied: set[str] = set()
    for capability in ordered:
        names = (capability.name, *capability.aliases)
        if occupied.intersection(names):
            raise ValueError(f"duplicate capability name or alias: {capability.name}")
        occupied.update(names)
    canonical = _json([item.model_dump(mode="json") for item in ordered])
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ToolCatalog(
        catalog_version=catalog_version,
        catalog_sha256=digest,
        capabilities=ordered,
    )


@dataclass(frozen=True)
class ToolCallError:
    ok: bool
    code: str
    tool_name: str
    detail: str


def normalize_tool_error(reason: str, *, tool_name: str, detail: str = "") -> ToolCallError:
    code = _ERROR_CODES.get(reason, "internal_error")
    safe_detail = _ROLE_TAG.sub("", detail).replace("```", "")[:2000]
    return ToolCallError(ok=False, code=code, tool_name=tool_name, detail=safe_detail)


def narrow_capabilities(
    parents: tuple[ToolCapability, ...],
    children: tuple[ToolCapability, ...],
) -> tuple[ToolCapability, ...]:
    parent_by_name = {item.name: item for item in parents}
    for child in children:
        parent = parent_by_name.get(child.name)
        if parent is None:
            raise ValueError(f"child capability {child.name!r} has no parent")
        widened = (
            _SCOPE_RANK[child.workspace_scope] > _SCOPE_RANK[parent.workspace_scope]
            or _APPROVAL_RANK[child.approval_policy] > _APPROVAL_RANK[parent.approval_policy]
            or not set(child.permissions).issubset(parent.permissions)
            or not set(child.network_scope).issubset(parent.network_scope)
            or child.timeout_ms > parent.timeout_ms
            or child.max_result_bytes > parent.max_result_bytes
        )
        if widened:
            raise ValueError(f"child capability {child.name!r} would widen parent authority")
    return children


__all__ = [
    "ToolCallError",
    "build_tool_catalog",
    "build_shipped_catalog",
    "catalog_from_hermes_registry",
    "capability_from_atlas",
    "capability_from_hermes",
    "capability_from_mcp",
    "narrow_capabilities",
    "normalize_tool_error",
    "write_catalog_artifact",
]
