---
phase: 04-event-bus
plan: "02"
subsystem: agent-runtime
tags: [audit, service, sqlite, pydantic, redaction, jsonl, tdd]
dependency_graph:
  requires:
    - 04-01 (package scaffold: atlas_runtime importable, db/run_id/lock fixtures)
  provides:
    - atlas_runtime.audit_service: emit(), get_events_for_run(), export_jsonl()
    - Full audit write boundary with Pydantic validation + secret redaction + transactional writes
    - 7 passing unit tests covering RUNTIME-03, AUDIT-01, AUDIT-02
  affects:
    - services/agent-runtime/tests/conftest.py (run_id fixture upgraded to seed FK rows)
    - services/agent-runtime/atlas_runtime/audit_service.py (new module)
    - services/agent-runtime/tests/test_audit_service.py (stubs replaced with full tests)
tech_stack:
  added: []
  patterns:
    - "_redact() applies SECRET_PATTERNS (URL querystring + JSON key-value + Bearer) before model construction"
    - "AuditEvent() constructed before INSERT — Pydantic Literal[...] validates event_type (HB-04-02 enforcement)"
    - "with lock: with conn: — threading.Lock + sqlite3 CM for atomic transactional writes"
    - "model_dump() dict passed to named-parameter INSERT — no string interpolation (T-04-02-T3)"
    - "Dependency injection: conn and lock always injected by callers, no global state"
    - "Re-validation on read: get_events_for_run() constructs AuditEvent(**row_dict) from SELECT"
key_files:
  created:
    - services/agent-runtime/atlas_runtime/audit_service.py
  modified:
    - services/agent-runtime/tests/test_audit_service.py
    - services/agent-runtime/tests/conftest.py
decisions:
  - "run_id fixture seeds mission+run rows for FK satisfaction: PRAGMA foreign_keys=ON blocks bare UUID INSERTs without parent rows in missions and runs tables"
  - "conftest.py deviation (Rule 2): run_id_fixture upgraded from pure UUID generator to FK-seeding fixture — required for correctness, not a test design change"
  - "ToolCall args/result None handling: missing 'args' key defaults to '{}', missing 'result' key defaults to None (ToolCall.result is Optional[str])"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-07"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
---

# Phase 04 Plan 02: Audit Service Implementation Summary

**One-liner:** atlas_runtime/audit_service.py with emit() + get_events_for_run() + export_jsonl() — Pydantic validation, SECRET_PATTERNS redaction, and transactional SQLite writes; 7 tests green.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Implement atlas_runtime/audit_service.py | 4311108 | atlas_runtime/audit_service.py |
| 2 | Full test suite in test_audit_service.py (replace stubs) | 2ee3221 | tests/test_audit_service.py, tests/conftest.py |

## Verification Results

```
pytest services/agent-runtime/tests/test_audit_service.py -v
7 passed — EXIT 0

pytest services/agent-runtime/tests/ -x -q
10 passed — EXIT 0

python -c "from atlas_runtime.audit_service import emit, get_events_for_run, export_jsonl; print('OK')"
OK

INSERT INTO audit_events count in audit_service.py: 1 (single call in emit())
AuditEvent() constructions in audit_service.py: 5 (emit x1, get_events_for_run x1, export_jsonl x1, plus docstring comments)
git diff HEAD -- _EXTERNAL_REPOS/hermes-agent/hermes_cli/cli.py: (empty — no changes)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] conftest.py run_id fixture seeded with FK parent rows**

- **Found during:** Task 1 verification — emit() raised `FOREIGN KEY constraint failed` when attempting INSERT into audit_events with a bare UUID run_id not present in the runs table.
- **Issue:** The DB fixture has `PRAGMA foreign_keys = ON` and the DDL declares `audit_events.run_id REFERENCES runs(id)`. The original `run_id_fixture` returned a raw `str(uuid.uuid4())` with no parent mission or run row. Any emit() call with FK enforcement active fails before writing.
- **Fix:** Updated `run_id_fixture(db)` to accept the `db` fixture and insert a minimal mission row + run row before returning the run_id. The fixture now acts as proper test scaffolding for FK-constrained audit writes.
- **Files modified:** services/agent-runtime/tests/conftest.py
- **Commit:** 2ee3221

## HB Compliance

| Hard Blocker | Status | Verification |
|---|---|---|
| HB-04-01: Secret redaction (JSON key-value pattern) | SATISFIED | `test_emit_redacts_secret_in_data` passes: `{"token": "sk-abc123"}` → `[REDACTED]` in stored data column |
| HB-04-02: All SQLite writes through Pydantic model layer | SATISFIED | Structural: `AuditEvent()` constructed before every `INSERT INTO audit_events`; `ToolCall()` constructed before every `INSERT INTO tool_calls`. `grep -c "INSERT INTO audit_events"` returns 1 (single call in `emit()`). |

## D-001 Check

```
git diff HEAD -- _EXTERNAL_REPOS/hermes-agent/hermes_cli/cli.py
git diff HEAD -- _EXTERNAL_REPOS/hermes-agent/hermes_cli/run_agent.py
(both empty — no changes to Hermes core files)
```

## Known Stubs

None — all three public functions are fully implemented. Wave 2 (04-03) consumes `emit()` from hook callbacks.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. The `audit_service.py` module is a pure in-process service layer — it receives an injected `sqlite3.Connection` and `threading.Lock`, writes via parameterized SQL only, and performs no I/O beyond SQLite. All STRIDE threats in the plan's threat model are mitigated as designed.

## Self-Check: PASSED

Files exist:
- FOUND: services/agent-runtime/atlas_runtime/audit_service.py
- FOUND: services/agent-runtime/tests/test_audit_service.py
- FOUND: services/agent-runtime/tests/conftest.py

Commits exist:
- FOUND: 4311108 (Task 1 — audit_service.py)
- FOUND: 2ee3221 (Task 2 — test suite + conftest FK fix)

pytest exit code: 0
7 PASSED in test_audit_service.py
10 PASSED in full services/agent-runtime/tests/ suite
