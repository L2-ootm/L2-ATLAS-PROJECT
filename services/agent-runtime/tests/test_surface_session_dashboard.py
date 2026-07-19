"""Tests for surface_session_service.list_sessions_dashboard (F11 sessions/subagent
dashboard, Phase 3 Track B): pagination, active_only filtering, actor aggregation
(counts + top-level tree), mission enrichment, and server-computed heartbeat health
at the healthy/stale/orphaned/unknown boundaries.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading

from atlas_core.schemas.agent_contract import (
    ModelIdentity,
    SurfaceIdentity,
    WorkspaceIdentity,
)
from atlas_core.schemas.surface_session import SurfaceSession
from atlas_runtime import surface_session_service as svc


def _create(db: sqlite3.Connection, lock: threading.Lock, **overrides) -> SurfaceSession:
    kwargs = dict(
        surface=SurfaceIdentity(kind="cli", session_id="surf-1"),
        workspace=WorkspaceIdentity(kind="global", root="/tmp/atlas"),
        agent="atlas",
        model=ModelIdentity(provider="anthropic", model_id="claude-opus-4"),
        permission_mode="ask",
        prompt_version="1.0.0",
        tool_catalog_version="1.0.0",
        context_policy_version="1.0.0",
    )
    kwargs.update(overrides)
    return svc.create_session(db, lock, **kwargs)


def _seed_mission(db: sqlite3.Connection, mission_id: str, title: str, intent: str) -> None:
    now = "2026-07-19T00:00:00+00:00"
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (mission_id, title, intent, "running", "", now, now),
    )
    db.commit()


def _insert_actor(
    db: sqlite3.Connection,
    *,
    actor_id: str,
    parent_run_id: str,
    session_id: str,
    status: str = "running",
    parent_actor_id: str | None = None,
    depth: int = 1,
    heartbeat_at: str | None = None,
    created_at: str | None = None,
    goal: str = "do work",
    mode: str = "joined",
    model: str = "test-model",
    role: str = "worker",
) -> None:
    """Direct-SQL actor seed (bypasses actor_service) so tests can pin exact
    heartbeat_at/created_at timestamps for TTL-boundary assertions."""
    now = created_at or "2026-07-19T00:00:00+00:00"
    db.execute(
        "INSERT INTO actors(id, parent_run_id, parent_actor_id, session_id, "
        "idempotency_key, role, goal, model, mode, status, depth, heartbeat_at, "
        "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            actor_id, parent_run_id, parent_actor_id, session_id, actor_id, role,
            goal, model, mode, status, depth, heartbeat_at, now, now,
        ),
    )
    db.commit()


# ---------------------------------------------------------------------------
# Empty / no-actor baseline
# ---------------------------------------------------------------------------


def test_dashboard_empty_list(db, lock) -> None:
    page = svc.list_sessions_dashboard(db)
    assert page == {"sessions": [], "total": 0, "limit": 50, "offset": 0}


def test_dashboard_single_session_no_actors(db, lock) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")

    page = svc.list_sessions_dashboard(db)

    assert page["total"] == 1
    entry = page["sessions"][0]
    assert entry["id"] == s.id
    assert entry["state"] == "active"
    assert entry["actor_count"] == 0
    assert entry["active_actor_count"] == 0
    assert entry["actors"] == []
    assert entry["mission_title"] is None
    assert entry["mission_intent"] is None
    assert entry["health"] == "healthy"
    assert entry["heartbeat_age_seconds"] is not None


# ---------------------------------------------------------------------------
# Actor aggregation: counts + multi-level tree (only top-level actors surface)
# ---------------------------------------------------------------------------


def test_dashboard_multi_level_actor_tree(db, lock, run_id) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # a1 (depth 1, top-level, running) -> a2 (depth 2, completed) -> a3 (depth 3, running)
    _insert_actor(
        db, actor_id="a1", parent_run_id=run_id, session_id=s.id,
        status="running", depth=1, heartbeat_at=now_iso,
    )
    _insert_actor(
        db, actor_id="a2", parent_run_id=run_id, session_id=s.id,
        status="completed", depth=2, parent_actor_id="a1", heartbeat_at=now_iso,
    )
    _insert_actor(
        db, actor_id="a3", parent_run_id=run_id, session_id=s.id,
        status="running", depth=3, parent_actor_id="a2", heartbeat_at=now_iso,
    )

    page = svc.list_sessions_dashboard(db)
    entry = page["sessions"][0]

    assert entry["actor_count"] == 3
    assert entry["active_actor_count"] == 2  # a1 + a3 running; a2 completed
    # only parent_actor_id IS NULL actors surface in the tree-row list
    assert [a["id"] for a in entry["actors"]] == ["a1"]
    assert entry["actors"][0]["status"] == "running"
    assert entry["actors"][0]["depth"] == 1


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def test_dashboard_pagination(db, lock) -> None:
    created_ids = []
    for i in range(5):
        s = _create(
            db, lock, surface=SurfaceIdentity(kind="cli", session_id=f"surf-page-{i}")
        )
        created_ids.append(s.id)

    page1 = svc.list_sessions_dashboard(db, limit=2, offset=0)
    page2 = svc.list_sessions_dashboard(db, limit=2, offset=2)
    page3 = svc.list_sessions_dashboard(db, limit=2, offset=4)

    assert page1["total"] == page2["total"] == page3["total"] == 5
    assert len(page1["sessions"]) == 2
    assert len(page2["sessions"]) == 2
    assert len(page3["sessions"]) == 1

    seen = (
        {e["id"] for e in page1["sessions"]}
        | {e["id"] for e in page2["sessions"]}
        | {e["id"] for e in page3["sessions"]}
    )
    assert seen == set(created_ids)  # every session seen exactly once across pages


def test_dashboard_limit_is_clamped(db, lock) -> None:
    _create(db, lock)
    page = svc.list_sessions_dashboard(db, limit=10_000)
    assert page["limit"] == 200  # clamped to the max


# ---------------------------------------------------------------------------
# active_only filtering
# ---------------------------------------------------------------------------


def test_dashboard_active_only_filters_terminal_sessions(db, lock) -> None:
    live = _create(db, lock, surface=SurfaceIdentity(kind="cli", session_id="surf-live"))
    svc.transition_session(db, lock, live.id, "active")

    done = _create(db, lock, surface=SurfaceIdentity(kind="cli", session_id="surf-done"))
    svc.transition_session(db, lock, done.id, "active")
    svc.transition_session(db, lock, done.id, "completed")

    page = svc.list_sessions_dashboard(db, active_only=True)

    ids = {e["id"] for e in page["sessions"]}
    assert live.id in ids
    assert done.id not in ids
    assert page["total"] == 1


def test_dashboard_active_only_keeps_non_terminal_non_active_states(db, lock) -> None:
    """`active_only` means 'still live', not literal state=='active' — a
    `starting` session (never transitioned) must still pass the filter."""
    starting = _create(db, lock)  # left in 'starting'

    page = svc.list_sessions_dashboard(db, active_only=True)

    assert starting.id in {e["id"] for e in page["sessions"]}


# ---------------------------------------------------------------------------
# Heartbeat staleness boundary (server-computed, TTL default 90s)
# ---------------------------------------------------------------------------


def test_dashboard_session_heartbeat_boundary_healthy_vs_stale(db, lock) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    now = datetime.datetime.now(datetime.timezone.utc)

    just_under = (now - datetime.timedelta(seconds=89)).isoformat()
    db.execute("UPDATE surface_sessions SET heartbeat_at=? WHERE id=?", (just_under, s.id))
    db.commit()
    page = svc.list_sessions_dashboard(db, session_ttl_seconds=90.0)
    assert page["sessions"][0]["health"] == "healthy"

    just_over = (now - datetime.timedelta(seconds=91)).isoformat()
    db.execute("UPDATE surface_sessions SET heartbeat_at=? WHERE id=?", (just_over, s.id))
    db.commit()
    page = svc.list_sessions_dashboard(db, session_ttl_seconds=90.0)
    assert page["sessions"][0]["health"] == "stale"


def test_dashboard_actor_heartbeat_boundary_healthy_vs_stale(db, lock, run_id) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    now = datetime.datetime.now(datetime.timezone.utc)

    healthy_hb = (now - datetime.timedelta(seconds=10)).isoformat()
    stale_hb = (now - datetime.timedelta(seconds=100)).isoformat()
    _insert_actor(
        db, actor_id="a-healthy", parent_run_id=run_id, session_id=s.id,
        status="running", heartbeat_at=healthy_hb,
    )
    _insert_actor(
        db, actor_id="a-stale", parent_run_id=run_id, session_id=s.id,
        status="running", heartbeat_at=stale_hb,
    )

    page = svc.list_sessions_dashboard(db, actor_ttl_seconds=90.0)
    by_id = {a["id"]: a for a in page["sessions"][0]["actors"]}

    assert by_id["a-healthy"]["health"] == "healthy"
    assert by_id["a-stale"]["health"] == "stale"


def test_dashboard_orphaned_session_after_reconciliation(db, lock) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    old_hb = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=500)
    ).isoformat()
    db.execute("UPDATE surface_sessions SET heartbeat_at=? WHERE id=?", (old_hb, s.id))
    db.commit()

    svc.reconcile_orphans(db, lock, ttl_seconds=90.0)
    page = svc.list_sessions_dashboard(db)

    entry = page["sessions"][0]
    assert entry["state"] == "reclaimed"
    assert entry["health"] == "orphaned"
    assert entry["heartbeat_age_seconds"] is None


def test_dashboard_orphaned_actor_status_reports_orphaned_health(db, lock, run_id) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    old_hb = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=500)
    ).isoformat()
    # Directly seed status='orphaned' (bypasses the terminal-immutable trigger,
    # which only guards UPDATEs, not the initial INSERT).
    _insert_actor(
        db, actor_id="a-orphaned", parent_run_id=run_id, session_id=s.id,
        status="orphaned", heartbeat_at=old_hb,
    )

    page = svc.list_sessions_dashboard(db)
    actor_entry = page["sessions"][0]["actors"][0]

    assert actor_entry["status"] == "orphaned"
    assert actor_entry["health"] == "orphaned"


def test_dashboard_completed_session_health_is_unknown(db, lock) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    svc.transition_session(db, lock, s.id, "completed")

    page = svc.list_sessions_dashboard(db)
    entry = page["sessions"][0]

    assert entry["health"] == "unknown"
    assert entry["heartbeat_age_seconds"] is None


# ---------------------------------------------------------------------------
# Mission enrichment
# ---------------------------------------------------------------------------


def test_dashboard_mission_title_and_intent_enrichment(db, lock) -> None:
    long_intent = "Investigate the sessions dashboard data model. " * 5
    _seed_mission(db, "mission-x", "Analyze codebase architecture", long_intent)
    s = _create(db, lock, mission_id="mission-x")
    svc.transition_session(db, lock, s.id, "active")

    page = svc.list_sessions_dashboard(db)
    entry = page["sessions"][0]

    assert entry["mission_title"] == "Analyze codebase architecture"
    assert entry["mission_intent"] == long_intent[:120]
    assert len(entry["mission_intent"]) == 120


def test_dashboard_missing_mission_id_yields_none_enrichment(db, lock) -> None:
    s = _create(db, lock, mission_id="mission-does-not-exist")
    svc.transition_session(db, lock, s.id, "active")

    page = svc.list_sessions_dashboard(db)
    entry = page["sessions"][0]

    assert entry["mission_title"] is None
    assert entry["mission_intent"] is None
