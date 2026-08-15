# Memory Provenance Doctrine — Design

**Status:** A–D shipped 2026-08-15 (`07102b4`, `a6d2007`, `d061843`, `f546366`)
**Date:** 2026-08-15
**Amends:** `2026-08-12-atlas-memory-v2-design-and-execution-plan.md` (B.2, B.4, B.5)
**Relates to:** `2026-08-12-knowledge-graph-control-plan.md`

This is not a competing plan. Memory v2 designed *what* memory is and *where* it
lives; it left *how good any given piece of it is* to a writer-set confidence
number. This document replaces that number with a grade the writer cannot set,
and defines what the model is allowed to do with each grade.

---

## Part A — Why (verified, not assumed)

The operator's framing: *"the model would try to operate even on shitty data."*
That is not a model defect. ATLAS destroys the quality signal before the model
ever sees it. Four findings, each verified against code or the live database on
2026-08-15.

### A.1 Every retrieved item arrives at the model at identical trust

`memory_router.assemble_envelope` renders every accepted snippet as:

```
<evidence source="..." trust="evidence">
```

`trust` is a hardcoded string literal (`memory_router.py:1245`). The operator's
own words, a failed run's stderr, a 0.92-confidence graph node and a wiki page
are typographically indistinguishable in the brief. Nothing in the prompt lets
the model weigh one against another, so it weighs them equally — which is the
reported behaviour.

### A.2 The one field that could carry quality is wrong and unread

`confidence=max(0.0, min(1.0, snippet.score))` (`memory_router.py:1235`).
`MemorySnippet.score` is documented **in its own docstring** as a sort key whose
scale is private to the emitting retriever, and most retrievers emit a negated
list index. So `confidence` is `0.0` for nearly every snippet in the system.

Measured directly against the real router:

| source | score | confidence | trust |
|---|---|---|---|
| `session_user:r1` | -0.0 | 0.0 | evidence |
| `failure:r3` | -1.0 | 0.0 | evidence |
| `brain:n7` | 0.92 | 0.92 | evidence |
| `wiki:w2` | -2.0 | 0.0 | evidence |

The field is also never rendered. It is a broken value that no consumer reads —
which is precisely how it survives a redesign and becomes load-bearing later.

### A.3 On the write side the agent grades its own homework

`graph_bridge.py:324` — `confidence=_confidence(args, default=0.8)`. The model
states its own confidence and ATLAS records it. `source_id` is `run:<id>`: it
captures *who said it*, never *what backed it*. There is no evidence requirement
and no path by which a claim can be distinguished from a checked fact.

Consequences, both live:

* **Contradictions resolve by recency, silently.** `node_id_for(entity_type,
  label)` means a re-assertion of the same entity upserts over the old row
  (`brain_service.upsert_node`). A later self-graded 0.8 guess overwrites an
  earlier verified fact and nothing surfaces the conflict.
* **Secrets land durably.** `redact()` runs in the router on the way *out*
  (`memory_router.py:1229`); `graph_bridge.py` never calls it. A secret written
  into `brain_nodes` is stored in the clear and scrubbed only in transit.

### A.4 The graph stores no knowledge at all

The finding that reframes the intake problem. Live `~/.atlas/atlas.db`,
2026-08-15:

```
brain_nodes: 348
  entity_type: run 175, mission 173      <- ATLAS's own bookkeeping
  confidence:  1.0 173, 0.9 168, 0.5 7
  source_id:   run:* 175, mission:<uuid> 173
```

**Zero agent-authored knowledge nodes.** No `concept` nodes, despite `concept`
being `add_node`'s default `entity_type`. The `atlas_graph` tool is registered
and writable; the agent simply never uses it, because nothing tells it what
belongs there and nothing rewards the write.

This is the same failure already diagnosed in `ec1eed75`: *"either the managed
path becomes the path of least resistance, or WP-B stays unused."* Adding intake
gates to a path nobody walks yields a well-governed empty graph. The gate and
the reason to write must ship together.

---

## Part B — The provenance ladder

One vocabulary, assigned by the code that knows the item's origin. **The agent
never sets it.**

| Grade | Assigned when | What it licenses |
|---|---|---|
| `stated` | the operator typed it | Authoritative about **intent**. Never overridden by inference. |
| `verified` | a check ran and passed (gate verdict `verified`) | Authoritative about **fact**. |
| `observed` | a tool returned it — file read, exit code, DB row | True **at its timestamp**. Decays. |
| `derived` | the agent concluded it from cited sources | Only as good as what it cites. |
| `reported` | a subagent, actor or module returned it | A **claim** (`skills/atlas/delegation.md`), now a data grade. |
| `asserted` | nothing traceable backs it | The floor. Usable, never citable. |

`verified` reuses the word `verification_gate` already emits
(`verified` / `unverified` / `contradicted` / `no_mutations` / `exempt`) rather
than competing with it.

### B.1 Three rules that make it more than a label

**Origin is structural, not declared.** A retriever knows which table it read, so
the retriever sets the grade. There is no code path in which a model's output
chooses its own grade. This is the whole fix for A.3.

**Two axes, deliberately collapsed to one.** `stated` outranks `verified` on what
the operator *wants*; `verified` outranks `stated` on what is *true*. Rather than
model both axes, one rank order applies and one exception is stated in doctrine:
intent conflicts resolve to `stated`, fact conflicts resolve to `verified`, and a
`verified` fact contradicting a `stated` intent is **surfaced to the operator,
never auto-resolved** — the world disagreeing with what you want is a decision,
not a merge.

**Grades decay; values do not.** `observed` carries `observed_at` and renders with
age. A file's contents observed three weeks ago is not the evidence that the same
read is today, and flattening that difference is how an agent acts confidently on
a file that has since changed.

### B.2 Rank

```
verified 5 > stated 4 > observed 3 > derived 2 > reported 1 > asserted 0
```

Used only for contradiction resolution (Part C) and retrieval floors (Part D).
It is not a relevance score and must never be compared against one — the mistake
`MemorySnippet.score` already made once.

### B.3 Amendment to Memory v2

| Memory v2 (B.2) | Replaced by |
|---|---|
| `confidence` — 0..1, "set by writer, adjusted by the gate" | `grade` — origin-derived, writer cannot set |
| `origin` — `operator` \| `agent` \| `derived` | the six-grade ladder above |

WP-1's `memories` table adopts `grade` as its origin column when it lands. Slice A
defines the vocabulary as a shared primitive so WP-1 inherits it rather than
introducing a second, incompatible scale.

---

## Part C — The write boundary (slice B)

**Grades are assigned by the writer, structurally.** `atlas_graph op=add_node`
drops `confidence` from its schema and gains optional
`evidence: [tool_call_id | audit_event_id, ...]`. The bridge resolves every
citation against the current run's `audit_events`:

| Writer | Grade |
|---|---|
| citations resolve | `derived` |
| no citations | `asserted` |
| operator CLI (`atlas brain add`) | `stated` |
| ATLAS itself, from a tool result | `observed` |
| actor / subagent return | `reported` |
| run-end promotion, gate verdict `verified` | `derived` → `verified` |

A citation that does **not** resolve rejects the write and names the offending
ids. A fabricated citation is a signal worth surfacing, not a reason to silently
downgrade.

**Contradiction is recorded, not resolved by recency.** On upsert to an existing
id with a materially different summary:

* incoming rank ≥ existing → overwrite, record supersession;
* incoming rank < existing → **keep the existing node**, write a conflict row,
  return the conflict to the agent;
* `verified` vs `stated` → never auto-resolved; surfaced to the operator.

**Redaction moves to the write boundary.** `redact()` on write; the read-side pass
stays for legacy rows and defence in depth.

**The gate ships with a reason to write.** `skills/atlas/memory.md` plus a
turn-context line stating what belongs in the graph (durable, reusable,
operator-specific) versus the scratchpad (this run only). `asserted` nodes are
accepted but not retrievable into context by default — a holding pen, promotable
on later citation. An ungrounded write costs nothing and buys nothing; a grounded
one pays. Same shape as the adoption fix that worked in `ec1eed75`.

---

## Part D — The read boundary (slice A)

`MemorySnippet` gains `grade` and `observed_at`. **No default** — each of the nine
retrievers declares its grade, because each one knows the table it read. A default
would silently mis-grade every retriever anyone adds later.

`RetrievedEvidence.trust` stops being the hardcoded `"evidence"` and carries the
grade. `confidence` is **deleted**: derived from a documented-private sort key,
wrong for nearly every snippet, read by nothing.

What the model sees:

```
<evidence source="session_user:r1" grade="stated">
<evidence source="failure:r3" grade="observed" age="3d">
<evidence source="actor:a9" grade="reported">
```

with one doctrine line rendered *in the brief itself* explaining what each grade
licenses — delivered next to the evidence rather than 20k tokens earlier in the
L1 prompt, which is the delivery lesson from `340050cf`.

`asserted` is excluded from retrieval by default, so the floor grade never reaches
the model as evidence at all.

### D.1 Retriever grade assignments

| Retriever | Grade | Why |
|---|---|---|
| `ConversationHistoryRetriever` | `stated` (user) / `reported` (assistant) | the operator's words are intent; the agent's past reply is its own claim |
| `RecentRunsRetriever` | `observed` | run rows are machine-written fact |
| `ObservationRetriever` | `observed` | tool-witnessed |
| `FailurePatternRetriever` | `observed` | a failure that happened |
| `WikiFtsRetriever` | `stated` | operator-authored documentation |
| `HybridKnowledgeRetriever` | `stated` | same corpus |
| `BrainRetriever` | node's stored grade | the graph carries its own |
| `SkillRetriever` | `stated` | doctrine the operator installed |
| `ScratchpadRetriever` | `derived` | the agent's own working notes |

---

## Part E — Sequencing

| Slice | Scope | Commit |
|---|---|---|
| **A** | read boundary: ladder primitive, grades on all 9 retrievers, rendering, `confidence` fixed | `07102b4` |
| **B** | write boundary: evidence citation, contradiction rows, redact-on-write, `skills/atlas/memory.md` | `a6d2007` |
| **C** | operator absorption: `brain remember` + `OperatorProfileRetriever` | `d061843` |
| **D** | the ask drives retrieval | `f546366` |

D turned out to be the largest gap, and not the one the design predicted. The
plan was "enrich a thin prompt from `stated` + `verified` material". The measured
problem was more basic: **the operator's ask contributed nothing to retrieval at
all.** Terms came from the Focus alone, so a run with no standing Focus derived
zero terms, every matched retriever no-opped, and the router abstained. There was
no thin-prompt enrichment to tune because there was no prompt-driven retrieval to
begin with. Feeding the intent into the term list is the whole of D; the enrich-
from-high-grades layer the design imagined is unnecessary now that the ask reaches
the retrievers and the grades reach the model.

## Part G — Closed in `9690e61`

* **`verified` is reachable.** The tempting rule — promote a run's claims when
  its verdict is `verified` — over-claims: a run can check one thing and write
  down five. The rule shipped is narrower. A `derived` node is promoted when the
  evidence it *cited* includes a tool call the gate counted as a **passing**
  check. `ObservedCall` already carried the call id at the loader, so the cost
  was one field, one list and one function, with nothing added to the verdict
  payload — no audit row grew, no fixture churned.
* **Conflicts are surfaced.** `atlas brain conflicts` lists what lost and what
  was kept; `--needs-operator` filters to the decisions ATLAS refused to make;
  `--ack` discards a row once acted on, because a list the operator cannot clear
  stops being read. No new module, no migration, no dependency.
* **The grade inference is deleted**, along with `_BRAIN_MACHINE_TYPES`. Every
  writer states its grade and `_node()` floors anything unstated at `asserted`. A
  reader that second-guesses its writers only adds a second answer to disagree
  with the first — which is precisely how an `asserted` node got reported as
  `derived`.
* **A live bug it exposed.** `run_executor` mirrors every terminal run into the
  graph and declared no grade, so both nodes floored to `asserted` — below the
  retrieval floor. Every future run would have filed itself out of every brief,
  silently, because the write succeeds. Caught before it reached the live DB
  (348 nodes, all still `observed`, because no run had completed since 0038).

## Part H — Measured, and deliberately not built

Baseline, 500 brain nodes and 200 wiki pages, one context assembly:

| | |
|---|---|
| queries per brief | **340** — of which ~320 are SQLite's own FTS5 index reads |
| application-level queries | ~20; the operator profile adds exactly **one** |
| median assembly | **23.8 ms** before this work, **24.5 ms** after (run-to-run variance; the work is byte-identical) |
| brief | 5758 chars, 724 est. tokens against a 8000 budget |

**`brain_service.search` runs one unindexed `LIKE %term%` scan per term**, up to
six per brief. Measured slope:

| nodes | median |
|---:|---:|
| 350 | 0.70 ms |
| 5 000 | 8.45 ms |
| 20 000 | 33.58 ms |
| 50 000 | 95.12 ms |

Cleanly linear at ~1.8 ms per 1000 nodes, **per brief**. At today's 348 nodes it
is 0.7 ms and not worth touching; an FTS index over a 348-row table is the
premature optimisation. The number to act on is **~10k nodes (~20 ms)**, and the
fix when it arrives is an FTS5 index over `label`/`metadata_json`, not a
different store.

## Part I — Still open

* **`asserted` has no exit.** The holding pen is one-way: a claim later backed by
  evidence stays `asserted` unless re-written. Promotion only lifts `derived`.
* **Conflicts have no cockpit surface.** The CLI makes escalation real; whether a
  `needs_operator` conflict should also interrupt the operator in the UI is a
  second use case, and has not been demonstrated yet.

---

## Part F — Testing

* ladder: table-driven, one case per origin;
* contradiction: one case per rank pair, plus the `verified`-vs-`stated`
  no-auto-resolve case;
* redaction-on-write: a secret in a node body never reaches `brain_nodes`;
* retrievers: a grade assertion per retriever, so a new retriever cannot ship
  ungraded;
* every rule verified by **mutation** — remove the rule, watch the test fail.
  A test that still passes with its rule deleted is not guarding it.
