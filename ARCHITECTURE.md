# ATLAS Architecture

ATLAS is an AI operator cockpit and agent harness built on the Hermes Agent
foundation. It closes the loop between operator intent, agent execution, and
auditable outcomes.

## System Overview

```
Operator
  |
  v
Cockpit (React)  ──HTTP──>  Rust Gateway (:8484)  ──CLI dispatch──>  ATLAS Runtime (Python)
  |                            |                                        |
  v                            v                                        v
Dashboard, Missions,       Read-only REST +                        Agent execution,
Discord, Graph, Console    SSE streaming                           context assembly,
                                                                      audit trail,
                                                                      wiki, goals
```

## Layers

### 1. Foundation (`foundation/atlas-hermes/`)

Vendored Hermes Agent (MIT, Nous Research). Not modified directly — extensions
go through plugins, CLI dispatch, or vendored sidecars (D-001). Contains the
agent loop, tool system, messaging adapters, and TUI.

### 2. Runtime (`services/agent-runtime/`)

ATLAS-owned Python services:

- **Agent adapters** — `NativeAtlasAgent`, `ClaudeCodeAgent` (AgentRuntime ABC)
- **Context assembly** — `context_service` + `MemoryRouter` (budget-aware, 5 retrievers)
- **Goal hierarchy** — Goal/Task/Observation CRUD + tree assembly
- **Mission lifecycle** — create, run, complete, fail, retry, archive
- **Discord control** — sidecar lifecycle + read/write API client
- **Policy engine** — workspace boundary + tool allowlist
- **Audit service** — event emission with secret redaction
- **Config service** — `~/.atlas/config.yaml` with env:VAR secret references

### 3. Schemas (`packages/atlas-core/`)

Pydantic v2 frozen models — the single source of truth for domain contracts.
Models: Mission, Project, Focus, Goal, Task, Observation, Run, AuditEvent,
ToolCall, Artifact, Source, WikiPage, MemoryProvenance, DiscordApproval.

### 4. Gateway (`native/atlas-core-rs/`)

Rust REST gateway (axum + rusqlite). Read-only against SQLite; writes go through
the `atlas` CLI contract. Endpoints cover missions, runs, wiki, discord,
projects, focus, goals, operations, modules (incl. collection records), mcp,
scratchpad, cashflow, console, auth, provider, channels, tools,
surface-sessions, freellmapi, config, graph, and host.

### 5. Cockpit (`services/web-ui-react/`)

React 19 + TypeScript + Tailwind v4 operator dashboard. Routes: Dashboard,
Missions, Runs, Wiki, Discord, Graph, Console, Projects, System.

### 6. Sidecars

- **L2-BOT** (`services/discord-bot/`) — vendored Discord bot for read/write operations
- **Cashflow** (`services/cashflow/`) — optional financial tracking module

### 7. Modules (`modules/`, `<ATLAS home>/modules/`)

Manifest-declared optional capabilities, off by default. A module declares
commands, cockpit pages, doctrine (injected into runs while active), typed
record collections, workflows and MCP servers; ATLAS executes all of it — no
module code runs. The agent reaches every active module through one generic
`atlas_module` tool. Contract:
`docs/plans/2026-08-12-module-capabilities-v2-and-outreach-design.md`.

### 8. Scratchpad and disposables (`scratchpad_service.py`)

Durable agent working memory outside the transcript: plans, findings, drafts and
generated one-off tools, each with a TTL and a sweep. A run resuming a session
gets its open entries back in the brief (`ScratchpadRetriever`); a generated
script is written under `<ATLAS home>/scratch/tools`, run out of process through
the existing terminal tool and permission broker, and deleted with its row
unless pinned. Nothing generated is imported into the runtime.

Materializing a tool requires a `rationale` — what was searched, and why this is
disposable rather than durable. It is stored on the entry, shown in the cockpit,
and emitted as a permanent `self_extension` audit event, so the reasoning
outlives the disposable it justified. Contract:
`docs/plans/2026-08-12-atlas-self-extension-roadmap.md`.

## Data Flow

1. Operator sets a **Focus** (current working context) with priorities and goals
2. `assemble_context` builds a secret-redacted markdown brief from the open
   Scratchpad, Focus, Goals, Observations, Wiki, Skills, and Prior Failures
3. The brief feeds the agent runtime (native or Claude Code)
4. Agent executes, emitting audit events throughout
5. Run completion writes a **compounding Observation** that feeds the next context
6. The cockpit displays live state via the Rust gateway

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| D-001: No foundation edits | Preserve upstream upgrade path |
| D-002: Audit-first runtime | Every action is traceable |
| D-003: SQLite/WAL/FTS5 | Zero-config, single-file datastore |
| D-012: Pydantic v2 schemas | Type-safe, JSON-serializable contracts |
| D-022: Rust gateway, Python runtime | Performance for reads, flexibility for logic |
| D-023: React cockpit (strangler-fig) | Gradual migration from Svelte |

## Security Model

- Credentials stored as `env:VAR` references, never inline
- Secret redaction at every boundary (audit, context, gateway responses)
- Gateway binds to loopback only
- Discord writes are approval-gated and audited
- Workspace boundary enforcement on file operations
