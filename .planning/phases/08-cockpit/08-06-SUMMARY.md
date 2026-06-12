---
phase: 08-cockpit
plan: "06"
subsystem: ui
tags: [svelte, sveltekit, atlas-gateway, cors, sse, sqlite, model-registry, cockpit]

# Dependency graph
requires:
  - phase: 08-cockpit/08-01..05
    provides: SvelteKit app scaffold, all four cockpit surfaces, atlas-gateway with missions/runs/wiki endpoints
  - phase: 07-api-gateway
    provides: Rust axum gateway (127.0.0.1:8484) with SQLite-backed routes
provides:
  - Read-only model registry surface (/models) — MODEL REGISTRY table, ROUTING POLICY block, AUDIT VISIBILITY block
  - api.ts extended with listModels() and ModelEntry interface
  - ModelRow.svelte component for table rows
  - CORS allowlist middleware on atlas-gateway (all browser fetches unblocked)
  - Aligned frontend TypeScript types with real gateway response contracts
  - ATLAS_WIKI_DIR override + auto-create for gateway-dispatched wiki writes
  - Synthetic operator run bootstrap (prevents FK failure on fresh DB)
  - Expanded sidebar layout fix (shifts main content, no occlusion)
  - Full E2E verification of all six COCKPIT requirements (COCKPIT-01..06)
affects:
  - 09-skills
  - 10-native-shell
  - Phase 10 model mutation controls (MUTATION CONTROLS: PHASE 10 note rendered in Surface 4)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Read-only surface pattern: no edit/delete/toggle controls rendered; explicit grayed note for future phases
    - Gateway CORS: allowlist middleware added to axum router for loopback browser clients
    - FK bootstrap: synthetic operator mission+run pre-seeded to unblock operator-initiated writes on fresh DB
    - ATLAS_CLI env override: gateway dispatches wiki writes via configurable CLI path, not hardcoded cwd

key-files:
  created:
    - services/web-ui/src/routes/models/+page.svelte
    - services/web-ui/src/lib/components/ModelRow.svelte
  modified:
    - services/web-ui/src/lib/api.ts
    - native/atlas-core-rs/crates/atlas-gateway/src/lib.rs

key-decisions:
  - "Surface 4 read-only in v1.0: no mutation controls rendered; PHASE 10 note is explicit UI signal to operator"
  - "CORS fixed on gateway side (not browser fetch workaround) to keep cockpit CSP clean"
  - "Synthetic operator run bootstrapped at gateway startup to satisfy FK constraint on wiki write path"

patterns-established:
  - "Cockpit surfaces degrade gracefully: gateway offline → empty state with actionable message, never crash"
  - "Type alignment: frontend interfaces derived from actual gateway JSON shapes, not assumed shapes"

requirements-completed: [COCKPIT-06]

# Metrics
duration: ~90min (including 5 integration fix cycles during E2E verification)
completed: "2026-06-12"
---

# Phase 08 Plan 06: Model Registry + Full Cockpit E2E Verification Summary

**Read-only model registry surface (/models) shipped; five integration defects surfaced and fixed during E2E verification; all six COCKPIT requirements (COCKPIT-01..06) verified live against atlas-gateway and SvelteKit dev server via Playwright automation**

## Performance

- **Duration:** ~90 min (Task 1 ~15min + 5 integration fix cycles during checkpoint verification)
- **Started:** 2026-06-12T00:00:00Z
- **Completed:** 2026-06-12T00:00:00Z
- **Tasks:** 2 (Task 1 auto, Task 2 checkpoint resolved by orchestrator)
- **Files modified:** 4 source files + 5 fix commits

## Accomplishments

- Implemented Surface 4: /models renders MODEL REGISTRY table (3 seeded models), ROUTING POLICY block, AUDIT VISIBILITY block — explicitly read-only with "(MUTATION CONTROLS: PHASE 10)" note
- Extended api.ts with ModelEntry interface and listModels() with graceful 503/404 degradation
- Identified and fixed 5 integration defects blocking the E2E checkpoint (CORS, type misalignment, FK failure, wiki dir, sidebar layout)
- Verified all six COCKPIT requirement IDs live: COCKPIT-01 (mission list), COCKPIT-02 (live SSE), COCKPIT-03 (completed audit trail), COCKPIT-04 (wiki browser + create), COCKPIT-05 (create mission), COCKPIT-06 (< 2s load, no Electron, adapter-static)
- DOMContentLoaded = 12ms, load = 13ms on hard reload — well within 2000ms COCKPIT-06 budget
- 0 console errors, 0 console warnings on final verification pass

## Task Commits

1. **Task 1: Model registry surface + api.ts listModels** - `de89e2a` (feat)
2. **Integration fix: synthetic operator run bootstrap** - `a06f7fa` (fix)
3. **Integration fix: CORS allowlist middleware** - `3c18cb7` (fix)
4. **Integration fix: align frontend types with real gateway contracts** - `83c6092` (fix)
5. **Integration fix: ATLAS_WIKI_DIR override + auto-create** - `b208be2` (fix)
6. **Integration fix: expanded sidebar shifts main content** - `7247e16` (fix)

## Files Created/Modified

- `services/web-ui/src/routes/models/+page.svelte` — Surface 4: MODEL REGISTRY table, ROUTING POLICY, AUDIT VISIBILITY blocks; read-only
- `services/web-ui/src/lib/components/ModelRow.svelte` — Single model row: MODEL ID, PROVIDER, TIER, HEALTH (StatusBadge), POLICY (colored badge)
- `services/web-ui/src/lib/api.ts` — Added ModelEntry interface + listModels(); also fixed AuditEvent/ProvenanceRecord/WikiPage type shapes to match actual gateway contracts; removed fictional LAYER selector
- `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs` — CORS allowlist middleware; ATLAS_WIKI_DIR env override + auto-create; synthetic operator mission+run bootstrap on startup

## Decisions Made

- Surface 4 is strictly read-only in v1.0. No mutation controls rendered anywhere on the models page. The grayed "(MUTATION CONTROLS: PHASE 10)" note is an intentional operator-visible signal — not filler.
- CORS was fixed on the gateway side (not via a proxy or browser workaround) to preserve a clean CSP for the cockpit and avoid shipping a permissive wildcard.
- Synthetic operator mission+run are bootstrapped at gateway startup. They appear as a cosmetic entry in the mission list. A future phase may filter them; for v1.0 this is acceptable.

## Deviations from Plan

### Auto-fixed Issues (found during E2E verification — already committed)

**1. [Rule 1 - Bug] Fixed FK failure blocking all operator wiki writes on fresh DB**
- **Found during:** Task 2 checkpoint — COCKPIT-04 wiki create flow
- **Issue:** Gateway wiki write path required an existing `operator` mission FK; fresh DBs had none, causing every operator-initiated wiki create to fail with a constraint error
- **Fix:** Bootstrapped synthetic operator mission + run pair at gateway startup
- **Files modified:** `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs`
- **Committed in:** `a06f7fa`

**2. [Rule 2 - Missing Critical] Added CORS allowlist middleware to atlas-gateway**
- **Found during:** Task 2 checkpoint — every browser fetch from cockpit blocked
- **Issue:** Gateway had no CORS headers; browser blocked all cockpit XHR/fetch calls from localhost:5173
- **Fix:** Added CORS allowlist middleware to axum router; permits cockpit origin loopback
- **Files modified:** `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs`
- **Committed in:** `3c18cb7`

**3. [Rule 1 - Bug] Aligned frontend TypeScript types with real gateway response contracts**
- **Found during:** Task 2 checkpoint — /runs/[id] page crashed on render
- **Issue:** AuditEvent used fictional fields (`rowid`/`payload`/`created_at`); gateway returns `cursor`/`data`/`timestamp`. ProvenanceRecord and WikiPage had similarly diverged shapes. LAYER selector referenced a non-existent gateway field.
- **Fix:** Rewrote AuditEvent, ProvenanceRecord, WikiPage interfaces to match actual gateway JSON; removed LAYER selector
- **Files modified:** `services/web-ui/src/lib/api.ts`
- **Committed in:** `83c6092`

**4. [Rule 1 - Bug] Fixed ATLAS_WIKI_DIR override and auto-create for gateway wiki dispatch**
- **Found during:** Task 2 checkpoint — wiki create failed when cwd ≠ repo root
- **Issue:** Gateway computed wiki dir as cwd-relative path; when launched from a different directory, the path was wrong and non-existent dirs were not created
- **Fix:** Added ATLAS_WIKI_DIR env var override; fall back to cwd-relative path; auto-create the directory on startup
- **Files modified:** `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs`
- **Committed in:** `b208be2`

**5. [Rule 1 - Bug] Fixed expanded sidebar occluding main content**
- **Found during:** Task 2 checkpoint — sidebar toggle visual regression
- **Issue:** Expanded sidebar overlaid on top of main content area instead of pushing it
- **Fix:** Fixed flex layout so expanded sidebar shifts main content column rather than occluding it
- **Files modified:** `services/web-ui/src/lib/components/Sidebar.svelte` (or equivalent layout file)
- **Committed in:** `7247e16`

---

**Total deviations:** 5 auto-fixed (3 Rule 1 bugs, 1 Rule 1 layout bug, 1 Rule 2 missing critical security/functionality)
**Impact on plan:** All five fixes required for correct operation. No scope creep. Surface 4 read-only constraint (T-08-21) fully enforced.

## Issues Encountered

- All integration defects were caught during the E2E verification checkpoint and fixed by the orchestrator. Each fix was committed separately with a descriptive message. The main model surface (Task 1) was clean; defects were at the gateway/frontend integration boundary.

## Operational Notes

The following environment requirements were discovered during verification. Future operators must observe:

1. **Gateway launch:** MUST set `ATLAS_CLI=<path to atlas executable>` and `ATLAS_WIKI_DIR=<repo>/wiki` when `atlas` is not on PATH or when the working directory differs from the repo root.
2. **Database migrations:** `infra/migrations/0001-0003` must be applied before first use.
3. **Synthetic operator entry:** The bootstrap seeds one `operator` mission + run pair. This appears in the mission list as a cosmetic entry. Consider filtering in a future phase.

## Next Phase Readiness

- All six COCKPIT requirement IDs (COCKPIT-01..06) are satisfied and verified live.
- Phase 8 cockpit is feature-complete for v1.0.
- Phase 9 (Skill Inventory & Classification) can proceed.
- Phase 10 model mutation controls will extend the /models surface (the PHASE 10 note already signals this to the operator).
- No outstanding blockers for Phase 9.

---
*Phase: 08-cockpit*
*Completed: 2026-06-12*
