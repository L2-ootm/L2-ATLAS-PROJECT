# D-020: Twenty CRM as ATLAS Foundation Layer

**Status:** ACCEPTED
**Date:** 2026-06-08
**Deciders:** L2-ootm

---

## Context

ATLAS is designed as "the harness of the world" — a modular autonomous agent system. D-007 deferred CRM/Pulse/contacts features to v2.0 pending research closure. Phase 6 delivered the LLM Wiki memory layer (Layer 2/3 of D-019). The agent's contact memory, relationship tracking, and outreach/Pulse capabilities require a CRM data substrate.

The user constraint: ATLAS is fully modular, branding is deferred to final phases, and we adopt best-in-class open-source tools as foundation layers rather than building from scratch where strong prior art exists.

Research intake: `docs/imports/TWENTY_CRM_INTAKE_2026-06-08.md`

---

## Decision

**Adopt Twenty as an external self-hosted service pillar for ATLAS CRM capabilities.**

Twenty runs as a Docker Compose sidecar alongside ATLAS. ATLAS agents interact with it via four surfaces:
1. **Core API** (`/rest/` or GraphQL) — record read/write for People, Companies, Opportunities, Tasks, Notes
2. **Metadata API** (`/rest/metadata/`) — custom object provisioning on deploy (`AgentInteraction`, `MissionContext`, `OutreachCampaign`)
3. **MCP server** — direct agent tool calls via the D-017 model router / MCP architecture already planned
4. **Webhooks** — HMAC-signed event triggers into the ATLAS agent loop (requires Phase 7 API receiver)

**This is not vendoring.** Twenty is an external service. ATLAS holds no Twenty source code. If Twenty is unavailable, ATLAS CRM features degrade gracefully — they are additive, not in the core runtime path.

---

## Rationale

| Factor | Assessment |
|--------|-----------|
| API maturity | REST + GraphQL, full CRUD, upsert via GraphQL, batch 60 records/req |
| Agent integration | Native MCP server (v2.0+); aligns with D-017 model router/MCP plan |
| Schema flexibility | Metadata API allows custom objects — ATLAS can provision its own types on deploy |
| Self-hosting | Docker Compose, PostgreSQL + Redis; production-ready since v2.1.0 (2026-04-24) |
| License | AGPL-3.0 core — calling an API is not a derivative work; no copyleft obligation |
| Maturity | 49.5k stars, YC-backed, 300+ contributors, v2.1.0 explicitly production-ready |
| Alternatives | SuiteCRM (legacy PHP), Odoo (ERP-scale), Erxes (omnichannel-first) — none suitable |
| Only risk | AGPL if ever embedding source; mitigated by sidecar-only integration pattern |

---

## Non-negotiables

- ATLAS never embeds Twenty source. Sidecar only.
- Never store OAuth tokens or API keys in audit payloads (D-017 applies to Twenty API keys too).
- Twenty API keys in `.env` / secrets store, never committed.
- Custom objects provisioned via Metadata API at deploy time, not hardcoded schema.

---

## Phase Impact

- **Phase 7 (API Gateway):** add `/webhooks/twenty` receiver endpoint
- **Phase 8 (Cockpit):** CRM panel reads from Twenty via ATLAS API layer
- **New Phase (post-8):** CRM/Pulse feature set — contact memory, relationship graph, outreach campaigns
- D-007 status: CRM after cockpit still holds; Twenty is the resolved substrate

---

## Alternatives Considered

| Option | Rejected because |
|--------|-----------------|
| Build bespoke CRM | High cost, no benefit over proven open-source |
| SuiteCRM | Legacy PHP, REST API surface shallow, no MCP |
| Erxes | Omnichannel platform, not CRM-data-first; heavyweight for ATLAS's use |
| Atomic CRM | MIT license but shallow feature set; lacks Metadata API, MCP, webhooks |
| Odoo CRM | ERP-scale overkill; OWL JS lock-in; poor agent integration story |

---

## References

- Intake doc: `docs/imports/TWENTY_CRM_INTAKE_2026-06-08.md`
- Prior decisions: D-007, D-017, D-019
- Twenty repo: https://github.com/twentyhq/twenty (AGPL-3.0)
