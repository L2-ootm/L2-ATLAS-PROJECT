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


# --- L4 workspace instructions ------------------------------------------------


def _workspace(root):
    from atlas_core.schemas.agent_contract import WorkspaceIdentity

    return WorkspaceIdentity(kind="project", root=str(root), project_id="p1")


def test_workspace_instruction_files_become_hash_pinned_sources(tmp_path):
    from atlas_runtime.agent_contract_service import load_workspace_instructions

    (tmp_path / "AGENTS.md").write_text("Run the suite before claiming done.", encoding="utf-8")
    sources, contents = load_workspace_instructions(_workspace(tmp_path))

    assert [s.source_id for s in sources] == ["AGENTS.md"]
    assert contents == ("Run the suite before claiming done.",)
    assert all(s.trust == "project" for s in sources)


def test_workspace_instructions_reach_the_stable_prompt(db, run_id, surface_session, tmp_path):
    """L4 has always been renderable and was never filled by anything."""
    (tmp_path / "AGENTS.md").write_text("Never touch the vendored foundation.", encoding="utf-8")
    db.execute(
        "UPDATE surface_sessions SET workspace_kind='project', workspace_root=?, "
        "project_id='p1' WHERE id=?",
        (str(tmp_path), surface_session),
    )
    db.execute("UPDATE runs SET session_id=? WHERE id=?", (surface_session, run_id))
    db.commit()

    snapshot = prepare_run_contract(db, run_id=run_id, mission_id=None, prompt="go")

    assert "[L4 WORKSPACE INSTRUCTIONS]" in snapshot.stable_prompt
    assert "Never touch the vendored foundation." in snapshot.stable_prompt
    assert snapshot.instruction_source_ids == ("AGENTS.md",)


def test_a_workspace_with_no_instruction_files_has_no_l4_layer(db, run_id, surface_session, tmp_path):
    db.execute(
        "UPDATE surface_sessions SET workspace_kind='project', workspace_root=?, "
        "project_id='p1' WHERE id=?",
        (str(tmp_path), surface_session),
    )
    db.execute("UPDATE runs SET session_id=? WHERE id=?", (surface_session, run_id))
    db.commit()

    snapshot = prepare_run_contract(db, run_id=run_id, mission_id=None, prompt="go")

    assert "[L4 WORKSPACE INSTRUCTIONS]" not in snapshot.stable_prompt
    assert snapshot.instruction_source_ids == ()


def test_an_instruction_file_holding_a_credential_is_excluded_not_fatal(tmp_path, caplog):
    """Raising would fail every run in the workspace; the scan exists to keep the
    secret out of the prompt, not to make the workspace unusable."""
    from atlas_runtime.agent_contract_service import load_workspace_instructions

    (tmp_path / "AGENTS.md").write_text('api_key="sk-live-abcdef123456"', encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("Prefer small diffs.", encoding="utf-8")

    sources, contents = load_workspace_instructions(_workspace(tmp_path))

    assert [s.source_id for s in sources] == ["CLAUDE.md"]
    assert "sk-live-abcdef123456" not in "".join(contents)


def test_an_oversized_instruction_file_is_truncated_with_a_marker(tmp_path):
    from atlas_runtime import agent_contract_service as svc

    (tmp_path / "AGENTS.md").write_text("x" * 20_000, encoding="utf-8")
    _sources, contents = svc.load_workspace_instructions(_workspace(tmp_path))

    assert len(contents[0]) <= svc._INSTRUCTION_FILE_CHARS + len(svc._TRUNCATION_NOTE)
    assert contents[0].endswith("size limit]")


def test_the_total_instruction_budget_is_enforced_across_files(tmp_path):
    from atlas_runtime import agent_contract_service as svc

    for name in ("AGENTS.md", "CLAUDE.md"):
        (tmp_path / name).write_text("y" * 20_000, encoding="utf-8")
    _sources, contents = svc.load_workspace_instructions(_workspace(tmp_path))

    body = sum(len(c) - len(svc._TRUNCATION_NOTE) for c in contents)
    assert body <= svc._INSTRUCTION_TOTAL_CHARS


def test_sources_and_contents_stay_index_aligned(tmp_path):
    """prompt_compiler re-hashes contents against sources and refuses a mismatch."""
    from atlas_runtime.agent_contract_service import load_workspace_instructions

    (tmp_path / "AGENTS.md").write_text("first", encoding="utf-8")
    (tmp_path / ".atlas").mkdir()
    (tmp_path / ".atlas" / "instructions.md").write_text("third", encoding="utf-8")

    sources, contents = load_workspace_instructions(_workspace(tmp_path))

    assert [s.source_id for s in sources] == ["AGENTS.md", ".atlas/instructions.md"]
    assert contents == ("first", "third")
    import hashlib

    for source, content in zip(sources, contents):
        assert source.sha256 == hashlib.sha256(content.encode("utf-8")).hexdigest()
