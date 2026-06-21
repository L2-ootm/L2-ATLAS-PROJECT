"""Discord sidecar control — start/stop/status the vendored L2-BOT discord.py
bot (services/discord-bot) so the operator can run the Discord surface from the
cockpit.

Mirrors cashflow_control.py: detached spawn + PID/state file + HTTP health probe.
The bot boots its own aiohttp API on http://localhost:8081 together with the
Discord gateway (services/discord-bot/bot/main.py), exposing /health, /guilds,
and /guilds/{id}/structure. ATLAS treats it as a sidecar (D-001: foundation
untouched); read data flows through the `atlas discord` CLI over that API.

The bot runs on its OWN interpreter/venv (discord.py, langchain, chromadb) — NOT
the ATLAS runtime venv — resolved by bot_python(). start() does NOT block on the
gateway handshake; it returns once spawned and the UI polls status.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import urllib.request

# discord_control.py -> atlas_runtime -> agent-runtime -> services ; /discord-bot
DISCORD_DIR = pathlib.Path(
    os.environ.get("ATLAS_DISCORD_DIR")
    or pathlib.Path(__file__).resolve().parents[2] / "discord-bot"
)
DISCORD_URL = os.environ.get("ATLAS_DISCORD_BOT_URL", "http://localhost:8081")
STATE_FILE = pathlib.Path.home() / ".atlas" / "discord-bot.json"


def _read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def bot_python() -> str:
    """Resolve the interpreter for the vendored bot.

    Order: ATLAS_DISCORD_PYTHON override -> the bot's own .venv -> bare `python`.
    The bot needs discord.py/langchain/chromadb, which live in its venv, not the
    ATLAS runtime venv.
    """
    env = os.environ.get("ATLAS_DISCORD_PYTHON", "").strip()
    if env:
        return env
    if os.name == "nt":
        venv = DISCORD_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        venv = DISCORD_DIR / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else "python"


def _token_fingerprint(token: str | None) -> str | None:
    """A non-reversible 12-hex fingerprint of a bot token (never the token itself)."""
    token = (token or "").strip()
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12] if token else None


def _bot_token() -> str | None:
    """The vendored bot's DISCORD_BOT_TOKEN from services/discord-bot/.env (best-effort)."""
    env_path = DISCORD_DIR / ".env"
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DISCORD_BOT_TOKEN") and "=" in line:
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        return None
    return None


def _foundation_discord_token() -> str | None:
    """The foundation messaging gateway's Discord token from ~/.hermes/config.yaml
    (best-effort; absent on most installs)."""
    cfg = pathlib.Path.home() / ".hermes" / "config.yaml"
    try:
        import yaml  # lazy; only needed for the coexistence check

        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    # Walk channels.discord.* looking for a token-bearing value, tolerant of layout.
    try:
        node = data.get("channels", {}).get("discord", {})
        for key in ("token", "bot_token", "api_key"):
            val = node.get(key)
            if isinstance(val, str) and val and not val.startswith("env:"):
                return val
    except Exception:
        return None
    return None


def coexistence_warning() -> str | None:
    """Non-fatal warning when the vendored sidecar and the foundation messaging
    gateway are configured against the SAME bot token (duplicate Discord gateway
    connections would disconnect one). Returns None when it can't tell — it never
    blocks startup and never logs the raw token (only a fingerprint comparison)."""
    a = _token_fingerprint(_bot_token())
    b = _token_fingerprint(_foundation_discord_token())
    if a and b and a == b:
        return (
            "warning: the vendored Discord sidecar and the foundation messaging "
            "gateway share a bot token — running both will disconnect one. Use a "
            "separate bot token, or do not start the foundation Discord adapter."
        )
    return None


def _health_payload(timeout: float = 1.0) -> dict | None:
    """Return the /health body, or None when the sidecar is unreachable."""
    try:
        with urllib.request.urlopen(f"{DISCORD_URL}/health", timeout=timeout) as resp:
            if getattr(resp, "status", resp.getcode()) >= 500:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def health_ok(timeout: float = 1.0) -> bool:
    return _health_payload(timeout) is not None


def status() -> dict:
    """Serializable status: {running, pid, ready, guild_count}."""
    payload = _health_payload()
    pid = _read_state().get("pid")
    if payload is None:
        return {"running": False, "pid": None, "ready": False, "guild_count": 0}
    return {
        "running": True,
        "pid": pid if isinstance(pid, int) else None,
        "ready": bool(payload.get("ready")),
        "guild_count": int(payload.get("guild_count") or 0),
    }


def start(poll_seconds: float = 0.0) -> tuple[bool, str]:
    """Spawn the vendored Discord bot detached; track its PID. Idempotent.

    Returns once spawned (the Discord gateway handshake can take seconds); the UI
    polls status. The bot reads its own services/discord-bot/.env via load_dotenv
    (cwd-based), so credentials stay in that file.
    """
    if health_ok():
        return True, "discord bot already running"
    if not DISCORD_DIR.exists():
        return False, f"discord bot not found at {DISCORD_DIR}"
    if not (DISCORD_DIR / "bot" / "main.py").exists():
        return False, f"discord bot entry missing: {DISCORD_DIR / 'bot' / 'main.py'}"

    python = bot_python()
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        )
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        [python, "-m", "bot.main"],
        cwd=str(DISCORD_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
        **kwargs,
    )
    _write_state({"pid": proc.pid})
    message = f"discord bot starting (pid {proc.pid}); {DISCORD_URL} shortly"
    warning = coexistence_warning()
    if warning:
        message = f"{message} — {warning}"
    return True, message


def stop() -> tuple[bool, str]:
    """Stop a Discord bot started by this primitive (via its state file).

    Idempotent: a bot not tracked here is already in the desired state.
    """
    pid = _read_state().get("pid")
    if not pid:
        return True, "discord bot not running"
    try:
        if os.name == "nt":
            # /T kills the child tree (the python process and any workers).
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        else:
            os.kill(int(pid), 15)
    finally:
        state = _read_state()
        state.pop("pid", None)
        _write_state(state)
    return True, f"stopped (pid {pid})"
