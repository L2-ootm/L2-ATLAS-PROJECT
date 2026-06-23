# Repo Triage — 2026-06-23

Workspace root: `C:\Users\Davi\Desktop\Projects\L2-ATLAS-PROJECT`

Top-level entries (42):
- .claude
- .coverage
- .env.example
- .git
- .gitattributes
- .github
- .gitignore
- .mimocode
- .planning
- .playwright-cli
- .pytest_cache
- .superpowers
- .venv
- AGENTS.md
- ARCHITECTURE.md
- ATTRIBUTION.md
- CLAUDE-FABLE-5.md
- CODE_OF_CONDUCT.md
- CONTRIBUTING.md
- LICENSE
- LIMITATIONS.md
- README.md
- SECURITY.md
- _EXTERNAL_REPOS
- apps
- artifacts
- atlas.cmd
- brand
- coverage.json
- coverage_branch.json
- docker-compose.yml
- docs
- foundation
- infra
- l2_atlas_30_day_mass_adoption_wedge_plan.md
- native
- output
- packages
- scripts
- services
- tests
- wiki

## README excerpt

```
# L2 ATLAS PROJECT

AI Company Operating Cockpit: mission control, agent runtime, persistent knowledge, integrations, pulse monitoring, and operator-grade autonomy.

ATLAS is an L2-owned operator cockpit/runtime built by evolving the Hermes Agent foundation into an ATLAS-branded harness, then adding mission, audit, policy, wiki, memory, router, gateway, and cockpit layers around that evolved foundation.

## Quickstart

```bash
git clone <your-fork-url> atlas && cd atlas
cp .env.example .env
./scripts/setup.sh          # or .\scripts\install-atlas-cli.ps1 on Windows
./atlas db init --demo      # optional: seed a demo mission so the cockpit isn't empty
./atlas up
./atlas doctor              # confirm db/config/gateway/cockpit/provider are all healthy
```

No provider API key required to try it — ATLAS runs in Mock Mode end-to-end
with zero credentials configured. Full walkthrough, troubleshooting, and the
optional Docker Compose path: see [`docs/INSTALL.md`](docs/INSTALL.md).

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
- [`docs/tools.md`](docs/tools.md) — developer integrations + Tool Manifest v0 (adding a tool = manifest + adapter)
- `foundation/README.md` — vendored Hermes-derived foundation, attribution, divergences

Optional retrieval research now tracked:

- `docs/research/2026-06-06_TURBOVEC_LOCAL_RETRI
```
