"""Golden workflow registry — one dispatch surface for all 3 demo-stable workflows.

Mirrors `operation_service.py`'s dataclass + tuple-registry + `_BY_ID` shape (the
D-1 vehicle precedent), but is NOT the same surface: `Operation.risk` uses
"internal"|"outward" vocabulary for goal-bound, agent-rendered instructions.
`GoldenWorkflow.risk` instead uses "internal"|"approval" — "internal" means the
workflow auto-runs and writes directly (Repo Triage, Research Brief); "approval"
means the workflow's underlying WRITE requires an explicit approve() call
(Self-Review) — it is NOT about the workflow itself being external-facing. Do
not conflate the two vocabularies when reading risk values across modules.

`dispatch()` is a pure pass-through: it looks up the workflow id and calls the
matching `golden_workflows.*` function with the given kwargs, normalizing
Self-Review's `ToolApproval` return into a dict (`.model_dump()`) so callers
(CLI, smoke tests) always get a uniform dict contract regardless of which
workflow ran.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Literal

from atlas_runtime.golden_workflows import repo_triage, research_brief, self_review


class GoldenWorkflowError(ValueError):
    """Raised for an unknown golden workflow id."""


@dataclass(frozen=True)
class GoldenWorkflow:
    id: str
    label: str
    description: str
    risk: Literal["internal", "approval"] = "internal"


_WORKFLOWS: tuple[GoldenWorkflow, ...] = (
    GoldenWorkflow(
        id="repo_triage",
        label="Repo Triage",
        description="Scan the workspace (top-level listing + README) and produce a triage artifact + wiki page.",
        risk="internal",
    ),
    GoldenWorkflow(
        id="research_brief",
        label="Research Brief",
        description="Search the wiki/codex for a topic and produce a brief artifact + wiki page (offline, FTS5).",
        risk="internal",
    ),
    GoldenWorkflow(
        id="self_review",
        label="Self-Review",
        description="Survey recent audit events and propose a review-note write — gated behind an explicit approval.",
        risk="approval",
    ),
)
_BY_ID = {w.id: w for w in _WORKFLOWS}


def list_workflows() -> list[GoldenWorkflow]:
    return list(_WORKFLOWS)


def get_workflow(workflow_id: str) -> GoldenWorkflow | None:
    return _BY_ID.get(workflow_id)


def dispatch(
    workflow_id: str,
    *,
    conn,
    lock,
    workspace_root: str,
    wiki_dir: pathlib.Path,
    topic: str = "atlas",
) -> dict:
    """Run the named golden workflow; return its result as a plain dict.

    Pure pass-through — no reimplementation of any workflow's logic. Raises
    `GoldenWorkflowError` for an unknown id rather than silently no-op'ing.
    """
    workflow = get_workflow(workflow_id)
    if workflow is None:
        raise GoldenWorkflowError(
            f"unknown golden workflow {workflow_id!r}. Known: "
            f"{', '.join(w.id for w in _WORKFLOWS)}"
        )

    if workflow_id == "repo_triage":
        return repo_triage.run_repo_triage(
            conn, lock, workspace_root=workspace_root, wiki_dir=wiki_dir
        )
    if workflow_id == "research_brief":
        return research_brief.run_research_brief(
            conn, lock, topic=topic, wiki_dir=wiki_dir
        )
    if workflow_id == "self_review":
        approval = self_review.run_self_review(
            conn, lock, workspace_root=workspace_root, wiki_dir=wiki_dir
        )
        return approval.model_dump()

    raise GoldenWorkflowError(f"no dispatch handler for {workflow_id!r}")  # pragma: no cover
