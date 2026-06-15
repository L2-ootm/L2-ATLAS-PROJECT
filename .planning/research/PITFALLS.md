# Pitfalls Research

**Domain:** Agentic harness (TUI + owned auth + model registry + agentic chat + Tauri PTY) added to an audit-first Windows system (ATLAS v1.1)
**Researched:** 2026-06-15
**Confidence:** HIGH — derived directly from the v1.1 prep set, project constraints, and concrete domain knowledge for each capability area. Not general web research.

---

## Critical Pitfalls

### Pitfall 1: Auth File Corruption via Concurrent Writers (Windows Locking)

**What goes wrong:**
Two processes (TUI session + background model-discover refresh) both read `~/.atlas/auth.json`, both modify in memory, and both write back. On Windows, Python's default file open does not hold an exclusive lock between read and write — the second writer silently overwrites the first. The file ends up truncated or with half-written JSON.

**Why it happens:**
Developers pattern-match on Unix `fcntl` locking, which does not exist on Windows. Windows file locking uses `msvcrt.locking` or `win32con.LOCKFILE_EXCLUSIVE_LOCK` via `pywin32`. The common mistake is either skipping locking entirely ("only one process writes") or using a cross-platform library that silently no-ops on Windows.

**How to avoid:**
- Use `msvcrt.locking` or `portalocker` (wraps `LockFileEx` on Windows) held across the full read-modify-write cycle, not just during the write.
- Write to a temp file in the same directory, then `os.replace()` (atomic on Windows when src and dst are on the same volume and filesystem). Never `write()` directly to the auth file.
- Validate JSON after write before releasing lock.
- Wrap in a retry loop for the lock-acquisition phase only (not for the write itself).
- Tests: inject two concurrent writers via threads; assert final file is valid JSON and neither write is silently lost.

**Warning signs:**
- `atlas auth status` intermittently fails to parse `auth.json`.
- `auth.json` is zero-length after a model-discover run that coincided with a TUI startup.
- The process that "wins" the race is not deterministic.

**Phase to address:** Phase 10.1 (ATLAS-owned auth store) — must be the first implementation requirement, before any feature that uses the auth file. Concurrent-write test is an acceptance gate for 10.1.

---

### Pitfall 2: Secret Values Leaking into Logs, Audit JSONL, or CLI Output

**What goes wrong:**
An API key or OAuth token reaches a log line in one of these ways:
1. Exception traceback includes the `requests.PreparedRequest` object, which has the `Authorization` header in its repr.
2. The `auth.json` dict is passed to a generic `logger.debug("config: %s", config)` call.
3. A Pydantic model that holds the credential is serialized to the ATLAS audit JSONL without field exclusion.
4. `atlas auth status` prints the `secret_ref` field because the template forgot to skip it.
5. A redacted hint like `sk-...abcd` is constructed by slicing — but the slice logic breaks for short keys and prints the full value.

**Why it happens:**
Audit-first logging is comprehensive by design, which is exactly what makes it dangerous when credentials flow into the audit path. The same structured-logging pattern that captures everything for traceability will capture secrets if the credential object is not sanitized before entering the event bus.

**How to avoid:**
- Define a `RedactedStr` type (Pydantic custom type or a thin wrapper) that always renders as `<redacted>` in `__repr__`, `__str__`, and JSON serialization. Use it for all secret fields.
- Implement `redact_auth_dict(d: dict) -> dict` that strips known secret keys before any log/audit emission. Unit test it with a fixture that contains all known field names.
- Add a `REDACTION_SENTINEL` string (`[REDACTED]`) and grep tests that scan CLI output, log files, and JSONL audit exports for known test-key prefixes (`sk-`, `Bearer `, `eyJ`) after every test that exercises auth paths.
- For HTTP client (httpx/requests): configure a logging transport that strips `Authorization` and `x-api-key` headers from debug logs.
- The `atlas auth status` command must have a dedicated output formatter — never pass the raw auth dict through a generic formatter.

**Warning signs:**
- Any `debug` or `error` log line contains `sk-` or `Bearer ` or a token-shaped string.
- `atlas audit export` produces JSONL that contains a key matching a regex for known secret prefixes.
- A Pydantic model's `.model_dump()` output includes raw credential values.

**Phase to address:** Phase 10.1 (auth store implementation) and Phase 10.2 (agentic chat, where model calls carry credentials). Redaction tests are a gate for both. Add a CI check that greps audit output for secret patterns.

---

### Pitfall 3: `~/.codex` Accidental Mutation

**What goes wrong:**
ATLAS accidentally writes to or depends on `~/.codex` in one of these scenarios:
1. The Hermes foundation's `runtime credential resolver` is called without scoping — it resolves Codex credentials and attempts to refresh/write back to `~/.codex/auth.json`.
2. A subprocess call to `codex` CLI is made with flags that trigger a side effect (e.g., `codex auth refresh`).
3. Model discovery calls an endpoint using Codex-resolved tokens, and the response includes a new token that gets persisted to the Codex store.
4. A developer adds a "convenience" code path that copies Codex tokens into ATLAS store but also touches the original file.
5. `~/.codex/config.toml` is opened for write instead of read due to a typo or wrong file handle mode.

**Why it happens:**
The Hermes foundation was designed to manage its own store AND detect Codex. The ATLAS fork inherits Hermes credential resolver code. If that code is called without restricting the write path to `~/.atlas`, it will write wherever it was designed to write. This is a namespace pollution bug introduced by inheritance without isolation.

**How to avoid:**
- Codex detection is implemented as a separate, read-only module that never calls credential write functions. The module interface: `detect_codex() -> CodexStatus` — no write path, no credential imports.
- The Hermes credential resolver, if used, must be called with explicit `store_path=~/.atlas` parameter. Any codepath that could write to `~/.hermes` or `~/.codex` must be audited and either parameterized or replaced.
- In tests: create a fake `HOME` dir with a pre-populated `~/.codex/auth.json`. Run all Codex detection and model discovery paths. Assert that `~/.codex/auth.json` is byte-identical after the test (stat + md5/hash comparison).
- Acceptance gate: `atlas auth add <any-provider>` + `atlas models discover` does not modify any file under `~/.codex/`.

**Warning signs:**
- `~/.codex/auth.json` `mtime` changes after running any ATLAS command.
- ATLAS auth flow opens `~/.codex/auth.json` with write mode (visible via file handle audit or ProcMon on Windows).
- `atlas auth status` shows `source: ~/.codex` for an ATLAS-owned credential entry.

**Phase to address:** Phase 10.1 (Codex read-only detection module) and Phase 10.3 (model discovery, which enumerates Codex as a source). The no-mutation test is a hard gate that must pass before 10.1 closes. The test should be run on every PR that touches auth or discovery code.

---

### Pitfall 4: Fallback Cascade Masking Real Auth Errors

**What goes wrong:**
The provider fallback cascade (OpenAI/Codex-compatible first, then others) silently falls through to a working but wrong provider when the primary fails due to an auth error. The operator sees a response but does not know it came from the wrong provider/model. This breaks auditability (the audit record says "provider=openrouter" when the intent was "provider=codex-compatible") and can cause silent billing on unexpected providers.

**Why it happens:**
The cascade design conflates two failure categories: transient failures (timeout, 503) which warrant a retry/fallback, and permanent failures (401 Unauthorized, 403 Forbidden) which indicate misconfiguration and should halt with operator notification. Naive cascade code catches `Exception` broadly and falls through regardless of failure reason.

**How to avoid:**
- Classify errors before falling through:
  - `401`, `403`: auth failure — do not cascade, surface `ATLAS_AUTH_ERROR` with provider name and remediation.
  - `429`: rate limit — cascade is acceptable but must be logged with reason.
  - `5xx`, timeout: transient — cascade with log.
  - `404 /models` endpoint: discovery failure only, not inference failure.
- Every cascade event must emit a structured audit event: `{ event: "provider_fallback", from: "openai", to: "openrouter", reason: "timeout_503", at: "..." }`.
- The TUI/CLI must surface the active provider on every response, not just at startup. If the cascade fires, the status bar must update to show the actual provider used.
- Operator-visible warning when fallback occurs during interactive chat: `[Fell back to openrouter — openai timed out. Run atlas auth doctor for details.]`
- Acceptance gate: inject a 401 response from the primary provider in tests; assert cascade does NOT fire and an `AUTH_ERROR` event is emitted instead.

**Warning signs:**
- Responses arrive without any provider attribution in the audit record.
- `atlas auth status` shows a provider as `needs_login` but `atlas chat -q "ping"` succeeds — the cascade silently used another.
- Audit JSONL has a mix of providers across a session without explicit fallback events.

**Phase to address:** Phase 10.2 (agentic chat / provider routing). Cascade logic and error classification must be specced before implementation begins. The audit event for fallback is a Phase 10.2 acceptance gate.

---

### Pitfall 5: Infinite or Expensive Retry Loops in Model Discovery

**What goes wrong:**
`atlas models discover` calls a remote provider's `/models` endpoint. When the provider is unreachable or rate-limited, discovery retries indefinitely (or with very long backoff), blocking CLI startup or TUI initialization. Worse, if discovery is triggered on every ATLAS startup, it makes paid API calls just to list models, consuming quota.

**Why it happens:**
Discovery feels like a cheap read operation but it is actually a network call with auth. Developers copy retry patterns from request libraries without capping total attempts or adding circuit breakers. Startup-time discovery is a common "nice to have" that silently becomes a performance and cost problem.

**How to avoid:**
- Discovery is always opt-in or cache-first. `atlas models list` reads from the SQLite registry (fast, no network). `atlas models discover` explicitly hits the network with a `--timeout` flag and a hard cap (e.g., 5s per provider, 3 retries max).
- Cache discovery results in the registry with a `last_seen` timestamp. Default TTL: 1 hour for remote providers, 30s for local sidecars.
- Never trigger remote discovery on TUI startup. At startup, read from the local registry only; show stale indicators if `last_seen` is old.
- Circuit breaker: after 2 consecutive failures per provider, mark as `offline` and skip for 10 minutes. Do not hammer a down provider on every user action.
- Log every network call made during discovery with provider, endpoint, and response code. This satisfies the audit-first requirement and makes cost/quota debugging tractable.

**Warning signs:**
- `atlas` TUI startup takes >2s regularly.
- Provider shows as `offline` in registry but model calls still attempt it.
- API rate-limit errors appear in logs on startup, not just during active chat.

**Phase to address:** Phase 10.3 (model/provider discovery). Cache TTL policy and circuit breaker are design requirements before implementation. Startup benchmark (<500ms to first TUI paint) is a 10.3 gate.

---

### Pitfall 6: Model Registry Duplicate Rows and Audit History Destruction

**What goes wrong:**
Discovery runs twice with different sources. The same model (`gpt-4o`) appears once as `source=seeded` and once as `source=openai_api`. Re-discovery then "deactivates" the seeded row and creates a new active row, destroying the `first_seen` history. Or worse: the composite key `(model_id, provider_id, source)` is not enforced, so each discovery run inserts new rows rather than upserts.

**Why it happens:**
Model IDs are not globally unique — the same string `claude-sonnet-4-6` can come from `openrouter`, `anthropic`, and `seeded`. If the upsert key does not include `source`, discovery merges across sources incorrectly. The `first_seen` timestamp gets overwritten on each upsert if the query uses `INSERT OR REPLACE` instead of `INSERT ... ON CONFLICT DO UPDATE SET last_seen = ...`.

**How to avoid:**
- Primary key is `(model_id, provider_id, source)` as specified in the v1.1 registry spec. This is non-negotiable.
- Upsert preserves `first_seen`: `ON CONFLICT(model_id, provider_id, source) DO UPDATE SET last_seen=excluded.last_seen, status=excluded.status, ...` — never touch `first_seen` after initial insert.
- Seeded rows have `source=seeded` and are never overwritten by discovery. Discovery can add a parallel row for the same model from a real source; the seeded row remains as a fallback.
- Deactivation is source-scoped: if OpenRouter no longer lists `model-x`, set `deactivated_at` only on the `(model-x, openrouter, openrouter_api)` row. The seeded or other-source rows are unaffected.
- Tests: run discovery twice with the same fixture; assert row count is stable (no duplicates) and `first_seen` is unchanged.

**Warning signs:**
- `atlas models list --all` shows the same model ID multiple times with no source difference.
- `first_seen` changes between discovery runs.
- A model disappears from the list after a discovery run that did not explicitly delete it.

**Phase to address:** Phase 10.3 (model registry schema and discovery). The upsert semantics are a schema design gate before any discovery code is written. The deactivation-scope test is a 10.3 acceptance gate.

---

### Pitfall 7: Fake "Available" Models (Health Status Lies)

**What goes wrong:**
The registry shows `status=available` for a model that requires auth, but auth is missing. The operator starts a chat, gets a 401 mid-session, and the TUI shows a cryptic error. Worse: `atlas models list --all` shows `available` for local sidecars (LM Studio, FreeLLMAPI) that are not running. The operator trusts the list and only discovers the failure when a mission runs.

**Why it happens:**
Discovery runs a `/models` endpoint check but does not validate that the credential actually works for inference. A provider's `/models` endpoint may be unauthenticated (returns 200 even without valid key) while inference requires the key. Similarly, a sidecar that was running during discovery may have stopped.

**How to avoid:**
- Separate `auth_status` from `status` in the schema (the v1.1 spec already does this). `status=available` means the model is listed by the provider; `auth_status=configured` means ATLAS has a credential. Neither alone guarantees an inference call will succeed.
- Display both columns in CLI/TUI. Never collapse them into a single "available" label.
- For local sidecars: health check is a TCP connect to the port, not just a `/models` response cache. TTL for sidecar health is 30s, not 1h.
- For remote providers: optionally run a minimal inference probe (`atlas models doctor --probe <provider>`) only on explicit operator request, not on every discover run. Never probe automatically on startup.
- `atlas chat -q` must resolve credentials and check health before sending the first token. On failure, surface: `Provider X: auth missing. Run atlas auth add X.` before any streaming starts.

**Warning signs:**
- `atlas models list` shows `available` for a provider the operator knows is unconfigured.
- Local sidecar listed as `available` but `curl localhost:1234/v1/models` fails.
- `atlas chat` begins streaming then fails mid-response with a 401.

**Phase to address:** Phase 10.3 (model/provider discovery and health). The `auth_status` vs `status` distinction is a schema gate. Sidecar TCP health check is a 10.3 implementation requirement.

---

### Pitfall 8: Agentic Model Calls Bypassing Audit Metadata

**What goes wrong:**
`atlas chat` sends a request to the provider through the Hermes AIAgent adapter. The Hermes call succeeds and the response is returned, but no ATLAS audit event is emitted for the model call. The audit JSONL shows mission start/end but has no record of what was sent to which model with what parameters. This violates the non-negotiable: "all autonomous actions are auditable."

**Why it happens:**
The Hermes AIAgent emits its own internal events (possibly to `~/.hermes/logs/` or its own bus). The ATLAS adapter does not intercept those events and re-emit them on the ATLAS event bus. The developer assumes Hermes logging is sufficient, but it is not under ATLAS control, not in ATLAS JSONL format, and not linked to ATLAS mission/run IDs.

**How to avoid:**
- The ATLAS-over-Hermes adapter must wrap every call to `AIAgent` with a pre-call and post-call audit event:
  - Pre: `{ event: "model_call_start", provider, model, run_id, mission_id, input_tokens_est, tools_requested, timestamp }`
  - Post: `{ event: "model_call_end", provider, model, run_id, output_tokens, finish_reason, duration_ms, timestamp }`
- These events must go through the ATLAS event bus (same path as v1.0 audit events), not to a separate logger.
- For streaming responses: emit `model_call_start` before first chunk, `model_call_end` after final chunk with token counts from the usage field.
- Acceptance gate: run `atlas chat -q "ping"` and assert the ATLAS audit JSONL contains at least one `model_call_start` and one `model_call_end` event with non-null `run_id`.

**Warning signs:**
- `atlas audit export` for a session has no model call events, only session start/end.
- Hermes logs in `~/.hermes/` exist but ATLAS JSONL does not reflect the same calls.
- Token counts are not tracked per session.

**Phase to address:** Phase 10.2 (agentic chat and runtime adapter). Audit metadata wrapping is a design requirement for the adapter, not an afterthought. The audit JSONL assertion test is a 10.2 acceptance gate.

---

### Pitfall 9: Tool Approval Gates Lost in the Adapter Layer

**What goes wrong:**
Hermes AIAgent supports tool calls and has an approval flow. When ATLAS wraps Hermes, the tool approval callback is either not wired (silent auto-approve for all tools) or wired to Hermes' internal UI rather than ATLAS TUI/CLI. The operator sees tool calls executing without any approval prompt. Dangerous tools (file writes, shell commands) run unattended.

**Why it happens:**
The adapter pattern prioritizes getting a working call loop first; approval gates are UI concerns that are "added later." But by the time the adapter is stable, the approval gate API is baked in on the Hermes side and adding ATLAS-side interception requires deeper refactoring.

**How to avoid:**
- Define the approval gate interface before implementing the adapter. The adapter must expose a `ToolApprovalCallback` protocol that the TUI/CLI registers. Even if the v1.1 default is `auto_approve=False` (always prompt), the protocol must exist and be wired.
- In the TUI: every pending tool call is surfaced as a blocking prompt before execution. The operator must explicitly approve or deny. Session cannot proceed while an approval is pending.
- In `atlas chat -q` (one-shot mode): non-interactive approval defaults to deny for any tool that touches the filesystem or runs shell commands. Only network read tools may auto-approve in `--non-interactive` mode, and only if explicitly configured.
- Tests: configure a mock tool that the agent always wants to call; assert that without explicit approval the tool does not execute.

**Warning signs:**
- Tool calls in chat appear in audit log without a preceding `tool_approval_requested` event.
- Running `atlas chat -q "write a file"` creates a file without prompting.
- The Hermes-side approval prompt appears (in Hermes styling) instead of ATLAS prompt.

**Phase to address:** Phase 10.2 (agentic chat) — approval protocol is a design gate. Phase 10.4 (TUI) — the interactive approval UI is a TUI acceptance gate.

---

### Pitfall 10: Secret Leakage into Chat Transcripts and Wiki

**What goes wrong:**
1. The operator pastes an API key into chat for debugging. The key lands in the session transcript, which is persisted to the ATLAS audit JSONL and potentially synced to the wiki. Future wiki exports or support sessions expose the key.
2. A tool call response from an external API returns a secret in its body (e.g., a credential rotation endpoint). The raw tool output is stored verbatim in the audit transcript.
3. The `auth.json` file path is passed as context to the agent, and the agent reads and outputs its content.

**Why it happens:**
Audit-first capture is designed to record everything. Without a post-capture redaction pass on user content and tool outputs, secrets that enter the transcript via user action or tool output are permanently stored.

**How to avoid:**
- Apply the same `RedactedStr` / redaction-regex pass to all transcript content before persistence, not only to internal auth events. Known secret patterns: `sk-[A-Za-z0-9]{20,}`, `Bearer [A-Za-z0-9._-]{20,}`, `eyJ[A-Za-z0-9_-]{10,}` (JWT prefix).
- Teach the TUI composer to warn when the user input matches a secret pattern: `Warning: your input looks like an API key. Do not share credentials in chat.`
- Tools that return raw HTTP responses must pass their output through the redaction filter before the output is stored in the audit JSONL.
- The wiki runtime must not auto-page chat sessions without operator review. Chat sessions are audit records, not wiki content, unless explicitly promoted.
- Acceptance gate: inject a test API key pattern into a chat message; assert the persisted audit record does not contain the raw value.

**Warning signs:**
- The audit JSONL contains `sk-` or `Bearer ` strings.
- The wiki has a page that was auto-generated from a chat session containing an embedded key.
- `atlas wiki search key` returns results from a chat session.

**Phase to address:** Phase 10.2 (transcript persistence and redaction pass). Phase 10.4 (TUI composer warning). Phase 10.5 (wiki integration gate for chat promotion).

---

### Pitfall 11: Tauri IPC Over-Permissioned or Unconstrained

**What goes wrong:**
The Tauri 2 shell uses a single broad IPC command like `invoke("run_command", { cmd: "..." })` that lets the frontend pass any shell command to the Rust backend. A bug in the SvelteKit cockpit (or a malicious injected script) can invoke arbitrary system commands through the IPC channel. This is equivalent to a remote code execution surface.

**Why it happens:**
Native IPC in Tauri 2 is fast and tempting to use as a generic "run anything" bridge. The capability system exists in Tauri 2 but requires explicit allowlist configuration in `tauri.conf.json`. Developers often start with a permissive config, intend to restrict it later, and ship without restricting it.

**How to avoid:**
- Use Tauri 2's capability system (`capabilities/` JSON files) to enumerate exactly which IPC commands the frontend may call. The allowlist is the contract — no command exists unless explicitly added.
- IPC commands must have typed schemas on both the Rust handler side (via Serde) and the frontend side (via typed wrappers). A command that accepts a raw string is a red flag.
- The PTY terminal pane is the only surface that runs arbitrary commands — and it runs them as the user (not via IPC). The PTY surface must not be controllable from the SvelteKit app via an IPC command that passes a command string; the PTY must be launched by the Rust backend with a fixed command (`atlas tui`) or a fixed allowlist.
- Do not use `tauri::plugin::shell` with `sidecar: false` and a broad pattern match. Every executable the app may launch must be in the bundle sidecar list or a fixed known path.
- Threat model document: enumerate every IPC command, its parameter types, who may call it, and what privilege it requires. This document is a Phase 10.5 acceptance gate.

**Warning signs:**
- `tauri.conf.json` has `"shell": { "all": true }` or similar blanket permission.
- A frontend component passes user-typed input directly to an IPC invoke call.
- The capability JSON has no explicit `allow` list.

**Phase to address:** Phase 10.5 (Tauri native shell scaffold). The IPC allowlist and threat model document are acceptance gates before the shell ships. The capability config must be reviewed before Phase 10.6 UAT.

---

### Pitfall 12: PTY Command Injection via Unsanitized Input

**What goes wrong:**
The Tauri native shell includes a terminal pane that runs a PTY. If the shell prompt input from the cockpit UI is passed to the PTY via an IPC command that accepts a raw string, an attacker (or a bug in the web layer) can inject shell metacharacters. Example: the cockpit sends `atlas chat -q "` followed by `"; rm -rf ~; echo "` and the PTY executes all three.

**Why it happens:**
PTY integration feels like terminal emulation (display only) but the Rust backend must feed the PTY master. If the input channel accepts arbitrary strings instead of single characters or validated command sequences, injection is trivial.

**How to avoid:**
- The PTY runs in a fixed shell context started by Tauri on launch. The user interacts with the PTY purely through keystroke forwarding (individual characters/bytes), not through a "send command string" IPC. The cockpit UI sends `{ key: "\n" }` and `{ key: "a" }`, not `{ command: "atlas chat -q ..." }`.
- For the "launch a one-shot query from the cockpit" use case: do not construct a shell command string. Instead, invoke the ATLAS backend function directly via a typed IPC command that accepts validated parameters, bypassing the PTY entirely.
- If a "run in terminal" button is needed, construct the command in Rust from an allowlisted template, not from frontend-provided strings.
- No subprocess spawning from JavaScript. The `tauri-plugin-shell` command must only execute pre-approved sidecars listed in the bundle.

**Warning signs:**
- The frontend sends a full command string via IPC, not individual keystrokes.
- PTY input handler in Rust accepts `String` without validation.
- Integration test sends a crafted string and verifies it executes as a command.

**Phase to address:** Phase 10.5 (PTY integration). Input model (keystrokes vs. command strings) must be decided before implementation begins. This is a design gate, not an afterthought.

---

### Pitfall 13: Remote Content in the Embedded WebView

**What goes wrong:**
The Tauri WebView loads a remote URL instead of the bundled SvelteKit app. A content security policy (CSP) misconfiguration allows the remote page to call ATLAS IPC commands. If an attacker can get the WebView to load a malicious page (via redirect, open redirect in cockpit, or a bug in navigation), they gain access to all enabled IPC commands.

**Why it happens:**
Development mode loads from `localhost:5173`. Shipping without switching to bundle loading (`tauri://localhost`) is a common mistake. Another variant: the cockpit has an "open link" feature that navigates the main WebView instead of opening the system browser.

**How to avoid:**
- Production build must use `"devUrl": null` and `"frontendDist": "../cockpit-web/build"` — never ship a remote URL.
- CSP must explicitly set `connect-src 'self' tauri://localhost` and no external origins. Review the generated CSP in `tauri.conf.json` before shipping.
- External links from the cockpit must open via `tauri::plugin::opener::open_url` (system browser), not via `window.location` or `<a target="_self">`. The navigation allowlist in the Tauri config must forbid navigating away from `tauri://localhost`.
- Tests: build the production bundle and assert the WebView cannot reach any external URL. Assert that an `<a href="https://evil.example.com">` in the cockpit opens the system browser, not the WebView.

**Warning signs:**
- `tauri.conf.json` `devUrl` is present without a build-mode conditional.
- The cockpit `<a>` tags use `target="_blank"` inside the WebView without Tauri link interception.
- CSP contains `connect-src *`.

**Phase to address:** Phase 10.5 (Tauri shell scaffold) and Phase 10.6 (UAT security review). CSP and bundle-mode verification are Phase 10.6 acceptance gates.

---

### Pitfall 14: OAuth Callback Localhost Server Accessible to Other Processes

**What goes wrong:**
When ATLAS implements an OAuth device code or loopback redirect flow, it opens a local HTTP server on `127.0.0.1:<port>` to receive the callback. On Windows, any process running as the same user can connect to `127.0.0.1` ports. A malicious or buggy local process (or another tab in a browser) can race the callback and capture the authorization code.

**Why it happens:**
The loopback callback is the standard OAuth pattern (RFC 8252), but it is designed for short-lived use with PKCE. Implementations that skip PKCE, use predictable ports, or keep the server open after the callback window are vulnerable to code interception.

**How to avoid:**
- Use PKCE (Proof Key for Code Exchange) for any OAuth authorization code flow. Without PKCE, a code interceptor can exchange the code for tokens.
- The callback server binds to `127.0.0.1` only (not `0.0.0.0`). Use port `0` (OS assigns ephemeral port) to avoid predictable ports.
- The server closes immediately after receiving one valid callback. Set a strict timeout (60s) and refuse any second request.
- Validate `state` parameter on every callback to prevent CSRF.
- Prefer device authorization grant (`urn:ietf:params:oauth:grant-type:device_code`) over loopback redirect when the provider supports it — no local server required.
- Document the threat model and the PKCE/state validation in Phase 10.1.

**Warning signs:**
- Callback server listens on a fixed port number (e.g., 8085) that can be pre-registered by another process.
- No PKCE verifier in the authorization request.
- Callback server stays open after returning the auth code to ATLAS.

**Phase to address:** Phase 10.1 (auth store and OAuth flow design). Threat model document for OAuth callback is a Phase 10.1 gate. PKCE validation test is a 10.1 acceptance gate.

---

### Pitfall 15: Secrets Captured in Screenshots or UI Logs

**What goes wrong:**
The native shell PTY pane shows `atlas auth status` output that includes a redacted hint like `sk-or-...abcd`. A Tauri screenshot API call (for bug reporting or UAT documentation) captures the terminal pane including the hint. The screenshot is committed to the repo in the UAT folder. Even a "redacted hint" can narrow a brute-force search if it includes enough characters.

A second variant: Tauri's default error reporting or crash handler includes a window capture that may contain the terminal pane contents.

**How to avoid:**
- The `atlas auth status` output must show only `[configured]` or `[not configured]` without any character hint. Hints are opt-in only (`atlas auth status --show-hints`), not default.
- Tauri's window capture / screenshot APIs must be excluded from the IPC allowlist. Screenshots for UAT must be taken by the operator manually with a separate tool, not via the app.
- The PTY terminal pane must not be included in Tauri's default error capture. If Tauri has a crash reporter plugin, configure it to exclude the WebView contents.
- Acceptance gate (Phase 10.6 UAT): the UAT guide explicitly states that terminal pane screenshots must be reviewed for credential hints before committing. Any committed screenshot must pass a regex check for `sk-`, `Bearer `, `eyJ`.

**Warning signs:**
- UAT screenshots in the repo contain terminal output with token-shaped strings.
- `atlas auth status` default output contains anything beyond `[configured]`/`[not configured]`.
- A Tauri plugin has `"screenshot": true` in its permissions.

**Phase to address:** Phase 10.6 (UAT and hardening). Screenshot review checklist is a UAT gate.

---

### Pitfall 16: Scope Drift — Hermes Rewrite

**What goes wrong:**
During Phase 10.2 (agentic chat), the developer finds that wiring ATLAS audit events into the Hermes AIAgent requires modifying internal Hermes classes. Rather than a thin adapter, they start adding ATLAS concepts directly into `foundation/atlas-hermes/`, effectively rewriting the Hermes foundation from the ATLAS service layer. By Phase 10.4, the vendored foundation has diverged so far from upstream Hermes that it is unmaintainable and the ATLAS service layer is still not clean.

**Why it happens:**
The adapter pattern requires discipline. The path of least resistance is to modify the thing you control (the vendored foundation) rather than designing a clean boundary. Each small modification seems reasonable in isolation but compounds into a rewrite.

**How to avoid:**
- The ATLAS-over-Hermes adapter must be implemented in `services/agent-runtime/` (ATLAS-owned) and must only call Hermes through its documented public API. If Hermes lacks a needed hook (e.g., pre/post-call event emission), add a hook to `foundation/atlas-hermes/` with a minimal, documented extension point — but do not reimplement Hermes logic.
- Track every modification to `foundation/atlas-hermes/` in `DIVERGENCE_LOG.md`. If the log grows by more than 10 entries in one phase, raise a flag.
- Before modifying any file in `foundation/atlas-hermes/`, ask: "Can this be done in the ATLAS adapter layer instead?" If yes, do it there.
- Phase 10.2 gate: the Hermes adapter is in `services/agent-runtime/`, not in `foundation/`. The `foundation/` directory diff is minimal (extension points only).

**Warning signs:**
- Files in `foundation/atlas-hermes/` are modified during Phase 10.2/10.4 work for reasons that are not "Hermes extension point."
- The ATLAS adapter file imports from more than 3 Hermes modules.
- `DIVERGENCE_LOG.md` has more than 5 new entries after a single phase.

**Phase to address:** Phase 10.2 (adapter design) — the boundary must be defined in architecture before the first line of adapter code. Phase gate: `DIVERGENCE_LOG.md` diff reviewed at phase close.

---

### Pitfall 17: Native Shell as Empty Wrapper (No Real Harness Behind It)

**What goes wrong:**
Phase 10.5 (native shell) starts before Phase 10.2/10.3/10.4 are complete. The Tauri shell is built to wrap the cockpit web app but the PTY terminal pane runs raw `bash` because `atlas tui` does not yet exist. The shell ships as a "native shell" milestone but the operator interaction model is: open Tauri → web cockpit works (same as v1.0) → terminal pane runs bash. The TUI, auth, and model discovery are not integrated. This is the v1.1 failure mode described in the prep docs.

**Why it happens:**
Tauri scaffolding is mechanical and produces visible output fast. Teams prioritize visible milestones. The native shell "works" before the harness it is supposed to host exists.

**How to avoid:**
- Phase 10.5 (native shell) must be gated on Phase 10.4 (TUI) and Phase 10.2 (agentic chat) being complete. The PTY command is `atlas tui`, not `bash`. If `atlas tui` does not exist, Phase 10.5 does not start.
- The Phase 10.5 definition of done explicitly requires: `atlas tui` runs in the PTY pane, shows auth/model status, and can complete an agentic chat session from within the native shell.
- A "Tauri scaffold only" intermediate deliverable (cockpit embed, no PTY, no harness integration) is acceptable as a Phase 10.5a with explicit labeling — it is not the done state.

**Warning signs:**
- The Phase 10.5 PR has no `atlas tui` entrypoint as a dependency.
- The PTY pane in the Tauri shell is started with a `cmd.exe` or `bash` command.
- Phase 10.5 closes before Phase 10.4 is complete.

**Phase to address:** Phase sequencing in the roadmap — 10.5 must have a hard dependency on 10.2 + 10.4. This is a roadmap design requirement, not just an implementation note.

---

### Pitfall 18: CRM/Pulse Feature Creep

**What goes wrong:**
During Phase 10.x, a "quick win" CRM integration is added to the native shell (contact list, pulse event stream) because it is technically easy given the architecture. This consumes scope from the harness phases and produces a partially-integrated CRM surface that is not production-ready and was explicitly deferred to v2.0.

**Why it happens:**
The architecture supports CRM (the database schema and event bus are there). When building the native shell, it is tempting to wire up deferred features because the integration points are visible. D-007 defers CRM, but the temptation increases as the native shell makes it feel "almost free."

**How to avoid:**
- D-007 (CRM not first surface) and the v1.1 non-goals list (`pulse/CRM remain deferred to v2.0`) are hard gates. Any PR that adds CRM/Pulse UI or data integration in v1.1 is out of scope.
- The native shell status bar shows: auth status, active model, active mission — not CRM contacts or pulse events.
- The REQUIREMENTS.md for v1.1 has no CRM or Pulse requirement IDs. A code review that adds any must be rejected.

**Warning signs:**
- Any `pulse_runtime` or `crm` import in Phase 10.x code.
- A native shell panel labeled "Contacts" or "Pulse" in Phase 10.x.
- A PR description that says "while I was at it, I wired up CRM."

**Phase to address:** Roadmap and REQUIREMENTS.md gate at milestone scope lock. Reviewable at every PR.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Inline secret in test fixture | Faster test setup | Accidental commit of real key | Never — use fake/generated keys only |
| `auth.json` without file lock | Simpler write path | Corruption under concurrent access | Never for production auth store |
| `INSERT OR REPLACE` for model upsert | Simpler SQL | Destroys `first_seen` audit history | Never — use `ON CONFLICT DO UPDATE` |
| Auto-approve all tool calls | Faster chat demo | Unaudited autonomous actions | Never — always prompt, even in dev |
| Remote URL in Tauri devUrl for production | Easy iteration | CSP bypass, IPC exposure | Dev only, never in production build |
| Skip PKCE for OAuth loopback | Less code | Auth code interception | Never — PKCE is required |
| Broad IPC allowlist (`shell.all = true`) | Fast prototyping | Arbitrary code execution surface | Dev scaffold only, never ship |
| Hermes foundation modification for ATLAS logic | Fastest path | Untrackable divergence, rewrite risk | Extension points only, logged in DIVERGENCE_LOG |
| Discovery on every TUI startup | Always-fresh model list | Slow startup, API quota burn, auth errors | Never — cache-first with explicit refresh |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Codex detection | Parse `~/.codex/auth.json` for token details | Read existence only; never deserialize token payload |
| Hermes AIAgent adapter | Call Hermes internals directly from ATLAS service layer | Use documented Hermes public API; add extension hook if missing |
| OpenRouter `/models` | Call on startup without auth check | Check auth present first; cache result with TTL |
| Tauri PTY | Feed user-typed command strings via IPC | Feed individual keystrokes; start PTY with fixed command |
| ATLAS audit bus + Hermes events | Log Hermes events to Hermes logger | Intercept in ATLAS adapter; re-emit on ATLAS event bus with run_id |
| Windows file permissions | Unix `chmod 600` idiom | Use `icacls` or `SetNamedSecurityInfo` to restrict `~/.atlas/auth.json` |
| OAuth callback server | Fixed port, no PKCE, server stays open | Ephemeral port, PKCE required, close after first valid callback |
| Fallback cascade | Catch all exceptions and fall through | Classify error: auth errors halt, transient errors cascade with audit event |
| Transcript persistence | Store raw tool outputs | Apply redaction filter before persistence |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| No `RedactedStr` type on credential fields | Secret in repr/log/audit | Define `RedactedStr` before first auth model is written |
| `auth.json` world-readable on Windows | Any local user reads tokens | Restrict with `icacls /grant:r` to current user only at creation |
| `Authorization` header in HTTP debug logs | Token exposure in log files | Custom httpx transport that strips auth headers |
| Non-atomic auth file write | Corruption on crash mid-write | Write to temp, then `os.replace()` |
| No state validation in OAuth callback | CSRF on authorization code | Validate `state` parameter, reject mismatches |
| PTY accepts command strings via IPC | Arbitrary code execution | PTY feeds keystrokes only; no command-string IPC |
| WebView loads remote origin | IPC accessible to attacker origin | Bundle mode only in production, strict CSP |
| Tool call auto-approve | Unaudited dangerous actions | Explicit approval gate, deny-by-default for FS/shell tools |
| Chat transcript stored without redaction | Secret persistence in audit JSONL | Redaction pass before any audit persistence |
| Seeded model rows not clearly labeled | Operator trusts fake availability | `source=seeded`, `status=fallback` displayed explicitly |

---

## "Looks Done But Isn't" Checklist

- [ ] **Auth store:** `atlas auth status` works but concurrent write test has not been run — verify with threading test.
- [ ] **Codex non-mutation:** ATLAS starts and runs `discover` without error — verify `~/.codex/auth.json` mtime is unchanged after test.
- [ ] **Redaction:** CLI output shows no secrets — verify by injecting a test key and grepping output, JSONL, and log files.
- [ ] **Cascade audit:** fallback fires and chat continues — verify that audit JSONL contains `provider_fallback` event with `from`/`to`/`reason` fields.
- [ ] **Model registry:** `atlas models list --all` shows multiple models — verify row count is stable after two consecutive discover runs (no duplicates, `first_seen` unchanged).
- [ ] **Tool approval:** `atlas chat` completes a tool-using session — verify audit JSONL has `tool_approval_requested` events before any `tool_executed` events.
- [ ] **PTY launch:** Tauri shell opens with terminal pane — verify PTY is running `atlas tui`, not `bash` or `cmd.exe`.
- [ ] **IPC allowlist:** Tauri app builds and runs — verify `capabilities/` JSON does not contain `shell.all` or broad patterns; enumerate every allowed command.
- [ ] **Bundle mode:** Tauri production build loads cockpit — verify no external URL fetch in network monitor during app startup.
- [ ] **Sidecar health:** `atlas models list` shows local provider as `available` — verify by stopping the sidecar and re-running; status must change to `offline`.

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Auth file concurrent-write corruption | Phase 10.1 | Threading test: two concurrent writers → valid JSON, no data loss |
| Secret leakage to logs/audit/CLI | Phase 10.1 (auth), 10.2 (chat) | Grep test: inject test key, assert not present in any output |
| Codex accidental mutation | Phase 10.1 | Fake-home test: `mtime` and hash of `~/.codex/auth.json` unchanged after all discovery/auth commands |
| Fallback cascade masking auth errors | Phase 10.2 | Inject 401 from primary: assert cascade does not fire, `AUTH_ERROR` event emitted |
| Infinite/expensive model discovery | Phase 10.3 | Startup benchmark <500ms; circuit breaker test with repeated failures |
| Model registry duplicate rows / `first_seen` loss | Phase 10.3 | Run discover twice: row count stable, `first_seen` unchanged |
| Fake "available" model status | Phase 10.3 | Stop sidecar: model status changes to `offline`; remote provider with missing auth shows `needs_login` not `available` |
| Agentic calls bypassing audit metadata | Phase 10.2 | `chat -q "ping"` → JSONL contains `model_call_start` + `model_call_end` with non-null `run_id` |
| Tool approval gates lost | Phase 10.2 (protocol), 10.4 (TUI) | Mock tool test: tool does not execute without approval event |
| Secret leakage into transcripts/wiki | Phase 10.2 (redaction), 10.4 (TUI warning) | Inject key pattern into chat message: persisted JSONL must not contain raw value |
| Tauri IPC over-permissioned | Phase 10.5 | Capabilities JSON review: every command explicitly listed; no blanket permissions |
| PTY command injection | Phase 10.5 | Input model review: PTY handler accepts keystrokes, not command strings |
| Remote content in WebView | Phase 10.5 (design), 10.6 (UAT) | Production build: no external URL in network monitor; CSP verified |
| OAuth callback interception | Phase 10.1 | PKCE present in auth request; callback server closes after one valid callback |
| Secrets in screenshots | Phase 10.6 UAT | Screenshot review checklist; regex check before committing UAT assets |
| Hermes rewrite drift | Phase 10.2 (adapter boundary) | `DIVERGENCE_LOG.md` diff at phase close; adapter lives in `services/`, not `foundation/` |
| Native shell as empty wrapper | Roadmap sequencing | Phase 10.5 blocked on 10.2 + 10.4 completion; PTY command is `atlas tui` |
| CRM/Pulse scope creep | Milestone scope lock | No CRM/Pulse requirement IDs in v1.1 REQUIREMENTS.md; PR rejection criteria |

---

## Sources

- ATLAS v1.1 prep set: `v1.1-extra-marathon-scope.md` sections 5H and 6 (security/audit gates and acceptance criteria)
- `v1.1-owned-auth-architecture.md` sections 12, 13 (security requirements and required tests)
- `v1.1-provider-model-registry-spec.md` sections 8, 10, 11 (schema safety, SQLite keys, discovery tests)
- `v1-cli-agentic-gap-2026-06-15.md` (root cause analysis of the v1.0 harness gap)
- `PROJECT.md` non-negotiables (audit-first, no secrets in repo, Rust-first D-022, two-layer branding D-021)
- RFC 8252 — OAuth 2.0 for Native Apps (PKCE and loopback redirect threat model)
- Tauri 2 capability system documentation (IPC allowlist, CSP, bundle mode)
- Rust `portalocker` / Windows `LockFileEx` for cross-platform file locking behavior

---
*Pitfalls research for: ATLAS v1.1 — agent harness, owned auth, model registry, agentic chat, Tauri PTY on Windows*
*Researched: 2026-06-15*
