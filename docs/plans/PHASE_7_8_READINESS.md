# Phase 7/8 Readiness

Date: 2026-06-11 · Status: living readiness note (update at phase transitions)

## What is ready for Phase 7

- Toolchain: cargo/rustc 1.96.0 + VS Build Tools C++ workload verified —
  `cargo build -p atlas-gateway` green (debug and release).
- First crate live: `native/atlas-core-rs/crates/atlas-gateway/` serves
  `GET /health` on 127.0.0.1:8484; release binary 2.53 MB (<20 MB budget).
- Data layer: migrations 0001–0003 (core, provenance, model_registry);
  WAL enabled; service layer (mission/run/audit/wiki) complete with 118
  green tests across the three suites.
- Write-path contract: `atlas` CLI (mission/wiki/models/channels/foundation
  sub-apps) is the dispatch boundary the gateway shells out to for writes.
- Schema source of truth: frozen Pydantic v2 models (D-012) ready for JSON
  Schema export → Rust contract tests.

## What blocks Phase 7

- Nothing hard-blocks the gateway itself.
- Docker Desktop absence blocks only the Twenty sidecar (`setup_twenty.ps1
  up`) — irrelevant to Phase 7. Podman is the preferred lighter engine (see
  `docs/operations/TWENTY_LOCAL_SETUP.md`).

## What Phase 7 must build (canonical: ROADMAP Phase 7 + phase CONTEXT.md)

1. REST endpoints: missions (create/list), runs (start/status), audit
   events (list), wiki (pages/search) — reads via direct SQLite read-only
   connections.
2. Writes dispatched through the `atlas` CLI contract (no business logic in
   Rust).
3. `GET /runs/{id}/stream` SSE via rowid-cursor poll (≤500 ms).
4. JSON Schema contract tests against atlas-core exports (D-012).
5. Budget verification: binary <20 MB, idle RSS <80 MB.

First exposure order for the gateway: `/health` (done) → missions list →
run detail + events → SSE stream → wiki search → mission create/run writes.

## What must be true before Phase 8 starts

- All 8 Phase 7 endpoint groups green with contract tests.
- SSE latency measured ≤500 ms on a live run.
- `apps/cockpit-web/` scaffolded against the running gateway (SvelteKit 2 /
  Svelte 5, adapter-static, no SSR, no browser-only APIs unsupported by
  WebView2 — D-021 native-portability constraints).
- OpenAPI-equivalent endpoint reference written (hand-maintained doc or
  generated) so the cockpit consumes a stable contract.

## What should NOT be built yet

- No native shell work (Phase 10/v1.1).
- No CRM/Twenty endpoints or panels (Phase 11/v2.0).
- No auth/multi-tenant/admin surfaces (v1.0 = single operator, loopback).
- No WebSockets (SSE covers v1.0).
- No new Python service code (D-022) — gateway logic is Rust only.
- No promotion of `native/atlas-core-rs/crates/` to top-level `crates/`
  mid-phase — decided move point is after Phase 7 endpoints are green,
  before Phase 8 begins (PRODUCTION_REPO_STRUCTURE §4.2).
