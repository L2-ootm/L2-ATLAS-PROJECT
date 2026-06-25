"""Safety-critical compaction/resume state invariants."""
from __future__ import annotations

from atlas_runtime.agent_contract_service import ResumeSnapshot
from atlas_runtime.agents.native import NativeAtlasAgent

from tests.test_agents import _pending_mission, _running_run, _FakeHarness


def test_resume_snapshot_round_trip_preserves_every_critical_field():
    snapshot = ResumeSnapshot(
        operator_directives=("do not publish",),
        workspace_root="C:/work/atlas",
        project_id="atlas",
        current_task="fix prompt contract",
        modified_files=("a.py", "b.py"),
        tool_state_json='{"active":["workspace"]}',
        permission_state_json='{"shell":"deny"}',
        unresolved_errors=("verification failed",),
        active_children=("child-1",),
        verification_status="failed",
        uncertainties=("schema drift unknown",),
        prompt_version="1.0.0",
        tool_catalog_version="1.0.0",
        context_policy_version="1.0.0",
        next_action="rerun verification",
    )
    assert ResumeSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    assert "deny" in snapshot.permission_state_json
    assert snapshot.verification_status == "failed"


def test_native_prepares_contract_before_foundation_execution(db, lock):
    mission_id = _pending_mission(db)
    run_id = _running_run(db, mission_id)
    harness = _FakeHarness(
        {
            "final_response": "done",
            "api_calls": 1,
            "completed": True,
            "failed": False,
            "error": None,
        }
    )
    outcome = NativeAtlasAgent(agent_factory=lambda session_id: harness).execute(
        db,
        lock,
        mission_id=mission_id,
        run_id=run_id,
        prompt="ship it",
    )
    assert outcome.status == "succeeded"
    assert db.execute(
        "SELECT COUNT(*) FROM agent_contract_snapshots WHERE run_id=?", (run_id,)
    ).fetchone()[0] == 1
