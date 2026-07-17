"""Operator-defined Graphify scopes — custom graph tabs backed by folders.

Built-in scopes (atlas/global/projects/obsidian) stay code-defined; custom
scopes are rows in ``graph_scopes`` (0025). Each has a slug id, display label,
folder path, and kind:

* ``markdown`` — one corpus graph of every ``*.md`` under the folder.
* ``projects`` — one cluster per child directory (a projects overview graph).

Antifragility: creation is idempotent (same label+path converges on the same
row), paths are validated before any write, and reads tolerate a pre-0025 DB
by returning empty. Deletion of an unknown scope raises so callers can
distinguish "already gone" from success.
"""
from __future__ import annotations

import datetime
import re
import sqlite3
import threading
from pathlib import Path
from typing import Optional

BUILTIN_SCOPES = ("atlas", "global", "projects", "obsidian")
VALID_KINDS = ("markdown", "projects")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class GraphScopeError(ValueError):
    """Raised for invalid scope inputs (bad path, kind, or unknown id)."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def slugify(label: str) -> str:
    slug = _SLUG_RE.sub("-", label.lower()).strip("-")
    if not slug:
        raise GraphScopeError("label must contain at least one letter or digit")
    return slug[:64]


def list_scopes(conn: sqlite3.Connection) -> list[dict]:
    """Custom scopes ordered by creation; empty on a pre-0025 DB."""
    try:
        cursor = conn.execute(
            "SELECT id, label, root_path, kind, created_at, updated_at "
            "FROM graph_scopes ORDER BY created_at ASC"
        )
    except sqlite3.OperationalError:
        return []
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor]


def get_scope(conn: sqlite3.Connection, scope_id: str) -> Optional[dict]:
    try:
        cursor = conn.execute(
            "SELECT id, label, root_path, kind, created_at, updated_at "
            "FROM graph_scopes WHERE id=?",
            (scope_id,),
        )
    except sqlite3.OperationalError:
        return None
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def create_scope(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    label: str,
    root_path: str,
    kind: str = "markdown",
) -> dict:
    """Create (or converge on) a custom scope; returns the row.

    Idempotent: an existing scope with the same id and path is returned
    unchanged. The same id pointing at a different path is an explicit error —
    silent repointing would corrupt an existing tab's meaning.
    """
    if kind not in VALID_KINDS:
        raise GraphScopeError(f"kind must be one of {VALID_KINDS}")
    if not label or not label.strip():
        raise GraphScopeError("label must not be empty")
    scope_id = slugify(label)
    if scope_id in BUILTIN_SCOPES:
        raise GraphScopeError(f"{scope_id!r} is a built-in scope")
    resolved = Path(root_path).expanduser()
    if not resolved.is_dir():
        raise GraphScopeError(f"folder not found: {root_path}")
    resolved_str = str(resolved.resolve())

    with lock:
        with conn:
            existing = get_scope(conn, scope_id)
            if existing is not None:
                if existing["root_path"] == resolved_str and existing["kind"] == kind:
                    return existing
                raise GraphScopeError(
                    f"scope {scope_id!r} already exists with a different folder/kind; "
                    "remove it first or pick another name"
                )
            now = _now()
            conn.execute(
                "INSERT INTO graph_scopes(id, label, root_path, kind, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (scope_id, label.strip(), resolved_str, kind, now, now),
            )
    created = get_scope(conn, scope_id)
    assert created is not None
    return created


def delete_scope(conn: sqlite3.Connection, lock: threading.Lock, scope_id: str) -> None:
    if scope_id in BUILTIN_SCOPES:
        raise GraphScopeError("built-in scopes cannot be removed")
    with lock:
        with conn:
            cursor = conn.execute("DELETE FROM graph_scopes WHERE id=?", (scope_id,))
            if cursor.rowcount == 0:
                raise GraphScopeError(f"scope {scope_id!r} not found")
