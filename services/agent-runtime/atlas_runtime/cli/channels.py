"""atlas channels subcommands — L2 BOT harness channel inspection.

Read-only surface over the foundation gateway config. Channel lifecycle is
owned by the foundation CLI (DIV-F-005 branded aliases):

    atlas-agent setup                                   # onboarding wizard
    atlas-agent config set gateway.platforms.X.enabled true
    atlas-agent gateway                                 # start the daemon

This module never writes config and never prints credential values — only
whether a credential key is present.
"""
from __future__ import annotations

import os
import pathlib
from typing import Any, Optional

import typer
import yaml

channels_app = typer.Typer(
    name="channels",
    help="Inspect L2 BOT harness channel connections (foundation gateway).",
)

# Credential-bearing keys we report presence (never values) for.
_CREDENTIAL_KEYS = ("token", "api_key", "app_secret", "client_secret", "auth_token")


def _hermes_home() -> pathlib.Path:
    """Resolve the foundation home (HERMES_HOME aware)."""
    try:
        from hermes_constants import get_hermes_home

        return pathlib.Path(get_hermes_home())
    except Exception:
        env = os.environ.get("HERMES_HOME", "").strip()
        return pathlib.Path(env) if env else pathlib.Path.home() / ".hermes"


def _load_platforms(config_path: pathlib.Path) -> Optional[dict[str, Any]]:
    """Return the gateway.platforms mapping from config.yaml, or None."""
    if not config_path.is_file():
        return None
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    gateway = data.get("gateway") or {}
    platforms = gateway.get("platforms") or {}
    return platforms if isinstance(platforms, dict) else {}


@channels_app.command("status")
def status() -> None:
    """Show configured channels: enabled state and credential presence."""
    home = _hermes_home()
    config_path = home / "config.yaml"
    typer.echo(f"foundation home: {home}")
    platforms = _load_platforms(config_path)
    if platforms is None:
        typer.echo(f"config not found: {config_path}")
        typer.echo("run `atlas-agent setup` to initialize the foundation config")
        raise typer.Exit(1)
    if not platforms:
        typer.echo("no channels configured (gateway.platforms is empty)")
        typer.echo("enable one: atlas-agent config set gateway.platforms.<name>.enabled true")
        return
    for name in sorted(platforms):
        entry = platforms[name] or {}
        if not isinstance(entry, dict):
            continue
        enabled = bool(entry.get("enabled"))
        has_cred = any(str(entry.get(k) or "").strip() for k in _CREDENTIAL_KEYS)
        cred = "credential: set" if has_cred else "credential: none (env override possible)"
        state = "ENABLED " if enabled else "disabled"
        typer.echo(f"{state}  {name:<16} {cred}")
    typer.echo("")
    typer.echo("launch daemon:  atlas-agent gateway")
    typer.echo("toggle channel: atlas-agent config set gateway.platforms.<name>.enabled true|false")
