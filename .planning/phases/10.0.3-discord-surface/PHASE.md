# 10.0.3 — Discord Surface (vendored L2-BOT sidecar)

> Status: **slice 1 DONE (read-only browser)** — 2026-06-21. Closes the channel-cockpit
> "Discord guild/channel browser" deferral.
> Owner concern: `services/discord-bot` (vendored), `services/agent-runtime` (control + CLI),
> `native/atlas-core-rs` (routes), `services/web-ui-react` (route). No foundation edits (D-001).

## Intent

The foundation Discord adapter runs passively on events and exposes **no guild/channel enumeration**,
so a cockpit Discord browser could not be built on it without editing the locked foundation (D-001).
`C:\Users\Davi\Desktop\Projects\L2-BOT` — a standalone discord.py bot that already serves a loopback
REST API (`/guilds`, `/guilds/{id}/structure`, `/roles`, …) and whose own operating model declares it
"the Discord/server tooling substrate used by ATLAS" — is the right substrate. This phase **vendors it
into the ATLAS tree as an ATLAS-controlled sidecar** (the `services/cashflow` pattern) and surfaces a
read-only Discord browser at a dedicated `/discord` cockpit route.

## Architecture

```
Cockpit /discord → Rust gateway /v1/discord/* → (dispatch_atlas) atlas discord CLI
   ├─ discord_control.py → spawn/stop services/discord-bot, ~/.atlas/discord-bot.json, /health probe
   └─ discord_api.py     → urllib GET http://localhost:8081/...  (stdlib; no discord deps)
services/discord-bot (vendored L2-BOT) → discord.py + aiohttp API :8081 → Discord
```

- **D-001**: the foundation Discord adapter is untouched; the surface is the vendored bot.
- **D-022**: the Rust gateway only dispatches the `atlas` CLI; the HTTP call to :8081 lives in Python.
- **Two interpreters**: the bot runs on its own `services/discord-bot/.venv`; the `atlas discord`
  read client runs in the ATLAS runtime venv (urllib only).

## Delivered (slice 1)

- **Vendored** `services/discord-bot/` (robocopy, excluding `chroma_db/`, `database.db`, `data/`,
  `scratch/`, caches, the bot's own planning dirs). Secrets/state gitignored (`.env`, `*.db`,
  `chroma_db/`, `data/`); secret gate verified (0 `.env`/`.db` tracked). Added `GET /health`
  (`{status, ready, guild_count}`) to the vendored `bot/api.py` for a clean readiness probe.
- **Lifecycle** `discord_control.py` (mirror `cashflow_control.py`): detached spawn of
  `<bot venv python> -m bot.main` with cwd=`services/discord-bot`, `~/.atlas/discord-bot.json` pid,
  `/health` probe, idempotent start/stop. Interpreter resolved via `ATLAS_DISCORD_PYTHON` → bot
  `.venv` → `python`; dir/url via `ATLAS_DISCORD_DIR`/`ATLAS_DISCORD_BOT_URL`.
- **Read client** `discord_api.py` (stdlib urllib): `list_guilds`, `get_structure`; typed
  `DiscordSidecarError` → clean "run `atlas discord start`" message.
- **CLI** `atlas discord start|status|stop|guilds|structure` (each `--json` for gateway dispatch).
- **Gateway** routes (dispatch the CLI): `GET /v1/discord/status`, `POST /v1/discord/{start,stop}`,
  `GET /v1/discord/guilds`, `GET /v1/discord/guilds/{id}/structure` (user `id` after `--`, `--json`
  before it).
- **Cockpit** `/discord` route (STRUCTURE pillar nav): sidecar status + Start/Stop, guild list →
  selected-guild structure (categories→channels with type glyphs + roles with color swatches);
  skeleton/empty/offline states.
- **Tests**: +12 Python (`test_discord_control.py`, `test_discord_cli.py`), +4 Rust route tests.

## Verification

- Suites: agent-runtime **182 passed** (1 known `claude_agent_sdk` env fail); `cargo test -p
  atlas-gateway` **68 passed**; web tsc/lint/build green.
- **End-to-end with real creds**: minimal bot venv (discord.py/aiohttp/aiosqlite/dotenv) →
  `atlas discord start` connected to Discord (ready, guild **"L2"**, 11 members) → `discord guilds`
  and `discord structure` returned live data (20 categories, real channel names, 18 roles) →
  `discord stop` cleanly killed the tree. (Full AI cogs need the complete `requirements.txt` incl.
  torch; not required for the browser surface.)

## Deferred (slice 2 — write/management, gated)

L2-BOT already exposes the endpoints; ATLAS write actions must be **approval-gated + audited** per the
operating-model non-negotiables: create/edit/delete channels & roles, send embeds, permission
overwrites. Also future: bot activity/stats dashboard, member/role assignment, MCP formalization.

## Coexistence note

Do not run the vendored L2-BOT and the foundation messaging gateway's Discord adapter against the
**same** bot token simultaneously (duplicate gateway connections). L2-BOT is the Discord browser/ops
runtime here; the foundation messaging gateway stays a separate concern (its own `~/.hermes` token).
