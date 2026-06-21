"""ATLAS CLI — atlas mission create|run|cancel|status subcommands.

Entry point: atlas_runtime.cli.main:app (registered in pyproject.toml [project.scripts]).

Design:
  - CLI handlers are thin wrappers only. No SQL, no emit() directly.
  - All business logic goes through the service layer (mission_service, run_service).
  - _get_connection() and _get_lock() are module-level factories; monkeypatch in tests.
"""
from __future__ import annotations

import sqlite3
import threading
import json

import typer

from atlas_runtime import (
    console_service,
    context_service,
    db,
    focus_service,
    goal_service,
    graph_service,
    mission_service,
    operation_service,
    project_service,
    run_executor,
    run_service,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = typer.Typer()
mission_app = typer.Typer(name="mission")
app.add_typer(mission_app, name="mission")
project_app = typer.Typer(name="project")
app.add_typer(project_app, name="project")
db_app = typer.Typer(name="db", help="Database lifecycle: apply migrations, inspect status.")
app.add_typer(db_app, name="db")
gateway_app = typer.Typer(name="gateway", help="Gateway lifecycle: start, status, stop.")
app.add_typer(gateway_app, name="gateway")
module_app = typer.Typer(name="module", help="Optional modules: list, activate, deactivate.")
app.add_typer(module_app, name="module")
cashflow_app = typer.Typer(name="cashflow", help="Cashflow module process: start, status, stop.")
app.add_typer(cashflow_app, name="cashflow")
console_app = typer.Typer(name="console", help="Cockpit console chat and workbench operations.")
app.add_typer(console_app, name="console")
graph_app = typer.Typer(name="graph", help="Project knowledge graph for the cockpit Graphify view.")
app.add_typer(graph_app, name="graph")
run_app = typer.Typer(name="run", help="Execute an already-started run (background-safe).")
app.add_typer(run_app, name="run")
focus_app = typer.Typer(name="focus", help="Command Center: the operator's Current Focus.")
app.add_typer(focus_app, name="focus")
goal_app = typer.Typer(name="goal", help="Command Center: goals, sub-goals, and the goal tree.")
app.add_typer(goal_app, name="goal")
task_app = typer.Typer(name="task", help="Command Center: tasks under a goal.")
app.add_typer(task_app, name="task")
observe_app = typer.Typer(name="observe", help="Command Center: observations on goals/runs.")
app.add_typer(observe_app, name="observe")
operation_app = typer.Typer(name="operation", help="Command Center: premade autonomous operations on goals.")
app.add_typer(operation_app, name="operation")
runtime_app = typer.Typer(name="runtime", help="In-process run executor daemon (background execution, b).")
app.add_typer(runtime_app, name="runtime")

try:
    from atlas_wiki.cli.main import wiki_app
    app.add_typer(wiki_app, name="wiki")
except ImportError:
    pass  # wiki service not installed — skip wiki subcommands gracefully

from atlas_runtime.cli.foundation import foundation_app
app.add_typer(foundation_app, name="foundation")

from atlas_runtime.cli.config import config_app, setup as _setup_cmd
app.add_typer(config_app, name="config")
app.command("setup", help="First-run wizard: configure ATLAS and write ~/.atlas/config.yaml.")(_setup_cmd)

from atlas_runtime.cli.models import models_app
app.add_typer(models_app, name="models")

from atlas_runtime.cli.channels import channels_app
app.add_typer(channels_app, name="channels")

from atlas_runtime.cli.discord import discord_app
app.add_typer(discord_app, name="discord")

from atlas_runtime.cli.tui import tui as _tui_cmd
app.command("tui", help="Launch the ATLAS terminal UI (foundation Ink TUI, ATLAS-skinned).")(_tui_cmd)

# Module-level lock singleton (monkeypatched in tests via _get_lock)
_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Connection + lock factories (injectable for tests)
# ---------------------------------------------------------------------------


def _get_connection() -> sqlite3.Connection:
    """Return a file-backed SQLite connection with WAL + FK enabled.

    Delegates to db.connect() — the single connection definition. Does NOT apply
    migrations (the gateway also opens this DB; schema changes happen only via the
    explicit `atlas db init`).
    """
    return db.connect()


def _get_lock() -> threading.Lock:
    """Return the module-level threading.Lock singleton."""
    return _LOCK


# ---------------------------------------------------------------------------
# console subcommands
# ---------------------------------------------------------------------------


@console_app.command("chat")
def console_chat(
    prompt: str = typer.Option(..., "--prompt", help="Prompt to send to the console agent"),
    agent: str = typer.Option(
        "native", "--agent", help="Console agent: native | claude_code"
    ),
    cwd: str | None = typer.Option(
        None, "--cwd", help="Folder binding for the console agent"
    ),
    stream: bool = typer.Option(
        False, "--stream", help="Emit one JSON event per line (NDJSON) as they happen"
    ),
) -> None:
    """Run one folder-aware console chat turn and print JSON.

    Default: print the full result as a single JSON object. With ``--stream``,
    print one ASCII-safe JSON event per line as it is produced (NDJSON) — the
    gateway forwards these so the cockpit tool-cards fill in real time.
    """
    if stream:
        import sys

        def on_event(event: dict) -> None:
            sys.stdout.write(json.dumps(event) + "\n")
            sys.stdout.flush()

        try:
            console_service.run_chat(prompt=prompt, agent=agent, cwd=cwd, on_event=on_event)
        except ValueError as exc:
            sys.stdout.write(json.dumps({"type": "failure", "error": str(exc)}) + "\n")
            sys.stdout.flush()
            raise typer.Exit(1)
        return

    try:
        result = console_service.run_chat(prompt=prompt, agent=agent, cwd=cwd)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(result, ensure_ascii=False))


# ---------------------------------------------------------------------------
# graph subcommands
# ---------------------------------------------------------------------------


@graph_app.command("build")
def graph_build(
    root: str = typer.Option(".", "--root", help="Project root containing .planning/"),
    scope: str = typer.Option(
        "atlas", "--scope", help="atlas | global | projects | obsidian"
    ),
    write: bool = typer.Option(
        False, "--write", help="Also cache the graph to .planning/graphs/graph.json"
    ),
) -> None:
    """Build the knowledge graph for the given scope and print it as JSON."""
    try:
        result = graph_service.build_graph(root=root, scope=scope)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    if write:
        from pathlib import Path

        out = Path(root).resolve() / ".planning" / "graphs"
        out.mkdir(parents=True, exist_ok=True)
        (out / "graph.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # ensure_ascii so the payload survives a cp1252 stdout on Windows; valid JSON either way.
    typer.echo(json.dumps(result))


# ---------------------------------------------------------------------------
# mission subcommands
# ---------------------------------------------------------------------------


@mission_app.command("create")
def create(
    title: str = typer.Option(..., "--title", help="Mission title"),
    intent: str = typer.Option("", "--intent", help="Mission intent"),
    project: str = typer.Option(
        None, "--project", help="Project ID — mission runs in that project's folder"
    ),
) -> None:
    """Create a Mission and print its ID."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        mission = mission_service.create_mission(
            conn, lock, title=title, intent=intent, project_id=project
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(mission.id)


@mission_app.command("run")
def run_mission(
    mission_id: str = typer.Argument(..., help="Mission ID to execute"),
    agent: str = typer.Option(
        "native", "--agent", help="Agent runtime to record/use: native | claude_code"
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Execute the run synchronously via the selected agent runtime (blocks)",
    ),
) -> None:
    """Start a Run for the given mission and print the run ID.

    With --execute, run it synchronously through the selected agent runtime
    and emit the audit trail. Without --execute the run is recorded with the
    chosen runtime but not executed (gateway-safe, non-blocking).
    """
    from atlas_runtime.agents import get_agent, known_agents

    conn = _get_connection()
    lock = _get_lock()

    if agent not in known_agents():
        typer.echo(f"Error: unknown agent {agent!r}; known: {known_agents()}", err=True)
        raise typer.Exit(1)

    try:
        run = run_service.start_run(
            conn, lock, mission_id=mission_id, agent_runtime=agent
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(run.id)

    if not execute:
        return

    # Intelligence Layer: feed the agent the live, secret-redacted ATLAS context
    # (Current Focus + Project + recent runs) ahead of the mission intent. The
    # executor owns the terminal transition and never leaves the run 'running'.
    prompt = _run_prompt(conn, mission_id)
    outcome = run_executor.execute_run(
        conn, lock, agent=get_agent(agent), mission_id=mission_id, run_id=run.id, prompt=prompt
    )
    typer.echo(outcome.status)


@mission_app.command("retry")
def retry_mission(
    mission_id: str = typer.Argument(..., help="Failed/cancelled mission ID to retry"),
    agent: str = typer.Option(
        "native", "--agent", help="Agent runtime to record/use: native | claude_code"
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Execute the retry run synchronously via the selected agent runtime (blocks)",
    ),
) -> None:
    """Reopen a failed/cancelled mission and start a fresh run; print the run ID.

    Reopens the mission in place (``failed|cancelled -> pending``), preserving
    prior runs as attempt history, then starts a new run on the same mission.
    With --execute, the new run is executed synchronously like ``mission run``.
    """
    from atlas_runtime.agents import get_agent, known_agents

    conn = _get_connection()
    lock = _get_lock()

    if agent not in known_agents():
        typer.echo(f"Error: unknown agent {agent!r}; known: {known_agents()}", err=True)
        raise typer.Exit(1)

    try:
        mission_service.retry_mission(conn, lock, mission_id=mission_id)
        run = run_service.start_run(
            conn, lock, mission_id=mission_id, agent_runtime=agent
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(run.id)

    if not execute:
        return

    prompt = _run_prompt(conn, mission_id)
    outcome = run_executor.execute_run(
        conn, lock, agent=get_agent(agent), mission_id=mission_id, run_id=run.id, prompt=prompt
    )
    typer.echo(outcome.status)


@mission_app.command("cancel")
def cancel(
    mission_id: str = typer.Argument(..., help="Mission ID to cancel"),
) -> None:
    """Cancel all active runs for the given mission."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        rows = conn.execute(
            "SELECT id, status FROM runs WHERE mission_id=? AND status='running'",
            (mission_id,),
        ).fetchall()
        if not rows:
            typer.echo("no active run")
            return
        for run_id, _ in rows:
            run_service.cancel_run(conn, lock, run_id=run_id, mission_id=mission_id)
        typer.echo("cancelled")
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


@mission_app.command("archive")
def archive(
    mission_id: str = typer.Argument(..., help="Mission ID to archive"),
    delete_after_days: int = typer.Option(
        30,
        "--delete-after-days",
        min=1,
        help="Delete archived mission after this many days",
    ),
) -> None:
    """Archive a succeeded/completed mission and print its ID."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        mission = mission_service.archive_mission(
            conn,
            lock,
            mission_id=mission_id,
            delete_after_days=delete_after_days,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(mission.id)


@mission_app.command("purge-archived")
def purge_archived() -> None:
    """Delete archived missions whose retention deadline has passed."""
    conn = _get_connection()
    lock = _get_lock()
    count = mission_service.purge_expired_archives(conn, lock)
    typer.echo(str(count))


@mission_app.command("status")
def status(
    mission_id: str = typer.Argument(..., help="Mission ID to query"),
) -> None:
    """Print the status of the given mission."""
    conn = _get_connection()
    row = conn.execute(
        "SELECT status FROM missions WHERE id=?", (mission_id,)
    ).fetchone()
    if row is None:
        typer.echo("not found")
        raise typer.Exit(1)
    typer.echo(row[0])


# ---------------------------------------------------------------------------
# project subcommands
# ---------------------------------------------------------------------------


@project_app.command("create")
def project_create(
    name: str = typer.Option(..., "--name", help="Project name"),
    path: str = typer.Option(..., "--path", help="Folder to create for the project"),
) -> None:
    """Create a NEW project folder and register it. Prints the project ID."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        project = project_service.create_project(conn, lock, name=name, root_path=path)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(project.id)


@project_app.command("register")
def project_register(
    name: str = typer.Option(..., "--name", help="Project name"),
    path: str = typer.Option(..., "--path", help="Existing folder to adopt"),
) -> None:
    """Register an EXISTING folder as a project. Prints the project ID."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        project = project_service.register_project(conn, lock, name=name, root_path=path)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(project.id)


@project_app.command("list")
def project_list() -> None:
    """List all projects as 'id<TAB>name<TAB>root_path'."""
    conn = _get_connection()
    for p in project_service.list_projects(conn):
        typer.echo(f"{p.id}\t{p.name}\t{p.root_path}")


# ---------------------------------------------------------------------------
# run subcommands — background-safe execution of an already-started run
# ---------------------------------------------------------------------------


def _run_prompt(conn: sqlite3.Connection, mission_id: str) -> str:
    """Assemble the secret-redacted operator context + mission intent."""
    ctx = context_service.assemble_context(conn, mission_id=mission_id)
    row = conn.execute("SELECT intent FROM missions WHERE id=?", (mission_id,)).fetchone()
    intent = row[0] if row and row[0] else ""
    return ctx.markdown + ("\n\n---\n\n" + intent if intent else "")


@run_app.command("exec")
def run_exec(
    run_id: str = typer.Argument(..., help="Run ID (already started, 'running') to execute"),
    agent: str = typer.Option("native", "--agent", help="Agent runtime: native | claude_code"),
) -> None:
    """Execute an already-started run to a terminal state.

    Assembles context, drives the agent, and transitions the run. Intended to be
    spawned by the gateway as a detached subprocess for background execution, so
    `POST /v1/missions/{id}/run` can return the run_id immediately.
    """
    from atlas_runtime.agents import get_agent, known_agents

    conn = _get_connection()
    lock = _get_lock()
    if agent not in known_agents():
        typer.echo(f"Error: unknown agent {agent!r}; known: {known_agents()}", err=True)
        raise typer.Exit(1)
    row = conn.execute("SELECT mission_id, status FROM runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        typer.echo(f"Error: run {run_id!r} not found", err=True)
        raise typer.Exit(1)
    mission_id, status = row
    if status != "running":
        typer.echo(f"Error: run is {status!r}, not running", err=True)
        raise typer.Exit(1)
    prompt = _run_prompt(conn, mission_id)
    outcome = run_executor.execute_run(
        conn, lock, agent=get_agent(agent), mission_id=mission_id, run_id=run_id, prompt=prompt
    )
    typer.echo(outcome.status)


# ---------------------------------------------------------------------------
# focus subcommands — Command Center Current Focus
# ---------------------------------------------------------------------------


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


@focus_app.command("create")
def focus_create(
    title: str = typer.Option(..., "--title", help="The current focus statement"),
    framework: str = typer.Option("", "--framework", help="Operative framework/approach"),
    priorities: str = typer.Option("", "--priorities", help="Comma-separated priorities"),
    drivers: str = typer.Option("", "--drivers", help="Comma-separated drivers"),
    project_id: str = typer.Option("", "--project", help="Bind to a project id"),
) -> None:
    """Create the Current Focus (archives any prior active one); prints its id."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        focus = focus_service.create_focus(
            conn,
            lock,
            title=title,
            framework=framework,
            priorities=_split_csv(priorities),
            drivers=_split_csv(drivers),
            project_id=project_id or None,
        )
    except focus_service.FocusError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(focus.id)


@focus_app.command("show")
def focus_show() -> None:
    """Print the Current Focus as JSON, or 'none'."""
    conn = _get_connection()
    focus = focus_service.get_current_focus(conn)
    typer.echo("none" if focus is None else json.dumps(focus.model_dump()))


@focus_app.command("list")
def focus_list(
    include_archived: bool = typer.Option(False, "--all", help="Include archived focuses"),
) -> None:
    """Print Focus rows as a JSON array (active only unless --all)."""
    conn = _get_connection()
    items = focus_service.list_focus(conn, include_archived=include_archived)
    typer.echo(json.dumps([f.model_dump() for f in items]))


@focus_app.command("archive")
def focus_archive(focus_id: str = typer.Argument(..., help="Focus ID to archive")) -> None:
    """Archive a Focus (clears it as Current)."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        focus_service.archive_focus(conn, lock, focus_id)
    except focus_service.FocusError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo("archived")


# ---------------------------------------------------------------------------
# goal / task / observe subcommands — Command Center goal hierarchy
# ---------------------------------------------------------------------------


@goal_app.command("create")
def goal_create(
    title: str = typer.Option(..., "--title", help="Goal title"),
    description: str = typer.Option("", "--description", help="Rich goal description/brief"),
    focus_id: str = typer.Option("", "--focus", help="Focus id this goal serves"),
    parent_goal_id: str = typer.Option("", "--parent", help="Parent goal id (creates a sub-goal)"),
    status: str = typer.Option("open", "--status", help="open|active|done|archived"),
) -> None:
    """Create a goal (or sub-goal via --parent); prints its id."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        goal = goal_service.create_goal(
            conn, lock,
            title=title, description=description,
            focus_id=focus_id or None, parent_goal_id=parent_goal_id or None, status=status,
        )
    except goal_service.GoalError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(goal.id)


@goal_app.command("list")
def goal_list(
    focus_id: str = typer.Option("", "--focus", help="Filter to a focus id"),
    include_archived: bool = typer.Option(False, "--all", help="Include archived goals"),
) -> None:
    """Print goals as a JSON array (non-archived unless --all)."""
    conn = _get_connection()
    items = goal_service.list_goals(
        conn, focus_id=focus_id or None, include_archived=include_archived
    )
    typer.echo(json.dumps([g.model_dump() for g in items]))


@goal_app.command("tree")
def goal_tree(focus_id: str = typer.Argument(..., help="Focus id to build the tree for")) -> None:
    """Print the nested goal tree (goals → children → tasks → observations) as JSON."""
    conn = _get_connection()
    typer.echo(json.dumps(goal_service.build_goal_tree(conn, focus_id=focus_id)))


@goal_app.command("update")
def goal_update(
    goal_id: str = typer.Argument(..., help="Goal id"),
    title: str = typer.Option("", "--title", help="New title"),
    description: str = typer.Option("", "--description", help="New description"),
    status: str = typer.Option("", "--status", help="open|active|done|archived"),
) -> None:
    """Patch a goal's fields (only provided ones change); prints 'updated'."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        goal_service.update_goal(
            conn, lock, goal_id,
            title=title or None, description=description or None, status=status or None,
        )
    except goal_service.GoalError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo("updated")


@goal_app.command("archive")
def goal_archive(goal_id: str = typer.Argument(..., help="Goal id to archive (cascades to sub-goals)")) -> None:
    """Archive a goal and its sub-goals."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        goal_service.archive_goal(conn, lock, goal_id)
    except goal_service.GoalError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo("archived")


@task_app.command("add")
def task_add(
    goal_id: str = typer.Option(..., "--goal", help="Goal id this task belongs to"),
    title: str = typer.Option(..., "--title", help="Task title"),
) -> None:
    """Add a task under a goal; prints its id."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        task = goal_service.create_task(conn, lock, goal_id=goal_id, title=title)
    except goal_service.GoalError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(task.id)


@task_app.command("list")
def task_list(goal_id: str = typer.Argument(..., help="Goal id")) -> None:
    """Print a goal's tasks as a JSON array."""
    conn = _get_connection()
    typer.echo(json.dumps([t.model_dump() for t in goal_service.list_tasks(conn, goal_id=goal_id)]))


@task_app.command("status")
def task_status(
    task_id: str = typer.Argument(..., help="Task id"),
    status: str = typer.Option(..., "--status", help="todo|doing|done"),
) -> None:
    """Set a task's status; prints 'updated'."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        goal_service.set_task_status(conn, lock, task_id, status)
    except goal_service.GoalError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo("updated")


@observe_app.command("add")
def observe_add(
    body: str = typer.Option(..., "--body", help="The observation text"),
    goal_id: str = typer.Option("", "--goal", help="Goal id to attach to"),
    run_id: str = typer.Option("", "--run", help="Run id to attach to"),
    source: str = typer.Option("operator", "--source", help="Provenance: operator|run:<id>|compounding-loop"),
) -> None:
    """Append an observation to a goal and/or run; prints its id."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        obs = goal_service.add_observation(
            conn, lock, body=body, goal_id=goal_id or None, run_id=run_id or None, source=source
        )
    except goal_service.GoalError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(obs.id)


@observe_app.command("list")
def observe_list(
    goal_id: str = typer.Option("", "--goal", help="Filter to a goal id"),
    run_id: str = typer.Option("", "--run", help="Filter to a run id"),
) -> None:
    """Print observations as a JSON array (newest first)."""
    conn = _get_connection()
    items = goal_service.list_observations(conn, goal_id=goal_id or None, run_id=run_id or None)
    typer.echo(json.dumps([o.model_dump() for o in items]))


@operation_app.command("list")
def operation_list() -> None:
    """Print the available premade operations as a JSON array."""
    ops = operation_service.list_operations()
    typer.echo(
        json.dumps(
            [{"id": o.id, "label": o.label, "description": o.description, "agent": o.agent, "risk": o.risk} for o in ops]
        )
    )


@operation_app.command("prepare")
def operation_prepare(
    op_id: str = typer.Option(..., "--op", help="Operation id (elaborate|recon|blockers|decompose)"),
    goal_id: str = typer.Option(..., "--goal", help="Goal id the operation targets"),
    agent: str = typer.Option("", "--agent", help="Agent runtime override (else the operation default)"),
) -> None:
    """Create a mission+run for an operation on a goal; prints the run id.

    Does NOT execute — the caller (gateway) spawns a detached `run exec` so the
    response returns immediately. The rendered operation instruction becomes the
    mission intent; the executor prepends the operator context ahead of it.
    """
    conn = _get_connection()
    lock = _get_lock()
    op = operation_service.get_operation(op_id)
    if op is None:
        typer.echo(f"Error: unknown operation {op_id!r}", err=True)
        raise typer.Exit(1)
    goal = goal_service.get_goal(conn, goal_id)
    if goal is None:
        typer.echo(f"Error: goal {goal_id!r} not found", err=True)
        raise typer.Exit(1)
    focus = focus_service.get_current_focus(conn)
    try:
        intent = operation_service.build_intent(op_id, goal=goal, focus=focus)
    except operation_service.OperationError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    project_id = focus.project_id if focus is not None else None
    mission = mission_service.create_mission(
        conn, lock, title=f"{op.label}: {goal.title}"[:120], intent=intent, project_id=project_id
    )
    run = run_service.start_run(
        conn, lock, mission_id=mission.id, agent_runtime=(agent or op.agent)  # type: ignore[arg-type]
    )
    typer.echo(run.id)


# ---------------------------------------------------------------------------
# runtime subcommands — in-process executor daemon (background execution, b)
# ---------------------------------------------------------------------------


@runtime_app.command("serve")
def runtime_serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host (loopback by default)"),
    port: int = typer.Option(8585, "--port", help="Bind port"),
) -> None:
    """Run the long-lived run-executor daemon (blocks).

    Hosts the in-process async executor over HTTP so the gateway can enqueue runs
    that execute on daemon-managed threads (the alternative to detached
    subprocesses). POST /v1/runs/enqueue {mission_id, agent}.
    """
    from atlas_runtime import runtime_daemon

    typer.echo(f"atlas runtime daemon on http://{host}:{port}")
    runtime_daemon.serve(host=host, port=port)


# ---------------------------------------------------------------------------
# db subcommands — migration runner (atlas db init / status)
# ---------------------------------------------------------------------------


@db_app.command("init")
def db_init() -> None:
    """Apply all pending migrations to ~/.atlas/atlas.db (idempotent, non-destructive)."""
    conn = db.connect()
    applied = db.apply_migrations(conn)
    if applied:
        for version in applied:
            typer.echo(f"applied {version}")
    else:
        typer.echo("already up to date")


@db_app.command("status")
def db_status() -> None:
    """Show each migration as applied [x] or pending [ ]."""
    conn = db.connect()
    for version, ok in db.migration_status(conn):
        typer.echo(f"{'[x]' if ok else '[ ]'} {version}")


# ---------------------------------------------------------------------------
# gateway subcommands — lifecycle primitive (atlas gateway start/status/stop)
# ---------------------------------------------------------------------------


@gateway_app.command("start")
def gateway_start() -> None:
    """Start the gateway if not already running; block until healthy."""
    from atlas_runtime import gateway_control

    ok, message = gateway_control.start()
    typer.echo(message)
    if not ok:
        raise typer.Exit(1)


@gateway_app.command("status")
def gateway_status() -> None:
    """Print 'online' or 'offline' based on the gateway /health endpoint."""
    from atlas_runtime import gateway_control

    typer.echo("online" if gateway_control.health_ok() else "offline")


@gateway_app.command("stop")
def gateway_stop() -> None:
    """Stop a gateway started by this CLI (via its PID file)."""
    from atlas_runtime import gateway_control

    ok, message = gateway_control.stop()
    typer.echo(message)
    if not ok:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# module subcommands — optional activatable modules (atlas module list/activate)
# ---------------------------------------------------------------------------


@module_app.command("list")
def module_list() -> None:
    """List modules as 'id<TAB>status<TAB>name'."""
    from atlas_runtime import module_service

    conn = _get_connection()
    for mod in module_service.list_modules(conn):
        typer.echo(f"{mod.id}\t{mod.status}\t{mod.name}")


@module_app.command("activate")
def module_activate(
    module_id: str = typer.Argument(..., help="Module id to activate (e.g. cashflow)"),
) -> None:
    """Activate an optional module."""
    from atlas_runtime import module_service

    conn = _get_connection()
    lock = _get_lock()
    try:
        mod = module_service.set_active(conn, lock, module_id=module_id, active=True)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"{mod.id} {mod.status}")


@module_app.command("deactivate")
def module_deactivate(
    module_id: str = typer.Argument(..., help="Module id to deactivate"),
) -> None:
    """Deactivate an optional module."""
    from atlas_runtime import module_service

    conn = _get_connection()
    lock = _get_lock()
    try:
        mod = module_service.set_active(conn, lock, module_id=module_id, active=False)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"{mod.id} {mod.status}")


# ---------------------------------------------------------------------------
# cashflow subcommands — vendored module process control
# ---------------------------------------------------------------------------


@cashflow_app.command("start")
def cashflow_start(
    backend: str = typer.Option(
        "local", "--backend", help="DB backend: local | supabase"
    ),
) -> None:
    """Start the cashflow app with the chosen DB backend."""
    from atlas_runtime import cashflow_control

    ok, message = cashflow_control.start(backend=backend)
    typer.echo(message)
    if not ok:
        raise typer.Exit(1)


@cashflow_app.command("status")
def cashflow_status() -> None:
    """Print cashflow process status as 'running|stopped <backend>'."""
    from atlas_runtime import cashflow_control

    st = cashflow_control.status()
    typer.echo(f"{'running' if st['running'] else 'stopped'} {st['backend']}")


@cashflow_app.command("stop")
def cashflow_stop() -> None:
    """Stop the cashflow process started by this CLI."""
    from atlas_runtime import cashflow_control

    ok, message = cashflow_control.stop()
    typer.echo(message)
    if not ok:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
