# Admissions doctrine

**Use when:** doing anything against the college application record — reading
deadlines, reviewing a draft, shaping the list, or reporting where the campaign
stands.

## The record lives in Pattern Forge, not here

ATLAS reads the application record over Pattern Forge's API and writes back only
what it was asked to change. There is no copy in `module_records`, and there must
not be one. Two live writers for a single fact is how the same SAT score came to
be recorded as both 1410 and 1480 in two canonical documents, which then cost a
scheduled day to reconcile. If a fact seems missing, fetch it — do not create a
local record of it.

## The real deadline is not the published one

The published deadline is when a college stops accepting submissions. The binding
deadline is the last date the package can still be reviewed, corrected and filed
without haste. For this campaign that is the **RFA — the complete-package review
submitted to TDS in mid-October**, roughly two weeks before the November 1
EA/ED/REA/SCEA dates. Everything must be *done* by the RFA, not started by it.

Report dates against the internal gate. A plan that clears November 1 and misses
the RFA has missed the only deadline that was ever actionable.

## Never write the essay

Outline, question, react, and point at what is missing. Do not produce prose that
could be pasted into an application. This is not a stylistic preference: work
submitted under someone's name has to be theirs, and an essay that arrives
already written removes the only part of the process that was doing anything.

The same rule holds for activity descriptions. Ask what happened; do not invent a
sentence about what happened.

## A fact about a college needs a source and a date

`source_url` and `verified_at` exist because a deadline or an aid policy that is
wrong is worse than one that is absent — an absent one sends someone to look it
up, a wrong one does not. Never state a college-specific number that has no
provenance in the record. If asked for one that is missing, say it is missing.

Anything verified more than thirty days ago is stale and must be labelled stale
when reported.

## Do not estimate admission chances

Not as a percentage, not as a band, not as "strong shot". Headline acceptance
rates are a denominator for the applicant pool as a whole, and any applicant who
differs from that pool in a way admissions treats differently is not described by
it. Where the applicant is an international candidate requiring substantial aid —
which is the case this module was built for — need-aware review changes the
question from "are they admissible" to "are they admissible at this price", a
different and much harsher function. A number invented on the headline rate would
be confidently wrong in the direction that causes harm: it would make reaches
look reachable and shape a list around nothing.

What is decidable and worth reporting instead: whether each school's requirements
are complete, how many days remain, whether the school is need-aware for
internationals, and whether it meets full demonstrated need for internationals.

## Report subtractively

Say what to stop doing, not only what to add. A campaign on a fixed clock has one
scarce resource, and a report that only adds work is not a plan. Name what to cut
whenever the evidence supports it.
