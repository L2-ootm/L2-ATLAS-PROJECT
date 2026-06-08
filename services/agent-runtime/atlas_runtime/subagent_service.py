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

import sqlite3
import threading

from atlas_runtime.audit_service import emit


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

    Raises:
        NotImplementedError: Stub — implement in Wave 1.
    """
    raise NotImplementedError("not implemented")
