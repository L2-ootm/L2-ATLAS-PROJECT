---
phase: 04-event-bus
plan: "01"
subsystem: agent-runtime
tags: [scaffold, packaging, testing, atlas-runtime, atlas-audit]
dependency_graph:
  requires: []
  provides:
    - services/agent-runtime package scaffold (atlas_runtime, atlas_audit importable)
    - db/run_id/lock pytest fixtures for all Wave 1 and Wave 2 plans
    - atlas_audit/plugin.yaml Hermes plugin manifest
  affects:
    - services/agent-runtime/tests/ (all subsequent test files in this phase)
tech_stack:
  added:
    - hatchling build backend for atlas-runtime
    - atlas-runtime editable install (pip install -e)
  patterns:
    - pytest fixtures: db (in-memory SQLite + WAL + FK + migration), run_id (uuid4), lock (threading.Lock)
    - module-level ImportError skip pattern for stub test files
key_files:
  created:
    - services/agent-runtime/pyproject.toml
    - services/agent-runtime/atlas_runtime/__init__.py
    - services/agent-runtime/atlas_audit/__init__.py
    - services/agent-runtime/atlas_audit/plugin.yaml
    - services/agent-runtime/tests/__init__.py
    - services/agent-runtime/tests/conftest.py
    - services/agent-runtime/tests/test_audit_service.py
    - services/agent-runtime/tests/test_atlas_audit_plugin.py
    - services/agent-runtime/tests/test_conftest.py
  modified: []
decisions:
  - "MIGRATION_PATH uses 4 parent hops (not 3 as in plan spec): conftest.py -> tests/ -> agent-runtime/ -> services/ -> root requires 4 .parent calls"
  - "atlas-core listed as plain dep (no URL) in pyproject.toml since pip does not resolve relative path:// URLs; atlas-core installed editably separately"
  - "Added test_conftest.py to ensure pytest exits 0 (not code 5) — the two stub files skip at module level leaving 0 runnable tests without it"
  - "tool.hatch.metadata.allow-direct-references = true added to pyproject.toml for future path-dep compatibility"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-07"
  tasks_completed: 2
  tasks_total: 2
  files_created: 9
  files_modified: 0
---

# Phase 04 Plan 01: Agent-Runtime Package Scaffold Summary

**One-liner:** services/agent-runtime editable package with atlas_runtime + atlas_audit stubs, db/run_id/lock pytest fixtures, and 5-hook plugin.yaml manifest for Hermes integration.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Package scaffold with pyproject.toml and init files | 27e037a | pyproject.toml, atlas_runtime/__init__.py, atlas_audit/__init__.py, atlas_audit/plugin.yaml |
| 2 | tests/conftest.py and stub test files | cb61dfe | tests/conftest.py, test_audit_service.py, test_atlas_audit_plugin.py, test_conftest.py |

## Verification Results

```
pytest services/agent-runtime/tests/ -x -q
3 passed, 2 skipped in 0.02s
Exit: 0
```

- `from atlas_runtime import __doc__` → "ATLAS agent-runtime service layer."
- `from atlas_audit import __version__` → "0.1.0"
- `atlas_audit/plugin.yaml` contains all 5 hooks: post_api_request, post_llm_call, post_tool_call, subagent_stop, post_approval_response
- db fixture: `SELECT name FROM sqlite_master WHERE name='audit_events'` returns non-None row

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] MIGRATION_PATH hop count corrected from 3 to 4**
- **Found during:** Task 2 — test_db_fixture_returns_connection failed (audit_events table not found)
- **Issue:** Plan spec said "3 parent hops" counting directory transitions (tests/ → agent-runtime/ → services/ → root). But `.parent` calls are counted from the file itself: file → tests/ → agent-runtime/ → services/ → root = 4 calls.
- **Fix:** Changed `pathlib.Path(__file__).parent.parent.parent` to `.parent.parent.parent.parent`
- **Files modified:** services/agent-runtime/tests/conftest.py
- **Commit:** cb61dfe

**2. [Rule 2 - Missing functionality] Added test_conftest.py smoke tests**
- **Found during:** Task 2 — after stub files both skip at module level, pytest exits with code 5 (no tests collected), not 0
- **Issue:** Plan success criterion requires exit 0 but all stubs skip immediately; exit 5 ≠ 0
- **Fix:** Added test_conftest.py with 3 always-passing fixture smoke tests to ensure at least one test runs per collection
- **Files modified:** services/agent-runtime/tests/test_conftest.py (new file)
- **Commit:** cb61dfe

**3. [Rule 1 - Bug] atlas-core path dependency form incompatible with pip**
- **Found during:** Task 1 — pip install failed with "relative path without working directory" for `atlas-core @ ../../packages/atlas-core`; then `${PROJECT_ROOT}` env var not recognized by hatchling context
- **Fix:** Listed `atlas-core` as plain name dependency (not URL). atlas-core installed as separate editable install first. `tool.hatch.metadata.allow-direct-references = true` retained for future path-dep use.
- **Files modified:** services/agent-runtime/pyproject.toml
- **Commit:** 27e037a

## Known Stubs

| File | Stub | Reason |
|------|------|--------|
| services/agent-runtime/tests/test_audit_service.py | All 7 test bodies are `pass`, skip on import | atlas_runtime.audit_service not implemented until Wave 1 |
| services/agent-runtime/tests/test_atlas_audit_plugin.py | All 4 test bodies are `pass`, skip on import | atlas_audit hook functions not implemented until Wave 2 |
| services/agent-runtime/atlas_audit/__init__.py | No register() function | Wave 2 adds register() and hook callbacks |

These stubs are intentional. Wave 1 (04-02) implements atlas_runtime.audit_service; Wave 2 (04-03) implements atlas_audit hook callbacks.

## Self-Check: PASSED

Files exist:
- FOUND: services/agent-runtime/pyproject.toml
- FOUND: services/agent-runtime/atlas_runtime/__init__.py
- FOUND: services/agent-runtime/atlas_audit/__init__.py
- FOUND: services/agent-runtime/atlas_audit/plugin.yaml
- FOUND: services/agent-runtime/tests/conftest.py
- FOUND: services/agent-runtime/tests/test_audit_service.py
- FOUND: services/agent-runtime/tests/test_atlas_audit_plugin.py

Commits exist:
- FOUND: 27e037a (Task 1)
- FOUND: cb61dfe (Task 2)
