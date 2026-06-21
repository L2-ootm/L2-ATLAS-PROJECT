"""
ATLAS non-boot Discord connection probe.

Uses the configured Discord bot token from .env to query Discord REST directly.
This does not start the Discord gateway bot, sync slash commands, or load cogs.
It prints only operational metadata and never prints secrets.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


DISCORD_API = "https://discord.com/api/v10"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def discord_get(path: str, token: str):
    request = urllib.request.Request(
        f"{DISCORD_API}{path}",
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": "L2-BOT-ATLAS-Probe/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"error": body}
        return exc.code, payload


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")

    token = os.getenv("DISCORD_BOT_TOKEN")
    guild_id = os.getenv("DISCORD_GUILD_ID")

    if not token:
        print("DISCORD_TOKEN=missing")
        return 2

    status, bot_user = discord_get("/users/@me", token)
    if status != 200:
        print("CONNECTION=failed")
        print(f"STATUS={status}")
        print(json.dumps(bot_user, ensure_ascii=True))
        return 1

    print("CONNECTION=ok")
    print(f"BOT_ID={bot_user.get('id')}")
    print(f"BOT_USERNAME={bot_user.get('username')}")

    if not guild_id:
        status, guilds = discord_get("/users/@me/guilds", token)
        if status != 200:
            print("GUILDS_FETCH=failed")
            print(f"STATUS={status}")
            print(json.dumps(guilds, ensure_ascii=True))
            return 1

        print("GUILDS_FETCH=ok")
        print(f"GUILD_COUNT={len(guilds)}")
        for guild in guilds[:10]:
            print(f"GUILD={guild.get('id')}|{guild.get('name')}")
        return 0

    status, guild = discord_get(f"/guilds/{guild_id}?with_counts=true", token)
    if status != 200:
        print("GUILD_FETCH=failed")
        print(f"STATUS={status}")
        print(json.dumps(guild, ensure_ascii=True))
        return 1

    print("GUILD_FETCH=ok")
    print(f"GUILD_ID={guild.get('id')}")
    print(f"GUILD_NAME={guild.get('name')}")
    print(f"APPROX_MEMBER_COUNT={guild.get('approximate_member_count')}")
    print(f"APPROX_PRESENCE_COUNT={guild.get('approximate_presence_count')}")

    status, channels = discord_get(f"/guilds/{guild_id}/channels", token)
    if status == 200:
        print("CHANNELS_FETCH=ok")
        print(f"CHANNEL_COUNT={len(channels)}")
    else:
        print("CHANNELS_FETCH=failed")
        print(f"STATUS={status}")
        print(json.dumps(channels, ensure_ascii=True))

    status, roles = discord_get(f"/guilds/{guild_id}/roles", token)
    if status == 200:
        print("ROLES_FETCH=ok")
        print(f"ROLE_COUNT={len(roles)}")
    else:
        print("ROLES_FETCH=failed")
        print(f"STATUS={status}")
        print(json.dumps(roles, ensure_ascii=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
