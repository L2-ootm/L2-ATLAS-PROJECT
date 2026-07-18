# GSD/L2 · ship — close the loop, leave no trap

Use when a milestone's final phase verifies clean, or when a body of work
leaves the session permanently (merge, release, pause).

## Procedure

1. **Milestone audit** — walk ROADMAP.md requirement by requirement: each one
   points at the shipped behavior that satisfies it, with its evidence tier
   from VERIFICATION.md. Requirements that quietly changed during execution
   are re-stated honestly, not retro-fitted.
2. **Entropy pass** — delete scratch files, dead flags, superseded docs the
   milestone created; a shipped milestone that leaves droppings taxes every
   later session.
3. **Handoff** — follow `skills/atlas/handoff.md`. The four sections (what
   changed / what was verified / what is owed / next actions) are mandatory;
   counts must match `git status --short -uall`.
4. **Archive** — move completed phase directories under
   `.planning/archive/<milestone>/`, update STATE.md frontmatter (milestone
   complete, next milestone or "awaiting direction").
5. **File the knowledge** — durable lessons (root causes, decision
   rationales, patterns worth reusing) go to the LLM Wiki with provenance,
   not into a markdown graveyard.
6. **Release mechanics** (when shipping outward): version bump, changelog,
   tag, and only then the publish step — each gated on the previous one
   actually succeeding.

## Stop conditions

Ship refuses to close when: verification verdict is `gaps`, owed UAT is
safety-relevant, uncommitted work is sitting in the tree, or the handoff
would contain a claim without evidence. Route back instead — an honest open
milestone beats a false closed one.
