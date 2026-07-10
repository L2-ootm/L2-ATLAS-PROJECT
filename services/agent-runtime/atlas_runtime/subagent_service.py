"""ATLAS subagent service — foundation delegation observer + audit bridge.

References:
  - RUNTIME-06: Subagents are governed: role, model tier, allowed tools,
    autonomy level, token budget captured per AuditEvent row.

The foundation's `delegate_tool.py` already spawns real subagents and fires
plugin hooks (`subagent_stop`, `post_tool_call`, ...) through
`hermes_cli.plugins.invoke_hook`. The `atlas_audit` plugin maps those hooks
onto `subagent_run`/`tool_call`/`llm_call` AuditEvents — but plugin discovery
only runs under the hermes CLI/gateway entry points, and the bundled shim is
additionally gated behind `plugins.enabled` config, so foundation subagent
spawns were never audited when ATLAS constructs `AIAgent` in-process
(NativeAtlasAgent).

`ensure_foundation_bridge()` closes that gap from the ATLAS side (D-001: no
foundation edits, no re-implemented spawning): it registers the real
`atlas_audit` hook callbacks directly with the foundation's PluginManager
singleton — the same registry `delegate_tool` consults via `invoke_hook` —
and binds the plugin's connection + session→run mapping for the current run.

`dispatch_subagent` remains the manual governance-envelope emitter
(RUNTIME-06) for callers that record a delegation decision without the
foundation in the loop.
"""
from __future__ import annotations

import logging
import sqlite3
import sys
import threading

from atlas_runtime.audit_service import emit

logger = logging.getLogger(__name__)

_bridge_lock = threading.Lock()
_hooks_registered = False


def _foundation_on_path() -> bool:
    """Put foundation/atlas-hermes on sys.path (same mechanism as native.py)."""
    from atlas_runtime.agents.native import _find_foundation  # noqa: PLC0415

    foundation = _find_foundation()
    if foundation is None:
        return False
    path = str(foundation)
    if path not in sys.path:
        sys.path.insert(0, path)
    return True


def _register_hooks_once() -> bool:
    """Register atlas_audit's hooks with the foundation PluginManager singleton.

    Bypasses plugin discovery deliberately: discovery is config-gated
    (`plugins.enabled`) and its bundled-shim import is order-fragile (the
    plugins dir can shadow the real `atlas_audit` package on sys.path). Direct
    registration through the public PluginContext facade is deterministic and
    works in any process that has both packages importable.
    """
    global _hooks_registered
    with _bridge_lock:
        if _hooks_registered:
            return True
        import atlas_audit  # noqa: PLC0415 — the real package, not the shim
        from hermes_cli.plugins import (  # noqa: PLC0415
            PluginContext,
            PluginManifest,
            get_plugin_manager,
        )

        manifest = PluginManifest(
            name="atlas_audit",
            version=getattr(atlas_audit, "__version__", ""),
            description="ATLAS audit bus (registered in-process by atlas_runtime)",
            source="atlas-runtime",
        )
        atlas_audit.register(PluginContext(manifest, get_plugin_manager()))
        _hooks_registered = True
        return True


def ensure_foundation_bridge(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    session_id: str | None = None,
) -> bool:
    """Make foundation subagent spawns visible on the ATLAS audit bus.

    Idempotent and fail-open: returns False (with a debug log) when the
    foundation or the atlas_audit package is unavailable, never raising into
    the run path. Maps both the harness session key (run_id — NativeAtlasAgent
    constructs the harness with session_id=run_id) and the optional ATLAS
    surface session id onto this run.
    """
    try:
        if not _foundation_on_path():
            return False
        if not _register_hooks_once():
            return False
        import atlas_audit  # noqa: PLC0415

        atlas_audit.set_connection(conn)
        atlas_audit.on_session_start(session_id=run_id, run_id=run_id)
        if session_id and session_id != run_id:
            atlas_audit.on_session_start(session_id=session_id, run_id=run_id)
        return True
    except Exception as exc:  # noqa: BLE001 — never block a run on auditing
        logger.debug("foundation audit bridge unavailable: %s", exc)
        return False


def dispatch_subagent(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: str,
    role: str,
    model_tier: str = "sonnet",
    allowed_tools: list[str] | None = None,
    autonomy_level: str = "supervised",
    token_budget: int = 4096,
) -> None:
    """Stub subagent dispatch — emits subagent_run AuditEvent (RUNTIME-06).

    Phase 5: No real subagent spawning. Emits governance envelope only.
    The payload includes role, model_tier, allowed_tools, autonomy_level,
    and token_budget as required by RUNTIME-06.

    emit() is wrapped in try/except so that audit failures do not propagate
    to callers (fail-open error guard from 05-PATTERNS.md).
    """
    payload = {
        "role": role,
        "model_tier": model_tier,
        "allowed_tools": allowed_tools if allowed_tools is not None else [],
        "autonomy_level": autonomy_level,
        "token_budget": token_budget,
    }
    try:
        emit(conn, lock, run_id=run_id, event_type="subagent_run", data=payload)
    except Exception as exc:
        logger.warning("subagent_service.dispatch_subagent failed: %s", exc)
