"""Normalized surface event projection (SURF-04, AGNT-01, AUD-01, plan 10.3-03).

ONE pure function projects immutable `audit_events` rows (plus the terminal `RunOutcome`)
into a `SurfaceEvent` stream with a discriminated `kind` and a monotonic PER-SESSION `seq`.
Every surface consumes this same projection — WebUI over gateway SSE, TUI over an in-process
iterator — so the two number events identically.

This is a READ-ONLY projection: no DB writes, no pub/sub, no new event bus (AGNT-01 / D-022).
Payloads ride `payload_json` as already-redacted JSON strings (the audit `data` is redacted at
write time by `audit_service.emit`); they are never re-derived or parsed into the public field
(D-013). The seq is assigned over the whole per-session sequence (the caller passes
`audit_service.get_events_for_session`), which is what makes reconnect gap-detection
(`replay_since(last_seq)`) work across a 0..N-run session.
"""
from __future__ import annotations

import datetime
import json
from typing import Iterable, Optional, Sequence, get_args

from atlas_core.schemas.surface_session import EventKind, SurfaceEvent

from atlas_runtime.agents.base import RunOutcome

_EVENT_KINDS = frozenset(get_args(EventKind))

# Default audit event_type → SurfaceEvent kind. Covers every AuditEvent.event_type member
# (a test asserts completeness). `llm_call` is refined to text/reasoning by payload, and a
# producer may override any mapping with an explicit `surface_kind` payload hint (so the full
# EventKind vocabulary — including `retry` — is reachable from the ledger).
_KIND_MAP: dict[str, EventKind] = {
    "llm_call": "text",  # refined to "reasoning" by payload below
    "tool_call": "tool_call",
    "tool_requested": "tool_call",
    "tool_completed": "tool_result",
    "tool_failed": "error",
    "subagent_run": "task",
    "approval": "approval",
    "artifact": "retrieval",
    "wiki_update": "retrieval",
    "memory_change": "retrieval",
    "failure": "error",
    "discord_action": "tool_result",
    "golden_workflow_started": "task",
    "golden_workflow_completed": "task",
    "surface_session_started": "task",
    "surface_session_suspended": "task",
    "surface_session_resumed": "task",
    "surface_session_reclaimed": "task",
    "surface_session_completed": "task",
    "surface_session_failed": "error",
    "run_cancelled": "error",
    "permission_transition": "approval",
    "config_change": "task",
    "auth_change": "task",
    "model_call_start": "text",
    "model_call_end": "text",
    "provider_fallback": "error",
}


def _payload_dict(data: str) -> dict:
    """Best-effort parse of the audit data JSON string into a dict — for the kind decision
    only; the public SurfaceEvent.payload_json keeps the original string (D-013)."""
    try:
        parsed = json.loads(data)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _kind_for(event_type: str, payload: dict) -> EventKind:
    hint = payload.get("surface_kind")
    if hint in _EVENT_KINDS:  # explicit producer hint wins (makes every kind reachable)
        return hint  # type: ignore[return-value]
    if event_type == "llm_call":
        return "reasoning" if payload.get("reasoning") else "text"
    return _KIND_MAP.get(event_type, "task")


def normalize_surface_events(
    audit_events: Sequence,
    run_outcome: Optional[RunOutcome] = None,
    *,
    session_id: str,
    start_seq: int = 0,
) -> tuple[SurfaceEvent, ...]:
    """Project an ordered per-session AuditEvent sequence into SurfaceEvents.

    `audit_events` must already be ordered (caller passes `get_events_for_session`). `seq`
    is assigned incrementally from `start_seq` over the WHOLE sequence — making it
    per-session, not per-run. If `run_outcome` is given, a terminal `completion` event is
    appended carrying its status/summary/stop_reason. Pure: returns a tuple, writes nothing.
    """
    events: list[SurfaceEvent] = []
    seq = start_seq
    last_run_id: Optional[str] = None
    for ae in audit_events:
        payload = _payload_dict(ae.data)
        occurred_at = (
            ae.timestamp.isoformat()
            if hasattr(ae.timestamp, "isoformat")
            else str(ae.timestamp)
        )
        last_run_id = ae.run_id
        events.append(
            SurfaceEvent(
                session_id=session_id,
                seq=seq,
                kind=_kind_for(ae.event_type, payload),
                run_id=ae.run_id,
                occurred_at=occurred_at,
                payload_json=ae.data if isinstance(ae.data, str) else "{}",
            )
        )
        seq += 1

    if run_outcome is not None:
        events.append(
            SurfaceEvent(
                session_id=session_id,
                seq=seq,
                kind="completion",
                run_id=last_run_id,
                occurred_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                payload_json=json.dumps(
                    {
                        "status": run_outcome.status,
                        "summary": run_outcome.summary,
                        "stop_reason": run_outcome.stop_reason,
                    }
                ),
            )
        )
    return tuple(events)


def replay_since(
    events: Iterable[SurfaceEvent], last_seq: int
) -> tuple[SurfaceEvent, ...]:
    """Return only events with seq > last_seq — the reconnect gap-detection primitive."""
    return tuple(e for e in events if e.seq > last_seq)


__all__ = ["normalize_surface_events", "replay_since"]
