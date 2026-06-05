---
phase: 01-hermes-foundation-audit
requirement: FOUND-02
source_sha: e8b9369a9d2df36139a5055cae3ed3c15691e03e
created: 2026-06-05
---

# Hermes Foundation Audit — Extension Surface Analysis

Authoritative audit of `NousResearch/hermes-agent` at SHA `e8b9369a9d2df36139a5055cae3ed3c15691e03e`.
All verdicts are sourced directly from the cloned repository at `_EXTERNAL_REPOS/hermes-agent/`.

---

## Audit-Event Bus Attach Verdict

**YES — the ATLAS audit-event bus can attach via the Hermes plugin system WITHOUT editing `cli.py` or `run_agent.py`.**

Confirmed from cloned source: `hermes_cli/plugins.py` defines `VALID_HOOKS` (17 named hooks) and a
`PluginContext` facade. The `model_tools.py:851-860` dispatch loop fires `invoke_hook("post_tool_call", ...)`
after every tool call. A plugin at `~/.hermes/plugins/atlas_audit/` or installed via pip entry-point
with a `register(ctx)` function calling `ctx.register_hook("post_tool_call", cb)` + `ctx.register_hook("pre_tool_call", cb)` etc.
is sufficient to attach the audit bus to all tool-call, LLM-call, and session lifecycle events.

Reference implementation: `plugins/observability/langfuse/__init__.py` — registers the same hooks
(pre/post_tool_call, pre/post_api_request, pre/post_llm_call) for full observability tracing.

---

## Extension Surface Table

| Surface | File / Module | Attachment Mechanism | ATLAS Use Case | Friction | Verdict |
|---------|---------------|---------------------|----------------|----------|---------|
| **Hook system** | `hermes_cli/plugins.py` · `VALID_HOOKS` | `ctx.register_hook(hook_name, callback)` inside `register(ctx)` | AuditEvent bus — observe all tool calls, LLM calls, session events | None — 17 hooks cover all observable events | CLEAN via plugin |
| **Tool registry** | `tools/registry.py` · `registry.register(...)` | `ctx.register_tool(name, toolset, schema, handler, override=False)` | Register ATLAS-specific tools; optionally wrap existing tools with `override=True` | `override=True` replaces entire handler — no partial wrapping | CLEAN via plugin |
| **Session store** | `hermes_state.py` · `class SessionDB` | Read-only via hook kwargs (`session_id`); no public write API for plugins | Link ATLAS Run records to Hermes session_id; read conversation history | **In-core edit required for write path** — plugins cannot write to `state.db` directly | IN-CORE for writes · CLEAN for reads via hook kwargs |
| **Delegation / subagents** | `agent/auxiliary_client.py`; `subagent_stop` hook | `subagent_stop` hook fires when a spawned subagent terminates | Observe subagent completion events for ATLAS audit trail | No spawn-initiation hook — only termination observable via plugin | PARTIAL — termination only |
| **Cron jobs** | `hermes_cli/cron.py`; `cron/` | Config-file addition or `hermes cron` CLI (no code edit) | Schedule ATLAS maintenance tasks independently of Hermes core | None | CLEAN — no code edit |
| **Profiles** | `hermes_cli/profiles.py`; `~/.hermes/profiles/<name>/` | Profile-level config, skills, plugins, memories scoped per profile | Isolate ATLAS audit state per project/context | Plugin path is per-profile — ATLAS plugin must be installed in the active profile | CLEAN via profile config |
| **Gateway** | `hermes_cli/gateway.py`; `gateway/` directory | `pre_gateway_dispatch` hook — fires before auth/pairing/dispatch on each MessageEvent; can skip/rewrite/allow | Intercept or annotate gateway messages for ATLAS | Observers only from hook; deep gateway logic requires in-core edit | CLEAN via hook for observation/filtering |
| **MCP servers** | `hermes_cli/mcp_config.py`; `hermes_cli/mcp_catalog.py`; `optional-mcps/` | MCP config file (`~/.hermes/mcp_servers.yaml` or per-project) — no code edit | Register ATLAS as an MCP provider or consume external MCP tools | MCP server config is external — no Hermes core edits needed | CLEAN via config |
| **Plugin surface** | `hermes_cli/plugins.py` · `PluginContext` | `register(ctx)` entry point; discovery from 4 paths: bundled, user (`~/.hermes/plugins/`), project (`.hermes/plugins/`, requires `HERMES_ENABLE_PROJECT_PLUGINS=1`), pip entry-point | ATLAS audit plugin is the primary integration vector | Project plugin path needs env var; user path (`~/.hermes/plugins/`) works without it | CLEAN — use user path or pip entry-point |
| **CLI/TUI boundary** | `hermes_cli/main.py` (554 KB); `hermes_cli/curses_ui.py` | No plugin hook at CLI boundary; `on_session_start` / `on_session_end` hooks cover session lifecycle | Monitor session start/end for audit records | No keystroke-level or prompt-render hook — session lifecycle via hooks is sufficient for ATLAS | CLEAN via session lifecycle hooks |

---

## VALID_HOOKS (complete list from `hermes_cli/plugins.py:128-168`)

```python
VALID_HOOKS = {
    "pre_tool_call",           # Before any tool executes — can return block dict to veto
    "post_tool_call",          # After tool completes — receives tool_name, args, result, task_id, session_id, tool_call_id, duration_ms
    "transform_terminal_output",
    "transform_tool_result",   # Post-tool result transform — return string to replace result
    "transform_llm_output",    # Transform LLM response text before returning to user
    "pre_llm_call",            # Before LLM API call — can inject ephemeral context
    "post_llm_call",
    "pre_api_request",         # Per API call (preferred over pre_llm_call for rate-limiting)
    "post_api_request",
    "on_session_start",        # Session lifecycle
    "on_session_end",
    "on_session_finalize",
    "on_session_reset",
    "subagent_stop",           # Fires when a spawned subagent terminates
    "pre_gateway_dispatch",    # Gateway: fires per MessageEvent before auth/dispatch
    "pre_approval_request",    # Approval lifecycle — observer only
    "post_approval_response",  # Approval lifecycle — observer only
}
```

---

## VERIFY-AT-EXECUTION Items — Resolved

| Item | Research Claim | Cloned-Source Resolution | ATLAS Impact |
|------|----------------|--------------------------|--------------|
| **System prompt augmentation** | UNKNOWN — likely in-core edit | CONFIRMED in-core. `agent/system_prompt.py` builds the prompt from config + context files + soul. The `pre_llm_call` hook adds only ephemeral (per-turn) context. Persistent system prompt injection requires editing `agent/system_prompt.py`. | DIV-001: in-core edit required; classify per divergence policy |
| **Artifact capture** | UNKNOWN — no `post_artifact` hook | CONFIRMED no dedicated artifact hook. Artifacts are created via tool calls (e.g. Write, Edit). ATLAS must identify artifact-creation tools by name in `post_tool_call.tool_name`. Tool wrapping via `ctx.register_tool(..., override=True)` is also viable but replaces the full handler. | DIV-002: use `post_tool_call` name-filtering; no in-core edit needed |
| **hermes_state.py write path** | LIKELY in-core edit | CONFIRMED in-core for writes. `SessionDB` (SQLite WAL) has no public external write API. Plugins receive `session_id` as a kwarg from hooks — sufficient to join ATLAS records to Hermes sessions in a parallel DB without touching `state.db`. | DIV-003: ATLAS maintains own Run DB; joins on `session_id` kwarg. No in-core edit needed |
| **Turn ID / request ID propagation** | Assumed `turn_id` + `api_request_id` in `post_tool_call` | CORRECTED. Actual `post_tool_call` kwargs (`model_tools.py:852-860`): `tool_name`, `args`, `result`, `task_id`, `session_id`, `tool_call_id`, `duration_ms`. No `turn_id` or `api_request_id`. AuditEvent correlation must use `task_id` (not `turn_id`). | DIV-004: ATLAS AuditEvent schema uses `task_id` as correlation key; `turn_id` column will map to `task_id` value |

---

## Plugin Discovery Paths (from `hermes_cli/plugins.py:1055-1100`)

| Priority | Path | Condition |
|----------|------|-----------|
| 4 (lowest) | Bundled `plugins/` in hermes-agent repo | Always loaded |
| 3 | `~/.hermes/plugins/` (user plugins) | Always loaded — **recommended ATLAS install path** |
| 2 | `./.hermes/plugins/` (project plugins) | Requires `HERMES_ENABLE_PROJECT_PLUGINS=1` env var |
| 1 (highest) | pip / entry-point (`hermes_agent.plugins` group) | Installed package; best for stable distribution |

Recommendation: Install ATLAS audit plugin at `~/.hermes/plugins/atlas_audit/` (user path, no env var needed) during Phase 4.

---

## Friction Points → Divergence Stubs (FOUND-03 input)

| ID | Friction | Tier per Divergence Policy | Decision |
|----|----------|---------------------------|----------|
| DIV-001 | System prompt augmentation requires editing `agent/system_prompt.py` | in-core edit (ATLAS-only) | Stub → docs/decisions/DIV-001-system-prompt-augmentation.md |
| DIV-002 | Artifact capture has no dedicated hook; must filter `post_tool_call.tool_name` | plugin (no in-core edit) | Stub → docs/decisions/DIV-002-artifact-capture.md |
| DIV-003 | `hermes_state.py` write path: no plugin API; ATLAS uses parallel DB with `session_id` join | plugin (parallel DB) | Stub → docs/decisions/DIV-003-hermes-state-write-path.md |
| DIV-004 | `post_tool_call` emits `task_id` not `turn_id`; schema must adapt | plugin-observable (ATLAS-only schema) | Stub → docs/decisions/DIV-004-turn-id-propagation.md |
