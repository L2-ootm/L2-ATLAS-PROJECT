# Qualification, scoring and the gates

Injected when the run is about qualifying, scoring or gating a prospect.

## Tiers

- **S** — warm or one degree away, verified budget behavior (they already sell
  something), audience matches an L2 thesis, and the gap is specific.
- **A** — cold but strong: verified offer, plausible specific gap, reachable
  decision-maker, no equivalent product already shipped.
- **B** — interesting, unproven. Stays in research; never in the send queue.

Tier is a judgement about *evidence*, not about how exciting the prospect is.
Excitement without a verified offer is tier B.

## Score (0–100), five components of 20

| Component | 20 points when |
|---|---|
| `demand` | verified prior sales or repeated public requests for the thing |
| `gap` | the gap is specific, current, and demonstrably unfilled |
| `reach` | you can reach the decision-maker on a legitimate, non-cold-automated channel |
| `fit` | L2 can build it with existing platform primitives, not a bespoke one-off |
| `timing` | something changed recently that makes now the moment |

Score below 50 → nurture. 50–69 → keep researching, do not send. 70+ → gate.

## The gates (a prospect passes them in order)

- **Gate 0 — partner intent.** Both sides willing to spend time validating.
- **Gate 1 — demand evidence.** At least one of: verified prior sales,
  repeated captured audience requests, waitlist conversion, paid reservation.
- **Gate 2 — offer test.** A landing page with a real price, scope and date;
  measure view → click → signup → payment.
- **Gate 3 — distribution test.** The partner actually executes the promised
  distribution. This tests the partnership, not the product.
- **Gate 4 — build authorization.** Only after demand *and* distribution
  signal. Bounded MVP, explicit stop date, acceptance criteria.
- **Gate 5 — recurring authorization.** Only after repeat-use evidence.
  Subscription is not automatically the next step.

Record every gate decision as a `gates` record: which gate, `pass|hold|fail`,
the evidence that decided it, and the rationale in one sentence. A gate that
passes on `hypothesis`-class evidence is a `hold`, not a `pass`.

## Kill criteria — stop work on a prospect when

- the gap is already filled by something they sell (record the invalidation);
- the decision-maker is unreachable on a legitimate channel;
- two gates in a row resolve to `hold` with no new evidence available;
- the work would require a bespoke build with no platform reuse.

Killing a prospect early is a win. The pipeline's cost is attention, and the
worst outcome is a queue of prospects nobody can honestly advance.
