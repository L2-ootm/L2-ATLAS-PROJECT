# deepseek-harness and hermes-agent: what actually merges, and where ATLAS should aim

**Date:** 2026-08-13. **Method:** GitHub REST/search API against both repositories, plus release
notes and CONTRIBUTING. Every number below was measured, not recalled; the queries are in-line so
they can be re-run. Counts move — treat them as a snapshot of 13 August 2026.

---

## 0. The one-paragraph answer

**deepseek-harness cannot be contributed to.** It was published today, has issues disabled, and
its pull-request endpoint returns 404 — zero PRs exist and none can be opened. **hermes-agent
merges about one PR in four that it decides on, and almost none of them from outside the core
three accounts** — but it *does* land outside work, by cherry-picking the commits and closing the
PR unmerged with authorship preserved. For both repos the open contribution surface is the
**plugin ecosystem, not the core repository**, and both say so in writing.

## 1. deepseek-harness — a code drop, not a project you can join

```
gh api repos/deepseek-ai/deepseek-harness
```

| Fact | Value |
|---|---|
| Created | **2026-08-13T11:56Z** — today |
| Stars / forks | 37,939 / 2,952 |
| `has_issues` | **false** |
| `GET /pulls` | **404** |
| `search/issues?q=repo:…+is:pr` | **0** |
| Discussions | enabled |
| License / default branch | MIT / `master` |
| Topics | `cordis`, `dsh`, `dsh-plugin` |

It ships a `CONTRIBUTING.md`, a development guide and an `AGENTS.md`, and simultaneously offers
no channel through which a contribution could arrive. That is not a contradiction to resolve —
it is a repo published ahead of its process. **Do not spend a day preparing a PR for it.**

What the topics say is the actual invitation: `dsh-plugin`. The architecture is
"everything is a plugin", built on Cordis, so the thing you can ship today without anyone's
permission is a plugin package. That is also the only artifact that survives if the core repo
later opens PRs and rejects yours.

**Recommendation:** watch for `has_issues` flipping true and the pulls endpoint returning 200.
Until then, treat it as a library to build on, not a project to contribute to.

## 2. hermes-agent — the numbers

```
gh api "search/issues?q=repo:NousResearch/hermes-agent+is:pr+is:merged"   → 10,521
gh api "search/issues?q=repo:NousResearch/hermes-agent+is:pr+is:open"     → 21,127
gh api "search/issues?q=repo:NousResearch/hermes-agent+is:pr+is:closed+is:unmerged" → 32,178
```

63,826 PRs total. Of the **42,699 that have been decided, 24.6% merged.** Three of four are
closed unmerged. And 21,127 are still open — a queue larger than the entire merged history.

Repo scale for context: 230,071 stars, 45,506 forks, 31,766 open issues, created 2025-07-22.

### 2.1 Who gets merged

The last 100 merged PRs, by author:

| Author | Merged | Note |
|---|---|---|
| teknium1 | 59 | release lead |
| kshitijk4poor | 15 | top community contributor, named in release notes |
| OutThisLife | 12 | desktop lead |
| hermes-seaeye[bot] | 3 | automation |
| everyone else | 11 | 10 distinct accounts, 1 PR each |

**86 of the last 100 merges came from three accounts.** The long tail is ~11%.

By title prefix: 60 `fix(...)`, 25 `feat(...)`, the rest `chore`/`docs`/`fmt` and a handful of
sentence-style titles from the desktop work. **The repo merges bug fixes.**

### 2.2 The salvage pattern — the finding that matters most

25 of the last 100 merged PRs carry `(salvage #NNNNN)` in the title. Cross-referencing against
the recently closed-unmerged list, the pairs are exact:

| Community PR — closed unmerged | Maintainer PR — merged |
|---|---|
| #85287 `fix(plugins): discover entrypoint capability declarations` | #85552 same title `(salvage #85287)` |
| #57593 `fix(tui_gateway): restore openrouter provider on session resume` | #85558 `(salvage #57593)` |
| #54643 `fix(zai): rewrite /api/anthropic…` | #85577 `(salvage #54643)` |
| #79787 `Fix: Preserve anthropic_messages api_mode…` | #85576 `(salvage #79787)` |
| #84230, #71100, #62804, #75040, #85512, #80493, #83782 | #85572, #85562, #85544, #85549, #85554, #85527, #85532 |

**Your PR is closed. Your change ships.** From the closing comment on #85287:

> Merged via PR #85552 — both commits cherry-picked onto current main **with your authorship
> preserved in git history**. During salvage we composed your capability discovery with the
> entry-point kind classification that landed in #85527 … Thanks for the metadata-based,
> import-free approach — exactly the right shape for this.

Verified rather than taken on trust. The author of #85287, `jeeves-assistant`:

```
search/issues?q=…+is:pr+is:merged+author:jeeves-assistant  → 0
search/commits?q=…+author:jeeves-assistant                 → 4
```

**Zero merged PRs, four authored commits in `main`.** So the credit is real but it is *git*
credit, not GitHub credit. This matters for the stated goal of strengthening an application: a
GitHub profile will show no merged PR into hermes-agent, while `git log --author` in a
230k-star repository will show four commits. If the evidence is going in an application, link
the commit, not the PR — and screenshot the maintainer's closing comment, which names you and
describes why the approach was right.

### 2.3 Why PRs die: duplicates, overwhelmingly

Six separate community PRs fixed the same cron misclassification bug — #70977, #70913, #61969,
#60593, #83188, #78503 — and every one was closed. The fix landed as maintainer PR #85536.
Closing comments are explicit, and unusually honest about it:

> Closing with credit — **and a credit correction**. This bug … was fixed on main via PR #85536,
> which cherry-picked #77648. Reviewing after the merge, we found **your PR was the EARLIEST
> submission of this fix — Jul 8, more than three weeks ahead** of the PR that got first-submitter
> credit. Our pre-merge duplicate sweep missed it because of [phrasing].

There is a first-submitter credit system, and it is fallible. The lesson is not "be fast", it is
**"be findable"** — the sweep matched on phrasing, and the PR that lost credit lost it for using
"local script timeouts" instead of the words the sweep looked for.

### 2.4 There is a triage bot, and it labels before a human reads

PR bodies carry machine verdicts:

```html
<!-- hermes-sweeper:review-verdict=keep_open salvageability=high -->
```

The label vocabulary is public and tells you the whole rubric:

- **Blast radius:** `sweeper:blast-contained`, `-moderate`, `-broad`, `-massive`
- **Dismissals:** `sweeper:implemented-on-main`, `sweeper:cannot-reproduce`, `sweeper:incoherent`,
  `sweeper:not-planned`
- **Risk flags:** `sweeper:risk-automation`, `-caching`, `-compatibility`, `-message-delivery`,
  `-platform-windows`

Merge outcomes by blast radius (labelled PRs only):

| Label | Open | Merged |
|---|---|---|
| `blast-contained` | 4,274 | 18 |
| `blast-moderate` | 10,970 | 66 |
| `blast-broad` | 1,567 | 8 |
| `blast-massive` | 248 | **0** |
| `ci-reviewed` | **9** | **66** |

Two readings, and both are actionable. **`blast-massive` has never merged** — a large-surface PR
is dead on arrival regardless of quality. And `ci-reviewed` is the only label where merged
outnumbers open, by 7:1: **the gate is reaching CI review.** Everything before that is a queue.

### 2.5 What CONTRIBUTING says will be rejected

Stated outright, and worth quoting because each one is a whole class of wasted work:

- **New memory providers in core** — "We are no longer accepting new memory providers into this
  repo." Ship a standalone plugin.
- **Third-party product integrations in core** — "These do not land in this repo."
- **Unbounded dependency specs** — `>=X.Y.Z` with no upper bound is rejected; use
  `>=floor,<next_major`.
- **Skill descriptions over 60 characters** — "Reviewers reject PRs that violate them."
- **Competing PRs** — collaborate on the existing one rather than opening a duplicate.
- One logical change per PR. `scripts/run_tests.sh` must pass. Conventional Commits titles.
- Skills need tests at `tests/skills/test_<skill>_skill.py`, stdlib + pytest + `unittest.mock`
  only, no live network.

### 2.6 The strategy this evidence implies

Ranked by expected value, highest first:

1. **Ship a plugin, not a core PR.** Both repos say the same thing in different words —
   hermes-agent refuses integrations and memory providers in core, deepseek-harness is topic-tagged
   `dsh-plugin` and accepts no PRs at all. A published plugin needs nobody's approval, cannot be
   closed as a duplicate, and is a linkable artifact.
2. **If you do open a PR: one `fix(scope):`, contained blast radius, tests, and a duplicate search
   before you write a line.** `gh search prs --repo NousResearch/hermes-agent --state all "<terms>"`
   — searching *closed* PRs is the step that six cron contributors skipped.
3. **Search with the maintainers' vocabulary, not yours.** The dedupe sweep is a text match; the
   PR that lost three weeks of priority lost it on phrasing.
4. **Expect salvage, and plan the evidence for it.** The realistic best outcome for an outside
   contributor is a cherry-picked commit and a closing comment that names you. That is genuinely
   worth having — but capture it, because GitHub's PR badge will not show it.
5. **Do not chase the P0/P1 backlog.** v0.18.0 cleared ~692 P0/P1 items in twelve days and the
   team states they intend to hold both at zero. The high-priority queue is where the core team
   lives; the merge rate there for outsiders is worst.

## 3. Hermes changes worth bringing into ATLAS

**ATLAS vendors hermes-agent at `e8b9369a9`, 2026-05-28 — v0.15.0.** Upstream is v0.20.1, and
`compare/e8b9369a9...main` reports **12,412 commits ahead**. Five minor releases have shipped since
the pin: 0.16.0 "The Surface Release", 0.17.0, 0.18.0 "The Judgment Release", 0.19.0 "The
Quicksilver Release", 0.20.x.

A wholesale re-vendor at 12k commits is not a maintenance task, it is a migration. Read this list
as **ideas to port**, not commits to merge.

### 3.1 Completion contracts and the verification evidence ledger — v0.18.0

This is the one that matters, because ATLAS built its sibling independently. ATLAS's verification
gate classifies a run's success claim against its own audit trail, and an `unverified` run now
costs an enforced check turn. Hermes shipped, in the same window:

- **Completion contracts on `/goal`** (#50501) — the operator states what "done" looks like, and
  the standing-goal loop judges completion **against that evidence** rather than stopping when the
  model is satisfied.
- **A coding verification evidence ledger** (#52285, #52286) — a profile-scoped record of the
  canonical project checks detected from the coding context, with **the gateway exposing
  verification status** as a first-class field.
- **A `pre_verify` hook** (#55413) for wiring in project-specific checks.
- **`verify-on-stop` defaulting OFF**, with a one-time migration, skipping doc-only edits, and
  gated off for messaging surfaces (#53552, #54740, #55449).

Three of these are things ATLAS has not done and should consider:

1. **A stated contract, authored by the operator, that the gate judges against.** ATLAS's gate
   currently classifies against the audit trail — it infers what "done" should have meant. A
   declared contract turns a judgement into a comparison.
2. **A durable evidence ledger separate from the event stream.** ATLAS emits audit events; a
   ledger keyed to *which checks this project actually has* is a different object, and it is what
   lets a later run know what verification is even available.
3. **Surface-aware defaults.** Hermes learned that verify-on-stop is wrong for messaging surfaces
   and doc-only edits. ATLAS's gate applies uniformly; the same exemptions probably apply.

**Do not port the code.** Port the three shapes, and keep ATLAS's own verdict vocabulary.

### 3.2 The sweeper — an idea ATLAS can use directly

`hermes-sweeper` writes a machine verdict and a `salvageability` score into every PR, plus blast
radius and risk labels, before a human looks. ATLAS already has module workflows and an
executable validator pattern (`/api/application/validate` in the admissions module is exactly
this shape). A sweeper for ATLAS's own inbound work — issues, module proposals, autonomous-loop
output — is the same mechanism: **a cheap classifier that attaches a verdict and a blast radius,
so a human only reads what survived triage.**

The blast-radius taxonomy is worth stealing verbatim: contained / moderate / broad / massive, with
the empirical fact attached that massive never merges.

### 3.3 `/learn` and `/journey` — against ATLAS's memory v2 program

`/learn <anything>` distils a reusable skill from a directory, a URL, or the workflow just walked
through, and **writes it to the standards in the project's CONTRIBUTING.md automatically**.
`/journey` renders the accumulated memories and skills as an editable timeline.

ATLAS's memory v2 program is about the opposite direction — the WP-0 win was cutting a
17K-character skills catalogue out of the prompt. `/journey` is the missing half: ATLAS can
retrieve skills but has no operator-facing view of what it has accumulated and no way to prune a
wrong one in place. That is a small, high-value surface for the cockpit.

### 3.4 Background subagent fan-out — v0.18.0 (#49734)

`delegate_task` fans out multiple subagents in the background, unblocking the chat, and returns
**one consolidated turn** when all finish. ATLAS's delegation is synchronous-shaped. The
consolidation-into-one-turn detail is the part worth copying: N separate result turns is what
makes fan-out unpleasant to read.

## 4. ATLAS and Nodex — what they can actually share

These two look unrelated (an agent OS and a browser-native P2P cache) and share one thing that
matters: **both are built around refusing to state a claim they cannot evidence.**

`NODEX_RESEARCH_RIGOR_STANDARD.md` requires every claim to fall into one of four evidence classes:

> 1. Formal argument. 2. Reproducible experiment. 3. Measured artifact. 4. Explicitly marked
> hypothesis. — *If a claim does not fit one of those classes, it does not belong in the paper
> track yet.*

And its README does this in practice: "Do not start broad external beta yet", "Treat
`npm run verify:deployed-p2p` as pending/flaky", "Broad beta remains claim-gated. The current
evidence does not prove WAN/NAT, forced TURN, mobile browser, background-tab behavior…".

**Nodex → ATLAS.** ATLAS's verification gate has four verdicts of its own. Nodex's four evidence
*classes* are a better-grounded vocabulary for the same job, and they come with a rule ATLAS lacks:
an unevidenced claim is not a failure, it is a **marked hypothesis** — it stays, labelled, rather
than being either asserted or dropped. That maps directly onto the gate's `unverified` verdict and
would make it more useful than a scolding.

**ATLAS → Nodex.** Nodex's rigor standard is a document; ATLAS's verification gate is a running
classifier that reads an audit trail. Nodex's claim-gating is currently enforced by Davi
remembering to enforce it — which is exactly the failure mode the standard is written against. An
ATLAS admissions-style module for Nodex (`context/rigor.md` as `inject: always`, a
`claim_sweep` workflow, an executable `validate` command over the evidence artifacts) would make
the standard something a run cannot skip. The admissions module is the template: it owns no
records, reads them over an API, and its validator re-reads rather than trusting the caller.

**Both → the idempotency work.** Nodex's recent commits are `feat(consistency): deliver
invalidations from durable outbox`, `feat(consistency): route through universal sequence
authority`, `fix(consistency): fail closed on untrusted freshness`. That is the same vocabulary as
the Pattern Forge pass on 13-14 August (idempotency keys, partial unique indexes, a duplicate
reported as already-applied). Three projects converging on one discipline is a sign it should be
written down once — an L2 doctrine file — rather than rediscovered a fourth time.

## 5. What to do next, in order

1. **Nothing for deepseek-harness** beyond watching whether it opens PRs. If you want a presence
   there, write a `dsh-plugin` — that is the only channel that exists.
2. **For hermes-agent, ship a plugin.** ATLAS is exactly the kind of thing their core explicitly
   refuses to absorb and their plugin system exists to host. A `hermes_agent.plugin_capabilities`
   entry point exposing ATLAS modules would be a real artifact and needs nobody's approval.
3. **If a PR is wanted anyway:** pick a `sweeper:blast-contained` bug, search *closed* PRs in the
   maintainers' phrasing first, one `fix(scope):` commit, tests, `scripts/run_tests.sh` green.
   Expect salvage; capture the closing comment.
4. **Port the three verification shapes** from §3.1 into ATLAS's gate — declared contract, evidence
   ledger, surface-aware exemptions. Do not re-vendor 12,412 commits to get them.
5. **Write the idempotency doctrine once**, as an L2 file, now that three projects have converged
   on it independently.

## 6. What was acted on — 2026-08-13

Same day, in this repo. Items 1, 4 and 5 are closed; 2 and 3 are not, for stated reasons.

| # | Item | Outcome |
|---|---|---|
| 1 | deepseek-harness | **Nothing built**, as recommended. The watch condition (`has_issues` true, `/pulls` returning 200) is unchanged; nothing to re-check until it flips. |
| 2 | Ship a hermes-agent plugin | **Not done.** Publishing a package under ATLAS's name to an external index is an outward-facing release, not a code change — it needs an operator decision on naming, ownership and where it is hosted before a line is written. |
| 3 | Open a `fix(scope):` PR | **Not done**, and correctly skipped: §2.1 puts the outside long tail at ~11% and the queue at 21,127 open. Item 2 is the higher-EV channel and it is blocked on the same decision. |
| 4 | Port the three verification shapes | **Shipped.** See `docs/decisions/D-024-verification-contract-and-check-ledger.md`. Declared contract (`.atlas/verification.json`) + durable check ledger (`verification_checks`, migration 0036) + a documentation-only `exempt` verdict. Two of the three shapes landed as specified; the third was narrowed — see below. |
| 5 | Write the idempotency doctrine once | **Shipped** as `skills/atlas/idempotency.md`, with a delivery test in `test_memory_router.py`, because a doctrine file no run can retrieve is a document rather than doctrine. |

The narrowing on item 4: hermes's surface-aware exemption has two halves, and only one was
portable. Doc-only edits are derivable from the audit trail the gate already reads, so that half
shipped. Gating the enforced check turn off for **messaging** surfaces is not implementable here
today — ATLAS's surface kinds are `cli|tui|webui|api|native|test` and the Discord sidecar creates
no surface session, so the branch would never execute. Shipping a knob that nothing can trigger
would have looked like three-for-three and been two-and-a-half.
