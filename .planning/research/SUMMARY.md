# Project Research Summary

**Project:** L2 ATLAS
**Milestone:** v1.1 — ATLAS Agent Harness & Native Operator Shell
**Domain:** Local AI operator runtime (TUI, owned auth, provider/model registry, agentic chat, native desktop shell)
**Researched:** 2026-06-15
**Confidence:** HIGH

## Executive Summary

v1.1 turns ATLAS from a cockpit MVP backed by an operational CLI into a credible local AI operator harness. Targeted research (4 parallel agents, grounded in the vendored Hermes v0.14.0 source and verified library versions) confirms the milestone is buildable largely by *adapting and extending* the Hermes foundation rather than rewriting it. The dominant risk is not capability — it is discipline: secret leakage into an audit-first system, Codex auth mutation, fallback cascades that mask real auth errors, and a native shell that ships as an empty wrapper over a missing harness.

The recommended approach is a Python adapter over Hermes AIAgent (LLM-adapter exception bucket under D-022), an ATLAS-owned file-store auth layer reusing Hermes' proven `fcntl`/`msvcrt` lock pattern, a provider/model registry as new Pydantic schemas + a `0004_registry_v2.sql` migration surfaced through the existing Rust gateway, an ATLAS-branded TUI forked from the Hermes Ink/TypeScript TUI over its existing stdio JSON-RPC `tui_gateway`, and a thin Tauri 2 native shell that is built last and hard-gated on the harness being real.

Key risks are mitigated by sequencing (auth first; native shell last, gated on chat+TUI), by test gates (concurrent-write, no-Codex-mutation byte-identity, redaction grep, idempotent-discovery, audit-metadata assertions), and by an explicit adapter boundary that keeps `foundation/` changes to extension-points-only (tracked in DIVERGENCE_LOG).

## Key Findings

### Recommended Stack

Adapt the existing Hermes Ink (TypeScript/React-for-terminal) TUI rather than build a Rust TUI — the JSON-RPC gateway and panel set already exist and are Windows-tested; a Rust rewrite would delay every other workstream for no v1.1 benefit. Rust is reserved for the new outer probe layer and the native shell. Python stays inside its D-022 exception buckets (Hermes foundation surface, LLM adapters, auth store integrating the Python credential resolver).

**Core technologies:**
- Ink ^6.8.0 + `@hermes/ink` (vendored fork) — ATLAS TUI renderer — already built, industry-standard for agent CLIs (Claude Code, Gemini CLI)
- Tauri 2.10.1 + `tauri-plugin-pty` 0.3.0 (portable-pty/ConPTY) + `@xterm/xterm` 6.0.0 — native shell + PTY — no Electron (D-005), Rust backend
- `async-openai` 0.41.0 (Rust) — provider health-check/model-discovery HTTP with custom `base_url` — outer registry layer
- Python `openai` SDK (existing Hermes venv) — agent inference — LLM-adapter exception bucket
- `fcntl`/`msvcrt` stdlib lock + `os.replace()` atomic write — auth file store — proven in Hermes `auth.py`; avoids `filelock` (active CVEs)
- JSON `~/.atlas/auth.json` + YAML `~/.atlas/config.yaml` — ATLAS-owned state, same dir as `atlas.db`

### Expected Features

**Must have (table stakes):** ATLAS-branded TUI (transcript, streaming, composer, tool activity, status bar, clean exit); `atlas` entrypoint + `chat -q`/interactive/`doctor`; `~/.atlas` auth store with atomic write + lock + redaction; `auth add/list/status/remove/doctor`; read-only Codex detection; provider registry with honest health; model registry v2 with source/status/auth; `models discover`/`list --all`; runtime adapter over Hermes AIAgent; OpenAI-first health-aware fallback cascade; audit metadata on model calls; Tauri shell + PTY running `atlas tui`; redaction test suite.

**Should have (competitive):** mission-bound chat + audit references in TUI; `atlas route show/set` task-class routing; session resume; token/context-window status bar; subagent activity panel; native auth/model readiness panel.

**Defer (v1.2+):** OS keychain; OAuth device-code flow; credential pools; native approval overlay; tray icon/global hotkey; model latency benchmarking. **(v2.0+):** CRM/Twenty, Pulse, voice/overlay, multi-user, mobile, public installer.

### Architecture Approach

New v1.1 components integrate along the existing 4-layer boundary without disturbing it: the agent adapter lives in `services/agent-runtime/` (Python) and reaches Hermes AIAgent via the existing stdio JSON-RPC `tui_gateway` (the TUI spawns `atlas tui_gateway` as a subprocess — chat traffic does **not** route through the Rust gateway). Registry data flows Pydantic schema → `0004` migration → Rust gateway read-only routes (`/providers`, `/models/v2`) → cockpit. The Tauri shell is a standalone `native/atlas-shell/` crate that embeds the static cockpit, starts the gateway subprocess, and hosts a PTY running `atlas tui`.

**Major components:**
1. `atlas_runtime/auth/` (Python) — `~/.atlas/auth.json` store, resolver, read-only `codex_detect`
2. `atlas_runtime/chat_adapter.py` (Python) — Hermes AIAgent wrapper, audit emission, fallback cascade
3. `atlas_runtime/provider_registry.py` + `0004_registry_v2.sql` — provider/model/route registry, source-scoped deactivation
4. `apps/atlas-tui/` (Ink/TS) — ATLAS-branded TUI over `tui_gateway` JSON-RPC
5. `native/atlas-shell/` (Tauri 2/Rust) — cockpit embed + capability-scoped PTY pane

### Critical Pitfalls

1. **Secret leakage into the audit-first path** — define a `RedactedStr` type and a `redact_auth_dict()` pass before the first auth model is written; CI grep of CLI output, logs, and audit JSONL for `sk-`/`Bearer `/`eyJ`.
2. **`~/.codex` accidental mutation** — Codex detection is a separate read-only module with no write path; prove byte-identity (mtime+hash) of `~/.codex/auth.json` after all auth/discovery commands.
3. **Fallback cascade masking auth errors** — classify errors (401/403 halt, never cascade; 429/5xx/timeout cascade with audit event); surface the provider actually used on every response.
4. **Model registry duplicates / `first_seen` loss** — composite key `(model_id, provider_id, source)`, `ON CONFLICT DO UPDATE` (never `INSERT OR REPLACE`), source-scoped deactivation only.
5. **Native shell as empty wrapper** — Phase 10.5 hard-gated on 10.2 (chat) + 10.4 (TUI); the PTY runs `atlas tui`, never `bash`/`cmd`. Plus discipline gates: adapter stays in `services/` (extension-points-only `foundation/` diff), PTY accepts keystrokes not command strings, Tauri IPC is an explicit allowlist, no CRM/Pulse creep.

## Implications for Roadmap

Seven phases (10.0–10.6), continuing v1.0's decimal-phase convention. Auth is the critical path for everything; the native shell is intentionally last.

### Phase 10.0: Harness Architecture & Threat-Model Design
**Rationale:** The auth-store layout (flat vs profile) and adapter boundary affect every downstream component; OAuth/IPC threat models must precede privileged code.
**Delivers:** committed auth design, TUI/transport decision (Ink + `tui_gateway`), registry schema draft (`0004`), OAuth-callback + native-IPC threat-model drafts, fallback-cascade spec.
**Avoids:** empty-wrapper and Hermes-rewrite pitfalls by fixing the boundary before code.

### Phase 10.1: ATLAS-Owned Auth Store & Codex Detection
**Rationale:** Critical-path dependency for chat, discovery, and TUI.
**Delivers:** `~/.atlas/auth.json` (atomic + lock + redaction), `atlas auth add/list/status/remove/doctor`, read-only Codex detection, redaction + no-mutation + concurrent-write test gates.
**Uses:** Hermes `fcntl`/`msvcrt` pattern. **Avoids:** pitfalls 1, 2, 14.

### Phase 10.2: Agentic Chat CLI & Runtime Adapter
**Delivers:** `atlas` entrypoint + branded tree, `atlas chat -q`/interactive, Hermes AIAgent adapter, OpenAI-first fallback cascade, audit metadata on calls, tool-approval protocol.
**Implements:** components 1–2. **Avoids:** pitfalls 3, 8, 9, 10, 16.

### Phase 10.3: Provider/Model Discovery & Cockpit Truth
**Delivers:** `0004` migration, provider registry, `atlas providers`/`models discover`/`list --all`, Rust gateway `/providers` + `/models/v2`, cockpit Models page alignment, `atlas doctor`.
**Avoids:** pitfalls 4, 5, 6, 7.

### Phase 10.4: ATLAS TUI
**Delivers:** ATLAS-branded Ink TUI over `tui_gateway` — transcript/composer/streaming/tool-activity/status-bar/auth-model awareness/clean exit/approval prompt.
**Uses:** Ink stack. **Avoids:** the Rust-rewrite anti-feature.

### Phase 10.5: Native Operator Shell (Tauri 2 + PTY)
**Rationale:** Built last; wraps a working harness.
**Delivers:** `native/atlas-shell/` Tauri 2 crate, cockpit embed, gateway subprocess launch, PTY running `atlas tui`, capability allowlist, native-IPC threat model.
**Avoids:** pitfalls 11, 12, 13, 15, 17.

### Phase 10.6: Integration & Manual UAT
**Delivers:** end-to-end wiring, operator runbooks (auth/TUI/models/native), v1.1 manual UAT guide, no-secret screenshot review, archive verdict.

### Phase Ordering Rationale
- Auth (10.1) precedes chat/discovery/TUI because all three resolve credentials through it.
- Discovery (10.3) precedes/parallels TUI (10.4) because the status bar needs the registry.
- Native shell (10.5) is hard-gated on chat (10.2) + TUI (10.4) to prevent the empty-wrapper failure.
- 10.0 is a no-REQ design phase (precedent: v1.0 Phase 7 owned no REQ-IDs).

### Research Flags
- **Phase 10.5 (native shell):** `tauri-plugin-pty` 0.3.0 is in active development (treat as beta; pin exactly) — needs a thin spike before committing the PTY approach.
- **Phase 10.1 (OAuth):** device-code/PKCE feasibility per target provider — only if OAuth is pulled in; default is API-key + read-only Codex.
- Phases 10.2/10.3/10.4 follow established Hermes patterns — standard, lower research need.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified via Context7/crates.io; Hermes source inspected |
| Features | HIGH | Grounded in Hermes/opencode/Claude Code/Aider behavior + operator-authored prep |
| Architecture | HIGH | All findings tied to real repo files (gateway, tui_gateway, auth, migrations) |
| Pitfalls | HIGH | Derived from prep security sections + concrete domain knowledge, phase-mapped |

**Overall confidence:** HIGH

### Gaps to Address
- `tauri-plugin-pty` stability: spike in 10.5; fall back to `portable-pty` direct + `tauri-plugin-shell` if the plugin breaks.
- Ink 6→7 / React 19 upgrade: keep `@hermes/ink` pin initially; treat upgrade as a separate task.
- First real provider end-to-end: OpenAI/Codex-compatible lane is primary per operator decision; validate live in 10.2 UAT.

## Sources

### Primary (HIGH confidence)
- Vendored `foundation/atlas-hermes/` — TUI (`ui-tui/`, `tui_gateway/`), `hermes_cli/auth.py`, `agent/conversation_loop.py`, `credential_pool.py`, `pty_bridge.py`
- `native/atlas-core-rs/crates/atlas-gateway/` (lib.rs, db.rs); `infra/migrations/0003_model_registry.sql`; `packages/atlas-core/.../core.py`
- Context7: Tauri 2, `async-openai`; crates.io/docs.rs for `tauri-plugin-pty` 0.3.0, `fd-lock` 4.0.4
- ATLAS `.planning/prep/` set (operator-authored)

### Secondary (MEDIUM confidence)
- opencode / Claude Code / Aider / Codex CLI observed behavior; circuit-breaker production literature; RFC 8252 (OAuth native-app PKCE)

---
*Research completed: 2026-06-15*
*Ready for roadmap: yes*
