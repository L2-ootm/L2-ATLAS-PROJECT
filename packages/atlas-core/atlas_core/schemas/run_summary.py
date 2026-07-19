"""RunSummary — structured, JSON-serializable replacement for the free-text
`runs.summary` field (Phase 3 Track A, F8).

Unlike the 7 Pydantic domain models in `core.py` (which mirror DB tables 1:1
per D-012), `RunSummary` is a computed/derived artifact generated once at run
completion from that run's `audit_events` — it has no DDL of its own and is
stored as a JSON string inside the existing `runs.summary` TEXT column (no
migration needed; see F8.md section 4.1, Option A). A plain dataclass keeps
that boundary honest: this is a value object produced by
`run_summary_service.generate_run_summary()`, not a table row.

Backward compatibility: existing rows hold free-text summaries written before
this feature existed. Every reader of `runs.summary` MUST treat a value that
is not valid RunSummary JSON as legacy free text — see `from_json()` below and
its callers in `memory_router.py`.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class RunSummary:
    """Structured summary of one run, generated from its audit_events.

    `goal`/`outcome`/`key_decisions`/`next_actions` are synthesized by a cheap
    auxiliary LLM (genuinely free-text judgment calls); every other field is
    extracted deterministically from event data — no LLM call needed to know
    which tools ran or which files were touched (see run_summary_service.py).
    """

    goal: str = ""
    outcome: str = ""
    completed_actions: list[str] = field(default_factory=list)
    key_decisions: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    tools_used: dict[str, int] = field(default_factory=dict)
    duration_ms: int = 0
    next_actions: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Canonical JSON form stored in `runs.summary`."""
        return json.dumps(asdict(self), sort_keys=True)

    @staticmethod
    def from_json(text: str | None) -> "RunSummary | None":
        """Parse a `runs.summary` value as a structured RunSummary.

        Returns None for anything that is not a JSON object produced by this
        schema (empty string, legacy free text, malformed JSON) — callers use
        that None to fall back to treating the value as legacy free text.
        Never raises: a corrupt/foreign JSON blob is just as "not structured"
        as plain prose.
        """
        if not text:
            return None
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        try:
            return RunSummary(
                goal=str(data.get("goal", "")),
                outcome=str(data.get("outcome", "")),
                completed_actions=[str(x) for x in data.get("completed_actions", []) or []],
                key_decisions=[str(x) for x in data.get("key_decisions", []) or []],
                files_touched=[str(x) for x in data.get("files_touched", []) or []],
                blockers=[str(x) for x in data.get("blockers", []) or []],
                tools_used={str(k): int(v) for k, v in (data.get("tools_used") or {}).items()},
                duration_ms=int(data.get("duration_ms") or 0),
                next_actions=[str(x) for x in data.get("next_actions", []) or []],
            )
        except (TypeError, ValueError):
            return None
