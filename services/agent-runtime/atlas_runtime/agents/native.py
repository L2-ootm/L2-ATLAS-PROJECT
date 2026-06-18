"""NativeAtlasAgent — the in-process / Hermes-foundation runtime (P4).

This runtime represents ATLAS's native execution path. Real Hermes-loop
wiring lives in the vendored foundation and is governed by D-001
(foundation = extension-points only), so this class does not re-implement
the Hermes loop. It emits a native-execution AuditEvent so the run carries
an audit record identical in shape to other runtimes (audit parity), and
returns a succeeded outcome. When the foundation loop is wired in, its work
is surfaced through the same audit bus this method uses.
"""
from __future__ import annotations

import logging
import sqlite3
import threading

from atlas_runtime.agents.base import AgentRuntime, RunOutcome
from atlas_runtime.audit_service import emit

logger = logging.getLogger(__name__)


class NativeAtlasAgent(AgentRuntime):
    name = "native"

    def execute(
        self,
        conn: sqlite3.Connection,
        lock: threading.Lock,
        *,
        mission_id: str,
        run_id: str,
        prompt: str,
    ) -> RunOutcome:
        try:
            emit(
                conn,
                lock,
                run_id=run_id,
                event_type="tool_call",
                tool_name="native_runtime",
                data={"runtime": "native", "mission_id": mission_id},
            )
        except Exception as exc:  # fail-open audit, never crash the run
            logger.warning("NativeAtlasAgent audit emit failed: %s", exc)
        return RunOutcome(status="succeeded", summary="native runtime executed")
