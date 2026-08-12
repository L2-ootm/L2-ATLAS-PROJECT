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

## Honest measurement: roughly 20% of the target

What exists today (verified, in this repo):

| Capability | State |
|---|---|
| Scaffold a new module from the agent | **Works** — `atlas module create` writes a valid v2 manifest + doctrine file, syncs and activates it. Same path for operator and agent. |
| Declare data, doctrine, plays, integrations without code | **Works** — capability v2: `collections`, `context`, `workflows`, `mcp`, pages. |
| Read/write its own module data mid-run | **Works** — `atlas_module` (query/create/update/delete/stats). |
| Durable working memory across compaction | **Works** — `atlas_scratchpad` with TTL policies and a sweep. |
| Wire an external integration | **Partial** — `mcp_service` registers and projects servers; the agent cannot yet enable one itself (operator-gated on purpose). |
| Write actual executable code for itself | **Does not exist** — it can write files with its harness tools, but nothing registers them as ATLAS capabilities. Every real tool is Python in this repo, added by a human-run session. |
| Judge durable vs disposable | **Does not exist** — no such decision is modeled anywhere. |
| Disposable artifacts with managed lifetime | **Substrate only** — `scratchpad_entries` has `kind='tool'`, a `path` column and TTL policies; nothing creates, registers or executes one. |
| Verify its own extension before adopting it | **Does not exist** — no generated-capability test gate. |
| Stop mid-task and re-plan deliberately | **Weak** — the run loop is a single forward pass with steering (`actor_bridge` inbox) and no self-initiated re-planning checkpoint. |
| Roll back a bad self-extension | **Partial** — `atlas module deactivate` and git for repo changes; nothing scoped to a generated capability. |

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
*Next.*

**L3 — Verified durable tools.** A disposable that proved its worth is promoted:
the agent writes a manifest + a test, ATLAS runs the test, the operator
approves, and the tool becomes a registered ATLAS capability with provenance and
a rollback handle.

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

## WP-A — The build/dispose decision (the judgment layer)

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
starting state. This decision gets recorded as a scratchpad entry
(`kind='finding'`) so the next run can see the reasoning instead of re-deriving
it — and so a pattern of the same disposable being rebuilt becomes visible
evidence for promotion.

## WP-B — Disposable tools (L2)

**Storage.** Already in place: `scratchpad_entries` with `kind='tool'`, `path`,
`ttl_policy`, `expires_at`, `pinned` (migration 0034).

**Creation.** `atlas_scratchpad op=write kind=tool` plus a new
`op=materialize`: writes the body to `<ATLAS home>/scratch/tools/<id>.<ext>`,
records the path, and returns the invocation line. The file lives outside the
repo — a disposable tool must never dirty the working tree.

**Execution.** Through the existing terminal tool and permission broker. No new
execution path, no in-process import, no privilege the agent did not already
have. This is deliberate: a disposable tool is a *saved command*, not a plugin.

**Lifetime.** The TTL policies already implemented: `run`, `session`,
`next_startup`, `hours`, `permanent`. Sweep deletes the row **and** the file.
Default for a generated tool: `next_startup`.

**Management.** Operator: `atlas scratch list --kind tool`, `scratch get`,
`scratch pin`, `scratch rm`, `scratch sweep [--startup]` — all shipped. Missing:
a cockpit surface (a Disposables panel with kind/TTL/owner/size and a purge
button) and a per-run cap so a looping agent cannot generate a hundred scripts.

**Promotion.** `atlas scratch pin` is the manual version today. The real
promotion path is WP-C.

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

1. **Read-back on resume.** A run that resumes a session should be handed its
   own open scratchpad entries automatically (a retriever in `memory_router`),
   not have to remember to ask. This is the single highest-value item here: it
   turns the scratchpad from a place to write into a place that writes back.
2. **File-backed bodies.** Large drafts belong on disk with the row holding the
   path (`path` column exists). Keeps the DB small and makes artifacts openable.
3. **Per-actor scratchpads.** Durable actors (`actor_service`) each get a scope,
   so a subagent's working notes do not collide with the parent's.
4. **Handoff entries.** A `kind='handoff'` written at run end and read at the
   next run start — the in-product version of the HANDOFF.md discipline.

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
| Self-verification before claiming done | GSD/L2 doctrine | A verification step the loop enforces, not one the model remembers — the evidence tiers already exist in the contract |

The theme: ATLAS already has most of the *mechanisms* (audit events, actors,
steering, scratchpad, missions). What is missing is the **loop discipline** that
invokes them at the right moments without being asked.

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

1. **WP-D-1 (scratchpad read-back)** — highest value per unit of work; makes the
   already-shipped scratchpad actually change behavior.
2. **WP-A (the decision) + WP-B (disposables)** — together, because disposables
   without the judgment layer are the landfill failure mode.
3. **WP-E (loop discipline)** — plan artifact, re-plan checkpoint, enforced
   verification step.
4. **WP-C (promotion pipeline)** — only after there are disposables worth
   promoting and a test gate to promote them through.
5. **L4/L5** — not before the above have run in anger for a while. A system that
   proposes changes to itself is only as good as its verification, and the
   verification is what we are building in 1–4.

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
