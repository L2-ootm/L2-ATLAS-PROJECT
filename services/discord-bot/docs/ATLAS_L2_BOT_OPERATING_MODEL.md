# ATLAS / L2 BOT Operating Model

**Date:** 2026-05-27  
**Status:** Design baseline for implementation

## Core Correction

ATLAS is the active operator and intelligence layer.

L2 BOT is the Discord/server tooling substrate used by ATLAS to act inside Discord infrastructure.

L2 BOT is not the strategic gateway and does not own sensitive reasoning. It exposes controlled tools for server operations: messaging, embeds, channel management, role management, server structure reads, and future managed actions.

## Framework Direction

The initial L2 BOT framing as one Discord process is not enough for ATLAS operations.

L2 BOT should evolve into an operations framework comparable in completeness to the GSD framework: defined folders, documented capabilities, reusable scripts, configs, project-local skills, and explicit tool contracts.

The Discord bot process remains one runtime surface, but ATLAS does not need to boot the bot for every operation. ATLAS can use scripts, direct Discord REST calls, local project functions, and future MCP-style tools through the configured environment.

Target structure:

```text
L2-BOT/
  bot/                    # Discord bot runtime, cogs, API bridge, existing tools
  scripts/                # ATLAS-runnable operational scripts
  configs/                # Non-secret capability and policy config
  tools/                  # ATLAS-facing tool wrappers and contracts
  skills/                 # Project-local operational skills
  ephemeral/              # Generated temporary artifacts, ignored and cleaned
  docs/                   # Architecture, policies, operating model
  tests/                  # Policy, scripts, API, and tool-contract tests
```

Secrets remain in `.env` or the host secret store. Config files must not contain tokens.

## Runtime Shape

```text
Discord or OpenClaw message
  -> ATLAS receives instruction
  -> ATLAS classifies intent, user scope, channel context, and risk
  -> ATLAS decides whether L2 BOT tooling is required
  -> ATLAS chooses the lightest safe surface: script, REST call, local function, bot API, or live bot runtime
  -> L2 BOT tooling executes approved Discord/server capability
  -> ATLAS reports result through the active channel
```

Messaging to users may happen through OpenClaw gateway channel capabilities when the active runtime supports it.

Discord server management should happen through L2 BOT tooling.

Booting the live Discord bot is only required for gateway-dependent behavior, event listeners, cogs, slash-command sync, or websocket state. It is not required for direct REST reads, server inventory probes, static tool execution, or local artifact generation.

## Responsibility Split

| Layer | Responsibility |
| --- | --- |
| ATLAS | Intent classification, reasoning, policy decisions, response strategy, sensitive access control |
| OpenClaw gateway | Active conversation transport and normal message delivery when available |
| L2 BOT | Discord operational framework: embeds, server reads, channel/role changes, scripts, tool wrappers, audit-visible actions |
| Discord | Server state, channel permissions, user roles, message transport |

## Access Policy Baseline

File and information access is controlled by ATLAS context and user scope, not by raw Discord permissions alone.

Initial scope model:

| Scope | Meaning | Local file access |
| --- | --- | --- |
| `founder` | Davi / DAVID L2 | Full operator access subject to explicit safety rules |
| `cofounder` | Arturo / Hawk L2 | Approved project and operational files when context supports it |
| `admin` | Trusted server administrator | Server management only; no broad PC access |
| `member` | Regular server member | Public/helpful context only |
| `unknown` | Unmapped user | Public answers only |

When uncertain, ATLAS must deny sensitive file access or ask for founder confirmation.

## L2 BOT Capability Surface

Current capabilities already present in the project:

- Read guilds through `bot/api.py`
- Read channels and structure through `GET /guilds/{guild_id}/channels` and `GET /guilds/{guild_id}/structure`
- Send embed messages through `POST /channels/{channel_id}/messages`
- Manage channels through bot API channel endpoints
- Manage roles through bot API role endpoints
- Use the existing agent tool registry and executor for Discord actions

Target ATLAS-facing capabilities:

- `discord.server.read_structure`
- `discord.channel.read`
- `discord.message.send`
- `discord.embed.send`
- `discord.channel.manage`
- `discord.role.manage`
- `discord.permissions.manage`
- `discord.audit.read`
- `artifact.ephemeral.create`
- `artifact.ephemeral.send`
- `artifact.ephemeral.cleanup`

Capability surfaces should be callable in three modes:

| Mode | Use case |
| --- | --- |
| `script` | One-shot ATLAS operations using `.env` and Discord REST without booting the bot |
| `local_function` | Reuse internal Python functions/classes directly in tests and automation |
| `runtime_api` | Use `bot/api.py` or live bot state when gateway context is required |

## MCP-Like Direction

The first version should be MCP-like in structure before becoming a formal MCP server.

The immediate goal is a stable tool contract that ATLAS can reason over:

```json
{
  "tool": "discord.server.read_structure",
  "actor": {
    "discord_user_id": "string",
    "scope": "founder|cofounder|admin|member|unknown"
  },
  "context": {
    "guild_id": "string",
    "channel_id": "string"
  },
  "arguments": {}
}
```

Formal MCP transport can be added after the authorization and tool contracts are stable.

## Ephemeral Artifacts

Generated files, reports, PDFs, exports, and temporary assets should be created inside an ephemeral workspace.

Rules:

- Use a dedicated ephemeral directory.
- Use unique request IDs for generated artifacts.
- Send artifacts only after scope validation.
- Delete artifacts after delivery or expiry.
- Never store secrets in generated artifacts.
- Log create/send/cleanup events.

## Development Sequence

1. Add an ATLAS operator skill for this project.
2. Add non-boot operational scripts for server inventory and connection probes.
3. Define identity and scope policy.
4. Define capability contracts around existing L2 BOT API/tooling.
5. Add a minimal server-info fetch path for ATLAS use.
6. Add audit logging for ATLAS-triggered actions.
7. Add ephemeral artifact lifecycle.
8. Add formal MCP server only after the above is stable.

## Non-Negotiables

- L2 BOT does not decide sensitive PC/file access by itself.
- Discord administrator permission is not equal to local machine trust.
- ATLAS must see actor, guild, channel, requested capability, and resource before sensitive actions.
- Destructive Discord actions require explicit policy approval and audit trail.
- Local file delivery requires scope validation.
