---
phase: 02-core-schemas
plan: "02"
subsystem: atlas-core
tags: [python-package, pydantic, schemas, frozen-models, field-serializer, pytest]
dependency_graph:
  requires:
    - 02-01 (installable atlas-core package in atlas-core venv)
  provides:
    - packages/atlas-core/atlas_core/schemas/core.py
    - packages/atlas-core/atlas_core/schemas/__init__.py (re-exports updated)
    - packages/atlas-core/tests/test_schemas.py
  affects:
    - 02-03 (test_migration.py will import models to check column-name alignment)
    - 04+ (all downstream phases import from atlas_core.schemas.core)
tech_stack:
  added: []
  patterns:
    - ConfigDict(frozen=True, str_strip_whitespace=True) on all 7 Pydantic v2 models
    - "@field_serializer on every datetime field — model_dump() returns ISO 8601 str"
    - str fields for JSON payloads (data/args/result) — no dict[str, Any] per D-013
    - str fields for paths — no pathlib.Path per D-013
    - SECRET_PATTERNS tuple at module level — Phase 4 applies redaction before AuditEvent.data write
key_files:
  created:
    - packages/atlas-core/atlas_core/schemas/core.py
    - packages/atlas-core/tests/test_schemas.py
  modified:
    - packages/atlas-core/atlas_core/schemas/__init__.py
decisions:
  - "Each model gets its own @field_serializer method — no shared serializer across models (pydantic v2 serializers are instance methods bound to their model)"
  - "test_json_schema_status_enum handles both inline 'enum' and 'anyOf' schema shapes to remain stable across pydantic v2 minor releases"
  - "test_frozen_model uses pytest.raises(Exception) — exact exception is ValidationError but catching Exception is acceptable since pydantic internals may vary"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-05T00:00:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 02 Plan 02: Core Domain Schemas — Summary

**One-liner:** 7 Pydantic v2 frozen models (Mission, Run, AuditEvent, ToolCall, Artifact, Source, WikiPage) with field_serializer datetime-to-ISO-8601, str-typed JSON payloads and paths, plus 14 passing SCHEMA-01/SCHEMA-03 tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write core.py with all 7 Pydantic v2 models | 3f8b59f | atlas_core/schemas/core.py, atlas_core/schemas/__init__.py |
| 2 | Write test_schemas.py covering SCHEMA-01 and SCHEMA-03 | 491a342 | tests/test_schemas.py |

## What Was Built

**Task 1** wrote `packages/atlas-core/atlas_core/schemas/core.py`:
- 7 models in declaration order: Mission, Run, AuditEvent, ToolCall, Artifact, Source, WikiPage.
- Every model: `model_config = ConfigDict(frozen=True, str_strip_whitespace=True)`.
- Every `datetime` field has `@field_serializer` returning `.isoformat()`, handling `Optional[datetime]` safely. `model_dump()` output is JSON-serializable without `default=str`.
- `AuditEvent.data` typed as `str = "{}"` (D-013 — no dict[str, Any]).
- `ToolCall.args` typed as `str = "{}"`, `result` as `Optional[str] = None` (D-013).
- `Artifact.path` and `Source.path` typed as `str` (D-013 — no pathlib.Path).
- `SECRET_PATTERNS` constant (2 compiled regex patterns) at module level, copied verbatim from `L2-Atlas/src/atlas_core/logging/jsonl_logger.py` per FOUND-04.
- `__all__` lists all 7 model names and `SECRET_PATTERNS`.
- Updated `atlas_core/schemas/__init__.py` with explicit re-exports and matching `__all__`.

**Task 2** wrote `packages/atlas-core/tests/test_schemas.py`:
- 14 tests covering: import (2), instantiation (2), serialization (4), JSON schema (4), SECRET_PATTERNS (1), frozen model (1).
- `test_json_schema_all_fields_present` asserts exact field set `{"id","title","intent","status","project","created_at","updated_at"}`.
- `test_json_schema_status_enum` handles both inline `enum` and `anyOf` schema shapes for pydantic version stability.
- All 14 tests pass: `pytest 9.0.3, Python 3.11.15`.

## Verification Results

| Check | Result |
|-------|--------|
| `from atlas_core.schemas.core import Mission; json.dumps(Mission(title='t').model_dump())` | PASS |
| `Mission.model_json_schema()['properties'].keys()` contains 7 canonical fields | PASS |
| `pytest packages/atlas-core/tests/test_schemas.py -v` exits 0, 14 passed | PASS |
| `grep dict[str, Any] core.py` returns 0 matches | PASS |
| `grep pathlib core.py` returns 0 matches | PASS |
| `ConfigDict(frozen=True` present in core.py (all 7 models) | PASS |
| `@field_serializer` present in core.py | PASS |
| `schemas/__init__.py` contains `from atlas_core.schemas.core import` | PASS |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all 7 models are fully implemented with all fields. `schemas/__init__.py` now exports all 7 models and `SECRET_PATTERNS`.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-02-04 mitigated | atlas_core/schemas/core.py | `SECRET_PATTERNS` constant declared; Phase 4 must apply redaction before populating `AuditEvent.data` |

No new threat surface introduced. T-02-06 (dict[str, Any] leakage) and T-02-07 (pathlib.Path leakage) confirmed mitigated by source grep and `test_serialization_no_dict_types` / `test_path_is_str` tests.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| packages/atlas-core/atlas_core/schemas/core.py | FOUND |
| packages/atlas-core/atlas_core/schemas/__init__.py | UPDATED |
| packages/atlas-core/tests/test_schemas.py | FOUND |
| Commit 3f8b59f (Task 1) | FOUND |
| Commit 491a342 (Task 2) | FOUND |
| pytest 14 passed | VERIFIED |
