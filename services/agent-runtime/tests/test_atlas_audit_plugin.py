"""Integration tests for atlas_audit Hermes plugin hook callbacks.

Tests inject the in-memory SQLite db fixture into the plugin via set_connection()
and pre-populate _CURRENT_RUN with a test session → run_id mapping, avoiding any
need to spawn a live Hermes process.

Pattern: each test exercises one hook callback end-to-end and asserts the
resulting audit_events and/or tool_calls rows via direct SQL queries.
"""

import pytest

import atlas_audit
from atlas_audit import (
    on_post_api_request,
    on_post_tool_call,
    on_subagent_stop,
    set_connection,
)


# ---------------------------------------------------------------------------
# Module-level fixture: wire plugin state for every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_plugin(db, run_id):
    """Inject db connection and seed _CURRENT_RUN for the test session.

    Tears down cleanly after each test so state never leaks between cases.
    """
    set_connection(db)
    with atlas_audit._STATE_LOCK:
        atlas_audit._CURRENT_RUN["test-session"] = run_id
    yield
    with atlas_audit._STATE_LOCK:
        atlas_audit._CURRENT_RUN.pop("test-session", None)
    set_connection(None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_post_tool_call_emits_audit_and_tool_call_rows(db, run_id):
    """on_post_tool_call with tool_name='terminal' produces one audit_events row
    (event_type='tool_call') and one tool_calls row linked to run_id."""
    on_post_tool_call(
        tool_name="terminal",
        args={"command": "echo hello"},
        session_id="test-session",
        task_id="test-task",
        tool_call_id="test-call",
        result='{"output": "hello"}',
        duration_ms=42,
    )

    audit_count = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE event_type='tool_call'"
    ).fetchone()[0]
    assert audit_count == 1, f"Expected 1 tool_call audit row, got {audit_count}"

    tc_count = db.execute(
        "SELECT COUNT(*) FROM tool_calls WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    assert tc_count == 1, f"Expected 1 tool_calls row, got {tc_count}"


def test_post_api_request_emits_llm_call_row(db, run_id):
    """on_post_api_request produces one audit_events row with event_type='llm_call'."""
    on_post_api_request(
        session_id="test-session",
        task_id="test-task",
        model="claude-sonnet-4-6",
        provider="anthropic",
        api_call_count=1,
        api_duration=1.234,
        finish_reason="stop",
        usage={"input_tokens": 2048, "output_tokens": 512},
    )

    count = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE event_type='llm_call'"
    ).fetchone()[0]
    assert count == 1, f"Expected 1 llm_call audit row, got {count}"


def test_subagent_stop_emits_subagent_run_row(db, run_id):
    """on_subagent_stop produces one audit_events row with event_type='subagent_run'."""
    on_subagent_stop(
        parent_session_id="test-session",
        child_role=None,
        child_summary="done",
        child_status="completed",
        duration_ms=1234,
    )

    count = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE event_type='subagent_run'"
    ).fetchone()[0]
    assert count == 1, f"Expected 1 subagent_run audit row, got {count}"


def test_hook_callback_does_not_reraise_on_error(db, run_id):
    """on_post_tool_call must not raise when session_id has no _CURRENT_RUN entry.

    The callback should log a warning and return — no AuditEvent row written.
    This verifies the fail-open requirement (T-04-03-D1 mitigation).
    """
    # Remove the test-session mapping to simulate unknown session
    with atlas_audit._STATE_LOCK:
        atlas_audit._CURRENT_RUN.pop("test-session", None)

    # Must not raise
    on_post_tool_call(
        tool_name="terminal",
        args={},
        session_id="no-such-session",
        task_id="t",
        tool_call_id="c",
        result=None,
        duration_ms=0,
    )

    count = db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    assert count == 0, f"Expected 0 audit rows (session unknown), got {count}"


def test_write_tool_produces_artifact_event(db, run_id):
    """on_post_tool_call with tool_name='Write' produces event_type='artifact'.

    Verifies _ARTIFACT_TOOLS detection and the artifact/tool_call branch
    in on_post_tool_call (Pitfall 6 — artifact tool name drift guard).
    """
    on_post_tool_call(
        tool_name="Write",
        args={"path": "/tmp/x.txt", "content": "hello"},
        session_id="test-session",
        task_id="t",
        tool_call_id="c",
        result="ok",
        duration_ms=5,
    )

    event_type = db.execute(
        "SELECT event_type FROM audit_events"
    ).fetchone()[0]
    assert event_type == "artifact", (
        f"Expected event_type='artifact' for Write tool, got {event_type!r}"
    )
