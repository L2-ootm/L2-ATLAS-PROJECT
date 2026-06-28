"""Single-asyncio-loop ATLAS terminal workbench (TUI-04, TUI-08).

This module is the structural backbone CONTEXT.md/RESEARCH.md mandate: ONE
asyncio event loop owns both the `prompt_toolkit` composer and the background
event-poll task. The status header is printed ONCE as a static line above the
composer; Rich `Live` is deliberately NOT used, because a timer-repainting
`Live` region cannot co-own the terminal with `prompt_toolkit`'s
`patch_stdout` + `prompt_async` without flooding the screen and leaking raw
cursor/erase escape codes (RESEARCH Pitfall 1). All header and
transcript/event content is printed via plain `console.print(...)` under
`patch_stdout`.

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
from typing import Callable, Optional

from rich.console import Console

from atlas_core.schemas.agent_contract import ModelIdentity, SurfaceIdentity, WorkspaceIdentity

from atlas_runtime import agent_contract_service
from atlas_runtime import mission_service
from atlas_runtime import surface_session_service
from atlas_runtime.run_executor import start_and_execute_async
from atlas_runtime.tool_catalog import build_shipped_catalog
from atlas_runtime.tui import capabilities as capabilities_module
from atlas_runtime.tui import command_dispatch as command_dispatch_module
from atlas_runtime.tui import header as header_module
from atlas_runtime.tui import session_select as session_select_module
from atlas_runtime.tui import transcript as transcript_module

_POLL_INTERVAL_SECONDS = 0.5

# Placeholder model identity shown in the status header at session-creation
# time, before any run has resolved a real provider/model. Mirrors
# `agent_contract_service.prepare_run_contract`'s own placeholder convention
# ("resolved-at-execution") rather than inventing a new sentinel — the REAL
# model is resolved per-run by NativeAtlasAgent._resolve_provider (ATLAS
# config + active Focus), independent of this header-only placeholder.
_PLACEHOLDER_MODEL = ModelIdentity(provider="resolved-at-execution", model_id="resolved-at-execution")


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


def _submit_to_agent(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    session_id: str,
    line: str,
    start_and_execute: Callable[..., object] = start_and_execute_async,
) -> None:
    """Submit one composer line as a mission run for the active session.

    Creates a fresh `pending` Mission (one per submitted line — `run_service`
    requires a pending mission to start a run), then drives it via
    `run_executor.start_and_execute_async` on a background daemon thread so
    the composer prompt is never blocked. The run is created with
    `session_id=session_id` so every AuditEvent it emits is joined back to
    THIS surface session by `audit_service.get_events_for_session` — closing
    the session -> run -> audit_events -> transcript loop CR-01 depends on.

    Defaults to the "native" AgentRuntime (`atlas_runtime.agents.native`),
    which never requires `claude_agent_sdk` — with no provider configured it
    falls back to a deterministic, clearly-labeled mock response rather than
    silently no-op'ing (the existing honest-failure contract). `start_and_execute`
    is injectable so tests can pass a stub/mock executor instead of spawning a
    real background thread (unit-testable without any live agent runtime).

    A blank/whitespace-only line is a no-op (stray Enter press) — no mission,
    no run, nothing submitted.
    """
    if not line.strip():
        return
    mission = mission_service.create_mission(
        conn, lock, title=line[:120], intent=line,
    )
    start_and_execute(
        conn, lock, mission_id=mission.id, prompt=line, session_id=session_id,
    )


def _resolve_conn_and_lock(
    conn: Optional[sqlite3.Connection], lock: Optional[threading.Lock]
) -> tuple[sqlite3.Connection, threading.Lock]:
    """Resolve `conn`/`lock` to real values via `cli.main`'s own factories.

    Mirrors every other command's DB-access pattern exactly (`cli/main.py`'s
    `_get_connection()`/`_get_lock()`) rather than inventing a second
    connection/lock source. Imported lazily to avoid a module-load-time
    circular import between `cli.main` and `tui.app` (Wave 4 wires this
    module INTO `cli.main`, not the other way around).
    """
    from atlas_runtime.cli import main as cli_main

    eff_conn = conn if conn is not None else cli_main._get_connection()
    eff_lock = lock if lock is not None else cli_main._get_lock()
    return eff_conn, eff_lock


def run_workbench(
    *,
    project: Optional[str] = None,
    global_: bool = False,
    conn: Optional[sqlite3.Connection] = None,
    lock: Optional[threading.Lock] = None,
) -> None:
    """Single-asyncio-loop ATLAS terminal workbench entrypoint (TUI-04).

    Resolves the workspace, creates a `starting` surface session, probes
    terminal capabilities, then runs ONE `asyncio.run` call that owns both the
    `prompt_toolkit` composer and the background transcript-poll task. The
    status header (`tui.header.render_status_header`) is printed once as a
    static line; every line — header, transcript events, command output — goes
    through `console.print(...)` under `patch_stdout`, never a Rich `Live`
    region (RESEARCH Pattern 2 / Pitfall 1).

    Ctrl-C / EOF on the composer prompt calls `handle_cancel` for the
    session-state unwind, then unconditionally cancels-and-awaits the poll
    task in a `finally` block BEFORE the `patch_stdout` context exits
    (RESEARCH Pitfall 4) — the poll task never outlives the loop.
    """
    eff_conn, eff_lock = _resolve_conn_and_lock(conn, lock)

    selection = session_select_module.select_workspace(
        eff_conn, project_id=project, use_global=global_
    )
    workspace = WorkspaceIdentity(
        kind=selection["kind"],
        root=selection["root_path"],
        project_id=selection.get("project_id"),
    )

    catalog = build_shipped_catalog()
    session = surface_session_service.create_session(
        eff_conn,
        eff_lock,
        surface=SurfaceIdentity(kind="tui", session_id=str(id(eff_conn))),
        workspace=workspace,
        agent="native",
        model=_PLACEHOLDER_MODEL,
        permission_mode="ask",
        prompt_version=agent_contract_service.PROMPT_VERSION,
        tool_catalog_version=catalog.catalog_version,
        context_policy_version=agent_contract_service.CONTEXT_POLICY_VERSION,
    )
    # A session is created in 'starting'; the composer loop only begins once
    # the workbench is actually ready to accept input, so transition to
    # 'active' here (Rule 1 fix — without this, handle_cancel's Ctrl-C/EOF
    # unwind always raised ValueError: 'starting' has no outgoing edge to
    # 'cancelling', _ALLOWED_FROM only permits that from 'active'/'suspended').
    surface_session_service.transition_session(eff_conn, eff_lock, session.id, "active")

    caps = capabilities_module.probe_capabilities()
    console = Console()

    async def _poll_loop(stop_event: asyncio.Event) -> None:
        """Background transcript-poll task: print unseen events, never via `Live`."""
        last_seq = -1  # transcript.poll_and_render's "nothing seen yet" sentinel
        while not stop_event.is_set():
            events = transcript_module.poll_and_render(
                eff_conn, console, session_id=session.id, last_seq=last_seq
            )
            for event in events:
                console.print(transcript_module.render_event(event, caps=caps))
            if events:
                last_seq = max(last_seq, *(event.seq for event in events))
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    async def _main_loop() -> None:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.patch_stdout import patch_stdout

        snapshot = {
            "model_id": _PLACEHOLDER_MODEL.model_id,
            "model_provider": _PLACEHOLDER_MODEL.provider,
            "permission_mode": session.permission_mode,
            "focus_title": None,
            # "active", not the stale frozen session.state ("starting")
            # captured before the transition_session call above.
            "state": "active",
        }

        with patch_stdout():
            # One-shot static status header above the composer. Deliberately NOT
            # wrapped in a Rich `Live` region: `Live` repaints on a timer and,
            # co-owning the terminal with prompt_toolkit's `patch_stdout` +
            # `prompt_async`, floods the screen with repeated headers and leaks
            # raw cursor/erase escape codes (RESEARCH Pitfall 1). The snapshot is
            # fixed for the session's lifetime, so a single print suffices;
            # transcript events stream below via `console.print` under the same
            # `patch_stdout`.
            header_module.render_status_header(console, snapshot)

            ptk_session: PromptSession = PromptSession(multiline=True)
            stop_event = asyncio.Event()
            poll_task = asyncio.create_task(_poll_loop(stop_event))
            try:
                while True:
                    line = await ptk_session.prompt_async("> ")
                    if line.startswith("/"):
                        result = command_dispatch_module.dispatch_command(
                            eff_conn, line, surface_session_id=session.id
                        )
                        console.print(result.text)
                    else:
                        _submit_to_agent(
                            eff_conn, eff_lock, session_id=session.id, line=line
                        )
            except (EOFError, KeyboardInterrupt):
                handle_cancel(eff_conn, eff_lock, session_id=session.id)
                stop_event.set()
            finally:
                poll_task.cancel()
                await asyncio.gather(poll_task, return_exceptions=True)

    asyncio.run(_main_loop())


__all__ = ["handle_cancel", "run_workbench"]

