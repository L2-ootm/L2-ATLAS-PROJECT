"""Structured run-summary generation (Phase 3 Track A, F8).

`generate_run_summary()` turns one run's raw `audit_events` into a
`RunSummary` — the JSON payload `run_service.complete_run()` stores in
`runs.summary`, replacing the previous free-text string.

Design (F8.md section 3.2): most fields are extracted deterministically from
event data — which tools ran, which files were touched, which errors fired,
how long the run took. Only `goal`, `outcome`, `key_decisions`, and
`next_actions` require genuine free-text judgment, so only those are handed
to a cheap auxiliary LLM. Everything else never leaves Python — cheaper,
faster, and directly unit-testable without a model in the loop.

The auxiliary call is injected as `synthesize` (mirrors
`mission_loop_service.Judge`'s DI pattern) so tests can stub it and the
default implementation (`_foundation_synthesize`) is fail-open: any error —
missing foundation, no configured provider, network failure — degrades to
the deterministic-only summary rather than blocking `complete_run()`.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from typing import Any, Callable

from atlas_core.schemas.core import AuditEvent
from atlas_core.schemas.run_summary import RunSummary

logger = logging.getLogger(__name__)

# Tool names used for runtime bookkeeping (native.py's provider-selection
# breadcrumbs), not agent actions — excluded from tools_used/completed_actions
# so the summary reflects real work, not plumbing.
_BOOKKEEPING_TOOLS = frozenset({"native_runtime", "freellmapi", "mock"})

# Argument keys that name a filesystem path, across every tool's arg schema
# observed in this codebase (workspace/read_file/write_file/patch/terminal
# cwd). Mirrors tool_service._PATH_ARG_KEYS without importing it — that set
# is scoped to policy target-path detection, a different (if overlapping)
# concern from summary extraction.
_PATH_KEYS = frozenset(
    {"path", "file", "file_path", "target", "target_path", "destination", "dest"}
)

_MESSAGE_KEYS = ("error", "message", "summary", "reason", "detail")

Synthesizer = Callable[[list[AuditEvent], RunSummary], dict[str, Any]]


def _parse_data(event: AuditEvent) -> dict[str, Any]:
    try:
        parsed = json.loads(event.data or "{}")
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_message(data: dict[str, Any]) -> str:
    """Best-effort human message from an event's data dict (mirrors
    memory_router._failure_message, applied here to a dict instead of a raw
    JSON string since callers have already parsed it)."""
    for key in _MESSAGE_KEYS:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _extract_paths(data: dict[str, Any]) -> list[str]:
    """Path-like argument values from an event's data — checks the nested
    `arguments` dict (native.py tool_requested shape) and the top level
    (any future/other emitter that inlines args directly)."""
    out: list[str] = []
    nested = data.get("arguments")
    sources = [data]
    if isinstance(nested, dict):
        sources.append(nested)
    for source in sources:
        for key, val in source.items():
            if key.lower() in _PATH_KEYS and isinstance(val, str) and val.strip():
                out.append(val.strip())
    return out


def _extract_deterministic(events: list[AuditEvent]) -> RunSummary:
    """Everything that does not require judgment — pure data extraction."""
    tools_used: dict[str, int] = {}
    completed_actions: list[str] = []
    blockers: list[str] = []
    files_touched: list[str] = []
    seen_files: set[str] = set()
    outcome_hint = ""

    def _note_files(data: dict[str, Any]) -> None:
        for path in _extract_paths(data):
            if path not in seen_files:
                seen_files.add(path)
                files_touched.append(path)

    for event in events:
        data = _parse_data(event)

        if event.event_type in ("tool_completed", "tool_failed"):
            name = event.tool_name or str(data.get("tool_name") or data.get("tool") or "")
            if name and name not in _BOOKKEEPING_TOOLS:
                tools_used[name] = tools_used.get(name, 0) + 1
                if event.event_type == "tool_completed":
                    completed_actions.append(name)
                else:
                    blockers.append(_extract_message(data) or f"{name} failed")
            _note_files(data)
        elif event.event_type == "tool_requested":
            _note_files(data)
        elif event.event_type == "failure":
            msg = _extract_message(data)
            if msg:
                blockers.append(msg)
        elif event.event_type == "subagent_run":
            role = data.get("role")
            goal = data.get("goal")
            phase = data.get("phase")
            if phase == "completed":
                label = str(goal or role or "subagent")[:120]
                status = data.get("status") or "done"
                completed_actions.append(f"delegated: {label} -> {status}")
            elif phase is None and role:
                # subagent_service.dispatch_subagent's stub payload has no
                # "phase" key at all — it is the whole (synchronous) record.
                completed_actions.append(f"delegated to {role}")
        elif event.event_type == "goal_judgement":
            verdict = data.get("verdict")
            reason = data.get("reason")
            if verdict:
                label = f"judged: {verdict}"
                if reason:
                    label += f" ({reason})"
                completed_actions.append(label)
                if verdict == "done":
                    outcome_hint = "succeeded"

    if not outcome_hint:
        outcome_hint = "failed" if blockers else ""

    duration_ms = 0
    if len(events) >= 2:
        delta = events[-1].timestamp - events[0].timestamp
        duration_ms = max(0, int(delta.total_seconds() * 1000))

    return RunSummary(
        outcome=outcome_hint,
        completed_actions=completed_actions,
        files_touched=files_touched,
        blockers=blockers,
        tools_used=tools_used,
        duration_ms=duration_ms,
    )


def _last_response_text(events: list[AuditEvent]) -> str:
    """The final assistant text, if any llm_call/model_call_end event carries
    one — mirrors mission_loop_service._run_response's field probing, kept
    local to avoid a cross-module dependency for one helper."""
    for event in reversed(events):
        if event.event_type not in ("llm_call", "model_call_end"):
            continue
        data = _parse_data(event)
        for key in ("response", "text", "content", "delta"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val
    return ""


def _foundation_synthesize(
    events: list[AuditEvent], deterministic: RunSummary
) -> dict[str, Any]:
    """Default synthesizer: a cheap auxiliary-model call for goal/outcome/
    key_decisions/next_actions, fed the deterministic facts (not raw events)
    to keep the call small. Fail-open on any error — an absent foundation, an
    unconfigured provider, or a network error all degrade to the
    deterministic-only summary rather than blocking complete_run()."""
    try:
        from atlas_runtime.subagent_service import _foundation_on_path  # noqa: PLC0415

        if not _foundation_on_path():
            return {}
        from agent.auxiliary_client import (  # type: ignore # noqa: PLC0415
            get_auxiliary_extra_body,
            resolve_provider_client,
        )
        from atlas_runtime import config_service  # noqa: PLC0415

        resolved = config_service.resolve_provider()
        client, model = resolve_provider_client(
            resolved.get("provider") or "auto",
            model=resolved.get("model") or None,
            explicit_base_url=resolved.get("base_url") or None,
            explicit_api_key=resolved.get("api_key") or None,
            main_runtime=resolved,
        )
        if client is None or not model:
            return {}
        facts = {
            "completed_actions": deterministic.completed_actions,
            "tools_used": deterministic.tools_used,
            "files_touched": deterministic.files_touched,
            "blockers": deterministic.blockers,
            "final_response": _last_response_text(events)[:4000],
        }
        prompt = (
            "Summarize this completed agent run as compact JSON with EXACTLY "
            'these keys: "goal" (one sentence, what the run was trying to '
            'accomplish), "outcome" (one sentence, succeeded/failed + why), '
            '"key_decisions" (list of short strings, notable technical choices),'
            ' "next_actions" (list of short strings, what remains — empty if '
            "nothing does). Facts extracted from the run:\n"
            + json.dumps(facts, ensure_ascii=False)
        )
        result = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You write terse structured run summaries. Reply with JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=500,
            timeout=20,
            extra_body=get_auxiliary_extra_body() or None,
        )
        raw = result.choices[0].message.content or ""
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception as exc:  # noqa: BLE001 — never block run completion
        logger.debug("run summary auxiliary synthesis failed: %s", exc)
        return {}


def generate_run_summary(
    events: list[AuditEvent],
    *,
    synthesize: Synthesizer | None = None,
) -> RunSummary:
    """Build a structured RunSummary from one run's audit_events.

    Deterministic fields (completed_actions/files_touched/blockers/
    tools_used/duration_ms/an outcome fallback) are always populated from
    `events` alone. goal/outcome/key_decisions/next_actions are then filled
    in by `synthesize` (defaults to `_foundation_synthesize`, injectable for
    tests) — its output is layered on top of, never replacing, the
    deterministic outcome fallback when synthesis yields nothing.
    """
    deterministic = _extract_deterministic(events)
    synth = synthesize or _foundation_synthesize
    try:
        narrative = synth(events, deterministic) or {}
    except Exception as exc:  # noqa: BLE001 — never block run completion
        logger.debug("run summary synthesis raised: %s", exc)
        narrative = {}

    goal = str(narrative.get("goal") or "").strip()
    outcome = str(narrative.get("outcome") or "").strip() or deterministic.outcome
    key_decisions = [str(x) for x in (narrative.get("key_decisions") or [])]
    next_actions = [str(x) for x in (narrative.get("next_actions") or [])]

    return dataclasses.replace(
        deterministic,
        goal=goal,
        outcome=outcome,
        key_decisions=key_decisions,
        next_actions=next_actions,
    )
