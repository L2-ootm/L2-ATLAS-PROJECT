"""Compile, persist, load, compare, and replay immutable run contracts."""
from __future__ import annotations

import datetime
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from atlas_core.schemas.agent_contract import (
    ContextEnvelope,
    ContextSource,
    ContractVersion,
    ModelIdentity,
    SessionBootstrap,
    SurfaceIdentity,
    WorkspaceIdentity,
)
from atlas_runtime.context_service import assemble_context
from atlas_runtime.memory_router import redact
from atlas_runtime.prompt_compiler import compile_prompt
from atlas_runtime.tool_catalog import build_shipped_catalog

PROMPT_VERSION = "1.0.1"
CONTEXT_POLICY_VERSION = "1.0.0"
_CORE_PATH = Path(__file__).parent / "prompts" / "atlas_core.md"


class ContractCompatibilityError(RuntimeError):
    pass


class RunContractSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    run_id: str
    mission_id: str | None
    contract_sha256: str
    prompt_version: str
    # Stored alongside its digest so the exact policy delivered to the model is
    # auditable. The default keeps pre-1.0.1 persisted snapshots loadable.
    stable_prompt: str = ""
    stable_prompt_sha256: str
    tool_catalog_version: str
    tool_catalog_sha256: str
    context_policy_version: str
    instruction_source_ids: tuple[str, ...]
    selected_source_ids: tuple[str, ...]
    rejected_source_ids: tuple[str, ...]
    bootstrap_message: str
    context_message: str
    context_markdown: str
    rendered_user_message: str
    created_at: str


class ResumeSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    operator_directives: tuple[str, ...]
    workspace_root: str
    project_id: str | None
    current_task: str
    modified_files: tuple[str, ...]
    tool_state_json: str
    permission_state_json: str
    unresolved_errors: tuple[str, ...]
    active_children: tuple[str, ...]
    verification_status: str
    uncertainties: tuple[str, ...]
    prompt_version: str
    tool_catalog_version: str
    context_policy_version: str
    next_action: str


def _version(version: str, content: bytes) -> ContractVersion:
    return ContractVersion(version=version, sha256=hashlib.sha256(content).hexdigest())


def _context_envelope(agent_context, policy: ContractVersion) -> ContextEnvelope:  # noqa: ANN001
    retrieval = agent_context.retrieval
    if retrieval is None:
        return ContextEnvelope(policy=policy)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sources = tuple(
        ContextSource(
            source_id=item.source_id,
            source_type=item.source_type
            if item.source_type in ContextSource.model_fields["source_type"].annotation.__args__
            else "memory",
            retrieved_at=now,
            confidence=item.confidence,
            relevance=max(0.0, min(1.0, item.score)),
            trust="evidence",
            content=item.content,
            truncated=item.truncated,
        )
        for item in retrieval.selected
    )
    return ContextEnvelope(
        policy=policy,
        budget_tokens=retrieval.token_budget,
        estimated_tokens=retrieval.estimated_tokens,
        sources=sources,
        rejected_source_ids=retrieval.rejected_source_ids,
    )


def _surface_and_workspace(
    conn: sqlite3.Connection,
    run_id: str,
) -> tuple[SurfaceIdentity, WorkspaceIdentity]:
    """Resolve the persisted execution surface; fall back for legacy CLI runs."""
    row = conn.execute(
        "SELECT s.id,s.surface_kind,s.workspace_kind,s.workspace_root,s.project_id "
        "FROM runs r JOIN surface_sessions s ON s.id=r.session_id WHERE r.id=?",
        (run_id,),
    ).fetchone()
    if row is None:
        return (
            SurfaceIdentity(kind="cli", session_id=run_id),
            WorkspaceIdentity(kind="global", root=str(Path.cwd())),
        )
    return (
        SurfaceIdentity(kind=row[1], session_id=row[0]),
        WorkspaceIdentity(kind=row[2], root=row[3], project_id=row[4]),
    )


def prepare_run_contract(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    mission_id: str | None,
    prompt: str,
) -> RunContractSnapshot:
    catalog = build_shipped_catalog()
    prompt_ref = _version(PROMPT_VERSION, _CORE_PATH.read_bytes())
    context_ref = _version(CONTEXT_POLICY_VERSION, b"ATLAS_CONTEXT_POLICY_V1")
    context = assemble_context(conn, mission_id=mission_id)
    envelope = _context_envelope(context, context_ref)
    surface, workspace = _surface_and_workspace(conn, run_id)
    bootstrap = SessionBootstrap(
        surface=surface,
        workspace=workspace,
        mission_id=mission_id,
        run_id=run_id,
        agent="native",
        model=ModelIdentity(provider="resolved-at-execution", model_id="resolved-at-execution"),
        permission_mode="ask",
        capabilities=tuple(item.name for item in catalog.capabilities),
        prompt=prompt_ref,
        tool_catalog=ContractVersion(
            version=catalog.catalog_version,
            sha256=catalog.catalog_sha256,
        ),
        context_policy=context_ref,
        context_budget_tokens=envelope.budget_tokens,
    )
    compilation = compile_prompt(bootstrap=bootstrap, context=envelope)
    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    base = {
        "run_id": run_id,
        "mission_id": mission_id,
        "prompt_version": prompt_ref.version,
        "stable_prompt": compilation.stable_prompt.decode("utf-8"),
        "stable_prompt_sha256": compilation.stable_prompt_sha256,
        "tool_catalog_version": catalog.catalog_version,
        "tool_catalog_sha256": catalog.catalog_sha256,
        "context_policy_version": context_ref.version,
        "instruction_source_ids": (),
        # Include both static context sources (focus/goals/project/operator observations)
        # and routed dynamic sources. The ContextEnvelope stores only routed evidence;
        # the markdown brief below is the full operator context actually supplied to
        # the harness, so its provenance must be part of the immutable snapshot too.
        "selected_source_ids": tuple(context.sources),
        "rejected_source_ids": envelope.rejected_source_ids,
        "bootstrap_message": compilation.bootstrap_message,
        "context_message": compilation.context_message,
        "context_markdown": context.markdown,
        "rendered_user_message": redact(prompt),
        "created_at": created_at,
    }
    canonical = json.dumps(base, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return RunContractSnapshot(id=str(uuid.uuid4()), contract_sha256=digest, **base)


def persist_contract(
    conn: sqlite3.Connection,
    snapshot: RunContractSnapshot,
) -> RunContractSnapshot:
    existing = load_contract(conn, snapshot.run_id)
    if existing is not None:
        if existing.contract_sha256 != snapshot.contract_sha256:
            raise ValueError("run already has a different immutable contract snapshot")
        return existing
    payload = snapshot.model_dump_json()
    with conn:
        conn.execute(
            "INSERT INTO agent_contract_snapshots "
            "(id,run_id,contract_sha256,snapshot_json,created_at) VALUES (?,?,?,?,?)",
            (
                snapshot.id,
                snapshot.run_id,
                snapshot.contract_sha256,
                payload,
                snapshot.created_at,
            ),
        )
    return snapshot


def load_contract(conn: sqlite3.Connection, run_id: str) -> RunContractSnapshot | None:
    row = conn.execute(
        "SELECT snapshot_json FROM agent_contract_snapshots WHERE run_id=?", (run_id,)
    ).fetchone()
    return None if row is None else RunContractSnapshot.model_validate_json(row[0])


def replay_contract(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    expected_prompt_version: str | None = None,
    expected_catalog_version: str | None = None,
    expected_context_policy_version: str | None = None,
) -> RunContractSnapshot:
    snapshot = load_contract(conn, run_id)
    if snapshot is None:
        raise LookupError(f"no contract snapshot for run {run_id}")
    checks = (
        ("prompt version", expected_prompt_version, snapshot.prompt_version),
        ("catalog version", expected_catalog_version, snapshot.tool_catalog_version),
        ("context policy version", expected_context_policy_version, snapshot.context_policy_version),
    )
    for label, expected, actual in checks:
        if expected is not None and expected != actual:
            raise ContractCompatibilityError(f"{label} incompatible: expected {expected}, got {actual}")
    return snapshot


__all__ = [
    "ContractCompatibilityError",
    "ResumeSnapshot",
    "RunContractSnapshot",
    "load_contract",
    "persist_contract",
    "prepare_run_contract",
    "replay_contract",
]
