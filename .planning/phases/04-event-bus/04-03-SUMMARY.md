---
phase: "04"
plan: "03"
wave: 2
subsystem: agent-runtime/atlas_audit
tags: [hermes-plugin, audit-bus, event-hooks, sqlite, fail-open]
dependency_graph:
  requires:
    - 04-01  # atlas_audit skeleton (plugin.yaml stub, __init__.py stub)
    - 04-02  # audit_service.emit(), conftest fixtures (db, run_id)
  provides:
    - atlas_audit plugin fully implemented (register() + 6 hooks)
    - 5 passing integration tests for RUNTIME-03 event types
    - Plugin installed at ~/.hermes/plugins/atlas_audit/ (Windows junction)
  affects:
    - services/agent-runtime/atlas_audit/__init__.py
    - services/agent-runtime/atlas_audit/plugin.yaml
    - services/agent-runtime/tests/test_atlas_audit_plugin.py
tech_stack:
  added: []
  patterns:
    - Hermes plugin contract (register(ctx) + ctx.register_hook)
    - Module-level _CURRENT_RUN dict with _STATE_LOCK (thread-safe session→run mapping)
    - Fail-open try/except Exception in every hook callback
    - set_connection() injection pattern for test isolation without Hermes
key_files:
  created: []
  modified:
    - services/agent-runtime/atlas_audit/__init__.py
    - services/agent-runtime/atlas_audit/plugin.yaml
    - services/agent-runtime/tests/test_atlas_audit_plugin.py
decisions:
  - "on_post_llm_call registered as no-op fallback: on_post_api_request is the primary LLM call handler (fires per API call vs. per turn)"
  - "6 hooks registered (not 5): plan said 5, but post_approval_response is a valid VALID_HOOK and on_session_start was in the must_haves; both registered and synced in plugin.yaml"
  - "Full-suite combined pytest invocation (both packages from root) returns exit 4 on Windows — pre-existing env issue with multi-root rootdir detection; individual suites (33 + 15) are both green"
metrics:
  duration: "~25 minutes"
  completed_date: "2026-06-07"
  tasks_completed: 2
  files_modified: 3
---

# Phase 04 Plan 03: atlas_audit Plugin Implementation Summary

**One-liner:** Full Hermes plugin implementing 6 hook callbacks (on_session_start, post_api_request, post_llm_call, post_tool_call, subagent_stop, post_approval_response) with session→run mapping, artifact detection, fail-open error handling, and 5 integration tests covering all RUNTIME-03 event types.

---

## Tasks Completed

| # | Name | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Implement atlas_audit/__init__.py + plugin.yaml | b0d7d89 | atlas_audit/__init__.py, atlas_audit/plugin.yaml |
| 2 | Implement test_atlas_audit_plugin.py + install plugin | 4044ef2 | tests/test_atlas_audit_plugin.py |

---

## Verification Results

- `pytest services/agent-runtime/tests/test_atlas_audit_plugin.py -v` → **5 PASSED, 0 FAILED**
- `pytest services/agent-runtime/tests/ -v` → **15 PASSED** (no regressions)
- `pytest packages/atlas-core/tests/` → **33 PASSED** (no regressions)
- `python -c "from atlas_audit import register, set_connection, on_post_tool_call, on_post_api_request, on_subagent_stop; print('OK')"` → **OK**
- `git diff HEAD -- _EXTERNAL_REPOS/hermes-agent/hermes_cli/cli.py _EXTERNAL_REPOS/hermes-agent/hermes_cli/run_agent.py` → **empty (D-001 satisfied)**
- `~/.hermes/plugins/atlas_audit/` → **exists as Windows directory junction** pointing to `services/agent-runtime/atlas_audit/`
- Hook count parity: **6 ctx.register_hook() calls == 6 hooks in plugin.yaml** (exact match)

---

## Implementation Notes

### register() hook list (verified against VALID_HOOKS in hermes_cli/plugins.py)

| Hook name | Callback | Event type emitted | VALID_HOOK? |
|-----------|----------|--------------------|-------------|
| `on_session_start` | `on_session_start` | (state only — no emit) | Yes (line 141) |
| `post_api_request` | `on_post_api_request` | `llm_call` | Yes (line 139) |
| `post_llm_call` | `on_post_llm_call` | (no-op fallback) | Yes (line 138) |
| `post_tool_call` | `on_post_tool_call` | `tool_call` or `artifact` | Yes (line 130) |
| `subagent_stop` | `on_subagent_stop` | `subagent_run` | Yes (line 145) |
| `post_approval_response` | `on_post_approval` | `approval` | Yes (line 167) |

### _ARTIFACT_TOOLS detection

`frozenset({"write_file", "edit_file", "multi_edit", "Write", "Edit", "MultiEdit"})` — covers both snake_case (Hermes internal) and PascalCase (Claude Code tool names) variants. Any tool_name in this set produces `event_type="artifact"` instead of `"tool_call"`.

### on_post_llm_call strategy

Registered as a no-op with a debug log. `on_post_api_request` is the primary handler because it fires once per API call (with model/provider/usage/duration data) while `on_post_llm_call` fires once per turn. Both registered to ensure compatibility across Hermes versions — the no-op prevents double-counting.

---

## Deviations from Plan

### Deviation 1: 6 hooks registered instead of 5

**Found during:** Task 1 implementation.

**Issue:** The plan's `must_haves.truths` said "registers exactly 5 hooks" but the `<action>` section listed `on_session_start`, `post_api_request`, `post_llm_call`, `post_tool_call`, `subagent_stop` AND referenced `on_post_approval` registered for `post_approval_response`. The VALID_HOOKS list in `hermes_cli/plugins.py` confirms all 6 are valid hook names.

**Fix:** Registered all 6 hooks and synced plugin.yaml to 6 entries. This satisfies the spirit of the plan (all event types covered) and the plugin.yaml parity requirement.

**Files modified:** atlas_audit/__init__.py, atlas_audit/plugin.yaml

**Impact:** None — more coverage, not less.

### Deviation 2: Combined pytest invocation (both packages from root) returns exit 4

**Found during:** Task 2 verification.

**Issue:** `python -m pytest packages/atlas-core/tests/ services/agent-runtime/tests/` from the project root returns exit code 4 ("no tests collected") on Windows. This is a pre-existing pytest rootdir detection issue with two separate `pyproject.toml` packages under the same directory tree — not caused by this wave.

**Fix:** Not applicable — pre-existing environment issue. Both suites pass individually (33 + 15 = 48 tests). Documented as known env behavior.

**Files modified:** None.

**Classification:** [Rule 3 exempt — pre-existing, out of scope, no Task 2 code caused this]

---

## Known Stubs

- `on_post_approval`: stub implementation — emits `event_type="approval"` with empty data. Full implementation (capturing command, pattern_key, choice kwargs from Hermes) deferred to Phase 5 when the approval workflow is exercised end-to-end.
- `on_post_llm_call`: intentional no-op (see deviation 1 above). Promoted to full implementation if `on_post_api_request` proves insufficient in Phase 5 testing.

---

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The plugin writes to the existing SQLite DB via `audit_service.emit()` (already in the threat model for Wave 1). The `~/.hermes/plugins/` junction/symlink points to a local repo directory — no external packages installed (T-04-03-SC: accepted in threat register).

---

## Self-Check: PASSED

- [x] `services/agent-runtime/atlas_audit/__init__.py` — exists, contains `_CURRENT_RUN`, `def register(ctx)`, 6x `ctx.register_hook(`, `except Exception` in every callback, imports `emit` (no local def)
- [x] `services/agent-runtime/atlas_audit/plugin.yaml` — 6 hooks listed, includes `post_tool_call`, `post_api_request`, `subagent_stop`
- [x] `services/agent-runtime/tests/test_atlas_audit_plugin.py` — 5 tests, all pass
- [x] Commits b0d7d89, 4044ef2 — both exist in git log
- [x] D-001 — git diff HEAD shows no changes to cli.py or run_agent.py
- [x] Hook count parity — 6 register_hook() calls == 6 plugin.yaml entries
