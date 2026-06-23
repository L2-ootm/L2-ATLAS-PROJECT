"""RED-first tests for golden_workflow_service core helpers (Phase 10.0.5-01).

Integration tests against the real in-memory DB (all migrations applied via
conftest.py's `db` fixture) — no mocking of golden_workflow_service internals.
"""
from __future__ import annotations

import hashlib

from atlas_runtime import mission_service
from atlas_runtime.audit_service import get_events_for_run
from atlas_runtime import golden_workflow_service


def test_ensure_golden_run_returns_operator_run_id_and_is_idempotent(db, lock):
    run_id_1 = golden_workflow_service.ensure_golden_run(db, lock)
    run_id_2 = golden_workflow_service.ensure_golden_run(db, lock)

    assert run_id_1 == mission_service.OPERATOR_RUN_ID
    assert run_id_2 == mission_service.OPERATOR_RUN_ID

    # Idempotent: only one missions row for the operator run id.
    count = db.execute(
        "SELECT COUNT(*) FROM missions WHERE id=?",
        (mission_service.OPERATOR_RUN_ID,),
    ).fetchone()[0]
    assert count == 1


def test_record_artifact_inserts_row(db, lock):
    run_id = golden_workflow_service.ensure_golden_run(db, lock)
    content = b"hello"

    artifact = golden_workflow_service.record_artifact(
        db,
        lock,
        run_id=run_id,
        path="x.md",
        artifact_type="file_write",
        content=content,
    )

    assert artifact.path == "x.md"
    assert artifact.sha256 == hashlib.sha256(content).hexdigest()
    assert artifact.size_bytes == len(content)

    rows = db.execute(
        "SELECT path, sha256, size_bytes FROM artifacts WHERE run_id=?",
        (run_id,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "x.md"
    assert rows[0][1] == hashlib.sha256(content).hexdigest()
    assert rows[0][2] == len(content)


def test_record_artifact_emits_artifact_audit_event(db, lock):
    run_id = golden_workflow_service.ensure_golden_run(db, lock)

    golden_workflow_service.record_artifact(
        db,
        lock,
        run_id=run_id,
        path="x.md",
        artifact_type="file_write",
        content=b"hello",
    )

    events = [e for e in get_events_for_run(db, run_id) if e.event_type == "artifact"]
    assert len(events) == 1
    import json

    data = json.loads(events[0].data)
    assert data["path"] == "x.md"


def test_emit_workflow_event_started_and_completed(db, lock):
    run_id = golden_workflow_service.ensure_golden_run(db, lock)

    golden_workflow_service.emit_workflow_event(
        db, lock, run_id=run_id, workflow_id="repo_triage", phase="started"
    )
    golden_workflow_service.emit_workflow_event(
        db, lock, run_id=run_id, workflow_id="repo_triage", phase="completed"
    )

    events = get_events_for_run(db, run_id)
    started = [e for e in events if e.event_type == "golden_workflow_started"]
    completed = [e for e in events if e.event_type == "golden_workflow_completed"]

    assert len(started) == 1
    assert len(completed) == 1

    import json

    assert json.loads(started[0].data)["workflow_id"] == "repo_triage"
    assert json.loads(completed[0].data)["workflow_id"] == "repo_triage"


def test_record_artifact_twice_same_path_appends_two_rows(db, lock):
    run_id = golden_workflow_service.ensure_golden_run(db, lock)

    golden_workflow_service.record_artifact(
        db,
        lock,
        run_id=run_id,
        path="dup.md",
        artifact_type="file_write",
        content=b"first",
    )
    golden_workflow_service.record_artifact(
        db,
        lock,
        run_id=run_id,
        path="dup.md",
        artifact_type="file_write",
        content=b"second",
    )

    rows = db.execute(
        "SELECT path FROM artifacts WHERE run_id=? AND path=?",
        (run_id, "dup.md"),
    ).fetchall()
    assert len(rows) == 2
