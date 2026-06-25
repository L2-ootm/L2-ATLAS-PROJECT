"""Surface session resume — identity preservation + fail-closed replay (SURF-05, plan 10.3-05).

Resume re-binds a suspended session to a live owner and rebuilds context by replaying the
immutable Phase 10.2 RunContractSnapshot; a version mismatch fails closed with no resume.
"""
import pytest

from atlas_core.schemas.agent_contract import (
    ModelIdentity,
    SurfaceIdentity,
    WorkspaceIdentity,
)

from atlas_runtime import surface_session_service as svc
from atlas_runtime.agent_contract_service import ContractCompatibilityError, load_contract
from atlas_runtime.agents.native import NativeAtlasAgent

from tests.test_agents import _FakeHarness, _pending_mission, _running_run


def _session_with_snapshot(db, lock, *, state="suspended", prompt_version_override=None):
    """Build a session whose run has a persisted RunContractSnapshot, in `state`."""
    mission_id = _pending_mission(db)
    run_id = _running_run(db, mission_id)
    harness = _FakeHarness(
        {"final_response": "done", "api_calls": 1, "completed": True, "failed": False, "error": None}
    )
    NativeAtlasAgent(agent_factory=lambda session_id: harness).execute(
        db, lock, mission_id=mission_id, run_id=run_id, prompt="ship it"
    )
    snap = load_contract(db, run_id)
    assert snap is not None
    session = svc.create_session(
        db, lock,
        surface=SurfaceIdentity(kind="tui", session_id="surf-x"),
        workspace=WorkspaceIdentity(kind="global", root="/tmp/atlas"),
        agent="atlas",
        model=ModelIdentity(provider="anthropic", model_id="claude-opus-4"),
        permission_mode="ask",
        prompt_version=prompt_version_override or snap.prompt_version,
        tool_catalog_version=snap.tool_catalog_version,
        context_policy_version=snap.context_policy_version,
        mission_id=mission_id,
        run_id=run_id,
    )
    # Drive into the requested state.
    svc.transition_session(db, lock, session.id, "active")
    if state == "suspended":
        svc.transition_session(db, lock, session.id, "suspended")
    elif state == "completed":
        svc.transition_session(db, lock, session.id, "completed")
    return session, snap


def test_resume_drives_to_active_and_audits(db, lock) -> None:
    session, _ = _session_with_snapshot(db, lock)
    resumed = svc.resume_session(db, lock, session.id, owner_token="owner-2")
    assert resumed.state == "active"
    assert resumed.owner_token == "owner-2"
    row = db.execute(
        "SELECT 1 FROM audit_events WHERE event_type='surface_session_resumed' AND session_id=?",
        (session.id,),
    ).fetchone()
    assert row is not None


def test_resume_preserves_identity(db, lock) -> None:
    session, _ = _session_with_snapshot(db, lock)
    before = svc.get_session(db, session.id)
    after = svc.resume_session(db, lock, session.id, owner_token="owner-2")
    assert after.surface == before.surface
    assert after.workspace == before.workspace
    assert after.mission_id == before.mission_id
    assert after.run_id == before.run_id
    assert after.id == before.id


def test_resume_version_mismatch_fails_closed(db, lock) -> None:
    session, _ = _session_with_snapshot(db, lock, prompt_version_override="9.9.9-incompatible")
    with pytest.raises(ContractCompatibilityError):
        svc.resume_session(db, lock, session.id, owner_token="owner-2")
    # No resume happened — the session is still suspended.
    assert svc.get_session(db, session.id).state == "suspended"


def test_resumed_session_not_reclaimed_by_sweep(db, lock) -> None:
    session, _ = _session_with_snapshot(db, lock)
    svc.resume_session(db, lock, session.id, owner_token="owner-2")
    reclaimed = svc.reconcile_orphans(db, lock, ttl_seconds=60)
    assert session.id not in reclaimed
    assert svc.get_session(db, session.id).state == "active"


def test_resume_completed_raises(db, lock) -> None:
    session, _ = _session_with_snapshot(db, lock, state="completed")
    with pytest.raises(ValueError):
        svc.resume_session(db, lock, session.id, owner_token="owner-2")
