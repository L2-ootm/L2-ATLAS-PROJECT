# Phase 02 Verification Report

**Phase:** 02 — Core Domain Schemas & SQLite Migration
**Date:** 2026-06-05
**Verdict:** PASS

## Success Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `core.py` exists with 7 models | PASS | `packages/atlas-core/atlas_core/schemas/core.py` — 231 lines. All 7 classes present: Mission, Run, AuditEvent, ToolCall, Artifact, Source, WikiPage. `__all__` enumerates all 7 plus `SECRET_PATTERNS`. |
| `from atlas_core.schemas.core import Mission` succeeds | PASS | `test_import` and `test_all_models_importable` both pass in Python 3.11.15. `schemas/__init__.py` re-exports all 7 models via package-level `__all__`. |
| `Mission.model_json_schema()` emits valid JSON Schema | PASS | `test_json_schema_valid_mission`, `test_json_schema_all_fields_present` (exact set: `{id, title, intent, status, project, created_at, updated_at}`), `test_json_schema_status_enum`, and `test_json_schema_all_models` all pass. All 7 models return `dict` with `properties` key. |
| `0001_core.sql` applies on fresh `:memory:` DB; 7 tables created | PASS | `test_migration_applies` and `test_all_tables_created` pass. Tables: missions, runs, audit_events, tool_calls, artifacts, sources, wiki_pages. Column counts verified per-table (7, 7, 11, 13, 8, 7, 8). |
| FTS5 virtual table created | PASS | `test_fts5_available` passes — `wiki_fts` row present in `sqlite_master`. `test_insert_and_fts_search` passes — insert + rebuild + `MATCH` returns 1+ rows. All 3 FTS5 trigger stubs present (`wiki_fts_insert`, `wiki_fts_update`, `wiki_fts_delete`). |
| Column names match Pydantic field names 1:1 | PASS | Tests cover Mission, Run, AuditEvent, WikiPage directly. Manual probe on untested models confirmed: ToolCall (13 cols), Artifact (8 cols), Source (7 cols) — all DDL column sets equal `model_fields.keys()` with no drift. |

## Requirements Coverage

| REQ-ID | Status | Notes |
|--------|--------|-------|
| SCHEMA-01 | PASS | All 7 Pydantic v2 models present with correct fields, enums, and FK relationships. All models use `ConfigDict(frozen=True)`. All datetime fields have `@field_serializer` returning ISO 8601 strings. No `dict[str, Any]` in public fields — `data`, `args`, `result` are typed `str`. No `pathlib.Path` in public fields — `path` is `str`. Mutation attempt raises `ValidationError` (test_frozen_model passes). |
| SCHEMA-02 | PASS | Migration applies without error on `:memory:` DB. `PRAGMA journal_mode=WAL` present (accepted as 'memory' on `:memory:` per test). `PRAGMA foreign_keys=ON` present; FK enforcement verified on `runs.mission_id → missions.id`. FTS5 virtual table and 3 trigger stubs created. All 7 tables created. |
| SCHEMA-03 | PASS | `model_json_schema()` returns valid dicts with `properties` for all 7 models. Mission fields match the expected 7-field set exactly. Status enum exposes `pending`. JSON Schema is the D-012 bridge to TS/Rust consumers. |

## Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Users\Davi\Desktop\Projects\L2-ATLAS-PROJECT\packages\atlas-core
configfile: pyproject.toml
collected 33 items

packages\atlas-core\tests\test_migration.py::test_migration_applies PASSED
packages\atlas-core\tests\test_migration.py::test_migration_file_exists PASSED
packages\atlas-core\tests\test_migration.py::test_all_tables_created PASSED
packages\atlas-core\tests\test_migration.py::test_fts5_available PASSED
packages\atlas-core\tests\test_migration.py::test_missions_column_count PASSED
packages\atlas-core\tests\test_migration.py::test_runs_column_count PASSED
packages\atlas-core\tests\test_migration.py::test_audit_events_column_count PASSED
packages\atlas-core\tests\test_migration.py::test_tool_calls_column_count PASSED
packages\atlas-core\tests\test_migration.py::test_artifacts_column_count PASSED
packages\atlas-core\tests\test_migration.py::test_sources_column_count PASSED
packages\atlas-core\tests\test_migration.py::test_wiki_pages_column_count PASSED
packages\atlas-core\tests\test_migration.py::test_column_names_match_fields_mission PASSED
packages\atlas-core\tests\test_migration.py::test_column_names_match_fields_run PASSED
packages\atlas-core\tests\test_migration.py::test_column_names_match_fields_audit_event PASSED
packages\atlas-core\tests\test_migration.py::test_column_names_match_fields_wiki_page PASSED
packages\atlas-core\tests\test_migration.py::test_fk_enforcement PASSED
packages\atlas-core\tests\test_migration.py::test_wal_mode PASSED
packages\atlas-core\tests\test_migration.py::test_fts5_triggers_present PASSED
packages\atlas-core\tests\test_migration.py::test_insert_and_fts_search PASSED
packages\atlas-core\tests\test_schemas.py::test_import PASSED
packages\atlas-core\tests\test_schemas.py::test_all_models_importable PASSED
packages\atlas-core\tests\test_schemas.py::test_model_instantiation_mission PASSED
packages\atlas-core\tests\test_schemas.py::test_model_instantiation_audit_event PASSED
packages\atlas-core\tests\test_schemas.py::test_serialization_no_datetime_objects PASSED
packages\atlas-core\tests\test_schemas.py::test_serialization_json_safe PASSED
packages\atlas-core\tests\test_schemas.py::test_serialization_no_dict_types PASSED
packages\atlas-core\tests\test_schemas.py::test_path_is_str PASSED
packages\atlas-core\tests\test_schemas.py::test_json_schema_valid_mission PASSED
packages\atlas-core\tests\test_schemas.py::test_json_schema_all_fields_present PASSED
packages\atlas-core\tests\test_schemas.py::test_json_schema_status_enum PASSED
packages\atlas-core\tests\test_schemas.py::test_json_schema_all_models PASSED
packages\atlas-core\tests\test_schemas.py::test_secret_patterns PASSED
packages\atlas-core\tests\test_schemas.py::test_frozen_model PASSED

============================= 33 passed in 0.15s ==============================
```

## Known Issues (from 02-REVIEW.md)

The following findings from the code review are acknowledged but deferred:

**[CRITICAL] — Deferred to Phase 4:** `SECRET_PATTERNS` (core.py:26) does not match JSON key-value notation (`"key": "value"`). Only URL-querystring-style `key=value` pairs are matched. Phase 4 is responsible for applying these patterns before writing `AuditEvent.data` and `ToolCall.args`/`result` to SQLite; that is the correct phase to fix coverage and add JSON-notation patterns. The patterns are structurally correct (2 compiled regexes in a tuple) and the SCHEMA-01 test passes against the current definition.

**[WARNING x5] — Deferred to Phase 4 or later:**
- Dead `None` branch in non-optional datetime serializers (copy-paste from `Run.finished_at`). Type noise only; no runtime impact.
- No JSON validity guard on `data`/`args` string fields. Phase 4 populates these fields and is the correct enforcement point.
- `sha256` fields accept arbitrary strings without a 64-char hex validator. Content-addressable integrity is a Phase 6 concern.
- `str_strip_whitespace=True` silently trims path strings. Documented behavior; no current consumer is affected.
- FK enforcement test structure is fragile (commit inside `raises` block). Functional today; refactor in next test sprint.

**[INFO x4] — Deferred to Phase 4 or later:**
- `MIGRATION_PATH` constant duplicated in `conftest.py` and `test_migration.py`.
- Column-name drift tests cover only 4 of 7 models (ToolCall, Artifact, Source are untested in-suite; manually verified in this report to be drift-free).
- FK enforcement tests cover only 1 of 6 FK relationships.
- `db_fixture` return type annotation is incorrect (suppressed with `# type: ignore[return]`).

None of these findings block the Phase 02 goal. The contract established by this phase — frozen Pydantic v2 models + matching SQLite DDL — is sound.

## Verdict

PASS — all 6 success criteria met, all 3 requirements satisfied, 33/33 tests pass.
