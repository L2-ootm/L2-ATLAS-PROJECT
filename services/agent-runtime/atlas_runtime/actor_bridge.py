"""Hermes-facing actor bridge — the `atlas_actor` tool + completion inbox hooks.

Registers with the foundation the same D-001-safe way subagent_service does
(direct PluginContext registration, no vendored edits, no discovery):

- Tool `atlas_actor` with one `op` input: run | spawn | status | wait | cancel.
  Hermes injects `parent_agent`; the handler resolves the current ATLAS run
  through atlas_audit's session→run map and the shared connection/lock.
- `pre_llm_call` hook: claims pending actor completions for the current run
  and returns them as ephemeral turn context (`{"context": ...}` — appended
  to the user message, never the cached system prefix).
- `post_llm_call` hook: acknowledges the claimed deliveries. A crash between
  the two releases the lease for retry at the next boundary.

All entry points are fail-open: an unavailable foundation or missing
connection degrades to a tool error string / no injection, never a crash in
the run path.
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Any, Optional

from atlas_runtime import actor_service

logger = logging.getLogger(__name__)

_bridge_lock = threading.Lock()
_registered = False

# claim tokens awaiting acknowledgement, keyed by parent run id
_PENDING_CLAIMS: dict[str, str] = {}
_CLAIMS_LOCK = threading.Lock()

# Surface (caller-facing) session id, keyed by ATLAS run id.
#
# native.py always constructs the Hermes harness with `session_id=run_id`
# (see agents/native.py's `factory(session_id=run_id)`), so `parent_agent
# .session_id` is the internal run id, never the real surface session the
# caller started the mission from. run_service.start_run() knows the real
# surface session id (its `session_id` kwarg) at run-creation time and
# records it here via record_surface_session(), before the harness — and
# therefore before ensure_actor_bridge()/atlas_actor_tool — ever runs for
# that run. atlas_actor_tool prefers this map over parent_agent.session_id
# when spawning actors, so actors are stamped with the caller's real
# session id instead of the run id, fixing UI cross-contamination between
# actors spawned from different browser sessions.
_SURFACE_SESSION_BY_RUN: dict[str, str] = {}
_SURFACE_SESSION_LOCK = threading.Lock()


def record_surface_session(
    *, session_id: Optional[str] = None, run_id: Optional[str] = None
) -> None:
    """Record the real surface session id for a run.

    Called from run_service.start_run() alongside atlas_audit.on_session_start,
    with the same two ids. A no-op when either id is missing or when they're
    equal (nothing to disambiguate — parent_agent.session_id already matches).
    Fail-open: never raises, since run creation must not depend on this.
    """
    try:
        if not session_id or not run_id or session_id == run_id:
            return
        with _SURFACE_SESSION_LOCK:
            _SURFACE_SESSION_BY_RUN[run_id] = session_id
    except Exception as exc:  # noqa: BLE001 — never block run creation
        logger.debug("actor bridge: could not record surface session: %s", exc)


def _surface_session_for_run(run_id: Optional[str]) -> Optional[str]:
    if not run_id:
        return None
    with _SURFACE_SESSION_LOCK:
        return _SURFACE_SESSION_BY_RUN.get(run_id)

TOOL_SCHEMA = {
    "name": "atlas_actor",
    "description": (
        "Durable ATLAS actor supervisor. Spawn child agents that survive "
        "this turn (and process restarts), inspect them, join them, or "
        "cancel them. op=run spawns and joins (blocks up to "
        "timeout_seconds); op=spawn returns a stable actor_id immediately "
        "and the completion is delivered to you at a later turn boundary; "
        "op=status inspects without consuming; op=wait joins an existing "
        "actor; op=cancel idempotently stops an actor and its descendants."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": ["run", "spawn", "status", "wait", "cancel"],
                "description": "Actor operation.",
            },
            "goal": {
                "type": "string",
                "description": "Child goal (required for run/spawn).",
            },
            "actor_id": {
                "type": "string",
                "description": "Existing actor id (required for status/wait/cancel).",
            },
            "model": {
                "type": "string",
                "description": "Optional model override; empty inherits the parent's.",
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Join timeout for run/wait (default 120).",
            },
            "idempotency_key": {
                "type": "string",
                "description": (
                    "Optional explicit spawn key. Identical keys return the "
                    "existing actor; pass unique keys to intentionally run "
                    "the same goal twice."
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


def _actor_view(actor: dict[str, Any]) -> dict[str, Any]:
    """Bounded, model-facing projection of an actor row."""
    view = {
        "actor_id": actor["id"],
        "status": actor["status"],
        "mode": actor["mode"],
        "goal": (actor.get("goal") or "")[:500],
        "model": actor.get("model"),
        "child_run_id": actor.get("child_run_id"),
        "created_at": actor.get("created_at"),
        "finished_at": actor.get("finished_at"),
    }
    if actor.get("result_preview"):
        view["result"] = actor["result_preview"]
    if actor.get("error"):
        view["error"] = actor["error"]
    if actor.get("delivery"):
        view["delivery"] = actor["delivery"]
    return view


def atlas_actor_tool(
    args: Optional[dict[str, Any]] = None,
    *,
    task_id: Optional[str] = None,
    parent_agent: Any = None,
    **framework: Any,
) -> str:
    """Hermes plugin handler for `atlas_actor`; returns a JSON string."""
    # Preserve the pre-0022 direct-call seam for programmatic callers while
    # making the production plugin ABI (one args dict + context kwargs) primary.
    if args is None:
        known = {"op", "goal", "actor_id", "model", "timeout_seconds", "idempotency_key"}
        args = {key: value for key, value in framework.items() if key in known}
    if not isinstance(args, dict):
        return _tool_error("atlas_actor arguments must be an object")
    op = str(args.get("op") or "status")
    goal = args.get("goal")
    actor_id = args.get("actor_id")
    model = args.get("model")
    timeout_seconds = args.get("timeout_seconds")
    idempotency_key = args.get("idempotency_key")
    conn, lock = _shared_state()
    if conn is None or lock is None:
        return _tool_error("actor supervisor unavailable: no ATLAS connection bound")
    run_id = _current_run_id(parent_agent, task_id)
    if run_id is None:
        return _tool_error("actor supervisor unavailable: no ATLAS run for this session")
    timeout = float(timeout_seconds) if timeout_seconds else 120.0
    try:
        if op in ("run", "spawn"):
            if not goal or not goal.strip():
                return _tool_error(f"op={op} requires a goal")
            mode = "joined" if op == "run" else "detached"
            # Prefer the caller's real surface session id (recorded by
            # run_service.start_run()) over parent_agent.session_id, which is
            # actually the internal run id (see native.py's harness
            # construction) and would otherwise get stamped onto the actor,
            # making actors from different browser sessions look
            # cross-contaminated in the UI. Falls back to the old behavior
            # when the map has no entry yet (e.g. run created outside
            # start_run(), or before that fix shipped) so nothing regresses.
            actor_session_id = _surface_session_for_run(run_id) or getattr(
                parent_agent, "session_id", None
            )
            actor, created = actor_service.spawn_actor(
                conn, lock,
                parent_run_id=run_id,
                goal=goal,
                mode=mode,
                model=model,
                session_id=actor_session_id,
                idempotency_key=idempotency_key,
            )
            if created:
                from atlas_runtime.actor_worker import launch_actor_worker  # noqa: PLC0415

                pid = launch_actor_worker(conn, lock, actor["id"])
                if pid is None:
                    refreshed = actor_service.get_actor(conn, actor["id"]) or actor
                    return json.dumps({"ok": False, **_actor_view(refreshed)})
            if op == "spawn":
                refreshed = actor_service.get_actor(conn, actor["id"]) or actor
                return json.dumps(
                    {
                        "ok": True,
                        "note": (
                            "detached actor started; its completion will be "
                            "delivered to you at a later turn, or join it with "
                            "op=wait"
                        ),
                        **_actor_view(refreshed),
                    }
                )
            joined = actor_service.wait_for_actor(
                conn, lock, actor["id"], timeout_seconds=timeout
            )
            if joined is None:
                return json.dumps(
                    {
                        "ok": True,
                        "actor_id": actor["id"],
                        "status": "running",
                        "note": (
                            f"still running after {timeout:.0f}s; check later "
                            "with op=status or join with op=wait"
                        ),
                    }
                )
            return json.dumps({"ok": True, **_actor_view(joined)})

        if op == "status":
            if not actor_id:
                return _tool_error("op=status requires actor_id")
            actor = actor_service.get_actor(conn, actor_id)
            if actor is None:
                return _tool_error(f"unknown actor: {actor_id}")
            return json.dumps({"ok": True, **_actor_view(actor)})

        if op == "wait":
            if not actor_id:
                return _tool_error("op=wait requires actor_id")
            joined = actor_service.wait_for_actor(
                conn, lock, actor_id, timeout_seconds=timeout
            )
            if joined is None:
                existing = actor_service.get_actor(conn, actor_id)
                if existing is None:
                    return _tool_error(f"unknown actor: {actor_id}")
                return json.dumps(
                    {
                        "ok": True,
                        "actor_id": actor_id,
                        "status": existing["status"],
                        "note": f"not terminal after {timeout:.0f}s",
                    }
                )
            return json.dumps({"ok": True, **_actor_view(joined)})

        if op == "cancel":
            if not actor_id:
                return _tool_error("op=cancel requires actor_id")
            cancelled = actor_service.cancel_actor(conn, lock, actor_id)
            try:
                from atlas_runtime.actor_worker import terminate_actor_pids  # noqa: PLC0415

                terminate_actor_pids(cancelled)
            except Exception as exc:  # noqa: BLE001
                logger.debug("terminate after cancel failed: %s", exc)
            return json.dumps(
                {
                    "ok": True,
                    "cancelled": [a["id"] for a in cancelled],
                    "note": "already terminal" if not cancelled else "cancelled",
                }
            )

        return _tool_error(f"unknown op: {op!r}")
    except ValueError as exc:
        return _tool_error(str(exc))
    except Exception as exc:  # noqa: BLE001 — tools must not throw into the loop
        logger.warning("atlas_actor tool failed: %s", exc)
        return _tool_error(f"actor supervisor error: {exc}")


# ---------------------------------------------------------------------------
# Completion inbox hooks
# ---------------------------------------------------------------------------


def on_pre_llm_call(*, session_id: str = "", **_: Any) -> Optional[dict[str, str]]:
    """Claim pending actor completions and inject a compact notice this turn."""
    try:
        import atlas_audit  # noqa: PLC0415

        conn, lock = _shared_state()
        if conn is None or lock is None or not session_id:
            return None
        run_id = atlas_audit.run_for_session(session_id)
        if run_id is None:
            return None
        token = str(uuid.uuid4())
        claimed = actor_service.claim_deliveries(
            conn, lock, parent_run_id=run_id, claim_token=token
        )
        if not claimed:
            return None
        with _CLAIMS_LOCK:
            _PENDING_CLAIMS[run_id] = token
        lines = ["[ATLAS actor completions]"]
        for delivery in claimed:
            status = delivery.get("status", "completed")
            frag = f"- actor {delivery.get('actor_id')}: {status}"
            goal = delivery.get("goal")
            if goal:
                frag += f" — goal: {goal}"
            if delivery.get("result_preview"):
                frag += f"\n  result: {str(delivery['result_preview'])[:2000]}"
            if delivery.get("error"):
                frag += f"\n  error: {str(delivery['error'])[:500]}"
            lines.append(frag)
        return {"context": "\n".join(lines)}
    except Exception as exc:  # noqa: BLE001 — never block a turn
        logger.debug("actor inbox pre_llm_call failed: %s", exc)
        return None


def on_post_llm_call(*, session_id: str = "", **_: Any) -> None:
    """Acknowledge the claim once the model has seen the completion notice."""
    try:
        import atlas_audit  # noqa: PLC0415

        conn, lock = _shared_state()
        if conn is None or lock is None or not session_id:
            return
        run_id = atlas_audit.run_for_session(session_id)
        if run_id is None:
            return
        with _CLAIMS_LOCK:
            token = _PENDING_CLAIMS.pop(run_id, None)
        if token:
            actor_service.acknowledge_deliveries(conn, lock, claim_token=token)
    except Exception as exc:  # noqa: BLE001
        logger.debug("actor inbox post_llm_call failed: %s", exc)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def ensure_actor_bridge() -> bool:
    """Register the actor tool + inbox hooks with the foundation, once.

    Mirrors subagent_service._register_hooks_once: direct PluginContext
    registration (deterministic, discovery-independent). Idempotent and
    fail-open — returns False when the foundation is unavailable.
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
                name="atlas_actors",
                version="0.1.0",
                description="ATLAS durable actor supervisor (registered in-process)",
                source="atlas-runtime",
            )
            ctx = PluginContext(manifest, get_plugin_manager())
            ctx.register_tool(
                name="atlas_actor",
                toolset="atlas",
                schema=TOOL_SCHEMA,
                handler=atlas_actor_tool,
                description="Durable subagent actors: run/spawn/status/wait/cancel",
            )
            ctx.register_hook("pre_llm_call", on_pre_llm_call)
            ctx.register_hook("post_llm_call", on_post_llm_call)
            _registered = True
            return True
        except Exception as exc:  # noqa: BLE001 — fail-open
            logger.debug("actor bridge unavailable: %s", exc)
            return False


__all__ = [
    "ensure_actor_bridge",
    "atlas_actor_tool",
    "on_pre_llm_call",
    "on_post_llm_call",
    "TOOL_SCHEMA",
]
