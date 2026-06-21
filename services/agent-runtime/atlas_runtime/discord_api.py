"""Thin HTTP client for the vendored Discord sidecar's read + write API.

Runs in the ATLAS runtime venv using only the stdlib (urllib) — no discord deps.
Targets the bot's loopback API (services/discord-bot/bot/api.py) on
ATLAS_DISCORD_BOT_URL (default http://localhost:8081). Used by the `atlas discord`
commands, which the Rust gateway dispatches (D-022: external calls stay in
Python; the gateway only dispatches the CLI).

Write wrappers (create/edit/delete channel & role, send embed, set permissions)
back the gated approval flow (discord_service): they are only ever called from
`discord_service.approve()`, after an operator has approved a pending request.
Each forwards a `reason` string the sidecar threads into Discord's audit log.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

DISCORD_URL = os.environ.get("ATLAS_DISCORD_BOT_URL", "http://localhost:8081")


class DiscordSidecarError(RuntimeError):
    """The sidecar was unreachable or returned an error (surfaced cleanly)."""


def _request(method: str, path: str, data: Optional[dict] = None, timeout: float = 10.0) -> Any:
    url = f"{DISCORD_URL}{path}"
    body: Optional[bytes] = None
    headers = {}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        # The sidecar returns a JSON {error: ...} body on 4xx/5xx — surface it.
        detail = ""
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            detail = payload.get("error", "") if isinstance(payload, dict) else ""
        except Exception:  # noqa: BLE001 — best-effort detail extraction
            detail = ""
        suffix = f": {detail}" if detail else ""
        raise DiscordSidecarError(f"discord sidecar {exc.code} for {path}{suffix}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise DiscordSidecarError(
            f"discord sidecar unreachable at {DISCORD_URL}; run `atlas discord start`"
        ) from exc
    except ValueError as exc:  # bad JSON
        raise DiscordSidecarError(f"discord sidecar returned invalid JSON for {path}") from exc


def _get(path: str, timeout: float = 5.0) -> Any:
    return _request("GET", path, timeout=timeout)


# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------


def list_guilds() -> list[dict]:
    """GET /guilds -> [{id, name}]."""
    data = _get("/guilds")
    return data if isinstance(data, list) else []


def get_structure(guild_id: str) -> dict:
    """GET /guilds/{id}/structure -> {guild, categories[], uncategorized[], roles[]}."""
    return _get(f"/guilds/{guild_id}/structure")


# ---------------------------------------------------------------------------
# Write API (approval-gated; called only by discord_service.approve)
# ---------------------------------------------------------------------------


def create_channel(
    guild_id: str,
    *,
    name: str,
    type: str = "text",
    category_id: Optional[str] = None,
    topic: str = "",
    reason: str = "Dashboard",
) -> dict:
    """POST /guilds/{id}/channels -> {id, name}."""
    return _request(
        "POST",
        f"/guilds/{guild_id}/channels",
        {"name": name, "type": type, "category_id": category_id, "topic": topic, "reason": reason},
    )


def edit_channel(
    guild_id: str,
    channel_id: str,
    *,
    name: Optional[str] = None,
    category_id: Optional[str] = None,
    topic: Optional[str] = None,
    reason: str = "Dashboard",
) -> dict:
    """PATCH /guilds/{id}/channels/{channel_id} -> {success}."""
    payload: dict = {"reason": reason}
    if name is not None:
        payload["name"] = name
    if category_id is not None:
        payload["category_id"] = category_id
    if topic is not None:
        payload["topic"] = topic
    return _request("PATCH", f"/guilds/{guild_id}/channels/{channel_id}", payload)


def delete_channel(guild_id: str, channel_id: str, *, reason: str = "Dashboard") -> dict:
    """DELETE /guilds/{id}/channels/{channel_id} -> {success}."""
    return _request(
        "DELETE", f"/guilds/{guild_id}/channels/{channel_id}", {"reason": reason}
    )


def create_role(
    guild_id: str,
    *,
    name: str,
    color_hex: str = "",
    hoist: bool = False,
    permissions: Optional[dict] = None,
    reason: str = "Dashboard",
) -> dict:
    """POST /guilds/{id}/roles -> {id, name}."""
    return _request(
        "POST",
        f"/guilds/{guild_id}/roles",
        {
            "name": name,
            "color_hex": color_hex,
            "hoist": hoist,
            "permissions": permissions or {},
            "reason": reason,
        },
    )


def edit_role(
    guild_id: str,
    role_id: str,
    *,
    name: Optional[str] = None,
    color_hex: Optional[str] = None,
    hoist: Optional[bool] = None,
    permissions: Optional[dict] = None,
    reason: str = "Dashboard",
) -> dict:
    """PATCH /guilds/{id}/roles/{role_id} -> {success}."""
    payload: dict = {"reason": reason}
    if name is not None:
        payload["name"] = name
    if color_hex is not None:
        payload["color_hex"] = color_hex
    if hoist is not None:
        payload["hoist"] = hoist
    if permissions is not None:
        payload["permissions"] = permissions
    return _request("PATCH", f"/guilds/{guild_id}/roles/{role_id}", payload)


def delete_role(guild_id: str, role_id: str, *, reason: str = "Dashboard") -> dict:
    """DELETE /guilds/{id}/roles/{role_id} -> {success}."""
    return _request("DELETE", f"/guilds/{guild_id}/roles/{role_id}", {"reason": reason})


def send_message(channel_id: str, *, embed: dict, reason: str = "Dashboard") -> dict:
    """POST /channels/{id}/messages -> {success}. `reason` is ATLAS-audit-only
    (Discord channel.send takes no audit reason)."""
    return _request(
        "POST", f"/channels/{channel_id}/messages", {"embed": embed, "reason": reason}
    )


def set_permissions(
    guild_id: str,
    channel_id: str,
    *,
    role_id: str,
    allow: Optional[list] = None,
    deny: Optional[list] = None,
    reason: str = "Dashboard",
) -> dict:
    """POST /guilds/{id}/channels/{channel_id}/permissions -> {success}."""
    return _request(
        "POST",
        f"/guilds/{guild_id}/channels/{channel_id}/permissions",
        {"role_id": role_id, "allow": allow or [], "deny": deny or [], "reason": reason},
    )
