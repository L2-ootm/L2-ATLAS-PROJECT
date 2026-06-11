# Hermes Infrastructure Consolidation Audit for ATLAS

**Date:** 2026-06-08
**Phase:** 4.5 — Native Cockpit Pillar Consolidation (extended)
**Hermes pin:** SHA `e8b9369a9d2df36139a5055cae3ed3c15691e03e` (`_EXTERNAL_REPOS/hermes-agent`)
**Audit scope:** Provider/model infrastructure, credential handling, skills/tools/plugins, runtime patterns, and ATLAS adaptation boundaries.

---

## Purpose

ATLAS is built on Hermes as its execution foundation. This audit answers: which Hermes infrastructure components can ATLAS use directly, which must be wrapped in ATLAS terms, which should be rewritten into ATLAS core, and which should remain external.

The audit covers infrastructure, not the AI agent loop itself. The agent loop (AIAgent, run_agent, cli.py) is out of scope — it is used as-is via the plugin/hook surface established in Phase 1 (see `docs/research/HERMES_FOUNDATION_AUDIT.md`).

---

## 1. Provider/Model Registry

### What Hermes provides

Hermes has a multi-transport provider system centered on `agent/transports/`:

- `base.py` — `ProviderTransport` ABC with four abstract methods: `api_mode`, `convert_messages`, `convert_tools`, `build_kwargs`, `normalize_response`.
- `anthropic.py` — Anthropic Messages API transport.
- `bedrock.py` — AWS Bedrock transport.
- `codex.py` — OpenAI Codex/o-series transport.
- `types.py` — `NormalizedResponse` shared type.

Model selection is driven by the `model` config object: `model.name`, `model.provider`, `model.api_mode`, `model.base_url`, `model.api_key`. Setting `model.provider = "custom"` and `model.base_url = "http://127.0.0.1:PORT/v1"` is the hook for custom OpenAI-compatible endpoints (including FreeLLMAPI).

Model capability metadata (context length, vision, tool-calling, modalities) is not centrally registered in a queryable registry in the inspected Hermes version — it is embedded per-transport.

### ATLAS adaptation verdict

| Hermes component | ATLAS action | Rationale |
|-----------------|--------------|-----------|
| `ProviderTransport` ABC | **Use directly** | Clean abstraction. ATLAS custom providers extend it. |
| `anthropic.py`, `bedrock.py`, `codex.py` transports | **Use directly** | Proven implementations. Do not rewrite. |
| Custom OpenAI-compatible endpoint (`model.base_url`) | **Use directly** | Already the FreeLLMAPI integration path. |
| Implicit model metadata (per-transport) | **Wrap / extend** | ATLAS needs a queryable model registry with policy labels. Add `atlas_core.model_registry` on top. |
| Model selection by name only | **Wrap** | ATLAS should route by task class + policy, not hardcoded names. The registry handles this. |

---

## 2. OAuth / API-Key Auth Handling

### What Hermes provides

`agent/credential_sources.py` defines a unified `RemovalStep`/`RemovalResult` pattern for the Hermes credential pool. Supported credential sources at the inspected SHA:

| Source ID | Description |
|-----------|-------------|
| `env:<VAR>` | `os.environ` or `~/.hermes/.env` |
| `claude_code` | `~/.claude/.credentials.json` |
| `hermes_pkce` | `~/.hermes/.anthropic_oauth.json` (OAuth PKCE) |
| `device_code` | `auth.json` providers: `openai-codex`, `nous`, others |
| `qwen-cli` | `~/.qwen/oauth_creds.json` |
| `gh_cli` | `gh auth token` (GitHub Copilot) |
| `config:<name>` | Custom provider config entry |
| `model_config` | `model.api_key` when `model.provider == "custom"` |
| `manual` | `hermes auth add` |

`agent/credential_persistence.py` handles storage/retrieval of credentials across sessions.

OAuth flows present: Anthropic PKCE, OpenAI Codex device_code, Qwen OAuth. These are implemented in `agent/transports/codex.py` (Codex OAuth) and analogous modules.

`azure_identity_adapter.py` provides Azure Entra ID / workload identity integration.

### ATLAS adaptation verdict

| Hermes component | ATLAS action | Rationale |
|-----------------|--------------|-----------|
| `env:` and `config:` sources | **Use directly** | Standard env/config loading; no ATLAS-specific concern. |
| `model_config` source | **Use directly** | This is how FreeLLMAPI sidecar key is injected. |
| `claude_code` credential bridge | **Use directly** | Lets ATLAS reuse the operator's existing Claude Code auth. |
| `hermes_pkce` / `device_code` OAuth | **Use as-is for now; wrap later** | Useful for Codex/OpenCode discovery. Wrap only when ATLAS needs to surface auth state in the cockpit UI. |
| `qwen-cli`, `gh_cli` | **Use as-is** | Niche but non-harmful. Do not remove. |
| `azure_identity_adapter` | **Keep external** | ATLAS v1.0 is local-operator-first. Azure identity is enterprise scope. Keep available but do not depend on it. |
| Credential persistence (`~/.hermes/`) | **Reuse path** | ATLAS should not create a competing credential store. Use Hermes' path for now; migrate to OS keychain (Tauri) when the native cockpit is built. |
| Full credential pool semantics | **Wrap in ATLAS provider auth layer** | ATLAS needs to query: "is provider X authenticated?", "what models can I access?". The raw pool is sufficient for now; a clean query API is needed by Phase 7. |

---

## 3. Credential Pool

### What Hermes provides

The credential pool (`agent/credential_pool`) seeds from all registered sources above. It is loaded at agent startup and refreshed on explicit auth events.

Key behavior:
- Pool entries are `(provider, source_id, token_value, metadata)` tuples.
- `load_pool()` runs all seed functions and deduplicates.
- `suppress_credential_source(provider, source_id)` persists a suppression flag so a removed credential stays removed across restarts.
- No central query API for "which providers are currently authenticated?" — callers iterate the pool.

### ATLAS adaptation verdict

| Concern | Action |
|---------|--------|
| Pool loading | **Use as-is** — Phase 5 and Phase 7 can depend on it unchanged. |
| "Which providers are authenticated?" query | **Add ATLAS wrapper** — `atlas_core.provider_status.get_authenticated_providers()` iterates the pool and returns a structured list. This is needed for the cockpit settings surface and the model registry. |
| Pool exposure to cockpit | **Never expose raw pool to webview** — the cockpit queries `GET /providers/status` (Phase 7 API). Provider auth is internal. |

---

## 4. Custom OpenAI-Compatible Endpoint Support

### What Hermes provides

When `model.provider == "custom"` and `model.base_url` is set, Hermes calls the endpoint as an OpenAI-compatible API using the standard `openai` Python client. The `model.api_key` from `model_config` credential source is used.

This is exactly the FreeLLMAPI integration path.

### ATLAS adaptation verdict

**Use directly.** No rewrite needed. ATLAS adds:

1. Config fields in `atlas-runtime`:
   - `free_gateway.enabled: bool`
   - `free_gateway.base_url: str` (default `http://127.0.0.1:3001/v1`)
   - `free_gateway.api_key_env: str` (env var name holding the sidecar unified key)
   - `free_gateway.allowed_task_classes: list[str]`
2. Health probe before routing (check `/v1/models` reachability).
3. Task class routing logic that selects `free_gateway` only for `free-tier-ok` tasks.

---

## 5. Model Selection and Configuration

### What Hermes provides

Model is configured per-profile via `model.name`, `model.provider`, `model.api_mode`, etc. There is no dynamic model registry with capability tags or policy labels. Model is essentially a static config at runtime startup.

`agent/models_dev.py` exists but is development/debug tooling, not a production registry.

### ATLAS adaptation verdict

| Gap | Action |
|-----|--------|
| Static model config only | **Extend with ATLAS model registry** — `atlas_core.model_registry` holds a queryable list of available models with: name, provider, source (config/discovered/free-tier), policy_labels, context_length, capability flags. |
| No dynamic discovery | **Add discovery layer** — populated from: (a) configured providers, (b) FreeLLMAPI `/v1/models`, (c) future Codex/Kilo catalogs. |
| No task-class routing | **Add routing layer** — `atlas_core.model_router.select(task_class, budget_tier, policy)` returns the best available model. |

---

## 6. Delegation Model Overrides

### What Hermes provides

Hermes delegation creates subagent sessions with isolated profiles. Each subagent can override: `model`, `model_name`, `allowed_tools`, `tool_budget`, `max_agent_iterations`. The delegation call is `agent.delegate(...)` and the result is tracked in the parent session.

### ATLAS adaptation verdict

**Use directly.** ATLAS `subagent_service.py` (Phase 5) already wraps this. The model override path allows ATLAS to route subagents to cheaper models for `free-tier-ok` work — this integrates with the model router.

No rewrite needed. The Phase 5 subagent AuditEvent already records model, tool allowlist, and token budget.

---

## 7. Profiles

### What Hermes provides

Profiles isolate: session history, memory/wiki, skills, cron jobs, gateway config, model config. Each profile has its own `~/.hermes/profiles/<name>/` directory. Multi-profile is production-proven.

### ATLAS adaptation verdict

**Use directly for ATLAS workspaces.** ATLAS workspace concept (mission workspace, environment policy) maps cleanly to Hermes profiles. One ATLAS workspace = one Hermes profile.

Phase 5 policy.py workspace boundary check should verify the active profile matches the workspace before executing shell/file operations.

---

## 8. Toolsets

### What Hermes provides

Toolsets are declared subsets of available tools. An agent can be restricted to a toolset at delegation time. Built-in toolsets include: read-only, file-write-limited, no-shell, etc. Custom toolsets are configurable.

### ATLAS adaptation verdict

**Use directly.** ATLAS capability tiers map to Hermes toolsets:

| ATLAS tier | Hermes toolset |
|-----------|---------------|
| Read | read-only toolset |
| Operator | default operator toolset (read + file write + git) |
| Shell | shell-enabled toolset |
| Network | network-enabled toolset |

The Phase 8 approval surface should show which toolset the agent is requesting to operate in.

---

## 9. Skills Lifecycle

### What Hermes provides

Skills are the Hermes equivalent of slash commands / task templates. Skills have: name, description, system prompt, tool restrictions, model overrides, triggers. They can be loaded from files, plugins, or the built-in registry.

`agent/skill_bundles.py` and `agent/skill_preprocessing.py` handle skill loading and parameter injection.

### ATLAS adaptation verdict

**Use directly.** Phase 9 (Skill Inventory & Classification) classifies and curates the skill pack. No skills infrastructure rewrite is needed. ATLAS adds:

- Skill metadata: policy class, public_safe flag, autonomy_level, risk.
- Skill allowlist per ATLAS workspace policy.
- Skill invocation is recorded as an AuditEvent of kind `skill_invoked`.

---

## 10. Plugins and MCP

### What Hermes provides

Hermes has a plugin system (see Phase 1 audit: `docs/research/HERMES_FOUNDATION_AUDIT.md`). The ATLAS audit plugin (`atlas_audit`) was built in Phase 4 using this surface. MCP (Model Context Protocol) tool servers are also supported via `agent/transports/hermes_tools_mcp_server.py`.

### ATLAS adaptation verdict

**Use directly.** ATLAS extends Hermes via plugins (Phase 4 pattern), not by modifying Hermes core. MCP server support can be used to expose ATLAS wiki/mission data to the agent context without internal coupling.

---

## 11. Cron

### What Hermes provides

`cron/` module provides profile-scoped cron job scheduling. Each job has: schedule expression, skill or task to invoke, profile context. Jobs persist across restarts.

### ATLAS adaptation verdict

**Use directly for scheduled mission triggers.** ATLAS cron missions (recurring intelligence runs, scheduled wiki updates) can be implemented as Hermes cron jobs targeting ATLAS skills.

Audit requirement: each cron trigger must emit an AuditEvent of kind `cron_trigger` before the skill executes.

---

## 12. Gateway Adapters

### What Hermes provides

`gateway/` module provides inbound message platform integrations: DingTalk, email, Feishu, Microsoft Graph webhook, QQ Bot, Home Assistant, Signal, etc.

These are external message channels feeding agent tasks. Not related to the AI provider gateway.

### ATLAS adaptation verdict

**Keep external / defer.** ATLAS v1.0 does not need channel gateway integrations. The gateway module should not be imported or depended on in ATLAS core until Phase 10+ (Pulse/CRM).

Do not remove — Hermes has it, and it will be available for later phases.

---

## 13. Session Store and Search

### What Hermes provides

Hermes session store holds: conversation history, tool call results, memory summaries, file attachments. Session search (`agent/context_references.py`) provides retrieval over session history.

### ATLAS adaptation verdict

**Use directly, but add ATLAS AuditEvent bridge.** The session store is the agent's working memory. ATLAS does not need to reimplement it.

ATLAS adds: after each significant session event (tool call, summary, error), write a corresponding AuditEvent to the ATLAS database. The session store is ephemeral; the audit log is permanent.

---

## 14. Memory

### What Hermes provides

Hermes memory (`agent/insights.py`, memory summary logic) produces condensed session summaries stored per-profile. Long-context session history is compacted into memory summaries that are injected into new sessions.

### ATLAS adaptation verdict

**Use directly, and extend with ATLAS wiki.** Hermes memory handles session-level compaction. ATLAS wiki (Phase 6) handles durable, curated, structured knowledge.

Flow: Hermes memory produces raw insight → ATLAS wiki ingest processes and structures it → wiki_pages table stores it → available for future sessions and cockpit browsing.

Do not reimplement Hermes memory. Extend it: the wiki layer enhances the evolved Hermes/ATLAS foundation's memory capability — it does not replace or wrap it.

---

## Summary: ATLAS Adaptation Boundary

| Component | Use directly | Wrap | Rewrite into ATLAS | Keep external |
|-----------|-------------|------|-------------------|--------------|
| `ProviderTransport` ABC + existing transports | Yes | | | |
| Custom OpenAI-compatible endpoint | Yes | | | |
| `credential_sources.py` pool | Yes | | | |
| OAuth (PKCE, device_code) | Yes (as-is v1.0) | Later (cockpit auth surface) | | |
| Azure identity | | | | Yes (enterprise scope) |
| Credential persistence (~/.hermes/) | Yes | | | |
| "Authenticated providers" query | | Wrap with ATLAS query API | | |
| Model selection | | Extend with ATLAS model registry | | |
| Dynamic model discovery | | | New (atlas_core.model_registry) | |
| Task-class routing | | | New (atlas_core.model_router) | |
| Delegation / subagent | Yes | | | |
| Profiles → workspaces | Yes | | | |
| Toolsets → capability tiers | Yes | | | |
| Skills lifecycle | Yes | | | |
| Plugins / MCP | Yes | | | |
| Cron | Yes | | | |
| Gateway adapters (channels) | | | | Yes (v2.0+) |
| Session store | Yes | Bridge to AuditEvent | | |
| Memory/insights | Yes | Bridge to wiki ingest | | |
