"""`atlas components` — manage optional SDK components (claude, codex).

The npm runtime ships lean; these commands let the operator add or remove the
optional agent SDKs after installation. Surfaces read the same availability
report (gateway /v1/components) to hide runtimes whose component is absent.
"""
from __future__ import annotations

import json

import typer

from atlas_runtime import component_service

components_app = typer.Typer(
    name="components",
    help="Optional SDK components: list availability, install, uninstall.",
)


def _echo(payload: dict | list, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(payload))
        return
    rows = payload if isinstance(payload, list) else [payload]
    for row in rows:
        state = "installed" if row.get("installed") else "not installed"
        cli = "cli found" if row.get("cli_present") else "cli missing"
        changed = " (changed)" if row.get("changed") else ""
        typer.echo(
            f"{row['name']:<8} {state:<14} {cli:<12} runtime={row['agent_runtime']}{changed}"
        )


@components_app.command("list")
def components_list(
    json_output: bool = typer.Option(False, "--json", help="Emit as JSON."),
) -> None:
    """Report availability of every managed component."""
    _echo(component_service.list_components(), json_output)


@components_app.command("install")
def components_install(
    name: str = typer.Argument(..., help="Component name: claude | codex"),
    json_output: bool = typer.Option(False, "--json", help="Emit as JSON."),
) -> None:
    """Install a component's pinned SDK into this runtime's Python environment."""
    try:
        result = component_service.install_component(name)
    except component_service.ComponentError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    _echo(result, json_output)


@components_app.command("uninstall")
def components_uninstall(
    name: str = typer.Argument(..., help="Component name: claude | codex"),
    json_output: bool = typer.Option(False, "--json", help="Emit as JSON."),
) -> None:
    """Remove a component's SDK from this runtime's Python environment."""
    try:
        result = component_service.uninstall_component(name)
    except component_service.ComponentError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    _echo(result, json_output)
