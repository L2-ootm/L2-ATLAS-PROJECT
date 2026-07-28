"""Server-side conversation history for surface sessions (migration 0030).

Before this module, conversation messages existed only in the cockpit's
localStorage behind a 150-message cap: history died with the browser tab and
could not be searched across sessions. `session_messages` is the durable record;
this service is the only writer.

Conventions mirror `surface_session_service`: `(conn, lock)` arguments, the
guarded write inside `with lock: with conn:`, and no audit emission while the
lock is held. Two rules are specific to this table:

* **seq is assigned inside the write transaction** (`MAX(seq) + 1` scoped to the
  session), not by the caller. Two processes may write to one session — the
  gateway dispatches CLI subprocesses, so the in-process lock is not the only
  serialization point — and `idx_session_messages_session_seq` is UNIQUE, so a
  race surfaces as an IntegrityError rather than silent reordering. That case is
  retried a bounded number of times against a freshly read max.
* **Content is redacted before persistence**, the same boundary
  `audit_service.emit` enforces. A transcript is exactly where a pasted API key
  ends up, and this table outlives the audit trail (retention purges
  `audit_events`; conversation history is meant to be kept).

Reads are windowed (`list_messages`) or FTS-backed (`search_messages`); neither
loads a whole session into memory.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading
import uuid
from typing import Any, Optional

from atlas_runtime.memory_router import estimate_tokens, redact

# Roles the CHECK constraint in 0030 accepts. Validated here so a bad role fails
# with a named error instead of an opaque sqlite3.IntegrityError.
VALID_ROLES = ("system", "user", "assistant", "tool")

# Bounded retries for a seq collision (a concurrent writer took the number we
# read). Each retry re-reads MAX(seq); the loop is bounded so a genuinely broken
# unique index cannot spin forever.
_SEQ_RETRIES = 5

# Windowed reads default and hard cap — the cockpit paginates, and an unbounded
# LIMIT would let one request pull an entire multi-thousand-message session.
_DEFAULT_LIMIT = 50
_MAX_LIMIT = 500

# SQLite 3's bundled FTS5 parser reports malformed MATCH expressions through
# SQLITE_ERROR. Keep this allowlist intentionally narrow: other SQLITE_ERROR
# messages include missing tables and ordinary SQL/schema failures, which must
# remain observable to callers.
_MALFORMED_FTS_EXACT_MESSAGES = frozenset({"unterminated string"})
_MALFORMED_FTS_MESSAGE_PREFIX = 'fts5: syntax error near "'


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _is_malformed_fts_query_error(exc: sqlite3.OperationalError) -> bool:
    """Whether *exc* is a bundled-SQLite FTS5 query-parser rejection."""
    if getattr(exc, "sqlite_errorcode", None) != sqlite3.SQLITE_ERROR:
        return False
    message = str(exc)
    return message in _MALFORMED_FTS_EXACT_MESSAGES or (
        message.startswith(_MALFORMED_FTS_MESSAGE_PREFIX) and message.endswith('"')
    )


def _row_to_message(row: sqlite3.Row | tuple) -> dict[str, Any]:
    (
        mid,
        surface_session_id,
        run_id,
        role,
        content,
        token_count,
        tool_call_id,
        tool_name,
        metadata_json,
        created_at,
        seq,
    ) = row
    try:
        metadata = json.loads(metadata_json or "{}")
    except (TypeError, ValueError):
        # A malformed metadata blob must not sink the whole read: the message
        # text is the payload that matters, metadata is auxiliary.
        metadata = {}
    return {
        "id": mid,
        "surface_session_id": surface_session_id,
        "run_id": run_id,
        "role": role,
        "content": content,
        "token_count": token_count,
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "metadata": metadata,
        "created_at": created_at,
        "seq": seq,
    }


_SELECT_COLUMNS = (
    "id, surface_session_id, run_id, role, content, token_count, "
    "tool_call_id, tool_name, metadata_json, created_at, seq"
)


def append_message(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    surface_session_id: str,
    role: str,
    content: str,
    run_id: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append one message to a session's history and return the stored row.

    `seq` is assigned here, never by the caller. `token_count` is computed once
    at write time so reads never re-tokenize (the design's stated reason for the
    column). Raises ValueError on an unknown role or an empty session id;
    sqlite3.IntegrityError propagates if the surface session or run does not
    exist, because a message with no session to belong to is a caller bug, not a
    recoverable state.
    """
    if not surface_session_id:
        raise ValueError("surface_session_id is required")
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role {role!r} (expected one of {', '.join(VALID_ROLES)})")

    safe_content = redact(content or "")
    metadata_json = json.dumps(metadata or {}, separators=(",", ":"), ensure_ascii=False)
    row = {
        "id": str(uuid.uuid4()),
        "surface_session_id": surface_session_id,
        "run_id": run_id,
        "role": role,
        "content": safe_content,
        "token_count": estimate_tokens(safe_content),
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "metadata_json": metadata_json,
        "created_at": _now_iso(),
    }

    last_error: Optional[sqlite3.IntegrityError] = None
    for _ in range(_SEQ_RETRIES):
        with lock:
            with conn:
                seq = (
                    conn.execute(
                        "SELECT COALESCE(MAX(seq), 0) + 1 FROM session_messages "
                        "WHERE surface_session_id=?",
                        (surface_session_id,),
                    ).fetchone()[0]
                )
                try:
                    conn.execute(
                        "INSERT INTO session_messages("
                        "id, surface_session_id, run_id, role, content, token_count, "
                        "tool_call_id, tool_name, metadata_json, created_at, seq) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            row["id"],
                            row["surface_session_id"],
                            row["run_id"],
                            row["role"],
                            row["content"],
                            row["token_count"],
                            row["tool_call_id"],
                            row["tool_name"],
                            row["metadata_json"],
                            row["created_at"],
                            seq,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    # Only a (session, seq) collision is retryable — a concurrent
                    # writer took the number we just read. A missing FK target
                    # will never succeed on a retry, so it propagates.
                    if "UNIQUE constraint failed" not in str(exc):
                        raise
                    last_error = exc
                    continue
        row["seq"] = seq
        return _row_to_message(
            (
                row["id"],
                row["surface_session_id"],
                row["run_id"],
                row["role"],
                row["content"],
                row["token_count"],
                row["tool_call_id"],
                row["tool_name"],
                row["metadata_json"],
                row["created_at"],
                seq,
            )
        )

    raise last_error if last_error else RuntimeError("seq assignment failed")


def list_messages(
    conn: sqlite3.Connection,
    surface_session_id: str,
    *,
    limit: int = _DEFAULT_LIMIT,
    before_seq: Optional[int] = None,
    after_seq: Optional[int] = None,
) -> dict[str, Any]:
    """One window of a session's history, oldest-first, with a `has_more` flag.

    Two cursors, both exclusive and mutually exclusive with each other:
    `after_seq` pages forward (the cockpit polling for new turns, mirroring
    `surface events --after-seq`), `before_seq` pages backwards (infinite scroll
    into older history). With neither, the newest `limit` messages are returned.

    Returns oldest-first in every mode so the caller renders the window without
    re-sorting; the backwards page is selected with `ORDER BY seq DESC LIMIT n`
    (so it uses the unique index and reads n rows, not the whole session) and
    reversed here.
    """
    limit = max(1, min(int(limit), _MAX_LIMIT))
    total = conn.execute(
        "SELECT COUNT(*) FROM session_messages WHERE surface_session_id=?",
        (surface_session_id,),
    ).fetchone()[0]

    if after_seq is not None:
        rows = conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM session_messages "  # noqa: S608 — fixed column list
            "WHERE surface_session_id=? AND seq>? ORDER BY seq ASC LIMIT ?",
            (surface_session_id, int(after_seq), limit + 1),
        ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
    else:
        params: list[Any] = [surface_session_id]
        clause = ""
        if before_seq is not None:
            clause = "AND seq<? "
            params.append(int(before_seq))
        params.append(limit + 1)
        rows = conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM session_messages "  # noqa: S608 — fixed column list
            f"WHERE surface_session_id=? {clause}ORDER BY seq DESC LIMIT ?",
            params,
        ).fetchall()
        has_more = len(rows) > limit
        rows = list(reversed(rows[:limit]))

    return {
        "session_id": surface_session_id,
        "messages": [_row_to_message(r) for r in rows],
        "total": total,
        "limit": limit,
        "has_more": has_more,
    }


def tail_messages(
    conn: sqlite3.Connection, surface_session_id: str, *, limit: int = 20
) -> list[dict[str, Any]]:
    """The last `limit` messages of a session, oldest-first — the replay window."""
    return list_messages(conn, surface_session_id, limit=limit)["messages"]


def search_messages(
    conn: sqlite3.Connection,
    query: str,
    *,
    surface_session_id: Optional[str] = None,
    limit: int = _DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """FTS5 search across message content, newest match first.

    Scoped to one session when `surface_session_id` is given, otherwise across
    every session — the cross-session search the localStorage transcript could
    never do. A malformed FTS query (an unbalanced quote from an operator's
    search box) raises sqlite3.OperationalError inside FTS5; that is returned as
    an empty result rather than a 500, since a typo in a search box is not an
    error condition worth failing a request over. All other database failures
    propagate so infrastructure faults cannot masquerade as valid empty results.
    """
    limit = max(1, min(int(limit), _MAX_LIMIT))
    if not (query or "").strip():
        return []
    sql = (
        f"SELECT m.id, m.surface_session_id, m.run_id, m.role, m.content, m.token_count, "  # noqa: S608
        "m.tool_call_id, m.tool_name, m.metadata_json, m.created_at, m.seq "
        "FROM session_messages_fts f JOIN session_messages m ON m.rowid = f.rowid "
        "WHERE session_messages_fts MATCH ?"
    )
    params: list[Any] = [query]
    if surface_session_id:
        sql += " AND m.surface_session_id=?"
        params.append(surface_session_id)
    sql += " ORDER BY m.created_at DESC, m.seq DESC LIMIT ?"
    params.append(limit)
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError as exc:
        if _is_malformed_fts_query_error(exc):
            return []
        raise
    return [_row_to_message(r) for r in rows]


def session_token_total(conn: sqlite3.Connection, surface_session_id: str) -> int:
    """Sum of stored `token_count` for a session — the compaction trigger input.

    Compaction itself is not implemented (`compaction_artifacts` is written by
    nothing yet); this is the measurement the threshold check will read, and it
    is useful on its own for reporting how large a session has grown.
    """
    return int(
        conn.execute(
            "SELECT COALESCE(SUM(token_count), 0) FROM session_messages "
            "WHERE surface_session_id=?",
            (surface_session_id,),
        ).fetchone()[0]
    )


__all__ = [
    "VALID_ROLES",
    "append_message",
    "list_messages",
    "search_messages",
    "session_token_total",
    "tail_messages",
]
