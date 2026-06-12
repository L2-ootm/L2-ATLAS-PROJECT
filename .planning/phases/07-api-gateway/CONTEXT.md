# Phase 7: API Gateway (Rust — D-022)

**Phase number:** 7
**Name:** API Gateway
**Status:** Pending (unblocked 2026-06-11 — toolchain green, atlas-gateway crate compiles and serves /health)

> Supersession note (2026-06-11): this context originally specified a FastAPI
> gateway at `apps/api/`. D-022 (Rust-first cementation) supersedes that: the
> gateway is a Rust binary (`axum` + `rusqlite`) in
> `native/atlas-core-rs/crates/atlas-gateway/`. D-021 moves the SSE stream
> endpoint into Phase 7 (the cockpit consumes it in Phase 8). The canonical
> success criteria live in `.planning/ROADMAP.md` Phase 7; this file mirrors
> them.

---

## Goal

Expose all mission, run, audit, and wiki operations via a typed REST API
(+ SSE stream) so the cockpit and future integrations have a stable
interface — delivered as the first native component: a Rust binary in
`native/atlas-core-rs/`.

---

## Requirements Covered

This phase has no exclusively owned REQ-IDs. It is the API infrastructure
layer that makes Phase 8 (cockpit) possible. All domain REQ-IDs are owned by
their originating phases (RUNTIME by Phase 5, WIKI by Phase 6, AUDIT by
Phase 4, COCKPIT by Phase 8).

Phase 7 satisfies the API surface required by COCKPIT-01..06 (Phase 8).

---

## Success Criteria (mirror of ROADMAP Phase 7)

1. `atlas-gateway` binary builds in release mode and starts on a loopback
   port (default 127.0.0.1:8484, env `ATLAS_GATEWAY_PORT`).
2. `GET /health` reports service status + DB probe.
3. `POST /missions` creates a mission; `GET /missions` returns a paginated
   list.
4. `POST /missions/{id}/run` starts a run; `GET /runs/{id}` returns status.
5. `GET /runs/{id}/events` returns the ordered AuditEvent list.
6. `GET /runs/{id}/stream` serves SSE (rowid-cursor poll, ≤500ms latency).
7. `GET /wiki/pages` paginated list; `GET /wiki/search?q=` FTS5 results.
8. Reads go direct to SQLite (WAL concurrent readers, D-003); writes
   dispatch through the `atlas` CLI contract — no business logic duplicated
   in Rust.
9. JSON responses validate against JSON Schema exported from the Pydantic
   models (D-012) via contract tests.
10. Budgets hold (D-022): binary <20 MB, idle RSS <80 MB.

---

## Key Decisions Applicable

- **D-022** (accepted): Rust gateway — axum + tokio + rusqlite (bundled).
  No FastAPI. No new Python service code.
- **D-021** (accepted): SSE stream endpoint is Phase 7 scope; Phase 8
  consumes it.
- **D-012** (locked): Pydantic v2 is schema source of truth — Rust responses
  are contract-tested against exported JSON Schema, not hand-maintained.
- **D-011** (locked, amended): gateway lives in the Rust workspace
  (`native/atlas-core-rs/crates/atlas-gateway/`), not `apps/api/` (removed).
  Future promotion to top-level `crates/` per PRODUCTION_REPO_STRUCTURE.md.
- **D-003** (locked): SQLite is the datastore — reads direct (read-only
  connections), writes via CLI dispatch to preserve audit/policy boundaries.
- **D-007** (locked): no CRM endpoints here.

---

## Low-model stabilization backlog

A bounded cleanup plan for minor remaining risks is documented at `07-LOW-MODEL-STABILIZATION-PLAN.md`. It covers `.gitattributes`, `docs/qa/VALIDATION_INDEX.md`, supersession headers for old architecture docs, wiki/raw ingestion rules, and a Podman/Twenty validation note. It is intentionally safe for a standard coding model and must not implement Phase 7 endpoints or modify the vendored foundation.

## What NOT to Build

- Do not build the cockpit frontend — that is Phase 8.
- Do not add CRM, Pulse, or Channels endpoints — those are post-v1.0.
- Do not add authentication/authorization middleware — v1.0 is
  single-operator local, loopback-only binding.
- Do not add WebSockets — SSE covers v1.0 streaming.
- Do not reimplement mission/run/wiki business logic in Rust — writes
  dispatch through the `atlas` CLI; Rust owns HTTP/SSE/read-path only.
- Do not add admin or multi-tenant endpoints.
