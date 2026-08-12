"""Hermes-facing module bridge — the `atlas_module` tool.

One tool for every active module. A module declares capability in `module.yaml`
and ATLAS executes it, so a newly installed module becomes agent-usable with
zero runtime changes — that is the whole point of the v2 capability contract
(docs/plans/2026-08-12-module-capabilities-v2-and-outreach-design.md).

Discover:

- op=list      — active modules with their collections, workflows and commands.
- op=describe  — one module's full capability surface.
- op=context   — read declared doctrine (including `inject: on_demand` files
                 that never enter the prompt automatically).
- op=workflow  — the ordered steps of a named play.

Records (the CRM substrate — module_records, 0034):

- op=query     — filter/search a collection, newest first.
- op=get       — one record by id.
- op=create    — insert (id collision merges, so retries converge).
- op=update    — merge fields into an existing record.
- op=delete    — soft-delete; the removed payload comes back as an undo record.
- op=stats     — live record counts per collection.

Registration mirrors graph_bridge (direct PluginContext registration, D-001
safe, fail-open). Every handler returns a JSON string and never raises into the
agent loop. Inactive modules are invisible here: the record data survives
deactivation, the capability does not.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

_bridge_lock = threading.Lock()
_registered = False

TOOL_SCHEMA = {
    "name": "atlas_module",
    "description": (
        "ATLAS modules — the operator's active optional capabilities. Discover "
        "what is available (op=list, op=describe), read a module's doctrine "
        "(op=context) and plays (op=workflow), and work with its records "
        "(op=query, op=get, op=create, op=update, op=delete, op=stats). "
        "Records are durable module data (e.g. an outreach CRM): create one "
        "when you learn something worth keeping, update it when it changes. "
        "Only active modules are reachable."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": [
                    "list", "describe", "context", "workflow",
                    "query", "get", "create", "update", "delete", "stats",
                ],
                "description": "Module operation.",
            },
            "module": {
                "type": "string",
                "description": "Module id (required for everything except op=list).",
            },
            "collection": {
                "type": "string",
                "description": "Collection id (record ops).",
            },
            "record_id": {
                "type": "string",
                "description": "Record id (op=get|update|delete; optional on create).",
            },
            "data": {
                "type": "object",
                "description": "Field values (op=create|update). Unknown fields are rejected.",
            },
            "where": {
                "type": "object",
                "description": "Exact field matches (op=query), e.g. {\"stage\": \"ready\"}.",
            },
            "search": {
                "type": "string",
                "description": "Free-text match across a record's values (op=query).",
            },
            "status": {
                "type": "string",
                "enum": ["active", "archived", "any"],
                "description": "Record status filter (op=query) or new status (op=update).",
            },
            "context_id": {
                "type": "string",
                "description": "Doctrine file id (op=context); omit for all of them.",
            },
            "workflow_id": {
                "type": "string",
                "description": "Workflow id (op=workflow); omit to list them.",
            },
            "limit": {
                "type": "number",
                "description": "Max rows (op=query, default 50, max 500).",
            },
        },
        "required": ["op"],
    },
}

_KNOWN_ARGS = frozenset(
    {
        "op", "module", "collection", "record_id", "data", "where", "search",
        "status", "context_id", "workflow_id", "limit",
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


def _module_summary(manifest: dict[str, Any], module_service: Any) -> dict[str, Any]:
    caps = module_service.capability
    return {
        "id": manifest.get("id", ""),
        "name": manifest.get("name", ""),
        "version": manifest.get("version", ""),
        "description": manifest.get("description", ""),
        "collections": [
            {"id": c["id"], "title": c.get("title", c["id"]),
             "fields": [f["name"] for f in c.get("fields", [])]}
            for c in caps(manifest, "collections")
        ],
        "workflows": [
            {"id": w["id"], "title": w.get("title", w["id"]),
             "description": w.get("description", "")}
            for w in caps(manifest, "workflows")
        ],
        "commands": [f"/{c['name']}" for c in caps(manifest, "commands")],
        "context": [
            {"id": c["id"], "title": c.get("title", c["id"]), "inject": c.get("inject", "always")}
            for c in caps(manifest, "context")
        ],
        "mcp": [m["name"] for m in caps(manifest, "mcp")],
    }


def atlas_module_tool(
    args: Optional[dict[str, Any]] = None,
    *,
    task_id: Optional[str] = None,
    parent_agent: Any = None,
    **framework: Any,
) -> str:
    """Hermes plugin handler for `atlas_module`; returns a JSON string."""
    from atlas_runtime import module_data_service, module_service  # noqa: PLC0415

    if args is None:
        args = {key: value for key, value in framework.items() if key in _KNOWN_ARGS}
    if not isinstance(args, dict):
        return _tool_error("atlas_module arguments must be an object")
    op = str(args.get("op") or "list")
    conn, lock = _shared_state()
    if conn is None or lock is None:
        return _tool_error("modules unavailable: no ATLAS connection bound")

    module_id = str(args.get("module") or "").strip()
    collection_id = str(args.get("collection") or "").strip()
    run_id = _current_run_id(parent_agent, task_id)

    try:
        if op == "list":
            manifests = module_service.active_manifests(conn)
            return json.dumps(
                {
                    "ok": True,
                    "op": op,
                    "count": len(manifests),
                    "modules": [_module_summary(m, module_service) for m in manifests],
                    "hint": (
                        "no active modules — the operator activates them with "
                        "`atlas module activate <id>`"
                    ) if not manifests else "",
                }
            )

        if not module_id:
            return _tool_error(f"op={op} requires 'module'")
        manifest = module_service.active_manifest(conn, module_id)
        if manifest is None:
            active = [m.get("id") for m in module_service.active_manifests(conn)]
            return _tool_error(
                f"module {module_id!r} is not active (active: {', '.join(active) or 'none'})"
            )

        if op == "describe":
            summary = _module_summary(manifest, module_service)
            summary["collection_detail"] = module_service.capability(manifest, "collections")
            return json.dumps({"ok": True, "op": op, "module": summary})

        if op == "context":
            wanted = str(args.get("context_id") or "").strip()
            blocks = []
            for entry in module_service.capability(manifest, "context"):
                if wanted and entry["id"] != wanted:
                    continue
                text = module_service.read_context_file(manifest, entry)
                blocks.append(
                    {
                        "id": entry["id"],
                        "title": entry.get("title", entry["id"]),
                        "inject": entry.get("inject", "always"),
                        "text": text or "(file missing on disk)",
                    }
                )
            if wanted and not blocks:
                known = [c["id"] for c in module_service.capability(manifest, "context")]
                return _tool_error(
                    f"module {module_id!r} has no context {wanted!r}"
                    f" (known: {', '.join(known) or 'none'})"
                )
            return json.dumps({"ok": True, "op": op, "module": module_id, "context": blocks})

        if op == "workflow":
            workflows = module_service.capability(manifest, "workflows")
            wanted = str(args.get("workflow_id") or "").strip()
            if not wanted:
                return json.dumps(
                    {
                        "ok": True, "op": op, "module": module_id,
                        "workflows": [
                            {"id": w["id"], "title": w.get("title", w["id"]),
                             "description": w.get("description", "")}
                            for w in workflows
                        ],
                    }
                )
            for workflow in workflows:
                if workflow["id"] == wanted:
                    return json.dumps(
                        {"ok": True, "op": op, "module": module_id, "workflow": workflow}
                    )
            return _tool_error(
                f"module {module_id!r} has no workflow {wanted!r}"
                f" (known: {', '.join(w['id'] for w in workflows) or 'none'})"
            )

        if op == "stats":
            return json.dumps(
                {
                    "ok": True, "op": op, "module": module_id,
                    "collections": module_data_service.collection_stats(conn, module_id),
                }
            )

        # --- record ops ----------------------------------------------------
        if not collection_id:
            return _tool_error(f"op={op} requires 'collection'")

        if op == "query":
            where = args.get("where") if isinstance(args.get("where"), dict) else None
            records = module_data_service.query_records(
                conn, module_id, collection_id,
                where=where,
                search=str(args.get("search") or ""),
                status=str(args.get("status") or "active"),
                limit=int(args.get("limit") or module_data_service.DEFAULT_LIMIT),
            )
            return json.dumps(
                {
                    "ok": True, "op": op, "module": module_id,
                    "collection": collection_id,
                    "count": len(records), "records": records,
                }
            )

        record_id = str(args.get("record_id") or "").strip()

        if op == "get":
            if not record_id:
                return _tool_error("op=get requires 'record_id'")
            module_data_service.resolve_collection(conn, module_id, collection_id)
            record = module_data_service.get_record(conn, module_id, collection_id, record_id)
            if record is None:
                return _tool_error(f"no record {record_id!r} in {module_id}/{collection_id}")
            return json.dumps({"ok": True, "op": op, "record": record})

        data = args.get("data")
        if op in ("create", "update") and not isinstance(data, dict):
            return _tool_error(f"op={op} requires 'data' as an object")

        if op == "create":
            record = module_data_service.create_record(
                conn, lock,
                module_id=module_id, collection_id=collection_id,
                data=dict(data or {}), record_id=record_id or None, run_id=run_id,
            )
            return json.dumps({"ok": True, "op": op, "record": record})

        if op == "update":
            if not record_id:
                return _tool_error("op=update requires 'record_id'")
            status = str(args.get("status") or "").strip() or None
            if status == "any":
                status = None
            record = module_data_service.update_record(
                conn, lock,
                module_id=module_id, collection_id=collection_id,
                record_id=record_id, data=dict(data or {}),
                run_id=run_id, status=status,
            )
            return json.dumps({"ok": True, "op": op, "record": record})

        if op == "delete":
            if not record_id:
                return _tool_error("op=delete requires 'record_id'")
            removed = module_data_service.delete_record(
                conn, lock,
                module_id=module_id, collection_id=collection_id,
                record_id=record_id, run_id=run_id,
            )
            return json.dumps({"ok": True, "op": op, "removed": removed})

        return _tool_error(f"unknown op {op!r}")
    except module_data_service.ModuleDataError as exc:
        return _tool_error(str(exc))
    except Exception as exc:  # noqa: BLE001 — never raise into the agent loop
        logger.debug("atlas_module op=%s failed: %s", op, exc)
        return _tool_error(f"atlas_module {op} failed: {exc}")


def ensure_module_bridge() -> bool:
    """Register the module tool with the foundation, once. Fail-open."""
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
                name="atlas_module",
                version="0.1.0",
                description="ATLAS module capabilities (registered in-process)",
                source="atlas-runtime",
            )
            ctx = PluginContext(manifest, get_plugin_manager())
            ctx.register_tool(
                name="atlas_module",
                toolset="atlas",
                schema=TOOL_SCHEMA,
                handler=atlas_module_tool,
                description=(
                    "Active module capabilities: list/describe, context, workflow, "
                    "and record query/get/create/update/delete/stats"
                ),
            )
            _registered = True
            return True
        except Exception as exc:  # noqa: BLE001 — fail-open
            logger.debug("module bridge unavailable: %s", exc)
            return False


__all__ = ["TOOL_SCHEMA", "atlas_module_tool", "ensure_module_bridge"]
