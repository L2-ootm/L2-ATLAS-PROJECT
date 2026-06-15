# Stack Research — ATLAS v1.1 (Agent Harness & Native Operator Shell)

**Domain:** Local AI operator runtime — TUI, auth store, provider registry, agentic chat, native desktop shell
**Researched:** 2026-06-15
**Confidence:** HIGH (all critical libraries verified via Context7 or direct docs/crates.io; Hermes source inspected)

---

## 1. TUI Framework

### Decision: Fork/adapt Hermes' TypeScript/Ink TUI — NOT a new Rust TUI for v1.1

**What Hermes already uses (inspected, not assumed):**

| Layer | Technology | Version (package.json) | Role |
|-------|-----------|----------------------|------|
| Runtime | Node.js / TypeScript | ESM, ts ^5.7.0 | Compilation and execution |
| TUI renderer | `ink` | ^6.8.0 in package.json; 7.0.5 latest | React component tree → ANSI terminal |
| Custom ink fork | `@hermes/ink` (`packages/hermes-ink/`) | 0.0.1 local | Hermes-patched Ink (yoga layout, BIDI, mouse, scroll, animations) |
| State management | `nanostores` + `@nanostores/react` | ^1.2.0 / ^1.1.0 | Lightweight atom-based shared state |
| Build | `esbuild` | ~0.27.0 | Single-file bundle for distribution |
| Dev runner | `tsx` | ^4.19.0 | Fast TypeScript execution without transpile step |
| Text input | `ink-text-input` | ^6.0.0 | Composer widget |
| Animations | `unicode-animations` | ^1.0.3 | Spinner/activity indicators |
| IPC to Python backend | JSON-RPC 2.0 over stdio (`tui_gateway/server.py`) | — | Bidirectional protocol |
| Testing | `vitest` | ^4.1.3 | Unit + component tests |

**Upstream `ink` status:**
- Ink 7.0.5 released 2026-06-13 (2 days before this research). Requires Node 22 + React 19.2.
- Hermes vendor pins `ink ^6.8.0`. The local `@hermes/ink` is a significant fork with yoga layout, BIDI, mouse events, and scroll — it does not just re-export upstream ink.
- Claude Code and Gemini CLI both use Ink 6/7 as their TUI, confirming this is the industry standard for Node-based CLI agent UIs.

**Why NOT Rust TUI (ratatui 0.30.0 + crossterm 0.29.0) for v1.1:**

| Criterion | Python/Ink (adapt Hermes) | Rust ratatui |
|-----------|--------------------------|--------------|
| Time to first usable TUI | Days (rebrand + add panels) | Weeks (rewrite all panels from scratch) |
| D-022 compliance | Allowed — Python TUI is in the Hermes foundation exception bucket | Compliant but unnecessary risk for v1.1 |
| Existing gateway protocol | JSON-RPC gateway already built and tested (`tui_gateway/server.py`) | Would require rewriting the 7000-line gateway or adding a second IPC protocol |
| ATLAS panels needed | Add mission/auth/model status bar on top of existing Hermes panels | Build every panel from scratch |
| Risk to auth/model/agent work | Low — TUI is isolated from data layers | High — delays all other workstreams |
| Windows terminal compat | Confirmed (Hermes tests explicitly cover Windows UTF-8, mouse residue suppression) | crossterm 0.29 is cross-platform but adds new unknowns |

**Recommendation:** Adapt the Hermes TypeScript/Ink TUI into ATLAS namespace (Option A/B hybrid). Do not build a Rust TUI for v1.1. Rust TUI is a v2.0 candidate only if Ink causes packaging problems at native-shell scale.

**D-022 classification:** TypeScript/Ink TUI lives in `apps/atlas-tui/` (new directory, equivalent to `ui-tui/`). It is a presentation-layer exception: it sits on top of the Python Hermes foundation and communicates via the existing JSON-RPC gateway. No new Python service code.

**What ATLAS TUI adds over Hermes TUI:**
- ATLAS banner / brand skin
- Mission context panel (`/mission bind`, `/run status`, audit tail)
- Auth/model status bar sourcing from `atlas auth status` JSON
- Provider cascade status display
- ATLAS-specific slash commands while inheriting Hermes session/tool commands

---

## 2. Tauri 2 Native Shell + Embedded PTY

### Tauri 2 Core

| Component | Technology | Version | Placement |
|-----------|-----------|---------|-----------|
| Desktop shell | Tauri | 2.10.1 (latest stable, 2026-03-04) | Rust (new `native/atlas-shell/` crate under D-022) |
| Cockpit embed | SvelteKit adapter-static in Tauri webview | same as v1.0 | Existing `apps/cockpit-web/` |
| Shell IPC | Tauri invoke + Channel | built-in | Rust |
| Shell subprocess spawn | `tauri-plugin-shell` | ^2.x (matches tauri 2.x series) | Rust |
| PTY terminal pane | `tauri-plugin-pty` | **0.3.0** (released 2026-06-06) | Rust |
| PTY backend | `portable-pty` | ^0.9.0 (pulled transitively by tauri-plugin-pty) | Rust |
| Frontend terminal | `@xterm/xterm` | **6.0.0** (stable, beta 6.1.0-beta.272 exists) | TypeScript/frontend |
| Frontend PTY bridge | `tauri-pty` npm package | matches tauri-plugin-pty 0.3.0 | TypeScript |

**IPC capability model (Tauri 2):**

Tauri 2 blocks all plugin commands by default. Capabilities are declared per-window in `capabilities/*.json`. For the PTY pane:
- Grant `shell:allow-execute` with explicit allowlist (only `atlas` binary, specific arg patterns).
- PTY data flows through Tauri's typed `Channel<T>` IPC (raw bytes; low overhead).
- No arbitrary command execution from the webview. `atlas` binary path must be in the sidecar or `externalBin` configuration.

**tauri-plugin-pty 0.3.0 specifics:**
- Uses `portable-pty 0.9.0` which wraps Windows ConPTY natively.
- Frontend: `npm install tauri-pty` (npm package named `tauri-pty`, NOT `tauri-plugin-pty`).
- Spawns shell process (e.g., `powershell.exe` on Windows) with column/row size.
- Bidirectional: `pty.onData()` → `terminal.write()` and `terminal.onData()` → `pty.write()`.
- Status: 0.3.0 is the current crates.io release (June 2026). Plugin is active but still in active development — treat as beta-stability. The GitHub README says "Developing! Welcome to contribute." Pin at `= "0.3.0"` to avoid breaking changes during v1.1 development.

**@xterm/xterm specifics:**
- Package scope changed from `xterm` → `@xterm/xterm` at v5. Use the scoped package.
- Current stable: 6.0.0. Do not use the old `xterm` package (no longer maintained).
- Addons: `@xterm/addon-fit` for terminal resize, `@xterm/addon-web-links` optional.

**What the PTY pane runs:** `atlas tui` (or `atlas` bare, which defaults to TUI in v1.1). The PTY is not a general-purpose system terminal — it is scoped to the ATLAS CLI. This is the v1.1 strategy; a more native panel integration using the same JSON-RPC gateway is a v2.x option.

---

## 3. OpenAI/Codex-Compatible Client + Endpoint / Auth Feasibility

### Recommendation: `async-openai` (Rust) for the new auth/provider layer; Python `openai` SDK stays in LLM adapter exception bucket only

| Concern | Finding | Placement |
|---------|---------|-----------|
| Rust client | `async-openai` 0.41.0 (latest, released 2026-06-04). `OpenAIConfig::with_api_base()` sets custom base URL. `with_api_key()` sets key. Supports Chat Completions streaming SSE and the Responses API (feature flag). | Rust — for the provider health-check / model-discovery layer that the atlas-gateway or a new `atlas-provider` crate needs |
| Python LLM adapter | Python `openai` SDK (latest ~1.x series). Already used by Hermes' agent runtime. | Python — exception bucket: LLM adapter; lives in services/agent-runtime adapter |
| OpenAI-first lane | Chat Completions API (`/v1/chat/completions`) via `async-openai` or OpenAI Python SDK. Responses API (`/v1/responses`) can be secondary for Codex-specific features. Both use the same `base_url` mechanism. | Start with Chat Completions; fallback cascade is provider-agnostic. |
| Codex OAuth reuse | **Detection-only.** Confirmed realistic. `~/.codex/auth.json` stores access tokens (format: OpenAI OAuth tokens). The file is explicitly treated as a password by Codex docs — no official API for third-party reuse. ATLAS must not read or mutate this file for its own auth. ATLAS may only detect existence + version string from `codex --version` and `~/.codex/auth.json` (presence only, never token value). | ATLAS reads nothing past file-exists check. |
| Fallback cascade | OpenAI-compatible lane first → any other configured provider that responds (OpenRouter, Anthropic, FreeLLMAPI, custom). Implemented in the credential resolver; not fixed priority. | Python resolver (exception: LLM adapter); routing config lives in `~/.atlas/config.yaml`. |

**async-openai key facts (v0.41.0, HIGH confidence via Context7 + lib.rs):**
```rust
let config = OpenAIConfig::new()
    .with_api_base("https://openrouter.ai/api/v1")
    .with_api_key("sk-or-...");
let client = Client::with_config(config);
```
- `OPENAI_BASE_URL` env var also respected for the base URL.
- Responses API is behind the `responses` feature flag — enable only if Codex-specific Responses endpoint is needed.
- Streaming: `create_stream()` returns `ChatCompletionResponseStream` (SSE). Fully async (tokio).

**D-022 classification:** `async-openai` goes in a new `atlas-provider` Rust crate for health checks and model discovery. The agent execution path stays in Python (Hermes AIAgent), which uses the Python `openai` SDK. This is the correct exception-bucket boundary: Rust handles the outer registry/probe layer; Python handles the inner inference call.

---

## 4. Auth File-Store Primitives

### Hermes pattern (inspected, ground truth)

Hermes `hermes_cli/auth.py` implements cross-process file locking using:
- **Unix:** `fcntl.flock(fd, LOCK_EX | LOCK_NB)` with retry loop
- **Windows:** `msvcrt.locking(fd.fileno(), LK_NBLCK, 1)` with retry loop
- Both are stdlib — no external library dependency
- `atomic_replace(tmp_path, target)` utility writes to temp file then `os.replace()` (atomic on Windows NTFS since Python 3.3)

**Recommendation for ATLAS Python auth store:** copy the same pattern from Hermes directly. It is already proven on Windows in this codebase. Do not add `filelock` (has active CVEs: CVE-2025-68146 and CVE-2026-22701 in SoftFileLock). Do not add `fs2` or `fd-lock` (Rust libs) for the Python layer.

**For Rust crates that need file locking** (future `atlas-provider` or `atlas-state` crate):

| Crate | Version | Windows mechanism | Recommendation |
|-------|---------|------------------|----------------|
| `fd-lock` | 4.0.4 | `LockFileEx` via `windows-sys` | Use for Rust auth store if ATLAS auth moves to Rust |
| `fs2` | 0.4.x | `LockFile`/`UnlockFile` Win32 | Older; works but less actively maintained |
| `named-lock` | varies | Mutex-based (not fd-level) | Do not use — not file-descriptor locking |

**For v1.1:** ATLAS auth store is Python because the auth commands (`atlas auth add/status/remove`) integrate directly with the Python Hermes provider resolver. Use Hermes' `fcntl`/`msvcrt` pattern verbatim, extracted into `services/agent-runtime/atlas_auth.py` (ATLAS namespace).

**File format: JSON (not TOML)**

Hermes uses JSON for auth store (`~/.hermes/auth.json`) and YAML for config (`config.yaml`). Maintain the same split:
- `~/.atlas/auth.json` — JSON, structured credential store (matches Hermes pattern, easy atomic write, no TOML parser dependency)
- `~/.atlas/config.yaml` — YAML, operator configuration (PyYAML already in Hermes venv)

**File permissions:** After atomic write, apply `chmod 600` on Unix. On Windows use `icacls` or `win32security` to restrict to current user only. Hermes `utils.py` uses `stat.S_IRUSR | stat.S_IWUSR` on the parent directory via `secure_parent_dir()`.

---

## Recommended Stack Table (Summary)

### Core Technologies

| Technology | Version | D-022 Layer | Purpose | Why |
|------------|---------|------------|---------|-----|
| Ink + TypeScript | ink 7.0.5 / ts 5.7 | Hermes foundation exception | ATLAS TUI renderer | Already built in Hermes; React-for-terminal is industry standard (Claude Code, Gemini CLI) |
| `@hermes/ink` (vendored) | 0.0.1 (local fork) | Hermes foundation exception | Custom yoga/BIDI/mouse/scroll patches | Required by existing Hermes TUI; do not replace |
| nanostores | ^1.2.0 | Hermes foundation exception | TUI state atoms | Used by existing Hermes TUI; tiny and zero-dependency |
| Tauri | 2.10.1 | Rust (D-022 native) | Native desktop shell | No Electron; Rust backend; webview embed |
| tauri-plugin-pty | 0.3.0 | Rust (D-022 native) | PTY terminal pane in native shell | Only production-quality PTY plugin for Tauri 2; portable-pty backend covers ConPTY on Windows |
| `@xterm/xterm` | 6.0.0 | Frontend (native shell webview) | Terminal renderer in PTY pane | Industry standard web terminal; actively maintained |
| async-openai | 0.41.0 | Rust (D-022 native) | Provider health checks, model discovery HTTP | Full Chat Completions + Responses API; custom base_url via `with_api_base` |
| Python openai SDK | latest 1.x | Python exception: LLM adapter | Hermes AIAgent inference calls | Already in Hermes venv; used by existing agent runtime |
| fcntl / msvcrt (stdlib) | Python stdlib | Python exception: auth | Auth file locking on Unix/Windows | Zero dependency; exact pattern already proven in Hermes auth.py |

### Supporting Libraries

| Library | Version | Placement | Purpose | When to Use |
|---------|---------|-----------|---------|-------------|
| `tauri-plugin-shell` | ^2.x | Rust | Sidecar/subprocess spawn with capability allowlist | Spawn `atlas` binary from native shell if not using plugin-pty directly |
| `portable-pty` | ^0.9.0 | Rust (transitive) | ConPTY/Unix PTY abstraction | Pulled automatically by tauri-plugin-pty |
| `tauri-pty` (npm) | matches 0.3.0 | TypeScript (native shell frontend) | JS bridge for PTY IPC | Companion to tauri-plugin-pty Rust crate |
| `@xterm/addon-fit` | ^0.10.0 | TypeScript (native shell frontend) | Resize terminal to container | Always needed with xterm.js in Tauri webview |
| `fd-lock` | 4.0.4 | Rust | File locking for future Rust auth crate | If/when auth store migrates to Rust (v2.x) |
| `httpx` | already in Hermes venv | Python | HTTP client for provider health checks | Already used by Hermes auth.py; use for ATLAS provider probes |
| PyYAML | already in Hermes venv | Python | Config file read/write | Already used; ATLAS config.yaml reads |
| `tsx` | ^4.19.0 | TypeScript dev tooling | Fast TS execution for TUI dev | Already in Hermes TUI; copy to ATLAS TUI |
| `esbuild` | ~0.27.0 | TypeScript build | Bundle TUI for distribution | Already in Hermes TUI |
| `vitest` | ^4.1.3 | TypeScript test | TUI unit tests | Already in Hermes TUI |

---

## Installation

```bash
# ATLAS TUI (new apps/atlas-tui/ — forked from foundation/atlas-hermes/ui-tui/)
# Copy package.json from ui-tui, rename package to "atlas-tui", update @hermes/ink ref
npm install  # installs ink, nanostores, ink-text-input, unicode-animations, etc.

# Native shell Rust (native/atlas-shell/Cargo.toml — new crate under native/atlas-core-rs/)
cargo add tauri@2.10
cargo add tauri-plugin-pty@0.3
cargo add tauri-plugin-shell

# Native shell frontend (inside apps/cockpit-web or apps/atlas-shell-ui/)
npm install @xterm/xterm @xterm/addon-fit tauri-pty

# Atlas provider Rust crate (native/atlas-core-rs/crates/atlas-provider/)
cargo add async-openai@0.41

# Python auth (services/agent-runtime/atlas_auth.py — no new pip deps needed)
# fcntl/msvcrt are stdlib; httpx and PyYAML already in Hermes venv
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| Ink/TypeScript TUI (adapt Hermes) | ratatui 0.30 (Rust TUI) | Rewrites 7000-line gateway + all panels; high risk, delays auth/model/agent work; D-022 allows Hermes exception |
| tauri-plugin-pty 0.3.0 | pty-process crate | pty-process has no Tauri IPC integration; would require custom channel plumbing |
| tauri-plugin-pty 0.3.0 | tauri-plugin-shell only | plugin-shell spawns processes but has no PTY (no raw terminal mode, no resize, no xterm.js binding) |
| @xterm/xterm 6.0.0 | xterm (old unscoped) | Old package unmaintained; scoped `@xterm/*` is the current org |
| async-openai 0.41.0 | openai-rs, rellfy/openai | async-openai has the highest download count, active maintenance, and native Responses API support |
| fcntl/msvcrt stdlib | Python filelock library | filelock 3.x has active CVEs (CVE-2025-68146, CVE-2026-22701) in SoftFileLock; stdlib pattern is already proven in Hermes |
| fd-lock 4.0.4 (Rust) | fs2 | fd-lock is more actively maintained and uses LockFileEx on Windows (stronger than fs2's approach) |
| JSON for auth store | TOML for auth store | Hermes uses JSON for auth; atomic_replace + json.dumps is already the proven pattern; TOML adds parser dependency |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| New Rust TUI (ratatui) for v1.1 | Rewrites proven gateway; delays all other workstreams by 3-4 weeks | Adapt Hermes Ink TUI |
| Python `filelock` library | Active CVEs in SoftFileLock (TOCTOU); advisory lock only anyway | fcntl + msvcrt stdlib (Hermes pattern) |
| Electron | D-005 hard no; Tauri is the decision | Tauri 2.x |
| `keytar` / OS keychain for v1.1 | Adds native binary dependency per platform; deferred in locked scope | File-store first with restricted permissions |
| Hermes' `copilot_auth.py` / Codex OAuth reuse | Reading or mutating `~/.codex/auth.json` is out of locked scope; Codex tokens are not licensed for third-party use | ATLAS-owned creds in `~/.atlas/auth.json` |
| OpenAI Responses API as primary lane | Responses API requires different response shape; not all providers support it | Chat Completions `/v1/chat/completions` as primary lane |
| `named-lock` Rust crate | Mutex-based, not fd-level locking; does not work cross-process on Windows reliably | fd-lock 4.0.4 |
| `ink ^7.x` right now (in ATLAS TUI fork) | Hermes vendor pins `^6.8.0`; `@hermes/ink` local fork likely not React 19 compatible without testing | Stay on ink ^6.8.0 initially; test ink 7 upgrade as a separate phase task |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|----------------|-------|
| tauri-plugin-pty 0.3.0 | tauri ^2, portable-pty ^0.9.0, tauri-pty npm (matching) | Pin at `= "0.3.0"` — plugin is in active development; breaking changes likely between minor versions |
| @xterm/xterm 6.0.0 | @xterm/addon-fit ^0.10.0, @xterm/addon-web-links ^0.11.0 | All @xterm/* addons must be on the same major (6.x) |
| async-openai 0.41.0 | tokio ^1, reqwest (internal) | Ensure tokio version matches atlas-gateway workspace dep (tokio = "1" — compatible) |
| ink ^6.8.0 | react ^19.2.4, ink-text-input ^6.0.0, node ^22 | Hermes already uses these exact versions — copy from ui-tui/package.json |
| Tauri 2.10.1 | tauri-plugin-shell ^2.x, tauri-plugin-pty 0.3.0 | All tauri-apps/* plugins must be on 2.x to match tauri core |

---

## Sources

- `/websites/v2_tauri_app` (Context7) — Tauri 2 plugin-shell, IPC capability model, sidecar pattern
- `/websites/rs_async-openai_0_34_0` (Context7) — OpenAIConfig struct, with_api_base, streaming Chat Completions
- `lib.rs/crates/async-openai` — confirmed 0.41.0 latest with Responses API feature flag
- `foundation/atlas-hermes/ui-tui/package.json` — Hermes TUI actual dependency versions (inspected)
- `foundation/atlas-hermes/packages/hermes-ink/package.json` — @hermes/ink local fork contents (inspected)
- `foundation/atlas-hermes/tui_gateway/server.py` — JSON-RPC gateway architecture (inspected, 7000 lines)
- `foundation/atlas-hermes/hermes_cli/auth.py` — fcntl/msvcrt auth locking pattern (inspected)
- `foundation/atlas-hermes/utils.py` — atomic_replace implementation (inspected)
- `docs.rs/crate/tauri-plugin-pty/latest` — version 0.3.0, portable-pty ^0.9.0 dep, Windows powershell spawn
- `docs.rs/crate/fd-lock/latest` — version 4.0.4, LockFileEx on Windows via windows-sys
- WebSearch: ink 7.0.5 (2026-06-13), @xterm/xterm 6.0.0 stable, Tauri 2.10.1 (2026-03-04)
- WebSearch: filelock CVE-2025-68146 and CVE-2026-22701 — confirmed reason to avoid
- `developers.openai.com/codex/auth` — confirmed ~/.codex/auth.json is access-token cache; no third-party reuse documented

---

*Stack research for: ATLAS v1.1 — Agent Harness & Native Operator Shell*
*Researched: 2026-06-15*
