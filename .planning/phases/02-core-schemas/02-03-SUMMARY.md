---
phase: 02-core-schemas
plan: "03"
subsystem: atlas-core
tags: [sqlite, migration, ddl, fts5, pytest, schema-02]
dependency_graph:
  requires:
    - 02-02 (core.py models written — column names derived from model_fields)
  provides:
    - infra/migrations/0001_core.sql
    - packages/atlas-core/tests/test_migration.py
  affects:
    - 04+ (INSERT statements use column names from this DDL)
    - Phase 6 (FTS5 trigger stubs prevent second migration pass)
tech_stack:
  added: []
  patterns:
    - "PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; as first two statements"
    - "CREATE TABLE IF NOT EXISTS with FK REFERENCES in dependency order"
    - "CREATE VIRTUAL TABLE wiki_fts USING fts5(title, body, content=wiki_pages, content_rowid=rowid)"
    - "FTS5 content-table triggers (INSERT/UPDATE/DELETE) for index maintenance"
    - "PRAGMA table_info() + model_fields.keys() set equality for drift detection"
key_files:
  created:
    - infra/migrations/0001_core.sql
    - packages/atlas-core/tests/test_migration.py
  modified: []
decisions:
  - "WAL mode test accepts 'wal' or 'memory' — WAL unsupported on :memory: SQLite in all versions"
  - "MIGRATION_PATH derived from __file__ in test module (not imported from conftest — conftest is not a module)"
  - "bool fields (policy_allowed, requires_approval) stored as INTEGER per SQLite type affinity mapping"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-05T00:00:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 02 Plan 03: SQLite Migration + Tests — Summary

**One-liner:** 0001_core.sql DDL for 7 tables + FTS5 virtual table + trigger stubs mirroring Pydantic model_fields 1:1 (D-012), validated by 19 SCHEMA-02 pytest tests; full suite 33 passed.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write infra/migrations/0001_core.sql | e3d0da8 | infra/migrations/0001_core.sql |
| 2 | Write test_migration.py covering SCHEMA-02 | 06d07be | packages/atlas-core/tests/test_migration.py |

## What Was Built

**Task 1** wrote `infra/migrations/0001_core.sql`:
- First two statements: `PRAGMA journal_mode = WAL;` and `PRAGMA foreign_keys = ON;`.
- 7 `CREATE TABLE IF NOT EXISTS` in FK dependency order: missions → runs → audit_events / tool_calls → artifacts, sources → wiki_pages.
- Column names mirror Pydantic `model_fields` keys 1:1 per D-012. No extra columns, no indexes (Phase 4 scope).
- Type affinity: `str`/`datetime` fields → `TEXT`, `int` fields → `INTEGER`, `bool` fields (`policy_allowed`, `requires_approval`) → `INTEGER`.
- `CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(title, body, content=wiki_pages, content_rowid=rowid)`.
- Three FTS5 trigger stubs (`wiki_fts_insert`, `wiki_fts_update`, `wiki_fts_delete`) with `-- TODO Phase 6` comment.

**Task 2** wrote `packages/atlas-core/tests/test_migration.py`:
- 19 tests covering: apply (2), table presence (2), column counts (7), column name drift (4), FK enforcement (1), WAL mode (1), FTS5 trigger stubs (1), FTS5 search (1).
- `test_column_names_match_fields_*` uses exact set equality between `PRAGMA table_info` column names and `Model.model_fields.keys()`.
- `test_fk_enforcement` uses `pytest.raises(sqlite3.IntegrityError)` on orphan FK insert with FK ON.
- `test_wal_mode` accepts both `'wal'` and `'memory'` — `:memory:` databases do not support WAL in all SQLite builds.
- `test_insert_and_fts_search` inserts a wiki_page, calls `INSERT INTO wiki_fts(wiki_fts) VALUES('rebuild')`, then asserts MATCH returns a row.

## Verification Results

| Check | Result |
|-------|--------|
| `migration OK` smoke check (7 tables + wiki_fts on :memory:) | PASS |
| `pytest packages/atlas-core/tests/ -v` — 33 passed, 0 failed | PASS |
| 7 `CREATE TABLE IF NOT EXISTS` in migration file | PASS |
| `CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts` present | PASS |
| All 3 FTS5 trigger names present in sqlite_master | PASS |
| Column names for missions, runs, audit_events, wiki_pages match model_fields | PASS |
| FK enforcement: IntegrityError on bad mission_id | PASS |
| FTS5 MATCH search returns row after rebuild | PASS |

## Phase 2 Success Criteria

| Criterion | Verified by |
|-----------|-------------|
| core.py exists with 7 models | test_schemas.py (plan 02-02) |
| `from atlas_core.schemas.core import Mission` succeeds | test_import |
| `Mission.model_json_schema()` emits valid JSON Schema | test_json_schema_valid_mission |
| 0001_core.sql applies without error; 7 tables created | test_migration_applies + test_all_tables_created |
| FTS5 virtual table created | test_fts5_available |
| Column names match Pydantic field names 1:1 | test_column_names_match_fields_* (4 tables) |

## Deviations from Plan

**1. [Rule 3 - Blocking] `from conftest import MIGRATION_PATH` fails collection**
- **Found during:** Task 2 test run
- **Issue:** `conftest.py` is auto-loaded by pytest — it is not a regular importable module. Importing it directly causes `ModuleNotFoundError` at collection time.
- **Fix:** Derived `MIGRATION_PATH` independently in `test_migration.py` using identical `pathlib.Path(__file__).parent.parent.parent.parent / "infra/migrations/0001_core.sql"` expression.
- **Files modified:** `packages/atlas-core/tests/test_migration.py`
- **Commit:** 06d07be

## Known Stubs

None — migration is complete DDL. FTS5 trigger stubs are intentional (marked `TODO Phase 6`) and functional placeholders, not missing implementation.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes at external trust boundaries introduced beyond those already scoped in the plan's threat model.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| infra/migrations/0001_core.sql | FOUND |
| packages/atlas-core/tests/test_migration.py | FOUND |
| Commit e3d0da8 (Task 1) | FOUND |
| Commit 06d07be (Task 2) | FOUND |
| pytest 33 passed | VERIFIED |
