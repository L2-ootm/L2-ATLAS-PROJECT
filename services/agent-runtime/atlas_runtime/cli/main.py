"""ATLAS CLI — atlas mission create|run|cancel|status subcommands.

Entry point: atlas_runtime.cli.main:app (registered in pyproject.toml [project.scripts]).

Design:
  - CLI handlers are thin wrappers only. No SQL, no emit() directly.
  - All business logic goes through the service layer (mission_service, run_service).
  - _get_connection() and _get_lock() are module-level factories; monkeypatch in tests.
"""
# Typer command registration intentionally interleaves imports with app construction.
# ruff: noqa: E402

from __future__ import annotations

import os
import pathlib
import sqlite3
import threading
import json
from typing import Optional

import typer

from atlas_runtime import (
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

app = typer.Typer(
    help=(
        "ATLAS - an auditable AI operating system for technical operators.\n\n"
        "Run bare `atlas` to open the terminal workbench. Common starting points:\n"
        "  atlas provider modes     show how you can wire a model\n"
        "  atlas provider status    what the active provider resolves to\n"
        "  atlas setup              first-run configuration wizard\n"
        "  atlas mission run <id> --execute   run an agent for real\n"
        "  atlas doctor             diagnose your install"
    ),
    no_args_is_help=False,  # bare `atlas` launches the workbench (see _root callback)
    add_completion=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
mission_app = typer.Typer(name="mission", help="Create, run, retry, and cancel agent missions.")
app.add_typer(mission_app, name="mission")
project_app = typer.Typer(name="project", help="Register and manage Project workspaces.")
app.add_typer(project_app, name="project")
db_app = typer.Typer(name="db", help="Database lifecycle: apply migrations, inspect status.")
app.add_typer(db_app, name="db")
gateway_app = typer.Typer(name="gateway", help="Gateway lifecycle: start, status, stop.")
app.add_typer(gateway_app, name="gateway")
module_app = typer.Typer(name="module", help="Optional modules: list, activate, deactivate.")
app.add_typer(module_app, name="module")
cashflow_app = typer.Typer(name="cashflow", help="Cashflow module process: start, status, stop.")
app.add_typer(cashflow_app, name="cashflow")
freellmapi_app = typer.Typer(name="freellmapi", help="FreeLLMAPI sidecar endpoint: install, start, status, stop.")
app.add_typer(freellmapi_app, name="freellmapi")
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
from atlas_runtime.cli.golden import golden_app
app.add_typer(golden_app, name="golden")
runtime_app = typer.Typer(name="runtime", help="In-process run executor daemon (background execution, b).")
app.add_typer(runtime_app, name="runtime")

try:
    from atlas_wiki.cli.main import wiki_app
    _WIKI_CLI_AVAILABLE = True
except ImportError:
    _WIKI_CLI_AVAILABLE = False

    @app.command("wiki", help="Wiki runtime commands (optional service).")
    def _missing_wiki() -> None:
        typer.echo(
            "wiki service is not installed; install the wiki runtime package to enable "
            "`atlas wiki` commands.",
            err=True,
        )
        raise typer.Exit(1)

if _WIKI_CLI_AVAILABLE:
    app.add_typer(wiki_app, name="wiki")

from atlas_runtime.cli.foundation import foundation_app
app.add_typer(foundation_app, name="foundation")

from atlas_runtime.cli.config import config_app, setup as _setup_cmd
app.add_typer(config_app, name="config")
app.command("setup", help="First-run wizard: configure ATLAS and write ~/.atlas/config.yaml.")(_setup_cmd)

from atlas_runtime.cli.auth import auth_app
app.add_typer(auth_app, name="auth")

from atlas_runtime.cli.models import models_app
app.add_typer(models_app, name="models")

from atlas_runtime.cli.provider import provider_app
app.add_typer(provider_app, name="provider")

from atlas_runtime.cli.channels import channels_app
app.add_typer(channels_app, name="channels")

from atlas_runtime.cli.discord import discord_app
app.add_typer(discord_app, name="discord")

from atlas_runtime.cli.tools import tools_app
app.add_typer(tools_app, name="tools")

from atlas_runtime.cli.surface import surface_app
app.add_typer(surface_app, name="surface")

terminal_app = typer.Typer(name="terminal", help="atlas-terminal (donor-based TUI surface) build/reachability status.")
app.add_typer(terminal_app, name="terminal")


@terminal_app.command("status", help="Is atlas-terminal built, what version, is the gateway reachable.")
def _terminal_status_cmd(
    json_output: bool = typer.Option(False, "--json", help="Emit as JSON."),
) -> None:
    from atlas_runtime import gateway_control
    from atlas_runtime.db import MIGRATIONS_DIR

    root = MIGRATIONS_DIR.parent.parent  # infra/migrations -> infra -> repo root
    terminal_dir = root / "services" / "atlas-terminal"
    package_json = terminal_dir / "package.json"
    built = (terminal_dir / "node_modules").is_dir()
    version = None
    if package_json.is_file():
        try:
            version = json.loads(package_json.read_text(encoding="utf-8")).get("version")
        except Exception:  # noqa: BLE001
            version = None
    gateway_reachable = gateway_control.health_ok()

    report = {
        "present": terminal_dir.is_dir(),
        "built": built,
        "version": version,
        "gateway_reachable": gateway_reachable,
    }
    if json_output:
        typer.echo(json.dumps(report))
        return
    typer.echo(f"present: {report['present']}")
    typer.echo(f"built (bun install ran): {built}")
    typer.echo(f"version: {version or 'unknown'}")
    typer.echo(f"gateway reachable: {gateway_reachable}")
    if not report["present"] or not built:
        typer.echo("remediation: cd services/atlas-terminal && bun install && bun run typecheck")


import atlas_runtime.cli.atlas_terminal as _atlas_terminal_mod
import atlas_runtime.cli.go_tui as _go_tui_mod
from atlas_runtime.cli.tui import legacy_foundation_tui


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    no_context: bool = typer.Option(
        False,
        "--no-context",
        help="Skip operator-context injection (Current Focus / goals / Operating Contract) for runs started from this session.",
    ),
) -> None:
    """ATLAS — bare invocation launches the terminal workbench."""
    # Central rotating file log for every CLI entry point (F13). Fail-open.
    from atlas_runtime import logging_config

    logging_config.configure_logging()
    if no_context:
        import os

        os.environ["ATLAS_SKIP_CONTEXT"] = "1"
    if ctx.invoked_subcommand is None:
        _launch_atlas_terminal(work_dir=_prompt_workspace_scope())


def _prompt_workspace_scope() -> Optional[str]:
    """Ask whether this session works in the current folder or the global workspace.

    Returns the chosen directory, or None to defer to the launcher default
    (ATLAS_WORK_DIR env override, else the current folder). Skipped when
    ATLAS_WORK_DIR is already set (explicit choice), when stdio is not a TTY,
    or when the current folder already is the global workspace root.
    """
    import os
    import sys

    if os.environ.get("ATLAS_WORK_DIR", "").strip():
        return None
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None
    from atlas_runtime import workspace_service

    cwd = os.getcwd()
    global_root = str(workspace_service.global_root())
    if os.path.normcase(os.path.abspath(cwd)) == os.path.normcase(global_root):
        return None
    typer.echo("Workspace scope:")
    typer.echo(f"  1) this folder            {cwd}")
    typer.echo(f"  2) default ATLAS workspace {global_root}")
    choice = typer.prompt("Execute in", default="1").strip()
    return global_root if choice == "2" else cwd


def _launch_atlas_terminal(gateway: Optional[str] = None, work_dir: Optional[str] = None) -> None:
    try:
        return_code = _atlas_terminal_mod.launch(gateway, work_dir=work_dir)
    except _atlas_terminal_mod.TerminalLaunchError as exc:
        typer.echo(f"terminal UI unavailable: {exc}", err=True)
        raise typer.Exit(1)
    if return_code:
        raise typer.Exit(return_code)


def _launch_go_tui(gateway: Optional[str] = None) -> None:
    try:
        return_code = _go_tui_mod.launch(gateway)
    except _go_tui_mod.TUILaunchError as exc:
        typer.echo(f"terminal UI unavailable: {exc}", err=True)
        raise typer.Exit(1)
    if return_code:
        raise typer.Exit(return_code)


@app.command("version", help="Print the ATLAS runtime version.")
def _version_cmd(
    json_output: bool = typer.Option(False, "--json", help="Emit as JSON."),
) -> None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        ver = version("atlas-runtime")
    except PackageNotFoundError:  # running from a source checkout without install
        ver = "0.1.0+dev"
    if json_output:
        typer.echo(json.dumps({"name": "atlas", "version": ver}))
    else:
        typer.echo(f"atlas {ver}")


@app.command("logs", help="Tail the ATLAS rotating log file (<ATLAS home>/logs/atlas.log).")
def _logs_cmd(
    tail: int = typer.Option(50, "--tail", "-n", help="Number of most recent lines to print (0 for the whole file)."),
    follow: bool = typer.Option(False, "--follow", "-f", help="Keep streaming new lines as they're written (Ctrl-C to stop)."),
    path_out: bool = typer.Option(False, "--path", help="Print the resolved log file path and exit."),
) -> None:
    from atlas_runtime import logging_config

    log_path = logging_config.log_file_path()
    if path_out:
        typer.echo(str(log_path))
        return
    if not log_path.exists():
        typer.echo(f"no log file yet at {log_path} (nothing has logged through atlas_runtime.logging_config in this ATLAS home)")
        raise typer.Exit(1)

    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    for line in (lines[-tail:] if tail > 0 else lines):
        typer.echo(line)

    if follow:
        import os
        import time

        fh = log_path.open("r", encoding="utf-8", errors="replace")
        try:
            fh.seek(0, os.SEEK_END)
            while True:
                line = fh.readline()
                if line:
                    typer.echo(line.rstrip("\n"))
                    continue
                time.sleep(0.5)
                try:
                    # RotatingFileHandler rotates by rename; a shrunk size means
                    # a fresh file was created at this path underneath us.
                    if log_path.stat().st_size < fh.tell():
                        fh.close()
                        fh = log_path.open("r", encoding="utf-8", errors="replace")
                except OSError:
                    pass
        except KeyboardInterrupt:
            pass
        finally:
            fh.close()


@app.command("tui", help="Launch the ATLAS terminal workbench.")
def _tui_cmd(
    gateway: Optional[str] = typer.Option(
        None,
        "--gateway",
        help="ATLAS gateway base URL (default: ATLAS_GATEWAY_URL or loopback :8484).",
    ),
) -> None:
    _launch_atlas_terminal(gateway, work_dir=_prompt_workspace_scope())


@app.command(
    "dev-go-tui",
    hidden=True,
    help="Launch the legacy Go/BubbleTea TUI (fallback until atlas-terminal UAT passes).",
)
def _dev_go_tui_cmd(
    gateway: Optional[str] = typer.Option(
        None,
        "--gateway",
        help="ATLAS gateway base URL (default: ATLAS_GATEWAY_URL or loopback :8484).",
    ),
) -> None:
    _launch_go_tui(gateway)


app.command(
    "dev-foundation-tui",
    hidden=True,
    help="Run the legacy vendored TUI from source (checkout-only, hidden).",
)(legacy_foundation_tui)

# Module-level lock singleton (monkeypatched in tests via _get_lock)
_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Connection + lock factories (injectable for tests)
# ---------------------------------------------------------------------------

# Surface-session liveness TTL: 3x a nominal 30s heartbeat interval (RESEARCH
# Pattern 5). A session whose heartbeat is older than this is treated as orphaned
# by the startup reconciliation sweep.
_HEARTBEAT_TTL_SECONDS = 90.0


def _get_connection() -> sqlite3.Connection:
    """Return a file-backed SQLite connection with WAL + FK enabled.

    Auto-applies any pending migrations on first use per process (idempotent,
    drift-tolerant). The gateway is dispatch-only (D-022) and shells out to the
    CLI for writes, so applying Python migrations before it reads is safe.
    """
    conn = db.connect()
    db.apply_migrations(conn)
    return conn


def _get_lock() -> threading.Lock:
    """Return the module-level threading.Lock singleton."""
    return _LOCK


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
        "native", "--agent", help="Agent runtime to record/use: native | claude_code | codex"
    ),
    session_id: str | None = typer.Option(
        None,
        "--session-id",
        help="Owning shared surface-session id.",
    ),
    goal: bool = typer.Option(
        False,
        "--goal",
        help="Enable the bounded judge-and-continue mission loop.",
    ),
    judge_model: str = typer.Option(
        "",
        "--judge-model",
        help="Judge override in provider/model form; empty inherits the chat session.",
    ),
    max_runs: int = typer.Option(
        12,
        "--max-runs",
        min=1,
        max=100,
        help="Maximum attempts for a goal mission.",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Execute the run synchronously via the selected agent runtime (blocks)",
    ),
    show_context: bool = typer.Option(
        False,
        "--show-context",
        help="Print the assembled context brief and exit without starting a run (debug)",
    ),
) -> None:
    """Start a Run for the given mission and print the run ID.

    With --execute, run it synchronously through the selected agent runtime
    and emit the audit trail. Without --execute the run is recorded with the
    chosen runtime but not executed (gateway-safe, non-blocking).
    """
    from atlas_runtime.agents import known_agents

    conn = _get_connection()
    lock = _get_lock()

    if show_context:
        _print_context(conn, mission_id)
        return

    if agent not in known_agents():
        typer.echo(f"Error: unknown agent {agent!r}; known: {known_agents()}", err=True)
        raise typer.Exit(1)

    try:
        if goal:
            from atlas_runtime import mission_loop_service  # noqa: PLC0415

            mission_loop_service.configure_loop(
                conn,
                lock,
                mission_id=mission_id,
                session_id=session_id,
                judge_model=judge_model,
                max_runs=max_runs,
            )
        run = run_service.start_run(
            conn,
            lock,
            mission_id=mission_id,
            session_id=session_id,
            agent_runtime=agent,
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
    outcome = _execute_run_chain(
        conn, lock, agent_name=agent, mission_id=mission_id, run_id=run.id
    )
    typer.echo(outcome.status)


@mission_app.command("retry")
def retry_mission(
    mission_id: str = typer.Argument(..., help="Failed/cancelled mission ID to retry"),
    agent: str = typer.Option(
        "native", "--agent", help="Agent runtime to record/use: native | claude_code | codex"
    ),
    session_id: str | None = typer.Option(
        None,
        "--session-id",
        help="Owning shared surface-session id.",
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
            conn,
            lock,
            mission_id=mission_id,
            session_id=session_id,
            agent_runtime=agent,
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


def _mission_workdir(conn: sqlite3.Connection, mission_id: str) -> Optional[str]:
    """The registered project root this mission is bound to, or None.

    A mission carries `project_id` when the operator bound a workspace
    (console binding, `mission create --project`). Runs must execute INSIDE
    that root — without this, every agent runs in whatever cwd the gateway
    happened to be started from, and the binding is cosmetic.
    """
    row = conn.execute(
        "SELECT project_id FROM missions WHERE id=?", (mission_id,)
    ).fetchone()
    project_id = row[0] if row else None
    if not project_id:
        return None
    try:
        project = project_service.get_project(conn, project_id)
    except Exception:  # noqa: BLE001 — a broken project must not block the run
        return None
    if project is None:
        return None
    root = pathlib.Path(project.root_path).expanduser()
    return str(root) if root.is_dir() else None


def _run_prompt(conn: sqlite3.Connection, mission_id: str) -> str:
    """Assemble the secret-redacted operator context + mission intent."""
    ctx = context_service.assemble_context(conn, mission_id=mission_id)
    row = conn.execute("SELECT intent FROM missions WHERE id=?", (mission_id,)).fetchone()
    intent = row[0] if row and row[0] else ""
    return ctx.markdown + ("\n\n---\n\n" + intent if intent else "")


def _print_context(conn: sqlite3.Connection, mission_id: str) -> None:
    """Print the assembled context brief with a provenance/budget header (debug)."""
    from atlas_runtime.memory_router import estimate_tokens

    ctx = context_service.assemble_context(conn, mission_id=mission_id)
    typer.echo(f"# context: {len(ctx.sources)} sources, ~{estimate_tokens(ctx.markdown)} tokens")
    if ctx.sources:
        typer.echo("# sources: " + ", ".join(ctx.sources))
    typer.echo(ctx.markdown)


@run_app.command("exec")
def run_exec(
    run_id: str = typer.Argument(..., help="Run ID (already started, 'running') to execute"),
    agent: str | None = typer.Option(
        None,
        "--agent",
        help="Agent runtime override; default discovers the persisted run runtime.",
    ),
) -> None:
    """Execute an already-started run to a terminal state.

    Assembles context, drives the agent, and transitions the run. Intended to be
    spawned by the gateway as a detached subprocess for background execution, so
    `POST /v1/missions/{id}/run` can return the run_id immediately.
    """
    from atlas_runtime.agents import known_agents

    conn = _get_connection()
    lock = _get_lock()
    row = conn.execute(
        "SELECT mission_id, status, agent_runtime FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    if row is None:
        typer.echo(f"Error: run {run_id!r} not found", err=True)
        raise typer.Exit(1)
    mission_id, status, persisted_agent = row
    agent_name = agent or persisted_agent or "native"
    if agent_name not in known_agents():
        typer.echo(f"Error: unknown agent {agent_name!r}; known: {known_agents()}", err=True)
        raise typer.Exit(1)
    if status != "running":
        typer.echo(f"Error: run is {status!r}, not running", err=True)
        raise typer.Exit(1)
    # Execute inside the mission's bound project root. Safe process-wide:
    # this CLI command is spawned as a dedicated detached subprocess per run
    # (see docstring), so chdir cannot leak across runs.
    workdir = _mission_workdir(conn, mission_id)
    if workdir:
        os.chdir(workdir)
    outcome = _execute_run_chain(
        conn, lock, agent_name=agent_name, mission_id=mission_id, run_id=run_id
    )
    typer.echo(outcome.status)


def _execute_run_chain(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    agent_name: str,
    mission_id: str,
    run_id: str,
):
    """Execute one ordinary run or the bounded chain owned by a goal worker."""
    from atlas_runtime import mission_loop_service  # noqa: PLC0415
    from atlas_runtime.agents import get_agent  # noqa: PLC0415

    agent = get_agent(agent_name)
    current_run_id = run_id
    outcome = None
    while True:
        prompt = _run_prompt(conn, mission_id)
        outcome = run_executor.execute_run(
            conn,
            lock,
            agent=agent,
            mission_id=mission_id,
            run_id=current_run_id,
            prompt=prompt,
        )
        decision = mission_loop_service.evaluate_after_run(
            conn,
            lock,
            mission_id=mission_id,
            run_id=current_run_id,
            run_status=outcome.status,
        )
        if decision.action != "continue":
            return outcome
        session_row = conn.execute(
            "SELECT session_id FROM runs WHERE id=?", (current_run_id,)
        ).fetchone()
        next_run = run_service.start_run(
            conn,
            lock,
            mission_id=mission_id,
            session_id=session_row[0] if session_row else None,
            agent_runtime=agent_name,
        )
        current_run_id = next_run.id


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
    from atlas_runtime import runtime_daemon, surface_session_service

    # Startup reconciliation (SURF-05): before accepting new runs, reclaim any
    # surface session / run left orphaned by a crashed prior process. The
    # in-process executor threads are lost on restart, so DB rows still marked
    # 'running' are stale and must not survive as unowned executions.
    try:
        conn = _get_connection()
        reclaimed = surface_session_service.reconcile_orphans(
            conn, _get_lock(), ttl_seconds=_HEARTBEAT_TTL_SECONDS
        )
        if reclaimed:
            typer.echo(f"reconciled {len(reclaimed)} orphaned surface session(s) at startup")
    except Exception as exc:  # noqa: BLE001 — never block the daemon on the sweep
        typer.echo(f"startup reconciliation skipped: {exc}", err=True)

    typer.echo(f"atlas runtime daemon on http://{host}:{port}")
    runtime_daemon.serve(host=host, port=port)


@runtime_app.command("reconcile")
def runtime_reconcile(
    ttl_seconds: float = typer.Option(
        _HEARTBEAT_TTL_SECONDS, "--ttl",
        help="Heartbeat TTL in seconds; sessions stale beyond it are reclaimed.",
    ),
) -> None:
    """Reclaim orphaned surface sessions and crash-left running runs (SURF-05).

    Reads DB state (not in-process threads). Safe to run at startup and idempotent.
    """
    from atlas_runtime import surface_session_service

    conn = _get_connection()
    reclaimed = surface_session_service.reconcile_orphans(
        conn, _get_lock(), ttl_seconds=ttl_seconds
    )
    typer.echo(f"reconciled {len(reclaimed)} orphaned surface session(s)")


# ---------------------------------------------------------------------------
# db subcommands — migration runner (atlas db init / status)
# ---------------------------------------------------------------------------


@db_app.command("init")
def db_init(
    demo: bool = typer.Option(
        False, "--demo", help="Also seed a demo mission/run/wiki entry.",
    ),
) -> None:
    """Apply all pending migrations to ~/.atlas/atlas.db (idempotent, non-destructive)."""
    conn = db.connect()
    applied = db.apply_migrations(conn)
    if applied:
        for version in applied:
            typer.echo(f"applied {version}")
    else:
        typer.echo("already up to date")

    from atlas_runtime import model_registry

    lock = _get_lock()
    seeded = model_registry.seed_default_models(conn, lock)
    if seeded:
        typer.echo(f"seeded default models: {', '.join(seeded)}")

    if demo:
        from atlas_runtime import demo_seed

        result = demo_seed.seed_demo_data(conn, lock)
        typer.echo(f"demo seed: {result}")


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


# (key, label, control-module name, default-checked-when-non-interactive, start() kwargs)
_UP_SERVICE_REGISTRY = (
    ("gateway", "Gateway (core API)", "gateway_control", True, {}),
    ("cockpit", "Cockpit (web UI)", "cockpit_control", True, {}),
    ("freellmapi", "FreeLLMAPI sidecar (free-tier LLM gateway)", "freellmapi_control", True, {}),
    ("cashflow", "Cashflow module", "cashflow_control", False, {}),
    ("discord", "Discord bot sidecar", "discord_control", False, {}),
)
_UP_CORE_KEYS = frozenset({"gateway", "cockpit"})


def _up_cmd(
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip the picker; start the default set (gateway, cockpit, freellmapi)."
    ),
    services: str = typer.Option(
        "", "--services", help="Comma-separated service keys to start, skipping the picker (e.g. gateway,cockpit)."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON (implies --yes)."),
) -> None:
    """Boot ATLAS services (idempotent). Checks what's already running, then on
    a real TTY lets the operator pick which of the rest to start — space to
    toggle, enter to confirm. Non-interactive runs (no TTY, or --yes/--json/
    --services given) start the default set without prompting. Thin wrapper
    only — no SQL/no emit() here; logic lives in the *_control modules."""
    import importlib
    import sys

    from atlas_runtime import gateway_control

    modules = {
        key: importlib.import_module(f"atlas_runtime.{mod_name}")
        for key, _, mod_name, _, _ in _UP_SERVICE_REGISTRY
    }
    running = {key: modules[key].health_ok(timeout=0.5) for key in modules}

    if services.strip():
        valid_keys = {key for key, *_ in _UP_SERVICE_REGISTRY}
        chosen = {tok.strip() for tok in services.split(",") if tok.strip()}
        unknown = chosen - valid_keys
        if unknown:
            typer.echo(f"unknown service(s): {', '.join(sorted(unknown))}", err=True)
            raise typer.Exit(1)
    elif not yes and not json_out and sys.stdin.isatty() and sys.stdout.isatty():
        from atlas_runtime.cli.interactive_select import SelectItem, SelectionCancelled, multi_select

        items = [
            SelectItem(key=key, label=label, checked=default_checked, locked=running[key])
            for key, label, _, default_checked, _ in _UP_SERVICE_REGISTRY
        ]
        try:
            chosen = set(multi_select(items, title="Select services to start:"))
        except SelectionCancelled:
            typer.echo("cancelled — nothing started.")
            raise typer.Exit(1)
    else:
        chosen = {key for key, _, _, default_checked, _ in _UP_SERVICE_REGISTRY if default_checked}

    core_ok = True
    failed = False
    results = []
    for key, _, _, _, start_kwargs in _UP_SERVICE_REGISTRY:
        is_core = key in _UP_CORE_KEYS
        if running[key]:
            ok, message = True, "already running"
        elif key not in chosen:
            ok, message = True, "skipped"
        elif not is_core and not core_ok:
            ok, message = True, "skipped — gateway/cockpit not healthy"
        else:
            ok, message = modules[key].start(**start_kwargs)
            if key == "gateway" and ok and gateway_control.binary_stale():
                typer.echo(
                    "gateway: WARNING binary predates its Rust sources — "
                    "cargo build --release -p atlas-gateway"
                )
            if is_core and not ok:
                core_ok = False
                failed = True
        results.append({"component": key, "ok": ok, "message": message})
        if not json_out:
            typer.echo(f"{key}: {message}")

    if json_out:
        typer.echo(json.dumps({"ok": not failed, "components": results}))
    if failed:
        raise typer.Exit(1)


app.command(
    "up",
    help="Boot ATLAS services (idempotent); interactive picker on a TTY, --yes/--services/--json for scripts.",
)(_up_cmd)


def _stop_result_is_idempotent_ok(message: str) -> bool:
    normalized = message.lower()
    return any(
        marker in normalized
        for marker in (
            "not running",
            "not managed here",
            "no pid",
            "no pid file",
            "already gone",
        )
    )


def _down_cmd(
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Stop optional sidecars, cockpit, then gateway (idempotent)."""
    from atlas_runtime import (
        cashflow_control,
        cockpit_control,
        discord_control,
        freellmapi_control,
        gateway_control,
    )

    stop_plan = (
        ("freellmapi", freellmapi_control.stop),
        ("cashflow", cashflow_control.stop),
        ("discord", discord_control.stop),
        ("cockpit", cockpit_control.stop),
        ("gateway", gateway_control.stop),
    )
    results = []
    failed = False
    for component, stop in stop_plan:
        ok, message = stop()
        effective_ok = ok or _stop_result_is_idempotent_ok(message)
        failed = failed or not effective_ok
        result = {"component": component, "ok": effective_ok, "message": message}
        results.append(result)
        if not json_out:
            typer.echo(f"{component}: {message}")

    if json_out:
        typer.echo(json.dumps({"ok": not failed, "components": results}))
    if failed:
        raise typer.Exit(1)


app.command("down", help="Stop sidecars + cockpit + gateway together (idempotent).")(_down_cmd)


def _restart_cmd(
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip the picker; start the default set (gateway, cockpit, freellmapi)."
    ),
    services: str = typer.Option(
        "", "--services", help="Comma-separated service keys to start, skipping the picker (e.g. gateway,cockpit)."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON (implies --yes)."),
) -> None:
    """Stop everything (atlas down), then boot again (atlas up). The up phase
    keeps its normal behavior: interactive picker on a TTY, or the default
    set with --yes/--services/--json. A failed down aborts before starting."""
    if not json_out:
        typer.echo("— stopping —")
    _down_cmd(json_out=json_out)
    if not json_out:
        typer.echo("— starting —")
    _up_cmd(yes=yes, services=services, json_out=json_out)


app.command(
    "restart",
    help="Restart ATLAS services: down, then the normal up flow (interactive picker on a TTY).",
)(_restart_cmd)


@app.command("help", help="Browse all ATLAS commands interactively (tabs, search, drill-down).")
def _help_cmd(
    plain: bool = typer.Option(
        False, "--plain", help="Skip the interactive browser; print the categorized listing and exit."
    ),
) -> None:
    from atlas_runtime.cli.help_browser import build_catalog, render_static, run_browser

    if plain:
        tab_order, tabs = build_catalog(typer.main.get_command(app))
        render_static(tab_order, tabs)
        return
    run_browser(app, typer.main.get_command(app))

from atlas_runtime.cli.doctor import _doctor_cmd

app.command(
    "doctor", help="Aggregate health check: db, config, gateway, cockpit, provider."
)(_doctor_cmd)


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


# ---------------------------------------------------------------------------
# freellmapi subcommands — external sidecar endpoint control (D-015)
# ---------------------------------------------------------------------------


@freellmapi_app.command("install")
def freellmapi_install(
    target: str = typer.Option(
        "", "--target", help="Install directory (default: <ATLAS home>/sidecars/freellmapi)."
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite a non-checkout directory already at the target."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Clone + build the FreeLLMAPI sidecar under ATLAS's own install home.

    Gives `atlas` full control of the sidecar's lifecycle end to end — no manual
    git clone required. Requires git + npm on PATH.
    """
    from atlas_runtime import freellmapi_control

    dest = pathlib.Path(target).expanduser() if target else None
    ok, message = freellmapi_control.install(dest, force=force)
    if json_out:
        typer.echo(json.dumps({"ok": ok, "message": message}))
    else:
        typer.echo(message)
    if not ok:
        raise typer.Exit(1)


@freellmapi_app.command("start")
def freellmapi_start(
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Start the FreeLLMAPI sidecar endpoint (external checkout)."""
    from atlas_runtime import freellmapi_control

    ok, message = freellmapi_control.start()
    if json_out:
        typer.echo(json.dumps({"ok": ok, "message": message, **freellmapi_control.status()}))
    else:
        typer.echo(message)
    if not ok:
        raise typer.Exit(1)


@freellmapi_app.command("status")
def freellmapi_status(
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Print FreeLLMAPI sidecar status."""
    from atlas_runtime import freellmapi_control

    st = freellmapi_control.status()
    if json_out:
        typer.echo(json.dumps(st))
    else:
        typer.echo(f"{'running' if st['running'] else 'stopped'} {st['base_url']}")


@freellmapi_app.command("stop")
def freellmapi_stop(
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Stop the FreeLLMAPI sidecar started by this CLI."""
    from atlas_runtime import freellmapi_control

    ok, message = freellmapi_control.stop()
    if json_out:
        typer.echo(json.dumps({"ok": ok, "message": message}))
    else:
        typer.echo(message)
    if not ok:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
