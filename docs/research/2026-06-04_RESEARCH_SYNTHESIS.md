# Research Synthesis — L2 ATLAS

Date: 2026-06-04

## Sources analyzed

Raw research reports moved to `docs/research/raw-reports/`:

1. `2026-06-04_01_hermes-foundation-architecture.md`
2. `2026-06-04_02_knowledge-runtime-llm-wiki-memory-rag.md`
3. `2026-06-04_03_subagents-workflows-skills.md`
4. `2026-06-04_04_native-desktop-overlay-stt-ui-report-a.md`
5. `2026-06-04_04b_native-desktop-overlay-stt-ui-report-b.md`
6. `2026-06-04_06_market-stack-engineering-practices.md`

Unrelated file left in Downloads:

- `deep-research-report.md` — legal/commercial research for selling websites to lawyers. Not part of L2 ATLAS.

Missing / incomplete relative to requested prompt set:

- No dedicated CRM/Pulse/Channels report was found. CRM/Pulse/channel conclusions appear inside Hermes and market reports, but a standalone deep dive still needs to be run.

---

## Executive synthesis

The reports converge on a strong direction:

> L2 ATLAS should be an enhanced Hermes-based agent operating system with an operator cockpit, persistent LLM Wiki, governed subagents, pulse monitoring, AI-native CRM primitives, and a Rust-first native sidecar — optimized for serious performance, not Electron-style bloat.

The strongest repeated recommendations:

1. **Use Hermes as the foundation, not as a black-box subprocess.**
2. **Keep the runtime auditable through an event bus and durable run logs.**
3. **Use SQLite/WAL/FTS5/sqlite-vec first, not premature Postgres complexity.**
4. **Build the knowledge runtime as LLM Wiki + search + memory, not RAG-only.**
5. **Make subagents governed, role-based, and model-tier aware.**
6. **Use Rust-native desktop sidecar; avoid Electron.**
7. **Keep WebUI for the full cockpit, native app for immediacy/overlay/voice.**
8. **Ship a narrow operator-cockpit loop first, not the entire 100x platform.**

---

## Cross-report agreements

### 1. Hermes foundation

All relevant reports agree that Hermes is the right foundation because it already contains:

- Python core agent loop;
- tools/toolsets;
- skills;
- memory providers;
- session store;
- gateway;
- cron;
- MCP;
- profiles;
- delegation/subagents;
- provider routing;
- CLI/TUI infrastructure.

The implementation-grade Hermes report adds an important correction: Hermes core is primarily Python, with TypeScript mostly around TUI/UI surfaces. ATLAS must respect that boundary.

### 2. Event/audit layer

The Hermes report and subagent report both converge on an audit-first runtime:

- every LLM call;
- every tool call;
- every subagent assignment;
- every external action;
- every approval;
- every artifact;
- every verification result.

This should become a central ATLAS object model, not an afterthought.

### 3. SQLite-first local architecture

The Hermes and knowledge reports strongly recommend SQLite/WAL/FTS5/sqlite-vec for early ATLAS.

Reasoning:

- matches Hermes's own local-first patterns;
- fast;
- simple;
- low operational overhead;
- portable;
- good enough for local and small-team work;
- avoids premature distributed infrastructure.

Postgres/pgvector remains a future SaaS/multi-tenant option, not MVP default.

### 4. LLM Wiki as compounding knowledge

The knowledge report strongly supports the attached LLM Wiki pattern:

- raw sources immutable;
- wiki pages maintained by agents;
- index/log/schema required;
- query results can be filed back;
- contradictions and stale claims must be tracked;
- RAG supports recall but does not replace compiled synthesis.

### 5. Native app performance

Both native reports agree:

- no Electron;
- Slint is the strongest candidate for polished native UI;
- egui is good for internal/debug/operator tools;
- iced is viable but not preferred;
- custom wgpu is powerful but too expensive for full MVP;
- Tauri can package cockpit or provide thin shell but should not own overlay/HUD core;
- voice models must not be loaded in idle path.

### 6. Market wedge

Market report aligns with product thesis:

- do not compete as another visual agent builder;
- do not compete as chat-with-files;
- wedge is technical founders / AI operators / small high-context teams;
- first demo should be a closed daily operation loop: sources → briefing → missions → approved actions → audit → closing brief.

---

## Conflicts and decisions needed

### Conflict 1 — WebUI stack: SvelteKit vs Next.js

Research report 01 recommends SvelteKit/Svelte 5 for the WebUI cockpit. Earlier planning assumed Next.js because L2 already uses it heavily.

Decision not locked yet.

Evaluation criteria:

- runtime performance;
- developer velocity;
- existing L2 code reuse;
- UI polish;
- ecosystem;
- desktop/web sharing;
- long-term maintainability.

Temporary decision:

> Keep WebUI framework open until a UI stack spike compares SvelteKit and Next.js against ATLAS cockpit requirements.

### Conflict 2 — Tauri role

Native reports agree Tauri is useful but disagree in tone on how much. The consistent synthesis is:

> Tauri is acceptable as a thin shell for the WebUI cockpit, but not as the core native overlay/sidecar runtime.

### Conflict 3 — CRM depth

Market/Hermes reports identify CRM as important, but no dedicated CRM report was found. Do not build CRM depth yet.

Temporary decision:

> Start with minimal AI-native CRM primitives after mission/wiki/run loop works.

### Conflict 4 — SaaS stack timing

Some research mentions product services in Node/TypeScript; knowledge report favors local SQLite. The synthesis:

> MVP should be local-first SQLite + enhanced Hermes runtime. SaaS/multi-tenant services come after dogfood validation.

---

## Recommended architecture after cross-check

```txt
L2-ATLAS-PROJECT
├── foundation/hermes-agent         # enhanced Hermes foundation / fork/submodule/worktree
├── atlas-core                      # ATLAS domain models, policy, audit, mission runtime
├── atlas-runtime                   # enhanced agent runtime, event bus, model router, subagents
├── atlas-knowledge                 # LLM Wiki + SQLite/FTS5/sqlite-vec + ingest/query/lint
├── atlas-pulse                     # monitors, scheduled/event checks, briefings
├── atlas-native                    # Rust/Slint sidecar, overlay, STT/TTS later
├── atlas-web                       # cockpit WebUI, framework TBD
└── atlas-skills                    # curated ATLAS-grade skills/workflows
```

Core runtime loop:

```txt
Mission / Source / Event
  → policy + context engine
  → enhanced Hermes/ATLAS agent runtime
  → tool/subagent/workflow execution
  → event bus + audit capture
  → artifacts + wiki/memory updates
  → cockpit + pulse next actions
```

---

## Locked recommendations

1. **Electron is out as default.**
2. **Rust-native sidecar is the native direction.**
3. **Slint is the leading candidate for native user-facing UI.**
4. **SQLite/WAL/FTS5/sqlite-vec is the MVP datastore direction.**
5. **LLM Wiki is a first-class runtime, not a documentation afterthought.**
6. **Subagents must be governed by role, model tier, toolset, risk, and audit.**
7. **Hermes is foundation; ATLAS enhances it directly.**
8. **CRM is important but not first implementation surface.**

---

## Immediate next work

1. Clone/pin Hermes foundation.
2. Run source audit of Hermes extension points against report 01.
3. Run deep audit of `L2-Atlas/src/atlas_core` and map extractable modules.
4. Create ATLAS domain schemas for Mission, Run, ToolCall, Artifact, Source, WikiPage, AuditEvent, AgentProfile, Skill, Workflow.
5. Create ATLAS SQLite schema draft.
6. Create UI stack spike: SvelteKit vs Next.js.
7. Run missing CRM/Pulse/Channels research.
