---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Operator Cockpit MVP
status: executing
last_updated: "2026-06-07T22:22:45.697Z"
last_activity: 2026-06-07 -- Phase 04 planning complete
progress:
  total_phases: 9
  completed_phases: 2
  total_plans: 13
  completed_plans: 9
  percent: 22
---

# STATE — L2 ATLAS

## Current Position

Phase: 04
Next: Phase 4 — ATLAS Event Bus & Audit Core
Status: Ready to execute
Last activity: 2026-06-07 -- Phase 04 planning complete

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

### Known blockers

None — all pre-build gates cleared. All research closed. D-006 locked. Build phases (4–8) can proceed.

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
| 4 | ATLAS Event Bus & Audit Core | Pending | — |
| 5 | Mission & Run Lifecycle | Pending | — |
| 6 | LLM Wiki Runtime | Pending | — |
| 7 | API Gateway | Pending | — |
| 8 | WebUI Operator Cockpit | Pending | — |
| 9 | Skill Inventory & Classification | Pending | — |
