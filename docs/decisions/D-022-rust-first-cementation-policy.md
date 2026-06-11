# D-022 — Rust-First Cementation Policy (resolves D-013's open timing)

**Date:** 2026-06-10
**Status:** Accepted
**Refines:** D-013 (Prototype in Python, Cement in Rust — locked direction, open timing)
**Supersedes:** ROADMAP Phase 7 FastAPI/uvicorn success criteria (contradicted D-013's dependency budget, which already banned web frameworks)

---

## Context

Operator mandate (2026-06-10): ATLAS must be lightweight and robust — minimal disk and RAM without losing functionality. Python is not acceptable as the long-term agent framework; Rust (Zig for narrow leaf components per D-013's "watch, don't bet") is the product core. Python remains usable only in minor, well-bounded cases.

D-013 already locked this direction and the migration prerequisites (frozen Pydantic models, JSON-stable wire format, no framework lock-in). What it left open was timing. The anti-bloat ATLAS runtime policy adds the governing migration rule: **never rewrite while behavior is unstable; stabilize contracts, then port stable modules incrementally.**

## Decision

### 1. Language boundary (permanent)

**Rust (product core, default for ALL new components):** CLI, API gateway, daemon/supervisor, policy engine, executor, state engine, parsers/writers, native shell (D-005/D-016), semantic retrieval (turbovec).

**Python (confined, by exception only):**
- The vendored Hermes foundation surface — its plugin ABI is Python; it remains the v1.x agent loop until L5 below.
- LLM/provider adapters (SDKs are Python-first; I/O-bound — language overhead is noise vs. API latency).
- Throwaway scripts, research workflows, smoke tests, prototypes (never shipped in the product binary).

No new Python service code beyond what exists today, except inside the exception buckets.

### 2. Cementation starts now: Phase 7 gateway is Rust

The Phase 7 API Gateway is a Rust binary (`axum` + `tokio` + `rusqlite` + `serde`), the first crate in the `native/atlas-core-rs` workspace (D-013 module map, D-011 layout):

- **Reads** (missions, runs, audit events, wiki pages, FTS search): direct SQLite access. D-003 chose WAL specifically for concurrent readers; read models are generated from the D-012 JSON Schema emission.
- **Writes** (create mission, start/cancel run): dispatched through the `atlas` CLI contract — the CLI is the stable language-agnostic command boundary. No business logic is duplicated in Rust until the owning service ports natively (L2 below); this prevents drift.
- **SSE stream** (`/runs/{id}/events/stream`): poll `audit_events` by rowid cursor (local single-operator; polling interval ≤ 500 ms is imperceptible and allocation-free).

This replaces the FastAPI plan everywhere it appears. FastAPI/uvicorn would have added a banned framework to a component that is pure infrastructure — exactly the "stack over stack" failure mode, and a disposable artifact by its own design.

### 3. Cementation ladder

| Step | Component → Rust | Trigger |
|---|---|---|
| L0 (now) | Phase 7 gateway (`atlas-gateway`); `atlasd` sidecar supervisor (`atlas up`) | Immediate — new, standalone |
| L1 | Policy engine + audit event writer (`atlas-policy`, `atlas-state`) | v1.0 shipped and dogfooded |
| L2 | Mission/run state engine + `atlas` CLI binary (`atlas-cli`, `atlas-runtime`) | L1 green; CLI contract frozen |
| L3 | Wiki/memory runtime (rusqlite FTS5 + sqlite-vec; turbovec) | L2 green |
| L4 | Gateway absorbs in-process calls (CLI dispatch removed) | L1–L3 native |
| L5 (v2.x) | Agent loop/harness core — the evolved Hermes foundation is strangled: Rust core owns execution, tool dispatch, sessions; Python shrinks to the provider-adapter layer | Contracts proven by months of operation |

Each step ports a module only after its behavior contract is stable (anti-bloat migration rule). D-018 is reinterpreted accordingly: Hermes is the **behavioral reference and v1.x runtime**, not the permanent core.

### 4. Budgets (merge gates for all native components)

- `atlas` CLI (Rust): startup < 100 ms, < 50 MB RAM.
- Gateway/daemon: < 80 MB idle, single static binary < 20 MB, no network calls unless requested.
- Native cockpit shell: Tauri 2 (no embedded Chromium — D-005), interactive frames < 16 ms.
- Dependency gate: every new crate justified; `cargo tree` reviewed; no ORM, no message bus, no plugin framework without measured need.

### 5. Existing Python (status, not debt amnesty)

`atlas-core`, `agent-runtime`, `wiki-runtime` remain the prototype rail that stabilizes the contracts L1–L3 will port. They already comply with D-013 migration prerequisites (frozen models, JSON-stable dumps, no frameworks). They are feature-frozen for architecture: bug fixes and contract polish only; new capability lands per the ladder.

## Consequences

- ROADMAP Phase 7 success criteria rewritten for the Rust gateway.
- `native/atlas-core-rs/` workspace created at Phase 7 start; Rust toolchain becomes a build prerequisite.
- Phase 7 is more work than the FastAPI version (~2x) but is not disposable — it is the first permanent native component, and the 30-day plan absorbs it (simple CRUD reads + 2 CLI-dispatched writes + SSE poll).
- Smoke/benchmark scripts in `scripts/` stay Python (exception bucket 3).
