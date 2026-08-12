"""MCP server registry — ATLAS-owned, projected onto the foundation.

Modules declare the MCP servers they want (`capabilities.mcp`) and operators add
their own; both land in one SQLite registry (`mcp_servers`, migration 0034).
Enabled rows are projected into the foundation's `mcp_servers` config map at run
start, stamped `managed_by: atlas`, exactly as `function_router.apply_autoconfig()`
projects auxiliary model slots.

Why a registry instead of writing Hermes config directly:

  - **Deactivating a module must retract its servers.** Projection reads the
    live registry joined against active modules, so switching a module off stops
    its MCP process from being offered on the next run — without editing, and
    then having to un-edit, someone else's config file.
  - **D-001.** The foundation is used as a library, never edited by hand. ATLAS
    writes only entries it stamped; a hand-authored operator server is left
    exactly as found, and is never imported into the ATLAS registry either, so
    ownership is unambiguous in both directions.
  - **Secrets stay out of the database.** `env` values hold `${VAR}` references.
    They are resolved from the process environment at projection time; an
    unresolvable reference disables the server with a readable reason instead of
    launching a process that will fail obscurely.

Everything here is best-effort at the run boundary: an MCP projection failure
must never fail a run.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

MANAGED_MARKER = "atlas"
_ENV_REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class McpError(ValueError):
    """Unknown server, invalid declaration, or an unresolvable env reference."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _row_to_server(row: sqlite3.Row | tuple, cols: list[str]) -> dict[str, Any]:
    server = dict(zip(cols, row))
    for key, default in (("args_json", "[]"), ("env_json", "{}")):
        try:
            server[key.removesuffix("_json")] = json.loads(server.get(key) or default)
        except json.JSONDecodeError:
            server[key.removesuffix("_json")] = json.loads(default)
        server.pop(key, None)
    server["enabled"] = bool(server.get("enabled"))
    return server


def list_servers(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every registered server, ordered by name."""
    cursor = conn.execute("SELECT * FROM mcp_servers ORDER BY name ASC")
    cols = [d[0] for d in cursor.description]
    return [_row_to_server(row, cols) for row in cursor]


def get_server(conn: sqlite3.Connection, name: str) -> Optional[dict[str, Any]]:
    cursor = conn.execute("SELECT * FROM mcp_servers WHERE name=?", (name,))
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    return None if row is None else _row_to_server(row, cols)


def upsert_server(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    name: str,
    transport: str = "stdio",
    command: str = "",
    args: Optional[list[str]] = None,
    env: Optional[dict[str, str]] = None,
    url: str = "",
    description: str = "",
    module_id: str = "",
    source: str = "operator",
    enabled: Optional[bool] = None,
) -> dict[str, Any]:
    """Register or update a server. `enabled=None` preserves the current state.

    Preserving enablement is what makes `sync_module_servers()` safe to run on
    every module sync: a manifest can change its command without silently
    re-enabling a server the operator turned off.
    """
    if not _NAME_RE.match(name or ""):
        raise McpError(f"invalid mcp server name {name!r}")
    if transport not in ("stdio", "http"):
        raise McpError(f"unsupported transport {transport!r}")
    if transport == "stdio" and not command:
        raise McpError(f"stdio server {name!r} needs a command")
    if transport == "http" and not url:
        raise McpError(f"http server {name!r} needs a url")

    existing = get_server(conn, name)
    if existing and existing.get("managed_by") != MANAGED_MARKER:
        raise McpError(f"server {name!r} is not ATLAS-managed")
    resolved_enabled = existing["enabled"] if (existing and enabled is None) else bool(enabled)
    now = _now()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO mcp_servers(name, module_id, transport, command, args_json,"
                " env_json, url, description, enabled, managed_by, source, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(name) DO UPDATE SET"
                " module_id=excluded.module_id, transport=excluded.transport,"
                " command=excluded.command, args_json=excluded.args_json,"
                " env_json=excluded.env_json, url=excluded.url,"
                " description=excluded.description, enabled=excluded.enabled,"
                " source=excluded.source, updated_at=excluded.updated_at",
                (
                    name, module_id, transport, command,
                    json.dumps(list(args or [])), json.dumps(dict(env or {})),
                    url, description, int(resolved_enabled), MANAGED_MARKER, source,
                    now, now,
                ),
            )
    updated = get_server(conn, name)
    assert updated is not None  # just wrote it
    return updated


def set_enabled(
    conn: sqlite3.Connection, lock: threading.Lock, *, name: str, enabled: bool
) -> dict[str, Any]:
    """Enable/disable a server. Idempotent."""
    if get_server(conn, name) is None:
        raise McpError(f"unknown mcp server: {name!r}")
    with lock:
        with conn:
            conn.execute(
                "UPDATE mcp_servers SET enabled=?, updated_at=?,"
                " last_status=CASE WHEN ?=0 THEN 'disabled' ELSE 'unknown' END"
                " WHERE name=?",
                (int(enabled), _now(), int(enabled), name),
            )
    server = get_server(conn, name)
    assert server is not None
    return server


def remove_server(conn: sqlite3.Connection, lock: threading.Lock, *, name: str) -> bool:
    """Delete a registry row. Module-declared servers come back on the next sync."""
    with lock:
        with conn:
            cursor = conn.execute("DELETE FROM mcp_servers WHERE name=?", (name,))
    return cursor.rowcount > 0


def sync_module_servers(
    conn: sqlite3.Connection, lock: threading.Lock
) -> dict[str, Any]:
    """Register MCP declarations from ACTIVE modules. Returns a summary.

    A module's first appearance honors its `enabled` flag (normally false —
    installing a module must not start talking to a third party); afterwards the
    operator's choice wins. Rows whose module went inactive are disabled rather
    than deleted, so re-activating the module restores the previous wiring.
    """
    from atlas_runtime import module_service  # noqa: PLC0415

    declared = module_service.module_mcp_declarations(conn)
    declared_names = {d["name"] for d in declared}
    registered: list[str] = []
    problems: list[str] = []
    for entry in declared:
        try:
            existing = get_server(conn, entry["name"])
            upsert_server(
                conn, lock,
                name=entry["name"],
                transport=entry.get("transport", "stdio"),
                command=entry.get("command", ""),
                args=entry.get("args") or [],
                env=entry.get("env") or {},
                url=entry.get("url", ""),
                description=entry.get("description", ""),
                module_id=entry.get("module_id", ""),
                source="module",
                enabled=None if existing else bool(entry.get("enabled")),
            )
            registered.append(entry["name"])
        except McpError as exc:
            problems.append(f"{entry.get('name', '?')}: {exc}")

    retired: list[str] = []
    rows = conn.execute(
        "SELECT name FROM mcp_servers WHERE source='module' AND enabled=1"
    ).fetchall()
    for (name,) in rows:
        if name not in declared_names:
            set_enabled(conn, lock, name=name, enabled=False)
            retired.append(name)
    return {"registered": sorted(registered), "retired": sorted(retired), "problems": problems}


def resolve_env(env: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Expand `${VAR}` references from the process env. Returns (resolved, missing)."""
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for key, raw in (env or {}).items():
        value = str(raw)
        for ref in _ENV_REF_RE.findall(value):
            actual = os.environ.get(ref)
            if actual is None:
                missing.append(ref)
                continue
            value = value.replace(f"${{{ref}}}", actual)
        resolved[key] = value
    return resolved, sorted(set(missing))


def foundation_server_config(server: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The Hermes-shaped config for one server, plus unresolved env references."""
    config: dict[str, Any] = {"managed_by": MANAGED_MARKER}
    if server.get("description"):
        config["description"] = server["description"]
    missing: list[str] = []
    if server.get("transport") == "http":
        config["url"] = server.get("url", "")
    else:
        config["command"] = server.get("command", "")
        if server.get("args"):
            config["args"] = list(server["args"])
        env, missing = resolve_env(server.get("env") or {})
        if env:
            config["env"] = env
    return config, missing


def _foundation_config_path() -> Optional[Path]:
    """The foundation's own config.yaml path, via its config module (D-001)."""
    from atlas_runtime import codex_auth  # noqa: PLC0415

    foundation = codex_auth._find_foundation()  # noqa: SLF001 — shared locator
    if foundation is None:
        return None
    import sys  # noqa: PLC0415

    path = str(foundation)
    if path not in sys.path:
        sys.path.insert(0, path)
    from hermes_cli import config as hermes_config  # noqa: PLC0415

    return Path(hermes_config.get_config_path())


def enabled_servers(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Enabled servers whose owning module (if any) is still active.

    The join is the retraction mechanism: no bookkeeping is needed when a module
    is deactivated mid-session, because the next projection simply stops seeing
    its servers.
    """
    from atlas_runtime import module_service  # noqa: PLC0415

    active = {m.get("id") for m in module_service.active_manifests(conn)}
    out: list[dict[str, Any]] = []
    for server in list_servers(conn):
        if not server["enabled"]:
            continue
        module_id = server.get("module_id") or ""
        if module_id and module_id not in active:
            continue
        out.append(server)
    return out


def apply_managed_servers(
    conn: Optional[sqlite3.Connection] = None,
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Project enabled servers into the foundation config. Never raises.

    Writes and removes only entries stamped `managed_by: atlas`. Servers with
    unresolvable `${VAR}` env references are skipped and reported — a half-wired
    server must not silently look enabled.
    """
    report: dict[str, Any] = {"applied": False, "written": [], "removed": [], "skipped": {}, "reason": ""}
    try:
        if conn is None:
            from atlas_runtime import db as atlas_db  # noqa: PLC0415

            conn = atlas_db.connect()
        servers = enabled_servers(conn)
        path = config_path or _foundation_config_path()
        if path is None:
            report["reason"] = "foundation config unavailable"
            return report
        import yaml  # noqa: PLC0415 — foundation dependency, present with it

        raw: dict[str, Any] = {}
        if path.exists():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                raw = loaded
        existing = raw.get("mcp_servers")
        if not isinstance(existing, dict):
            existing = {}

        desired: dict[str, dict[str, Any]] = {}
        for server in servers:
            config, missing = foundation_server_config(server)
            if missing:
                report["skipped"][server["name"]] = f"unset env: {', '.join(missing)}"
                continue
            desired[server["name"]] = config

        merged = dict(existing)
        changed = False
        for name, config in desired.items():
            current = existing.get(name)
            if isinstance(current, dict) and current.get("managed_by") != MANAGED_MARKER:
                # Operator-authored server of the same name: leave it alone and
                # say so, rather than fighting over the key every run.
                report["skipped"][name] = "operator-owned entry in the foundation config"
                continue
            if current != config:
                merged[name] = config
                changed = True
                report["written"].append(name)
        for name, current in list(existing.items()):
            if not isinstance(current, dict) or current.get("managed_by") != MANAGED_MARKER:
                continue
            if name not in desired:
                merged.pop(name, None)
                changed = True
                report["removed"].append(name)

        if changed:
            raw["mcp_servers"] = merged
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                yaml.safe_dump(raw, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
        report["applied"] = True
    except Exception as exc:  # noqa: BLE001 — projection must never fail a run
        report["reason"] = str(exc)
        logger.debug("mcp projection skipped: %s", exc)
    return report


def probe_server(
    conn: sqlite3.Connection, lock: threading.Lock, *, name: str, timeout: float = 20.0
) -> dict[str, Any]:
    """Connect to a server, list its tools, record the outcome. Never raises.

    Uses the foundation's own probe so ATLAS and Hermes agree on what
    "reachable" means.
    """
    server = get_server(conn, name)
    if server is None:
        raise McpError(f"unknown mcp server: {name!r}")
    config, missing = foundation_server_config(server)
    status = "error"
    tools: list[str] = []
    error = ""
    if missing:
        error = f"unset env: {', '.join(missing)}"
    else:
        try:
            from atlas_runtime import codex_auth  # noqa: PLC0415

            foundation = codex_auth._find_foundation()  # noqa: SLF001
            if foundation is None:
                raise RuntimeError("foundation not on path")
            import sys  # noqa: PLC0415

            if str(foundation) not in sys.path:
                sys.path.insert(0, str(foundation))
            from hermes_cli.mcp_config import _probe_single_server  # noqa: PLC0415

            probe = dict(config)
            probe.pop("managed_by", None)
            probe.pop("description", None)
            tools = [t[0] for t in _probe_single_server(name, probe, connect_timeout=timeout)]
            status = "ok"
        except Exception as exc:  # noqa: BLE001 — a probe failure is a result, not a crash
            error = str(exc)
    with lock:
        with conn:
            conn.execute(
                "UPDATE mcp_servers SET last_status=?, last_checked_at=?, last_error=?,"
                " updated_at=? WHERE name=?",
                (status, _now(), error[:500], _now(), name),
            )
    return {"name": name, "status": status, "tools": tools, "error": error}


__all__ = [
    "MANAGED_MARKER",
    "McpError",
    "apply_managed_servers",
    "enabled_servers",
    "foundation_server_config",
    "get_server",
    "list_servers",
    "probe_server",
    "remove_server",
    "resolve_env",
    "set_enabled",
    "sync_module_servers",
    "upsert_server",
]
