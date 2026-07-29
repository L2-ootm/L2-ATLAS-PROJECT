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


@pytest.mark.parametrize("transition", ["succeeded", "failed", "cancelled"])
def test_terminal_transition_is_a_stable_completion_event(transition: str) -> None:
    events = normalize_surface_events(
        [_ae("tool_call", data=json.dumps({"transition": transition}))],
        session_id="sess",
    )
    assert events[0].kind == "completion"


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


# ---------------------------------------------------------------------------
# orchestration Evidence Plane fixture (10.8-10)
# ---------------------------------------------------------------------------


def test_orchestration_evidence_fixture_is_metadata_only_and_byte_stable() -> None:
    occurred_at = datetime.datetime(
        2026, 7, 29, 17, 0, 0, tzinfo=datetime.timezone.utc
    )
    actor = AuditEvent(
        run_id="run-parent",
        session_id="surface-1",
        event_type="subagent_run",
        timestamp=occurred_at,
        data=json.dumps(
            {
                "surface_kind": "task",
                "orchestration": "subagent",
                "actor": True,
                "phase": "completed",
                "status": "succeeded",
                "subagent_id": "actor-parent",
                "parent_id": "run-parent",
                "goal": "Inspect runtime",
                "evidence": {
                    "change_set_id": "aggregate-parent",
                    "child_change_set_ids": ["leaf-a", "leaf-b", "leaf-a"],
                    "file_count": 2,
                    "additions": 11,
                    "deletions": 4,
                    "coverage": "complete",
                    "availability": "available",
                    "redaction_count": 0,
                    "ancestry": {
                        "actor_id": "actor-parent",
                        "parent_actor_id": None,
                        "team_run_id": None,
                        "goal_id": "goal-1",
                    },
                    "patch": "must never cross the event boundary",
                    "hunks": [{"content": "must never cross the event boundary"}],
                    "blob": "must never cross the event boundary",
                },
            },
            ensure_ascii=False,
        ),
    )
    team = AuditEvent(
        run_id="run-parent",
        session_id="surface-1",
        event_type="subagent_run",
        timestamp=occurred_at + datetime.timedelta(seconds=1),
        data=json.dumps(
            {
                "surface_kind": "task",
                "orchestration": "team",
                "phase": "cancelled",
                "status": "cancelled",
                "team_run_id": "team-1",
                "evidence": {
                    "evidence_ids": ["leaf-a", "leaf-b", "leaf-b"],
                    "file_count": 2,
                    "additions": 11,
                    "deletions": 4,
                    "coverage": "partial",
                    "availability": "partial",
                    "cleanup": {
                        "status": "partial",
                        "error": "worker still stopping",
                    },
                },
            }
        ),
    )
    incident = AuditEvent(
        run_id="run-child",
        session_id="surface-1",
        event_type="failure",
        timestamp=occurred_at + datetime.timedelta(seconds=2),
        data=json.dumps(
            {
                "surface_kind": "error",
                "orchestration": "goal",
                "phase": "failed",
                "status": "failed",
                "goal_id": "goal-1",
                "evidence": {
                    "change_set_ids": ["leaf-a"],
                    "file_count": 1,
                    "additions": 7,
                    "deletions": 1,
                    "coverage": "unavailable",
                    "availability": "unavailable",
                    "incident": {
                        "kind": "read_only_mutation",
                        "status": "denied",
                        "reason": "actor produced file changes",
                    },
                    "result": "must never cross the event boundary",
                },
            }
        ),
    )

    events = normalize_surface_events(
        [actor, team, incident],
        session_id="surface-1",
        start_seq=40,
    )

    assert [event.seq for event in events] == [40, 41, 42]
    assert [event.kind for event in events] == ["task", "task", "error"]
    assert [event.occurred_at for event in events] == [
        "2026-07-29T17:00:00+00:00",
        "2026-07-29T17:00:01+00:00",
        "2026-07-29T17:00:02+00:00",
    ]
    assert events[0].payload_json == (
        '{"actor":true,"evidence":{"additions":11,"ancestry":{"actor_id":'
        '"actor-parent","goal_id":"goal-1","parent_actor_id":null,'
        '"team_run_id":null},"availability":"available","coverage":"complete",'
        '"deletions":4,"evidence_ids":["aggregate-parent","leaf-a","leaf-b"],'
        '"file_count":2,"incident":null,"redaction_count":0},'
        '"goal":"Inspect runtime","orchestration":"subagent","parent_id":'
        '"run-parent","phase":"completed","status":"succeeded","subagent_id":'
        '"actor-parent","surface_kind":"task"}'
    )
    assert events[1].payload_json == (
        '{"evidence":{"additions":11,"ancestry":{"actor_id":null,"goal_id":'
        'null,"parent_actor_id":null,"team_run_id":null},"availability":'
        '"partial","cleanup":{"error":"worker still stopping","status":'
        '"partial"},"coverage":"partial","deletions":4,"evidence_ids":'
        '["leaf-a","leaf-b"],"file_count":2,"incident":null,'
        '"redaction_count":0},"orchestration":"team","phase":"cancelled",'
        '"status":"cancelled","surface_kind":"task","team_run_id":"team-1"}'
    )
    assert events[2].payload_json == (
        '{"evidence":{"additions":7,"ancestry":{"actor_id":null,"goal_id":'
        'null,"parent_actor_id":null,"team_run_id":null},"availability":'
        '"unavailable","coverage":"unavailable","deletions":1,"evidence_ids":'
        '["leaf-a"],"file_count":1,"incident":{"kind":"read_only_mutation",'
        '"reason":"actor produced file changes","status":"denied"},'
        '"redaction_count":0},"goal_id":"goal-1","orchestration":"goal",'
        '"phase":"failed","status":"failed","surface_kind":"error"}'
    )
    serialized = "\n".join(event.model_dump_json() for event in events)
    assert "must never cross the event boundary" not in serialized
    assert '"patch"' not in serialized
    assert '"hunks"' not in serialized
    assert '"blob"' not in serialized
    assert '"result"' not in serialized


def test_orchestration_evidence_unknown_states_fail_closed() -> None:
    events = normalize_surface_events(
        [
            _ae(
                "subagent_run",
                data=json.dumps(
                    {
                        "orchestration": "subagent",
                        "phase": "completed",
                        "status": "succeeded",
                        "evidence": {
                            "change_set_id": "change-1",
                            "coverage": "future-value",
                            "availability": "future-value",
                            "cleanup": {"status": "future-value"},
                        },
                    }
                ),
            )
        ],
        session_id="sess",
    )
    payload = json.loads(events[0].payload_json)
    assert payload["evidence"]["coverage"] == "unavailable"
    assert payload["evidence"]["availability"] == "unavailable"
    assert payload["evidence"]["cleanup"]["status"] == "failed"
    assert payload["status"] == "failed"
