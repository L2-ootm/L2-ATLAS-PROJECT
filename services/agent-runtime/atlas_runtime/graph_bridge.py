"""Hermes plugin bridge for the bounded ``atlas_graph`` query tool."""
from __future__ import annotations

import json
import logging
import threading
from typing import Any

from atlas_runtime.graph_query import query_graph

logger = logging.getLogger(__name__)
_bridge_lock = threading.Lock()
_registered = False

TOOL_SCHEMA = {
    "name": "atlas_graph",
    "description": (
        "Read ATLAS knowledge graphs. Search and traverse the global, projects, "
        "Obsidian, or agent-context scope without mutating or rebuilding them."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["search", "node", "neighbors", "path", "content", "stats"]},
            "scope": {"type": "string", "enum": ["global", "projects", "obsidian", "agent"], "default": "agent"},
            "query": {"type": "string", "description": "Text to match for op=search."},
            "node_id": {"type": "string", "description": "Origin node for node/neighbors/path/content."},
            "target_id": {"type": "string", "description": "Destination node for op=path."},
            "depth": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 12},
        },
        "required": ["op"],
    },
}


def atlas_graph_tool(args: dict[str, Any], **_kwargs: Any) -> str:
    if not isinstance(args, dict):
        return json.dumps({"ok": False, "error": "atlas_graph arguments must be an object"})
    try:
        return json.dumps(query_graph(**args), ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001 — tool boundary is fail-open
        logger.warning("atlas_graph query failed: %s", exc)
        return json.dumps({"ok": False, "error": str(exc)})


def ensure_graph_bridge() -> bool:
    """Register the graph tool through Hermes's in-process plugin seam once."""
    global _registered
    with _bridge_lock:
        if _registered:
            return True
        try:
            from atlas_runtime.subagent_service import _foundation_on_path  # noqa: PLC0415

            if not _foundation_on_path():
                return False
            from hermes_cli.plugins import PluginContext, PluginManifest, get_plugin_manager  # noqa: PLC0415

            manifest = PluginManifest(
                name="atlas_graph_query",
                version="0.1.0",
                description="ATLAS bounded read-only graph query plane",
                source="atlas-runtime",
            )
            ctx = PluginContext(manifest, get_plugin_manager())
            ctx.register_tool(
                name="atlas_graph",
                toolset="atlas",
                schema=TOOL_SCHEMA,
                handler=atlas_graph_tool,
                description="Search and traverse ATLAS knowledge graphs",
            )
            _registered = True
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("graph bridge unavailable: %s", exc)
            return False


__all__ = ["ensure_graph_bridge", "atlas_graph_tool", "TOOL_SCHEMA"]
