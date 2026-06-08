---
phase: 06-wiki-runtime
plan: 01
subsystem: atlas-core/schemas + infra/migrations
tags: [schema, migration, pydantic, sqlite, D-012, D-019, wiki]
dependency_graph:
  requires: []
  provides: [MemoryProvenance model, Source.untrusted field, Source.ingested_by_run_id field, 0002 migration]
  affects: [packages/atlas-core/atlas_core/schemas/core.py, infra/migrations/0002_wiki_provenance.sql]
tech_stack:
  added: []
  patterns: [Pydantic v2 frozen model, Literal type constraints, field_serializer ISO 8601, SQLite ALTER TABLE ADD COLUMN, CREATE INDEX]
key_files:
  created: [infra/migrations/0002_wiki_provenance.sql]
  modified: [packages/atlas-core/atlas_core/schemas/core.py]
decisions:
  - MemoryProvenance.sensitivity defaults to "internal" (not "public") per least-privilege principle
  - No WAL PRAGMA in 0002 — WAL set at connection open time, not migration time
metrics:
  duration: ~10 minutes
  completed: 2026-06-08
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 06 Plan 01: Extend Source model + add MemoryProvenance + 0002 migration Summary

**One-liner:** MemoryProvenance frozen Pydantic v2 model (D-019) with Literal layer/sensitivity types and ISO 8601 serializer, plus 0002 SQL migration wiring untrusted/ingested_by_run_id onto sources and creating the memory_provenance table.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend Source model and add MemoryProvenance to atlas_core/schemas/core.py | c763d51 | packages/atlas-core/atlas_core/schemas/core.py |
| 2 | Write infra/migrations/0002_wiki_provenance.sql | 528d73b | infra/migrations/0002_wiki_provenance.sql |

## What Was Built

**Task 1 — core.py changes:**
- `Source` model gains `untrusted: bool = False` and `ingested_by_run_id: Optional[str] = None` fields — backward-compatible; all existing `Source(...)` calls continue to work.
- `MemoryProvenance` class added with `frozen=True`, `str_strip_whitespace=True`, 10 fields matching D-019 specification:
  - `layer: Literal["WIKI", "PROFILE", "GRAPH", "SKILL", "AUDIT"]`
  - `sensitivity: Literal["public", "internal", "private", "restricted"] = "internal"`
  - `written_at` serialized to ISO 8601 string via `@field_serializer`
- `"MemoryProvenance"` added to `__all__`.

**Task 2 — 0002_wiki_provenance.sql:**
- `ALTER TABLE sources ADD COLUMN untrusted INTEGER NOT NULL DEFAULT 0`
- `ALTER TABLE sources ADD COLUMN ingested_by_run_id TEXT`
- `CREATE TABLE IF NOT EXISTS memory_provenance` with 10 columns matching `MemoryProvenance.model_dump()` keys 1:1 (D-012 schema-as-source-of-truth)
- `REFERENCES sources(id)` and `REFERENCES audit_events(id)` FKs enforced
- Two indexes: `idx_memory_provenance_item` and `idx_memory_provenance_run`
- No FTS5 trigger DDL — already wired in 0001_core.sql

## Verification Results

```
Schema OK
Migration OK — columns: ['audit_event_id', 'id', 'item_id', 'layer', 'operator_id', 'run_id', 'sensitivity', 'source_id', 'untrusted', 'written_at']
Pytest: 33 passed
```

All 5 success criteria passed:
1. `from atlas_core.schemas.core import MemoryProvenance` — OK
2. `MemoryProvenance(layer="WIKI", item_id="test").model_dump()["written_at"]` returns ISO 8601 string — OK
3. `Source(path="f", sha256="a"*64, size_bytes=1).untrusted` returns `False` — OK
4. 0001 + 0002 applied to `:memory:` produces correct columns — OK
5. All 33 existing atlas-core tests pass — OK

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — no stub values or placeholder data introduced.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or trust-boundary schema changes beyond what the plan's threat model covers.

## Self-Check: PASSED

- `packages/atlas-core/atlas_core/schemas/core.py` — exists and verified
- `infra/migrations/0002_wiki_provenance.sql` — exists and verified
- Commit c763d51 — exists
- Commit 528d73b — exists
