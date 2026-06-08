---
phase: 05-mission-run-lifecycle
plan: "01"
subsystem: agent-runtime
tags: [scaffolding, stubs, wave-0, cli, mission-lifecycle]
requires: [phase-04-audit-core]
provides:
  - atlas_runtime.mission_service (create_mission, get_mission, list_missions stubs)
  - atlas_runtime.run_service (start_run, complete_run, fail_run, cancel_run stubs)
  - atlas_runtime.policy (PolicyDecision, check_workspace_boundary, check_workspace_boundary_and_emit, check_tool_allowed stubs)
  - atlas_runtime.subagent_service (dispatch_subagent stub)
  - atlas_runtime.cli.main (Typer app with mission create/run/cancel/status)
affects: [05-02-PLAN, 05-03-PLAN, 05-04-PLAN]
tech-stack:
  added: [typer>=0.25.0, pytest-cov>=7.0]
  patterns: [stub-xfail-tdd, lock-conn-injection, emit-after-lock, pydantic-first-write]
key-files:
  created:
    - services/agent-runtime/atlas_runtime/mission_service.py
    - services/agent-runtime/atlas_runtime/run_service.py
    - services/agent-runtime/atlas_runtime/policy.py
    - services/agent-runtime/atlas_runtime/subagent_service.py
    - services/agent-runtime/atlas_runtime/cli/__init__.py
    - services/agent-runtime/atlas_runtime/cli/main.py
    - services/agent-runtime/tests/test_mission_service.py
    - services/agent-runtime/tests/test_run_service.py
    - services/agent-runtime/tests/test_policy.py
    - services/agent-runtime/tests/test_cli.py
  modified:
    - services/agent-runtime/pyproject.toml
decisions:
  - "All service stubs raise NotImplementedError — Wave 1 executors implement against exact signatures"
  - "test_status_unknown_id_exits_one marked non-xfail (CLI status queries DB directly, no stub involved)"
  - "CLI cancel command queries runs table directly for mission_id + status='running'; no mission_service.cancel_mission stub needed"
metrics:
  duration: "5m"
  completed: "2026-06-08"
  tasks_completed: 2
  tasks_total: 2
  files_created: 10
  files_modified: 1
---

# Phase 05 Plan 01: Phase 5 Wave 0 Scaffolding Summary

**One-liner:** Stub service modules + xfail test skeletons establishing exact function signatures, import structure, and test contracts for Wave 1 Phase 5 implementation.

---

## What Was Built

Wave 0 scaffolding for the Phase 5 mission/run lifecycle. All 11 files created or modified establish the compilation baseline that Wave 1 executors implement against. No business logic — every service function stub raises `NotImplementedError("not implemented")`.

**Service modules (7 files):**
- `mission_service.py`: `create_mission`, `get_mission`, `list_missions` — D-002/D-003 audit-first CRUD stubs
- `run_service.py`: `start_run`, `complete_run`, `fail_run`, `cancel_run` — D-001/D-002 lifecycle state machine stubs
- `policy.py`: `PolicyDecision` dataclass, `check_workspace_boundary`, `check_workspace_boundary_and_emit`, `check_tool_allowed` — D-006/RUNTIME-07 cross-platform policy stubs
- `subagent_service.py`: `dispatch_subagent` — RUNTIME-06 governance stub (Phase 5 is stub-only; no real spawning)
- `cli/__init__.py`: package init with `__version__ = "0.1.0"`
- `cli/main.py`: Typer app with `mission create/run/cancel/status` subcommands; `_get_connection()` / `_get_lock()` injectable for tests

**Test files (4 files, 25 tests total):**
- `test_mission_service.py`: 5 xfail tests (create persists, returns model, get returns None, list empty, status pending)
- `test_run_service.py`: 9 xfail tests (start/complete/cancel lifecycle, subagent dispatch) + local `mission_id` fixture
- `test_policy.py`: parametrized workspace boundary (3 cases), tool allowlist (2 tests), boundary-emit test — 6 xfail total
- `test_cli.py`: 4 xfail stubs + 1 non-xfail test (status unknown ID — CLI queries DB directly, no stub)

**pyproject.toml additions:**
- `[project.scripts]` atlas entry point
- `typer>=0.25.0` in dependencies
- `pytest-cov>=7.0` in dev extras
- `[tool.coverage.run]` (branch=true, source=atlas_runtime)
- `[tool.coverage.report]` (fail_under=80)

---

## Test Results

```
25 tests collected
24 xfailed (strict=True — stubs raise NotImplementedError as expected)
1 passed (test_status_unknown_id_exits_one — CLI status handler queries DB directly)
0 errors
0 failures
```

---

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1: Service stubs + CLI | f1385cc | feat(05-01): scaffold Phase 5 service module stubs and CLI |
| Task 2: Test skeletons | 8fba329 | feat(05-01): add Wave 0 xfail test skeletons for Phase 5 services |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_status_unknown_id_exits_one xfail marker removed**
- **Found during:** Task 2 verification
- **Issue:** `test_status_unknown_id_exits_one` was marked `xfail(strict=True)` but the `status` CLI command queries the DB directly (no stub involved), so it passes. With `strict=True`, a passing xfail = XPASS = test FAILED.
- **Fix:** Removed `@pytest.mark.xfail` from that specific test. Left a docstring explaining why it's non-xfail. All other 24 tests remain xfail.
- **Files modified:** `services/agent-runtime/tests/test_cli.py`
- **Commit:** 8fba329

---

## Known Stubs

All service functions are intentional stubs (Wave 0 contract). Wave 1 plans (05-02 through 05-04) will implement each function. Stub list:

| Stub | File | Resolved by |
|------|------|-------------|
| `create_mission`, `get_mission`, `list_missions` | mission_service.py | 05-02-PLAN |
| `start_run`, `complete_run`, `fail_run`, `cancel_run` | run_service.py | 05-02-PLAN |
| `check_workspace_boundary`, `check_workspace_boundary_and_emit`, `check_tool_allowed` | policy.py | 05-02-PLAN |
| `dispatch_subagent` | subagent_service.py | 05-02-PLAN |
| CLI `create/run/cancel` (call stubs) | cli/main.py | 05-02-PLAN (service layer) |

The CLI `status` command is fully functional (queries DB directly).

---

## Threat Surface Scan

No new trust boundaries introduced by Wave 0 scaffolding beyond what the plan's `<threat_model>` already documented:
- T-05-01: SQL injection via title/intent — parameterized queries enforced in Wave 1 implementation
- T-05-02: Path traversal in policy.py — pathlib.Path.resolve() required in Wave 1 implementation
- T-05-03: Secret leakage in subagent payload — emit() _redact() inherited, applied in Wave 1

No unplanned threat flags introduced.

---

## Self-Check: PASSED

All 11 source/test files exist at expected paths. Both task commits (f1385cc, 8fba329) found in git log. 25 tests collected, 24 xfailed, 1 passed, 0 errors.
