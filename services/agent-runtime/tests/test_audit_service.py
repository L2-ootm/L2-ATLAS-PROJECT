"""Full test suite for atlas_runtime.audit_service — Wave 1 implementation.

Covers:
  RUNTIME-03: emit() writes AuditEvent + optional ToolCall rows transactionally,
              validates event_type via Pydantic, and redacts secrets in data.
  AUDIT-01:   get_events_for_run() returns ordered AuditEvent list.
  AUDIT-02:   export_jsonl() produces valid JSONL with all fields present.
"""

import json

import pytest
from pydantic import ValidationError

from atlas_runtime.audit_service import emit, export_jsonl, get_events_for_run


# ---------------------------------------------------------------------------
# RUNTIME-03: basic emit() coverage
# ---------------------------------------------------------------------------


def test_emit_tool_call(db, run_id, lock):
    """emit with event_type='tool_call' and tool_call_kwargs writes one audit_events
    row AND one tool_calls row, both with the correct run_id."""
    emit(
        db,
        lock,
        run_id=run_id,
        event_type="tool_call",
        task_id="task-1",
        session_id="sess-1",
        tool_call_id="tc-1",
        tool_name="terminal",
        data={"cmd": "ls"},
        duration_ms=42,
        tool_call_kwargs={
            "tool_name": "terminal",
            "args": {"command": "ls"},
            "result": '{"output": "file.txt"}',
        },
    )
    audit_count = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    assert audit_count == 1

    tc_count = db.execute(
        "SELECT COUNT(*) FROM tool_calls WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    assert tc_count == 1


def test_emit_llm_call(db, run_id, lock):
    """emit with event_type='llm_call' and no tool_call_kwargs writes one
    audit_events row and zero tool_calls rows."""
    emit(
        db,
        lock,
        run_id=run_id,
        event_type="llm_call",
        data={"model": "claude-3-5", "tokens": 512},
    )
    audit_count = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    assert audit_count == 1

    tc_count = db.execute(
        "SELECT COUNT(*) FROM tool_calls WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    assert tc_count == 0


def test_emit_artifact(db, run_id, lock):
    """emit with event_type='artifact' and tool_call_kwargs writes one audit_events
    row with event_type='artifact' AND one tool_calls row."""
    emit(
        db,
        lock,
        run_id=run_id,
        event_type="artifact",
        tool_name="Write",
        tool_call_kwargs={
            "tool_name": "Write",
            "args": {"path": "/tmp/x.txt"},
        },
    )
    audit_count = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    assert audit_count == 1

    row = db.execute(
        "SELECT event_type FROM audit_events WHERE run_id=?", (run_id,)
    ).fetchone()
    assert row[0] == "artifact"

    tc_count = db.execute(
        "SELECT COUNT(*) FROM tool_calls WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    assert tc_count == 1


# ---------------------------------------------------------------------------
# RUNTIME-03: secret redaction (HB-04-01)
# ---------------------------------------------------------------------------


def test_emit_redacts_secret_in_data(db, run_id, lock):
    """emit with a dict containing 'token' key stores [REDACTED] instead of the
    raw secret value in the data column of audit_events, and the stored string
    remains valid JSON."""
    emit(
        db,
        lock,
        run_id=run_id,
        event_type="llm_call",
        data={"token": "sk-abc123", "normal_key": "value"},
    )
    row = db.execute(
        "SELECT data FROM audit_events WHERE run_id=?", (run_id,)
    ).fetchone()[0]

    assert "sk-abc123" not in row
    assert "[REDACTED]" in row
    # Stored data must still be valid JSON (not broken by redaction)
    parsed = json.loads(row)
    assert parsed["token"] == "[REDACTED]"
    assert parsed["normal_key"] == "value"


@pytest.mark.parametrize("value,raw", [
    ("sk-string", '"sk-string"'),       # JSON string value
    (42, "42"),                          # JSON numeric value (WR-04 coverage)
    (None, "null"),                      # JSON null
])
def test_redact_json_value_types_remain_valid_json(db, run_id, lock, value, raw):
    """Redaction of JSON key-value pairs must produce valid JSON for string,
    numeric, and null secret values.  Each stored data field must survive
    json.loads() after the secret value is replaced."""
    emit(
        db,
        lock,
        run_id=run_id,
        event_type="llm_call",
        data={"token": value, "ok": "x"},
    )
    stored = db.execute(
        "SELECT data FROM audit_events WHERE run_id=?", (run_id,)
    ).fetchone()[0]

    assert raw not in stored or "[REDACTED]" in stored
    parsed = json.loads(stored)  # Must not raise
    assert parsed["token"] == "[REDACTED]"
    assert parsed["ok"] == "x"


# ---------------------------------------------------------------------------
# RUNTIME-03: Pydantic enum guard — no orphaned rows on invalid event_type (HB-04-02)
# ---------------------------------------------------------------------------


def test_emit_invalid_event_type_raises_no_orphan(db, run_id, lock):
    """emit with an invalid event_type raises pydantic.ValidationError before any
    INSERT executes. audit_events count remains 0 after the exception."""
    with pytest.raises(ValidationError):
        emit(db, lock, run_id=run_id, event_type="not_a_real_type")

    count = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    assert count == 0


# ---------------------------------------------------------------------------
# AUDIT-01: ordered retrieval
# ---------------------------------------------------------------------------


def test_get_events_for_run_ordered(db, run_id, lock):
    """get_events_for_run returns a list of AuditEvent objects with timestamps in
    ascending order after emitting 3 events."""
    from atlas_core.schemas.core import AuditEvent

    emit(db, lock, run_id=run_id, event_type="llm_call", data={"seq": 1})
    emit(db, lock, run_id=run_id, event_type="llm_call", data={"seq": 2})
    emit(db, lock, run_id=run_id, event_type="llm_call", data={"seq": 3})

    events = get_events_for_run(db, run_id)

    assert len(events) == 3
    assert all(isinstance(e, AuditEvent) for e in events)
    assert events[0].timestamp <= events[1].timestamp <= events[2].timestamp


# ---------------------------------------------------------------------------
# AUDIT-02: JSONL export
# ---------------------------------------------------------------------------


def test_export_jsonl_valid(db, run_id, lock):
    """export_jsonl returns a string with exactly 2 lines after emitting 2 events;
    each line is valid JSON and contains the correct run_id value."""
    emit(db, lock, run_id=run_id, event_type="llm_call", data={"n": 1})
    emit(db, lock, run_id=run_id, event_type="artifact", tool_name="Write")

    jsonl = export_jsonl(db, run_id)

    lines = [ln for ln in jsonl.splitlines() if ln.strip()]
    assert len(lines) == 2

    for line in lines:
        obj = json.loads(line)
        assert "run_id" in obj
        assert obj["run_id"] == run_id
