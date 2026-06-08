---
phase: 06-wiki-runtime
plan: "05"
subsystem: wiki-cli
tags: [cli, typer, wiki, tdd]
dependency_graph:
  requires: ["06-02", "06-03", "06-04"]
  provides: ["wiki-cli-surface"]
  affects: ["atlas-runtime-cli"]
tech_stack:
  added: []
  patterns: ["Typer sub-app registration via try/except", "CliRunner + monkeypatch pattern", "thin-CLI-wrapper"]
key_files:
  created:
    - services/wiki-runtime/atlas_wiki/cli/main.py
    - services/wiki-runtime/tests/test_cli.py
  modified:
    - services/agent-runtime/atlas_runtime/cli/main.py
    - services/wiki-runtime/atlas_wiki/wiki_service.py
decisions:
  - "CLI uses run_id='operator' for all commands — tests insert a matching runs row to satisfy FK"
  - "FTS5 query wrapped in double-quotes in search_wiki to prevent hyphen-as-exclude-operator parse errors"
metrics:
  duration_minutes: 12
  completed_date: "2026-06-08"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 06 Plan 05: Wiki CLI Sub-App Summary

**One-liner:** Typer wiki sub-app with ingest/update/search/semantic/lint commands registered into atlas_runtime CLI via graceful try/except import.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Add failing CLI tests | 47dd358 | services/wiki-runtime/tests/test_cli.py |
| 1 (GREEN) | Implement atlas_wiki/cli/main.py | 82f4697 | atlas_wiki/cli/main.py, tests/test_cli.py, wiki_service.py |
| 2 | Register wiki_app in atlas_runtime CLI | 5ab6ac0 | services/agent-runtime/atlas_runtime/cli/main.py |

## Verification Results

- 6 wiki CLI tests pass (test_cli.py)
- 44 existing atlas-runtime tests pass (no regression)
- No SQL in atlas_wiki/cli/main.py handler functions (only PRAGMA in connection factory, matching atlas_runtime pattern)
- try/except ImportError block present in atlas_runtime/cli/main.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FTS5 hyphen query parse error in search_wiki**
- **Found during:** Task 1, GREEN phase — test_search_no_results_exits_zero failing with `OperationalError('no such column: no')`
- **Issue:** FTS5 interprets hyphens in query strings as exclude operators (e.g., `xyzzy-no-match` → `xyzzy - no - match`), causing `no` to be treated as a column reference
- **Fix:** Wrapped query in double-quotes in `wiki_service.search_wiki` (`safe_query = '"' + query.replace('"', '""') + '"'`) — treats input as phrase/prefix search, avoids operator misparse
- **Files modified:** services/wiki-runtime/atlas_wiki/wiki_service.py
- **Commit:** 82f4697

**2. [Rule 1 - Bug] FK constraint failure for run_id="operator" in tests**
- **Found during:** Task 1, GREEN phase — test_ingest_exits_zero_prints_uuid failing with `IntegrityError('FOREIGN KEY constraint failed')`
- **Issue:** CLI hardcodes `run_id="operator"` but in-memory test DB has no runs row with that id; emit() in wiki_service inserts an audit_event row with that run_id
- **Fix:** Added inline mission+run insertion with id="operator" in the two affected tests (ingest and update), rather than changing the service design
- **Files modified:** services/wiki-runtime/tests/test_cli.py
- **Commit:** 82f4697

## Known Stubs

None — all CLI commands are wired to live wiki_service functions.

## Threat Surface Scan

No new threat surface introduced. wiki_app is registered behind try/except (T-06-13 satisfied). CLI contains no direct SQL in handler functions (T-06-12 satisfied).

## Self-Check: PASSED

- [x] services/wiki-runtime/atlas_wiki/cli/main.py exists
- [x] services/wiki-runtime/tests/test_cli.py exists
- [x] services/agent-runtime/atlas_runtime/cli/main.py modified (wiki_app block present)
- [x] Commits 47dd358, 82f4697, 5ab6ac0 exist in git log
- [x] 6 + 44 = 50 tests pass
