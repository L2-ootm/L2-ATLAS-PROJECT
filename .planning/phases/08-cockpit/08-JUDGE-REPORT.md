# Phase 8 Judge Report — Weaknesses and Scoping Risks

Date: 2026-06-12. Mandate: "analyse it to find weaknesses, be also a judge for our project, what is scoped in a bad way that will likely make us fail."

Every item below is classified: FACT (verified this phase), INFERENCE (follows from facts), or RECOMMENDATION.

## A. Process defects proven by this phase

1. **Speculative contracts (FACT).** Plans 08-02/08-03 defined `api.ts` types from UI-SPEC prose before the gateway contract existed. Result: `rowid/payload/created_at` vs the real `cursor/data/timestamp` — the runs page crashed on first load and needed commit 83c6092.
   RECOMMENDATION: contract-first. Frontend types must be derived from `db.rs` JSON emitters (or a shared schema file) — never from a design spec.

2. **Spec invented schema (FACT).** 08-UI-SPEC specified fields that do not exist anywhere in the store: model `tier/health/policy`, wiki `layer`, provenance `sha256/lint_status`. Three components shipped dead affordances and were rewritten.
   RECOMMENDATION: UI-SPEC authoring must include a schema audit step against `infra/migrations/`.

3. **CORS absent from every plan (FACT).** Without commit 3c18cb7 the entire cockpit was non-functional in a browser — the single most basic integration constraint of a "web UI talks to local gateway" phase was missed by planning and caught only in live E2E.
   INFERENCE: plan-checking validates internal coherence but not cross-boundary runtime constraints. RECOMMENDATION: add an "integration preconditions" checklist (CORS, auth, ports, env) to gateway-adjacent phases.

4. **Wave planning overlap (FACT).** Two wave-2 plans both listed `api.ts` in files_modified, forcing sequential fallback. Planner must treat files_modified intersection as a hard wave-split criterion.

5. **Zero tests for new gateway surface (FACT).** All 26 gateway tests predate Phase 8. The wiki write, models, cancel, and SSE handlers shipped untested; CR-02 (replay-from-0) and CR-03 (slug normalization break) are exactly the defects an SSE-reconnect test and a slug round-trip test would have caught.
   RECOMMENDATION: `/gsd-add-tests 8` before Phase 9 builds on these endpoints.

6. **Verification sweep missed a surface (FACT).** The E2E console sweep ran on /missions but not /wiki, so CR-01 (crash on first search keystroke) shipped. Verification plans must enumerate every route, not "the happy path."

7. **Dormant cross-phase defect (FACT).** The operator-run FK violation shipped in Phase 6 and only detonated here on a fresh DB. No CI job exercises a fresh-database bootstrap.
   RECOMMENDATION: add a fresh-DB smoke job (migrate → one write per CLI surface).

8. **Env-coupled gateway (FACT).** The gateway silently requires `ATLAS_CLI` and `ATLAS_WIKI_DIR`; wrong env produces "program not found" or files in the wrong tree. Documented in 08-06 SUMMARY, but there is no single canonical runbook.
   RECOMMENDATION: one `docs/operations/RUNNING.md` + fail-fast startup validation (gateway should verify the CLI exists at boot, not at first write).

9. **Agent mortality (FACT).** The code-fixer subagent died mid-task on a provider session limit. The spot-check-then-resume protocol worked, but orchestration must always assume subagents can die with partial uncommitted work.

## B. Scoping risks that can make the project fail

10. **Write path = subprocess per request (FACT today, risk forward).** Every write spawns the Python CLI (~hundreds of ms) against one SQLite store. Acceptable for a single operator; collapses under any multi-user or hosted ambition. The 30s dispatch timeout added this phase bounds the damage but does not change the architecture.
    INFERENCE: the loopback-only, no-auth, subprocess-write gateway and the stated "60% elite dev adoption / GitHub influence" goal are different products. Decide explicitly: ATLAS v1 is a **local-first single-operator tool** (defensible, differentiated) — do not let hosted/multi-user creep in without a gateway rewrite (auth, direct DB writes, job queue).

11. **Adoption philosophy vs. packaging reality (INFERENCE).** What could earn GitHub influence is already here: audit-everything provenance, mission/run model, local-first store. What blocks adoption is friction: no installer story until Phase 10 (Tauri), env-var setup, no docs site, remote Google Fonts contradicting the offline/local-first claim (IN-06). Elite developers judge a repo in minutes; the README-to-first-mission path is the real adoption metric, not UI polish.

12. **Module system is a seam, not yet a system (FACT).** `modules.ts` + sidebar registry is the right minimal seam, and L2 CASHFLOW will be its first real test. A genuine module system still needs route-level code splitting and per-module API namespaces; defer until CASHFLOW forces the abstraction (pain-driven, do not build it speculatively).

13. **CI blind spots (FACT).** `strict: false` + warn-level prerender handlers (IN-12) mean broken routes never fail a build. Tighten once the route set stabilizes.

## C. Deferred findings (tracked, non-blocking)

IN-03 (`window.location.href` → `goto`), IN-05 (runs index placeholder copy), IN-06 (self-host fonts), IN-09 (modal focus trap/Escape), IN-12 (strict prerender), IN-07 (lint contradiction rule subject-blind).

## Verdict

Phase 8 delivered its goal (6/6 requirements verified, all critical/warning review findings fixed and re-verified live). The recurring failure mode across the phase was **contracts invented upstream of reality** — spec fields, API types, and integration constraints written before checking the systems they describe. Every critical defect this phase traces to that one habit. Fix the process (schema-first specs, contract-derived types, integration-precondition checklists, tests for new surfaces) and the codebase quality is already at the bar the project aims for.
