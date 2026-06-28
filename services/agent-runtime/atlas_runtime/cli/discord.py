"""atlas discord — control the vendored Discord sidecar and browse Discord.

Lifecycle (start/status/stop) wraps discord_control (a sidecar process, like
`atlas cashflow`). Read commands (guilds/structure) call the sidecar's loopback
API via discord_api. Each command supports --json so the Rust gateway can
dispatch and parse it (D-022). Read-only: channel/role *writes* are a gated
follow-up.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import threading
from typing import Optional

import typer

discord_app = typer.Typer(
    name="discord",
    help="Discord surface: sidecar lifecycle + browse + gated writes (propose/approve).",
)

# Module-level lock singleton (monkeypatched in tests via _get_lock).
_LOCK = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    """File-backed SQLite connection (WAL + FK) for the gated-write approval queue."""
    from atlas_runtime.cli import main

    return main._get_connection()


def _get_lock() -> threading.Lock:
    return _LOCK


@discord_app.command("status")
def status(json_out: bool = typer.Option(False, "--json", help="Emit JSON.")) -> None:
    """Show whether the Discord sidecar is running (+ readiness, guild count)."""
    from atlas_runtime import discord_control

    state = discord_control.status()
    if json_out:
        typer.echo(json.dumps(state))
        return
    if not state["running"]:
        typer.echo("stopped")
        return
    ready = "ready" if state["ready"] else "starting"
    typer.echo(f"running ({ready}, {state['guild_count']} guilds, pid {state['pid']})")


@discord_app.command("start")
def start(json_out: bool = typer.Option(False, "--json", help="Emit JSON.")) -> None:
    """Start the Discord sidecar (detached; tracked by pid file)."""
    from atlas_runtime import discord_control

    ok, message = discord_control.start()
    if json_out:
        typer.echo(json.dumps({"ok": ok, "message": message, **discord_control.status()}))
        if not ok:
            raise typer.Exit(1)
        return
    typer.echo(message)
    if not ok:
        raise typer.Exit(1)


@discord_app.command("stop")
def stop(json_out: bool = typer.Option(False, "--json", help="Emit JSON.")) -> None:
    """Stop a Discord sidecar started by this CLI (idempotent)."""
    from atlas_runtime import discord_control

    ok, message = discord_control.stop()
    if json_out:
        typer.echo(json.dumps({"ok": ok, "message": message}))
        if not ok:
            raise typer.Exit(1)
        return
    typer.echo(message)
    if not ok:
        raise typer.Exit(1)


@discord_app.command("guilds")
def guilds(json_out: bool = typer.Option(False, "--json", help="Emit JSON.")) -> None:
    """List the guilds the bot is in (via the sidecar API)."""
    from atlas_runtime import discord_api

    try:
        data = discord_api.list_guilds()
    except discord_api.DiscordSidecarError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    if json_out:
        typer.echo(json.dumps({"guilds": data}))
        return
    for g in data:
        typer.echo(f"{g.get('id')}\t{g.get('name')}")


@discord_app.command("structure")
def structure(
    guild_id: str = typer.Argument(..., help="Guild (server) id."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Show a guild's structure: categories -> channels, plus roles."""
    from atlas_runtime import discord_api

    try:
        data = discord_api.get_structure(guild_id)
    except discord_api.DiscordSidecarError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    if json_out:
        typer.echo(json.dumps(data))
        return
    guild = data.get("guild", {})
    typer.echo(f"{guild.get('name')} ({guild.get('member_count')} members)")
    for cat in data.get("categories", []):
        typer.echo(f"# {cat.get('name')}")
        for ch in cat.get("channels", []):
            typer.echo(f"  {ch.get('type')}: {ch.get('name')}")
    if data.get("roles"):
        typer.echo(f"roles: {', '.join(r.get('name') for r in data['roles'])}")


# ---------------------------------------------------------------------------
# Gated writes — propose / approvals / approve / reject (Phase C)
# ---------------------------------------------------------------------------


@discord_app.command("propose")
def propose(
    action: str = typer.Argument(..., help="create_channel|edit_channel|delete_channel|create_role|edit_role|delete_role|send_message|set_permissions"),
    guild: str = typer.Option(..., "--guild", help="Guild (server) id."),
    target: Optional[str] = typer.Option(None, "--target", help="Channel/role id for edit/delete/permissions/message."),
    params: Optional[str] = typer.Option(None, "--params", help="JSON object of action params (gateway path)."),
    name: Optional[str] = typer.Option(None, "--name", help="Channel/role name (convenience)."),
    type_: Optional[str] = typer.Option(None, "--type", help="Channel type (text|voice|forum|category)."),
    category: Optional[str] = typer.Option(None, "--category", help="Parent category id (convenience)."),
    topic: Optional[str] = typer.Option(None, "--topic", help="Channel topic (convenience)."),
    color: Optional[str] = typer.Option(None, "--color", help="Role color hex (convenience)."),
    hoist: Optional[bool] = typer.Option(None, "--hoist", help="Hoist the role (convenience)."),
    reason: Optional[str] = typer.Option(None, "--reason", help="Operator note recorded with the request."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Propose a gated Discord write (records a pending approval; nothing executes)."""
    from atlas_runtime import discord_service

    payload: dict = {}
    if params:
        try:
            payload = json.loads(params)
            if not isinstance(payload, dict):
                raise ValueError("params must be a JSON object")
        except ValueError as exc:
            typer.echo(f"Error: invalid --params JSON: {exc}", err=True)
            raise typer.Exit(1)
    # Convenience flags overlay the JSON payload.
    for key, val in (
        ("name", name), ("type", type_), ("category_id", category),
        ("topic", topic), ("color_hex", color), ("hoist", hoist),
    ):
        if val is not None:
            payload[key] = val

    conn = _get_connection()
    lock = _get_lock()
    try:
        approval = discord_service.propose(
            conn, lock, action=action, guild_id=guild, target_id=target,
            params=payload, reason=reason,
        )
    except discord_service.DiscordApprovalError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    if json_out:
        typer.echo(json.dumps(approval.model_dump()))
        return
    typer.echo(f"{approval.id}\tpending\t{approval.summary}")


@discord_app.command("approvals")
def approvals(
    status: str = typer.Option("pending", "--status", help="Filter by status; 'all' for every row."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """List Discord write approvals (pending by default)."""
    from atlas_runtime import discord_service

    conn = _get_connection()
    rows = discord_service.list_approvals(conn, status=None if status == "all" else status)
    if json_out:
        typer.echo(json.dumps({"approvals": [a.model_dump() for a in rows]}))
        return
    if not rows:
        typer.echo("no approvals")
        return
    for a in rows:
        typer.echo(f"{a.id}\t{a.status}\t{a.action}\t{a.summary}")


@discord_app.command("approve")
def approve(
    approval_id: str = typer.Argument(..., help="Approval id to execute."),
    reason: Optional[str] = typer.Option(None, "--reason", help="Override the audit reason."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Approve + execute a pending Discord write via the sidecar."""
    from atlas_runtime import discord_service

    conn = _get_connection()
    lock = _get_lock()
    try:
        approval = discord_service.approve(conn, lock, approval_id=approval_id, reason=reason)
    except discord_service.DiscordApprovalError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    # A failed Discord write is a processed outcome (status="failed"), not a CLI
    # error — exit 0 so the JSON/status reaches the gateway/cockpit. Only an
    # un-processable approval (bad id / not pending) exits non-zero (above).
    if json_out:
        typer.echo(json.dumps(approval.model_dump()))
        return
    typer.echo(f"{approval.id}\t{approval.status}")


@discord_app.command("reject")
def reject(
    approval_id: str = typer.Argument(..., help="Approval id to reject."),
    reason: Optional[str] = typer.Option(None, "--reason", help="Why it was rejected."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Reject a pending Discord write (it will never execute)."""
    from atlas_runtime import discord_service

    conn = _get_connection()
    lock = _get_lock()
    try:
        approval = discord_service.reject(conn, lock, approval_id=approval_id, reason=reason)
    except discord_service.DiscordApprovalError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    if json_out:
        typer.echo(json.dumps(approval.model_dump()))
        return
    typer.echo(f"{approval.id}\t{approval.status}")
