"""Command palette dispatch: core-first, deferred-with-seams (TUI-07).

`dispatch_command` is the SOLE entry point the composer's slash-command input
funnels through. It never raises — every branch (core handler success, core
handler typed-error, deferred extension seam, unknown command, or a handler
bug) returns a `CommandResult` the caller renders. This is the structural
guarantee required by T-10.6-22 (a single malformed command must never kill
the TUI's asyncio main loop).

Core groups (`project`, `focus`, `mission`, `config`, `permission`) are thin
wrappers that delegate immediately to the existing service layer — no new
business logic lives here. Deferred groups (`wiki`, `subagent`, `context`)
are registered through the SAME `_register` path with `deferred=True`, so a
follow-up phase can swap in a real implementation by re-registering the name
without touching `dispatch_command` itself (CONTEXT's "clean extension seam,
not an opaque error stub" requirement).

`dispatch_command` takes the active surface session's id as a required
keyword-only `surface_session_id` and threads it to every handler (CR-02/CR-03
fix) — the `/permission` group's `list_actionable`/`resolve_approval_choice`
calls are scoped to a REAL session id, never the empty-string placeholder this
module previously hard-coded.
"""
from __future__ import annotations

import logging
import shlex
import sqlite3
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from atlas_runtime import config_service
from atlas_runtime import focus_service
from atlas_runtime import permission_broker
from atlas_runtime import project_service
from atlas_runtime.tui import permission_ui

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommandResult:
    """Renderable outcome of a dispatched command.

    `is_error` mirrors `not ok` under a name the test suite's error-card
    assertions expect (`getattr(result, "is_error", True)`); both attributes
    are kept in sync so callers can use either vocabulary.
    """

    ok: bool
    text: str
    deferred: bool = False

    @property
    def is_error(self) -> bool:
        return not self.ok


Handler = Callable[[sqlite3.Connection, List[str], str], CommandResult]

COMMAND_REGISTRY: Dict[str, "_RegistryEntry"] = {}


@dataclass(frozen=True)
class _RegistryEntry:
    handler: Handler
    deferred: bool = False


def _register(name: str, handler: Handler, *, deferred: bool = False) -> None:
    """Register (or replace) a command name's handler.

    Every entry — core or deferred — goes through this single path. A
    follow-up phase implementing a deferred group calls `_register("wiki",
    real_handler)` to replace the seam below; `dispatch_command` itself never
    changes.
    """
    COMMAND_REGISTRY[name] = _RegistryEntry(handler=handler, deferred=deferred)


# ---------------------------------------------------------------------------
# Core handlers: thin wrappers over existing services, no added logic.
# ---------------------------------------------------------------------------


def _handle_project(
    conn: sqlite3.Connection, args: List[str], surface_session_id: str
) -> CommandResult:
    del surface_session_id  # project commands are not session-scoped
    sub = args[0] if args else "list"
    try:
        if sub == "list":
            projects = project_service.list_projects(conn)
            if not projects:
                return CommandResult(ok=True, text="no projects registered")
            lines = [f"{p.id}  {p.name}  {p.root_path}" for p in projects]
            return CommandResult(ok=True, text="\n".join(lines))
        if sub == "show" and len(args) > 1:
            project = project_service.get_project(conn, args[1])
            if project is None:
                return CommandResult(ok=False, text=f"no project found for id: {args[1]}")
            return CommandResult(ok=True, text=f"{project.id}  {project.name}  {project.root_path}")
        return CommandResult(ok=False, text=f"unknown project subcommand: {sub}")
    except project_service.ProjectError as exc:
        return CommandResult(ok=False, text=str(exc))


def _handle_focus(
    conn: sqlite3.Connection, args: List[str], surface_session_id: str
) -> CommandResult:
    del surface_session_id  # focus commands are not session-scoped
    sub = args[0] if args else "show"
    try:
        if sub == "show":
            focus = focus_service.get_current_focus(conn)
            if focus is None:
                return CommandResult(ok=True, text="no current focus set")
            return CommandResult(ok=True, text=f"{focus.id}  {focus.title}")
        if sub == "list":
            items = focus_service.list_focus(conn)
            if not items:
                return CommandResult(ok=True, text="no focus entries")
            lines = [f"{f.id}  {f.title}" for f in items]
            return CommandResult(ok=True, text="\n".join(lines))
        return CommandResult(ok=False, text=f"unknown focus subcommand: {sub}")
    except focus_service.FocusError as exc:
        return CommandResult(ok=False, text=str(exc))


def _handle_config(
    conn: sqlite3.Connection, args: List[str], surface_session_id: str
) -> CommandResult:
    del surface_session_id  # config commands are not session-scoped
    if not args:
        return CommandResult(ok=False, text="usage: config get <key> | config set <key> <value>")
    sub = args[0]
    if sub == "get" and len(args) > 1:
        key = args[1]
        try:
            value = config_service.get_value(conn, key)
        except KeyError:
            return CommandResult(ok=False, text=f"unknown key: {key}")
        return CommandResult(ok=True, text=f"{key} = {value}")
    if sub == "set" and len(args) > 2:
        key, value = args[1], args[2]
        try:
            config_service.set_value(conn, key, value)
        except KeyError:
            return CommandResult(ok=False, text=f"unknown key: {key}")
        return CommandResult(ok=True, text=f"{key} set to {value}")
    return CommandResult(ok=False, text=f"unknown config subcommand: {sub}")


def _handle_permission(
    conn: sqlite3.Connection, args: List[str], surface_session_id: str
) -> CommandResult:
    if not args:
        return CommandResult(ok=False, text="usage: permission list | permission decide <id> <choice>")
    sub = args[0]
    if sub == "list":
        # surface_session_id is the REAL active session's id, threaded through
        # dispatch_command by the app.py composer call site (CR-02/CR-03 fix).
        # list_actionable's strict-scope filter returns only THIS session's
        # actionable approvals — never another session's rows.
        approvals = permission_broker.list_actionable(
            conn, surface_session_id=surface_session_id
        )
        if not approvals:
            return CommandResult(ok=True, text="no actionable approvals")
        lines = [f"{a.id}  {a.tool_name}  {a.risk_level}" for a in approvals]
        return CommandResult(ok=True, text="\n".join(lines))
    if sub == "decide" and len(args) > 2:
        approval_id, choice = args[1], args[2]
        try:
            result = permission_ui.resolve_approval_choice(
                conn,
                approval_id=approval_id,
                surface_session_id=surface_session_id,
                choice=choice,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a typed CommandResult
            return CommandResult(ok=False, text=f"decision failed: {exc}")
        if result is None:
            return CommandResult(ok=True, text="cancelled")
        return CommandResult(ok=True, text=f"{approval_id} -> {result.status}")
    return CommandResult(ok=False, text=f"unknown permission subcommand: {sub}")


# ---------------------------------------------------------------------------
# Deferred extension seams (wiki/Brain, subagents, context) — explicit
# "not yet available" markers, never opaque errors or fake success.
# ---------------------------------------------------------------------------


def _make_deferred_handler(name: str) -> Handler:
    def _handler(
        conn: sqlite3.Connection, args: List[str], surface_session_id: str
    ) -> CommandResult:
        del conn, args, surface_session_id
        return CommandResult(
            ok=False,
            deferred=True,
            text=(
                f"'{name}' commands are deferred to a follow-up phase "
                "(TUI-07 core-first scope, see 10.6-CONTEXT.md); not yet "
                "available in this workbench."
            ),
        )

    return _handler


_register("project", _handle_project)
_register("focus", _handle_focus)
_register("config", _handle_config)
_register("permission", _handle_permission)

# WR-02: "mission" is registered as a deferred extension seam, not a working
# "core" handler — its only previous subcommands (list/show) unconditionally
# returned failure, presenting a delivered-but-broken feature as core scope.
# A follow-up phase implementing real mission list/show against
# mission_service replaces this via _register("mission", real_handler).
for _deferred_name in ("mission", "wiki", "subagent", "context"):
    _register(_deferred_name, _make_deferred_handler(_deferred_name), deferred=True)


def _parse(command_text: str) -> tuple[Optional[str], List[str]]:
    """Split a slash-command string into `(command, args)`.

    Accepts both `"/project list"` (composer vocabulary, leading slash
    stripped) and a bare `"project list"`. Returns `(None, [])` for an empty
    or whitespace-only input.
    """
    stripped = command_text.strip()
    if not stripped:
        return None, []
    if stripped.startswith("/"):
        stripped = stripped[1:]
    try:
        parts = shlex.split(stripped)
    except ValueError:
        parts = stripped.split()
    if not parts:
        return None, []
    return parts[0], parts[1:]


def dispatch_command(
    conn: sqlite3.Connection, command_text: str, *, surface_session_id: str
) -> CommandResult:
    """Parse and dispatch a composer slash-command string.

    `surface_session_id` is the active workbench session's id (CR-02/CR-03
    fix) — every handler receives it as its third positional argument so
    session-scoped groups (`permission`) can filter strictly to THIS
    session's rows rather than an empty-string placeholder that could never
    match a real row.

    Never raises: an unknown command name returns an error-card-shaped
    `CommandResult` (never an exception); any exception raised by a
    registered handler itself is caught by the outer guard below and
    converted into a `CommandResult` too, so a single malformed command can
    never crash the TUI's asyncio main loop (T-10.6-22 — the one deliberate
    broad `except Exception` in this module).
    """
    command, args = _parse(command_text)
    if command is None:
        return CommandResult(ok=False, text="empty command")

    entry = COMMAND_REGISTRY.get(command)
    if entry is None:
        return CommandResult(ok=False, text=f"unknown command: {command}")

    try:
        return entry.handler(conn, args, surface_session_id)
    except Exception as exc:  # noqa: BLE001 - last line of defense, see T-10.6-22
        logger.exception("tui command dispatch failed: %s", command)
        return CommandResult(ok=False, text=f"command '{command}' failed: {exc}")


__all__ = ["CommandResult", "COMMAND_REGISTRY", "dispatch_command"]
