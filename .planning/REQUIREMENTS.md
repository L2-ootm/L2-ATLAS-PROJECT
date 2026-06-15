# Requirements: L2 ATLAS — v1.1 (ATLAS Agent Harness & Native Operator Shell)

**Defined:** 2026-06-15
**Core Value:** A serious, auditable AI operating system for technical founders, AI operators, and small high-context teams.
**Milestone goal:** Make ATLAS credible as a local AI operator runtime — owned TUI, owned auth, real provider/model discovery, agentic chat over the vendored Hermes foundation, and a Tauri 2 native shell hosting cockpit + PTY.

Scope derived from `.planning/research/` (STACK/FEATURES/ARCHITECTURE/PITFALLS/SUMMARY) and the `.planning/prep/` set. Locked operator decisions: Codex **read-only** detection only; OpenAI/Codex-compatible lane **first** then health-aware fallback; **file-store-first** auth (keychain deferred).

## v1 Requirements

Requirements for the v1.1 release. Each maps to exactly one phase (10.0–10.6).

### TUI — Terminal User Interface

- [ ] **TUI-01**: Running `atlas` (and `atlas tui`) opens an ATLAS-branded TUI with a header/status bar showing active model and auth state.
- [ ] **TUI-02**: TUI renders a scrollable transcript of user and assistant turns.
- [ ] **TUI-03**: TUI streams assistant responses incrementally with a visible activity indicator during model calls.
- [ ] **TUI-04**: TUI provides a multi-line composer with submit and cancel.
- [ ] **TUI-05**: TUI shows tool-call activity inline in the transcript during agent execution.
- [ ] **TUI-06**: TUI surfaces an auth/model warning before the first prompt when auth or model is unavailable.
- [ ] **TUI-07**: TUI exposes `/help` and an ATLAS slash-command surface.
- [ ] **TUI-08**: TUI exits cleanly on Ctrl-C without corrupting session state; the session persists and can be resumed.
- [ ] **TUI-09**: TUI presents a blocking approval prompt before any dangerous tool call executes.

### CLI — Command Surface

- [ ] **CLI-01**: `atlas --help` shows an ATLAS-branded command tree (chat/auth/models/providers/doctor/tui) and runs without `python -m`.
- [ ] **CLI-02**: `atlas chat -q "<prompt>"` returns a model response or precise auth remediation.
- [ ] **CLI-03**: `atlas chat` starts an interactive session (or routes to the TUI) and exits cleanly.
- [ ] **CLI-04**: `atlas doctor` reports environment readiness (Python/Rust/Node, DB, gateway, auth, models, foundation).
- [ ] **CLI-05**: All CLI commands return clear exit codes (0 success, non-zero failure).
- [ ] **CLI-06**: No CLI command prints secret values (enforced by redaction tests).

### AUTH — ATLAS-Owned Auth Store

- [ ] **AUTH-01**: ATLAS stores credentials in an ATLAS-owned store at `~/.atlas/auth.json` (never in `~/.codex` or `~/.hermes`).
- [ ] **AUTH-02**: Auth writes are atomic (temp + replace) and guarded by a cross-process lock; concurrent writers never corrupt or silently lose data.
- [ ] **AUTH-03**: `atlas auth add <provider>` stores an API key for at least one real provider.
- [ ] **AUTH-04**: `atlas auth list` / `atlas auth status` shows configured providers and auth state without exposing credential values.
- [ ] **AUTH-05**: `atlas auth remove <provider>` revokes a stored credential.
- [ ] **AUTH-06**: `atlas auth doctor` checks file permissions, parse validity, and provider reachability with actionable output.
- [ ] **AUTH-07**: ATLAS detects a local Codex installation/auth presence read-only and never mutates `~/.codex` (test-proven byte-identity).
- [ ] **AUTH-08**: Auth status output, logs, and audit records never contain raw secret values (redaction-tested).

### PROVIDERS — Provider Registry

- [ ] **PROV-01**: Providers are modeled separately from credentials, models, and runtime/api-mode.
- [ ] **PROV-02**: `atlas providers list` / `status` shows each provider's source, health, and auth state honestly (offline shown as offline).
- [ ] **PROV-03**: `atlas providers doctor` explains each unhealthy provider with an actionable remediation command.
- [ ] **PROV-04**: Codex appears as an advisory read-only provider entry (source = external), never as a credential source.

### MODELS — Model Registry

- [ ] **MOD-01**: `atlas models discover` merges sources (seeded + auth-store providers + local sidecars + read-only external) into the registry.
- [ ] **MOD-02**: `atlas models list --all` shows model_id, provider, source, status, auth_status, and last_seen.
- [ ] **MOD-03**: Discovery is idempotent — repeated runs do not duplicate rows or overwrite `first_seen` (composite key model_id+provider+source).
- [ ] **MOD-04**: Deactivation is source-scoped — one provider going offline never deactivates models from other sources.
- [ ] **MOD-05**: `status` and `auth_status` are distinct; a model is never shown available when its auth is missing or its sidecar is down.
- [ ] **MOD-06**: The cockpit Models page reflects the real registry (source/status/auth), not only seeded rows.

### AGENT — Runtime Adapter & Chat Loop

- [ ] **AGNT-01**: An ATLAS runtime adapter wraps Hermes AIAgent in `services/agent-runtime/`; `foundation/` changes are extension-points only (DIVERGENCE_LOG-tracked), not a Hermes rewrite.
- [ ] **AGNT-02**: Live chat tries the OpenAI/Codex-compatible lane first, then automatically falls back through other configured providers ordered by liveness (health-aware cascade, not fixed priority).
- [ ] **AGNT-03**: Auth failures (401/403) halt with remediation and never silently cascade; the provider actually used is surfaced on the response.
- [ ] **AGNT-04**: Every model call emits ATLAS audit metadata (model_call_start/end with provider, model, run_id, token usage) on the ATLAS event bus.
- [ ] **AGNT-05**: Dangerous tool calls require explicit approval (deny-by-default in non-interactive `-q` mode); Hermes approval gates are preserved through the adapter.
- [ ] **AGNT-06**: Chat transcripts pass a redaction filter before persistence (no secrets in audit JSONL or wiki).

### NATIVE — Tauri 2 Operator Shell

- [ ] **NAT-01**: A Tauri 2 shell (no Electron) launches and embeds the SvelteKit cockpit from a local bundle (no remote origin in production).
- [ ] **NAT-02**: The shell hosts a PTY terminal pane that runs `atlas tui` (not a bare bash/cmd shell).
- [ ] **NAT-03**: IPC is capability-scoped via an explicit allowlist; the PTY accepts keystrokes, not command strings (no arbitrary-exec bridge).
- [ ] **NAT-04**: The shell surfaces auth/model readiness and routes remediation to the CLI/TUI.
- [ ] **NAT-05**: The shell remains local-first — no external network calls except explicit model/provider integrations.

### SECURITY

- [ ] **SEC-01**: A redaction test suite scans CLI output, logs, and audit JSONL for known secret patterns (`sk-`, `Bearer `, `eyJ`) and passes.
- [ ] **SEC-02**: A test proves `~/.codex` is byte-identical (mtime + hash) after all ATLAS auth and discovery commands.
- [ ] **SEC-03**: `~/.atlas/auth.json` is created with current-user-only permissions (icacls on Windows).
- [ ] **SEC-04**: A native-IPC threat-model document enumerates every IPC command, its parameters, caller, and privilege.
- [ ] **SEC-05**: Any shipped OAuth callback flow uses PKCE + state validation + an ephemeral loopback port that closes after one callback; otherwise OAuth is explicitly deferred with a documented decision.

### AUDIT

- [ ] **AUD-01**: Provider fallback emits a structured audit event (from / to / reason).
- [ ] **AUD-02**: Free (non-mission) chat sessions still emit audit events; mission-bound chats update mission/run state.

### UX

- [ ] **UX-01**: ATLAS TUI and native shell present ATLAS branding (banner, skin, status bar) with no imported-source (Hermes/Codex) branding leaks.
- [ ] **UX-02**: Error and remediation copy is actionable and standardized — every failure states the next command to run.

### DOCS

- [ ] **DOC-01**: Operator runbooks exist for auth, TUI, models, and the native shell (`docs/operations/ATLAS_AUTH.md`, `ATLAS_TUI.md`, `ATLAS_MODELS.md`, `NATIVE_SHELL.md`).
- [ ] **DOC-02**: A v1.1 manual UAT guide exists covering TUI, one-shot chat, auth, model discovery, cockpit, and native shell.

## Future Requirements

Deferred to v1.2+. Tracked, not in this roadmap.

### Routing
- **ROUTE-01**: `atlas route show` displays task-class → provider/model policy.
- **ROUTE-02**: `atlas route set <task-class> <provider>/<model>` configures routing with a fallback policy.

### TUI (advanced)
- **TUIX-01**: Mission context panel in TUI (`/mission bind`, run/audit references).
- **TUIX-02**: Token/context-window progress bar in the status bar.
- **TUIX-03**: Subagent/task activity accordion.
- **TUIX-04**: Full session branching/resume (`/resume`) beyond basic persistence.

### Auth (advanced)
- **AUTHX-01**: OS keychain integration (Windows DPAPI/Credential Manager, macOS Keychain, Linux Secret Service).
- **AUTHX-02**: OAuth device-code flow for providers that support it (Anthropic, Google).
- **AUTHX-03**: Credential pools (multiple keys per provider for rotation/failover).

### Native (advanced)
- **NATX-01**: Native approval-prompt overlay for dangerous tool calls.
- **NATX-02**: Tray icon and global hotkey.

### Models (advanced)
- **MODX-01**: Model latency/quota benchmarking and display.

## Out of Scope

Explicitly excluded for v1.1. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Rust TUI rewrite (ratatui) | Duplicates the working, tested Hermes Ink TUI; delays all other workstreams. Reassess post-v1.1 only if Ink limits emerge. |
| Importing or mutating Codex credentials | Locked decision: read-only detection only; `~/.codex` never written. |
| Reusing OpenAI/Codex OAuth protocol for ATLAS auth | Not licensed/documented for third-party reuse; ATLAS uses its own API-key store. Revisit only if a spike proves feasibility. |
| Electron (any fallback) | D-005 hard no. If Tauri PTY blocks, defer native shell rather than switch. |
| OS keychain in v1.1 | File-store-first decision; platform-specific native code deferred to v1.2+. |
| Auto-probing paid remote providers on startup | Risks billing/quota and slow startup; discovery is opt-in/cache-first. |
| Inline secret display for debugging | Secrets in TUI/logs/screenshots are an unacceptable risk; redacted/opt-in hints only. |
| Rewriting the Hermes agent loop | High risk, no operator benefit; thin adapter only. |
| CRM/Twenty, Pulse, WhatsApp, voice/overlay | Deferred to v2.0 (D-007, D-009, D-020). No CRM/Pulse REQ-IDs in v1.1. |
| Multi-user / SaaS auth, mobile app, public installer | Out of v1.1 scope; single-operator local-first. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | 10.1 | Pending |
| AUTH-02 | 10.1 | Pending |
| AUTH-03 | 10.1 | Pending |
| AUTH-04 | 10.1 | Pending |
| AUTH-05 | 10.1 | Pending |
| AUTH-06 | 10.1 | Pending |
| AUTH-07 | 10.1 | Pending |
| AUTH-08 | 10.1 | Pending |
| CLI-06 | 10.1 | Pending |
| SEC-01 | 10.1 | Pending |
| SEC-02 | 10.1 | Pending |
| SEC-03 | 10.1 | Pending |
| SEC-05 | 10.1 | Pending |
| CLI-01 | 10.2 | Pending |
| CLI-02 | 10.2 | Pending |
| CLI-03 | 10.2 | Pending |
| AGNT-01 | 10.2 | Pending |
| AGNT-02 | 10.2 | Pending |
| AGNT-03 | 10.2 | Pending |
| AGNT-04 | 10.2 | Pending |
| AGNT-05 | 10.2 | Pending |
| AGNT-06 | 10.2 | Pending |
| AUD-01 | 10.2 | Pending |
| AUD-02 | 10.2 | Pending |
| CLI-04 | 10.3 | Pending |
| CLI-05 | 10.3 | Pending |
| PROV-01 | 10.3 | Pending |
| PROV-02 | 10.3 | Pending |
| PROV-03 | 10.3 | Pending |
| PROV-04 | 10.3 | Pending |
| MOD-01 | 10.3 | Pending |
| MOD-02 | 10.3 | Pending |
| MOD-03 | 10.3 | Pending |
| MOD-04 | 10.3 | Pending |
| MOD-05 | 10.3 | Pending |
| MOD-06 | 10.3 | Pending |
| UX-02 | 10.3 | Pending |
| TUI-01 | 10.4 | Pending |
| TUI-02 | 10.4 | Pending |
| TUI-03 | 10.4 | Pending |
| TUI-04 | 10.4 | Pending |
| TUI-05 | 10.4 | Pending |
| TUI-06 | 10.4 | Pending |
| TUI-07 | 10.4 | Pending |
| TUI-08 | 10.4 | Pending |
| TUI-09 | 10.4 | Pending |
| UX-01 | 10.4 | Pending |
| NAT-01 | 10.5 | Pending |
| NAT-02 | 10.5 | Pending |
| NAT-03 | 10.5 | Pending |
| NAT-04 | 10.5 | Pending |
| NAT-05 | 10.5 | Pending |
| SEC-04 | 10.5 | Pending |
| DOC-01 | 10.6 | Pending |
| DOC-02 | 10.6 | Pending |

**Coverage:**
- v1 requirements: 55 total
- Mapped to phases: 55
- Unmapped: 0 ✓
- Phase 10.0 is a design/enabling phase and owns no v1 REQ-IDs (precedent: v1.0 Phase 7).

---
*Requirements defined: 2026-06-15*
*Last updated: 2026-06-15 after milestone v1.1 scoping (research-informed, inline roadmap)*
