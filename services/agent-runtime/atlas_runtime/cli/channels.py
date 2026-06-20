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

import json
import os
import pathlib
import tempfile
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


def _load_config(config_path: pathlib.Path) -> Optional[dict[str, Any]]:
    """Return the full foundation config doc, or None if absent."""
    if not config_path.is_file():
        return None
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def _load_platforms(config_path: pathlib.Path) -> Optional[dict[str, Any]]:
    """Return the gateway.platforms mapping from config.yaml, or None."""
    data = _load_config(config_path)
    if data is None:
        return None
    gateway = data.get("gateway") or {}
    platforms = gateway.get("platforms") or {}
    return platforms if isinstance(platforms, dict) else {}


def _save_config(config_path: pathlib.Path, data: dict[str, Any]) -> None:
    """Atomically write the foundation config doc back. NOTE: a YAML round-trip
    does not preserve comments; the foundation config is machine-managed here."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    fd, tmp = tempfile.mkstemp(dir=str(config_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.replace(tmp, str(config_path))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _set_enabled(config_path: pathlib.Path, name: str, enabled: bool) -> None:
    """Set gateway.platforms.<name>.enabled, preserving the rest of the doc."""
    data = _load_config(config_path) or {}
    gateway = data.setdefault("gateway", {})
    if not isinstance(gateway, dict):
        gateway = {}
        data["gateway"] = gateway
    platforms = gateway.setdefault("platforms", {})
    if not isinstance(platforms, dict):
        platforms = {}
        gateway["platforms"] = platforms
    entry = platforms.setdefault(name, {})
    if not isinstance(entry, dict):
        entry = {}
        platforms[name] = entry
    entry["enabled"] = enabled
    _save_config(config_path, data)


def _channels_summary(platforms: dict[str, Any]) -> list[dict[str, Any]]:
    """Serializable channel list: name, enabled, credential presence (never values)."""
    out: list[dict[str, Any]] = []
    for name in sorted(platforms):
        entry = platforms[name] or {}
        if not isinstance(entry, dict):
            continue
        out.append(
            {
                "name": name,
                "enabled": bool(entry.get("enabled")),
                "credential_present": any(
                    str(entry.get(k) or "").strip() for k in _CREDENTIAL_KEYS
                ),
            }
        )
    return out


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
    typer.echo("toggle channel: atlas channels enable|disable <name>")


@channels_app.command("json")
def emit_json() -> None:
    """Print channels as JSON (consumed by the gateway GET /v1/channels)."""
    platforms = _load_platforms(_hermes_home() / "config.yaml")
    typer.echo(json.dumps({"channels": _channels_summary(platforms or {})}))


@channels_app.command("enable")
def enable(name: str = typer.Argument(..., help="Channel/platform name, e.g. discord")) -> None:
    """Enable a channel in the foundation gateway config."""
    _set_enabled(_hermes_home() / "config.yaml", name, True)
    typer.echo(f"enabled {name}")


@channels_app.command("disable")
def disable(name: str = typer.Argument(..., help="Channel/platform name, e.g. discord")) -> None:
    """Disable a channel in the foundation gateway config."""
    _set_enabled(_hermes_home() / "config.yaml", name, False)
    typer.echo(f"disabled {name}")
