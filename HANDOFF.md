# Handoff — L2 ATLAS Finish Sprint

**Date:** 2026-07-03 (updated later the same day)  
**Sprint deadline:** 2026-07-09  
**Current mode:** mission analysis documented; implementation resumes at donor TUI STAGE 1.

## Session update — 2026-07-03 (later): hygiene + mission analysis

- Consistency review ran first (`.planning/reports/handoff-roadmap-consistency-review-2026-07-03.md`):
  STAGE 0 had been left untracked despite STATE claiming "committed"; uncommitted WIP broke
  7 cockpit tests + 2 python tests. All fixed and committed:
  - `feat(freellmapi)` — sidecar key autowire into `atlas models refresh`, sidecar panel
    moved Models→Settings, canonical provider names, tests updated. Gates fresh: agent-runtime
    **732 passed / 1 skipped**; cockpit 44 tests + tsc + zero-warning lint + build/bundle;
    atlas-terminal 5 bun tests + tsc + `--smoke` boot LIVE.
  - `feat(atlas-terminal)` — STAGE 0 committed (plan, OMNI wiring strategy, Bun adapter scaffold).
- **Flag for operator:** `freellmapi status` now returns the sidecar `api_key` cleartext
  (local-only convenience; diverges from the masked-secret contract). Ratify or revert.
- `get_key.py` at repo root is stray scratch (logic productionized in
  `freellmapi_control.get_api_key()`); recommend deletion.
- Mission analysis + execution order for the operator's 2026-07-03 task list:
  `docs/plans/2026-07-03-finish-mission-analysis-and-execution-order.md` — workstreams
  WS-A (donor TUI, main), WS-B (installer), WS-C (CLI polish), WS-D (`atlas up` + model
  fetch), WS-E (TUI caching), WS-F (surface wiring law), WS-G (cashflow, document-only).
  Contains file:line problem inventories for CLI, `atlas up`, and Go TUI caching.
- **STAGE 1 DONE (2026-07-03 night, commit `97ca5112`)**: donor chat loop live-verified
  end-to-end (session → prompt_async → mission/run → SSE parts → idle; permission bridge
  with owner token). Two root causes fixed on the way: `resolve_provider` now derefs the
  freellmapi sidecar key (no env side channel), and `freellmapi_control.start` no longer
  forces `NODE_ENV=production` (sidecar died at boot demanding ENCRYPTION_KEY).
  Note: the free route currently lacks tool-calling (HTTP 429 exhausted) — real runs need
  a tool-capable model/route; wiring itself is proven.
- **STAGE 2 DONE (2026-07-03 late night, commits `4e7478a2`/`1432e5ae`/`1c606dcf`)**:
  donor TUI vendored wholesale (138 files + SDK v2 + pure modules + shims for disabled
  server/plugin machinery), boots over the ATLAS adapter (internal plugins load,
  composer renders, live provider in status), identity scrubbed (flags/aliases/branding/
  i18n). tsc clean, 9 bun tests, smoke + headless boot verified. Operator ratifications
  applied: get_key.py deleted; freellmapi status api_key exposure kept (documented).
- **STAGE 3 progress (2026-07-03, later)**:
  1. **DONE** — vendor-tree branding scrub: `src/vendor/opencode/cli/logo.ts` still had
     the raw MIMO/CODE block-letter wordmark (STAGE 2's scrub only covered `src/tui/**`,
     not `src/vendor/opencode/**`). Replaced with the same ATLAS wordmark font already
     used by `services/atlas-tui/internal/tui/theme.go` (`unicodeLogoRows`), so both TUI
     surfaces share one identity. Also fixed `MC |`/`OC |` terminal-title prefixes and the
     `/doc` command's external `mimo.xiaomi.com` link (now opens the repo README).
     Note: `providerID: "xiaomi"` / model name `mimo-v2.5` are real upstream identifiers
     for the Xiaomi MiMo model family used by the freellmapi route — NOT branding, left
     untouched.
  2. **DONE** — removed `dialog-mimo-login.tsx` and its `provider.login`/`provider.connect`/
     `provider.logout` command wiring in `app.tsx`, plus orphaned `tui.dialog.login.*` /
     `tui.command.provider.{login,connect,logout}.title` / `tui.command.logout.toast` i18n
     keys across all 7 locales. This whole feature called `oauth.authorize`, `auth.remove`,
     `auth.set`, `instance.dispose` — none of which the ATLAS adapter (`atlasFetch.ts`)
     implements (all 501 `notImplemented`), so it was already dead/broken over the ATLAS
     gateway, not just donor-branded. Consistent with the "ATLAS keeps
     provider/auth/config authority" guardrail — no second identity system was added.
  3. **DONE** — added `test/sdkClient.test.ts`: exercises `createOpencodeClient` (the real
     client `src/tui/context/sdk.tsx` builds) through the adapter, asserting
     `session.create`/`session.list` return no client-level error. Closes the gap where
     the existing chat-loop tests only drove `handle.fetch` directly, not the generated
     SDK client the TUI actually calls. The previously-reported "Creating a session
     failed" toast (2026-07-03 screenshot) could NOT be reproduced against current code —
     both the raw adapter and the SDK v2 client succeed in isolation; if it recurs, check
     the browser/terminal console per the toast's own instruction (mission analysis notes
     it may be stale, predating STAGE 2c's identity scrub commit).
  Verified after each change: `bunx tsc --noEmit` clean, `bun test` (10/10 pass),
  `bun run smoke` boots. Committed as `6568574e`.
  4. **DONE** (commit `430cd86`) — Go TUI vs donor feature-gap audit (via Explore agent)
     found only two real gaps: **Settings** (no config-write path at all — donor's
     `dialog-model.tsx` calls `global.config.update` but the adapter had no PATCH
     `/config` route) and **model readiness classification** (Go TUI's
     live/unconfigured/degraded/mock verdict had no analog). Permission bridge
     (`chat.ts`'s pollPermissions/replyPermission + `routes/session/permission.tsx`) was
     already a superset of the Go overlay; the idle logo shimmer in `logo.tsx` already
     covers idle-animation intent (mechanically different from `starfield.go` but not a
     regression). Ported: `atlasFetch.ts` gained `/atlas/config` (GET/PATCH),
     `/atlas/auth/providers`, `/atlas/auth/codex/import`, `/atlas/provider/status` —
     forwarding 1:1 onto the exact gateway routes `internal/client/client.go` already
     uses (`GET/PATCH /v1/config`, `POST /v1/auth/*`, `GET /v1/provider/status`) — no new
     gateway work needed. `src/tui/util/readiness.ts` ports `readiness.go`'s
     `readinessFor`/`mockAllowed` verbatim (test cases mirrored from
     `readiness_test.go`). New `/settings` command (`dialog-atlas-settings.tsx`) built
     from the donor's existing `DialogSelect`/`DialogPrompt` primitives — provider,
     model, auth mode, base URL, API key, reasoning effort. **Scope cut**: the Go TUI's
     post-save connectivity probe (`startProbe`/`archiveProbe`, an ephemeral
     mission+SSE-classify round trip) was not ported — save + a `/provider/status`
     refresh gives the same readiness signal without the extra mission plumbing. Revisit
     if operator UAT shows the probe step is missed.
  Verified: `bunx tsc --noEmit` clean, `bun test` 18/18, `bun run smoke` boots.
- **STAGE 3 parity audit — CONCLUSION (2026-07-03, later)**: feature-for-feature vs
  services/atlas-tui (the current working `atlas tui`):
  - Settings, model readiness, permission bridge, idle animation: **at parity**
    (settings/readiness ported this session; permissions/idle were already covered —
    see the earlier "STAGE 3 progress" entry above).
  - Built-in slash commands (init/review/dream/distill/goal/deep-research): **at
    parity** — both TUIs now execute all six for real (donor side wired this session;
    commit `f4bfa43`).
  - FreeLLMAPI sidecar control (status/start/stop): **at parity** — was the one real
    gap the audit found; closed in commit `cea05c6`.
  - Workflows (`ATLAS_TUI_EXPERIMENTAL_WORKFLOW_TOOL`): experimental/flagged on both
    sides, not a blocking gap either direction.
  - Branding/vendor-tree scrub: swept (STAGE 2c + this session's logo.ts/app.tsx fixes)
    and now mechanically guarded (`scripts/scan-atlas-terminal-boundary.ps1`).
  **Flagged but NOT fixed this session** (found during the audit, out of scope for a
  parity pass — product decisions, not bugs): `dialog-go-upsell.tsx` and the `/share`
  command still reference `opencode.ai` (donor's own paid-upsell/share-hosting
  product — currently dead code, `/share`'s backend route is unimplemented in the
  adapter, so nothing is actually sent there); `tui-migrate.ts`'s `TUI_SCHEMA_URL`
  points at `https://opencode.ai/tui.json` for TUI-config-schema migration; ~30 theme
  JSON files carry a `$schema: https://opencode.ai/theme.json` reference (editor
  tooling hint only, not user-facing). None of these block a retirement decision, but
  they're real remaining vendor-tree surface if a future scrub pass runs.
  **Retirement gate: NOT decided.** Per this file's own guardrail ("do not mark the
  sprint complete without explicit verification and operator UAT"), whether
  `atlas tui` actually switches to atlas-terminal is the operator's call, not something
  claimed here. Recommended UAT before deciding: `cd services/atlas-terminal && bun run
  dev` — exercise the prompt loop, `/settings` (new), `/freellmapi-status` (new),
  `/dream` `/distill` `/goal` `/deep-research` (new), and confirm the branding fix and
  the previously-reported "Creating a session failed" toast (unreproduced against
  current code in this session's testing).
- **Next action:** operator UAT (above) → retirement-gate decision → then WS-D (`atlas
  up` full topology), WS-C (CLI polish), and WS-B's remaining installer steps
  (`docs/plans/2026-07-03-wsb-installer-plan.md` §7 steps 3-6: clean-machine runbook,
  the TUI-binary-manifest decision gated on the retirement call, real CI
  publishing), per
  `docs/plans/2026-07-03-finish-mission-analysis-and-execution-order.md`.

## Current state

The earlier Cashflow topographic integration and ATLAS Go TUI presentation pass remain in the
working tree. A later dashboard visual correction attempt was judged worse by the operator and
was rolled back. Do not restart another broad visual redesign from that failed direction.

The most recent operator direction was documentation only. The sprint plan is now captured in:

- `docs/plans/2026-07-03-sprint-to-2026-07-09-milestone-finish.md`
- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/STATE.md`

## Sprint target

Finish the active milestones by 2026-07-09 with polish and stability across the agent config
surface, web cockpit, terminal, cashflow module, model/provider config, installer, CLI, and TUI.

## Priorities

1. **Unify Settings and System**
   - Settings and System should become one modular control page.
   - Use tabs or dynamic sections instead of two competing sidebar destinations.
   - Existing `/settings` and `/system` routes may remain only as compatibility shims or redirects.

2. **Polish configuration for agent, web, and terminal**
   - Same categories and effective values across WebUI, TUI, and CLI.
   - Include provider/model/auth state, permission mode, workspace/project, context/Brain controls,
     diagnostics, hot-reload vs restart-required state, and remediation.

3. **Make Models/config dynamic**
   - Models page must render from live provider/model/config contracts.
   - Show effective value, source, auth state, validation state, health/probe result, and route/fallback policy.

4. **Stabilize Cashflow integration**
   - Treat Cashflow as an ATLAS module, not a detached dashboard.
   - Keep launch/handoff deterministic, module health visible, and route smoke green.
   - Visual work should focus on spacing, padding, and layer hierarchy first.

5. **Create installation package path**
   - Install, update, uninstall/rollback, doctor/health check, clean-machine instructions, and versioned artifact.

6. **Polish CLI commands**
   - Coherent naming, discoverable help, script-safe output where needed.
   - Cover status, doctor, config, models, cashflow, and retained legacy/rollback paths explicitly.

7. **Refactor TUI using MiMoCode as principal presentation donor**
   - MiMoCode MIT presentation code may be copied/ported/modified with notices retained.
   - Keep ATLAS runtime, provider, config, audit, policy, session, and storage authority.
   - Focus on gradient smoothness, animation cadence, composer geometry, command menu alignment,
     spacing, and transcript ergonomics.

## Visual debt to carry forward

- The layout is not polished enough because some card/panel text has effectively zero margin.
- Spacing needs a deliberate system pass: section gaps, panel padding, sidebar rhythm, and text density.
- Layering needs cleanup: topo background, glass panels, rails, and nav should read as one depth stack.
- Avoid another uncontrolled dashboard redesign. First fix spacing and layers surgically.

## Existing verification from the prior implementation pass

- `services/cashflow`: lint/build/route smoke previously passed.
- `services/atlas-tui`: Go tests/vet/stripped build previously passed.
- MiMoCode MIT attribution is retained in `docs/third-party/ATLAS_TUI_UPSTREAM_NOTICE.md`.

Re-run fresh verification before claiming any new implementation is complete.

## Suggested next implementation order

1. Settings/System consolidation spec and route compatibility decision.
2. Dynamic model/config contract audit.
3. Cashflow stabilization checklist and spacing pass.
4. Installer/package path.
5. CLI command polish.
6. MiMoCode-donor TUI refactor plan, then implementation.

## Guardrails

- No code changes were requested in the last documentation-only step.
- Do not add a second donor runtime/backend.
- Do not split Settings/System further.
- Do not start CRM, voice, or overlay work in this sprint.
- Do not mark the sprint complete without explicit verification and operator UAT.
