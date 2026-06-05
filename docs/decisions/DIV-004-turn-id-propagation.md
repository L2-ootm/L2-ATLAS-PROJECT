---
id: DIV-004
phase: 01-hermes-foundation-audit
friction: turn-id-propagation
tier: plugin (ATLAS-only schema)
classification: ATLAS-only
status: RESOLVED — use task_id as correlation key
created: 2026-06-05
---

# DIV-004 — Turn ID and Request ID Propagation

## Friction

ATLAS AuditEvent schema references a `turn_id` field to correlate tool calls within a conversation
turn. The RESEARCH.md assumed `post_tool_call` would provide `turn_id` and `api_request_id` kwargs.

## Cloned-Source Evidence

Actual `post_tool_call` invocation in `model_tools.py:852-860`:

```python
invoke_hook(
    "post_tool_call",
    tool_name=function_name,
    args=function_args,
    result=result,
    task_id=task_id or "",
    session_id=session_id or "",
    tool_call_id=tool_call_id or "",
    duration_ms=duration_ms,
)
```

No `turn_id` or `api_request_id` kwargs exist. Available correlation keys are:
- `task_id` — the active task identifier (maps to what ATLAS called "turn_id")
- `session_id` — the session identifier
- `tool_call_id` — the specific tool call ID within the turn

## Divergence Policy Analysis

- **Plugin (ATLAS schema adaptation)**: ✅ ATLAS renames its `turn_id` schema field to `task_id`
  (or maps `task_id` → `turn_id` at the AuditEvent layer). No Hermes change needed.
- **In-core edit**: Not required — Hermes already provides `task_id` as the turn-level correlation key.

## Decision

ATLAS AuditEvent schema uses `task_id` as the turn-level correlation key (not `turn_id`). The
`turn_id` column in the Phase 2 schema is renamed to `task_id` or stores the `task_id` value.
`tool_call_id` provides call-level granularity within a turn.

**Classification:** ATLAS-only schema correction — no Hermes core edit.

## Phase 2 Action

- [ ] Update AuditEvent Pydantic model: `task_id: str` (maps from `post_tool_call` kwargs)
- [ ] Update AuditEvent Pydantic model: `tool_call_id: str` for sub-turn granularity
- [ ] Remove `turn_id` and `api_request_id` fields from Phase 2 schema (were based on incorrect assumption)
