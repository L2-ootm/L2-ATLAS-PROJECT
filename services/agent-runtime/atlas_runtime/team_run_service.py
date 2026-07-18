"""Team run — the group-chat message log and round bookkeeping.

DB-pure, mirroring actor_service.py's split: this module owns the
`team_runs` and `team_chat_messages` tables (state machine + the ordered,
cursor-consumed buffer). Process launch and the round-robin driver that
turns members via the existing actor supervisor live in team_run_worker.py.
See docs/plans/2026-07-18-agent-teams-and-group-chat-design.md.
"""
from __future__ import annotations

import datetime
import re
import sqlite3
import threading
import uuid
from typing import Any, Optional

CONTENT_CAP = 4000
MAX_ROUNDS_CAP = 20
DEFAULT_MAX_ROUNDS = 6
ACTIVE_STATUSES = ("queued", "running")
TERMINAL_STATUSES = ("completed", "failed", "cancelled")

_MENTION_RE = re.compile(r"^@([a-zA-Z0-9_-]+):\s*(.*)$", re.DOTALL)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    return {d[0]: row[i] for i, d in enumerate(cursor.description)}


def parse_target(content: str) -> tuple[str, str]:
    """Extract an `@role_label: ...` mention prefix. Returns (target, content).

    `target` defaults to "all" when no recognizable mention prefix is present.
    """
    match = _MENTION_RE.match((content or "").strip())
    if match:
        role_label, rest = match.group(1), match.group(2).strip()
        return role_label, (rest or content.strip())
    return "all", (content or "").strip()


def is_done_signal(content: str) -> bool:
    """A member's turn ends the run early when its whole message is `DONE`."""
    return (content or "").strip().upper() == "DONE"


# ---------------------------------------------------------------------------
# team_runs
# ---------------------------------------------------------------------------


def create_team_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    team_id: str,
    kickoff_message: str,
    mission_id: Optional[str] = None,
    parent_run_id: Optional[str] = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> dict[str, Any]:
    kickoff_message = (kickoff_message or "").strip()
    if not kickoff_message:
        raise ValueError("kickoff_message must be non-empty")
    if max_rounds < 1 or max_rounds > MAX_ROUNDS_CAP:
        raise ValueError(f"max_rounds must be between 1 and {MAX_ROUNDS_CAP}")
    team_run_id = f"team-run-{uuid.uuid4()}"
    now = _now()
    with lock:
        with conn:
            team_row = conn.execute("SELECT 1 FROM teams WHERE id=?", (team_id,)).fetchone()
            if team_row is None:
                raise ValueError(f"team {team_id!r} not found")
            members = conn.execute(
                "SELECT 1 FROM team_members WHERE team_id=?", (team_id,)
            ).fetchone()
            if members is None:
                raise ValueError("team has no members; add at least one before running")
            conn.execute(
                "INSERT INTO team_runs(id, team_id, parent_run_id, mission_id,"
                " status, max_rounds, current_round, created_at, updated_at)"
                " VALUES (?,?,?,?,'queued',?,0,?,?)",
                (team_run_id, team_id, parent_run_id, mission_id, max_rounds, now, now),
            )
            conn.execute(
                "INSERT INTO team_chat_messages(id, team_run_id, seq, round,"
                " sender_actor_id, sender_role, target, content, created_at)"
                " VALUES (?,?,1,0,NULL,'orchestrator','all',?,?)",
                (f"msg-{uuid.uuid4()}", team_run_id, kickoff_message[:CONTENT_CAP], now),
            )
    run = get_team_run(conn, team_run_id)
    assert run is not None
    return run


def get_team_run(conn: sqlite3.Connection, team_run_id: str) -> Optional[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM team_runs WHERE id=?", (team_run_id,))
    row = cur.fetchone()
    return _row_to_dict(cur, row) if row else None


def list_team_runs(
    conn: sqlite3.Connection, *, team_id: Optional[str] = None, limit: int = 50
) -> list[dict[str, Any]]:
    if team_id:
        cur = conn.execute(
            "SELECT * FROM team_runs WHERE team_id=? ORDER BY created_at DESC LIMIT ?",
            (team_id, max(1, min(limit, 100))),
        )
    else:
        cur = conn.execute(
            "SELECT * FROM team_runs ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        )
    return [_row_to_dict(cur, row) for row in cur.fetchall()]


def mark_team_run_running(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    team_run_id: str,
    *,
    parent_run_id: Optional[str] = None,
) -> bool:
    """CAS queued -> running. When the run has no anchor run yet (a team run
    started outside an existing mission/run), `parent_run_id` sets one so
    every member actor spawned this round has a valid `runs(id)` to attach
    to — the same anchor actor_service.spawn_actor already requires."""
    now = _now()
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE team_runs SET status='running', started_at=?, updated_at=?,"
                " parent_run_id=COALESCE(parent_run_id, ?)"
                " WHERE id=? AND status='queued'",
                (now, now, parent_run_id, team_run_id),
            )
            return cur.rowcount == 1


def set_current_round(
    conn: sqlite3.Connection, lock: threading.Lock, team_run_id: str, round_no: int
) -> bool:
    now = _now()
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE team_runs SET current_round=?, updated_at=?"
                " WHERE id=? AND status='running'",
                (round_no, now, team_run_id),
            )
            return cur.rowcount == 1


def finish_team_run(
    conn: sqlite3.Connection, lock: threading.Lock, team_run_id: str, *, status: str
) -> bool:
    """Monotonic terminal transition. Repeated finishing is a no-op."""
    if status not in TERMINAL_STATUSES:
        raise ValueError(f"invalid terminal status: {status!r}")
    now = _now()
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE team_runs SET status=?, finished_at=?, updated_at=?"
                " WHERE id=? AND status IN ('queued','running')",
                (status, now, now, team_run_id),
            )
            return cur.rowcount == 1


def cancel_team_run(conn: sqlite3.Connection, lock: threading.Lock, team_run_id: str) -> bool:
    return finish_team_run(conn, lock, team_run_id, status="cancelled")


# ---------------------------------------------------------------------------
# team_chat_messages (the buffer)
# ---------------------------------------------------------------------------


def append_message(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    team_run_id: str,
    *,
    round_no: int,
    sender_role: str,
    content: str,
    sender_actor_id: Optional[str] = None,
    target: Optional[str] = None,
) -> dict[str, Any]:
    resolved_target, cleaned = (target, content) if target else parse_target(content)
    now = _now()
    with lock:
        with conn:
            next_seq = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM team_chat_messages WHERE team_run_id=?",
                (team_run_id,),
            ).fetchone()[0]
            msg_id = f"msg-{uuid.uuid4()}"
            conn.execute(
                "INSERT INTO team_chat_messages(id, team_run_id, seq, round,"
                " sender_actor_id, sender_role, target, content, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    msg_id, team_run_id, next_seq, round_no, sender_actor_id,
                    sender_role, resolved_target, cleaned[:CONTENT_CAP], now,
                ),
            )
    cur = conn.execute("SELECT * FROM team_chat_messages WHERE id=?", (msg_id,))
    return _row_to_dict(cur, cur.fetchone())


def list_messages(
    conn: sqlite3.Connection, team_run_id: str, *, since_seq: int = 0
) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT * FROM team_chat_messages WHERE team_run_id=? AND seq>?"
        " ORDER BY seq ASC",
        (team_run_id, since_seq),
    )
    return [_row_to_dict(cur, row) for row in cur.fetchall()]


def build_inbox(
    conn: sqlite3.Connection, team_run_id: str, *, role_label: str, since_seq: int = 0
) -> list[dict[str, Any]]:
    """Unseen messages targeted at this role or broadcast to all.

    This is the whole buffer: an append-only, seq-ordered log with a per-
    member read cursor (`since_seq`). No concurrent claimants exist by
    construction — team members take turns one at a time — so no lease is
    needed here the way actor_deliveries needs one for parallel actors.
    """
    cur = conn.execute(
        "SELECT * FROM team_chat_messages WHERE team_run_id=? AND seq>?"
        " AND target IN ('all', ?) ORDER BY seq ASC",
        (team_run_id, since_seq, role_label),
    )
    return [_row_to_dict(cur, row) for row in cur.fetchall()]


def render_inbox(inbox: list[dict[str, Any]]) -> str:
    """Render an inbox as plain text context to append to a member's goal."""
    if not inbox:
        return ""
    lines = ["", "--- Team chat so far ---"]
    for msg in inbox:
        sender = msg["sender_role"] if msg.get("sender_actor_id") else "orchestrator"
        lines.append(f"[{sender}]: {msg['content']}")
    lines.append("--- End team chat ---")
    return "\n".join(lines)


__all__ = [
    "DEFAULT_MAX_ROUNDS",
    "MAX_ROUNDS_CAP",
    "parse_target",
    "is_done_signal",
    "create_team_run",
    "get_team_run",
    "list_team_runs",
    "mark_team_run_running",
    "set_current_round",
    "finish_team_run",
    "cancel_team_run",
    "append_message",
    "list_messages",
    "build_inbox",
    "render_inbox",
]
