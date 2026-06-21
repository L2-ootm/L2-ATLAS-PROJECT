"""atlas config + atlas setup — ATLAS-owned config (~/.atlas/config.yaml).

Thin CLI over config_service. `config show/get/set` are non-interactive; `setup`
is the first-run wizard. Secrets are only ever stored as `env:VAR` references —
the wizard asks for an env var NAME, never a key value.
"""
from __future__ import annotations

import json
import pathlib

import typer
import yaml

from atlas_runtime import config_service as cfgsvc

config_app = typer.Typer(name="config", help="Read/write ATLAS config (~/.atlas/config.yaml).")


@config_app.command("show")
def show() -> None:
    """Print the current config (secrets shown as env: refs only)."""
    cfg = cfgsvc.load_config()
    typer.echo(yaml.safe_dump(cfgsvc.masked_dict(cfg), sort_keys=False).rstrip())


@config_app.command("json")
def emit_json() -> None:
    """Print the masked config as JSON (consumed by the gateway /v1/config)."""
    typer.echo(json.dumps(cfgsvc.masked_dict(cfgsvc.load_config())))


@config_app.command("get")
def get(key: str = typer.Argument(..., help="Dotted key, e.g. provider.model")) -> None:
    """Print one config value by dotted key."""
    cfg = cfgsvc.load_config()
    try:
        typer.echo(cfgsvc.get_value(cfg, key))
    except KeyError:
        typer.echo(f"unknown key: {key}")
        raise typer.Exit(1)


@config_app.command("set")
def set_value(
    key: str = typer.Argument(..., help="Dotted key, e.g. runtime.iteration_budget"),
    value: str = typer.Argument(..., help="New value (coerced to the field type)"),
) -> None:
    """Set one config value by dotted key (re-validated, then saved atomically)."""
    cfg = cfgsvc.load_config()
    try:
        # Pydantic coerces strings to the target field type on revalidation; an
        # inline secret on provider.api_key is rejected here.
        cfg = cfgsvc.set_value(cfg, key, value)
    except KeyError:
        typer.echo(f"unknown key: {key}")
        raise typer.Exit(1)
    except Exception as exc:  # validation error
        typer.echo(f"invalid value for {key}: {exc}")
        raise typer.Exit(1)
    cfgsvc.save_config(cfg)
    typer.echo(f"set {key} = {cfgsvc.get_value(cfg, key)}")


@config_app.command("export")
def export_config(
    output: str = typer.Option(
        None, "--output", "-o", help="Write to this path (default: stdout)"
    ),
) -> None:
    """Export the full config as YAML (to a file or stdout).

    The file is already secret-safe — credentials are stored only as ``env:VAR``
    references, never inline values — so the export is a plain round-trippable dump.
    """
    cfg = cfgsvc.load_config()
    body = yaml.safe_dump(cfg.model_dump(), sort_keys=False)
    if output:
        path = pathlib.Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        typer.echo(f"exported -> {path}")
    else:
        typer.echo(body.rstrip())


@config_app.command("import")
def import_config(
    path: str = typer.Argument(..., help="YAML config file to import (replaces current config)"),
) -> None:
    """Import a config from a YAML file (replace semantics, atomically saved).

    Validation enforces the no-inline-secret rule: a file with an inline
    ``provider.api_key`` is rejected before anything is written.
    """
    src = pathlib.Path(path)
    if not src.is_file():
        typer.echo(f"Error: file not found: {src}", err=True)
        raise typer.Exit(1)
    try:
        data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
        cfg = cfgsvc.AtlasConfig.model_validate(data)
    except Exception as exc:  # parse or validation error
        typer.echo(f"Error: invalid config in {src}: {exc}", err=True)
        raise typer.Exit(1)
    saved = cfgsvc.save_config(cfg)
    typer.echo(f"imported -> {saved}")


def setup() -> None:
    """First-run wizard: configure provider, runtime, gateway, cockpit; write
    ~/.atlas/config.yaml and optionally initialize the database."""
    cfg = cfgsvc.load_config()
    typer.echo("ATLAS Setup")
    typer.echo("===========")

    typer.echo("\n1. AI Provider")
    name = typer.prompt("   provider", default=cfg.provider.name)
    model = typer.prompt("   model", default=cfg.provider.model)
    key_var = typer.prompt(
        "   API key env var name (stored as env:VAR; blank to keep)", default=""
    ).strip()
    api_key = f"env:{key_var}" if key_var else cfg.provider.api_key

    typer.echo("\n2. Agent Runtime")
    default_agent = typer.prompt(
        "   default agent (native|claude_code)", default=cfg.runtime.default_agent
    )
    budget = typer.prompt("   iteration budget", default=cfg.runtime.iteration_budget, type=int)

    typer.echo("\n3. Gateway")
    rust_port = typer.prompt("   gateway port", default=cfg.gateway.rust_port, type=int)
    messaging_enabled = typer.confirm(
        "   enable messaging gateway?", default=cfg.gateway.messaging_enabled
    )

    typer.echo("\n4. Cockpit")
    cockpit_port = typer.prompt("   cockpit port", default=cfg.cockpit.port, type=int)

    new = cfgsvc.AtlasConfig(
        provider=cfgsvc.ProviderConfig(
            name=name, model=model, api_key=api_key, base_url=cfg.provider.base_url
        ),
        runtime=cfgsvc.RuntimeConfig(
            default_agent=default_agent,
            iteration_budget=budget,
            compression=cfg.runtime.compression,
        ),
        gateway=cfgsvc.GatewayConfig(
            rust_port=rust_port,
            messaging_enabled=messaging_enabled,
            messaging_port=cfg.gateway.messaging_port,
        ),
        cockpit=cfgsvc.CockpitConfig(port=cockpit_port, branding=cfg.cockpit.branding),
        modules=cfg.modules,
    )
    path = cfgsvc.save_config(new)
    typer.echo(f"\nwrote {path}")

    if typer.confirm("initialize the database now (atlas db init)?", default=True):
        import threading

        from atlas_runtime import db, model_registry

        conn = db.connect()
        applied = db.apply_migrations(conn)
        typer.echo(
            "migrations: " + (", ".join(applied) if applied else "already up to date")
        )
        seeded = model_registry.seed_default_models(conn, threading.Lock())
        if seeded:
            typer.echo("seeded default models: " + ", ".join(seeded))

    typer.echo("setup complete — start with: atlas gateway start")
