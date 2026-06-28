"""atlas tools — list/inspect tools, call them (policy-gated), manage approvals.

Mirrors cli/discord.py. Each command supports --json so the Rust gateway can
dispatch and parse it (D-022). `call` routes through tool_service.invoke (the
single policy chokepoint): read-class tools run now; write/shell tools return a
pending approval. Exit-code convention (copied from discord approve): a PROCESSED
outcome exits 0 so the JSON reaches the gateway; an un-processable call (unknown
tool, bad approval id, not pending) echoes to stderr and exits non-zero.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import threading
from typing import Optional

import typer

tools_app = typer.Typer(
    name="tools",
    help="Developer tool integrations: list/manifests/call (policy-gated) + approvals.",
)

# Module-level lock singleton (monkeypatched in tests via _get_lock).
_LOCK = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    """File-backed SQLite connection (WAL + FK) for the tool approval queue."""
    from atlas_runtime.cli import main

    return main._get_connection()


def _get_lock() -> threading.Lock:
    return _LOCK


@tools_app.command("list")
def list_tools(json_out: bool = typer.Option(False, "--json", help="Emit JSON.")) -> None:
    """List the known tool names."""
    from atlas_runtime.tools import registry

    names = registry.get_registry().known_tools()
    if json_out:
        typer.echo(json.dumps({"tools": names}))
        return
    for n in names:
        typer.echo(n)


@tools_app.command("manifests")
def manifests(json_out: bool = typer.Option(False, "--json", help="Emit JSON.")) -> None:
    """Print every tool manifest (name/risk_level/permissions/inputs/outputs)."""
    from atlas_runtime.tools import registry

    ms = registry.get_registry().manifests
    payload = [m.model_dump() for m in ms.values()]
    if json_out:
        typer.echo(json.dumps({"manifests": payload}))
        return
    for m in ms.values():
        typer.echo(f"{m.name}\t{m.risk_level}\t{m.description}")


@tools_app.command("call")
def call(
    tool_name: str = typer.Argument(..., help="Tool name (pass after `--` from the gateway)."),
    mode: str = typer.Option("read_only", "--mode", help="Policy mode (v0: read_only)."),
    args: Optional[str] = typer.Option(None, "--args", help="JSON object of tool args."),
    reason: Optional[str] = typer.Option(None, "--reason", help="Operator note for write/shell."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Invoke a tool through the policy chokepoint. Read-class runs now; write/shell
    returns a pending approval."""
    from atlas_runtime import tool_service

    payload: dict = {}
    if args:
        try:
            payload = json.loads(args)
            if not isinstance(payload, dict):
                raise ValueError("--args must be a JSON object")
        except ValueError as exc:
            typer.echo(f"Error: invalid --args JSON: {exc}", err=True)
            raise typer.Exit(1)

    conn = _get_connection()
    lock = _get_lock()
    try:
        outcome = tool_service.invoke(
            conn, lock, tool_name=tool_name, args=payload, mode=mode, reason=reason
        )
    except ValueError as exc:  # unknown/unclassified tool — never auto-runs
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    if json_out:
        typer.echo(json.dumps(outcome.model_dump()))
        return
    # ToolApproval has .status; ToolResult has .ok.
    if hasattr(outcome, "status"):
        typer.echo(f"{outcome.id}\t{outcome.status}\t{outcome.summary}")
    else:
        typer.echo(f"{outcome.tool_name}\t{'ok' if outcome.ok else 'failed'}")


@tools_app.command("approvals")
def approvals(
    status: str = typer.Option("pending", "--status", help="Filter by status; 'all' for every row."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """List tool approvals (pending by default)."""
    from atlas_runtime import tool_service

    conn = _get_connection()
    rows = tool_service.list_approvals(conn, status=None if status == "all" else status)
    if json_out:
        typer.echo(json.dumps({"approvals": [a.model_dump() for a in rows]}))
        return
    if not rows:
        typer.echo("no approvals")
        return
    for a in rows:
        typer.echo(f"{a.id}\t{a.status}\t{a.tool_name}\t{a.summary}")


@tools_app.command("approve")
def approve(
    approval_id: str = typer.Argument(..., help="Approval id to execute."),
    reason: Optional[str] = typer.Option(None, "--reason", help="Override the audit reason."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Approve + execute a pending write/shell tool call."""
    from atlas_runtime import tool_service

    conn = _get_connection()
    lock = _get_lock()
    try:
        approval = tool_service.approve(conn, lock, approval_id=approval_id, reason=reason)
    except tool_service.ToolApprovalError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    # A failed tool run is a processed outcome (status="failed"), not a CLI error
    # — exit 0 so the JSON reaches the gateway. Only un-processable ids exit non-zero.
    if json_out:
        typer.echo(json.dumps(approval.model_dump()))
        return
    typer.echo(f"{approval.id}\t{approval.status}")


@tools_app.command("reject")
def reject(
    approval_id: str = typer.Argument(..., help="Approval id to reject."),
    reason: Optional[str] = typer.Option(None, "--reason", help="Why it was rejected."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Reject a pending tool approval (it will never execute)."""
    from atlas_runtime import tool_service

    conn = _get_connection()
    lock = _get_lock()
    try:
        approval = tool_service.reject(conn, lock, approval_id=approval_id, reason=reason)
    except tool_service.ToolApprovalError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    if json_out:
        typer.echo(json.dumps(approval.model_dump()))
        return
    typer.echo(f"{approval.id}\t{approval.status}")
