"""Hermes-facing knowledge-graph bridge — the `atlas_graph` tool.

Gives the agent first-class read, write AND curation access to the durable
ATLAS Brain graph (0014 brain_nodes/brain_edges) plus management of Graphify
tabs (0025 graph_scopes).

Read:

- op=search      — find nodes by label/metadata substring.
- op=explain     — one node with its immediate neighbors.
- op=list        — browse the graph by entity_type (what is in here?).
- op=stats       — whole-graph inventory: counts by type, relation, project.
- op=neighbors   — walk out from a node up to depth 4.
- op=path        — shortest relation chain between two nodes.

Write:

- op=add_node    — idempotently upsert a node. The id is derived from
                   (entity_type, label) so repeating the same call converges
                   instead of duplicating.
- op=link        — idempotently upsert a relation between two existing nodes.

Curate — the graph has to be correctable, not only growable, or every wrong
fact it ever learned stays forever:

- op=update      — correct a node's label/type/summary/confidence. Renaming
                   re-keys the node and rewrites its edges so the add_node
                   convergence invariant survives.
- op=forget      — delete a node and its edges. Returns the removed payload so
                   the run transcript carries an undo record.
- op=unlink      — delete one relation; already-gone is not an error.

Graphify tabs:

- op=list_scopes | add_scope | remove_scope | set_scope_root.

Registration mirrors actor_bridge (direct PluginContext registration, D-001
safe, fail-open). All handlers return JSON strings and never raise into the
agent loop. Writes carry provenance: source_id records the creating run.
"""
from __future__ import annotations

import datetime
import json
import logging
import re
import sqlite3
import threading
from typing import Any, Optional

from atlas_core.schemas import provenance

logger = logging.getLogger(__name__)

_bridge_lock = threading.Lock()
_registered = False

_SLUG_RE = re.compile(r"[^a-z0-9]+")

TOOL_SCHEMA = {
    "name": "atlas_graph",
    "description": (
        "ATLAS knowledge graph. Query the durable brain graph (op=search, "
        "op=explain, op=list, op=stats, op=neighbors, op=path), record new "
        "knowledge (op=add_node, op=link — idempotent, safe to retry), correct "
        "or remove what is wrong (op=update, op=forget, op=unlink), and manage "
        "Graphify tabs (op=list_scopes, op=add_scope, op=remove_scope, "
        "op=set_scope_root). Prefer op=update over adding a second node when a "
        "fact changes, and op=forget when it turns out to be wrong."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": [
                    "search", "explain", "list", "stats", "neighbors", "path",
                    "add_node", "link", "update", "forget", "unlink",
                    "list_scopes", "add_scope", "remove_scope", "set_scope_root",
                ],
                "description": "Graph operation.",
            },
            "query": {"type": "string", "description": "Search text (op=search)."},
            "node_id": {
                "type": "string",
                "description": "Node id (op=explain|neighbors|update|forget).",
            },
            "label": {
                "type": "string",
                "description": (
                    "Human label (op=add_node), corrected label (op=update), or "
                    "tab label (op=add_scope)."
                ),
            },
            "entity_type": {
                "type": "string",
                "description": (
                    "Node type slug, e.g. concept|decision|person|system "
                    "(op=add_node|update, filter for op=list)."
                ),
            },
            "summary": {
                "type": "string",
                "description": "Short summary stored in node metadata (op=add_node|update).",
            },
            "confidence": {
                "type": "number",
                "description": (
                    "Ranking hint 0..1 within a grade (op=add_node|update). This does "
                    "NOT set how trusted the node is — that is derived from `evidence`."
                ),
            },
            "evidence": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "op=add_node: ids of tool calls or audit events from THIS run that "
                    "back the claim. Citing real evidence records the node as `derived`; "
                    "citing nothing records it as `asserted`, which is stored but kept "
                    "out of future runs' context. Ids that do not resolve reject the "
                    "write — do not invent them."
                ),
            },
            "source_id": {
                "type": "string",
                "description": "Edge source node id (op=link|unlink|path).",
            },
            "target_id": {
                "type": "string",
                "description": "Edge target node id (op=link|unlink|path).",
            },
            "relation": {
                "type": "string",
                "description": "Edge relation slug, e.g. relates_to|depends_on (op=link|unlink).",
            },
            "project_id": {
                "type": "string",
                "description": "Optional project scope for nodes/edges.",
            },
            "depth": {
                "type": "number",
                "description": "Traversal depth 1-4 (op=neighbors|path, default 1).",
            },
            "scope_id": {
                "type": "string",
                "description": "Graphify tab id (op=remove_scope|set_scope_root).",
            },
            "path": {
                "type": "string",
                "description": "Existing folder path (op=add_scope|set_scope_root).",
            },
            "kind": {
                "type": "string",
                "enum": ["markdown", "projects"],
                "description": "Scope kind (op=add_scope, default markdown).",
            },
            "limit": {
                "type": "number",
                "description": "Result cap for search/list/neighbors (default 20).",
            },
        },
        "required": ["op"],
    },
}

_KNOWN_ARGS = frozenset(
    {
        "op", "query", "node_id", "label", "entity_type", "summary", "confidence",
        "evidence", "source_id", "target_id", "relation", "project_id", "depth",
        "scope_id", "path", "kind", "limit",
    }
)


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
        # Returned on every read so the agent sees the standing of what it is
        # about to build on, not only of what it just wrote.
        "grade": getattr(node, "grade", provenance.ASSERTED),
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
    from atlas_runtime import (  # noqa: PLC0415
        brain_service,
        graph_scope_service,
        memory_router,
    )
    from atlas_core.schemas.brain import BrainEdge, BrainNode  # noqa: PLC0415

    if args is None:
        args = {key: value for key, value in framework.items() if key in _KNOWN_ARGS}
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

        if op == "list":
            nodes = brain_service.list_nodes(
                conn,
                project_id=project_id,
                entity_type=(args.get("entity_type") or None) or None,
                limit=int(args.get("limit") or 20),
            )
            return json.dumps({"ok": True, "nodes": [_node_view(n) for n in nodes]})

        if op == "stats":
            return json.dumps({"ok": True, "stats": brain_service.stats(conn)})

        if op == "neighbors":
            node_id = str(args.get("node_id") or "").strip()
            if not node_id:
                return _tool_error("op=neighbors requires node_id")
            node = brain_service.explain(conn, node_id)
            if node is None:
                return _tool_error(f"unknown node: {node_id}")
            related = brain_service.neighbors(
                conn,
                node_id,
                project_id=node.project_id,
                depth=int(args.get("depth") or 1),
                limit=int(args.get("limit") or 20),
            )
            return json.dumps(
                {
                    "ok": True,
                    "node_id": node_id,
                    "edges": list(brain_service.edges_for(conn, node_id)),
                    "neighbors": [_node_view(n) for n in related],
                }
            )

        if op == "path":
            source_id = str(args.get("source_id") or "").strip()
            target_id = str(args.get("target_id") or "").strip()
            if not source_id or not target_id:
                return _tool_error("op=path requires source_id and target_id")
            # find_path scopes on an exact project_id; the tool's default scope
            # is the global (NULL) one, matching add_node with no project_id.
            chain = brain_service.find_path(
                conn,
                source_id,
                target_id,
                project_id=project_id,
                max_depth=int(args.get("depth") or 4),
            )
            return json.dumps({"ok": True, "path": list(chain), "found": bool(chain)})

        if op == "add_node":
            label = str(args.get("label") or "").strip()
            entity_type = str(args.get("entity_type") or "concept").strip() or "concept"
            if not label:
                return _tool_error("op=add_node requires label")
            run_id = _current_run_id(parent_agent, task_id) or "agent"
            cited = _citations(args)
            resolved, unresolved = _resolve_citations(conn, run_id, cited)
            if unresolved:
                # A citation that does not resolve is worth surfacing rather than
                # quietly downgrading: either the model invented an id, or it is
                # pointing at evidence from a different run. Both are wrong in
                # ways the agent can correct on the next attempt.
                return _tool_error(
                    "evidence ids not found in this run's audit trail: "
                    + ", ".join(sorted(unresolved))
                    + ". Cite tool calls made in this run, or omit `evidence` "
                    "and the node will be recorded as unbacked."
                )
            metadata: dict[str, Any] = {}
            # Redact on the way IN. The router redacts on the way out, so a secret
            # written here used to be scrubbed in transit while sitting in the
            # clear in the database forever.
            summary = memory_router.redact(str(args.get("summary") or "").strip())
            if summary:
                metadata["summary"] = summary[:2000]
            if resolved:
                metadata["evidence"] = resolved[:20]
            node = BrainNode(
                id=node_id_for(entity_type, label),
                entity_type=entity_type,
                label=memory_router.redact(label),
                project_id=project_id,
                source_id=f"run:{run_id}",
                source_version=_now(),
                updated_at=_now(),
                confidence=_confidence(args, default=0.8),
                grade=_grade_for_write(resolved),
                metadata_json=json.dumps(metadata),
            )
            with lock:
                outcome = brain_service.upsert_node_checked(conn, node)
            if not outcome.written:
                # Refused, and told why. A silent no-op would be repeated.
                return json.dumps({
                    "ok": False,
                    "error": (
                        "a better-established claim about this entity is already "
                        f"recorded ({outcome.conflict['incumbent_grade']} beats "
                        f"{node.grade}). Your claim was kept as a conflict, not "
                        "discarded."
                    ),
                    "conflict": outcome.conflict,
                    "node": _node_view(outcome.node),
                })
            return json.dumps({"ok": True, "node": _node_view(outcome.node)})

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

        if op == "update":
            node_id = str(args.get("node_id") or "").strip()
            if not node_id:
                return _tool_error("op=update requires node_id")
            current = brain_service.explain(conn, node_id)
            if current is None:
                return _tool_error(f"unknown node: {node_id}")
            label = str(args.get("label") or "").strip() or None
            entity_type = str(args.get("entity_type") or "").strip() or None
            summary = str(args.get("summary") or "").strip() or None
            confidence = _confidence(args, default=None)
            if label is None and entity_type is None and summary is None and confidence is None:
                return _tool_error(
                    "op=update needs at least one of label, entity_type, summary, confidence"
                )
            # Re-key whenever type/label change so id stays == node_id_for(type,
            # label) and a later add_node converges instead of duplicating.
            new_id = None
            if label is not None or entity_type is not None:
                new_id = node_id_for(entity_type or current.entity_type, label or current.label)
                if new_id == node_id:
                    new_id = None
            run_id = _current_run_id(parent_agent, task_id) or "agent"
            with lock:
                updated = brain_service.update_node(
                    conn,
                    node_id,
                    label=label,
                    entity_type=entity_type,
                    confidence=confidence,
                    metadata={"summary": summary[:2000]} if summary else None,
                    source_id=f"run:{run_id}",
                    new_id=new_id,
                )
            return json.dumps(
                {"ok": True, "node": _node_view(updated), "renamed_from": node_id if new_id else None}
            )

        if op == "forget":
            node_id = str(args.get("node_id") or "").strip()
            if not node_id:
                return _tool_error("op=forget requires node_id")
            with lock:
                removed = brain_service.delete_node(conn, node_id)
            if removed is None:
                return _tool_error(f"unknown node: {node_id}")
            # The removed payload is the undo record — return it in full.
            return json.dumps({"ok": True, "removed": removed})

        if op == "unlink":
            source_id = str(args.get("source_id") or "").strip()
            target_id = str(args.get("target_id") or "").strip()
            relation = str(args.get("relation") or "relates_to").strip() or "relates_to"
            if not source_id or not target_id:
                return _tool_error("op=unlink requires source_id and target_id")
            with lock:
                deleted = brain_service.delete_edge(conn, source_id, target_id, relation)
            # Already-gone is success: unlink must be safe to retry.
            return json.dumps({"ok": True, "deleted": deleted})

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

        if op == "remove_scope":
            scope_id = str(args.get("scope_id") or "").strip()
            if not scope_id:
                return _tool_error("op=remove_scope requires scope_id")
            graph_scope_service.delete_scope(conn, lock, scope_id)
            return json.dumps({"ok": True, "removed": scope_id})

        if op == "set_scope_root":
            scope_id = str(args.get("scope_id") or "").strip()
            path = str(args.get("path") or "").strip()
            if not scope_id or not path:
                return _tool_error("op=set_scope_root requires scope_id and path")
            scope = graph_scope_service.set_scope_root(
                conn, lock, scope_id=scope_id, root_path=path
            )
            return json.dumps({"ok": True, "scope": scope})

        return _tool_error(f"unknown op: {op!r}")
    except ValueError as exc:
        return _tool_error(str(exc))
    except Exception as exc:  # noqa: BLE001 — tools must not throw into the loop
        logger.warning("atlas_graph tool failed: %s", exc)
        return _tool_error(f"knowledge graph error: {exc}")


def _confidence(args: dict[str, Any], *, default: float | None) -> float | None:
    """Parse the optional confidence argument, clamped to the schema's 0..1.

    Models pass confidence as a string often enough that rejecting one would
    fail a legitimate call; an unparseable value falls back to the default
    rather than erroring the whole op.
    """
    raw = args.get("confidence")
    if raw is None or raw == "":
        return default
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return default


def _citations(args: dict[str, Any]) -> list[str]:
    """The evidence ids the caller offered, in whatever shape the model sent.

    Models pass a list, a comma-joined string, or a bare id with roughly equal
    frequency. All three mean the same thing, and rejecting two of them would
    push callers back toward citing nothing — which is the outcome this whole
    mechanism exists to make unattractive.
    """
    raw = args.get("evidence")
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(part).strip() for part in raw if str(part).strip()]
    return []


def _resolve_citations(
    conn: sqlite3.Connection, run_id: str, cited: list[str]
) -> tuple[list[str], list[str]]:
    """Split cited ids into those this run actually produced and those it did not.

    A citation is checked against `audit_events` for *this* run, by event id or
    tool call id. Scoping to the run is the point: without it a model could cite
    any id in the database, and a citation that cannot be wrong is not evidence.
    """
    if not cited or not run_id or run_id == "agent":
        return [], list(cited)
    placeholders = ",".join("?" for _ in cited)
    try:
        rows = conn.execute(
            f"SELECT id, tool_call_id FROM audit_events WHERE run_id=? "  # noqa: S608
            f"AND (id IN ({placeholders}) OR tool_call_id IN ({placeholders}))",
            (run_id, *cited, *cited),
        ).fetchall()
    except sqlite3.Error as exc:
        # Unreadable audit trail must not reject an otherwise good write; it
        # only costs the node its promotion to `derived`.
        logger.debug("citation check failed for run %s: %s", run_id, exc)
        return [], list(cited)
    known = {str(value) for row in rows for value in row if value}
    resolved = [cid for cid in cited if cid in known]
    return resolved, [cid for cid in cited if cid not in known]


def _grade_for_write(resolved: list[str]) -> str:
    """What a node written through this tool is entitled to claim.

    `derived` is the ceiling for anything an agent writes, even with citations:
    it read some evidence and drew a conclusion, which is not the same as the
    conclusion having been checked. Promotion to `verified` happens elsewhere,
    from the verification gate's verdict, and never on the writer's say-so.
    """
    return provenance.DERIVED if resolved else provenance.ASSERTED


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
                description=(
                    "Knowledge graph: search/explain/list/stats/neighbors/path, "
                    "add_node/link, update/forget/unlink, and Graphify tab management"
                ),
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
