# Phase 1: Hermes Foundation Clone & Extension Audit — Research

**Researched:** 2026-06-04
**Domain:** Hermes agent extension surfaces, plugin/hook architecture, Python module extraction audit
**Confidence:** HIGH (extension surfaces confirmed directly from upstream source files via gh API)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-001: Hermes foundation used directly (not black-box subprocess)
- D-002: Audit-first runtime — every runtime action emits structured AuditEvents; audit-event bus must attach WITHOUT in-core edits if possible
- D-008: Skills classified before shipping as ATLAS-grade
- D-011: Canonical repo layout: foundation/ + packages/atlas-core + services/* + apps/* + infra/ + native/
- Hermes SHA: `e8b9369a9d2df36139a5055cae3ed3c15691e03e` (MIT, v0.14.0 / tag v2026.5.16-1302-ge8b9369a9)
- Divergence policy: plugin > tool > hook > skill > ATLAS-only override > in-core edit
- Every in-core edit requires a docs/decisions/ record classified as: upstreamable | plugin-tool | ATLAS-only | experimental

### Claude's Discretion
- Vendoring method for `_EXTERNAL_REPOS/hermes-agent` deferred until after audit (submodule vs subtree vs fork)

### Deferred Ideas (OUT OF SCOPE)
- Do not write any ATLAS service code, schemas, or migrations (Phase 2)
- Do not begin the event bus implementation (Phase 4)
- Do not classify skills beyond identifying the surface (Phase 9)
- Do not ship any runnable ATLAS code in this phase
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FOUND-01 | Clone Hermes at pinned SHA with secret-scan gate confirming clean copy | §Secret-Scan Gate — patterns, tools, POSIX+PS commands verified |
| FOUND-02 | Extension-point audit documenting hook/tool/plugin surfaces; YES/NO on audit-event bus | §Extension Surface Table — all surfaces sourced from upstream code; §Audit-Event Bus Verdict |
| FOUND-03 | Every Hermes divergence classified (upstreamable/plugin-tool/ATLAS-only/experimental) | §Divergence Policy Inputs — friction points identified for audit |
| FOUND-04 | Per-module classification (port/rewrite/reference/discard) for atlas_core donor modules | §Module Extraction Inputs — classification evidence checklist per module |
</phase_requirements>

---

## Summary

Hermes v0.14.0 (SHA e8b9369) is a Python-primary agent framework with a well-designed,
documented extension system. **Three surfaces are officially sanctioned for external extension
without editing core files:** the plugin system (directory plugins, pip entry-points, user
plugins), the tool registry (self-registering callable handlers), and shell hooks (YAML-
configured scripts receiving JSON payloads via stdin). All three are documented upstream and
compose cleanly. The divergence preference order (plugin > tool > hook > skill > ATLAS-only >
in-core) maps directly to these surfaces.

For D-002, the critical finding is affirmative: **the audit-event bus CAN attach via the plugin
system without editing cli.py or run_agent.py.** The Langfuse observability plugin (bundled
at `plugins/observability/langfuse/`) is the precise template: it registers callbacks on six
hooks (pre/post_tool_call, pre/post_llm_call, pre/post_api_request) through a standard
`register(ctx)` function and `plugin.yaml` manifest. The ATLAS audit plugin follows this pattern
exactly. Evidence is sourced directly from upstream source — not inferred.

The six atlas_core donor modules in `L2-Atlas/src/atlas_core/` are small, well-structured
Python 3.11 files. Three are classifiable now as **rewrite** (PowerShell-specific),
**port-or-rewrite** (schema-dependent), and **reference** (concept preserved but superseded by
Hermes primitives). The final classification of each requires confirming Hermes overlaps at
execution time.

**Primary recommendation:** Wire the ATLAS audit plugin as a Hermes directory plugin at
`plugins/atlas_audit/` inside the cloned foundation. No core edits required.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tool execution | Hermes core (run_agent.py) | Plugin hook surface | Core dispatches; plugins observe via post_tool_call |
| Audit event emission | Hermes plugin surface | ATLAS plugin (Phase 4) | `post_tool_call`, `post_llm_call` hooks already fire per-action |
| Session/state store | Hermes core (hermes_state.py) | ATLAS SQLite (Phase 2) | Hermes owns its session DB; ATLAS owns the AuditEvent DB |
| Skill classification | Hermes skills/ surface | ATLAS skill registry | Hermes loads skills; ATLAS wraps/classifies them (Phase 9) |
| Cron scheduling | Hermes cron/ module | ATLAS (no change needed) | Hermes cron is self-contained; ATLAS can define cron jobs in config |
| MCP integration | Hermes tools/mcp_tool.py | config.yaml mcp_servers | Add MCP servers via config; no code edit needed |
| Delegation/subagents | Hermes delegate_task tool | plugin hook (subagent_start/stop) | Subagents observable via hooks without in-core edit |
| Gateway/messaging | Hermes gateway/ | ATLAS out of scope v1 | Telegram/Discord gateway; not touched in Phase 1 |
| Profile isolation | Hermes hermes_cli/profiles.py | config flag | Each profile is a full HERMES_HOME; ATLAS can use a named profile |
| Secret scan gate | Git + Python scan tool | PowerShell fallback | Run at clone time before any commit; enforced by plan task |

---

## Extension Surface Table

All rows sourced from upstream via `gh api` direct file reads at the pinned SHA branch.

| Surface | Exists | Registration Mechanism | Key File(s) | Notes |
|---------|--------|----------------------|-------------|-------|
| **Plugin system** | YES | `plugin.yaml` manifest + `register(ctx)` in `__init__.py` | `hermes_cli/plugins.py` | 4 discovery sources: bundled (`plugins/`), user (`~/.hermes/plugins/`), project (`./.hermes/plugins/`), pip entry-point group `hermes_agent.plugins` |
| **Tool registry** | YES | `tools.registry.register(name, toolset, schema, handler)` at module import | `tools/registry.py` | Singleton `ToolRegistry`; thread-safe; plugins call `ctx.register_tool()` which delegates here; `override=True` replaces built-ins |
| **Shell hooks** | YES | `hooks:` block in `~/.hermes/config.yaml`; consent gate at first use | `agent/shell_hooks.py`, `hermes_cli/hooks.py` | JSON stdin/stdout wire protocol; fire via same `invoke_hook()` path as Python plugins; Python plugins win ties on block decisions |
| **Python lifecycle hooks** | YES | `ctx.register_hook(hook_name, callback)` inside `register(ctx)` | `hermes_cli/plugins.py` (VALID_HOOKS) | 22 named hooks — see list below |
| **MCP integration** | YES | `mcp_servers:` key in config.yaml; `hermes mcp add` | `hermes_cli/mcp_config.py`, `tools/mcp_tool.py` | Add any MCP server without code edit; config-driven |
| **Session/state store** | YES (read-only attach) | `hermes_state.py` — internal SQLite (~180KB); no public write API | `hermes_state.py` | VERIFY AT EXECUTION: confirm whether a plugin can subscribe to state-change events or only read via `hermes_state` module imports |
| **Delegation / subagents** | YES | `delegate_task` tool + `subagent_start` / `subagent_stop` hooks | `tools/` (delegate_task tool), `hermes_cli/plugins.py` (VALID_HOOKS) | Plugins observe subagent lifecycle; spawning subagents uses the tool, not a direct API |
| **Cron / scheduling** | YES | `cron/` entries in `~/.hermes/cron/` dir; `cron/jobs.py`, `cron/scheduler.py` | `cron/scheduler.py` | `tick()` called every 60s from gateway background thread; prompt-injection guard; toolset restrictions enforced |
| **Profiles** | YES | `hermes profile create <name>`; `-p <name>` CLI flag or sticky `profile use` | `hermes_cli/profiles.py` | Each profile is a fully isolated HERMES_HOME; config, .env, skills, sessions, cron all isolated |
| **Skill surface** | YES | Skill directory under `~/.hermes/skills/<name>/SKILL.md`; `optional-skills/` for bundled extras | `agent/skill_utils.py`, `skills/` | Plugin can also call `ctx.register_skill(name, path)` for plugin-owned skills |
| **Gateway / server interface** | YES | `gateway/run.py`; separate process | `gateway/`, `tui_gateway/` | Messaging bridge for Telegram/Discord/Slack; not relevant Phase 1 |
| **CLI / TUI boundary** | YES | CLI in `hermes_cli/`; TUI in `ui-tui/` (TypeScript); Python/TS boundary is stable | `hermes_cli/main.py`, `ui-tui/` | TypeScript surfaces TUI only; all logic is Python; ATLAS should not touch `ui-tui/` |
| **Provider surface** | YES | `providers/` + `hermes model` CLI; `model.default` in config.yaml | `providers/` | Switch LLM provider with no code change |
| **Auxiliary tasks** | YES | `ctx.register_auxiliary_task(key, fn)` — persistent background coroutines | `hermes_cli/plugins.py` | For long-lived plugin background work |
| **Message injection** | YES | `ctx.inject_message(content, role)` | `hermes_cli/plugins.py (PluginContext)` | Plugin can inject messages into active conversation; queued if agent idle |

### Complete VALID_HOOKS List (from `hermes_cli/plugins.py`)

[VERIFIED: upstream source, `hermes_cli/plugins.py` VALID_HOOKS set]

```
pre_tool_call           post_tool_call
transform_terminal_output  transform_tool_result
transform_llm_output    pre_llm_call              post_llm_call
pre_api_request         post_api_request          api_request_error
on_session_start        on_session_end            on_session_finalize
on_session_reset        subagent_start            subagent_stop
pre_gateway_dispatch
pre_approval_request    post_approval_response
```

**Return-value semantics:**
- `pre_tool_call`: can return `{"decision": "block", "reason": "..."}` or `{"action": "block", ...}` to veto a tool call
- `pre_llm_call`: can return `{"context": "..."}` to inject ephemeral context into the user message (never system prompt)
- `post_*` hooks: observer-only; return values ignored
- `transform_*` hooks: first non-None string wins replacement

---

## Audit-Event Bus Verdict

**VERDICT: YES — the ATLAS audit-event bus can attach via the plugin system without editing cli.py or run_agent.py.**

[VERIFIED: upstream source, `plugins/observability/langfuse/__init__.py` and `plugin.yaml`]

**Evidence:**

1. The bundled Langfuse observability plugin (`plugins/observability/langfuse/`) is the exact
   reference implementation. Its `plugin.yaml` declares hooks:
   ```yaml
   hooks:
     - pre_api_request
     - post_api_request
     - pre_llm_call
     - post_llm_call
     - pre_tool_call
     - post_tool_call
   ```
   Its `register(ctx)` function calls `ctx.register_hook(...)` for each hook with a callback
   that writes observability traces. No core files are modified.

2. `tool_executor.py` calls `_emit_post_tool_call_hook()` which resolves to
   `hermes_cli.plugins.invoke_hook("post_tool_call", ...)` with full metadata:
   `tool_name`, `args`, `result`, `task_id`, `session_id`, `tool_call_id`, `turn_id`,
   `api_request_id`, `duration_ms`, `status`, `error_type`, `error_message`.
   This fires for **every** tool call in both sequential and concurrent dispatch paths.

3. `model_tools._emit_post_tool_call_hook()` has a fast-path no-op guard (`has_hook()` check)
   so unregistered hooks cost only one dict lookup.

4. Subagent lifecycle is observable via `subagent_start` / `subagent_stop` hooks.

5. Approval lifecycle is observable via `pre_approval_request` / `post_approval_response`.

**What post_tool_call does NOT directly cover:** LLM calls themselves are covered by
`post_llm_call` / `post_api_request`. Session start/end are covered by `on_session_start` /
`on_session_end`. The union of these hooks provides full runtime observability for every
AuditEvent type defined in REQUIREMENTS.md RUNTIME-03.

**ATLAS audit plugin template:**
```python
# plugins/atlas_audit/__init__.py
def register(ctx) -> None:
    ctx.register_hook("on_session_start",       on_session_start)
    ctx.register_hook("on_session_end",         on_session_end)
    ctx.register_hook("pre_tool_call",          on_pre_tool_call)
    ctx.register_hook("post_tool_call",         on_post_tool_call)
    ctx.register_hook("post_llm_call",          on_post_llm_call)
    ctx.register_hook("post_api_request",       on_post_api_request)
    ctx.register_hook("subagent_start",         on_subagent_start)
    ctx.register_hook("subagent_stop",          on_subagent_stop)
    ctx.register_hook("post_approval_response", on_approval)
```

**Caveat:** AuditEvent schema and SQLite writer are Phase 2/4 work. Phase 1 confirms
the attachment point only — implementation is out of scope.

---

## Divergence Policy Inputs

### Preference-Order Reality Check

| Operation | Easiest path | Friction | Risk of in-core temptation |
|-----------|-------------|----------|---------------------------|
| Observe any tool call | `post_tool_call` plugin hook | None — fully supported | LOW |
| Observe any LLM call | `post_llm_call` / `post_api_request` | None — fully supported | LOW |
| Block a tool call | `pre_tool_call` → return block dict | None — supported | LOW |
| Add a new tool | `ctx.register_tool()` in plugin | None — clean API | LOW |
| Add a new CLI command | `ctx.register_cli_command()` | None — supported | LOW |
| Inject context into LLM turn | `pre_llm_call` → return {"context": ...} | Ephemeral only, no system prompt | MEDIUM — may tempt prompt injection |
| Modify system prompt | [VERIFY AT EXECUTION] whether a hook or config supports this | UNKNOWN — likely requires in-core edit | HIGH — flag in audit |
| Override approval flow | `pre_tool_call` block (pre-approval); post hooks observe only | Cannot programmatically grant approval | MEDIUM — approval UI is hardwired |
| Add a cron job | Config file addition or `hermes cron` CLI | No code edit needed | LOW |
| Override tool behavior | `ctx.register_tool(..., override=True)` | Replaces entire handler | MEDIUM — debug complexity |
| Capture artifacts | [VERIFY AT EXECUTION] no dedicated artifact hook found | UNKNOWN | HIGH — may require in-core edit |

### Most Likely In-Core Edit Friction Points

1. **System prompt augmentation.** `agent/system_prompt.py` builds the system prompt. If ATLAS
   needs to inject persistent operator identity or policy context into the system prompt (not
   ephemeral turn context), this file likely needs an in-core edit. The `pre_llm_call` hook
   only injects into the user message. [VERIFY AT EXECUTION]

2. **Artifact capture.** There is no `post_artifact` hook in VALID_HOOKS. ATLAS RUNTIME-03
   requires AuditEvents for artifact creation. This may require either (a) wrapping the artifact
   tool via `ctx.register_tool(..., override=True)` or (b) an in-core edit. [VERIFY AT EXECUTION]

3. **hermes_state.py write path.** The session state DB is ~180KB of internal code. If ATLAS
   needs to co-write state alongside Hermes (e.g., to link a Hermes session_id to an ATLAS
   Run record), the write path likely requires in-core edit or a parallel DB with join keys.
   [VERIFY AT EXECUTION]

4. **Turn ID and request ID propagation.** `post_tool_call` receives `turn_id` and
   `api_request_id`. Confirm at execution that these are populated non-empty for all code
   paths (sequential and concurrent dispatch). Empty IDs would break AuditEvent correlation.

---

## Module Extraction Inputs (FOUND-04)

The donor modules live at `C:/Users/Davi/Desktop/Projects/L2-Atlas/src/atlas_core/`.
They are Python 3.11, ~1.6K–7.4KB each, already read at research time.

### Evidence Required Per Module During Audit

For each module, the execution-time audit must collect:

1. **All external imports** — does it import anything beyond stdlib + atlas_core? (signals porting cost)
2. **Does Hermes already have this functionality?** — if yes, classify as reference/discard
3. **Are there Pydantic v1 models?** — if yes, rewrite required (D-012 mandates Pydantic v2)
4. **Any Windows/PowerShell-only APIs?** — if yes, must be rewritten for cross-platform
5. **Does it carry data contracts?** — if yes, link to which Phase 2 Pydantic schema it seeds

### Preliminary Classification (to be confirmed at execution)

| Module | Size | Preliminary Class | Evidence Collected at Research Time |
|--------|------|-------------------|--------------------------------------|
| `mission_control/parser.py` | 5.0KB | **port** | Pure stdlib (re, hashlib, pathlib). Parses `@atlas` Markdown Kanban to `MissionBoard`. Uses internal `task_model.py` dataclasses (not Pydantic). No Windows-specific code. Functional logic is reusable. Needs Pydantic v2 `Mission` model (Phase 2 SCHEMA-01). Data contract feeds Phase 2. |
| `execution/policy.py` | 3.0KB | **reference → rewrite** | Pure stdlib. `WorkspacePolicy` + `CommandPolicyEngine` with hardcoded PowerShell blocked patterns (e.g., `Remove-Item -Recurse`, `Set-ExecutionPolicy`). Cross-platform rewrite needed (RUNTIME-07). Hermes has `tool_guardrails.py` — audit overlap at execution. Concepts valid; implementation is Windows-biased. |
| `execution/powershell.py` | 4.3KB | **rewrite** | Hard dependency on `powershell.exe` as shell. RUNTIME-07 requires cross-platform. The execution boundary pattern (policy gate + logger + command result) is valuable concept; implementation must be rewritten for Hermes terminal_tool integration. Windows-only = cannot port. |
| `logging/jsonl_logger.py` | 1.9KB | **reference** | Pure stdlib (json, re, pathlib). Append-only JSONL with secret redaction regexes. Hermes has `hermes_logging.py` — [VERIFY AT EXECUTION] whether it covers the same need. JsonlLogger pattern is clean but the ATLAS AuditEvent (Phase 2) supersedes it as the durable event store. Keep as reference for redaction patterns. |
| `runtime/orchestrator.py` | 7.4KB | **reference** | Imports PowerShellExecutor, JsonlLogger, MissionParser, CommandPolicyEngine — inherits PowerShell dependency. `AtlasOrchestrator.run_task()` shows the policy→execute→log flow that becomes the ATLAS runtime loop. Concept maps to Phase 5 Mission & Run Lifecycle. Actual code cannot be ported as-is due to PowerShell executor. |
| `skills/registry.py` | 1.6KB | **reference** | Pure stdlib (pathlib). In-memory `SkillRegistry` backed by `SkillManifest.from_file()`. Hermes has a full skills system (`skills/`, `agent/skill_utils.py`, `agent/skill_bundles.py`). Phase 9 owns skill classification. Keep as reference for manifest schema design. Do not port; superseded by Hermes skills. |

### Data-Carrying Modules → Phase 2 Schema Linkage

| Module | Data Contracts | Phase 2 Schema Target |
|--------|---------------|----------------------|
| `mission_control/parser.py` | `Mission`, `MissionBoard`, `MissionStep`, `MissionDiagnostic` | `SCHEMA-01 Mission` model — status enum, project, description, tags, steps |
| `mission_control/task_model.py` | `MissionBoard.counts_by_status` dict | `SCHEMA-01 Run` status enum |
| `runtime/orchestrator.py` | `ExecutionResult`, `ExecutionPlan`, `CommandResult` | `SCHEMA-01 Run`, `ToolCall`, `AuditEvent` — maps to outcome/status fields |
| `execution/policy.py` | `PolicyDecision.allowed`, `.requires_approval`, `.reason` | `SCHEMA-01 AuditEvent.policy_decision` field (Phase 2) |
| `logging/jsonl_logger.py` | JSONL `{timestamp, event, data}` shape | `SCHEMA-01 AuditEvent` base shape; redaction patterns carry over |

---

## Secret-Scan Gate (FOUND-01)

### What the Runtime Install Contains (DO NOT VENDOR)

`C:/Users/Davi/AppData/Local/hermes/hermes-agent` contains:
- `.env` (~23KB) — live API keys
- `state.db` (~73MB) — session database
- `auth.json` — authentication credentials
- Session DBs, gateway state, logs

The upstream fresh clone at pinned SHA ships only `.env.example` (template, no values) and
no state DB. A fresh clone from upstream is CLEAN by design.

### Secret-Scan Patterns to Check Post-Clone

The following patterns would indicate accidental state contamination:

| Pattern | Risk | Check Command |
|---------|------|---------------|
| `.env` (non-example) | Live API keys | `git ls-files .env` — must return empty |
| `auth.json` | Auth credentials | `git ls-files auth.json` — must return empty |
| `*.db` files | State databases | `git ls-files "*.db"` — must return empty |
| `state.db` | Session history | `git ls-files state.db` — must return empty |
| `cli-config.yaml` (non-example) | Sensitive SSH paths (in upstream .gitignore) | `git ls-files cli-config.yaml` — must return empty |
| `sessions/` directory | Session files | `git ls-files sessions/` — must return empty |
| `logs/` directory | Runtime logs | `git ls-files logs/` — must return empty |
| Private key files `*.pem`, `*.ppk` | Credentials | `git ls-files "*.pem" "*.ppk"` — must return empty |
| Any file > 10MB | Likely state DB | `git ls-files | xargs -I{} git cat-file -s HEAD:{} 2>/dev/null` |

### Recommended Secret-Scan Approach

**Tool:** `detect-secrets` (Yelp) — installable via pip, cross-platform, no native deps.

```bash
# Install (use project's uv venv or system pip)
pip install detect-secrets

# Run baseline scan on the fresh clone
detect-secrets scan _EXTERNAL_REPOS/hermes-agent > /tmp/hermes-secrets-baseline.json

# Fail if any secrets found (exit code 1 = secrets detected)
detect-secrets audit /tmp/hermes-secrets-baseline.json --report --fail-on-unaudited
```

**PowerShell fallback (no pip available):**
```powershell
# Git-level check: verify no secrets files tracked
$secretFiles = @('.env', 'auth.json', 'state.db', 'cli-config.yaml')
foreach ($f in $secretFiles) {
    $tracked = git -C _EXTERNAL_REPOS/hermes-agent ls-files $f
    if ($tracked) { Write-Error "SECRET FILE TRACKED: $f"; exit 1 }
}

# Check for any .db files
$dbFiles = git -C _EXTERNAL_REPOS/hermes-agent ls-files "*.db"
if ($dbFiles) { Write-Error "DB FILES TRACKED: $dbFiles"; exit 1 }

Write-Output "CLEAN: no secret files tracked in clone"
```

**ASSERT CLEAN condition:** `git ls-files` on the fresh clone must return zero results for
all secret-pattern matches, AND `detect-secrets scan` must return an empty results dict.

**Note:** `detect-secrets` must be installed into a virtual environment, not the Hermes runtime
venv at `C:/Users/Davi/AppData/Local/hermes/hermes-agent/venv`. Use the project's own venv or
a throwaway `uv venv` for the scan.

---

## Preliminary Audit Checklist

These items translate directly into planner tasks.

### Wave 1: Clone + Secret Gate (FOUND-01)

- [ ] **1.1** Create `_EXTERNAL_REPOS/` directory at project root (outside git tree, add to `.gitignore`)
- [ ] **1.2** `git clone https://github.com/NousResearch/hermes-agent.git _EXTERNAL_REPOS/hermes-agent`
- [ ] **1.3** `git -C _EXTERNAL_REPOS/hermes-agent checkout e8b9369a9d2df36139a5055cae3ed3c15691e03e`
- [ ] **1.4** Verify SHA: `git -C _EXTERNAL_REPOS/hermes-agent rev-parse HEAD` must equal pinned SHA
- [ ] **1.5** Run secret-scan gate (detect-secrets or PowerShell fallback) — assert CLEAN
- [ ] **1.6** Verify no `.env`, `auth.json`, `*.db`, `sessions/`, `logs/` tracked by git
- [ ] **1.7** Confirm `git -C _EXTERNAL_REPOS/hermes-agent status` is clean (no unstaged changes)
- [ ] **1.8** Record clone confirmation in docs with SHA verification output

### Wave 2: Extension Surface Audit (FOUND-02)

- [ ] **2.1** Read `hermes_cli/plugins.py` — confirm VALID_HOOKS list, `PluginContext` API, plugin discovery sources (4 sources), plugin manifest required fields
- [ ] **2.2** Read `tools/registry.py` — confirm `register()` signature, toolset system, `dispatch()` behavior
- [ ] **2.3** Read `agent/shell_hooks.py` — confirm JSON wire protocol, event names, block/allow response shapes
- [ ] **2.4** Read `plugins/observability/langfuse/plugin.yaml` and `__init__.py` — use as ATLAS audit plugin template; confirm `register(ctx)` pattern
- [ ] **2.5** Read `model_tools.py` — confirm `_emit_post_tool_call_hook()` fires for all code paths; verify `turn_id` and `api_request_id` are non-empty in production paths
- [ ] **2.6** Read `agent/tool_executor.py` — confirm both sequential and concurrent dispatch call `_emit_terminal_post_tool_call`; confirm concurrent path coverage
- [ ] **2.7** Read `agent/system_prompt.py` — determine whether ATLAS can augment system prompt via config/plugin or requires in-core edit (friction point #1)
- [ ] **2.8** Search for artifact creation sites — `grep -r "artifact" _EXTERNAL_REPOS/hermes-agent --include="*.py" -l` — determine if `post_artifact` hook is needed or if artifact tools are already covered by `post_tool_call`
- [ ] **2.9** Read `hermes_state.py` — determine session ID shape, whether session_id is stable across a run, and whether ATLAS can read it from a hook context
- [ ] **2.10** Read `cron/scheduler.py` and `cron/jobs.py` — confirm job schema, how jobs are added, toolset restrictions
- [ ] **2.11** Read `hermes_cli/profiles.py` — confirm ATLAS-named profile is a viable isolation strategy
- [ ] **2.12** Read `hermes_cli/mcp_config.py` — confirm `mcp_servers` config key structure for adding ATLAS MCP servers without code edit
- [ ] **2.13** Write `docs/research/HERMES_FOUNDATION_AUDIT.md` with one row per surface, YES/NO verdict per row, and the final YES/NO/PARTIAL on audit-event bus

### Wave 3: Divergence Classification Stubs (FOUND-03)

- [ ] **3.1** For each friction point identified (system prompt, artifact capture, hermes_state write, turn_id gaps): create a stub `docs/decisions/DIV-NNN-<name>.md` with classification (UNKNOWN pending code audit → will be resolved at Phase 4)
- [ ] **3.2** Confirm that plugin/tool/hook surface covers all Phase 4 AuditEvent types without in-core edit, or document which type requires in-core edit
- [ ] **3.3** `git status` in `_EXTERNAL_REPOS/hermes-agent` must be clean (no ATLAS files added inside the Hermes clone)

### Wave 4: Module Extraction Plan (FOUND-04)

- [ ] **4.1** Read `L2-Atlas/src/atlas_core/mission_control/task_model.py` — extract field names for Phase 2 `Mission` schema mapping
- [ ] **4.2** Read `L2-Atlas/src/atlas_core/runtime/models.py` — extract field names for Phase 2 `Run`, `ToolCall`, `AuditEvent` schema mapping
- [ ] **4.3** Confirm `execution/policy.py` has no Pydantic v1 imports (uses stdlib dataclasses — already confirmed at research time)
- [ ] **4.4** Confirm `logging/jsonl_logger.py` secret-redaction regex patterns are worth carrying into Phase 2 AuditEvent sanitizer
- [ ] **4.5** Verify `skills/registry.py` against Hermes skill surface — confirm superseded (expected outcome: discard)
- [ ] **4.6** Write `docs/imports/L2_ATLAS_MODULE_EXTRACTION_PLAN.md` with final classification table and Phase 2 schema links

### Phase Gate Verification

- [ ] `_EXTERNAL_REPOS/hermes-agent` at correct SHA and secret-scan CLEAN
- [ ] `docs/research/HERMES_FOUNDATION_AUDIT.md` exists, every surface row filled, YES/NO verdict stated
- [ ] `docs/imports/L2_ATLAS_MODULE_EXTRACTION_PLAN.md` exists, all 6 modules classified
- [ ] `git status` of L2-ATLAS-PROJECT working tree is clean (audit produces only docs, no code)

---

## Common Pitfalls

### Pitfall 1: Vendoring the Runtime Install

**What goes wrong:** `cp -r C:/Users/Davi/AppData/Local/hermes/hermes-agent .` accidentally
copies `state.db` (~73MB), `.env` (~23KB with live keys), `auth.json`, session DBs.
**Why it happens:** The runtime install is the convenient local reference for the SHA.
**How to avoid:** Always clone from `https://github.com/NousResearch/hermes-agent.git` at pinned SHA. Never copy from AppData.
**Warning signs:** Clone directory size > 50MB; `git ls-files *.db` returns results; `.env` is non-empty.

### Pitfall 2: Monolith File Noise Obscures Extension Surfaces

**What goes wrong:** `cli.py` (685KB), `run_agent.py` (202KB), `hermes_state.py` (180KB)
are searched wholesale, leading to the false conclusion that all functionality requires
in-core edits.
**Why it happens:** Large files make grep-based audits noisy.
**How to avoid:** Start the audit from the plugin system documentation and VALID_HOOKS list
(already confirmed). Use targeted file reads, not full-file greps.
**Warning signs:** Audit notes say "couldn't find hook for X" without checking `model_tools.py`
and `hermes_cli/plugins.py` specifically.

### Pitfall 3: Assuming shell_hooks and Python plugins are different systems

**What goes wrong:** Plan treats `hooks:` in config.yaml as the hook system and overlooks the
Python plugin hook system, or vice versa.
**Why it happens:** Two hook surfaces, similar naming.
**How to avoid:** They compose through the same `invoke_hook()` call path. Python plugins are
registered first; shell hooks fire through the same dispatcher. ATLAS uses the Python plugin
surface (more expressive, no subprocess overhead).

### Pitfall 4: Classifying donor modules without checking Hermes overlap

**What goes wrong:** `skills/registry.py` gets ported when Hermes already has a complete skill
system; `logging/jsonl_logger.py` gets ported when Phase 2's AuditEvent supersedes it.
**Why it happens:** Auditing donor modules in isolation without comparing to Hermes internals.
**How to avoid:** For each donor module, explicitly check whether Hermes has an equivalent.
The audit checklist items 4.1–4.5 enforce this.

### Pitfall 5: Windows line endings / path separators in the clone

**What goes wrong:** Git on Windows converts LF to CRLF if `core.autocrlf=true`, creating
spurious diffs in the clone.
**Why it happens:** Default Windows Git config.
**How to avoid:** Clone with `git clone --config core.autocrlf=false`. The Hermes repo has a
`.gitattributes` file — verify it forces LF for Python files at execution time.

### Pitfall 6: Confusing `_EXTERNAL_REPOS/` location with project repo

**What goes wrong:** Files are added to `_EXTERNAL_REPOS/hermes-agent/` and accidentally
committed to the L2-ATLAS-PROJECT repo.
**Why it happens:** `_EXTERNAL_REPOS/` is a subdirectory of the project root.
**How to avoid:** Add `_EXTERNAL_REPOS/` to `.gitignore` in L2-ATLAS-PROJECT before the clone.
The phase gate requires `git status` of L2-ATLAS-PROJECT to be clean after the audit.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| git | Clone + secret scan | Yes | 2.54.0.windows.1 | — |
| Python | detect-secrets, module reading | Yes | 3.11.15 | — |
| uv | Venv for detect-secrets | Yes | 0.11.16 | pip |
| detect-secrets | FOUND-01 secret scan | Not installed | — | PowerShell git ls-files fallback (documented above) |
| gh CLI | Research (used above) | Yes | — | — |

**Missing dependencies with no fallback:** None — PowerShell fallback covers the secret scan.

**Missing dependencies with fallback:**
- `detect-secrets`: installable via `pip install detect-secrets` or `uv pip install detect-secrets`. Plan task should install into a throwaway venv, not the Hermes runtime venv.

---

## Validation Architecture

> `workflow.nyquist_validation` status: not explicitly set in config — treated as enabled.

This is a pure audit phase (no product code written). Test coverage applies only to the audit
deliverables (documents exist, contain required content).

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Notes |
|--------|----------|-----------|-------------------|-------|
| FOUND-01 | Clone at SHA with CLEAN secret scan | Smoke | `git -C _EXTERNAL_REPOS/hermes-agent rev-parse HEAD` == pinned SHA | Manual assertion; no test file needed |
| FOUND-02 | Audit doc exists, all rows filled | Structural | `test -f docs/research/HERMES_FOUNDATION_AUDIT.md` | Content review is manual |
| FOUND-03 | Divergence stubs exist in docs/decisions/ | Structural | `ls docs/decisions/DIV-*.md` | Content review is manual |
| FOUND-04 | Extraction plan doc exists, 6 modules classified | Structural | `test -f docs/imports/L2_ATLAS_MODULE_EXTRACTION_PLAN.md` | Content review is manual |

**All phase-gate verification is documentation/structural — no unit tests needed for this phase.**

---

## Security Domain

> ATLAS secret-scan gate is the primary security control for Phase 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Phase 1 is read-only audit |
| V3 Session Management | No | Phase 1 is read-only audit |
| V4 Access Control | No | Phase 1 is read-only audit |
| V5 Input Validation | No | No user inputs in this phase |
| V6 Cryptography | No | No crypto in this phase |
| V2.1 Secret Handling | YES | `detect-secrets` scan gate; git ls-files assertions |

### Threat Patterns for This Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Runtime install vendored into repo | Information Disclosure | Clone fresh from upstream only; gitignore `_EXTERNAL_REPOS/` |
| `.env` / `auth.json` tracked by git | Information Disclosure | `git ls-files` assertions in secret-scan gate |
| State DB (`state.db`) tracked by git | Information Disclosure | `git ls-files *.db` assertion |
| Windows CRLF corruption of Python source | Tampering | Clone with `core.autocrlf=false` |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `turn_id` and `api_request_id` are non-empty in all production tool-call paths | Audit-Event Bus Verdict | AuditEvent correlation gaps; would require in-core fix before Phase 4 |
| A2 | System prompt augmentation requires in-core edit (no plugin hook) | Divergence Policy Inputs | If a plugin API exists, one friction point is eliminated |
| A3 | There is no `post_artifact` hook in VALID_HOOKS at pinned SHA | Divergence Policy Inputs | If added, artifact AuditEvents are fully covered without override |
| A4 | `hermes_state.py` has no public write API accessible from a plugin | Extension Surface Table | If it does, ATLAS session linking is simpler |

All A1–A4 are resolved by reading the actual cloned source in Wave 2 of the execution checklist.

---

## Open Questions

1. **System prompt augmentation path**
   - What we know: `pre_llm_call` injects into user message (not system prompt). `agent/system_prompt.py` builds the system prompt.
   - What's unclear: Is there a plugin API or config key for appending to the system prompt? Or does it require editing `system_prompt.py`?
   - Recommendation: Audit `agent/system_prompt.py` in Wave 2 task 2.7. If in-core edit required, create DIV-001 record and classify as ATLAS-only.

2. **Artifact coverage via post_tool_call**
   - What we know: Tools that produce artifacts (file writes, code gen) call the tool registry, which fires `post_tool_call`. So artifact creation IS observable via `post_tool_call` with `tool_name` indicating the artifact tool.
   - What's unclear: Whether `post_tool_call` result payload includes the artifact path/content, or whether a separate artifact surface exists.
   - Recommendation: Audit Wave 2 task 2.8. Likely `post_tool_call` is sufficient for RUNTIME-03.

3. **`_EXTERNAL_REPOS/` vs git submodule**
   - What we know: Vendoring method deferred (D per CONTEXT.md) until after the extension audit.
   - What's unclear: After the audit, does ATLAS need in-core Hermes edits? If yes, fork is required. If plugin-only, submodule or subtree works.
   - Recommendation: This question is answered by the audit itself. The plan must not pre-answer it.

---

## Sources

### Primary (HIGH confidence)

- `gh api repos/NousResearch/hermes-agent/contents/hermes_cli/plugins.py` — VALID_HOOKS, PluginContext API, plugin discovery sources, register_hook signature, invoke_hook implementation
- `gh api repos/NousResearch/hermes-agent/contents/plugins/observability/langfuse/plugin.yaml` — plugin manifest structure, hooks declaration
- `gh api repos/NousResearch/hermes-agent/contents/plugins/observability/langfuse/__init__.py` — register(ctx) pattern, full observability plugin implementation
- `gh api repos/NousResearch/hermes-agent/contents/model_tools.py` (lines 812–858, 987–1120) — `_emit_post_tool_call_hook()` implementation and all call sites
- `gh api repos/NousResearch/hermes-agent/contents/agent/tool_executor.py` (lines 1–100) — tool dispatch, `_emit_terminal_post_tool_call` call
- `gh api repos/NousResearch/hermes-agent/contents/agent/shell_hooks.py` (lines 1–100) — shell hooks wire protocol, JSON stdin/stdout format
- `gh api repos/NousResearch/hermes-agent/contents/tools/registry.py` — ToolRegistry singleton, register() signature
- `gh api repos/NousResearch/hermes-agent/contents/hermes_cli/profiles.py` — profile isolation model
- `gh api repos/NousResearch/hermes-agent/contents/cron/scheduler.py` (lines 1–80) — cron architecture
- `C:/Users/Davi/Desktop/Projects/L2-Atlas/src/atlas_core/` — all 6 donor modules read directly

### Secondary (MEDIUM confidence)

- GitHub directory listing of `hermes-agent/` top-level, `agent/`, `hermes_cli/`, `plugins/`, `tools/`, `skills/` — confirmed directory structure and file inventory
- `gh api repos/NousResearch/hermes-agent/contents/.env.example` — confirmed clean template (no live keys)
- `gh api repos/NousResearch/hermes-agent/contents/.gitignore` — confirmed upstream excludes `.env`, `*.db`, `cli-config.yaml`, `auth.json`

---

## Metadata

**Confidence breakdown:**
- Extension surfaces: HIGH — all sourced from direct upstream code reads via gh API
- Audit-event bus verdict: HIGH — confirmed by Langfuse plugin as direct working template
- Donor module classifications: MEDIUM — code read directly; Hermes overlap not yet verified
- Secret-scan gate: HIGH — upstream .gitignore and .env.example confirm clean clone shape

**Research date:** 2026-06-04
**Valid until:** 2026-07-04 (upstream moves fast; re-verify VALID_HOOKS if SHA changes)
