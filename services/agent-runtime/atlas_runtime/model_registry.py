"""ATLAS model registry — live model discovery for the AI router (D-017).

Keeps a local SQLite table (`model_registry`) in sync with the model list
exposed by an OpenAI-compatible gateway (FreeLLMAPI sidecar per D-015, or any
endpoint serving GET <base_url>/models). New models appearing upstream are
recorded automatically on refresh; models that disappear are deactivated, not
deleted, so routing history stays resolvable.

Design constraints:
- D-022: this module is in the LLM-adapter Python bucket (it feeds the Python
  agent loop's provider selection). The Rust gateway reads the same SQLite
  table directly for /models serving — no logic duplication.
- No new dependencies: HTTP via urllib (loopback sidecar only per spike
  hardening — never point this at an untrusted host).
- conn/lock injected by callers, same as audit_service/mission_service.
- Schema creation is idempotent (CREATE TABLE IF NOT EXISTS) and mirrored in
  infra/migrations/0003_model_registry.sql.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_GATEWAY_URL = "http://127.0.0.1:3001/v1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_registry (
    model_id    TEXT PRIMARY KEY,
    provider    TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1
)
"""

_PROVIDER_SCHEMA = """
CREATE TABLE IF NOT EXISTS provider_registry (
    provider_id       TEXT PRIMARY KEY,
    display_name      TEXT,
    auth_type         TEXT,
    default_base_url  TEXT,
    api_modes_json    TEXT NOT NULL DEFAULT '{}',
    source            TEXT,
    status            TEXT,
    last_checked      TEXT,
    last_error        TEXT
)
"""

_MODEL_V2_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_registry_v2 (
    model_id        TEXT NOT NULL,
    provider_id     TEXT NOT NULL,
    source          TEXT NOT NULL,
    api_mode        TEXT,
    status          TEXT,
    auth_status     TEXT,
    context_window  INTEGER,
    metadata_json   TEXT NOT NULL DEFAULT '{}',
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    deactivated_at  TEXT,
    PRIMARY KEY(model_id, provider_id, source)
)
"""


@dataclass(frozen=True)
class RefreshResult:
    """Outcome of one registry refresh against a gateway."""

    source: str
    added: list[str]
    retained: list[str]
    deactivated: list[str]

    @property
    def total_active(self) -> int:
        return len(self.added) + len(self.retained)


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create legacy and v2 registry tables if absent."""
    conn.execute(_SCHEMA)
    conn.execute(_PROVIDER_SCHEMA)
    conn.execute(_MODEL_V2_SCHEMA)


# Deterministic baseline registry for fresh installs / offline use. This REPLACES
# the old untracked one-off that seeded these same rows into ~/.atlas/atlas.db with
# no code provenance. source="seed" keeps them distinct from gateway-discovered
# rows, and refresh()'s source-scoped deactivation never touches them, so they act
# as an offline fallback when no LLM gateway is configured.
SEED_SOURCE = "seed"
DEFAULT_SEED_MODELS: tuple[tuple[str, str], ...] = (
    ("claude-fable-5", "anthropic"),
    ("claude-sonnet-4-6", "anthropic"),
    ("gemini-2.5-pro", "google"),
)


def seed_default_models(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    models: tuple[tuple[str, str], ...] = DEFAULT_SEED_MODELS,
) -> list[str]:
    """Insert the baseline default models if absent (idempotent). Returns ids inserted.

    Keyed on the model_id PRIMARY KEY via INSERT OR IGNORE: an existing row (seeded
    OR gateway-discovered) is never overwritten, so re-running is a no-op and a real
    `refresh` of the same id always wins. Called from `atlas db init` / `atlas setup`.
    """
    now = datetime.now(timezone.utc).isoformat()
    inserted: list[str] = []
    with lock:
        with conn:
            ensure_schema(conn)
            for model_id, provider in models:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO model_registry "
                    "(model_id, provider, source, first_seen, last_seen, active) "
                    "VALUES (?,?,?,?,?,1)",
                    (model_id, provider, SEED_SOURCE, now, now),
                )
                if cur.rowcount:
                    inserted.append(model_id)
    logger.info("model_registry.seed_default_models: inserted=%d", len(inserted))
    return inserted


def gateway_base_url() -> str:
    """Resolve the gateway base URL (env ATLAS_LLM_GATEWAY_URL, else default)."""
    return os.environ.get("ATLAS_LLM_GATEWAY_URL", DEFAULT_GATEWAY_URL).rstrip("/")


def fetch_gateway_models(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 10.0,
) -> list[dict]:
    """GET <base_url>/models and return the OpenAI-format model entries.

    Args:
        base_url: Gateway base URL ending in /v1. Defaults to env/loopback.
        api_key: Bearer token; defaults to env ATLAS_LLM_GATEWAY_KEY.
        timeout: Socket timeout in seconds.

    Returns:
        List of model dicts (each has at least "id"; "owned_by" if provided).

    Raises:
        URLError/HTTPError on network failure, ValueError on malformed body.
    """
    url = (base_url or gateway_base_url()).rstrip("/") + "/models"
    key = api_key if api_key is not None else os.environ.get("ATLAS_LLM_GATEWAY_KEY", "")
    req = urllib.request.Request(url)
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        raise ValueError(f"unexpected /models response shape from {url}")
    return [m for m in data if isinstance(m, dict) and m.get("id")]


def refresh(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    source: Optional[str] = None,
    fetcher: Callable[[], list[dict]] = fetch_gateway_models,
    auth_status_resolver: Callable[[str], str] | None = None,
) -> RefreshResult:
    """Sync the registry with the gateway's current model list.

    - Models seen for the first time are inserted (first_seen = now).
    - Models already known get last_seen bumped and active = 1 (reactivation
      covers models that vanished and came back upstream).
    - Active models for this source missing from the response get active = 0.

    Args:
        conn: SQLite connection.
        lock: Lock protecting the shared connection.
        source: Label for where these models come from (defaults to the
            resolved gateway URL). Deactivation is scoped to this source so
            multiple gateways can share the table.
        fetcher: Injectable model-list fetcher (tests pass a fake).

    Returns:
        RefreshResult with added/retained/deactivated model id lists.
    """
    src = source or gateway_base_url()
    models = fetcher()
    now = datetime.now(timezone.utc).isoformat()
    incoming = {
        str(model["id"]): {
            "provider_id": str(model.get("owned_by") or "unknown"),
            "api_mode": (
                str(model["api_mode"])
                if model.get("api_mode") is not None
                else None
            ),
            "context_window": int(model.get("context_window") or 0),
        }
        for model in models
    }

    with lock:
        with conn:
            ensure_schema(conn)
            known = {
                row[0]
                for row in conn.execute(
                    "SELECT model_id FROM model_registry WHERE source=?", (src,)
                )
            }
            added = sorted(set(incoming) - known)
            retained = sorted(set(incoming) & known)
            active_known = {
                row[0]
                for row in conn.execute(
                    "SELECT model_id FROM model_registry WHERE source=? AND active=1",
                    (src,),
                )
            }
            deactivated = sorted(active_known - set(incoming))
            for model_id in added:
                conn.execute(
                    "INSERT OR IGNORE INTO model_registry VALUES (?,?,?,?,?,1)",
                    (
                        model_id,
                        incoming[model_id]["provider_id"],
                        src,
                        now,
                        now,
                    ),
                )
            for model_id in retained:
                conn.execute(
                    "UPDATE model_registry SET last_seen=?, active=1, provider=? "
                    "WHERE model_id=? AND source=?",
                    (
                        now,
                        incoming[model_id]["provider_id"],
                        model_id,
                        src,
                    ),
                )
            for model_id in deactivated:
                conn.execute(
                    "UPDATE model_registry SET active=0 WHERE model_id=? AND source=?",
                    (model_id, src),
                )

            incoming_v2_keys: set[tuple[str, str]] = set()
            for model_id, details in incoming.items():
                provider_id = str(details["provider_id"])
                incoming_v2_keys.add((model_id, provider_id))
                auth_status = "unknown"
                if auth_status_resolver is not None:
                    try:
                        resolved = auth_status_resolver(provider_id)
                    except Exception:  # status projection must not break discovery
                        resolved = "unknown"
                    if resolved in {
                        "available",
                        "auth_present",
                        "needs_api_key",
                        "needs_login",
                        "offline",
                        "rate_limited",
                        "expired",
                        "unknown",
                    }:
                        auth_status = resolved
                conn.execute(
                    "INSERT INTO provider_registry "
                    "(provider_id,display_name,auth_type,default_base_url,"
                    "api_modes_json,source,status,last_checked,last_error) "
                    "VALUES (?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(provider_id) DO UPDATE SET "
                    "display_name=excluded.display_name,"
                    "source=excluded.source,status=excluded.status,"
                    "last_checked=excluded.last_checked,last_error=NULL",
                    (
                        provider_id,
                        provider_id,
                        None,
                        None,
                        "{}",
                        src,
                        "available",
                        now,
                        None,
                    ),
                )
                conn.execute(
                    "INSERT INTO model_registry_v2 "
                    "(model_id,provider_id,source,api_mode,status,auth_status,"
                    "context_window,metadata_json,first_seen,last_seen,deactivated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,NULL) "
                    "ON CONFLICT(model_id,provider_id,source) DO UPDATE SET "
                    "api_mode=excluded.api_mode,status=excluded.status,"
                    "auth_status=excluded.auth_status,"
                    "context_window=excluded.context_window,"
                    "metadata_json=excluded.metadata_json,"
                    "last_seen=excluded.last_seen,deactivated_at=NULL",
                    (
                        model_id,
                        provider_id,
                        src,
                        details["api_mode"],
                        "available",
                        auth_status,
                        details["context_window"],
                        "{}",
                        now,
                        now,
                    ),
                )

            active_v2 = conn.execute(
                "SELECT model_id,provider_id FROM model_registry_v2 "
                "WHERE source=? AND deactivated_at IS NULL",
                (src,),
            ).fetchall()
            for model_id, provider_id in active_v2:
                if (model_id, provider_id) not in incoming_v2_keys:
                    conn.execute(
                        "UPDATE model_registry_v2 "
                        "SET status='offline',last_seen=?,deactivated_at=? "
                        "WHERE model_id=? AND provider_id=? AND source=?",
                        (now, now, model_id, provider_id, src),
                    )

    logger.info(
        "model_registry.refresh: source=%s added=%d retained=%d deactivated=%d",
        src, len(added), len(retained), len(deactivated),
    )
    return RefreshResult(source=src, added=added, retained=retained, deactivated=deactivated)


def list_models(
    conn: sqlite3.Connection,
    *,
    active_only: bool = True,
) -> list[dict]:
    """Return registry rows as dicts, newest first."""
    ensure_schema(conn)
    where = "WHERE active=1" if active_only else ""
    cursor = conn.execute(
        f"SELECT model_id, provider, source, first_seen, last_seen, active "
        f"FROM model_registry {where} ORDER BY first_seen DESC, model_id"
    )
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor]


def list_models_v2(
    conn: sqlite3.Connection,
    *,
    active_only: bool = True,
) -> list[dict]:
    """Return v2 composite registry rows without credential material."""
    ensure_schema(conn)
    where = "WHERE deactivated_at IS NULL" if active_only else ""
    cursor = conn.execute(
        "SELECT model_id,provider_id,source,api_mode,status,auth_status,"
        "context_window,metadata_json,first_seen,last_seen,deactivated_at "
        f"FROM model_registry_v2 {where} "
        "ORDER BY first_seen DESC,model_id,provider_id,source"
    )
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor]


def list_models_control_plane(
    conn: sqlite3.Connection,
    *,
    active_only: bool = True,
) -> list[dict]:
    """Prefer v2 rows; fall back to a v2-shaped legacy projection."""
    rows = list_models_v2(conn, active_only=active_only)
    if rows:
        return rows
    return [
        {
            "model_id": row["model_id"],
            "provider_id": row["provider"],
            "source": row["source"],
            "api_mode": None,
            "status": "available" if row["active"] else "offline",
            "auth_status": "unknown",
            "context_window": 0,
            "metadata_json": "{}",
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
            "deactivated_at": None if row["active"] else row["last_seen"],
        }
        for row in list_models(conn, active_only=active_only)
    ]
