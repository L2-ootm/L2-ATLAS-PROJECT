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
- **Next action — STAGE 3:**
  1. Operator UAT: `cd services/atlas-terminal && bun run dev` in Windows Terminal
     (mouse, dialogs, model selector, prompt loop against the live gateway).
  2. Remove donor account-login feature (`dialog-mimo-login.tsx`, mimo_login/mimo_free
     i18n keys) and its command wiring.
  3. Extend `scripts/tui-boundary-check.ps1` to services/atlas-terminal.
  4. Parity audit vs Go TUI (starfield idle, modes, workflows, /freellmapi, settings
     overlay) → default-surface decision + Go TUI retirement gate (tested rollback).
  Then WS-D (`atlas up` full topology), WS-C (CLI polish), WS-B (installer) per
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
