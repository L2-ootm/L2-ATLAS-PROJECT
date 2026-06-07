# Phase 04 State Review — ATLAS Event Bus & Audit Core

**Date:** 2026-06-07  
**Reviewer:** ATLAS/Hermes independent pass  
**Scope:** Phase 04 completion state, planning artifacts, git state, tests, and targeted manual probes.

## Verdict

**Conditional pass with one closure blocker found in manual probing.**

The committed Phase 04 implementation is structurally strong: service + plugin exist, the code review blockers appear addressed, and the local test suites pass. However, a targeted probe found that secret redaction can produce invalid JSON inside `AuditEvent.data` for JSON-key secrets because the replacement removes JSON value quotes.

This should be fixed before Phase 05 relies on audit payloads as a stable contract.

## Evidence

### Git state

Latest Phase 04 commit:

```text
a06663d chore(phase-04): mark complete — 15 tests green, 7/7 success criteria verified
```

Working tree is not clean. Current unrelated/uncommitted items include:

```text
 M .gitignore
 M README.md
 M docs/architecture/SYSTEM_OVERVIEW.md
 M docs/research/DEEP_RESEARCH_BACKLOG.md
?? .planning/phases/03-research-closure/03-01-SUMMARY.md
?? .planning/phases/03-research-closure/03-02-SUMMARY.md
?? .planning/phases/04-event-bus/04-PATTERNS.md
?? docs/decisions/D-014-turbovec-local-semantic-retrieval-spike.md
?? docs/research/2026-06-06_TURBOVEC_LOCAL_RETRIEVAL_SPIKE.md
```

### Tests rerun

From `services/agent-runtime`:

```text
python -m pytest tests/ -q
15 passed in 0.05s
```

From `packages/atlas-core`:

```text
python -m pytest tests/ -q
33 passed in 0.07s
```

## Phase 04 success criteria status

| Criterion | Status | Notes |
|---|---:|---|
| Event bus service exists | Pass | `atlas_runtime/audit_service.py` provides `emit`, `get_events_for_run`, `export_jsonl`. |
| Tool call writes AuditEvent + ToolCall | Pass | Covered by tests and plugin probe. |
| LLM call writes AuditEvent | Pass | Covered by tests. |
| Ordered events retrieval | Pass | Covered by tests. |
| JSONL export | Pass | Export string ends with newline in current implementation. |
| Transactional writes / no orphan on invalid event type | Pass | Covered by tests. |
| No Hermes core edits | Pass based on reported verification | No direct Phase 04 core edits observed in review artifacts. |

## Closure blocker

### B-04-01 — Redaction breaks JSON validity for JSON-key secret values

Manual probe:

```python
emit(conn, lock, run_id='r1', event_type='llm_call', data={
    'token': 12345,
    'secret': None,
    'password': True,
    'ok': 'x',
})
```

Stored row observed:

```text
{"token": [REDACTED], "secret": [REDACTED], "password": [REDACTED], "ok": "x"}
```

This is **not valid JSON** because `[REDACTED]` is not quoted. The issue applies to quoted string secrets too, because the second regex captures the full JSON value including quotes:

```python
re.compile(r'(?i)"(token|api[_-]?key|secret|password)"\s*:\s*("[^"]*"|\d+|null|true|false)')
```

Then `_replace_group2()` replaces group 2 with the bare string `[REDACTED]`.

Impact:

- `AuditEvent.data` is documented as a JSON string.
- Future Phase 05/07 consumers may parse `data` and fail.
- Current tests only assert the raw secret is absent and `[REDACTED]` appears; they do not parse the stored `data` JSON.

Required fix:

- For JSON key-value redaction, replace the value with a quoted JSON string: `"[REDACTED]"`.
- Add a regression test that does:

```python
stored = db.execute("SELECT data FROM audit_events").fetchone()[0]
parsed = json.loads(stored)
assert parsed["token"] == "[REDACTED]"
```

Also test string, numeric, null, and boolean secret values.

## Carry-forward notes

- `post_llm_call` remains a documented no-op. Acceptable for Phase 04 if `post_api_request` is the intended primary LLM event source, but Phase 05 should prove that the real Hermes path fires the expected hook in an end-to-end run.
- `register(ctx, conn=None)` still depends on Phase 05 lifecycle to call `set_connection()` or pass `conn`; acceptable as a Phase 05 integration responsibility, but must be explicitly included in Phase 05 success tests.
- Working tree has unrelated/uncommitted docs/research artifacts. Clean or intentionally commit/stash before Phase 05 to keep review boundaries clear.

## Recommendation

Do not start Phase 05 execution until B-04-01 is fixed and covered by tests. After that, Phase 04 can be treated as complete and ready as the audit foundation for Mission & Run Lifecycle.
