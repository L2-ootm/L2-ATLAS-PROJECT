# HANDOFF / ROADMAP CONSISTENCY REVIEW — 2026-07-03

Session start of the multi-session finish mission (donor TUI refactor, installer, CLI polish,
surface wiring, TUI caching). Verified before trusting continuation state.

## 1. Inspected

- `HANDOFF.md` (finish-sprint handoff, 2026-07-03)
- `.planning/STATE.md` (Current Position: 5 finish-sprint items)
- `.planning/ROADMAP.md` (v1.1 active, finish-sprint overlay section)
- `docs/plans/2026-07-03-mimo-donor-tui-refactor-plan.md`
- `docs/plans/2026-07-03-sprint-to-2026-07-09-milestone-finish.md`
- `docs/architecture/OMNI_SURFACE_WIRING_STRATEGY.md`
- `git status --short -uall`, `git log`

## 2. Inconsistencies found

1. **STATE.md claimed STAGE 0 committed; it was not.** The Current Position item 5 said
   "plan committed ... (this commit)" but the plan doc, `OMNI_SURFACE_WIRING_STRATEGY.md`,
   and the entire `services/atlas-terminal/` package (8 files) were untracked. Last commit
   on main was `9a64daba` (dynamic Models).
2. **Uncommitted post-commit WIP broke tests.** 8 tracked files modified (freellmapi
   api-key injection into `atlas models refresh`, sidecar panel moved Models→Settings,
   canonical provider naming, sidecar start/stop in Settings). 7 cockpit tests + 1
   agent-runtime test failed because tests were not updated with the UI/contract change.
3. **Stray `get_key.py` at repo root** — scratch script reading the freellmapi
   `unified_api_key` from the sidecar DB. Its logic was productionized as
   `freellmapi_control.get_api_key()`; the scratch remains untracked. Recommend deletion.

## 3. Fixes made

- Updated `src/test/models.test.tsx` (sidecar panel no longer on Models — asserted absence),
  `src/test/settings.test.tsx` (mocked `freellmapiStatus/Start/Stop`; sidecar absent by
  default so the freellmapi base-URL guard test still exercises the empty path),
  `tests/test_freellmapi_control.py` (status shape now includes `api_key`; 2 new
  `get_api_key` tests: absent checkout, real sqlite read).
- WIP + STAGE 0 committed (see git log after this report).

## 4. Drift-signal grep results

- No donor-identity drift checked yet in `services/atlas-terminal` beyond notices
  (`ATTRIBUTION.md` present); full boundary-scan extension is a STAGE 2 deliverable.
- **Flag for operator review:** `freellmapi_control.status()` now returns the sidecar
  `api_key` in cleartext, exposed via `atlas freellmapi status --json` and gateway
  `/v1/freellmapi/status`, consumed by Settings autofill. This is a deliberate local-only
  convenience (self-hosted sidecar key, loopback gateway) but diverges from the
  masked-secret contract used everywhere else. Documented; not reverted.

## 5. Remaining concerns

- Go TUI remains default surface; atlas-terminal is STAGE 0 only (adapter skeleton).
- ROADMAP phase table still shows 10.8 "Not planned"; the finish-sprint overlay is the
  operative plan — acceptable, but 10.8 closeout must reconcile it.

## 6. Verification commands

- `bun test` (atlas-terminal): 5 pass. `bunx tsc --noEmit`: clean.
- `bun run src/main.tsx --smoke`: exit 0, gateway LIVE (freellmapi/mimo-v2.5).
- Cockpit `npm test`: 44/44 after fixes; `tsc --noEmit` clean.
- agent-runtime focused `-k "freellmapi or models"`: 23 passed. Full suite run at commit time.

## 7. Result

Handoff usable. STAGE 0 claims verified true at code level; the "committed" claim was the
only material falsehood and is corrected by committing. Continue to STAGE 1.
