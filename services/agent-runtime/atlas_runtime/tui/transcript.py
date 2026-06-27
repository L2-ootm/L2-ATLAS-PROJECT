"""Append-only transcript polling + per-EventKind rendering (TUI-04, TUI-05).

Two pure-ish layers live in this single module:

- `poll_and_render`: a gap-free poll/replay primitive. It reads the durable
  `surface_events` table (the persisted projection cache written by the
  surface-session run loop) for one session, and returns only the events with
  `seq > last_seq`, in ascending seq order — via `surface_events.replay_since`,
  never by re-deriving ordering/gap-detection itself (RESEARCH Don't Hand-Roll).
  It performs zero Rich `Console`/`Live` calls; printing each returned event is
  the caller's responsibility (Wave 3's app.py background poll task).
- `render_event`: a per-`EventKind` dispatcher that turns one already-normalized,
  already-redacted `SurfaceEvent` (D-013) into a Rich renderable. It never
  re-parses `payload_json` to re-derive `kind`/ordering, and it never re-redacts
  or resolves secrets — payloads are rendered as-is.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Optional

from rich.box import ASCII
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.text import Text

from atlas_core.schemas.surface_session import SurfaceEvent

from atlas_runtime import surface_events as surface_events_module
from atlas_runtime.agents.base import RunOutcome
from atlas_runtime.tui.capabilities import Capabilities, probe_capabilities
from atlas_runtime.tui.theme import safe_style


def _events_for_session(conn: sqlite3.Connection, session_id: str) -> tuple[SurfaceEvent, ...]:
    """Read the persisted `surface_events` rows for one session, in seq order.

    This is the durable read-side counterpart to `surface_events.normalize_surface_events`:
    rows here are already-normalized SurfaceEvents (one row per projected event), so this
    function only re-hydrates them — it never re-derives `kind` or re-assigns `seq`.
    """
    cursor = conn.execute(
        "SELECT session_id, seq, kind, run_id, occurred_at, payload_json "
        "FROM surface_events WHERE session_id = ? ORDER BY seq ASC",
        (session_id,),
    )
    return tuple(
        SurfaceEvent(
            session_id=row[0],
            seq=row[1],
            kind=row[2],
            run_id=row[3],
            occurred_at=row[4],
            payload_json=row[5],
        )
        for row in cursor.fetchall()
    )


def poll_and_render(
    conn: sqlite3.Connection,
    console: Console,
    *,
    session_id: str,
    last_seq: int = 0,
    run_outcome: Optional[RunOutcome] = None,
) -> list[SurfaceEvent]:
    """Poll the per-session SurfaceEvent stream and return only the unseen tail.

    Pure data retrieval and gap-free slicing — never prints/clears via `console`
    (the parameter is accepted for call-site symmetry with the Wave 3 render loop
    but is not invoked here; callers print each returned event with `render_event`
    themselves). Returns a list ordered by ascending `seq`, all `seq > last_seq`.
    Delegates ordering/gap-detection to `surface_events.replay_since` (never
    re-derived here) and only adapts its tuple result to a list for callers.
    """
    del console  # accepted for signature symmetry; poll_and_render does no I/O on it
    events = _events_for_session(conn, session_id)
    return list(surface_events_module.replay_since(events, last_seq))


def _safe_payload(event: SurfaceEvent) -> dict:
    """Best-effort parse of `payload_json`; never raises on malformed input (T-10.6-08)."""
    try:
        parsed = json.loads(event.payload_json)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def render_event(
    event: SurfaceEvent, *, caps: Optional[Capabilities] = None
) -> RenderableType:
    """Render one SurfaceEvent into a Rich renderable, dispatched on `event.kind`.

    Trusts `event.kind`/`event.seq` as already-normalized (never re-parses
    `payload_json` to re-derive them). `payload_json` is parsed defensively
    (malformed input falls back to `{}` rather than raising). `caps` defaults
    to a fresh `probe_capabilities()` snapshot when not supplied so this
    function is usable standalone; pass an explicit `caps` to honor a specific
    terminal's no-color/ASCII-box capabilities.
    """
    caps = caps if caps is not None else probe_capabilities()
    payload = _safe_payload(event)
    box = ASCII if caps.box_style == "ascii" else None

    if event.kind == "text":
        body = payload.get("text") or payload.get("content") or "(empty text event)"
        return Text(str(body))

    if event.kind == "reasoning":
        body = payload.get("reasoning") or payload.get("text") or "(empty reasoning event)"
        return Text(str(body), style=safe_style("muted", caps))

    if event.kind == "tool_call":
        tool_name = payload.get("tool") or payload.get("name") or "unknown tool"
        args = payload.get("args") or payload.get("arguments") or {}
        panel_kwargs = {"title": f"tool_call: {tool_name}"}
        if box is not None:
            panel_kwargs["box"] = box
        return Panel(Text(str(args) or "(no args)"), **panel_kwargs)

    if event.kind == "tool_result":
        tool_name = payload.get("tool") or payload.get("name") or "unknown tool"
        success = bool(payload.get("success", True))
        summary = payload.get("summary") or payload.get("diff") or payload.get("result") or "(no result)"
        style = safe_style("success", caps) if success else safe_style("danger", caps)
        panel_kwargs = {"title": f"tool_result: {tool_name}"}
        if box is not None:
            panel_kwargs["box"] = box
        return Panel(Text(str(summary), style=style), **panel_kwargs)

    if event.kind == "task":
        name = payload.get("task") or payload.get("subagent") or payload.get("name") or "task"
        phase = payload.get("phase") or payload.get("status") or "update"
        return Text(f"task[{name}]: {phase}")

    if event.kind == "retry":
        attempt = payload.get("attempt") or payload.get("attempt_count") or "?"
        reason = payload.get("reason") or "retrying"
        return Text(f"retry (attempt {attempt}): {reason}", style=safe_style("warning", caps))

    if event.kind == "retrieval":
        source = payload.get("source") or payload.get("provenance") or "unknown source"
        summary = payload.get("summary") or payload.get("uri") or "(no summary)"
        panel_kwargs = {"title": f"retrieval: {source}"}
        if box is not None:
            panel_kwargs["box"] = box
        return Panel(Text(str(summary)), **panel_kwargs)

    if event.kind == "approval":
        decision = payload.get("decision") or payload.get("status") or "pending"
        actor = payload.get("actor") or payload.get("approver") or ""
        suffix = f" by {actor}" if actor else ""
        return Text(f"approval: {decision}{suffix}")

    if event.kind == "error":
        message = payload.get("message") or payload.get("error") or "(no error message)"
        return Text(str(message), style=safe_style("danger", caps))

    if event.kind == "completion":
        status = payload.get("status") or "unknown"
        summary = payload.get("summary") or ""
        suffix = f": {summary}" if summary else ""
        return Text(f"completion: {status}{suffix}", style=safe_style("primary", caps))

    raise ValueError(f"unrecognized SurfaceEvent.kind: {event.kind!r}")


__all__ = ["poll_and_render", "render_event"]
