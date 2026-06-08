---
phase: 05-mission-run-lifecycle
plan: "04"
subsystem: agent-runtime/cli
tags: [cli, typer, testing, coverage]
dependency_graph:
  requires:
    - "05-02"  # mission_service + run_service implementation
    - "05-03"  # policy_service + subagent_service implementation
  provides:
    - "atlas CLI: mission create|run|cancel|status subcommands functional"
    - "Full test suite gate: 85% branch coverage, 44 tests passing"
  affects:
    - services/agent-runtime/atlas_runtime/cli/main.py
    - services/agent-runtime/tests/test_cli.py
    - services/agent-runtime/tests/test_run_service.py
tech_stack:
  added: []
  patterns:
    - "Typer CLI with monkeypatched _get_connection/_get_lock for test isolation"
    - "CliRunner from typer.testing for CLI integration tests"
key_files:
  created: []
  modified:
    - services/agent-runtime/tests/test_cli.py
    - services/agent-runtime/tests/test_run_service.py
decisions:
  - "CLI was already fully implemented in Wave 0 stub — only xfail markers needed removal"
  - "fail_run test added per plan spec to exercise direct delegation path in run_service"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-08"
---

# Phase 05 Plan 04: CLI Wire-Up and Coverage Gate Summary

**One-liner:** Removed xfail markers from CLI tests (Wave 0 stub was already the full implementation) and added test_fail_run_sets_failed to hit plan-specified coverage targets; full suite passes at 85% branch coverage.

## What Was Built

### Task 1: Remove xfail markers from test_cli.py

The Wave 0 CLI stub (`atlas_runtime/cli/main.py`) already contained complete, working implementations of all four subcommands (create, run, cancel, status). The four `@pytest.mark.xfail(reason="stub — implement in Wave 1", strict=True)` markers caused XPASS(strict) failures because the implementation already passed. Removing the markers made all 5 CLI tests green immediately.

CLI architecture confirmed correct:
- `create`: calls `mission_service.create_mission()`, echoes UUID
- `run`: calls `run_service.start_run()`, echoes run ID, handles ValueError → exit 1
- `cancel`: SELECT running runs, calls `run_service.cancel_run()` per row, echoes "cancelled"
- `status`: SELECT mission status, echoes status or "not found" + exit 1
- No INSERT/UPDATE SQL in CLI layer
- No `emit()` calls in CLI layer

### Task 2: Full suite coverage gate

Added `test_fail_run_sets_failed` to `test_run_service.py` to directly exercise the `fail_run()` delegation path (previously uncovered at line 155).

Final coverage results:
| Module | Stmts | Branch | Cover |
|--------|-------|--------|-------|
| atlas_runtime/__init__.py | 0 | 0 | 100% |
| atlas_runtime/audit_service.py | 60 | 18 | 87% |
| atlas_runtime/cli/__init__.py | 1 | 0 | 100% |
| atlas_runtime/cli/main.py | 60 | 8 | 75% |
| atlas_runtime/mission_service.py | 23 | 2 | 92% |
| atlas_runtime/policy.py | 28 | 4 | 97% |
| atlas_runtime/run_service.py | 51 | 12 | 84% |
| atlas_runtime/subagent_service.py | 12 | 0 | 83% |
| **TOTAL** | **235** | **44** | **85%** |

Gate: `--cov-fail-under=80` → PASSED (85%)
Test count: 44 passed, 0 failed, 0 errors

Note: `cli/main.py` at 75% — `_get_connection()` (lines 39-44) is always monkeypatched in tests (by design for isolation). Error branches for ValueError in run/cancel are not exercised by current tests. The total gate of 80% is met at the suite level.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 2726527 | feat(05-04): remove xfail markers from CLI tests — all 5 passing |
| Task 2 | dc7d591 | feat(05-04): add test_fail_run_sets_failed; full suite 85% branch coverage |

## Deviations from Plan

**1. [Rule 1 - Bug] CLI was already implemented — no implementation needed**
- **Found during:** Task 1
- **Issue:** The plan described rewriting CLI handler bodies ("replace the stub create/run/cancel/status handlers"). In fact, the Wave 0 stub already contained complete, working implementations identical to what the plan specified. The tests were failing only because of `strict=True` xfail markers.
- **Fix:** Removed xfail markers only. No handler bodies were modified.
- **Files modified:** services/agent-runtime/tests/test_cli.py
- **Impact:** Zero — correct behavior achieved with minimal change.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. CLI reads only via parameterized SELECT queries (no mutation SQL). No new trust boundaries created.

## Known Stubs

None — all CLI subcommands are fully functional and wired to the service layer.

## Self-Check: PASSED

- [x] test_cli.py xfail markers removed — 5/5 tests passing
- [x] test_run_service.py has test_fail_run_sets_failed
- [x] Full suite: 44 passed, 0 failed, 0 errors
- [x] Coverage gate (80%) met: 85% total branch coverage
- [x] mission_service.py: 92% (>80%)
- [x] run_service.py: 84% (>80%)
- [x] CLI has no INSERT/UPDATE SQL, no emit() calls
- [x] atlas entry point registered in pyproject.toml
- [x] Commits 2726527 and dc7d591 exist on worktree-agent-a95319e64705f9fda branch
