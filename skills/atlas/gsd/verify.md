# GSD/L2 · verify — the goal, proven backward

Use after execution claims a phase is done. Verification checks the **goal**,
not the task list — completed tasks are the weakest form of evidence.

## Produce

`.planning/phases/<NN-slug>/VERIFICATION.md`:

- **Goal check** — does the codebase now deliver what the phase promised?
  Work backward from the promise to the artifacts that prove it.
- **Evidence table** — per claim, the tier it reaches:
  `registered` (code exists) → `configured` (wired) → `reachable` (responds)
  → `verified-live` (exercised end-to-end, output read). A claim without a
  tier is not a claim.
- **UAT owed** — everything only the operator/live environment can confirm,
  as concrete numbered steps.
- **Verdict** — `passed`, `passed-with-owed-UAT`, or `gaps` (with the gap
  list routed back to plan/execute).

## Procedure

1. Re-run the plan's verification block yourself; read the output. Reported
   counts must come from this run, not from execution's memory.
2. For each phase requirement: locate the delivering code/behavior and
   exercise it the way a user would (drive the surface, not just the tests).
3. Check the seams: does the feature survive a restart, a reload, an empty
   state, a second run (idempotency)?
4. Grep for drift the change should have removed (dead flags, stale docs,
   old names). Found drift is a finding, not a footnote.
5. Update STATE.md with the verdict.

## ATLAS-native

- "Exercise it like a user" means the real surface: WebUI page, terminal
  command, or gateway endpoint — cite the audit run id or screenshot path.
- Suites are necessary, not sufficient: green tests with an unproven surface
  is `configured`, not `verified-live`.
