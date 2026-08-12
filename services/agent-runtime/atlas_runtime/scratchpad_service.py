"""Agent scratchpad — durable working memory with an expiry policy.

A long agent run accumulates things that are neither conversation nor product:
a plan it is following, a finding it must not re-derive, a draft it will refine,
a throwaway script it generated. Today those live only in the transcript, which
means a compaction or a context reset destroys them, and the agent redoes work
it already did. The scratchpad is where that state goes instead.

The same table backs the **disposable artifact** direction
(`docs/plans/2026-08-12-atlas-self-extension-roadmap.md`): a generated one-off
tool and a scratch note differ only in `kind` and `ttl_policy`. Both need an
owner, an expiry, a sweep, and a promotion path — so both live in
`scratchpad_entries` (migration 0034) rather than in two half-built registries.

TTL policies:

  run           — dies when the run that wrote it ends
  session       — dies with the surface session
  next_startup  — survives the process, swept on the next startup
  hours         — explicit wall-clock expiry (`expires_in_hours`)
  permanent     — never swept (still deletable by hand)

`pinned` survives every sweep regardless of policy: pinning is how a disposable
artifact graduates into something the operator keeps.

Conventions follow module_data_service: plain dicts, lock-injected mutations,
idempotent writes (same id converges instead of duplicating).
"""
from __future__ import annotations

import datetime
import re
import sqlite3
import threading
import uuid
from typing import Any, Optional

MAX_BODY_BYTES = 256 * 1024
MAX_ENTRIES = 2_000
DEFAULT_LIMIT = 25
MAX_LIMIT = 200

SCOPES = ("run", "session", "project", "global")
KINDS = ("note", "plan", "finding", "draft", "artifact", "tool")
TTL_POLICIES = ("run", "session", "next_startup", "hours", "permanent")

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


class ScratchpadError(ValueError):
    """Invalid scope/kind/ttl, oversized body, or an unknown entry."""


def _now_dt() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _now() -> str:
    return _now_dt().isoformat()


def _slug(text: str) -> str:
    return _SLUG_STRIP.sub("-", str(text).strip().lower()).strip("-")[:64]


_COLUMNS = (
    "id, scope, owner, run_id, session_id, kind, title, body, path, ttl_policy,"
    " expires_at, pinned, created_at, updated_at"
)


def _row(row: tuple) -> dict[str, Any]:
    entry = dict(zip(_COLUMNS.replace(" ", "").split(","), row))
    entry["pinned"] = bool(entry["pinned"])
    return entry


def get_entry(conn: sqlite3.Connection, entry_id: str) -> Optional[dict[str, Any]]:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM scratchpad_entries WHERE id=?", (entry_id,)
    ).fetchone()
    return None if row is None else _row(row)


def list_entries(
    conn: sqlite3.Connection,
    *,
    scope: str = "",
    owner: str = "",
    run_id: str = "",
    session_id: str = "",
    kind: str = "",
    search: str = "",
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Filtered entries, most recently updated first."""
    limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    sql = f"SELECT {_COLUMNS} FROM scratchpad_entries WHERE 1=1"
    params: list[Any] = []
    for column, value in (
        ("scope", scope), ("owner", owner), ("run_id", run_id),
        ("session_id", session_id), ("kind", kind),
    ):
        if value:
            sql += f" AND {column}=?"
            params.append(value)
    if search:
        sql += " AND (title LIKE ? OR body LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    return [_row(row) for row in conn.execute(sql, params)]


def _expiry_for(ttl_policy: str, expires_in_hours: Optional[float]) -> Optional[str]:
    if ttl_policy != "hours":
        return None
    hours = float(expires_in_hours if expires_in_hours is not None else 24.0)
    if hours <= 0:
        raise ScratchpadError("expires_in_hours must be positive")
    return (_now_dt() + datetime.timedelta(hours=hours)).isoformat()


def write_entry(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    title: str,
    body: str = "",
    entry_id: Optional[str] = None,
    kind: str = "note",
    scope: str = "run",
    ttl_policy: str = "session",
    expires_in_hours: Optional[float] = None,
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
    owner: str = "",
    path: str = "",
    pinned: Optional[bool] = None,
    append: bool = False,
) -> dict[str, Any]:
    """Create or overwrite an entry (append=True adds to the existing body).

    The id derives from the title when not given, so a run that keeps writing
    "current plan" keeps updating one entry instead of leaving twelve.
    """
    if kind not in KINDS:
        raise ScratchpadError(f"kind must be one of {', '.join(KINDS)}")
    if scope not in SCOPES:
        raise ScratchpadError(f"scope must be one of {', '.join(SCOPES)}")
    if ttl_policy not in TTL_POLICIES:
        raise ScratchpadError(f"ttl must be one of {', '.join(TTL_POLICIES)}")
    title = str(title or "").strip()
    if not title:
        raise ScratchpadError("title is required")
    body = str(body or "")
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise ScratchpadError(
            f"body exceeds {MAX_BODY_BYTES} bytes — write the long form to a file "
            "and keep its path in the entry"
        )
    if scope == "run" and not run_id:
        # A run-scoped entry with no run cannot ever be swept by its own policy.
        scope = "session" if session_id else "global"
    entry_id = (entry_id or _slug(title) or f"scratch-{uuid.uuid4().hex[:12]}").strip()
    if not _ID_RE.match(entry_id):
        raise ScratchpadError(f"invalid entry id {entry_id!r}")

    existing = get_entry(conn, entry_id)
    if existing is None:
        count = conn.execute("SELECT COUNT(*) FROM scratchpad_entries").fetchone()[0]
        if int(count) >= MAX_ENTRIES:
            raise ScratchpadError(
                f"scratchpad is at its {MAX_ENTRIES}-entry cap — sweep or remove entries"
            )
    if append and existing is not None:
        body = (existing["body"] + ("\n" if existing["body"] and body else "") + body)[
            : MAX_BODY_BYTES
        ]

    now = _now()
    expires_at = _expiry_for(ttl_policy, expires_in_hours)
    resolved_pin = bool(existing["pinned"]) if (existing and pinned is None) else bool(pinned)
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO scratchpad_entries(id, scope, owner, run_id, session_id, kind,"
                " title, body, path, ttl_policy, expires_at, pinned, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(id) DO UPDATE SET"
                " scope=excluded.scope, owner=excluded.owner, run_id=excluded.run_id,"
                " session_id=excluded.session_id, kind=excluded.kind, title=excluded.title,"
                " body=excluded.body, path=excluded.path, ttl_policy=excluded.ttl_policy,"
                " expires_at=excluded.expires_at, pinned=excluded.pinned,"
                " updated_at=excluded.updated_at",
                (
                    entry_id, scope, owner, run_id, session_id, kind, title, body, path,
                    ttl_policy, expires_at, int(resolved_pin), now, now,
                ),
            )
    written = get_entry(conn, entry_id)
    assert written is not None  # just wrote it
    return written


def set_pinned(
    conn: sqlite3.Connection, lock: threading.Lock, *, entry_id: str, pinned: bool
) -> dict[str, Any]:
    """Pin (keep through every sweep) or unpin an entry."""
    if get_entry(conn, entry_id) is None:
        raise ScratchpadError(f"unknown scratchpad entry: {entry_id!r}")
    with lock:
        with conn:
            conn.execute(
                "UPDATE scratchpad_entries SET pinned=?, updated_at=? WHERE id=?",
                (int(pinned), _now(), entry_id),
            )
    entry = get_entry(conn, entry_id)
    assert entry is not None
    return entry


def remove_entry(conn: sqlite3.Connection, lock: threading.Lock, *, entry_id: str) -> bool:
    """Delete an entry outright (pinning does not protect an explicit delete)."""
    with lock:
        with conn:
            cursor = conn.execute("DELETE FROM scratchpad_entries WHERE id=?", (entry_id,))
    return cursor.rowcount > 0


def sweep(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    startup: bool = False,
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    """Delete expired entries. Pinned entries always survive.

    - always: `hours` entries past `expires_at`
    - `run_id`: that run's `run`-policy entries (call when a run finishes)
    - `session_id`: that session's `session`-policy entries
    - `startup=True`: `next_startup` entries, plus every `run`/`session` entry
      left behind by a previous process (their owners cannot come back)
    """
    removed: dict[str, int] = {}
    now = _now()
    with lock:
        with conn:
            cursor = conn.execute(
                "DELETE FROM scratchpad_entries WHERE pinned=0 AND ttl_policy='hours'"
                " AND expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            )
            removed["expired"] = cursor.rowcount
            if run_id:
                cursor = conn.execute(
                    "DELETE FROM scratchpad_entries"
                    " WHERE pinned=0 AND ttl_policy='run' AND run_id=?",
                    (run_id,),
                )
                removed["run"] = cursor.rowcount
            if session_id:
                cursor = conn.execute(
                    "DELETE FROM scratchpad_entries"
                    " WHERE pinned=0 AND ttl_policy='session' AND session_id=?",
                    (session_id,),
                )
                removed["session"] = cursor.rowcount
            if startup:
                cursor = conn.execute(
                    "DELETE FROM scratchpad_entries"
                    " WHERE pinned=0 AND ttl_policy IN ('next_startup','run','session')"
                )
                removed["startup"] = cursor.rowcount
    removed["total"] = sum(removed.values())
    return removed


def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Counts by kind and ttl policy — the operator's management view."""
    by_kind = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT kind, COUNT(*) FROM scratchpad_entries GROUP BY kind"
        )
    }
    by_ttl = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT ttl_policy, COUNT(*) FROM scratchpad_entries GROUP BY ttl_policy"
        )
    }
    total = conn.execute("SELECT COUNT(*) FROM scratchpad_entries").fetchone()[0]
    pinned = conn.execute(
        "SELECT COUNT(*) FROM scratchpad_entries WHERE pinned=1"
    ).fetchone()[0]
    return {"total": int(total), "pinned": int(pinned), "by_kind": by_kind, "by_ttl": by_ttl}


__all__ = [
    "KINDS",
    "MAX_BODY_BYTES",
    "MAX_ENTRIES",
    "SCOPES",
    "TTL_POLICIES",
    "ScratchpadError",
    "get_entry",
    "list_entries",
    "remove_entry",
    "set_pinned",
    "stats",
    "sweep",
    "write_entry",
]
