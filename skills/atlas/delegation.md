# Skill: delegation

**Use when:** handing work to a subagent, an actor, a team member, or a
parallel batch of them — and, just as much, when reading what one of them sent
back. Also when a run depends on work another run did, when picking up a
handoff, and when several agents share a repository, a branch, or a database.

The premise: **an agent's report is a claim about its own work, and the reader
has none of the context that produced it.** Delegated work rarely fails because
a subagent did something badly. It fails because the next agent read "done" and
built on it. Nobody lied and nobody checked, and the mistake surfaces three
steps later, in code that looks correct.

## Handing work out

1. **A delegated prompt inherits nothing.** The subagent does not have the
   conversation, the decision you made two turns ago, or the reason a file is
   laid out the way it is. Give it the goal, the exact paths, the acceptance
   criteria, and the scope guard — what it must not touch. If you would have to
   explain something to a new colleague, it belongs in the prompt.
2. **State the acceptance criterion as something checkable.** "Make the tests
   pass" is checkable. "Improve the module" is a request for an opinion, and
   the report you get back will be one.
3. **Never write "based on your findings, decide X."** That hands the judgment
   to the party with the least context. Synthesize first, delegate a concrete
   instruction second.
4. **Parallel agents must not share a writable surface.** Two agents editing
   one file, one branch, or one row will produce a result neither of them
   described. Give each its own scope, or run them in sequence.

## Reading work back

5. **Treat every returned claim as unverified until you have checked the part
   you are about to depend on.** Not all of it — the specific thing. If the
   next step imports a function the subagent says it wrote, open the file. If
   it says the suite is green, run the suite. Checking the claim you are about
   to build on is cheap; discovering it was wrong after building on it is not.
6. **A missing verification is not a passing one.** ATLAS states a verification
   position on every delegated result precisely because silence gets read as
   confirmation. `unverified` and `no check ran against this` mean the same
   thing as far as your next step is concerned: nobody looked.
7. **An agent that died mid-task leaves plausible wreckage.** A half-applied
   edit compiles more often than it should. When a subagent errored, timed out,
   or was cancelled, assume the workspace is in a state nobody intended and
   inspect it before continuing.
8. **Disagreement between two agents is information, not noise.** If one
   reports a file has one shape and another assumes a different one, do not
   pick the more confident report. Read the file.

## Working alongside others

9. **State your assumption where the other side can see it.** If you are
   proceeding on the belief that another agent produced a particular interface,
   say so — in the handoff, the commit message, or the plan. An assumption
   written down gets corrected; one held silently gets built upon.
10. **The record is what happened; a summary is what someone said happened.**
    Prefer the audit trail, the diff, the test output, and the file over any
    prose account of them — including your own from earlier in the run.

**What to check before you rely on delegated work.** Which specific claim does
my next step depend on? Did anything actually check it, or am I reading a
report? If it turns out to be false, where does that surface — here, or three
steps downstream in something that looks fine? If the answer is "downstream",
check it now.
