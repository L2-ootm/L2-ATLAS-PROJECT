"""Immutable run-contract persistence and replay tests."""
from __future__ import annotations

import json

import pytest

from atlas_runtime.agent_contract_service import (
    ContractCompatibilityError,
    load_contract,
    persist_contract,
    prepare_run_contract,
    replay_contract,
)


def test_migration_creates_immutable_run_linked_snapshot_table(db):
    columns = {
        row[1] for row in db.execute("PRAGMA table_info(agent_contract_snapshots)")
    }
    assert {"id", "run_id", "contract_sha256", "snapshot_json", "created_at"} <= columns


def test_prepare_persist_load_and_replay_round_trip(db, run_id):
    snapshot = prepare_run_contract(
        db,
        run_id=run_id,
        mission_id=None,
        prompt="Inspect the workspace and report evidence.",
    )
    persisted = persist_contract(db, snapshot)
    assert persist_contract(db, snapshot).id == persisted.id
    loaded = load_contract(db, run_id)
    assert loaded == persisted
    replay = replay_contract(db, run_id)
    assert replay.contract_sha256 == snapshot.contract_sha256
    assert replay.stable_prompt_sha256 == snapshot.stable_prompt_sha256
    assert "You are ATLAS" in replay.stable_prompt
    assert "verified-live" in replay.stable_prompt
    assert replay.context_markdown.startswith("# ATLAS Operator Context")


def test_prepare_uses_the_run_surface_and_workspace(db, run_id, surface_session):
    db.execute(
        "UPDATE surface_sessions SET surface_kind='webui', workspace_kind='project', "
        "workspace_root='C:/work/atlas', project_id='atlas' WHERE id=?",
        (surface_session,),
    )
    db.execute("UPDATE runs SET session_id=? WHERE id=?", (surface_session, run_id))
    db.commit()

    snapshot = prepare_run_contract(db, run_id=run_id, mission_id=None, prompt="identify surface")
    bootstrap = json.loads(snapshot.bootstrap_message)["payload"]

    assert bootstrap["surface"] == {"kind": "webui", "session_id": surface_session}
    assert bootstrap["workspace"] == {
        "kind": "project",
        "project_id": "atlas",
        "root": "C:/work/atlas",
    }


def test_snapshot_is_redacted_and_excludes_hidden_reasoning(db, run_id):
    snapshot = prepare_run_contract(
        db,
        run_id=run_id,
        mission_id=None,
        prompt="Authorization: Bearer abc.def.ghi",
    )
    persist_contract(db, snapshot)
    raw = db.execute(
        "SELECT snapshot_json FROM agent_contract_snapshots WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    assert "abc.def.ghi" not in raw
    assert "[REDACTED]" in raw
    assert "chain_of_thought" not in raw
    # Policy prose may mention reasoning traces; no hidden reasoning payload or
    # field may be persisted in the auditable contract snapshot.
    assert '"reasoning":' not in raw.lower()
    assert "reasoning_content" not in raw.lower()
    json.loads(raw)


def test_snapshot_rows_are_immutable(db, run_id):
    persist_contract(
        db,
        prepare_run_contract(db, run_id=run_id, mission_id=None, prompt="x"),
    )
    with pytest.raises(Exception):
        db.execute(
            "UPDATE agent_contract_snapshots SET snapshot_json='{}' WHERE run_id=?",
            (run_id,),
        )


def test_replay_reports_explicit_version_incompatibility(db, run_id):
    persist_contract(
        db,
        prepare_run_contract(db, run_id=run_id, mission_id=None, prompt="x"),
    )
    with pytest.raises(ContractCompatibilityError, match="prompt version"):
        replay_contract(db, run_id, expected_prompt_version="9.0.0")
