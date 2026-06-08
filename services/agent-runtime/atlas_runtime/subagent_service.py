"""ATLAS subagent service — dispatch_subagent stub.

References:
  - RUNTIME-06: Subagents are governed: role, model tier, allowed tools,
    autonomy level, token budget captured per AuditEvent row.

Phase 5 note: This is a stub-only implementation. No real subagent spawning
occurs in Phase 5. The stub emits a subagent_run AuditEvent with the full
governance envelope so that RUNTIME-06 acceptance criteria are satisfied.
Real subagent spawning is deferred to a later phase.
"""
from __future__ import annotations

import logging
import sqlite3
import threading

from atlas_runtime.audit_service import emit

logger = logging.getLogger(__name__)


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
