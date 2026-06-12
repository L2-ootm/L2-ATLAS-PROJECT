---
phase: 08-cockpit
plan: "02"
subsystem: atlas-gateway (Rust)
tags: [rust, axum, sqlite, rest-api, wiki, models, cancel]
dependency_graph:
  requires: []
  provides: [wiki-write-endpoints, wiki-detail-endpoint, models-endpoint, cancel-run-endpoint]
  affects: [atlas-gateway binary, Phase 8 cockpit surfaces 2/3/4]
tech_stack:
  added: []
  patterns: [D-022 dispatch pattern (atlas CLI write, direct SQLite read), blocking() helper, ApiError enum]
key_files:
  created: []
  modified:
    - native/atlas-core-rs/crates/atlas-gateway/src/db.rs
    - native/atlas-core-rs/crates/atlas-gateway/src/lib.rs
decisions:
  - Provenance sourced from memory_provenance table (item_id = slug), not a wiki_provenance table; absent table returns null provenance (not error)
  - atlas wiki update CLI takes positional slug + --title + --body; no --layer arg exists; layer column absent from wiki_pages schema; plan spec adapted to actual schema
  - model_registry columns are model_id/provider/source/first_seen/last_seen/active; plan spec (tier/health/policy/updated_at) does not match 0003_model_registry.sql; actual columns used
  - list_models swallows "no such table" rusqlite error at prepare() step and returns Ok(vec![]); model_registry table may be absent on fresh deployments
  - cancel_run returns mission + runs (via get_mission) rather than run detail; no current-run ID is returned by atlas CLI cancel dispatch
metrics:
  duration: 18m
  completed: "2026-06-12"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 8 Plan 02: Gateway Write + Detail Endpoints Summary

Gateway extended with five new endpoints (wiki create/update/detail, model registry list, run cancel) following the D-022 dispatch pattern. `cargo build -p atlas-gateway` and `cargo test -p atlas-gateway` both pass clean; 26 existing tests green, no regressions.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add wiki page detail + model registry reads to db.rs | b8ee45e | native/atlas-core-rs/crates/atlas-gateway/src/db.rs |
| 2 | Add wiki write handlers + models + cancel endpoints to lib.rs | 124022d | native/atlas-core-rs/crates/atlas-gateway/src/lib.rs |

## What Was Built

**db.rs additions:**
- `get_wiki_page(path, slug)` — SELECT slug/title/body/created_at/updated_at; returns `Ok(None)` on QueryReturnedNoRows; fetches most recent provenance row from `memory_provenance` by item_id, returns null if table absent or no rows
- `list_models(path, limit)` — SELECT model_id/provider/source/first_seen/last_seen/active from model_registry ORDER BY model_id; returns `Ok(vec![])` when table absent (no such table error swallowed at prepare step)

**lib.rs additions:**
- `wiki_page_detail` — GET /v1/wiki/pages/{slug} → 200 `{ page }` or 404
- `wiki_create` — POST /v1/wiki/pages → dispatches `atlas wiki update <slug> --title <title> --body <body>`, reads back, returns 201 `{ page }`
- `wiki_update` — PUT /v1/wiki/pages/{slug} → pre-reads current page to merge optional title/body fields, dispatches, returns 200 `{ page }` or 404 if not found
- `models_list` — GET /v1/models → returns `{ models: [...], count: N }`
- `cancel_run` — POST /v1/missions/{id}/cancel → dispatches `atlas mission cancel <id>`, returns `{ mission, runs, message: "run cancelled" }`
- Router: `/v1/wiki/pages` merged to `get(wiki_pages).post(wiki_create)`; added `/v1/wiki/pages/{slug}`, `/v1/models`, `/v1/missions/{id}/cancel`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Schema mismatch] wiki_pages has no `layer` column**
- **Found during:** Task 1 schema review (infra/migrations/0001_core.sql)
- **Issue:** Plan specified `layer INTEGER` in SELECT queries and `--layer` dispatch arg, but the actual schema uses `version INTEGER` and has no layer concept
- **Fix:** Removed `layer` from all SQL queries and dispatch args; `atlas wiki update` CLI accepts `slug --title --body` only (verified in services/wiki-runtime/atlas_wiki/cli/main.py)
- **Files modified:** db.rs (no layer in SELECT), lib.rs (no --layer in dispatch args, no layer field in CreateWikiPageBody/UpdateWikiPageBody)
- **Commit:** b8ee45e, 124022d

**2. [Rule 1 - Schema mismatch] model_registry has different columns than plan specified**
- **Found during:** Task 1 schema review (infra/migrations/0003_model_registry.sql)
- **Issue:** Plan specified columns `model_id, provider, tier, health, policy, updated_at`; actual schema is `model_id, provider, source, first_seen, last_seen, active`
- **Fix:** Used actual column names from migration file
- **Files modified:** db.rs list_models function
- **Commit:** b8ee45e

**3. [Rule 2 - Missing correctness] Provenance table is memory_provenance not wiki_provenance**
- **Found during:** Task 1 migration review
- **Issue:** Plan referenced "wiki_provenance table" which does not exist; provenance is in `memory_provenance` (migration 0002) keyed by item_id
- **Fix:** Query `memory_provenance WHERE item_id = ?1` for provenance; any error (absent table, no rows) is silently null rather than propagating as DbError
- **Files modified:** db.rs get_wiki_page
- **Commit:** b8ee45e

## Verification

```
cargo build -p atlas-gateway  → exit 0
cargo test -p atlas-gateway   → 26 tests passed (5 suites, 1.21s)
```

- All 5 new handler functions present in lib.rs
- All new routes registered (no duplicate /v1/wiki/pages)
- get_wiki_page returns Ok(None) for unknown slug
- list_models returns Ok(vec![]) when model_registry table absent

## Known Stubs

None. All five endpoints are fully wired — reads go direct to SQLite, writes dispatch to atlas CLI.

## Threat Surface Scan

No new trust boundaries beyond those in the plan's threat model:
- T-08-05: wiki create/update body inputs passed as explicit named CLI args (--title, --body, --slug) via tokio::process::Command argv — no shell interpolation
- T-08-06: cancel_run mission ID from URL path param passed as positional CLI arg — no shell interpolation
- No new network endpoints, auth paths, or schema changes beyond the plan's specification

## Self-Check: PASSED

- b8ee45e: `get_wiki_page` and `list_models` in db.rs — verified present
- 124022d: all 5 handlers and routes in lib.rs — verified present
- cargo build -p atlas-gateway: exit 0
- cargo test -p atlas-gateway: 26 passed
