# ATLAS Memory v2 — Design and Execution Plan

**Date:** 2026-08-12
**Status:** prepared for execution, not started
**Scope:** (A) close the Hermes instruction/path crossing at the prompt boundary,
(B) rework the memory system into an active/passive, agent-managed, operator-
toggleable plane.
**Constraints honored:** D-001 (never edit `foundation/atlas-hermes`), D-023 (one
ATLAS runtime, no second agent/eval framework), DIV-001 (prefer an ATLAS-only fix
over an in-core edit).

This document is written so the next session is execution, not rediscovery. Every
claim in Part A is cited to a file and line read on 2026-08-12. Part E lists what
was **not** verified and must be measured before the fixes are called done.

---

## Part A — Diagnosis (verified by code reading)

### A.1 The Hermes crossing

The vendored harness composes its system prompt in three tiers and joins them
`stable → context → volatile`
(`foundation/atlas-hermes/agent/system_prompt.py:314-337`).

ATLAS's entire compiled contract (L0–L4, `prompt_compiler.compile_prompt`) is
handed to the harness as `system_message`
(`services/agent-runtime/atlas_runtime/agents/native.py:836,864`), and the harness
places `system_message` in the **context** tier
(`system_prompt.py:260-261`) — i.e. *after* its own stable tier.

So the model reads Hermes-owned instructions before it reads
"You are ATLAS, the operator agent inside L2 ATLAS."

**What is actually leaking (unconditional):**

| # | Leak | Location | Content |
|---|---|---|---|
| 1 | `HERMES_AGENT_HELP_GUIDANCE` | `system_prompt.py:101` (appended with no gate) | Names "the Hermes Agent foundation this system is built on", instructs `skill_view(name='hermes-agent')`, links `hermes-agent.nousresearch.com/docs` |
| 2 | Active-profile hint | `system_prompt.py:215-240` | Emits `~/.hermes/profiles/<name>/`, `~/.hermes/skills/`, `~/.hermes/plugins/`, `~/.hermes/cron/`, `~/.hermes/memories/` verbatim, plus cross-profile write-guard semantics ATLAS does not use |

**What is leaking conditionally, gated on `agent.valid_tool_names`
(`system_prompt.py:104-122`):**

| # | Leak | Gate | Why it is worse than cosmetic |
|---|---|---|---|
| 3 | `MEMORY_GUIDANCE` | `"memory" in valid_tool_names` | Tells the model "You have persistent memory across sessions… memory is injected into every turn" and to write via the `memory` tool. ATLAS passes `skip_memory=True` (`native.py:273`), which only nulls `_memory_store`/`_memory_manager` (`agent/agent_init.py:1073,1094`) — **it does not remove the tool or the guidance**. The model is told it has a memory system ATLAS switched off. |
| 4 | `SESSION_SEARCH_GUIDANCE` | `"session_search" in valid_tool_names` | Points recall at Hermes transcripts, not ATLAS `session_messages` |
| 5 | `SKILLS_GUIDANCE` + skills prompt | skills tools present | Points skill authoring at `~/.hermes/skills/`, not `skills/atlas/` |

**Explicitly ruled out as a cause:** `DEFAULT_AGENT_IDENTITY`
(`agent/prompt_builder.py`) has already been rebranded in this fork — it reads
"You are ATLAS, the operator agent inside L2 ATLAS." The identity block is fine.
The crossing comes from the *surrounding* guidance blocks and the tier ordering,
not from the identity string.

**Why the current mitigations do not hold.** `skip_context_files=True` and
`skip_memory=True` (`native.py:271-273`) suppress cwd context files and the memory
store. Neither touches leaks 1, 2, 4 or 5, and leak 3 survives `skip_memory`
entirely.

### A.2 The memory system as it exists

The architecture is sound and is worth building on, not replacing.

- **Assembly:** `context_service.assemble_context` renders static sections (Focus,
  goal tree, Project, Operating Contract) and delegates dynamic sections to
  `MemoryRouter` (`memory_router.py`).
- **Retrievers (8):** `RecentRunsRetriever`, `ConversationHistoryRetriever`,
  `ObservationRetriever`, `FailurePatternRetriever`, `WikiFtsRetriever`,
  `HybridKnowledgeRetriever`, `BrainRetriever`, `SkillRetriever`
  (`memory_router.py:165-853`).
- **Boundary discipline (keep):** one redaction implementation applied to every
  snippet; provenance token per snippet (`wiki:<id>`, `run:<id>`, …); a
  `RetrievalEnvelope` with selected/rejected recorded on the run contract.
- **Delivery:** the brief is delivered per turn as a synthetic prefix
  (`native._volatile_context_message`) so the cached system prefix stays
  byte-stable — a good decision, keep it.

### A.3 Gaps against the goal

| # | Gap | Evidence |
|---|---|---|
| G1 | **No active recall.** Agent-facing tools are `atlas_actor`, `atlas_graph`, `atlas_team` (`prompt_compiler.py:35`). There is no way for the agent to ask "what do I know about X" mid-run. `atlas_graph` reaches the brain graph only — 1 of 8 sources. | `prompt_compiler.py:35`; `native.py:644-663` |
| G2 | **No typed memory object.** Knowledge is scattered across runs, observations, brain nodes and wiki pages. Nothing carries scope, confidence, TTL, supersession, or origin. | absence across `atlas_runtime/` |
| G3 | **No agent-managed custom summaries.** `run_summary_service` writes per-run summaries; `storage_compressor` compresses tool output for storage. Neither consolidates a session into durable semantic memory. | `run_summary_service.py`, `storage_compressor.py` |
| G4 | **No decay, dedup, or forgetting.** `retention_service` purges `audit_events` by age and is not memory-aware. | `retention_service.py` |
| G5 | **Ranking is not comparable across retrievers.** `MemorySnippet.score` is a private sort key per retriever; only some set a normalized `relevance`. Cross-section ordering is fixed priority, so a highly relevant wiki hit can never outrank a stale recent run. The docstring documents this as a known hazard. | `memory_router.py:88-109` |
| G6 | **Toggles are four global booleans.** `token_budget`, `enable_semantic`, `enable_skills`, `enable_brain`, `inject_operator_context`. No per-scope, per-retriever, per-session or per-run control; the only run-level escape is `ATLAS_SKIP_CONTEXT=1`. | `packages/atlas-core/atlas_core/schemas/control_plane.py:97-105`; `context_service.py:161-166` |
| G7 | **No feedback loop.** Nothing measures whether injected memory was retrieved correctly, used, or helped. | `evals/agent_contract.py` covers contract conformance only |

### A.4 Prime Agent doctrine — what transfers

Per this repo's own 2026-08-09 review
(`docs/qa/harness-quality-review-2026-08-09.md:145-152`), Prime Agent stays
reference-only under D-023. Four patterns transfer to memory:

1. **Host-owned bounded gates.** A memory write is validated by ATLAS, not trusted
   from the model.
2. **Failed-gate output feeds the next attempt.** A rejected write returns its
   reason so the agent can correct it once, within a bounded retry.
3. **Exhausted budget is not success.** A truncated brief must say so, not silently
   drop evidence.
4. **Versioned refinement with rollback.** Consolidation passes are versioned and
   revertible.

---

## Part B — Design: ATLAS Memory v2

### B.1 Principles

1. **One retrieval implementation, two entry points.** Passive (pre-run push) and
   active (in-run tool call) route through the same `MemoryRouter`. Divergent code
   paths would guarantee divergent answers.
2. **Memory is evidence, not instruction.** Already the ATLAS posture
   (`atlas_core.md:27-28`) — v2 must not weaken it. Retrieved memory never
   acquires instruction authority.
3. **Every memory carries provenance and a confidence.** No anonymous facts.
4. **The host gates writes.** The model proposes; ATLAS validates, dedups,
   redacts, and records a receipt.
5. **Forgetting is a feature.** A memory system with no expiry becomes a liability
   — this is precisely the failure the vendored `MEMORY_GUIDANCE` warns about.
6. **Off is a first-class state.** Every layer must be disableable without editing
   code, at global / project / session / run precedence.

### B.2 The memory object

New table `memories` (new migration; `session_messages` was 0030, so this lands
after the current head).

| Field | Purpose |
|---|---|
| `id` | stable id |
| `scope` | `global` \| `user` \| `project` \| `session` |
| `kind` | `fact` \| `preference` \| `convention` \| `failure` \| `procedure` \| `episodic_summary` |
| `body` | redacted text |
| `confidence` | 0..1, set by writer, adjusted by the gate |
| `origin` | `operator` \| `agent` \| `derived` (consolidation) |
| `source_ids` | provenance tokens, same vocabulary the router already emits |
| `project_id` / `session_id` | scope binding |
| `created_at`, `last_used_at`, `use_count` | decay inputs |
| `expires_at` | TTL; null = no expiry |
| `superseded_by` | id of the memory that replaced this one |
| `status` | `active` \| `superseded` \| `expired` \| `rejected` |
| `version` | bumped on consolidation, enables rollback |

### B.3 Retrieval: passive and active

- **Passive** — unchanged trigger point (`assemble_context` before a run), but the
  section set and budget come from the resolved `MemoryPolicy` (B.6), and a
  truncated brief emits an explicit "N items dropped at budget" line rather than
  ending silently.
- **Active** — new `atlas_memory` tool, registered exactly like `graph_bridge` /
  `actor_bridge` (`ensure_memory_bridge()`, called from `native.execute` beside the
  existing three) and added to `prompt_compiler.AGENT_FACING_TOOLS`. Note
  `test_prompt_compiler` asserts that tuple matches what the bridges register — it
  must be updated in the same commit or the suite fails.

Actions: `search(query, scope?, kind?, k?)`, `write(kind, scope, body, confidence?,
ttl?)`, `update(id, …)`, `supersede(id, by_id, reason)`, `forget(id, reason)`,
`list(scope?, kind?)`. All return the `{"ok": bool, …}` shape the runtime already
classifies as success/failure (`native._tool_result_failed`).

### B.4 The write gate (Prime Agent pattern 1 + 2)

A proposed write is rejected, with a machine-readable reason returned to the agent,
when it:

1. matches `SECRET_PATTERNS`;
2. is a near-duplicate of an active memory (offer `update` instead);
3. is a staleness class — PR/issue numbers, commit SHAs, "phase N done", file
   counts, task progress (the vendored guidance's own rule set, which is correct
   and worth keeping);
4. exceeds the per-scope memory count budget without superseding something;
5. carries no usable provenance.

The agent gets exactly one bounded correction attempt per proposal. Every accepted
and rejected write is audited.

### B.5 Consolidation, decay, forgetting

Extend `retention_service` rather than adding a scheduler:

- **Expire** — TTL elapsed → `status=expired`.
- **Decay** — rank down by `last_used_at`/`use_count`; below threshold, demote out
  of the passive brief while remaining findable by active `search`. Decayed ≠
  deleted.
- **Consolidate** — merge near-duplicate `fact`/`preference` memories into one
  `derived` memory citing its sources; bump `version`; keep the sources
  `superseded` (not deleted) so the pass is revertible.
- **Contradict** — a new memory that contradicts an active one sets
  `superseded_by` rather than co-existing.

### B.6 Toggle plane (`MemoryPolicy`)

Replace the four booleans in `ContextConfig` with a policy resolved at
**global → project → session → run** precedence, backward compatible (the existing
booleans map onto per-retriever enables so no config migration breaks):

- `enabled` (master off switch)
- `autonomy`: `off` | `read_only` | `propose` | `autonomous_write`
- per-scope enable (`global`/`user`/`project`/`session`)
- per-retriever enable (the 8 existing + `memories`)
- `token_budget`
- `inject_operator_context` (retained)

Surfaced through: `atlas memory` CLI, cockpit Settings, and `ATLAS_MEMORY_*` env
for a single run. Mutations reuse the existing `ConfigChangeReceipt` path so the
operator gets the same typed receipt they already get for provider changes.

### B.7 Evaluation (closes G7)

Extend `evals/agent_contract.py`, reusing the `pass`/`fail`/`abstain` verdict model
fixed in Q-001/Q-002:

- **recall@k** — a planted fact is returned by `search`;
- **injection fidelity** — a scoped memory appears in the assembled brief when in
  scope and is absent when out of scope;
- **gate correctness** — each rejection class fires on its fixture and nothing else;
- **supersession** — a superseded memory stops appearing in passive briefs;
- **no-leak conformance** — the compiled system prompt contains no `hermes` /
  `~/.hermes` substring (this is the WP-0 regression test).

---

## Part C — Execution plan

Ordered. WP-0 is independent and should land first — it is small, it is the defect
the operator actually observed, and it de-risks everything after it.

### WP-0 — Close the Hermes crossing

**Approach (D-001 safe).** In `native._default_factory`, beside the existing
`_harden_compaction(agent)` instance-hardening precedent, add
`_scrub_foundation_prompt(agent)` that **wraps `agent._build_system_prompt`** with
an ATLAS composer. Wrapping the method (rather than setting
`agent._cached_system_prompt` once) is required because context compression rebuilds
the prompt mid-session (`agent/conversation_compression.py:338,372`) and a one-shot
assignment would be silently undone.

The wrapper:
1. calls through to the foundation implementation;
2. removes the Hermes-branded blocks — exact-match against the imported constants
   `HERMES_AGENT_HELP_GUIDANCE`, `MEMORY_GUIDANCE`, `SESSION_SEARCH_GUIDANCE`,
   `SKILLS_GUIDANCE`, plus a regex for the inline active-profile hint (it is inline
   code, not a constant, so constant-patching cannot reach it);
3. hoists the ATLAS contract to position 0 so ATLAS identity precedes everything.

**Files:** `services/agent-runtime/atlas_runtime/agents/native.py` (+ its tests).

**Acceptance:**
- A conformance test asserts the final composed system prompt contains no
  case-insensitive `hermes` and no `~/.hermes` (except where ATLAS deliberately
  names the foundation).
- Byte-stability preserved: the composed prefix is identical across turns of one
  session (the prefix-cache invariant `_contract_system_message` protects).
- A live run's system prompt is captured and diffed against the pre-fix baseline
  (see E.1).

**Decide during execution:** whether the harness's `memory`, `session_search` and
skills tools should be removed from the toolset for ATLAS runs (honest: ATLAS owns
these) or remapped onto ATLAS equivalents in WP-2. Removal is the correct interim
state — advertising a disabled memory tool is the defect.

### WP-1 — Memory object + store

Migration for `memories` (B.2) + `memory_service.py` with typed CRUD, redaction on
write, provenance required. No behavior change yet.
**Acceptance:** service unit tests; redaction proven on write; migration
up/down clean on a populated DB.

### WP-2 — `atlas_memory` tool + write gate

`memory_bridge.ensure_memory_bridge()` following `graph_bridge`; register in
`native.execute`; add to `AGENT_FACING_TOOLS` **and** update `test_prompt_compiler`
in the same commit.
**Acceptance:** each gate rejection class has a test; one bounded correction retry
is proven; a live run writes and reads back a memory.

### WP-3 — Unified relevance + `MemoryRouter.search()`

Give every retriever a normalized 0..1 `relevance`; rank across sections with a
per-section floor so Focus and failure evidence cannot be starved; expose
`MemoryRouter.search()` as the shared implementation behind both the passive brief
and WP-2's `search`.
**Acceptance:** the `memory_router.py:88-109` hazard docstring can be retired
because the field is no longer optional; budget truncation is reported, not silent.

### WP-4 — Custom summaries, auto-ingested

Rolling session summary written at run end from `session_messages` (never raw
`audit_events` — the ~200K-token trap already recorded in
`.planning/todos/POST-SESSION-2026-07-17.md`), stored as
`kind=episodic_summary, scope=session`. Promotion to `project` scope when
referenced or when it survives N sessions. Operator-authored summaries via
`atlas memory write`. Agent may propose promotion; the gate decides.
**Acceptance:** a multi-run session produces exactly one rolling summary that is
versioned and revertible.

### WP-5 — Decay, consolidation, forgetting

Extend `retention_service` per B.5.
**Acceptance:** consolidation is revertible by version; expired and decayed
memories leave the passive brief but stay findable by active search; every
mutation audited.

### WP-6 — Toggle plane

`MemoryPolicy` (B.6) with global→project→session→run resolution, backward-compatible
mapping from the current booleans, CLI + cockpit + env surfaces, `ConfigChangeReceipt`
on mutation.
**Acceptance:** memory can be fully disabled at each level and the run's contract
snapshot proves the resolved policy that was applied.

### WP-7 — Memory evals

Per B.7.
**Acceptance:** the new dimensions are in the promotion gate and the gate still
passes.

---

## Part D — Best-practice checklist to sweep before/while building

Carried into WP-3/WP-4 review, not treated as settled:

- Episodic vs semantic vs procedural separation (the `kind` taxonomy encodes it —
  confirm the split earns its complexity).
- Write-time extraction vs read-time synthesis: v2 does write-time (gated) plus
  read-time ranking. Confirm the cost split is right for local SQLite.
- Recency/frequency/relevance blend for decay — pick and document the formula
  rather than leaving it implicit.
- Contradiction handling: supersede (chosen) vs confidence decay vs both.
- Retrieval evaluation before retrieval tuning — WP-7 should land close to WP-3,
  not last, or tuning is unmeasurable.
- Memory poisoning: retrieved memory must never gain instruction authority. This is
  already ATLAS's stated posture; the new tool must not create a hole in it.

**Open for a research pass next session** (my knowledge has a cutoff; these move
fast and should be checked, not recalled): current published patterns for agent
memory consolidation and forgetting, and whether any of them beat the design above
on the specific axis of a single-operator local-first agent.

---

## Part E — Owed live checks

**E.1 and E.2 are now MEASURED (2026-08-12), not inferred.** Method: construct the
agent exactly as `native._default_factory` does (real operator config resolved
through `config_service.resolve_provider()` → `freellmapi` / `model=auto`), then
call `agent._build_system_prompt(SENTINEL)`. The composed prompt is a pure function
of the agent instance, so no network turn is needed and the result is
deterministic — a better regression baseline than a live turn.

**E.1 — RESULT. The crossing is an ordering defect first, a branding defect second.**

| Measure | Before WP-0 | After WP-0 |
|---|---|---|
| Composed prompt | 23,697 chars | 1,484 chars |
| ATLAS contract begins at offset | **23,585** (last 0.5%) | **0** |
| `hermes` occurrences (case-insensitive) | **35** | **0** |
| `~/.hermes` occurrences | 1 | 0 |
| `valid_tool_names` | 18 | 18 (unchanged) |

The dominant term was **not** in Part A's list: `build_skills_system_prompt`
emitted a **~17,000-char catalogue of Hermes-ecosystem skills** — 72% of the whole
prompt — naming `hermes-cloud-gateway`, `hermes-cronjobs`, `kanban-worker`,
`petdex`, `godmode` and dozens more. ATLAS was paying that on every turn of every
run, and it is the single largest reason the model presented as Hermes.

**E.2 — RESULT. Leaks 3–5 all fire.** Measured `valid_tool_names` (18):

```
clarify, delegate_task, discord, discord_admin, execute_code, memory, patch,
process, read_file, search_files, session_search, skill_manage, skill_view,
skills_list, terminal, text_to_speech, todo, write_file
```

`memory`, `session_search` and `skill_manage` are all present, so
`MEMORY_GUIDANCE`, `SESSION_SEARCH_GUIDANCE` and `SKILLS_GUIDANCE` were all being
emitted. Confirmed in the captured text: *"You have persistent memory across
sessions"* appeared at offset 819 — while `skip_memory=True` had nulled the store.

**Resolution of the WP-0 open question (tool removal vs remapping):** neither.
Shipped answer is **mute at the prompt gate, keep the tool dispatchable** —
`valid_tool_names` is filtered only for the duration of prompt composition and
restored immediately. Skill discovery stays live through `skills_list` on demand
instead of costing 17K chars per turn, and no capability the model already had
disappears. The branding filter behind it works on *structure* (drop any
stable-tier block that names the harness) rather than by matching the frozen text
of the guidance constants, which would silently stop matching on any upstream
reword.

**E.3 — Confirm the migration head** before writing the WP-1 migration. Still owed.

---

## Sequencing note

Phase 10.8 Plan 04 is still the active blocking checkpoint (`.planning/STATE.md`):
genuine Windows Terminal visual checks and the installed permission/cancellation/
reconnect rows remain evidence debt, and the recorded decision is `defer`. This
memory program is **not** a substitute for closing that. WP-0 is small and
self-contained enough to land alongside it; WP-1 onward is a v1.2-scale body of
work and should be scoped as its own phase rather than absorbed into 10.8.
</content>
</invoke>
