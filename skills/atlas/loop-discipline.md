# Skill: loop-discipline

**Use when:** running any multi-step change — planning a slice, executing it,
re-planning after contrary evidence, or deciding whether a change is verified
before you claim it is done. Also when a run came back unverified and you need
to know which tests, checks and verification evidence actually count.

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

   This step is checked mechanically. At run end ATLAS rebuilds what you did
   from the audit trail and files the run as one of four states:

   | verdict | what the trail showed |
   |---|---|
   | `no_mutations` | nothing observable changed — nothing to verify |
   | `verified` | you changed state, then a test/build/lint/typecheck ran and passed |
   | `contradicted` | you changed state, checks ran, and every one of them failed |
   | `unverified` | you changed state and never checked it |

   Three things follow from how it counts. The check must come **after** the
   change — a suite you ran before editing proves nothing about the edit.
   `git status` and re-reading a file you just wrote are recorded, but they are
   weak signals and never make a run `verified`. And a `contradicted` run that
   reports success is prefixed `[verification failed]` in its own summary,
   because that combination is a false claim, not a near miss.

   The verdict is durable (`verification_verdict` audit event) and its
   uncertainty reaches the next run's context, so an unverified change is
   something a later run inherits rather than something that disappears at the
   end of this one. When you genuinely cannot verify — no suite exists, the
   environment is missing — say so in your own words too; the gate records the
   absence of evidence, not your reason for it.

   **An `unverified` run does not simply end.** It is given one more turn whose
   only job is to run a check, and that turn is spent from the same budget as
   the rest of the run. Checking your own work in the first place is therefore
   strictly cheaper than being asked to. Only the commands you run in that turn
   count — restating the answer changes nothing, and the demand is issued once,
   so a run that ignores it finishes `unverified` on the record.
5. **Report honestly.** Failures and skipped verification are stated plainly,
   with the evidence. A summary that hides a red test is a defect.
6. **Reduce entropy on contact.** If you find drift (stale docs, dead code,
   duplicated state) in the files you touch, fix it if trivial or record it if
   not — never widen scope silently.
7. **Stop conditions.** Stop and surface to the operator when: an action is
   destructive or hard to reverse, a secret/credential would be exposed, the
   goal has drifted from what was asked, or the same failure repeats twice
   with no new information.
