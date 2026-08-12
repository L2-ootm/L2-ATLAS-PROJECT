# Skill: loop-discipline

GSD-style execution loop for any multi-step change. The point: verified
progress over apparent progress.

1. **Load state before editing.** Read the relevant handoff/state/docs and the
   files you will change. Never continue from memory of a past session when a
   file can be read.
2. **Plan the smallest coherent slice.** One goal, bounded file set, explicit
   done-condition. Defer everything else explicitly (write it down).
   Write the plan to your scratchpad before a long task —
   `atlas_scratchpad op=write kind=plan title="<task>"` — and re-read it when
   you resume. The transcript does not survive a compaction; the scratchpad
   does. Findings you must not re-derive go in as `kind=finding`.
   **Re-plan deliberately** when evidence contradicts the plan: update the
   entry, say what changed, then continue. Two failures with no new
   information mean the approach is wrong, not the arguments.
3. **Execute with atomic commits.** Each commit is one logical change with a
   message stating what and why. Never mix unrelated changes.
4. **Verify before claiming.** Run the tests/build/typecheck that cover the
   change and read the output. "Should work" is not a state; capabilities are
   registered / configured / reachable / verified-live — say which one you
   proved.
5. **Report honestly.** Failures and skipped verification are stated plainly,
   with the evidence. A summary that hides a red test is a defect.
6. **Reduce entropy on contact.** If you find drift (stale docs, dead code,
   duplicated state) in the files you touch, fix it if trivial or record it if
   not — never widen scope silently.
7. **Stop conditions.** Stop and surface to the operator when: an action is
   destructive or hard to reverse, a secret/credential would be exposed, the
   goal has drifted from what was asked, or the same failure repeats twice
   with no new information.
