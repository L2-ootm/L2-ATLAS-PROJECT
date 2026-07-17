# GSD/L2 · execute — atomic delivery with honest deviations

Use with an existing PLAN.md. Execution is the only step that changes product
code; everything it does must be reconstructible from commits + SUMMARY.md.

## Procedure

1. Read PLAN.md and CONTEXT.md. Refuse to execute a plan whose done-conditions
   are uncheckable — route back to `plan.md` instead of improvising.
2. Per task: implement → run the task's done-condition → commit. One commit
   per task (or per coherent sub-change), conventional message, what+why.
3. **Deviation rules** — when reality disagrees with the plan:
   - *Bug found in touched code:* fix it, note it in SUMMARY.md.
   - *Plan step impossible/wrong:* stop the step, record the reason, do the
     minimal correct alternative if obvious, otherwise surface to the
     operator. Never silently substitute a different scope.
   - *Locked decision needs changing:* stop and surface — that is a context
     change, not an execution detail.
4. Track progress in PLAN.md checkboxes as tasks complete, so an interrupted
   session resumes from the file, not from memory.
5. Finish with `.planning/phases/<NN-slug>/SUMMARY.md`: what shipped (with
   commit hashes), deviations, what verification ran, what is owed.
6. Update STATE.md's Current Position before ending the session.

## ATLAS-native

- Task groups marked `[actor-ok]` may run as durable actors: spawn with
  stable idempotency keys, then `status`/`wait` — never respawn after an
  ambiguous failure without checking status first.
- Every run is already in the audit ledger; cite run ids in SUMMARY.md for
  anything a reviewer would want to replay.
- Long autonomous stretches run as a judged mission (`/goal`) whose stop
  condition is the plan's verification block — the judge enforces the
  done-conditions, not vibes.
