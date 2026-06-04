# L2 ATLAS on Hermes Agent — Implementation-Grade Architecture

**Bottom line up front:** Build ATLAS as a **layered extension of Hermes Agent's Python core via its supported plugin/hook/provider surfaces, plus a separate Node/TypeScript "ATLAS product plane"** that talks to Hermes through its three documented programmatic protocols (TUI-gateway JSON-RPC, the OpenAI-compatible `/v1` API server with its `/v1/runs/{id}/events` SSE stream, and ACP) — do **not** fork `run_agent.py`. This is achievable to ~90% in 30 days *because* Hermes already ships the hard parts (agent loop, tool registry, SQLite+FTS5 sessions, cron, delegation/subagents, multi-agent Kanban, 20+ provider routing, an Ink TUI, an embeddable web dashboard); ATLAS's job is the **domain layer** (Mission/Run/CRM/Wiki/Pulse schemas + policy/audit) and the **product layer** (a SvelteKit cockpit + an enhanced Ink CLI/TUI), not re-inventing the runtime.

## TL;DR

- **Hermes is a Python-core agent (84.6% Python, 11.8% TypeScript), not a TypeScript framework.** The agent loop is `AIAgent` in `run_agent.py`; the Ink/React TUI (`ui-tui/`) is a thin client over a Python `tui_gateway` JSON-RPC process. Any plan that assumed "extend a TS agent framework" must be discarded. ATLAS extends Hermes through its **plugin system** (`register(ctx)` with `pre_tool_call`/`post_tool_call`/`pre_llm_call`/`post_llm_call`/`on_session_start`/`on_session_end` hooks, `ctx.register_tool`, `ctx.register_cli_command`, dashboard tabs) and consumes it from the product plane over **HTTP+SSE / JSON-RPC**. Nous's own rule (Teknium, May 2026) — plugins must not modify core files — *is* the clean-architecture guardrail.
- **Stack decisions that survive scrutiny:** monorepo with **pnpm workspaces + Turborepo**; **SQLite (WAL) + FTS5 + `sqlite-vec`** as the ATLAS datastore (mirrors Hermes's own choice, no Postgres at small-team scale); **SvelteKit** for the cockpit (smaller bundles, higher RPS per VPS for a power-user dashboard); **SSE for live run/event streaming** (server→client only, the 95% case; matches Hermes's own `/v1/runs/{id}/events` SSE), HTTP POST for commands; **Ink** for the enhanced TUI (composes with Hermes's existing Ink TUI); and **Tauri 2 (Rust) reserved** for the future desktop sidecar (~30–50 MB idle, sub-0.5 s start vs Electron's 150–300 MB and 1–2 s) — never Electron.
- **30 days to 90% is realistic** only if the critical path holds: Wk1 = monorepo + ATLAS SQLite schema + a Hermes plugin emitting every tool/LLM/session event onto an event bus and persisting an immutable hash-chained JSONL+SQLite audit log; Wk2 = Mission engine + Model Router policy + Wiki/Knowledge runtime; Wk3 = SvelteKit cockpit (dashboard/missions/runs/audit/wiki/CRM) over SSE + enhanced Ink CLI; Wk4 = CRM/Pulse/Discord (L2-BOT) integration, stabilization, Windows+Linux packaging. Desktop sidecar, STT/TTS overlays, and ML contradiction detection are explicitly **day-31+**.

## Key Findings

1. **Hermes is large, fast-moving, production-real.** ~178k stars, ~30.4k forks, 10,351 commits, 16 releases, latest **v0.15.2 (`v2026.5.29.2`, May 29 2026)**, MIT, ~25,000-test pytest suite across ~1,250 files. The May 2026 "Velocity Release" (v0.15.0) cut `run_agent.py` from 16,083 → 3,821 lines across 14 `agent/*` modules and repeatedly shaved cold start (`hermes --version` 701 → 258 ms; Termux 2.9 → 0.8 s). It is a moving target — pin to a commit SHA and track upstream deliberately.
2. **Every extension point ATLAS needs already exists:** tool registry (`tools/registry.py`, import-time auto-discovery), 28 toolsets, delegation/subagents (`tools/delegate_tool.py`), cron (`cron/jobs.py`+`scheduler.py`, agent-native), Kanban multi-agent board (durable SQLite, swarm topology, per-task model overrides), memory-provider ABC, an observability plugin pattern (Langfuse: one span/turn, one generation/LLM call, one observation/tool call), and three integration protocols.
3. **Cleanest boundary is process-level:** Hermes core + the ATLAS Hermes-plugin run inside the Python process; ATLAS domain/product services run as a separate Node process; they communicate over JSON-RPC/HTTP+SSE plus a shared SQLite/JSONL audit substrate. This preserves upstream-mergeability, satisfies the no-core-edits rule, and lets the future Rust sidecar wrap the Node product plane as a Tauri sidecar.

---

# 1. Hermes Agent Architecture Deep Dive

### 1.1 What Hermes actually is (drop one assumption)
Hermes is **not** a TypeScript agent framework. Language split: **Python 84.6% / TypeScript 11.8% / TeX 0.9% / JS 0.8% / Shell 0.5%**. The core is `AIAgent` in `run_agent.py`; every surface (CLI, gateway, ACP, batch, OpenAI-compatible API server) constructs that single Python class. The TypeScript is the **Ink (React) TUI** in `ui-tui/`, a thin client speaking newline-delimited JSON-RPC over stdio to `tui_gateway/server.py`. The embedded `hermes dashboard` web chat is the *same* `hermes --tui` process surfaced via a POSIX-PTY WebSocket bridge (`hermes_cli/pty_bridge.py` + `@app.websocket("/api/pty")`) — which needs WSL on Windows.

**Consequence:** the "enhanced agent runtime on top of Hermes" is built in **Python** (a plugin); the "beautiful CLI/TUI" and "WebUI cockpit" are **TypeScript** talking over wire protocols. Embrace the polyglot split — it is the seam Nous designed.

### 1.2 Architecture map (verified against official docs)
```
┌──────────────── Entry Points (all construct the same AIAgent) ────────────────┐
│ CLI (cli.py)  Gateway (gateway/run.py)  ACP (acp_adapter/)                     │
│ Batch Runner  API Server (gateway/platforms/api_server.py)  Python Library    │
│ TUI (ui-tui/ ⇄ tui_gateway/server.py JSON-RPC)                               │
└───────────────────────────────┬───────────────────────────────────────────────┘
                                 ▼
┌──────────────────────── AIAgent (run_agent.py, ~3.8k LOC) ─────────────────────┐
│ prompt_builder.py (stable→context→volatile)  | runtime_provider.py (18+        │
│ context_compressor.py / prompt_caching.py     |  providers→api_mode+creds)     │
│ model_tools.py (discover, schema, dispatch, hooks) | 3 API modes: chat_compl., │
│ memory_manager.py + memory_provider.py (ABC)  |  codex_responses, anthropic    │
│ Synchronous loop: ThreadPoolExecutor up to 8 parallel tool workers             │
└───────────┬───────────────────────────────────────────────┬────────────────────┘
            ▼                                                 ▼
┌──────────────────────┐                       ┌──────────────────────────────────┐
│ Session storage      │                       │ Tool backends                     │
│ hermes_state.py      │                       │ tools/registry.py (70+ tools,     │
│ SQLite + FTS5        │                       │  28 toolsets, self-register)      │
│ lineage, atomic write│                       │ Terminal:6 (local,docker,ssh,     │
│ gateway/session.py   │                       │  modal,daytona,singularity)       │
└──────────────────────┘                       │ Browser:5  Web:4  MCP:dynamic     │
                                               └──────────────────────────────────┘
  cron/ (jobs.py+scheduler.py)   plugins/ (hooks,tools,providers,dashboard tabs)
  tools/delegate_tool.py (subagents)   plugins/kanban/ (multi-agent board)
```
Facts ATLAS depends on:
- **Tool registration is import-time + decentralized.** `tools/*.py` with top-level `registry.register(...)` auto-discovers, but a tool is exposed only if wired into a toolset in `toolsets.py`. Handlers **must return a JSON string**. ATLAS tools follow this from a plugin (`ctx.register_tool`), no core edits.
- **The hook system is the audit seam.** `pre/post_tool_call` fire from `model_tools.py`; `pre/post_llm_call` + `on_session_start/end` from `run_agent.py`. Only `pre_llm_call` has a meaningful return (inject context into the current turn's *user message*, never the system prompt — to preserve prompt caching).
- **Sessions = SQLite+FTS5** (`hermes_state.py`, `SessionDB`) with parent/child lineage, per-platform isolation, atomic writes; `session_search` rebuilt FTS5-only in v0.15.0 (~4,500× faster, free).
- **Delegation is synchronous, non-durable.** `delegate_task` spawns isolated subagents; parent blocks; `role="leaf"` (default, can't re-delegate) vs `role="orchestrator"` (bounded by `delegation.max_spawn_depth` default 2; `max_concurrent_children` default 3). For durable long work Nous directs you to **cron** or `terminal(background=True, notify_on_complete=True)`.
- **Cron jobs are first-class agent tasks** (JSON store; `"30m"`/`"every monday 9am"`/`"0 9 * * *"`/ISO; 3-min hard interrupt; `.tick.lock`; `skip_memory=True`).
- **Profiles** isolate everything via `HERMES_HOME`; all state paths must use `get_hermes_home()`.
- **Build:** Python via `uv`/`pyproject.toml` (PyPI lagged git: v0.14.0 source vs 0.13.0 PyPI as of May 18 2026 — install from git pinned to a SHA). Strict dependency-pinning policy (`>=floor,<next_major`; git deps by 40-char SHA) after the litellm compromise and the May 2026 "Mini Shai-Hulud" worm.

### 1.3 Preserve vs wrap/replace
| Subsystem | Verdict | Why |
|---|---|---|
| `AIAgent` loop, provider resolution, 3 API modes | **Preserve, never fork** | 25k-test coverage; cold-start tuned; fast upstream |
| Tool registry + toolsets + MCP | **Extend via plugin** | clean `ctx.register_tool`, auto-discovery |
| Hooks | **Build on** | sanctioned interception/audit seam |
| SQLite+FTS5 sessions | **Preserve; add `atlas.db` alongside** | don't pollute Hermes schema |
| Cron + Kanban | **Drive from ATLAS** | Pulse=cron; long missions=Kanban swarm |
| Delegation/subagents | **Wrap w/ cost tracking** | add token/cost in `post_llm_call` |
| Memory | **Wrap** | ATLAS Wiki superset; bridge via `pre_llm_call` |
| Ink TUI | **Extend, don't replace** | Nous: add panels, don't rebuild transcript |
| Embedded dashboard (PTY) | **Replace for cockpit** | PTY-over-WS needs WSL on Windows; use `/v1`+JSON-RPC |
| Provider plugins | **Reuse** | Tier-0 local = OpenAI-compatible endpoint |

---

# 2. ATLAS Enhancement Architecture (Layering, Schemas, Policy, Mission Engine)

### 2.1 Three-plane layering
```
┌─ PRODUCT PLANE (TS/Node) ───────────────────────────────────────────────────┐
│ cockpit (SvelteKit) · cli (Ink) · gateway (Node: SSE bus, REST, auth, audit) │
│   consumes Hermes via /v1 API (HTTP+SSE) + tui_gateway JSON-RPC              │
└──────────────────────────────┬───────────────────────────────────────────────┘
            HTTP+SSE / JSON-RPC / shared SQLite(read)
┌──────────────────────────────▼───────────────────────────────────────────────┐
│ DOMAIN PLANE (Python in-proc + TS services)                                   │
│ atlas-hermes-plugin (Py): hooks→bus, ATLAS tools, audit write                 │
│ atlas-core (TS): Mission engine, Model Router policy, Wiki, CRM, Pulse        │
│ atlas.db (SQLite WAL+FTS5+sqlite-vec) + audit/*.jsonl (immutable, hash-chained)│
└──────────────────────────────┬───────────────────────────────────────────────┘
            plugin register(ctx) / hooks / tools
┌──────────────────────────────▼───────────────────────────────────────────────┐
│ RUNTIME PLANE (Hermes, unmodified, pinned SHA)                                │
│ AIAgent·tools·sessions·cron·delegation·Kanban·routing·memory·MCP·API·TUI gw   │
└────────────────────────────────────────────────────────────────────────────────┘
```
- *Inside Hermes process:* only `atlas-hermes-plugin` (registers tools, subscribes all six hooks, forwards normalized events to bus+audit; never edits core).
- *Alongside (Node service):* `atlas-gateway` + `atlas-core`; owns `atlas.db`; drives Hermes via `/v1` (`POST /v1/runs` → SSE `/v1/runs/{id}/events` → `/v1/runs/{id}/approval`/`/stop`) and TUI-gateway JSON-RPC (`prompt.submit`, `session.*`, `approval.respond`, `command.dispatch`, `delegation.status`, `spawn_tree.*`).
- *Wrapping (future):* Tauri Rust sidecar bundles `atlas-cli`/`atlas-gateway`.

### 2.2 Inter-plane contracts
1. **Runtime→Domain (event ingress):** plugin emits one normalized `AtlasEvent` per hook; append-only, at-least-once, ordered per `run_id`; transport = UDS/localhost HTTP + synchronous JSONL append (audit must not depend on bus uptime).
2. **Domain→Runtime (command egress):** only via documented protocols (`POST /v1/runs`, approvals, `command.dispatch` for `/model`, cron/Kanban for durable work). No private state (`ctx._cli_ref.agent` forbidden).
3. **Domain→Product (read+stream):** REST CRUD + one SSE endpoint per concern (`/api/events/runs|pulse|audit`); product never writes `atlas.db` directly (single writer).
4. **Shared types:** all schemas live once in `packages/atlas-schema` (Zod) → codegen to TS types, JSON Schema, and a Python mirror.

### 2.3 Domain schemas (Zod, single source of truth)
```ts
import { z } from "zod";
export const Id = z.string().uuid(); export const Ts = z.string().datetime();
export const Money = z.object({ amount: z.number(), currency: z.string().default("USD") });

export const Mission = z.object({ id:Id, title:z.string(), goal:z.string(),
  successCriteria:z.array(z.string()).default([]),
  status:z.enum(["draft","active","blocked","done","archived"]).default("draft"),
  ownerId:Id.optional(), parentMissionId:Id.optional(),
  hermesKanbanBoard:z.string().optional(), progress:z.number().min(0).max(1).default(0),
  createdAt:Ts, updatedAt:Ts });

export const Task = z.object({ id:Id, missionId:Id, title:z.string(),
  status:z.enum(["todo","doing","blocked","done","cancelled"]).default("todo"),
  acceptance:z.array(z.string()).default([]), assignedAgent:z.string().optional(),
  hermesTaskId:z.string().optional(), dependsOn:z.array(Id).default([]),
  modelTierHint:z.enum(["t0","t1","t2","t3"]).optional(), createdAt:Ts, updatedAt:Ts });

export const Run = z.object({ id:Id, missionId:Id.optional(), taskId:Id.optional(),
  hermesRunId:z.string(), hermesSessionId:z.string().optional(),
  status:z.enum(["queued","running","awaiting_approval","succeeded","failed","interrupted"]),
  model:z.string(), provider:z.string(), tier:z.enum(["t0","t1","t2","t3"]),
  tokensIn:z.number().default(0), tokensOut:z.number().default(0),
  cacheReadTokens:z.number().default(0), reasoningTokens:z.number().default(0),
  costUsd:z.number().default(0), startedAt:Ts, endedAt:Ts.optional() });

export const ToolCall = z.object({ id:Id, runId:Id, name:z.string(),
  argsJson:z.string(), resultJson:z.string().optional(), toolset:z.string().optional(),
  status:z.enum(["started","progress","completed","error"]),
  durationMs:z.number().optional(), startedAt:Ts, endedAt:Ts.optional() });

export const Artifact = z.object({ id:Id, runId:Id.optional(), missionId:Id.optional(),
  kind:z.enum(["file","report","image","wiki","export"]),
  path:z.string(), sha256:z.string(), bytes:z.number(), createdAt:Ts });

export const WikiEntry = z.object({ id:Id, slug:z.string(), title:z.string(), body:z.string(),
  sourceRefs:z.array(z.object({kind:z.enum(["raw","url","run","crm"]),ref:z.string()})).default([]),
  provenance:z.enum(["agent","human","import"]).default("agent"),
  contradictions:z.array(z.object({entryId:Id,note:z.string()})).default([]),
  pinned:z.boolean().default(false), embeddingId:z.string().optional(),
  version:z.number().default(1), createdAt:Ts, updatedAt:Ts });

export const Person = z.object({ id:Id, name:z.string(), orgId:Id.optional(),
  emails:z.array(z.string()).default([]), handles:z.record(z.string()).default({}),
  tags:z.array(z.string()).default([]), notes:z.string().default(""), createdAt:Ts, updatedAt:Ts });
export const Organization = z.object({ id:Id, name:z.string(), domain:z.string().optional(),
  tags:z.array(z.string()).default([]), createdAt:Ts, updatedAt:Ts });
export const Opportunity = z.object({ id:Id, title:z.string(), orgId:Id.optional(), personId:Id.optional(),
  stage:z.enum(["lead","qualified","proposal","won","lost"]).default("lead"),
  value:Money.optional(), missionId:Id.optional(), createdAt:Ts, updatedAt:Ts });
export const Touchpoint = z.object({ id:Id, personId:Id.optional(), orgId:Id.optional(),
  opportunityId:Id.optional(), channel:z.enum(["discord","email","call","meeting","note"]),
  direction:z.enum(["in","out"]).default("out"), summary:z.string(), runId:Id.optional(), at:Ts });

export const PulseCheck = z.object({ id:Id, name:z.string(), kind:z.enum(["scheduled","event"]),
  schedule:z.string().optional(), query:z.string(), thresholds:z.record(z.number()).default({}),
  lastStatus:z.enum(["ok","warn","alert","unknown"]).default("unknown"),
  lastRunId:Id.optional(), hermesCronJobId:z.string().optional(), createdAt:Ts, updatedAt:Ts });

export const AuditEvent = z.object({ id:Id, at:Ts, actor:z.enum(["agent","human","system"]),
  kind:z.enum(["tool_call","llm_call","run_state","approval","mission_change","crm_change","wiki_change","pulse","config_change"]),
  runId:Id.optional(), missionId:Id.optional(), payloadJson:z.string(),
  reversible:z.boolean().default(false), inverseJson:z.string().optional(),
  prevHash:z.string(), hash:z.string() });
```

### 2.4 Policy / audit (every action logged, auditable, reversible-where-possible)
- **Capture:** `post_tool_call`/`post_llm_call`/`on_session_*` build `AuditEvent`s; token/cost from Hermes's canonical `agent.usage_pricing` (input/output/`cache_read`/`cache_creation`/`reasoning` tokens) — same breakdown Langfuse consumes.
- **Integrity:** append-only JSONL with per-line **hash chain** (`prevHash→hash`) + mirror row in `atlas.db.audit_events`. JSONL = truth; SQLite = index; tamper-evident; rotate daily, never rewrite.
- **Reversibility:** reversible actions (wiki/CRM/mission edits) store `inverseJson` for one-click undo; irreversible (sent email, executed shell, external write) flagged `reversible:false` and approval-gated.
- **Approval gating:** reuse Hermes's flow (`tools/approval.py`; `/v1/runs/{id}/approval`; `approval.request`/`respond`). ATLAS adds a `pre_tool_call` hook that **blocks** with structured deny when mission policy forbids — the sanctioned blocking mechanism.

### 2.5 Mission engine
- **Short missions:** `POST /v1/runs` with goal+context, stream `/v1/runs/{id}/events`, update `Run`/`Task` from events.
- **Long/durable:** provision a Hermes **Kanban board** (`hermesKanbanBoard`); use auto-decomposition + swarm (root→parallel workers→gated verifier→gated synthesizer→shared blackboard) with per-task model overrides from `modelTierHint`; in-gateway dispatcher; read `/workers/active`, `/runs/{id}`, `/inspect`.
- **Progress:** weighted leaf-task completion; success criteria are explicit checklist items marked by a verifier subagent or human approval; mission-state changes are reversible audit events.
- **Anti-pattern guard:** never model a long mission as a single `delegate_task` (non-durable, dies on parent interrupt); auto-route missions over `delegation.child_timeout_seconds` to cron/Kanban.

---

# 3. Tool/Action Event Bus

### 3.1 Design
```
Hermes hooks ─► atlas-hermes-plugin ─► normalize to AtlasEvent
        │
   ┌────┼─────────────────────────────┐
   ▼    ▼                             ▼
audit/*.jsonl  localhost ingress    in-proc ring buffer (backpressure)
(sync, hash-   (UDS/HTTP POST→gateway)
 chained)            │
              atlas-gateway EventHub (eventemitter2)
                     │
        ┌────────────┼───────────────┐
        ▼            ▼               ▼
   SSE /api/events/* atlas.db writer  replay engine
   (per-topic)       (batched, WAL)   (reads JSONL by run_id/time)
```

### 3.2 Library recommendation
- **`eventemitter2`** inside Node (namespaced `tool.*`/`run.*`/`pulse.*`, wildcards, near-native perf). **Do not** add Kafka/NATS/RabbitMQ — over-engineering and blows the memory budget at this scale; day-31+ only.
- **Runtime→gateway transport:** UDS (Linux) / named pipe or localhost HTTP (Windows); plugin POSTs batched `AtlasEvent[]` (flush 100 ms or 50 events).
- **Persistence:** dual — synchronous JSONL append in plugin (truth, survives gateway downtime) + batched SQLite writes under WAL.
- **WebUI streaming: SSE, not WebSocket** — events are server→client only; Hermes's `/v1/runs/{id}/events` is already SSE; free auto-reconnect via `EventSource`; HTTP/2 multiplexing sidesteps the 6-connection HTTP/1.1 cap. Commands via HTTP POST. WebSocket reserved for the future desktop overlay's bidirectional needs.

### 3.3 AtlasEvent + SSE framing
```ts
export const AtlasEvent = z.object({ id:Id, seq:z.number(),
  runId:Id.optional(), missionId:Id.optional(),
  topic:z.enum(["tool","llm","run","approval","pulse","mission","crm","wiki"]),
  type:z.string(), at:Ts, payload:z.record(z.any()) });
```
```
id: 1487
event: tool.complete
data: {"runId":"…","name":"web_extract","durationMs":812,"status":"completed"}
```
Reconnect resumes from `Last-Event-ID` (`seq`); gateway backfills from `atlas.db` → exactly-once delivery to UI atop at-least-once ingress.

### 3.4 Replay & inspection
Replay reads immutable JSONL (or `atlas.db` by `runId`/time) and re-emits into a "replay" SSE channel with a speed scrubber in the Run Inspector. Hash-chained append-only audit makes replay deterministic and tamper-evident — any past run reconstructable event-by-event with exact tool args/results/cost/approvals.

---

# 4. Model Router & Subagent Orchestration

### 4.1 Don't rebuild routing
Hermes's `runtime_provider.py` maps `(provider, model)` → `(api_mode, api_key, base_url)` across 18+ providers/300+ models with OAuth, credential pools, aliases, mid-session hot-swap (`/model`, `command.dispatch`, `X-Hermes-Model`), a `smart_model_routing` config section, and per-task model overrides in Kanban. ATLAS implements a **policy layer over** this, not a new router.

### 4.2 Four tiers as Hermes aliases + ATLAS policy
```ts
export const ModelTier = z.enum(["t0","t1","t2","t3"]);
export const RoutePolicy = z.object({ tier:ModelTier, primary:z.string(),
  fallback:z.string().optional(), maxTokensIn:z.number(),
  approxCostPer1kOut:z.number(), allowToolsets:z.array(z.string()).optional() });
```
| Tier | Purpose | Example route | Selection |
|---|---|---|---|
| T0 local/private | sensitive/offline | `ollama:llama3.1` / OpenAI-compat llama.cpp | `private` flag or no network |
| T1 cheap/fast | mechanical/routine | `gpt-4o-mini`, `claude-haiku`, `gemini-flash` | default leaf tasks, summaries, titles |
| T2 strong/review | architecture/research/review | `gpt-4o`, `claude-sonnet/opus`, `gemini-pro` | orchestrator/verifier, `modelTierHint:"t2"` |
| T3 specialized | code/vision/embeddings | code models; `vision_analyze`; embeddings via Ollama/`sqlite-rembed` | tool-driven |

Tier-0 is just an OpenAI-compatible `base_url` (Ollama/llama.cpp), already first-class — no new provider plugin. ATLAS stores routes in `atlas.db`; resolves `modelTierHint → primary` at run start.

### 4.3 Subagents, aggregation, cost
Reuse Hermes delegation/Kanban; ATLAS adds (1) **cost tracking** — `post_llm_call` accumulates `agent.usage_pricing` into `Run`/Mission; (2) **budget enforcement** — `pre_llm_call`/`pre_tool_call` aborts when `Mission.budgetUsd` exceeded (atop Hermes's `iteration_budget` + grace); (3) **aggregation** — Kanban synthesizer output → `Artifact`; verifier pass/fail marks success criteria. Observe spawns via `delegation.status`, `subagent.interrupt`, `spawn_tree.*`.

### 4.4 Token/context optimization
Lean on `context_compressor.py`, `prompt_caching.py`, `model_metadata.py`, and the **cache-stability rule** (never mutate past context/toolsets/system prompt mid-conversation). Inject mission/wiki context via `pre_llm_call` into the user message (cache-safe); make ATLAS slash commands **deferred by default with opt-in `--now`** (canonical Hermes pattern). Add per-tier `maxTokensIn` guardrails + pre-flight token estimate (downgrade tier or compress if over).

---

# 5. Persistent LLM Wiki / Knowledge Runtime

### 5.1 Storage: SQLite + FTS5 + sqlite-vec (hybrid, file-based) — not Postgres
Workload shape (single writer = gateway; many readers; small-team scale) favors SQLite: mirrors Hermes's own proven choice (sessions, Kanban are SQLite), zero extra infra, trivially bundled by the future Tauri sidecar. On NVMe with WAL + `synchronous=NORMAL`: ~10,000–50,000 writes/sec, read latency 100–1000× lower than networked DBs, ~0.02 ms/query vs ~0.10 ms for Postgres-over-socket. SQLite's only hard limit (concurrent writers) is moot because all writes funnel through one `atlas-gateway` writer. Postgres earns its keep only with multi-writer servers, heavy analytics, or pgvector/PostGIS/replication — none apply; choosing it adds a daemon, auth, vacuum/backup ops, and $10–25/mo for no real gain.

**PRAGMAs on every connection:**
```sql
PRAGMA journal_mode = WAL; PRAGMA synchronous = NORMAL; PRAGMA busy_timeout = 5000;
PRAGMA cache_size = -65536; PRAGMA mmap_size = 268435456; PRAGMA foreign_keys = ON;
```
Monitor WAL size, checkpoint frequency, `SQLITE_BUSY` count (SQLite observability is weak by default). Use `better-sqlite3` (synchronous, fastest Node binding) for the writer.

### 5.2 Knowledge runtime
```
raw sources (IMMUTABLE)            agent-maintained wiki (MUTABLE, versioned)
raw/<sha256>.{md,html,json} ─► WikiEntry (markdown + sourceRefs)
+ Artifact(sha256,bytes)            ├─ FTS5 → lexical search
                                    ├─ sqlite-vec → semantic search
                                    ├─ provenance: agent|human|import
                                    └─ contradictions[] → lint/flag
```
- Raw sources immutable + content-addressed; wiki references, never overwrites — provenance always traceable.
- Every wiki write = `AuditEvent(kind:"wiki_change")` + inverse patch (undo); `version` increments; old versions in the chain.
- **Contradiction/lint v1 (cheap):** FTS5 overlap + T1 model check during a Curator-style pass; embedding-cluster contradiction detection is **day-31+**. Lint (broken `sourceRefs`, orphan raw, stale provenance) runs on the Pulse schedule.
- **Embeddings: `sqlite-vec`** (maintained successor to deprecated `sqlite-vss`; pure C, no deps, runs everywhere incl. Windows/WASM, SIMD KNN, transaction-safe, metadata-filtered). Generate locally via **Ollama** (e.g. 768-dim `gte`/`granite`) or `sqlite-rembed` for remote APIs — keeping Tier-0 fully offline. Avoid external vector DBs (Pinecone/Weaviate/Qdrant) — unjustified infra here.

### 5.3 Hermes-memory bridge
- **v1: `pre_llm_call` injection** — query wiki (FTS5+vector), return `{context:"…wiki+provenance…"}`; exact documented RAG/memory mechanism, cache-safe, no Hermes changes.
- **v2: memory-provider plugin** — implement `MemoryProvider` ABC (`sync_turn`/`prefetch`/`shutdown`/`post_setup`) to become Hermes's selected backend; heavier, single-select; defer unless the wiki must fully replace MEMORY.md/USER.md.

---

# 6. Pulse Monitoring System
- **Scheduled checks = Hermes cron jobs** (`hermesCronJobId`) using native formats; a check prompt or a `no_agent` pre-run **script** (stdout = whole job — cheap metric collection with no model call); delivery to Discord (L2-BOT)/email; protected by cron's 3-min interrupt and `.tick.lock`.
- **Event-driven checks** = `atlas-gateway` rules over the bus (`run.failed`, cost spike, `SQLITE_BUSY` surge, mission blocked) → immediate alert.
- **Alerts/briefings:** thresholds classify `ok|warn|alert`; `warn→alert` raises an alert + delivery + `AuditEvent(kind:"pulse")`; daily briefing composed by a T1 model from audit rollups.
- **Anomaly detection v1:** rolling mean/σ baselines on cost/duration/failure — no ML (ML day-31+).
- **Dashboard:** status tiles (color by `lastStatus`), live alert feed (SSE `/api/events/pulse`), cost/duration sparklines, approval queue (drains via `/v1/runs/{id}/approval`); all SSE, no polling.

---

# 7. CRM / Relationship Runtime
- **Schema/relationships** (§2.3): `Organization 1─* Person *─* Opportunity *─* Touchpoint`; touchpoints link to runs and wiki (`sourceRef kind:"crm"`); opportunities link to missions. Every mutation = `AuditEvent(kind:"crm_change")` + inverse (undo). FTS5-indexed + `sqlite-vec`-embedded for "find similar."
- **Discord (L2-BOT):** route through Hermes's Discord adapter + `discord`/`discord_admin` toolsets; a gateway/post-tool hook auto-creates `Touchpoint`s on send/receive (with `runId`); add an ATLAS `crm_*` toolset (`crm_upsert_person`, `crm_log_touchpoint`, `crm_link_opportunity`) so the agent maintains CRM as a side effect.
- **Email:** Hermes IMAP/SMTP adapter → `Touchpoint(channel:"email")`; outbound mail `reversible:false` → approval-gated.
- **Calendar:** v1 = manual `meeting` touchpoints + optional Google Meet bundled plugin (join/transcribe/summarize → touchpoint + WikiEntry); two-way CalDAV/Google sync **day-31+**.
- **Loop:** opportunities spawn missions; mission runs generate touchpoints/artifacts; wiki accumulates a provenance-tracked dossier per person/org.

---

# 8. WebUI Cockpit
### 8.1 Framework: SvelteKit (Svelte 5 runes)
For a power-user, real-time-heavy, self-hosted cockpit: SvelteKit compiles to vanilla JS with no virtual-DOM runtime — far smaller baseline bundles than Next.js (~3–5 KB gzip vs React's ~85–130 KB runtime) and higher RPS on identical cheap VPS hardware (~1,200 vs ~850 in published benchmarks). ATLAS is internal/self-hosted and doesn't need Next.js's Vercel/edge/ISR/SEO ecosystem. **Honest caveat:** Next.js has the bigger ecosystem and AI-assistant familiarity; if the team is React-committed, the acceptable fallback is **Vite + React (plain, not Next.js)** to stay lean. Avoid Next.js itself (server/RSC weight) and any Electron-style shell. Pair SvelteKit with the `node` adapter, Tailwind, and a virtualized list/table for large logs.

### 8.2 Views
| View | Content | Live source |
|---|---|---|
| Dashboard | mission tiles, active runs, cost today, pulse alerts, approval queue | SSE `runs`+`pulse` |
| Missions | mission tree, task kanban, success-criteria checklist, progress | REST + SSE `run/mission.*` |
| Runs | live list; Run Inspector w/ event timeline, tool args/results, token+cost, replay scrubber | SSE `/v1/runs/{id}/events` proxied + replay |
| Audit | filterable hash-chain-verified log; undo for reversible events | REST paged |
| Wiki | markdown browse/edit, provenance, contradiction flags, FTS+semantic search | REST + FTS5/sqlite-vec |
| CRM | people/orgs/opportunities/touchpoints, linked missions | REST + FTS5 |
| Integrations | provider/model routes, Discord/email/MCP, plugin toggle, cron/pulse | REST → `config.set` JSON-RPC |

### 8.3 Real-time & performance
`EventSource` per topic (HTTP/2 multiplexed, auto-reconnect with `Last-Event-ID` backfill); commands via POST; route code-split; virtualize long lists; **coalesce high-frequency `tool.progress` to ~200 ms ticks** to avoid render storms; cockpit server <150 MB RAM (SvelteKit node adapter idles well under). Svelte runes/stores cover state — no Redux/react-query needed for SSE feeds.

---

# 9. CLI / TUI Layer
### 9.1 Library: Ink
Hermes's TUI is already Ink/React; Nous's explicit rule is "extend Ink, don't rebuild the transcript/composer." Ink is the mainstream AI-CLI choice (Claude Code and Gemini CLI both on Ink 6 + React 19; Ink v6.7+ uses DEC synchronized output for atomic frames). **Reject Bubbletea/Ratatui for v1** (force a Go/Rust companion + second render model — unjustified now; day-31+ only for a standalone fast TUI) and blessed/neo-blessed (legacy). Performance: coalesce tool-progress events; use `<Static>` for append-only log regions.

### 9.2 What it does
`atlas-cli` (Ink) over **`tui_gateway` JSON-RPC** (same protocol as Hermes's TUI) + `atlas-gateway` REST/SSE: mission control (list/create/start/inspect; `prompt.submit`/`session.steer`/`session.interrupt`; drive Kanban); run inspection + audit JSONL tailing; inline approvals via `approval.respond`/`clarify.respond`/`sudo.respond`/`secret.respond` (respect the gateway's two-guard inline-dispatch rule); slash autocomplete, `/model` hot-swap, `spawn_tree.list` overlay, cost meter, skin matching Hermes's skin engine. ATLAS adds in-process subcommands via `ctx.register_cli_command` (`hermes atlas <subcmd>`, no `main.py` edits); everything else is the standalone `atlas` binary.

---

# 10. Repository & Packaging Strategy
- **One ATLAS monorepo (pnpm workspaces)**; **Hermes as a git submodule pinned to a 40-char SHA**, installed editable via `uv pip install -e` into a dedicated venv. Never fork Hermes editable into the tree. Submodule+SHA gives reproducible builds, easy `git diff upstream/main`, deliberate upgrades. The **ATLAS plugin lives in the ATLAS repo** (symlinked/copied into `~/.hermes/plugins/atlas/` or pip entry point), so upstream pulls never touch it.
- **Turborepo over Nx** — for a small team with `apps/`+`packages/` JS/TS and "builds too slow" pain, ~20-line config, fastest build caching, incremental adoption. Nx's generators/graph/boundary-enforcement are over-engineering at 30-day small-team scale (day-31+ reconsideration). The Python plugin sits outside Turbo's JS graph — manage with `uv`, invoke its tests from a Turbo wrapper task.

**Folder structure:**
```
atlas/
├── pnpm-workspace.yaml · turbo.json · package.json
├── vendor/hermes/                  # submodule, pinned SHA (read-only)
├── apps/{cockpit(SvelteKit), cli(Ink), gateway(Node SSE/REST/audit)}
├── packages/{atlas-schema(Zod→TS/JSONSchema/Py), atlas-core, atlas-db(better-sqlite3+FTS5+vec),
│            hermes-client(/v1+JSON-RPC+ACP), ui}
├── plugins/atlas-hermes-plugin/    # Python: register(ctx), hooks→bus, ATLAS tools, audit
├── scripts/{pin-hermes.sh, codegen-schema.ts}
└── src-tauri/                      # RESERVED (empty in 30 days)
```
- **Names:** `@l2/atlas-schema|atlas-core|atlas-db|hermes-client|cockpit|cli|gateway`; Python `l2-atlas-hermes-plugin`.
- **Versioning:** independent ATLAS SemVer; record pinned Hermes SHA in `atlas/HERMES_PIN`, surface in `atlas doctor` + cockpit footer. Mirror Hermes's pinning policy (`>=floor,<next_major`; git deps by SHA; `uv lock` with hashes) given supply-chain history.
- **Build Windows+Linux:** Node apps via thin launcher; cockpit = SvelteKit node-adapter server; Python plugin via `uv`. Future Tauri sidecar produces per-`-$TARGET_TRIPLE` installers.

---

# 11. Windows + Linux Support
- **Native Windows is supported by Hermes** (PowerShell installer, native subprocess paths, taskkill process management, portable MinGit). The **only** feature needing WSL is the *embedded dashboard PTY chat pane* — which ATLAS deliberately replaces with `/v1` API + JSON-RPC, so the cockpit works natively on Windows.
- **PowerShell executor (already in L2-Atlas):** expose as an ATLAS tool that shells through Hermes's terminal backend; gate destructive commands through `tools/approval.py` + ATLAS policy; mark shell writes `reversible:false`.
- **Cross-platform discipline:** use `get_hermes_home()` (never hardcode `~/.hermes`); `pathlib`/`tempfile.gettempdir()` not POSIX hardcodes; `psutil.pid_exists` not `os.kill(pid,0)`; `multiprocessing spawn` (Hermes's own test-isolation uses spawn for Linux/macOS/Windows parity). Transport = localhost HTTP on Windows (named pipes) / UDS on Linux.
- **Desktop sidecar reservation: Tauri 2 (Rust), never Electron.** `src-tauri/` reserved now, built day-31+. Tauri bundles the Node `atlas-gateway`/`atlas-cli` as **sidecar external binaries** (`externalBin` in `tauri.conf.json`, named per `-$TARGET_TRIPLE`, spawned via `app.shell().sidecar(...)`, stdout piped to the UI via events; grant `shell:allow-execute`/`allow-spawn`). Standalone Node binaries (~80–100 MB, gitignored, fetched by a checksummed download script) keep it self-contained.
- **Why not Electron:** Tauri uses the OS WebView + Rust core → installers <10 MB and ~30–50 MB idle RAM vs Electron's bundled Chromium (80–150 MB installers, 150–300 MB RAM); startup ~0.3–0.5 s vs ~1–2 s. For overlays/hotkeys/STT-TTS that stay resident all day, Tauri's footprint is decisive. Caveat: Tauri uses platform WebViews (WebView2/Chromium on Windows, WebKitGTK on Linux) so test rendering on both and ship `-webkit-` polyfills.

---

# 12. Performance Requirements
- **Targets:** CLI start <2 s, WebUI cockpit <5 s, agent-runtime footprint <200 MB, cockpit server <150 MB. Hermes already hits aggressive cold starts (`hermes --version` 258 ms) — ATLAS must not regress it; keep the plugin's import cost minimal (lazy-import heavy deps; the plugin's only hot path is hook callbacks).
- **Optimizations:** SQLite **WAL** + the PRAGMA set (§5.1); connection pooling in the gateway (single writer, pooled readers); **lazy loading** of cockpit routes + plugin modules; **streaming responses** end-to-end (SSE; never buffer full runs); coalesce high-frequency events (§3, §8, §9); `better-sqlite3` synchronous binding for the writer to avoid async overhead.
- **Profiling:** Node `--prof`/`clinic.js` for the gateway; Python `py-spy` (sampling, no code change) for the plugin/agent; SvelteKit Lighthouse + bundle analyzer for the cockpit; track WAL size/checkpoint/`SQLITE_BUSY` counters surfaced in the Pulse dashboard.

---

# 13. Risks & Mitigation
| Risk | Mitigation |
|---|---|
| **Hermes upstream breaking changes** (fast-moving; ~10k commits) | Pin to a SHA; contract-test the `/v1`, JSON-RPC, hook, and `ctx` surfaces in CI; upgrade is an explicit `pin-hermes.sh` + green-tests gate; never edit core (no merge conflicts possible) |
| **Over-engineering in 30 days** | Reuse cron/Kanban/delegation/sessions as-is; SQLite not Postgres; eventemitter2 not a broker; SvelteKit not Electron; ML/contradiction/sidecar deferred to day-31+ |
| **Context window / token cost** | Per-tier token guardrails, dollar budgets enforced in hooks, lean on Hermes compression+caching, cache-safe context injection |
| **Data loss / audit integrity** | Append-only hash-chained JSONL as source of truth, synchronous write in-plugin (survives gateway downtime), SQLite WAL mirror, daily rotation, never rewrite |
| **Tool-execution sandboxing** | Use Hermes's `tools/approval.py` dangerous-command detection + container/SSH/Modal terminal backends; ATLAS `pre_tool_call` policy can hard-block; irreversible actions approval-gated |
| **Credential management** | Secrets in `.env` only (Hermes convention) or Bitwarden Secrets Manager (Hermes-supported single bootstrap token); strict dependency pinning by SHA after litellm/Mini-Shai-Hulud incidents; never log secrets in audit (mask in payloads) |
| **Single-writer SQLite contention** | All writes through one gateway writer; `busy_timeout`; monitor `SQLITE_BUSY`; if it ever saturates, that's the signal to evaluate LibSQL/Turso or Postgres (day-31+) |

---

# 14. 30-Day Roadmap (target 90% shipped, stable)

**Week 1 — Foundation.** Deliverables: monorepo (pnpm+Turbo); `vendor/hermes` submodule pinned + installed; `atlas-schema` (Zod→TS/JSON/Py codegen); `atlas-db` (migrations, WAL PRAGMAs, FTS5, sqlite-vec); **`atlas-hermes-plugin`** subscribing all six hooks → normalized `AtlasEvent`s → **hash-chained JSONL audit + SQLite**; `atlas-gateway` skeleton with the eventemitter2 hub + one SSE endpoint. *Acceptance:* a Hermes run produces a complete, replayable, tamper-evident audit trail with correct `agent.usage_pricing` cost. *Risk:* hook payload shape — validate against real runs early. **CRITICAL PATH.**

**Week 2 — Core systems.** Mission engine (short via `/v1/runs`; long via Kanban swarm) with progress + success criteria + reversible state; Model Router policy + tier table + cost/budget enforcement in hooks; Wiki/Knowledge runtime (immutable raw + versioned entries + FTS5 + sqlite-vec + provenance + `pre_llm_call` injection bridge). *Acceptance:* a multi-step mission runs end-to-end, routes by tier, stays within budget, and its artifacts/wiki entries are provenance-tracked. **CRITICAL PATH (mission engine).**

**Week 3 — Product surfaces.** SvelteKit cockpit: Dashboard, Missions, Runs (+Run Inspector with replay), Audit (with undo), Wiki, CRM — all over SSE; enhanced Ink `atlas-cli` over JSON-RPC (mission control, log tail, inline approvals). *Acceptance:* an operator can launch, watch live, inspect, approve, replay, and undo entirely from cockpit and CLI; cockpit <5 s load, server <150 MB.

**Week 4 — Integration, stabilization, polish.** CRM auto-touchpoints + `crm_*` toolset; Discord (L2-BOT) + email channels; Pulse (cron-backed scheduled + event-driven, alerts/briefings, dashboard); Integrations view (routes/plugins/config via `config.set`); Windows+Linux packaging + `atlas doctor`; contract tests + perf pass. *Acceptance:* clean install on Windows and Linux; Pulse alerts deliver to Discord; full audit/replay verified; CI green against pinned Hermes.

**Critical path (must not slip):** Week-1 audit/event plumbing → Week-2 mission engine → Week-3 Run Inspector + approvals. **Defer to day 31+:** Tauri desktop sidecar + overlays/STT/TTS/hotkeys; ML contradiction detection + embedding-cluster anomaly detection; two-way calendar sync; memory-provider-plugin path; Nx/broker/Postgres migrations; multi-node fleet.

---

# 15. Open Questions (require L2 Systems decisions)
1. **Hermes-memory ownership:** does the ATLAS Wiki fully *replace* MEMORY.md/USER.md (memory-provider plugin, v2) or *augment* them (pre_llm_call injection, v1)? Affects how tightly ATLAS couples to Hermes's memory lifecycle.
2. **Single vs multi-profile cockpit:** one ATLAS cockpit per Hermes profile, or one cockpit aggregating multiple profiles? Drives whether `atlas.db` is per-profile (simple, isolated) or shared (needs profile-scoping throughout).
3. **Where the mission "brain" lives:** is decomposition/verification driven by ATLAS code (deterministic, auditable) or by a Hermes orchestrator subagent (flexible, but less controllable)? Hybrid is likely, but the default must be chosen.
4. **Audit retention & privacy:** retention window, redaction policy for secrets/PII in payloads, and whether the JSONL chain is exportable/signed for external compliance.
5. **Embedding model + dimensionality:** which local Ollama embedding model (and dim) is the standard, given Tier-0 offline requirements and sqlite-vec storage cost?
6. **Tauri sidecar boundary (day-31+):** does the desktop sidecar bundle Node binaries (self-contained, ~80–100 MB) or require a system Node (smaller, fragile PATH)? Affects installer size and update strategy.
7. **Kanban vs ATLAS mission tree as the durable source of truth:** if both track tasks, which is authoritative on conflict, and how is state reconciled?
8. **Upstream contribution posture:** are any ATLAS-built capabilities (e.g. a generic audit/observability plugin) contributed back to Hermes to reduce the maintenance surface, or kept proprietary in the ATLAS repo?

---

*This document is implementation-grade and reflects the verified state of Hermes Agent as of v0.15.2 (May 29 2026). Hermes evolves rapidly; the single most important operational discipline is pinning to a commit SHA and gating upgrades on ATLAS's contract tests. Every architectural choice above optimizes for the stated constraints — performance-first, Windows+Linux, no Electron, no black-box fork, 90% in 30 days — and explicitly defers the genuinely hard/slow items (desktop sidecar, ML detection, broker/Postgres) to day 31+ so the critical path stays shippable.*