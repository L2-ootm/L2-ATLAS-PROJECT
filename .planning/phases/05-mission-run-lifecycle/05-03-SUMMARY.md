---
phase: 05-mission-run-lifecycle
plan: "03"
subsystem: agent-runtime
tags: [policy-engine, subagent-governance, workspace-boundary, pathlib, emit-after-lock, tdd]
requires:
  - 05-01 (Wave 0 stubs)
  - 05-02 (run_service.start_run — needed by subagent test)
provides:
  - atlas_runtime.policy (check_workspace_boundary, check_workspace_boundary_and_emit, check_tool_allowed — fully implemented)
  - atlas_runtime.subagent_service (dispatch_subagent stub — emits subagent_run AuditEvent)
affects:
  - 05-04-PLAN (CLI tests can now call policy functions through run lifecycle)
tech-stack:
  added: []
  patterns:
    - pathlib-resolve-boundary (workspace boundary via Path.resolve() + relative_to() — cross-platform, no shell logic)
    - emit-after-lock (policy failure events emitted outside lock acquisition — inherited from Plan 02 pattern)
    - fail-open-error-guard (dispatch_subagent wraps emit() in try/except — audit failures do not crash callers)
    - reject-by-default (check_tool_allowed denies any unclassified tool — D-008)
key-files:
  created: []
  modified:
    - services/agent-runtime/atlas_runtime/policy.py
    - services/agent-runtime/atlas_runtime/subagent_service.py
    - services/agent-runtime/tests/test_policy.py
    - services/agent-runtime/tests/test_run_service.py
decisions:
  - "check_workspace_boundary joins target_path to resolved_root before calling resolve() — pins relative paths to workspace, prevents CWD-escape (Pitfall 3)"
  - "Absolute paths outside workspace (e.g. C:\\Users\\other\\file.txt) fail relative_to() because pathlib discards the workspace_root prefix on join when target_path is absolute"
  - "check_tool_allowed has no emit() call — tool rejection is logged by the caller which has run_id context; policy check is pure"
  - "dispatch_subagent is a Phase 5 stub — no real spawning; only emits subagent_run AuditEvent with governance envelope"
metrics:
  duration: "6m"
  completed: "2026-06-08"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 4
---

# Phase 05 Plan 03: Policy Engine + Subagent Governance Stub Summary

**One-liner:** Cross-platform workspace boundary enforcement via pathlib.Path.resolve() and subagent governance stub emitting RUNTIME-06 AuditEvent with full governance payload.

---

## What Was Built

Wave 1 implementation for RUNTIME-06 and RUNTIME-07. Both modules were stubs raising `NotImplementedError` — replaced with production-ready implementations.

**policy.py (3 functions):**
- `check_workspace_boundary(target_path, workspace_root)` — resolves workspace_root via `Path(workspace_root).resolve()`; resolves target via `(resolved_root / target_path).resolve()` (pins relative paths to workspace_root, prevents CWD-escape); calls `relative_to()` — ValueError on out-of-workspace path; returns `PolicyDecision(allowed=True/False, reason=...)`. Handles Windows-style absolute paths via Python's pathlib join semantics (absolute target_path discards workspace prefix, fails relative_to check).
- `check_workspace_boundary_and_emit(conn, lock, run_id, target_path, workspace_root)` — delegates to `check_workspace_boundary()`; on rejection calls `emit()` with `event_type="failure"`, `policy_result=decision.reason`; returns decision.
- `check_tool_allowed(tool_name, allowed_tools)` — single if/else; no DB or emit; returns `PolicyDecision(allowed=True, reason="tool_in_allowlist")` or `PolicyDecision(allowed=False, reason=f"tool_not_allowed: ...")`.

**subagent_service.py (1 function):**
- `dispatch_subagent(conn, lock, *, run_id, role, model_tier, allowed_tools, autonomy_level, token_budget)` — builds governance payload dict with 5 keys (normalizes `allowed_tools=None` to `[]`); calls `emit(conn, lock, run_id=run_id, event_type="subagent_run", data=payload)`; wraps in `try/except Exception` for fail-open behavior; returns `None`. No real subagent spawning in Phase 5.

---

## Test Results

```
15 tests collected
15 passed
0 xfailed
0 failed
0 errors

Breakdown:
  test_policy.py: 6 passed (3 parametrized boundary cases + 2 tool allowlist + 1 failure emit)
  test_run_service.py: 9 passed (8 from Plan 02 + test_dispatch_subagent_emits_subagent_run now green)
```

---

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1: policy.py + test_policy.py | 60b735d | feat(05-03): implement policy.py workspace boundary and tool allowlist (RUNTIME-07) |
| Task 2: subagent_service.py + test_run_service.py | b7e1b0b | feat(05-03): implement subagent_service dispatch stub with subagent_run AuditEvent (RUNTIME-06) |

---

## Deviations from Plan

None — plan executed exactly as written. All critical design constraints honored:
- `pathlib.Path.resolve()` only for path normalization — no `os.sep`, no shell logic, no string splitting
- emit-after-lock pattern: `check_workspace_boundary_and_emit` calls `emit()` outside any lock (emit() acquires the lock internally)
- Fail-open error guard in `dispatch_subagent` (try/except wrapping emit call)
- `allowed_tools` normalized from `None` to `[]` before storage
- No subprocess/Popen/spawn imports in subagent_service.py

---

## Known Stubs

The following pre-existing stubs from Wave 0 remain (not in scope for this plan):

| Stub | File | Resolved by |
|------|------|-------------|
| CLI `create/run/cancel` (call stubs) | cli/main.py | 05-04-PLAN |

---

## Threat Surface Scan

No new trust boundaries beyond what the plan's `<threat_model>` documented:
- T-05-02: Path traversal in policy.py — mitigated: `(resolved_root / target_path).resolve()` + `relative_to()` prevents ../../ CWD-escape; absolute paths outside workspace fail `relative_to()` check
- T-05-06: Unclassified tool bypass — mitigated: `check_tool_allowed` rejects any tool_name not in allowed_tools (no default-allow)
- T-05-03: Secret leakage in subagent payload — mitigated: `dispatch_subagent` data passes through `emit()` which calls `_redact()` via SECRET_PATTERNS before storage

No unplanned threat flags introduced.

---

## Self-Check: PASSED

- `policy.py` exists, no `shell=True`, no `os.sep`, no string split on path separators
- `subagent_service.py` exists, no subprocess/Popen/spawn references
- Commit `60b735d` exists in git log (Task 1)
- Commit `b7e1b0b` exists in git log (Task 2)
- 15 tests passed, 0 xfailed, 0 errors (verified via pytest)
