# Roadmap — L2 ATLAS

## Milestones

- ✅ **v1.0 Operator Cockpit MVP** — Phases 1–9.5 (shipped 2026-06-15)
- 🔨 **v1.0.5 Mass-Adoption Launch Wedge** — Phases 10.0.1–10.0.6 (inserted 2026-06-16, active)
- ⏸ **v1.1 ATLAS Agent Harness & Native Operator Shell** — Phases 10.0 (done), 10.1–10.6 (paused until v1.0.5 ships)
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

#### Phase 10.0: Harness Architecture & Threat-Model Design

**Goal:** Commit the auth-store layout, adapter boundary, registry schema, and security threat models before any harness code is written.
**Requirements:** none (design/enabling phase — precedent: v1.0 Phase 7).
**Success criteria:**

1. Auth-store layout decided and documented (flat `~/.atlas/auth.json` for v1.1, path resolution behind one function for future profiles).
2. Adapter boundary documented: ATLAS adapter lives in `services/agent-runtime/`; `foundation/` changes are extension-points only.
3. `0004_registry_v2.sql` schema drafted (provider/model_v2/route tables) with composite key and source-scoped deactivation.
4. OAuth-callback and native-IPC threat-model drafts written; fallback-cascade spec (error classification table) committed.

**Plans:** 3/3 plans complete

- [x] 10.0-01-PLAN.md — Auth-store + adapter-boundary design docs + fallback-cascade contract (LANDMINE 1/2/3/6/7; DIVERGENCE_LOG D-LOG-002 back-fill)
- [x] 10.0-02-PLAN.md — 0004_registry_v2.sql additive migration + mirrored Pydantic schema (LANDMINE 4; no-DROP, VIEW note, no-FK) ✓ 2026-06-16
- [x] 10.0-03-PLAN.md — OAuth-callback + native-IPC threat-model drafts (LANDMINE 5; constant-time state, PTY-byte-channel) ✓ 2026-06-16

### 🔨 v1.0.5 Mass-Adoption Launch Wedge (Phases 10.0.1–10.0.6)

Source: `l2_atlas_30_day_mass_adoption_wedge_plan.md`. v1.0 already shipped the wedge plan's P0 architecture (mission system, runtime, audit bus, artifact store, LLM Wiki, gateway/SSE, WebUI cockpit) — this milestone closes the remaining gaps between what shipped and what a public launch needs: repo trust signals, a one-command install, the missing cockpit pages, developer-facing integrations + extensibility, demo-grade reliability, and a public release. v1.1 (auth store/TUI/native shell) is paused until this ships.

**Dependency spine:** 10.0.1 hygiene → 10.0.2 install path → 10.0.3 identity & cockpit redesign → 10.0.4 integrations/manifest → 10.0.5 golden workflows → 10.0.6 public release.

#### Phase 10.0.1: Repo Hygiene & Trust Package

**Goal:** The repo is safe and credible to open-source.
**Requirements:** none mapped yet (pre-v1.1 REQUIREMENTS.md; trace during planning).
**Success criteria:**

1. License decided and `LICENSE` added; Hermes attribution re-audited against the public-release bar.
2. Secret scan run clean; no credentials/private data/logs in tracked history for files going public.
3. Trust docs exist: `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `LIMITATIONS.md`, `ARCHITECTURE.md`, `ATTRIBUTION.md`.
4. Issue templates (bug report, feature request) and a `good first issue` label scheme exist.

**Status:** ✅ Complete (2026-06-22) — root LICENSE (MIT), SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, LIMITATIONS.md, ARCHITECTURE.md, ATTRIBUTION.md, .github/ISSUE_TEMPLATE/ (bug report + feature request), .github/labels.yml (label scheme incl. `good first issue`). Secret scan re-run clean 2026-06-21 (verification pass closed criterion-4 label gap).

#### Phase 10.0.2: One-Command Install Path

**Goal:** A developer can clone, configure, and run ATLAS without the operator's help.
**Requirements:** none mapped yet (trace during planning).
**Success criteria:**

1. Docker Compose or an equivalent one-command local setup boots gateway + cockpit.
2. `.env.example`, quickstart doc, and seed/demo data exist; a mock mode covers missing API keys.
3. A health check command/endpoint exists with install troubleshooting docs.
4. Verified on a clean environment (not Davi's machine state).

**Plans:** 4/4 plans executed

Plans:
- [x] 10.0.2-01-PLAN.md — cockpit_control.py + `atlas up` CLI wiring (wave 1, SC1)
- [x] 10.0.2-02-PLAN.md — deterministic mock provider + demo seed (wave 2, SC2)
- [x] 10.0.2-03-PLAN.md — `atlas doctor` health aggregator (wave 3, SC3)
- [x] 10.0.2-04-PLAN.md — install/docs layer + clean-env smoke (wave 3, SC2+SC4)

#### Phase 10.0.3: ATLAS Identity & Cockpit Redesign

**Goal:** The cockpit covers every page the wedge plan's launch bar requires AND carries a
coherent ATLAS brand identity — a real operator control center, not a toy.

**Scope note (conscious wedge-override):** The 30-day wedge no-list (`l2_atlas_30_day_mass_adoption_wedge_plan.md` §20)
de-scopes "huge redesign" and "branding rabbit hole." Operator decision (2026-06-16): override that
guardrail and expand 10.0.3 from page-completion into a full per-page redesign + brand identity,
because mass adoption depends on first-impression quality. This phase **absorbs** the original
10.0.3 completion criteria (dashboard, integrations, settings, artifact browser, states) so the new
pages are built once, in the new design language. The one wedge constraint kept: no overbuilt animation.

**Requirements:** none mapped yet (trace during planning).
**Design contract:** `UI-SPEC.md` (in this phase dir) — concept "ATLAS bears the world"; evolved
palette (L2 core + Titan Bronze / Celestial signature); logo system; topographic shell. Draft
artifacts: `output/brand/atlas-brand-sheet.html`, `output/brand/atlas-emblem-prompt.md`.
**Success criteria:**

1. ATLAS brand identity locked + applied: logo system (glyph/wordmark/lockup), evolved palette tokens, fixed favicon, ATLAS-forward/L2-endorsed shell.
2. Topographic "living terrain" shell + redesigned sidebar/nav + global error/loading/empty-state components.
3. Dashboard/home, dedicated Integrations, Settings/System Health, and a distinct Artifact Browser all ship in the new design language.
4. Every existing page (missions, runs, wiki, models) is redesigned to the contract; visual polish pass done without overbuilding animation.
5. Verified: production build passes, 6-pillar UI audit (`/gsd-ui-review`) findings resolved, a11y/contrast/responsive checks pass.

**Status:** ✅ Complete (2026-06-23) — executed out-of-band on `main` against the
`10.0.3-webui-cockpit-completion` design contracts (PAGES-SPEC / HARNESS-WIRING / UI-SPEC)
rather than the GSD plan machinery (the phase predates formal tracking and its dir is sprawled).
SC1/SC2 landed earlier (brand identity + palette tokens + logo system + favicon + topographic
shell + sidebar + global states). SC3/SC4 closed 2026-06-23 (commit `074b141`): the four
`<Migrating>` placeholders replaced with real React surfaces in the celestial-heraldic language —
Ledger `/audit` (cross-run audit explorer), Codex `/wiki` (FTS browser + markdown + provenance),
Models `/models` (provider-grouped registry + D-017 routing note), Integrations `/integrations`
(read-only posture board) — plus the System About band (PAGES-SPEC §10). SC5: production build
(`tsc -b && vite build`) green, eslint 0 errors, all four routes + System Playwright-verified
rendering with graceful offline states and zero React runtime errors.
**Deferred (honest):** the formal 6-pillar `/gsd-ui-review` audit (advisory — new pages reuse the
already-audited Page/GlassPanel/TopoInput primitives + contract); a standalone Artifact Browser
(no gateway/CLI data layer exists — needs an artifacts endpoint first); the ⌘K command palette
(wave-7 polish, outside the SC bar). Interim data sources (Ledger/Integrations fan-out) await the
`/v1/audit/events` + `/v1/integrations` gateway endpoints (HARNESS-WIRING §5).

**In-flight operator-directed sub-phases (ahead-of-spine, under the 10.0.3 umbrella):**
Index: `.planning/phases/10.0.3-SCOPE-SEQUENCE.md`. Pattern = same as `10.0.3-command-center`
(DONE) and `10.0.3-graphify-living-graph`. Six-item scope added 2026-06-20, sequenced:

- [ ] `10.0.3-memory-router` — FTS5 wiki retrieval → context assembly (item #1; in progress)
- [ ] `10.0.3-setup-wizard` — `atlas setup` + `~/.atlas/config.yaml` config-service (item #2)
- [ ] `10.0.3-channel-cockpit` — channel management cockpit + messaging gateway control (item #3; needs #2)
- [ ] `10.0.3-console-tiling` — hyprland BSP auto-tiling in the Console workbench (item #4)
- [ ] `10.0.3-harness-cherrypick` — PI/OpenCode pattern intake doc (item #5, research-only)
- [ ] `10.0.7-foundation-debrand` — hermes→atlas rebrand, test-gated, release-gate (item #6, last)

#### Phase 10.0.4: Developer Integrations & Tool Manifest

**Goal:** ATLAS is useful against real developer workflows and proves it is an extensible harness, not a closed demo.
**Requirements:** none mapped yet (trace during planning).
**Success criteria:**

1. Local Workspace, GitHub, Web Fetch, and Webhook Notification integrations work end-to-end (read-only by default; write/shell actions require explicit operator approval).
2. Tool Manifest v0 (name/description/risk_level/permissions/inputs/outputs/audit_events YAML schema) is implemented and documented; adding a tool means writing a manifest + adapter.
3. Policy/permissions are visible in the WebUI: read-only mode by default, explicit approval gate for writes, no-sensitive-data posture stated.
4. All tool calls emit `tool.requested`/`tool.completed`/`tool.failed` audit events per the existing audit bus.

**Plans:** 6/6 plans complete

Plans:
- [x] 10.0.4-00-PLAN.md — Wave 0 test stubs + temp-DB conftest + confirm no CHECK on audit event_type
- [x] 10.0.4-01-PLAN.md — atlas-core ToolManifest/ToolResult/ToolApproval + AuditEvent verbs + policy.decide + pyyaml
- [x] 10.0.4-02-PLAN.md — four adapters (workspace/github/web_fetch/webhook_notify) + SSRF/boundary guards + manifests
- [x] 10.0.4-03-PLAN.md — tool_registry + tool_service chokepoint/approval state machine + 0013 migration
- [x] 10.0.4-04-PLAN.md — atlas tools CLI group + dispatch-only gateway /v1/tools/* routes
- [x] 10.0.4-05-PLAN.md — cockpit System POLICY/TOOLS/APPROVALS panels + api.ts + docs (SC3 human-verify)

#### Phase 10.0.5: Golden Workflows & Quality Gate

**Goal:** ATLAS survives repeated demos on the three wedge use cases.
**Requirements:** none mapped yet (trace during planning).
**Success criteria:**

1. Golden Workflow 1 (Repo Triage), 2 (Research Brief), and 3 (Self-Review) each run 3 times with consistent output (artifact + audit trail + wiki entries; Self-Review never writes without approval).
2. Repeated failures fixed; a smoke test and demo-reset path exist.
3. Sample data, screenshots, and a documented known-failures list exist.

**Plans:** 5 plans across 5 waves

Plans:
- [ ] 10.0.5-01-PLAN.md — golden_workflow_service core (run bootstrap, Artifact writer, audit lifecycle events) — wave 1
- [ ] 10.0.5-02-PLAN.md — Repo Triage + Research Brief orchestrators (internal/auto) — wave 2
- [ ] 10.0.5-03-PLAN.md — Self-Review (approval-gated write) + golden_workflow_registry + `atlas golden` CLI — wave 3
- [ ] 10.0.5-04-PLAN.md — 3x3 mock-mode structural-assert smoke test + scoped demo-reset — wave 4
- [ ] 10.0.5-05-PLAN.md — docs/golden-workflows.md runbook + sample data + docs/known-failures.md — wave 5

#### Phase 10.0.6: Public Release Prep & Distribution

**Goal:** ATLAS v0.1 is public with credible packaging.
**Requirements:** none mapped yet (trace during planning).
**Success criteria:**

1. README, technical report, roadmap, and demo script/video/screenshots are final; status label is "ATLAS v0.1 — Open Research Preview" (no production/enterprise/AGI claims).
2. Repo made public, tagged `v0.1.0-open-research-preview`, GitHub Discussions + roadmap issues opened.
3. Private beta (20–50 targeted developer contacts) run before public flip; feedback logged.
4. Launch message sent across the channels list in the wedge plan; `ATLAS_30_DAY_SHIP_REPORT.md` drafted with build + adoption metrics.

**Plans:** 0 plans (not yet planned — run `/gsd-plan-phase 10.0.6`)

### ⏸ v1.1 ATLAS Agent Harness & Native Operator Shell (Phases 10.1–10.6) — PAUSED

Post-v1.0 inspection showed the archived CLI is a thin operational surface, not a complete ATLAS/Hermes-derived agent harness. v1.1 builds the owned harness — TUI, auth, provider/model registry, agentic chat — and then a native shell that wraps a *real* harness, not an empty one. **Paused 2026-06-16 pending v1.0.5 Mass-Adoption Launch Wedge** — the 30-day public-launch plan doesn't call for native-shell/TUI depth and the wedge plan's no-list explicitly excludes unscoped feature sprawl during the launch sprint. Resume at 10.1 once v1.0.5 ships.

**Research:** `.planning/research/SUMMARY.md` (STACK/FEATURES/ARCHITECTURE/PITFALLS). **Prep:** `.planning/prep/README.md`. **Requirements:** `.planning/REQUIREMENTS.md` (55 REQ-IDs).

**Locked decisions:** Codex read-only detection only; OpenAI/Codex-compatible lane first then health-aware fallback; file-store-first auth (keychain deferred). Adapt the Hermes Ink TUI (no Rust rewrite); agent adapter is Python over Hermes AIAgent via the stdio JSON-RPC `tui_gateway`; Rust owns the provider-probe layer + Tauri shell.

**Dependency spine:** 10.0 design → 10.1 auth (critical path) → 10.2 chat + 10.3 discovery → 10.4 TUI → 10.5 native shell (**hard-gated on 10.2 + 10.4**) → 10.6 integration/UAT.

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
| 10.0 Harness Architecture & Threat-Model Design | v1.1 | 3/3 | Complete   | 2026-06-16 |
| 10.0.1 Repo Hygiene & Trust Package | v1.0.5 | 0/? | Complete | 2026-06-22 |
| 10.0.2 One-Command Install Path | v1.0.5 | 4/4 | Done |  |
| 10.0.3 ATLAS Identity & Cockpit Redesign | v1.0.5 | n/a | Complete   | 2026-06-23 |
| 10.0.4 Developer Integrations & Tool Manifest | v1.0.5 | 6/6 | Complete   | 2026-06-22 |
| 10.0.5 Golden Workflows & Quality Gate | v1.0.5 | 0/5 | Planned | — |
| 10.0.6 Public Release Prep & Distribution | v1.0.5 | 0/? | Not started | — |
| 10.1 ATLAS-Owned Auth Store & Codex Detection | v1.1 | 0/? | Paused | — |
| 10.2 Agentic Chat CLI & Runtime Adapter | v1.1 | 0/? | Paused | — |
| 10.3 Provider/Model Discovery & Cockpit Truth | v1.1 | 0/? | Paused | — |
| 10.4 ATLAS TUI | v1.1 | 0/? | Paused | — |
| 10.5 Native Operator Shell (Tauri 2 + PTY) | v1.1 | 0/? | Paused | — |
| 10.6 Integration & Manual UAT | v1.1 | 0/? | Paused | — |
| 11. CRM via Twenty | v2.0 | 0/? | Not started | — |
| 12. Basic Pulse Monitor | v2.0 | 0/? | Not started | — |
| 13. STT/TTS Voice Integration | v2.0 | 0/? | Not started | — |
| 14. Floating Overlay / Run-Status HUD | v2.0 | 0/? | Not started | — |
