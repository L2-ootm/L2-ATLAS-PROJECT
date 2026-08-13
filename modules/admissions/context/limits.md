# Hard limits, and where they bind

**Use when:** touching an activity, an honor, an essay, or anything with a count
attached.

## The limits are data, not memory — and they belong to a system, not to applying

Character and word limits live in `application-systems.ts` in Pattern Forge, one
profile per application system, each carrying a `source` and a `verifiedAt`.
**Read them from there.** Do not state a limit from memory: Additional
Information went from 650 words to 300 for the 2025-26 cycle, and the Activities
section was renamed for 2026-27. A limit recalled from training data is a limit
from an earlier cycle.

At time of writing the Common App profile says: position 50 characters,
organisation 100, description 150; ten activities, five honors — verified
2026-08-13. Verify before quoting.

**A profile may state no limits at all, and that is an answer.** Coalition's
section figures have not been checked by this project and UCAS has no activities
section; both carry `null` rather than a plausible number. When the record says
null, say "no verified limit for this system — check the portal". Do not fall
back to the Common App's numbers because they are the ones you know. An invented
limit is worse than none: it passes text the portal will truncate while looking
like it was checked.

**Units differ by system.** The Common App counts activity entries in characters
and essays in words; UCAS counts the personal statement in characters. Four
thousand characters read as four thousand words is wrong by a factor of six, in
the direction that loses the essay. The profile's `essayUnit` says which.

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

## The restrictive-plan rule, and where it does not apply

ED, ED2, REA and SCEA are mutually exclusive **across the whole list** — at most
one may be live. No portal enforces this: both applications go through and the
violation surfaces months later as a withdrawn offer. The validator reports it as
a blocker. Treat it as one.

**This is a US rule, not a rule about applying.** UCAS has no plan that binds an
applicant to one university, so the conflict cannot exist there and reporting one
asserts something false about the applicant's situation. The restrictive set is a
property of the profile (`restrictivePlans`), and it is empty for `uk_ucas` and
`other`. Read it; do not assume the four.

A stored plan value may also be relabelled by the system — a UCAS row stores `RD`
and displays "Equal consideration", because the database CHECK from migration
0005 only accepts the seven US strings. Quote what the applicant sees, which is
the profile's `planLabels`, not the raw column.
