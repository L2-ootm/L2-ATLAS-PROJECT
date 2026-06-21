"""atlas discord — control the vendored Discord sidecar and browse Discord.

Lifecycle (start/status/stop) wraps discord_control (a sidecar process, like
`atlas cashflow`). Read commands (guilds/structure) call the sidecar's loopback
API via discord_api. Each command supports --json so the Rust gateway can
dispatch and parse it (D-022). Read-only: channel/role *writes* are a gated
follow-up.
"""
from __future__ import annotations

import json

import typer

discord_app = typer.Typer(
    name="discord",
    help="Discord surface: sidecar lifecycle + guild/channel/role browse (read-only).",
)


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
