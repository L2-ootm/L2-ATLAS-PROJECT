# Phase 6: LLM Wiki Runtime

**Phase number:** 6
**Name:** LLM Wiki Runtime
**Status:** Pending

---

## Goal

Implement the wiki ingest, update, query, and lint pipeline — the compounding knowledge layer that persists valuable agent output across runs.

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

1. `atlas wiki ingest <path>` copies the file to `wiki/raw/`, computes SHA-256, creates a Source row, and emits an AuditEvent of kind `wiki_update`.
2. `atlas wiki update <slug> --body "..."` upserts a WikiPage row, appends to wiki/log.md, and updates wiki/index.md.
3. `atlas wiki search "query"` returns ranked results via FTS5 full-text search.
4. `atlas wiki semantic "query"` returns results via sqlite-vec vector search (or prints a clear "sqlite-vec not loaded" message if the extension is absent).
5. `atlas wiki lint` reports at least one stale/contradicted claim on a wiki page deliberately seeded with a contradiction.
6. wiki/index.md has an entry for every WikiPage row in the database; wiki/log.md has an entry for every wiki_update AuditEvent.
7. Service layer unit tests cover ingest, update, search, and lint paths (≥ 80% branch coverage on wiki_service.py).

---

## Key Decisions Applicable

- **D-004** (locked): LLM Wiki is first-class runtime — raw sources are immutable; wiki pages are agent-maintained; RAG supplements but does not replace structured wiki pages.
- **D-002** (locked): Audit-first — every wiki operation (ingest, update, lint) emits an AuditEvent via the Phase 4 event bus.
- **D-003** (locked): SQLite/WAL/FTS5/sqlite-vec is the datastore — FTS5 for text search, sqlite-vec for semantic search. If sqlite-vec is not available as a loadable extension, degrade gracefully with a clear error message.
- **D-011** (locked): Canonical repo layout — wiki service at `services/wiki-runtime/`; wiki markdown files at `wiki/`.
- Architecture rule: Layer (1) raw sources are immutable; layer (2) compiled wiki/memory is agent-maintained. Do not allow agents to modify raw source files.

---

## What NOT to Build

- Do not build the REST API for wiki endpoints — that is Phase 7.
- Do not build the cockpit wiki browser UI — that is Phase 8.
- Do not implement Pulse wiki health monitoring — that is v2.0.
- Do not build wiki-to-CRM linkage — that is v2.0.
- Do not implement multi-user wiki permissions — ATLAS is single-operator for v1.0.
- The lint pass should be rule-based (contradiction detection via simple heuristics or LLM call) — do not build a full knowledge-graph consistency checker.
- Keep sqlite-vec integration optional and gracefully degraded — do not block the phase on sqlite-vec availability.
