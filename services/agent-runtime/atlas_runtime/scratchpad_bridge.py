"""Hermes-facing scratchpad bridge — the `atlas_scratchpad` tool.

Working memory the agent owns, outside the transcript. A plan written here
survives a compaction; a finding written here is not re-derived three turns
later; a draft written here can be picked up by the next run on the same
session. Entries carry a TTL so the scratchpad does not become a junk drawer
(`scratchpad_service` for the policy semantics).

Ops: write | append | read | list | remove | pin | sweep.

The run and session ids are resolved from the harness binding, not from model
input — an agent cannot claim to be another run, and the default `ttl=session`
means notes disappear with the work they belonged to unless deliberately kept.
Registration mirrors graph_bridge (direct PluginContext registration, D-001
safe, fail-open); every handler returns a JSON string.
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
    "name": "atlas_scratchpad",
    "description": (
        "Your scratchpad: durable working memory outside the transcript. "
        "op=write a plan/finding/draft you must not lose, op=append to extend "
        "it, op=read or op=list to recover it after a context reset, op=remove "
        "when it is spent, op=pin to keep it beyond its TTL. Prefer writing the "
        "plan here before a long task and re-reading it when you resume. "
        "Entries default to the current run/session and expire with it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": ["write", "append", "read", "list", "remove", "pin", "sweep"],
                "description": "Scratchpad operation.",
            },
            "id": {
                "type": "string",
                "description": "Entry id (op=read|remove|pin; optional on write — derived from title).",
            },
            "title": {"type": "string", "description": "Short title (op=write|append)."},
            "body": {"type": "string", "description": "Entry content (op=write|append)."},
            "kind": {
                "type": "string",
                "enum": ["note", "plan", "finding", "draft", "artifact", "tool"],
                "description": "What this entry is (default note).",
            },
            "scope": {
                "type": "string",
                "enum": ["run", "session", "project", "global"],
                "description": "Who it belongs to (default run).",
            },
            "ttl": {
                "type": "string",
                "enum": ["run", "session", "next_startup", "hours", "permanent"],
                "description": "When it expires (default session).",
            },
            "expires_in_hours": {
                "type": "number",
                "description": "Lifetime when ttl=hours (default 24).",
            },
            "path": {
                "type": "string",
                "description": "Optional file this entry refers to (e.g. a generated script).",
            },
            "pinned": {"type": "boolean", "description": "Pin state (op=pin)."},
            "search": {"type": "string", "description": "Substring filter (op=list)."},
            "limit": {"type": "number", "description": "Max entries (op=list, default 25)."},
        },
        "required": ["op"],
    },
}

_KNOWN_ARGS = frozenset(
    {
        "op", "id", "title", "body", "kind", "scope", "ttl", "expires_in_hours",
        "path", "pinned", "search", "limit",
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


def _binding(parent_agent: Any = None, task_id: Optional[str] = None) -> tuple[str, str]:
    """(run_id, session_id) for the calling agent; ("", "") when unbound."""
    try:
        import atlas_audit  # noqa: PLC0415

        session_id = getattr(parent_agent, "session_id", None) or task_id or ""
        if not session_id:
            return "", ""
        run_id = atlas_audit.run_for_session(str(session_id)) or ""
        return str(run_id), str(session_id)
    except Exception:  # noqa: BLE001
        return "", ""


def atlas_scratchpad_tool(
    args: Optional[dict[str, Any]] = None,
    *,
    task_id: Optional[str] = None,
    parent_agent: Any = None,
    **framework: Any,
) -> str:
    """Hermes plugin handler for `atlas_scratchpad`; returns a JSON string."""
    from atlas_runtime import scratchpad_service  # noqa: PLC0415

    if args is None:
        args = {key: value for key, value in framework.items() if key in _KNOWN_ARGS}
    if not isinstance(args, dict):
        return _tool_error("atlas_scratchpad arguments must be an object")
    op = str(args.get("op") or "list")
    conn, lock = _shared_state()
    if conn is None or lock is None:
        return _tool_error("scratchpad unavailable: no ATLAS connection bound")
    run_id, session_id = _binding(parent_agent, task_id)
    entry_id = str(args.get("id") or "").strip()

    try:
        if op in ("write", "append"):
            entry = scratchpad_service.write_entry(
                conn, lock,
                title=str(args.get("title") or entry_id or ""),
                body=str(args.get("body") or ""),
                entry_id=entry_id or None,
                kind=str(args.get("kind") or "note"),
                scope=str(args.get("scope") or "run"),
                ttl_policy=str(args.get("ttl") or "session"),
                expires_in_hours=args.get("expires_in_hours"),
                run_id=run_id or None,
                session_id=session_id or None,
                owner=run_id or session_id or "agent",
                path=str(args.get("path") or ""),
                append=(op == "append"),
            )
            return json.dumps({"ok": True, "op": op, "entry": entry})

        if op == "read":
            if not entry_id:
                return _tool_error("op=read requires 'id'")
            entry = scratchpad_service.get_entry(conn, entry_id)
            if entry is None:
                return _tool_error(f"no scratchpad entry {entry_id!r}")
            return json.dumps({"ok": True, "op": op, "entry": entry})

        if op == "list":
            entries = scratchpad_service.list_entries(
                conn,
                scope=str(args.get("scope") or ""),
                kind=str(args.get("kind") or ""),
                search=str(args.get("search") or ""),
                limit=int(args.get("limit") or scratchpad_service.DEFAULT_LIMIT),
            )
            # Bodies can be large; the list view is an index, op=read is the fetch.
            index = [
                {
                    "id": e["id"], "title": e["title"], "kind": e["kind"],
                    "scope": e["scope"], "ttl_policy": e["ttl_policy"],
                    "pinned": e["pinned"], "updated_at": e["updated_at"],
                    "chars": len(e["body"]),
                }
                for e in entries
            ]
            return json.dumps({"ok": True, "op": op, "count": len(index), "entries": index})

        if op == "remove":
            if not entry_id:
                return _tool_error("op=remove requires 'id'")
            removed = scratchpad_service.remove_entry(conn, lock, entry_id=entry_id)
            return json.dumps({"ok": True, "op": op, "id": entry_id, "removed": removed})

        if op == "pin":
            if not entry_id:
                return _tool_error("op=pin requires 'id'")
            pinned = args.get("pinned")
            entry = scratchpad_service.set_pinned(
                conn, lock, entry_id=entry_id,
                pinned=True if pinned is None else bool(pinned),
            )
            return json.dumps({"ok": True, "op": op, "entry": entry})

        if op == "sweep":
            removed = scratchpad_service.sweep(conn, lock)
            return json.dumps({"ok": True, "op": op, "removed": removed})

        return _tool_error(f"unknown op {op!r}")
    except scratchpad_service.ScratchpadError as exc:
        return _tool_error(str(exc))
    except Exception as exc:  # noqa: BLE001 — never raise into the agent loop
        logger.debug("atlas_scratchpad op=%s failed: %s", op, exc)
        return _tool_error(f"atlas_scratchpad {op} failed: {exc}")


def ensure_scratchpad_bridge() -> bool:
    """Register the scratchpad tool with the foundation, once. Fail-open."""
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
                name="atlas_scratchpad",
                version="0.1.0",
                description="ATLAS agent scratchpad (registered in-process)",
                source="atlas-runtime",
            )
            ctx = PluginContext(manifest, get_plugin_manager())
            ctx.register_tool(
                name="atlas_scratchpad",
                toolset="atlas",
                schema=TOOL_SCHEMA,
                handler=atlas_scratchpad_tool,
                description=(
                    "Durable agent working memory: write/append/read/list/remove/"
                    "pin/sweep plans, findings and drafts with a TTL"
                ),
            )
            _registered = True
            return True
        except Exception as exc:  # noqa: BLE001 — fail-open
            logger.debug("scratchpad bridge unavailable: %s", exc)
            return False


__all__ = ["TOOL_SCHEMA", "atlas_scratchpad_tool", "ensure_scratchpad_bridge"]
