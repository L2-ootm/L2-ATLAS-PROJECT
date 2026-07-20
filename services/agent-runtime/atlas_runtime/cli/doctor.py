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
import os
import shutil
import socket
import subprocess
import urllib.parse
from datetime import datetime, timezone

import typer
import yaml

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

    # 9. DB schema — detailed migration state (supplements check #1 with counts
    # and the latest version; never double-fails all_ok, check #1 already does).
    try:
        conn2 = db.connect()
        applied2 = db.applied_versions(conn2)
        migration_files = sorted(db.MIGRATIONS_DIR.glob("*.sql"))
        total = len(migration_files)
        applied_count = len(applied2)
        latest = migration_files[-1].name if migration_files else None
        pending_count = total - applied_count
        if pending_count == 0:
            echo("db_schema", f"{applied_count}/{total} applied, latest={latest}", ok=True)
        else:
            pending_names = [f.name for f in migration_files if f.name not in applied2]
            echo(
                "db_schema",
                f"{applied_count}/{total} applied, pending={pending_count} ({', '.join(pending_names)})",
                ok=False,
            )
    except Exception as exc:  # noqa: BLE001
        echo("db_schema", f"error - {exc}", ok=False)

    # 10. Config schema version/revision — informational; check #2 already
    # fails the run on an unparseable or unsupported config.
    try:
        config_path = config_service.default_config_path()
        if config_path.is_file():
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                schema_ver = raw.get("schema_version", config_service.CONFIG_SCHEMA_VERSION)
                revision = raw.get("revision", 0)
                ver_ok = isinstance(schema_ver, int) and 1 <= schema_ver <= config_service.CONFIG_SCHEMA_VERSION
                echo(
                    "config_schema",
                    f"v{schema_ver} rev={revision} (supported 1..{config_service.CONFIG_SCHEMA_VERSION})",
                    ok=ver_ok,
                )
            else:
                echo("config_schema", "non-object config file", ok=False)
        else:
            echo("config_schema", "no config file (using defaults)", ok=True)
    except Exception as exc:  # noqa: BLE001
        echo("config_schema", f"error - {exc}", ok=False)

    # 11. Gateway process + port — beyond the HTTP-only check #3: PID
    # liveness and port binding, so "down" and "wedged behind a dead PID with
    # something else on the port" are distinguishable. Fails all_ok only on
    # that specific inconsistent state; check #3 already covers plain "down".
    try:
        from atlas_runtime import gateway_control

        pid_file = gateway_control.PID_FILE
        pid_alive = False
        pid_info = "no pid file"
        if pid_file.is_file():
            try:
                pid = int(pid_file.read_text(encoding="utf-8").strip())
                if os.name == "nt":
                    tasklist = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                        capture_output=True, timeout=5,
                    )
                    pid_alive = str(pid) in (tasklist.stdout or b"").decode("utf-8", errors="replace")
                else:
                    os.kill(pid, 0)
                    pid_alive = True
                pid_info = f"pid={pid}, alive={pid_alive}"
            except (ValueError, OSError):
                pid_info = "pid file unreadable or invalid"

        port_ok = False
        port_info = "port not reachable"
        try:
            parsed = urllib.parse.urlparse(gateway_control.GATEWAY_URL)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 8484
            with socket.create_connection((host, port), timeout=1):
                port_ok = True
                port_info = f"{host}:{port} listening"
        except OSError:
            pass

        inconsistent = pid_alive and not port_ok
        echo("gateway_process", f"{pid_info}, {port_info}", ok=not inconsistent)
    except Exception as exc:  # noqa: BLE001
        echo("gateway_process", f"error - {exc}", ok=False)

    # 12. Toolchain — Python and Node.js must be on PATH (D-022 routes through
    # both); Rust/cargo is optional (only needed to rebuild the gateway).
    try:
        toolchain_info: dict[str, str] = {}
        for tool_name, cmd in (("python3", "python3"), ("python", "python"), ("node", "node"), ("cargo", "cargo")):
            found = shutil.which(cmd)
            if not found:
                continue
            try:
                probe = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=5)
                toolchain_info[tool_name] = probe.stdout.strip() if probe.returncode == 0 else f"found at {found}"
            except Exception:  # noqa: BLE001
                toolchain_info[tool_name] = f"found at {found}"

        python_ok = bool(toolchain_info.get("python") or toolchain_info.get("python3"))
        node_ok = bool(toolchain_info.get("node"))
        parts = [f"{name}={value}" for name, value in toolchain_info.items()]
        missing = [name for name, ok in (("python", python_ok), ("node", node_ok)) if not ok]

        if missing:
            echo("toolchain", f"missing: {', '.join(missing)} ({'; '.join(parts)})", ok=False)
            all_ok = False
        else:
            echo("toolchain", "; ".join(parts), ok=True)
    except Exception as exc:  # noqa: BLE001
        echo("toolchain", f"error - {exc}", ok=False)

    # 13. RTK — optional but recommended for 60-90% token savings on shell commands.
    try:
        rtk_disabled = os.environ.get("ATLAS_RTK_DISABLED", "").strip().lower() in {"1", "true", "yes"}
        rtk_found = shutil.which("rtk") is not None
        if rtk_disabled:
            echo("rtk", "disabled (ATLAS_RTK_DISABLED=1)", ok=True)
        elif rtk_found:
            try:
                probe = subprocess.run(["rtk", "--version"], capture_output=True, text=True, timeout=5)
                version_str = probe.stdout.strip().split("\n")[0] if probe.returncode == 0 else "found"
                echo("rtk", f"{version_str} (60-90% token savings)", ok=True)
            except Exception:  # noqa: BLE001
                echo("rtk", "found (version unknown)", ok=True)
        else:
            echo("rtk", "not found (optional — install for 60-90% token savings)", ok=True)
    except Exception as exc:  # noqa: BLE001
        echo("rtk", f"error - {exc}", ok=True)

    # 14. Version — the runtime version the npm launcher materialized and
    # handed off to us (ATLAS_RUNTIME_VERSION, set by launcher.js). Purely
    # informational context; unset means doctor was invoked directly (dev).
    runtime_version = os.environ.get("ATLAS_RUNTIME_VERSION", "").strip()
    echo("version", runtime_version or "unknown (invoked outside the npm launcher)", ok=True)

    if json_output:
        typer.echo(json.dumps(report))

    if not all_ok:
        raise typer.Exit(1)
