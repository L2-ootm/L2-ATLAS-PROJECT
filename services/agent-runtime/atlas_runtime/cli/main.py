"""ATLAS CLI — atlas mission create|run|cancel|status subcommands.

Entry point: atlas_runtime.cli.main:app (registered in pyproject.toml [project.scripts]).

Design:
  - CLI handlers are thin wrappers only. No SQL, no emit() directly.
  - All business logic goes through the service layer (mission_service, run_service).
  - _get_connection() and _get_lock() are module-level factories; monkeypatch in tests.
"""
from __future__ import annotations

import pathlib
import sqlite3
import threading

import typer

from atlas_runtime import mission_service, project_service, run_service

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = typer.Typer()
mission_app = typer.Typer(name="mission")
app.add_typer(mission_app, name="mission")
project_app = typer.Typer(name="project")
app.add_typer(project_app, name="project")

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
    """Return a file-backed SQLite connection with WAL + FK enabled."""
    db_path = pathlib.Path.home() / ".atlas" / "atlas.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
) -> None:
    """Start a Run for the given mission and print the run ID."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        run = run_service.start_run(conn, lock, mission_id=mission_id)
        typer.echo(run.id)
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


if __name__ == "__main__":
    app()
