"""ATLAS audit service — emit(), get_events_for_run(), export_jsonl().

This is the core write boundary for all audit data in the system.
Every hook callback in Wave 2 (atlas_audit plugin) delegates here.

Design constraints:
- HB-04-02: AuditEvent() is always constructed before any INSERT — Pydantic
  validates event_type (Literal enum) and raises ValidationError on invalid
  values before any SQL executes. No raw INSERT without model construction.
- D-013: data, args, result fields are JSON strings (not dicts).
- All writes are transactional: "with conn:" rolls back both audit_events and
  tool_calls INSERTs on any exception — no orphaned rows.
- No global state, no connection management — conn and lock are always injected
  by callers (dependency injection; connection management is the plugin's
  responsibility in Wave 2).
"""
from __future__ import annotations

import io
import json
import logging
import sqlite3
import threading
from typing import Any, Optional

from atlas_core.schemas.core import AuditEvent, ToolCall, SECRET_PATTERNS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _redact(text: str) -> str:
    """Apply all SECRET_PATTERNS to a string before persistence.

    Covers: URL querystring key=value, JSON key-value "token":"...", Bearer token.
    Replaces the secret value (group 2) with [REDACTED] while preserving the
    surrounding text structure (valid JSON remains valid JSON after redaction).
    """
    for pat in SECRET_PATTERNS:
        text = pat.sub(lambda m: m.group(0).replace(m.group(2), "[REDACTED]"), text)
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def emit(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: str,
    event_type: str,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    data: Optional[Any] = None,
    duration_ms: Optional[int] = None,
    policy_result: Optional[str] = None,
    tool_call_kwargs: Optional[dict] = None,
) -> AuditEvent:
    """Persist one AuditEvent (and optionally one ToolCall) in a single transaction.

    Steps:
    1. Serialize and redact the data payload.
    2. Construct AuditEvent — Pydantic validates event_type; ValidationError
       propagates to caller before any DB write (HB-04-02).
    3. If tool_call_kwargs is provided, serialize/redact args and result, then
       construct ToolCall linked to the event.
    4. Acquire lock, then write both rows atomically inside "with conn:" context
       manager. On any exception both INSERTs roll back together.
    5. Return the constructed AuditEvent.

    Args:
        conn: SQLite connection (may be shared across threads with check_same_thread=False).
        lock: threading.Lock protecting the shared connection.
        run_id: Identifier for the current agent run.
        event_type: One of the Literal values in AuditEvent.event_type.
        task_id: Hermes task_id from hook kwargs (DIV-004).
        session_id: Hermes session_id from hook kwargs.
        tool_call_id: Hermes tool_call_id from hook kwargs.
        tool_name: Name of the tool invoked (for tool_call/artifact events).
        data: Dict or None — serialized to JSON string and redacted before storage.
        duration_ms: Elapsed time in milliseconds for this event.
        policy_result: Optional policy evaluation result string.
        tool_call_kwargs: If not None, a ToolCall row is also written. Must contain
            at minimum "tool_name". Optional keys: "args" (dict|str), "result"
            (dict|str|None), "exit_code", "stdout", "stderr", "duration_ms",
            "policy_allowed", "requires_approval".

    Returns:
        The constructed and persisted AuditEvent.

    Raises:
        pydantic.ValidationError: If event_type or any other field fails Pydantic
            validation. No DB write occurs in this case.
    """
    # Step 1: serialize and redact data payload (D-013: data is str not dict)
    data_str = _redact(json.dumps(data if data is not None else {}))

    # Step 2: construct AuditEvent — ValidationError propagates before any INSERT
    event = AuditEvent(
        run_id=run_id,
        event_type=event_type,
        task_id=task_id,
        session_id=session_id,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        data=data_str,
        duration_ms=duration_ms,
        policy_result=policy_result,
    )
    row = event.model_dump()  # datetime → ISO 8601 string via field_serializer

    # Step 3: optionally construct ToolCall
    tc: Optional[ToolCall] = None
    if tool_call_kwargs is not None:
        tc_kwargs: dict = dict(tool_call_kwargs)

        # Serialize and redact args (D-013)
        args_val = tc_kwargs.get("args")
        if isinstance(args_val, dict):
            tc_kwargs["args"] = _redact(json.dumps(args_val))
        elif isinstance(args_val, str):
            tc_kwargs["args"] = _redact(args_val)
        else:
            tc_kwargs["args"] = "{}"

        # Serialize and redact result (D-013)
        result_val = tc_kwargs.get("result")
        if isinstance(result_val, dict):
            tc_kwargs["result"] = _redact(json.dumps(result_val))
        elif isinstance(result_val, str):
            tc_kwargs["result"] = _redact(result_val)
        else:
            tc_kwargs["result"] = None

        tc = ToolCall(audit_event_id=event.id, run_id=run_id, **tc_kwargs)

    # Step 4: acquire lock and write transactionally
    with lock:
        with conn:  # BEGIN … COMMIT on success, ROLLBACK on exception
            conn.execute(
                "INSERT INTO audit_events VALUES "
                "(:id,:run_id,:task_id,:session_id,:tool_call_id,"
                ":event_type,:tool_name,:timestamp,:duration_ms,:data,:policy_result)",
                row,
            )
            if tc is not None:
                conn.execute(
                    "INSERT INTO tool_calls VALUES "
                    "(:id,:audit_event_id,:run_id,:tool_name,:args,:result,"
                    ":exit_code,:stdout,:stderr,:duration_ms,:policy_allowed,"
                    ":requires_approval,:timestamp)",
                    tc.model_dump(),
                )

    logger.debug(
        "audit_service.emit: event_id=%s event_type=%s run_id=%s",
        event.id,
        event_type,
        run_id,
    )

    # Step 5: return the AuditEvent
    return event


def get_events_for_run(
    conn: sqlite3.Connection,
    run_id: str,
) -> list[AuditEvent]:
    """Return all AuditEvent rows for a run, ordered by timestamp ASC.

    Re-validates each row through AuditEvent() on read to catch any schema
    drift between stored data and the current model definition.

    Args:
        conn: SQLite connection.
        run_id: Run identifier to filter by.

    Returns:
        List of AuditEvent objects ordered by timestamp ascending.
    """
    cursor = conn.execute(
        "SELECT * FROM audit_events WHERE run_id=? ORDER BY timestamp ASC",
        (run_id,),
    )
    cols = [d[0] for d in cursor.description]
    return [AuditEvent(**dict(zip(cols, row))) for row in cursor]


def export_jsonl(
    conn: sqlite3.Connection,
    run_id: str,
    dest: Optional[io.TextIOBase] = None,
) -> str:
    """Export the ordered audit trail for a run as JSONL.

    Each line is a complete JSON object produced by AuditEvent.model_dump_json().
    Datetime fields are serialized to ISO 8601 strings by Pydantic's field_serializer.

    Args:
        conn: SQLite connection.
        run_id: Run identifier to filter by.
        dest: Optional text stream to write lines to (each line suffixed with "\\n").
            If None, only the return value is produced.

    Returns:
        JSONL string — one JSON object per line, joined by "\\n".
        Returns "" if no events exist for the given run_id.
    """
    cursor = conn.execute(
        "SELECT * FROM audit_events WHERE run_id=? ORDER BY timestamp ASC",
        (run_id,),
    )
    cols = [d[0] for d in cursor.description]
    lines: list[str] = []
    for row in cursor:
        event = AuditEvent(**dict(zip(cols, row)))
        line = event.model_dump_json()
        lines.append(line)
        if dest is not None:
            dest.write(line + "\n")
    return "\n".join(lines)
