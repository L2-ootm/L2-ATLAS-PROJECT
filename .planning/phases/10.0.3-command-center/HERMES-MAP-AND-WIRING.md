# Hermes Foundation Map & Complete Wiring Plan

**Date:** 2026-06-19
**Scope:** What Hermes provides, what ATLAS builds, Rust vs Python, context budget wiring
**Status:** Research complete

---

## Part 1: What Hermes Provides

### The AIAgent Loop (run_agent.py, ~4600 LOC)

The core is a synchronous conversation loop:
```
while iterations < max_budget:
    1. Check interrupt
    2. API call to LLM (streaming or non-streaming)
    3. If tool_calls: dispatch via handle_function_call()
    4. If no tool_calls: return final_response
    5. Post-tool hooks (plugin callbacks)
    6. Context compression check
    7. Retry on errors (error_classifier.py)
    8. Fallback model switching (credential_pool rotation)
```

**Provided:** Full tool-calling loop with retry, fallback, compression, streaming, 60+ constructor parameters.

**ATLAS gap:** The loop is reactive (user message -> response). No mission-scoped execution, no plan-driven iteration, no RunOutcome-based lifecycle.

### Tools (83 files, 50+ tools)

| Category | Tools | Status for ATLAS |
|----------|-------|------------------|
| **File ops** | read_file, write_file, patch, search_files | **USE AS-IS** — core agent capability |
| **Terminal** | terminal, process | **USE AS-IS** — shell execution |
| **Web** | web_search, web_extract | **USE AS-IS** — research capability |
| **Browser** | navigate, snapshot, click, type, scroll, CDP | **USE AS-IS** — computer use |
| **Vision** | vision_analyze, video_analyze | **USE AS-IS** — multimodal |
| **Code execution** | execute_code | **USE AS-IS** — sandboxed execution |
| **Delegation** | delegate_task | **EXTEND** — needs durable delegation, structured handoff |
| **Memory** | memory, session_search | **REPLACE** — ATLAS needs mission-scoped memory, not personal notes |
| **Skills** | skills_list, skill_view, skill_manage | **EXTEND** — needs project-local skill loading |
| **Todo** | todo | **USE AS-IS** — task tracking |
| **MCP** | mcp_tool | **USE AS-IS** — tool integration protocol |
| **Kanban** | kanban_* (10 tools) | **DEFER** — multi-agent dispatch, not core |
| **Messaging** | send_message, discord | **DEFER** — platform integrations |
| **Image/Video gen** | image_generate, video_generate | **DEFER** — creative tools |
| **Home Assistant** | ha_* | **DEFER** — IoT integration |
| **Cron** | cronjob | **DEFER** — scheduling |

### Providers (28 model plugins)

All major providers supported: OpenAI, Anthropic, Google/Gemini, Bedrock, Azure, DeepSeek, xAI, OpenRouter, Ollama, Copilot, Nous, HuggingFace, Novita, NVIDIA, Xiaomi, Moonshot, Qwen, and more.

**Status:** **USE AS-IS.** Provider routing is Hermes's strongest capability. ATLAS should not rebuild this.

### Memory Providers (8 plugins)

Honcho, mem0, supermemory, byterover, hindsight, holographic, openviking, retaindb.

**Status:** **REPLACE.** Hermes memory is user-profile oriented. ATLAS needs mission-scoped memory with provenance chains. The 6-layer memory framework (D-019) defines what ATLAS needs.

### Messaging Platforms (19 platforms)

Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Email, SMS, DingTalk, WeCom, Feishu, Weixin, QQBot, Yuanbao, BlueBubbles, Webhook, API Server, MS Graph, Home Assistant.

**Status:** **DEFER.** Channel integration is v2.0 scope. Not core to the agentic loop.

### Skills (90+ across 24 categories)

Major categories: software-development (debugging, TDD, planning, code review), github (PR workflow, issues, codebase inspection), research (arxiv, llm-wiki), creative (design, diagrams, media), productivity (notion, linear, google-workspace), autonomous-ai-agents (claude-code, codex, hermes-agent).

**Status:** **SELECTIVELY USE.** The software-development and github skills are directly relevant. Others are domain-specific and should be loaded on-demand.

### Context Compression

Auto-summarization of middle turns when context approaches limit. Compression model feasibility checks. StreamingContextScrubber for real-time sanitization.

**Status:** **USE AS-IS.** This is mature infrastructure.

### Credential Pool

Multi-key rotation with cooldown, account-level throttle detection, failover between providers.

**Status:** **USE AS-IS.** Critical for production reliability.

### Tool Registry

Auto-discovery via AST inspection, TTL-cached check_fn (30s), MCP dynamic refresh, plugin override support.

**Status:** **USE AS-IS.** Well-designed, extensible.

### Plugin System

General hooks (pre/post tool, pre/post LLM, session start/end), memory-provider ABC, model-provider discovery, context-engine extension, image-gen providers.

**Status:** **USE AS-IS.** The ATLAS audit plugin already uses this system successfully.

---

## Part 2: What ATLAS Must Build

### Category A: Core Runtime (Not Provided by Hermes)

| Module | What | Why | Rust? | Priority |
|--------|------|-----|-------|----------|
| **Mission lifecycle** | Mission CRUD, status machine, archival | Hermes has no mission concept | L2 | P0 |
| **Run lifecycle** | Run CRUD, start/complete/cancel/fail transitions | Hermes sessions are conversation-scoped | L2 | P0 |
| **Audit event writer** | Structured event persistence with redaction | Hermes has hooks but no structured audit trail | L1 | P0 |
| **Policy engine** | Workspace boundary, tool allowlist, approval gates | Hermes has advisory guardrails, not enforcement | L1 | P0 |
| **Handoff protocol** | HANDOFF.md generation and consumption | Hermes has delegate_task with summary only | Python first | P0 |
| **Stop conditions** | Secret/scope/runtime/done checks | Hermes has iteration budget only | Python first | P0 |
| **Claim taxonomy** | Evidence/inference/uncertainty classification | Not provided by any system | Python first | P0 |
| **Memory router** | 6-layer context selection with budget | Hermes has personal memory only | Python first | P1 |
| **Context assembly** | Multi-layer brief with RAG retrieval | Hermes has basic context injection | Python first | P1 |
| **Entropy reduction** | 8-class scan + report | Not provided by any system | Python first | P1 |
| **Graph engine** | SQLite-backed entity graph with extractors | Not provided by any system | Python first | P1 |
| **Embedding service** | fastembed + sqlite-vec integration | Hermes has no embedding infra | Python first | P1 |

### Category B: ATLAS-Specific Extensions (Hermes Partially Provides)

| Module | What Hermes Has | What ATLAS Needs | Change |
|--------|----------------|------------------|--------|
| **NativeAtlasAgent** | Stub (emits event, returns succeeded) | Real Hermes loop invocation | Wire `AIAgent.run_conversation()` through `AgentRuntime.execute()` |
| **Delegation** | `delegate_task` (sync, not durable) | Durable delegation with handoff | Extend with HANDOFF.md protocol |
| **Memory** | User-profile MEMORY.md | Mission-scoped memory | Replace with ATLAS memory layers |
| **Skill loading** | `~/.hermes/skills/` path | Project-local + L2 skill registry | Add project path resolution |
| **Provider routing** | Provider/model with credential pool | Mission-aware routing (different models per phase) | Extend with Focus.framework-based routing |

### Category C: Infrastructure (Not Provided by Hermes)

| Module | What | Why | Rust? | Priority |
|--------|------|-----|-------|----------|
| **Rust CLI binary** | `atlas` CLI in Rust | Eliminate subprocess overhead (L4) | L2 | P2 |
| **Runtime daemon** | In-process executor over HTTP | Already built in Python, cement later | L2 | P2 |
| **Dashboard auth** | Operator authentication | Cockpit needs auth for multi-user | Python first | P3 |
| **Channel integration** | Telegram/Discord/Slack | v2.0 scope | Python | v2.0 |

---

## Part 3: Rust vs Python Decision Matrix

### The D-022 Rule

> "Rust-first immediately for all new infrastructure. Python confined to: (1) Hermes plugin ABI, (2) LLM provider adapters, (3) throwaway scripts."

### Module Classification

| Module | Current | Target | Rationale |
|--------|---------|--------|-----------|
| Gateway (REST + SSE) | **Rust** | Rust (L0) | Already done. Read-only, CLI-dispatch writes. |
| Audit event writer | Python | **Rust (L1)** | Every action goes through this. High-frequency writes. GIL bottleneck. Safety-critical redaction. |
| Policy engine | Python | **Rust (L1)** | Enforcement must be compile-time correct. No advisory-only. |
| Pydantic models | Python | **Rust (L2)** | 1:1 serde mapping. JSON-stable. Migration contracts. |
| CLI binary | Python | **Rust (L2)** | Stable command boundary. Single binary. <100ms startup. |
| Run executor | Python | **Rust (L2)** | Thread→tokio tasks. Structured cancellation. Never orphan runs. |
| Mission/run state | Python | **Rust (L2)** | State machine correctness. Atomic transitions. |
| Context assembly | Python | **Rust (L2)** | Secret redaction is safety-critical. Correctness > iteration speed. |
| Wiki service | Python | **Rust (L3)** | FTS5 already in Rust (db.rs). Semantic search via turbovec. |
| Graph service | Python | **Rust (L3)** | File I/O + regex. Parallel scanning with rayon. |
| Agent adapters | Python | **Python (permanent)** | LLM SDKs are Python-first. I/O-bound. Language overhead is noise vs API latency. |
| LLM provider routing | Python | **Python (permanent)** | Hermes plugin ABI. 28 providers. Not worth rewriting. |
| Throwaway scripts | Python | **Python** | No performance requirement. |

### Where Rust Wins

1. **Audit writes under load.** Every agent action calls `emit()`. GIL serializes writes. Rust's tokio tasks + connection-per-task eliminate this.

2. **CLI subprocess overhead.** The Rust gateway spawns `atlas` CLI processes for every write (~50-100ms per write). At L4, this disappears entirely.

3. **State machine correctness.** Mission/Run status transitions are safety-critical. Rust's type system enforces "never leave a run orphaned as running."

4. **Secret redaction.** `SECRET_PATTERNS` regexes run on every write path. Rust's `regex` crate is faster, and compile-time guarantees reduce attack surface.

5. **Process lifecycle.** Subprocess spawn, kill-tree, timeout — OS-level primitives where Rust excels.

### Where Rust Is Overkill

1. **LLM provider adapters.** Waiting on 500ms+ API responses. Language overhead is noise.

2. **Context assembly.** Runs once per invocation. String concatenation. Not a bottleneck.

3. **Graph service at current scale.** 400-600 nodes is within Python's capability.

4. **Wiki lint rules.** Complex business logic easier to iterate in Python.

5. **Throwaway scripts.** No performance requirement.

### The CLI Contract Is the Migration Spec

Every Python service function is already defined as a CLI subcommand with typed inputs/outputs:
- `atlas mission create --title ... --intent ...` → `mission_service.create_mission()`
- `atlas run exec <run_id>` → `run_executor.execute_run()`
- `atlas wiki search --query ...` → `wiki_service.search_wiki()`
- `atlas graph build --scope ...` → `graph_service.build_graph()`

The CLI arguments define the Rust function signature. The CLI output defines the Rust return type. Migration is mechanical: replace the Python function body with Rust, keep the same CLI interface.

---

## Part 4: Context Budget Wiring

### The Problem

Current context assembly produces ~500 tokens. The database has millions. The agent operates blind.

### The Solution: 3-Tier Retrieval

```
HOT (always loaded): ~1K tokens
  Focus + Mission + Handoff summary

WARM (RAG-retrieved): ~3-5K tokens
  Wiki pages (FTS5/semantic) + Skills + Graph neighbors + Audit patterns

COLD (search on demand): 0 tokens injected
  Full wiki bodies + Tool outputs + Full audit + Graph full
  Agent reads via tools when needed

Total background context: ~5-8K tokens (4% of 200K window)
Working memory: ~192K tokens (96%)
```

### How Each Retrieval Layer Connects

| Layer | Source | Mechanism | Tokens | When |
|-------|--------|-----------|--------|------|
| **FTS5 wiki search** | `wiki_pages` + `wiki_fts` | `search_wiki(query)` → BM25 ranking | 200-600 | Always (first attempt) |
| **Semantic search** | `wiki_pages` + `wiki_vec` | `semantic_search(query)` → cosine similarity | 200-600 | When FTS5 returns poor results |
| **Graph traversal** | `graph_nodes` + `graph_edges` | `get_neighbors(entity_id, depth=2)` | 300-800 | When task involves relationships |
| **Audit patterns** | `audit_events` | `SELECT WHERE event_type='failure' ORDER BY timestamp` | 100-300 | When debugging or prior failures |
| **Skill matching** | `SKILL_INVENTORY.md` | Keyword match against Focus.framework | 100-300 | When domain-specific task |
| **Provenance chain** | `memory_provenance` | JOIN against wiki pages in context | 100-300 | When wiki pages are selected |

### The Memory Router (Implementation)

```python
class MemoryRouter:
    """Selects and compacts context layers within a token budget."""
    
    def assemble(self, request: MemoryRequest) -> AgentContext:
        budget = TokenBudget(total=8000, used=0)
        
        # 1. Hot context (always)
        hot = self._hot_context(request.focus, request.mission, request.handoff)
        budget.allocate(hot.tokens)
        
        # 2. Warm layers (budget-aware)
        warm_budget = budget.remaining
        
        # FTS5 wiki (always try first)
        if warm_budget > 1000:
            wiki_results = self._search_wiki_fts(request.query, limit=3)
            budget.allocate(sum(r.tokens for r in wiki_results))
        
        # Semantic fallback (if FTS5 poor)
        if warm_budget > 1000 and self._fts5_quality(wiki_results) < threshold:
            wiki_sem = self._search_wiki_semantic(request.query, limit=3)
            budget.allocate(sum(r.tokens for r in wiki_sem))
        
        # Audit patterns (if debugging)
        if request.is_debugging and warm_budget > 500:
            audit = self._retrieve_audit_patterns(request.mission_id, limit=5)
            budget.allocate(audit.tokens)
        
        # Graph neighbors (if complex task)
        if request.complexity == 'high' and warm_budget > 500:
            graph = self._retrieve_graph_neighbors(request.focus_id, depth=2)
            budget.allocate(graph.tokens)
        
        # Skills (if domain-specific)
        if request.focus.framework and warm_budget > 300:
            skills = self._match_skills(request.focus.framework)
            budget.allocate(skills.tokens)
        
        # 3. Assemble final brief
        return AgentContext(
            markdown=self._render(hot, warm_items),
            sources=tuple(budget.sources),
            token_budget_used=budget.used
        )
```

### Token Counting

Use a simple estimator (not tiktoken — add a dependency for token counting):

```python
def estimate_tokens(text: str) -> int:
    """Conservative token estimate: ~4 chars per token for English."""
    return len(text) // 4
```

For higher accuracy, use `tiktoken` when available (optional dependency).

### Embedding Infrastructure

| Component | Status | Action |
|-----------|--------|--------|
| `wiki_vec` table | **Missing** — referenced in code but never created | Create migration 0010 |
| `fastembed` | **Code exists** — lazy import in `semantic_search()` | Wire into `update_wiki_page()` |
| `sqlite-vec` | **Optional dep** — graceful FTS5 fallback | Install, create vec0 table |
| Embedding model | **Not chosen** | Use `BAAI/bge-small-en-v1.5` (384-dim, ONNX, no GPU) |
| Embedding on write | **Not implemented** | Compute in `update_wiki_page()`, store in `wiki_vec` |
| Embedding on query | **Code exists** — `semantic_search()` | Wire into `MemoryRouter` |

### Implementation Steps

| Step | What | Effort | Unlocks |
|------|------|--------|---------|
| 1 | Create `wiki_vec` migration (0010) | 0.5 day | Embedding storage |
| 2 | Wire FTS5 into `context_service.py` | 0.5 day | Wiki retrieval |
| 3 | Add embedding computation to `update_wiki_page()` | 1 day | Semantic search |
| 4 | Build `MemoryRouter` class | 2 days | Budget-aware selection |
| 5 | Wire router into `_run_prompt()` | 0.5 day | Agent gets RAG context |
| 6 | Add token counting | 0.5 day | Budget enforcement |
| 7 | Add graph retrieval (when engine exists) | 1 day | Structural context |
| 8 | Add audit pattern retrieval | 0.5 day | Failure-aware context |

**Total: ~6 days** to go from 500-token starvation to 8K-token RAG-powered context.

---

## Part 5: The Complete Wiring Map

### How Everything Connects

```
                    ┌─────────────────────────────────────┐
                    │         OPERATOR (Cockpit UI)       │
                    │  Focus → Mission → Run → Review     │
                    └──────────┬──────────────────────────┘
                               │
                    ┌──────────▼──────────────────────────┐
                    │        COMMAND CENTER               │
                    │  Focus card, quick-capture,         │
                    │  launch run, activity feed          │
                    └──────────┬──────────────────────────┘
                               │
                    ┌──────────▼──────────────────────────┐
                    │     MEMORY ROUTER (NEW)             │
                    │  Selects layers, enforces budget    │
                    │  ~8K tokens total                   │
                    └──┬────┬────┬────┬────┬──────────────┘
                       │    │    │    │    │
          ┌────────────┘    │    │    │    └────────────┐
          ▼                 ▼    │    ▼                 ▼
    ┌───────────┐  ┌──────────┐ │ ┌──────────┐  ┌──────────┐
    │ HOT       │  │ FTS5     │ │ │ GRAPH    │  │ AUDIT    │
    │ Focus     │  │ Wiki     │ │ │ Engine   │  │ Patterns │
    │ Mission   │  │ Search   │ │ │ (future) │  │ (SQL)    │
    │ Handoff   │  └────┬─────┘ │ └──────────┘  └──────────┘
    └───────────┘       │       │
                        ▼       ▼
                  ┌──────────────────┐
                  │  SEMANTIC SEARCH │
                  │  fastembed +     │
                  │  sqlite-vec      │
                  └──────────────────┘
                               │
                    ┌──────────▼──────────────────────────┐
                    │     CONTEXT ASSEMBLY                │
                    │  Renders markdown brief             │
                    │  Secret redaction                   │
                    │  Provenance tracking                │
                    └──────────┬──────────────────────────┘
                               │
                    ┌──────────▼──────────────────────────┐
                    │     RUN EXECUTOR                    │
                    │  Stop condition checks              │
                    │  Agent dispatch                     │
                    │  Terminal state transitions         │
                    │  Handoff generation                 │
                    └──┬───────────────────────┬──────────┘
                       │                       │
          ┌────────────┘                       └────────────┐
          ▼                                                 ▼
    ┌───────────┐                                    ┌───────────┐
    │ NATIVE    │                                    │ CLAUDE    │
    │ AGENT     │                                    │ CODE      │
    │ (Hermes   │                                    │ (SDK)     │
    │  loop)    │                                    │           │
    └─────┬─────┘                                    └─────┬─────┘
          │                                                 │
          ▼                                                 ▼
    ┌───────────────────────────────────────────────────────────┐
    │                    HERMES FOUNDATION                       │
    │  50+ tools, 28 providers, context compression,           │
    │  credential pool, tool registry, plugin system            │
    └───────────────────────────────────────────────────────────┘
                               │
                    ┌──────────▼──────────────────────────┐
                    │     AUDIT SERVICE (Rust L1)         │
                    │  emit() → SQLite + SSE              │
                    │  Secret redaction                   │
                    │  Pydantic-first validation          │
                    └──┬───────────────────────┬──────────┘
                       │                       │
          ┌────────────┘                       └────────────┐
          ▼                                                 ▼
    ┌───────────┐                                    ┌───────────┐
    │  GATEWAY  │                                    │  GRAPH    │
    │  (Rust)   │                                    │  ENGINE   │
    │  REST+SSE │                                    │  (future) │
    └───────────┘                                    └───────────┘
```

### The Data Flow

1. **Operator** creates Focus → Mission via Command Center
2. **Memory Router** assembles context: hot (Focus+Mission+Handoff) + warm (FTS5/wiki + skills + audit patterns)
3. **Context Assembly** renders markdown brief, applies secret redaction, tracks provenance
4. **Run Executor** checks stop conditions, dispatches to agent (Native or Claude Code)
5. **Agent** executes via Hermes foundation (tools, providers, compression)
6. **Audit Service** persists every action as AuditEvent (Rust L1 when cemented)
7. **Handoff Service** writes HANDOFF.md after terminal state
8. **Graph Engine** receives audit events, updates entity graph (when built)
9. **Next run** inherits handoff state via Memory Router

### What Each Layer Needs From Each Other

| Layer | Needs From Others | Provides To Others |
|-------|-------------------|-------------------|
| **Memory Router** | Wiki FTS5/semantic, Graph neighbors, Audit patterns, Skills | Budget-aware context brief |
| **Context Assembly** | Memory Router output, Focus, Project | Secret-redacted markdown brief |
| **Run Executor** | Context Assembly output, Stop conditions, Agent registry | RunOutcome + HANDOFF.md |
| **Audit Service** | Every module's emit() calls | AuditEvent persistence, SSE stream |
| **Graph Engine** | Audit events, Wiki pages, Memory provenance | Entity graph, neighbor queries |
| **Handoff Service** | Run outcome, Audit events, Focus state | HANDOFF.md for next session |
| **Entropy Service** | Git diff, File system, Audit history | Entropy report for next context |
| **Policy Engine** | Workspace boundary, Tool allowlist | Enforcement decisions |
| **Agent Adapters** | Hermes foundation, Context brief | RunOutcome, Audit events |

---

## Part 6: Implementation Priority

### P0 (This Week) — Safety + Continuity

| What | Files | Days | Unlocks |
|------|-------|------|---------|
| Handoff service | `handoff_service.py` (NEW) | 1-2 | Cross-session continuity |
| Stop conditions | `run_executor.py` (MODIFY) | 1-2 | Safety gate |
| Claim taxonomy | `core.py` (MODIFY RunOutcome) | 1 | Evidence discipline |
| FTS5 into context | `context_service.py` (MODIFY) | 0.5 | Wiki retrieval |

### P1 (Next Week) — Intelligence

| What | Files | Days | Unlocks |
|------|-------|------|---------|
| Memory router | `memory_router.py` (NEW) | 2 | Budget-aware selection |
| wiki_vec migration | `0010_wiki_embeddings.sql` (NEW) | 0.5 | Embedding storage |
| Embedding on write | `wiki_service.py` (MODIFY) | 1 | Semantic search |
| Deep context assembly | `context_service.py` (MODIFY) | 2 | Multi-layer briefs |
| Entropy service | `entropy_service.py` (NEW) | 2 | Code/docs cleanup |

### P2 (Following Week) — Foundation

| What | Files | Days | Unlocks |
|------|-------|------|---------|
| Graph hook | `audit_service.py` (MODIFY) | 1 | Live graph updates |
| Loop spec mapping | `cli/main.py` (MODIFY) | 1-2 | Framework executability |
| Rust audit writer | `atlas-state` crate (NEW) | 3-5 | L1 cementation |

### P3 (Month 2) — Cementation

| What | Files | Days | Unlocks |
|------|-------|------|---------|
| Rust CLI binary | `atlas-cli` crate (NEW) | 5-8 | Single binary, <100ms |
| Rust run executor | `atlas-exec` crate (NEW) | 5-8 | Structured cancellation |
| Rust context assembly | Part of atlas-cli | 3-5 | Safety-critical redaction |

---

## Part 7: Open Questions

1. **turbovec availability.** D-014 references it as a spike candidate but the GitHub repo returns 0. Is it a private/unreleased project? Should we use sqlite-vec as the immediate option?

2. **NativeAtlasAgent wiring.** The Hermes loop is ~4600 LOC synchronous code. Wiring it through `AgentRuntime.execute()` requires: (a) passing the assembled context as the system prompt, (b) capturing tool calls as AuditEvents, (c) handling the iteration budget. How much of the Hermes constructor参数 need to be configurable from ATLAS?

3. **Embedding model choice.** `BAAI/bge-small-en-v1.5` is the fastembed default. Is this appropriate for ATLAS domain content (planning docs, technical decisions, wiki pages)? Should we evaluate `colbert-ir/colbertv2.0` for late interaction?

4. **Context budget sizing.** 8K tokens for background context is a starting point. Should this be configurable per Focus.framework? Should different mission types get different budgets?

5. **Graph engine timing.** The graph hook (Layer 6) depends on the graph engine existing. Should we build a minimal graph engine (WP-1 from the graph phase plan) before or after the memory router?

6. **Entropy scan cadence.** Every N runs? On phase completion? On operator trigger? What's the right default?

7. **Rust migration scope for L1.** The audit service is 241 lines of Python. Should we migrate just `emit()`, or the entire audit module including `get_events_for_run()` and `export_jsonl()`?
