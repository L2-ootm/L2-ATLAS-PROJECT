---
id: DIV-002
phase: 01-hermes-foundation-audit
friction: artifact-capture
tier: plugin
classification: plugin-tool
status: PENDING — deferred to Phase 4 implementation
created: 2026-06-05
---

# DIV-002 — Artifact Capture

## Friction

ATLAS RUNTIME-03 requires AuditEvents for artifact creation (files written, code executed, etc.).
There is no dedicated `post_artifact` hook in Hermes VALID_HOOKS.

## Cloned-Source Evidence

Artifacts are created by specific tool calls (e.g., `Write`, `Edit`, `code_execution_tool`). The
`post_tool_call` hook in `model_tools.py:851-860` fires after every tool dispatch and provides:
`tool_name`, `args`, `result`, `task_id`, `session_id`, `tool_call_id`, `duration_ms`.

An artifact-creation event is fully observable by filtering on `tool_name` in the `post_tool_call`
callback — no additional hook is needed.

Alternative: `ctx.register_tool(name, ..., override=True)` wraps the entire handler, but this
replaces the built-in implementation and requires maintaining the full tool proxy — higher
maintenance cost with no benefit over name-filtering.

## Divergence Policy Analysis

- **Plugin (hook)**: ✅ `post_tool_call` name-filter is sufficient. This is the least-invasive
  approach and matches the Langfuse observability plugin pattern exactly.
- **Tool override**: Viable but over-engineered for a pure observation use case.
- **In-core edit**: Not required.

## Decision

ATLAS audit plugin registers `post_tool_call` and maintains an internal set of artifact-tool names
(`{"Write", "Edit", "code_execution_tool", ...}`). When `tool_name` matches, the callback emits
an `AuditEvent(type="artifact_created", ...)` with args and result.

**Classification:** plugin-tool — pure observation via existing hook, no Hermes core edit.

## Phase 4 Action

- [ ] Define the canonical set of artifact-creating tool names (source from `tools/registry.py`)
- [ ] Implement `on_post_tool_call` in the ATLAS audit plugin with artifact name-filter
- [ ] Write test asserting AuditEvent fires on Write/Edit tool calls
