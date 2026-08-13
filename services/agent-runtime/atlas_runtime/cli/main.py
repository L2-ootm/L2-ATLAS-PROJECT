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
import subprocess
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
module_records_app = typer.Typer(name="records", help="Module collection records (the module's own data).")
module_app.add_typer(module_records_app, name="records")
mcp_app = typer.Typer(name="mcp", help="MCP servers: registry, enablement, foundation projection.")
app.add_typer(mcp_app, name="mcp")
scratch_app = typer.Typer(name="scratch", help="Agent scratchpad: inspect, pin, sweep working memory.")
app.add_typer(scratch_app, name="scratch")
cashflow_app = typer.Typer(name="cashflow", help="Cashflow module process: start, status, stop.")
app.add_typer(cashflow_app, name="cashflow")
freellmapi_app = typer.Typer(name="freellmapi", help="FreeLLMAPI sidecar endpoint: install, start, status, stop.")
app.add_typer(freellmapi_app, name="freellmapi")
graph_app = typer.Typer(name="graph", help="Project knowledge graph for the cockpit Graphify view.")
app.add_typer(graph_app, name="graph")
brain_app = typer.Typer(
    name="brain",
    help="Durable knowledge graph: inspect, curate, and forget what ATLAS knows.",
)
app.add_typer(brain_app, name="brain")
run_app = typer.Typer(name="run", help="Execute an already-started run (background-safe).")
app.add_typer(run_app, name="run")
focus_app = typer.Typer(name="focus", help="Command Center: the operator's Current Focus.")
app.add_typer(focus_app, name="focus")
retention_app = typer.Typer(name="retention", help="Data lifecycle: compress, preview, usage.")
app.add_typer(retention_app, name="retention")
team_app = typer.Typer(name="team", help="Agent presets, team rosters, and group-chat team runs.")
app.add_typer(team_app, name="team")
team_preset_app = typer.Typer(name="preset", help="Reusable single-agent presets.")
team_app.add_typer(team_preset_app, name="preset")
team_run_cli_app = typer.Typer(name="run", help="Start/inspect a team's round-robin group-chat run.")
team_app.add_typer(team_run_cli_app, name="run")
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

from atlas_runtime.cli.components import components_app
app.add_typer(components_app, name="components")

from atlas_runtime.cli.discord import discord_app
app.add_typer(discord_app, name="discord")

from atlas_runtime.cli.tools import tools_app
app.add_typer(tools_app, name="tools")

from atlas_runtime.cli.surface import surface_app
app.add_typer(surface_app, name="surface")

from atlas_runtime.cli.skills import skills_app
app.add_typer(skills_app, name="skills")

terminal_app = typer.Typer(name="terminal", help="atlas-terminal (donor-based TUI surface) build/reachability status.")
app.add_typer(terminal_app, name="terminal")


@terminal_app.command("status", help="Is atlas-terminal built, what version, is the gateway reachable.")
def _terminal_status_cmd(
    json_output: bool = typer.Option(False, "--json", help="Emit as JSON."),
) -> None:
    from atlas_runtime import gateway_control
    resolution_error = None
    try:
        layout = _atlas_terminal_mod.resolve_terminal_layout()
    except _atlas_terminal_mod.TerminalLaunchError as exc:
        layout = None
        resolution_error = str(exc)

    source_dir = layout.source_dir if layout is not None else None
    workspace = layout.workspace if layout is not None else None
    component = layout.component if layout is not None else None
    source_present = bool(source_dir is not None and source_dir.is_dir())
    workspace_present = bool(workspace is not None and workspace.is_dir())
    built = bool(
        workspace is not None
        and component is not None
        and (workspace / component.deps_marker).is_dir()
    )

    # Before an immutable release has been provisioned there is no sidecar
    # package.json yet, so report the shipped version. Once a workspace exists,
    # inspect what launch will actually execute and do not mask a broken mirror.
    package_json = None
    if workspace_present and workspace is not None:
        package_json = workspace / "package.json"
    elif source_dir is not None:
        package_json = source_dir / "package.json"
    version = None
    package_valid = False
    package_error = None
    if package_json is not None and package_json.is_file():
        try:
            package = json.loads(package_json.read_text(encoding="utf-8"))
            if not isinstance(package, dict):
                raise ValueError("package.json root is not an object")
            raw_version = package.get("version")
            version = raw_version if isinstance(raw_version, str) else None
            package_valid = True
        except (OSError, ValueError) as exc:
            package_error = str(exc)
    elif package_json is not None:
        package_error = "package.json not found"
    gateway_reachable = gateway_control.health_ok()

    report = {
        # Preserve the legacy keys while making their meaning explicit through
        # additive fields. ``present`` continues to mean source availability;
        # ``built`` means the resolved execution workspace has dependencies.
        "present": source_present,
        "built": built,
        "version": version,
        "gateway_reachable": gateway_reachable,
        "source_dir": str(source_dir) if source_dir is not None else None,
        "source_present": source_present,
        "workspace": str(workspace) if workspace is not None else None,
        "workspace_present": workspace_present,
        "mirrored": layout.mirrored if layout is not None else None,
        "package_valid": package_valid,
        "package_error": package_error,
        "resolution_error": resolution_error,
    }
    if json_output:
        typer.echo(json.dumps(report))
        return
    typer.echo(f"present: {report['present']}")
    typer.echo(f"built (bun install ran): {built}")
    typer.echo(f"version: {version or 'unknown'}")
    typer.echo(f"gateway reachable: {gateway_reachable}")
    if resolution_error:
        typer.echo(f"resolution error: {resolution_error}")
    elif package_error:
        typer.echo(f"package error: {package_error}")
    if not report["present"] or not built:
        typer.echo("remediation: run `atlas` to provision atlas-terminal dependencies")


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


@app.command("rtk", help="RTK (Rust Token Killer) status and control — 60-90% token savings on shell commands.")
def _rtk_cmd(
    action: str = typer.Argument("status", help="Action: status, enable, disable"),
    json_output: bool = typer.Option(False, "--json", help="Emit as JSON."),
) -> None:
    import shutil

    env_var = "ATLAS_RTK_DISABLED"
    current_disabled = os.environ.get(env_var, "").strip().lower() in {"1", "true", "yes"}
    rtk_found = shutil.which("rtk") is not None

    if action == "status":
        if json_output:
            typer.echo(json.dumps({
                "available": rtk_found,
                "disabled": current_disabled,
                "env_var": env_var,
            }))
        else:
            if current_disabled:
                typer.echo("rtk: disabled (ATLAS_RTK_DISABLED=1)")
            elif rtk_found:
                try:
                    probe = subprocess.run(["rtk", "--version"], capture_output=True, text=True, timeout=5)
                    version_str = probe.stdout.strip().split("\n")[0] if probe.returncode == 0 else "found"
                    typer.echo(f"rtk: {version_str} — 60-90% token savings")
                except (OSError, subprocess.SubprocessError):
                    typer.echo("rtk: available (version unknown) — 60-90% token savings")
            else:
                typer.echo("rtk: not installed — install for 60-90% token savings")
                typer.echo("  https://github.com/rtk-ai/rtk")

    elif action == "enable":
        # Remove the disable env var from the process environment
        if env_var in os.environ:
            del os.environ[env_var]
        # Write to ATLAS config if available
        try:
            config_path = os.environ.get("ATLAS_CONFIG_PATH", "")
            if not config_path:
                atlas_home = os.environ.get("ATLAS_HOME", os.path.expanduser("~/.atlas"))
                config_path = os.path.join(atlas_home, "config.yaml")
            if os.path.exists(config_path):
                import yaml
                with open(config_path) as f:
                    cfg = yaml.safe_load(f) or {}
                rtk_cfg = cfg.setdefault("rtk", {})
                rtk_cfg["enabled"] = True
                with open(config_path, "w") as f:
                    yaml.dump(cfg, f, default_flow_style=False)
                typer.echo("rtk: enabled (config updated)")
            else:
                typer.echo("rtk: enabled (set ATLAS_RTK_DISABLED=0 for this session)")
        except Exception as exc:
            typer.echo(f"rtk: enabled (config update failed: {exc})")

    elif action == "disable":
        os.environ[env_var] = "1"
        try:
            config_path = os.environ.get("ATLAS_CONFIG_PATH", "")
            if not config_path:
                atlas_home = os.environ.get("ATLAS_HOME", os.path.expanduser("~/.atlas"))
                config_path = os.path.join(atlas_home, "config.yaml")
            if os.path.exists(config_path):
                import yaml
                with open(config_path) as f:
                    cfg = yaml.safe_load(f) or {}
                rtk_cfg = cfg.setdefault("rtk", {})
                rtk_cfg["enabled"] = False
                with open(config_path, "w") as f:
                    yaml.dump(cfg, f, default_flow_style=False)
                typer.echo("rtk: disabled (config updated)")
            else:
                typer.echo("rtk: disabled (set ATLAS_RTK_DISABLED=1 for this session)")
        except Exception as exc:
            typer.echo(f"rtk: disabled (config update failed: {exc})")

    else:
        typer.echo(f"Unknown action: {action}. Use: status, enable, disable", err=True)
        raise typer.Exit(1)


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
        "atlas",
        "--scope",
        help="atlas | global | projects | obsidian | <custom scope id>",
    ),
    write: bool = typer.Option(
        False, "--write", help="Also cache the graph to .planning/graphs/graph.json"
    ),
) -> None:
    """Build the knowledge graph for the given scope and print it as JSON."""
    from atlas_runtime import graph_scope_service

    try:
        if scope in graph_scope_service.BUILTIN_SCOPES:
            override = graph_scope_service.resolve_builtin_override(_get_connection(), scope)
            result = graph_service.build_graph(root=root, scope=scope, override_root=override)
        else:
            custom = graph_scope_service.get_scope(_get_connection(), scope)
            if custom is None:
                typer.echo(f"Error: unknown graph scope {scope!r}", err=True)
                raise typer.Exit(1)
            result = graph_service.build_custom_graph(
                custom["id"], custom["root_path"], custom["kind"]
            )
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


@graph_app.command("scopes")
def graph_scopes() -> None:
    """Print custom graph scopes (operator-defined Graphify tabs) as JSON."""
    from atlas_runtime import graph_scope_service

    typer.echo(json.dumps(graph_scope_service.list_scopes(_get_connection())))


@graph_app.command("add-scope")
def graph_add_scope(
    label: str = typer.Option(..., "--label", help="Display label for the graph tab"),
    path: str = typer.Option(..., "--path", help="Folder the graph is built from"),
    kind: str = typer.Option(
        "markdown", "--kind", help="markdown (one corpus) | projects (cluster per child dir)"
    ),
) -> None:
    """Create a custom graph scope; prints the scope row as JSON."""
    from atlas_runtime import graph_scope_service

    conn = _get_connection()
    lock = _get_lock()
    try:
        scope = graph_scope_service.create_scope(
            conn, lock, label=label, root_path=path, kind=kind
        )
    except graph_scope_service.GraphScopeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(scope))


@graph_app.command("remove-scope")
def graph_remove_scope(
    scope_id: str = typer.Argument(..., help="Custom scope id to remove"),
) -> None:
    """Remove a custom graph scope (built-ins cannot be removed)."""
    from atlas_runtime import graph_scope_service

    conn = _get_connection()
    lock = _get_lock()
    try:
        graph_scope_service.delete_scope(conn, lock, scope_id)
    except graph_scope_service.GraphScopeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo("removed")


@graph_app.command("set-scope-root")
def graph_set_scope_root(
    scope_id: str = typer.Argument(..., help="Scope id (custom, or projects/obsidian)"),
    path: str = typer.Option(..., "--path", help="New folder for the graph tab"),
) -> None:
    """Repoint a graph tab's folder. Works for custom scopes and for the folder
    built-ins projects/obsidian; prints the resulting scope row as JSON."""
    from atlas_runtime import graph_scope_service

    conn = _get_connection()
    lock = _get_lock()
    try:
        scope = graph_scope_service.set_scope_root(conn, lock, scope_id=scope_id, root_path=path)
    except graph_scope_service.GraphScopeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(scope))


# ---------------------------------------------------------------------------
# brain subcommands — operator control over the durable knowledge graph
#
# The graph the agent writes through the `atlas_graph` tool is the same one
# these commands read and curate. Everything prints JSON so the gateway can
# dispatch to them (D-022) and so a human can pipe them.
# ---------------------------------------------------------------------------


def _brain_node_view(node) -> dict:
    """Flatten a BrainNode for JSON output, decoding metadata for readability."""
    try:
        metadata = json.loads(node.metadata_json or "{}")
    except (TypeError, ValueError):
        metadata = {}
    return {
        "id": node.id,
        "entity_type": node.entity_type,
        "label": node.label,
        "project_id": node.project_id,
        "source_id": node.source_id,
        "updated_at": node.updated_at,
        "confidence": node.confidence,
        "metadata": metadata,
    }


@brain_app.command("stats")
def brain_stats() -> None:
    """Inventory the whole graph: counts by entity type, relation, and project."""
    from atlas_runtime import brain_service

    typer.echo(json.dumps(brain_service.stats(_get_connection())))


@brain_app.command("list")
def brain_list(
    entity_type: Optional[str] = typer.Option(
        None, "--type", help="Only nodes of this entity type"
    ),
    project: Optional[str] = typer.Option(
        None, "--project", help="Project scope (default: the global scope)"
    ),
    limit: int = typer.Option(50, "--limit", help="Max nodes to return (cap 100)"),
) -> None:
    """List nodes in a scope, most recently updated first."""
    from atlas_runtime import brain_service

    nodes = brain_service.list_nodes(
        _get_connection(), project_id=project, entity_type=entity_type, limit=limit
    )
    typer.echo(json.dumps([_brain_node_view(n) for n in nodes]))


@brain_app.command("search")
def brain_search(
    query: str = typer.Argument(..., help="Substring matched against label and metadata"),
    project: Optional[str] = typer.Option(None, "--project", help="Project scope"),
    limit: int = typer.Option(20, "--limit", help="Max nodes to return (cap 100)"),
) -> None:
    """Search nodes by label or metadata substring."""
    from atlas_runtime import brain_service

    nodes = brain_service.search(
        _get_connection(), query, project_id=project, limit=limit
    )
    typer.echo(json.dumps([_brain_node_view(n) for n in nodes]))


@brain_app.command("show")
def brain_show(
    node_id: str = typer.Argument(..., help="Node id, e.g. concept:retry-safety"),
) -> None:
    """Show one node with every edge incident to it, inbound and outbound."""
    from atlas_runtime import brain_service

    conn = _get_connection()
    node = brain_service.explain(conn, node_id)
    if node is None:
        typer.echo(f"Error: unknown node {node_id!r}", err=True)
        raise typer.Exit(1)
    typer.echo(
        json.dumps(
            {
                "node": _brain_node_view(node),
                "edges": list(brain_service.edges_for(conn, node_id)),
            }
        )
    )


@brain_app.command("add")
def brain_add(
    label: str = typer.Option(..., "--label", help="Human-readable node label"),
    entity_type: str = typer.Option(
        "concept", "--type", help="Entity type slug, e.g. concept|decision|system"
    ),
    summary: Optional[str] = typer.Option(None, "--summary", help="Short summary"),
    confidence: float = typer.Option(0.9, "--confidence", help="Confidence 0..1"),
    project: Optional[str] = typer.Option(None, "--project", help="Project scope"),
) -> None:
    """Add or converge on a node. The id is derived from type+label, so running
    this twice updates rather than duplicates."""
    from atlas_runtime import brain_service, graph_bridge
    from atlas_core.schemas.brain import BrainNode

    now = _brain_now()
    metadata = {"summary": summary[:2000]} if summary else {}
    try:
        node = BrainNode(
            id=graph_bridge.node_id_for(entity_type, label),
            entity_type=entity_type,
            label=label,
            project_id=project,
            source_id="operator:cli",
            source_version=now,
            updated_at=now,
            confidence=confidence,
            metadata_json=json.dumps(metadata),
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    with _get_lock():
        brain_service.upsert_node(_get_connection(), node)
    typer.echo(json.dumps(_brain_node_view(node)))


@brain_app.command("link")
def brain_link(
    source: str = typer.Option(..., "--from", help="Source node id"),
    target: str = typer.Option(..., "--to", help="Target node id"),
    relation: str = typer.Option("relates_to", "--relation", help="Relation slug"),
    project: Optional[str] = typer.Option(None, "--project", help="Project scope"),
) -> None:
    """Link two existing nodes. Idempotent — safe to re-run."""
    from atlas_runtime import brain_service
    from atlas_core.schemas.brain import BrainEdge

    try:
        with _get_lock():
            brain_service.upsert_edge(
                _get_connection(),
                BrainEdge(
                    source_id=source, target_id=target, relation=relation, project_id=project
                ),
            )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(
        json.dumps({"source_id": source, "target_id": target, "relation": relation})
    )


@brain_app.command("update")
def brain_update(
    node_id: str = typer.Argument(..., help="Node id to correct"),
    label: Optional[str] = typer.Option(None, "--label", help="Corrected label"),
    entity_type: Optional[str] = typer.Option(None, "--type", help="Corrected entity type"),
    summary: Optional[str] = typer.Option(None, "--summary", help="Replacement summary"),
    confidence: Optional[float] = typer.Option(None, "--confidence", help="New confidence 0..1"),
) -> None:
    """Correct a node. Changing label or type re-keys it and rewrites its edges,
    so the id stays derivable from type+label."""
    from atlas_runtime import brain_service, graph_bridge

    if label is None and entity_type is None and summary is None and confidence is None:
        typer.echo("Error: pass at least one of --label --type --summary --confidence", err=True)
        raise typer.Exit(1)
    conn = _get_connection()
    current = brain_service.explain(conn, node_id)
    if current is None:
        typer.echo(f"Error: unknown node {node_id!r}", err=True)
        raise typer.Exit(1)
    new_id = None
    if label is not None or entity_type is not None:
        candidate = graph_bridge.node_id_for(
            entity_type or current.entity_type, label or current.label
        )
        new_id = candidate if candidate != node_id else None
    try:
        with _get_lock():
            updated = brain_service.update_node(
                conn,
                node_id,
                label=label,
                entity_type=entity_type,
                confidence=confidence,
                metadata={"summary": summary[:2000]} if summary else None,
                source_id="operator:cli",
                new_id=new_id,
            )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(
        json.dumps(
            {"node": _brain_node_view(updated), "renamed_from": node_id if new_id else None}
        )
    )


@brain_app.command("forget")
def brain_forget(
    node_id: str = typer.Argument(..., help="Node id to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm the deletion"),
) -> None:
    """Delete a node and its edges. Prints exactly what was removed — keep that
    output if you might want it back."""
    from atlas_runtime import brain_service

    if not yes:
        typer.echo("Error: refusing to delete without --yes", err=True)
        raise typer.Exit(1)
    with _get_lock():
        removed = brain_service.delete_node(_get_connection(), node_id)
    if removed is None:
        typer.echo(f"Error: unknown node {node_id!r}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(removed))


@brain_app.command("unlink")
def brain_unlink(
    source: str = typer.Option(..., "--from", help="Source node id"),
    target: str = typer.Option(..., "--to", help="Target node id"),
    relation: str = typer.Option("relates_to", "--relation", help="Relation slug"),
) -> None:
    """Remove one relation. Already-gone counts as success."""
    from atlas_runtime import brain_service

    with _get_lock():
        deleted = brain_service.delete_edge(_get_connection(), source, target, relation)
    typer.echo(json.dumps({"deleted": deleted}))


@brain_app.command("path")
def brain_path(
    source: str = typer.Option(..., "--from", help="Start node id"),
    target: str = typer.Option(..., "--to", help="End node id"),
    project: Optional[str] = typer.Option(None, "--project", help="Project scope"),
    depth: int = typer.Option(4, "--depth", help="Max hops (1-4)"),
) -> None:
    """Shortest relation chain between two nodes, or an empty path if unrelated."""
    from atlas_runtime import brain_service

    try:
        chain = brain_service.find_path(
            _get_connection(), source, target, project_id=project, max_depth=depth
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps({"path": list(chain), "found": bool(chain)}))


@brain_app.command("export")
def brain_export(
    out: Optional[str] = typer.Option(None, "--out", help="Write to this file instead of stdout"),
) -> None:
    """Export the whole graph as JSON — a backup you own and can re-import."""
    from atlas_runtime import brain_service

    payload = brain_service.export_graph(_get_connection())
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if out:
        out_path = pathlib.Path(out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        typer.echo(json.dumps({"written": str(out_path), "counts": {
            "nodes": len(payload["nodes"]), "edges": len(payload["edges"])
        }}))
        return
    typer.echo(text)


@brain_app.command("import")
def brain_import(
    source_file: str = typer.Argument(..., help="A file produced by `atlas brain export`"),
) -> None:
    """Merge an exported graph in. Upserts, so re-importing is a no-op."""
    from atlas_runtime import brain_service

    path = pathlib.Path(source_file).expanduser()
    if not path.is_file():
        typer.echo(f"Error: file not found: {source_file}", err=True)
        raise typer.Exit(1)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        typer.echo(f"Error: could not read {source_file}: {exc}", err=True)
        raise typer.Exit(1)
    if not isinstance(payload, dict):
        typer.echo("Error: export payload must be a JSON object", err=True)
        raise typer.Exit(1)
    try:
        with _get_lock():
            result = brain_service.import_graph(_get_connection(), payload)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(result))


def _brain_now() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()


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
    origin: str = typer.Option(
        "operator",
        "--origin",
        help="Mission authorship: operator (deliberate) | chat (prompt wrapper) | system",
    ),
) -> None:
    """Create a Mission and print its ID."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        mission = mission_service.create_mission(
            conn, lock, title=title, intent=intent, project_id=project, origin=origin
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
    _echo_outcome(conn, run.id, outcome)


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
    _echo_outcome(conn, run.id, outcome)


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


@mission_app.command("update")
def mission_update(
    mission_id: str = typer.Argument(..., help="Mission ID to update"),
    title: str = typer.Option(None, "--title", help="New title"),
    intent: str = typer.Option(None, "--intent", help="New intent"),
    project: str = typer.Option(None, "--project", help="New project ID"),
) -> None:
    """Update a pending/failed/cancelled mission."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        mission = mission_service.update_mission(
            conn, lock, mission_id=mission_id,
            title=title, intent=intent, project_id=project,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(mission.id)


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


@project_app.command("rename")
def project_rename(
    project_id: str = typer.Argument(..., help="Project ID to rename"),
    name: str = typer.Option(..., "--name", help="New project name"),
) -> None:
    """Rename a project (the folder on disk is unchanged)."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        project = project_service.rename_project(conn, lock, project_id=project_id, name=name)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(project.id)


@project_app.command("unregister")
def project_unregister(
    project_id: str = typer.Argument(..., help="Project ID to unregister"),
) -> None:
    """Unregister a project. The folder on disk is never deleted.

    Missions/focus bound to it are detached (history kept). Prints the
    number of detached missions.
    """
    conn = _get_connection()
    lock = _get_lock()
    try:
        detached = project_service.unregister_project(conn, lock, project_id=project_id)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(str(detached))


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


def _echo_outcome(conn: sqlite3.Connection, run_id: str, outcome: object) -> None:
    """Print a finished run's status, then what its own trail says about it.

    The status keeps the first line to itself because scripts read it. The
    verdict is read back from its `verification_verdict` audit event rather than
    parsed out of the outcome's prose, so what the operator is shown and what
    the record holds cannot drift apart. `no_mutations` prints nothing: a
    read-only run has nothing to answer for, and a line saying so on every run
    would train the operator to skip the ones that matter.
    """
    typer.echo(getattr(outcome, "status", ""))
    try:
        row = conn.execute(
            "SELECT data FROM audit_events WHERE run_id=? AND "
            "event_type='verification_verdict' ORDER BY timestamp DESC, rowid DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        payload = json.loads(row[0]) if row and row[0] else {}
    except Exception:  # noqa: BLE001 — reporting must never fail the command
        return
    state = payload.get("state")
    changes = payload.get("mutation_count") or 0
    if state == "verified":
        detail = f"passed {', '.join(payload.get('signals') or []) or 'a check'}"
    elif state == "contradicted":
        detail = (
            f"every check failed ({', '.join(payload.get('failed_signals') or [])}) "
            f"after {changes} change(s)"
        )
    elif state == "unverified":
        detail = f"{changes} change(s), no test/build/lint/typecheck ran after them"
    else:
        return
    typer.echo(f"verification: {state} — {detail}")


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
    _echo_outcome(conn, run_id, outcome)


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


@focus_app.command("activate")
def focus_activate(focus_id: str = typer.Argument(..., help="Focus ID to make current")) -> None:
    """Make an existing Focus the Current Focus (archives any other active one)."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        focus = focus_service.activate_focus(conn, lock, focus_id)
    except focus_service.FocusError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(focus.model_dump()))


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
# retention subcommands — data lifecycle management
# ---------------------------------------------------------------------------


@retention_app.command("compress")
def retention_compress(
    after_days: int = typer.Option(14, "--after-days", help="Compress archives older than N days"),
) -> None:
    """Compress old archived mission data."""
    from atlas_runtime import retention_service

    conn = _get_connection()
    lock = _get_lock()
    count = retention_service.compress_mission_data(conn, lock, after_archive_days=after_days)
    typer.echo(str(count))


@retention_app.command("usage")
def retention_usage() -> None:
    """Show storage usage statistics."""
    from atlas_runtime import retention_service
    import json as json_mod

    conn = _get_connection()
    usage = retention_service.get_storage_usage(conn)
    typer.echo(json_mod.dumps(usage, indent=2))


@retention_app.command("preview")
def retention_preview() -> None:
    """Preview missions that would be purged."""
    from atlas_runtime import retention_service
    import json as json_mod

    conn = _get_connection()
    preview = retention_service.get_purge_preview(conn)
    typer.echo(json_mod.dumps(preview, indent=2))


# ---------------------------------------------------------------------------
# team subcommands — agent presets, team rosters, group-chat team runs
# ---------------------------------------------------------------------------


@team_preset_app.command("create")
def team_preset_create(
    name: str = typer.Option(..., "--name", help="Unique preset name"),
    role_label: str = typer.Option(..., "--role", help="Role label (e.g. researcher)"),
    goal_template: str = typer.Option(..., "--goal", help="Goal template text"),
    description: str = typer.Option("", "--description"),
    model: str = typer.Option("", "--model"),
    provider: str = typer.Option("", "--provider"),
    mode: str = typer.Option("joined", "--mode", help="joined|detached"),
) -> None:
    """Create a reusable agent preset; prints it as JSON."""
    from atlas_runtime import team_service

    conn, lock = _get_connection(), _get_lock()
    try:
        preset = team_service.create_preset(
            conn, lock, name=name, role_label=role_label, goal_template=goal_template,
            description=description, model=model or None, provider=provider or None, mode=mode,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(preset))


@team_preset_app.command("list")
def team_preset_list() -> None:
    """List all agent presets as a JSON array."""
    from atlas_runtime import team_service

    conn = _get_connection()
    typer.echo(json.dumps(team_service.list_presets(conn)))


@team_preset_app.command("update")
def team_preset_update(
    preset_id: str = typer.Argument(...),
    name: str = typer.Option("", "--name"),
    role_label: str = typer.Option("", "--role"),
    goal_template: str = typer.Option("", "--goal"),
    description: str = typer.Option("", "--description"),
    model: str = typer.Option("", "--model"),
    provider: str = typer.Option("", "--provider"),
    mode: str = typer.Option("", "--mode"),
) -> None:
    """Patch a preset's fields (only provided ones change); prints it as JSON."""
    from atlas_runtime import team_service

    conn, lock = _get_connection(), _get_lock()
    fields = {
        k: v for k, v in {
            "name": name, "role_label": role_label, "goal_template": goal_template,
            "description": description, "model": model, "provider": provider, "mode": mode,
        }.items() if v
    }
    try:
        preset = team_service.update_preset(conn, lock, preset_id, **fields)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(preset))


@team_preset_app.command("delete")
def team_preset_delete(preset_id: str = typer.Argument(...)) -> None:
    """Delete a preset (refuses if it's still on a team roster)."""
    from atlas_runtime import team_service

    conn, lock = _get_connection(), _get_lock()
    try:
        ok = team_service.delete_preset(conn, lock, preset_id)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo("deleted" if ok else "not found")


@team_app.command("create")
def team_create(
    name: str = typer.Option(..., "--name", help="Unique team name"),
    description: str = typer.Option("", "--description"),
) -> None:
    """Create a team; prints it as JSON."""
    from atlas_runtime import team_service

    conn, lock = _get_connection(), _get_lock()
    try:
        team = team_service.create_team(conn, lock, name=name, description=description)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(team))


@team_app.command("list")
def team_list() -> None:
    """List all teams (with resolved members) as a JSON array."""
    from atlas_runtime import team_service

    conn = _get_connection()
    typer.echo(json.dumps(team_service.list_teams(conn)))


@team_app.command("get")
def team_get(team_id: str = typer.Argument(...)) -> None:
    """Print one team (with resolved members) as JSON."""
    from atlas_runtime import team_service

    conn = _get_connection()
    team = team_service.get_team(conn, team_id)
    if team is None:
        typer.echo("Error: team not found", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(team))


@team_app.command("update")
def team_update(
    team_id: str = typer.Argument(...),
    name: str = typer.Option("", "--name"),
    description: str = typer.Option("", "--description"),
) -> None:
    """Patch a team's name/description; prints it as JSON."""
    from atlas_runtime import team_service

    conn, lock = _get_connection(), _get_lock()
    fields = {k: v for k, v in {"name": name, "description": description}.items() if v}
    try:
        team = team_service.update_team(conn, lock, team_id, **fields)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(team))


@team_app.command("delete")
def team_delete(team_id: str = typer.Argument(...)) -> None:
    """Delete a team (refuses while it has an active run)."""
    from atlas_runtime import team_service

    conn, lock = _get_connection(), _get_lock()
    try:
        ok = team_service.delete_team(conn, lock, team_id)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo("deleted" if ok else "not found")


@team_app.command("set-members")
def team_set_members(
    team_id: str = typer.Argument(...),
    preset_ids: str = typer.Option(..., "--presets", help="Comma-separated preset ids, in order"),
) -> None:
    """Replace a team's roster and ordering; prints the team as JSON."""
    from atlas_runtime import team_service

    conn, lock = _get_connection(), _get_lock()
    ids = [p.strip() for p in preset_ids.split(",") if p.strip()]
    try:
        team = team_service.set_team_members(conn, lock, team_id, ids)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(team))


@team_run_cli_app.command("start")
def team_run_start(
    team_id: str = typer.Option(..., "--team", help="Team id to run"),
    message: str = typer.Option(..., "--message", help="Kickoff message"),
    mission_id: str = typer.Option("", "--mission", help="Originating mission id (optional)"),
    max_rounds: int = typer.Option(
        6, "--max-rounds", help="Round-robin round cap (server-capped at 20)"
    ),
) -> None:
    """Start a team's round-robin group-chat run; prints the team_run as JSON."""
    from atlas_runtime import team_run_service
    from atlas_runtime.team_run_worker import launch_team_run_worker

    conn, lock = _get_connection(), _get_lock()
    try:
        run = team_run_service.create_team_run(
            conn, lock, team_id=team_id, kickoff_message=message,
            mission_id=mission_id or None, max_rounds=max_rounds,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    pid = launch_team_run_worker(run["id"])
    if pid is None:
        typer.echo("Error: team run worker failed to launch", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(run))


@team_run_cli_app.command("status")
def team_run_status(team_run_id: str = typer.Argument(...)) -> None:
    """Print one team_run's state as JSON."""
    from atlas_runtime import team_run_service

    conn = _get_connection()
    run = team_run_service.get_team_run(conn, team_run_id)
    if run is None:
        typer.echo("Error: team run not found", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(run))


@team_run_cli_app.command("messages")
def team_run_messages(
    team_run_id: str = typer.Argument(...),
    since_seq: int = typer.Option(0, "--since-seq", help="Only messages after this seq"),
) -> None:
    """Print a team_run's group-chat log as a JSON array."""
    from atlas_runtime import team_run_service

    conn = _get_connection()
    typer.echo(json.dumps(team_run_service.list_messages(conn, team_run_id, since_seq=since_seq)))


@team_run_cli_app.command("cancel")
def team_run_cancel(team_run_id: str = typer.Argument(...)) -> None:
    """Idempotently cancel a queued/running team run."""
    from atlas_runtime import team_run_service

    conn, lock = _get_connection(), _get_lock()
    ok = team_run_service.cancel_team_run(conn, lock, team_run_id)
    typer.echo("cancelled" if ok else "already terminal or not found")


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
    status: str = typer.Option("", "--status", help="open|active|paused|done|archived"),
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


@goal_app.command("delete")
def goal_delete(
    goal_id: str = typer.Argument(..., help="Goal id to hard-delete (cascades to sub-goals/tasks)")
) -> None:
    """Delete a goal subtree permanently; observations are detached, not deleted."""
    conn = _get_connection()
    lock = _get_lock()
    try:
        count = goal_service.delete_goal(conn, lock, goal_id)
    except goal_service.GoalError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"deleted {count}")


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
        conn,
        lock,
        title=f"{op.label}: {goal.title}"[:120],
        intent=intent,
        project_id=project_id,
        origin="system",
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
        from atlas_runtime import actor_service

        orphaned_actors = actor_service.reconcile_orphan_actors(
            conn, _get_lock(), ttl_seconds=_HEARTBEAT_TTL_SECONDS
        )
        if orphaned_actors:
            typer.echo(f"reconciled {len(orphaned_actors)} orphaned actor(s) at startup")
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
    from atlas_runtime import actor_service, surface_session_service

    conn = _get_connection()
    reclaimed = surface_session_service.reconcile_orphans(
        conn, _get_lock(), ttl_seconds=ttl_seconds
    )
    typer.echo(f"reconciled {len(reclaimed)} orphaned surface session(s)")
    orphaned_actors = actor_service.reconcile_orphan_actors(
        conn, _get_lock(), ttl_seconds=ttl_seconds
    )
    typer.echo(f"reconciled {len(orphaned_actors)} orphaned actor(s)")


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
def gateway_status(
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Print the ownership-aware gateway lifecycle status."""
    from atlas_runtime import gateway_control

    payload = gateway_control.status()
    if json_out:
        typer.echo(json.dumps(payload))
    else:
        typer.echo("online" if payload.get("running") else "offline")


@gateway_app.command("stop")
def gateway_stop() -> None:
    """Stop a gateway started by this CLI (via its PID file)."""
    from atlas_runtime import gateway_control

    ok, message = gateway_control.stop()
    typer.echo(message)
    if not ok:
        raise typer.Exit(1)


@gateway_app.command("recover")
def gateway_recover() -> None:
    """Remove safely-proven stale gateway state without killing a process."""
    from atlas_runtime import gateway_control

    ok, message = gateway_control.recover()
    typer.echo(message)
    if not ok:
        raise typer.Exit(1)


# (key, label, control-module name, default-checked-when-non-interactive, start() kwargs)
_UP_SERVICE_REGISTRY = (
    ("gateway", "Gateway (core API)", "gateway_control", True, {}),
    ("cockpit", "Cockpit (web UI)", "cockpit_control", True, {}),
    (
        "freellmapi",
        "FreeLLMAPI sidecar (free-tier LLM gateway)",
        "freellmapi_control",
        True,
        {"poll_seconds": 10.0},
    ),
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
            ok, message, code = True, "already running", "already_ready"
        elif key not in chosen:
            ok, message, code = True, "skipped", "skipped"
        elif not is_core and not core_ok:
            ok, message, code = True, "skipped — gateway/cockpit not healthy", "dependency_unready"
        else:
            ok, message = modules[key].start(**start_kwargs)
            code = "started" if ok else "start_failed"
            if key == "gateway" and ok and gateway_control.binary_stale():
                typer.echo(
                    "gateway: WARNING binary predates its Rust sources — "
                    "cargo build --release -p atlas-gateway"
                )
            if is_core and not ok:
                core_ok = False
                failed = True
        results.append({"component": key, "ok": ok, "code": code, "message": message})
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


_STOPPED_SERVICE_STATES = frozenset({"stopped", "not_managed", "not_installed"})


def _structured_service_state(module: object) -> str:
    """Normalize lifecycle status without interpreting human-facing messages."""
    status_fn = getattr(module, "status", None)
    if callable(status_fn):
        try:
            payload = status_fn()
        except Exception:
            return "unknown"
        if isinstance(payload, dict):
            state = payload.get("state")
            if isinstance(state, str) and state:
                return state
            if payload.get("ready") is True:
                return "ready"
            if payload.get("running") is True:
                return "running"
            if payload.get("running") is False:
                return "stopped"
    return "unknown"


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
        ("freellmapi", freellmapi_control),
        ("cashflow", cashflow_control),
        ("discord", discord_control),
        ("cockpit", cockpit_control),
        ("gateway", gateway_control),
    )
    results = []
    failed = False
    for component, module in stop_plan:
        before = _structured_service_state(module)
        ok, message = module.stop()
        after = _structured_service_state(module)
        already_stopped = before in _STOPPED_SERVICE_STATES and after in _STOPPED_SERVICE_STATES
        effective_ok = ok or already_stopped
        failed = failed or not effective_ok
        code = "stopped" if ok else "already_stopped" if already_stopped else "stop_failed"
        result = {
            "component": component,
            "ok": effective_ok,
            "code": code,
            "state": after,
            "message": message,
        }
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


@module_app.command("sync")
def module_sync(
    json_output: bool = typer.Option(False, "--json", help="Emit the sync summary as JSON."),
) -> None:
    """Discover manifest modules (module.yaml) and sync them into the registry.

    Scans <repo>/modules and <ATLAS home>/modules. Activation state survives
    re-sync; vanished modules are flagged missing, never deleted.
    """
    import json as _json

    from atlas_runtime import module_service

    from atlas_runtime import mcp_service

    conn, lock = _get_connection(), _get_lock()
    summary = module_service.sync_modules(conn, lock)
    # A module's MCP declarations are part of its manifest, so discovering the
    # manifest and registering its servers is one operation from the operator's
    # side. Registration never enables anything (mcp_service.sync_module_servers).
    summary["mcp"] = mcp_service.sync_module_servers(conn, lock)
    if json_output:
        typer.echo(_json.dumps(summary, indent=2))
        return
    typer.echo(f"discovered: {', '.join(summary['discovered']) or '(none)'}")
    if summary["missing"]:
        typer.echo(f"missing: {', '.join(summary['missing'])}")
    if summary["mcp"]["registered"]:
        typer.echo(f"mcp registered: {', '.join(summary['mcp']['registered'])}")
    for problem in summary["problems"] + summary["mcp"]["problems"]:
        typer.echo(f"problem: {problem}", err=True)


@module_app.command("create")
def module_create(
    module_id: str = typer.Argument(..., help="New module id ([a-z0-9-])."),
    name: str = typer.Option(None, "--name", help="Display name (defaults from the id)."),
    activate: bool = typer.Option(
        True, "--activate/--no-activate",
        help="Sync and activate the module right after scaffolding.",
    ),
) -> None:
    """Scaffold a manifest module in <ATLAS home>/modules (self-wiring entry point).

    Creates module.yaml with a starter command and page, then syncs (and by
    default activates) it so the module is immediately live on every surface.
    """
    from atlas_runtime import module_service

    try:
        target = module_service.create_module_scaffold(module_id, name=name)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"scaffolded {target}")
    conn = _get_connection()
    lock = _get_lock()
    module_service.sync_modules(conn, lock)
    if activate:
        mod = module_service.set_active(conn, lock, module_id=module_id, active=True)
        typer.echo(f"{mod.id} {mod.status}")


@module_app.command("info")
def module_info(
    module_id: str = typer.Argument(..., help="Module id."),
    json_output: bool = typer.Option(False, "--json", help="Emit the capability surface as JSON."),
) -> None:
    """Show a module's full capability surface (v2: context, collections, workflows, mcp)."""
    import json as _json

    from atlas_runtime import module_service

    conn = _get_connection()
    manifest = module_service.active_manifest(conn, module_id)
    if manifest is None:
        # Fall back to the stored manifest so `info` still explains an inactive module.
        manifest = module_service.get_manifest(conn, module_id)
        if manifest is None:
            typer.echo(f"Error: no manifest for module {module_id!r}", err=True)
            raise typer.Exit(1)
        typer.echo("status: inactive (capabilities are not reachable until activated)")
    if json_output:
        typer.echo(_json.dumps(manifest, indent=2))
        return
    caps = module_service.capability
    typer.echo(f"{manifest['id']} v{manifest.get('version', '0')} — {manifest.get('name', '')}")
    if manifest.get("description"):
        typer.echo(manifest["description"])
    for label, key in (
        ("commands", "commands"), ("context", "context"),
        ("collections", "collections"), ("workflows", "workflows"), ("mcp", "mcp"),
    ):
        entries = caps(manifest, key)
        if not entries:
            continue
        typer.echo(f"\n{label}:")
        for entry in entries:
            name = entry.get("name") or entry.get("id") or "?"
            detail = entry.get("description") or entry.get("title") or ""
            typer.echo(f"  {name}\t{detail}")


@module_app.command("context")
def module_context(
    module_id: str = typer.Argument(..., help="Module id."),
    context_id: str = typer.Argument(None, help="Context file id (default: all)."),
) -> None:
    """Print a module's declared doctrine — exactly what a run would be given."""
    from atlas_runtime import module_service

    conn = _get_connection()
    manifest = module_service.active_manifest(conn, module_id) or module_service.get_manifest(
        conn, module_id
    )
    if manifest is None:
        typer.echo(f"Error: no manifest for module {module_id!r}", err=True)
        raise typer.Exit(1)
    printed = False
    for entry in module_service.capability(manifest, "context"):
        if context_id and entry["id"] != context_id:
            continue
        printed = True
        typer.echo(f"--- {entry['id']} ({entry.get('inject', 'always')}) ---")
        typer.echo(module_service.read_context_file(manifest, entry) or "(file missing on disk)")
    if not printed:
        typer.echo("(no matching context declared)")


@module_records_app.command("list")
def module_records_list(
    module_id: str = typer.Argument(..., help="Module id."),
    collection: str = typer.Argument(..., help="Collection id."),
    search: str = typer.Option("", "--search", help="Free-text filter."),
    limit: int = typer.Option(50, "--limit", help="Max rows."),
    json_output: bool = typer.Option(False, "--json", help="Emit records as JSON."),
) -> None:
    """List records in a module collection."""
    import json as _json

    from atlas_runtime import module_data_service

    try:
        records = module_data_service.query_records(
            _get_connection(), module_id, collection, search=search, limit=limit
        )
    except module_data_service.ModuleDataError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    if json_output:
        typer.echo(_json.dumps(records, indent=2))
        return
    for record in records:
        summary = ", ".join(f"{k}={v}" for k, v in list(record["data"].items())[:4])
        typer.echo(f"{record['id']}\t{summary}")


@module_records_app.command("get")
def module_records_get(
    module_id: str = typer.Argument(..., help="Module id."),
    collection: str = typer.Argument(..., help="Collection id."),
    record_id: str = typer.Argument(..., help="Record id."),
) -> None:
    """Print one record as JSON."""
    import json as _json

    from atlas_runtime import module_data_service

    try:
        module_data_service.resolve_collection(_get_connection(), module_id, collection)
    except module_data_service.ModuleDataError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    record = module_data_service.get_record(_get_connection(), module_id, collection, record_id)
    if record is None:
        typer.echo(f"Error: no record {record_id!r}", err=True)
        raise typer.Exit(1)
    typer.echo(_json.dumps(record, indent=2))


@module_records_app.command("set")
def module_records_set(
    module_id: str = typer.Argument(..., help="Module id."),
    collection: str = typer.Argument(..., help="Collection id."),
    data_json: str = typer.Argument(..., help='Field values as JSON, e.g. {"name":"Acme"}.'),
    record_id: str = typer.Option(None, "--id", help="Record id (default: derived from the label field)."),
) -> None:
    """Create or update a record (create merges on an existing id, so retries converge)."""
    import json as _json

    from atlas_runtime import module_data_service

    try:
        data = _json.loads(data_json)
    except ValueError as exc:
        typer.echo(f"Error: invalid JSON: {exc}", err=True)
        raise typer.Exit(1)
    conn, lock = _get_connection(), _get_lock()
    try:
        record = module_data_service.create_record(
            conn, lock, module_id=module_id, collection_id=collection,
            data=data, record_id=record_id,
        )
    except module_data_service.ModuleDataError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(record["id"])


@module_records_app.command("rm")
def module_records_rm(
    module_id: str = typer.Argument(..., help="Module id."),
    collection: str = typer.Argument(..., help="Collection id."),
    record_id: str = typer.Argument(..., help="Record id."),
) -> None:
    """Soft-delete a record (the payload is retained for undo)."""
    from atlas_runtime import module_data_service

    try:
        module_data_service.delete_record(
            _get_connection(), _get_lock(),
            module_id=module_id, collection_id=collection, record_id=record_id,
        )
    except module_data_service.ModuleDataError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"{record_id} deleted")


# ---------------------------------------------------------------------------
# mcp subcommands — MCP server registry and foundation projection
# ---------------------------------------------------------------------------


@mcp_app.command("list")
def mcp_list(
    json_output: bool = typer.Option(False, "--json", help="Emit the registry as JSON."),
) -> None:
    """List registered MCP servers as 'name<TAB>state<TAB>source<TAB>target'."""
    import json as _json

    from atlas_runtime import mcp_service

    servers = mcp_service.list_servers(_get_connection())
    if json_output:
        typer.echo(_json.dumps(servers, indent=2))
        return
    for server in servers:
        target = server["url"] or " ".join([server["command"], *server["args"]]).strip()
        state = "enabled" if server["enabled"] else "disabled"
        owner = f"module:{server['module_id']}" if server["module_id"] else server["source"]
        typer.echo(f"{server['name']}\t{state}\t{owner}\t{target}")


@mcp_app.command("add")
def mcp_add(
    name: str = typer.Argument(..., help="Server name ([a-z0-9._-])."),
    command: str = typer.Option("", "--command", help="Executable for a stdio server."),
    arg: list[str] = typer.Option([], "--arg", help="Argument for the command (repeatable)."),
    url: str = typer.Option("", "--url", help="Endpoint for an http server."),
    env: list[str] = typer.Option(
        [], "--env", help="KEY=${VAR} env reference (repeatable). Never a literal secret."
    ),
    description: str = typer.Option("", "--description", help="What this server is for."),
    enable: bool = typer.Option(False, "--enable", help="Enable it immediately."),
) -> None:
    """Register an operator-owned MCP server in the ATLAS registry."""
    from atlas_runtime import mcp_service

    env_map: dict[str, str] = {}
    for item in env:
        key, _, value = item.partition("=")
        if not key or not value:
            typer.echo(f"Error: --env expects KEY=VALUE (got {item!r})", err=True)
            raise typer.Exit(1)
        env_map[key.strip()] = value.strip()
    try:
        server = mcp_service.upsert_server(
            _get_connection(), _get_lock(),
            name=name,
            transport="http" if url else "stdio",
            command=command, args=list(arg), env=env_map, url=url,
            description=description, source="operator", enabled=enable,
        )
    except mcp_service.McpError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"{server['name']} {'enabled' if server['enabled'] else 'disabled'}")


@mcp_app.command("enable")
def mcp_enable(name: str = typer.Argument(..., help="Server name.")) -> None:
    """Enable a server and project it onto the foundation."""
    _mcp_set_enabled(name, True)


@mcp_app.command("disable")
def mcp_disable(name: str = typer.Argument(..., help="Server name.")) -> None:
    """Disable a server and retract it from the foundation."""
    _mcp_set_enabled(name, False)


def _mcp_set_enabled(name: str, enabled: bool) -> None:
    from atlas_runtime import mcp_service

    conn, lock = _get_connection(), _get_lock()
    try:
        server = mcp_service.set_enabled(conn, lock, name=name, enabled=enabled)
    except mcp_service.McpError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    report = mcp_service.apply_managed_servers(conn)
    typer.echo(f"{server['name']} {'enabled' if server['enabled'] else 'disabled'}")
    if not report["applied"]:
        typer.echo(f"projection skipped: {report['reason']}", err=True)
    for skipped, reason in report["skipped"].items():
        typer.echo(f"skipped {skipped}: {reason}", err=True)


@mcp_app.command("remove")
def mcp_remove(name: str = typer.Argument(..., help="Server name.")) -> None:
    """Delete a registry entry (module-declared servers return on the next sync)."""
    from atlas_runtime import mcp_service

    conn, lock = _get_connection(), _get_lock()
    removed = mcp_service.remove_server(conn, lock, name=name)
    mcp_service.apply_managed_servers(conn)
    typer.echo(f"{name} {'removed' if removed else 'not found'}")


@mcp_app.command("sync")
def mcp_sync(
    json_output: bool = typer.Option(False, "--json", help="Emit the sync summary as JSON."),
) -> None:
    """Register MCP declarations from active modules, then project onto the foundation."""
    import json as _json

    from atlas_runtime import mcp_service

    conn, lock = _get_connection(), _get_lock()
    summary = mcp_service.sync_module_servers(conn, lock)
    summary["projection"] = mcp_service.apply_managed_servers(conn)
    if json_output:
        typer.echo(_json.dumps(summary, indent=2))
        return
    typer.echo(f"registered: {', '.join(summary['registered']) or '(none)'}")
    if summary["retired"]:
        typer.echo(f"retired: {', '.join(summary['retired'])}")
    for problem in summary["problems"]:
        typer.echo(f"problem: {problem}", err=True)
    projection = summary["projection"]
    typer.echo(
        f"projection: written={len(projection['written'])} removed={len(projection['removed'])}"
        + (f" ({projection['reason']})" if projection["reason"] else "")
    )


@mcp_app.command("test")
def mcp_test(
    name: str = typer.Argument(..., help="Server name."),
    timeout: float = typer.Option(20.0, "--timeout", help="Connect timeout in seconds."),
) -> None:
    """Connect to a server and list the tools it exposes."""
    from atlas_runtime import mcp_service

    try:
        result = mcp_service.probe_server(
            _get_connection(), _get_lock(), name=name, timeout=timeout
        )
    except mcp_service.McpError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"{result['name']} {result['status']}")
    for tool in result["tools"]:
        typer.echo(f"  {tool}")
    if result["error"]:
        typer.echo(result["error"], err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# scratch subcommands — the agent scratchpad, from the operator's side
# ---------------------------------------------------------------------------


@scratch_app.command("list")
def scratch_list(
    kind: str = typer.Option("", "--kind", help="Filter by kind."),
    scope: str = typer.Option("", "--scope", help="Filter by scope."),
    search: str = typer.Option("", "--search", help="Substring filter."),
    limit: int = typer.Option(25, "--limit", help="Max entries."),
) -> None:
    """List scratchpad entries as 'id<TAB>kind<TAB>ttl<TAB>title'."""
    from atlas_runtime import scratchpad_service

    entries = scratchpad_service.list_entries(
        _get_connection(), kind=kind, scope=scope, search=search, limit=limit
    )
    for entry in entries:
        pin = "*" if entry["pinned"] else " "
        typer.echo(f"{pin}{entry['id']}\t{entry['kind']}\t{entry['ttl_policy']}\t{entry['title']}")


@scratch_app.command("get")
def scratch_get(entry_id: str = typer.Argument(..., help="Entry id.")) -> None:
    """Print a scratchpad entry's body."""
    from atlas_runtime import scratchpad_service

    entry = scratchpad_service.get_entry(_get_connection(), entry_id)
    if entry is None:
        typer.echo(f"Error: no scratchpad entry {entry_id!r}", err=True)
        raise typer.Exit(1)
    typer.echo(f"# {entry['title']} ({entry['kind']}, ttl={entry['ttl_policy']})")
    if entry.get("rationale"):
        typer.echo(f"# why: {entry['rationale']}")
    typer.echo(entry["body"])


@scratch_app.command("materialize")
def scratch_materialize(
    title: str = typer.Argument(..., help="What the disposable tool does."),
    from_file: str = typer.Option("", "--from-file", help="Read the script body from a file."),
    body: str = typer.Option("", "--body", help="Script body (inline)."),
    why: str = typer.Option(
        "", "--why",
        help="Required: why this is disposable and what already-existing thing it is not.",
    ),
    language: str = typer.Option("python", "--lang", help="python|bash|powershell|node|sql|text."),
    ttl: str = typer.Option("next_startup", "--ttl", help="Expiry policy."),
    entry_id: str = typer.Option("", "--id", help="Explicit entry id (default: slug of title)."),
) -> None:
    """Write a disposable script to the ATLAS scratch dir and register its TTL."""
    import pathlib as _pathlib

    from atlas_runtime import scratchpad_service

    if from_file:
        try:
            body = _pathlib.Path(from_file).read_text(encoding="utf-8")
        except OSError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1)
    try:
        result = scratchpad_service.materialize_tool(
            _get_connection(), _get_lock(),
            title=title, body=body, rationale=why, language=language, ttl_policy=ttl,
            entry_id=entry_id or None, scope="global", owner="operator",
        )
    except scratchpad_service.ScratchpadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"{result['id']}\t{result['path']}")
    typer.echo(f"run: {result['invocation']}")


@scratch_app.command("pin")
def scratch_pin(
    entry_id: str = typer.Argument(..., help="Entry id."),
    unpin: bool = typer.Option(False, "--unpin", help="Unpin instead."),
) -> None:
    """Pin an entry so no sweep removes it (the keep-this promotion)."""
    from atlas_runtime import scratchpad_service

    try:
        entry = scratchpad_service.set_pinned(
            _get_connection(), _get_lock(), entry_id=entry_id, pinned=not unpin
        )
    except scratchpad_service.ScratchpadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"{entry['id']} {'pinned' if entry['pinned'] else 'unpinned'}")


@scratch_app.command("rm")
def scratch_rm(entry_id: str = typer.Argument(..., help="Entry id.")) -> None:
    """Delete a scratchpad entry."""
    from atlas_runtime import scratchpad_service

    removed = scratchpad_service.remove_entry(_get_connection(), _get_lock(), entry_id=entry_id)
    typer.echo(f"{entry_id} {'removed' if removed else 'not found'}")


@scratch_app.command("sweep")
def scratch_sweep(
    startup: bool = typer.Option(
        False, "--startup",
        help="Also drop next_startup entries and orphaned run/session entries.",
    ),
) -> None:
    """Delete expired entries (pinned entries always survive)."""
    from atlas_runtime import scratchpad_service

    removed = scratchpad_service.sweep(_get_connection(), _get_lock(), startup=startup)
    typer.echo(" ".join(f"{k}={v}" for k, v in removed.items()))


@scratch_app.command("stats")
def scratch_stats() -> None:
    """Counts by kind and TTL policy."""
    import json as _json

    from atlas_runtime import scratchpad_service

    typer.echo(_json.dumps(scratchpad_service.stats(_get_connection()), indent=2))


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


@cashflow_app.command("provision")
def cashflow_provision(
    force: bool = typer.Option(
        False, "--force", help="Reinstall and rebuild even if fingerprints match."
    ),
) -> None:
    """Install deps and build the cashflow bundle now, streaming progress.

    Cashflow ships as source, so this is the step that turns it into something
    runnable. `cashflow start` triggers the same work in the background; run
    this when you would rather watch it finish.
    """
    from atlas_runtime import cashflow_control

    ok, message = cashflow_control.provision(force=force, log=typer.echo)
    typer.echo(message)
    if not ok:
        raise typer.Exit(1)


@cashflow_app.command("status")
def cashflow_status() -> None:
    """Print cashflow process status as 'running|stopped|provisioning <backend>'."""
    from atlas_runtime import cashflow_control

    st = cashflow_control.status()
    phase = st.get("phase", "idle")
    label = "running" if st["running"] else ("provisioning" if phase == "provisioning" else "stopped")
    typer.echo(f"{label} {st['backend']}")
    detail = st.get("detail")
    if detail:
        typer.echo(detail)


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
