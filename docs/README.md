# docs/ — Documentation Authority Map

Canonical product statement:

> ATLAS is an L2-owned operator cockpit/runtime built by evolving the Hermes
> Agent foundation into an ATLAS-branded harness, then adding mission, audit,
> policy, wiki, memory, router, gateway, and cockpit layers around that
> evolved foundation.

## Authority order (when documents conflict)

1. `AGENTS.md` (repo root) — local operating constraints.
2. `docs/decisions/` — accepted ADRs. Canonical. See `decisions/INDEX.md`.
3. `docs/architecture/` — current target architecture. Explains, never
   overrides, decisions.
4. `.planning/` — live execution state (STATE.md, ROADMAP.md, phase
   contexts). Tracks what is true *now*.
5. `docs/research/`, `docs/imports/` — **inputs, not canonical.** A research
   or intake document becomes truth only when an ADR promotes it.

When a conflict is found, patch the losing document with a short note
pointing to the winning ADR. Do not silently rewrite history.

## Folder purposes

| Folder | Holds | Authority |
|---|---|---|
| `decisions/` | ADRs (D-NNN) + runtime divergence decisions (DIV-NNN) | Canonical |
| `architecture/` | Target-architecture specs and strategy docs | Explanatory |
| `operations/` | Runbooks: setup, sidecars, channels, recovery | Operational truth |
| `plans/` | Implementation/stabilization plans, readiness notes | Execution input |
| `research/` | Raw research, spikes, benchmarks, audits | Input only |
| `imports/` | Intake notes from donor/reference systems | Input only |
| `qa/` | Validation reports and test evidence | Evidence |
| `vision/`, `foundation/`, `private/` | Long-range notes, foundation docs, local-only material | Context |

Foundation-tree provenance lives outside docs/: `foundation/ATTRIBUTION.md`
and `foundation/DIVERGENCE_LOG.md` (DIV-F-NNN entries) govern every change to
the vendored Hermes-derived foundation.
