# Architecture Patterns — ATLAS v1.1 Integration

**Domain:** Agentic harness integration into existing ATLAS operator runtime
**Researched:** 2026-06-15
**Confidence:** HIGH — all findings grounded in actual repo files

---

## Existing Architecture (Locked, v1.0)

Four layers, immovable:

| Layer | What lives here |
|-------|----------------|
| L1 Raw sources | `wiki/`, immutable source assets |
| L2 Compiled memory | SQLite WAL (`~/.atlas/atlas.db`) + LLM Wiki runtime |
| L3 Runtime | `foundation/atlas-hermes/` (vendored Hermes v0.14.0) + `services/agent-runtime/` (Python) + `services/wiki-runtime/` |
| L4 Cockpit UI | `apps/cockpit-web/` (SvelteKit) → `native/atlas-core-rs/crates/atlas-gateway` (Axum/rusqlite, SSE) |

**Write contract (D-022):** The Rust gateway is read-only against SQLite. All mutations go through `dispatch_atlas()` → subprocess call to `atlas` CLI → Python service layer → SQLite. This is the established and tested pattern in `lib.rs:dispatch_atlas()`.

**Schema source of truth (D-012):** `packages/atlas-core/atlas_core/schemas/core.py` — Pydantic v2 frozen models. SQLite DDL in `infra/migrations/` mirrors these 1:1. Any new domain models follow this path.

**Python exception buckets (D-022):** Hermes foundation surface, LLM adapters, throwaway scripts. No new Python services outside these three categories.

**DB path:** `~/.atlas/atlas.db` — already canonical in both `services/agent-runtime/atlas_runtime/cli/main.py:_get_connection()` and `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:default_db_path()`.

---

## Question 1: Agent Adapter and TUI Transport Placement

### Where does the agentic chat adapter live?

**Decision: Python, in the LLM-adapter exception bucket. This is not a grey area.**

Rationale grounded in code:

1. `foundation/atlas-hermes/agent/conversation_loop.py` is the Hermes agent loop — 3,900+ lines, handles model call, tool dispatch, retries, fallbacks, compression, post-turn hooks, memory. Wrapping from Rust would require either IPC overhead or full reimplementation. Neither is acceptable.
2. `foundation/atlas-hermes/agent/credential_pool.py` imports directly from `hermes_cli.auth` — `PROVIDER_REGISTRY`, `_load_auth_store`, `_save_auth_store`, etc. The credential resolution chain is entirely within the Python process.
3. D-022 explicitly names "LLM adapters" as a Python exception bucket. A chat adapter over Hermes AIAgent is structurally equivalent to an LLM adapter.

The adapter lives in `services/agent-runtime/atlas_runtime/` as a new module — e.g., `atlas_runtime/chat_adapter.py` — and is exposed via new CLI subcommands (`atlas chat`, `atlas chat -q`). It wraps Hermes AIAgent, adds ATLAS audit event emission on model calls (using the existing `atlas_audit` plugin surface), and implements the health-aware fallback cascade.

### How does the TUI reach the runtime?

**Decision: The ATLAS TUI spawns the `tui_gateway` as a subprocess (stdio JSON-RPC), exactly as Hermes TUI does. Do not route through the Rust atlas-gateway for chat traffic.**

Evidence:

- `foundation/atlas-hermes/tui_gateway/entry.py` is the gateway entrypoint. It receives `HERMES_PYTHON_SRC_ROOT` env var, sets up the Python path, and serves JSON-RPC over stdio.
- `foundation/atlas-hermes/tui_gateway/transport.py` defines `StdioTransport`, `WSTransport` (WebSocket variant), and `TeeTransport` (mirrors to a sidecar WS — used by the dashboard PTY bridge).
- `foundation/atlas-hermes/tui_gateway/ws.py` shows the full WebSocket path — same `server.dispatch()` function, different transport. This means both stdio and WS are already supported.
- `foundation/atlas-hermes/hermes_cli/pty_bridge.py` is POSIX-only (uses `fcntl`, `termios`, `ptyprocess`). It explicitly notes native Windows ConPTY would need `pywinpty`. This is relevant for the Tauri PTY decision below.

**ATLAS-branded TUI transport options, in order of preference:**

| Option | Mechanism | Effort | Risk |
|--------|-----------|--------|------|
| A (recommended) | ATLAS TUI spawns `atlas tui_gateway` subprocess over stdio JSON-RPC (same as Hermes) | Low — reuse existing transport layer | Low |
| B | ATLAS TUI connects to `tui_gateway` over WebSocket (WS transport already implemented in `ws.py`) | Medium | Low |
| C | Route chat through Rust atlas-gateway | High — would require reimplementing agent loop in Rust or a new Python-Rust bridge | Not acceptable for v1.1 |

Option A is the correct choice. The `tui_gateway/server.py` `dispatch()` function is the single RPC handler for all TUI interactions. ATLAS wraps it with ATLAS-branded entry (`atlas tui_gateway` subcommand) that sets `ATLAS_HOME`, `ATLAS_DB`, and any ATLAS-specific env vars before exec-ing the Python gateway subprocess.

**ATLAS TUI architecture:**
```
atlas tui  (CLI entry, Python)
    │
    ├── spawns subprocess: atlas tui_gateway (Python, stdio JSON-RPC)
    │       └── tui_gateway/server.py dispatch() — handles agent turns, tool calls, approval prompts
    │               └── agent/conversation_loop.py — Hermes AIAgent loop
    │                       └── credential_pool.py → auth.py → ~/.atlas/auth.json
    │
    └── ATLAS TUI frontend (options: Ink/Node like Hermes, or Python rich/textual)
            └── JSON-RPC over stdio to gateway subprocess
```

The TUI frontend itself (the visual layer) is a new component. Hermes uses an Ink (Node.js/React) TUI launched by the Python CLI. ATLAS can either:
- Reuse the same Ink pattern (adds Node dependency, but inherits all Hermes TUI features)
- Build a Python-native TUI using `textual` or `rich` (simpler stack, less feature parity initially)

For v1.1, **the Ink route is lower risk for TUI feature parity** because the tui_gateway JSON-RPC protocol is already stable and the Hermes TUI already handles streaming, tool activity, approval prompts. An ATLAS-branded Ink TUI can reuse the protocol. Python-native TUI is viable if Ink dependency is rejected.

**The Python TUI does NOT go through the Rust atlas-gateway.** The Rust gateway serves the cockpit UI (HTTP/SSE). The TUI communicates directly with the Python tui_gateway subprocess.

---

## Question 2: Provider/Model/Route Registry — Data Flow and Schema

### New Pydantic schemas required

Add to `packages/atlas-core/atlas_core/schemas/core.py` (or a new `registry.py` module in the same package):

```python
class Provider(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider_id: str
    display_name: str
    auth_type: Literal["api_key", "oauth_device_code", "oauth_external", "noauth"]
    default_base_url: str = ""
    api_modes: list[str] = []          # ["chat_completions", "responses", ...]
    source: str                         # "seeded", "atlas_config", "discovered"
    status: Literal["available", "needs_login", "needs_api_key", "offline", "unknown"] = "unknown"
    last_checked: Optional[datetime] = None
    last_error: Optional[str] = None

class ModelEntry(BaseModel):
    model_config = ConfigDict(frozen=True)
    model_id: str
    provider_id: str
    source: str                          # "seeded", "openrouter_models_api", "local_lmstudio", ...
    api_mode: str
    status: Literal["available", "auth_present", "needs_login", "offline", "deactivated", "unknown"] = "unknown"
    auth_status: Literal["present", "missing", "external", "noauth"] = "missing"
    context_window: Optional[int] = None
    metadata: str = "{}"                 # JSON string per D-013
    first_seen: datetime = ...
    last_seen: datetime = ...
    deactivated_at: Optional[datetime] = None

class RoutePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    task_class: str                      # "chat_default", "coding", "planning", ...
    provider_id: str
    model_id: str
    fallback_policy: str = "{}"         # JSON string
    updated_at: datetime = ...
```

### SQLite migration (new file: `infra/migrations/0004_registry_v2.sql`)

```sql
-- 0004: provider + model registry v2 + route policy (v1.1)
-- Extends 0003_model_registry.sql. Old model_registry preserved for
-- backwards compatibility (Rust gateway /models reads it; v1.0 rows stay).

CREATE TABLE IF NOT EXISTS provider_registry (
    provider_id       TEXT PRIMARY KEY,
    display_name      TEXT NOT NULL,
    auth_type         TEXT NOT NULL,
    default_base_url  TEXT NOT NULL DEFAULT '',
    api_modes_json    TEXT NOT NULL DEFAULT '[]',
    source            TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'unknown',
    last_checked      TEXT,
    last_error        TEXT
);

CREATE TABLE IF NOT EXISTS model_registry_v2 (
    model_id         TEXT NOT NULL,
    provider_id      TEXT NOT NULL,
    source           TEXT NOT NULL,
    api_mode         TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'unknown',
    auth_status      TEXT NOT NULL DEFAULT 'missing',
    context_window   INTEGER,
    metadata_json    TEXT NOT NULL DEFAULT '{}',
    first_seen       TEXT NOT NULL,
    last_seen        TEXT NOT NULL,
    deactivated_at   TEXT,
    PRIMARY KEY (model_id, provider_id, source)
);

CREATE TABLE IF NOT EXISTS route_policy (
    task_class           TEXT PRIMARY KEY,
    provider_id          TEXT NOT NULL,
    model_id             TEXT NOT NULL,
    fallback_policy_json TEXT NOT NULL DEFAULT '{}',
    updated_at           TEXT NOT NULL
);
```

### Data flow: schema → migration → gateway → cockpit

```
atlas_core/schemas/registry.py   (Pydantic v2, D-012)
    │
    ├── emit JSON Schema → used for TS cockpit type generation and Rust serde
    │
    └── atlas_runtime services write via atlas CLI subcommands
            │
            ├── atlas providers refresh / atlas models discover
            │       ↓
            │   infra/migrations/0004 tables in ~/.atlas/atlas.db
            │       ↓
            │   Rust atlas-gateway reads provider_registry + model_registry_v2
            │       via new db.rs query functions
            │       ↓
            │   GET /providers, GET /models (new Rust routes in lib.rs)
            │       ↓
            │   SvelteKit cockpit Models page (apps/cockpit-web/)
            │
            └── atlas route set <task-class> <provider/model>
                    ↓
                route_policy table (written via CLI dispatch, read by agent chat_adapter)
```

**Source-scoped deactivation (preserves audit history):**

The existing `model_registry.refresh()` in `atlas_runtime/model_registry.py` already implements source-scoped deactivation: `active=0 WHERE model_id=? AND source=?`. The v2 schema extends this: when a provider source goes offline, `deactivated_at` is set on affected `model_registry_v2` rows for that `(provider_id, source)` combination only. Rows from other sources are untouched. Global deletion is never performed — consistent with the v1.0 pattern.

**New Rust gateway routes required (modifications to `lib.rs`):**

```rust
GET /providers          → db::list_providers() → reads provider_registry
GET /providers/:id      → db::get_provider()
GET /models/v2          → db::list_models_v2() → reads model_registry_v2 with status/auth_status
GET /routes             → db::list_routes()
```

These are read-only additions following the existing gateway pattern. All writes continue through `dispatch_atlas()`.

---

## Question 3: ATLAS Auth Store and Codex Read-Only Detection

### Auth store design

The Hermes auth system (`foundation/atlas-hermes/hermes_cli/auth.py`) provides the exact reference pattern:

- `AUTH_STORE_VERSION = 1`
- `~/.hermes/auth.json` — per-provider credential state with `_auth_store_lock` (cross-process file lock using `fcntl` on POSIX, `msvcrt` on Windows)
- `atomic_replace()` / `atomic_yaml_write()` from `utils` — atomic writes
- `PROVIDER_REGISTRY: Dict[str, ProviderConfig]` — static known-provider registry
- `_load_auth_store()` / `_save_auth_store()` — read/write with lock

**ATLAS auth store location:** `~/.atlas/auth.json` (same directory as `atlas.db` — already canonical).

**ATLAS runtime credential resolver** replaces Hermes `resolve_provider()`. The resolver priority chain:

```
1. Explicit --provider / --model CLI flags
2. ~/.atlas/auth.json (ATLAS-owned, api_key or oauth types)
3. ATLAS config env references (ATLAS_OPENAI_API_KEY etc.)
4. No-auth local providers (LM Studio/Ollama on loopback — status checked via short-timeout HTTP probe)
5. External tool read-only status (codex detection → advisory only, never extracted as credentials)
6. Fail with remediation: "atlas auth add <provider>"
```

**Critical: the resolver never reads `~/.codex/auth.json` as a credential source.** It only probes whether the file exists for status reporting.

### Codex read-only detection

Detection is entirely filesystem + subprocess probe, no credential extraction:

```python
# atlas_runtime/auth/codex_detect.py  (new module)

from pathlib import Path
import shutil, subprocess

def detect_codex() -> dict:
    codex_bin = shutil.which("codex")
    codex_auth = Path.home() / ".codex" / "auth.json"
    codex_config = Path.home() / ".codex" / "config.toml"

    version = None
    if codex_bin:
        try:
            result = subprocess.run(["codex", "--version"],
                                    capture_output=True, text=True, timeout=3)
            version = result.stdout.strip() or None
        except Exception:
            pass

    return {
        "binary": codex_bin,
        "version": version,
        "auth_file_present": codex_auth.exists(),
        "config_file_present": codex_config.exists(),
        "status": (
            "installed_auth_present" if codex_bin and codex_auth.exists()
            else "installed_no_auth" if codex_bin
            else "not_installed"
        ),
        "readonly": True,   # Always: ATLAS never writes to ~/.codex
    }
```

This output flows into `atlas auth status` display and into `atlas models discover` (Codex status = advisory row with `auth_status="external"`, never `"present"`). The `ATLAS never mutates ~/.codex` invariant is enforced by the absence of any write path — there is no code that opens `~/.codex/*` for writing.

**Coupling concern:** ATLAS state is decoupled from Codex by the resolver priority chain above. If Codex auth is present, `atlas models discover` may list Codex-served models with `auth_status="external"` and `source="codex_external_readonly"`. These rows are informational only — the chat adapter will not select them unless the user explicitly routes to them. The health-aware cascade (`OpenAI/Codex-compatible first`) refers to the ATLAS-owned OpenAI-compatible lane (ATLAS's own OpenRouter or OpenAI API key), not to the external Codex CLI.

---

## Question 4: Tauri 2 Native Shell — Embedding, PTY, and Trust Boundary

### Shell structure

```
native/
  atlas-shell/           (NEW — separate Tauri 2 crate, NOT inside atlas-core-rs)
    src-tauri/
      src/
        main.rs           Tauri 2 app entry
        commands.rs       IPC command handlers (allowlisted)
        pty.rs            PTY bridge (windows: ConPTY via portable-pty or tauri-plugin-pty)
      tauri.conf.json     capability scopes
    src/                  SvelteKit static embed (symlink or build copy)
```

Tauri 2 lives as a new workspace member or separate crate in `native/atlas-shell/`. It is not added to the existing `atlas-core-rs` workspace (that workspace is for the gateway crate; adding Tauri would add its bundler dependencies and build complexity). A standalone crate referencing the atlas-core-rs workspace as a path dependency is fine if shared types are needed, but for v1.1 the shell is thin enough that no types need to be shared.

### Cockpit embedding

SvelteKit builds to `apps/cockpit-web/build/` (adapter-static). Tauri 2 loads this as a local file:// asset. No network origin for the cockpit in native mode.

```json
// tauri.conf.json
{
  "bundle": { "resources": { "../apps/cockpit-web/build": "cockpit" } },
  "app": { "windows": [{ "url": "cockpit/index.html", "label": "cockpit" }] }
}
```

The cockpit JS in native mode still calls `localhost:PORT` for the Rust atlas-gateway (same as browser mode). The Tauri shell starts the gateway subprocess on launch and passes the port to the cockpit via a Tauri IPC command or a startup env var injected into the webview.

### PTY for `atlas` CLI

Hermes `pty_bridge.py` is POSIX-only (`fcntl`, `ptyprocess`). On Windows, Tauri 2 should use `portable-pty` (Rust crate) which wraps both POSIX pty and Windows ConPTY, or `tauri-plugin-shell` with a persistent child process. The recommended path:

- Use `portable-pty` Rust crate in `native/atlas-shell/src-tauri/src/pty.rs`
- Expose a Tauri IPC command `pty_write` and a Tauri event `pty_data` for the cockpit terminal pane
- The cockpit's terminal pane (xterm.js or a simple pre element) subscribes to `pty_data` events and sends keystrokes via `pty_write` commands

```
Cockpit terminal pane (SvelteKit + xterm.js)
    │
    ├── invoke("pty_write", { data: "atlas chat -q ping\n" })
    │       ↓
    │   pty.rs: write to ConPTY stdin
    │
    └── listen("pty_data", handler)
            ↑
        pty.rs: read ConPTY stdout → emit "pty_data" event
```

### IPC trust boundary

Tauri 2 capability model: all IPC commands are opt-in per capability scope. The capability file lists exactly which commands the webview can invoke.

**Allowed IPC (webview → Tauri):**
- `pty_write` — send bytes to the PTY child (rate-limited, max frame size enforced)
- `pty_resize` — notify PTY of terminal resize
- `pty_spawn` — spawn a new PTY session running `atlas` (bounded: max 1 session per window)
- `pty_kill` — kill the current PTY session
- `get_gateway_port` — retrieve the port the shell started atlas-gateway on
- `open_auth_url` — open an OAuth callback URL in the default browser (loopback only, validated)

**Blocked at the trust boundary:**
- Arbitrary shell execution (no `shell_execute` open command)
- Filesystem reads/writes outside sanctioned paths
- Network requests from Rust layer (cockpit uses its own fetch to the gateway)
- Any command that would expose credential values

**Threat model summary:**
- The cockpit webview runs file:// (no web origin). This prevents CORS-based attacks but webview scripting is still possible if the SvelteKit app has XSS vulnerabilities. The cockpit must not pass arbitrary user-controlled strings directly into IPC commands.
- `pty_spawn` is the highest-risk command: it starts a process as the current user. It must only accept a fixed allowlist of programs (`["atlas"]` or `["atlas", "tui"]`) — not arbitrary strings from the webview.
- OAuth loopback callback (`open_auth_url`): Tauri's `open_url` command must validate the URL matches `http://127.0.0.1:<port>/callback` before opening. No arbitrary URLs accepted from the webview.
- Secrets must never appear in IPC payloads. Auth flows happen in the Python CLI subprocess, not through Tauri IPC.

The trust boundary is: **the Tauri Rust layer is the authority.** The webview is an untrusted presentation layer. The Rust layer validates all IPC arguments before acting.

---

## Question 5: Build Order for Phase 10.x

### Dependency graph

```
Auth store (10.1)
    │
    ├── required by: Chat adapter (10.2) — credential resolver
    ├── required by: Model discovery (10.3) — auth status per provider
    └── required by: TUI (10.4) — shows auth readiness in status bar

Chat adapter (10.2) — depends on Auth store
    │
    └── required by: TUI (10.4) — TUI sends prompts to chat adapter via tui_gateway

Model discovery (10.3) — depends on Auth store
    │
    ├── required by: TUI (10.4) — model picker in status bar
    └── required by: Cockpit Models page (10.3 output)

TUI (10.4) — depends on Auth + Chat + Model discovery
    │
    └── required by: Native shell PTY (10.5) — PTY must have something useful to run

Native shell scaffold (10.5.a) — independent of above (Tauri scaffold + cockpit embed)

Native PTY integration (10.5.b) — depends on TUI being runnable

Integration + UAT (10.6) — depends on everything above
```

### Recommended phase sequence

| Phase | Name | What ships | New vs Modified |
|-------|------|-----------|----------------|
| 10.0 | Design & Architecture | Auth design, TUI arch decision, registry schema, threat model, IPC spec | New: `.planning/` docs only |
| 10.1 | ATLAS Auth Store | `~/.atlas/auth.json`, `atlas auth` commands, Codex detection, redaction tests | NEW: `atlas_runtime/auth/` module; MODIFY: `cli/main.py` (add auth_app) |
| 10.2 | Agentic Chat CLI | `atlas chat -q`, `atlas chat` interactive, ATLAS tui_gateway bridge, audit events on model calls | NEW: `atlas_runtime/chat_adapter.py`, `cli/chat.py`; MODIFY: `cli/main.py` (add chat_app) |
| 10.3 | Model/Provider Discovery | `atlas providers`, `atlas models discover`, registry v2 schema + migration, Rust gateway routes for /providers + /models/v2, cockpit Models page update | NEW: `atlas_runtime/provider_registry.py`, `cli/providers.py`, migration 0004; MODIFY: `cli/models.py`, `lib.rs` (new routes), `db.rs`, cockpit models route |
| 10.4 | ATLAS TUI | ATLAS-branded TUI (Ink or textual), `atlas tui` command, transcript/composer/tool activity/status bar, model/auth awareness, session persistence | NEW: `apps/atlas-tui/` or `services/atlas-tui/`; MODIFY: `cli/main.py` (add tui subcommand) |
| 10.5 | Native Shell | Tauri 2 scaffold in `native/atlas-shell/`, cockpit embed, atlas-gateway subprocess launch, PTY integration (`portable-pty`), IPC capability file, threat model | NEW: `native/atlas-shell/` (all new); MODIFY: cockpit startup to accept gateway port IPC |
| 10.6 | Integration + UAT | Shell + TUI + cockpit + auth + models all wired; manual UAT guide; redaction tests; no-secret screenshots | MODIFY: integration wiring, test coverage |

### Phase 10.0 is required before 10.1

Phase 10.0 must produce a written auth design decision and the migration 0004 schema draft. Phase 10.1 cannot start until the auth store layout is committed to — the profile-vs-flat question (`~/.atlas/auth.json` vs `~/.atlas/profiles/default/auth.json`) affects every other component that resolves credentials.

**Recommendation:** use the minimal flat layout for v1.1 (`~/.atlas/auth.json`, `~/.atlas/atlas.db`). Wrap all path resolution behind a single function so profile support can be added later without changing call sites. The Rust gateway already resolves `$ATLAS_DB` or `~/.atlas/atlas.db` — this is the established convention.

### New vs Modified Component Inventory

**New files/modules:**
- `services/agent-runtime/atlas_runtime/auth/` — `store.py`, `codex_detect.py`, `resolver.py`
- `services/agent-runtime/atlas_runtime/chat_adapter.py`
- `services/agent-runtime/atlas_runtime/provider_registry.py`
- `services/agent-runtime/atlas_runtime/cli/auth.py`
- `services/agent-runtime/atlas_runtime/cli/chat.py`
- `services/agent-runtime/atlas_runtime/cli/providers.py`
- `infra/migrations/0004_registry_v2.sql`
- `packages/atlas-core/atlas_core/schemas/registry.py` (or additions to `core.py`)
- `native/atlas-shell/` (entire Tauri 2 crate)
- `apps/atlas-tui/` (TUI frontend, new top-level app)

**Modified files:**
- `services/agent-runtime/atlas_runtime/cli/main.py` — add `auth_app`, `chat_app`, `providers_app` typers; update `models_app`
- `services/agent-runtime/atlas_runtime/cli/models.py` — add `atlas models discover`, extend `list` output with `source/status/auth_status`
- `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs` — add GET /providers, GET /models/v2, GET /routes routes
- `native/atlas-core-rs/crates/atlas-gateway/src/db.rs` — add `list_providers()`, `list_models_v2()`, `list_routes()`
- `apps/cockpit-web/` — Models page update to consume `/models/v2` with status/auth columns
- `native/atlas-core-rs/Cargo.toml` — no change needed unless atlas-shell is added as workspace member

---

## Architecture Diagrams

### v1.1 Runtime data flow (at-a-glance)

```
OPERATOR
  │
  ├── atlas tui ──── spawns ──── tui_gateway subprocess (Python, stdio JSON-RPC)
  │                                     │
  │                                     └── conversation_loop.py (Hermes AIAgent)
  │                                               │
  │                                               ├── credential_resolver.py → ~/.atlas/auth.json
  │                                               ├── provider_registry.py → provider_registry table
  │                                               └── audit_service.py → audit_events table
  │
  ├── atlas chat -q ── chat_adapter.py ── same chain as above (one-shot)
  │
  ├── atlas auth status/add ── auth/store.py → ~/.atlas/auth.json
  │
  ├── atlas models discover ── provider_registry.py → model_registry_v2 table
  │
  └── native/atlas-shell (Tauri 2)
          │
          ├── webview: cockpit (SvelteKit, file://)
          │       └── HTTP → atlas-gateway (localhost:PORT)
          │               └── db.rs → ~/.atlas/atlas.db (read-only)
          │                       └── writes via dispatch_atlas() → atlas CLI
          │
          └── PTY pane (portable-pty)
                  └── spawns: atlas tui (or atlas chat)
                          └── same as above
```

### Auth resolution at call time

```
atlas chat -q "prompt"
    │
    └── chat_adapter.py: resolve_credentials()
            │
            ├── 1. --provider flag? → use directly
            ├── 2. ~/.atlas/auth.json → load provider entry → check status/expiry
            ├── 3. env vars (ATLAS_OPENAI_API_KEY etc.)
            ├── 4. local sidecars: probe http://127.0.0.1:1234/v1 (timeout 2s)
            ├── 5. codex_detect.py → external status only, never credential
            └── 6. fail: "atlas auth add <provider> — run this to configure"
```

### Model discovery data flow

```
atlas models discover
    │
    ├── load ~/.atlas/auth.json → get configured providers
    ├── for each configured provider with auth:
    │       GET <base_url>/models → upsert model_registry_v2 rows
    ├── probe local sidecars (LM Studio :1234, Ollama :11434, FreeLLMAPI :3001)
    ├── codex_detect.py → insert advisory row (source=codex_external_readonly)
    └── deactivate missing rows per source (source-scoped, not global)
            │
            └── model_registry_v2 in ~/.atlas/atlas.db
                    │
                    ├── Rust gateway GET /models/v2 → cockpit Models page
                    └── CLI: atlas models list --all
```

---

## Component Boundaries

| Component | Responsibility | Communicates With | Language |
|-----------|---------------|-------------------|----------|
| `atlas_runtime/auth/` | ATLAS auth store: read/write/lock/redact `~/.atlas/auth.json` | CLI commands, chat_adapter, provider_registry | Python (exception bucket) |
| `atlas_runtime/chat_adapter.py` | Thin adapter over Hermes AIAgent: credential resolution, audit emission, cascade | tui_gateway, CLI chat commands, audit_service | Python (LLM adapter exception bucket) |
| `atlas_runtime/provider_registry.py` | Merged provider/model discovery: probe sidecars, call `/models` endpoints, upsert SQLite | auth store, SQLite, CLI | Python (LLM adapter exception bucket) |
| `tui_gateway/` (Hermes, vendored) | JSON-RPC server: dispatches agent turns, tool calls, approvals over stdio or WS | ATLAS TUI frontend, chat_adapter | Python |
| `atlas-gateway` (Rust) | Read-only HTTP/SSE over SQLite; write dispatch via atlas CLI subprocess | cockpit, native shell | Rust |
| `atlas-shell` (Tauri 2) | Native window: hosts cockpit webview, starts gateway subprocess, PTY | cockpit webview (IPC), atlas-gateway (HTTP), atlas CLI (PTY) | Rust |
| `apps/atlas-tui/` | ATLAS-branded TUI frontend (Ink or textual): connects to tui_gateway subprocess | tui_gateway (stdio JSON-RPC) | Node/TS (Ink) or Python |
| `apps/cockpit-web/` | SvelteKit operator cockpit | atlas-gateway HTTP/SSE | TypeScript |

---

## Scalability Considerations

All of v1.1 is single-operator, local-first. No distributed concerns for this milestone.

| Concern | Single operator (v1.1) |
|---------|----------------------|
| SQLite concurrency | WAL mode handles gateway reads + CLI writes concurrently — already tested in v1.0 |
| Auth file locking | Cross-process lock via fcntl/msvcrt — same pattern as Hermes, proven |
| Model discovery latency | Short per-provider timeouts (2s local, 10s remote) — runs in background CLI, not on hot path |
| PTY session lifecycle | One PTY per native shell window — no pooling needed |

---

## Sources

- `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs` — dispatch_atlas(), route table, gateway architecture
- `native/atlas-core-rs/crates/atlas-gateway/src/db.rs` — read-only SQLite pattern, open_ro()
- `foundation/atlas-hermes/tui_gateway/entry.py`, `server.py`, `transport.py`, `ws.py` — tui_gateway JSON-RPC architecture
- `foundation/atlas-hermes/hermes_cli/auth.py` — ProviderConfig, PROVIDER_REGISTRY, auth store patterns
- `foundation/atlas-hermes/hermes_cli/providers.py` — HermesOverlay, transport types
- `foundation/atlas-hermes/agent/conversation_loop.py` — AIAgent loop scope and dependencies
- `foundation/atlas-hermes/agent/credential_pool.py` — credential resolution chain
- `foundation/atlas-hermes/hermes_cli/pty_bridge.py` — POSIX PTY constraint (Windows note)
- `foundation/atlas-hermes/tui_gateway/ws.py` — WebSocket transport (same dispatch function)
- `services/agent-runtime/atlas_runtime/model_registry.py` — source-scoped deactivation pattern
- `services/agent-runtime/atlas_runtime/cli/main.py` — existing CLI structure, db path
- `infra/migrations/0003_model_registry.sql` — existing registry schema
- `packages/atlas-core/atlas_core/schemas/core.py` — Pydantic v2 schema pattern (D-012)
- `.planning/prep/v1.1-owned-auth-architecture.md` — auth store spec
- `.planning/prep/v1.1-provider-model-registry-spec.md` — registry domain model
- `.planning/prep/v1.1-extra-marathon-scope.md` — workstream definitions
