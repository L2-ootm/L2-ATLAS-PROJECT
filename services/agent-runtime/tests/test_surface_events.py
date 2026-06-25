"""Tests for surface_events — the normalized read-projection (SURF-04, AGNT-01, plan 10.3-03).

Covers the kind-coverage matrix, the terminal RunOutcome completion event, monotonic
per-session seq contiguous across multiple runs of one session, and reconnect replay.
"""
import datetime
import json
import uuid

import pytest

from atlas_core.schemas.core import AuditEvent
from atlas_core.schemas.surface_session import EventKind
from typing import get_args

from atlas_runtime import audit_service
from atlas_runtime import surface_events
from atlas_runtime.agents.base import RunOutcome
from atlas_runtime.surface_events import _KIND_MAP, normalize_surface_events, replay_since


def _ae(event_type: str, *, data: str = "{}", run_id: str = "r-1") -> AuditEvent:
    return AuditEvent(run_id=run_id, event_type=event_type, data=data, session_id="sess")


# ---------------------------------------------------------------------------
# kind map
# ---------------------------------------------------------------------------


def test_kind_map_covers_every_audit_event_type() -> None:
    valid = set(get_args(AuditEvent.model_fields["event_type"].annotation))
    assert valid == set(_KIND_MAP), "every AuditEvent.event_type must map to a kind"


@pytest.mark.parametrize("event_type,expected", sorted(_KIND_MAP.items()))
def test_normalizer_maps_every_audit_type(event_type: str, expected: str) -> None:
    evs = normalize_surface_events([_ae(event_type)], session_id="sess")
    assert evs[0].kind == expected


def test_llm_call_splits_text_vs_reasoning() -> None:
    text = normalize_surface_events([_ae("llm_call", data="{}")], session_id="sess")
    reasoning = normalize_surface_events(
        [_ae("llm_call", data='{"reasoning": true}')], session_id="sess"
    )
    assert text[0].kind == "text"
    assert reasoning[0].kind == "reasoning"


def test_every_event_kind_is_reachable() -> None:
    inputs = [
        _ae("llm_call", data="{}"),  # text
        _ae("llm_call", data='{"reasoning": true}'),  # reasoning
        _ae("tool_call"),  # tool_call
        _ae("tool_completed"),  # tool_result
        _ae("subagent_run"),  # task
        _ae("tool_failed"),  # error
        _ae("artifact"),  # retrieval
        _ae("approval"),  # approval
        _ae("failure", data='{"surface_kind": "retry"}'),  # retry via producer hint
    ]
    evs = normalize_surface_events(inputs, RunOutcome(status="succeeded"), session_id="sess")
    produced = {e.kind for e in evs}
    assert set(get_args(EventKind)).issubset(produced)


# ---------------------------------------------------------------------------
# completion + seq + replay
# ---------------------------------------------------------------------------


def test_completion_event_carries_run_outcome() -> None:
    outcome = RunOutcome(status="failed", summary="boom", stop_reason="max_runtime_exceeded")
    evs = normalize_surface_events([_ae("llm_call")], outcome, session_id="sess")
    completion = evs[-1]
    assert completion.kind == "completion"
    payload = json.loads(completion.payload_json)
    assert payload == {
        "status": "failed",
        "summary": "boom",
        "stop_reason": "max_runtime_exceeded",
    }


def test_seq_is_monotonic_per_session() -> None:
    evs = normalize_surface_events(
        [_ae("llm_call"), _ae("tool_call"), _ae("tool_completed")], session_id="sess"
    )
    assert [e.seq for e in evs] == [0, 1, 2]


def test_replay_since_returns_only_newer() -> None:
    evs = normalize_surface_events(
        [_ae("llm_call"), _ae("tool_call"), _ae("tool_completed")], session_id="sess"
    )
    newer = replay_since(evs, last_seq=0)
    assert [e.seq for e in newer] == [1, 2]


def test_seq_contiguous_across_two_runs_of_one_session(db, lock) -> None:
    """The per-session gap-detection guarantee: a session spanning two runs yields ONE
    contiguous seq space (0..N), not two restarting per-run sequences."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    mission_id = str(uuid.uuid4())
    run_a = str(uuid.uuid4())
    run_b = str(uuid.uuid4())
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (mission_id, "m", "", "running", "", now, now),
    )
    for rid in (run_a, run_b):
        db.execute(
            "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
            "VALUES (?,?,?,?,?,?,?)",
            (rid, mission_id, "sess-1", "running", now, None, ""),
        )
    db.commit()

    audit_service.emit(db, lock, run_id=run_a, event_type="llm_call", session_id="sess-1")
    audit_service.emit(db, lock, run_id=run_a, event_type="tool_call", session_id="sess-1")
    audit_service.emit(db, lock, run_id=run_b, event_type="tool_completed", session_id="sess-1")
    audit_service.emit(db, lock, run_id=run_b, event_type="llm_call", session_id="sess-1")

    aes = audit_service.get_events_for_session(db, "sess-1")
    assert len(aes) == 4
    evs = normalize_surface_events(aes, session_id="sess-1")
    assert [e.seq for e in evs] == [0, 1, 2, 3]
    assert {e.run_id for e in evs} == {run_a, run_b}


def test_normalizer_performs_no_writes(db, lock) -> None:
    """Pure projection: normalizing must not touch the DB."""
    before = db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    normalize_surface_events([_ae("llm_call")], session_id="sess")
    after = db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    assert before == after
