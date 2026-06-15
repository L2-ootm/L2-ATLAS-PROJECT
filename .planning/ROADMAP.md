# Roadmap — L2 ATLAS

## Milestones

- ✅ **v1.0 Operator Cockpit MVP** — Phases 1–9.5 (shipped 2026-06-15)
- 📋 **v1.1 Native Cockpit Shell** — Phase 10 (planned)
- 📋 **v2.0 CRM, Pulse & Voice** — Phases 11–14 (planned)

## Phases

<details>
<summary>✅ v1.0 Operator Cockpit MVP (Phases 1–9.5) — SHIPPED 2026-06-15</summary>

Closed the first operator loop: create mission → run through the ATLAS runtime
(vendored Hermes foundation) → capture audit trail → file to LLM Wiki → monitor in a
web cockpit. 34/34 requirements complete.

- [x] Phase 1: Hermes Foundation Clone & Extension Audit (4/4) — 2026-06-05
- [x] Phase 2: Core Domain Schemas & SQLite Migration (3/3) — 2026-06-06
- [x] Phase 3: Research Closure — WebUI Spike & CRM Intake (2/2) — 2026-06-06
- [x] Phase 4: ATLAS Event Bus & Audit Core (3/3) — 2026-06-07
- [x] Phase 4.5: FreeLLMAPI Sidecar Gateway (spike) — 2026-06-08
- [x] Phase 5: Mission & Run Lifecycle (4/4) — 2026-06-08
- [x] Phase 6: LLM Wiki Runtime (6/6) — 2026-06-08
- [x] Phase 7: API Gateway (Rust — atlas-gateway) — 2026-06-11
- [x] Phase 8: Operator Cockpit (web-first, native-portable) (6/6) — 2026-06-12
- [x] Phase 8.5: State Cleanup + Ownership + Missing Tests — 2026-06-14
- [x] Phase 9: Skill Inventory & Classification (1/1) — 2026-06-15
- [x] Phase 9.5: v1.0 Public Hardening & Manual Acceptance — 2026-06-15

Full detail: `.planning/milestones/v1.0-ROADMAP.md` ·
Requirements: `.planning/milestones/v1.0-REQUIREMENTS.md`

</details>

### 📋 v1.1 Native Cockpit Shell (planned)

- [ ] Phase 10: Native Cockpit Shell — Tauri 2/Rust shell wrapping the Phase 8 app;
  PTY/terminal pane, OS keychain, native approvals, IPC capability model, threat-model
  gate. Governed by `NATIVE_COCKPIT_STRATEGY.md` (D-021 §2).

### 📋 v2.0 CRM, Pulse & Voice (planned)

- [ ] Phase 11: CRM via Twenty (sidecar wiring, custom objects, webhooks, CRM panel — D-020/D-021)
- [ ] Phase 12: Basic Pulse Monitor
- [ ] Phase 13: STT/TTS Voice Integration
- [ ] Phase 14: Floating Overlay / Run-Status HUD

## Progress

| Phase | Milestone | Plans | Status | Completed |
|---|---|---|---|---|
| 1. Hermes Foundation Clone & Extension Audit | v1.0 | 4/4 | Complete | 2026-06-05 |
| 2. Core Domain Schemas & SQLite Migration | v1.0 | 3/3 | Complete | 2026-06-06 |
| 3. Research Closure — WebUI Spike & CRM Intake | v1.0 | 2/2 | Complete | 2026-06-06 |
| 4. ATLAS Event Bus & Audit Core | v1.0 | 3/3 | Complete | 2026-06-07 |
| 4.5 FreeLLMAPI Sidecar Gateway (spike) | v1.0 | — | Complete | 2026-06-08 |
| 5. Mission & Run Lifecycle | v1.0 | 4/4 | Complete | 2026-06-08 |
| 6. LLM Wiki Runtime | v1.0 | 6/6 | Complete | 2026-06-08 |
| 7. API Gateway (Rust) | v1.0 | — | Complete | 2026-06-11 |
| 8. Operator Cockpit | v1.0 | 6/6 | Complete | 2026-06-12 |
| 8.5 State Cleanup + Ownership + Tests | v1.0 | — | Complete | 2026-06-14 |
| 9. Skill Inventory & Classification | v1.0 | 1/1 | Complete | 2026-06-15 |
| 9.5 Public Hardening & Manual Acceptance | v1.0 | — | Complete | 2026-06-15 |
| 10. Native Cockpit Shell | v1.1 | 0/? | Not started | — |
| 11. CRM via Twenty | v2.0 | 0/? | Not started | — |
| 12. Basic Pulse Monitor | v2.0 | 0/? | Not started | — |
| 13. STT/TTS Voice Integration | v2.0 | 0/? | Not started | — |
| 14. Floating Overlay / Run-Status HUD | v2.0 | 0/? | Not started | — |
