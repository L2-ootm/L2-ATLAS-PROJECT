# ATLAS Go TUI + Multi-Mode Provider Mesh — Design

**Date:** 2026-06-28
**Status:** Design (validated forks; pending section validation)
**Operator directives (this session):**
1. Replace the below-bar Rich/prompt_toolkit TUI with an opencode/MiMo-grade terminal workbench.
2. Reimplement the TUI in **Go (BubbleTea/Charm)** — *TUI and needed glue only*; the **Rust runtime/gateway stays**.
3. Full **settings/provider rework** so the operator can wire models **every way**:
   - **Codex OAuth import** — reuse the ChatGPT auth from the existing `~/.codex` install.
   - **Claude Code** — run on the local Claude subscription session (agent runtime).
   - **API keys** — direct provider keys (OpenRouter/OpenAI/Anthropic/compatible).
   - **FreeLLMAPI** — free models for testing/prototyping (privacy-cost, opt-in).
4. North star: a beautiful terminal surface where the operator wires any provider and **runs + watches a real agent** end-to-end.

This pulls forward the v1.2 *Provider Mesh & Runtime Interoperability* draft and the v1.2 *SOTA-TUI* candidate, reordered **provider-first, TUI-second**.

---

## 1. Architecture — why this is low-friction

opencode's celebrated TUI is **not a monolith**: it is a thin Go/BubbleTea client over an HTTP+SSE server. ATLAS **already has that server** — the Rust gateway with `/v1/runs/{id}/stream` (SSE), `/v1/missions/*`, `/v1/config`, `/v1/tools/*`. So the Go TUI is a **sidecar client of the existing gateway**, not a new runtime.

```
┌─────────────────────────┐     HTTP + SSE      ┌──────────────────────┐     CLI contract     ┌──────────────────────┐
│  atlas-tui (Go/Bubble-  │ ──────────────────▶ │  atlas-gateway (Rust │ ───────────────────▶ │  agent-runtime (Py)  │
│  Tea) — NEW sidecar     │ ◀────────────────── │  axum) — dispatch    │ ◀─────────────────── │  agents/ + auth/cfg  │
│  render + input only    │   normalized events │  only (D-022)        │   JSON + audit rows  │  + foundation harness│
└─────────────────────────┘                     └──────────────────────┘                      └──────────────────────┘
```

**Invariants preserved:**
- **D-022:** gateway stays dispatch-only; Python owns auth/config/run state; the new Go binary holds **no** business logic — render + input + HTTP only.
- **D-001:** the vendored Hermes foundation is used, not edited.
- **v1.2 "adapters only":** no donor runtime/config/auth/identity imported. We study MiMo's TS source and upstream opencode's Go patterns for *structure/UX*; we write ATLAS-native Go.
- The TUI consumes the **same** surface-session / normalized-event / permission contracts (10.3/10.5/10.6) the cockpit will — one agent, many surfaces.

**Why provider-first:** the operator's north star is "wire models every way and test." The wiring is a Python/gateway substrate that is **independently testable via the CLI before the Go TUI exists**, and lower-risk (it extends the existing `auth_service`/`config_service`). The Go TUI then *surfaces* it. Building the surface first would have nothing real to drive.

---

## 2. Workstream B — Multi-Mode Provider Mesh (substrate, first)

### 2.1 Provider profile model

Today: a single `ProviderConfig{name, model, api_key("env:VAR"|""), base_url}` plus an ATLAS-owned `auth.json` keyed by provider (api_key records) and a read-only `detect_external_auth()` that *sees* `~/.codex/auth.json` and `~/.claude/.credentials.json` by presence only.

Rework: a **provider profile** carries an explicit **auth mode**.

| auth_mode | meaning | secret location | resolution |
|---|---|---|---|
| `api_key` | direct key | ATLAS `auth.json` (encrypted-at-rest store) or `env:VAR` | existing path |
| `oauth_import` | import external OAuth (Codex/ChatGPT) | **read-through** from `~/.codex/auth.json`; ATLAS stores only a *pointer + expiry*, never copies the long-lived secret unless required | new (§2.2) |
| `claude_code` | local Claude subscription | none (SDK uses local `claude` session) | existing `ClaudeCodeAgent` |
| `freellmapi` | free OpenAI-compatible endpoint | none or free key | base_url provider (§2.3) |

`ProviderConfig` gains `auth_mode: Literal[...] = "api_key"` (back-compat default) and an optional `profile_id`. `resolve_provider()` branches on `auth_mode` to produce the `(model, provider, base_url, api_key|token)` the `NativeAtlasAgent` factory already accepts — **no change to the agent execution contract**, only to how credentials are resolved.

### 2.2 Codex OAuth import

`~/.codex/auth.json` = `{auth_mode:"chatgpt", OPENAI_API_KEY:null, tokens:{id_token, access_token, refresh_token, account_id}}`. Import flow:
- New `codex_auth.py`: read the file read-only (respect `CODEX_HOME`), parse tokens, surface `{email, expiry, account_id}` (secret-free) for status.
- Resolution returns a **bearer token** + the ChatGPT-backend base_url so the foundation harness calls the same endpoint Codex does. **Refresh:** if `access_token` is expired and a `refresh_token` exists, refresh via the documented OAuth token endpoint; otherwise fail closed with remediation ("re-login with `codex` CLI").
- **Provenance/safety:** import is explicitly operator-initiated and audited (`auth_change` event, source=`codex_import`). ATLAS never writes back to `~/.codex`. Token bytes are redacted everywhere except the runtime call boundary.
- **Open risk:** the ChatGPT-backend request shape is not a public stable contract. De-risk spike required before committing (mirror the P4 `claude-agent-sdk` spike discipline). If the spike fails, downgrade Codex to "API-key only" and keep the OAuth-import as a flagged experiment.

### 2.3 FreeLLMAPI wiring

Per D-015 (sidecar-first). A `freellmapi` profile is a base_url provider (OpenAI-compatible) with optional/empty key. Deliver: a curated free-model list, a **privacy warning** surfaced at selection ("free models may log prompts — do not send secrets"), and routing through the same `NativeAtlasAgent`. Sidecar lifecycle reuses the Discord/Cashflow `*_control.py` pattern if a local proxy is needed; otherwise a remote base_url is sufficient.

### 2.4 Claude Code mode

Already implemented (`ClaudeCodeAgent`). Rework = make it a first-class selectable profile and **close the venv gap**: the active PATH python is the pip-less Hermes venv, so `claude-agent-sdk` is not importable in gateway-dispatch context. Fix: install `atlas-runtime[claude]` into the gateway's dispatch venv (documented in the install path) and add a `doctor` check.

### 2.5 Gateway auth control-plane (dispatch-only)

New routes mirroring the CLI (D-022): `GET /v1/auth` (status list, secret-free), `POST /v1/auth/providers` (configure profile/api_key), `POST /v1/auth/codex/import`, `DELETE /v1/auth/providers/{id}`. Each validates body, shells `atlas auth ...`, returns masked JSON. No secrets cross masked APIs.

---

## 3. Workstream A — Go/BubbleTea TUI Sidecar (surface, second)

New module `services/atlas-tui/` (Go). Attribution/notices per the 10.1 provenance regime. BubbleTea Elm-architecture (Model/Update/View); Lipgloss for the L2 theme (Electric Violet / Cyber Blue / Titanium White, HUD voice).

**Components (reimplemented patterns, ATLAS-native):**
- **Gateway client** — typed Go HTTP client + SSE consumer (`/v1/runs/{id}/stream` named events: `audit`/`end`/`stream_error`), config/auth/tools/missions.
- **Status header** — workspace (global/project), model, auth mode + health, permission mode, context budget, session state.
- **Transcript** — streamed normalized events (text, reasoning, tool calls/results, tasks/subagents, retries, retrieval provenance, errors, completion) with scrollback + syntax/diff rendering.
- **Composer** — multi-line input, command palette (`/mission`, `/focus`, `/wiki`, `/config`, `/provider`, `/session`).
- **Provider/settings flow** — pick profile + auth mode; api_key entry (hidden), `codex import`, `claude_code`, `freellmapi`; **"Test connection / run a probe"** action → fires a real one-shot run and streams it. *This is the "wire any provider and test" deliverable.*
- **Permission pane** — maps the broker/tool-approval queue (10.5) to a blocking native prompt; only this session's requests are actionable.

**Launcher:** `atlas tui` spawns the Go binary (built sidecar), demoting the Python Rich workbench to a fallback, then retiring it per the 10.8 cutover discipline (tested rollback + dated retirement). Cross-platform build (Windows-first, given the dev box).

---

## 4. Phasing (GSD)

Provider-first so each phase is independently testable; TUI consumes a proven substrate.

| Phase | Deliverable | Gate |
|---|---|---|
| **P1** Provider profile model + auth-mode resolution | `ProviderConfig.auth_mode`, branched `resolve_provider`, migration if needed; CLI `atlas auth` extended | unit + CLI smoke; existing suites green |
| **P2** Codex OAuth import (spike→impl) | `codex_auth.py` read/refresh, audited import, runtime resolution | **de-risk spike** then real run against ChatGPT backend |
| **P3** FreeLLMAPI + Claude-Code profiles | free-model routing + privacy warning; claude_code venv gap closed + `doctor` | live free-model run; claude_code run |
| **P4** Gateway auth control-plane | `/v1/auth*` dispatch routes | `cargo test` + contract tests |
| **P5** Go TUI sidecar scaffold + gateway client | `services/atlas-tui` builds; connects; streams a run | end-to-end stream of a real run |
| **P6** TUI panes (header/transcript/composer/permission) | usable workbench | cross-terminal render tests |
| **P7** TUI provider/settings + test-probe flow | wire any provider in-TUI and run a probe | operator UAT: 4 modes each fire a run |
| **P8** Launcher cutover + retire Rich TUI | `atlas tui` → Go binary; rollback + retirement note | 10.8-style cutover gate |

P1–P4 (substrate) land and are CLI-testable before any Go is written. P2's spike is the highest risk and is gated.

---

## 5. Risks / open items

- **Codex ChatGPT-backend contract instability** (P2) — spike-gated; fallback = API-key-only.
- **Go toolchain added to the repo** — accepted (operator-approved); isolated to `services/atlas-tui`. Budget: cold-start + idle-memory baselines per the 10.1 regime.
- **Two terminal stacks during transition** — bounded by the 10.8 cutover discipline (no indefinite duplicate).
- **MiMo `USE_RESTRICTIONS.md`** beyond MIT — we import *patterns*, not code; re-confirm before any snippet reuse.
- **FreeLLMAPI privacy** — explicit warning + never default; secrets-in-prompt stop already exists (`SECRET_PATTERNS`).

---

## 6. Provenance

- Donor: `XiaomiMiMo/MiMo-Code` (TS/Bun) + upstream `opencode` (Go/BubbleTea) patterns. Reference checkouts gitignored under `_EXTERNAL_REPOS/`.
- Attribution: extend `ATTRIBUTION.md` + `docs/third-party/` per the 10.1 intake regime.
- No donor runtime/config/auth/identity in shipped code (v1.2 constraint).
