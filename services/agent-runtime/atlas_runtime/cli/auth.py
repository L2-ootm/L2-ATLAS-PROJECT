"""Local secret-safe auth management commands."""
from __future__ import annotations

import json
import sqlite3
import threading

import typer

from atlas_runtime import auth_service

auth_app = typer.Typer(
    name="auth",
    help="Manage ATLAS-owned credentials and inspect external auth presence.",
)


def _get_connection() -> sqlite3.Connection:
    from atlas_runtime.cli import main

    return main._get_connection()


def _get_lock() -> threading.Lock:
    from atlas_runtime.cli import main

    return main._get_lock()


def _render_error(exc: auth_service.AuthServiceError) -> None:
    typer.echo(
        json.dumps(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "remediation": exc.remediation,
                }
            }
        ),
        err=True,
    )


def _status_for(provider: str):
    for status in auth_service.list_auth_status():
        if status.provider == provider:
            return status
    return auth_service.doctor(provider=provider)


@auth_app.command("add")
def add(
    provider: str = typer.Argument(..., help="Provider id, e.g. openrouter"),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="Optional provider endpoint metadata",
    ),
) -> None:
    """Prompt privately for an API key and store it in auth.json."""
    secret = typer.prompt("API key", hide_input=True)
    try:
        status = auth_service.set_api_key(
            provider,
            secret,
            base_url=base_url,
            conn=_get_connection(),
            audit_lock=_get_lock(),
            source="cli",
        )
    except auth_service.AuthServiceError as exc:
        _render_error(exc)
        raise typer.Exit(1)
    typer.echo(json.dumps(status.model_dump(), ensure_ascii=False))


@auth_app.command("remove")
def remove(provider: str = typer.Argument(..., help="Provider id")) -> None:
    """Remove an ATLAS-owned credential; safe to repeat."""
    try:
        removed = auth_service.remove_provider(
            provider,
            conn=_get_connection(),
            audit_lock=_get_lock(),
            source="cli",
        )
    except auth_service.AuthServiceError as exc:
        _render_error(exc)
        raise typer.Exit(1)
    typer.echo(f"{provider}: {'removed' if removed else 'already absent'}")


@auth_app.command("list")
def list_auth() -> None:
    """List masked auth status from owned, env, and external sources."""
    try:
        statuses = auth_service.list_auth_status()
    except auth_service.AuthServiceError as exc:
        _render_error(exc)
        raise typer.Exit(1)
    for status in statuses:
        typer.echo(
            f"{status.provider}\t{status.status}\t{status.source}\t"
            f"{status.redacted_hint or '—'}"
        )


@auth_app.command("status")
def status(provider: str = typer.Argument(..., help="Provider id")) -> None:
    """Show one provider's masked auth status."""
    try:
        value = _status_for(provider)
    except auth_service.AuthServiceError as exc:
        _render_error(exc)
        raise typer.Exit(1)
    typer.echo(json.dumps(value.model_dump(), ensure_ascii=False))


@auth_app.command("json")
def emit_json() -> None:
    """Emit all masked auth status as JSON."""
    try:
        statuses = auth_service.list_auth_status()
    except auth_service.AuthServiceError as exc:
        _render_error(exc)
        raise typer.Exit(1)
    typer.echo(
        json.dumps(
            [status.model_dump() for status in statuses],
            ensure_ascii=False,
        )
    )


@auth_app.command("codex-status")
def codex_status() -> None:
    """Show the operator's Codex (ChatGPT OAuth) login status — secret-free."""
    from atlas_runtime import codex_auth

    typer.echo(json.dumps(codex_auth.cli_status(), ensure_ascii=False))


@auth_app.command("import-codex")
def import_codex() -> None:
    """Import the existing Codex/ChatGPT OAuth login for use as a provider.

    Reads ~/.codex/auth.json read-only and hands the tokens to the foundation,
    which stores+refreshes them in its own store (never writes back to ~/.codex).
    Set provider.auth_mode=oauth_import to run on the imported login.
    """
    from atlas_runtime import codex_auth

    try:
        result = codex_auth.import_from_codex_cli()
    except Exception as exc:  # noqa: BLE001 — surface as a clean CLI error
        typer.echo(json.dumps({"error": {"message": str(exc)[:200]}}), err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(result, ensure_ascii=False))
    if not result.get("imported"):
        raise typer.Exit(1)


@auth_app.command("doctor")
def doctor(provider: str = typer.Argument(..., help="Provider id")) -> None:
    """Diagnose one provider's auth boundary and show remediation."""
    try:
        value = auth_service.doctor(provider=provider)
    except auth_service.AuthServiceError as exc:
        _render_error(exc)
        raise typer.Exit(1)
    typer.echo(json.dumps(value.model_dump(), ensure_ascii=False))


__all__ = ["auth_app"]
