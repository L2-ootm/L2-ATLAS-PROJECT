# Feature Research — ATLAS v1.1 Agent Harness

**Domain:** Agentic CLI/TUI harness (local AI operator runtime)
**Researched:** 2026-06-15
**Confidence:** HIGH (grounded in Hermes v0.14.0 vendored source, opencode, Claude Code, Aider, Codex CLI behavior, and circuit-breaker/resilience production literature)

---

## Scope Note

This document covers only v1.1 NEW features. The v1.0 surfaces (mission/run lifecycle, audit event bus, LLM Wiki, Rust gateway SSE, SvelteKit cockpit, Models seed page) are existing baselines, not re-specced here. Features are organized by the seven v1.1 requirement categories: TUI, CLI, AUTH, PROVIDERS, MODELS, AGENT, NATIVE. A cross-cutting SECURITY category appears in the dependency section.

---

## Category: TUI — Terminal User Interface

### Table Stakes (Operators Expect These)

| Feature | Why Expected | Complexity | ATLAS Surface Dependency |
|---------|--------------|------------|--------------------------|
| ATLAS-branded header/status bar | Every serious agentic TUI (Hermes, Claude Code, opencode) shows tool name + current model + auth state before first prompt. Missing = operator does not know what they are running. | LOW | Cockpit branding, auth store |
| Static transcript (user + assistant turns, scrollable) | Table stakes for any chat surface. Hermes uses `Static` Ink component + `useVirtualHistory` hook to avoid rendering thousands of components. | MEDIUM | Hermes TUI vendored src |
| Streaming assistant response (live token rendering) | Operators expect to see output as it arrives; waiting for full response feels broken. Hermes implements via `StreamingAssistant` with `message.delta` gateway events. | MEDIUM | Hermes TUI gateway JSON-RPC |
| Multi-line composer with submit/cancel | Multi-line input is required for pasting code/context. Single-line composers feel like toys. | LOW | Hermes TextInput component |
| Tool call visibility in transcript | Every serious harness (Claude Code, opencode, Aider, Hermes) shows tool calls inline. Operators need to know what the agent is doing. | MEDIUM | Hermes ToolTrail tree, audit event bus |
| Spinner/activity indicator during model call | Clear busy state prevents user re-prompting during execution. | LOW | Gateway event `session.send` state |
| Clean exit that preserves session state | Operator must be able to Ctrl-C without losing conversation or corrupting state files. | LOW | Session persistence layer |
| Auth/model warning before first prompt | If auth is missing or model unavailable, operator must be told before they type anything. Silent failure on first send is a trust-breaker. | LOW | Auth store, provider registry |
| Slash command help (`/help`) | Expected in every serious TUI. Claude Code, Hermes, opencode all expose slash commands. | LOW | Central command registry |
| Error messages that state what to do next | "auth error" alone is unacceptable. Must include remediation path (`atlas auth add openrouter`). | LOW | Auth doctor, command surface |

### Differentiators (ATLAS-Specific Advantage)

| Feature | Value Proposition | Complexity | ATLAS Surface Dependency |
|---------|-------------------|------------|--------------------------|
| Mission context panel (bind chat to mission, show run/audit state) | No comparable tool (Hermes, opencode, Aider) surfaces mission/run/audit state in TUI. This is ATLAS' structural differentiation. | HIGH | Mission/run lifecycle (v1.0), audit event bus |
| Audit event reference in transcript | Showing audit event IDs/counts alongside agent turns gives operator full traceability without leaving TUI. | MEDIUM | Audit event bus (v1.0) |
| Wiki artifact links in TUI (`/wiki`) | LLM Wiki integration visible in TUI is unique to ATLAS. | MEDIUM | LLM Wiki runtime (v1.0) |
| Token/context window progress bar in status bar | Color-coded (green/yellow/red) visual indicator. Hermes has a feature request for this (#683); opencode shows it via models.dev metadata. High operator value for cost awareness. | LOW | Model registry context_window field |
| Subagent/task accordion (heat-mapped activity) | Hermes has `SubagentAccordion` with heat-map resource visualization. ATLAS can inherit and brand this. | HIGH | Hermes TUI, agent runtime adapter |
| Session resume with `/resume` | Hermes supports session branching/resume. ATLAS should expose this with mission awareness (resume session bound to mission X). | MEDIUM | Session persistence, mission lifecycle |
| `LiveTodoPanel` — in-progress task list beneath triggering message | Hermes feature showing Pending/In-Progress/Completed tasks beneath the message that spawned them. Makes agent work legible. | HIGH | Hermes TUI (inheritable) |
| ATLAS TUI gateway JSON-RPC backend (structured protocol) | Using JSON-RPC over stdio (Hermes pattern) decouples TUI rendering from runtime, enabling future native panel integration. Non-TUI tools (plain CLI, native pane) can share the same backend. | HIGH | Hermes tui_gateway, ATLAS runtime adapter |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Rust TUI rewrite from scratch (ratatui) | Aligns Rust-first strategy | High risk for v1.1; duplicates existing Hermes Ink TUI; delays auth/model/agent work. Hermes TUI is working, tested, and architecturally sound. | Adapt/extend Hermes Ink TUI with ATLAS namespace and panels. Reassess after v1.1 ships. |
| Inline secret display for debugging | Operators want to verify tokens work | Secrets in TUI output are an unacceptable security risk; screenshots, logs, and terminal history all capture them. | Redacted hints only (`sk-...xyz`). `/auth doctor` for validity check. |
| Real-time everything update (polling every second) | Operators want live status | Constant polling burns CPU and terminal redraws; TTY flicker is worse than stale status. | Update status bar after each API call event, not on a timer. |
| Monolithic Python print-based TUI | Simpler initial implementation | Stray prints corrupt JSON-RPC stdio protocol (proven Hermes design lesson). | Redirect all prints to stderr. Reserve stdout for JSON-RPC protocol messages. |

---

## Category: CLI — Command Surface

### Table Stakes

| Feature | Why Expected | Complexity | ATLAS Surface Dependency |
|---------|--------------|------------|--------------------------|
| `atlas` default entry (opens TUI) | opencode, Hermes both default to TUI when invoked bare. Operators expect `atlas` to open the harness, not a help menu. | LOW | TUI launch |
| `atlas --help` with ATLAS-branded command tree | Every serious CLI shows structured help. Must not show raw Hermes/Typer internals. | LOW | CLI framework (Typer or equivalent) |
| `atlas chat -q "<prompt>"` one-shot | Non-interactive single-turn agent call. Used in scripts, CI, quick queries. Claude Code (`-p`), opencode (`--message`), Hermes all expose this. | MEDIUM | Agent runtime adapter, auth store |
| `atlas chat` interactive (or alias to `atlas tui`) | Interactive mode without full TUI is useful for non-terminal-capable environments. | MEDIUM | Agent runtime adapter |
| `atlas doctor` readiness check | Claude Code, opencode both expose doctor/health commands. Operators expect a single command to diagnose all issues. | LOW | Auth store, provider registry, gateway health |
| Clear exit codes (0 success, non-zero failure) | Table stakes for any scripting-capable CLI. | LOW | All commands |
| No secrets in any CLI output | Table stakes. Violations create irreversible trust damage. | LOW | Auth store redaction layer |

### Differentiators

| Feature | Value Proposition | Complexity | ATLAS Surface Dependency |
|---------|-------------------|------------|--------------------------|
| `atlas auth status/add/list/remove/doctor` full subcommand tree | opencode exposes `auth login/list/logout`. ATLAS expands to include doctor (validity check) and remove (explicit revocation). More actionable than bare auth. | MEDIUM | Auth store |
| `atlas providers list/status/doctor` | No comparable tool surfaces provider health this clearly. Most tools conflate provider + credential. | MEDIUM | Provider registry |
| `atlas models discover/list --all/doctor` | Discovery + multi-source listing with source/status/auth columns is unique. opencode has `models [provider]`; ATLAS adds source transparency. | MEDIUM | Model registry |
| `atlas route show/set/doctor` | Task-class routing policy is an ATLAS concept absent from other tools. Enables `cheap_summary → openrouter/fast-model`, `high_reasoning → openrouter/claude-sonnet`. | HIGH | Route policy table |
| `atlas mission status/bind` from CLI | No other CLI tool surfaces mission state from a terminal command. | MEDIUM | Mission lifecycle (v1.0) |
| Secret-safe output verified by automated redaction tests | Most tools rely on convention, not tests. ATLAS should have CI-enforced redaction tests proving no key values appear in any command output. | LOW | Test suite |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Importing Codex CLI credentials into ATLAS | Operator already has Codex token and wants to reuse it | Creates dependency on external tool's credential format; Codex auth.json format is undocumented and can change; legal/API TOS risk. | Read-only Codex detection only. Operator adds their OpenAI API key to ATLAS auth store separately. |
| Global `--verbose` flag that dumps config with secrets | Debugging convenience | Config dumps always risk printing credentials if masking logic has a gap. | `--debug` flag that prints non-secret fields only. Separate `atlas auth doctor` for credential validity. |

---

## Category: AUTH — ATLAS-Owned Auth Store

### Table Stakes

| Feature | Why Expected | Complexity | ATLAS Surface Dependency |
|---------|--------------|------------|--------------------------|
| Auth store at `~/.atlas/auth.json` | Hermes uses `~/.hermes/auth.json`; opencode uses `~/.local/share/opencode/auth.json`; Codex uses `~/.codex/auth.json`. Operators expect tool-scoped credential storage, never shared. | LOW | File system |
| Atomic write (write-to-temp + rename) | Auth files written non-atomically are corrupted if process dies mid-write. Cross-process lock prevents race on concurrent `atlas auth add` calls. | LOW | Rust or Python file I/O with tempfile |
| Cross-process file lock | Without locking, two simultaneous `atlas` processes can corrupt the auth file. | LOW | File lock library (`fcntl`/`flock` on POSIX; LockFile on Windows) |
| Redacted status output (show hint, never raw value) | Every serious tool redacts secrets in display. Pattern: `sk-...xyz` (last 4 chars). Never print full token. | LOW | Auth display layer |
| `atlas auth add <provider>` prompt flow (API key entry) | Minimum viable add flow. Operator pastes API key, ATLAS stores it. | LOW | Auth store write |
| `atlas auth list` showing providers + auth state | opencode `auth list`; Hermes shows configured providers. Operator expects to see what is configured without exposing values. | LOW | Auth store read |
| `atlas auth remove <provider>` | Explicit revocation path. Without it, operator must manually edit JSON. | LOW | Auth store write |
| `atlas auth status` (alias to list with health) | Convenience alias combining list + health check. | LOW | Auth store + provider health |
| `atlas auth doctor` (validity + permission check) | Checks file permissions (600/700 on POSIX), parse validity, token expiry if decodable, provider reachability. | MEDIUM | Auth store, provider health |
| Codex external tool detection (read-only) | ATLAS must detect whether `~/.codex/auth.json` exists and surface it as advisory (external, read-only). This satisfies the operator awareness use case without ATLAS depending on or mutating Codex state. | LOW | File system read-only probe |
| No mutation of `~/.codex` | Non-negotiable (locked decision). | LOW | Negative constraint — enforce via code review + test |

### Differentiators

| Feature | Value Proposition | Complexity | ATLAS Surface Dependency |
|---------|-------------------|------------|--------------------------|
| Profile-ready structure from day one (`~/.atlas/profiles/default/`) | Enables multi-context operation later (personal/work/client) without breaking change to file format. opencode and Hermes both support profile concepts. | LOW | Auth store design |
| Credential pool support (multiple keys per provider) | Enables rotation/failover at the credential level, not just provider level. Hermes has credential pool concept. | HIGH | Auth store schema |
| OAuth device-code flow for providers that support it (Anthropic, Google) | API-key-only entry is functional but inferior for providers that offer OAuth. Device code (print URL, poll for token) avoids user pasting long API keys. | HIGH | OAuth client library |
| Token expiry detection + refresh hint | If credential has expiry metadata, `auth doctor` surfaces time-to-expiry and remediation command before it fails mid-run. | MEDIUM | Auth store expiry field |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| OS keychain integration (v1.1) | More secure than plaintext file | Keychain APIs differ significantly between Windows (DPAPI/Credential Manager), macOS (Keychain), and Linux (Secret Service/libsecret). Adds platform-specific native code risk. File store with restricted permissions (600) is acceptable for v1.1. | Defer to v1.2+. File store with correct permissions is the v1.1 standard. |
| OAuth callback server without documented threat model | Allows richer OAuth flows | A local HTTP server on a fixed port is an attack surface. Binding to loopback only, short-lived server, state validation, and PKCE are required before any OAuth callback is shipped. | Write the threat model first (Phase 10.0). Ship OAuth only after threat model is reviewed. |
| Shared credential store (ATLAS + other tools reading same file) | Convenience | Creates implicit dependency coupling; ATLAS cannot control format changes; other tools may write malformed data. | ATLAS stores only in `~/.atlas`. Read-only probes of other tool stores are acceptable (Codex detection). |

---

## Category: PROVIDERS — Provider Registry

### Table Stakes

| Feature | Why Expected | Complexity | ATLAS Surface Dependency |
|---------|--------------|------------|--------------------------|
| Provider modeled separately from credential | Conflating them (as v1.0 did) makes health status ambiguous and prevents multiple credentials per provider. opencode separates provider config from auth.json. | MEDIUM | New `provider_registry` table |
| Provider health check (can we reach this endpoint?) | Operators need to know if a provider is offline before trying to use it. Short timeout (1–3s) probe. | LOW | Provider registry + HTTP probe |
| Provider source shown in status output | Operator must know if a provider came from ATLAS config, auth store, or external detection. | LOW | Source field in registry |
| Honest offline/unavailable display | Showing a provider as available when it is offline erodes trust immediately. | LOW | Health check result |
| `atlas providers list` and `atlas providers status` | Minimum CLI surface for provider visibility. | LOW | Provider registry read |
| `atlas providers doctor` | Explains each unhealthy provider with actionable remediation. | LOW | Health check + auth check |

### Differentiators

| Feature | Value Proposition | Complexity | ATLAS Surface Dependency |
|---------|-------------------|------------|--------------------------|
| API mode/runtime adapter field (chat_completions vs responses vs anthropic_messages vs local_openai_compatible) | Most tools implicitly assume OpenAI chat_completions. ATLAS must explicitly model the adapter so the agent runtime knows how to call each provider. Critical for Codex Responses API, Anthropic messages API, and local sidecars. | MEDIUM | Provider registry schema |
| Risk class field on provider (remote-paid, remote-free, local-noauth) | Enables safety policy: local/free providers can be probed freely; paid remote providers only when auth exists. Prevents accidental billing surprises. | LOW | Provider registry schema |
| Codex external tool detected as advisory provider entry | `codex` appears in `atlas providers list` as `source: codex_external_readonly, status: detected` giving operators unified visibility across their AI tool environment. | LOW | File system probe, provider registry |
| FreeLLMAPI / LM Studio / Ollama local sidecar entries | Local sidecars are probed with short timeouts on well-known ports (FreeLLMAPI: 3001, LM Studio: 1234, Ollama: 11434). Present even when offline so operator can see what was configured. | MEDIUM | Provider registry, HTTP probe |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Auto-probe all remote providers on startup | Discover what's available | Probing paid remote endpoints without auth risks unnecessary billing or quota consumption. Also slows startup. | Remote providers only probed when ATLAS has credentials for them AND `--include-remote` flag is passed. Local sidecars always probed (no auth, known ports, cheap timeout). |

---

## Category: MODELS — Model Registry

### Table Stakes

| Feature | Why Expected | Complexity | ATLAS Surface Dependency |
|---------|--------------|------------|--------------------------|
| Model rows include `source` column | Operators must know if a model came from a seed row, live API discovery, or local sidecar. v1.0 showed only seeded rows with no provenance. | LOW | model_registry_v2 schema |
| Model rows include `auth_status` column | Showing a model as available when auth is missing is misleading. | LOW | Auth store join |
| Model rows include `status` column (available/offline/needs_login/rate_limited) | Honest status prevents operators from trying models that will fail immediately. | LOW | Health check + auth join |
| `atlas models list --all` with source/status/auth columns | Standard output. opencode has `models [provider]`; ATLAS expands with provenance and status. | LOW | model_registry_v2 read |
| `atlas models discover` (merge all sources) | Operators expect discovery to actually query live endpoints, not just show static seeds. | MEDIUM | Discovery algorithm (auth-store + sidecar + remote API) |
| Source-scoped deactivation (not global) | If OpenRouter goes offline, OpenRouter models are deactivated; local models are unaffected. v1.0 had no source concept. | MEDIUM | model_registry_v2 schema, per-source status |
| Seeded fallback rows still listed (marked as `source: seeded`) | Backward compatibility with v1.0. Seeds provide a baseline when no live provider is configured. | LOW | Backward compat migration |
| Cockpit Models page reflects real registry | v1.0 cockpit shows only 3 seeded rows. v1.1 must fetch from live registry including source/status/auth. | MEDIUM | Gateway /models endpoint extension, SvelteKit cockpit |

### Differentiators

| Feature | Value Proposition | Complexity | ATLAS Surface Dependency |
|---------|-------------------|------------|--------------------------|
| Task suitability tags on models (`coding`, `fast_background`, `high_reasoning`, `vision`) | Enables intelligent route policy. opencode has capability metadata via models.dev; ATLAS can carry these as tags from discovery or manual override. | MEDIUM | model_registry_v2 metadata_json |
| `context_window` field with visual display | Operators need to know before loading a large context whether the model can handle it. | LOW | model_registry_v2 schema, TUI status bar |
| `tool_support` and `reasoning_support` flags | Agent runtime must know whether a model supports tool calls before dispatching tool-using tasks to it. | LOW | model_registry_v2 schema |
| `atlas models doctor` with per-model remediation | Per-model explanation of why a model is unavailable and what command fixes it. Goes beyond provider-level doctor. | MEDIUM | Auth store + health check |
| `atlas route show/set` for task-class routing | Route policy separates "what model do I use for coding" from "which model is configured". Hermes has routing concepts; ATLAS should formalize them as operator-configurable policy. | HIGH | route_policy table |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Auto-query paid provider `/models` endpoint on every startup | Always have fresh model list | `/models` API calls may count against quota or incur cost depending on provider. Also reveals intent (you are querying this provider) even before the operator has confirmed they want to use it. | Cache model list; refresh only on explicit `atlas models discover` or `--refresh` flag. Respect `last_seen` TTL. |
| Global deactivation when any source goes offline | Simplicity | Kills all models when one provider is temporarily down. Destroys operator's ability to fall back to local or other providers. | Per-source deactivation only. |

---

## Category: AGENT — Runtime Adapter and Chat Loop

### Table Stakes

| Feature | Why Expected | Complexity | ATLAS Surface Dependency |
|---------|--------------|------------|--------------------------|
| `atlas chat -q` returns real response or precise auth remediation | Minimum credibility test. If first `atlas chat -q "ping"` produces either a real response or a human-actionable error, the harness is credible. | MEDIUM | Hermes AIAgent adapter, auth store, provider registry |
| Interactive chat through CLI/TUI | Operators expect to hold a conversation, not just one-shot queries. | MEDIUM | Hermes AIAgent adapter, session persistence |
| Tool call visibility in TUI during agent execution | Operators need to see what the agent is doing (file reads, web calls, bash). Claude Code and Hermes both show this inline. | MEDIUM | Hermes ToolTrail, audit event bus |
| Dangerous tool approval gates preserved | Critical safety requirement. ATLAS must not strip the approval prompts that Hermes/Hermes AIAgent use for shell execution and file writes. | LOW | Hermes tool approval hooks |
| Session state persisted and resumable | Agent conversations should survive TUI restarts. Hermes uses `session.resume` RPC. | MEDIUM | Session store, Hermes session model |
| Audit metadata on model calls | Every model call should emit at minimum: provider, model_id, timestamp, token usage, session_id. Connects agent activity to ATLAS audit event bus. | MEDIUM | Audit event bus (v1.0), ATLAS runtime adapter |

### Differentiators

| Feature | Value Proposition | Complexity | ATLAS Surface Dependency |
|---------|-------------------|------------|--------------------------|
| Mission-bound chat (chat creates/updates mission state) | No comparable harness surfaces the concept of binding a chat session to a project mission. Unique ATLAS structural advantage. | HIGH | Mission/run lifecycle (v1.0), ATLAS runtime adapter |
| OpenAI/Codex-compatible lane tried FIRST, then automatic fallback cascade (locked decision) | Operators expect their preferred provider to be primary. Fallback should be automatic and transparent, not manual reconfiguration. | HIGH | Provider fallback cascade (see concrete spec below) |
| Subagent/task activity display in TUI | Hermes `SubagentAccordion` with heat-map. ATLAS inherits and brands this. | HIGH | Hermes TUI, ATLAS runtime adapter |
| Slash commands for agent control (`/stop`, `/approve`, `/deny`, `/background`) | Operators need to interrupt, approve, or background running tasks from TUI without killing the session. | MEDIUM | TUI slash command registry, Hermes interrupt RPC |
| Free chat sessions auditable even without mission binding | Every interaction is loggable. Sessions without a mission still emit audit events. | MEDIUM | Audit event bus (v1.0) |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Rewriting the Hermes agent loop from scratch | ATLAS-native agent loop | High risk, high effort, duplicates tested Hermes code. No operator benefit in v1.1. | Thin ATLAS runtime adapter over Hermes AIAgent. ATLAS adds mission/audit semantics on top; does not replace the loop. |
| Streaming provider responses directly from Hermes to TUI without audit layer | Simplicity | ATLAS-grade audit requires every model call to emit structured events. Bypassing the audit layer makes calls untraceable. | Emit audit events at the adapter boundary, not inside the Hermes loop. |

---

## Category: NATIVE — Tauri 2 Shell

### Table Stakes

| Feature | Why Expected | Complexity | ATLAS Surface Dependency |
|---------|--------------|------------|--------------------------|
| Tauri 2 shell (no Electron) | Locked decision (D-005, D-022). Operators and the project explicitly reject Electron. Tauri 2 is stable (2.0 released 2024). | HIGH | Tauri 2 Rust workspace |
| Embed existing SvelteKit cockpit | v1.0 cockpit is already built. Native shell should wrap it, not replace it. | MEDIUM | apps/cockpit-web adapter-static build |
| PTY terminal pane running `atlas` | Operators want to run the TUI inside the native window. xterm.js + tauri-plugin-pty (or alternative) provides bidirectional PTY. | HIGH | TUI, tauri-plugin-pty |
| IPC allowlist documented and scoped | Tauri 2 replaced Tauri 1 allowlist with capabilities/permissions/scopes model. Each IPC command must be explicitly permitted. | MEDIUM | Tauri 2 capabilities config |
| Threat model document for native IPC | Before any privileged IPC is shipped, a written threat model is required. | LOW | Documentation |
| No secrets in UI/logs/screenshots | The native window must not display credential values in any visible surface. | LOW | Redaction layer consistency |
| `atlas --help` and `atlas tui` runnable from PTY pane | Minimum UAT criterion: shell opens, PTY launches `atlas`, commands execute. | LOW | TUI, PTY integration |

### Differentiators

| Feature | Value Proposition | Complexity | ATLAS Surface Dependency |
|---------|-------------------|------------|--------------------------|
| Unified window: cockpit (SvelteKit) + PTY pane side-by-side | Operator can view mission/audit/wiki web cockpit alongside the terminal agent session. No other tool does this natively. | HIGH | Tauri 2 multi-webview or split layout |
| Auth/model readiness panel in native shell | Native window shows provider/model health at a glance, even when PTY is running a chat session. | MEDIUM | Provider registry, model registry, native IPC |
| Native approval prompt overlay for dangerous tool calls | Shell can intercept tool approval requests from the TUI and show a native dialog. More ergonomic than TUI inline prompt. | HIGH | Tool approval RPC, Tauri dialog API |
| PTY uses ATLAS's own `atlas tui` not a bare shell | The PTY pane is purpose-built for `atlas tui`, not a generic bash session. This makes the native shell feel like an ATLAS product, not a terminal emulator with a cockpit stuck next to it. | LOW | TUI launch |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Electron as fallback if Tauri proves hard | Safety net | Electron is explicitly ruled out (D-005, D-022). Using Electron even temporarily sets a bad precedent and adds ~100MB to distribution. | If Tauri 2 PTY proves blocked, defer native shell to post-v1.1 rather than switch to Electron. |
| Tauri shell built before TUI/auth/model are stable | Showing progress | A native shell wrapping a broken harness gives false confidence. Shell UAT cannot pass until TUI, auth, and model discovery pass independently. | Gate Tauri work on TUI + auth + agent green. |
| Bundling OS keychain integration in v1.1 Tauri shell | Secure credential storage | Platform-specific native code (DPAPI on Windows, Keychain on macOS, libsecret on Linux) adds significant implementation risk. File-store-first is sufficient for v1.1. | Defer OS keychain to v1.2+. Tauri v1.1 shell reads from `~/.atlas/auth.json`. |
| Global hotkey and tray icon | Operator convenience | Nice-to-have that adds complexity to the Tauri app lifecycle and requires additional OS permissions. Defers focus from core harness. | Defer to P2 / v1.2+. |

---

## Provider Fallback Cascade — Concrete Specification

This is the most critical cross-cutting behavior. The locked decision is: "OpenAI/Codex-compatible lane tried first, then automatic fallback through other configured providers that actually respond." This section makes that precise and testable.

### Cascade Ordering Logic

The cascade order is NOT fixed priority. It is determined at runtime by liveness, not by configuration position:

```
1. ATTEMPT: OpenAI/Codex-compatible provider (highest priority lane)
   - API mode: chat_completions OR codex_responses (as configured)
   - Timeout for first token: 10s (configurable)
   - If 200 OK + streaming begins → use this provider for the full response

2. ON FAILURE from step 1 (auth error, 4xx, 5xx, timeout, connection refused):
   - Classify error:
     - 401/403 → auth_failed (do NOT retry; no backoff; skip to next provider)
     - 429 → rate_limited (skip to next provider; mark with cooldown)
     - 500/502/503/504 → transient (retry once with 1s delay, then skip)
     - timeout → transient (skip immediately)
     - connection refused → offline (skip; mark provider offline)
   
3. BUILD FALLBACK POOL:
   - All configured providers with credentials present
   - Exclude providers in cooldown (model-level cooldown, NOT provider-level)
   - Exclude providers with permanent auth_failed status
   - Order by: local/free first (no billing risk), then remote paid
   - Do NOT use fixed config order; use liveness-detected order

4. ITERATE FALLBACK POOL:
   - Try each provider with same timeout (10s first-token)
   - Apply same error classification
   - Do NOT cascade 401/403 — these are non-retryable
   - Stop on first 200 OK + streaming
   - If pool exhausted → fail with structured error

5. USER-VISIBLE BEHAVIOR during cascade:
   - TUI shows: "[attempting fallback: openrouter]" in activity panel
   - NOT: raw HTTP error codes or internal provider names
   - Final failure message: actionable ("No configured provider responded. Run: atlas auth doctor")

6. CIRCUIT BREAKER (per-model, not per-provider):
   - Track failure count per (provider_id, model_id) in session state
   - Threshold: 3 failures → mark model as cooldown for 60s
   - A different model on the same provider is NOT affected
   - After cooldown: probe with lightweight health-check before re-entering pool
```

### Failure Classification Table

| HTTP Status | Error Class | Retry? | Cascade? | Cooldown? | Show User |
|-------------|-------------|--------|----------|-----------|-----------|
| 401/403 | auth_failed | No | Yes | No (permanent until re-auth) | "Auth expired for [provider]. Run: atlas auth add [provider]" |
| 429 | rate_limited | No | Yes | Yes (60s) | "[provider] rate-limited, trying next" |
| 500/502/503/504 | transient | Once (1s) | Yes (after retry) | Yes (30s) | "[provider] unavailable, trying next" |
| timeout (>10s) | timeout | No | Yes | Yes (30s) | "[provider] timed out, trying next" |
| connection refused | offline | No | Yes | Yes (120s) | "[provider] offline, trying next" |
| 400 | bad_request | No | No | No | "Model call failed: [reason]" |
| 404 | not_found | No | No | No | "Model [id] not found on [provider]" |

### Testable Invariants

1. Cascade never fires on 400 (bad request is caller fault, not provider fault).
2. Cascade never fires on 401/403 for non-credential issues (wrong model name is a 404, not an auth error).
3. A 429 on `claude-opus-4` does NOT put `claude-sonnet-4-6` into cooldown (model-level isolation).
4. When all providers are exhausted, output is a structured error with remediation text, not a stack trace.
5. No provider in cooldown is attempted before its timer expires.
6. The OpenAI/Codex-compatible lane is always the first attempt, even if it failed in the previous session (cooldown resets per session start).
7. Cascade activity messages appear in the TUI activity panel before the final result.

---

## Feature Dependencies

```
ATLAS Auth Store
    └──required-by──> Provider Health Check
    └──required-by──> Model Registry (auth_status field)
    └──required-by──> Agent Runtime (credential resolution)
    └──required-by──> `atlas chat -q` (provider auth)
    └──required-by──> TUI auth/model warning panel

Provider Registry
    └──required-by──> Model Registry (provider_id FK)
    └──required-by──> Provider Fallback Cascade
    └──required-by──> `atlas providers list/status/doctor`

Model Registry v2
    └──required-by──> TUI status bar (model display)
    └──required-by──> Route Policy
    └──required-by──> Cockpit Models page (truth alignment)
    └──required-by──> `atlas models list --all`

Hermes TUI (adapted/extended)
    └──required-by──> ATLAS TUI (branded, mission panels added)
    └──required-by──> PTY in Tauri native shell

ATLAS Runtime Adapter (thin wrapper over Hermes AIAgent)
    └──required-by──> `atlas chat -q` (one-shot)
    └──required-by──> Interactive chat
    └──required-by──> Provider Fallback Cascade
    └──required-by──> Audit metadata on model calls

Provider Fallback Cascade
    └──required-by──> `atlas chat -q` (reliable first response)
    └──required-by──> ATLAS TUI (cascade activity display)

Tauri 2 shell scaffold
    └──required-by──> PTY pane (atlas tui in native window)
    └──required-by──> Native IPC threat model (must precede privileged IPC)
    └──Gate:──> TUI + auth + agent must pass green before Tauri UAT
```

### Dependency Notes

- Auth store is the critical path for almost everything. Phase 10.1 (auth store) must complete before Phases 10.2 (agent chat), 10.3 (model discovery), and 10.4 (TUI) can pass acceptance.
- Model registry v2 schema migration must preserve v1.0 seeded rows (backward compat).
- Tauri native shell is intentionally last (Phase 10.5) because it wraps a working harness, not an incomplete one.
- The JSON-RPC gateway between TUI and runtime is the architectural load-bearer: it must be designed before TUI and agent work diverge.

---

## MVP Definition (v1.1)

### Launch With (v1.1 = all of these)

- [x] ATLAS auth store at `~/.atlas/auth.json` with atomic write, lock, redaction
- [x] `atlas auth add/list/status/remove/doctor` for at least one real provider
- [x] Codex external tool detected read-only; `~/.codex` never mutated
- [x] Provider registry with separate health/status/source fields
- [x] Model registry v2 with source/status/auth columns
- [x] `atlas models discover` + `atlas models list --all`
- [x] ATLAS runtime adapter over Hermes AIAgent
- [x] `atlas chat -q` returning real response or actionable auth error
- [x] Interactive chat through TUI
- [x] Provider fallback cascade (OpenAI-first, then liveness-ordered)
- [x] ATLAS-branded TUI with transcript, composer, streaming, tool activity, status bar
- [x] Audit metadata on model calls
- [x] Tauri 2 shell with cockpit embed and PTY pane running `atlas tui`
- [x] IPC threat model document
- [x] All commands pass redaction tests (no credential values in any output)

### Add After Validation (v1.2)

- [ ] OS keychain integration — trigger: operators request it; file store proven insufficient
- [ ] OAuth device-code flow for Anthropic/Google — trigger: API key flow proves insufficient for target audience
- [ ] Credential pools — trigger: rotation use case emerges
- [ ] Native approval prompt overlay in Tauri shell — trigger: TUI inline approval proves insufficient
- [ ] Tray icon and global hotkey — trigger: operator workflow feedback
- [ ] Model latency benchmarking — trigger: routing performance questions arise

### Future Consideration (v2+)

- [ ] CRM/Twenty integration — deferred by D-007
- [ ] Public marketplace/skill installer — deferred by scope
- [ ] Multi-user cloud auth — deferred by scope
- [ ] Mobile — deferred by scope
- [ ] Rust TUI rewrite — reassess when Hermes TUI adaptation hits limits

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Auth store (atomic + lock + redact) | HIGH | LOW | P1 |
| `atlas auth add/status/doctor` | HIGH | LOW | P1 |
| Codex read-only detection | MEDIUM | LOW | P1 |
| Provider registry with health | HIGH | MEDIUM | P1 |
| Model registry v2 (source/status/auth) | HIGH | MEDIUM | P1 |
| `atlas models discover/list --all` | HIGH | MEDIUM | P1 |
| ATLAS runtime adapter (Hermes AIAgent) | HIGH | MEDIUM | P1 |
| `atlas chat -q` one-shot | HIGH | MEDIUM | P1 |
| Provider fallback cascade | HIGH | HIGH | P1 |
| ATLAS TUI (transcript + composer + streaming + status bar) | HIGH | HIGH | P1 |
| Audit metadata on model calls | HIGH | LOW | P1 |
| Tauri 2 scaffold + cockpit embed | MEDIUM | HIGH | P1 |
| PTY pane running `atlas tui` | HIGH | MEDIUM | P1 |
| Redaction test suite | HIGH | LOW | P1 |
| Mission context panel in TUI | HIGH | MEDIUM | P2 |
| `atlas route show/set` | MEDIUM | HIGH | P2 |
| Session resume (`/resume`) | MEDIUM | MEDIUM | P2 |
| Token/context window progress bar | MEDIUM | LOW | P2 |
| Subagent/task accordion in TUI | MEDIUM | HIGH | P2 |
| Native auth/model readiness panel | MEDIUM | MEDIUM | P2 |
| OS keychain integration | MEDIUM | HIGH | P3 |
| OAuth device-code flow | MEDIUM | HIGH | P3 |
| Native approval prompt overlay | LOW | HIGH | P3 |
| Tray icon / global hotkey | LOW | MEDIUM | P3 |

---

## Competitor Feature Analysis

| Feature | Hermes v0.14.0 | opencode | Aider | Claude Code | ATLAS v1.1 Approach |
|---------|----------------|----------|-------|-------------|---------------------|
| TUI architecture | React/Ink + Python JSON-RPC gateway over stdio | SolidJS + HTTP server (opencode serve) | Python Rich terminal, no full TUI | Node.js + React Ink | Fork/extend Hermes Ink TUI; add ATLAS mission panels |
| Status bar contents | FaceTicker verb + context bar (color-coded) | Model + provider + token display | Tokens + cost | Model + session info | Brand + profile + model + auth state + mission + token bar |
| Auth store location | `~/.hermes/auth.json` | `~/.local/share/opencode/auth.json` | `.aider.conf.yml` / env vars | `~/.claude/` | `~/.atlas/auth.json` (profile-ready) |
| Provider fallback | Not documented in v0.14.0 | None documented; single provider per session | None (user switches manually) | Via ANTHROPIC_API_KEY / USE_BEDROCK flags | OpenAI-compatible first; then liveness-ordered cascade; circuit breaker per model |
| Model discovery sources | Config + env | models.dev registry + credentials file | No multi-source discovery | Anthropic API only | seeded + auth-store + sidecar probe + remote API query + codex read-only |
| Codex detection | None | None | None | N/A (is Anthropic's tool) | Read-only probe of `~/.codex/auth.json`; surface as advisory provider |
| Mission context in TUI | None | None | None | None | ATLAS-specific: mission panel, `/mission bind`, audit references |
| Native shell | None | Electron desktop | None | None | Tauri 2 (Rust), no Electron, PTY + cockpit embed |
| Tool approval gates | Yes (interactive confirm) | Yes | Yes (with --yes bypass) | Yes | Inherited from Hermes; preserved in ATLAS adapter |
| Session resume | Yes (`session.resume` RPC) | Sessions persist by project | Continuation via `--continue` | `/resume` command | Inherited from Hermes; extended with mission binding |

---

## Sources

- Hermes v0.14.0 vendored source (`foundation/atlas-hermes/`): TUI architecture, gateway, session model — HIGH confidence
- Hermes TUI DeepWiki deep dive (deepwiki.com/nousresearch/hermes-agent/3.3-tui) — HIGH confidence
- Hermes feature requests #504, #683 (github.com/NousResearch/hermes-agent) — MEDIUM confidence (community evidence of table stakes)
- opencode documentation (opencode.ai/docs/cli, opencode.ai/docs/config) — HIGH confidence
- opencode provider/model configuration (deepwiki.com/sst/opencode/3.3-provider-and-model-configuration) — HIGH confidence
- OpenAI Codex CLI auth documentation (developers.openai.com/codex/auth) — MEDIUM confidence (observed behavior, not open-source)
- Tauri 2 IPC/capabilities architecture (v2.tauri.app/blog/tauri-20) — HIGH confidence
- tauri-plugin-pty (github.com/Tnze/tauri-plugin-pty): active development, not production-stable — LOW confidence (evaluate alternatives)
- Circuit breaker and cascade patterns: getmaxim.ai production guide; openclaw/openclaw issue #49732 (cascade failure case study) — MEDIUM confidence
- LLM retry/backoff best practices: AWS prescriptive guidance, dev.to/sandhu93 — MEDIUM confidence
- ATLAS prep documents (`v1.1-extra-marathon-scope.md`, `v1.1-tui-agent-ux-spec.md`, `v1.1-provider-model-registry-spec.md`, `v1.1-exhaustive-backlog.md`) — HIGH confidence (operator-authored, primary source)

---

*Feature research for: ATLAS v1.1 Agent Harness & Native Operator Shell*
*Researched: 2026-06-15*
