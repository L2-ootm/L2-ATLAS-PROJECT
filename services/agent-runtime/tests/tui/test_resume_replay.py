"""Resume/replay version pinning, fail-closed on drift (TUI-09).

RED until atlas_runtime.tui.resume exists (Wave 1+).
"""
from __future__ import annotations

import datetime
import json
import uuid

import pytest

from atlas_runtime.agent_contract_service import ContractCompatibilityError
from atlas_runtime.tui.resume import resume_or_fail_closed


def _seed_mismatched_contract(db, run_id: str) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    snapshot_json = json.dumps(
        {
            "run_id": run_id,
            "prompt_version": "0.9.0-stale",
            "tool_catalog_version": "0.9.0-stale",
            "context_policy_version": "0.9.0-stale",
        }
    )
    db.execute(
        "INSERT INTO agent_contract_snapshots(run_id, snapshot_json, created_at) "
        "VALUES (?,?,?)",
        (run_id, snapshot_json, now),
    )
    db.commit()


def test_resume_calls_replay_contract_before_transition(
    db, surface_session, monkeypatch
):
    """TUI-09: resume calls replay_contract BEFORE any state transition."""
    run_id = str(uuid.uuid4())
    order = []
    monkeypatch.setattr(
        "atlas_runtime.tui.resume.agent_contract_service.replay_contract",
        lambda conn, rid, **kw: order.append("replay") or object(),
    )
    monkeypatch.setattr(
        "atlas_runtime.tui.resume.surface_session_service.resume_session",
        lambda conn, lock, sid, **kw: order.append("resume"),
    )
    resume_or_fail_closed(
        db,
        session_id=surface_session,
        run_id=run_id,
        expected_prompt_version="1.0.0",
        expected_catalog_version="1.0.0",
        expected_context_policy_version="1.0.0",
    )
    assert order == ["replay", "resume"]


def test_version_drift_raises_contract_compatibility_error_and_blocks_resume(
    db, surface_session
):
    """TUI-09: a real version-mismatched contract fails closed via the actual
    agent_contract_service.replay_contract path (no monkeypatch of the real check)."""
    run_id = str(uuid.uuid4())
    _seed_mismatched_contract(db, run_id)
    with pytest.raises(ContractCompatibilityError):
        resume_or_fail_closed(
            db,
            session_id=surface_session,
            run_id=run_id,
            expected_prompt_version="1.0.0",
            expected_catalog_version="1.0.0",
            expected_context_policy_version="1.0.0",
        )
