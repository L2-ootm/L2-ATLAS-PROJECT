"""Thin HTTP client for the vendored Discord sidecar's read API.

Runs in the ATLAS runtime venv using only the stdlib (urllib) — no discord deps.
Targets the bot's loopback API (services/discord-bot/bot/api.py) on
ATLAS_DISCORD_BOT_URL (default http://localhost:8081). Used by the `atlas discord`
read commands, which the Rust gateway dispatches (D-022: external calls stay in
Python; the gateway only dispatches the CLI).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DISCORD_URL = os.environ.get("ATLAS_DISCORD_BOT_URL", "http://localhost:8081")


class DiscordSidecarError(RuntimeError):
    """The sidecar was unreachable or returned an error (surfaced cleanly)."""


def _get(path: str, timeout: float = 5.0) -> Any:
    url = f"{DISCORD_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise DiscordSidecarError(f"discord sidecar {exc.code} for {path}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise DiscordSidecarError(
            f"discord sidecar unreachable at {DISCORD_URL}; run `atlas discord start`"
        ) from exc
    except ValueError as exc:  # bad JSON
        raise DiscordSidecarError(f"discord sidecar returned invalid JSON for {path}") from exc


def list_guilds() -> list[dict]:
    """GET /guilds -> [{id, name}]."""
    data = _get("/guilds")
    return data if isinstance(data, list) else []


def get_structure(guild_id: str) -> dict:
    """GET /guilds/{id}/structure -> {guild, categories[], uncategorized[], roles[]}."""
    return _get(f"/guilds/{guild_id}/structure")
