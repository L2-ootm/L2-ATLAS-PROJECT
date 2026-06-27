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

from atlas_core.schemas.agent_contract import ModelIdentity, SurfaceIdentity, WorkspaceIdentity

from atlas_runtime import agent_contract_service
from atlas_runtime import surface_session_service
from atlas_runtime.tool_catalog import build_shipped_catalog
from atlas_runtime.tui import capabilities as capabilities_module
from atlas_runtime.tui import header as header_module
from atlas_runtime.tui import session_select as session_select_module
from atlas_runtime.tui import transcript as transcript_module

_POLL_INTERVAL_SECONDS = 0.5

# Placeholder model identity for the not-yet-wired agent path (see
# `_submit_to_agent`). Mirrors `agent_contract_service.prepare_run_contract`'s
# own placeholder convention ("resolved-at-execution") rather than inventing a
# new sentinel — real model resolution is wired when the agent-invocation path
# lands (out of this plan's scope, TUI-04/TUI-08 backbone only).
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


async def _submit_to_agent(line: str) -> None:
    """Extension point for the agent-invocation path — NOT wired in this plan.

    The composer's non-slash-command input lands here. Actually invoking the
    agent runtime (model call, tool loop, transcript event emission) is wired
    in a later phase/plan; this stub exists so that path is a clearly-named,
    visibly-not-yet-implemented no-op rather than a silently dropped line of
    operator input (T-10.6-21, disposition "accept" — no agent invocation, no
    secret/credential path exists yet to leak).
    """
    del line  # not yet wired — see docstring


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


def _render_header_for_live(console: Console, snapshot: dict) -> object:
    """Adapt `header.render_status_header`'s print-side-effect contract to a renderable.

    `tui.header.render_status_header(console, snapshot)` prints directly and
    returns `None` (its committed Wave-1 contract) rather than returning a
    `RenderableType` — so it cannot be passed straight to `Live.update`, which
    requires a renderable. Capturing the same call's console output via
    `console.capture()` and replaying it as `Text.from_ansi(...)` preserves
    `header.py` as the single source of header-formatting logic (never
    duplicated here) while satisfying `Live.update`'s renderable contract.
    """
    from rich.text import Text

    with console.capture() as capture:
        header_module.render_status_header(console, snapshot)
    return Text.from_ansi(capture.get())


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
    `prompt_toolkit` composer and the background transcript-poll task. Rich
    `Live` is constructed exactly once, scoped exclusively to the status
    header (`tui.header.render_status_header`) — `console.print(...)` under
    `patch_stdout` carries every other line (transcript events, command
    output), never a second `Live` region (RESEARCH Pattern 2 / Pitfall 1).

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

    caps = capabilities_module.probe_capabilities()
    console = Console()

    async def _poll_loop(stop_event: asyncio.Event) -> None:
        """Background transcript-poll task: print unseen events, never via `Live`."""
        last_seq = 0
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

        async with patch_stdout():
            with Live(console=console, refresh_per_second=4, transient=False) as live:
                snapshot = {
                    "model_id": _PLACEHOLDER_MODEL.model_id,
                    "model_provider": _PLACEHOLDER_MODEL.provider,
                    "permission_mode": session.permission_mode,
                    "focus_title": None,
                    "state": session.state,
                }
                live.update(_render_header_for_live(console, snapshot))

                ptk_session: PromptSession = PromptSession(multiline=True)
                stop_event = asyncio.Event()
                poll_task = asyncio.create_task(_poll_loop(stop_event))
                try:
                    while True:
                        line = await ptk_session.prompt_async("> ")
                        if line.startswith("/"):
                            # Slash-command dispatch lands in a later plan
                            # (10.6-07's command_dispatch.dispatch_command);
                            # no dispatcher exists yet in this plan's scope.
                            console.print(f"(unrecognized command: {line})")
                        else:
                            await _submit_to_agent(line)
                except (EOFError, KeyboardInterrupt):
                    handle_cancel(eff_conn, eff_lock, session_id=session.id)
                    stop_event.set()
                finally:
                    poll_task.cancel()
                    await asyncio.gather(poll_task, return_exceptions=True)

    asyncio.run(_main_loop())


__all__ = ["handle_cancel", "run_workbench"]
