"""ATLAS CLI — `atlas provider`: wire and inspect AI providers (the mesh).

Thin wrappers over atlas_runtime.provider_service (read-only composition) and the
existing auth/config services. Lets an operator see which ways they can wire a
model (api_key / Codex OAuth / Claude Code / FreeLLMAPI), what the active provider
resolves to, and whether a real run would call a provider or fall back to MOCK MODE.
"""
from __future__ import annotations

import json

import typer

from atlas_runtime import provider_service

provider_app = typer.Typer(
    name="provider",
    help="Wire and inspect AI providers - Codex OAuth, Claude Code, API keys, FreeLLMAPI.",
    no_args_is_help=True,
)

# ASCII-safe markers: ATLAS CLI must render on Windows cmd/PowerShell (cp1252),
# no-color, and non-UTF terminals. No Unicode glyphs in default human output.
_OK = "[ok]"
_NO = "[--]"


@provider_app.command("status")
def status(
    json_output: bool = typer.Option(False, "--json", help="Emit status as JSON."),
) -> None:
    """Show the active provider, model, auth mode, and whether runs hit MOCK MODE."""
    info = provider_service.active_status()
    if json_output:
        typer.echo(json.dumps(info, ensure_ascii=False))
        return
    mode_flag = "MOCK MODE" if info["mock_mode"] else "live"
    typer.echo(f"{info['provider']}/{info['model']}  [{mode_flag}]")
    typer.echo(f"  auth mode : {info['auth_mode']}  ({info['auth_mode_label']})")
    if info["base_url"]:
        typer.echo(f"  base url  : {info['base_url']}")
    typer.echo(f"  credentials present: {'yes' if info['credentials_present'] else 'no'}")
    if info["remediation"]:
        typer.echo(f"  remediation: {info['remediation']}")


@provider_app.command("modes")
def modes(
    json_output: bool = typer.Option(False, "--json", help="Emit the board as JSON."),
) -> None:
    """List the four ways to wire a model and which are available on this machine."""
    board = provider_service.modes_status()
    if json_output:
        typer.echo(json.dumps(board, ensure_ascii=False))
        return
    for m in board:
        mark = _OK if m["available"] else _NO
        active = "  <- active" if m["active"] else ""
        typer.echo(f"{mark} {m['mode']:<13} {m['label']}{active}")
        typer.echo(f"    {m['detail']}")
        if m["remediation"]:
            typer.echo(f"    fix: {m['remediation']}")


@provider_app.command("test")
def test(
    json_output: bool = typer.Option(False, "--json", help="Emit the verdict as JSON."),
) -> None:
    """Readiness check: is the active provider wired to run for real?

    Dry by default (no run, no network). To fire a real end-to-end probe, run a
    mission: `atlas mission create ... && atlas mission run <id> --execute`.
    """
    info = provider_service.active_status()
    ready = not info["mock_mode"]
    verdict = {
        "ready": ready,
        "provider": info["provider"],
        "model": info["model"],
        "auth_mode": info["auth_mode"],
        "reason": (
            "credentials resolve — runs will call the provider" if ready
            else "no resolvable credentials — runs fall back to MOCK MODE"
        ),
        "remediation": info["remediation"],
    }
    if json_output:
        typer.echo(json.dumps(verdict, ensure_ascii=False))
    else:
        typer.echo(f"{_OK if ready else _NO} {verdict['reason']}")
        if verdict["remediation"]:
            typer.echo(f"  fix: {verdict['remediation']}")
        if ready:
            typer.echo("  probe a real run: atlas mission run <id> --execute")
    if not ready:
        raise typer.Exit(1)


__all__ = ["provider_app"]
