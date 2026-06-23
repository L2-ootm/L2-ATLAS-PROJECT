"""ATLAS golden-workflow orchestrator core (Phase 10.0.5).

Deterministic-orchestrator helpers shared by all three golden workflows
(Repo Triage, Research Brief, Self-Review). The mock LLM provider produces
no structural output (canned text only, no tool calls) — see
`.planning/phases/10.0.5-golden-workflows-quality-gate/10.0.5-CONTEXT.md`
"CRITICAL — mock provider produces no structural output". Golden workflows
therefore perform real reads via the tool layer and write artifacts/wiki
entries/audit events directly, independent of the LLM.

This module provides only the orchestrator-core primitives:
  - `ensure_golden_run` — bootstrap the shared operator run (FK target for
    artifacts/audit_events), delegating to `mission_service.ensure_operator_run`.
    Named separately so call sites read as golden-workflow domain language,
    not mission internals.
  - `record_artifact` — the FIRST writer to the `artifacts` table in this
    codebase. Computes sha256/size_bytes server-side from the actual bytes
    written (never trusts a caller-supplied hash — T-1005-01), inserts an
    Artifact row, then emits an `"artifact"` AuditEvent tagging the
    golden-workflow identity in `data`.
  - `emit_workflow_event` — emits `"golden_workflow_started"` /
    `"golden_workflow_completed"` lifecycle events, tagged with `workflow_id`
    in `data` so the wave-4 demo-reset path can scope deletes precisely.

Deliberately NOT provided here: a `write_wiki_entry` wrapper. Wave 2/3
workflow implementations call `atlas_wiki.wiki_service.update_wiki_page`
directly with the `run_id` returned by `ensure_golden_run` — adding a thin
wrapper here would be a redundant indirection layer. Cross-service import is
done at call time inside each workflow module, not here, since this module
has no wiki dependency of its own.
"""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from typing import Literal, Optional

from atlas_core.schemas.core import Artifact, AuditEvent

from atlas_runtime import mission_service
from atlas_runtime.audit_service import emit


def ensure_golden_run(conn: sqlite3.Connection, lock: threading.Lock) -> str:
    """Idempotently bootstrap the shared operator run; return its run id.

    Thin wrapper over `mission_service.ensure_operator_run` — golden workflows
    are operator-initiated, non-agentic side effects (no LLM-driven Run of
    their own), so they reuse the same synthetic operator mission/run pair
    used by wiki edits and gated Discord actions. This avoids an FK violation
    on a fresh database (T-1005-02): artifacts/audit_events both reference
    `runs(id)`, and the operator run must exist before either INSERT.
    """
    return mission_service.ensure_operator_run(conn, lock)


def record_artifact(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: str,
    path: str,
    artifact_type: Literal["file_write", "file_edit", "file_delete", "unknown"],
    content: bytes,
    audit_event_id: Optional[str] = None,
) -> Artifact:
    """Insert an Artifact row and emit a matching `"artifact"` audit event.

    sha256/size_bytes are computed here from `content` — never accepted as
    caller-supplied values (T-1005-01: tampering mitigation). Artifacts are
    append-only (no upsert): calling this twice with the same `path` for the
    same `run_id` inserts two distinct rows, matching the existing `artifacts`
    table design (mission_service.purge_expired_archives deletes by run_id,
    not by path, confirming no uniqueness assumption exists elsewhere).

    The audit event is emitted AFTER the insert's `with lock: with conn:`
    block releases (emit-after-lock pattern, mirrors wiki_service) — `emit()`
    acquires its own lock/transaction and must not be nested inside this
    function's.
    """
    sha256 = hashlib.sha256(content).hexdigest()
    size_bytes = len(content)

    artifact = Artifact(
        run_id=run_id,
        audit_event_id=audit_event_id,
        path=path,
        artifact_type=artifact_type,
        sha256=sha256,
        size_bytes=size_bytes,
    )
    row = artifact.model_dump()

    with lock:
        with conn:
            conn.execute(
                "INSERT INTO artifacts "
                "(id, run_id, audit_event_id, path, artifact_type, sha256, "
                "size_bytes, created_at) "
                "VALUES (:id, :run_id, :audit_event_id, :path, :artifact_type, "
                ":sha256, :size_bytes, :created_at)",
                row,
            )

    emit(
        conn,
        lock,
        run_id=run_id,
        event_type="artifact",
        data={
            "path": path,
            "artifact_type": artifact_type,
            "sha256": artifact.sha256,
        },
    )

    return artifact


def emit_workflow_event(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: str,
    workflow_id: str,
    phase: Literal["started", "completed"],
    data: Optional[dict] = None,
) -> AuditEvent:
    """Emit a golden-workflow lifecycle event (`golden_workflow_<phase>`).

    `data["workflow_id"]` tags which of the 3 golden workflows produced the
    event, independent of which workflow runs — this is what makes every
    golden-workflow invocation auditable and lets the wave-4 demo-reset path
    scope deletes by workflow_id.
    """
    event_type = f"golden_workflow_{phase}"
    payload = {"workflow_id": workflow_id, **(data or {})}
    return emit(conn, lock, run_id=run_id, event_type=event_type, data=payload)
