"""Repo Triage golden workflow (Phase 10.0.5-02) — internal-risk, auto-run.

Deterministic orchestrator: scans the workspace via the real `tool_service`
chokepoint (never a direct filesystem read — T-1005-04 tampering mitigation),
writes a markdown triage summary as an Artifact, and upserts a wiki page.
Independent of any LLM output (mock provider produces no structural output —
see 10.0.5-CONTEXT.md "CRITICAL — mock provider produces no structural
output").

`run_repo_triage` calling `tool_service.invoke(tool_name="workspace", ...)`
for both the top-level listing and the README read is what makes the audit
trail honest: every workspace touch emits its own `tool_requested` /
`tool_completed` event through the 10.0.4 policy chokepoint, in addition to
this workflow's own `golden_workflow_started`/`golden_workflow_completed`
bookend events.
"""
from __future__ import annotations

import datetime
import json
import pathlib

from atlas_runtime import golden_workflow_service, tool_service
from atlas_wiki import wiki_service

_WORKFLOW_ID = "repo_triage"


def run_repo_triage(
    conn,
    lock,
    *,
    workspace_root: str,
    wiki_dir: pathlib.Path,
) -> dict:
    """Run one Repo Triage pass against `workspace_root`; return a result dict.

    Returns: {"artifact_path": str, "wiki_slug": str, "run_id": str}.
    Graceful degradation: a missing README.md produces a "no README found"
    note in the summary rather than raising (T-1005-06-equivalent — a real
    demo repo is never guaranteed to look identical across re-runs).
    """
    run_id = golden_workflow_service.ensure_golden_run(conn, lock)
    golden_workflow_service.emit_workflow_event(
        conn, lock, run_id=run_id, workflow_id=_WORKFLOW_ID, phase="started"
    )

    date_str = datetime.date.today().isoformat()
    ctx = {"workspace_root": workspace_root}

    list_result = tool_service.invoke(
        conn, lock, tool_name="workspace", args={"op": "list", "path": "."}, ctx=ctx,
    )
    if getattr(list_result, "ok", False):
        names = json.loads(list_result.output or "[]")
    else:
        names = []

    readme_result = tool_service.invoke(
        conn, lock, tool_name="workspace", args={"op": "read", "path": "README.md"}, ctx=ctx,
    )
    if getattr(readme_result, "ok", False):
        readme_excerpt = (readme_result.output or "").strip()[:2000]
        readme_section = f"## README excerpt\n\n```\n{readme_excerpt}\n```\n"
    else:
        readme_section = "## README\n\nNo README found.\n"

    summary_lines = [
        f"# Repo Triage — {date_str}\n",
        f"\nWorkspace root: `{workspace_root}`\n",
        f"\nTop-level entries ({len(names)}):\n",
    ]
    for name in names:
        summary_lines.append(f"- {name}\n")
    summary_lines.append(f"\n{readme_section}")
    summary = "".join(summary_lines)

    artifact_path = f"golden/repo-triage-{date_str}.md"
    golden_workflow_service.record_artifact(
        conn,
        lock,
        run_id=run_id,
        path=artifact_path,
        artifact_type="file_write",
        content=summary.encode("utf-8"),
    )

    wiki_slug = f"repo-triage-{date_str}"
    wiki_dir = pathlib.Path(wiki_dir)
    wiki_dir.mkdir(parents=True, exist_ok=True)
    wiki_service.update_wiki_page(
        conn,
        lock,
        slug=wiki_slug,
        title=f"Repo Triage — {date_str}",
        body=summary,
        run_id=run_id,
        wiki_dir=wiki_dir,
    )

    golden_workflow_service.emit_workflow_event(
        conn,
        lock,
        run_id=run_id,
        workflow_id=_WORKFLOW_ID,
        phase="completed",
        data={"artifact_path": artifact_path, "wiki_slug": wiki_slug},
    )

    return {"artifact_path": artifact_path, "wiki_slug": wiki_slug, "run_id": run_id}
