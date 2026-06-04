---
milestone: v1.0
name: Operator Cockpit MVP
status: in_progress
phase: 1
progress:
  phases_total: 9
  phases_complete: 0
  phases_in_progress: 1
last_updated: 2026-06-04
---

# STATE — L2 ATLAS

## Current Position

Phase: 1 — Hermes Foundation Clone & Extension Audit (in progress)
Plan: docs/plans/2026-06-04_CLAUDE_IMPLEMENTATION_START_PLAN.md (Tasks 2–4 map to this phase)
Status: Phase 1 active — Task 1 complete (Hermes pin recorded), Task 2 (fresh clone) next
Last activity: 2026-06-04 — GSD ingest-docs merge complete; REQUIREMENTS.md + ROADMAP.md created; Milestone v1.0 initialized

## Accumulated Context

### Decisions logged

- D-001: Hermes foundation used directly — locked
- D-002: Audit-first runtime — locked
- D-003: SQLite/WAL/FTS5/sqlite-vec MVP datastore — locked
- D-004: LLM Wiki first-class runtime — locked
- D-005: Rust-first native, no Electron — locked
- D-006: WebUI framework open (SvelteKit vs Next.js) — Phase 3 spike required
- D-007: CRM after mission/run/audit/wiki/cockpit — locked
- D-008: Skills classified before shipping — locked
- D-009: STT/TTS/overlay after runtime loop — locked
- D-010: CRM/Pulse/Channels research missing — Phase 3 intake required
- D-011: Canonical repo layout ratified — locked
- D-012: Pydantic v2 schema source of truth — locked

### Known blockers

None — all pre-build gates cleared (D-011/D-012 ratified, Hermes pinned, extraction plan framed).

### Pending todos

- [ ] Task 2: Clone Hermes fresh at SHA e8b9369a9… into _EXTERNAL_REPOS/hermes-agent, run secret-scan gate (Phase 1)
- [ ] Task 3: Write docs/research/HERMES_FOUNDATION_AUDIT.md (Phase 1)
- [ ] Task 4: Write docs/imports/L2_ATLAS_MODULE_EXTRACTION_PLAN.md (Phase 1)
- [ ] Task 6: Write packages/atlas-core/atlas_core/schemas/core.py (Phase 2)
- [ ] Task 7: Write infra/migrations/0001_core.sql (Phase 2)
- [ ] Task 8: Write docs/research/WEBUI_STACK_SPIKE.md + patch NATIVE_APP_STRATEGY (Phase 3)
- [ ] Task 9: Write docs/research/CRM_PULSE_CHANNELS_DEEP_DIVE.md (Phase 3)
- [ ] Task 10: Phase-close update STATE/RISKS/decisions (Phase 3 close)

### Hermes pin (verified 2026-06-04)

- Upstream: https://github.com/NousResearch/hermes-agent.git
- SHA: e8b9369a9d2df36139a5055cae3ed3c15691e03e
- License: MIT
- Version: 0.14.0 (tag v2026.5.16-1302-ge8b9369a9)
- CRITICAL: Never vendor C:/Users/Davi/AppData/Local/hermes/hermes-agent — contains secrets/state

## Phase History

| Phase | Name | Status | Completed |
|---|---|---|---|
| — | Project setup + research | Done | 2026-06-04 |
| — | D-011/D-012 ratification | Done | 2026-06-04 |
| — | Hermes pin (Task 1) | Done | 2026-06-04 |
| 1 | Hermes Foundation Clone & Extension Audit | In progress | — |
| 2 | Core Domain Schemas & SQLite Migration | Pending | — |
| 3 | Research Closure (WebUI Spike + CRM Intake) | Pending | — |
| 4 | ATLAS Event Bus & Audit Core | Pending | — |
| 5 | Mission & Run Lifecycle | Pending | — |
| 6 | LLM Wiki Runtime | Pending | — |
| 7 | API Gateway | Pending | — |
| 8 | WebUI Operator Cockpit | Pending | — |
| 9 | Skill Inventory & Classification | Pending | — |
