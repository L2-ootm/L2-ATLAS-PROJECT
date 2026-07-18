"""Agent presets and teams — persistent, reusable agent configuration.

Two distinct structures (docs/plans/2026-07-18-agent-teams-and-group-chat-
design.md): a preset is one reusable single-agent configuration; a team is a
named, ordered roster of presets. Both are plain CRUD over SQLite, following
the same conventions as mission_service.py (lock-serialized writes, ISO
timestamps, ValueError for caller mistakes). Runtime orchestration of a team
(spawning members, the group-chat message log) lives in team_run_service.py.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
import uuid
from typing import Any, Optional

NAME_CAP = 200
DESCRIPTION_CAP = 2000
GOAL_TEMPLATE_CAP = 4000


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    return {d[0]: row[i] for i, d in enumerate(cursor.description)}


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------


def create_preset(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    name: str,
    role_label: str,
    goal_template: str,
    description: str = "",
    model: Optional[str] = None,
    provider: Optional[str] = None,
    mode: str = "joined",
) -> dict[str, Any]:
    name = (name or "").strip()
    role_label = (role_label or "").strip()
    goal_template = (goal_template or "").strip()
    if not name:
        raise ValueError("preset name must be non-empty")
    if not role_label:
        raise ValueError("preset role_label must be non-empty")
    if not goal_template:
        raise ValueError("preset goal_template must be non-empty")
    if mode not in ("joined", "detached"):
        raise ValueError(f"invalid preset mode: {mode!r}")
    name = name[:NAME_CAP]
    preset_id = f"preset-{uuid.uuid4()}"
    now = _now()
    with lock:
        with conn:
            existing = conn.execute(
                "SELECT 1 FROM agent_presets WHERE name=?", (name,)
            ).fetchone()
            if existing is not None:
                raise ValueError(f"a preset named {name!r} already exists")
            conn.execute(
                "INSERT INTO agent_presets(id, name, role_label, description,"
                " goal_template, model, provider, mode, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    preset_id, name, role_label, description[:DESCRIPTION_CAP],
                    goal_template[:GOAL_TEMPLATE_CAP], model, provider, mode,
                    now, now,
                ),
            )
    preset = get_preset(conn, preset_id)
    assert preset is not None
    return preset


def get_preset(conn: sqlite3.Connection, preset_id: str) -> Optional[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM agent_presets WHERE id=?", (preset_id,))
    row = cur.fetchone()
    return _row_to_dict(cur, row) if row else None


def list_presets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM agent_presets ORDER BY name ASC")
    return [_row_to_dict(cur, row) for row in cur.fetchall()]


def update_preset(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    preset_id: str,
    **fields: Any,
) -> dict[str, Any]:
    allowed = {
        "name", "role_label", "description", "goal_template", "model",
        "provider", "mode",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"cannot update fields: {sorted(unknown)}")
    updates: list[str] = []
    params: list[Any] = []
    for key, value in fields.items():
        if key == "mode" and value not in ("joined", "detached"):
            raise ValueError(f"invalid preset mode: {value!r}")
        if key in ("name", "role_label", "goal_template") and not str(value or "").strip():
            raise ValueError(f"preset {key} must be non-empty")
        updates.append(f"{key}=?")
        params.append(value)
    if not updates:
        raise ValueError("at least one field must be provided")
    updates.append("updated_at=?")
    now = _now()
    params.append(now)
    params.append(preset_id)
    with lock:
        with conn:
            existing = conn.execute(
                "SELECT 1 FROM agent_presets WHERE id=?", (preset_id,)
            ).fetchone()
            if existing is None:
                raise ValueError(f"preset {preset_id!r} not found")
            conn.execute(
                f"UPDATE agent_presets SET {', '.join(updates)} WHERE id=?",  # noqa: S608
                params,
            )
    preset = get_preset(conn, preset_id)
    assert preset is not None
    return preset


def delete_preset(conn: sqlite3.Connection, lock: threading.Lock, preset_id: str) -> bool:
    """Refuses to delete a preset that is still on a team roster."""
    with lock:
        with conn:
            in_use = conn.execute(
                "SELECT 1 FROM team_members WHERE preset_id=?", (preset_id,)
            ).fetchone()
            if in_use is not None:
                raise ValueError(
                    "preset is still a member of one or more teams; remove it"
                    " from those rosters first"
                )
            cur = conn.execute("DELETE FROM agent_presets WHERE id=?", (preset_id,))
            return cur.rowcount == 1


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


def create_team(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    name: str,
    description: str = "",
) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("team name must be non-empty")
    name = name[:NAME_CAP]
    team_id = f"team-{uuid.uuid4()}"
    now = _now()
    with lock:
        with conn:
            existing = conn.execute("SELECT 1 FROM teams WHERE name=?", (name,)).fetchone()
            if existing is not None:
                raise ValueError(f"a team named {name!r} already exists")
            conn.execute(
                "INSERT INTO teams(id, name, description, created_at, updated_at)"
                " VALUES (?,?,?,?,?)",
                (team_id, name, description[:DESCRIPTION_CAP], now, now),
            )
    team = get_team(conn, team_id)
    assert team is not None
    return team


def get_team(conn: sqlite3.Connection, team_id: str) -> Optional[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM teams WHERE id=?", (team_id,))
    row = cur.fetchone()
    if row is None:
        return None
    team = _row_to_dict(cur, row)
    team["members"] = _team_members(conn, team_id)
    return team


def _team_members(conn: sqlite3.Connection, team_id: str) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT p.* FROM team_members tm JOIN agent_presets p ON p.id=tm.preset_id"
        " WHERE tm.team_id=? ORDER BY tm.position ASC",
        (team_id,),
    )
    return [_row_to_dict(cur, row) for row in cur.fetchall()]


def list_teams(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM teams ORDER BY name ASC")
    teams = [_row_to_dict(cur, row) for row in cur.fetchall()]
    for team in teams:
        team["members"] = _team_members(conn, team["id"])
    return teams


def update_team(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    team_id: str,
    **fields: Any,
) -> dict[str, Any]:
    allowed = {"name", "description"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"cannot update fields: {sorted(unknown)}")
    updates: list[str] = []
    params: list[Any] = []
    for key, value in fields.items():
        if key == "name" and not str(value or "").strip():
            raise ValueError("team name must be non-empty")
        updates.append(f"{key}=?")
        params.append(value)
    if not updates:
        raise ValueError("at least one field must be provided")
    updates.append("updated_at=?")
    now = _now()
    params.append(now)
    params.append(team_id)
    with lock:
        with conn:
            existing = conn.execute("SELECT 1 FROM teams WHERE id=?", (team_id,)).fetchone()
            if existing is None:
                raise ValueError(f"team {team_id!r} not found")
            conn.execute(
                f"UPDATE teams SET {', '.join(updates)} WHERE id=?",  # noqa: S608
                params,
            )
    team = get_team(conn, team_id)
    assert team is not None
    return team


def delete_team(conn: sqlite3.Connection, lock: threading.Lock, team_id: str) -> bool:
    with lock:
        with conn:
            in_use = conn.execute(
                "SELECT 1 FROM team_runs WHERE team_id=? AND status IN ('queued','running')",
                (team_id,),
            ).fetchone()
            if in_use is not None:
                raise ValueError("team has an active run; cancel it before deleting the team")
            conn.execute("DELETE FROM team_members WHERE team_id=?", (team_id,))
            cur = conn.execute("DELETE FROM teams WHERE id=?", (team_id,))
            return cur.rowcount == 1


def set_team_members(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    team_id: str,
    preset_ids: list[str],
) -> dict[str, Any]:
    """Replace the team's roster and ordering in one transaction."""
    if not preset_ids:
        raise ValueError("a team must have at least one member")
    if len(set(preset_ids)) != len(preset_ids):
        raise ValueError("duplicate preset_id in roster")
    with lock:
        with conn:
            team_row = conn.execute("SELECT 1 FROM teams WHERE id=?", (team_id,)).fetchone()
            if team_row is None:
                raise ValueError(f"team {team_id!r} not found")
            for preset_id in preset_ids:
                preset_row = conn.execute(
                    "SELECT 1 FROM agent_presets WHERE id=?", (preset_id,)
                ).fetchone()
                if preset_row is None:
                    raise ValueError(f"preset {preset_id!r} not found")
            conn.execute("DELETE FROM team_members WHERE team_id=?", (team_id,))
            conn.executemany(
                "INSERT INTO team_members(team_id, preset_id, position) VALUES (?,?,?)",
                [(team_id, preset_id, i) for i, preset_id in enumerate(preset_ids)],
            )
            conn.execute("UPDATE teams SET updated_at=? WHERE id=?", (_now(), team_id))
    team = get_team(conn, team_id)
    assert team is not None
    return team


__all__ = [
    "create_preset",
    "get_preset",
    "list_presets",
    "update_preset",
    "delete_preset",
    "create_team",
    "get_team",
    "list_teams",
    "update_team",
    "delete_team",
    "set_team_members",
]
