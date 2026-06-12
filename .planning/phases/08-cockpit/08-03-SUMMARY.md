---
phase: "08-cockpit"
plan: "03"
subsystem: "web-ui"
tags: ["sveltekit", "svelte5", "missions", "crud", "modal", "data-table"]
dependency_graph:
  requires:
    - "08-01 (GlassPanel, HudLabel, StatusBadge, api.ts)"
    - "08-02 (gateway endpoints: listMissions, createMission, getMission, startRun)"
  provides:
    - "/missions route: mission list with data table, empty state, error state"
    - "CreateMissionModal component with optimistic insert and flash animation"
    - "/missions/[id] route: mission detail, runs table, LAUNCH NEW RUN"
  affects:
    - "services/web-ui SPA — all routes now visible via fallback 200.html"
tech_stack:
  added: []
  patterns:
    - "Svelte 5 $state / $derived / onMount for data fetching"
    - "Optimistic UI: prepend to array on creation, flash ID tracking with setTimeout"
    - "CSS keyframe animation for flash border-left effect (box-shadow inset)"
    - "adapter-static SPA fallback (200.html) for dynamic [id] routes"
    - "data-topo-active attribute for CSS topo glow activation on hover"
key_files:
  created:
    - "services/web-ui/src/lib/components/MissionRow.svelte"
    - "services/web-ui/src/lib/components/CreateMissionModal.svelte"
    - "services/web-ui/src/routes/missions/[id]/+page.svelte"
  modified:
    - "services/web-ui/src/routes/missions/+page.svelte"
    - "services/web-ui/svelte.config.js"
decisions:
  - "D-08-03-fallback: Changed adapter-static fallback from null to 200.html with strict:false to support dynamic /missions/[id] route — the SPA client router handles navigation; this is the standard SvelteKit SPA pattern for adapter-static"
  - "D-08-03-flash-animation: Flash border-left implemented via CSS keyframe using box-shadow inset rather than border-left property — avoids layout reflow on table rows; achieves identical visual with better performance"
metrics:
  duration: "~12 minutes"
  completed: "2026-06-12"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 2
---

# Phase 08 Plan 03: Mission List Surface Summary

**One-liner:** Mission list route with glass panel data table, status badges, optimistic mission creation modal with flash animation, and mission detail route with runs table and LAUNCH NEW RUN — wired to live Phase 7 gateway endpoints.

---

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Mission list page with data table and empty/error states | 665baf4 | missions/+page.svelte, MissionRow.svelte |
| 2 | Create mission modal + optimistic insert + mission detail route | 64719c4 | CreateMissionModal.svelte, missions/[id]/+page.svelte, svelte.config.js |

---

## Verification Results

- `npm run check`: **0 errors, 0 warnings** (svelte-check 4.2.x, TypeScript strict, Svelte 5)
- `npm run build`: **exits 0**, static output with 200.html fallback
- No Electron in package.json: **PASS**
- missions/+page.svelte contains "listMissions", "CREATE MISSION", "NO MISSIONS RECORDED", "GATEWAY OFFLINE": **PASS**
- MissionRow.svelte contains "StatusBadge" and "rgba(255,255,255,0.03)": **PASS**
- CreateMissionModal.svelte contains "DISCARD", "MISSION CREATE FAILED", "rgba(127,0,255,0.20)", "min-height: 96px": **PASS**
- missions/[id]/+page.svelte contains "getMission", "startRun", "LAUNCH NEW RUN": **PASS**
- missions/[id]/+page.svelte uses $page.params.id (no hardcoded IDs): **PASS**

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] adapter-static strict mode rejects dynamic [id] route**
- **Found during:** Task 2 (npm run build)
- **Issue:** svelte.config.js had `fallback: null, strict: true` which caused the build to error when /missions/[id] was not found during crawl — dynamic routes with unknown IDs can't be prerendered statically
- **Fix:** Changed `fallback: 'null'` → `fallback: '200.html'`, `strict: false`, added `handleUnseenRoutes: 'warn'`. The SPA client router handles /missions/[id] navigation at runtime via the 200.html fallback. This is the standard adapter-static SPA pattern and consistent with D-006 (SPA, no SSR).
- **Files modified:** services/web-ui/svelte.config.js
- **Commit:** 64719c4

**2. [Rule 1 - Bug] Svelte 5 a11y: role="row" is redundant on tr elements**
- **Found during:** Task 1 (npm run check)
- **Issue:** Adding `role="row"` to `<tr>` is redundant and triggers Svelte 5's a11y linter
- **Fix:** Removed the role attribute; tr already has implicit row semantics
- **Files modified:** MissionRow.svelte

**3. [Rule 1 - Bug] .ts extension in import paths not allowed without allowImportingTsExtensions**
- **Found during:** Task 1 (npm run check)
- **Issue:** `import from '$lib/api.ts'` triggers TS error — the tsconfig doesn't enable allowImportingTsExtensions; SvelteKit resolves .ts without the extension
- **Fix:** Removed `.ts` suffix from all import paths → `import from '$lib/api'`
- **Files modified:** MissionRow.svelte, missions/+page.svelte

**4. [Rule 2 - Missing] Dialog element needs tabindex for keyboard focus management**
- **Found during:** Task 2 (npm run check)
- **Issue:** Svelte 5 a11y linter requires `tabindex` on elements with `role="dialog"` — needed for focus trap correctness and keyboard Escape handling
- **Fix:** Added `tabindex="-1"` to the overlay div; allows focus to be programmatically set to dialog when opened
- **Files modified:** CreateMissionModal.svelte

---

## Known Stubs

None. All surfaces are fully wired to live API endpoints. The topo glow effect uses the CSS `data-topo-active` attribute pattern (CSS-only, no topo_engine.js import needed per plan spec).

---

## Threat Flags

No new threat surface beyond the plan's threat model:
- T-08-09: title/intent passed to createMission() → gateway → atlas CLI; no shell interpolation path in the frontend
- T-08-10: mission_id from $page.params.id passed to getMission() and startRun() via encodeURIComponent in apiFetch
- T-08-11: optimistic insert immediately replaced by API response on success; no client-side persistence

---

## Self-Check: PASSED

- [x] services/web-ui/src/routes/missions/+page.svelte — FOUND
- [x] services/web-ui/src/lib/components/MissionRow.svelte — FOUND
- [x] services/web-ui/src/lib/components/CreateMissionModal.svelte — FOUND
- [x] services/web-ui/src/routes/missions/[id]/+page.svelte — FOUND
- [x] Commit 665baf4 — verified in git log
- [x] Commit 64719c4 — verified in git log
