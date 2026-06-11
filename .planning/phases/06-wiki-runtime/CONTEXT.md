# Phase 6: LLM Wiki Runtime — First Memory Framework Layer

**Phase number:** 6
**Name:** LLM Wiki Runtime (first implementation step of the ATLAS memory framework)
**Status:** Pending

---

## Goal

Implement the wiki ingest, update, query, and lint pipeline as the first concrete implementation step of the broader ATLAS diverse memory framework (D-019). This phase delivers Layer 2 (LLM Wiki compiled knowledge) and the optional path for Layer 3 (local semantic retrieval), together with the memory provenance schema that all future memory layers depend on.

Phase 6 is not just "a wiki." It establishes the durable, auditable, operator-correctable knowledge layer that separates ATLAS from agent harnesses with only chat history or simple RAG.

---

## Foundation Framing

Phase 6 is built from within the evolved Hermes/L2 foundation (D-018). The wiki service is an enhancement to the foundation's memory capability — it does not replace Hermes profile/session memory (Layer 1) and does not introduce a competing storage system. It extends the same SQLite datastore and the same AuditEvent bus established in earlier phases.

---

## Memory Framework Context

This phase delivers:

| Memory layer | Deliverable |
|-------------|------------|
| Layer 2 — LLM Wiki | Wiki ingest, update, FTS search, lint, source registry, index/log maintenance |
| Layer 3 — Semantic retrieval | Optional sqlite-vec path; gracefully degraded to FTS if unavailable |
| Layer 5 — Audit/event memory | Every wiki operation emits an AuditEvent; wiki updates linked to run_id / source_id |
| Memory provenance schema | `MemoryProvenance` record type for all future memory writes |
| Graph memory research input | Document graph-memory design questions for v2.0 — no implementation |

---

## Requirements Covered

| REQ-ID | Description |
|--------|-------------|
| WIKI-01 | User can ingest a raw source file into the wiki (immutable raw copy, SHA-256 stamped, Source row created) |
| WIKI-02 | Agent can create or update a WikiPage; change logged in wiki/log.md and reflected in database |
| WIKI-03 | User can query wiki pages via FTS5 full-text search and get ranked results |
| WIKI-04 | wiki/index.md and wiki/log.md remain consistent after every agent-driven wiki update |
| WIKI-05 | Semantic vector search (sqlite-vec) returns relevant wiki pages for a natural-language query |
| AUDIT-03 | Wiki lint pass flags pages with stale or contradicted claims |

---

## Success Criteria

1. `atlas wiki ingest <path>` copies the file to `wiki/raw/`, computes SHA-256, creates a Source row with `untrusted: false` (internal) or `untrusted: true` (external origin), and emits an AuditEvent of kind `wiki_update` with `source_id` and `run_id` in the payload.
2. `atlas wiki update <slug> --body "..."` upserts a WikiPage row, appends to wiki/log.md, updates wiki/index.md, and writes a `MemoryProvenance` record linking the update to its AuditEvent.
3. `atlas wiki search "query"` returns ranked results via FTS5 full-text search with source citations (wiki slug + source_id).
4. `atlas wiki semantic "query"` returns results via sqlite-vec vector search (or prints a clear "sqlite-vec not loaded" message if the extension is absent). Results include source citations.
5. `atlas wiki lint` reports at least one stale/contradicted claim on a wiki page deliberately seeded with a contradiction.
6. wiki/index.md has an entry for every WikiPage row; wiki/log.md has an entry for every wiki_update AuditEvent.
7. Every wiki operation that modifies state carries a complete provenance record: which run, which source, which AuditEvent, which operator.
8. Service layer unit tests cover ingest, update, search, lint, and provenance paths (≥ 80% branch coverage on wiki_service.py).

---

## Key Decisions Applicable

- **D-004** (locked): LLM Wiki is first-class runtime — raw sources are immutable; wiki pages are agent-maintained; retrieval supplements but does not replace structured wiki pages or citations.
- **D-002** (locked): Audit-first — every wiki operation (ingest, update, lint) emits an AuditEvent via the Phase 4 event bus.
- **D-003** (locked): SQLite/WAL/FTS5/sqlite-vec — FTS5 for text search, sqlite-vec for semantic search. Degrade gracefully if sqlite-vec is unavailable.
- **D-011** (locked): Canonical repo layout — wiki service at `services/wiki-runtime/`; wiki markdown files at `wiki/`.
- **D-014** (accepted): Turbovec/sqlite-vec spike — optional semantic retrieval path; benchmark before enabling by default.
- **D-018** (locked): L2/ATLAS is the evolved Hermes foundation — wiki service enhances foundation memory, does not create a parallel system.
- **D-019** (accepted): Diverse memory framework — Phase 6 is Layer 2 + optional Layer 3. Memory provenance schema must be designed and documented in this phase even if not all layers are implemented.

---

## Memory Architecture Requirements for Phase 6

### Source registry

Every ingested file becomes a `Source` record with:
- `id` — stable UUID, must not change across re-ingestion of the same file.
- `path` — original path.
- `sha256` — content hash.
- `untrusted` — boolean; True for externally-sourced content.
- `ingested_at`, `ingested_by_run_id`.

Source IDs are stable. If the same file is re-ingested, the existing Source is updated (not replaced) to preserve all references from wiki pages and AuditEvents.

### FTS full-text search (primary retrieval)

FTS5 virtual table over `wiki_pages(title, body)`. Search results include: wiki slug, title, FTS rank, and source_id citation. Always available regardless of sqlite-vec status.

### Optional semantic retrieval (Layer 3 path)

If sqlite-vec is loaded:
- Embed wiki page bodies with a local embedding model (fastembed/ONNX or equivalent, no cloud API).
- Store vectors in the sqlite-vec extension table.
- Search returns ranked candidates with wiki slug and source_id citation alongside each item.
- If sqlite-vec is not loaded: print clear diagnostic message, return FTS results as fallback.

Source IDs must remain stable across vector index rebuilds. The index is a search cache, not the ground truth. The wiki_pages table is always the ground truth.

### Memory provenance (new in Phase 6)

Design and implement the `MemoryProvenance` record type (see D-019 and `AGENT_MEMORY_FRAMEWORK_STRATEGY.md`). Every wiki update writes a provenance record. This is the foundation for all future memory layers.

### Audit-linked memory updates

Every wiki operation that changes state must link to the AuditEvent that authorized or triggered it. An agent-driven wiki update references the `run_id` and `audit_event_id` of the run that produced it. An operator-driven update references the operator session.

### Untrusted-source handling

Ingested content from external URLs, emails, or external files is marked `untrusted: true` in the Source record. The wiki lint pass must flag wiki pages that cite only untrusted sources for a given claim. The memory router (future) will wrap untrusted-origin content with `untrusted_context_message` before injection.

### Graph-memory research (no implementation)

During Phase 6, document the following as open design questions for v2.0 graph memory:
- How should mission → run → artifact → source relationships be represented as a graph?
- What graph schema serves "which decisions led to this wiki page?"
- Can Graphify-style extraction produce meaningful edges from existing ATLAS artifacts?

These questions go into `docs/research/GRAPH_MEMORY_RESEARCH_NOTES.md` (to be created). No graph code is implemented in Phase 6.

---

## What NOT to Build

- Do not build the REST API for wiki endpoints — that is Phase 7.
- Do not build the cockpit wiki browser UI — that is Phase 8.
- Do not implement graph memory — document design questions only (v2.0).
- Do not implement the full memory router — design it in Phase 6, implement in Phase 7.
- Do not implement Pulse wiki health monitoring — that is v2.0.
- Do not build wiki-to-CRM linkage — that is v2.0.
- Do not implement multi-user wiki permissions — ATLAS is single-operator for v1.0.
- The lint pass is rule-based (heuristics + optional LLM call) — not a full knowledge-graph consistency checker.
- Keep sqlite-vec integration optional and gracefully degraded — do not block the phase on sqlite-vec availability.
- Do not use a cloud vector DB — local only (sqlite-vec or FTS5 fallback).
