"""Hermes-facing team bridge — the `atlas_team` tool (CASE-05).

The team engine has had a complete backend for a while — `team_service` (presets,
teams, rosters), `team_run_service` (runs, the append-only chat buffer with a
per-member read cursor), and `team_run_worker` (the detached round-robin worker) —
plus gateway routes and CLI commands. The agent could reach none of it: only
`atlas_actor` and `atlas_graph` were ever registered, so a model asked to
"convene the review team" had no way to do it.

Registration mirrors `actor_bridge.ensure_actor_bridge` exactly: direct
PluginContext registration (D-001-safe, discovery-independent), idempotent, and
fail-open — an unavailable foundation degrades to no tool, never a crash.

**Scope: run and observe, not compose.** `list`, `run`, `status`, `messages` and
`cancel` are exposed; create/update/delete of teams, rosters and presets are
not. Team composition is operator configuration — which models, at what cost,
with which system prompts — and it is the input to the resource-spawning
operation this tool already exposes. An agent that can both invent a roster and
run it has no bound on what it spins up; an agent that can only run the rosters
an operator defined does. Compose through `atlas team ...` or the cockpit.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

from atlas_runtime import team_run_service, team_service

logger = logging.getLogger(__name__)

_bridge_lock = threading.Lock()
_registered = False

# Model-facing caps. The chat buffer is unbounded on disk (append-only, one row
# per member turn); a model reading it must not be handed an entire multi-round
# transcript in one tool result.
_MESSAGE_PAGE = 50
_CONTENT_PREVIEW = 2000
_KICKOFF_CAP = 8000

TOOL_SCHEMA = {
    "name": "atlas_team",
    "description": (
        "Run an operator-defined ATLAS agent team: a round-robin group chat "
        "between preset members that works a kickoff message toward a result. "
        "op=list shows the teams available and their members; op=run starts a "
        "team on a kickoff message and returns immediately with a team_run_id "
        "(the run continues in a detached worker); op=status inspects a run's "
        "state and round; op=messages reads the group chat since a sequence "
        "number; op=cancel stops a run. Teams themselves are configured by the "
        "operator and cannot be created or edited from here."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": ["list", "run", "status", "messages", "cancel"],
                "description": "Team operation.",
            },
            "team_id": {
                "type": "string",
                "description": "Team to run (required for op=run; use op=list to find one).",
            },
            "team_run_id": {
                "type": "string",
                "description": "Existing team run (required for status/messages/cancel).",
            },
            "message": {
                "type": "string",
                "description": "Kickoff message for the team (required for op=run).",
            },
            "max_rounds": {
                "type": "number",
                "description": "Round-robin round cap for op=run (default 6, server-capped).",
            },
            "since_seq": {
                "type": "number",
                "description": (
                    "op=messages read cursor: return only messages after this "
                    "sequence number. Pass the last seq you saw to poll."
                ),
            },
        },
        "required": ["op"],
    },
}


def _shared_state() -> tuple[Any, Optional[threading.Lock]]:
    """The connection+lock atlas_audit holds for the current process."""
    try:
        import atlas_audit  # noqa: PLC0415

        return atlas_audit.get_connection(), atlas_audit.get_lock()
    except Exception:  # noqa: BLE001
        return None, None


def _current_run_id(parent_agent: Any = None, task_id: Optional[str] = None) -> Optional[str]:
    """The ATLAS run behind this harness session, if any (see actor_bridge)."""
    try:
        import atlas_audit  # noqa: PLC0415

        session_id = getattr(parent_agent, "session_id", None) or task_id
        if not session_id:
            return None
        return atlas_audit.run_for_session(str(session_id)) or None
    except Exception:  # noqa: BLE001
        return None


def _tool_error(message: str) -> str:
    return json.dumps({"ok": False, "error": message})


def _team_view(team: dict[str, Any]) -> dict[str, Any]:
    """Bounded projection of a team row: identity plus the roster's shape.

    Member presets carry system prompts and provider config; the model needs to
    know who is on the team and what they are for, not how they are wired.
    """
    return {
        "team_id": team["id"],
        "name": team.get("name"),
        "description": (team.get("description") or "")[:500],
        "members": [
            {
                "role_label": member.get("role_label") or member.get("name"),
                "model": member.get("model"),
            }
            for member in team.get("members", [])
        ],
    }


def _run_view(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "team_run_id": run["id"],
        "team_id": run.get("team_id"),
        "status": run.get("status"),
        "current_round": run.get("current_round"),
        "max_rounds": run.get("max_rounds"),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
    }


def _message_view(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "seq": message.get("seq"),
        "round": message.get("round"),
        "from": message.get("sender_role") or "orchestrator",
        "to": message.get("target") or "all",
        "content": (message.get("content") or "")[:_CONTENT_PREVIEW],
    }


def atlas_team_tool(
    args: Optional[dict[str, Any]] = None,
    *,
    task_id: Optional[str] = None,
    parent_agent: Any = None,
    **framework: Any,
) -> str:
    """Hermes plugin handler for `atlas_team`; returns a JSON string."""
    # Same dual calling convention as atlas_actor_tool: one args dict from the
    # plugin ABI, or loose kwargs from a programmatic caller/test.
    if args is None:
        known = {"op", "team_id", "team_run_id", "message", "max_rounds", "since_seq"}
        args = {key: value for key, value in framework.items() if key in known}
    if not isinstance(args, dict):
        return _tool_error("atlas_team arguments must be an object")

    op = str(args.get("op") or "list")
    team_id = args.get("team_id")
    team_run_id = args.get("team_run_id")
    message = args.get("message")
    conn, lock = _shared_state()
    if conn is None or lock is None:
        return _tool_error("team engine unavailable: no ATLAS connection bound")

    try:
        if op == "list":
            teams = team_service.list_teams(conn)
            if not teams:
                return json.dumps(
                    {
                        "ok": True,
                        "teams": [],
                        "note": (
                            "no teams are configured; an operator defines them with "
                            "`atlas team create` and `atlas team members`"
                        ),
                    }
                )
            return json.dumps({"ok": True, "teams": [_team_view(t) for t in teams]})

        if op == "run":
            if not team_id:
                return _tool_error("op=run requires team_id (use op=list to find one)")
            if not message or not str(message).strip():
                return _tool_error("op=run requires a kickoff message")
            max_rounds = args.get("max_rounds")
            kwargs: dict[str, Any] = {}
            if max_rounds:
                kwargs["max_rounds"] = int(max_rounds)
            run = team_run_service.create_team_run(
                conn, lock,
                team_id=str(team_id),
                kickoff_message=str(message)[:_KICKOFF_CAP],
                # Anchor the team run to the run that asked for it, so the
                # cockpit can attribute it and retention treats it as that
                # mission's work rather than an orphan.
                parent_run_id=_current_run_id(parent_agent, task_id),
                **kwargs,
            )
            from atlas_runtime.team_run_worker import launch_team_run_worker  # noqa: PLC0415

            pid = launch_team_run_worker(run["id"])
            if pid is None:
                # The row exists but nothing will advance it. Report the failure
                # instead of handing back an id that will never progress —
                # a "running" team run that no worker owns is exactly the stale
                # wait CASE-04 is about.
                team_run_service.finish_team_run(
                    conn, lock, run["id"], status="failed"
                )
                return json.dumps(
                    {"ok": False, "error": "team run worker failed to launch", **_run_view(run)}
                )
            return json.dumps(
                {
                    "ok": True,
                    "note": (
                        "team run started in a detached worker; poll op=status "
                        "and read the group chat with op=messages"
                    ),
                    **_run_view(run),
                }
            )

        if op == "status":
            if not team_run_id:
                return _tool_error("op=status requires team_run_id")
            run = team_run_service.get_team_run(conn, str(team_run_id))
            if run is None:
                return _tool_error(f"unknown team run: {team_run_id}")
            return json.dumps({"ok": True, **_run_view(run)})

        if op == "messages":
            if not team_run_id:
                return _tool_error("op=messages requires team_run_id")
            run = team_run_service.get_team_run(conn, str(team_run_id))
            if run is None:
                return _tool_error(f"unknown team run: {team_run_id}")
            since_seq = int(args.get("since_seq") or 0)
            messages = team_run_service.list_messages(
                conn, str(team_run_id), since_seq=since_seq
            )
            page = messages[:_MESSAGE_PAGE]
            payload = {
                "ok": True,
                "team_run_id": team_run_id,
                "status": run.get("status"),
                "messages": [_message_view(m) for m in page],
                "has_more": len(messages) > len(page),
            }
            if page:
                # The cursor to pass back on the next poll, so the model does
                # not have to derive it from the last element itself.
                payload["next_since_seq"] = page[-1].get("seq")
            return json.dumps(payload)

        if op == "cancel":
            if not team_run_id:
                return _tool_error("op=cancel requires team_run_id")
            run = team_run_service.get_team_run(conn, str(team_run_id))
            if run is None:
                return _tool_error(f"unknown team run: {team_run_id}")
            changed = team_run_service.cancel_team_run(conn, lock, str(team_run_id))
            return json.dumps(
                {
                    "ok": True,
                    "team_run_id": team_run_id,
                    "note": "cancelled" if changed else "already terminal",
                }
            )

        return _tool_error(f"unknown op: {op!r}")
    except ValueError as exc:
        return _tool_error(str(exc))
    except Exception as exc:  # noqa: BLE001 — tools must not throw into the loop
        logger.warning("atlas_team tool failed: %s", exc)
        return _tool_error(f"team engine error: {exc}")


def ensure_team_bridge() -> bool:
    """Register the `atlas_team` tool with the foundation, once.

    Mirrors `actor_bridge.ensure_actor_bridge`: direct PluginContext
    registration, idempotent, fail-open (returns False when the foundation is
    unavailable). No hooks — teams deliver their result through their own chat
    buffer, which the model polls, so there is no completion inbox to drain.
    """
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
                name="atlas_teams",
                version="0.1.0",
                description="ATLAS agent team engine (registered in-process)",
                source="atlas-runtime",
            )
            ctx = PluginContext(manifest, get_plugin_manager())
            ctx.register_tool(
                name="atlas_team",
                toolset="atlas",
                schema=TOOL_SCHEMA,
                handler=atlas_team_tool,
                description="Operator-defined agent teams: list/run/status/messages/cancel",
            )
            _registered = True
            return True
        except Exception as exc:  # noqa: BLE001 — fail-open
            logger.debug("team bridge unavailable: %s", exc)
            return False


__all__ = [
    "TOOL_SCHEMA",
    "atlas_team_tool",
    "ensure_team_bridge",
]
