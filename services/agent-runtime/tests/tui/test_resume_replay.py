"""Resume/replay version pinning, fail-closed on drift (TUI-09).

RED until atlas_runtime.tui.resume exists (Wave 1+).
"""
from __future__ import annotations

import datetime
import uuid

import pytest

from atlas_runtime.agent_contract_service import (
    ContractCompatibilityError,
    RunContractSnapshot,
    persist_contract,
)
from atlas_runtime.tui.resume import resume_or_fail_closed


def _seed_mismatched_contract(db, run_id: str) -> None:
    """Seed a real, schema-valid run + immutable contract snapshot whose stored
    prompt/catalog/context-policy versions are stale relative to the "1.0.0"
    versions every test in this module expects, so replay_contract's real
    comparison (not a mock) fails closed."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    mission_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (mission_id, "resume-test-mission", "", "pending", "", now, now),
    )
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, mission_id, None, "running", now, None, ""),
    )
    db.commit()
    snapshot = RunContractSnapshot(
        id=str(uuid.uuid4()),
        run_id=run_id,
        mission_id=mission_id,
        contract_sha256=str(uuid.uuid4()),
        prompt_version="0.9.0-stale",
        stable_prompt_sha256="stale",
        tool_catalog_version="0.9.0-stale",
        tool_catalog_sha256="stale",
        context_policy_version="0.9.0-stale",
        instruction_source_ids=(),
        selected_source_ids=(),
        rejected_source_ids=(),
        bootstrap_message="",
        context_message="",
        rendered_user_message="",
        created_at=now,
    )
    persist_contract(db, snapshot)


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
