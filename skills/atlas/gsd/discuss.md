# GSD/L2 · discuss — lock context before planning

Use before planning any phase whose gray areas could change the plan. Skip
only when the phase is mechanical and the plan writes itself.

## Produce

`.planning/phases/<NN-slug>/CONTEXT.md` capturing:

- **Decisions made** — each gray area with the chosen answer and why.
- **Assumptions verified** — checked against the actual codebase, with file
  paths as evidence (assumptions from memory are listed as unverified).
- **Deferred** — questions that don't block this phase, written down so they
  are not silently lost.

## Procedure

1. Read STATE.md, ROADMAP.md, and the phase goal. Read the code the phase
   will touch — the codebase outranks any description of it.
2. List the gray areas: anything where two reasonable implementations would
   diverge (data shape, UX behavior, failure handling, naming, scope edges).
3. Resolve each: from the repo when it has the answer; from the operator when
   it is genuinely their call. Ask focused questions with concrete options,
   never open-ended "any thoughts?".
4. Write CONTEXT.md. Decisions recorded here are LOCKED for the phase —
   changing one later is a deviation `execute.md` must surface, not absorb.

## ATLAS-native

- Use the knowledge graph (`atlas_graph` search/neighbors) to find the real
  call sites and contracts before assuming them.
- When a decision depends on live behavior, run it and cite the run/audit id
  instead of reasoning from the source alone.
