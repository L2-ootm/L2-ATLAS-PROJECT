# Skill: memory

**Use when:** deciding whether something you learned should outlive this run,
writing to the knowledge graph, or reading evidence out of a context brief that
carries grades. Also when two sources disagree, and when you are about to state
something as established.

The premise: **an agent will operate on bad data as confidently as on good data,
unless the data says which it is.** The failure is not that a model believes a
wrong fact. It is that a wrong fact and a checked one arrive looking identical,
so nothing in the run can tell them apart. Quality has to travel *with* the
information or it does not exist.

## Reading evidence

1. **The grade on a piece of evidence is a fact about where it came from, not an
   opinion about how good it is.** `stated` means the operator said it.
   `verified` means a check passed. `observed` means a tool saw it at a stated
   time. `derived` means someone reasoned to it from sources. `reported` means
   another agent claims it. `asserted` means nothing backs it at all.
2. **`stated` settles what the operator wants; `verified` settles what is
   true.** These are different questions and the ladder does not merge them. If
   a verified fact contradicts a stated intent, that is not yours to resolve —
   surface it. Reality disagreeing with the plan is news, not an error to
   silently correct.
3. **An `observed` item is true as of its timestamp and no later.** The brief
   renders an age for a reason. A file read three weeks ago describes a file
   that has had three weeks to change; if your next step depends on it, read it
   again rather than citing the memory.
4. **Do not launder a grade by restating it.** Repeating a `reported` claim in
   your own summary does not make it observed. If everything you have is thin,
   say the answer is thin — an accurate "I could not confirm this" is worth more
   than a confident sentence built on `derived` material.

## Writing to the graph

5. **Write what will still be true, and useful, in a month.** Durable facts,
   operator preferences and conventions, architectural decisions and their
   reasons, failure modes that will recur. That is what the graph is for.
6. **Do not write what has a shelf life.** Task progress, phase numbers, commit
   SHAs, PR numbers, file counts, "X is now done". These are true for a week and
   misleading forever after, and the graph has no way to notice they went stale.
   Working state belongs in the scratchpad, which expires on purpose.
7. **Cite the evidence that backs the claim.** `atlas_graph op=add_node` takes
   `evidence` — the ids of tool calls from *this run* that support what you are
   recording. Citing real evidence records the node as `derived`. Citing nothing
   records it as `asserted`, which is stored but deliberately kept out of future
   runs' context: an unbacked claim that reaches a prompt is indistinguishable
   from a checked one once it is there.
8. **Never invent a citation.** Ids that do not resolve against this run's audit
   trail reject the write and are reported back to you. A citation that cannot
   be wrong would not be evidence.
9. **You cannot grade your own claim.** `confidence` ranks nodes within a grade;
   it does not set one. Nothing you write is `verified` on your own say-so —
   that comes from a check actually running.

## When claims collide

10. **A weaker claim never overwrites a stronger one, and is never thrown away
    either.** If your write is refused, the graph already holds a
    better-established answer about that entity; your version is kept as a
    recorded conflict. Read what is there before re-asserting — you may be
    right, in which case the thing to produce is the evidence, not a louder
    repetition.
11. **Agreement is not a conflict.** Re-recording something the graph already
    says is corroboration and is accepted. Only a materially different claim
    about the same entity contests it.

**What to check before you write.** Will this still be true next month? Does
anything in this run actually back it, and can I name that thing? Am I recording
what I learned, or what I did? If it is what I did, the run summary already has
it, and the graph does not want it.
