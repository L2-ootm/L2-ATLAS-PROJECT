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
    db_path = pathlib.Path.home() / ".atlas" / "atlas.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
