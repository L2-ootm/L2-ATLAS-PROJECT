# ULTRARESEARCH — Full Codebase Analysis

**Project:** L2 ATLAS PROJECT  
**Date:** 2026-07-11  
**Mode:** ultraresearch (5 parallel subagents, full codebase scan)  
**Scope:** Architecture, tech stack, vendor reuse, all calls/routes, blockers, future possibilities

---

## Executive Summary

L2 ATLAS is an **AI operator cockpit** built on a vendored Hermes Agent foundation (NousResearch, MIT), with MIT-licensed presentation mechanics ported from MiMo-Code (Xiaomi). The system is 90% through its v1.1 milestone (48/48 plans, Phase 10.8 remaining). It consists of 5+ services across 4 languages (Python, Rust, Go, TypeScript), connected by a Rust REST gateway on localhost:8484. The main risk is 38 unpushed commits with zero CI validation. v2.0 is a placeholder with zero planning artifacts.

---

## 1. Architecture Overview

### Layer Map

| Layer | Location | Role | Language |
|-------|----------|------|----------|
| **Foundation** | `foundation/atlas-hermes/` | Vendored Hermes Agent — agent loop, tool system, messaging adapters | Python |
| **Schemas** | `packages/atlas-core/` | Pydantic v2 frozen domain models (Mission, Run, AuditEvent, etc.) | Python |
| **Runtime** | `services/agent-runtime/` | 55 Python modules: agent adapters, context assembly, goal hierarchy, mission lifecycle, audit, policy, config | Python |
| **Gateway** | `native/atlas-core-rs/` | REST gateway (axum + rusqlite). Reads SQLite directly; writes dispatch to Python CLI | Rust |
| **Cockpit** | `services/web-ui-react/` | React 19 + Tailwind v4 + Vite 8. Optional Tauri shell | TypeScript |
| **Go TUI** | `services/atlas-tui/` | Go/BubbleTea thin client — HTTP + SSE to gateway | Go |
| **atlas-terminal** | `services/atlas-terminal/` | Bun/Solid donor-TUI over ATLAS gateway via fetch-adapter seam | TypeScript |
| **Sidecars** | `services/discord-bot/`, `services/cashflow/`, `services/wiki-runtime/` | Discord bot, financial tracking, wiki ingestion | Python/Node |

### How Pieces Connect

```
                    HTTP/REST + SSE
  Cockpit (React)  ─────────────────>  Rust Gateway (:8484)  <────── HTTP/REST + SSE  Go TUI
                                        |          |
                                        |  CLI dispatch (subprocess)
                                        |          |
                                        v          v
                                   Python Runtime (atlas CLI)
                                        |
                                        v
                                   Foundation (Hermes AIAgent)
                                        |
                                        v
                                   LLM Provider (OpenAI, Claude, etc.)
```

atlas-terminal sits parallel to the Go TUI, using the same gateway contract through its fetch-adapter translation layer.

**Key architectural rule (D-022):** The Rust gateway contains zero business logic for writes. Every POST dispatches to the Python CLI via subprocess. The gateway only reads SQLite directly for GET endpoints.

### Data Flow: Mission → Execution → Audit

1. **Create Mission** — Operator creates via CLI/cockpit/terminal → `mission_service.create_mission()` → Pydantic validation → SQLite INSERT → audit event `mission_created`
2. **Context Assembly** — `context_service.assemble_context()` builds secret-redacted markdown brief from Focus, Goals, Wiki, Brain graph, recent runs
3. **Run Execution** — `run_executor.execute_run()` dispatches to `NativeAtlasAgent` (Hermes) or `ClaudeCodeAgent` → emits `AuditEvent`s throughout
4. **Completion** — Run transitions to terminal state → Brain graph upserted → Observation written
5. **Review** — Cockpit/Go TUI/atlas-terminal render the audit trail

---

## 2. Tech Stack

### Languages & Frameworks

| Language | Where | Purpose |
|----------|-------|---------|
| Python 3.11+ | agent-runtime, atlas-core, foundation | Orchestration, schemas, Hermes foundation |
| Rust 2021 | native/atlas-core-rs | Gateway (axum 0.8, rusqlite 0.32, tokio) |
| Go 1.26 | services/atlas-tui | Terminal workbench (BubbleTea, Lipgloss) |
| TypeScript | web-ui-react, atlas-terminal, cashflow | Cockpit UI, terminal adapter, cashflow |
| JavaScript | packages/atlas-cli | npm installer package |
| SQL | infra/migrations | 19 SQLite schema migrations |

### Key Dependencies

**Python:** atlas-core (Pydantic v2), typer, pyyaml, openai 2.24.0, pydantic 2.13.4, httpx 0.28.1, rich 14.3.3, tenacity 9.1.4

**Rust:** axum 0.8, tokio 1, rusqlite 0.32 (bundled), serde + serde_json, futures-util. Release: LTO thin, strip, codegen-units 1 (<20MB binary)

**Go:** charmbracelet/bubbletea 1.3.10, charmbracelet/lipgloss 1.1.0, charmbracelet/bubbles 0.21.0

**TypeScript/Cockpit:** react 19.2, react-router-dom 7.18, vite 8.0, tailwindcss 4.3, three 0.184, 3d-force-graph 1.80

**TypeScript/atlas-terminal:** solid-js 1.9.9, @opentui/core 0.1.99, effect 4.0.0-beta.48, zod 4.1.8

**Database:** SQLite/WAL/FTS5 — single-file at `~/.atlas/atlas.db`, 19 migrations, ~22 tables

---

## 3. Vendor/Donor Code Reuse

### Hermes Foundation (`foundation/atlas-hermes/`)

- **Source:** NousResearch/hermes-agent v0.14.0, MIT licensed
- **Scope:** Full agent runtime — run_agent.py, CLI, model_tools, gateway, plugins, skills, TUI, web, tools, tests
- **Divergences:** 7 controlled modifications (ATLAS skin, plugin shim, CLI aliases, safety quarantines)
- **Rule (D-001):** Not modified directly; evolved through extension points only
- **~12,900 hermes references** exist in the foundation tree (deferred de-brand)

### MiMo-Code Donor (TUI Presentation)

Two parallel surfaces:

1. **atlas-terminal (TypeScript/Bun):** Wholesale port of MiMo-Code's SolidJS/OpenTUI/Effect presentation layer. 137 vendored vendor files in `src/vendor/`. Fetch-adapter seam translates donor HTTP to ATLAS gateway contracts.

2. **atlas-tui (Go/BubbleTea):** Pattern-ported native reimplementation. 24 Go files. No donor runtime imported — pure thin client of ATLAS Rust gateway. Presentation mechanics (50ms cadence, starfield, autocomplete geometry) ported to Go.

### Other Vendored Code

- L2-BOT (Discord sidecar, MIT)
- pixel-art-studio (Synero palettes, MIT)
- Ported utilities from anomalyco/opencode inside Hermes foundation
- TEN VAD (Agora WASM, Apache 2.0)

### Rebrand Status

**Mostly complete.** Remaining donor references fall into two categories:

1. **Structural SDK identifiers** (must remain): `@opencode/Global`, `"opencode"` provider IDs, `mimo-v2.5` model name, Effect service keys
2. **Residual branding** (~30 theme files with `opencode.ai` in `$schema` refs, port-tracking comments in foundation code)

### License Compliance

All donor notices properly retained. THIRD_PARTY_LICENSES.md is comprehensive. No copyleft (GPL/LGPL/AGPL/MPL) in any direct dependency tree.

---

## 4. All Routes, Calls, and Interfaces

### Gateway Routes (~80 distinct routes)

| Category | Key Endpoints | Count |
|----------|---------------|-------|
| Health | `GET /health` | 1 |
| Missions | CRUD + run/retry/cancel/archive | 8 |
| Runs | List, detail, events, SSE stream | 4 |
| Wiki | CRUD + FTS5 search | 5 |
| Config/Auth/Provider | View, patch, import, status, modes | 7 |
| Models | List, refresh | 2 |
| FreeLLMAPI | Status, start, stop | 3 |
| Discord | Status, start/stop, guilds, proposals, approvals | 8 |
| Tools | Manifests, calls, approvals | 3 |
| Surface Sessions | CRUD, events, approvals, heartbeat, suspend/resume/cancel/close | 12 |
| Knowledge Graph | View | 1 |
| Projects | CRUD + register | 4 |
| Focus/Goals/Tasks | CRUD for command center | 10 |
| Operations | List, run | 2 |
| Modules | List, activate, deactivate | 3 |
| Cashflow | Status, start/stop, summary, full launcher | 5 |
| Messaging | Channels, toggle, gateway status/start/stop | 5 |
| Host | Folder picker (Windows) | 1 |

### CLI Commands

| Group | Commands | Description |
|-------|----------|-------------|
| `atlas` (bare) | — | Launch Go TUI workbench |
| `atlas mission` | create, run, retry, cancel, archive, purge-archived, status | Mission lifecycle |
| `atlas up/down` | — | Start/stop all services |
| `atlas doctor` | — | Aggregate health check |
| `atlas config` | json, patch | Configuration management |
| `atlas auth` | json, add, codex-status, import-codex | Auth store |
| `atlas models` | — | Model registry |
| `atlas provider` | status, modes, test | Provider mesh |
| `atlas tools` | manifests, call, approvals | Tool management |
| `atlas surface` | — | Surface session management |
| `atlas focus/goal/task/observe` | create, list, tree, update, archive | Command center |
| `atlas graph` | build | Knowledge graph |
| `atlas wiki` | — | Wiki management |
| `atlas gateway` | start, status, stop | Gateway lifecycle |
| `atlas db` | init, status | Database migrations |
| `atlas freellmapi/discord/cashflow` | start, status, stop | Sidecar control |
| `atlas golden` | — | Golden workflow management |
| `atlas terminal` | status | atlas-terminal build status |

### External API Integrations

| Integration | Mechanism | Location |
|-------------|-----------|----------|
| FreeLLMAPI | Sidecar on :3001, OpenAI-compatible | `freellmapi_control.py` |
| OpenAI/Anthropic | Via Hermes foundation AIAgent | `agents/native.py` |
| Codex/ChatGPT OAuth | `codex_auth.py` delegates to Hermes | `~/.codex/auth.json` |
| Claude Code | claude-agent-sdk + local CLI | `agents/claude_code.py` |
| Discord | Vendored sidecar via loopback API | `discord_control.py` |
| Supabase | Optional Postgres for cashflow | `services/cashflow/` |

### SSE/Streaming

| Endpoint | Transport | Consumers |
|----------|-----------|-----------|
| `GET /v1/runs/{id}/stream` | SSE (500ms poll) | Go TUI, React cockpit |
| `GET /v1/surface-sessions/{id}/events` | HTTP polling | Go TUI, React cockpit |

### IPC Mechanisms

| Mechanism | Producer → Consumer | Protocol |
|-----------|---------------------|----------|
| Gateway HTTP | Surfaces → Gateway | REST + SSE |
| Gateway → Python CLI | Rust → Python subprocess | stdout/stderr capture |
| CLI stdin | Gateway → Python (secrets) | Piped stdin |
| Detached subprocess | Gateway → Python (runs) | Background process |
| FreeLLMAPI sidecar | Node.js → Native agent | HTTP :3001 |
| Discord sidecar | Node.js → Python CLI | HTTP loopback |

---

## 5. Current Blockers

### Critical (prevent v1.1 archive)

| # | Blocker | Severity | Status |
|---|---------|----------|--------|
| 1 | **Phase 10.8 not executed** (0/4 plans) — cross-surface conformance, representative battery, adversarial tests, operator UAT | HIGH | Blocked on push + UAT |
| 2 | **38 commits unpushed to origin** — CI never verified, no integration feedback | HIGH | Awaiting operator push |
| 3 | **atlas-terminal session-create toast** (F12) — root cause unknown, blocks retirement gate decision | HIGH | Needs real Windows Terminal TTY UAT |
| 4 | **TUI retirement gate not decided** — Go TUI vs atlas-terminal as default `atlas` | HIGH | Operator decision required |

### High-Priority Gaps

| # | Gap | Impact |
|---|-----|--------|
| 5 | No security scanning in CI (SAST, dependency audit) | Production risk |
| 6 | No production Docker infrastructure | Deployment blocked |
| 7 | No monitoring/observability | No production readiness |
| 8 | No performance benchmarking | No latency guarantees |
| 9 | v2.0 has zero planning artifacts | Roadmap fiction |
| 10 | FreeLLMAPI unpatched upstream security advisory | Distribution risk |

### Deferred Work

| # | Item | Reason |
|---|------|--------|
| 11 | F20: setTimeout workarounds in atlas-terminal | Vendored donor internals, no TUI render test coverage |
| 12 | Foundation de-brand (hermes→atlas) | ~12,900 references, test-gated, operator-directed |
| 13 | Mixed CLI --json convention | Real refactor scope (~9 modules + tests) |

### Known Failures

| # | Issue | Status |
|---|-------|--------|
| 14 | Live cockpit screenshots deferred to UAT | Awaiting full-stack boot |
| 15 | Determinism is mock-mode only | Design choice |
| 16 | Research Brief web_fetch variant not implemented | Offline-only |
| 17 | test_claude_code_missing_sdk raises without optional dep | Known, documented |

### TODO/FIXME (ATLAS-specific, actionable)

| # | Location | Issue |
|---|----------|-------|
| 18 | `atlas-terminal/src/tui/component/prompt/index.tsx:581` | Prompt interrupt should be its own command |
| 19 | `atlas-terminal/parsers-config.ts:153` | Tree-sitter HTML injections not working |
| 20 | `atlas-terminal/parsers-config.ts:277` | Replace unofficial tree-sitter-nix WASM |
| 21 | `atlas-terminal/src/sdk/gen/client/client.gen.ts:172` | SDK client error return type improvement |
| 22 | `atlas-terminal/src/vendor/opencode/util/effect-zod.ts:20` | Effect Schema input-order preservation |

### Windows-Specific

| # | Issue | Status |
|---|-------|--------|
| 23 | System tar breaks on C:\ paths | FIXED (src/tarball.js) |
| 24 | Windows TTY differs from POSIX | Blocked on ConPTY/node-pty |
| 25 | Gateway binary naming (atlas-gateway.exe) | Handled |
| 26 | Windows TUI input handling (win32.ts) | Implemented |
| 27 | workspace_service cross-drive test skip | Intentional |

---

## 6. Security Assessment

| Area | Score | Notes |
|------|-------|-------|
| **Security** | 9/10 | Loopback-only gateway, strict CORS, owner tokens, path traversal guards, no hardcoded creds, parameterized SQL (except fastmcp), comprehensive secret redaction |
| **Performance** | 6/10 | N+1 fixed, indexes added, but goal_tree unbounded scans, 42 sync imports in hot path, no HTTP caching |
| **Data Integrity** | 8/10 | Atomic DB writes, optimistic locking, Pydantic at boundaries. Secondary writes fail silently (observation, brain graph). No retention cleanup for brain_nodes/brain_edges |
| **Configuration** | 7/10 | Pydantic validation, corruption safety, revision locking. Config migration chain landed |
| **Dependencies** | 9/10 | Lean surface, no known CVEs, ogl removed |
| **API Contracts** | 7/10 | Gateway-cockpit consistent, SSE format consistent. Terminal nonce issue fixed |
| **State Management** | 8/10 | No shared mutable state, proper surface session lifecycle. graphCache no eviction |
| **Deployment** | 6/10 | Docker incomplete. PID reuse guarded. Daemon lacks SIGTERM handler |
| **Cross-Surface** | 7/10 | Provider/status/permissions consistent. Terminal lacks mission browser |
| **Dead Code** | 9/10 | Zero unused imports in agent-runtime. 77 TODOs (75 foundation, 2 actionable) |
| **Error Propagation** | 7/10 | Agent loop well handled. Orphan reaper landed. Cockpit reconnect improved |
| **Testing** | 5/10 | ~1,850+ test files (Hermes strong). Zero CI for ATLAS packages. No performance tests, no frontend security tests |

### Specific Security Concerns

1. **FreeLLMAPI cleartext API key** — `freellmapi status` returns sidecar api_key in cleartext (operator ratified, documented)
2. **FreeLLMAPI unpatched upstream advisory** — >30 days, no direct ATLAS risk as loopback-only
3. **No frontend security tests** — zero security-focused tests for React cockpit or atlas-terminal
4. **SSRF guards present but untested** — three-layer defense exists but no penetration test coverage
5. **f-string SQL in fastmcp template** — flagged, needs parameterized replacement

---

## 7. Future Possibilities & Missing Pieces

### v1.2 Provider Mesh & Runtime Interoperability (Draft)

7 phases (PM-01 through PM-07): Foundation Boundary Manifest, Bidirectional WebUI Gap Audit, Provider Mesh Contract, Role-Keyed Model Rulebook, Capability/Cost/Health Scoring, Provider Backends, Configuration Surfaces.

**Activation gate:** v1.1 must be archived. No timelines, no dev-day estimates. Architectural skeleton only.

### v1.3 Gated Self-Evolution (Draft)

One phase (EV-01): Gated Foundation Sync Pilot. Five promotion levels: Observe → Propose → Validate → Publish → Tracked auto-merge. Default autonomy ceiling: observe/propose. **Highest-risk idea in the portfolio.**

### v2.0 CRM, Pulse & Voice (Stubs)

| Phase | Scope | Status |
|-------|-------|--------|
| 11 | CRM via Twenty (sidecar) | Not started, D-010 still open |
| 12 | Basic Pulse Monitor | Not started |
| 13 | STT/TTS Voice Integration | Not started |
| 14 | Floating Overlay / Run-Status HUD | Not started |

**Zero planning, zero requirements, zero research artifacts exist for v2.0.**

### Missing Infrastructure

| Category | Status |
|----------|--------|
| **CI/CD** | Authored (atlas-ci.yml, 7 jobs) but never verified on a real push. Missing: clippy/fmt lint, ruff lint, ESLint, E2E job, security scanning, release automation |
| **Docker** | Basic dev-only compose. Missing: production Dockerfile, health checks, volume management, registry publishing, multi-arch builds |
| **Monitoring** | Essentially nonexistent. Only basic file logging. No APM, metrics, tracing, alerting |
| **Performance** | No benchmarking infrastructure. No p50/p95/p99 measurement. No latency tracking |
| **Security scanning** | No SAST, no dependency audit in CI, no secret scanning automation |

### Scalability Assessment

**Intentionally local-first.** Single-process architecture, SQLite WAL, single-writer, no horizontal scaling. These are design choices for a local operator cockpit, not bugs. Scaling becomes relevant only for multi-user or cloud deployment.

### Operator-Gated Items

| Item | Status |
|------|--------|
| Push 38 commits to origin | Blocked |
| Verify CI runs on first push | Blocked on push |
| Interactive atlas-terminal UAT (F12) | Needs real TTY Windows Terminal |
| Approve/reject real tool call from atlas-terminal | Blocked on session creation |
| Go TUI vs atlas-terminal default surface decision | Blocked on Phase 10.8 UAT |
| Phase 10.8 UAT execution | Operator must run scripted UAT |
| v1.0.5 public release actions | Repo public, tag, beta, launch message |
| CLA PERSONAL_ACCESS_TOKEN secret | Needs fine-grained PAT |

### Language Migration Status (D-022)

- **Done:** Gateway is Rust (Phase 7)
- **Not started:** CLI, policy, executor, mission parser, state still Python
- **Prerequisites met:** Frozen Pydantic v2, JSON-stable model_dump, no circular deps
- **Next module candidates:** CLI surface, policy engine, mission parser

---

## 8. Test Coverage Summary

| Package | Tests | Status |
|---------|-------|--------|
| agent-runtime | 766 | All passing (1 skipped) |
| atlas-core | 97 | All passing |
| atlas-cli | 20 (Windows) | All passing |
| atlas-terminal | 28 (bun test) | All passing |
| atlas-tui | 101 (go test) | All passing |
| atlas-gateway | 104 (cargo test) | All passing |
| cockpit (React) | 44 | All passing |
| E2E | 1 | Passing (requires gateway binary) |
| **Total** | **~1,161 ATLAS-specific** | All green |

Hermes foundation has ~1,850+ additional test files inherited upstream.

---

## 9. Decision Log (Open)

| ID | Decision | Status |
|----|----------|--------|
| D-010 | CRM/Pulse/Channels deep-dive research | OPEN |
| D-023 | Svelte → React migration | COMPLETE |
| Retirement gate | Go TUI vs atlas-terminal as default | PENDING (Phase 10.8) |

---

## 10. Key Findings

1. **v1.0 shipped and archived. v1.1 is 90% complete.** 48/48 plans done, Phase 10.8 (4 plans) remains. The gap is verification, UAT, and operator decisions — not code.

2. **38 unpushed commits are the biggest risk.** CI has never run. The E2E test has never been verified in a clean environment. A push would immediately surface integration issues.

3. **v2.0 is a placeholder.** Four bullet points in a roadmap with zero planning artifacts. CRM integration has a D-010 decision still marked "open."

4. **License compliance is thorough.** Every donor has proper attribution at every level. No copyleft contamination.

5. **Security posture is strong for a local-first tool** (9/10) but lacks production hardening (no security scanning in CI, no frontend security tests).

6. **The D-022 Python→Rust migration has barely started.** Only the gateway is Rust. The entire orchestration layer remains Python. Prerequisites are met but no migration work has begun.

7. **The skill ecosystem is Hermes-inherited.** No ATLAS-specific operator skills beyond the ultra development framework.

8. **Docker and monitoring are development-grade**, not production-grade. No structured observability, no health checks, no resource limits.

---

*Generated by ULTRARESEARCH mode — 5 parallel explore subagents, synthesized 2026-07-11*
