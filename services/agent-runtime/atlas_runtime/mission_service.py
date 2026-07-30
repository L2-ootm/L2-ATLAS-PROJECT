"""ATLAS mission service — create_mission, get_mission, list_missions.

Implements the mission CRUD layer for the Phase 5 mission state machine.
References:
  - D-002: Audit-first runtime — every state transition emits an AuditEvent.
  - D-003: SQLite/WAL is the datastore — all mission state persisted there.

All mutations go through the service layer. No raw SQL from CLI or tests.
Lock injection pattern follows Phase 4 audit_service.py conventions.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
from typing import Optional

from atlas_core.schemas.core import Mission

OPERATOR_RUN_ID = "operator"

# Retention ownership is deliberately centralized here. Any migration that adds
# an FK into one of RETENTION_FK_ROOTS must extend this matrix and the populated
# purge fixture before it can ship.
RETENTION_FK_ROOTS = frozenset(
    {"actors", "audit_events", "missions", "runs", "surface_sessions", "team_runs"}
)
RETENTION_FK_POLICY = {
    ("actor_deliveries", "actor_id", "actors"): "explicit-delete",
    ("actor_steering", "actor_id", "actors"): "explicit-delete",
    ("actors", "parent_run_id", "runs"): "explicit-delete",
    ("agent_contract_snapshots", "run_id", "runs"): "cascade",
    ("artifacts", "audit_event_id", "audit_events"): "explicit-delete",
    ("artifacts", "run_id", "runs"): "explicit-delete",
    ("audit_events", "run_id", "runs"): "explicit-delete",
    ("compaction_artifacts", "surface_session_id", "surface_sessions"): "retained",
    ("evidence_change_sets", "run_id", "runs"): "cascade",
    ("evidence_full_results", "run_id", "runs"): "cascade",
    ("memory_provenance", "audit_event_id", "audit_events"): "set-null",
    ("mission_archive", "mission_id", "missions"): "cascade",
    ("mission_compressions", "mission_id", "missions"): "explicit-delete",
    ("mission_loops", "mission_id", "missions"): "explicit-delete",
    ("run_judgements", "mission_id", "missions"): "explicit-delete",
    ("run_judgements", "run_id", "runs"): "explicit-delete",
    ("runs", "mission_id", "missions"): "explicit-delete",
    ("session_messages", "run_id", "runs"): "set-null",
    ("session_messages", "surface_session_id", "surface_sessions"): "retained",
    ("team_chat_messages", "team_run_id", "team_runs"): "explicit-delete",
    ("team_runs", "mission_id", "missions"): "explicit-delete",
    ("team_runs", "parent_run_id", "runs"): "explicit-delete",
    ("tool_calls", "audit_event_id", "audit_events"): "explicit-delete",
    ("tool_calls", "run_id", "runs"): "explicit-delete",
}
RETENTION_SOFT_OWNERSHIP_POLICY = {
    # Actor work executes as its own mission/run graph. This intentionally soft
    # link must be traversed before the actor row (the only ownership evidence)
    # is deleted.
    ("actors", "child_run_id", "runs"): "recursive-delete",
}


class RetentionBlockedError(RuntimeError):
    """A retention candidate still owns live work and cannot be deleted safely."""


def _delete_retention_owned_mission_graph(
    conn: sqlite3.Connection,
    mission_id: str,
    *,
    visited_mission_ids: set[str],
) -> None:
    """Apply the child-first mission retention policy inside the caller's transaction.

    Conversation messages and compaction artifacts are durable history. Their
    surface session survives and message run ownership is detached. Empty
    sessions that have no remaining run or history ownership are removed.
    Terminal actors transfer retention ownership to their soft-linked child
    mission/run graph. A queued/running actor blocks the whole purge transaction.
    """
    if mission_id in visited_mission_ids:
        return
    visited_mission_ids.add(mission_id)

    run_rows = conn.execute(
        "SELECT id, session_id FROM runs WHERE mission_id=?", (mission_id,)
    ).fetchall()
    run_ids = [row[0] for row in run_rows]
    session_ids = {row[1] for row in run_rows if row[1]}
    session_ids.update(
        row[0]
        for row in conn.execute(
            "SELECT id FROM surface_sessions WHERE mission_id=? "
            "OR run_id IN (SELECT id FROM runs WHERE mission_id=?)",
            (mission_id, mission_id),
        ).fetchall()
    )

    # Team and actor execution graphs must be removed child-first.
    team_run_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM team_runs WHERE mission_id=? "
            "OR parent_run_id IN (SELECT id FROM runs WHERE mission_id=?)",
            (mission_id, mission_id),
        ).fetchall()
    ]
    for team_run_id in team_run_ids:
        conn.execute(
            "DELETE FROM team_chat_messages WHERE team_run_id=?", (team_run_id,)
        )
    conn.execute(
        "DELETE FROM team_runs WHERE mission_id=? "
        "OR parent_run_id IN (SELECT id FROM runs WHERE mission_id=?)",
        (mission_id, mission_id),
    )

    for run_id in run_ids:
        session_ids.update(
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT surface_session_id FROM session_messages WHERE run_id=?",
                (run_id,),
            ).fetchall()
        )
        actor_rows = conn.execute(
            "SELECT id, status, child_run_id FROM actors WHERE parent_run_id=?",
            (run_id,),
        ).fetchall()
        live_actor_ids = [
            actor_id
            for actor_id, status, _child_run_id in actor_rows
            if status in {"queued", "running"}
        ]
        if live_actor_ids:
            raise RetentionBlockedError(
                f"mission {mission_id!r} still owns live actors: "
                f"{', '.join(sorted(live_actor_ids))}"
            )

        child_mission_ids: list[str] = []
        for _actor_id, _status, child_run_id in actor_rows:
            if not child_run_id:
                continue
            child = conn.execute(
                "SELECT mission_id FROM runs WHERE id=?", (child_run_id,)
            ).fetchone()
            if child is not None:
                child_mission_ids.append(child[0])
        for child_mission_id in child_mission_ids:
            _delete_retention_owned_mission_graph(
                conn,
                child_mission_id,
                visited_mission_ids=visited_mission_ids,
            )

        for actor_id, _status, _child_run_id in actor_rows:
            conn.execute("DELETE FROM actor_deliveries WHERE actor_id=?", (actor_id,))
            conn.execute("DELETE FROM actor_steering WHERE actor_id=?", (actor_id,))
        conn.execute("DELETE FROM actors WHERE parent_run_id=?", (run_id,))

        # Preserve transcript/compiled knowledge while removing references to
        # raw execution history that is about to disappear.
        conn.execute("UPDATE session_messages SET run_id=NULL WHERE run_id=?", (run_id,))
        conn.execute("UPDATE observations SET run_id=NULL WHERE run_id=?", (run_id,))
        conn.execute(
            "UPDATE sources SET ingested_by_run_id=NULL WHERE ingested_by_run_id=?",
            (run_id,),
        )
        conn.execute(
            "UPDATE memory_provenance SET run_id=NULL, audit_event_id=NULL "
            "WHERE run_id=? OR audit_event_id IN "
            "(SELECT id FROM audit_events WHERE run_id=?)",
            (run_id, run_id),
        )

        # Delete raw execution dependencies before audit events and runs.
        conn.execute("DELETE FROM tool_approvals WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM discord_approvals WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM tool_calls WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM artifacts WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM run_judgements WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM agent_contract_snapshots WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM audit_events WHERE run_id=?", (run_id,))

    conn.execute("DELETE FROM mission_compressions WHERE mission_id=?", (mission_id,))
    conn.execute("DELETE FROM mission_loops WHERE mission_id=?", (mission_id,))
    conn.execute("DELETE FROM run_judgements WHERE mission_id=?", (mission_id,))
    conn.execute("DELETE FROM runs WHERE mission_id=?", (mission_id,))

    # A retained session owns messages/compaction history. A session with no
    # remaining run or history ownership is disposable, together with its
    # soft-referenced permission state.
    for session_id in session_ids:
        is_owned = conn.execute(
            "SELECT "
            "EXISTS(SELECT 1 FROM runs WHERE session_id=?), "
            "EXISTS(SELECT 1 FROM session_messages WHERE surface_session_id=?), "
            "EXISTS(SELECT 1 FROM compaction_artifacts WHERE surface_session_id=?)",
            (session_id, session_id, session_id),
        ).fetchone()
        if is_owned and not any(is_owned):
            conn.execute(
                "DELETE FROM tool_approvals WHERE surface_session_id=?", (session_id,)
            )
            conn.execute(
                "DELETE FROM approval_channels WHERE surface_session_id=?", (session_id,)
            )
            conn.execute(
                "DELETE FROM session_allow_rules WHERE surface_session_id=?", (session_id,)
            )
            conn.execute("DELETE FROM surface_sessions WHERE id=?", (session_id,))

    conn.execute("DELETE FROM mission_archive WHERE mission_id=?", (mission_id,))
    conn.execute("DELETE FROM missions WHERE id=?", (mission_id,))


def _assert_retention_fk_integrity(conn: sqlite3.Connection) -> None:
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise sqlite3.IntegrityError(
            f"retention purge left foreign-key violations: {violations!r}"
        )


def ensure_operator_run(conn: sqlite3.Connection, lock: threading.Lock) -> str:
    """Idempotently create the synthetic operator mission/run pair; return its id.

    Operator-initiated writes (wiki edits, gated Discord actions, …) carry
    run_id="operator", but audit_events.run_id is NOT NULL REFERENCES runs(id).
    On a fresh database no such run exists, so the write would fail the FK check.
    Bootstrap the pseudo-run lazily rather than relaxing the schema — the audit
    chain stays referentially intact. Mirrors the wiki-runtime precedent.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO missions"
                    "(id, title, intent, status, project, origin, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        OPERATOR_RUN_ID,
                        "Operator console",
                        "Synthetic mission for operator-initiated writes outside agent runs",
                        "archived",
                        "",
                        "system",
                        now,
                        now,
                    ),
                )
            except sqlite3.OperationalError as exc:
                # Pre-0024 DB pending migration: write without origin rather than
                # failing the operator action (0024 backfills it later).
                if "origin" not in str(exc):
                    raise
                conn.execute(
                    "INSERT OR IGNORE INTO missions"
                    "(id, title, intent, status, project, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        OPERATOR_RUN_ID,
                        "Operator console",
                        "Synthetic mission for operator-initiated writes outside agent runs",
                        "archived",
                        "",
                        now,
                        now,
                    ),
                )
            conn.execute(
                "INSERT OR IGNORE INTO runs(id, mission_id, session_id, status, started_at, summary) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    OPERATOR_RUN_ID,
                    OPERATOR_RUN_ID,
                    OPERATOR_RUN_ID,
                    "completed",
                    now,
                    "Synthetic run recording operator-initiated writes",
                ),
            )
    return OPERATOR_RUN_ID


def create_mission(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    title: str,
    intent: str = "",
    project: str = "",
    project_id: Optional[str] = None,
    origin: str = "operator",
    mission_id: Optional[str] = None,
) -> Mission:
    """Insert a new Mission row and return the constructed Mission.

    Pydantic-first write guard: constructs Mission model before any SQL.
    ValidationError propagates before any DB write if inputs are invalid.

    If project_id is given it must reference an existing project (folder-backed
    working directory); a ValueError is raised before any write otherwise.

    `origin` records authorship: 'operator' for deliberate missions, 'chat' for
    per-prompt wrappers, 'system' for machine-created internals (0024).
    """
    # Pydantic-first: construct and validate before any SQL
    mission_kwargs = {
        "title": title,
        "intent": intent,
        "project": project,
        "project_id": project_id,
        "origin": origin,
    }
    if mission_id is not None:
        mission_kwargs["id"] = mission_id
    mission = Mission(**mission_kwargs)
    row = mission.model_dump()

    with lock:
        with conn:
            existing_cur = conn.execute(
                "SELECT * FROM missions WHERE id=?", (mission.id,)
            )
            existing_row = existing_cur.fetchone()
            if existing_row is not None:
                existing = Mission(
                    **dict(zip((d[0] for d in existing_cur.description), existing_row))
                )
                if mission_id is None or (
                    existing.title != mission.title
                    or existing.intent != mission.intent
                    or existing.project != mission.project
                    or existing.project_id != mission.project_id
                    or existing.origin != mission.origin
                ):
                    raise ValueError(f"Mission id collision for {mission.id!r}")
                return existing
            if mission.project_id is not None:
                exists = conn.execute(
                    "SELECT 1 FROM projects WHERE id=?", (mission.project_id,)
                ).fetchone()
                if exists is None:
                    raise ValueError(f"unknown project_id: {mission.project_id}")
            try:
                conn.execute(
                    "INSERT INTO missions"
                    "(id, title, intent, status, project, project_id, origin, created_at, updated_at) "
                    "VALUES (:id, :title, :intent, :status, :project, :project_id, :origin, "
                    ":created_at, :updated_at)",
                    row,
                )
            except sqlite3.OperationalError as exc:
                # Pre-0024 DB pending migration: insert without origin so the
                # mission is not lost; the 0024 backfill classifies it later.
                if "origin" not in str(exc):
                    raise
                conn.execute(
                    "INSERT INTO missions"
                    "(id, title, intent, status, project, project_id, created_at, updated_at) "
                    "VALUES (:id, :title, :intent, :status, :project, :project_id, "
                    ":created_at, :updated_at)",
                    row,
                )

    return mission


def update_mission(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
    title: Optional[str] = None,
    intent: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Mission:
    """Update a pending/failed/cancelled mission's fields.

    Only missions in terminal-but-reopenable states can be edited.
    Running/succeeded/archived missions are immutable.
    """
    editable_statuses = {"pending", "failed", "cancelled"}
    updates = []
    params = []

    if title is not None:
        if not title.strip():
            raise ValueError("title cannot be empty")
        updates.append("title=?")
        params.append(title.strip())
    if intent is not None:
        updates.append("intent=?")
        params.append(intent.strip())
    if project_id is not None:
        updates.append("project_id=?")
        params.append(project_id if project_id else None)

    if not updates:
        raise ValueError("at least one field (title, intent, project_id) must be provided")

    updates.append("updated_at=?")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    params.append(now)
    params.append(mission_id)

    with lock:
        with conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id=?", (mission_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Mission {mission_id!r} not found")
            status = str(row[0]).lower()
            if status not in editable_statuses:
                raise ValueError(
                    f"Cannot edit mission in state {row[0]!r} "
                    "(only pending, failed, or cancelled missions can be edited)"
                )
            if project_id is not None and project_id:
                exists = conn.execute(
                    "SELECT 1 FROM projects WHERE id=?", (project_id,)
                ).fetchone()
                if exists is None:
                    raise ValueError(f"unknown project_id: {project_id}")
            sql = f"UPDATE missions SET {', '.join(updates)} WHERE id=?"
            conn.execute(sql, params)

    mission = get_mission(conn, mission_id)
    if mission is None:
        raise ValueError(f"Mission {mission_id!r} not found after update")
    return mission


def get_mission(
    conn: sqlite3.Connection,
    mission_id: str,
) -> Optional[Mission]:
    """Return the Mission for the given id, or None if not found."""
    cursor = conn.execute(
        "SELECT * FROM missions WHERE id=?",
        (mission_id,),
    )
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    if row is None:
        return None
    return Mission(**dict(zip(cols, row)))


def list_missions(
    conn: sqlite3.Connection,
) -> list[Mission]:
    """Return all Mission rows ordered by created_at ASC."""
    cursor = conn.execute(
        "SELECT * FROM missions ORDER BY created_at ASC",
    )
    cols = [d[0] for d in cursor.description]
    return [Mission(**dict(zip(cols, row))) for row in cursor]


def archive_mission(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
    delete_after_days: int,
) -> Mission:
    """Archive a succeeded/completed mission and stamp its retention deadline.

    Archived missions remain readable until a purge sweep. Only successful
    terminal missions can be archived; pending/running/failed/cancelled missions
    keep their explicit lifecycle status.
    """
    if delete_after_days < 1:
        raise ValueError("delete_after_days must be >= 1")

    archived_at = datetime.datetime.now(datetime.timezone.utc)
    delete_after = archived_at + datetime.timedelta(days=delete_after_days)

    with lock:
        with conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id=?", (mission_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Mission {mission_id!r} not found")
            status = str(row[0]).lower()
            if status not in {"succeeded", "completed"}:
                raise ValueError(
                    f"Cannot archive mission in state {row[0]!r}"
                )
            conn.execute(
                "UPDATE missions SET status='archived', updated_at=? WHERE id=?",
                (archived_at.isoformat(), mission_id),
            )
            conn.execute(
                "INSERT INTO mission_archive(mission_id, archived_at, delete_after) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(mission_id) DO UPDATE SET "
                "archived_at=excluded.archived_at, delete_after=excluded.delete_after",
                (mission_id, archived_at.isoformat(), delete_after.isoformat()),
            )

    mission = get_mission(conn, mission_id)
    if mission is None:
        raise ValueError(f"Mission {mission_id!r} not found after archive")
    return mission


def retry_mission(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
) -> Mission:
    """Reopen a failed/cancelled mission so it can be run again, in place.

    A mission whose last run failed (or was cancelled) is otherwise terminal:
    ``start_run`` requires a ``pending`` mission. This reopens it by cycling the
    status ``failed|cancelled -> pending`` so the normal run path applies again.

    Prior ``runs`` rows are left untouched — they remain attached as attempt
    history (the compounding-loop provenance of earlier failures). No audit is
    emitted here; the subsequent ``start_run`` records the ``started`` transition.
    Mirrors ``archive_mission``'s atomic guarded-UPDATE shape.
    """
    with lock:
        with conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id=?", (mission_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Mission {mission_id!r} not found")
            status = str(row[0]).lower()
            if status not in {"failed", "cancelled"}:
                raise ValueError(
                    f"Cannot retry mission in state {row[0]!r} "
                    "(only failed or cancelled missions can be retried)"
                )
            updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute(
                "UPDATE missions SET status='pending', updated_at=? WHERE id=?",
                (updated_at, mission_id),
            )

    mission = get_mission(conn, mission_id)
    if mission is None:
        raise ValueError(f"Mission {mission_id!r} not found after retry")
    return mission


def purge_expired_archives(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    now: Optional[str] = None,
) -> int:
    """Delete archived missions whose retention deadline has passed.

    SQLite foreign keys in the early schema do not cascade from missions to runs,
    so dependent raw evidence is removed explicitly and compact knowledge records
    are detached from the deleted run. The purge is scoped only to rows present
    in mission_archive and status='archived'.
    """
    now_iso = now or datetime.datetime.now(datetime.timezone.utc).isoformat()

    with lock:
        with conn:
            rows = conn.execute(
                "SELECT mission_id FROM mission_archive "
                "WHERE delete_after <= ? "
                "AND mission_id IN (SELECT id FROM missions WHERE status='archived')",
                (now_iso,),
            ).fetchall()
            mission_ids = [row[0] for row in rows]
            visited_mission_ids: set[str] = set()
            for mission_id in mission_ids:
                _delete_retention_owned_mission_graph(
                    conn,
                    mission_id,
                    visited_mission_ids=visited_mission_ids,
                )
            _assert_retention_fk_integrity(conn)
    return len(mission_ids)
