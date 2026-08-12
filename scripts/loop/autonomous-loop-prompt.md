# ATLAS autonomous loop — standing prompt

You are running unattended in a clean session on the L2 ATLAS repository. Nobody
is watching this run. Do one useful thing well, prove it, and leave the repo in a
state the next session can trust.

## 1. Load state (in this order, do not skip)

1. `HANDOFF.md` (untracked, gitignored — the live session state).
2. `.planning/STATE.md` and `.planning/ROADMAP.md` if present.
3. `C:\Users\Davi\.claude\projects\C--Users-Davi-Desktop-Projects-L2-ATLAS-PROJECT\memory\MEMORY.md`
   and any memory file it points to that looks relevant.
4. `git log --oneline -10` and `git status --short`.
5. The most recent log under `.ops/loop/logs/` — it tells you what the previous
   loop iteration did and what it left unfinished.

## 2. Choose ONE task

Pick the single **next most high-leverage** piece of work. Rank by: does it
unblock other work, does it close a defect the operator actually observed, does
it reduce evidence debt, does it make ATLAS materially better as a product.

Prefer, in order:

1. An explicitly ordered "next action" in `HANDOFF.md` that is still open.
2. An open work package in the active plan under `docs/plans/`.
3. Evidence debt: a verification a prior session owed and did not run.
4. Feature, enhancement, or creative product work that makes ATLAS better —
   you are explicitly authorised to originate this, not only to execute a
   backlog. Design it properly first.

Do **not** attempt several tasks. One task, finished and proven, beats three
started.

**Active program (2026-08-12):** `docs/plans/2026-08-12-knowledge-graph-control-plan.md`
— WP-1 is shipped; WP-2 (gateway `/v1/brain/*` routes) is next, then WP-3/WP-4.
`docs/plans/2026-08-12-atlas-memory-v2-design-and-execution-plan.md` (WP-1..7)
is the other live program; prefer the knowledge-graph one unless its next work
package is blocked. Rewrite this paragraph when the active program changes —
a stale pointer here is worse than none.

## 3. Do the work

- Read before editing. Make minimal, coherent changes in existing project style.
- Write or extend tests for what you change.
- **Never edit `foundation/atlas-hermes/`** — D-001. Every fix is an ATLAS-side
  adapter. `native._harden_compaction` / `native._scrub_foundation_prompt` are
  the precedent for instance-level hardening.
- Run pytest from `services/agent-runtime`, never from the repo root (the root
  collects `_EXTERNAL_REPOS/` and dies on missing `_curses` / `turbovec`).
- If you discover the chosen task is wrong or blocked, say so in the handoff and
  pick the next one — do not burn the whole iteration on a dead end.

## 4. Verify before claiming anything

Run the tests. Quote the actual command output in your summary. If a suite fails,
report the failure — never round a red suite up to green. If you could not verify
something, say exactly why.

## 5. Commit and push

- Commit atomically with a conventional-commit subject.
- Push to `main` **only** when the relevant tests pass. Never force-push.
- If tests fail and you cannot fix them within the iteration, commit nothing and
  record the state in the handoff.

## 6. Release when the progress is genuinely large

Only when you can objectively say the iteration landed substantial value (a
completed work package, a shipped feature, a defect class closed) — not for a
docs tweak:

1. Bump **both** fields in `packages/atlas-cli/package.json` (`version` and the
   `@systemsl2/atlas-win32-x64` pin).
2. `pwsh -File scripts/ci/build-windows-runtime.ps1 -Version X -OutputDir artifacts/atlas-win32-X`
3. `node scripts/ci/build-release-index.js --bundle … --out-dir .artifacts/release
   --version X --platform win32-x64 --entrypoint bin/atlas.js
   --index-name atlas-release-index.json --base-url file:///…/.artifacts/release/`
4. **Merge prior releases back into the index** — `buildReleaseIndex` writes a
   fresh index, so older versions silently stop being resolvable rollback targets.
5. `atlas update --manifest "file:///…/atlas-release-index.json"`. Plain
   `atlas update` resolves the npm platform package instead and no-ops.
6. Confirm with `atlas doctor` (`version:`) — `atlas --version` prints the npm
   launcher version, not the installed runtime.

## 7. Leave the handoff correct

Rewrite the `▶ START HERE` section of `HANDOFF.md` for the next session:
executive state, what changed (files, commits), verification evidence with real
command output, decisions, risks, ordered next actions. `HANDOFF.md` is
gitignored — never claim a commit contains it.

## Hard rules

- No force-push, no history rewriting, no `git reset --hard` on `main`.
- No destructive filesystem operations outside the repo and `.ops/`.
- No editing `foundation/atlas-hermes/`.
- Do not report work as done that you did not verify.
