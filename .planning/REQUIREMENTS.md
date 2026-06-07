# Requirements — L2 ATLAS v1.0

Milestone: **v1.0 — Operator Cockpit MVP**
Generated: ingest-docs merge 2026-06-04
Status: Active

---

## FOUNDATION — Hermes Integration

- [ ] **FOUND-01**: Developer can clone Hermes fresh at the pinned SHA with a secret-scan gate that confirms no auth/state files were copied.
- [ ] **FOUND-02**: Developer can read a Hermes extension-point audit documenting hook/tool/plugin surfaces and whether the audit-event bus can attach without in-core edits.
- [ ] **FOUND-03**: Every divergence from upstream Hermes is classified (upstreamable / plugin-tool / ATLAS-only / experimental) and recorded in docs/decisions/.
- [ ] **FOUND-04**: Developer can read a per-module classification (port/rewrite/reference/discard) for all L2-Atlas atlas_core donor modules.

## SCHEMA — Domain Contracts

- [x] **SCHEMA-01**: Pydantic v2 models exist for Mission, Run, AuditEvent, ToolCall, Artifact, Source, and WikiPage with correct field names, enums, and FK relationships.
- [x] **SCHEMA-02**: SQLite migration 0001_core.sql applies on a fresh database (WAL mode, foreign keys enforced, FTS5 index created).
- [x] **SCHEMA-03**: model_json_schema() emits valid JSON Schema for all core Pydantic models (D-012 TS/Rust bridge verified).

## RUNTIME — Enhanced Agent Runtime

- [ ] **RUNTIME-01**: User can create a Mission (title + intent) via CLI or API and see it persisted in the database.
- [ ] **RUNTIME-02**: User can execute a Mission and have it processed by the enhanced ATLAS/Hermes runtime loop.
- [ ] **RUNTIME-03**: Every LLM call, tool call, subagent run, approval, external action, and artifact emits a structured AuditEvent row in the database.
- [ ] **RUNTIME-04**: A completed Run shows final status (succeeded/failed), start/finish timestamps, and a summary.
- [ ] **RUNTIME-05**: User can cancel a running Mission and see a partial audit trail in the database.
- [ ] **RUNTIME-06**: Subagents are governed: role, model tier, allowed tools, autonomy level, and token budget are captured per AuditEvent row.
- [ ] **RUNTIME-07**: Policy engine enforces cross-platform workspace/command safety (not Windows-only PowerShell).

## WIKI — LLM Knowledge Runtime

- [ ] **WIKI-01**: User can ingest a raw source file into the wiki (immutable raw copy stored, SHA-256 stamped, Source row created).
- [ ] **WIKI-02**: Agent can create or update a WikiPage and the change is logged in wiki/log.md and reflected in the database.
- [ ] **WIKI-03**: User can query wiki pages via full-text search (FTS5) and get ranked results.
- [ ] **WIKI-04**: wiki/index.md and wiki/log.md remain consistent after every agent-driven wiki update.
- [ ] **WIKI-05**: Semantic vector search (sqlite-vec) returns relevant wiki pages for a natural-language query.

## AUDIT — Observability

- [ ] **AUDIT-01**: User can retrieve the full ordered audit trail for any Run from the API.
- [ ] **AUDIT-02**: Audit trail is exportable as JSONL (one event per line, all fields present).
- [ ] **AUDIT-03**: Wiki lint pass flags pages with stale or contradicted claims.

## COCKPIT — Operator UI

- [ ] **COCKPIT-01**: User can view a list of missions (with status, created timestamp) from the web cockpit.
- [ ] **COCKPIT-02**: User can view the real-time audit event stream for an active run.
- [ ] **COCKPIT-03**: User can view the full audit trail for a completed run.
- [ ] **COCKPIT-04**: User can browse and search wiki pages from the cockpit.
- [ ] **COCKPIT-05**: User can create and launch a mission from the cockpit UI.
- [ ] **COCKPIT-06**: Cockpit loads in < 2 seconds on a local machine (no Electron startup tax).

## SKILLS — Skill & Workflow Registry

- [ ] **SKILLS-01**: Skill inventory document exists: name, path, description, class, public-safe flag, polish-required flag, ATLAS relevance.
- [ ] **SKILLS-02**: Core ATLAS skill pack has required metadata (name, version, class, autonomy_level, risk, requires_tools, requires_secrets, verification, public_safe).
- [ ] **SKILLS-03**: Developer Operator Pack classified with same metadata schema.
- [ ] **SKILLS-04**: L2 Systems Pack classified as l2-internal (not public default).

## RESEARCH — Open Research Items

- [x] **RESEARCH-01**: WebUI stack spike document exists comparing SvelteKit/Svelte 5 vs Next.js/React against cockpit requirements, ending in a concrete recommendation (resolves D-006).
- [x] **RESEARCH-02**: CRM/Pulse/Channels deep-dive research document exists with open questions and MVP boundary defined.

---

## Future Requirements (Milestone 2+)

### PULSE
- PULSE-01: User sees a periodic briefing of repo state, inboxes, deadlines, and wiki health.
- PULSE-02: Heartbeat monitors run on cron and emit AuditEvents.

### CRM
- CRM-01: Contact/Organization/Opportunity models exist in SQLite with audit trail linkage.
- CRM-02: CRM entities linkable to missions.

### NATIVE
- NATIVE-01: Rust native sidecar with global command palette and IPC to runtime.
- NATIVE-02: STT/TTS voice integration via Hermes providers.
- NATIVE-03: Floating overlay / run-status HUD with inline approval prompts.

---

## Out of Scope (v1.0)

- WhatsApp/production messaging integration — too risky before runtime is proven
- Multi-tenant SaaS, billing, Postgres — post-dogfood only
- Self-modifying agent behavior — governance work required first
- MCP marketplace UI — later
- Mobile app — later

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| FOUND-01 | Phase 1 | Pending |
| FOUND-02 | Phase 1 | Pending |
| FOUND-03 | Phase 1 | Pending |
| FOUND-04 | Phase 1 | Pending |
| SCHEMA-01 | Phase 2 | Complete |
| SCHEMA-02 | Phase 2 | Complete |
| SCHEMA-03 | Phase 2 | Complete |
| RESEARCH-01 | Phase 3 | Complete |
| RESEARCH-02 | Phase 3 | Complete |
| RUNTIME-03 | Phase 4 | Pending |
| AUDIT-01 | Phase 4 | Pending |
| AUDIT-02 | Phase 4 | Pending |
| RUNTIME-01 | Phase 5 | Pending |
| RUNTIME-02 | Phase 5 | Pending |
| RUNTIME-04 | Phase 5 | Pending |
| RUNTIME-05 | Phase 5 | Pending |
| RUNTIME-06 | Phase 5 | Pending |
| RUNTIME-07 | Phase 5 | Pending |
| WIKI-01 | Phase 6 | Pending |
| WIKI-02 | Phase 6 | Pending |
| WIKI-03 | Phase 6 | Pending |
| WIKI-04 | Phase 6 | Pending |
| WIKI-05 | Phase 6 | Pending |
| AUDIT-03 | Phase 6 | Pending |
| COCKPIT-01 | Phase 8 | Pending |
| COCKPIT-02 | Phase 8 | Pending |
| COCKPIT-03 | Phase 8 | Pending |
| COCKPIT-04 | Phase 8 | Pending |
| COCKPIT-05 | Phase 8 | Pending |
| COCKPIT-06 | Phase 8 | Pending |
| SKILLS-01 | Phase 9 | Pending |
| SKILLS-02 | Phase 9 | Pending |
| SKILLS-03 | Phase 9 | Pending |
| SKILLS-04 | Phase 9 | Pending |
