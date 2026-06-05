---
id: DIV-003
phase: 01-hermes-foundation-audit
friction: hermes-state-write-path
tier: plugin (parallel DB)
classification: ATLAS-only
status: RESOLVED — parallel DB pattern chosen
created: 2026-06-05
---

# DIV-003 — Hermes State Write Path

## Friction

ATLAS needs to link ATLAS Run records to Hermes session IDs so that audit trails can be correlated
with conversation history. `hermes_state.py` (`class SessionDB`) is a 180KB SQLite-backed store
with no public external write API for plugins.

## Cloned-Source Evidence

`hermes_state.py:346` defines `class SessionDB` (SQLite WAL mode, `state.db`). The class manages
messages, turns, and FTS5 search — all internal. Plugins have no `ctx.session_db` accessor or
write method.

However, every `post_tool_call` hook invocation receives `session_id` as a kwarg. Every
`on_session_start` / `on_session_end` hook receives session lifecycle context. ATLAS therefore
receives the session identifier at every observable event — sufficient to join records.

## Divergence Policy Analysis

- **Plugin (observation)**: ✅ `session_id` kwarg from hooks is sufficient to create a join key
  between ATLAS Run records and Hermes sessions. ATLAS maintains its own DB with a `hermes_session_id`
  column — no writes to `state.db` needed.
- **In-core edit**: Only required if ATLAS must **write** into Hermes's session history (e.g., inject
  ATLAS-generated messages into the conversation record). This is not a Phase 1–4 requirement.

## Decision

ATLAS maintains a separate Run DB (Phase 2 schema). The `hermes_session_id` field in ATLAS Run
records is populated from the `session_id` kwarg in `on_session_start` / `post_tool_call` hooks.
Correlation is a JOIN across two DBs — no writes to `state.db`, no Hermes fork.

**Classification:** ATLAS-only — parallel DB with session_id join. No Hermes core edit required.

## Phase 4 Action

- [ ] Implement `on_session_start` handler that creates ATLAS Run record with `hermes_session_id`
- [ ] Verify `session_id` kwarg is non-empty in `on_session_start` (vs populated only after first tool call)
