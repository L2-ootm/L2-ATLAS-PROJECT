# Roadmap — L2 ATLAS

## Milestones

- ✅ **v1.0 Operator Cockpit MVP** — Phases 1–9.5 (shipped 2026-06-15)
- 🔨 **v1.1 ATLAS Agent Harness & Native Operator Shell** — Phases 10.0–10.6 (scoped 2026-06-15)
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

### 🔨 v1.1 ATLAS Agent Harness & Native Operator Shell (Phases 10.0–10.6)

Post-v1.0 inspection showed the archived CLI is a thin operational surface, not a complete ATLAS/Hermes-derived agent harness. v1.1 builds the owned harness — TUI, auth, provider/model registry, agentic chat — and then a native shell that wraps a *real* harness, not an empty one.

**Research:** `.planning/research/SUMMARY.md` (STACK/FEATURES/ARCHITECTURE/PITFALLS). **Prep:** `.planning/prep/README.md`. **Requirements:** `.planning/REQUIREMENTS.md` (55 REQ-IDs).

**Locked decisions:** Codex read-only detection only; OpenAI/Codex-compatible lane first then health-aware fallback; file-store-first auth (keychain deferred). Adapt the Hermes Ink TUI (no Rust rewrite); agent adapter is Python over Hermes AIAgent via the stdio JSON-RPC `tui_gateway`; Rust owns the provider-probe layer + Tauri shell.

**Dependency spine:** 10.0 design → 10.1 auth (critical path) → 10.2 chat + 10.3 discovery → 10.4 TUI → 10.5 native shell (**hard-gated on 10.2 + 10.4**) → 10.6 integration/UAT.

#### Phase 10.0: Harness Architecture & Threat-Model Design

**Goal:** Commit the auth-store layout, adapter boundary, registry schema, and security threat models before any harness code is written.
**Requirements:** none (design/enabling phase — precedent: v1.0 Phase 7).
**Success criteria:**

1. Auth-store layout decided and documented (flat `~/.atlas/auth.json` for v1.1, path resolution behind one function for future profiles).
2. Adapter boundary documented: ATLAS adapter lives in `services/agent-runtime/`; `foundation/` changes are extension-points only.
3. `0004_registry_v2.sql` schema drafted (provider/model_v2/route tables) with composite key and source-scoped deactivation.
4. OAuth-callback and native-IPC threat-model drafts written; fallback-cascade spec (error classification table) committed.

**Plans:** 3 plans (Wave 1, parallel — design docs are independent).Plans:

- [ ] 10.0-01-PLAN.md — Auth-store + adapter-boundary design docs + fallback-cascade contract (LANDMINE 1/2/3/6/7; DIVERGENCE_LOG D-LOG-002 back-fill)
- [x] 10.0-02-PLAN.md — 0004_registry_v2.sql additive migration + mirrored Pydantic schema (LANDMINE 4; no-DROP, VIEW note, no-FK) ✓ 2026-06-16
- [x] 10.0-03-PLAN.md — OAuth-callback + native-IPC threat-model drafts (LANDMINE 5; constant-time state, PTY-byte-channel) ✓ 2026-06-16

#### Phase 10.1: ATLAS-Owned Auth Store & Codex Detection

**Goal:** A secure, ATLAS-owned credential store with read-only Codex detection and proven no-leak/no-mutation guarantees.
**Requirements:** AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07, AUTH-08, CLI-06, SEC-01, SEC-02, SEC-03, SEC-05
**Success criteria:**

1. `atlas auth add/list/status/remove/doctor` work against `~/.atlas/auth.json` for at least one real provider.
2. Concurrent-writer test produces valid JSON with no lost write; auth file is current-user-only.
3. `atlas auth status` and all logs/audit pass the redaction grep (no `sk-`/`Bearer `/`eyJ`).
4. `~/.codex/auth.json` is byte-identical (mtime + hash) after every auth/discovery command.

#### Phase 10.2: Agentic Chat CLI & Runtime Adapter

**Goal:** A credible one-shot and interactive agent chat over Hermes AIAgent with audit-safe calls and an honest fallback cascade.
**Requirements:** CLI-01, CLI-02, CLI-03, AGNT-01, AGNT-02, AGNT-03, AGNT-04, AGNT-05, AGNT-06, AUD-01, AUD-02
**Success criteria:**

1. `atlas chat -q "ping"` returns a real response or precise auth remediation; `atlas chat` runs interactively and exits cleanly.
2. Injecting a 401 on the primary provider halts with an AUTH_ERROR (no silent cascade); a transient failure cascades and emits a `provider_fallback` audit event; the provider actually used is surfaced.
3. The audit JSONL for a chat contains `model_call_start` + `model_call_end` with a non-null run_id; tool calls require approval (deny-by-default in `-q`).
4. `foundation/` diff is extension-points only (DIVERGENCE_LOG reviewed); transcripts are redaction-filtered before persistence.

#### Phase 10.3: Provider/Model Discovery & Cockpit Truth

**Goal:** A real provider/model registry with honest status that the CLI and cockpit both reflect.
**Requirements:** CLI-04, CLI-05, PROV-01, PROV-02, PROV-03, PROV-04, MOD-01, MOD-02, MOD-03, MOD-04, MOD-05, MOD-06, UX-02
**Success criteria:**

1. `atlas models discover` merges seeded + auth-store + local-sidecar + read-only-external sources; `atlas models list --all` shows source/status/auth_status/last_seen.
2. Two consecutive discover runs leave row count stable and `first_seen` unchanged; stopping a sidecar flips its models to `offline` (source-scoped).
3. `atlas providers list/status/doctor` and `atlas doctor` report honest health with actionable remediation; exit codes are correct.
4. The cockpit Models page renders the live registry (source/status/auth), not only seeded rows.

#### Phase 10.4: ATLAS TUI

**Goal:** An ATLAS-branded terminal UI over the `tui_gateway` that can hold an auditable agent session.
**Requirements:** TUI-01, TUI-02, TUI-03, TUI-04, TUI-05, TUI-06, TUI-07, TUI-08, TUI-09, UX-01
**Success criteria:**

1. `atlas` / `atlas tui` opens an ATLAS-branded TUI with a model/auth status bar and no Hermes/Codex branding leaks.
2. A prompt streams a response with inline tool-call activity and a `/help` command surface.
3. Missing auth/model is surfaced before the first send; dangerous tool calls show a blocking approval prompt.
4. Ctrl-C exits cleanly and the session can be resumed.

#### Phase 10.5: Native Operator Shell (Tauri 2 + PTY)

**Goal:** A Tauri 2 native shell that hosts the cockpit and a PTY running the real `atlas tui`, with a capability-scoped IPC boundary. **Hard-gated on 10.2 + 10.4.**
**Requirements:** NAT-01, NAT-02, NAT-03, NAT-04, NAT-05, SEC-04
**Success criteria:**

1. The Tauri 2 shell (no Electron) launches, embeds the cockpit from a local bundle, and makes no external calls except explicit integrations.
2. The PTY pane runs `atlas tui` (not bash/cmd) and can complete an agentic chat from inside the shell.
3. IPC is an explicit allowlist; the PTY accepts keystrokes, not command strings; a native-IPC threat-model document enumerates every command.
4. The shell surfaces auth/model readiness and routes remediation to the CLI/TUI.

#### Phase 10.6: Integration & Manual UAT

**Goal:** Everything wired end-to-end, documented, and accepted with no secret leakage.
**Requirements:** DOC-01, DOC-02
**Success criteria:**

1. Operator runbooks exist for auth, TUI, models, and the native shell.
2. A v1.1 manual UAT guide covers TUI, one-shot chat, auth, model discovery, cockpit, and native shell, and is executed.
3. UAT screenshots/terminal captures pass a credential-pattern review before commit.
4. v1.1 archive verdict recorded.

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
| 10.0 Harness Architecture & Threat-Model Design | v1.1 | 3/3 | Complete | 2026-06-16 |
| 10.1 ATLAS-Owned Auth Store & Codex Detection | v1.1 | 0/? | Not started | — |
| 10.2 Agentic Chat CLI & Runtime Adapter | v1.1 | 0/? | Not started | — |
| 10.3 Provider/Model Discovery & Cockpit Truth | v1.1 | 0/? | Not started | — |
| 10.4 ATLAS TUI | v1.1 | 0/? | Not started | — |
| 10.5 Native Operator Shell (Tauri 2 + PTY) | v1.1 | 0/? | Not started | — |
| 10.6 Integration & Manual UAT | v1.1 | 0/? | Not started | — |
| 11. CRM via Twenty | v2.0 | 0/? | Not started | — |
| 12. Basic Pulse Monitor | v2.0 | 0/? | Not started | — |
| 13. STT/TTS Voice Integration | v2.0 | 0/? | Not started | — |
| 14. Floating Overlay / Run-Status HUD | v2.0 | 0/? | Not started | — |
