---
phase: 05-mission-run-lifecycle
plan: "02"
subsystem: agent-runtime
tags: [mission-service, run-service, state-machine, emit-after-lock, pydantic-first, tdd]
requires:
  - phase-04-audit-core
  - 05-01 (Wave 0 stubs)
provides:
  - atlas_runtime.mission_service (create_mission, get_mission, list_missions — fully implemented)
  - atlas_runtime.run_service (start_run, complete_run, fail_run, cancel_run — fully implemented)
affects:
  - 05-03-PLAN (policy service tests depend on run_service.start_run working)
  - 05-04-PLAN (CLI tests depend on mission/run services)
tech-stack:
  added: []
  patterns:
    - emit-after-lock (deadlock prevention — emit() called strictly outside with-lock blocks)
    - pydantic-first-write-guard (Mission/Run model constructed before any SQL INSERT)
    - dual-table-atomic-update (runs+missions updated in same with conn: block)
    - lock-conn-injection (conn+lock injected into all service functions)
key-files:
  created: []
  modified:
    - services/agent-runtime/atlas_runtime/mission_service.py
    - services/agent-runtime/atlas_runtime/run_service.py
    - services/agent-runtime/tests/test_mission_service.py
    - services/agent-runtime/tests/test_run_service.py
decisions:
  - "mission_service.create_mission does not call emit() — no run_id exists at create time (RESEARCH.md A2)"
  - "cancel_run uses status='cancelled' matching Run.status Literal — not 'failed'"
  - "start_run wires atlas_audit.set_connection + on_session_start after lock released (D-001 Hermes integration)"
  - "emit() for all transitions uses event_type='tool_call' with data.transition field"
  - "subagent test remains xfail — dispatch_subagent stub not implemented until Plan 03"
metrics:
  duration: "8m"
  completed: "2026-06-08"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 4
---

# Phase 05 Plan 02: Mission & Run Service Implementation Summary

**One-liner:** Full mission CRUD and run lifecycle state machine with Pydantic-first write guard, dual-table atomic updates, and emit-after-lock deadlock prevention.

---

## What Was Built

Wave 1 implementation for the Phase 5 mission/run lifecycle. Replaced all `NotImplementedError` stubs with production-ready service functions. Both modules enforce the critical design constraints from CONTEXT.md and PATTERNS.md.

**mission_service.py (3 functions):**
- `create_mission(conn, lock, *, title, intent, project)` — constructs `Mission` Pydantic model before any SQL, inserts row with parameterized `:param` style query inside `with lock: with conn:` block, returns the model. No `emit()` call (no run_id exists at create time).
- `get_mission(conn, mission_id)` — parameterized `SELECT` by id, reconstructs via `Mission(**dict(zip(cols, row)))`, returns `None` if missing.
- `list_missions(conn)` — `SELECT ... ORDER BY created_at ASC`, reconstructs each row as `Mission`, returns `list[Mission]`.

**run_service.py (4 functions):**
- `start_run(conn, lock, *, mission_id, session_id)` — validates mission exists and is `"pending"` (raises `ValueError` otherwise); constructs `Run` model; atomically INSERTs run row and UPDATEs mission to `"running"` in single `with lock: with conn:` block; wires `atlas_audit.set_connection(conn)` and `atlas_audit.on_session_start(...)` after lock released; calls `emit()` with `event_type="tool_call"`, `data={"transition": "started"}` after lock; returns `Run`.
- `complete_run(conn, lock, *, run_id, mission_id, status, summary)` — validates run exists and is `"running"`; atomically updates both `runs` and `missions` tables to terminal status in single `with lock: with conn:` block; calls `emit()` after lock.
- `fail_run(conn, lock, *, run_id, mission_id, summary)` — thin wrapper calling `complete_run(..., status="failed")`.
- `cancel_run(conn, lock, *, run_id, mission_id)` — validates run is `"running"`; atomically updates both tables to `"cancelled"` with `finished_at` timestamp; calls `emit()` after lock; existing `audit_events` rows are never deleted.

---

## Test Results

```
14 tests collected
13 passed
1 xfailed (test_dispatch_subagent_emits_subagent_run — Plan 03 pending)
0 failed
0 errors

Breakdown:
  test_mission_service.py: 5 passed
  test_run_service.py: 8 passed, 1 xfailed
```

---

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1: mission_service + tests | 72b5bc0 | feat(05-02): implement mission_service create/get/list with Pydantic-first write guard |
| Task 2: run_service + tests | d5fe735 | feat(05-02): implement run_service state machine with emit-after-lock pattern |

---

## Deviations from Plan

None — plan executed exactly as written. All critical design constraints honored:
- Emit-after-lock pattern enforced in all 3 state-transition functions (`start_run`, `complete_run`, `cancel_run`)
- Pydantic-first write guard in `create_mission` and `start_run`
- Dual-table atomic updates in `complete_run` and `cancel_run`
- `cancel_run` uses `"cancelled"` (not `"failed"`) matching `Run.status` Literal
- No f-string SQL anywhere in either service module
- `mission_service` has zero `emit()` calls (verified: `grep -c "emit(" mission_service.py == 0`)

---

## Known Stubs

No new stubs introduced. The following pre-existing stubs from Wave 0 remain (not in scope for this plan):

| Stub | File | Resolved by |
|------|------|-------------|
| `check_workspace_boundary`, `check_workspace_boundary_and_emit`, `check_tool_allowed` | policy.py | 05-03-PLAN |
| `dispatch_subagent` | subagent_service.py | 05-03-PLAN |
| CLI `create/run/cancel` (call stubs) | cli/main.py | 05-03/05-04-PLAN |

---

## Threat Surface Scan

No new trust boundaries introduced beyond what the plan's `<threat_model>` documented:
- T-05-01: SQL injection via title/intent — mitigated by parameterized `:param` INSERT and `model_dump()` dict (no f-string SQL)
- T-05-04: State machine bypass — mitigated by status validation before every transition (raises `ValueError` on wrong state)
- T-05-05: Dual-table atomicity — mitigated by both UPDATE statements inside same `with lock: with conn:` block

No unplanned threat flags introduced.

---

## Self-Check: PASSED

- `mission_service.py` exists and has 0 `emit()` calls, 0 f-string SQL
- `run_service.py` exists; all `emit()` calls appear outside `with lock:` blocks
- Commit `72b5bc0` exists in git log (Task 1)
- Commit `d5fe735` exists in git log (Task 2)
- 13 tests passed, 1 xfailed, 0 errors (verified via `rtk proxy python -m pytest`)
