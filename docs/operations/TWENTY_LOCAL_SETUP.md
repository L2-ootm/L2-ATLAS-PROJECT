# Twenty CRM — Local Sidecar Setup

**Doctrine (D-020/D-021):** Twenty runs as a pinned upstream sidecar. ATLAS
talks to it via Core API, Metadata API, MCP, and webhooks. No Twenty source
in the ATLAS codebase; no fork; no rebrand of Twenty itself (AGPL-3.0 +
trademark). The operator-facing L2 branding lives in the ATLAS cockpit, which
fronts Twenty data through our API layer.

## Prerequisites

- A container engine (**none installed on the dev machine as of
  2026-06-11**). **Podman is preferred** — daemonless, no always-on VM
  service, materially lower idle RAM than Docker Desktop (no-bloat budget):
  `winget install RedHat.Podman`, then `podman machine init` and
  `podman machine start` (WSL2 backend; `podman machine stop` reclaims the
  RAM when the sidecar is not in use). Docker Desktop remains a supported
  fallback (`winget install Docker.DockerDesktop`). `setup_twenty.ps1`
  auto-detects (podman → docker); force with `-Engine podman|docker`.
  Note: Twenty's official compose targets Docker; if a Podman
  incompatibility appears (healthcheck/volume semantics), fall back with
  `-Engine docker` and record the issue here.
- ~2 GB RAM headroom for the stack (server, worker, twenty-postgres-spilo, redis).

## Install / lifecycle

```powershell
pwsh scripts/setup_twenty.ps1 fetch    # downloads OFFICIAL compose at pinned tag (v2.1.0) + generates secrets
pwsh scripts/setup_twenty.ps1 up       # start — UI at http://localhost:3000
pwsh scripts/setup_twenty.ps1 status
pwsh scripts/setup_twenty.ps1 down     # stop; Postgres volume preserved
```

The fetched files land in `infra/compose/twenty/` (entire directory
gitignored except this doctrine's README pointer — we pin upstream's files at
a tag instead of hand-maintaining a copy that drifts). `.env` holds generated
secrets and the Twenty API key later — **never commit it**.

## Version policy

- Pinned at `v2.1.0` (first production-mature 2.x per intake). Bump only via
  `-Version` after reading the Twenty changelog — v1.x → v2.0 had breaking
  API changes (intake open question #7).
- Postgres must use the official `twentycrm/twenty-postgres-spilo` image from
  the fetched compose — generic Postgres lacks `pg_graphql` (issue #8032).

## ATLAS integration surfaces (wired in later phases)

| Surface | Use | Phase |
|---|---|---|
| Core API (`/rest/`, GraphQL) | CRUD on people/companies/opportunities | Phase 11 |
| Metadata API (`/rest/metadata/`) | Provision `AgentInteraction`, `MissionContext`, `OutreachCampaign` custom objects at deploy time | Phase 11 |
| MCP server | Direct agent tool calls (community server wired into the D-017 MCP registry) | Phase 11 |
| Webhooks → `/webhooks/twenty` | Event-driven triggers into the agent loop; HMAC SHA256-verified; receiver must be idempotent by event ID (retry behavior undocumented) | Phase 7 (receiver), Phase 11 (flows) |

## Hard rules

- Twenty contact data is PII: it must NEVER route through `free-tier-ok` /
  `no-sensitive-data` model paths (D-017).
- Twenty API keys live in `.env` / secrets store — never in audit payloads,
  never committed.
- If AGPL ever becomes a real distribution constraint, the documented
  fallback is Atomic CRM (MIT) — see intake open question #5.
