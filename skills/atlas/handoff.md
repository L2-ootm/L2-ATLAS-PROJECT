# Skill: handoff

When a session changed project state, leave a handoff the next session (agent
or human) can trust without this conversation's history.

Write to the project's handoff/state file (HANDOFF.md or equivalent):

1. **What changed** — files, commits, migrations, config; exact paths.
2. **What was verified** — which suites/builds ran and their real results.
   Distinguish verified facts from likely inferences from open questions.
3. **What is owed** — UAT the environment couldn't perform, deferred slices,
   known gaps. An unstated gap is a trap for the next session.
4. **Next actions** — concrete, ordered, safe to start cold.

Rules: counts must match `git status`; never write "production-ready" or
"complete" without the evidence line that proves it; never mark historical
work as done because it looks done — check the repo truth first.
