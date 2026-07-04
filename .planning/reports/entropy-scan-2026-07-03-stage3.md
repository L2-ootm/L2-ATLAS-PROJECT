# ENTROPY SCAN — 2026-07-03 (STAGE 3 session)

Scope: this session's slices — services/atlas-terminal (donor TUI vendor-tree
scrub, settings/readiness port, slash commands, freellmapi control, boundary
scanner wiring) and packages/atlas-cli (new WS-B installer scaffold). Report-
first; only evidence-backed safe fixes applied.

## Executive read

Working tree was already clean at scan time (`git status --short` empty) —
all session commits landed with passing verification (tsc/tests/smoke or
node --test, per commit). No stray scratch files, no dead code introduced.
The one real finding is doc drift: `.planning/STATE.md` (the formal GSD state
tracker) was last touched at the STAGE 2-complete commit and does not
reflect this session's STAGE 3 work, which lives in `HANDOFF.md` and
`docs/plans/*` instead. Applied a pointer update rather than duplicating
HANDOFF's detail into STATE.md.

## Surfaces inspected

- `git status --short`, `git ls-files | grep -iE "\.bak$|\.orig$|~$|scratch|get_key"`
  — clean; two scratch probe files created mid-session
  (`probe_session.ts`, `probe_session2.ts` in services/atlas-terminal) were
  already deleted before any commit, so nothing to clean here.
- `services/atlas-terminal`: `bunx tsc --noEmit`, `bun test` (25/25),
  `bun run smoke` — all green as of the last commit in this session.
- `packages/atlas-cli`: `node --test test/commands.test.js` (7/7) plus a
  manual end-to-end install→doctor→update→doctor→rollback→doctor→
  uninstall→doctor cycle against a scratch `ATLAS_HOME` — verified, then
  the scratch directory was removed.
- `.planning/STATE.md` vs `HANDOFF.md`: STATE.md's last entry is the STAGE 2
  architectural mandate note (commit `36fbd59e`); HANDOFF.md has since
  gained the full STAGE 3 narrative (branding scrub, login-dialog removal,
  settings/readiness port, slash commands, boundary scanner, installer
  scaffold, parity audit conclusion) across 8 commits. STATE.md had not
  been updated to match.
- `.planning/ROADMAP.md`: no mention of WS-B/installer/atlas-cli at all —
  not drift, since this sprint's workstream tracking (WS-A..G) was never
  folded into ROADMAP.md; it lives in the mission-analysis doc and
  HANDOFF.md by design (session's own prior convention, not something this
  scan should silently change).

## Safe deletions

None found in scope — no dead files, unused exports, or orphaned scripts
from this session's work.

## Applied fixes

- `.planning/STATE.md`: appended a dated pointer entry noting STAGE 3
  progress and directing to HANDOFF.md, so the two docs don't silently
  diverge on "what stage are we at."

## Consolidation / modularization candidates

None identified — `packages/atlas-cli` and `services/atlas-terminal`'s new
files (`src/adapter/commands.ts`, `src/tui/util/readiness.ts`, the settings
dialog) are each single-purpose additions with one call site; no repeated
logic to fold together yet.

## Deferred (do not touch yet)

- `foundation/atlas-hermes/**/dist/*.js` and `dist/*.css` (two vendored
  dashboard plugins) are tracked in git as committed build output. This
  predates this session and is out of this scan's scope — worth a separate,
  deliberate look at whether that vendoring choice (committed dist vs.
  build-on-install) is still intentional, but not something to touch inside
  a STAGE 3 TUI-focused pass.
- The parity-audit-flagged donor surface (`dialog-go-upsell.tsx`, `/share`,
  `tui-migrate.ts`'s `TUI_SCHEMA_URL`, ~30 theme JSON `$schema` URLs — all
  pointing at `opencode.ai`) is real remaining vendor-tree surface, already
  logged in HANDOFF.md as a flagged-not-fixed item from the parity audit,
  not re-litigated here. It doesn't currently do anything (the `/share`
  backend route is unimplemented, so nothing is actually sent to a third
  party) — a product decision (remove vs. give ATLAS its own equivalent),
  not a cleanup.

## Contract/idempotency notes

- `packages/atlas-cli`'s `install`/`update` refuse to clobber an existing
  version directory (`CliError` if the target version already exists) —
  covered by a dedicated test.
- `rollback` without a recorded `previousVersion` and no explicit `--to`
  fails closed with a `CliError` rather than guessing — covered by a test.
- `doctor`'s manifest-checksum verification correctly flags drift (tested by
  tampering a file post-install and re-running doctor).

## Verification plan (executed)

atlas-terminal: `bunx tsc --noEmit` ✓ · `bun test` 25/25 ✓ · `bun run smoke` ✓
· boundary scan (`scan-atlas-terminal-boundary.ps1`) passes clean, self-test
passes ✓.
atlas-cli: `node --test test/commands.test.js` 7/7 ✓ · manual end-to-end
lifecycle cycle ✓ (scratch directory removed after).
Working tree: `git status --short` clean before and after this scan (no
uncommitted drift introduced).
