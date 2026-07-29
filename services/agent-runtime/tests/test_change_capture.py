from __future__ import annotations

import json
from pathlib import Path

import pytest

import atlas_audit
from atlas_audit import on_post_tool_call, set_connection
from atlas_runtime.evidence_bridge import CaptureReceipt


@pytest.fixture(autouse=True)
def setup_plugin(db, run_id):
    set_connection(db)
    with atlas_audit._STATE_LOCK:
        atlas_audit._CURRENT_RUN["capture-session"] = run_id
    yield
    with atlas_audit._STATE_LOCK:
        atlas_audit._CURRENT_RUN.pop("capture-session", None)
    set_connection(None)


@pytest.mark.parametrize(
    ("outcome", "expected_coverage"),
    [
        ("succeeded", "complete"),
        ("failed", "partial"),
        ("timed_out", "partial"),
        ("aborted", "partial"),
    ],
)
def test_file_tool_outcomes_emit_normalized_evidence_receipts(
    monkeypatch, tmp_path, db, outcome, expected_coverage
):
    workspace = tmp_path / "workspace"
    target = workspace / "nested" / "note.txt"
    target.parent.mkdir(parents=True)
    observed = {}

    def persist_change_capture(**kwargs):
        observed.update(kwargs["capture"])
        return CaptureReceipt(
            change_set_id="change-1",
            coverage=expected_coverage,
            status="captured" if outcome == "succeeded" else "partial",
            file_count=1,
            additions=1,
            deletions=1,
            redaction_count=2,
        )

    monkeypatch.setattr(
        atlas_audit.evidence_bridge,
        "persist_change_capture",
        persist_change_capture,
    )
    on_post_tool_call(
        tool_name="write_file",
        args={"path": str(target), "content": "api_key=after-secret\n"},
        result={"status": outcome},
        session_id="capture-session",
        tool_call_id="call-1",
        duration_ms=17,
        capture_metadata={
            "workspace_root": str(workspace),
            "path": str(target),
            "before": "api_key=before-secret\n",
            "after": "api_key=after-secret\n",
            "operation": "edit",
            "outcome": outcome,
            "actor_id": "actor-1",
        },
    )

    assert observed["files"][0]["path"] == "nested/note.txt"
    assert observed["coverage"] == expected_coverage
    assert observed["actor_id"] == "actor-1"
    event_data = json.loads(
        db.execute(
            "SELECT data FROM audit_events WHERE tool_call_id='call-1'"
        ).fetchone()[0]
    )
    assert event_data["evidence"]["capture_status"] in {"captured", "partial"}
    assert event_data["evidence"]["change_set_id"] == "change-1"
    assert event_data["evidence"]["duration_ms"] == 17


def test_outside_workspace_capture_is_explicitly_unavailable(
    monkeypatch, tmp_path, db
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    called = False

    def persist_change_capture(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("outside path must not cross the Rust boundary")

    monkeypatch.setattr(
        atlas_audit.evidence_bridge,
        "persist_change_capture",
        persist_change_capture,
    )
    on_post_tool_call(
        tool_name="Write",
        args={"path": str(outside), "content": "do not capture"},
        result="failed",
        session_id="capture-session",
        tool_call_id="outside-call",
        capture_metadata={
            "workspace_root": str(workspace),
            "path": str(outside),
            "before": "",
            "after": "do not capture",
            "operation": "create",
            "outcome": "failed",
        },
    )

    assert called is False
    data = json.loads(
        db.execute(
            "SELECT data FROM audit_events WHERE tool_call_id='outside-call'"
        ).fetchone()[0]
    )
    assert data["evidence"]["capture_status"] == "unavailable"
    assert data["evidence"]["error_code"] == "outside_workspace"
    assert str(Path(outside)) not in json.dumps(data)

