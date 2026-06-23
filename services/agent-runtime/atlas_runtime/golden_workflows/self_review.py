"""Self-Review golden workflow (Phase 10.0.5-03) — approval-gated, never auto-writes.

Deterministic orchestrator (mirrors Repo Triage / Research Brief): no LLM call,
no structural dependency on the agent provider. It surveys the recent audit
trail for the shared operator run and proposes a markdown review note — but
the WRITE of that note is never executed inline. It routes through
`tool_service.invoke(tool_name="golden_review_write", ...)`, a write-class tool
(manifest `risk_level: write`), which the 10.0.4 policy chokepoint
unconditionally short-circuits to a PENDING `ToolApproval` row. There is no
code path in this module that calls the `golden_review_write` adapter
directly — the approval gate IS the only path to disk (D-1, T-1005-07).

Naming distinction (read before extending): `run_self_review`'s OWN workflow
lifecycle reaches `"completed"` (it emits `golden_workflow_completed`) as soon
as it has successfully PROPOSED the write — not when the write has executed.
The underlying `ToolApproval.status` independently tracks "pending" ->
"executed"/"rejected" via `tool_service.approve`/`reject`. Do not conflate the
two: the workflow's job is to propose, not to execute.

De-dup policy: NONE. Each call to `run_self_review` creates one fresh, distinct
pending approval, even if called multiple times the same day. This matches the
demo intent ("run 3x, assess 3x") and keeps the function's contract simple and
unambiguous — callers that want de-dup can filter `list_approvals` themselves.
"""
from __future__ import annotations

import datetime
import pathlib

from atlas_core.schemas.tool import ToolApproval

from atlas_runtime import golden_workflow_service, tool_service
from atlas_runtime.audit_service import get_events_for_run

_WORKFLOW_ID = "self_review"


def run_self_review(
    conn,
    lock,
    *,
    workspace_root: str,
    wiki_dir: pathlib.Path,
) -> ToolApproval:
    """Run one Self-Review pass; return the PENDING `ToolApproval` for its proposed write.

    `wiki_dir` is accepted for call-shape parity with the other two golden
    workflows (and for future use — a wiki-page proposal variant) but is not
    yet written to by this workflow; only the review-note file write is
    proposed. Nothing is written to disk by this function — only
    `tool_service.approve` (an explicit, separate call) executes the write.
    """
    run_id = golden_workflow_service.ensure_golden_run(conn, lock)
    golden_workflow_service.emit_workflow_event(
        conn, lock, run_id=run_id, workflow_id=_WORKFLOW_ID, phase="started"
    )

    date_str = datetime.date.today().isoformat()
    events = get_events_for_run(conn, run_id)
    recent = events[-20:]

    lines = [
        f"# Self-Review — {date_str}\n",
        f"\nOperator run: `{run_id}`\n",
        f"\nRecent audit events ({len(recent)} of {len(events)} total):\n",
    ]
    for event in recent:
        lines.append(f"- `{event.event_type}` at {event.timestamp}\n")
    if not events:
        lines.append("\nNo audit events recorded yet for this run.\n")
    note = "".join(lines)

    review_path = f"golden/self-review-{date_str}.md"
    approval = tool_service.invoke(
        conn,
        lock,
        tool_name="golden_review_write",
        args={"path": review_path, "content": note},
        ctx={"workspace_root": workspace_root},
        reason="golden_workflow:self_review",
    )

    golden_workflow_service.emit_workflow_event(
        conn,
        lock,
        run_id=run_id,
        workflow_id=_WORKFLOW_ID,
        phase="completed",
        data={"approval_id": approval.id, "approval_status": approval.status},
    )

    return approval
