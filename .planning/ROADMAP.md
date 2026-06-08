# Roadmap — L2 ATLAS

## Milestone v1.0: Operator Cockpit MVP

**Goal:** Ship the first closed operator loop — create mission → run through enhanced ATLAS/Hermes runtime → capture audit trail → file artifacts to LLM Wiki → display in web cockpit.

**Start:** 2026-06-04
**Status:** In progress (Phase 5 planned; pending Wave 0 execution)

---

## Phases

- [x] **Phase 1: Hermes Foundation Clone & Extension Audit** - Clean Hermes clone + authoritative extension-surface audit (completed 2026-06-05)
- [x] **Phase 2: Core Domain Schemas & SQLite Migration** - Pydantic v2 domain model + SQLite schema as single authoritative data contract (completed 2026-06-06)
- [x] **Phase 3: Research Closure — WebUI Spike & CRM Intake** - Close open research gaps D-006 and D-010 (completed 2026-06-06)
- [x] **Phase 4: ATLAS Event Bus & Audit Core** - Structured audit event bus wired into Hermes runtime (completed 2026-06-07)
- [x] **Phase 5: Mission & Run Lifecycle** - Core mission state machine: create, execute, complete, cancel (completed 2026-06-08)
- [ ] **Phase 6: LLM Wiki Runtime** - Wiki ingest, update, query, and lint pipeline
- [ ] **Phase 7: API Gateway** - Typed REST API exposing all mission, run, audit, and wiki operations
- [ ] **Phase 8: WebUI Operator Cockpit** - Web cockpit: mission management, run monitoring, audit viewer, wiki browser
- [ ] **Phase 9: Skill Inventory & Classification** - Complete classified skill inventory for curated default skill pack

### Candidate Sidecar Spikes

- [x] **Phase 4.5 / Phase 5 adjunct: FreeLLMAPI Sidecar Gateway** - Accepted for spike via D-015. Mock and real Kilo keyless smoke tests passed. Integrate as loopback OpenAI-compatible gateway for `free-tier-ok` task classes; do not vendor into ATLAS core yet. (completed 2026-06-08)

---

## Phase Details

### Phase 1: Hermes Foundation Clone & Extension Audit

**Goal:** Produce a clean, secret-free Hermes clone at the pinned SHA and an authoritative audit of all extension surfaces so every future ATLAS addition is properly grounded.

**Depends on:** Nothing (first phase)

**Requirements:** FOUND-01, FOUND-02, FOUND-03, FOUND-04

**Success Criteria** (what must be TRUE):

1. `_EXTERNAL_REPOS/hermes-agent` exists at SHA `e8b9369a9…`, secret-scan gate reports CLEAN.
2. `docs/research/HERMES_FOUNDATION_AUDIT.md` exists with every extension-surface row filled (hook, tool registry, session store, delegation, cron, profiles, gateway, MCP, plugin surface, CLI/TUI boundary).
3. The audit states a clear YES/NO verdict on whether the audit-event bus can attach via plugin/hook without editing cli.py or run_agent.py.
4. `docs/imports/L2_ATLAS_MODULE_EXTRACTION_PLAN.md` exists with every atlas_core module classified (port/rewrite/reference/discard) and data-carrying modules linked to Phase 2 schemas.
5. L2-Atlas repo working tree is unmodified after the audit (git status clean).

**Plans:** 4/4 plans complete

Plans:

- [x] 01-01-PLAN.md — Clone Hermes at pinned SHA, add gitignore, run secret-scan gate
- [x] 01-02-PLAN.md — Extension-surface audit + event-bus YES/NO verdict from cloned source
- [x] 01-03-PLAN.md — Divergence decision stubs for identified friction points
- [x] 01-04-PLAN.md — L2-Atlas atlas_core donor module extraction plan

---

### Phase 2: Core Domain Schemas & SQLite Migration

**Goal:** Establish the Pydantic v2 domain model and SQLite schema as the single authoritative data contract — the foundation every other phase builds on.

**Depends on:** Phase 1

**Requirements:** SCHEMA-01, SCHEMA-02, SCHEMA-03

**Success Criteria** (what must be TRUE):

1. `packages/atlas-core/atlas_core/schemas/core.py` exists with Mission, Run, AuditEvent, ToolCall, Artifact, Source, WikiPage as Pydantic v2 models.
2. `from atlas_core.schemas.core import Mission` succeeds in a clean Python 3.11 environment.
3. `Mission.model_json_schema()` emits valid JSON Schema with all fields present.
4. `infra/migrations/0001_core.sql` applies on a fresh SQLite `:memory:` DB without errors; all 7 tables created (missions, runs, audit_events, tool_calls, artifacts, sources, wiki_pages).
5. FTS5 virtual table created (or blocked state documented with sqlite build note).
6. Column names in DDL match Pydantic field names 1:1 (no silent drift).

**Plans:** 3/3 plans complete

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Package scaffold, venv setup, editable install, pytest conftest

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Pydantic v2 models (core.py) + schema/serialization tests

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-03-PLAN.md — SQLite migration DDL + migration validation test suite

---

### Phase 3: Research Closure — WebUI Spike & CRM Intake

**Goal:** Close the two open research gaps (D-006 WebUI framework, D-010 CRM/Pulse research) so no build phase encounters an unresolved architectural fork.

**Depends on:** Phase 2 (schema shapes inform UI data contract)

**Requirements:** RESEARCH-01, RESEARCH-02

**Success Criteria** (what must be TRUE):

1. `docs/research/WEBUI_STACK_SPIKE.md` exists with scored comparison of SvelteKit/Svelte 5 vs Next.js/React against cockpit-specific criteria (realtime stream, L2 code reuse, bundle size, polish ceiling).
2. Spike ends in a concrete framework recommendation OR a defined 1-day build spike that would objectively decide it.
3. `NATIVE_APP_STRATEGY.md` no longer presupposes Next.js (C3 inconsistency patched).
4. `docs/research/CRM_PULSE_CHANNELS_DEEP_DIVE.md` exists with defined open questions, MVP boundary, and a research brief ready for a future deep-dive agent.
5. D-006 updated to "spike complete / recommendation: [framework]" or "spike required."

**Plans:** 2/2 plans complete

**Wave 1** *(parallel -- no dependencies)*

Plans:
- [x] 03-01-PLAN.md -- WebUI stack spike document, NATIVE_APP_STRATEGY.md patch, D-006 locked
- [x] 03-02-PLAN.md -- CRM/Pulse/Channels deep-dive intake document

---

### Phase 4: ATLAS Event Bus & Audit Core

**Goal:** Wire a structured audit event bus into the Hermes runtime so every important action emits a durable AuditEvent — the audit-first requirement that all observability builds on.

**Depends on:** Phase 1 (extension-surface audit), Phase 2 (schemas + DB)

**Requirements:** RUNTIME-03, AUDIT-01, AUDIT-02

**Success Criteria** (what must be TRUE):

1. ATLAS event bus module exists at `services/agent-runtime/atlas_core/event_bus.py` (or equivalent per D-011 layout).
2. Running a Hermes tool call via ATLAS produces at minimum one ToolCall row in the SQLite database.
3. Running a mock LLM call via ATLAS produces an AuditEvent row of kind `llm_call`.
4. `GET /runs/{id}/events` returns a correctly ordered list of AuditEvent records.
5. Exporting a run's audit trail as JSONL produces valid JSONL (one JSON object per line, all required fields present).
6. All audit writes are transactional — partial failures do not leave orphaned event rows.
7. No in-core edits to Hermes cli.py or run_agent.py required (verified by git diff showing no changes to those files, or a divergence decision record exists if edits were unavoidable).

**Plans:** 3/3 plans complete

**Wave 0** *(no dependencies)*

Plans:
- [x] 04-01-PLAN.md — Service package scaffold + conftest + test stubs (pyproject, atlas_runtime, atlas_audit skeleton, db/run_id/lock fixtures)

**Wave 1** *(blocked on Wave 0 completion)*

Plans:
- [x] 04-02-PLAN.md — audit_service.py (emit, get_events_for_run, export_jsonl) + full test suite

**Wave 2** *(blocked on Wave 1 completion)*

Plans:
- [x] 04-03-PLAN.md — atlas_audit Hermes plugin (register, hook callbacks, session->run mapping) + integration tests + plugin install

---

### Phase 5: Mission & Run Lifecycle

**Goal:** Implement the core mission state machine — create, execute, complete, cancel — backed by the audit event bus, with a working CLI and unit-tested service layer.

**Depends on:** Phase 2 (schemas), Phase 4 (event bus)

**Requirements:** RUNTIME-01, RUNTIME-02, RUNTIME-04, RUNTIME-05, RUNTIME-06, RUNTIME-07

**Success Criteria** (what must be TRUE):

1. `atlas mission create --title "Test" --intent "..."` persists a Mission row and prints the mission ID.
2. `atlas mission run <id>` starts execution, creates a Run row, emits task.started AuditEvent.
3. A completed run transitions to `succeeded` or `failed` status with finish timestamp and summary.
4. `atlas mission cancel <id>` stops an active run and transitions it to `failed`; partial audit trail is preserved.
5. Subagent assignment creates an AuditEvent of kind `subagent_run` with role, model tier, tool allowlist, and token budget in the payload.
6. Policy engine rejects a command outside the workspace boundary and emits an AuditEvent of kind `failure`.
7. Policy engine works on Linux (bash) and Windows (PowerShell) paths — confirmed by two test runs.
8. All service layer functions have unit tests (≥ 80% branch coverage on mission_service.py and run_service.py).

**Plans:** 4/4 plans complete

**Wave 0** *(no dependencies)*

Plans:
- [x] 05-01-PLAN.md — Scaffold: pyproject.toml update, all service stubs, CLI skeleton, test skeletons (xfail)

**Wave 1** *(blocked on Wave 0 completion — runs in parallel)*

Plans:
- [x] 05-02-PLAN.md — mission_service.py + run_service.py implementation (RUNTIME-01/02/04/05)
- [x] 05-03-PLAN.md — policy.py + subagent_service.py implementation (RUNTIME-06/07)

**Wave 2** *(blocked on Wave 1 completion)*

Plans:
- [x] 05-04-PLAN.md — CLI main.py wiring + full suite coverage gate

---

### Phase 6: LLM Wiki Runtime

**Goal:** Implement the wiki ingest, update, query, and lint pipeline — the compounding knowledge layer that persists valuable agent output across runs.

**Depends on:** Phase 2 (schemas + DB), Phase 5 (mission/run lifecycle for audit events)

**Requirements:** WIKI-01, WIKI-02, WIKI-03, WIKI-04, WIKI-05, AUDIT-03

**Success Criteria** (what must be TRUE):

1. `atlas wiki ingest <path>` copies the file to `wiki/raw/`, computes SHA-256, creates a Source row, and emits an AuditEvent of kind `wiki_update`.
2. `atlas wiki update <slug> --body "..."` upserts a WikiPage row, appends to wiki/log.md, and updates wiki/index.md.
3. `atlas wiki search "query"` returns ranked results via FTS5 full-text search.
4. `atlas wiki semantic "query"` returns results via sqlite-vec vector search (or prints a clear "sqlite-vec not loaded" message if the extension is absent).
5. `atlas wiki lint` reports at least one stale/contradicted claim on a wiki page deliberately seeded with a contradiction.
6. wiki/index.md has an entry for every WikiPage row in the database; wiki/log.md has an entry for every wiki_update AuditEvent.
7. Service layer unit tests cover ingest, update, search, and lint paths (≥ 80% branch coverage on wiki_service.py).

**Plans:** 6 plans

**Wave 1** *(no dependencies)*

Plans:
- [x] 06-01-PLAN.md — Extend atlas_core Source model + MemoryProvenance + 0002 migration

**Wave 2** *(blocked on Wave 1 — runs in parallel)*

Plans:
- [ ] 06-02-PLAN.md — atlas-wiki package scaffold (pyproject.toml, __init__ files, service stubs)
- [ ] 06-03-PLAN.md — wiki_service.py core functions (ingest, update, search, lint) + test_wiki_service.py
- [ ] 06-04-PLAN.md — provenance_service.py + test_provenance_service.py

**Wave 3** *(blocked on Wave 2 completion — runs in parallel)*

Plans:
- [ ] 06-05-PLAN.md — atlas_wiki CLI main.py + test_cli.py + atlas_runtime CLI extension
- [ ] 06-06-PLAN.md — Full coverage gate + GRAPH_MEMORY_RESEARCH_NOTES.md

---

### Phase 7: API Gateway

**Goal:** Expose all mission, run, audit, and wiki operations via a typed REST API so the cockpit and future integrations have a stable interface.

**Depends on:** Phase 5 (mission/run lifecycle), Phase 6 (wiki runtime)

**Requirements:** (none exclusively owned — Phase 7 is the API infrastructure layer enabling Phase 8; all domain REQ-IDs are owned by their originating phases)

**Success Criteria** (what must be TRUE):

1. FastAPI server starts with `uvicorn atlas_api.main:app` and serves the OpenAPI spec at `/docs`.
2. `POST /missions` creates a mission; `GET /missions` returns a paginated list.
3. `POST /missions/{id}/run` starts a run; `GET /runs/{id}` returns run status.
4. `GET /runs/{id}/events` returns ordered AuditEvent list with all fields.
5. `GET /wiki/pages` returns a paginated page list; `GET /wiki/search?q=` returns FTS5 results.
6. All endpoints return proper HTTP status codes (201 create, 200 ok, 404 not found, 422 validation error).
7. OpenAPI schema matches the Pydantic response models (no manual schema drift).
8. Integration tests cover all 8 endpoints (happy path + one error case each).

**Plans:** TBD

---

### Phase 8: WebUI Operator Cockpit

**Goal:** Ship the first web-based operator cockpit — mission management, real-time run monitoring, audit trail viewer, and wiki browser — in the framework decided by the Phase 3 spike.

**Depends on:** Phase 3 (framework decision), Phase 7 (API)

**Requirements:** COCKPIT-01, COCKPIT-02, COCKPIT-03, COCKPIT-04, COCKPIT-05, COCKPIT-06

**Success Criteria** (what must be TRUE):

1. `npm run dev` (or equivalent) starts the cockpit dev server and renders the mission list page without errors.
2. Mission list page loads and displays all missions from the API with status badges.
3. Mission create form submits to the API and the new mission appears in the list without page reload.
4. Run detail page renders a real-time streaming audit event log (new events appear without manual refresh).
5. Wiki browser shows a searchable list of pages and renders page content.
6. Cockpit initial page load completes in < 2 seconds (measured with devtools network throttle disabled, localhost).
7. No Electron dependency in package.json.
8. Cockpit renders without errors in latest Chrome and Firefox.

**Plans:** TBD
**UI hint:** yes

---

### Phase 9: Skill Inventory & Classification

**Goal:** Produce a complete, classified skill inventory so ATLAS can ship with a curated default skill pack rather than an undifferentiated dump of every existing skill.

**Depends on:** Phase 1 (Hermes skill surface known); parallel to Phases 4–8

**Requirements:** SKILLS-01, SKILLS-02, SKILLS-03, SKILLS-04

**Success Criteria** (what must be TRUE):

1. `docs/imports/SKILL_INVENTORY.md` exists with every skill from Hermes skills dir, l2-agent-skills, and OpenClaw/GSD imports listed with: name, path, description, class (core/operator/l2-internal/personal-private/experimental/deprecated), public-safe flag, polish-required flag.
2. Core ATLAS Pack skills have complete metadata (name, version, class, autonomy_level, risk, requires_tools, requires_secrets, verification steps, public_safe: true).
3. Developer Operator Pack skills have the same metadata and are marked public_safe: true.
4. L2 Systems Pack skills classified l2-internal and public_safe: false.
5. No personal/private skill paths are referenced in any public-facing manifest.
6. Skill registry loads all core + operator pack skills without error on a clean Hermes install.

**Plans:** TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Hermes Foundation Clone & Extension Audit | 4/4 | Complete    | 2026-06-05 |
| 2. Core Domain Schemas & SQLite Migration | 3/3 | Complete    | 2026-06-06 |
| 3. Research Closure — WebUI Spike & CRM Intake | 2/2 | Complete    | 2026-06-06 |
| 4. ATLAS Event Bus & Audit Core | 3/3 | Complete   | 2026-06-07 |
| 5. Mission & Run Lifecycle | 4/4 | Complete    | 2026-06-08 |
| 6. LLM Wiki Runtime | 1/6 | In progress | - |
| 7. API Gateway | 0/0 | Not started | - |
| 8. WebUI Operator Cockpit | 0/0 | Not started | - |
| 9. Skill Inventory & Classification | 0/0 | Not started | - |

---

## Milestone v2.0: Pulse, CRM & Native Sidecar (planned)

_Not sequenced yet. Phases will be defined after v1.0 completes and is dogfooded._

Phase 10: Basic Pulse Monitor
Phase 11: CRM Primitives (Contact/Organization/Opportunity)
Phase 12: Rust Native Sidecar Spike (command palette + local IPC)
Phase 13: STT/TTS Voice Integration
Phase 14: Floating Overlay / Run-Status HUD

---

## Phase Dependency Map

```
Phase 1 (Hermes audit) ──────────────────────────────► Phase 4 (Event Bus)
Phase 2 (Schemas + DB) ─────────┬───────────────────► Phase 4
                                 └───────────────────► Phase 5 ──► Phase 7 ──► Phase 8
Phase 3 (Research closure) ─────────────────────────► Phase 8 (framework decision)
Phase 4 (Event Bus) ────────────────────────────────► Phase 5
Phase 5 (Mission/Run) ─────────────────────────────► Phase 6 ──► Phase 7
Phase 6 (Wiki Runtime) ─────────────────────────────► Phase 7
Phase 7 (API) ──────────────────────────────────────► Phase 8
Phase 8 (Cockpit) — ships MVP loop end-to-end
Phase 9 (Skills) — parallel to 4–8, not blocking
```

Phases 1–3 are foundation/audit — no shipped service code, only docs + schemas.
Phases 4–8 are the MVP build track — each produces running, testable code.
Phase 9 is parallel infrastructure — can run alongside 4–8 without blocking.

---

## Coverage Map (34 REQ-IDs, 100% assigned)

| REQ-ID | Phase |
|--------|-------|
| FOUND-01 | Phase 1 |
| FOUND-02 | Phase 1 |
| FOUND-03 | Phase 1 |
| FOUND-04 | Phase 1 |
| SCHEMA-01 | Phase 2 |
| SCHEMA-02 | Phase 2 |
| SCHEMA-03 | Phase 2 |
| RESEARCH-01 | Phase 3 |
| RESEARCH-02 | Phase 3 |
| RUNTIME-03 | Phase 4 |
| AUDIT-01 | Phase 4 |
| AUDIT-02 | Phase 4 |
| RUNTIME-01 | Phase 5 |
| RUNTIME-02 | Phase 5 |
| RUNTIME-04 | Phase 5 |
| RUNTIME-05 | Phase 5 |
| RUNTIME-06 | Phase 5 |
| RUNTIME-07 | Phase 5 |
| WIKI-01 | Phase 6 |
| WIKI-02 | Phase 6 |
| WIKI-03 | Phase 6 |
| WIKI-04 | Phase 6 |
| WIKI-05 | Phase 6 |
| AUDIT-03 | Phase 6 |
| COCKPIT-01 | Phase 8 |
| COCKPIT-02 | Phase 8 |
| COCKPIT-03 | Phase 8 |
| COCKPIT-04 | Phase 8 |
| COCKPIT-05 | Phase 8 |
| COCKPIT-06 | Phase 8 |
| SKILLS-01 | Phase 9 |
| SKILLS-02 | Phase 9 |
| SKILLS-03 | Phase 9 |
| SKILLS-04 | Phase 9 |
