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
_EVIDENCE_AVAILABILITY = frozenset(
    {"available", "redacted", "partial", "binary", "too_large", "corrupt", "unavailable"}
)
_EVIDENCE_COVERAGE = frozenset({"complete", "tool_only", "partial", "unavailable"})
_CLEANUP_STATES = frozenset({"complete", "partial", "failed"})
_ORCHESTRATION_FIELDS = (
    "runtime",
    "surface_kind",
    "orchestration",
    "actor",
    "phase",
    "status",
    "subagent_id",
    "parent_id",
    "depth",
    "goal",
    "model",
    "tool",
    "tool_count",
    "background",
    "mode",
    "role",
    "team_run_id",
    "goal_id",
    "transition",
)

# Default audit event_type → SurfaceEvent kind. Covers every AuditEvent.event_type member
# (a test asserts completeness). `llm_call` is refined to text/reasoning by payload, and a
# producer may override any mapping with an explicit `surface_kind` payload hint (so the full
# EventKind vocabulary — including `retry` — is reachable from the ledger).
_KIND_MAP: dict[str, EventKind] = {
    "llm_call": "text",  # refined to "reasoning" by payload below
    "llm_delta": "text",
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
    "goal_judgement": "task",
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
    if payload.get("transition") in {"succeeded", "failed", "cancelled"}:
        return "completion"
    if event_type == "llm_call":
        return "reasoning" if payload.get("reasoning") else "text"
    if event_type == "goal_judgement" and payload.get("state") in {
        "done",
        "paused",
        "exhausted",
        "failed",
    }:
        return "completion"
    return _KIND_MAP.get(event_type, "task")


def _non_negative_int(value: object) -> int:
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _optional_text(value: object) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def _evidence_ids(evidence: dict) -> list[str]:
    candidates: list[object] = [evidence.get("change_set_id")]
    for key in ("evidence_ids", "change_set_ids", "child_change_set_ids"):
        value = evidence.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    seen: set[str] = set()
    identities: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate or candidate in seen:
            continue
        seen.add(candidate)
        identities.append(candidate)
    return identities


def _orchestration_evidence_payload(payload: dict) -> Optional[str]:
    """Return canonical metadata-only JSON for an orchestration evidence event.

    Evidence bodies are retrieved through the owner-authorized range API. The
    normalized event deliberately whitelists identity, totals, provenance and
    failure state so a producer cannot accidentally push patches, hunks, blobs
    or full results through replay/SSE. Reference order is stable and duplicate
    child identities are removed without recomputing Rust-owned totals.
    """
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict) or payload.get("orchestration") not in {
        "subagent",
        "team",
        "goal",
    }:
        return None

    raw_ancestry = evidence.get("ancestry")
    ancestry = raw_ancestry if isinstance(raw_ancestry, dict) else {}
    coverage = evidence.get("coverage")
    if coverage not in _EVIDENCE_COVERAGE:
        coverage = "unavailable"
    availability = evidence.get("availability")
    if availability not in _EVIDENCE_AVAILABILITY:
        availability = "unavailable"

    raw_cleanup = evidence.get("cleanup")
    cleanup = None
    if isinstance(raw_cleanup, dict):
        cleanup_status = raw_cleanup.get("status")
        if cleanup_status not in _CLEANUP_STATES:
            cleanup_status = "failed"
        cleanup = {
            "status": cleanup_status,
            "error": _optional_text(raw_cleanup.get("error")),
        }

    raw_incident = evidence.get("incident")
    incident = None
    if isinstance(raw_incident, dict):
        incident = {
            "kind": _optional_text(raw_incident.get("kind")) or "policy_incident",
            "status": _optional_text(raw_incident.get("status")) or "denied",
            "reason": _optional_text(raw_incident.get("reason")),
        }

    normalized = {
        key: payload[key]
        for key in _ORCHESTRATION_FIELDS
        if key in payload and payload[key] is not None
    }
    normalized["evidence"] = {
        "evidence_ids": _evidence_ids(evidence),
        "file_count": _non_negative_int(evidence.get("file_count")),
        "additions": _non_negative_int(evidence.get("additions")),
        "deletions": _non_negative_int(evidence.get("deletions")),
        "coverage": coverage,
        "availability": availability,
        "redaction_count": _non_negative_int(evidence.get("redaction_count")),
        "ancestry": {
            "actor_id": _optional_text(ancestry.get("actor_id")),
            "parent_actor_id": _optional_text(ancestry.get("parent_actor_id")),
            "team_run_id": _optional_text(ancestry.get("team_run_id")),
            "goal_id": _optional_text(ancestry.get("goal_id")),
        },
        "incident": incident,
    }
    if cleanup is not None:
        normalized["evidence"]["cleanup"] = cleanup

    unsafe_state = (
        availability != "available"
        or coverage in {"partial", "unavailable"}
        or incident is not None
        or (cleanup is not None and cleanup["status"] != "complete")
        or normalized.get("phase") in {"failed", "cancelled", "orphaned"}
    )
    if unsafe_state:
        normalized["status"] = (
            "cancelled" if normalized.get("phase") == "cancelled" else "failed"
        )
    return json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


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
        canonical_evidence = _orchestration_evidence_payload(payload)
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
                payload_json=(
                    canonical_evidence
                    if canonical_evidence is not None
                    else ae.data if isinstance(ae.data, str) else "{}"
                ),
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
