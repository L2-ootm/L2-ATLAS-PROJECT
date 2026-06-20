"""ATLAS focus service — the Command Center's Current Focus (CC-1, WP-2).

A Focus is the operator's active working context: title, framework, priorities,
drivers, optionally bound to a project. A single Focus is 'active' at a time (the
Current Focus); promoting a new one archives the prior. This entity feeds the
Intelligence-Layer context-assembly step (WP-3) — the live state an agent run
inherits.

Conventions follow project_service.py:
  - Pydantic-first write guard (construct + validate before any SQL).
  - All mutations go through the service layer with lock+conn atomic blocks.
  - priorities/drivers are JSON-array strings on the model; this service
    encodes/decodes them at the boundary (helpers below). DDL in 0009_focus.sql.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading
from typing import Optional, Sequence

from atlas_core.schemas.core import Focus

_UNSET = object()


class FocusError(ValueError):
    """Raised for invalid focus inputs (empty title, unknown id)."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def encode_list(items: Optional[Sequence[str]]) -> str:
    """JSON-encode a list of strings for the priorities/drivers columns."""
    return json.dumps([str(i) for i in (items or [])])


def decode_list(raw: str) -> list[str]:
    """Decode a priorities/drivers JSON-array string back to a list."""
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(i) for i in value] if isinstance(value, list) else []


def _row_to_focus(cursor: sqlite3.Cursor) -> Optional[Focus]:
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    return Focus(**dict(zip(cols, row))) if row is not None else None


def create_focus(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    title: str,
    framework: str = "",
    priorities: Optional[Sequence[str]] = None,
    drivers: Optional[Sequence[str]] = None,
    project_id: Optional[str] = None,
    make_current: bool = True,
) -> Focus:
    """Create a Focus. If `make_current` (default), archive any other active
    Focus first so there is exactly one Current Focus."""
    if not title or not title.strip():
        raise FocusError("title must not be empty")
    focus = Focus(
        title=title,
        framework=framework,
        priorities=encode_list(priorities),
        drivers=encode_list(drivers),
        project_id=project_id,
        status="active" if make_current else "archived",
    )
    row = focus.model_dump()
    with lock:
        with conn:
            if make_current:
                conn.execute(
                    "UPDATE focus SET status='archived', updated_at=? WHERE status='active'",
                    (_now(),),
                )
            conn.execute(
                "INSERT INTO focus"
                "(id, title, framework, priorities, drivers, project_id, status, created_at, updated_at) "
                "VALUES (:id, :title, :framework, :priorities, :drivers, :project_id, :status, :created_at, :updated_at)",
                row,
            )
    return focus


def get_focus(conn: sqlite3.Connection, focus_id: str) -> Optional[Focus]:
    """Return the Focus for the given id, or None."""
    return _row_to_focus(conn.execute("SELECT * FROM focus WHERE id=?", (focus_id,)))


def get_current_focus(conn: sqlite3.Connection) -> Optional[Focus]:
    """Return the single active Focus (newest if several), or None."""
    return _row_to_focus(
        conn.execute(
            "SELECT * FROM focus WHERE status='active' "
            "ORDER BY updated_at DESC, created_at DESC LIMIT 1"
        )
    )


def list_focus(conn: sqlite3.Connection, *, include_archived: bool = False) -> list[Focus]:
    """List Focus rows (active only by default) newest-first."""
    sql = "SELECT * FROM focus"
    if not include_archived:
        sql += " WHERE status='active'"
    sql += " ORDER BY created_at DESC"
    cursor = conn.execute(sql)
    cols = [d[0] for d in cursor.description]
    return [Focus(**dict(zip(cols, row))) for row in cursor]


def update_focus(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    focus_id: str,
    *,
    title: Optional[str] = None,
    framework: Optional[str] = None,
    priorities: object = _UNSET,
    drivers: object = _UNSET,
    project_id: object = _UNSET,
) -> Focus:
    """Patch the provided fields of a Focus. Unset args are left unchanged;
    pass `project_id=None` explicitly to clear it. Raises FocusError if unknown."""
    sets: list[str] = []
    params: list[object] = []
    if title is not None:
        if not title.strip():
            raise FocusError("title must not be empty")
        sets.append("title=?")
        params.append(title.strip())
    if framework is not None:
        sets.append("framework=?")
        params.append(framework)
    if priorities is not _UNSET:
        sets.append("priorities=?")
        params.append(encode_list(priorities))  # type: ignore[arg-type]
    if drivers is not _UNSET:
        sets.append("drivers=?")
        params.append(encode_list(drivers))  # type: ignore[arg-type]
    if project_id is not _UNSET:
        sets.append("project_id=?")
        params.append(project_id)

    if not sets:
        existing = get_focus(conn, focus_id)
        if existing is None:
            raise FocusError(f"focus {focus_id!r} not found")
        return existing

    sets.append("updated_at=?")
    params.append(_now())
    params.append(focus_id)
    with lock:
        with conn:
            cursor = conn.execute(
                f"UPDATE focus SET {', '.join(sets)} WHERE id=?", params
            )
            if cursor.rowcount == 0:
                raise FocusError(f"focus {focus_id!r} not found")
    updated = get_focus(conn, focus_id)
    assert updated is not None  # row existed (rowcount != 0)
    return updated


def archive_focus(conn: sqlite3.Connection, lock: threading.Lock, focus_id: str) -> None:
    """Archive a Focus (status -> archived). Raises FocusError if unknown."""
    with lock:
        with conn:
            cursor = conn.execute(
                "UPDATE focus SET status='archived', updated_at=? WHERE id=?",
                (_now(), focus_id),
            )
            if cursor.rowcount == 0:
                raise FocusError(f"focus {focus_id!r} not found")
