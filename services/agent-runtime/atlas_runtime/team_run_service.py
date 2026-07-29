"""Team run — the group-chat message log and round bookkeeping.

DB-pure, mirroring actor_service.py's split: this module owns the
`team_runs` and `team_chat_messages` tables (state machine + the ordered,
cursor-consumed buffer). Process launch and the round-robin driver that
turns members via the existing actor supervisor live in team_run_worker.py.
See docs/plans/2026-07-18-agent-teams-and-group-chat-design.md.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import re
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from atlas_runtime import change_reconciliation
from atlas_runtime.run_service import persist_full_result_reference

logger = logging.getLogger(__name__)

CONTENT_CAP = 4000
MAX_ROUNDS_CAP = 20
DEFAULT_MAX_ROUNDS = 6
ACTIVE_STATUSES = ("queued", "running")
TERMINAL_STATUSES = ("completed", "failed", "cancelled")

_MENTION_RE = re.compile(r"^@([a-zA-Z0-9_-]+):\s*(.*)$", re.DOTALL)


class TeamRunCancelledError(RuntimeError):
    """Raised when a writer loses the cancellation race."""


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(  # noqa: S603
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            check=False,
        )
        return result.returncode == 0 and f'"{pid}"' in result.stdout
    try:  # pragma: no cover - POSIX only
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


def _terminate_process_tree(pid: int) -> bool:
    """Request bounded process-tree termination; verification is separate."""
    if pid <= 0:
        return True
    try:
        if os.name == "nt":
            result = subprocess.run(  # noqa: S603
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
                check=False,
            )
            return result.returncode == 0 or not _pid_alive(pid)
        os.killpg(os.getpgid(pid), 15)  # pragma: no cover - POSIX only
        return True
    except (OSError, ValueError):
        return not _pid_alive(pid)


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


def _lossless_team_content(
    conn: sqlite3.Connection, team_run_id: str, content: str
) -> str:
    if len(content) <= CONTENT_CAP:
        return content
    reference = persist_full_result_reference(
        conn,
        owner_kind="team_run",
        owner_id=team_run_id,
        content=content,
        preview_limit=CONTENT_CAP,
        team_run_id=team_run_id,
    )
    return json.dumps(
        {"preview": reference["preview"], "full_result": reference},
        ensure_ascii=False,
        sort_keys=True,
    )


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
    if len(kickoff_message) > CONTENT_CAP:
        stored_kickoff = _lossless_team_content(conn, team_run_id, kickoff_message)
        with lock:
            with conn:
                conn.execute(
                    "UPDATE team_chat_messages SET content=?"
                    " WHERE team_run_id=? AND seq=1",
                    (stored_kickoff, team_run_id),
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


def record_worker_pid(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    team_run_id: str,
    pid: int,
) -> bool:
    """Persist the detached worker identity before it starts spawning actors."""
    with lock:
        with conn:
            cur = conn.execute(
                "UPDATE team_runs SET worker_pid=?, updated_at=?"
                " WHERE id=? AND status IN ('queued','running')",
                (pid, _now(), team_run_id),
            )
            return cur.rowcount == 1


def cancellation_requested(conn: sqlite3.Connection, team_run_id: str) -> bool:
    row = conn.execute(
        "SELECT status, cancel_requested_at FROM team_runs WHERE id=?",
        (team_run_id,),
    ).fetchone()
    return row is None or row[0] == "cancelled" or row[1] is not None


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
    team_run = get_team_run(conn, team_run_id)
    if team_run is None or team_run["status"] not in ACTIVE_STATUSES:
        return False
    if status == "completed":
        escaped = (
            team_run_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        change_set_ids = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT ecs.id FROM evidence_change_sets ecs"
                " LEFT JOIN actors actor ON actor.id=ecs.actor_id"
                " WHERE ecs.team_run_id=?"
                " OR actor.idempotency_key LIKE ? ESCAPE '\\'"
                " ORDER BY ecs.id",
                (team_run_id, f"{escaped}:%"),
            ).fetchall()
        ]
        if change_set_ids:
            db_row = conn.execute("PRAGMA database_list").fetchone()
            db_path = Path(db_row[2]) if db_row and db_row[2] else None
            receipt = change_reconciliation.persist_reference_aggregation(
                db_path=db_path,
                provenance={
                    "run_id": team_run.get("parent_run_id"),
                    "team_run_id": team_run_id,
                },
                child_change_set_ids=change_set_ids,
            )
            if receipt.status != "captured":
                # Evidence failure is explicit without corrupting the team's
                # already-completed application result.
                logger.error(
                    "team %s evidence aggregation unavailable: %s",
                    team_run_id,
                    receipt.error_code,
                )
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
    """Cancel actors/runs/processes, then persist verified cleanup truth.

    The boolean reports whether this call made the terminal transition. Cleanup
    outcome remains available on the run for both first and repeated calls.
    """
    now = _now()
    with lock:
        with conn:
            row = conn.execute(
                "SELECT status, worker_pid FROM team_runs WHERE id=?",
                (team_run_id,),
            ).fetchone()
            if row is None:
                return False
            changed = row[0] in ACTIVE_STATUSES
            if row[0] not in ACTIVE_STATUSES and row[0] != "cancelled":
                return False
            conn.execute(
                "UPDATE team_runs SET status='cancelled',"
                " cancel_requested_at=COALESCE(cancel_requested_at, ?),"
                " finished_at=COALESCE(finished_at, ?), updated_at=?,"
                " cleanup_status='pending', cleanup_error=NULL WHERE id=?",
                (now, now, now, team_run_id),
            )
            actors_cur = conn.execute(
                "SELECT * FROM actors WHERE idempotency_key LIKE ? ESCAPE '\\'",
                (team_run_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + ":%",),
            )
            columns = [description[0] for description in actors_cur.description]
            actors = [dict(zip(columns, actor)) for actor in actors_cur.fetchall()]
            worker_pid = row[1]

    # Actor cancellation emits lifecycle events and therefore must run outside
    # the transaction/lock held above.
    from atlas_runtime import actor_service  # noqa: PLC0415
    from atlas_runtime.actor_worker import terminate_actor_pids  # noqa: PLC0415

    transitioned: list[dict[str, Any]] = []
    for actor in actors:
        transitioned.extend(actor_service.cancel_actor(conn, lock, actor["id"]))
    terminate_actor_pids(transitioned)

    child_run_ids = {
        actor["child_run_id"] for actor in actors if actor.get("child_run_id")
    }
    with lock:
        with conn:
            for child_run_id in child_run_ids:
                child = conn.execute(
                    "SELECT mission_id FROM runs WHERE id=? AND status='running'",
                    (child_run_id,),
                ).fetchone()
                if child is None:
                    continue
                conn.execute(
                    "UPDATE runs SET status='cancelled', finished_at=? WHERE id=?",
                    (now, child_run_id),
                )
                if child[0]:
                    conn.execute(
                        "UPDATE missions SET status='cancelled', updated_at=? WHERE id=?",
                        (now, child[0]),
                    )

    termination_requested = True
    if worker_pid and int(worker_pid) != os.getpid():
        termination_requested = _terminate_process_tree(int(worker_pid))

    deadline = time.monotonic() + 1.0
    worker_alive = bool(worker_pid and int(worker_pid) != os.getpid() and _pid_alive(int(worker_pid)))
    while worker_alive and time.monotonic() < deadline:
        time.sleep(0.05)
        worker_alive = _pid_alive(int(worker_pid))

    live_actor_count = conn.execute(
        "SELECT COUNT(*) FROM actors WHERE idempotency_key LIKE ? ESCAPE '\\'"
        " AND status IN ('queued','running')",
        (team_run_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + ":%",),
    ).fetchone()[0]
    live_child_count = 0
    if child_run_ids:
        placeholders = ",".join("?" for _ in child_run_ids)
        live_child_count = conn.execute(
            f"SELECT COUNT(*) FROM runs WHERE id IN ({placeholders})"  # noqa: S608
            " AND status='running'",
            tuple(child_run_ids),
        ).fetchone()[0]

    if live_actor_count == 0 and live_child_count == 0 and not worker_alive:
        cleanup_status, cleanup_error = "complete", None
    elif termination_requested:
        cleanup_status = "partial"
        cleanup_error = (
            f"cleanup incomplete: actors={live_actor_count},"
            f" child_runs={live_child_count}, worker_alive={worker_alive}"
        )
    else:
        cleanup_status = "failed"
        cleanup_error = "process-tree termination request failed"

    with lock:
        with conn:
            conn.execute(
                "UPDATE team_runs SET cleanup_status=?, cleanup_error=?, updated_at=?"
                " WHERE id=?",
                (cleanup_status, cleanup_error, _now(), team_run_id),
            )
    return changed


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
    stored_content = _lossless_team_content(conn, team_run_id, cleaned)
    now = _now()
    with lock:
        with conn:
            status = conn.execute(
                "SELECT status FROM team_runs WHERE id=?", (team_run_id,)
            ).fetchone()
            if status is None:
                raise ValueError(f"team run {team_run_id!r} not found")
            if status[0] == "cancelled":
                raise TeamRunCancelledError(
                    f"team run {team_run_id!r} was cancelled before append"
                )
            if status[0] not in ACTIVE_STATUSES:
                raise ValueError(f"cannot append to team run in state {status[0]!r}")
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
                    sender_role, resolved_target, stored_content, now,
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
    "record_worker_pid",
    "cancellation_requested",
    "set_current_round",
    "finish_team_run",
    "cancel_team_run",
    "append_message",
    "list_messages",
    "build_inbox",
    "render_inbox",
    "TeamRunCancelledError",
]
