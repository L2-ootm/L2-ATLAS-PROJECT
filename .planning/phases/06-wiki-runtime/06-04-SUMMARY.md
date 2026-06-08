---
phase: 06-wiki-runtime
plan: "04"
subsystem: wiki-service
tags:
  - wiki
  - provenance
  - tdd
  - coverage
dependency_graph:
  requires:
    - "06-01"  # MemoryProvenance schema + 0002 migration
    - "06-02"  # atlas-wiki package scaffold
    - "06-03"  # provenance_service.py already implemented as deviation
  provides:
    - "test_provenance_service (4 tests)"
  affects:
    - "06-05"  # wiki CLI can rely on provenance service as fully tested
tech_stack:
  added: []
  patterns:
    - "Pydantic-first validation before SQL (write_provenance)"
    - "dict(zip(cols, row)) read-back pattern"
    - "pytest.raises(pydantic.ValidationError) for invalid Literal"
key_files:
  created:
    - "services/wiki-runtime/tests/test_provenance_service.py"
  modified: []
decisions:
  - "06-04 scope reduced to test authoring only — provenance_service.py was fully implemented as a Rule 2 deviation in 06-03 (required by update_wiki_page at GREEN phase)"
  - "Coverage measured at provenance_service.py level (100%) and full suite level (84%); plan's >=80% branch coverage requirement satisfied on both axes"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-08"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
requirements:
  - WIKI-02
  - WIKI-05
  - AUDIT-03
---

# Phase 6 Plan 04: Provenance Service Tests Summary

**One-liner:** Dedicated test_provenance_service.py with 4 focused tests covering write/read field fidelity and Pydantic-first invalid-layer validation, achieving 100% branch coverage on provenance_service.py.

## What Was Built

### Implementation state at plan start

`services/wiki-runtime/atlas_wiki/provenance_service.py` was already fully implemented as a Rule 2 deviation in plan 06-03 (write_provenance and get_provenance both complete, 100% coverage from wiki_service test suite). No implementation work remained.

### Task 1: test_provenance_service.py

`services/wiki-runtime/tests/test_provenance_service.py` (79 lines):

- `test_write_provenance_creates_row`: calls `write_provenance`, verifies return is `MemoryProvenance`, verifies exactly 1 DB row with correct `item_id`.
- `test_write_provenance_fields`: passes `run_id` fixture, reads back `layer`/`item_id`/`run_id` from DB directly, asserts field fidelity.
- `test_get_provenance_returns_records`: calls `get_provenance`, asserts `list[MemoryProvenance]` length 1 with correct `item_id`, `layer`, `sensitivity`.
- `test_write_provenance_invalid_layer`: asserts `pydantic.ValidationError` raised before any SQL for `layer="INVALID"`, verifies DB row count remains 0.

All 4 tests use the `db` and `lock` fixtures from `conftest.py` (created in 06-03).

## Test Results

```
20 passed (16 test_wiki_service + 4 test_provenance_service)
atlas_wiki/provenance_service.py: 100% coverage (22 stmts, 2 branches)
atlas_wiki/wiki_service.py:        82% coverage
TOTAL: 84%
Required coverage of 80% reached.
```

## Deviations from Plan

### Scope reduction: implementation already complete (prior plan deviation)

**Context:** Plan 06-04 specified implementing `provenance_service.py` from NotImplementedError stubs. Per 06-03 SUMMARY, both functions were implemented there as a Rule 2 deviation (required to make wiki_service tests GREEN).

**Action:** Verified the existing implementation satisfies all must_haves from this plan's frontmatter, then focused solely on creating the dedicated test file.

**No code deviations in this plan.** The test file matches the 4-function spec exactly.

## Known Stubs

None.

## Threat Flags

None — T-06-10 (invalid layer bypassing Pydantic) is confirmed mitigated: `test_write_provenance_invalid_layer` verifies `pydantic.ValidationError` fires before any SQL and leaves zero DB rows.

## Self-Check: PASSED

- `services/wiki-runtime/tests/test_provenance_service.py`: EXISTS (79 lines)
- Commit `f379ec9` (feat(06-04)): VERIFIED in git log
- All 4 tests pass: VERIFIED
- provenance_service.py branch coverage >= 80%: VERIFIED (100%)
- Full suite coverage >= 80%: VERIFIED (84%)
