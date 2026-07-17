"""ATLAS structured audit event bus — Hermes plugin.

Registers hook callbacks with the Hermes plugin system via register(ctx).
Every Hermes runtime event (tool call, LLM call, subagent run, approval)
is mapped to an AuditEvent row persisted by atlas_runtime.audit_service.

Design:
- Session-to-run mapping: _CURRENT_RUN[session_id] = run_id, populated by
  on_session_start before any other hooks fire. Tests inject state directly.
- Connection injection: set_connection(conn) allows tests to supply an
  in-memory SQLite connection without spawning Hermes.
- Fail-open: every hook callback wraps its body in try/except Exception so
  a plugin error never crashes the Hermes event loop. Hermes also wraps
  callbacks independently (verified: hermes_cli/plugins.py:1557-1568).
- Thread safety: _STATE_LOCK protects all reads/writes to _CURRENT_RUN.
- D-001: No edits to hermes_cli/cli.py or hermes_cli/run_agent.py.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from typing import Any

from atlas_runtime.audit_service import emit

logger = logging.getLogger(__name__)

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_STATE_LOCK = threading.Lock()
_CURRENT_RUN: dict[str, str] = {}   # session_id -> run_id

_CONN: sqlite3.Connection | None = None
_LOCK: threading.Lock = threading.Lock()

# Artifact-producing tool names (Write, Edit, MultiEdit and snake_case variants).
# Any tool_name in this set produces event_type="artifact" instead of "tool_call".
# Verified against Hermes _DEFAULT_PAYLOADS and ATLAS tool taxonomy (04-RESEARCH.md).
_ARTIFACT_TOOLS: frozenset[str] = frozenset(
    {"write_file", "edit_file", "multi_edit", "Write", "Edit", "MultiEdit"}
)


# ---------------------------------------------------------------------------
# Public helpers (for test injection and plugin startup)
# ---------------------------------------------------------------------------


def set_connection(conn: sqlite3.Connection | None) -> None:
    """Inject a SQLite connection into the plugin.

    Used by tests to supply an in-memory db without spawning Hermes.
    Called with None in teardown to reset state between tests.
    Guarded by _LOCK to prevent TOCTOU races with concurrent emit() calls.
    """
    global _CONN
    with _LOCK:
        _CONN = conn


def get_connection() -> sqlite3.Connection | None:
    """Snapshot the injected connection (for sibling ATLAS plugins, e.g. the
    actor bridge) under the same lock used by set_connection()."""
    with _LOCK:
        return _CONN


def get_lock() -> threading.Lock:
    """The lock that guards writes through this plugin's connection. Sibling
    plugins sharing the connection must share this lock."""
    return _LOCK


def run_for_session(session_id: str) -> str | None:
    """Resolve the ATLAS run_id mapped to a Hermes session, if any."""
    with _STATE_LOCK:
        return _CURRENT_RUN.get(session_id)


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------


def register(ctx, conn: sqlite3.Connection | None = None) -> None:
    """Register atlas_audit hook callbacks with the Hermes plugin context.

    Hook names are verified against hermes_cli/plugins.py VALID_HOOKS:
      "on_session_start" — VALID (line 141)
      "post_api_request" — VALID (line 139)
      "post_llm_call"    — VALID (line 138)
      "post_tool_call"   — VALID (line 130)
      "subagent_stop"    — VALID (line 145)
      "post_approval_response" — VALID (line 167)

    Registers exactly 6 hooks. plugin.yaml hooks list must match exactly.

    Args:
        ctx: Hermes plugin context providing register_hook().
        conn: Optional SQLite connection to initialise _CONN at registration time.
            If provided, equivalent to calling set_connection(conn) before hooks fire.
            Phase 5's start_run() will call set_connection() before invoking Hermes
            when a persistent connection is managed by the mission lifecycle.
    """
    if conn is not None:
        set_connection(conn)
    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("post_api_request", on_post_api_request)
    ctx.register_hook("post_llm_call", on_post_llm_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)
    ctx.register_hook("subagent_stop", on_subagent_stop)
    ctx.register_hook("post_approval_response", on_post_approval)


# ---------------------------------------------------------------------------
# Hook callbacks
# ---------------------------------------------------------------------------


def on_session_start(*, session_id: str = "", run_id: str = "", **_: Any) -> None:
    """Populate session_id → run_id mapping when a Hermes session starts.

    Called by Hermes (hook name: "on_session_start") before any other hooks.
    In Phase 5, the session launch code calls this explicitly before starting
    the Hermes agent loop. In tests, state is injected directly into _CURRENT_RUN.
    """
    try:
        # Hermes's generic hook invocation knows the session id but not ATLAS's
        # run id. Never let that empty notification erase the explicit mapping
        # installed by run_service/subagent_service before the harness starts.
        if not session_id or not run_id:
            logger.debug(
                "atlas_audit: ignoring incomplete session_start session_id=%s run_id=%s",
                session_id,
                run_id,
            )
            return
        with _STATE_LOCK:
            _CURRENT_RUN[session_id] = run_id
        logger.debug(
            "atlas_audit: session_start session_id=%s run_id=%s", session_id, run_id
        )
    except Exception as exc:
        logger.warning("atlas_audit: on_session_start failed: %s", exc)


def on_post_tool_call(
    *,
    tool_name: str = "",
    args: Any = None,
    result: Any = None,
    task_id: str = "",
    session_id: str = "",
    tool_call_id: str = "",
    duration_ms: int = 0,
    **_: Any,
) -> None:
    """Emit an AuditEvent (and ToolCall) for every tool invocation.

    event_type is "artifact" if tool_name is a write/edit tool, else "tool_call".
    Resolves run_id from _CURRENT_RUN[session_id]; drops event with a warning
    if the session is unknown (T-04-03-T2 mitigation).
    """
    try:
        with _STATE_LOCK:
            run_id = _CURRENT_RUN.get(session_id)
        if run_id is None:
            logger.warning(
                "atlas_audit: no run_id for session %s — event dropped", session_id
            )
            return

        # Snapshot _CONN under _LOCK to prevent TOCTOU race with set_connection()
        with _LOCK:
            conn_snapshot = _CONN
        if conn_snapshot is None:
            logger.error(
                "atlas_audit: no connection — audit event dropped (call set_connection first)"
            )
            return

        event_type = "artifact" if tool_name in _ARTIFACT_TOOLS else "tool_call"

        # Pass raw args/result — emit() handles dict/str/None serialization (D-013)
        emit(
            conn_snapshot,
            _LOCK,
            run_id=run_id,
            event_type=event_type,
            task_id=task_id,
            session_id=session_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            duration_ms=duration_ms,
            tool_call_kwargs={
                "tool_name": tool_name,
                "args": args,
                "result": result,
            },
        )
    except Exception as exc:
        logger.warning("atlas_audit: on_post_tool_call failed: %s", exc)


def on_post_api_request(
    *,
    task_id: str = "",
    session_id: str = "",
    model: str = "",
    provider: str = "",
    api_call_count: int = 0,
    api_duration: float = 0.0,
    finish_reason: str = "",
    usage: Any = None,
    **_: Any,
) -> None:
    """Emit an AuditEvent for each LLM API call (preferred over on_post_llm_call).

    Maps post_api_request kwargs directly to AuditEvent(event_type="llm_call").
    api_duration is in seconds (Hermes convention); converted to duration_ms.
    """
    try:
        with _STATE_LOCK:
            run_id = _CURRENT_RUN.get(session_id)
        if run_id is None:
            logger.warning(
                "atlas_audit: no run_id for session %s — event dropped", session_id
            )
            return

        with _LOCK:
            conn_snapshot = _CONN
        if conn_snapshot is None:
            logger.error(
                "atlas_audit: no connection — audit event dropped (call set_connection first)"
            )
            return

        duration_ms = int(api_duration * 1000)
        data = {
            "model": model,
            "provider": provider,
            "usage": usage or {},
            "finish_reason": finish_reason,
            "api_call_count": api_call_count,
        }

        emit(
            conn_snapshot,
            _LOCK,
            run_id=run_id,
            event_type="llm_call",
            task_id=task_id,
            session_id=session_id,
            duration_ms=duration_ms,
            data=data,
        )
    except Exception as exc:
        logger.warning("atlas_audit: on_post_api_request failed: %s", exc)


def on_post_llm_call(
    *,
    task_id: str = "",
    session_id: str = "",
    model: str = "",
    provider: str = "",
    api_call_count: int = 0,
    api_duration: float = 0.0,
    finish_reason: str = "",
    usage: Any = None,
    **_: Any,
) -> None:
    """Fallback LLM call hook (post_llm_call fires once per turn, not per API call).

    For MVP, this is a no-op — on_post_api_request is the primary handler and
    fires per API call (preferred). Registering both ensures compatibility with
    Hermes versions that fire only one of the two hooks. Logging at debug level
    so it's visible during development without spamming production logs.
    """
    try:
        logger.debug(
            "atlas_audit: on_post_llm_call fired (fallback; "
            "on_post_api_request is the primary handler)"
        )
        # No-op: on_post_api_request handles the AuditEvent write.
        # If on_post_api_request does not fire for this session, this hook
        # can be promoted to a full implementation in a future iteration.
    except Exception as exc:
        logger.warning("atlas_audit: on_post_llm_call failed: %s", exc)


def on_subagent_stop(
    *,
    parent_session_id: str = "",
    child_role: Any = None,
    child_summary: str = "",
    child_status: str = "",
    duration_ms: int = 0,
    **_: Any,
) -> None:
    """Emit an AuditEvent when a subagent run completes.

    Resolves run_id from _CURRENT_RUN[parent_session_id] — the parent session
    owns the run, not the child session.
    """
    try:
        with _STATE_LOCK:
            run_id = _CURRENT_RUN.get(parent_session_id)
        if run_id is None:
            logger.warning(
                "atlas_audit: no run_id for session %s — event dropped",
                parent_session_id,
            )
            return

        with _LOCK:
            conn_snapshot = _CONN
        if conn_snapshot is None:
            logger.error(
                "atlas_audit: no connection — audit event dropped (call set_connection first)"
            )
            return

        data = {
            "child_role": str(child_role) if child_role is not None else None,
            "child_summary": child_summary,
            "child_status": child_status,
        }

        emit(
            conn_snapshot,
            _LOCK,
            run_id=run_id,
            event_type="subagent_run",
            session_id=parent_session_id,
            duration_ms=duration_ms,
            data=data,
        )
    except Exception as exc:
        logger.warning("atlas_audit: on_subagent_stop failed: %s", exc)


def on_post_approval(*, session_id: str = "", **_: Any) -> None:
    """Emit an AuditEvent when an approval decision is made.

    Stub implementation — captures that an approval event occurred.
    Full implementation (capturing command, pattern_key, choice) is a
    Phase 5 enhancement once the approval workflow is exercised end-to-end.
    """
    try:
        with _STATE_LOCK:
            run_id = _CURRENT_RUN.get(session_id)
        if run_id is None:
            logger.warning(
                "atlas_audit: no run_id for session %s — event dropped", session_id
            )
            return

        with _LOCK:
            conn_snapshot = _CONN
        if conn_snapshot is None:
            logger.error(
                "atlas_audit: no connection — audit event dropped (call set_connection first)"
            )
            return

        emit(
            conn_snapshot,
            _LOCK,
            run_id=run_id,
            event_type="approval",
            session_id=session_id,
            data={},
        )
    except Exception as exc:
        logger.warning("atlas_audit: on_post_approval failed: %s", exc)
