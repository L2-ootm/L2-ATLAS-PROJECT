---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Operator Cockpit MVP
status: Awaiting next milestone
last_updated: "2026-06-15T17:41:36.005Z"
last_activity: 2026-06-15 — Milestone v1.0 completed and archived
progress:
  total_phases: 11
  completed_phases: 11
  total_plans: 33
  completed_plans: 33
  percent: 100
---

# STATE — L2 ATLAS

## Current Position

Phase: Milestone v1.0 complete (tag `v1.0`)
Plan: —
Status: Awaiting next milestone — run `/gsd-new-milestone` to scope v1.1 (Native Cockpit Shell)
Last activity: 2026-06-15 — Milestone v1.0 completed and archived

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-15) · `.planning/MILESTONES.md`

**Core value:** A serious, auditable AI operating system for technical founders/operators.
**Current focus:** Planning next milestone (v1.1 Native Cockpit Shell).

## Deferred Items

Acknowledged at milestone close on 2026-06-15:

| Category | Item | Status |
|---|---|---|
| verification | Phase 08 `08-VERIFICATION.md` | human_needed — satisfied by 09.5 manual operator UAT (all Phase 8 cockpit surfaces exercised end-to-end) |
| uat | Phase 08 `08-HUMAN-UAT.md` | passed (0 pending) — superseded by 09.5 UAT |
| public-release | `PUBLIC_RELEASE_HARDENING.md §4` items 1–5, 7–8 | bounded, pre-public-publish / post-v1.0 (item 6 fonts RESOLVED) |

## Accumulated Context

### Decisions logged

- D-001: Hermes foundation used directly — locked
- D-002: Audit-first runtime — locked
- D-003: SQLite/WAL/FTS5/sqlite-vec MVP datastore — locked
- D-004: LLM Wiki first-class runtime — locked
- D-005: Rust-first native, no Electron — locked
- D-006: WebUI framework — SvelteKit/Svelte 5 with adapter-static — locked (2026-06-06)
- D-007: CRM after mission/run/audit/wiki/cockpit — locked
- D-008: Skills classified before shipping — locked
- D-009: STT/TTS/overlay after runtime loop — locked
- D-010: CRM/Pulse/Channels research intake complete — 14 open questions captured, research brief written
- D-011: Canonical repo layout ratified — locked
- D-012: Pydantic v2 schema source of truth — locked
- D-013: Language strategy — Prototype in Python, Cement in Rust — locked direction, open timing
- D-014: Optional turbovec local semantic retrieval spike — accepted for spike, not core adoption
- D-015: FreeLLMAPI sidecar gateway — accepted for integration spike; sidecar first, managed sidecar second, fork/vendor last
- D-016: Terax AI — accepted as Rust-native desktop cockpit reference pillar (not vendor); native shell direction locked (now Phase 10/v1.1 per D-021 §1 — Phase 8 is web-first)
- D-017: AI router connector strategy — ATLAS model_registry + model_router, FreeLLMAPI sidecar-first, task-class routing, audit-event metadata for all LLM calls
- D-018: Hermes-as-foundation L2/ATLAS harness strategy — evolve Hermes foundation; do not route through stock Hermes; foundation transformation not wrapper
- D-019: Diverse efficient agent memory framework — 6 memory layers + policy-governed memory router; Phase 6 delivers Layer 2+3; Phase 7 memory API; Phase 8 memory inspection surface
- D-019 impl (06-01): MemoryProvenance frozen model + 0002 migration are the schema foundation for all Phase 6 wiki service plans
- D-019 impl (06-02): atlas-wiki package scaffold with sqlite-vec/fastembed in optional [semantic] group only; no [project.scripts]; wiki_app registered into atlas-runtime via try/except import
- D-019 impl (06-03): wiki service core implemented via TDD — ingest/update/search/lint + provenance service write_provenance/get_provenance; 84% coverage; all WIKI-01..05 + AUDIT-03 satisfied
- D-019 impl (06-04): provenance_service.py verified complete via dedicated 4-test suite; 100% branch coverage; T-06-10 (invalid layer bypass) confirmed mitigated by Pydantic-first guard
- D-019 impl (06-05): wiki CLI sub-app wired via TDD; 6 CLI tests pass; atlas_runtime CLI extended with try/except import; FTS5 hyphen-query bug auto-fixed (Rule 1)
- D-019 impl (06-06): Phase 6 coverage gate passed at 81% (26 wiki + 33 core + 44 runtime tests green); graph memory Layer 4 design questions documented in GRAPH_MEMORY_RESEARCH_NOTES.md — no implementation; SQLite adjacency list (Option A) leading candidate for v2.0
- D-019 impl (06-FINAL): Phase 6 VERIFIED 2026-06-08 — 8/8 deliverables confirmed, 87.54% coverage (31 tests), 06-VERIFICATION.md written; coverage gap fix: CLI result-display loops, ValueError path, factory types now covered
- D-020: Twenty CRM adopted as external self-hosted service pillar — Docker Compose sidecar; ATLAS integrates via Core API, Metadata API, MCP server, webhooks; AGPL-3.0 sidecar-only (no copyleft obligation); CRM/Pulse features land post-Phase 8; D-007 CRM-after-cockpit ordering preserved
- License confirmation (Phase 4.5): all four reference pillars confirmed permissive — Terax Apache-2.0, Odysseus MIT, Hermes MIT, FreeLLMAPI MIT. No copyleft obligation.
- D-022 (2026-06-10): Rust-first cementation policy — resolves D-013 open timing; Phase 7 gateway is Rust (axum + rusqlite, first native/atlas-core-rs crate; reads direct SQLite, writes via `atlas` CLI contract, SSE via rowid poll); Python confined to Hermes foundation surface + LLM adapters + scripts; L0–L5 cementation ladder ends with Rust harness core strangling the Python agent loop (v2.x); budgets locked (CLI <100ms/<50MB, daemon <80MB idle, binary <20MB)
- D-008 satisfied (2026-06-15, Phase 9): `docs/imports/SKILL_INVENTORY.md` classifies ~266 skills across 7 source groups. ATLAS Core Pack = 7 credential-free public-safe skills; Developer Operator Pack = ~18 opt-in; L2 Systems Pack = 9 l2-internal/personal-private (public_safe: false). Release blockers logged: `red-teaming/godmode` + `inference/obliteratus` ship in the vendored *default* tree (must quarantine before public distribution); `l2-mind`/`vault-scan` never ship. GSD classified external-reference (build framework, not shipped).
- D-021 (2026-06-10): v1.0 sequencing + branding consolidation — Phase 8 web-first (native shell → Phase 10/v1.1); canonical phase numbering (9 skills, 10 native shell, 11 CRM/Twenty, 12 Pulse); memory framework = 6 layers (AGENT_MEMORY_FRAMEWORK_STRATEGY.md canonical); Twenty = external relationship system of record, Layer 4 graph = local derived index referencing Twenty by ID; Terax reuse architecture-level only; FreeLLMAPI fork triggers defined (2-of-4 criteria); two-layer branding policy (L2/ATLAS brand = experience layer + vendored Hermes-derived foundation; sidecars stay pinned upstream unbranded); Hermes vendored to foundation/atlas-hermes with ATTRIBUTION + DIVERGENCE_LOG (D-018 implementation start)

### Known blockers

- ~~VS Build Tools missing~~ RESOLVED 2026-06-11: Build Tools C++ workload installed; `cargo build -p atlas-gateway` green (debug + release). Release binary 2.53 MB (<20 MB D-022 budget). `/health` verified live on 127.0.0.1:8484 for both profiles.
- No container engine installed (verified 2026-06-11) — blocks `setup_twenty.ps1 up`, not the fetch (already validated: official compose pinned at v2.1.0 with generated secrets in gitignored infra/compose/twenty/). Preferred engine is now Podman (daemonless, no-bloat — operator install: `winget install RedHat.Podman`); Docker Desktop is the fallback. Script auto-detects podman → docker.

### New candidate spikes

- 2026-06-07: FreeLLMAPI integration spike report added at `docs/research/FREELLMAPI_INTEGRATION_SPIKE_2026-06-07.md`. Closed-env mock provider and real Kilo keyless provider smoke tests passed. Recommendation: sidecar OpenAI-compatible free-tier gateway first; consider Phase 4.5 / Phase 5 routing integration, not direct vendoring.

### Pending todos

- [x] Task 2: Clone Hermes at SHA e8b9369a9… into _EXTERNAL_REPOS/hermes-agent, secret-scan CLEAN (Phase 1 ✅)
- [x] Task 3: docs/research/HERMES_FOUNDATION_AUDIT.md written, 10 surface rows, YES verdict (Phase 1 ✅)
- [x] Task 4: docs/imports/L2_ATLAS_MODULE_EXTRACTION_PLAN.md written, 6 modules classified (Phase 1 ✅)
- [x] Task 6: packages/atlas-core/atlas_core/schemas/core.py — 7 frozen Pydantic v2 models, 33 tests green (Phase 2 ✅)
- [x] Task 7: infra/migrations/0001_core.sql — 7 tables, FTS5, WAL (Phase 2 ✅)
- [x] Task 8: WEBUI_STACK_SPIKE.md + NATIVE_APP_STRATEGY patch + D-006 locked SvelteKit (Phase 3 ✅ e71dbe3)
- [x] Task 9: CRM_PULSE_CHANNELS_DEEP_DIVE.md — 14 open questions, MVP boundary, research brief (Phase 3 ✅ 68039e5)
- [x] Task 10: Phase-close update STATE/RISKS/decisions (Phase 3 ✅)

### Hermes pin (verified 2026-06-04)

- Upstream: https://github.com/NousResearch/hermes-agent.git
- SHA: e8b9369a9d2df36139a5055cae3ed3c15691e03e
- License: MIT
- Version: 0.14.0 (tag v2026.5.16-1302-ge8b9369a9)
- CRITICAL: Never vendor C:/Users/Davi/AppData/Local/hermes/hermes-agent — contains secrets/state

### Coverage fix (2026-06-04)

RUNTIME-04 was previously listed in both Phase 4 and Phase 5 in the draft ROADMAP.md.
Resolution: RUNTIME-04 ("completed Run shows final status, timestamps, summary") is owned by Phase 5 (Mission & Run Lifecycle) — it is the completion outcome of the state machine, not an audit bus primitive.
Phase 4 coverage updated to: RUNTIME-03, AUDIT-01, AUDIT-02 only.
Phase 7 previously claimed COCKPIT-01 (partial) and RUNTIME-01 (partial) — these were removed; Phase 7 owns no v1 REQ-IDs (infrastructure phase enabling Phase 8).
Final count: 34 REQ-IDs total, all mapped, no duplicates.

## Phase History

| Phase | Name | Status | Completed |
|---|---|---|---|
| — | Project setup + research | Done | 2026-06-04 |
| — | D-011/D-012 ratification | Done | 2026-06-04 |
| — | Hermes pin (Task 1) | Done | 2026-06-04 |
| — | Roadmap finalization + phase dirs | Done | 2026-06-04 |
| 1 | Hermes Foundation Clone & Extension Audit | Done | 2026-06-05 |
| 2 | Core Domain Schemas & SQLite Migration | Done | 2026-06-06 |
| 3 | Research Closure (WebUI Spike + CRM Intake) | Done | 2026-06-06 |
| 4 | ATLAS Event Bus & Audit Core | Done | 2026-06-07 |
| 5 | Mission & Run Lifecycle | Done | 2026-06-08 |
| 6 | LLM Wiki Runtime | Done | 2026-06-08 |
| 7 | API Gateway (Rust) | Done | 2026-06-11 |
| 8 | WebUI Operator Cockpit | Done | 2026-06-12 |
| 8.5 | State cleanup + ownership + missing tests | Done | 2026-06-14 |
| 9 | Skill Inventory & Classification | Done | 2026-06-15 |
| 9.5 | v1.0 Public Hardening & Manual Acceptance | Executed (UAT pending) | 2026-06-15 |

## Performance Metrics

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 08-cockpit P05 | 25m | 2 tasks | 6 files |
| Phase 08-cockpit P06 | 90min | 2 tasks | 4 files |

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
- Visual CLI inspection guide added: `docs/operations/CLI_VISUAL_MANUAL.md`
