---
phase: 5
slug: mission-run-lifecycle
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-07
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `services/agent-runtime/pyproject.toml` → `[tool.pytest.ini_options]` testpaths = ["tests"] |
| **Quick run command** | `pytest services/agent-runtime/tests/test_mission_service.py services/agent-runtime/tests/test_run_service.py -x -q` |
| **Full suite command** | `pytest services/agent-runtime/ --cov=atlas_runtime --cov-branch --cov-fail-under=80` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest services/agent-runtime/tests/test_mission_service.py services/agent-runtime/tests/test_run_service.py -x -q`
- **After every plan wave:** Run `pytest services/agent-runtime/ --cov=atlas_runtime --cov-branch --cov-fail-under=80`
- **Before `/gsd-verify-work`:** Full suite must be green with ≥80% branch coverage on `atlas_runtime/mission_service.py` and `atlas_runtime/run_service.py`
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | RUNTIME-01 | T-05-01 | SQL injection via title/intent — parameterized queries only | unit stub | `pytest tests/test_mission_service.py -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 0 | RUNTIME-02 | — | — | unit stub | `pytest tests/test_run_service.py -x` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 0 | RUNTIME-07 | T-05-02 | Path traversal — `pathlib.Path.resolve()` + `relative_to()` check | unit stub | `pytest tests/test_policy.py -x` | ❌ W0 | ⬜ pending |
| 05-01-04 | 01 | 0 | RUNTIME-01 | — | — | CLI stub | `pytest tests/test_cli.py -x` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | RUNTIME-01 | T-05-01 | Pydantic validates inputs before SQL | unit | `pytest tests/test_mission_service.py -x` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 1 | RUNTIME-02 | — | Lock released before emit() to prevent deadlock | unit | `pytest tests/test_run_service.py::test_start_run -x` | ❌ W0 | ⬜ pending |
| 05-02-03 | 02 | 1 | RUNTIME-04 | — | Both runs and missions updated atomically | unit | `pytest tests/test_run_service.py::test_complete_run -x` | ❌ W0 | ⬜ pending |
| 05-02-04 | 02 | 1 | RUNTIME-05 | — | Partial audit trail preserved on cancel | unit | `pytest tests/test_run_service.py::test_cancel_run -x` | ❌ W0 | ⬜ pending |
| 05-02-05 | 02 | 1 | RUNTIME-06 | T-05-03 | Secret leakage in subagent payload — redact() called via emit() | unit | `pytest tests/test_run_service.py::test_subagent_governance -x` | ❌ W0 | ⬜ pending |
| 05-02-06 | 02 | 1 | RUNTIME-07 | T-05-02 | Workspace boundary rejects `../../` traversal on Linux + Windows paths | unit (parametrized) | `pytest tests/test_policy.py -x` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 2 | RUNTIME-01 | — | — | CLI | `pytest tests/test_cli.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/agent-runtime/tests/test_mission_service.py` — stubs for RUNTIME-01 (create, get, list, cancel)
- [ ] `services/agent-runtime/tests/test_run_service.py` — stubs for RUNTIME-02, RUNTIME-04, RUNTIME-05, RUNTIME-06
- [ ] `services/agent-runtime/tests/test_policy.py` — stubs for RUNTIME-07 (parametrized Linux + Windows path cases)
- [ ] `services/agent-runtime/tests/test_cli.py` — stubs for CLI subcommand invocations via Click CliRunner
- [ ] `services/agent-runtime/atlas_runtime/mission_service.py` — module stub with function signatures + docstrings
- [ ] `services/agent-runtime/atlas_runtime/run_service.py` — module stub with function signatures + docstrings
- [ ] `services/agent-runtime/atlas_runtime/policy.py` — module stub with function signatures + docstrings
- [ ] `services/agent-runtime/atlas_runtime/subagent_service.py` — stub (Phase 5 is all-stub for subagents)
- [ ] `services/agent-runtime/atlas_runtime/cli/__init__.py` — empty module init
- [ ] `services/agent-runtime/atlas_runtime/cli/main.py` — Typer app with four commands (create, run, cancel, status)
- [ ] `services/agent-runtime/pyproject.toml` — add `[project.scripts]` atlas entry + `typer` dep + `pytest-cov` to dev

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Policy engine works on actual Windows PowerShell paths | RUNTIME-07 | Must run on the real OS; pytest parametrize provides path string coverage but OS-level resolution requires real execution | Run `atlas mission create --title "T" --intent "..."` then `atlas mission run <id>` on both Linux and Windows |
| Hermes runtime loop integration end-to-end | RUNTIME-02 | Full Hermes loop requires external context/session not easily mocked | Manually run `atlas mission run <id>` against a real Hermes session; confirm `task.started` AuditEvent appears in `audit_events` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
