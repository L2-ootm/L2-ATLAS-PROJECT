# ATLAS Self-Extension Roadmap

Date: 2026-08-12
Status: direction document — the operator's stated target, with an honest
measurement of where the product actually is
Related: `2026-08-12-module-capabilities-v2-and-outreach-design.md`,
`2026-07-16-module-framework-design.md`, `2026-08-12-atlas-memory-v2-design-and-execution-plan.md`

## The target, stated plainly

> When ATLAS is asked to do something and the lack of a capability stops it, it
> should be able to build that capability — a tool, a module, a feature —
> implement it cleanly, and continue. It should weigh whether the thing is worth
> keeping, and when it is not, build it as a disposable that manages its own
> deletion. It should think mid-session, keep its own scratchpad, and stop to
> re-plan the way a good agent does.

Today ATLAS is **not close to that**. This document says how far it actually is,
what the levels between here and there are, and what each one costs.

> **Update 2026-08-12 (later the same day):** WP-D-1 and WP-B shipped, moving
> the honest number from ~20% to ~30%. What changed: the scratchpad now writes
> back on resume, and a run can materialize a disposable script with a managed
> lifetime and an operator-visible surface. What did **not** change: nothing
> mechanically enforces the build/dispose judgment (WP-A is still doctrine), and
> there is no promotion pipeline (WP-C). See the per-row states below.

> **Update 2026-08-13 — the doctrine was not reaching a run.** Before writing
> more machinery, this session went looking for what "use it in anger" would
> break against. It found the answer upstream of the mechanism: the L2 doctrine
> was unreachable.
>
> 1. **The L1 core prompt was stale.** Its `## Self-extension` section named
>    three skills and not `self-extension.md`, and told the model that module
>    capabilities were "limited to slash commands and schema-driven pages" —
>    capability *v1* language, false since v2. A run was actively instructed
>    that it could not do things it can, and never told that the disposable path
>    exists at all.
> 2. **The brief's "Relevant Skills" section advertised skills that are not
>    installed.** `SkillRetriever` parsed `docs/imports/SKILL_INVENTORY.md`, an
>    imported *planning* document. Of its 74 parsed rows, several are proposed
>    packs ("Analyst Pack (proposed, post-v1.0)") and taxonomy headings, none is
>    an ATLAS skill, and none is invocable by the ATLAS agent. Meanwhile the 90
>    real skills on disk — including all four `skills/atlas/` doctrine files —
>    reached no run at all. That is precisely what `atlas_core.md` forbids:
>    asserting a capability without confirming it exists here.
>
> Both are closed, and WP-A is no longer doctrine-only: `op=materialize`
> requires a `rationale`, stores it on the entry (migration 0035), emits a
> durable `self_extension` audit event, and shows it in the Disposables panel.
> The judgment is still the model's; the *record* of it is now the product's.
> Honest number: ~35%. The measurement did not move much, because delivering
> doctrine correctly is a precondition for L2 rather than a level beyond it —
> what changed is that the ~30% claimed on 2026-08-12 was partly untrue.

## Honest measurement: roughly 20% of the target

What exists today (verified, in this repo):

| Capability | State |
|---|---|
| Scaffold a new module from the agent | **Works** — `atlas module create` writes a valid v2 manifest + doctrine file, syncs and activates it. Same path for operator and agent. |
| Declare data, doctrine, plays, integrations without code | **Works** — capability v2: `collections`, `context`, `workflows`, `mcp`, pages. |
| Read/write its own module data mid-run | **Works** — `atlas_module` (query/create/update/delete/stats). |
| Durable working memory across compaction | **Works** — `atlas_scratchpad` with TTL policies and a sweep. |
| Wire an external integration | **Partial** — `mcp_service` registers and projects servers; the agent cannot yet enable one itself (operator-gated on purpose). |
| Write actual executable code for itself | **Partial (2026-08-12)** — `atlas_scratchpad op=materialize` writes a bounded script to `<ATLAS home>/scratch/tools` and returns its invocation; it runs out of process through the existing terminal tool. Nothing registers it as a first-class ATLAS tool — that is L3. |
| Judge durable vs disposable | **Doctrine, now recorded (2026-08-13)** — the four questions live in `skills/atlas/self-extension.md`, in the `atlas_scratchpad` description, and in the L1 core prompt, and all three are now reachable by a run. `op=materialize` refuses without a `rationale`, which is stored on the entry, emitted as a `self_extension` audit event, and shown in the cockpit. Nothing grades the answer — that is not enforceable — but an unexplained disposable can no longer be minted. |
| Find the doctrine that applies to the work | **Works (2026-08-13)** — the brief's "Relevant Skills" section is sourced from the 90 skills actually on disk (`skills/atlas/` doctrine + packaged `SKILL.md` skills), IDF-weighted so a stopword match cannot outrank a real one, and each entry carries its path. It previously listed proposed packs from an imported planning document. |
| Disposable artifacts with managed lifetime | **Works (2026-08-12)** — materialize + TTL + sweep deletes row *and* file, 5 tools per run, writes confined to the scratch root, operator-visible in the cockpit Disposables panel. |
| Recover its own working memory after a reset | **Works (2026-08-12)** — `ScratchpadRetriever` hands a resuming run its open plans/findings/tools, session-keyed, self-budgeted, redacted. |
| Verify its own extension before adopting it | **Does not exist** — no generated-capability test gate. |
| Stop mid-task and re-plan deliberately | **Weak** — the run loop is a single forward pass with steering (`actor_bridge` inbox) and no self-initiated re-planning checkpoint. |
| Roll back a bad self-extension | **Partial** — `atlas module deactivate` and git for repo changes; a disposable is retired by deleting it (cockpit, CLI, or its own TTL). |

Roughly: the *declarative* half of self-extension is real; the *executable*
half, the *judgment* layer, and the *self-verification* layer are absent. 20% is
a fair number, and the missing 80% is the hard part.

## Why the missing part is hard (and must not be rushed)

1. **Executing generated code inside the operator's runtime is the whole
   security model, inverted.** Everything ATLAS ships today rests on "a module
   is data; ATLAS is the only thing that runs." A generated tool breaks that
   sentence. The answer is not to abandon the constraint but to move it: a
   generated tool runs *out of process*, under a declared contract, with an
   approval gate and an audit trail — the sidecar/MCP shape, not an import.
2. **A self-extending agent with no taste produces a landfill.** The failure
   mode is not a security breach, it is fifty half-working single-use tools with
   overlapping names, none tested, all loaded. Disposability with enforced
   expiry is the antidote, and it has to be the *default*, with durability the
   exception that must be argued for.
3. **Self-verification is the gate that makes the rest safe.** A capability
   ATLAS built for itself and never tested is a claim, not a capability. The
   evidence discipline that already governs ATLAS's answers must govern its
   self-extension: registered → configured → reachable → verified-live.

## Capability levels

**L0 — Manual.** A human writes the code. *(Where every real ATLAS tool is today.)*

**L1 — Declarative self-extension.** The agent composes new behavior out of
capabilities ATLAS already executes: modules, collections, doctrine, workflows,
commands, pages. No new code. **Shipped 2026-08-12.**

**L2 — Disposable executables.** The agent writes a bounded script, registers it
as a disposable tool with a TTL and an owner, runs it out of process under the
existing permission broker, and lets it expire. Nothing enters the repo.
**Shipped 2026-08-12** (`op=materialize`, per-run cap, file-aware sweep,
cockpit Disposables panel). Unproven in anger: no run has yet hit a real missing
capability and built its way through it.

**L3 — Verified durable tools.** A disposable that proved its worth is promoted:
the agent writes a manifest + a test, ATLAS runs the test, the operator
approves, and the tool becomes a registered ATLAS capability with provenance and
a rollback handle. Its precondition — ATLAS being able to tell a verified run
from a run that claims to be one — shipped 2026-08-13 as the verification gate
(WP-E-1); the promotion pipeline itself is still WP-C.

**L4 — Feature-level self-extension.** The agent proposes a change to ATLAS
itself (a service, a route, a page), implements it on a branch, runs the real
suites, and opens it for review. The judgment moves up: is this a product
feature, or a one-off that should have been L2?

**L5 — Continuous self-improvement.** ATLAS notices repeated friction across
runs (the same failure, the same missing step), proposes the capability that
would remove it, and carries it through L2→L3→L4 with the operator approving
transitions, not implementations.

Everything below is the work between L1 and L3, in dependency order.

---

## WP-A — The build/dispose decision (the judgment layer) — RECORDED 2026-08-13

Before anything is generated, ATLAS must answer, in the run transcript:

1. **Is the capability actually missing?** Search first: `atlas_module op=list`,
   the tool catalog, the MCP registry, the skills inventory. Most "missing"
   capabilities already exist under a different name. A generated duplicate is a
   worse outcome than the original friction.
2. **Will this be needed again?** Evidence, not intuition: has this need
   appeared in prior runs (failure patterns, run summaries, the brain graph)?
   Once → disposable. Repeatedly → candidate for durable.
3. **Is it bounded?** A capability that needs credentials, network write access
   or more than ~200 lines is not a self-extension, it is a feature request.
   Say so and stop.
4. **What is the cheapest thing that removes the block?** Usually a shell
   one-liner, a query, or a workflow entry — not a tool.

The default answer is **disposable**. Durability is a promotion, never a
starting state.

**What ships (2026-08-13).** The decision is a required field, not a hoped-for
habit. `op=materialize` (and `atlas scratch materialize --why`) refuses a tool
whose reasoning was not stated, and the reasoning lands in three places with
three different lifetimes:

| Where | Lifetime | Who reads it |
|---|---|---|
| `scratchpad_entries.rationale` (0035) | dies with the disposable's TTL | the run, on read-back |
| `self_extension` audit event | permanent | a later run, and WP-C's promotion evidence |
| Disposables panel, under the title | live | the operator deciding pin-or-expire |

The audit event is the load-bearing one. A scratchpad row is *supposed* to
disappear; without a record that outlives it, "this same disposable has been
rebuilt three times" is unknowable, and the promotion criterion in WP-C has no
evidence to read.

What this does **not** do: judge the answer. A 40-character floor stops an empty
gesture and nothing more. A model that writes a plausible sentence and skips the
search still gets its tool. Mechanising the *quality* of the judgment would mean
verifying a negative ("nothing existing covers this"), which is the search
problem again — see WP-C, where a test gate does the verifying instead.

## WP-B — Disposable tools (L2) — SHIPPED 2026-08-12

**Storage.** `scratchpad_entries` with `kind='tool'`, `path`, `ttl_policy`,
`expires_at`, `pinned` (migration 0034) — no new schema was needed.

**Creation.** `atlas_scratchpad op=materialize` (and `atlas scratch
materialize` for the operator) writes the body to
`<ATLAS home>/scratch/tools/<id>.<ext>`, records the path, and returns the
invocation line. The file lives outside the repo — a disposable tool must never
dirty the working tree.

**Execution.** Through the existing terminal tool and permission broker. No new
execution path, no in-process import, no privilege the agent did not already
have. This is deliberate: a disposable tool is a *saved command*, not a plugin.

**Lifetime.** The TTL policies: `run`, `session`, `next_startup`, `hours`,
`permanent`. Sweep deletes the row **and** the file — but only when the file
resolves inside the scratch root, because `path` is agent-supplied and an entry
pointing at a repo file is a reference, not an artifact ATLAS owns. Default for
a generated tool: `next_startup`.

**Bounds.** 5 tools per run (updating an existing one is not minting a new one),
64 KB per body — past that it is a feature request, not a self-extension.

**Management.** Operator: `atlas scratch list --kind tool`, `scratch get`,
`scratch pin`, `scratch rm`, `scratch sweep [--startup]`, plus the cockpit
Disposables panel (Control → TOOLS & POLICY) with pin, delete and sweep over
`GET/DELETE/POST /v1/scratchpad*`.

**Promotion.** `atlas scratch pin` (CLI or the panel's pin button) is the manual
version today. The real promotion path is WP-C.

## WP-C — Verified durable tools (L3)

A disposable graduates when it has been used in ≥N runs (evidence from the
scratchpad's own history) or the operator pins it and asks. Promotion is a
pipeline, and every stage is a gate:

1. **Manifest.** The agent writes a tool manifest in the existing
   `tools/manifests/` shape (name, schema, risk class, permissions, side
   effects) — the same contract the built-in tools declare.
2. **Test.** The agent writes at least one real test that fails without the
   tool. No test, no promotion.
3. **Run the suite.** ATLAS runs the project's actual test command. A promotion
   that breaks an existing test is rejected automatically, not argued about.
4. **Operator approval.** A diff and a one-paragraph justification: what it
   does, why it is durable rather than disposable, what it can touch.
5. **Register with provenance.** `created_by_run`, the promoting run's id, the
   originating disposable's id, and a rollback handle (`atlas tool retire <name>`
   restores the prior state).

The honest constraint: until a generated tool can be executed out-of-process
under a declared contract, L3 tools should be **module workflows and MCP
servers**, not Python in `atlas_runtime/`. That is not a limitation to
engineer around; it is the security boundary doing its job.

## WP-D — Agent scratchpad, beyond v1

Shipped: durable entries with TTL, kinds, pinning, sweep, and an `atlas_scratchpad`
tool the model is told to use for plans and findings.

Next, in order of value:

1. ~~**Read-back on resume.**~~ **Shipped 2026-08-12.** `ScratchpadRetriever`
   hands a resuming run its open entries at the top of the brief, keyed on the
   session (a resumed run has a new run id and the same session), ordered
   pinned → plan → finding → tool → draft → note → newest, budgeted at ~700
   tokens so continuity cannot crowd out recall, and redacted at the same
   boundary as every other snippet. The router's abstain guard now exempts
   self-keyed retrievers: a run with no Current Focus is exactly the run most
   likely to need its own plan back.
2. **File-backed bodies.** Large drafts belong on disk with the row holding the
   path. Half-done: `materialize_tool` does this for `kind='tool'`; `op=write`
   still stores every other kind inline (capped at 256 KB).
3. **Per-actor scratchpads.** Durable actors (`actor_service`) each get a scope,
   so a subagent's working notes do not collide with the parent's.
4. **Handoff entries.** A `kind='handoff'` written at run end and read at the
   next run start — the in-product version of the HANDOFF.md discipline. Now
   cheap: read-back already delivers it, so this is a write convention plus a
   kind.

## WP-E — Inline execution and mid-session re-thinking

The practices worth importing, and what each requires here:

| Practice | Source | What ATLAS needs |
|---|---|---|
| An explicit, visible task list the agent maintains and checks off | Claude Code | A `kind='plan'` scratchpad convention plus a cockpit render; the storage exists |
| Plan-before-execute with an approval boundary | Claude Code plan mode | A run mode that produces a plan artifact and stops for approval — `mission_service` has the state machine to hold it |
| Deliberate stop-and-re-plan when evidence contradicts the plan | Prime/Hermes agents | A checkpoint the model can invoke (`atlas_scratchpad op=write kind=plan` + a re-plan step in the loop), plus a budget trigger that forces one |
| Interrupt and steer a running agent | shipped | `actor_bridge` steering inbox — extend to the main run loop, not just actors |
| Compaction that preserves the plan | Claude Code | The scratchpad survives compaction by construction; needs the read-back from WP-D-1 |
| Subagents for bounded fan-out | shipped | `atlas_actor` / teams — needs the disposable-scratchpad scoping from WP-D-3 |
| Hooks at lifecycle points | Claude Code | ATLAS has audit events; a hook surface (pre-run, post-tool, pre-commit) would let the operator enforce policy without patching the runtime |
| Self-verification before claiming done | GSD/L2 doctrine | ~~A verification step the loop enforces, not one the model remembers~~ — **shipped 2026-08-13**, see below |

The theme: ATLAS already has most of the *mechanisms* (audit events, actors,
steering, scratchpad, missions). What is missing is the **loop discipline** that
invokes them at the right moments without being asked.

### WP-E-1 — The verification gate (shipped 2026-08-13)

The last line of this document said the remaining work was "judgment,
verification and loop discipline, not code generation", and that steps 2 and 4
were "instructions the model is asked to follow — nothing verifies that it did".
The verification gate is the first of those to become mechanism, and it applies
far beyond self-extension: it governs every run ATLAS executes.

`verification_gate.py` reconstructs what a run did from its own audit trail —
tool arguments from `tool_requested`/`tool_call`, outcomes from
`tool_completed`/`tool_failed`, joined on call id — and reduces it to one
verdict:

| verdict | the trail showed |
|---|---|
| `no_mutations` | nothing observable changed; nothing required verification |
| `verified` | state changed, then a test/build/lint/typecheck ran **after** it and passed |
| `contradicted` | state changed, checks ran, and every one failed — a success claim here is false |
| `unverified` | state changed and was never checked |

Three design decisions carry the weight.

**The trail, not the transcript.** The model cannot narrate its way to
`verified`; the classifier never reads the final response. This is the first
claim ATLAS makes about a run that does not originate with the agent.

**Ordering is load-bearing.** A signal only counts when it follows a mutation. A
suite run before the edit says nothing about the edit, and that distinction is
tested rather than assumed.

**Weak signals stay weak.** `git status` and re-reading a file you just wrote
are recorded and reported, but never promote a run to `verified`. `git status`
runs in a large share of sessions; if it counted, the gate would agree with
every claim it was built to question.

Placed in `run_executor.execute_run` — the chokepoint every runtime passes
through — and applied before `complete_run`, so the verdict rides the paths that
already exist: the run summary, the compounding-loop observation, and the brain
graph. An unverified change is inherited by the next run rather than forgotten
at the end of this one. Team and actor workers have their own execution paths
and are not yet covered.

**What it deliberately does not do:** change `RunOutcome.status`. A heuristic
classifier on its first day must not be able to fail runs that worked — that is
the same unverified self-modification the gate exists to catch. Promoting
`contradicted` to a failed run is a later change, and the evidence for it will
come from what this one observes. `ATLAS_VERIFICATION_GATE=0` disables it.

**First use in anger (same day).** The gate was run over all 205 runs in the
live history — the standing instruction in this document is that the next work
package should come from what breaks, not from the list. It broke something
upstream of itself. `_json_safe_preview` truncated the *encoded JSON* of tool
arguments over 2 KB, and a tool call's identifying argument (`path`, `command`)
is short and sits in front of the bulk that overflows. Every large write in the
history is recorded without naming the file it wrote, and 176 of 229 `terminal`
calls without their command. That is an audit-trail defect, not a gate defect:
the surface renderers and any later reasoning about what a run did were reading
the same broken rows. Fixed by shrinking fields instead of the envelope.

The distribution is worth recording precisely because it is unflattering to the
exercise: **200 of the 205 historical runs made no observable state change.**
This machine's history is dominated by read-only chat and demo runs, so it
validated the *reader* against real payload shapes and taught the classifier
nothing about runs that do real work. That evidence still has to come from live
runs, and the roadmap should not claim otherwise.

**Delivery.** The L1 core prompt now names the rule in the gate's own
vocabulary and `skills/atlas/loop-discipline.md` carries the detail, both under
delivery tests — the discipline adopted after the previous doctrine layer
reached no run at all. Writing those tests found that the retriever indexed only
the *first line* of a `**Use when:**` block (all four ATLAS doctrine files wrap
it, so `handoff.md` was searchable by everything except the word "handoff") and
read `description: |` as the literal string `"|"` (the ultra pack was indexed
under one meaningless token). Both fixed. The lesson repeats: the delivery test
is worth more than the doctrine file.

## WP-F — Safety rails (non-negotiable, gates every level above L1)

- **Never self-modifiable:** the permission broker, the hardline policy, the
  audit bus, the prompt compiler's L0/L1 layers, migrations, and this list.
  A self-extension that touches them is rejected mechanically, not by judgment.
- **Out-of-process by default.** Generated executables run as subprocesses under
  the existing permission model. No dynamic import into the runtime.
- **No new credentials.** A generated capability may reference existing
  `${VAR}` env names; it may never request, store or print a secret.
- **Every generated artifact is attributable.** Run id, session id, prompt that
  caused it, and a diff. An artifact with no provenance is deleted by the sweep,
  not adopted.
- **Bounded blast radius.** Per-run caps on generated artifacts; a disposable
  tool cannot write outside the scratch directory without an approval.
- **Rollback before adoption.** Nothing is promoted without a documented way to
  retire it.

## Sequencing

1. ~~**WP-D-1 (scratchpad read-back)**~~ — done 2026-08-12.
2. ~~**WP-B (disposables)**~~ — done 2026-08-12. ~~**WP-A doctrine only**~~ —
   the decision is now required and recorded (2026-08-13); see WP-A above.
3. ~~**WP-G (doctrine delivery)**~~ — done 2026-08-13, and it was not on this
   list. Looking for what "in anger" would break against turned up something
   upstream of the run: the L1 prompt described capability v1 and never named
   `self-extension.md`, and the brief's skills section came from an imported
   planning document rather than the skills on disk. **The lesson worth keeping:
   a doctrine layer needs a delivery test, not just a file.** Two now exist —
   `test_skill_retriever_sees_the_real_atlas_doctrine` asserts the real
   `skills/atlas/self-extension.md` is reachable through the real retriever, and
   the prompt goldens pin the L1 text.
4. **Use it in anger.** Still owed, and now worth more: a run that hits a real
   missing capability will be told the truth about what it can do, will find the
   doctrine that applies, and cannot mint a disposable without saying why. The
   next work package should come from what breaks, not from this list.
5. **WP-E (loop discipline)** — ~~enforced verification step~~ done 2026-08-13
   (WP-E-1 above): the loop now judges the claim without being asked. Still
   open: the **plan artifact** (a run mode that produces a plan and stops for
   approval) and the **re-plan checkpoint** (a budget trigger that forces a
   re-think mid-run). `kind='plan'` read-back remains the substrate for both.
   The obvious next increment on the gate itself is the enforced turn: when a
   run ends `unverified`, spend one more turn demanding the check rather than
   only recording its absence. That needs `native.execute`'s single opaque
   `run_conversation` call refactored into a reusable `_run_turn`, which is also
   what the re-plan checkpoint needs — one refactor, two features.
6. **WP-C (promotion pipeline)** — only after there are disposables worth
   promoting and a test gate to promote them through. The evidence for
   promotion is now collectable and durable: a disposable rebuilt three times
   leaves three `self_extension` audit events behind, each with the reasoning
   that justified it, and they survive the sweep that removes the tools.
7. **L4/L5** — not before the above have run in anger for a while. A system that
   proposes changes to itself is only as good as its verification, and the
   verification is what we are building in 4–6.

## What "done" looks like for the next slice

An operator asks for something ATLAS cannot do. ATLAS:

1. searches for the capability and reports honestly that it is missing;
2. states whether this is one-off or recurring, with evidence from prior runs;
3. writes a disposable tool, registers it with a `next_startup` TTL, runs it out
   of process, and completes the original task;
4. records what it built and why, so the third time this happens the evidence
   for promotion is already there;
5. and the tool is gone the next morning unless someone pinned it.

That is L2. It is a realistic next milestone, and it is roughly 40% of the
target — which is the honest way to say that the remaining 60% is judgment,
verification and loop discipline, not code generation.

**Where that stands after 2026-08-12:** steps 1, 3 and 5 are mechanism the
product now has; steps 2 and 4 are instructions the model is asked to follow.
Nothing verifies that it did. Calling this "L2 complete" would be the exact
overclaim the roadmap exists to prevent — the machinery is in place and it has
never been exercised by a run that actually needed it.

**Where that stands after 2026-08-13:** step 4 moved from instruction to
mechanism — a disposable cannot exist without a recorded reason, and the record
outlives the disposable. Step 1's *first half* also moved: the run is now told
what it can actually do (capability v2, not v1) and is handed the doctrine file
that governs the decision, which it previously had no way to find. Step 2 is
still an instruction, and the search in step 1 is still unverified — a run that
skips it and writes a fluent rationale is indistinguishable from one that did
the work. And the whole sequence remains **unexercised**: no run has needed a
capability it did not have and built its way through. That sentence has now
survived two sessions, which is itself the finding.

**Where that stands after WP-E-1 (2026-08-13):** the honest number moves from
~20% to ~25%, and the movement is not in code generation. What changed is that
ATLAS can now tell a working run from a run that says it worked — including its
own self-extension runs, which produce exactly the mutation-without-a-check
signature the gate is built to catch (`materialize` writes an executable and is
classified as a state change for this reason). Step 2 of the L2 sequence — "state
whether this is one-off or recurring, with evidence" — is still an instruction.
Step 1's search is still unverified. But the *outer* claim, "and completes the
original task", is no longer taken on the model's word, and that was the claim
everything else rested on.
