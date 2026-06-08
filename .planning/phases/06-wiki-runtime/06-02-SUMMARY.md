---
phase: 06-wiki-runtime
plan: 02
subsystem: services/wiki-runtime
tags: [scaffold, package, pyproject, stubs, atlas-wiki, D-019]
dependency_graph:
  requires: [06-01]
  provides: [atlas-wiki installable package, wiki_service stubs, provenance_service stubs]
  affects: [services/wiki-runtime/pyproject.toml, services/wiki-runtime/atlas_wiki/__init__.py, services/wiki-runtime/atlas_wiki/cli/__init__.py, services/wiki-runtime/atlas_wiki/wiki_service.py, services/wiki-runtime/atlas_wiki/provenance_service.py, services/wiki-runtime/tests/__init__.py]
tech_stack:
  added: [atlas-wiki (editable package), hatchling build backend]
  patterns: [editable install, optional dependency groups, NotImplementedError stubs, lazy import guard]
key_files:
  created:
    - services/wiki-runtime/pyproject.toml
    - services/wiki-runtime/atlas_wiki/__init__.py
    - services/wiki-runtime/atlas_wiki/cli/__init__.py
    - services/wiki-runtime/atlas_wiki/wiki_service.py
    - services/wiki-runtime/atlas_wiki/provenance_service.py
    - services/wiki-runtime/tests/__init__.py
  modified: []
decisions:
  - sqlite-vec and fastembed placed in optional [semantic] group only — never auto-installed per T-06-03 threat mitigation
  - No [project.scripts] entry in atlas-wiki — wiki_app registered into atlas-runtime via try/except import
  - wiki_service.py explicitly comments "DO NOT import sqlite_vec or fastembed at module level"
metrics:
  duration: ~10 minutes
  completed: 2026-06-08
  tasks_completed: 2
  tasks_total: 2
  files_changed: 6
---

# Phase 06 Plan 02: atlas-wiki Package Scaffold Summary

**One-liner:** Installable atlas-wiki package scaffold with hatchling pyproject.toml, semantic optional deps group, and NotImplementedError stubs for wiki_service and provenance_service — ready for 06-03 and 06-04 implementation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create services/wiki-runtime/ package scaffold | 0668733 | pyproject.toml, atlas_wiki/__init__.py, atlas_wiki/cli/__init__.py, tests/__init__.py |
| 2 | Create stub modules wiki_service and provenance_service | 74a344f | atlas_wiki/wiki_service.py, atlas_wiki/provenance_service.py |

## What Was Built

**Task 1 — Package scaffold:**
- `pyproject.toml`: hatchling build backend, `name="atlas-wiki"`, `requires-python=">=3.11"`
- Dependencies: `atlas-core`, `atlas-runtime`, `typer>=0.25.0`
- Optional groups: `semantic = ["sqlite-vec>=0.1.9", "fastembed>=0.8.0"]` (not auto-installed), `dev = ["pytest>=9.0", "pytest-cov>=7.0"]`
- No `[project.scripts]` section — wiki CLI injected into atlas-runtime via try/except
- Coverage: `source=["atlas_wiki"]`, `fail_under=80`
- `atlas_wiki/__init__.py`: module docstring, empty body
- `atlas_wiki/cli/__init__.py`: module docstring, empty body
- `tests/__init__.py`: empty test package marker

**Task 2 — Stub modules:**
- `wiki_service.py`: five stubs — `ingest_source`, `update_wiki_page`, `search_wiki`, `semantic_search`, `lint`
  - All raise `NotImplementedError`; all imports correct
  - Explicit comment guards `sqlite_vec`/`fastembed` from module-level import (T-06-03)
- `provenance_service.py`: two stubs — `write_provenance`, `get_provenance`
  - All raise `NotImplementedError`; `MemoryProvenance` import from atlas_core

## Verification Results

```
pip install -e services/wiki-runtime/ → exit 0
import atlas_wiki → OK
from atlas_wiki import wiki_service, provenance_service → OK
grep sqlite_vec/fastembed at module level → 0 matches
pytest services/agent-runtime/tests/ -x -q → 44 passed (no regressions)
```

All 5 success criteria passed:
1. `pyproject.toml` has `name="atlas-wiki"`, `atlas-runtime` dependency, `semantic` optional group, `fail_under=80` — OK
2. `pip install -e services/wiki-runtime/` exits 0 — OK
3. `from atlas_wiki import wiki_service, provenance_service` succeeds — OK
4. No top-level `sqlite_vec`/`fastembed` imports in `wiki_service.py` — OK
5. All five function stubs present in `wiki_service.py` with correct signatures — OK

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

The following stubs are intentional and tracked for implementation by 06-03/06-04:

| File | Function | Reason |
|------|----------|--------|
| atlas_wiki/wiki_service.py | ingest_source | Implemented by 06-03 |
| atlas_wiki/wiki_service.py | update_wiki_page | Implemented by 06-03 |
| atlas_wiki/wiki_service.py | search_wiki | Implemented by 06-03 |
| atlas_wiki/wiki_service.py | semantic_search | Implemented by 06-03 |
| atlas_wiki/wiki_service.py | lint | Implemented by 06-03 |
| atlas_wiki/provenance_service.py | write_provenance | Implemented by 06-04 |
| atlas_wiki/provenance_service.py | get_provenance | Implemented by 06-04 |

These stubs are the scaffolding purpose of this plan — not incomplete work. The plan's goal is a shell that 06-03 and 06-04 fill.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes beyond what the plan's threat model covers. T-06-03 (sqlite_vec/fastembed at module level) mitigated by explicit comment guard and optional-only dependency placement.

## Self-Check: PASSED

- `services/wiki-runtime/pyproject.toml` — exists and verified
- `services/wiki-runtime/atlas_wiki/__init__.py` — exists and verified
- `services/wiki-runtime/atlas_wiki/cli/__init__.py` — exists and verified
- `services/wiki-runtime/atlas_wiki/wiki_service.py` — exists and verified
- `services/wiki-runtime/atlas_wiki/provenance_service.py` — exists and verified
- `services/wiki-runtime/tests/__init__.py` — exists and verified
- Commit 0668733 — Task 1 scaffold
- Commit 74a344f — Task 2 stubs
