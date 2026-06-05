---
phase: 1
slug: hermes-foundation-audit
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-04
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> **This is a pure audit phase — it writes NO product code.** Validation is therefore
> structural (artifacts exist, contain required content, external trees unmodified),
> not unit/integration testing. There is no Wave 0 test scaffolding because there is
> nothing executable to test.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — structural/documentation verification (file existence + content assertions + git state) |
| **Config file** | none — no test runner for a doc-only phase |
| **Quick run command** | `git status --short` (must be clean for external repos) + `test -f` on each deliverable |
| **Full suite command** | Phase-gate verification block (see Per-Task Verification Map) |
| **Estimated runtime** | < 5 seconds (filesystem + git assertions) |

---

## Sampling Rate

- **After every task commit:** Assert the task's deliverable file exists and the relevant external tree (`_EXTERNAL_REPOS/hermes-agent`, L2-Atlas source) is in the expected git state.
- **After every plan wave:** Re-run the structural assertions for all deliverables produced so far.
- **Before `/gsd-verify-work`:** All five success criteria from CONTEXT.md must assert true.
- **Max feedback latency:** 5 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | FOUND-01 | T-1-01 (secret leakage) | No secret-bearing file enters the repo; clone is fresh from upstream, never the AppData runtime install | structural | `git -C _EXTERNAL_REPOS/hermes-agent rev-parse HEAD` equals `e8b9369a9d2df36139a5055cae3ed3c15691e03e` | ✅ | ⬜ pending |
| 01-01-02 | 01 | 1 | FOUND-01 | T-1-01 | Secret-scan reports CLEAN before any `git add` of the clone or audit artifacts | structural | secret-scan exits 0 (no `.env`/`auth.json`/`*.db`/token matches in tracked paths) | ✅ | ⬜ pending |
| 01-02-01 | 02 | 2 | FOUND-02 | — | Audit doc records every extension surface with a sourced verdict | structural | `test -f docs/research/HERMES_FOUNDATION_AUDIT.md` and it contains a row for each: hook, tool registry, session store, delegation, cron, profiles, gateway, MCP, plugin surface, CLI/TUI boundary | ✅ | ⬜ pending |
| 01-02-02 | 02 | 2 | FOUND-02 | — | Audit states explicit YES/NO event-bus attach verdict | structural | audit doc contains a verdict line answering "can the audit-event bus attach via plugin/hook without editing cli.py/run_agent.py" with YES or NO | ✅ | ⬜ pending |
| 01-03-01 | 03 | 3 | FOUND-03 | — | Each identified divergence has a decision stub classified by the divergence policy | structural | `ls docs/decisions/` shows a stub per identified divergence, each tagged upstreamable/plugin-tool/ATLAS-only/experimental | ✅ | ⬜ pending |
| 01-04-01 | 04 | 4 | FOUND-04 | — | Every atlas_core donor module classified; data-carrying modules linked to Phase 2 | structural | `test -f docs/imports/L2_ATLAS_MODULE_EXTRACTION_PLAN.md` and it classifies all 6 modules (parser, policy, powershell, jsonl_logger, orchestrator, skills/registry) as port/rewrite/reference/discard | ✅ | ⬜ pending |
| 01-04-02 | 04 | 4 | FOUND-04 | — | L2-Atlas source tree unmodified by the audit | structural | L2-Atlas source repo `git status` is clean (read-only audit honored) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements — no test scaffolding applies to a doc-only audit phase. The "framework" is `git` + filesystem assertions, both already present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Extension-surface verdicts are accurate against the cloned source | FOUND-02 | Correctness of an audit claim cannot be asserted by file existence — it requires reading the actual cloned Hermes code | For each surface row, confirm the cited file/registration mechanism exists in `_EXTERNAL_REPOS/hermes-agent` at the pinned SHA; spot-check the event-bus verdict against the observability plugin template |
| Divergence classifications match the divergence policy order | FOUND-03 | Judgment call (plugin > tool > hook > skill > ATLAS-only > in-core) per divergence | Review each stub: confirm the chosen tier is the least-invasive option that achieves the goal |
| Module port/rewrite/reference/discard calls are justified | FOUND-04 | Each call depends on reading the donor module and checking Hermes overlap | Confirm each module's classification cites concrete evidence (deps, Windows-coupling, Hermes equivalent) |

---

## Validation Sign-Off

- [x] All tasks have structural automated verify (no executable code to unit-test in this phase)
- [x] Sampling continuity: every task has a structural assertion (file existence + git state)
- [x] Wave 0 covers all MISSING references (none — no test scaffolding needed)
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-04
