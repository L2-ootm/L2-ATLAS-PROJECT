"""Hermes-facing knowledge-graph bridge — the `atlas_graph` tool.

Gives the agent first-class read AND write access to the durable ATLAS Brain
graph (0014 brain_nodes/brain_edges) plus the ability to create Graphify tabs
(0025 graph_scopes):

- op=search      — find nodes by label/metadata substring.
- op=explain     — one node with its immediate neighbors.
- op=add_node    — idempotently upsert a node. The id is derived from
                   (entity_type, label) so repeating the same call converges
                   instead of duplicating.
- op=link        — idempotently upsert a relation between two existing nodes.
- op=list_scopes — list custom Graphify scopes (graph tabs).
- op=add_scope   — create a Graphify tab from an existing folder.

Registration mirrors actor_bridge (direct PluginContext registration, D-001
safe, fail-open). All handlers return JSON strings and never raise into the
agent loop. Writes carry provenance: source_id records the creating run.
"""
from __future__ import annotations

import datetime
import json
import logging
import re
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

_bridge_lock = threading.Lock()
_registered = False

_SLUG_RE = re.compile(r"[^a-z0-9]+")

TOOL_SCHEMA = {
    "name": "atlas_graph",
    "description": (
        "ATLAS knowledge graph. Query the durable brain graph (op=search, "
        "op=explain), record new knowledge as nodes/relations (op=add_node, "
        "op=link — idempotent, safe to retry), and manage Graphify tabs "
        "(op=list_scopes, op=add_scope with an existing folder path)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": ["search", "explain", "add_node", "link", "list_scopes", "add_scope"],
                "description": "Graph operation.",
            },
            "query": {"type": "string", "description": "Search text (op=search)."},
            "node_id": {"type": "string", "description": "Node id (op=explain)."},
            "label": {
                "type": "string",
                "description": "Human label (op=add_node) or tab label (op=add_scope).",
            },
            "entity_type": {
                "type": "string",
                "description": "Node type slug, e.g. concept|decision|person|system (op=add_node).",
            },
            "summary": {
                "type": "string",
                "description": "Optional short summary stored in node metadata (op=add_node).",
            },
            "source_id": {"type": "string", "description": "Edge source node id (op=link)."},
            "target_id": {"type": "string", "description": "Edge target node id (op=link)."},
            "relation": {
                "type": "string",
                "description": "Edge relation slug, e.g. relates_to|depends_on (op=link).",
            },
            "project_id": {
                "type": "string",
                "description": "Optional project scope for nodes/edges.",
            },
            "path": {"type": "string", "description": "Existing folder path (op=add_scope)."},
            "kind": {
                "type": "string",
                "enum": ["markdown", "projects"],
                "description": "Scope kind (op=add_scope, default markdown).",
            },
            "limit": {"type": "number", "description": "Result cap for search (default 20)."},
        },
        "required": ["op"],
    },
}


def _tool_error(message: str) -> str:
    return json.dumps({"ok": False, "error": message})


def _shared_state() -> tuple[Any, Optional[threading.Lock]]:
    try:
        import atlas_audit  # noqa: PLC0415

        return atlas_audit.get_connection(), atlas_audit.get_lock()
    except Exception:  # noqa: BLE001
        return None, None


def _current_run_id(parent_agent: Any = None, task_id: Optional[str] = None) -> Optional[str]:
    try:
        import atlas_audit  # noqa: PLC0415

        session_id = getattr(parent_agent, "session_id", None) or task_id
        if not session_id:
            return None
        return atlas_audit.run_for_session(str(session_id)) or None
    except Exception:  # noqa: BLE001
        return None


def _node_view(node: Any) -> dict[str, Any]:
    try:
        metadata = json.loads(node.metadata_json or "{}")
    except (TypeError, ValueError):
        metadata = {}
    return {
        "id": node.id,
        "entity_type": node.entity_type,
        "label": node.label,
        "project_id": node.project_id,
        "confidence": node.confidence,
        "metadata": metadata,
    }


def node_id_for(entity_type: str, label: str) -> str:
    """Stable node id from type+label so repeated add_node calls converge."""
    type_slug = _SLUG_RE.sub("-", entity_type.lower()).strip("-") or "concept"
    label_slug = _SLUG_RE.sub("-", label.lower()).strip("-")[:80]
    if not label_slug:
        raise ValueError("label must contain at least one letter or digit")
    return f"{type_slug}:{label_slug}"


def atlas_graph_tool(
    args: Optional[dict[str, Any]] = None,
    *,
    task_id: Optional[str] = None,
    parent_agent: Any = None,
    **framework: Any,
) -> str:
    """Hermes plugin handler for `atlas_graph`; returns a JSON string."""
    from atlas_runtime import brain_service, graph_scope_service  # noqa: PLC0415
    from atlas_core.schemas.brain import BrainEdge, BrainNode  # noqa: PLC0415

    if args is None:
        known = {
            "op", "query", "node_id", "label", "entity_type", "summary",
            "source_id", "target_id", "relation", "project_id", "path", "kind", "limit",
        }
        args = {key: value for key, value in framework.items() if key in known}
    if not isinstance(args, dict):
        return _tool_error("atlas_graph arguments must be an object")
    op = str(args.get("op") or "search")
    conn, lock = _shared_state()
    if conn is None or lock is None:
        return _tool_error("knowledge graph unavailable: no ATLAS connection bound")
    project_id = (args.get("project_id") or None) or None

    try:
        if op == "search":
            query = str(args.get("query") or "").strip()
            if not query:
                return _tool_error("op=search requires query")
            limit = int(args.get("limit") or 20)
            nodes = brain_service.search(conn, query, project_id=project_id, limit=limit)
            return json.dumps({"ok": True, "nodes": [_node_view(n) for n in nodes]})

        if op == "explain":
            node_id = str(args.get("node_id") or "").strip()
            if not node_id:
                return _tool_error("op=explain requires node_id")
            node = brain_service.explain(conn, node_id)
            if node is None:
                return _tool_error(f"unknown node: {node_id}")
            related = brain_service.neighbors(
                conn, node_id, project_id=node.project_id, depth=1, limit=20
            )
            return json.dumps(
                {
                    "ok": True,
                    "node": _node_view(node),
                    "neighbors": [_node_view(n) for n in related],
                }
            )

        if op == "add_node":
            label = str(args.get("label") or "").strip()
            entity_type = str(args.get("entity_type") or "concept").strip() or "concept"
            if not label:
                return _tool_error("op=add_node requires label")
            run_id = _current_run_id(parent_agent, task_id) or "agent"
            metadata: dict[str, Any] = {}
            summary = str(args.get("summary") or "").strip()
            if summary:
                metadata["summary"] = summary[:2000]
            node = BrainNode(
                id=node_id_for(entity_type, label),
                entity_type=entity_type,
                label=label,
                project_id=project_id,
                source_id=f"run:{run_id}",
                source_version=_now(),
                updated_at=_now(),
                confidence=0.8,
                metadata_json=json.dumps(metadata),
            )
            with lock:
                brain_service.upsert_node(conn, node)
            return json.dumps({"ok": True, "node": _node_view(node)})

        if op == "link":
            source_id = str(args.get("source_id") or "").strip()
            target_id = str(args.get("target_id") or "").strip()
            relation = str(args.get("relation") or "relates_to").strip() or "relates_to"
            if not source_id or not target_id:
                return _tool_error("op=link requires source_id and target_id")
            edge = BrainEdge(
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                project_id=project_id,
            )
            with lock:
                brain_service.upsert_edge(conn, edge)
            return json.dumps(
                {"ok": True, "edge": {"source_id": source_id, "target_id": target_id, "relation": relation}}
            )

        if op == "list_scopes":
            scopes = graph_scope_service.list_scopes(conn)
            return json.dumps(
                {
                    "ok": True,
                    "builtin": list(graph_scope_service.BUILTIN_SCOPES),
                    "custom": scopes,
                }
            )

        if op == "add_scope":
            label = str(args.get("label") or "").strip()
            path = str(args.get("path") or "").strip()
            kind = str(args.get("kind") or "markdown").strip() or "markdown"
            if not label or not path:
                return _tool_error("op=add_scope requires label and path")
            scope = graph_scope_service.create_scope(
                conn, lock, label=label, root_path=path, kind=kind
            )
            return json.dumps({"ok": True, "scope": scope})

        return _tool_error(f"unknown op: {op!r}")
    except ValueError as exc:
        return _tool_error(str(exc))
    except Exception as exc:  # noqa: BLE001 — tools must not throw into the loop
        logger.warning("atlas_graph tool failed: %s", exc)
        return _tool_error(f"knowledge graph error: {exc}")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def ensure_graph_bridge() -> bool:
    """Register the graph tool with the foundation, once. Fail-open."""
    global _registered
    with _bridge_lock:
        if _registered:
            return True
        try:
            from atlas_runtime.subagent_service import _foundation_on_path  # noqa: PLC0415

            if not _foundation_on_path():
                return False
            from hermes_cli.plugins import (  # noqa: PLC0415
                PluginContext,
                PluginManifest,
                get_plugin_manager,
            )

            manifest = PluginManifest(
                name="atlas_graph",
                version="0.1.0",
                description="ATLAS knowledge graph read/write (registered in-process)",
                source="atlas-runtime",
            )
            ctx = PluginContext(manifest, get_plugin_manager())
            ctx.register_tool(
                name="atlas_graph",
                toolset="atlas",
                schema=TOOL_SCHEMA,
                handler=atlas_graph_tool,
                description="Knowledge graph: search/explain/add_node/link/list_scopes/add_scope",
            )
            _registered = True
            return True
        except Exception as exc:  # noqa: BLE001 — fail-open
            logger.debug("graph bridge unavailable: %s", exc)
            return False


__all__ = [
    "TOOL_SCHEMA",
    "atlas_graph_tool",
    "ensure_graph_bridge",
    "node_id_for",
]
