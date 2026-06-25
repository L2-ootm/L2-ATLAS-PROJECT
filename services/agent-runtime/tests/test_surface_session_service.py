"""Tests for surface_session_service — lifecycle state machine, SQL side effects,
and audit emission (SURF-01, AUD-01, plan 10.3-01).
"""
import sqlite3
import threading

import pytest

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


# ---------------------------------------------------------------------------
# create / get / list
# ---------------------------------------------------------------------------


def test_create_session_persists_all_surf01_fields(db, lock) -> None:
    s = _create(db, lock)
    row = db.execute(
        "SELECT surface_kind, surface_session_id, workspace_kind, workspace_root, "
        "agent, model_provider, model_id, permission_mode, prompt_version, "
        "tool_catalog_version, context_policy_version, state FROM surface_sessions WHERE id=?",
        (s.id,),
    ).fetchone()
    assert row == (
        "cli", "surf-1", "global", "/tmp/atlas",
        "atlas", "anthropic", "claude-opus-4", "ask", "1.0.0",
        "1.0.0", "1.0.0", "starting",
    )


def test_create_session_returns_validated_model(db, lock) -> None:
    s = _create(db, lock)
    assert isinstance(s, SurfaceSession)
    assert s.state == "starting"


def test_create_session_emits_started_audit_with_session_id(db, lock) -> None:
    s = _create(db, lock)
    row = db.execute(
        "SELECT event_type, session_id FROM audit_events "
        "WHERE event_type='surface_session_started' AND session_id=?",
        (s.id,),
    ).fetchone()
    assert row is not None
    assert row == ("surface_session_started", s.id)


def test_get_session_returns_persisted_model(db, lock) -> None:
    s = _create(db, lock)
    got = svc.get_session(db, s.id)
    assert got is not None
    assert got.id == s.id
    assert got.surface.kind == "cli"
    assert got.workspace.root == "/tmp/atlas"
    assert got.model.provider == "anthropic"


def test_get_session_missing_returns_none(db, lock) -> None:
    assert svc.get_session(db, "nope") is None


def test_list_sessions_returns_inserted(db, lock) -> None:
    a = _create(db, lock)
    b = _create(db, lock, surface=SurfaceIdentity(kind="tui", session_id="surf-2"))
    ids = {s.id for s in svc.list_sessions(db)}
    assert {a.id, b.id}.issubset(ids)


# ---------------------------------------------------------------------------
# transitions
# ---------------------------------------------------------------------------


def test_legal_transition_chain(db, lock) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    svc.transition_session(db, lock, s.id, "suspended")
    svc.transition_session(db, lock, s.id, "resuming")
    svc.transition_session(db, lock, s.id, "active")
    assert svc.get_session(db, s.id).state == "active"


def test_illegal_jump_raises(db, lock) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    svc.transition_session(db, lock, s.id, "completed")
    # completed is terminal — completed->active must be rejected by the table guard
    with pytest.raises(ValueError):
        svc.transition_session(db, lock, s.id, "active")


def test_transition_missing_session_raises(db, lock) -> None:
    with pytest.raises(ValueError):
        svc.transition_session(db, lock, "nope", "active")


def test_cooperative_cancel_terminates_completed(db, lock) -> None:
    """SURF-06 alignment: cancelling->completed is the clean terminal; there is
    no `cancelled` session state."""
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    svc.transition_session(db, lock, s.id, "cancelling")
    svc.transition_session(db, lock, s.id, "completed")
    assert svc.get_session(db, s.id).state == "completed"


def test_cancelling_to_active_rejected(db, lock) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    svc.transition_session(db, lock, s.id, "cancelling")
    with pytest.raises(ValueError):
        svc.transition_session(db, lock, s.id, "active")


def test_cancelling_to_failed_allowed(db, lock) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    svc.transition_session(db, lock, s.id, "cancelling")
    svc.transition_session(db, lock, s.id, "failed")
    assert svc.get_session(db, s.id).state == "failed"


def test_every_transition_emits_one_audit_event(db, lock) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    svc.transition_session(db, lock, s.id, "suspended")
    rows = db.execute(
        "SELECT event_type FROM audit_events WHERE session_id=? "
        "AND event_type LIKE 'surface_session_%' ORDER BY timestamp ASC",
        (s.id,),
    ).fetchall()
    types = [r[0] for r in rows]
    # started + resumed(active) + suspended
    assert "surface_session_started" in types
    assert "surface_session_resumed" in types  # transition INTO active
    assert "surface_session_suspended" in types


def test_transition_audit_carries_session_id(db, lock) -> None:
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    row = db.execute(
        "SELECT session_id FROM audit_events "
        "WHERE event_type LIKE 'surface_session_%' AND session_id=? LIMIT 1",
        (s.id,),
    ).fetchone()
    assert row is not None and row[0] == s.id


def test_terminal_immutability_enforced_by_db(db, lock) -> None:
    """Once a row is terminal the DB trigger blocks any further UPDATE, so a
    service transition out of a terminal state raises (guard) and the row cannot
    be mutated even by a raw UPDATE."""
    s = _create(db, lock)
    svc.transition_session(db, lock, s.id, "active")
    svc.transition_session(db, lock, s.id, "completed")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE surface_sessions SET state='active' WHERE id=?", (s.id,))


def test_surface_session_fixture_yields_starting_row(db, surface_session) -> None:
    row = db.execute(
        "SELECT state FROM surface_sessions WHERE id=?", (surface_session,)
    ).fetchone()
    assert row is not None and row[0] == "starting"
