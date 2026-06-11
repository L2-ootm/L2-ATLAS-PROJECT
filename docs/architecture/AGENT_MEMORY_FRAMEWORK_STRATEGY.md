# ATLAS Diverse Efficient Agent Memory Framework Strategy

**Date:** 2026-06-08
**Phase:** 4.5 — architecture context (extended)
**Status:** Accepted direction — implementation begins Phase 6
**Decision record:** `docs/decisions/D-019-diverse-agent-memory-framework.md`
**Foundation principle:** `docs/architecture/HERMES_FIRST_FOUNDATION_PRINCIPLE.md`
**Input document:** `docs/architecture/DIVERSE_AGENT_MEMORY_FRAMEWORK.md`

---

## Strategic Statement

Memory is a major differentiator for the L2/ATLAS harness. Most current agent harnesses treat memory as one of: chat history, simple vector search, profile notes, or static RAG documents. ATLAS will be different.

The L2/ATLAS harness is built from the evolved Hermes foundation. It combines seven memory layers into a governed, efficient, agent-native memory framework. The goal is not more context — the goal is better selected, more trustworthy, and more efficient memory.

```
Hermes self-improving memory
  + LLM Wiki compiled knowledge
  + local semantic retrieval
  + graph memory (entities, relationships, missions)
  + audit/event memory
  + skill/procedure memory
  → governed by a policy-aware memory router
```

This is not an add-on. It is built from within the evolved Hermes/L2 foundation.

---

## Foundation Framing

ATLAS memory is not layered on top of Hermes from the outside. It evolves Hermes' memory infrastructure from within:

- Hermes session memory and profile memory are the starting point — proven, production-grade.
- Each additional layer enhances the foundation without duplicating what Hermes already does correctly.
- The memory router is a new capability inside the L2/ATLAS foundation, not a wrapper service.

Change classification (D-018):
- Hermes profile/session memory → **Preserve from Hermes**
- LLM Wiki, source registry, audit-event memory → **Enhance in L2/ATLAS foundation**
- Semantic retrieval (turbovec/sqlite-vec) → **Enhance in L2/ATLAS foundation**
- Graph memory (OpenGraph/Graphify) → **L2 product module**
- Skill/procedure memory → **Enhance in L2/ATLAS foundation**
- Memory router → **L2 product module**

---

## Memory Layers

### Layer 1 — Hermes Profile and Session Memory

**What it provides:** user profile, persistent preferences, session recall, stable operational facts, self-improving skill extraction.

**ATLAS role:**
- Preserve Hermes memory strengths.
- Add stricter memory classification: distinguish task artifacts (ephemeral) from long-term operational facts (durable).
- Prevent stale task output from becoming long-term memory without a lint pass.
- Connect all memory writes to an AuditEvent: what was written, from what source, by which run.

**Storage:** Hermes `~/.hermes/profiles/<workspace>/` (existing).

**Phase:** Available now. Governed starting Phase 6.

---

### Layer 2 — LLM Wiki Compiled Knowledge

**What it provides:** curated, maintained, evidence-grade project/operational knowledge. Not a raw document dump.

**ATLAS role:**
- Long-term operating knowledge that agents can read and update safely.
- Source registry with immutable raw copies + SHA-256 provenance.
- Compiled wiki pages: structured, linted, contradiction-detected.
- Wiki/log.md and wiki/index.md maintain audit-linked update history.
- FTS5 full-text search (primary retrieval).
- Semantic search via sqlite-vec (optional, gracefully degraded).

**Storage:** `wiki/` directory + SQLite `wiki_pages` and `sources` tables.

**Phase:** Phase 6 (first implementation).

---

### Layer 3 — Local Semantic Retrieval (turbovec/sqlite-vec)

**What it provides:** efficient local vector retrieval for semantic candidate search. Privacy-preserving, no mandatory cloud vector DB.

**ATLAS role:**
- Optional semantic layer over SQLite wiki pages and source chunks.
- Benchmarked against real ATLAS queries before enabling by default.
- Fallback to FTS5 when sqlite-vec is unavailable or unloaded.
- Source IDs must remain stable across index rebuilds (no floating chunk IDs).
- Vector retrieval surfaces candidates — it does not replace citations or source provenance.

**Storage:** sqlite-vec extension loaded into the ATLAS SQLite DB. Index stored in `db/atlas.db`.

**Phase:** Phase 6 (optional path, gracefully degraded). Spike deferred if sqlite-vec is unavailable (D-014).

---

### Layer 4 — Graph Memory (OpenGraph/Graphify)

> **Boundary vs. Twenty CRM (D-020/D-021 §4):** Twenty is the system of record for external relationship data (people, organizations, opportunities, interactions) — accessed via API/MCP/webhooks only. Layer 4 is a **local derived knowledge graph over ATLAS-native entities** (missions, runs, sources, wiki pages, skills). It may reference Twenty records by stable ID; it never duplicates or re-stores Twenty's data.

**What it provides:** relationship-aware memory. Entities, relationships, missions, runs, people, sources, decisions, skills, artifacts — all traversable.

**ATLAS role:**
- Model operational relationships: missions → runs → artifacts → decisions → people → skills → sources.
- Answer questions like "what decisions led here?", "which skills are tied to this workflow?", "which sources back this claim?".
- Graphify-style extraction: transform project docs, code structure, and conversation artefacts into a queryable graph.
- All graph edges must have a source backing — no hallucinated relationships stored as facts.

**Storage:** `.planning/graphs/` (Graphify pattern) or a dedicated SQLite graph table.

**Phase:** Research input in Phase 6. First implementation in Phase 7 or Phase 8 adjunct. Full graph in v2.0.

---

### Layer 5 — Audit/Event Memory

**What it provides:** every meaningful action produces a durable event record. Tool calls, model calls, approvals, failures, artifacts, state transitions — all queryable.

**ATLAS role:**
- Operational memory and run replay.
- Accountability: every memory update has a linked AuditEvent with source, run_id, and operator context.
- Provenance for memory writes: any wiki update, profile update, or skill modification must reference an AuditEvent.
- Evidence for future planning and research: "what did the agent do in run X that led to outcome Y?"

**Storage:** `audit_events` and `tool_calls` tables (SQLite, Phase 4).

**Phase:** Available now (Phase 4). Queried as a memory layer starting Phase 6.

---

### Layer 6 — Skill/Procedure Memory

**What it provides:** reusable workflows, procedures extracted from difficult tasks, operational playbooks.

**ATLAS role:**
- L2-curated skill packs with classification: autonomy_level, risk, requires_tools, requires_secrets, public_safe.
- Skill provenance: which run produced or improved a skill, what source backs it.
- Skill effectiveness tracking via AuditEvents (skill invoked → outcome).
- Safe skill sharing and export: L2-internal skills stay classified; public skills meet the public_safe bar.

**Storage:** Hermes skill directory + ATLAS `skill_metadata` table (Phase 9).

**Phase:** Phase 9. Referenced by the memory router from Phase 6 onward.

---

## Memory Router

The memory router is the policy-governed dispatch layer. It selects which memory layers to consult for a given agent context assembly request.

```
task intent + policy labels + sensitivity classification + source scope
      │
      ▼
atlas_core.memory_router.select(context: MemoryRequest) -> MemoryPackage
      │
      ├─► Layer 1: Hermes profile memory        (always: operational baseline)
      ├─► Layer 1: Session history search        (if: session-recall intent)
      ├─► Layer 2: LLM Wiki query                (if: wiki-scope, research, fact-check)
      ├─► Layer 3: Semantic retrieval            (if: semantic-scope, wiki available)
      ├─► Layer 4: Graph memory traversal        (if: graph-scope, graph available)
      ├─► Layer 5: Audit/event query             (if: run-history, evidence-scope)
      └─► Layer 6: Skill loading                 (if: task-execution, skill-match)
            │
            ▼
      compressed context package
      (ranked, deduplicated, provenance-labeled)
```

### Router decisions

| Decision | Trigger condition |
|----------|------------------|
| Use profile memory | Always — operational baseline, preferences, identity |
| Search session history | `intent: recall`, `scope: session`, or `scope: recent` |
| Query wiki | `scope: wiki`, `scope: research`, `intent: fact-check`, `intent: draft` |
| Use semantic retrieval | Wiki available + semantic-capable model + `scope: semantic` |
| Traverse graph memory | Graph available + `scope: graph`, `intent: relationship-query` |
| Load audit/event history | `scope: run-history`, `intent: evidence`, `intent: replay` |
| Load skills | `intent: task-execution`, skill match found |
| Block layer | `policy: no-sensitive-data` + layer contains sensitive content |
| Block provider injection | `provider: experimental` + any sensitive memory present |

### Memory router controls

- **Provider safety check:** if the target model/provider carries `no-sensitive-data` or `experimental` policy labels, the router must not inject memory that contains sensitive or private content, even if the task requests it.
- **Sensitivity labels:** every memory item carries a sensitivity label (public, internal, private, restricted). The router matches against the provider's policy label.
- **Untrusted sources:** all memory items derived from external/untrusted sources carry `untrusted: true`. The router wraps these in the `untrusted_context_message` wrapper (Odysseus pattern) before injection.
- **Source provenance required:** semantic and graph retrieval must include the source ID and wiki slug alongside each retrieved item. The agent context must be able to cite the source, not just quote a chunk.

---

## Required Memory Controls

These are non-negotiable invariants for all memory layers.

| Control | Rule |
|---------|------|
| Memory writes need provenance | Every write to any memory layer must reference a run_id, source_id, or operator action. No anonymous memory updates. |
| Sensitive memory requires policy labels | Any memory item containing credentials, PII, private client data, or L2-internal material must carry a sensitivity label before storage. |
| External/untrusted sources must be marked | Content from web fetch, file paste, email, or any external tool output is `untrusted: true` on ingestion. |
| Vector retrieval cannot replace citations | Semantic search surfaces candidates. The agent must cite the wiki page or source record, not the vector chunk ID. |
| Graph relationships require source backing | A graph edge (A → relates-to → B) must reference the source record or AuditEvent that established the relationship. No inferred edges stored as facts without provenance. |
| Memory must be compact and efficient | Context assembly must compress, rank, and deduplicate before injection. No raw context dumps. Prefer structured summaries over full-text payloads where possible. |
| Local/private memory stays local | Profile memory, private wiki pages, and L2-internal skills never leave the local machine. No cloud sync without explicit operator action. |
| Memory is queryable, inspectable, and correctable | The operator must be able to: list what is in memory, see why it was stored, correct or delete incorrect entries, and trace any memory write to its source. |

---

## Memory Provenance Schema

Every memory write (wiki update, profile update, skill update, graph edge) produces a provenance record:

```python
@dataclass
class MemoryProvenance:
    layer: MemoryLayer              # WIKI | PROFILE | GRAPH | SKILL | AUDIT
    item_id: str                    # wiki slug / skill name / graph node ID
    run_id: str | None              # run that produced this memory update
    source_id: str | None           # source record (if from ingest)
    audit_event_id: str | None      # AuditEvent that triggered the write
    operator_id: str | None         # operator who approved or manually created it
    sensitivity: SensitivityLabel   # PUBLIC | INTERNAL | PRIVATE | RESTRICTED
    untrusted: bool                 # True if any source is external/untrusted
    written_at: datetime
```

This record is stored alongside the memory item. It is the answer to "why was this stored?" and "who is responsible?"

---

## Context Package Format

The memory router returns a structured `MemoryPackage`, not a raw string dump:

```python
@dataclass
class MemoryItem:
    layer: MemoryLayer
    item_id: str
    content_summary: str            # compressed representation
    citation: str                   # source slug / wiki page URL / audit event ID
    sensitivity: SensitivityLabel
    untrusted: bool
    relevance_score: float

@dataclass
class MemoryPackage:
    items: list[MemoryItem]         # ranked by relevance, deduplicated
    token_budget_used: int          # estimated tokens for this package
    layers_queried: list[MemoryLayer]
    layers_blocked: list[tuple[MemoryLayer, str]]  # (layer, reason)
    provenance_ids: list[str]       # all source/audit IDs referenced
```

The agent receives the `MemoryPackage` and assembles the context. Citations are injected alongside content. Blocked layers are logged as AuditEvents.

---

## Implementation Phases

| Phase | Memory layer delivered |
|-------|----------------------|
| Phase 4 (done) | Audit/event memory (AuditEvent bus, ToolCall records) |
| Phase 5 (done) | Policy engine for workspace boundary (memory write authorization) |
| Phase 6 | LLM Wiki (Layer 2): ingest, FTS search, optional semantic search, source registry, provenance, audit-linked updates. Memory provenance schema. |
| Phase 7 | Memory router API endpoints: `POST /memory/query`, `GET /memory/items/{id}`, `GET /memory/provenance/{id}`. Skill memory query interface. |
| Phase 8 | Cockpit memory surface: source browser, wiki browser, memory inspection/correction, retrieval diagnostics, "why was this loaded?" view. |
| Phase 9 | Skill/procedure memory (Layer 6): classification, provenance, effectiveness tracking. |
| v2.0 | Graph memory (Layer 4): full OpenGraph/Graphify implementation. Multi-layer memory router with graph traversal. |

---

## Differentiator Statement

The L2/ATLAS harness is stronger than current agent harnesses because:

| Capability | Common harnesses | L2/ATLAS |
|-----------|-----------------|----------|
| Memory type | Chat history or simple RAG | 7 governed layers |
| Source provenance | None or implicit | Explicit provenance record on every write |
| Sensitive data | Unguarded injection | Policy labels + provider safety check |
| Retrieval | Nearest-neighbor chunks | Ranked, cited, provenance-labeled items |
| External content | Raw injection | `untrusted_context_message` wrapper required |
| Operator visibility | None | Queryable, inspectable, correctable |
| Compaction | Full-text dump | Compressed context package with token budget |
| Graph relationships | None | Relationship-aware traversal (v2.0) with source backing |
| Audit trail | None | Every memory write linked to AuditEvent |
