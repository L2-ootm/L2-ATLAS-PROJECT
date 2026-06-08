---
phase: 06-wiki-runtime
plan: "03"
subsystem: wiki-service
tags:
  - wiki
  - fts5
  - audit
  - tdd
  - provenance
dependency_graph:
  requires:
    - "06-01"  # schema + 0002 migration
    - "06-02"  # atlas-wiki package scaffold
  provides:
    - "wiki_service.ingest_source"
    - "wiki_service.update_wiki_page"
    - "wiki_service.search_wiki"
    - "wiki_service.semantic_search"
    - "wiki_service.lint"
    - "provenance_service.write_provenance"
    - "provenance_service.get_provenance"
  affects:
    - "06-04"  # provenance_service full impl was partially delivered here
    - "06-05"  # wiki CLI thin wrappers over these functions
tech_stack:
  added:
    - "pytest-cov (coverage reporting)"
  patterns:
    - "TDD RED/GREEN cycle"
    - "Pydantic-first write guard (Source, WikiPage before any SQL)"
    - "Emit-after-lock (audit event emitted after with lock: block exits)"
    - "FTS5 rowid JOIN to wiki_pages (content table constraint)"
    - "Lazy optional imports (sqlite_vec, fastembed inside try/except)"
    - "Path traversal guard (pathlib.Path.resolve().is_file())"
key_files:
  created:
    - "services/wiki-runtime/tests/conftest.py"
    - "services/wiki-runtime/tests/test_wiki_service.py"
  modified:
    - "services/wiki-runtime/atlas_wiki/wiki_service.py"
    - "services/wiki-runtime/atlas_wiki/provenance_service.py"
decisions:
  - "provenance_service.write_provenance implemented in 06-03 (not deferred to 06-04) — required by update_wiki_page to avoid NotImplementedError at GREEN phase"
  - "Test suite extended from 12 to 16 tests to reach >=80% branch coverage"
  - "get_provenance implemented alongside write_provenance for completeness"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-08"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 2
requirements:
  - WIKI-01
  - WIKI-02
  - WIKI-03
  - WIKI-04
  - WIKI-05
  - AUDIT-03
---

# Phase 6 Plan 03: Wiki Service Implementation Summary

**One-liner:** Wiki service core implemented via TDD — ingest_source with SHA-256 dedup, FTS5 search with rowid JOIN, lint rules (empty_body, untrusted_only, stale_date, cross_page_contradiction), and provenance tracking via emit-after-lock pattern.

## What Was Built

### Task 1: RED — conftest.py + test_wiki_service.py

`services/wiki-runtime/tests/conftest.py`:
- `db` fixture: in-memory SQLite with both 0001 and 0002 migrations applied sequentially
- `run_id` fixture: inserts missions + runs rows for FK-safe audit event and wiki operations
- `lock` fixture: `threading.Lock()` for concurrency control
- `wiki_dir` fixture: `tmp_path/raw/`, `index.md`, `log.md` stubs

`services/wiki-runtime/tests/test_wiki_service.py`:
- 16 test functions (12 required + 4 boundary coverage tests)
- Covers all WIKI-01..05 + AUDIT-03 behaviors
- RED commit `40c466e`: all 12 initial tests fail with NotImplementedError as expected

### Task 2: GREEN — wiki_service.py + provenance_service.py

`services/wiki-runtime/atlas_wiki/wiki_service.py`:
- `ingest_source`: path traversal guard, SHA-256 dedup (preserves ID on re-ingest), emit-after-lock wiki_update event
- `update_wiki_page`: slug normalization, upsert with version increment, emit-after-lock, provenance write, index + log update
- `search_wiki`: FTS5 rowid JOIN (never SELECT from wiki_fts alone), parameterized query
- `semantic_search`: lazy sqlite_vec + fastembed imports inside try/except; FTS5 fallback when absent
- `lint`: four rules — empty_body, untrusted_only, stale_date, cross_page_contradiction
- `_update_index`: rewrites index.md from DB state
- `_append_log`: appends to log.md in "a" mode

`services/wiki-runtime/atlas_wiki/provenance_service.py`:
- `write_provenance`: Pydantic-first construction, lock-guarded INSERT into memory_provenance
- `get_provenance`: returns all MemoryProvenance records for an item_id

GREEN commit `4a7ce5e`: all 16 tests pass, 84% total coverage (82% wiki_service.py).

## Test Results

```
16 passed
atlas_wiki/wiki_service.py: 82% branch coverage
atlas_wiki/provenance_service.py: 100% coverage
TOTAL: 84%
```

## Verification Checks

- No top-level `sqlite_vec`/`fastembed` imports (T-06-SC): confirmed
- Emit-after-lock: both emit() calls are outside `with lock:` blocks (T-06-08): confirmed
- FTS5 rowid JOIN pattern present (T-06-06): confirmed
- Path traversal guard in ingest_source (T-06-05): ValueError raised for non-file paths

## Deviations from Plan

### Auto-added: provenance_service fully implemented (Rule 2)

**Found during:** Task 2 GREEN phase

**Issue:** `update_wiki_page` calls `provenance_service.write_provenance(...)`, which raised `NotImplementedError` (stub from 06-02). The plan expected write_provenance to remain a stub until 06-04, but that would have blocked all tests from passing.

**Fix:** Implemented both `write_provenance` and `get_provenance` in `provenance_service.py` as part of this plan.

**Files modified:** `services/wiki-runtime/atlas_wiki/provenance_service.py`

**Commit:** `4a7ce5e`

### Extended test count: 12 → 16 (Rule 2 — coverage gate)

**Found during:** Task 2 coverage measurement

**Issue:** 12 tests yielded 74% coverage — below the 80% threshold specified in the plan's success criteria.

**Fix:** Added 4 boundary tests: `test_ingest_source_invalid_path`, `test_lint_untrusted_only`, `test_lint_stale_date`, `test_provenance_get`.

**Coverage result:** 84% total (82% wiki_service.py, 100% provenance_service.py).

## Known Stubs

None — all public functions are fully implemented with non-stub bodies. The semantic search full path (sqlite_vec + fastembed available) is unreachable in the test environment because these optional dependencies are not installed, but the fallback path is fully tested.

## Threat Flags

None — all T-06-05 through T-06-SC mitigations from the plan's threat model are implemented and verified.

## Self-Check: PASSED

- `services/wiki-runtime/tests/conftest.py`: EXISTS
- `services/wiki-runtime/tests/test_wiki_service.py`: EXISTS
- `services/wiki-runtime/atlas_wiki/wiki_service.py`: EXISTS (min_lines=150, actual ~170)
- `services/wiki-runtime/atlas_wiki/provenance_service.py`: EXISTS
- Commits `40c466e` (RED) and `4a7ce5e` (GREEN): VERIFIED in git log
- All 16 tests pass: VERIFIED
- Coverage >= 80%: VERIFIED (84% total)
