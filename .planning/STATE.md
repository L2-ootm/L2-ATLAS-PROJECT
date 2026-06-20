---
gsd_state_version: 1.0
milestone: v1.0.5
milestone_name: Mass-Adoption Launch Wedge
status: in_progress
last_updated: "2026-06-20T15:45:00.000Z"
last_activity: 2026-06-20 -- Command Center complete (WP-0 through WP-6 DONE), loop-engineering slice complete (LE-0 through LE-5 DONE), NativeAtlasAgent wired to harness, goal hierarchy + compounding loop + operations all operational, Graphify visual refinement (lightning, auto-orbit, minimap sync), full session analysis + documentation produced
progress:
  total_phases: 13
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 8
---

# STATE — L2 ATLAS

## Current Position

Phase: 10.0.1 — not started (planned next: Repo Hygiene & Trust Package, v1.0.5 wedge)
Plan: 10.0 closed; 10.1 not yet planned
Status: in_progress
In-flight (ahead of spine, operator-directed): 10.0.3 ATLAS Identity & Cockpit Redesign — brand
  direction approved at gate; ATLAS palette tokens, logo system (3 variants), favicon, topographic
  shell + sidebar redesign landed. UI-SPEC + per-page redesign wave outstanding.
  Conscious override of the wedge no-list (§20) recorded in ROADMAP 10.0.3.
  REACT PIVOT (operator-directed, D-023): gradual strangler-fig migration Svelte→React underway.
  New parallel app `services/web-ui-react` (Vite + React 19 + TS + Tailwind v4 + React Router 7)
  scaffolded and BUILDING GREEN (tsc + vite). Foundation copied verbatim (tokens.css, api.ts,
  topoEngine.ts, favicon, FX keyframes); shell ported (AtlasMark, TopoField, Sidebar, hud
  primitives); soft-aurora OGL effect integrated; first React surface = Dashboard operator HUD
  (live telemetry + graceful loading/empty/offline states), proven via Playwright
  (output/react-pivot/). Svelte cockpit stays live until React reaches route parity.
Last activity: 2026-06-19 -- Operator console window manager: draggable/tiled chat workbench, project/folder binding, native chat bridge, Claude Code SDK path wired
Loop note: pre-existing dirty state on branch `feat/cockpit-p3-glass-p4` (`.planning/prep/next-steps-db-runner-async-supabase.md`)
  blocked safe code-changing automation. Report-only continuation state written to
  `.planning/reports/atlas-living-context-loop-2026-06-18-dirty-worktree-guard.md`.

### Operator big-plan progress (2026-06-18, web-ui-react)
- **P1 GlassTopo (DONE+verified):** signature frosted-glass-over-glowing-topo surface
  (`src/components/GlassTopo.tsx`). RETUNED to match the L2 reference: resting field is now the
  star (dense cellSize 9, freq 0.015, restingOpacity 0.82, 8 levels), thin frost (blur 3px),
  tight bloom (drop-shadow 2px), vignette. Crisp glowing contour map through frost — not smoke.
  Applied to New-Mission modal (ai/violet), Mission hero (info), Run hero (good when live),
  Projects modal (good/green ≈ reference). Shots: output/playwright/glasstopo-v2-modal-final.png,
  projects-create-modal-green.png.
- **P2 Private repo (DONE):** github.com/L2-ootm/L2-ATLAS-PROJECT private; secrets gate clean.
- **P3 Folder-backed Projects (DONE, full stack, verified):**
  - DB: `infra/migrations/0005_projects.sql` — projects table (IF NOT EXISTS) + `missions.project_id`
    (bare ADD COLUMN, mirrors the 0002 additive pattern; fresh-apply convention — NO tracked runner
    built, that remains the slated `atlas db init` gap).
  - Schema: `Project` model + `Mission.project_id` in `packages/atlas-core/.../core.py`.
  - Service/CLI: `atlas_runtime/project_service.py` (create-in-folder / register-existing / get /
    list, path validation, dup-path reject) + `mission_service.create_mission(project_id=…)` +
    CLI `atlas project create|register|list` + `mission create --project`.
  - Gateway (Rust): `GET /v1/projects`, `POST /v1/projects` (create), `POST /v1/projects/register`,
    `GET /v1/projects/{id}` (+ its missions); graceful pre-0005 fallback; MISSION_COLS untouched.
  - React: `/projects` route + STRUCTURE nav (FolderGit2) + api client + create/register modal +
    optional project picker on New-Mission. Shots: output/playwright/projects-page.png.
  - Verified: agent-runtime 26 + atlas-core 33 pytest green (conftest now applies ALL migrations;
    drift guards updated for project_id); fresh-DB P3 smoke 10/10; cargo test 34+3 green; web
    check/lint/build green. **LANDED 2026-06-18:** gateway rebuilt, `/v1/projects` live (HTTP 200);
    committed on branch `feat/cockpit-p3-glass-p4` (0dc0bd3).
- **P4 Modular agents (DONE — 2026-06-18, branch `feat/cockpit-p3-glass-p4`):**
  - DE-RISK SPIKE PASSED: `claude-agent-sdk` 0.2.104 runs on the LOCAL `claude` CLI (v2.1.179)
    session with NO `ANTHROPIC_API_KEY` (subscription auth); structured stream maps to AuditEvents.
    See memory `p4-agent-sdk-derisk.md`.
  - Backend (commit 0dc...→ b-slice): `atlas_runtime/agents/` — AgentRuntime ABC + RunOutcome,
    registry ("native"|"claude_code"), NativeAtlasAgent (audit-parity), ClaudeCodeAgent (SDK,
    optional dep `atlas-runtime[claude]`, lazy import, stream→emit). Migration 0006
    `runs.agent_runtime` (NOT NULL DEFAULT 'native') + Run schema field + 0001-scoped drift guards.
    `start_run(agent_runtime=…)` persists it. CLI `atlas mission run --agent X [--execute]`
    (--execute runs synchronously via the runtime, then completes the run).
  - Gateway (Rust) + Console (commit 921eb2e): `POST /v1/missions/{id}/run` accepts
    `{agent:"native"|"claude_code"}` (default native; 400 invalid; record-only, no --execute),
    forwards `--agent`; runs expose `agent_runtime`. React NATIVE|CLAUDE CODE selector on
    MissionDetail → startRun(agent); AgentBadge across Runs/RunDetail/MissionDetail; console nav
    planned→active; live logs via existing useRunStream+SSE.
  - Verified: cargo 37+3, agent-runtime 64, atlas-core 33, React tsc/lint/build green; native
    `--execute` smoke end-to-end (run succeeded, agent_runtime recorded, audit trail emitted).
  - DEFERRED (next slice): gateway-triggered LONG claude_code runs need async/background execution
    — the 30s dispatch timeout makes the gateway record-only today; the CLI `--execute` path is the
    live executor. Console live-stream works for runs an executor drives.
  - ⚠️ RUNTIME-DB MIGRATION GAP (antifragility finding): there is NO migration runner; existing
    `~/.atlas/atlas.db` had only 0001-era schema (missing 0005 AND 0006), so committed P3 + P4 were
    broken at runtime until 0005+0006 were hand-applied this session. The slated `atlas db init`
    runner is now a real prerequisite — fresh installs get all migrations via bootstrap, but
    existing DBs silently drift. Build the runner before further schema work.
- **Operator UX slice (DONE — 2026-06-19, live-verified):**
  - Succeeded/completed missions can now be archived with retention (`mission_archive.archived_at/delete_after`);
    purge deletes expired archived missions and their runs/audit/tool/artifact rows. CLI + gateway routes landed.
  - Mission detail/archive panel, archived mission filtering, softer glass modal treatment, glassier run rows, and
    Claude Code orange selector state landed in React. Run detail topo now releases with an expanding radial mask
    before settling into clean audit logs.
  - Cashflow is now a native `/cashflow` ATLAS route backed by the Rust gateway reading `services/cashflow/dev.db`;
    the old System-page server start/iframe control path was removed. Cashflow module activated live.
  - Projects page live readback verified with `L2 ATLAS PROJECT` and `L2 Cashflow` registered. Proof shots:
    `output/playwright/ux-projects-page.png`, `ux-cashflow-page.png`, `ux-mission-archive-panel.png`,
    `ux-claude-selector-orange.png`, `ux-run-detail-clean-logs.png`.
  - Console direction set for next slice: VS Code/Claude-style conversation surface in ATLAS visual language,
    then modular panes (chat, audit stream, tools/files, memory/context) with draggable tiling and topo-aware motion.
- **Operator UX cleanup (DONE — 2026-06-19, live-verified):**
  - Removed the `Missions.refresh()` automatic archive purge call. Root cause: page navigation was invoking
    `POST /v1/missions/purge-archived`, which shells through the CLI contract and can surface Windows terminals.
    Purge remains available as an explicit backend/API operation only.
  - Restored the New Mission modal material to the pre-cleanup glow/blur treatment; kept only the requested
    project selector behavior. Live run audit topo was strengthened and pings are no longer gated by the release phase.
  - Cashflow summary page now includes a `Complete Cashflow` handoff to the future gateway endpoint
    `http://127.0.0.1:8484/cashflow/full`. Proof shots: `output/playwright/ux-new-mission-modal-restored.png`,
    `ux-cashflow-complete-button.png`, `ux-run-live-topo-restored.png`.
- **Operator UX console/projects foundation (DONE — 2026-06-19, live-verified):**
  - New Mission project selection now uses a custom ATLAS popover (`ProjectSelector`) instead of the native Windows
    dropdown; project name/path are scannable and the "No project" state remains explicit.
  - Projects create/register modals now prioritize folder picking. In the Tauri desktop shell, `select_folder`
    opens the OS folder picker via `rfd`; browser mode degrades to manual paste because browsers cannot expose
    arbitrary absolute local paths.
  - Projects rows now include an `Open` console action routing to `/console?project=<id>`. The `/console` route is
    now a first-pass VS Code-like ATLAS workbench: tabs (`atlas.chat`, `audit.stream`, `context.graph`), project rail,
    chat/composer, context/tool dock, local draft message stream, and responsive mobile collapse.
  - Shared page header and Projects table now respond at narrow widths; console long paths wrap instead of clipping.
    Proof shots: `output/playwright/ux-project-selector-polished.png`,
    `ux-project-folder-picker.png`, `ux-projects-console-buttons-final.png`,
    `ux-console-project-tabs-final.png`, `ux-projects-mobile-header-fixed.png`,
    `ux-console-mobile-header-fixed.png`.
  - Verified: `npm run check`, `npm run lint`, `npm run build` green in `services/web-ui-react`; `cargo check`
    green in `services/web-ui-react/src-tauri`; Playwright project handoff and console composer smoke passed.
- **Operator console window manager (DONE/PARTIAL — 2026-06-19, live-verified):**
  - `/console` is now a modular workbench: VS Code-like tabs, new chat/audit/tools/context window creation,
    tile layout reordering, free-layout pointer dragging, active-window focus, and topo-aware semantic window zones.
  - Project integration is live. Projects route to `/console?project=<id>`; the console resolves project root, binds
    chat/tool/context panes to that folder, and can switch to manual folder binding through the desktop folder picker.
  - Added the chat execution bridge: `atlas console chat`, gateway `POST /v1/console/chat`, React `consoleChat`, and
    Native/Claude Code mode selection. Native mode returns a receipt through the real gateway and populates audit rows.
  - Claude Code mode is code-wired through `claude-agent-sdk` with `cwd`, `permission_mode="dontAsk"`, read/search tool
    allowance, and preset `claude_code` prompt context. The local `claude.exe` exists, but the active `python` runtime is
    the Hermes venv without `pip`; `claude_agent_sdk` is not importable there, so the UI now reports the missing optional
    SDK cleanly instead of breaking. Install `atlas-runtime[claude]` in the gateway dispatch Python to make it execute.
  - Verification: `npm run check`, `npm run lint`, `npm run build` green; gateway `/v1/console/chat` native probe green;
    Playwright verified bound boot receipt, new chat window creation, free-layout drag, native chat response, Claude-mode
    fallback, and zero browser warnings. Proof shots: `output/playwright/ux-console-window-manager-tile.png`,
    `ux-console-new-chat-window.png`, `ux-console-window-manager-free-dragged.png`,
    `ux-console-native-chat-response.png`, `ux-console-claude-mode-sdk-missing.png`.

- **Operator console UX continuation (DONE — 2026-06-19, browser-verified):**
  - Claude Code is now per-window: `+ Claude Code` spawns a separate `claude.code` chat window while existing native
    chats remain native. The global agent toggle behavior was removed from the console workbench.
  - Free mode now has live drag + live resize through pointer and mouse fallbacks, a scrollable free canvas, and initial
    window geometry that keeps resize handles visible at 1280x720. Exclusive tabs mode remains available for one-window-per-tab use.
  - Browser-mode folder selection is wired through the Rust gateway at `POST /v1/host/select-folder`; Projects and Console use
    the shared `selectFolder()` host helper instead of the desktop-only Tauri path. Project modals keep manual path entry as a fallback.
  - The Context window now contains the first Hermes Brain / Graphify surface: a topo-lit 3D-ish neuron field with memory,
    skills, runs, audit, and Graphify nodes. Graphify remains disabled in `.planning/config.json`, so this is a UI contract
    and activation point rather than a graph build.
  - Added global ATLAS custom scrollbars and kept project-to-console binding live from `/projects`.
  - Verification: `npm run check`, `npm run lint`, and elevated `npm run build` green in `services/web-ui-react`;
    `cargo check -p atlas-gateway` green in `native/atlas-core-rs`; in-app browser verified `/console` no `agent is not defined`, Claude spawns separately,
    tile/free/tabs cycle, free resize and drag both mutate geometry live, `/projects` Open binds `/console?project=<id>`,
    New Project modal has browser-friendly folder-picker copy, and browser console errors stayed empty.
### Six-item operator scope (added 2026-06-20, in-flight under 10.0.3)

Operator added six items, sequenced for execution (index:
`.planning/phases/10.0.3-SCOPE-SEQUENCE.md`; each has a PHASE.md). Status as of 2026-06-20:
1. **DONE** Memory router — FTS5 wiki retrieval into `context_service.assemble_context` (`18bbfb4`).
   6 tests; 157 agent-runtime pass (1 pre-existing claude_agent_sdk env fail).
2. **DONE** Setup wizard + config-service — `atlas setup`, `~/.atlas/config.yaml`, `atlas config
   show/get/set/json`, gateway `GET /v1/config`, System RUNTIME CONFIG panel (`76df72d`). 14 tests.
3. **DONE (management floor)** Channel cockpit — `atlas channels enable/disable/json`, gateway
   `GET /v1/channels` + `POST /v1/channels/{name}/toggle`, System CHANNELS panel (`ad48554`). 6 tests.
   Deferred: messaging-gateway process lifecycle, Discord browser (see PHASE.md).
4. **DONE (core)** Console BSP auto-tiling — pure `bspLayout.computeDwindle` + `bsp` LayoutMode wired
   into Console (`39f61aa`). Deferred: manual split-boundary resize; no JS test runner → tsc/build-gated.
5. **DONE** Harness cherry-pick — `docs/research/HARNESS_CHERRYPICK_PI_OPENCODE.md`, 9 patterns
   classified adopt/adapt/skip (`0c4600a`). PI = pi-mono harness.
6. **DEFERRED** Foundation de-brand hermes→atlas (`10.0.7-foundation-debrand`) — operator-directed to a
   dedicated session (~12.9k refs, foundation-locked tree, test-gated). PHASE.md is the ready plan.

All work committed on `main` (commits `e3269cb`..`0c4600a`). Verification: agent-runtime 157 pass
(1 known env fail), `cargo test -p atlas-gateway` config/channel tests pass + compiles, web
tsc/lint/build green.

## Project Reference


See: `.planning/PROJECT.md` (updated 2026-06-15) · `.planning/MILESTONES.md`

**Core value:** A serious, auditable AI operating system for technical founders/operators.
**Current focus:** Phase 10.0.1 — Repo Hygiene & Trust Package (v1.0.5 wedge active; v1.1 paused at 10.0)

## Deferred Items

Acknowledged at milestone close on 2026-06-15:

| Category | Item | Status |
|---|---|---|
| verification | Phase 08 `08-VERIFICATION.md` | human_needed — satisfied by 09.5 manual operator UAT (all Phase 8 cockpit surfaces exercised end-to-end) |
| uat | Phase 08 `08-HUMAN-UAT.md` | passed (0 pending) — superseded by 09.5 UAT |
| public-release | `PUBLIC_RELEASE_HARDENING.md §4` items 1–5, 7–8 | bounded, pre-public-publish / post-v1.0 (item 6 fonts RESOLVED) |

## Accumulated Context

### Roadmap Evolution

- Phase 10.0.1 inserted after Phase 10.0: Mass-Adoption Launch Wedge (v1.0.5): Repo Hygiene & Trust Package — first of 6 phases (10.0.1-10.0.6) inserted ahead of v1.1 Phase 10.1+ per l2_atlas_30_day_mass_adoption_wedge_plan.md; v1.1 native-shell/auth/TUI work paused until wedge ships (URGENT)

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
- D-023 (2026-06-17): WebUI framework pivot Svelte→React — AMENDS D-006. Operator-directed gradual
  strangler-fig migration. New parallel app `services/web-ui-react`: Vite + React 19 + TypeScript +
  Tailwind v4 (@tailwindcss/vite) + React Router 7, adapter-static-equivalent (Vite SPA, `dist/`,
  WebView2-safe — no SSR/Node runtime APIs). Rationale: React Bits acceptance-bar effects + real
  shadcn drop in directly; framework-agnostic core (tokens.css, api.ts, topoEngine.ts) transfers
  verbatim, so migration is low-risk. Migrate route-by-route (Dashboard first, then missions/runs/
  wiki/models, then new pages); Svelte cockpit remains the served build until React reaches parity,
  at which point the gateway/native shell point at `web-ui-react/dist` and the Svelte app retires.
  CELESTIAL-HERALDIC REDESIGN (operator-directed, via ultradesign dark-luxe): cockpit rebuilt to
  the attached ATLAS brand reference — Cinzel engraved wordmark, ATLAS palette (void #0B0D12, ivory
  #EDEAE0, celestial #4F8BFF, titan bronze #B08A57 filigree), code-drawn astrolabe mark + filigree
  (compass-star/astrolabe rings/starfield), hairline rails replacing empty glass cards, real
  skeleton/empty/offline states. Aurora fog removed. Tooling upgraded to latest (vite 8, ts 6,
  plugin-react 6, lucide 1, react-router 7.18) + ESLint 10 flat config; tsc/lint/build all green.
  BRAND ASSETS: 8 GPT-image raws organized under brand/atlas/{source,sheets}; vivid-blue "celestial"
  emblem = primary, bronze = filigree (D-024). Processed via brand/atlas/process.py (PIL): emblem
  cut to transparent webp (figure+full), governance seal, app-icons from the globe. Integrated:
  Operator-Atlas emblem = dashboard hero focal; seal = empty states; app-icon/apple-touch links.
  IA replan saved: .planning/phases/10.0.3-webui-cockpit-completion/ULTRAPLAN-assets-and-IA.md
  (pillared nav Mission/Audit/Structure + NEW pages: Audit Ledger, Integrations, System/About,
  ⌘K palette). NEXT WAVE: build the new page set from scratch per that IA.
  DESIGN/PLAN DOC SET (2026-06-17, in phase 10.0.3 dir): PAGES-SPEC.md (verbose per-page specs),
  HARNESS-WIRING.md (gateway contract; found unused SSE /v1/runs/{id}/stream to wire + 4 missing
  endpoints: /v1/runs, /v1/audit/events, /v1/integrations, /v1/system), UX-VISUAL-SPEC.md (plasma
  glassmorphism + typing-reactive TopoInput via the already-ported engine's pushTrail/sonarPing;
  L2 5-laws-of-effects applied). NEW PHASE planned: 10.0.7 Foundation De-brand
  (.planning/phases/10.0.7-foundation-debrand/PHASE.md) — strip Hermes branding from vendored
  foundation/atlas-hermes, retain MIT LICENSE + ATTRIBUTION; insert via /gsd-phase before 10.0.6.
  BUILD WAVE STARTED (2026-06-17): (1) modular layout foundation — pillared nav registry
  (modules.ts navSections: MISSION/AUDIT/STRUCTURE/SYSTEM), Sidebar renders pillar sections,
  reusable Page scaffold, all new routes wired (audit/integrations/system). (2) TopoInput —
  typing-reactive input: per-field topo via the ported engine's pushTrail at the caret, validation
  tones (info/ai/good/bad); terrain blooms violet under AI-bound fields ("typing = authorship") —
  verified live in the create-mission modal. (3) Real Missions page — table + TopoInput filter +
  status chips + create modal (createMission), three states (skeleton/empty-seal/offline).
  tsc/lint/build green.
  BUILD WAVE 2-3 (2026-06-17, MISSION pillar + showpiece): (4) PlasmaGlass lift — GlassPanel
  upgraded (specular top edge + inner-light box-shadow, blur(14px) saturate(1.35), optional
  semantic `glow` bleed) so all surfaces inherit polish. (5) api.ts: openRunStream(id,after)
  EventSource + interim listRuns (fan-out listMissions→getMission, deduped/sorted) until /v1/runs
  ships. (6) useRunStream hook — ported Svelte SSE logic: named events audit/end/stream_error,
  lastCursor dedupe, single transport retry, 500-row cap, terminal-run history paging, newCursors
  set for blur-in/sonar. (7) Mission detail (lifecycle rail + runs table + launch/cancel-all). (8)
  Runs list (cross-mission interim feed, LiveBadge + GlowBorder on running rows). (9) Run detail
  SHOWPIECE — live SSE, electric GlowBorder, CRT-textured audit log over a dedicated topo field
  firing sonarPing per arriving event, auto-scroll pin, cancel + JSONL export (truncation-guarded).
  Primitives: LiveBadge, SseEventRow, RunTimeline, GlowBorder. CONSOLE wired into IA (MISSION
  pillar, status 'planned' → Sidebar dims it + "SOON" tag; branded v1.1 placeholder route) — IA
  forward-compatible, no chat surface yet (v1.1, outside wedge). App.tsx routes live (was
  <Migrating>). tsc/lint/build GREEN.
  LIVE SMOKE PASSED (2026-06-17, Playwright vs real gateway on :8484, cockpit :5173): /runs/:id on
  a live RUNNING run connected via SSE, streamed run_started + tool_call rows with policy chips,
  LIVE badge + electric border, ZERO console/CORS errors; finished run loaded history + showed
  Export JSONL; Runs list rendered the interim cross-mission feed (4 runs, dedup, LIVE row);
  Mission detail, Console placeholder, sidebar SOON tag all render. Screenshot:
  output/playwright/runDetail-live-showpiece.png. Fixed from live data: gateway status vocab is
  completed/cancelled (not succeeded) — StatusBadge + RunTimeline now map COMPLETED→cyan,
  CANCELLED→muted-red.
  BORDERGLOW (2026-06-17): cursor-reactive modal border ported from reactbits BorderGlow
  (.planning/research/ui-effects/border-glow.md) — ATLAS-toned (2px radius, celestial/violet, loud
  interior mesh-fill dropped). New component services/web-ui-react/src/components/BorderGlow.tsx +
  .abg-* CSS in app.css; pointer sets --cursor-angle/--edge-proximity, wedge lights the edge nearest
  the cursor. Applied to the New Mission modal (violet, AI-authoring context). tsc/build green,
  visually verified (output/playwright/modal-borderglow-tuned.png). Reusable for future modals.
  GLASSTOPO (2026-06-18): frosted-glass-over-topo surface ported from L2 Systems Design System
  (topo_engine.js / topo_patterns.html .ti-shell). New component web-ui-react/src/components/
  GlassTopo.tsx — per-panel vivid topo field (tone-tinted resting lattice + glow) behind a
  backdrop-filter blur(11px) saturate(1.4) glass layer, so terrain glows THROUGH the frost; slow
  ambient orbit + pointer reactivity for the fluidic feel; prefers-reduced-motion → static. Applied
  to translucent set: New Mission modal (violet/ai), Mission hero (info), Run hero (good when live).
  Full-takeover/dense surfaces stay opaque. tsc/lint/build GREEN; modal verified
  (output/playwright/glasstopo-modal2.png).
  PRIVATE REPO (2026-06-18): github.com/L2-ootm/L2-ATLAS-PROJECT created PRIVATE via gh; pushed
  main (3761 files). .gitignore hardened (added atlas.cmd, .claude/). Secret gate clean — remote
  has no .env/.key/.pem/.db/atlas.cmd/.claude (only .env.example template). Commit c520ece.

  BIG PLAN (operator-approved 2026-06-18, "everything one big plan"; plan file
  ~/.claude/plans/session-wrap-the-atlas-vivid-river.md). P1 glass-topo ✅ + P2 private repo ✅ DONE.
  REMAINING (each multi-session, backend-heavy):
  P3 — Folder-backed Projects (full vision): projects table maps to a working dir; create-in-folder
  + register existing folder; missions run in project cwd. Stack: migration 0005 (projects +
  missions.project_id FK — NOTE: ALTER ADD COLUMN is non-idempotent in SQLite; VERIFY the migration
  runner tracks applied files before adding, or boot breaks), Project schema in packages/atlas-core,
  project_service.py + mission_service(--project) + run_service(cwd) + CLI project group
  (services/agent-runtime), Rust gateway CRUD in atlas-gateway lib.rs+db.rs, React /projects route+
  nav+api+folder-path UI.
  P4 — Modular agents: AgentRuntime ABC (NativeAtlas | ClaudeCode). ClaudeCodeAgent uses the Claude
  Agent SDK driven by the USER'S LOCAL Claude Code session (subscription auth, NOT an API key —
  must behave like the `claude` they run on their PC). DE-RISK FIRST: confirm the SDK honors local
  session auth before building UI. runs.agent_runtime column (migration 0006), CLI/gateway --agent,
  Console agent-tabs (NATIVE | CLAUDE CODE) reusing useRunStream+SSE for live logs; flip Console nav
  planned→active. DONE 2026-06-18 (see P3/P4 status above). NEXT SESSION: (1) build the `atlas db
  init` migration runner (runtime-DB drift gap — see P4 finding); (2) async/background run executor
  so the gateway can drive long claude_code runs; (3) Command Center (agent-driven ops dashboard,
  Intelligence-Layer — design note in .planning/prep/).
  Idempotency posture (P4): run creation is replay-guarded by the pending-state precondition (a
  duplicate run trigger fails start_run while the mission is 'running'); complete_run/cancel_run are
  guarded by the running-state precondition (no double-terminal); audit emit is fail-open +
  append-only (partial-failure safe). The real antifragility gap is the missing migration runner.
  ODYSSEUS BASELINE doc'd (phase 10.0.3 dir / ODYSSEUS-PAGE-BASELINE.md): reference pillar's 8
  surfaces mapped to our IA. Biggest GAP = a CONSOLE/CHAT surface (direct conversational agent
  interaction, every turn audited) — Odysseus leads with it, we lack it; reuses our SSE+ledger
  plumbing. Other adds to reach the floor: Models→Cookbook+Compare, deep-research as a mission
  template, Codex authoring mode. Conscious exclusions (cockpit ≠ workspace): email/calendar/PIM/
  image gallery. STANCE: Odysseus = direction/UX/feature reference (explicitly allowed — ideas/page
  sets aren't copyrightable; we reimplement natively). Direct code/CSS/asset reuse is GATED: repo
  shows AGPL-3.0 (copyleft) vs MIT in D-016 — confirm before copying any source. "Borrow the
  direction, write our own code."
- D-024 (2026-06-17): ATLAS brand identity locked to the celestial-heraldic reference. Primary =
  vivid-blue "celestial" Operator-Atlas emblem (titan bearing a constellation globe over a circuit
  temple); titan bronze #B08A57 = precious filigree/wordmark only; ivory #EDEAE0 text; Cinzel
  engraved display serif (Orbitron dropped). Photographic emblems for large brand moments
  (hero/splash/About/empty); crisp vector marks for tiny sizes (favicon/nav). Supersedes the
  earlier warm-bronze #E0A94E direction. Page IA replanned around MISSION/AUDIT/STRUCTURE pillars.

### Known blockers

- ~~VS Build Tools missing~~ RESOLVED 2026-06-11: Build Tools C++ workload installed; `cargo build -p atlas-gateway` green (debug + release). Release binary 2.53 MB (<20 MB D-022 budget). `/health` verified live on 127.0.0.1:8484 for both profiles.
- No container engine installed (verified 2026-06-11) — blocks `setup_twenty.ps1 up`, not the fetch (already validated: official compose pinned at v2.1.0 with generated secrets in gitignored infra/compose/twenty/). Preferred engine is now Podman (daemonless, no-bloat — operator install: `winget install RedHat.Podman`); Docker Desktop is the fallback. Script auto-detects podman → docker.

### New candidate spikes

- 2026-06-07: FreeLLMAPI integration spike report added at `docs/research/FREELLMAPI_INTEGRATION_SPIKE_2026-06-07.md`. Closed-env mock provider and real Kilo keyless provider smoke tests passed. Recommendation: sidecar OpenAI-compatible free-tier gateway first; consider Phase 4.5 / Phase 5 routing integration, not direct vendoring.

- 2026-06-15: Agent-Reach candidate tool intake added at `docs/research/AGENT_REACH_INTEGRATION_INTAKE_2026-06-15.md`. Updated per Davi direction: treat Agent-Reach as an ATLAS internet capability layer; document all CLI functions and plan `atlas reach` wrappers/TUI readiness. Credential/platform volatility notes are implementation constraints, not adoption blockers.

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
| 10.0 | Harness Architecture & Threat-Model Design (v1.1) | Done | 2026-06-16 |

## Performance Metrics

(v1.0.5 Mass-Adoption Launch Wedge phases 10.0.1-10.0.6 inserted 2026-06-16, not yet started — see Phase History note below.)

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 08-cockpit P05 | 25m | 2 tasks | 6 files |
| Phase 08-cockpit P06 | 90min | 2 tasks | 4 files |
| Phase 10.0 P01 | 7m | 3 tasks | 4 files |
| Phase 10.0 P02 | 8min | 2 tasks | 3 files |
| Phase 10.0 P03 | 12min | 2 tasks | 2 files |

## Operator Next Steps

- v1.0.5 Mass-Adoption Launch Wedge is now active (inserted 2026-06-16 ahead of v1.1, per `l2_atlas_30_day_mass_adoption_wedge_plan.md`). Continue at Phase 10.0.1 with `/gsd-discuss-phase 10.0.1` then `/gsd-plan-phase 10.0.1` (repo hygiene & trust package first; spine is 10.0.1 -> 10.0.2 -> 10.0.3 -> 10.0.4 -> 10.0.5 -> 10.0.6).
- v1.1 is paused at Phase 10.0 (design complete, 10.1+ not started). Resume at Phase 10.1 with `/gsd-discuss-phase 10.1` once v1.0.5 ships.
- Use `.planning/prep/README.md` as the preparation index; extra-marathon scope is in `.planning/prep/v1.1-extra-marathon-scope.md`.
- Visual CLI inspection guide added: `docs/operations/CLI_VISUAL_MANUAL.md`
- Post-v1.0 gap report added: `.planning/reports/v1-cli-agentic-gap-2026-06-15.md`
- Required v1.1 additions now explicitly include Hermes-class ATLAS TUI, ATLAS-owned auth store/flows, Codex read-only detection without mutation, provider/model/runtime registry, agentic chat, and native shell/PTY.

## Decisions

- [Phase ?]: AUTH_STORE: cross-process OS-handle lock (not os.replace) is the no-corruption guarantee on Windows
- [Phase ?]: ADAPTER: cascade is adapter-driven (not Hermes fallback_model); error classification + audit stay in ATLAS code
- [Phase ?]: DIVERGENCE_LOG: canonical scheme D-LOG-NNN; DIV-F-* superseded; atlas_audit back-filled as D-LOG-002
- [Phase ?]: FALLBACK_CASCADE: 400 needs body inspection (ambiguous=HALT/LANDMINE 6); garbled responses are CASCADE-class (LANDMINE 7)
- [10.0-02]: SCHEMA-02: 0004 migration is additive; legacy model_registry (0003) untouched until 10.3 gateway reader cutover
- [10.0-02]: SCHEMA-03: route_policy is schema-only in v1.1 (LANDMINE 4); routing enforcement deferred to v1.2 ROUTE-01/02
- [10.0-02]: SCHEMA-04: FK not enforced on model_registry_v2.provider_id in v1.1; hard FK deferred to v1.2
- [10.0-02]: SCHEMA-05: compat VIEW (model_registry AS SELECT from model_registry_v2) is recommended 10.3 cutover; drafted as SQL comment only
- [10.0-03]: OAUTH: deferred for v1.1 (SEC-05); gate spec committed with 9 hard gates; hmac.compare_digest is the constant-time state comparison requirement
- [10.0-03]: IPC: Tauri 2 deny-by-default; PTY transports bytes not command strings (LANDMINE 5 NAT-03 hard gate)
- [10.0-03]: IPC: pty_open fixed argv (atlas tui --profile <id>); profile_id validated against known profiles, never free-form
- [10.0-03]: IPC: gateway 127.0.0.1:8484 is loopback HTTP, NOT an IPC surface; no capability grant needed

---

## Session Analysis Documentation (2026-06-19/20)

Full codebase analysis, loop engineering synthesis, foundation mapping, and gateway audit produced:

**Command Center (`.planning/phases/10.0.3-command-center/`):**
- `PLAN.md` — all WPs marked DONE (WP-0 through WP-6, LE-0 through LE-5)
- `SESSION-SUMMARY.md` — complete session arc, files created/modified, architecture delivered
- `GATEWAY-BRIEF.md` — gateway 39 routes, CLI/TUI status, rebranding scope
- `LOOP-ENGINEERING-SYNTHESIS.md` — 7-layer wiring plan (handoff, stops, claims, deep context, entropy, graph, loop specs)
- `HERMES-MAP-AND-WIRING.md` — foundation map, Rust vs Python boundary, context budget wiring
- `FOUNDATION-AND-CHANNELS-ANALYSIS.md` — foundation integration status, channel management suite design

**Graphify (`.planning/phases/10.0.3-graphify-living-graph/`):**
- `GAP-ANALYSIS.md` — 15 gaps identified, priority matrix
- `SPEC.md` — entity model, storage, visuals, API design
- `PHASE.md` — 8 work packages, 19-24 days
- `CONTEXT.md` — system context, related systems
- `AGENT-PROMPT.md` — refined agent prompt with 10 improvements
- `CHECKPOINT.md` — post-refinement checkpoint

## Living Graph Documentation (2026-06-19)

Full codebase analysis of the Graphify knowledge graph system completed. Documentation produced:

**Gap Analysis:** `.planning/phases/10.0.3-graphify-living-graph/GAP-ANALYSIS.md`
- 15 gaps identified across runtime integration, incremental updates, semantic edges, activity tracking, living visuals, wiki/memory integration, and more
- Priority matrix: P0 (runtime entities, wiki integration, Agent Context tab), P1 (persistence, incremental updates, activity, living visuals), P2-P3 (semantic edges, mutations, export)

**Design Spec:** `.planning/phases/10.0.3-graphify-living-graph/SPEC.md`
- Entity model: 11 node types, 13 edge types with Pydantic schema
- Storage: SQLite graph tables with recursive CTE traversal
- Graph engine: entity extractors, incremental builder, activity scoring
- Living visuals: node states (resting/active/firing/refractory/hot/cold), link effects (synaptic flash, dendrite curves, nebula glow)
- API surface: 11 new gateway endpoints
- Integration points: wiki, audit, memory provenance, console, RAG

**Phase Plan:** `.planning/phases/10.0.3-graphify-living-graph/PHASE.md`
- 8 work packages, 19-24 days estimated
- WP-1: Graph schema & storage foundation
- WP-2: Entity extractors (missions, runs, wiki, decisions, phases, audit, files, activity)
- WP-3: Graph builder pipeline (incremental)
- WP-4: Gateway endpoints (11 new routes)
- WP-5: Activity scoring
- WP-6: Agent Context tab (UI)
- WP-7: Living visual effects (neuron animation, nebula storm)
- WP-8: Tests

**Context Document:** `.planning/phases/10.0.3-graphify-living-graph/CONTEXT.md`
- Operator vision translation (neuron connections, nebula storms, wiki/RAG integration)
- Current system inventory (backend, gateway, UI, visual language)
- Related systems mapping (wiki, audit, memory provenance, 6-layer framework)
- Files that will change, testing evidence, operator context

**Key decisions pending:** D-025 (graph storage), D-026 (update strategy), D-027 (entity schema), D-028 (visual language), Rust vs Python for graph engine
