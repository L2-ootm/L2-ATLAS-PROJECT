# L2 ATLAS PROJECT

AI Company Operating Cockpit: mission control, agent runtime, persistent knowledge, integrations, pulse monitoring, and operator-grade autonomy.

ATLAS is an L2-owned operator cockpit/runtime built by evolving the Hermes Agent foundation into an ATLAS-branded harness, then adding mission, audit, policy, wiki, memory, router, gateway, and cockpit layers around that evolved foundation.

## Current phase

Phases 1–6 complete and verified (foundation audit, schemas, research closure, audit bus, mission/run lifecycle, LLM Wiki). Phase 7 — Rust API Gateway + SSE (D-022) — is next. See `.planning/STATE.md` for live state and `docs/plans/PHASE_7_8_READINESS.md` for readiness.

## First ship target

ATLAS Operator Cockpit MVP:

1. Create mission.
2. Run through the ATLAS runtime built from the evolved Hermes foundation.
3. Persist run/audit/artifacts.
4. File valuable output into LLM Wiki.
5. Display state in cockpit.

## Orientation

- `docs/README.md` — documentation authority order
- `docs/architecture/OVERVIEW.md` — one-page architecture
- `docs/decisions/INDEX.md` — ADR index (D-001…D-022)
- `foundation/README.md` — vendored Hermes-derived foundation, attribution, divergences

Optional retrieval research now tracked:

- `docs/research/2026-06-06_TURBOVEC_LOCAL_RETRIEVAL_SPIKE.md` — evaluates `turbovec` as a compressed local semantic index behind SQLite metadata and ATLAS policy filters.

## Rules

- Use Hermes as the foundation codebase, vendored at `foundation/atlas-hermes/` and evolved in place (D-018). ATLAS is never a thin wrapper around, or a route through, stock Hermes.
- Raw sources are immutable.
- Every autonomous action is auditable.
- LLM Wiki compounds knowledge; RAG alone is not enough.
- Existing L2 repos are source assets, not blindly merged code.
