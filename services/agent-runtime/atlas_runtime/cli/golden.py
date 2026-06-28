"""atlas golden — list/run the 3 demo-stable golden workflows (Phase 10.0.5-03).

Mirrors cli/tools.py's thin-CLI-wrapper style: `_get_connection`/`_get_lock`
module-level factories (monkeypatched in tests), a `--json` flag on every
command, `typer.Exit(1)` on error. Backed by `golden_workflow_registry` —
not nested under `operation_app` since golden workflows are not goal-bound
(see golden_workflow_registry module docstring for the risk-vocabulary
distinction from Operations).
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import threading
from typing import Optional

import typer

from atlas_runtime import golden_workflow_registry

golden_app = typer.Typer(
    name="golden",
    help="Golden workflows: list and run the 3 demo-stable orchestrators (D-1).",
)

# Module-level lock singleton (monkeypatched in tests via _get_lock).
_LOCK = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    """File-backed SQLite connection (WAL + FK) for golden-workflow side effects."""
    from atlas_runtime.cli import main

    return main._get_connection()


def _get_lock() -> threading.Lock:
    return _LOCK


@golden_app.command("list")
def list_workflows(json_out: bool = typer.Option(False, "--json", help="Emit JSON.")) -> None:
    """List the 3 golden workflows (id/label/description/risk)."""
    workflows = golden_workflow_registry.list_workflows()
    if json_out:
        typer.echo(json.dumps([w.id for w in workflows]))
        return
    for w in workflows:
        typer.echo(f"{w.id}\t{w.risk}\t{w.label}")


@golden_app.command("run")
def run_workflow(
    workflow_id: str = typer.Argument(..., help="Workflow id: repo_triage | research_brief | self_review."),
    workspace: str = typer.Option(".", "--workspace", help="Workspace root for repo_triage/self_review."),
    topic: str = typer.Option("atlas", "--topic", help="Topic for research_brief."),
    wiki_dir: Optional[str] = typer.Option(None, "--wiki-dir", help="Wiki directory (default: <workspace>/wiki)."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Run one golden workflow and print its result."""
    conn = _get_connection()
    lock = _get_lock()
    resolved_wiki_dir = pathlib.Path(wiki_dir) if wiki_dir else pathlib.Path(workspace) / "wiki"

    try:
        result = golden_workflow_registry.dispatch(
            workflow_id,
            conn=conn,
            lock=lock,
            workspace_root=workspace,
            wiki_dir=resolved_wiki_dir,
            topic=topic,
        )
    except golden_workflow_registry.GoldenWorkflowError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    if json_out:
        typer.echo(json.dumps(result))
        return
    for key, value in result.items():
        typer.echo(f"{key}\t{value}")


# Scoped demo-reset predicates — every DELETE is tied to the golden-workflow
# naming convention so the command can NEVER touch real operator data. This is
# the T-1005-10 mitigation: there is no code path here that issues a bare
# `DELETE FROM` without one of these prefix predicates.
_ARTIFACT_PRED = "path LIKE 'golden/%'"
_WIKI_PRED = (
    "slug LIKE 'repo-triage-%' OR slug LIKE 'research-brief-%' "
    "OR slug LIKE 'self-review-%'"
)
_APPROVAL_PRED = "reason LIKE 'golden_workflow:%'"


@golden_app.command("reset")
def golden_reset(
    confirm: bool = typer.Option(
        False, "--confirm", help="Actually delete. Without this flag the command is a dry-run and deletes NOTHING."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Reset demo state — delete ONLY golden-workflow-tagged rows.

    Scoped, dry-run-by-default destructive command. Deletes exactly:
      - artifacts WHERE path LIKE 'golden/%'
      - wiki_pages WHERE slug LIKE 'repo-triage-%'/'research-brief-%'/'self-review-%'
      - tool_approvals WHERE reason LIKE 'golden_workflow:%'

    It NEVER touches audit_events, missions, or runs — the operator's run/audit
    history (which IS the consistent audit trail SC1 requires) stays intact. The
    dry-run default is the safety rail (T-1005-11): without --confirm it only
    reports what WOULD be deleted. The LIKE-prefix predicates guard against
    accidental deletion of real operator data (T-1005-10) — there is no bare
    DELETE here.
    """
    conn = _get_connection()
    lock = _get_lock()

    if not confirm:
        a = conn.execute(f"SELECT COUNT(*) FROM artifacts WHERE {_ARTIFACT_PRED}").fetchone()[0]
        w = conn.execute(f"SELECT COUNT(*) FROM wiki_pages WHERE {_WIKI_PRED}").fetchone()[0]
        t = conn.execute(f"SELECT COUNT(*) FROM tool_approvals WHERE {_APPROVAL_PRED}").fetchone()[0]
        summary = {"dry_run": True, "artifacts_deleted": a, "wiki_pages_deleted": w, "tool_approvals_deleted": t}
    else:
        with lock:
            with conn:
                ac = conn.execute(f"DELETE FROM artifacts WHERE {_ARTIFACT_PRED}").rowcount
                wc = conn.execute(f"DELETE FROM wiki_pages WHERE {_WIKI_PRED}").rowcount
                tc = conn.execute(f"DELETE FROM tool_approvals WHERE {_APPROVAL_PRED}").rowcount
        summary = {"dry_run": False, "artifacts_deleted": ac, "wiki_pages_deleted": wc, "tool_approvals_deleted": tc}

    if json_out:
        typer.echo(json.dumps(summary))
        return
    verb = "would delete" if summary["dry_run"] else "deleted"
    typer.echo(
        f"[{'dry-run' if summary['dry_run'] else 'reset'}] {verb}: "
        f"{summary['artifacts_deleted']} artifacts, "
        f"{summary['wiki_pages_deleted']} wiki pages, "
        f"{summary['tool_approvals_deleted']} tool approvals"
    )
    if summary["dry_run"]:
        typer.echo("Re-run with --confirm to actually delete.")
