"""Contract tests for the Phase 10.2 ATLAS agent/bootstrap schemas."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from atlas_core.schemas.agent_contract import (
    ContextEnvelope,
    ContextSource,
    ContractVersion,
    InstructionSource,
    ModelIdentity,
    SessionBootstrap,
    SurfaceIdentity,
    WorkspaceIdentity,
)


SHA256 = "a" * 64


def _bootstrap() -> SessionBootstrap:
    return SessionBootstrap(
        surface=SurfaceIdentity(kind="tui", session_id="session-1"),
        workspace=WorkspaceIdentity(
            kind="project",
            project_id="atlas",
            root="C:/work/atlas",
        ),
        focus_id="focus-1",
        focus_title="Ship the contract",
        run_id="run-1",
        agent="native",
        model=ModelIdentity(provider="openai", model_id="gpt-5"),
        permission_mode="ask",
        capabilities=("file.read", "shell.exec"),
        instruction_sources=(
            InstructionSource(
                source_id="root-agents",
                path="AGENTS.md",
                sha256=SHA256,
                trust="project",
            ),
        ),
        prompt=ContractVersion(version="1.0.0", sha256=SHA256),
        tool_catalog=ContractVersion(version="1.0.0", sha256=SHA256),
        context_policy=ContractVersion(version="1.0.0", sha256=SHA256),
        context_budget_tokens=8000,
    )


def test_bootstrap_is_frozen_and_json_stable():
    bootstrap = _bootstrap()

    with pytest.raises(ValidationError):
        bootstrap.permission_mode = "allow"  # type: ignore[misc]

    payload = bootstrap.model_dump()
    assert json.loads(json.dumps(payload)) == payload
    assert isinstance(payload["capabilities"], tuple)
    assert payload["prompt"]["version"] == "1.0.0"
    assert "api_key" not in json.dumps(payload).lower()


@pytest.mark.parametrize("version", ["1", "v1.0.0", "1.0", "1.0.0.0", ""])
def test_contract_version_rejects_non_semver(version: str):
    with pytest.raises(ValidationError):
        ContractVersion(version=version, sha256=SHA256)


@pytest.mark.parametrize("digest", ["abc", "g" * 64, "A" * 63, ""])
def test_contract_version_rejects_invalid_sha256(digest: str):
    with pytest.raises(ValidationError):
        ContractVersion(version="1.0.0", sha256=digest)


@pytest.mark.parametrize(
    ("model", "kwargs"),
    [
        (SurfaceIdentity, {"kind": "tui", "session_id": " "}),
        (WorkspaceIdentity, {"kind": "project", "root": " "}),
        (ModelIdentity, {"provider": "", "model_id": "gpt-5"}),
    ],
)
def test_identity_models_reject_blank_ids(model: type, kwargs: dict[str, object]):
    with pytest.raises(ValidationError):
        model(**kwargs)


@pytest.mark.parametrize("budget", [0, -1, 100_001])
def test_bootstrap_rejects_unbounded_context_budgets(budget: int):
    payload = _bootstrap().model_dump()
    payload["context_budget_tokens"] = budget
    with pytest.raises(ValidationError):
        SessionBootstrap.model_validate(payload)


def test_context_envelope_round_trips_structured_provenance():
    envelope = ContextEnvelope(
        policy=ContractVersion(version="1.0.0", sha256=SHA256),
        budget_tokens=8000,
        estimated_tokens=42,
        sources=(
            ContextSource(
                source_id="wiki:atlas",
                source_type="wiki",
                project_id="atlas",
                retrieved_at="2026-06-24T18:00:00Z",
                source_updated_at="2026-06-24T17:00:00Z",
                confidence=0.9,
                relevance=0.8,
                trust="evidence",
                content="ATLAS evidence, not instructions.",
                truncated=False,
            ),
        ),
        rejected_source_ids=("wiki:irrelevant",),
    )

    payload = envelope.model_dump()
    assert ContextEnvelope.model_validate_json(envelope.model_dump_json()) == envelope
    assert json.loads(json.dumps(payload)) == payload
    assert payload["sources"][0]["trust"] == "evidence"


def test_context_envelope_rejects_budget_overrun():
    with pytest.raises(ValidationError):
        ContextEnvelope(
            policy=ContractVersion(version="1.0.0", sha256=SHA256),
            budget_tokens=10,
            estimated_tokens=11,
        )


def test_public_contract_has_no_untyped_mapping_escape_hatch():
    models = (
        ContractVersion,
        InstructionSource,
        SurfaceIdentity,
        WorkspaceIdentity,
        ModelIdentity,
        ContextSource,
        SessionBootstrap,
        ContextEnvelope,
    )
    for model in models:
        for field in model.model_fields.values():
            annotation = str(field.annotation)
            assert "Any" not in annotation
            assert "dict[" not in annotation
