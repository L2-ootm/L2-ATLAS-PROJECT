# ATLAS Native Cockpit Strategy

**Date:** 2026-06-08
**Status:** Locked direction for the native shell — governs **Phase 10 (Native Cockpit Shell, v1.1)** per D-021 §1. Phase 8 ships the web-first, native-portable SvelteKit cockpit that this shell later wraps unchanged.
**Sequencing update (2026-06-10, D-021):** v1.0 delivers the cockpit as a browser app against the Phase 7 API under native-portability constraints (adapter-static, no SSR runtime, no WebView2-incompatible APIs, no OS-privileged features). Everything in this document that requires the Tauri shell — PTY/terminal pane, OS keychain, native approval popups, Tauri IPC capability model, threat-model gate — is Phase 10 scope. Nothing else in this document changes.
**Reference pillars:** Terax AI (`8200938397ec31f89119bec808a3355d80e90d0e`, Apache-2.0), Odysseus (`8449baea80db7763e713685ec98760cd8d398802`, MIT, source-inspected — see `docs/research/ODYSSEUS_AUDIT.md`)

---

## Strategic Statement

ATLAS Phase 8 is not a generic web dashboard. It is a native operator cockpit: a local-first, Rust-backed desktop application that wraps the ATLAS runtime and exposes operator surfaces for mission management, run monitoring, audit, and approval.

The web UI layer (SvelteKit, D-006) remains valid for information-dense surfaces. It runs inside the native shell, not standalone. The native shell owns OS integration: PTY sessions, OS keychain, global hotkeys, system tray, approval popups, and the IPC bridge to the ATLAS runtime.

**Core equation:**
```
Odysseus ambition + Terax native speed + Hermes tooling + ATLAS audit/policy/wiki
```

---

## ATLAS Runtime Boundary

The ATLAS runtime owns all domain logic. The cockpit is a client, not a co-owner.

**Runtime owns:**
- Mission model and state machine.
- Run lifecycle: create, start, execute, complete, cancel, fail.
- AuditEvent bus: every meaningful action emits a typed event.
- ToolCall, Artifact, Source, and WikiPage records.
- Policy decisions: workspace boundary, capability authorization, spend limits.
- Model/provider routing and credential resolution.
- Wiki ingest, update, lint, and search.
- Skills and workflow execution.
- Cron and subagent lifecycle.
- Approval state machine: emit ApprovalRequest, receive Grant/Deny.

**Runtime does NOT own:**
- Terminal rendering.
- File tree display.
- Git panel display.
- Approval UI popup.
- OS keychain UI.
- Global hotkeys.
- System tray icon.

---

## Native Cockpit Shell Boundary

The native cockpit shell owns all local OS surface concerns. It has no domain logic — it delegates every state change to the ATLAS runtime via the IPC bridge.

**Shell owns:**
- Tauri/Rust binary lifecycle: startup, tray, update, shutdown.
- Local PTY session management (via `portable-pty`).
- Terminal pane rendering (xterm.js inside webview, or equivalent native).
- Mission/run view surfaces (consuming Phase 7 API).
- Approval prompt rendering: surface ApprovalRequest from runtime, return Grant/Deny.
- File/artifact context picker: attach local files to missions/runs/wiki.
- Git/diff viewer: show source evidence for implementation runs.
- Provider/settings UI: configure model, keys, local options (writes to OS keychain via runtime).
- Native credential UX: OS keychain read/write via Rust backend, never exposed to webview state.
- System tray: run-in-progress indicator, quick-access to cockpit.
- Notification surface: run completion, approval pending, wiki update, error alerts.

**Shell does NOT own:**
- Policy decisions.
- Audit event storage.
- Model selection logic.
- Mission state transitions (these are API calls to the runtime).
- Any credential in plaintext form (keys transit Rust backend only).

---

## Local IPC/API Bridge

The cockpit communicates with the ATLAS runtime via two channels:

### Channel 1 — REST API (Phase 7)

Used for: all CRUD operations, query operations, and commands that are not latency-critical.

- `POST /missions` — create mission.
- `GET /missions` — list missions.
- `POST /missions/{id}/run` — start run.
- `GET /runs/{id}` — poll run status.
- `GET /runs/{id}/events` — paginated audit event list.
- `GET /wiki/pages` — list wiki pages.
- `GET /wiki/search?q=` — FTS5 search.
- `POST /approvals/{id}/grant` — grant approval.
- `POST /approvals/{id}/deny` — deny approval.

Transport: HTTP on `127.0.0.1` only. No external network binding.

### Channel 2 — SSE/WebSocket (Phase 7 streaming endpoint)

Used for: real-time audit event stream during active runs, approval request push.

- `/runs/{id}/stream` — SSE stream of AuditEvents as they are emitted.
- `/approvals/stream` — SSE stream of pending ApprovalRequests.

The cockpit subscribes to these streams and updates the UI without polling.

### Channel 3 — Tauri IPC (native shell only)

Used for: cockpit-internal operations that require OS access without going through the Python runtime.

- PTY session create/resize/close.
- Keychain read/write (proxied through Rust backend, never exposed to webview).
- File picker (OS file dialog).
- Notification dispatch.

Tauri IPC is never used for ATLAS domain operations — those always go through the REST/SSE API.

### Transport Security

- All API communication is localhost only (`127.0.0.1`; no `0.0.0.0` binding).
- Tauri IPC: capability-declared commands only. The webview cannot call undeclared commands.
- No TLS required for loopback. Authentication is implicit (local user session).
- Correlation IDs: every request carries a `x-atlas-correlation-id` header. The runtime records this in AuditEvents.

---

## Capability Model

Operations in the cockpit are grouped into capability tiers. The policy engine (Phase 5) enforces these. The cockpit presents the active tier in approval prompts.

| Tier | Operations | Authorization |
|------|-----------|--------------|
| Read | View missions, runs, audit log, wiki pages, run status | Always permitted for local operator |
| Operator | Create mission, launch run, cancel run, wiki ingest/update | Session token present (v1.0: implicit local) |
| Shell | Execute terminal command, spawn subprocess, git operation | Workspace authorization + policy check |
| Network | Outbound HTTP (via ATLAS AI proxy), external API call | Workspace allowlist + audit event |
| Destructive | Delete artifact, purge wiki entry, force-cancel active run | Confirmation prompt + dual AuditEvents |
| Admin | Credential write, policy change, workspace config update | Explicit admin grant (v1.0: local user is always admin; flag for v2.0 multi-user) |

The approval surface must display: tier name, operation summary, affected resources, and matching policy rule.

---

## Credential and Keychain Policy

1. Provider API keys (OpenAI, Anthropic, FreeLLMAPI, etc.) live in the OS keychain. Windows: Credential Manager. macOS: Keychain. Linux: libsecret/Secret Service.
2. The Rust backend reads credentials from the keychain on demand. The key value is never written to disk, environment, or Tauri IPC payload.
3. The webview UI shows only a masked indicator ("key present" / "key missing"), never the key value.
4. When the operator sets a new key via the settings surface, it is sent to the Rust backend via Tauri IPC. The backend writes to keychain. The webview does not store the value.
5. Credentials are scoped to a workspace profile. Different workspaces can use different providers.
6. The ATLAS runtime Python service retrieves credentials by requesting them from the Rust sidecar on each use, not by caching them in Python process memory for longer than a single request.

---

## Audit-Event Requirements for Cockpit Operations

Every cockpit-initiated operation that changes state or accesses external resources must emit an AuditEvent. Minimum requirements:

| Operation | AuditEvent kind | Required payload fields |
|-----------|----------------|------------------------|
| Terminal command executed | `tool_call` | session_id, run_id, command, cwd, workspace |
| File attached to mission/run | `artifact_attached` | mission_id, run_id, file_path, sha256, source_trust |
| Approval granted | `approval_granted` | approval_id, mission_id, run_id, capability_tier, operator, timestamp |
| Approval denied | `approval_denied` | approval_id, mission_id, run_id, capability_tier, operator, reason |
| Credential accessed | `credential_access` | key_type, workspace_id, purpose (never log key value) |
| Policy check performed | `policy_check` | rule_id, outcome (permit/deny), operation, workspace_id |
| External HTTP request | `http_request` | url, method, status_code, run_id (via ATLAS AI proxy) |

---

## Minimum Phase 8 Cockpit Surfaces

Phase 8 must ship these six surfaces. No more in v1.0.

### Surface 1 — Mission List/Detail

- List all missions with: ID, title, status badge, created timestamp, last-updated timestamp.
- Mission detail: full metadata, linked runs, policy tags, assigned workspace.
- Create mission form: title, intent/description, workspace selection.
- Cancel mission action: confirmation prompt → API call → AuditEvent.

### Surface 2 — Run Timeline / Audit Stream

- List runs for a mission with: run ID, status, start/finish timestamps.
- Run detail: real-time SSE audit event stream while active. Paginated history when complete.
- Each AuditEvent rendered as a typed entry: kind icon, timestamp, payload summary.
- Filter by event kind. Export as JSONL.
- Run cancel: confirmation prompt → API call → AuditEvent.

### Surface 3 — Terminal Pane Bound to a Run

- Open a terminal pane associated with a Run ID.
- PTY session managed by Rust backend. Shell selected from workspace policy.
- Each command boundary captured via shell markers → emits `tool_call` AuditEvent with run_id.
- Scrollback limited to N lines; full history available in audit log.
- Session tied to run lifecycle: when run completes or is cancelled, terminal may be closed or preserved as read-only.

### Surface 4 — Approval Prompt Surface

- ApprovalRequests arrive via SSE stream.
- Displayed as a native-style popup (not a browser modal): operation summary, capability tier, affected resources, policy rule, diff/preview if available.
- Operator actions: Grant, Deny, Escalate (defer for review).
- Response sent to `POST /approvals/{id}/grant` or `/deny`.
- Both request and response emit AuditEvents.
- Timeout: unanswered approvals expire per policy; expiry emits `approval_expired` AuditEvent.

### Surface 5 — File/Artifact Context Panel

- Browse workspace files. Select files to attach to a mission or run.
- Attached files become Source records with provenance: path, sha256, attachment timestamp, run_id.
- External files (dragged in from outside workspace) are flagged `untrusted: true`.
- Artifact list for a run: all outputs (files, diffs, logs) captured during execution.
- Download/open artifact from cockpit.

### Surface 6 — Provider/Model Settings Surface

- List configured providers: name, type (cloud/local), key status (present/absent).
- Add/update provider: enter API key → sent to Rust backend → written to OS keychain.
- Select default model per tier: mission-plan model, task-execution model, wiki-lint model.
- Workspace configuration: which shell, which filesystem boundary, which providers are permitted.
- All settings changes emit AuditEvents of kind `config_change`.

---

## Windows-First Validation Requirements

Davi's primary host is Windows 11. Phase 8 must be validated on Windows first.

1. Tauri binary builds and runs on Windows 11 (x64).
2. ConPTY PTY sessions work: shell spawns, resizes, output streams correctly.
3. WSL2 detection: if the workspace path is inside WSL2, shell session is created inside WSL2 via `wsl.exe` + ConPTY.
4. Windows Credential Manager: provider key write/read via keychain succeeds without elevation.
5. Windows Defender does not flag the binary (sign the binary or document the workaround for development builds).
6. Named Pipe or TCP loopback IPC functions correctly (no firewall block for localhost).
7. SvelteKit web cockpit renders correctly in WebView2 (bundled with Windows 11).
8. Performance targets on Windows: cockpit visible within 3 seconds of launch (cold start). Approval prompt visible within 200ms of event receipt.

Linux validation is secondary for v1.0. Mac is not a primary target.

---

## Why ATLAS Must Avoid Electron-Style Bloat

D-005 (locked) states: no Electron. The technical reasons:

1. **Binary size**: Electron bundles Chromium (~150MB+). Tauri uses the OS WebView (~0MB added). ATLAS target is a small, auditable binary.
2. **Memory**: Electron runs a separate renderer process per window. Tauri shares the OS WebView process. Idle RAM difference: ~300MB (Electron) vs ~40MB (Tauri).
3. **Startup time**: Electron cold-starts Chromium. Tauri launches the OS WebView (already running on Windows 11 / macOS). ATLAS target: ≤ 500ms to tray icon.
4. **OS integration**: Electron's Chromium sandbox conflicts with PTY process management, keychain access, and system API calls. Tauri's Rust backend has direct OS access.
5. **Audit surface**: Electron's multi-process architecture makes it harder to audit what the app is actually doing. Tauri's declared capability model makes the attack surface explicit.
6. **Philosophy**: ATLAS is designed for permanence and operational reliability. Electron's heavy dependency graph is the opposite of permanence.

---

## Why ATLAS Must Avoid Copying Odysseus' Broad Workspace Sprawl

Odysseus demonstrates workspace ambition but also demonstrates the failure mode ATLAS must avoid:

1. **Premature surface sprawl**: shipping many surfaces before any of them are operationally reliable is a reliability trap. ATLAS v1.0 ships exactly six cockpit surfaces, all well-tested.
2. **Feature creep masking core instability**: a workspace with many integrations can appear productive while the core audit/state machine is unreliable. ATLAS validates the audit trail and policy engine before expanding the UI.
3. **Context bloat**: a workspace that injects many sources into agent context degrades quality and increases cost. ATLAS wiki lint (Phase 6) and source ranking prevent this.
4. **Scope confusion**: mixing a mission-control cockpit with a generic AI assistant muddies the product boundary. ATLAS is an operator tool for mission-oriented work, not a general AI assistant shell.

The correct lesson from Odysseus is product ambition and security discipline. The anti-lesson is the sprawl.

---

## Phase 8 Pre-Work Requirements

Before Phase 8 implementation begins, the following must be complete:

1. This document (`NATIVE_COCKPIT_STRATEGY.md`) is reviewed and not overridden.
2. Phase 7 API is implemented and tested (REST + SSE streaming endpoints).
3. `ODYSSEUS_AUDIT.md` is source-inspected and complete — **done** (SHA `8449baea80db7763e713685ec98760cd8d398802`, MIT license confirmed, Phase 4.5).
4. A formal cockpit threat model document (`docs/security/COCKPIT_THREAT_MODEL.md`) is written using Odysseus' `THREAT_MODEL.md` format as a template (capability table + enforcement location per row).
5. Tauri 2 environment confirmed buildable on developer's Windows 11 machine.
6. `portable-pty` ConPTY tested in a minimal Rust prototype on Windows 11.

---

## Non-Negotiables

- Do not start a Phase 8 build without a complete Phase 7 API.
- Do not add CRM, Pulse, or channels surfaces in Phase 8.
- Do not add STT/TTS/voice in Phase 8 (D-009 locked).
- Do not use Electron (D-005 locked).
- Do not expose credentials to the webview.
- Do not skip the formal cockpit threat model before granting broad desktop permissions.
- Every cockpit operation that changes state must emit an AuditEvent.
