"""ATLAS goal service — the Command Center goal hierarchy (loop-engineering slice).

Focus → Goals → Tasks, plus Observations attached to goals/runs. Goals nest via
`parent_goal_id` (sub-goals). The context-assembly step walks `build_goal_tree`
to synthesize loop-engineered run instructions; the compounding loop appends
Observations (`add_observation`, source="compounding-loop") on run completion —
never mutating operator-owned goals.

Conventions follow focus_service.py:
  - Pydantic-first write guard (construct + validate before any SQL).
  - All mutations go through lock+conn atomic blocks.
  - DDL in 0010_goal_model.sql.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
from typing import Optional

from atlas_core.schemas.core import Goal, Observation, Task

_UNSET = object()


class GoalError(ValueError):
    """Raised for invalid goal/task/observation inputs (empty title, unknown id)."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _rows(cursor: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor]


def _one(cursor: sqlite3.Cursor) -> Optional[dict]:
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    return dict(zip(cols, row)) if row is not None else None


# --- Goals -------------------------------------------------------------------


def create_goal(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    title: str,
    description: str = "",
    focus_id: Optional[str] = None,
    parent_goal_id: Optional[str] = None,
    status: str = "open",
    position: int = 0,
) -> Goal:
    """Create a Goal under a Focus (and optionally a parent goal → sub-goal)."""
    if not title or not title.strip():
        raise GoalError("title must not be empty")
    goal = Goal(
        title=title,
        description=description,
        focus_id=focus_id,
        parent_goal_id=parent_goal_id,
        status=status,  # type: ignore[arg-type]
        position=position,
    )
    row = goal.model_dump()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO goals"
                "(id, focus_id, parent_goal_id, title, description, status, position, created_at, updated_at) "
                "VALUES (:id, :focus_id, :parent_goal_id, :title, :description, :status, :position, :created_at, :updated_at)",
                row,
            )
    return goal


def get_goal(conn: sqlite3.Connection, goal_id: str) -> Optional[Goal]:
    row = _one(conn.execute("SELECT * FROM goals WHERE id=?", (goal_id,)))
    return Goal(**row) if row is not None else None


def list_goals(
    conn: sqlite3.Connection,
    *,
    focus_id: Optional[str] = None,
    parent_goal_id: object = _UNSET,
    include_archived: bool = False,
) -> list[Goal]:
    """List goals, optionally scoped to a focus and/or parent. `parent_goal_id`
    accepts None (top-level goals only) when passed explicitly."""
    clauses: list[str] = []
    params: list[object] = []
    if focus_id is not None:
        clauses.append("focus_id=?")
        params.append(focus_id)
    if parent_goal_id is not _UNSET:
        if parent_goal_id is None:
            clauses.append("parent_goal_id IS NULL")
        else:
            clauses.append("parent_goal_id=?")
            params.append(parent_goal_id)
    if not include_archived:
        clauses.append("status != 'archived'")
    sql = "SELECT * FROM goals"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY position ASC, created_at ASC"
    return [Goal(**row) for row in _rows(conn.execute(sql, params))]


def update_goal(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    goal_id: str,
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    position: Optional[int] = None,
    parent_goal_id: object = _UNSET,
    focus_id: object = _UNSET,
) -> Goal:
    """Patch the provided fields of a Goal. Unset args are left unchanged."""
    sets: list[str] = []
    params: list[object] = []
    if title is not None:
        if not title.strip():
            raise GoalError("title must not be empty")
        sets.append("title=?")
        params.append(title.strip())
    if description is not None:
        sets.append("description=?")
        params.append(description)
    if status is not None:
        if status not in ("open", "active", "paused", "done", "archived"):
            raise GoalError(f"invalid status {status!r}")
        sets.append("status=?")
        params.append(status)
    if position is not None:
        sets.append("position=?")
        params.append(position)
    if parent_goal_id is not _UNSET:
        sets.append("parent_goal_id=?")
        params.append(parent_goal_id)
    if focus_id is not _UNSET:
        sets.append("focus_id=?")
        params.append(focus_id)

    if not sets:
        existing = get_goal(conn, goal_id)
        if existing is None:
            raise GoalError(f"goal {goal_id!r} not found")
        return existing

    sets.append("updated_at=?")
    params.append(_now())
    params.append(goal_id)
    with lock:
        with conn:
            cursor = conn.execute(f"UPDATE goals SET {', '.join(sets)} WHERE id=?", params)
            if cursor.rowcount == 0:
                raise GoalError(f"goal {goal_id!r} not found")
    updated = get_goal(conn, goal_id)
    assert updated is not None
    return updated


def archive_goal(conn: sqlite3.Connection, lock: threading.Lock, goal_id: str) -> None:
    """Archive a goal and its descendant sub-goals (status -> archived)."""
    with lock:
        with conn:
            ids = _collect_subtree(conn, goal_id)
            if not ids:
                raise GoalError(f"goal {goal_id!r} not found")
            now = _now()
            conn.executemany(
                "UPDATE goals SET status='archived', updated_at=? WHERE id=?",
                [(now, gid) for gid in ids],
            )


def delete_goal(conn: sqlite3.Connection, lock: threading.Lock, goal_id: str) -> int:
    """Hard-delete a goal and its descendant sub-goals.

    Tasks under the deleted goals are removed with them; observations are
    detached (goal_id -> NULL) rather than deleted so run provenance and the
    compounding loop's learned findings survive. Returns the number of goals
    deleted. Idempotent at the API layer: deleting an unknown id raises
    GoalError so callers can distinguish "already gone" from success.
    """
    with lock:
        with conn:
            ids = _collect_subtree(conn, goal_id)
            if not ids:
                raise GoalError(f"goal {goal_id!r} not found")
            conn.executemany("DELETE FROM tasks WHERE goal_id=?", [(gid,) for gid in ids])
            conn.executemany(
                "UPDATE observations SET goal_id=NULL WHERE goal_id=?",
                [(gid,) for gid in ids],
            )
            conn.executemany("DELETE FROM goals WHERE id=?", [(gid,) for gid in ids])
    return len(ids)


def _collect_subtree(conn: sqlite3.Connection, goal_id: str) -> list[str]:
    """Return goal_id plus all descendant goal ids (BFS). Empty if id unknown."""
    if conn.execute("SELECT 1 FROM goals WHERE id=?", (goal_id,)).fetchone() is None:
        return []
    collected = [goal_id]
    frontier = [goal_id]
    while frontier:
        nxt: list[str] = []
        for gid in frontier:
            for (child_id,) in conn.execute(
                "SELECT id FROM goals WHERE parent_goal_id=?", (gid,)
            ).fetchall():
                collected.append(child_id)
                nxt.append(child_id)
        frontier = nxt
    return collected


# --- Tasks -------------------------------------------------------------------


def create_task(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    goal_id: str,
    title: str,
    status: str = "todo",
    position: int = 0,
) -> Task:
    if not title or not title.strip():
        raise GoalError("title must not be empty")
    task = Task(goal_id=goal_id, title=title, status=status, position=position)  # type: ignore[arg-type]
    row = task.model_dump()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO tasks(id, goal_id, title, status, position, created_at, updated_at) "
                "VALUES (:id, :goal_id, :title, :status, :position, :created_at, :updated_at)",
                row,
            )
    return task


def list_tasks(conn: sqlite3.Connection, *, goal_id: str) -> list[Task]:
    return [
        Task(**row)
        for row in _rows(
            conn.execute(
                "SELECT * FROM tasks WHERE goal_id=? ORDER BY position ASC, created_at ASC",
                (goal_id,),
            )
        )
    ]


def set_task_status(
    conn: sqlite3.Connection, lock: threading.Lock, task_id: str, status: str
) -> Task:
    if status not in ("todo", "doing", "done"):
        raise GoalError(f"invalid status {status!r}")
    with lock:
        with conn:
            cursor = conn.execute(
                "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
                (status, _now(), task_id),
            )
            if cursor.rowcount == 0:
                raise GoalError(f"task {task_id!r} not found")
    row = _one(conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)))
    assert row is not None
    return Task(**row)


# --- Observations ------------------------------------------------------------


def add_observation(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    body: str,
    goal_id: Optional[str] = None,
    run_id: Optional[str] = None,
    source: str = "operator",
) -> Observation:
    """Append a provenance-tracked observation. Used by the operator and by the
    compounding loop (source='compounding-loop')."""
    if not body or not body.strip():
        raise GoalError("body must not be empty")
    obs = Observation(body=body, goal_id=goal_id, run_id=run_id, source=source)
    row = obs.model_dump()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO observations(id, goal_id, run_id, body, source, created_at) "
                "VALUES (:id, :goal_id, :run_id, :body, :source, :created_at)",
                row,
            )
    return obs


def list_observations(
    conn: sqlite3.Connection,
    *,
    goal_id: Optional[str] = None,
    run_id: Optional[str] = None,
    limit: int = 50,
) -> list[Observation]:
    clauses: list[str] = []
    params: list[object] = []
    if goal_id is not None:
        clauses.append("goal_id=?")
        params.append(goal_id)
    if run_id is not None:
        clauses.append("run_id=?")
        params.append(run_id)
    sql = "SELECT * FROM observations"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return [Observation(**row) for row in _rows(conn.execute(sql, params))]


# --- Tree assembly -----------------------------------------------------------


def build_goal_tree(conn: sqlite3.Connection, *, focus_id: str) -> list[dict]:
    """Return the non-archived goal forest for a focus: top-level goals each with
    nested `children`, their `tasks`, and recent `observations`. The shape the
    gateway serves and context_service synthesizes the loop brief from."""
    goals = list_goals(conn, focus_id=focus_id)
    by_parent: dict[Optional[str], list[Goal]] = {}
    for g in goals:
        by_parent.setdefault(g.parent_goal_id, []).append(g)

    def node(goal: Goal) -> dict:
        d = goal.model_dump()
        d["tasks"] = [t.model_dump() for t in list_tasks(conn, goal_id=goal.id)]
        d["observations"] = [
            o.model_dump() for o in list_observations(conn, goal_id=goal.id, limit=10)
        ]
        d["children"] = [node(child) for child in by_parent.get(goal.id, [])]
        return d

    return [node(g) for g in by_parent.get(None, [])]
