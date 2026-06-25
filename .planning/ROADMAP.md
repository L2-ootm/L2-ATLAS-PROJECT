# Roadmap — L2 ATLAS

## Milestones

- ✅ **v1.0 Operator Cockpit MVP** — Phases 1–9.5 (shipped 2026-06-15)
- ⏸ **v1.0.5 Mass-Adoption Launch Wedge** — Phases 10.0.1–10.0.6 (code/docs complete; outward release actions operator-gated)
- 🔨 **v1.1 ATLAS Agent Harness & Multi-Surface Workbench** — Phases 10.0 (done), 10.1–10.8 (resumed 2026-06-23)
- 📐 **v1.2 Provider Mesh & Runtime Interoperability** — milestone-local draft PM-01–PM-06; activates only after v1.1 is archived
- 🧪 **v1.3 Gated Self-Evolution Candidate** — milestone-local draft EV-01; preserved separately because its risk and promotion gates exceed v1.2
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

### ⏸ v1.0.5 Mass-Adoption Launch Wedge (Phases 10.0.1–10.0.6) — OPERATOR-GATED

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

**Plans:** 5/5 plans complete

Plans:
- [x] 10.0.5-01-PLAN.md — golden_workflow_service core (run bootstrap, Artifact writer, audit lifecycle events) — wave 1
- [x] 10.0.5-02-PLAN.md — Repo Triage + Research Brief orchestrators (internal/auto) — wave 2
- [x] 10.0.5-03-PLAN.md — Self-Review (approval-gated write) + golden_workflow_registry + `atlas golden` CLI — wave 3
- [x] 10.0.5-04-PLAN.md — 3x3 mock-mode structural-assert smoke test + scoped demo-reset — wave 4
- [x] 10.0.5-05-PLAN.md — docs/golden-workflows.md runbook + sample data + docs/known-failures.md — wave 5

#### Phase 10.0.6: Public Release Prep & Distribution

**Goal:** ATLAS v0.1 is public with credible packaging.
**Requirements:** none mapped yet (trace during planning).
**Success criteria:**

1. README, technical report, roadmap, and demo script/video/screenshots are final; status label is "ATLAS v0.1 — Open Research Preview" (no production/enterprise/AGI claims).
2. Repo made public, tagged `v0.1.0-open-research-preview`, GitHub Discussions + roadmap issues opened.
3. Private beta (20–50 targeted developer contacts) run before public flip; feedback logged.
4. Launch message sent across the channels list in the wedge plan; `ATLAS_30_DAY_SHIP_REPORT.md` drafted with build + adoption metrics.

**Status:** ⏸ DRAFTS COMPLETE / OPERATOR-GATED (2026-06-23). Per operator decision, executed
drafts-only — the outward-facing, irreversible actions are NOT performed autonomously.
- SC1 ✅ DONE: README final pass ("ATLAS v0.1 — Open Research Preview" label, accurate v0.1
  scope, explicit non-claims) + `docs/release/{TECHNICAL_REPORT,PUBLIC_ROADMAP,DEMO_SCRIPT}.md`.
  (Live demo screenshots/video deferred to the operator UAT step in the checklist.)
- SC2 ⛔ OPERATOR: make repo public, tag `v0.1.0-open-research-preview`, open Discussions + issues.
- SC3 ⛔ OPERATOR: private beta (20–50 devs) + feedback log; live demo screenshots.
- SC4 ⏸ DRAFT/OPERATOR: `docs/release/LAUNCH_MESSAGE.md` + `ATLAS_30_DAY_SHIP_REPORT.md` drafted
  (real build metrics; adoption metrics are operator-filled post-launch); sending is operator-gated.
- Handoff: `docs/release/RELEASE_CHECKLIST.md` enumerates every operator-gated action.

**Plans:** none (executed as a direct drafts-only pass, not via plan machinery — the remaining
SCs are human/operator actions, not codeable plans).

### 🔨 v1.1 ATLAS Agent Harness & Multi-Surface Workbench (Phases 10.1–10.8) — ACTIVE

v1.1 turns the existing ATLAS agent/runtime into one coherent operator workbench across
terminal and web surfaces. A third-party terminal project is used only as an implementation
and UX reference/donor; runtime code, packages, commands, configuration, storage paths,
environment variables, generated artifacts, and UI identity are ATLAS-native. Ethical
provenance and required notices remain in documentation.

There is **no donor-specific agent runtime**. The terminal and web clients use the same
ATLAS agent, Projects/Current Focus/mission/run model, context assembly, audit bus, policy,
configuration, and approval state.

**Research:** `.planning/research/SUMMARY.md`; `.kilo/ULTRAPLAN_ATLAS_TUI_HARNESS.md`.
**Requirements:** `.planning/REQUIREMENTS.md`.
**AI contract:** `.planning/phases/10.2-agent-contract-tool-context-intelligence/10.2-AI-SPEC.md`.

**Locked decisions (2026-06-23):**

- one ATLAS agent/runtime, many surfaces;
- donor TUI code is transformed into an ATLAS-owned surface, not wrapped as a branded binary;
- donor identity may appear only in attribution/license/design-history documentation;
- `~/.atlas/config.yaml` is the authoritative non-secret configuration store for every surface;
- every execution is bound to a surface session and a global or registered-project workspace;
- permission requests are actionable only from the surface session that initiated execution;
- system-prompt invariants are versioned and cache-stable; dynamic ATLAS context is separately
  budgeted, provenance-tagged, redacted, and replayable;
- the Brain knowledge graph becomes the retrieval spine for wiki/memory/relationship discovery,
  but weak retrieval must abstain rather than inject noise;
- native/Tauri shell work is deferred until the TUI/WebUI surface protocol is stable.

**Dependency spine:** 10.1 donor intake → 10.2 agent/tool/context contract → 10.3 shared
surface/workspace protocol → 10.4 global config control plane → 10.5 permission broker →
10.6 TUI → 10.7 WebUI agent/queue UX → 10.8 cross-surface UAT and cutover.

#### Phase 10.1: ATLAS TUI Harness Intake & Provenance

**Goal:** Extract and transform the useful terminal rendering, interaction, session, and
component patterns into an ATLAS-native codebase without importing a second agent/runtime,
provider system, config store, memory system, telemetry path, or product identity.
**Requirements:** INTAKE-01, INTAKE-02, INTAKE-03, INTAKE-04, INTAKE-05, SEC-01
**Success criteria:**

1. A source/license/component inventory classifies every donor module as adopt, rewrite, or
   reject; prohibited runtime/provider/storage/telemetry modules are absent from shipped code.
2. Runtime grep and package inspection find no donor product names, commands, env vars, config
   keys, state paths, URLs, analytics, update, or share endpoints outside approved documentation.
3. ATLAS attribution and third-party notices identify provenance and retained licenses without
   implying original authorship.
4. Dependency, binary/bundle size, cold/warm startup, idle memory, and file-count baselines are
   recorded with explicit v1.1 budgets.

**Plans:** 3/3 complete

- [x] 10.1-01-PLAN.md — pinned-source inventory, adopt/rewrite/reject matrix, attribution, notices, and legal release gate
- [x] 10.1-02-PLAN.md — clean ATLAS package boundary, reproducible inventory generator, and fail-closed identity/dependency/artifact scanner
- [x] 10.1-03-PLAN.md — test-first minimal OpenTUI/Solid ATLAS shell with build, offline, startup, memory, size, and boundary baselines

#### Phase 10.2: Agent Contract, Tool Semantics & Context Intelligence

**Goal:** Freeze one versioned ATLAS agent contract before building surfaces: system prompt,
identity/bootstrap, tool-call semantics, workflow behavior, context hierarchy, Brain/wiki RAG,
skills, compaction/resume, provenance, and evaluation.
**Requirements:** PROMPT-01, PROMPT-02, PROMPT-03, PROMPT-04, PROMPT-05, TOOL-01, TOOL-02,
TOOL-03, TOOL-04, TOOL-05, CTX-01, CTX-02, CTX-03, CTX-04, CTX-05, EVAL-01, EVAL-02
**Success criteria:**

1. Every runtime tool has a machine-readable capability contract covering schema, purpose,
   risk, permissions, workspace scope, network behavior, side effects, timeout, cancellation,
   idempotency, result limits, redaction, audit events, and surface rendering.
2. The prompt compiler emits a versioned, deterministic, provider-aware prompt with an immutable
   ATLAS identity/core, explicit instruction precedence, tool/workflow discipline, evidence and
   verification rules, and a session bootstrap envelope; donor/Hermes product identity never
   reaches the operator-facing agent.
3. Dynamic context uses a separate redacted/provenance-tagged budget: Current Focus, project,
   goals/tasks, recent runs/failures, observations, relevant skills, wiki evidence, and Brain
   graph neighborhoods/paths. Retrieval thresholds support explicit abstention.
4. Prompt/context snapshots are stored by version and source IDs so a run can be replayed and
   explained without persisting secrets or unrestricted chain-of-thought.
5. Deterministic, adversarial, RAG, tool-choice, permission, compaction/resume, and multi-model
   eval suites meet the thresholds in `10.2-AI-SPEC.md`.

**Plans:** 5/5 plans complete

**Wave 1**

- [x] 10.2-01-PLAN.md — frozen prompt/bootstrap/context schemas and deterministic layered compiler

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 10.2-02-PLAN.md — generated tool capability catalog, narrowing, errors, and conformance
- [x] 10.2-03-PLAN.md — durable Brain graph, bounded query API, structured retrieval, and abstention

**Wave 3** *(blocked on Waves 1–2 completion)*

- [x] 10.2-04-PLAN.md — immutable run-contract snapshots, replay, native preparation, and resume invariants

**Wave 4** *(blocked on Waves 2–3 completion)*

- [x] 10.2-05-PLAN.md — 30-scenario evaluation dataset and deterministic promotion gate

**Cross-cutting constraints:**

- No second agent/runtime, general agent/RAG framework, or external tracing runtime.
- Frozen Pydantic v2 and JSON-stable contracts; network-free prompt/context/catalog assembly.
- Deterministic safety gates override optional LLM judging.
- Tool/context capabilities may narrow but never silently widen authority.

#### Phase 10.3: Shared Surface Session & Workspace Protocol

**Goal:** Give TUI, WebUI, CLI, API, and future native clients one ATLAS session contract over the
existing agent, bound to either the ATLAS global workspace or a registered Project root.
**Requirements:** SURF-01, SURF-02, SURF-03, SURF-04, SURF-05, SURF-06, AGNT-01, AUD-01
**Success criteria:**

1. A surface session records surface type, surface instance, workspace kind, project/root,
   mission/run/session IDs, agent/model, permission mode, prompt/context versions, and lifecycle.
2. Global and project sessions resolve canonical working directories through the existing
   Project registry; traversal, symlink escape, stale roots, and unregistered path behavior are
   test-covered.
3. Both TUI and WebUI stream the same normalized agent events for text, reasoning state,
   tool calls/results, tasks/subagents, retries, context use, approvals, errors, and completion.
4. Cancel, disconnect, reconnect, resume, compaction, and process restart have explicit,
   tested state transitions with no orphaned running session.

**Plans:** 5/5 plans complete

**Wave 1**

- [x] 10.3-01-PLAN.md — frozen SurfaceSession model, migration 0016, lifecycle state-machine service
- [x] 10.3-02-PLAN.md — workspace_service fail-closed path containment with typed errors (incl. cross_project)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 10.3-03-PLAN.md — SurfaceEvent normalized projection + one normalizer (per-session seq) + conformance tests
- [x] 10.3-04-PLAN.md — cooperative cancel token (watchdog + tool-gate + subprocess) + heartbeat liveness + reconciliation sweep

**Wave 3** *(blocked on Waves 1-2 completion)*

- [x] 10.3-05-PLAN.md — session resume via the 10.2 RunContractSnapshot replay invariant (identity preservation)

#### Phase 10.4: Global Configuration, Auth & Model Control Plane

**Goal:** Make ATLAS configuration, provider/model selection, and secret-safe auth status
consistent and writable from every authorized surface without independent config implementations.
**Requirements:** CFG-01, CFG-02, CFG-03, CFG-04, CFG-05, CFG-06, AUTH-01, AUTH-02, MOD-01, MOD-02, UX-01
**Success criteria:**

1. `~/.atlas/config.yaml` has a versioned frozen schema, atomic cross-process updates, optimistic
   conflict detection, current-user permissions, masked reads, and audit/change events.
2. CLI, gateway, TUI, and WebUI use the same GET/PATCH contract; a change from one surface becomes
   visible to the others without restart or silent last-writer-wins loss.
3. Secrets remain references/ATLAS-owned auth records and never cross masked config APIs; external
   credential stores are detected read-only unless separately authorized.
4. Provider/model/runtime/permission/context settings expose source, effective value, validation,
   restart requirement, health, and actionable remediation.

**Plans:** 2/5 plans executed

**Wave 1**

- [x] 10.4-01-PLAN.md — frozen control-plane contracts, secure file primitive, and revisioned config

**Wave 2** *(after Wave 1)*

- [x] 10.4-02-PLAN.md — ATLAS-owned auth store, external credential detection, and auth CLI
- [ ] 10.4-03-PLAN.md — masked config snapshot/PATCH service, audit, and config CLI

**Wave 3** *(after Wave 2)*

- [ ] 10.4-04-PLAN.md — v2 model registry compatibility and provider/model effective status

**Wave 4** *(after Wave 3)*

- [ ] 10.4-05-PLAN.md — Rust gateway GET/PATCH delivery with typed HTTP error mapping

#### Phase 10.5: Surface-Scoped Permission Broker

**Goal:** Route every approval request to the surface session that caused it while keeping ATLAS
policy, persistence, audit, and exactly-once execution authoritative.
**Requirements:** PERM-01, PERM-02, PERM-03, PERM-04, PERM-05, PERM-06, PERM-07, SEC-02,
AUD-02
**Success criteria:**

1. Approval records include requesting surface/session, run/tool call, risk, normalized args,
   workspace, expiry, decision, reason, and audit provenance.
2. TUI-owned execution uses the ATLAS TUI native blocking prompt; WebUI-owned execution appears
   only in the matching WebUI queue/sidebar; another surface cannot approve or reject it.
3. Headless/API execution denies `ask` decisions unless an explicit approval channel was
   registered; disconnect/timeout follows a configured fail-closed policy.
4. Concurrent replies execute a deferred action at most once; cancellation, expiry, rejection,
   malformed/stale requests, and process restart are test-covered.
5. Session-scoped “allow once/always” rules cannot silently widen global policy or cross
   workspace/surface boundaries.

#### Phase 10.6: ATLAS Terminal Workbench

**Goal:** Ship `atlas` / `atlas tui` as an ATLAS-native terminal client for the existing agent,
Projects, Focus, missions/runs, configuration, tools, subagents/tasks, context, and permissions.
**Requirements:** TUI-01, TUI-02, TUI-03, TUI-04, TUI-05, TUI-06, TUI-07, TUI-08, TUI-09,
TUI-10, TUI-11
**Success criteria:**

1. Startup offers global workspace or registered Project selection and shows a compact ATLAS text
   identity, workspace, model/auth, permission mode, context budget, and session state.
2. Transcript/composer streaming renders normalized agent/tool/task/subagent/retry/context events
   and exposes mission/focus/wiki/Brain/config/session commands without a second backend.
3. Dangerous actions block on the native ATLAS permission prompt; cancellation and Ctrl-C unwind
   agent, tools, and child work cleanly.
4. Session resume/replay preserves prompt/context version and workspace identity; narrow/wide,
   no-color, Unicode/ASCII-safe, Windows Terminal, cmd, PowerShell, VS Code, and WSL tests pass.
5. Source, snapshots, packages, paths, runtime output, and binaries contain no imported product
   identity beyond approved documentation/notices.

#### Phase 10.7: Web Agent Surface & Permission Queue UX

**Goal:** Make the cockpit a first-class client of the same agent/session/config/permission
contracts, with unobtrusive controls that appear only when operationally relevant.
**Requirements:** WEB-01, WEB-02, WEB-03, WEB-04, WEB-05, WEB-06
**Success criteria:**

1. The WebUI starts global/project sessions through the shared protocol and renders event parity
   with the TUI, including tools, tasks/subagents, retrieval provenance, retries, and cancellation.
2. A minimal conditional header appears for active agent/session state; a right sidebar appears
   only for matching WebUI-owned pending approvals/queues or when explicitly pinned.
3. Permission decisions, config writes, project selection, reconnect/resume, and queue state are
   accessible, responsive, keyboard-usable, and screen-reader announced.
4. TUI-owned approvals never appear as actionable WebUI items; global read-only audit history may
   show their terminal outcome and provenance.

#### Phase 10.8: Cross-Surface Conformance, UAT & Cutover

**Goal:** Prove one agent behaves consistently and safely across TUI and WebUI, then cut over
without retaining an indefinite duplicate terminal stack.
**Requirements:** TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, DOC-01, DOC-02
**Success criteria:**

1. A shared conformance suite runs the same reference missions across TUI and WebUI and verifies
   event, tool, retrieval, config, permission, audit, cancellation, and final-outcome equivalence.
2. At least 20 representative runs meet reliability, prompt/RAG quality, no-secret, no-unapproved
   write, exactly-once approval, startup, memory, and latency budgets.
3. Prompt-injection, poisoned knowledge, malicious tool output, path escape, stale config,
   concurrent writers/approvers, disconnect/restart, and compaction/resume adversarial tests pass.
4. Operator UAT and runbooks cover global/project work, configuration, Brain/wiki retrieval,
   permissions, recovery, attribution, and rollback.
5. The new TUI becomes default only after the legacy terminal path has a tested rollback and a
   dated retirement decision; Tauri/native-shell planning resumes afterward.

## Future Milestone Queue

Future work is intentionally kept out of the active phase list so GSD progress,
dependency, and completion queries describe only v1.1. Milestone-local identifiers
avoid reserving global phase and ADR numbers before activation.

- **v1.2 Provider Mesh & Runtime Interoperability:** draft phases `PM-01`–`PM-06`.
  Scope, dependencies, requirements, and activation gates:
  `.planning/milestones/v1.2-ROADMAP-DRAFT.md` and
  `.planning/milestones/v1.2-REQUIREMENTS-DRAFT.md`.
- **v1.3 Gated Self-Evolution Candidate:** draft phase `EV-01`, preserved as a
  separate risk-gated milestone candidate in
  `.planning/milestones/v1.3-SELF-EVOLUTION-DRAFT.md`.
- Corrected portfolio design:
  `docs/plans/2026-06-24-atlas-provider-mesh-self-evolution-design.md`.

Canonical global phase numbers and ADR IDs will be allocated only when each
milestone is activated through the normal milestone workflow.

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
| 10.0.5 Golden Workflows & Quality Gate | v1.0.5 | 5/5 | Complete   | 2026-06-23 |
| 10.0.6 Public Release Prep & Distribution | v1.0.5 | n/a | Drafts done / operator-gated | 2026-06-23 |
| 10.1 ATLAS TUI Harness Intake & Provenance | v1.1 | 3/3 | Complete with memory exception | 2026-06-24 |
| 10.2 Agent Contract, Tool Semantics & Context Intelligence | v1.1 | 5/5 | Complete    | 2026-06-25 |
| 10.3 Shared Surface Session & Workspace Protocol | v1.1 | 5/5 | Complete | 2026-06-25 |
| 10.4 Global Configuration, Auth & Model Control Plane | v1.1 | 2/5 | In Progress | 2026-06-25 |
| 10.5 Surface-Scoped Permission Broker | v1.1 | 0/? | Not planned | — |
| 10.6 ATLAS Terminal Workbench | v1.1 | 0/? | Not planned | — |
| 10.7 Web Agent Surface & Permission Queue UX | v1.1 | 0/? | Not planned | — |
| 10.8 Cross-Surface Conformance, UAT & Cutover | v1.1 | 0/? | Not planned | — |
| 11. CRM via Twenty | v2.0 | 0/? | Not started | — |
| 12. Basic Pulse Monitor | v2.0 | 0/? | Not started | — |
| 13. STT/TTS Voice Integration | v2.0 | 0/? | Not started | — |
| 14. Floating Overlay / Run-Status HUD | v2.0 | 0/? | Not started | — |
