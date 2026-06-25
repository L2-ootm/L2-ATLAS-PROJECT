"""Heartbeat liveness + startup reconciliation sweep (SURF-05, AUD-01, plan 10.3-04).

The sweep guarantees no unowned running session or run survives a restart, without
falsely reclaiming live (fresh-heartbeat) work, using stdlib owner-token/TTL liveness
(never os.kill — broken on Windows).
"""
import datetime
import uuid

from atlas_runtime import surface_session_service as svc


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _insert_mission_run(db, *, session_id, status="running"):
    mid = str(uuid.uuid4())
    rid = str(uuid.uuid4())
    now = _now().isoformat()
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (mid, "m", "", "running", "", now, now),
    )
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?,?,?,?,?,?,?)",
        (rid, mid, session_id, status, now, None, ""),
    )
    db.commit()
    return mid, rid


def _insert_session(db, *, state="active", heartbeat_at, run_id=None):
    sid = str(uuid.uuid4())
    now = _now().isoformat()
    db.execute(
        "INSERT INTO surface_sessions"
        "(id, surface_kind, surface_session_id, workspace_kind, workspace_root, run_id, "
        "agent, model_provider, model_id, permission_mode, prompt_version, "
        "tool_catalog_version, context_policy_version, state, heartbeat_at, "
        "created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            sid, "cli", "surf", "global", "/tmp/atlas", run_id,
            "atlas", "anthropic", "claude-opus-4", "ask", "1.0.0",
            "1.0.0", "1.0.0", state, heartbeat_at, now, now,
        ),
    )
    db.commit()
    return sid


def test_heartbeat_refreshes_active_session(db, lock) -> None:
    old = (_now() - datetime.timedelta(hours=1)).isoformat()
    sid = _insert_session(db, state="active", heartbeat_at=old)
    svc.heartbeat(db, lock, sid)
    hb = db.execute(
        "SELECT heartbeat_at FROM surface_sessions WHERE id=?", (sid,)
    ).fetchone()[0]
    assert hb > old


def test_stale_session_reclaimed_with_run_and_audit(db, lock) -> None:
    stale = (_now() - datetime.timedelta(hours=1)).isoformat()
    sid = _insert_session(db, state="active", heartbeat_at=stale)
    _, rid = _insert_mission_run(db, session_id=sid, status="running")

    reclaimed = svc.reconcile_orphans(db, lock, ttl_seconds=60)

    assert sid in reclaimed
    assert svc.get_session(db, sid).state == "reclaimed"
    run_status = db.execute("SELECT status FROM runs WHERE id=?", (rid,)).fetchone()[0]
    assert run_status == "cancelled"
    audit = db.execute(
        "SELECT 1 FROM audit_events WHERE event_type='surface_session_reclaimed' AND session_id=?",
        (sid,),
    ).fetchone()
    assert audit is not None


def test_fresh_session_not_reclaimed(db, lock) -> None:
    fresh = _now().isoformat()
    sid = _insert_session(db, state="active", heartbeat_at=fresh)
    _, rid = _insert_mission_run(db, session_id=sid, status="running")

    reclaimed = svc.reconcile_orphans(db, lock, ttl_seconds=60)

    assert sid not in reclaimed
    assert svc.get_session(db, sid).state == "active"
    # live work protected: a fresh session's running run is NOT cancelled
    assert db.execute("SELECT status FROM runs WHERE id=?", (rid,)).fetchone()[0] == "running"


def test_orphan_running_run_with_no_session_cancelled(db, lock) -> None:
    _, rid = _insert_mission_run(db, session_id=None, status="running")
    svc.reconcile_orphans(db, lock, ttl_seconds=60)
    assert db.execute("SELECT status FROM runs WHERE id=?", (rid,)).fetchone()[0] == "cancelled"


def test_sweep_is_idempotent(db, lock) -> None:
    stale = (_now() - datetime.timedelta(hours=1)).isoformat()
    sid = _insert_session(db, state="active", heartbeat_at=stale)
    _insert_mission_run(db, session_id=sid, status="running")

    first = svc.reconcile_orphans(db, lock, ttl_seconds=60)
    second = svc.reconcile_orphans(db, lock, ttl_seconds=60)

    assert sid in first
    assert second == []  # nothing left to reclaim
    assert svc.get_session(db, sid).state == "reclaimed"
