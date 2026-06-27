"""Workspace picker: global vs registered Project selection + cwd resolution (TUI-02).

Resolution order: an explicit `project_id` or `use_global` flag resolves directly
via `workspace_service.resolve_workspace` with no interactive prompt attempted.
With neither flag and no TTY, fails closed immediately (never blocks on input).
With neither flag and a TTY, falls back to an interactive `prompt_toolkit` picker
over the registered projects (plus a literal global-workspace entry).
"""
from __future__ import annotations

import sqlite3
import sys
from typing import Optional

from atlas_runtime import project_service
from atlas_runtime import workspace_service


def _stdin_is_tty() -> bool:
    """Whether stdin is an interactive TTY. Patched directly in tests."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def select_workspace(
    conn: sqlite3.Connection,
    *,
    project_id: Optional[str] = None,
    use_global: bool = False,
    interactive: Optional[bool] = None,
) -> dict:
    """Resolve the operator's workspace selection to a `resolve_workspace`-shaped dict.

    - `project_id` given -> resolves directly as kind="project", no picker.
    - `use_global=True` -> resolves directly as kind="global", no picker.
    - Neither given -> requires an interactive TTY (or explicit `interactive=True`);
      raises `RuntimeError` immediately if non-interactive rather than blocking on
      input.
    """
    if project_id is not None:
        result = workspace_service.resolve_workspace(
            conn, kind="project", project_id=project_id
        )
        return _as_selection_dict(result, kind="project", project_id=project_id)

    if use_global:
        result = workspace_service.resolve_workspace(
            conn, kind="global", use_global=True
        )
        return _as_selection_dict(result, kind="global", project_id=None)

    is_interactive = interactive if interactive is not None else _stdin_is_tty()
    if not is_interactive:
        raise RuntimeError(
            "no workspace specified: pass --project <id> or --global, "
            "or run interactively"
        )

    return _prompt_for_workspace(conn)


def _as_selection_dict(
    resolved: object, *, kind: str, project_id: Optional[str]
) -> dict:
    """Normalize a `resolve_workspace` return value to the picker's dict shape.

    Production `workspace_service.resolve_workspace` returns a plain root-path
    `str`; tests monkeypatch it to return an already-shaped dict (`kind`,
    `project_id`, `root_path`) for direct assertion. Pass dicts through
    unchanged, wrap bare strings into the same shape.
    """
    if isinstance(resolved, dict):
        return resolved
    return {"kind": kind, "project_id": project_id, "root_path": resolved}


def _prompt_for_workspace(conn: sqlite3.Connection) -> dict:
    """Interactive global-or-Project picker over `prompt_toolkit`.

    Populates options from `project_service.list_projects(conn)` alongside a
    literal "global workspace" entry, then resolves the chosen option via the
    same `workspace_service.resolve_workspace` call used by the flag paths.
    """
    from prompt_toolkit.shortcuts import radiolist_dialog

    projects = project_service.list_projects(conn)
    values: list[tuple[Optional[str], str]] = [(None, "global workspace")]
    values.extend((project.id, f"{project.name} ({project.root_path})") for project in projects)

    selected_project_id = radiolist_dialog(
        title="ATLAS workspace",
        text="Select a workspace for this session:",
        values=values,
    ).run()

    if selected_project_id is None:
        result = workspace_service.resolve_workspace(
            conn, kind="global", use_global=True
        )
        return _as_selection_dict(result, kind="global", project_id=None)
    result = workspace_service.resolve_workspace(
        conn, kind="project", project_id=selected_project_id
    )
    return _as_selection_dict(result, kind="project", project_id=selected_project_id)


__all__ = ["select_workspace"]
