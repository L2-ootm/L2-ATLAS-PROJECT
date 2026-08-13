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
    # "configured", not "live": nothing here touched the network, and in ATLAS's
    # own vocabulary "live" is the verified tier. `provider test --probe` is what
    # earns the stronger word.
    mode_flag = "MOCK MODE" if info["mock_mode"] else "configured"
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
    probe: bool = typer.Option(
        False, "--probe", help="Also connect to the provider endpoint and report whether it answers."
    ),
) -> None:
    """Readiness check: is the active provider wired to run for real?

    Dry by default (no run, no network) — it reports that credentials resolve,
    which is a fact about configuration and not about anything being reachable.
    `--probe` connects to the endpoint and reports whether it answers.
    """
    info = provider_service.probe_reachable() if probe else provider_service.active_status()
    configured = not info["mock_mode"]
    # Dry: "configured" is everything the check establishes. Saying "runs will
    # call the provider" promised a future fact that no config read can support —
    # and it said exactly that while the endpoint was refusing connections.
    reason = (
        "credentials resolve - provider is configured (endpoint not probed)" if configured
        else "no resolvable credentials - runs fall back to MOCK MODE"
    )
    ready = configured
    if probe and configured:
        if info["reachable"] is True:
            reason = f"configured and reachable - {info['probe_detail']}"
        elif info["reachable"] is False:
            ready = False
            reason = f"configured but UNREACHABLE - {info['probe_detail']}"
        else:
            reason = f"credentials resolve; not probeable - {info['probe_detail']}"
    verdict = {
        "ready": ready,
        "configured": configured,
        "reachable": info.get("reachable") if probe else None,
        "probed": bool(probe and info.get("probed")),
        "provider": info["provider"],
        "model": info["model"],
        "auth_mode": info["auth_mode"],
        "reason": reason,
        "remediation": info["remediation"],
    }
    if json_output:
        typer.echo(json.dumps(verdict, ensure_ascii=False))
    else:
        typer.echo(f"{_OK if ready else _NO} {verdict['reason']}")
        if verdict["remediation"]:
            typer.echo(f"  fix: {verdict['remediation']}")
        if ready and not probe:
            typer.echo("  check the endpoint answers: atlas provider test --probe")
        elif ready:
            typer.echo("  probe a real run: atlas mission run <id> --execute")
    if not ready:
        raise typer.Exit(1)


__all__ = ["provider_app"]
