# Research protocol

On-demand: read this before a research pass so the pass produces records, not
impressions.

## What a research pass must produce

Six answers, each backed by a `signals` record with a confidence class and a
source URL where one exists:

1. **Current offer** — what they already sell, at what price, on what platform.
   Check: their site, their link-in-bio, their store, pinned posts, any course
   marketplace listing. This is the answer that most often kills the thesis.
2. **Audience shape** — who buys, roughly how many, what they ask for. Public
   comments and repeated questions are the best evidence here.
3. **The gap** — a specific thing the audience keeps asking for that the
   current offer does not deliver. Quote the asks; do not paraphrase them into
   a market claim.
4. **Why now** — a recent change: a launch, a complaint pattern, a platform
   shift, a hire, a price change.
5. **Reachability** — who decides, and on what legitimate channel. A public
   business email, a professional inbox they answer, or a warm intro. If the
   only path is cold DM automation, the answer is "unreachable".
6. **Smallest test** — the cheapest thing that would prove or kill the thesis.
   Usually a landing page or a single post, never a build.

## Sequence

1. `atlas_module op=query collection=prospects` — is this prospect already
   known? Never start a second record for the same person.
2. Read their own surfaces first (site, store, bio). Primary sources beat
   commentary.
3. Write each fact as a `signals` record as you find it, not at the end. A run
   that dies mid-research must leave its findings behind.
4. Search for the gap already being filled — explicitly try to invalidate the
   thesis before investing in it.
5. Score the prospect (see `qualification`), set `tier` and `stage`, and write
   `next_action` + `next_action_at`.
6. Report: what is verified, what is reported, what is still unknown, and the
   single next step.

## Unknowns are results

An honest `unknown` is more valuable than a confident guess: it tells the next
run where to look. Record unknowns in the prospect's `open_questions` field
rather than filling gaps with plausible-sounding inference.
