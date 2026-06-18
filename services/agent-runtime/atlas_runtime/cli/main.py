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

import typer

from atlas_runtime import db, mission_service, project_service, run_service

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

try:
    from atlas_wiki.cli.main import wiki_app
    app.add_typer(wiki_app, name="wiki")
except ImportError:
    pass  # wiki service not installed — skip wiki subcommands gracefully

from atlas_runtime.cli.foundation import foundation_app
app.add_typer(foundation_app, name="foundation")

from atlas_runtime.cli.models import models_app
app.add_typer(models_app, name="models")

from atlas_runtime.cli.channels import channels_app
app.add_typer(channels_app, name="channels")

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

    try:
        row = conn.execute(
            "SELECT intent FROM missions WHERE id=?", (mission_id,)
        ).fetchone()
        prompt = row[0] if row and row[0] else ""
        outcome = get_agent(agent).execute(
            conn, lock, mission_id=mission_id, run_id=run.id, prompt=prompt
        )
        run_service.complete_run(
            conn,
            lock,
            run_id=run.id,
            mission_id=mission_id,
            status=outcome.status,
            summary=outcome.summary,
        )
        typer.echo(outcome.status)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


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


if __name__ == "__main__":
    app()
