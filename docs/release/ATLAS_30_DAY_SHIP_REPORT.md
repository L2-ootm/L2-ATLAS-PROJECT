# ATLAS 30-Day Ship Report (DRAFT)

> **DRAFT.** Build metrics below are real (from the repo at v0.1 prep). Adoption metrics are
> placeholders the operator fills AFTER the launch wave + private beta — I cannot and do not
> generate adoption numbers.

## What shipped

Open research preview of ATLAS, an auditable AI agent operating cockpit built on an evolved
Hermes foundation. v0.1 delivers: mission creation + run lifecycle, live audit/event streams,
artifact persistence, LLM Wiki filing with provenance, GitHub/local-workspace/web integrations
via an extensible tool manifest, a web cockpit, and an approval-gated self-review workflow.

## Build metrics (real, at v0.1 prep)

| Metric | Value |
|--------|-------|
| Commits (total) | 392 |
| Commits on the v1.0.5 wedge | ~104 |
| Python modules | 171 |
| Rust files (gateway) | 11 |
| Cockpit routes | 17 |
| SQL migrations | 13 |
| Developer tools (Manifest v0) | 5 |
| Logged architecture decisions | 32 (D-001…D-024 + impl notes) |
| Tests | agent-runtime ~369 pass (+atlas-core 52, Rust gateway, cockpit build green) |
| Golden-workflow quality gate | 3 workflows × 3 runs, structural-assert, green |

## Wedge phases (v1.0.5)

- 10.0.1 Repo Hygiene & Trust Package — complete (LICENSE + 6 trust docs + issue templates)
- 10.0.2 One-Command Install Path — complete (`atlas up`/`doctor`, mock mode, install/docs)
- 10.0.3 ATLAS Identity & Cockpit Redesign — complete (brand + per-page redesign wave)
- 10.0.4 Developer Integrations & Tool Manifest — complete (4 adapters + policy chokepoint)
- 10.0.5 Golden Workflows & Quality Gate — complete (3 workflows + smoke + demo-reset)
- 10.0.6 Public Release Prep & Distribution — drafts prepared; operator-gated actions pending

## Adoption metrics (operator fills post-launch)

- Repo stars / forks: `<fill>`
- GitHub Discussions threads / issues opened: `<fill>`
- Private beta participants (target 20–50) + feedback themes: `<fill>`
- External reactions (HN/X/LinkedIn/Discord): `<fill>`
- Recognition submissions (Algoverse, hackathons, mentor reviews): `<fill>`

## Honest limitations

Per `docs/known-failures.md`: live-LLM output is non-deterministic (mock mode is the
demo-stable path); not hardened for sensitive data; no `web_fetch` Research Brief variant
yet; cockpit screenshots are operator-captured. v0.1 is a research preview, not a product.

## Next

See `docs/release/PUBLIC_ROADMAP.md`.
