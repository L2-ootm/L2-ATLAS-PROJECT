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
    """Create the model_registry table if it does not exist (idempotent)."""
    conn.execute(_SCHEMA)


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
    incoming = {m["id"]: str(m.get("owned_by", "")) for m in models}

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
                    "INSERT INTO model_registry VALUES (?,?,?,?,?,1)",
                    (model_id, incoming[model_id], src, now, now),
                )
            for model_id in retained:
                conn.execute(
                    "UPDATE model_registry SET last_seen=?, active=1, provider=? "
                    "WHERE model_id=? AND source=?",
                    (now, incoming[model_id], model_id, src),
                )
            for model_id in deactivated:
                conn.execute(
                    "UPDATE model_registry SET active=0 WHERE model_id=? AND source=?",
                    (model_id, src),
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
