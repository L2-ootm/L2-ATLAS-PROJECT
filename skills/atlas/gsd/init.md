# GSD/L2 · init — bootstrap the planning contract

Use when a project (or a new milestone) has no `.planning/` contract yet.
Never overwrite an existing contract — read it and route to `progress.md`
instead.

## Produce

Create `.planning/` with exactly three living files (more only when the
project earns them):

1. **PROJECT.md** — what this is, for whom, what done means for v1. Include
   the explicit non-goals; scope creep starts where non-goals are unstated.
2. **ROADMAP.md** — numbered phases toward the current milestone. Each phase
   has: goal (one sentence), requirements it covers, and a checkable success
   criterion. Phases are outcomes, not task lists.
3. **STATE.md** — frontmatter (milestone, status, progress counts,
   last_updated) + a "Current Position" section. This is the file every
   session reads first; keep it current or the framework is dead weight.

## Procedure

1. Interview the operator only for what the repo cannot answer: intent,
   audience, constraints, priorities. Inspect the codebase for the rest.
2. Draft PROJECT.md; confirm the non-goals explicitly with the operator.
3. Derive phases backward from the milestone's definition of done — every
   requirement maps to exactly one phase; no phase without a requirement.
4. Write STATE.md pointing at phase 1 as `next`.
5. Commit as `docs(planning): bootstrap GSD/L2 contract`.

## ATLAS-native

- Register the repo as an ATLAS project (`atlas project` / Projects page) so
  missions and runs bind to it and the audit trail is scoped.
- Long-horizon milestones can run as judged missions later (`/goal`), but the
  contract files stay the source of truth for what "met" means.
