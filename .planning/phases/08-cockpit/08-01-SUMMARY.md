---
phase: "08-cockpit"
plan: "01"
subsystem: "web-ui"
tags: ["sveltekit", "svelte5", "tailwind-v4", "design-system", "scaffold", "api-client"]
dependency_graph:
  requires: []
  provides:
    - "services/web-ui SvelteKit app"
    - "L2 design tokens globally available"
    - "GlassPanel/HudLabel/StatusBadge Svelte 5 primitives"
    - "Typed API client for Phase 7 gateway (127.0.0.1:8484)"
    - "Four-route sidebar shell (Missions/Runs/Wiki/Models)"
    - "CockpitModule registry for nav extension"
  affects: []
tech_stack:
  added:
    - "SvelteKit 2.21.x"
    - "Svelte 5.34.x (runes mode)"
    - "Tailwind CSS v4 (@tailwindcss/vite plugin)"
    - "@sveltejs/adapter-static 3.0.x"
    - "Vite 6.3.x"
    - "@lucide/svelte 1.17.x (Lucide icons, Svelte 5 fork)"
    - "svelte-check 4.2.x"
    - "TypeScript 5.8.x"
  patterns:
    - "Svelte 5 runes ($state, $derived, $props)"
    - "Svelte 5 snippets (children Snippet pattern)"
    - "SvelteKit adapter-static with prerender=true + ssr=false"
    - "CSS custom properties for design tokens (no Tailwind class bloat on tokens)"
    - "Module registry pattern (CockpitModule[] in src/lib/modules.ts)"
key_files:
  created:
    - "services/web-ui/package.json"
    - "services/web-ui/svelte.config.js"
    - "services/web-ui/vite.config.ts"
    - "services/web-ui/tsconfig.json"
    - "services/web-ui/.gitignore"
    - "services/web-ui/src/app.html"
    - "services/web-ui/src/app.css"
    - "services/web-ui/src/lib/tokens.css"
    - "services/web-ui/src/lib/tailwind-v4.css"
    - "services/web-ui/src/lib/modules.ts"
    - "services/web-ui/src/lib/api.ts"
    - "services/web-ui/src/lib/index.ts"
    - "services/web-ui/src/lib/components/GlassPanel.svelte"
    - "services/web-ui/src/lib/components/HudLabel.svelte"
    - "services/web-ui/src/lib/components/StatusBadge.svelte"
    - "services/web-ui/src/lib/components/Sidebar.svelte"
    - "services/web-ui/src/routes/+layout.ts"
    - "services/web-ui/src/routes/+layout.svelte"
    - "services/web-ui/src/routes/+page.svelte"
    - "services/web-ui/src/routes/missions/+page.svelte"
    - "services/web-ui/src/routes/runs/+page.svelte"
    - "services/web-ui/src/routes/wiki/+page.svelte"
    - "services/web-ui/src/routes/models/+page.svelte"
  modified: []
decisions:
  - "D-lucide-svelte-deprecated: lucide-svelte@0.511.0 is deprecated; migrated to @lucide/svelte@1.17.0 (official Svelte 5 fork, same API, same MIT license)"
  - "D-prerender-layout: Added +layout.ts with prerender=true + ssr=false to satisfy adapter-static strict mode; plan specified fallback:null which requires all routes to be prerenderable"
  - "D-sveltekit-vite-import: @sveltejs/vite-plugin-svelte v5 no longer exports 'sveltekit'; correct import is @sveltejs/kit/vite"
  - "D-module-registry: Added src/lib/modules.ts with typed CockpitModule[] registry per orchestrator direction; nav is data-driven, no shell rewiring for future modules"
metrics:
  duration: "569 seconds (~9.5 minutes)"
  completed: "2026-06-12"
  tasks_completed: 3
  tasks_total: 3
  files_created: 23
  files_modified: 0
---

# Phase 08 Plan 01: SvelteKit Scaffold + L2 Design System Summary

**One-liner:** SvelteKit 5/Svelte 5 cockpit scaffold with L2 Systems design tokens, adapter-static SPA build, four-route sidebar shell driven by a typed module registry, and a fully-typed API client covering all Phase 7 gateway endpoints.

---

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | SvelteKit/Svelte 5 scaffold + L2 design system wiring | 324c9bf | package.json, svelte.config.js, vite.config.ts, tokens.css, app.css, modules.ts |
| 2 | Shared primitives (GlassPanel, HudLabel, StatusBadge) + API client | ee3ee90 | GlassPanel.svelte, HudLabel.svelte, StatusBadge.svelte, api.ts, index.ts |
| 3 | Sidebar shell + root layout + placeholder routes | 01f67de | Sidebar.svelte, +layout.svelte, +layout.ts, +page.svelte, missions/runs/wiki/models pages |

---

## Verification Results

- `npm run check`: **0 errors, 0 warnings** (svelte-check 4.2.x, TypeScript strict)
- `npm run build`: **exits 0**, static output written to `build/` with index.html + all 4 route HTMLs
- No Electron in package.json: **PASS**
- All L2 tokens (--l2-void-page, --l2-font-mono, --l2-font-display, etc.) available globally: **PASS**
- GlassPanel contains `rgba(20,20,20,0.60)`: **PASS**
- StatusBadge contains #00FF94, #FF0055, #00F0FF: **PASS**
- api.ts exports `Mission` interface, `listMissions`, `streamRun`, targets `127.0.0.1:8484`: **PASS**
- Sidebar contains `L2 // SYSTEMS`, `localStorage`, `#00F0FF`, `expanded`: **PASS**

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `lucide-svelte` deprecated — migrated to `@lucide/svelte`**
- **Found during:** Task 1 (npm install)
- **Issue:** `lucide-svelte@0.511.0` prints a deprecation notice: "Package deprecated. Please use @lucide/svelte instead." The plan specifies `lucide-svelte` but the UI-SPEC registry safety section's audit (2026-06-11) was performed when lucide-svelte was still the active package. `@lucide/svelte` is the official Svelte 5 fork with identical API.
- **Fix:** Replaced `lucide-svelte` dependency with `@lucide/svelte@1.17.0`. Updated all imports in modules.ts.
- **Files modified:** package.json, src/lib/modules.ts
- **Commit:** 324c9bf / ee3ee90

**2. [Rule 3 - Blocking] `@sveltejs/vite-plugin-svelte` v5 incompatible import path**
- **Found during:** Task 1 (svelte-kit sync)
- **Issue:** SvelteKit 2.x uses `@sveltejs/kit/vite` for the sveltekit() Vite plugin export, not `@sveltejs/vite-plugin-svelte`. Using the wrong import caused `sveltekit` to be undefined.
- **Fix:** Changed `import { sveltekit } from '@sveltejs/vite-plugin-svelte'` → `import { sveltekit } from '@sveltejs/kit/vite'`. Removed `@sveltejs/vite-plugin-svelte` from devDependencies (it's bundled by @sveltejs/kit).
- **Files modified:** vite.config.ts, package.json
- **Commit:** 324c9bf

**3. [Rule 3 - Blocking] adapter-static strict mode requires explicit prerender**
- **Found during:** Task 3 (npm run build)
- **Issue:** adapter-static strict mode (default) rejected the build because routes weren't explicitly marked prerenderable. The plan specified `fallback: null` which is incompatible with dynamic runtime rendering.
- **Fix:** Added `src/routes/+layout.ts` exporting `prerender = true` and `ssr = false`. This is correct for the adapter-static SPA pattern and aligns with D-006 and D-021 §1 (no SSR runtime).
- **Files created:** src/routes/+layout.ts
- **Commit:** 01f67de

**4. [Rule 1 - Type] Svelte 5 `Component<LucideProps>` type for module registry**
- **Found during:** Task 2 (npm run check)
- **Issue:** `ComponentType` is the Svelte 4 class-constructor type. Svelte 5 icons are typed as `Component<LucideProps>`.
- **Fix:** Updated CockpitModule interface to use `Component<LucideProps>` from svelte and `@lucide/svelte` respectively. Also installed `@types/node` to resolve a SvelteKit-generated tsconfig warning.
- **Files modified:** src/lib/modules.ts
- **Commit:** ee3ee90

### Orchestrator Creative Direction Applied

- **ASCII ATLAS wordmark:** Implemented as a `<pre>` element in the sidebar header (expanded state only), styled in `--l2-fg-3` per L2 token colors. Kept to 4 lines, tasteful and monospace-aligned. `aria-hidden="true"` to avoid screen-reader noise.
- **Module-registry nav:** Implemented `src/lib/modules.ts` exporting `CockpitModule[]` with id/label/route/icon/status. Sidebar iterates `cockpitModules` array — no rewiring needed for future modules. Four Phase 8 entries registered.
- **Quality bar:** Strict TypeScript, no `any`, `npm run check` 0 errors/warnings, `npm run build` exits 0. Accessible markup: `<nav aria-label>`, `aria-label` on icon-only buttons, `aria-current="page"` on active nav items.

---

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| "Surface implemented in Phase 8 Plan 03." | src/routes/missions/+page.svelte | Placeholder — replaced by Plan 03 |
| "Surface implemented in Phase 8 Plan 04." | src/routes/runs/+page.svelte | Placeholder — replaced by Plan 04 |
| "Surface implemented in Phase 8 Plan 05." | src/routes/wiki/+page.svelte | Placeholder — replaced by Plan 05 |
| "Surface implemented in Phase 8 Plan 06." | src/routes/models/+page.svelte | Placeholder — replaced by Plan 06 |

These stubs do not block Plan 01's goal (scaffold + primitives + shell). Each subsequent surface plan replaces the relevant route.

---

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model. No new endpoints, no auth paths, no file access patterns, no schema changes introduced. T-08-SC (npm install) was mitigated — all packages verified MIT/Apache with no slopsquatted alternatives substituted.

---

## Self-Check: PASSED

- [x] services/web-ui/package.json — FOUND
- [x] services/web-ui/src/lib/tokens.css — FOUND
- [x] services/web-ui/src/lib/api.ts — FOUND
- [x] services/web-ui/src/lib/components/Sidebar.svelte — FOUND
- [x] services/web-ui/src/routes/+layout.svelte — FOUND
- [x] services/web-ui/build/index.html — FOUND
- [x] Commit 324c9bf — verified in git log
- [x] Commit ee3ee90 — verified in git log
- [x] Commit 01f67de — verified in git log
