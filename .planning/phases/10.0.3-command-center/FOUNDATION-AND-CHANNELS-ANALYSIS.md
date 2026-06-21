# ATLAS Foundation & Channel Integration Analysis

**Date:** 2026-06-19
**Framing:** The Hermes foundation IS the ATLAS foundation. Rebranded via DIV-F-005 (`atlas-agent`, `atlas-harness`). The divergence from Hermes is minimal: quarantined skills, audit plugin shim, branded entry points, custom skin. Everything else — 50+ tools, 28 providers, 8 memory providers, 19 messaging platforms, context compression, credential pool, tool registry, plugin system — IS ATLAS's infrastructure.

---

## Part 1: Foundation Integration Status

### What Works

**Audit bridge** — The `atlas_audit` plugin registers 6 hooks with the ATLAS harness plugin system. Every runtime event (API call, tool call, subagent stop, approval) flows through `audit_service.emit()` into SQLite. Thread-safe, fail-open, tested. This is the observation layer that makes everything auditable.

**Branded entry points** — `atlas-agent` → `hermes_cli.main:main`, `atlas-harness` → `run_agent:main`. Same code, ATLAS branding. Working.

**Tool registry** — Auto-discovery, TTL-cached check_fn, MCP dynamic refresh. 50+ tools: file ops, terminal, web, browser, vision, code execution, delegation, memory, skills, todo, kanban, messaging, image/video gen, home assistant, computer use. All registered and callable.

**Provider layer** — 28 model provider plugins. OpenAI, Anthropic, Google/Gemini, Bedrock, Azure, DeepSeek, xAI, OpenRouter, Ollama, Copilot, Nous, HuggingFace, Novita, NVIDIA, Xiaomi, and more. Credential pool with multi-key rotation, cooldown, throttle detection. The provider layer IS ATLAS's AI router.

**Context compression** — Auto-summarization of middle turns when context approaches limit. StreamingContextScrubber for real-time sanitization. Works.

**Session persistence** — SQLite-backed session store with FTS5 search, reset policies, suspend/resume, pruning.

**Skill system** — 90+ built-in skills across 24 categories. Software development (debugging, TDD, planning, code review), GitHub (PR workflow, issues), research (arxiv, llm-wiki), creative (design, diagrams). Curator lifecycle, skills hub.

**Plugin system** — General hooks (pre/post tool, pre/post LLM, session start/end), memory-provider ABC, model-provider discovery, context-engine extension. The ATLAS audit plugin uses this successfully.

**Gateway** — Production-grade multi-platform messaging daemon. 22+ built-in adapters. Session management, delivery routing, streaming, restart drain, crash forensics.

### What's Disconnected

**NativeAtlasAgent** — The `execute()` method is a stub. It emits one audit event and returns "succeeded." It never creates an `AIAgent`, never calls `run_conversation()`, never runs the harness loop. The ATLAS harness IS the execution engine, but the `NativeAtlasAgent` doesn't use it.

The fix is not "invoke Hermes" — it's "use our own harness." The harness code is at `foundation/atlas-hermes/run_agent.py`. The `AIAgent` class is the ATLAS agent loop. `NativeAtlasAgent.execute()` should instantiate `AIAgent` with ATLAS config and run it.

**Console native mode** — Returns a canned "switch to Claude Code" message. Same gap as above — the harness exists but isn't wired through the console.

**Agent-runtime dependency** — `pyproject.toml` declares `atlas-core` and `typer` as deps but NOT the foundation. The foundation is a sibling install, not a declared dependency. This means `import run_agent` or `from run_agent import AIAgent` would work at runtime (same venv) but isn't enforced by the build system.

### What Needs Wiring

| Module | Current State | What Needs to Happen |
|--------|--------------|---------------------|
| **NativeAtlasAgent** | Stub (5 lines, does nothing) | Instantiate `AIAgent` with ATLAS config, run the harness loop, map response to `RunOutcome` |
| **Console native mode** | Canned response | Same as above — wire through the harness |
| **agent-runtime deps** | Foundation not declared | Add `[foundation]` optional extra pointing to the vendored package |
| **Config mapping** | No ATLAS→Hermes config bridge | Build `atlas_config_to_hermes()` that maps Focus, Mission, Project to AIAgent constructor params |

### The AIAgent Constructor (~60 params)

The harness accepts: credentials, routing (base_url, api_key, provider, api_mode), model selection, max_iterations, tool configuration (enabled/disabled toolsets), session context (session_id, user_id, chat_id, thread_id), callbacks (~12 types), budget management (iteration_budget, fallback_model, credential_pool), checkpoint management, platform metadata.

ATLAS needs to map:
- `credentials` → from `~/.atlas/auth.json` (the auth store)
- `provider/model` → from Focus.framework or model registry
- `session_id` → from run_id (audit trail linkage)
- `callbacks` → audit hook registration (already wired via plugin)
- `iteration_budget` → configurable per Focus
- `tools` → tool allowlist from policy engine

---

## Part 2: Channel Integration Status

### What Exists in the Foundation

22+ messaging platform adapters, all production-grade:

| Platform | Adapter LOC | Status | ATLAS Integration |
|----------|------------|--------|-------------------|
| **Discord** | 6,231 | Most tested platform (32+ test files) | Not exposed in cockpit |
| **Telegram** | ~2,000 | Built-in, streaming edits, voice, reactions | Not exposed in cockpit |
| **Slack** | ~1,500 | Built-in | Not exposed in cockpit |
| **WhatsApp** | ~1,000 | Node bridge | Not exposed in cockpit |
| **Signal** | ~800 | HTTP bridge | Not exposed in cockpit |
| **Matrix** | ~1,200 | Built-in | Not exposed in cockpit |
| **Email** | ~600 | IMAP/SMTP | Not exposed in cockpit |
| **SMS** | ~400 | Twilio | Not exposed in cockpit |
| **DingTalk** | ~800 | Built-in | Not exposed in cockpit |
| **WeCom** | ~1,000 | Built-in with crypto | Not exposed in cockpit |
| **Feishu/Lark** | ~1,200 | Built-in with comment rules | Not exposed in cockpit |
| **WeChat** | ~600 | Built-in | Not exposed in cockpit |
| **BlueBubbles** | ~500 | iMessage | Not exposed in cockpit |
| **QQ Bot** | ~800 | Built-in with chunked upload | Not exposed in cockpit |
| **Yuanbao** | ~1,000 | Built-in with media/stickers | Not exposed in cockpit |
| **Webhook** | ~400 | Generic | Not exposed in cockpit |
| **MS Graph** | ~500 | Microsoft Graph | Not exposed in cockpit |
| **API Server** | ~600 | HTTP API | Partially (gateway REST) |
| **HomeAssistant** | ~500 | Built-in | Not exposed in cockpit |

**Plugin platforms** (8 additional): Discord (also plugin), IRC, Teams, Google Chat, LINE, Mattermost, ntfy, SimpleX.

### What ATLAS Has for Channel Management

| CLI Command | What It Does | Limitation |
|-------------|-------------|------------|
| `atlas channels status` | Read-only inspection of config.yaml channels | Shows enabled/disabled + credential presence. No mutation. |
| `atlas gateway start` | Starts the Rust ATLAS gateway | This is the REST API gateway, NOT the messaging gateway |
| `atlas-agent gateway start` | Starts the Hermes messaging gateway | This IS the channel daemon. Branded but not exposed in cockpit |

### The Two Gateways

ATLAS has two distinct gateway processes:

1. **Rust ATLAS gateway** (`atlas-gateway` on port 8484) — REST API + SSE over SQLite. Serves the cockpit UI. No messaging channels. Read-only writes via CLI dispatch.

2. **Python messaging gateway** (`atlas-agent gateway`) — Multi-platform messaging daemon. Connects to Discord, Telegram, Slack, etc. Runs the ATLAS harness on incoming messages. Emits audit events.

They are independent processes. The Rust gateway does not manage the Python messaging gateway. The cockpit cannot start/stop/configure the messaging gateway.

---

## Part 3: L2 BOT Discord Management Suite

### Why Discord First

Discord is the most heavily tested adapter (6,231 LOC, 32+ tests). It supports: slash commands, threads, reactions, channel skill bindings, role-based auth, voice, DM policy, free-response channels. It's the natural first channel for an L2 management suite.

### What the Adapter Already Supports

| Feature | Implementation | Cockpit Exposure |
|---------|---------------|-----------------|
| Channel enable/disable | `config.yaml` boolean | **None** |
| Credential status | env var check | **None** |
| Per-channel allowed channels | config list | **None** |
| DM policy (allow/block/pairing) | config enum | **None** |
| Group policy | config enum | **None** |
| Require mention | config boolean | **None** |
| Free-response channels | config list | **None** |
| Channel skill bindings | config mapping | **None** |
| Channel prompt overrides | config text | **None** |
| Role-based auth | config mapping | **None** |
| Guild overview | Discord API | **None** |
| Channel list | Discord API | **None** |
| Thread management | Discord API | **None** |
| Slash command status | Discord API | **None** |
| Voice session monitoring | Discord API | **None** |
| Bot activity stats | audit_events | **None** |
| Message analytics | audit_events | **None** |
| Cost tracking | audit_events | **None** |

### Architecture for the Suite

```
┌──────────────────────────────────────────────────┐
│              COCKPIT (React)                      │
│                                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │ Channel    │  │ Discord    │  │ Bot        │  │
│  │ Config     │  │ Guild/Ch   │  │ Activity   │  │
│  │ Editor     │  │ Browser    │  │ Dashboard  │  │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  │
│        │               │               │          │
│  ┌─────▼───────────────▼───────────────▼──────┐  │
│  │         Gateway REST API (Rust)             │  │
│  │  GET/PUT /v1/channels/*                     │  │
│  │  GET /v1/discord/guilds                     │  │
│  │  GET /v1/discord/channels                   │  │
│  │  GET /v1/discord/stats                      │  │
│  └─────┬───────────────┬──────────────────────┘  │
│        │               │                         │
│  ┌─────▼──────┐  ┌─────▼──────────────────────┐  │
│  │ Config     │  │ Audit Events (SQLite)       │  │
│  │ .yaml read │  │ Bot activity, cost, errors  │  │
│  │ + write    │  │                              │  │
│  └─────┬──────┘  └────────────────────────────┘  │
│        │                                          │
│  ┌─────▼──────────────────────────────────────┐  │
│  │ Messaging Gateway (Python)                  │  │
│  │ atlas-agent gateway start                   │  │
│  │ 22+ platform adapters                       │  │
│  │ Discord adapter: 6,231 LOC                  │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### New Gateway Endpoints Needed

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/channels` | GET | List all configured channels with enabled/status/credential-presence |
| `/v1/channels/{name}` | GET | Read channel config |
| `/v1/channels/{name}` | PUT | Update channel config |
| `/v1/channels/{name}/toggle` | POST | Enable/disable channel |
| `/v1/discord/guilds` | GET | List Discord guilds (from Discord API) |
| `/v1/discord/guilds/{id}/channels` | GET | List channels in guild |
| `/v1/discord/guilds/{id}/roles` | GET | List roles in guild |
| `/v1/discord/stats` | GET | Bot activity stats from audit_events |
| `/v1/discord/stats/cost` | GET | Token cost breakdown |
| `/v1/gateway/messaging/start` | POST | Start the messaging gateway |
| `/v1/gateway/messaging/stop` | POST | Stop the messaging gateway |
| `/v1/gateway/messaging/status` | GET | Messaging gateway health |

### Implementation Priority

| WP | What | Effort | Impact |
|----|------|--------|--------|
| WP-A | Channel config read/write in Rust gateway (config.yaml) | 2 days | Foundation for all UI |
| WP-B | `atlas channels enable/disable` CLI commands | 1 day | CLI management |
| WP-C | System page — Channels tab with enable/disable toggles | 2 days | Basic cockpit management |
| WP-D | System page — Provider config tab | 1 day | Provider management |
| WP-E | Discord guild/channel browser in cockpit | 3 days | Discord management |
| WP-F | Discord per-channel config editor | 2 days | Deep Discord management |
| WP-G | Bot activity dashboard (audit_events aggregation) | 2 days | Operational visibility |
| WP-H | Messaging gateway lifecycle in cockpit (start/stop/status) | 1 day | Gateway management |
| WP-I | `atlas setup` wizard | 3 days | First-run experience |

**Total: ~17 days** for the full channel management suite.

---

## Part 4: Setup Wizard

### What Hermes Has

`hermes setup` — 3,458 LOC interactive wizard with 5 sections:
1. Model & Provider
2. Terminal Backend
3. Agent Settings
4. Messaging Platforms
5. Tools

Config stored in `~/.hermes/config.yaml` + `~/.hermes/.env`.

### What ATLAS Needs

`atlas setup` — ATLAS-branded wizard that configures the complete system:

```
atlas setup

  ATLAS Setup Wizard
  ══════════════════

  1. AI Provider
     Select provider: [OpenRouter / Anthropic / OpenAI / Ollama / Custom]
     Enter API key: ****
     Select model: [gpt-4o / claude-sonnet-4 / ...]
     ✓ Provider configured

  2. Agent Runtime
     Select default runtime: [native (ATLAS harness) / claude_code]
     Iteration budget: [50 / 90 / custom]
     ✓ Runtime configured

  3. Database
     Database path: [~/.atlas/atlas.db]
     Running migrations... ✓

  4. Gateway
     Rust gateway binary: [auto-detect / manual path]
     Messaging gateway: [enable / skip]
     ✓ Gateway configured

  5. Messaging (optional)
     Enable Discord? [y/N]
     Discord bot token: ****
     Enable Telegram? [y/N]
     Telegram bot token: ****
     ✓ Channels configured

  6. Cockpit
     Web-UI port: [3000]
     Branding: [ATLAS / custom]
     ✓ Cockpit configured

  Setup complete. Run `atlas gateway start` to launch.
```

### Config Architecture

```
~/.atlas/
  config.yaml          # Main config (providers, runtime, gateway, cockpit)
  auth.json            # API keys and tokens (encrypted, cross-process locked)
  atlas.db             # SQLite database
  gateway.pid          # Rust gateway PID file
  gateway-messaging.pid # Messaging gateway PID file
```

Separate from Hermes's `~/.hermes/` — ATLAS owns its own config space.

### Config Schema

```yaml
# ~/.atlas/config.yaml
provider:
  name: openrouter          # openrouter | anthropic | openai | ollama | custom
  api_key: env:OPENROUTER_API_KEY  # or direct value
  model: anthropic/claude-sonnet-4
  base_url: null            # custom endpoint

runtime:
  default_agent: native     # native | claude_code
  iteration_budget: 90
  compression: auto

gateway:
  rust_binary: auto         # auto-detect or explicit path
  rust_port: 8484
  messaging_enabled: true
  messaging_port: 8585

channels:
  discord:
    enabled: false
    token: env:DISCORD_BOT_TOKEN
    guilds: []              # empty = all guilds
    dm_policy: pairing      # allow | block | pairing
    require_mention: true
    free_response: []       # channels that don't need @mention
    skill_bindings: {}      # channel_id -> skill_pack
    channel_prompts: {}     # channel_id -> system prompt override
  telegram:
    enabled: false
    token: env:TELEGRAM_BOT_TOKEN
  slack:
    enabled: false
    token: env:SLACK_BOT_TOKEN
    app_token: env:SLACK_APP_TOKEN

cockpit:
  port: 3000
  branding: atlas

modules:
  cashflow: false
  wiki: true
  graph: true
```

---

## Part 5: System Page Redesign

### Current State

The System page shows:
- Gateway status (online/offline)
- Database status (ok/error)
- Module toggles (cashflow activate/deactivate)
- Offline start affordance (Tauri shell detection)

### Proposed Tabs

| Tab | Content | Priority |
|-----|---------|----------|
| **Overview** | Gateway status, database status, agent runtime status, messaging gateway status, system info (OS, Python version, Rust binary version) | P0 |
| **Providers** | Current provider, model, API key status (masked), model registry list, test connection button | P0 |
| **Channels** | All configured channels, enable/disable toggles, credential status, per-channel settings editor | P1 |
| **Modules** | Activatable modules with toggle, module health status | P0 (existing) |
| **Logs** | Recent audit events (table with filtering), error log, gateway logs | P1 |
| **Setup** | First-run wizard, configuration editor (YAML), import/export config | P2 |
| **Discord** | Guild browser, channel list, role list, per-channel config, bot activity stats, voice sessions | P2 |
| **About** | Version info, attribution (Hermes foundation), divergence log, license | P3 |

### Component Structure

```
src/routes/System.tsx (redesigned)
  ├── SystemOverview.tsx     — status cards, system info
  ├── SystemProviders.tsx    — provider config, model registry
  ├── SystemChannels.tsx     — channel list, enable/disable, settings
  ├── SystemModules.tsx      — module toggles (existing, moved)
  ├── SystemLogs.tsx         — audit event viewer, filters
  ├── SystemSetup.tsx        — wizard, config editor
  ├── SystemDiscord.tsx      — Discord-specific management
  └── SystemAbout.tsx        — version, attribution
```

---

## Part 6: Wiring Map

### How Everything Connects

```
┌─────────────────────────────────────────────────────────────┐
│                    COCKPIT (React)                           │
│                                                             │
│  System Page tabs: Overview | Providers | Channels |        │
│                     Modules | Logs | Setup | Discord | About │
│                                                             │
│  Command Center: Focus → Launch Run → Activity Feed          │
│  Graph: Knowledge graph with lightning, auto-orbit           │
│  Console: Chat workbench with tool cards                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────┐
│               RUST ATLAS GATEWAY (port 8484)                │
│                                                             │
│  REST API: missions, runs, wiki, projects, modules,         │
│            graph, models, console, cashflow, focus           │
│                                                             │
│  NEW: /v1/channels/*, /v1/discord/*,                        │
│       /v1/gateway/messaging/*                                │
│                                                             │
│  Reads: SQLite (audit, missions, runs, wiki, etc)           │
│         Config.yaml (channels, providers)                    │
│  Writes: CLI dispatch (atlas focus create, etc)             │
└──────────┬──────────────────────────────┬───────────────────┘
           │ CLI dispatch                 │ Config read/write
┌──────────▼──────────────┐  ┌────────────▼──────────────────┐
│  ATLAS CLI (Python)     │  │  CONFIG (~/.atlas/config.yaml)│
│                         │  │                                │
│  atlas mission create   │  │  provider: openrouter          │
│  atlas run exec         │  │  runtime: native               │
│  atlas focus create     │  │  channels:                     │
│  atlas wiki search      │  │    discord:                    │
│  atlas graph build      │  │      enabled: true             │
│  atlas db init          │  │      token: env:DISCORD_TOKEN  │
│  atlas channels status  │  │    telegram:                   │
│  atlas setup            │  │      enabled: false             │
│  atlas foundation status│  │                                │
└──────────┬──────────────┘  └────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│              ATLAS RUNTIME (Python)                          │
│                                                             │
│  Services:                                                  │
│    focus_service     — operator intent (singleton)          │
│    context_service   — memory router + brief assembly       │
│    run_executor      — async execution + stop conditions    │
│    audit_service     — event emission + redaction           │
│    mission_service   — mission lifecycle                    │
│    handoff_service   — HANDOFF.md generation (P0)           │
│    entropy_service   — code/docs cleanup (P1)               │
│                                                             │
│  Agent Runtimes:                                            │
│    NativeAtlasAgent  — ATLAS harness loop (WIRED: P0)      │
│    ClaudeCodeAgent   — Claude Code SDK (WORKING)            │
│                                                             │
│  Plugins:                                                   │
│    atlas_audit       — 6 hooks → AuditEvent bus             │
└──────────┬──────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│           ATLAS HARNESS (foundation/atlas-hermes/)           │
│                                                             │
│  THIS IS THE ATLAS AGENT LOOP. Rebranded from Hermes.       │
│  Not an external dependency — it IS the foundation.          │
│                                                             │
│  AIAgent:                                                   │
│    run_conversation() — tool-calling loop with retry,       │
│                         fallback, compression, streaming     │
│    ~60 constructor params (credentials, routing, tools,     │
│                            session, callbacks, budget)      │
│                                                             │
│  50+ tools: file, terminal, web, browser, vision, code,     │
│             delegation, memory, skills, todo, kanban,       │
│             messaging, image/video gen, MCP, computer use   │
│                                                             │
│  28 providers: OpenAI, Anthropic, Google, Bedrock, Azure,   │
│                DeepSeek, xAI, OpenRouter, Ollama, etc       │
│                                                             │
│  Plugin system: hooks, memory ABC, model discovery,         │
│                 context engine, image gen                    │
│                                                             │
│  Gateway: 22+ messaging platforms                            │
│    Discord (6,231 LOC, 32+ tests)                           │
│    Telegram, Slack, WhatsApp, Signal, Matrix, Email, SMS    │
│    DingTalk, WeCom, Feishu, WeChat, QQBot, Yuanbao         │
│    Webhook, API Server, MS Graph, HomeAssistant             │
│                                                             │
│  Context compression, credential pool, session persistence  │
└─────────────────────────────────────────────────────────────┘
```

### The Key Insight

The foundation IS ATLAS. There's no "invoking Hermes" — there's using our own harness. The `NativeAtlasAgent` should call `AIAgent.run_conversation()` the same way `ClaudeCodeAgent` calls the Claude SDK. The harness is the execution engine. The ATLAS runtime wraps it with missions, runs, audit, context, and handoff.

---

## Part 7: Implementation Priority

### P0 (This Sprint) — Core Wiring

| What | Files | Days | Unlocks |
|------|-------|------|---------|
| Wire NativeAtlasAgent to ATLAS harness | `agents/native.py` | 2 | Native execution path works |
| Config mapping (ATLAS → harness params) | `config_service.py` (NEW) | 1 | Provider/runtime/channel config |
| Setup wizard (basic) | `cli/setup.py` (NEW) | 2 | First-run experience |
| System page Overview tab | `System.tsx` (MODIFY) | 1 | Basic status visibility |

### P1 (Next Sprint) — Channel Management

| What | Files | Days | Unlocks |
|------|-------|------|---------|
| Channel config read/write in gateway | `lib.rs` (MODIFY) | 2 | Cockpit can manage channels |
| `atlas channels enable/disable` | `cli/channels.py` (MODIFY) | 1 | CLI channel management |
| System page Channels tab | `SystemChannels.tsx` (NEW) | 2 | Cockpit channel management |
| System page Providers tab | `SystemProviders.tsx` (NEW) | 1 | Provider management |
| Messaging gateway lifecycle | `gateway_control.py` (EXTEND) | 1 | Start/stop messaging from cockpit |

### P2 (Following Sprint) — Discord Suite

| What | Files | Days | Unlocks |
|------|-------|------|---------|
| Discord guild/channel browser | `SystemDiscord.tsx` (NEW) | 3 | Discord management |
| Discord per-channel config | `SystemDiscord.tsx` (EXTEND) | 2 | Deep Discord config |
| Bot activity dashboard | `SystemLogs.tsx` (NEW) | 2 | Operational visibility |
| Setup wizard (full) | `cli/setup.py` (EXTEND) | 1 | Complete first-run |

### P3 (Month 2) — Polish

| What | Files | Days | Unlocks |
|------|-------|------|---------|
| System page Logs tab | `SystemLogs.tsx` (NEW) | 2 | Audit trail viewer |
| System page Setup tab | `SystemSetup.tsx` (NEW) | 2 | Config editor |
| System page About tab | `SystemAbout.tsx` (NEW) | 1 | Attribution |
| Config import/export | `cli/config.py` (NEW) | 1 | Backup/restore |

---

## Summary

| Dimension | Status | Priority |
|-----------|--------|----------|
| **Foundation is ATLAS** | Rebranded, 6 divergences, working audit bridge | Done |
| **Native agent execution** | Stub — needs harness wiring | P0 |
| **Channel adapters** | 22+ exist, all production-grade | Exists |
| **Channel cockpit UI** | Nothing built | P1 |
| **Discord management** | Adapter exists (6K LOC), no cockpit surface | P2 |
| **Setup wizard** | Hermes has one, ATLAS doesn't | P0 |
| **System page redesign** | Basic status only, needs 8 tabs | P0-P3 |

The foundation is massive and production-grade. The gaps are wiring (native agent → harness), UI (channel management in cockpit), and experience (setup wizard). All solvable — the infrastructure exists, the connections don't.
