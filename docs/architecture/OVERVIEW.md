# ATLAS Architecture — One-Page Overview

Date: 2026-06-11 · Authority: explanatory (ADRs in `docs/decisions/` win)

> ATLAS is an L2-owned operator cockpit/runtime built by evolving the Hermes
> Agent foundation into an ATLAS-branded harness, then adding mission, audit,
> policy, wiki, memory, router, gateway, and cockpit layers around that
> evolved foundation.

```text
Hermes Agent foundation → L2/ATLAS enhanced foundation → ATLAS product/runtime/cockpit
```

## Layers

| Layer | Lives in | Language | Status |
|---|---|---|---|
| Evolved foundation (agent loop, CLI, tools, skills, channels/gateway daemon, providers, sessions) | `foundation/atlas-hermes/` — vendored at pinned SHA, MIT, every change in `foundation/DIVERGENCE_LOG.md` (DIV-F-001..006) | Python | Active; rebranded via built-in `atlas` skin |
| Domain contracts | `packages/atlas-core/` (frozen Pydantic v2, D-012) | Python → JSON Schema → TS/Rust | Done (Phase 2) |
| ATLAS runtime (mission/run lifecycle, audit bus, policy, model registry) | `services/agent-runtime/` + `atlas_audit` bundled foundation plugin | Python (existing service bucket) | Done (Phases 4–5) + D-017 registry |
| LLM Wiki (Layer 2/3 memory: ingest/search/lint/provenance) | `services/wiki-runtime/` → `wiki/` markdown | Python | Done (Phase 6) |
| API Gateway (REST + SSE) | `native/atlas-core-rs/crates/atlas-gateway/` (axum + rusqlite; reads direct SQLite, writes via `atlas` CLI dispatch) | **Rust (D-022)** | Phase 7 — crate scaffolded, builds green, /health live |
| Operator cockpit (mission list/detail, run timeline, live audit stream, wiki browser) | `apps/cockpit-web/` — SvelteKit/Svelte 5, adapter-static, native-portable | TypeScript | Phase 8 (web-first per D-021) |
| Native shell (Tauri 2 wrapping the same app) | Phase 10 / v1.1 | Rust | Later |
| Datastore | `~/.atlas/atlas.db` — SQLite WAL + FTS5 (+ sqlite-vec optional), migrations in `infra/migrations/` | SQL | Active (0001–0003) |

## Sidecars (pinned upstream, never forked or rebranded — D-021 §8)

- **FreeLLMAPI** — OpenAI-compatible free-tier router on loopback; ATLAS
  model registry live-syncs from its `/v1/models` (D-015/D-017).
- **Twenty CRM** — AGPL + trademark: external self-hosted service, API/MCP/
  webhook integration only, Phase 11/v2.0 (D-020).

## v1.0 vs later

- **v1.0 (Phases 7–9):** Rust gateway + SSE → web cockpit → skill
  classification. Single operator, loopback, no auth.
- **v1.1 (Phase 10):** Tauri native shell.
- **v2.0+ (Phases 11–12):** CRM via Twenty sidecar, Pulse monitoring,
  graph memory Layer 4.

## Rust cementation (D-022)

All new infrastructure is Rust. Python persists only in: the Hermes-derived
foundation surface, LLM adapters, existing services, and throwaway scripts.
The L0–L5 ladder ends with a Rust harness core strangling the Python agent
loop (v2.x). Budgets: CLI <100 ms/<50 MB, daemon <80 MB idle, binaries
<20 MB. Reference input for the ladder: `eikarna/hermes-rs` (community Rust
port of Hermes) — evaluate as reference material, do not vendor without an
ADR.
