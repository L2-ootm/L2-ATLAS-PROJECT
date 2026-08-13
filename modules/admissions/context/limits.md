# Hard limits, and where they bind

**Use when:** touching an activity, an honor, an essay, or anything with a count
attached.

## The limits are data, not memory

Character and word limits live in `COMMON_APP_LIMITS` in Pattern Forge, with a
`source` and a `verifiedAt`. **Read them from there.** Do not state a limit from
memory: Additional Information went from 650 words to 300 for the 2025-26 cycle,
and the Activities section was renamed for 2026-27. A limit recalled from
training data is a limit from an earlier cycle.

At time of writing the record says: position 50 characters, organisation 100,
description 150; ten activities, five honors. Verify before quoting.

## Where the limit binds

The limit binds **at submission**, not at draft. An over-length draft is stored
deliberately — the sentence exists because that is what it needed before being
cut, and refusing the write would mean retyping from memory, which is worse than
being over.

So: never delete or truncate a draft to make it fit. Report the overage with the
exact number of characters to remove, and let the applicant choose what goes.

## Do not compute the count yourself

`GET /api/application/validate` re-reads the record and returns every overage.
Use it. A count computed in a run is a second definition of the same thing, and
the two will disagree the first time one of them handles trailing whitespace
differently. The validator trims trailing whitespace and counts interior spaces;
that is the definition.

## The restrictive-plan rule

ED, ED2, REA and SCEA are mutually exclusive **across the whole list** — at most
one may be live. No portal enforces this: both applications go through and the
violation surfaces months later as a withdrawn offer. The validator reports it as
a blocker. Treat it as one.
