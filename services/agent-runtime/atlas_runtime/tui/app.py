"""Single-asyncio-loop ATLAS terminal workbench (TUI-04, TUI-08).

This module is the structural backbone CONTEXT.md/RESEARCH.md mandate: ONE
asyncio event loop owns both the `prompt_toolkit` composer and the background
event-poll task. Rich `Live` is scoped EXCLUSIVELY to the status header line —
it never co-owns the terminal with `prompt_toolkit`'s `patch_stdout` (RESEARCH
Pitfall 1). All transcript/event content is printed via plain
`console.print(...)` under `patch_stdout`, never through a second `Live`
region.

`handle_cancel` is the Ctrl-C / cancel unwind (TUI-08): it drives the owning
session toward `"cancelling"` via `surface_session_service.transition_session`
and lets `ValueError` propagate un-swallowed if the session is not in a state
from which `"cancelling"` is reachable (fail-closed — a stuck/terminal session
must surface as an error, never silently no-op). It intentionally does not
call `run_service.cancel_run` itself: the existing `cancelling` transition
pathway already drives downstream run/tool cancellation (see
`surface_session_service.reconcile_orphans`'s use of `run_service.cancel_run`);
re-deriving that cascade here would duplicate logic owned by the session/run
services from Phase 10.2-10.3.
"""
from __future__ import annotations

import asyncio
import sqlite3
import threading
from typing import Optional

from rich.console import Console
from rich.live import Live

from atlas_runtime import surface_session_service
from atlas_runtime.tui import capabilities as capabilities_module
from atlas_runtime.tui import header as header_module
from atlas_runtime.tui import session_select as session_select_module
from atlas_runtime.tui import transcript as transcript_module

_POLL_INTERVAL_SECONDS = 0.5


def handle_cancel(
    conn: sqlite3.Connection,
    lock: Optional[threading.Lock] = None,
    *,
    session_id: str,
) -> None:
    """Ctrl-C / EOF unwind: drive the owning session to `"cancelling"` (TUI-08).

    Performs exactly one session-state-mutating call —
    `surface_session_service.transition_session(conn, lock, session_id,
    "cancelling")` — and does not wrap it in a try/except that would swallow
    `ValueError`. If the session is already in a terminal state (or otherwise
    cannot legally reach `"cancelling"`), `transition_session`'s own
    `_ALLOWED_FROM` guard raises `ValueError`; that propagates unmodified so
    the caller's outer handler can render an error card instead of silently
    no-op'ing on a stuck session.
    """
    eff_lock = lock if lock is not None else threading.Lock()
    surface_session_service.transition_session(conn, eff_lock, session_id, "cancelling")


__all__ = ["handle_cancel"]
