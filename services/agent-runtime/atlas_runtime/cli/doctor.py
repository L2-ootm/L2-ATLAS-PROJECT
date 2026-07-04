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

import importlib
import json
from datetime import datetime, timezone

import typer

from atlas_runtime import config_service, db


def _doctor_cmd(json_output: bool = typer.Option(False, "--json", help="Emit the report as JSON.")) -> None:
    """Aggregate health check: db, config, gateway, cockpit, sidecars, provider."""
    all_ok = True
    cfg = None
    report: dict[str, object] = {}

    def echo(key: str, message: str, *, ok: bool) -> None:
        report[key] = {"status": message, "ok": ok}
        if not json_output:
            typer.echo(f"{key}: {message}")

    # 1. DB — migration status.
    try:
        conn = db.connect()
        rows = db.migration_status(conn)
        pending = [version for version, applied in rows if not applied]
        if pending:
            echo("db", f"pending migrations - {', '.join(pending)}", ok=False)
            all_ok = False
        else:
            echo("db", "ok", ok=True)
    except Exception as exc:  # noqa: BLE001 — report, never crash the run
        echo("db", f"error - {exc}", ok=False)
        all_ok = False

    # 2. Config — load validity.
    try:
        cfg = config_service.load_config()
        echo("config", "ok", ok=True)
    except Exception as exc:  # noqa: BLE001
        echo("config", f"invalid - {exc}", ok=False)
        all_ok = False

    # 3. Gateway — health_ok() + binary staleness (informational, never fails
    # the overall run: a stale-but-healthy binary is still serving requests).
    try:
        from atlas_runtime import gateway_control

        if gateway_control.health_ok():
            stale = gateway_control.binary_stale()
            if stale:
                # ok=False here is deliberately NOT folded into all_ok/exit code —
                # a stale-but-healthy binary is still serving requests — but a
                # JSON consumer checking report.gateway.ok must see the warning,
                # not a boolean identical to a genuinely fresh gateway.
                echo(
                    "gateway",
                    "ok (binary STALE — cargo build --release -p atlas-gateway)",
                    ok=False,
                )
            else:
                echo("gateway", "ok", ok=True)
        else:
            echo("gateway", "down", ok=False)
            all_ok = False
    except Exception as exc:  # noqa: BLE001
        echo("gateway", f"error - {exc}", ok=False)
        all_ok = False

    # 4. Cockpit — health_ok(), reused not re-implemented.
    try:
        from atlas_runtime import cockpit_control

        if cockpit_control.health_ok():
            echo("cockpit", "ok", ok=True)
        else:
            echo("cockpit", "down", ok=False)
            all_ok = False
    except Exception as exc:  # noqa: BLE001
        echo("cockpit", f"error - {exc}", ok=False)
        all_ok = False

    # 5. Optional sidecars — informational only, never fail the overall run:
    # each is an external/optional module (D-015 for freellmapi; cashflow and
    # discord are opt-in modules).
    for name, module_name, remediation in (
        ("freellmapi", "freellmapi_control", "atlas freellmapi start"),
        ("cashflow", "cashflow_control", "atlas cashflow start"),
        ("discord", "discord_control", "atlas discord start"),
    ):
        try:
            module = importlib.import_module(f"atlas_runtime.{module_name}")
            if module.health_ok(timeout=0.5):
                echo(name, "ok", ok=True)
            else:
                echo(name, f"offline - {remediation}", ok=False)
        except Exception as exc:  # noqa: BLE001
            echo(name, f"error - {exc}", ok=False)

    # 6. Model registry freshness — informational; flags a catalog nobody has
    # refreshed recently rather than failing the run.
    try:
        conn = db.connect()
        cur = conn.execute("SELECT MAX(last_seen) FROM model_registry_v2")
        row = cur.fetchone()
        last_seen = row[0] if row else None
        if not last_seen:
            echo("model_registry", "empty - run `atlas models refresh`", ok=False)
        else:
            # last_seen is stored as an ISO-8601 string (model_registry.py's
            # datetime.now(timezone.utc).isoformat()), never a numeric epoch.
            try:
                seen_at = datetime.fromisoformat(last_seen)
                age_seconds = (datetime.now(timezone.utc) - seen_at).total_seconds()
            except (TypeError, ValueError):
                age_seconds = None
            if age_seconds is not None and age_seconds > 86400:
                echo(
                    "model_registry",
                    f"stale ({int(age_seconds // 3600)}h old) - run `atlas models refresh`",
                    ok=False,
                )
            else:
                echo("model_registry", "fresh", ok=True)
    except Exception as exc:  # noqa: BLE001
        echo("model_registry", f"error - {exc}", ok=False)

    # 7. Provider — configured / live (credential-less) / mock. Never echo the
    # resolved api_key value. Informational only — never fails the overall run.
    # Uses provider_service.active_status so credential-less modes (claude_code,
    # freellmapi) report "live", not a false "mock" (P3).
    if cfg is None:
        # all_ok already False from the config check above; this branch is purely
        # informational. ok=False (not the bare-string default) so --json's
        # per-key shape stays {"status": str, "ok": bool} for every key.
        echo("provider", "skipped (config invalid)", ok=False)
    else:
        try:
            from atlas_runtime import provider_service

            st = provider_service.active_status(cfg)
            if st["credentials_present"]:
                echo("provider", "configured", ok=True)
            elif not st["mock_mode"]:
                echo("provider", f"live ({st['auth_mode']})", ok=True)
            else:
                echo("provider", "mock", ok=True)
        except Exception as exc:  # noqa: BLE001
            echo("provider", f"error - {exc}", ok=False)

    # 8. Claude-Code runtime — SDK + local `claude` CLI presence (P3). Reuses the
    # canonical provider_service check; informational, never fails the run.
    try:
        from atlas_runtime import provider_service

        cc = provider_service.claude_code_status()
        if cc["available"]:
            echo("claude_code", "ok", ok=True)
        else:
            echo("claude_code", f"unavailable - {cc['detail']}", ok=False)
    except Exception as exc:  # noqa: BLE001
        echo("claude_code", f"error - {exc}", ok=False)

    if json_output:
        typer.echo(json.dumps(report))

    if not all_ok:
        raise typer.Exit(1)
