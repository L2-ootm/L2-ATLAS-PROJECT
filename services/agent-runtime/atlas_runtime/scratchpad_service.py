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
import logging
import pathlib
import re
import sqlite3
import threading
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 256 * 1024
MAX_ENTRIES = 2_000
DEFAULT_LIMIT = 25
MAX_LIMIT = 200

SCOPES = ("run", "session", "project", "global")
KINDS = ("note", "plan", "finding", "draft", "artifact", "tool")
TTL_POLICIES = ("run", "session", "next_startup", "hours", "permanent")

# Disposable tools (WP-B). A generated script is bounded in three ways: it lives
# under one ATLAS-owned directory (never the repo, never an arbitrary path the
# model names), it carries a TTL that defaults to "gone by tomorrow", and a
# single run may only mint a handful before ATLAS says no — a looping agent
# cannot leave a hundred scripts behind.
MAX_TOOLS_PER_RUN = 5
MAX_TOOL_BODY_BYTES = 64 * 1024

# language -> (file extension, how the operator/agent invokes it)
TOOL_LANGUAGES: dict[str, tuple[str, str]] = {
    "python": ("py", "python"),
    "bash": ("sh", "bash"),
    "sh": ("sh", "bash"),
    "powershell": ("ps1", "pwsh -File"),
    "node": ("js", "node"),
    "javascript": ("js", "node"),
    "sql": ("sql", ""),
    "text": ("txt", ""),
}

# Read-back ordering (WP-D-1): a plan the run was following outranks a finding,
# which outranks the script it generated, which outranks loose notes.
_KIND_PRIORITY = ("plan", "finding", "tool", "draft", "note", "artifact")
DEFAULT_OPEN_LIMIT = 6

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


def open_entries(
    conn: sqlite3.Connection,
    *,
    session_id: str = "",
    run_id: str = "",
    limit: int = DEFAULT_OPEN_LIMIT,
    kinds: tuple[str, ...] = _KIND_PRIORITY,
) -> list[dict[str, Any]]:
    """The entries a resuming run should be handed back (WP-D-1).

    "Open" means: written by this session (a resumed run has a NEW run id but the
    SAME session, which is exactly the case read-back exists for), or by this
    run, or pinned at project/global scope — a pinned entry is the agent's own
    statement that it outlives the work that produced it.

    Ordered by usefulness on resume, not by recency alone: pinned first, then the
    kind priority (a plan beats a loose note), then newest.
    """
    if not session_id and not run_id:
        return []
    limit = max(1, min(int(limit or DEFAULT_OPEN_LIMIT), MAX_LIMIT))
    kinds = tuple(k for k in kinds if k in KINDS) or _KIND_PRIORITY
    ownership = ["(scope IN ('project','global') AND pinned=1)"]
    params: list[Any] = []
    if session_id:
        ownership.append("session_id=?")
        params.append(session_id)
    if run_id:
        ownership.append("run_id=?")
        params.append(run_id)
    kind_order = " ".join(
        f"WHEN ? THEN {index}" for index in range(len(kinds))
    )
    sql = (
        f"SELECT {_COLUMNS} FROM scratchpad_entries"
        f" WHERE ({' OR '.join(ownership)})"
        f" AND kind IN ({','.join('?' for _ in kinds)})"
        f" ORDER BY pinned DESC, CASE kind {kind_order} ELSE 99 END, updated_at DESC"
        " LIMIT ?"
    )
    params.extend(kinds)          # IN (...)
    params.extend(kinds)          # CASE kind WHEN ...
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


# ---------------------------------------------------------------------------
# Disposable tools (WP-B) — a generated script is a scratchpad entry with a file
# ---------------------------------------------------------------------------


def scratch_root(root: str | pathlib.Path | None = None) -> pathlib.Path:
    """Where materialized tools live: `<ATLAS home>/scratch/tools`.

    Outside the repository on purpose — a disposable tool must never dirty the
    working tree, and the sweep must never be able to reach a tracked file.
    Resolved at call time so ATLAS_HOME-isolated tests and releases both work.
    """
    if root is not None:
        return pathlib.Path(root).expanduser().resolve()
    from atlas_runtime import config_service  # noqa: PLC0415 — avoid an import cycle

    return (config_service.atlas_home() / "scratch" / "tools").resolve()


def _is_managed(path: str, root: pathlib.Path) -> bool:
    """True only for a file ATLAS itself materialized under `root`.

    `path` is operator/agent-supplied (op=write accepts one), so containment is
    checked before anything is unlinked. An entry pointing at a repo file is
    a reference, not an artifact, and the sweep leaves it alone.
    """
    if not path:
        return False
    try:
        return pathlib.Path(path).resolve().is_relative_to(root)
    except (OSError, ValueError):
        return False


def _unlink_managed(paths: list[str], root: pathlib.Path) -> int:
    removed = 0
    for path in paths:
        if not _is_managed(path, root):
            continue
        try:
            pathlib.Path(path).unlink()
            removed += 1
        except FileNotFoundError:
            continue
        except OSError as exc:  # locked/permission — the row is gone regardless
            logger.debug("scratchpad file %s not removed: %s", path, exc)
    return removed


def materialize_tool(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    title: str,
    body: str,
    language: str = "python",
    entry_id: Optional[str] = None,
    ttl_policy: str = "next_startup",
    expires_in_hours: Optional[float] = None,
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
    owner: str = "",
    scope: str = "run",
    root: str | pathlib.Path | None = None,
) -> dict[str, Any]:
    """Write a one-off script to disk and register it as a disposable tool.

    This is the L2 self-extension primitive: the agent that hits a missing
    capability writes the smallest script that removes the block, gets back the
    command line for it, and runs it through the *existing* terminal tool and
    permission broker. No new execution path, no in-process import, no privilege
    the agent did not already have — a disposable tool is a saved command, not a
    plugin. It expires on the next startup unless someone pins it.

    Returns the entry plus `invocation` (how to run it) and `root`.
    """
    if language not in TOOL_LANGUAGES:
        raise ScratchpadError(
            f"language must be one of {', '.join(sorted(TOOL_LANGUAGES))}"
        )
    body = str(body or "")
    if not body.strip():
        raise ScratchpadError("a disposable tool needs a body — use op=write for a note")
    if len(body.encode("utf-8")) > MAX_TOOL_BODY_BYTES:
        raise ScratchpadError(
            f"tool body exceeds {MAX_TOOL_BODY_BYTES} bytes — a self-extension this "
            "large is a feature request, not a disposable"
        )
    title = str(title or "").strip()
    if not title:
        raise ScratchpadError("title is required")
    resolved_id = (entry_id or _slug(title) or f"tool-{uuid.uuid4().hex[:12]}").strip()
    if not _ID_RE.match(resolved_id):
        raise ScratchpadError(f"invalid entry id {resolved_id!r}")

    existing = get_entry(conn, resolved_id)
    if existing is None and run_id:
        minted = conn.execute(
            "SELECT COUNT(*) FROM scratchpad_entries WHERE kind='tool' AND run_id=?",
            (run_id,),
        ).fetchone()[0]
        if int(minted) >= MAX_TOOLS_PER_RUN:
            raise ScratchpadError(
                f"this run already materialized {MAX_TOOLS_PER_RUN} tools — reuse one, "
                "remove one, or stop and report that the capability is missing"
            )

    extension, runner = TOOL_LANGUAGES[language]
    directory = scratch_root(root)
    target = (directory / f"{resolved_id}.{extension}").resolve()
    if not target.is_relative_to(directory):
        raise ScratchpadError(f"refusing to write outside the scratch root: {target}")
    try:
        directory.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    except OSError as exc:
        raise ScratchpadError(f"could not write {target}: {exc}") from exc

    entry = write_entry(
        conn, lock,
        title=title,
        body=body,
        entry_id=resolved_id,
        kind="tool",
        scope=scope,
        ttl_policy=ttl_policy,
        expires_in_hours=expires_in_hours,
        run_id=run_id,
        session_id=session_id,
        owner=owner,
        path=str(target),
    )
    invocation = f"{runner} {target}".strip() if runner else str(target)
    return {**entry, "invocation": invocation, "root": str(directory)}


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


def remove_entry(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    entry_id: str,
    root: str | pathlib.Path | None = None,
) -> bool:
    """Delete an entry outright (pinning does not protect an explicit delete).

    A materialized tool's file goes with it: leaving orphaned scripts behind is
    the landfill failure mode the TTL exists to prevent.
    """
    existing = get_entry(conn, entry_id)
    with lock:
        with conn:
            cursor = conn.execute("DELETE FROM scratchpad_entries WHERE id=?", (entry_id,))
    removed = cursor.rowcount > 0
    if removed and existing and existing["path"]:
        _unlink_managed([existing["path"]], scratch_root(root))
    return removed


def sweep(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    startup: bool = False,
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
    root: str | pathlib.Path | None = None,
) -> dict[str, Any]:
    """Delete expired entries. Pinned entries always survive.

    - always: `hours` entries past `expires_at`
    - `run_id`: that run's `run`-policy entries (call when a run finishes)
    - `session_id`: that session's `session`-policy entries
    - `startup=True`: `next_startup` entries, plus every `run`/`session` entry
      left behind by a previous process (their owners cannot come back)

    Files materialized under the scratch root go with their rows (`files` in the
    result); paths pointing anywhere else are references and are left untouched.
    """
    removed: dict[str, int] = {}
    doomed_paths: list[str] = []
    now = _now()

    def _delete(label: str, where: str, params: tuple[Any, ...]) -> None:
        doomed_paths.extend(
            row[0]
            for row in conn.execute(
                f"SELECT path FROM scratchpad_entries WHERE {where} AND path<>''", params
            )
        )
        removed[label] = conn.execute(
            f"DELETE FROM scratchpad_entries WHERE {where}", params
        ).rowcount

    with lock:
        with conn:
            _delete(
                "expired",
                "pinned=0 AND ttl_policy='hours' AND expires_at IS NOT NULL"
                " AND expires_at < ?",
                (now,),
            )
            if run_id:
                _delete("run", "pinned=0 AND ttl_policy='run' AND run_id=?", (run_id,))
            if session_id:
                _delete(
                    "session",
                    "pinned=0 AND ttl_policy='session' AND session_id=?",
                    (session_id,),
                )
            if startup:
                _delete(
                    "startup",
                    "pinned=0 AND ttl_policy IN ('next_startup','run','session')",
                    (),
                )
    removed["total"] = sum(removed.values())
    removed["files"] = _unlink_managed(doomed_paths, scratch_root(root))
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
    "MAX_TOOLS_PER_RUN",
    "MAX_TOOL_BODY_BYTES",
    "SCOPES",
    "TOOL_LANGUAGES",
    "TTL_POLICIES",
    "ScratchpadError",
    "get_entry",
    "list_entries",
    "materialize_tool",
    "open_entries",
    "remove_entry",
    "scratch_root",
    "set_pinned",
    "stats",
    "sweep",
    "write_entry",
]
