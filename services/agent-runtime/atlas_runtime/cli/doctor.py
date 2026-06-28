"""`atlas doctor` — single-command health aggregator.

Wraps existing health primitives (db migration status, config load, gateway/
cockpit health_ok, provider resolution) into one pass/fail report. Does NOT
re-implement any check: each line below delegates to the same service-layer
function the dedicated CLI commands (`atlas db status`, `atlas gateway
status`, ...) already use.

Secret-safe output (CLI-06 posture, T-10.0.2-09): the provider check NEVER
echoes the resolved `api_key` value, only "configured" or "mock".

Independent checks (T-10.0.2-10): each of the five checks is wrapped in its
own try/except so one failing subsystem never prevents the others from
reporting.
"""
from __future__ import annotations

import typer

from atlas_runtime import config_service, db


def _doctor_cmd() -> None:
    """Aggregate health check: db, config, gateway, cockpit, provider."""
    all_ok = True
    cfg = None

    # 1. DB — migration status.
    try:
        conn = db.connect()
        rows = db.migration_status(conn)
        pending = [version for version, applied in rows if not applied]
        if pending:
            typer.echo(f"db: pending migrations - {', '.join(pending)}")
            all_ok = False
        else:
            typer.echo("db: ok")
    except Exception as exc:  # noqa: BLE001 — report, never crash the run
        typer.echo(f"db: error - {exc}")
        all_ok = False

    # 2. Config — load validity.
    try:
        cfg = config_service.load_config()
        typer.echo("config: ok")
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"config: invalid - {exc}")
        all_ok = False

    # 3. Gateway — health_ok(), reused not re-implemented.
    try:
        from atlas_runtime import gateway_control

        if gateway_control.health_ok():
            typer.echo("gateway: ok")
        else:
            typer.echo("gateway: down")
            all_ok = False
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"gateway: error - {exc}")
        all_ok = False

    # 4. Cockpit — health_ok(), reused not re-implemented.
    try:
        from atlas_runtime import cockpit_control

        if cockpit_control.health_ok():
            typer.echo("cockpit: ok")
        else:
            typer.echo("cockpit: down")
            all_ok = False
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"cockpit: error - {exc}")
        all_ok = False

    # 5. Provider — configured / live (credential-less) / mock. Never echo the
    # resolved api_key value. Informational only — never fails the overall run.
    # Uses provider_service.active_status so credential-less modes (claude_code,
    # freellmapi) report "live", not a false "mock" (P3).
    if cfg is None:
        # all_ok already False from the config check above; this branch is purely informational.
        typer.echo("provider: skipped (config invalid)")
    else:
        try:
            from atlas_runtime import provider_service

            st = provider_service.active_status(cfg)
            if st["credentials_present"]:
                typer.echo("provider: configured")
            elif not st["mock_mode"]:
                typer.echo(f"provider: live ({st['auth_mode']})")
            else:
                typer.echo("provider: mock")
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"provider: error - {exc}")

    # 6. Claude-Code runtime — SDK + local `claude` CLI presence (P3). Reuses the
    # canonical provider_service check; informational, never fails the run.
    try:
        from atlas_runtime import provider_service

        cc = provider_service.claude_code_status()
        if cc["available"]:
            typer.echo("claude_code: ok")
        else:
            typer.echo(f"claude_code: unavailable - {cc['detail']}")
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"claude_code: error - {exc}")

    if not all_ok:
        raise typer.Exit(1)
