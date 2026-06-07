---
phase: 4
slug: event-bus
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-07
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `services/agent-runtime/pyproject.toml` (created Wave 0) |
| **Quick run command** | `pytest services/agent-runtime/tests/ -x -q` |
| **Full suite command** | `pytest packages/atlas-core/tests/ services/agent-runtime/tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest services/agent-runtime/tests/ -x -q`
- **After every plan wave:** Run `pytest packages/atlas-core/tests/ services/agent-runtime/tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-scaffold | 01 | 0 | RUNTIME-03 | — | N/A | infra | `pytest services/agent-runtime/tests/ -x -q` | ❌ W0 | ⬜ pending |
| 04-emit-tool-call | 02 | 1 | RUNTIME-03 | T-V5 | Pydantic validates event_type; invalid literal raises before DB write | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_emit_tool_call -x` | ❌ W0 | ⬜ pending |
| 04-emit-llm-call | 02 | 1 | RUNTIME-03 | T-V5 | Pydantic validates event_type; secret patterns redact data before persist | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_emit_llm_call -x` | ❌ W0 | ⬜ pending |
| 04-emit-artifact | 02 | 1 | RUNTIME-03 | — | N/A | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_emit_artifact -x` | ❌ W0 | ⬜ pending |
| 04-redaction | 02 | 1 | RUNTIME-03 | T-V5 | JSON key-value patterns (token, api_key, secret, password) redacted before persistence | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_redaction -x` | ❌ W0 | ⬜ pending |
| 04-partial-failure | 02 | 1 | RUNTIME-03 | T-V5 | Partial failure (invalid event_type) does not persist orphaned row | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_emit_invalid_type -x` | ❌ W0 | ⬜ pending |
| 04-get-events | 03 | 2 | AUDIT-01 | — | N/A | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_get_events_ordered -x` | ❌ W0 | ⬜ pending |
| 04-export-jsonl | 03 | 2 | AUDIT-02 | — | N/A | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_export_jsonl -x` | ❌ W0 | ⬜ pending |
| 04-plugin-hooks | 04 | 2 | RUNTIME-03 | T-V7 | Hook callbacks never re-raise; log on failure only | unit | `pytest services/agent-runtime/tests/test_atlas_audit_plugin.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/agent-runtime/pyproject.toml` — package scaffold with `atlas-core` editable dep
- [ ] `services/agent-runtime/tests/__init__.py` — empty init
- [ ] `services/agent-runtime/tests/conftest.py` — `db` fixture (mirror Phase 2 pattern, 3 `.parent` hops), `run_id` fixture
- [ ] `services/agent-runtime/tests/test_audit_service.py` — stub tests covering RUNTIME-03, AUDIT-01, AUDIT-02 (all marked `xfail` or skip until impl)
- [ ] `services/agent-runtime/tests/test_atlas_audit_plugin.py` — stub tests for plugin hook callbacks

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| No in-core edits to Hermes cli.py or run_agent.py | RUNTIME-03 (SC-7) | Verified by git diff, not by test | `git diff HEAD _EXTERNAL_REPOS/hermes-agent/cli.py _EXTERNAL_REPOS/hermes-agent/hermes_cli/run_agent.py` must show no changes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
