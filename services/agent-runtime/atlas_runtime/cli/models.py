"""ATLAS CLI — atlas models refresh|list subcommands (D-017 AI router).

Thin wrappers over atlas_runtime.model_registry; no SQL here.
"""
from __future__ import annotations

import json

import typer

from atlas_runtime import config_service, control_plane_service, model_registry

models_app = typer.Typer(name="models", help="AI router model registry")


@models_app.command("refresh")
def refresh(
    gateway: str = typer.Option(
        None, "--gateway", help="Gateway base URL (default: ATLAS_LLM_GATEWAY_URL or loopback sidecar)"
    ),
) -> None:
    """Sync the model registry with the gateway's live /models list."""
    from atlas_runtime.cli.main import _get_connection, _get_lock

    conn = _get_connection()
    lock = _get_lock()
    base = gateway.rstrip("/") if gateway else None
    try:
        result = model_registry.refresh(
            conn,
            lock,
            source=base,
            fetcher=lambda: model_registry.fetch_gateway_models(base_url=base),
        )
    except Exception as exc:  # network/parse errors surface as exit 1
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"source: {result.source}")
    typer.echo(
        f"added: {len(result.added)}  retained: {len(result.retained)}  "
        f"deactivated: {len(result.deactivated)}  active: {result.total_active}"
    )
    for model_id in result.added:
        typer.echo(f"+ {model_id}")
    for model_id in result.deactivated:
        typer.echo(f"- {model_id}")


@models_app.command("list")
def list_cmd(
    all_models: bool = typer.Option(False, "--all", help="Include deactivated models"),
) -> None:
    """List registered models (active by default)."""
    from atlas_runtime.cli.main import _get_connection

    conn = _get_connection()
    rows = model_registry.list_models(conn, active_only=not all_models)
    if not rows:
        typer.echo("no models registered")
        return
    for row in rows:
        flag = "" if row["active"] else "  [inactive]"
        provider = f" ({row['provider']})" if row["provider"] else ""
        typer.echo(f"{row['model_id']}{provider}{flag}")


@models_app.command("status")
def status(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit the shared ProviderModelStatus object as JSON",
    ),
) -> None:
    """Show configured/effective provider, model, auth, and registry health."""
    from atlas_runtime.cli.main import _get_connection

    snapshot = control_plane_service.get_config_snapshot(
        config_service.load_config(),
        conn=_get_connection(),
    )
    effective = snapshot.effective
    if effective is None:
        typer.echo("model status unavailable", err=True)
        raise typer.Exit(1)
    if json_output:
        typer.echo(json.dumps(effective.model_dump(), ensure_ascii=False))
        return
    typer.echo(
        f"{effective.effective_provider}/{effective.effective_model} "
        f"[{effective.model_health}] source={effective.source} "
        f"auth={effective.auth_status} fallback={effective.fallback_status}"
    )
    if effective.remediation:
        typer.echo(f"remediation: {effective.remediation}")
