---
phase: 02-core-schemas
plan: "01"
subsystem: atlas-core
tags: [python-package, hatchling, pydantic, pytest, sqlite, venv]
dependency_graph:
  requires: []
  provides:
    - packages/atlas-core/pyproject.toml
    - packages/atlas-core/atlas_core/__init__.py
    - packages/atlas-core/atlas_core/schemas/__init__.py
    - packages/atlas-core/tests/__init__.py
    - packages/atlas-core/tests/conftest.py
    - packages/atlas-core/.venv (editable install)
  affects:
    - 02-02 (requires installable atlas-core package in atlas-core venv)
    - 02-03 (conftest.py db fixture applies 0001_core.sql when written)
tech_stack:
  added:
    - hatchling 1.30.1 (build backend)
    - pydantic>=2.0 (project dependency)
    - pytest>=9.0 (dev extra)
    - ruff>=0.15 (dev extra)
  patterns:
    - Project-scoped Python venv at packages/atlas-core/.venv (isolates from Hermes venv)
    - Editable install via: uv pip install -e packages/atlas-core[dev] --python <venv-python>
    - conftest.py db fixture with guarded migration application (exists check)
key_files:
  created:
    - packages/atlas-core/pyproject.toml
    - packages/atlas-core/atlas_core/__init__.py
    - packages/atlas-core/atlas_core/schemas/__init__.py
    - packages/atlas-core/tests/__init__.py
    - packages/atlas-core/tests/conftest.py
  modified: []
decisions:
  - "Project-scoped venv at packages/atlas-core/.venv prevents editable install targeting Hermes venv (Pitfall 6 from research)"
  - "conftest.py uses MIGRATION_PATH.exists() guard so fixture does not fail before plan 02-03 writes 0001_core.sql"
  - "tests/__init__.py is empty; required for pytest test discovery in packages/atlas-core/tests/"
metrics:
  duration: "~1 minute"
  completed: "2026-06-06T00:39:17Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 0
---

# Phase 02 Plan 01: atlas-core Package Bootstrap — Summary

**One-liner:** Hatchling-backed atlas-core Python package with project-scoped venv, editable install into Python 3.11, and guarded :memory: SQLite fixture for migration tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create atlas-core package tree and pyproject.toml | 545b9da | pyproject.toml, atlas_core/__init__.py, schemas/__init__.py, tests/__init__.py |
| 2 | Create venv, install editable, write conftest.py | 91c839c | tests/conftest.py (.venv not tracked) |

## What Was Built

**Task 1** created the full Python package directory tree under `packages/atlas-core/`:
- `pyproject.toml` with hatchling build backend, `pydantic>=2.0` production dep, `pytest>=9.0` and `ruff>=0.15` as dev extras, `[tool.hatch.build.targets.wheel] packages = ["atlas_core"]` (not `src/`), and `[tool.pytest.ini_options] testpaths = ["tests"]`.
- `atlas_core/__init__.py` with `__version__ = "0.1.0"` only.
- `atlas_core/schemas/__init__.py` with empty `__all__` placeholder (re-exports added in plan 02-02).
- `tests/__init__.py` empty (pytest discovery requirement).

**Task 2** created the project-scoped venv and conftest:
- `uv venv packages/atlas-core/.venv --python 3.11` creates the isolated environment.
- `uv pip install -e "packages/atlas-core[dev]" --python packages/atlas-core/.venv/Scripts/python.exe` installs 13 packages including pydantic 2.13.4, pytest 9.0.3, ruff 0.15.16.
- `import atlas_core; atlas_core.__version__` outputs `0.1.0` from the atlas-core venv.
- `atlas_core` is NOT present in the Hermes venv at `C:\Users\Davi\AppData\Local\hermes\hermes-agent\venv`.
- `tests/conftest.py` defines the `db` fixture with `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys = ON`, and a guarded `MIGRATION_PATH.exists()` check so the fixture does not raise `FileNotFoundError` before plan 02-03 writes `0001_core.sql`.

## Verification Results

| Check | Result |
|-------|--------|
| pyproject.toml hatchling backend | PASS |
| pyproject.toml packages = ["atlas_core"] | PASS |
| pyproject.toml testpaths = ["tests"] | PASS |
| `import atlas_core` from atlas-core venv | PASS (0.1.0) |
| atlas_core NOT in Hermes venv | PASS (ModuleNotFoundError) |
| PRAGMA journal_mode=WAL in conftest.py | PASS |
| PRAGMA foreign_keys = ON in conftest.py | PASS |
| MIGRATION_PATH resolves to project root/infra/migrations/0001_core.sql | PASS |
| packages/atlas-core/src/ not created | PASS |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- `packages/atlas-core/atlas_core/schemas/__init__.py`: `__all__ = []` — intentional placeholder. Re-exports added in plan 02-02 when `core.py` is written. This file cannot be used to import models yet; it is correct for plan 01 scope.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary changes. The uv install sourced all packages from PyPI; all 4 packages (pydantic, pytest, ruff, hatchling) were pre-audited as [OK] by slopcheck 0.6.1 in 02-RESEARCH.md. The threat register mitigations for T-02-01 and T-02-02 are confirmed applied:
- T-02-01 (wrong venv target): `--python packages/atlas-core/.venv/Scripts/python.exe` explicitly passed; Hermes venv confirmed clean.
- T-02-02 (wrong packages path): `packages = ["atlas_core"]` verified in pyproject.toml and confirmed by successful editable install.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| packages/atlas-core/pyproject.toml | FOUND |
| packages/atlas-core/atlas_core/__init__.py | FOUND |
| packages/atlas-core/atlas_core/schemas/__init__.py | FOUND |
| packages/atlas-core/tests/__init__.py | FOUND |
| packages/atlas-core/tests/conftest.py | FOUND |
| packages/atlas-core/.venv | FOUND |
| Commit 545b9da (Task 1) | FOUND |
| Commit 91c839c (Task 2) | FOUND |
