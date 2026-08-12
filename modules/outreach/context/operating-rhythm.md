# Operating rhythm

On-demand: the weekly and daily loop the pipeline runs on.

## Daily (the queue)

1. **Due today** — prospects whose `next_action_at` is today or past, ordered
   by tier then score. Report them as a queue with the exact next action, not
   as a status dump.
2. **Replies** — any `touches` with direction `inbound` and no follow-up
   recorded. These outrank everything else; a reply left cold is the most
   expensive item in the pipeline.
3. **Research debt** — prospects in `research` older than 7 days with no new
   signal. Either advance them or move them to nurture; a stale research
   record is a decision nobody made.
4. **Drafts waiting on a human** — anything drafted but not sent. Name them so
   the operator can send or kill.

## Weekly (the review)

Report, in this order, with numbers from the records:

- Sent, replied, reply rate, and reply rate by message variant.
- Gates cleared and gates held, with the reason each hold is held.
- Invalidated hypotheses — what was learned and what will not be re-pitched.
- Kills — who left the pipeline and why. A week with no kills is a warning.
- One thing to change next week, stated as an experiment (`experiments`
  record: hypothesis, variable, metric, decision rule).

## Cadence limits

- No more than 20 active prospects in `ready` or later at one time. Beyond
  that, follow-ups get dropped and the ledger becomes fiction.
- No more than 5 new sends a day. Outbound quality collapses at volume, and
  volume is not the constraint being tested.
- Every prospect in `ready`+ has exactly one owner and one next action with a
  date. A record with no next action is a record nobody owns.

## Metrics that matter

`reply_rate` (replies ÷ sends), `qualified_rate` (discovery ÷ replies),
`gate_1_rate` (demand evidence ÷ discovery), `cycle_days` (first touch →
gate 1). Track them per campaign, not globally — a global average hides which
thesis is working.
