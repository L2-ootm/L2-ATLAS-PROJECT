---
phase: 06
slug: wiki-runtime
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-08
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already installed, matches agent-runtime pattern) |
| **Config file** | `services/wiki-runtime/pyproject.toml` — Wave 0 creates it |
| **Quick run command** | `python -m pytest services/wiki-runtime/tests -q` |
| **Full suite command** | `python -m pytest services/wiki-runtime/tests packages/atlas-core/tests -q` |
| **Estimated runtime** | ~10 seconds (service unit tests, no sqlite-vec semantic tests unless extension present) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest services/wiki-runtime/tests -q`
- **After every plan wave:** Run `python -m pytest services/wiki-runtime/tests packages/atlas-core/tests -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | — | — | Schema extension does not break existing tests | unit | `python -m pytest packages/atlas-core/tests -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | — | — | Migration applies cleanly; sources table has untrusted + ingested_by_run_id | unit | `python -m pytest packages/atlas-core/tests -q` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | WIKI-01 | — | ingest() copies file to wiki/raw/, computes SHA-256, creates Source row with untrusted flag | unit | `python -m pytest services/wiki-runtime/tests/test_wiki_service.py::test_ingest -q` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 1 | WIKI-01 | — | ingest() emits AuditEvent with kind=wiki_update, source_id, run_id | unit | `python -m pytest services/wiki-runtime/tests/test_wiki_service.py::test_ingest_emits_audit -q` | ❌ W0 | ⬜ pending |
| 06-02-03 | 02 | 1 | WIKI-02 | — | update() upserts WikiPage row, appends to wiki/log.md, updates wiki/index.md, writes MemoryProvenance | unit | `python -m pytest services/wiki-runtime/tests/test_wiki_service.py::test_update -q` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 1 | WIKI-03 | — | search() returns ranked FTS5 results with slug + source_id citation | unit | `python -m pytest services/wiki-runtime/tests/test_wiki_service.py::test_search -q` | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 1 | WIKI-05 | — | semantic_search() degrades to FTS if sqlite-vec absent; returns results with citations when present | unit | `python -m pytest services/wiki-runtime/tests/test_wiki_service.py::test_semantic -q` | ❌ W0 | ⬜ pending |
| 06-04-01 | 04 | 1 | AUDIT-03 | — | lint() flags pages with untrusted-only citations | unit | `python -m pytest services/wiki-runtime/tests/test_wiki_service.py::test_lint -q` | ❌ W0 | ⬜ pending |
| 06-04-02 | 04 | 1 | AUDIT-03 | — | lint() flags contradicted claims between pages | unit | `python -m pytest services/wiki-runtime/tests/test_wiki_service.py::test_lint_contradiction -q` | ❌ W0 | ⬜ pending |
| 06-05-01 | 05 | 2 | WIKI-01 | — | CLI: atlas wiki ingest <path> runs without error; Source row created | cli | `python -m pytest services/wiki-runtime/tests/test_cli.py::test_cli_ingest -q` | ❌ W0 | ⬜ pending |
| 06-05-02 | 05 | 2 | WIKI-02 | — | CLI: atlas wiki update <slug> runs without error; WikiPage row upserted | cli | `python -m pytest services/wiki-runtime/tests/test_cli.py::test_cli_update -q` | ❌ W0 | ⬜ pending |
| 06-05-03 | 05 | 2 | WIKI-03 | — | CLI: atlas wiki search "query" returns ranked results | cli | `python -m pytest services/wiki-runtime/tests/test_cli.py::test_cli_search -q` | ❌ W0 | ⬜ pending |
| 06-05-04 | 05 | 2 | WIKI-05 | — | CLI: atlas wiki semantic "query" degrades gracefully when sqlite-vec absent | cli | `python -m pytest services/wiki-runtime/tests/test_cli.py::test_cli_semantic -q` | ❌ W0 | ⬜ pending |
| 06-05-05 | 05 | 2 | AUDIT-03 | — | CLI: atlas wiki lint returns lint findings | cli | `python -m pytest services/wiki-runtime/tests/test_cli.py::test_cli_lint -q` | ❌ W0 | ⬜ pending |
| 06-06-01 | 06 | 2 | WIKI-04 | — | wiki/index.md has entry for every WikiPage row after update | unit | `python -m pytest services/wiki-runtime/tests/test_wiki_service.py::test_index_consistency -q` | ❌ W0 | ⬜ pending |
| 06-06-02 | 06 | 2 | WIKI-04 | — | wiki/log.md has entry for every wiki_update AuditEvent | unit | `python -m pytest services/wiki-runtime/tests/test_wiki_service.py::test_log_consistency -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/wiki-runtime/pyproject.toml` — package config for atlas-wiki
- [ ] `services/wiki-runtime/atlas_wiki/__init__.py` — package init
- [ ] `services/wiki-runtime/atlas_wiki/wiki_service.py` — stub with function signatures
- [ ] `services/wiki-runtime/atlas_wiki/provenance_service.py` — stub
- [ ] `services/wiki-runtime/atlas_wiki/cli/__init__.py` — cli package
- [ ] `services/wiki-runtime/atlas_wiki/cli/main.py` — wiki_app Typer sub-app stub
- [ ] `services/wiki-runtime/tests/__init__.py` — test package
- [ ] `services/wiki-runtime/tests/conftest.py` — db, run_id, lock, wiki_dir fixtures
- [ ] `services/wiki-runtime/tests/test_wiki_service.py` — test stubs (RED phase)
- [ ] `services/wiki-runtime/tests/test_provenance_service.py` — test stubs (RED phase)
- [ ] `services/wiki-runtime/tests/test_cli.py` — CLI test stubs (RED phase)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| sqlite-vec native extension loads on Windows 11 | WIKI-05 | Native DLL extension; automated tests skip if absent | Install sqlite-vec, run `python -c "import sqlite_vec; import sqlite3; conn=sqlite3.connect(':memory:'); conn.enable_load_extension(True); sqlite_vec.load(conn); print('OK')"` |
| fastembed ONNX model downloads on first run | WIKI-05 | Requires network access and disk space (~100MB) | Run `atlas wiki semantic "test query"` after installing fastembed; first run triggers model download |

---

## Validation Architecture

### Test Layering

| Layer | Tools | What it covers |
|-------|-------|----------------|
| Unit: service functions | pytest + sqlite3 in-memory DB | ingest, update, search, lint, provenance — all paths including error paths |
| Unit: schema extension | pytest | Source.untrusted, Source.ingested_by_run_id, MemoryProvenance model validation |
| Unit: migration | pytest | 0002 migration applies cleanly on top of 0001; source table columns present |
| CLI: thin wrapper | pytest + typer.testing.CliRunner | All 5 subcommands; monkeypatch _get_connection/_get_lock |
| Integration: cross-phase | pytest (separate run) | packages/atlas-core tests unbroken after schema extension |

### Coverage Target

≥80% branch coverage on `wiki_service.py` (per CONTEXT.md success criterion 8). Coverage measured with `python -m pytest services/wiki-runtime/tests --cov=atlas_wiki --cov-report=term-missing`.

### sqlite-vec Conditional Testing

All tests touching `semantic_search()` must use `pytest.importorskip("sqlite_vec")` at the top of the test function (not module level). This ensures the test suite runs completely on machines without sqlite-vec installed. The degradation path (returns FTS results with a diagnostic message) must be tested in a separate test that does NOT importorskip.

### Critical Invariants

1. `Source.untrusted` must never be None — validated in Pydantic model (default=False).
2. Every wiki write that changes state must emit an AuditEvent before returning.
3. Every WikiPage update must write a MemoryProvenance record with the same `audit_event_id`.
4. wiki/index.md and wiki/log.md are updated in-process after every DB write (same call, same function).
5. FTS5 triggers handle index maintenance automatically — no manual FTS5 INSERT in service code.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
