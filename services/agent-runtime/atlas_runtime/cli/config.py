"""Thin CLI adapters over the canonical configuration control plane."""
from __future__ import annotations

import json
import pathlib
import sqlite3
import threading

import typer
import yaml
from atlas_core.schemas.control_plane import ConfigPatchRequest, ControlPlaneError
from pydantic import ValidationError

from atlas_runtime import config_service as cfgsvc
from atlas_runtime import control_plane_service

config_app = typer.Typer(
    name="config",
    help="Read/write ATLAS config (~/.atlas/config.yaml).",
)


def _get_connection() -> sqlite3.Connection:
    from atlas_runtime.cli import main

    return main._get_connection()


def _get_lock() -> threading.Lock:
    from atlas_runtime.cli import main

    return main._get_lock()


def _error_payload(exc: ControlPlaneError) -> dict[str, object]:
    error: dict[str, object] = {
        "code": exc.code,
        "message": exc.message,
        "remediation": exc.remediation,
    }
    if exc.field is not None:
        error["field"] = exc.field
    payload: dict[str, object] = {"error": error}
    if exc.current_revision is not None:
        payload["current_revision"] = exc.current_revision
    return payload


def _render_structured_error(exc: ControlPlaneError) -> None:
    typer.echo(json.dumps(_error_payload(exc), ensure_ascii=False), err=True)


def _exit_code(exc: ControlPlaneError) -> int:
    return 2 if exc.code == "config_revision_conflict" else 1


def _flatten_config(config: cfgsvc.AtlasConfig) -> dict[str, object]:
    changes: dict[str, object] = {}

    def visit(prefix: str, value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if not prefix and key in {"schema_version", "revision"}:
                    continue
                visit(f"{prefix}.{key}" if prefix else key, child)
            return
        changes[prefix] = value

    visit("", config.model_dump())
    return changes


@config_app.command("show")
def show() -> None:
    """Print the current masked config and setting metadata as YAML."""
    snapshot = control_plane_service.get_config_snapshot()
    typer.echo(
        yaml.safe_dump(
            snapshot.model_dump(),
            sort_keys=False,
        ).rstrip()
    )


@config_app.command("json")
def emit_json() -> None:
    """Emit the canonical masked snapshot consumed by gateway and surfaces."""
    snapshot = control_plane_service.get_config_snapshot()
    typer.echo(json.dumps(snapshot.model_dump(), ensure_ascii=False))


@config_app.command("get")
def get(key: str = typer.Argument(..., help="Dotted key, e.g. provider.model")) -> None:
    """Print one configured value by dotted key."""
    config = cfgsvc.load_config()
    try:
        typer.echo(cfgsvc.get_value(config, key))
    except KeyError:
        typer.echo(f"unknown key: {key}")
        raise typer.Exit(1)


@config_app.command("patch")
def patch_config(
    expected_revision: int = typer.Option(
        ...,
        "--expected-revision",
        min=0,
        help="Revision returned by the last masked GET",
    ),
    changes_json: str = typer.Option(
        ...,
        "--changes-json",
        help="JSON object whose keys are dotted config paths",
    ),
) -> None:
    """Apply one optimistic multi-field patch and emit the new snapshot."""
    try:
        request = ConfigPatchRequest(
            expected_revision=expected_revision,
            changes_json=changes_json,
            source_surface="cli",
        )
        snapshot = control_plane_service.patch(
            _get_connection(),
            _get_lock(),
            expected_revision=request.expected_revision,
            changes=request.changes(),
            source_surface=request.source_surface,
        )
    except ValidationError as exc:
        error = ControlPlaneError(
            "config_invalid",
            "invalid config patch request",
            "provide a non-negative revision and a JSON object of dotted changes",
        )
        _render_structured_error(error)
        raise typer.Exit(1) from exc
    except ControlPlaneError as exc:
        _render_structured_error(exc)
        raise typer.Exit(_exit_code(exc))
    typer.echo(json.dumps(snapshot.model_dump(), ensure_ascii=False))


@config_app.command("set")
def set_value(
    key: str = typer.Argument(..., help="Dotted key, e.g. runtime.iteration_budget"),
    value: str = typer.Argument(..., help="New value, validated against the schema"),
) -> None:
    """Set one value through the same optimistic audited PATCH path."""
    current = cfgsvc.load_config()
    try:
        candidate = cfgsvc.set_value(current, key, value)
        typed_value = cfgsvc.get_value(candidate, key)
        snapshot = control_plane_service.patch(
            _get_connection(),
            _get_lock(),
            expected_revision=current.revision,
            changes={key: typed_value},
            source_surface="cli",
        )
    except KeyError:
        typer.echo(f"unknown key: {key}")
        raise typer.Exit(1)
    except ControlPlaneError as exc:
        typer.echo(f"invalid value for {key}: {exc.message}")
        typer.echo(f"remediation: {exc.remediation}")
        raise typer.Exit(_exit_code(exc))
    typer.echo(f"set {key} = {cfgsvc.get_value(snapshot, key)}")


@config_app.command("export")
def export_config(
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Write to this path (default: stdout)",
    ),
) -> None:
    """Export the versioned non-secret config as round-trippable YAML."""
    config = cfgsvc.load_config()
    body = yaml.safe_dump(config.model_dump(), sort_keys=False)
    if output:
        path = pathlib.Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        typer.echo(f"exported -> {path}")
    else:
        typer.echo(body.rstrip())


@config_app.command("import")
def import_config(
    path: str = typer.Argument(
        ...,
        help="YAML config file whose settings replace the current settings",
    ),
) -> None:
    """Import settings through the audited optimistic PATCH path."""
    source = pathlib.Path(path)
    if not source.is_file():
        typer.echo(f"Error: file not found: {source}", err=True)
        raise typer.Exit(1)
    try:
        data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        imported = cfgsvc.AtlasConfig.model_validate(data)
    except Exception as exc:
        typer.echo(f"Error: invalid config in {source}: {exc}", err=True)
        raise typer.Exit(1)

    current = cfgsvc.load_config()
    try:
        control_plane_service.patch(
            _get_connection(),
            _get_lock(),
            expected_revision=current.revision,
            changes=_flatten_config(imported),
            source_surface="cli_import",
        )
    except ControlPlaneError as exc:
        _render_structured_error(exc)
        raise typer.Exit(_exit_code(exc))
    typer.echo(f"imported -> {cfgsvc.default_config_path()}")


def setup() -> None:
    """First-run wizard that patches selected fields and preserves the rest."""
    config = cfgsvc.load_config()
    typer.echo("ATLAS Setup")
    typer.echo("===========")

    typer.echo("\n1. AI Provider")
    name = typer.prompt("   provider", default=config.provider.name)
    model = typer.prompt("   model", default=config.provider.model)
    key_var = typer.prompt(
        "   API key env var name (stored as env:VAR; blank to keep)",
        default="",
    ).strip()
    api_key = f"env:{key_var}" if key_var else config.provider.api_key

    typer.echo("\n2. Agent Runtime")
    default_agent = typer.prompt(
        "   default agent (native|claude_code)",
        default=config.runtime.default_agent,
    )
    budget = typer.prompt(
        "   iteration budget",
        default=config.runtime.iteration_budget,
        type=int,
    )

    typer.echo("\n3. Gateway")
    rust_port = typer.prompt(
        "   gateway port",
        default=config.gateway.rust_port,
        type=int,
    )
    messaging_enabled = typer.confirm(
        "   enable messaging gateway?",
        default=config.gateway.messaging_enabled,
    )

    typer.echo("\n4. Cockpit")
    cockpit_port = typer.prompt(
        "   cockpit port",
        default=config.cockpit.port,
        type=int,
    )

    changes = {
        "provider.name": name,
        "provider.model": model,
        "provider.api_key": api_key,
        "runtime.default_agent": default_agent,
        "runtime.iteration_budget": budget,
        "gateway.rust_port": rust_port,
        "gateway.messaging_enabled": messaging_enabled,
        "cockpit.port": cockpit_port,
    }
    try:
        control_plane_service.patch(
            _get_connection(),
            _get_lock(),
            expected_revision=config.revision,
            changes=changes,
            source_surface="cli_setup",
        )
    except ControlPlaneError as exc:
        _render_structured_error(exc)
        raise typer.Exit(_exit_code(exc))
    typer.echo(f"\nwrote {cfgsvc.default_config_path()}")

    if typer.confirm("initialize the database now (atlas db init)?", default=True):
        from atlas_runtime import db, model_registry

        conn = db.connect()
        applied = db.apply_migrations(conn)
        typer.echo(
            "migrations: "
            + (", ".join(applied) if applied else "already up to date")
        )
        seeded = model_registry.seed_default_models(conn, threading.Lock())
        if seeded:
            typer.echo("seeded default models: " + ", ".join(seeded))

    typer.echo("setup complete — start with: atlas gateway start")


__all__ = ["config_app", "setup"]
