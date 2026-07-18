# GSD/L2 · plan — a plan the goal can't slip through

Use after context is locked. A plan is good when a cold session could execute
it without asking questions and the phase goal could not fail silently.

## Produce

`.planning/phases/<NN-slug>/PLAN.md`:

- **Goal** — one sentence, copied from ROADMAP.md, not paraphrased looser.
- **Tasks** — each with: files it touches, the change, and a **done-condition
  that can be checked** (a command, a test name, an observable behavior).
  "Implement X" without a check is not a task.
- **Verification block** — the exact suites/builds/commands that must pass,
  plus any UAT only the operator can perform (named now, not discovered
  later).
- **Out of scope** — what this plan deliberately does not do.

## Procedure

1. Read CONTEXT.md and the target files. Map each ROADMAP requirement of this
   phase onto at least one task (coverage check — orphan requirements mean
   the plan is incomplete).
2. Order tasks by dependency; mark independent groups that could run as
   parallel actors.
3. **Goal-backward pass:** for the phase goal, ask "how could this plan
   complete every task and still miss the goal?" Add the missing task or
   tighten a done-condition until the answer is "it couldn't".
4. Keep it small. A plan over ~8 tasks is usually two slices — split it.
5. Commit as `docs(planning): plan phase <NN>`.

## ATLAS-native

- Parallelizable task groups become durable actors at execute time — note
  them as `[actor-ok]` so `execute.md` can spawn without re-deriving safety.
- Done-conditions that need a live surface name the surface (WebUI page,
  terminal command, gateway endpoint) so verification is mechanical.
