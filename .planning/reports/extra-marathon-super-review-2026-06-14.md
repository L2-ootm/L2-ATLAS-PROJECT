# L2 ATLAS EXTRA-MARATHON SUPER REVIEW — 2026-06-14

Reviewer: Claude (Opus 4.8), adversarial extra-marathon standard.
Scope: verify reality before Phase 09. No new product features built. No artifacts deleted.

## 1. Verdict

**Approved to plan Phase 09 — after fixes.**

The shipped codebase is in good shape: 160 automated tests pass (134 Python + 26 Rust), Phase 8 is genuinely verified, and the Phase 8 Judge Report is honest and accurate. The project is **not** at risk from bad code. It is at risk from **unsafe continuation state**: an internally self-contradicting `STATE.md`, and a large, fully-uncommitted, off-roadmap subsystem (module catalog + installer + L2-BOT integration runtime) that no phase owns and that contradicts the project's own anti-speculation guidance. These are state/process hygiene blockers, not architecture failures. Resolve the three blockers in §3 and Phase 09 (skill inventory, doc-only) can start safely with the smallest scope already correctly defined in its `CONTEXT.md`.

## 2. Repo truth inspected

**Git status summary** (`git status --short -uall`): 5 modified tracked files (`.gitignore`, `docs/architecture/OVERVIEW.md`, `docs/plans/PHASE_7_8_READINESS.md`, `services/agent-runtime/atlas_runtime/cli/main.py`, `wiki/index.md`, `wiki/log.md`) and a large block of untracked files in four clusters: (a) generated logs (`.playwright-cli/`, `native/.../.playwright-cli/`, `services/web-ui/.playwright-cli/`, `services/integration-runtime/.pytest_cache/`); (b) module catalog (`modules/`, `scripts/list_modules.py`, `docs/architecture/MODULE_SYSTEM.md`); (c) installer (`install/`, `packages/atlas-installer/`, `docs/operations/MODULE_INSTALLATION.md`); (d) L2-BOT integration runtime (`services/integration-runtime/`, `docs/operations/L2_BOT_HARNESS_INTEGRATION.md`). No `.planning/` files are dirty — the planning state inconsistencies below are in committed files.

**Commit head:** `c5ddf3d docs(phase-08): evolve PROJECT.md after phase completion`. Branch `main`.

**Files/dirs inspected:** `.planning/STATE.md`, `ROADMAP.md`, `PROJECT.md`, `AGENTS.md`, `.planning/phases/08-cockpit/{08-JUDGE-REPORT,08-VERIFICATION}.md`, `.planning/phases/09-skill-inventory/CONTEXT.md`, `docs/architecture/{OVERVIEW,MODULE_SYSTEM}.md`, `docs/operations/L2_BOT_HARNESS_INTEGRATION.md`, `services/integration-runtime/atlas_integrations/l2_bot/adapter.py`, gateway test files, `infra/migrations/`, module trees, `docs/operations/`.

**Commands run:**
- `git status --short -uall`, `git log`, `git diff` on each modified tracked file.
- Python: `pytest -q` in `packages/atlas-core` (33), `services/agent-runtime` (54), `services/wiki-runtime` (31), `services/integration-runtime` (16). All pass via `.venv` (Python 3.11.15).
- Rust: `cargo test -p atlas-gateway` → 26 passed (1.42s). cargo 1.96.0.
- Enumerated gateway test function names in `crates/atlas-gateway/tests/{api,contract}.rs`.

**Commands NOT run and why:**
- Svelte build/`svelte-check` — not re-run; Phase 8 verification confirms `build/` output exists with all 5 route HTML files. Cost (npm install + build) not justified given existing evidence; flagged as not-independently-reverified.
- Fresh-DB bootstrap smoke (migrate → one write per CLI surface) — does not exist as a script (Judge item 7); could not run what isn't there. This is itself a finding (§6).
- Live browser E2E (SSE stream, JSONL export, debounce, load time) — requires running gateway + dev server + active run; Phase 8 left these as `human_needed`. Not re-run; routed to operator UAT.

## 3. Critical blockers

**B1 — `STATE.md` is internally self-contradictory; continuation tooling cannot trust it.**
- Evidence: `.planning/STATE.md` frontmatter says `completed_phases: 7`, `percent: 70`, and the Phase History table (lines 112–114) marks Phase 7 and Phase 8 **Pending**. The body (line 14, 21–23) says "Phase 08 complete (6/6) — ready to discuss Phase 09" and "Phase: 09", while line 23 still reads "Next: Execute Phase 08". `ROADMAP.md` (lines 20–21, 314–315) and `PROJECT.md` (line 104) both say Phases 1–8 complete. Three sources inside one file disagree.
- Impact: any GSD command (or human) that reads frontmatter/history will believe Phase 7–8 are unbuilt and 30% of work remains, while the body says the opposite. Auto-progression logic keys off `completed_phases`/`percent`. This makes automated continuation unsafe.
- Required fix: set frontmatter `completed_phases: 8`, recompute `percent` (8/9 real phases ≈ 89%, or 8/10 if Phase 10 counts), set Phase History rows 7 and 8 to `Done` with their completion dates (2026-06-11, 2026-06-12), and delete the stale "Next: Execute Phase 08" line. Make STATE agree with ROADMAP and PROJECT.

**B2 — Large off-roadmap subsystem is uncommitted, unowned, and contradicts the project's own guidance.**
- Evidence: `modules/` (4 manifests + schema), `scripts/list_modules.py`, `install/` (ps1+sh), `packages/atlas-installer/`, and `services/integration-runtime/` (full Python package: adapter, CLI, 16 tests) are all untracked. `docs/architecture/OVERVIEW.md` diff documents them as "Active". `services/agent-runtime/atlas_runtime/cli/main.py` has an uncommitted edit wiring `integrations_app` into the `atlas` CLI. None of this appears in `ROADMAP.md`. The Phase 8 Judge Report **item 12** explicitly says: "A genuine module system still needs route-level code splitting and per-module API namespaces; **defer until CASHFLOW forces the abstraction (pain-driven, do not build it speculatively).**" The module system was then built speculatively the same week.
- Impact: (a) continuation is destructive-unsafe — a `git clean -fdx` or accidental checkout destroys an entire untested-in-CI subsystem and ~9 files of docs; (b) the installer is Phase 10 territory per ROADMAP ("no installer story until Phase 10"); (c) L2-BOT channel integration is v2.0 territory; (d) it directly violates the anti-speculation discipline the project just wrote down.
- Required fix (decide explicitly, do not drift): either **(a)** carve an explicit phase entry (e.g. an inserted "Integrations & Module Catalog" phase, or fold into the Phase 11 channels milestone), commit the work with a `.gitignore` update for generated artifacts, and accept it as scope; or **(b)** move it off `main`'s working tree (dedicated branch / `git stash` / worktree) until a phase owns it. Do not begin Phase 09 on top of an uncommitted parallel subsystem.

**B3 — D-022 Rust-first / new-Python-service tension is unresolved for `services/integration-runtime/`.**
- Evidence: `services/integration-runtime/` is a new Python service package (`pyproject.toml`, `atlas_integrations` with adapter + Typer CLI). `PROJECT.md` Non-Negotiables (line 87) and `AGENTS.md` (lines 24–34) state: "no new Python service code outside the exception buckets (Hermes foundation surface, LLM adapters, throwaway scripts)." An external-harness integration adapter is none of those three.
- Impact: either the policy has an undocumented fourth exception bucket (operator-side integration adapters), or this is a silent D-022 breach. Left ambiguous, every future integration will cite this as precedent and the Rust-first policy erodes.
- Required fix: make an explicit decision record — either add "external integration adapters" as a sanctioned Python exception under D-022 (with rationale: I/O-bound, operator-side, read-only detection), or schedule it for Rust cementation. Tie this to the B2 decision.

## 4. High-priority issues

**H1 — Four Phase-8 gateway surfaces shipped with zero tests.** `crates/atlas-gateway/tests/api.rs` has 23 tests and `contract.rs` has 3, but none cover `wiki_create` (POST), `wiki_update` (PUT), `models_list` (GET /v1/models), or `cancel_run` (POST /v1/missions/{id}/cancel) — the exact handlers Phase 8 added (`lib.rs` 485/517/556/571). Confirms Judge item 5. Impact: the write/cancel/model paths Phase 09 may build on are unverified. Fix: `/gsd-add-tests 8` adding handler tests + a slug round-trip and SSE replay-from-0 regression (CR-02/CR-03).

**H2 — No canonical runbook; gateway env-coupling is tribal knowledge.** `docs/operations/RUNNING.md` does not exist (Judge item 8 recommendation unimplemented). Startup requirements (`ATLAS_CLI`, `ATLAS_WIKI_DIR`, migrate 0001–0003, ports 8484/5173) are scattered across `PROJECT.md` line 104, `08-VERIFICATION.md`, and `08-06-SUMMARY.md`. Impact: a fresh operator cannot start the system without reading phase summaries (fails Gate D). Fix: one `docs/operations/RUNNING.md` + fail-fast CLI-exists check at gateway boot.

**H3 — Generated artifacts are untracked and not gitignored.** `.playwright-cli/` (3 dirs of console/page/png logs), `services/integration-runtime/.pytest_cache/`, and `__pycache__/*.pyc` under integration-runtime are untracked. The `.gitignore` edit added only `.superpowers/`, not these. Impact: noise in `git status`, risk of accidental commit, and they obscure real drift. Fix: add `.playwright-cli/`, `.pytest_cache/` to `.gitignore`; confirm `__pycache__/` already covered (it is for tracked trees, but new tree needs the root pattern to apply).

## 5. Contract/schema/API drift findings

- **Resolved-but-untested drift (good).** The Phase 8 Judge Report (items 1–2) documents that frontend `api.ts` types and `08-UI-SPEC` fields were invented ahead of the real gateway contract (`rowid/payload/created_at` vs real `cursor/data/timestamp`; invented model `tier/health/policy`, wiki `layer`, provenance `sha256/lint_status`). Commits 83c6092 and the 08-06 rewrites fixed them, and 08-VERIFICATION traces each surface to real DB queries (FLOWING). This is real, and the root-cause ("contracts invented upstream of reality") is correctly diagnosed.
- **Remaining contract gap:** `contract.rs` verifies only `mission_response`, `run_response`, and `audit_event_response` against the Pydantic JSON Schema (D-012). The Phase-8-added shapes — `wiki_page`, `model_entry` — have **no** contract test, so the same invented-field class of bug can recur there undetected. Recommendation for Phase 09+: extend `contract.rs` to assert every gateway response shape against `atlas_core.*.model_json_schema()`, and adopt a contract-first rule (frontend types generated from the schema, never from a spec) as a standing process gate.

## 6. Test/CI gaps

- **Pass inventory (verified this review):** atlas-core 33, agent-runtime 54, wiki-runtime 31, integration-runtime 16 (Python) + gateway 26 (Rust) = **160 green.**
- **No fresh-DB smoke** (Judge item 7). The Phase-6 operator-run FK bug detonated only on a fresh DB during Phase 8; nothing exercises migrate→write-per-CLI-surface. This is the single highest-value missing test.
- **Gateway write/cancel/model surfaces untested** (H1).
- **`strict: false` + warn-level prerender** (Judge item 13 / IN-12): broken routes never fail a build, so Svelte build "green" is a weak signal. Svelte build/check not re-run this review.
- **integration-runtime is not in any CI/install wiring** beyond `modules/core/manifest.json` install steps — its 16 tests run only if someone `cd`s into it.

## 7. Runtime/operations gaps

- No canonical `RUNNING.md` (H2). Env-coupling (`ATLAS_CLI`, `ATLAS_WIKI_DIR`) is fail-late, not fail-fast.
- Migrations 0001–0003 exist (`infra/migrations/`), but the "apply 0001–0003 on fresh installs" instruction lives only in prose, not a script.
- Installer scaffold (`install/`, `packages/atlas-installer/`) exists but is uncommitted, dry-run, and Phase-10-premature (B2). README-to-first-mission path — the real adoption metric per Judge item 11 — is still undocumented.
- Remote Google Fonts (IN-06) contradict the offline/local-first claim; deferred but unresolved.

## 8. Product/UX gaps

Phase 8 verification (18/18 static truths) is thorough, but 6 runtime behaviors remain `human_needed` and were **not** re-verified live this review: SSE live stream, create-flash animation, JSONL export download, 300ms search debounce, gateway health poll, and <2s DOMContentLoaded (claimed 12ms in 08-06-SUMMARY, unconfirmed in operator env). Deferred UX debt tracked but open: `window.location.href`→`goto` (IN-03), runs index placeholder copy (IN-05), modal focus-trap/Escape (IN-09), self-host fonts (IN-06), lint contradiction rule is subject-blind (IN-07). None block Phase 09 (doc-only), but they block "daily-usable product."

## 9. Architecture/scope risk

- **Core architecture is coherent.** Layer separation (raw / wiki / runtime / cockpit) holds. Rust gateway reads SQLite directly and writes via `atlas` CLI dispatch per D-022. Phase 8 cockpit is adapter-static and native-portable for the Phase 10 Tauri shell. No Electron. This is sound.
- **Subprocess-per-write is the real ceiling** (Judge item 10): every write spawns the Python CLI against one SQLite store. Correct and acceptable **only** as a local-first single-operator tool. The stated "60% elite-dev adoption / GitHub influence" ambition is a different product (auth, direct DB writes, job queue). Decision must be stated explicitly: ATLAS v1 = local-first single-operator. Do not let hosted/multi-user creep in without a gateway rewrite.
- **Scope creep is the dominant risk, not under-building.** The uncommitted module/installer/L2-BOT subsystem (B2) is precisely the "project collapsing under accumulated ambition" failure mode. The discipline that wrote Judge item 12 must be applied to the work that violated it.
- **Phase 9 scope is correctly bounded** in `09-skill-inventory/CONTEXT.md` ("do not build a skill UI or marketplace... do not write a skill auto-discovery service... classify existing ones"). Keep it there.

## 10. Idempotency/antifragility risks

- **Module manifests claim idempotent lifecycle** (`MODULE_SYSTEM.md`: "install.steps re-run safely; healthcheck is read-only") but there is **no test** asserting re-running `install.steps` is a no-op, and no installer actually executes them yet. Claim is unverified.
- **L2-BOT adapter is correctly antifragile** (`adapter.py`): pure filesystem existence checks, presence-only `.env` boolean, never boots the bot, never reads secrets, never calls Discord. This is the right safety posture and is tested (16 tests).
- **Gateway write path** dispatches to the `atlas` CLI with a 30s timeout (added Phase 8). On dispatch failure mid-write, partial DB state risk depends on CLI transaction discipline — covered for audit writes (Phase 4 SC#6) but not asserted for the new wiki write/cancel paths (ties to H1).
- **SSE replay** (`sse_stream_replays_events_and_ends_for_finished_run`) is tested for finished runs; replay-from-0 on reconnect (CR-02) regression test is still missing.

## 11. Entropy cleanup list

| Item | Classification |
|---|---|
| `.playwright-cli/`, `native/.../.playwright-cli/`, `services/web-ui/.playwright-cli/` (console/page/png logs) | **ignore** — add to `.gitignore`, then they vanish from status |
| `services/integration-runtime/.pytest_cache/`, `__pycache__/*.pyc` | **ignore** — add patterns; never commit |
| `modules/`, `scripts/list_modules.py`, `docs/architecture/MODULE_SYSTEM.md` | **investigate → commit-under-explicit-phase or branch-out** (B2) |
| `install/`, `packages/atlas-installer/`, `docs/operations/MODULE_INSTALLATION.md` | **investigate → defer to Phase 10** (B2); branch-out of `main` |
| `services/integration-runtime/`, `docs/operations/L2_BOT_HARNESS_INTEGRATION.md`, `main.py` edit | **investigate → commit-under-explicit-phase** with D-022 decision (B2/B3) |
| `docs/architecture/OVERVIEW.md`, `docs/plans/PHASE_7_8_READINESS.md` edits | **commit** — accurate doc updates, but only alongside the work they describe (B2) |
| `wiki/index.md`, `wiki/log.md` edits | **commit** — runtime-generated wiki state from operator writes; confirm they are intended output, then commit |
| `.gitignore` `.superpowers/` edit | **commit** — correct, extend with the ignore patterns above |
| `STATE.md` self-contradiction | **fix** (B1) — not deletion, reconciliation |

## 12. Phase 09 readiness decision

- **What Phase 09 should do:** produce `docs/imports/SKILL_INVENTORY.md` — every skill from the Hermes skills dir, `l2-agent-skills`, and imported GSD/legacy skill packs, classified (core / operator / l2-internal / personal-private / experimental / deprecated) with public-safe and polish-required flags; full metadata for Core + Operator packs (SKILLS-01..04). Documentation and classification only.
- **What Phase 09 must NOT do:** build a skill UI, marketplace, auto-discovery service, or versioning infra (per `CONTEXT.md`); reference any `C:/Users/Davi/AppData/Local/hermes/` personal/private skill paths in public manifests; and **must not** absorb, formalize, or extend the uncommitted module/installer/L2-BOT subsystem — that is a separate scope decision (B2).
- **Preconditions before Phase 09 starts:** (1) B1 — STATE.md reconciled and consistent with ROADMAP; (2) B2 — the uncommitted subsystem is either committed under an explicit phase or moved off `main`'s working tree, so `main` is clean and continuation is non-destructive; (3) generated-artifact gitignore (H3) applied. H1 (gateway tests) is strongly recommended but can run in parallel since Phase 09 is doc-only and does not touch the gateway.
- **Smallest safe Phase 09 scope:** the classification document plus pack metadata. No code, no registry service, no manifests beyond the inventory doc. This is exactly what `CONTEXT.md` already specifies — do not expand it.

## 13. Recommended next 3 actions

1. **Reconcile `STATE.md`** (B1): frontmatter `completed_phases: 8` + recomputed percent, Phase History rows 7–8 → `Done` (2026-06-11 / 2026-06-12), delete the stale "Next: Execute Phase 08" line. Single source of truth restored.
2. **Resolve the uncommitted subsystem** (B2/B3): decide commit-under-explicit-phase vs branch-out. If committing, add the ROADMAP phase entry + D-022 Python-exception decision record, add the gitignore patterns (H3), and commit; if deferring, move it to a branch/worktree so `main` is clean. Either way, `main`'s working tree must be safe before Phase 09.
3. **`/gsd-add-tests 8`** (H1 + fresh-DB smoke): cover `wiki_create`/`wiki_update`/`models_list`/`cancel_run`, add a migrate→write-per-surface fresh-DB smoke, and a slug round-trip + SSE replay-from-0 regression. Run in parallel with Phase 09 planning.

## 14. Verification evidence appendix

```
$ git log -1 --format='%H %s'
c5ddf3d0af1e280cce6ad3ba133f9ca38d79cc3f docs(phase-08): evolve PROJECT.md after phase completion

# Python suites (.venv, Python 3.11.15)
packages/atlas-core      : 33 passed
services/agent-runtime   : 54 passed
services/wiki-runtime    : 31 passed
services/integration-runtime : 16 passed

# Rust (cargo 1.96.0)
$ cargo test -p atlas-gateway
26 passed (5 suites, 1.42s)

# Gateway test coverage gap (api.rs / contract.rs test fn names)
present: health, missions_list, mission_detail, run_detail, run_events,
         wiki_search, wiki_pages, sse_stream (replay + 404),
         post_mission, start_run, mission/run/audit_event contract
ABSENT : wiki_create, wiki_update, models_list, cancel_run   <-- Phase 8 surfaces, untested

# Migrations
infra/migrations/0001_core.sql  0002_wiki_provenance.sql  0003_model_registry.sql

# Runbook check
docs/operations/RUNNING.md -> does not exist  (Judge item 8 unimplemented)

# STATE.md contradiction (committed file)
frontmatter: completed_phases: 7 / percent: 70
Phase History table: Phase 7 Pending | Phase 8 Pending
body line 14: "Phase 08 complete (6/6) — ready to discuss Phase 09"
body line 23: "Next: Execute Phase 08"
ROADMAP.md / PROJECT.md: Phases 1–8 complete

# Off-roadmap untracked subsystem
modules/{core,l2-bot-harness,skills}/manifest.json + manifest.schema.json + README.md
scripts/list_modules.py
install/{README.md,unix/install.sh,windows/install.ps1}
packages/atlas-installer/{package.json,README.md}
services/integration-runtime/  (atlas_integrations: adapter.py, cli.py, l2_bot/; tests 16)
main.py (uncommitted): app.add_typer(integrations_app, name="integrations")
```

_Review complete. The build is sound; the bookkeeping and scope discipline are the risk. Fix B1–B3 and Phase 09 starts on safe ground._
