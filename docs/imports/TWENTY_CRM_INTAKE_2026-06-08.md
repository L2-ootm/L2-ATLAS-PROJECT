# Twenty CRM Intake for ATLAS

Source: https://github.com/twentyhq/twenty
Reviewed commit/release: sdk/v2.9.1 (June 5, 2026); v2.0.0 stable (April 21, 2026)
License: AGPL-3.0 (core) + Commercial License (twenty-ee enterprise features)
Stack: TypeScript (78%), NestJS, PostgreSQL, Redis, BullMQ, React, Jotai, Nx monorepo

---

## Overview

Twenty is the leading open-source CRM alternative to Salesforce/HubSpot, self-described as "the open alternative to Salesforce, designed for AI." As of June 2026 it has 49,500 GitHub stars, 7,100 forks, 11,590+ commits, and 300+ active contributors. It is Y Combinator-backed with a $5M seed round (November 2024, Runa Capital). v2.1.0 (April 24, 2026) is the first release the team explicitly marks as production-ready for single-tenant self-hosted deployments. v2.0.0 (April 21, 2026) shipped an AI SDK, native MCP server, and git-backed workspace versioning.

For ATLAS the relevant framing is: Twenty is a well-funded, API-first, metadata-driven CRM with both REST and GraphQL surfaces, a native MCP server, webhook support, and a clean PostgreSQL data store — all self-hostable. It is not a generic data platform. Its object model (People, Companies, Opportunities, Tasks, Notes + custom objects) maps directly to the contact memory, relationship tracking, and outreach/Pulse features planned for ATLAS v2.0 in D-007.

---

## Architecture

### Runtime services

| Service | Image | Role |
|---------|-------|------|
| twenty-server | twentycrm/twenty | NestJS backend — API, metadata engine, auth, workflow runner |
| twenty-worker | twentycrm/twenty (worker mode) | BullMQ background job processor |
| twenty-postgres | twentycrm/twenty-postgres-spilo | PostgreSQL 15 with pg_graphql extension |
| redis | redis:7 | Queue broker for BullMQ; session cache |

Four services total. Idle footprint: ~750 MB RAM. Small-team production: 1–2 GB / 2 vCPU.

### Monorepo structure

Nx monorepo. Backend is NestJS with a metadata-driven schema engine — objects and fields are stored as configuration, not hard-coded tables. Every workspace gets its own Postgres schema. The metadata engine generates GraphQL/REST endpoints dynamically from the current object graph, so custom objects receive identical API surface to built-in objects automatically.

### Data persistence

Standard PostgreSQL. The twenty-postgres image adds the `pg_graphql` extension (used for some internal query paths). An external Postgres instance can be supplied — the twenty-postgres image is not mandatory. Data is directly queryable via psql, pg_dump, and any BI tool.

### Self-hosting deployment options

- **Docker Compose:** First-class. One-line install script (`VERSION=vx.y.z bash <(curl...)`). Services defined in a provided `docker-compose.yml`. Environment variables: `ENCRYPTION_KEY` (openssl rand -base64 32), `PG_DATABASE_PASSWORD`, `SERVER_URL`.
- **Kubernetes / Helm:** Community-maintained Helm charts exist on Artifact Hub (`cloud-exit/twentycrm-helm`, `AMecea/helm-twentycrm`). Not first-party maintained. External Postgres and Redis can be supplied. AKS deployment manifests documented in community forum.
- **Railway / Nuon / cloud PaaS:** One-click deploy templates exist but are not relevant for ATLAS.

### Upgrade path

Version-pinned via `VERSION=vx.y.z` in the install script. No official in-place upgrade automation documented; restore from backup is the stated recovery path.

---

## Integration Surface

### API architecture

Twenty exposes two orthogonal API surfaces, each available as both REST and GraphQL:

| API | Base path | Purpose |
|-----|-----------|---------|
| Core API | `/rest/` and `/graphql/` | CRUD on records: People, Companies, Opportunities, Tasks, Notes, custom objects |
| Metadata API | `/rest/metadata/` and `/metadata/` | Schema management: create/modify/delete objects, fields, relations |

No static API reference exists. Each workspace generates its own schema from its metadata. The interactive playground lives at **Settings → API & Webhooks** after key creation. This is a deliberate design choice — custom objects are first-class citizens with no second-class status.

### Authentication

- Bearer token via API key: `Authorization: Bearer YOUR_API_KEY`
- Keys created in Settings → API & Webhooks → + Create key (shown once, copy immediately)
- Keys can be role-scoped (read-only, write, admin subsets)
- OAuth support available for external apps acting on behalf of users (Twenty Cloud; self-hosted OAuth setup is documented)
- Rate limit: **100 requests/minute** per key (cloud); self-hosted has no enforced limit by default

### GraphQL — key patterns

```graphql
# Query people with filter
query {
  people(filter: { email: { like: "%@acme.com" } }) {
    edges {
      node {
        id
        name { firstName lastName }
        email
        company { name }
      }
    }
  }
}

# Batch create companies (up to 60 per request)
mutation CreateCompanies($input: [CompanyCreateInput!]!) {
  createCompanies(data: $input) {
    id
    name
    domainName
  }
}

# Upsert (GraphQL-only — no REST equivalent)
mutation UpsertPerson($input: PersonUpdateInput!, $id: ID!) {
  upsertPerson(data: $input, id: $id) {
    id
    name { firstName lastName }
  }
}
```

Relations are traversable in a single query. Pagination follows Relay-style `edges/node/cursor` conventions.

### REST — key patterns

```
GET    /rest/people?filter=email[like]=%25@acme.com&limit=20
POST   /rest/people          { "name": { "firstName": "Ada" }, "email": "ada@acme.com" }
PATCH  /rest/people/:id      { "jobTitle": "Engineer" }
DELETE /rest/people/:id

POST   /rest/metadata/objects    { "nameSingular": "AgentMemory", "namePlural": "AgentMemories", ... }
```

### Webhooks

Events are fired for all objects (built-in and custom):

| Event pattern | Example |
|--------------|---------|
| `{object}.created` | `person.created`, `company.created`, `agentMemory.created` |
| `{object}.updated` | `opportunity.updated`, `task.updated` |
| `{object}.deleted` | `note.deleted` |

Payload format:
```json
{
  "event": "person.created",
  "data": { /* full record fields */ },
  "timestamp": "2026-06-08T12:00:00Z"
}
```

Security: `X-Twenty-Webhook-Signature` (HMAC SHA256 of `{timestamp}:{payload}`) and `X-Twenty-Webhook-Timestamp` headers. Validation requires timing-safe comparison. Delivery failure: non-2xx responses are logged; retry mechanism not formally documented. Event filtering not yet available (planned).

### MCP server

Twenty v2.0 ships a **native MCP server** in every workspace (Cloud). For self-hosted, a community MCP server (`mhenry3164/twenty-crm-mcp-server`) exposes the full GraphQL/REST surface as MCP tools:

- `create_person`, `get_person`, `update_person`, `list_people`, `delete_person`
- `create_company`, `get_company`, `update_company`, `list_companies`, `delete_company`
- `create_task`, `get_task`, `update_task`, `list_tasks`, `delete_task`
- `create_note`, `get_note`, `update_note`, `list_notes`, `delete_note`
- `get_metadata_objects`, `get_object_metadata`, `search_records`

Dynamic schema discovery: the MCP server reflects the live workspace schema, so custom ATLAS objects created via Metadata API automatically appear as tools. An ATLAS agent with the Twenty MCP server configured becomes a first-class CRM operator.

### Batching

Both REST and GraphQL support batch create/update/delete/upsert up to **60 records per request**. GraphQL-only: batch upsert in a single mutation.

---

## ATLAS Feature Fit

### Contact memory and relationship graph

Twenty's `People` and `Companies` objects with their relation fields provide the storage substrate for ATLAS agent contact memory. Custom fields can extend Person records with ATLAS-specific metadata: agent interaction history, relationship strength score, last-contact-by-agent, mission context tags. The Metadata API lets ATLAS provision these fields programmatically on first deployment without manual UI work.

### Relationship tracking

The flexible relation system (a single field can point to either a Person or Company depending on context) supports the kind of multi-entity relationship graph ATLAS agents need to reason about. Opportunities can relate to either a person or a company, covering both deal and network-graph use cases.

### Outreach / Pulse

ATLAS Pulse (contact-initiated outreach, follow-up cadences) maps to:
- Twenty `Tasks` — to-do records linked to any CRM object, driveable by agent via API
- Twenty `Notes` — free-text memory attached to any record, writable by agent
- Twenty Workflows — built-in automation triggers that can fire on record events, enabling agent-free follow-up chains for simple cases
- Webhooks — notify ATLAS when a person record is updated (e.g. email reply logged), triggering the next outreach step in the agent loop

### Deal pipeline

`Opportunities` with configurable stages. Writable via `PATCH /rest/opportunities/:id` with `{ "stage": "ProposalSent" }`. The GraphQL upsert mutation is ideal for agent-driven pipeline updates where the record may or may not exist.

### Agent-native CRM records

The Metadata API is the key differentiator: ATLAS can create custom objects such as `AgentSession`, `MissionContext`, `OutreachCampaign`, or `ContactSignal` that live inside Twenty alongside normal CRM objects, share the same API surface, and trigger the same webhook events. This collapses the boundary between CRM data and agent operational data into one system.

### Email and calendar sync

Twenty supports email and calendar sync but only for People, Companies, and Opportunities. Custom objects do not participate in sync. This is relevant if ATLAS wants to read inbound email directly from Twenty rather than via a separate mail channel.

---

## Comparison to Alternatives

### Open-source CRM field for programmatic / agent integration (2026)

| Dimension | **Twenty** | **Erxes** | **SuiteCRM** | **Odoo CRM** | **Atomic CRM** |
|-----------|-----------|-----------|-------------|-------------|----------------|
| Primary stack | TypeScript/NestJS | TypeScript/GraphQL | PHP/Legacy | Python/OWL JS | TypeScript/Supabase |
| License | AGPL-3.0 + Commercial EE | GPL-3.0 | AGPL-3.0 | LGPLv3 | MIT |
| API style | REST + GraphQL (both first-class) | GraphQL-first | REST (limited) | JSON-RPC + REST | REST + GraphQL |
| Custom objects via API | Yes (Metadata API) | Yes (limited) | No (plugin only) | Yes (complex) | Yes |
| Native MCP server | Yes (v2.0) | No | No | No | Yes (MIT) |
| Webhooks | Yes (all objects, HMAC-signed) | Yes | Limited | Yes | Unknown |
| Agent integration readiness | **Highest** — MCP, dynamic schema, clean API | Medium | Low | Low | High (simpler) |
| Self-hosting maturity | High — Docker Compose, Helm community | Medium | High (mature but old) | High (heavy) | High (Supabase) |
| Production-ready since | v2.1.0 (April 2026) | v1.x (older) | Years | Years | Early |
| GitHub stars | 49.5k | ~3k | ~4k | N/A (Odoo) | ~1.5k |
| Active development | Very high (v2.9.1, June 2026) | Moderate | Moderate | Very high | Low-moderate |
| Resource footprint | ~750 MB idle (4 services) | Heavier (many services) | Medium | Very heavy | Light (Supabase) |
| CRM depth | Full | Full (omnichannel) | Full (enterprise) | Full (ERP) | Minimal |
| ATLAS fit | **Primary candidate** | Secondary | Not recommended | Not recommended | Secondary (lighter) |

**Erxes** is primarily an omnichannel customer engagement platform (messenger, email, WhatsApp, call center) rather than a pure CRM. Its GraphQL API is usable but the product emphasis is on live-chat and ticketing, not contact/deal data modeling. For ATLAS Pulse, Erxes' messaging channels are interesting but the CRM data layer is not as clean as Twenty's.

**SuiteCRM** has a large module ecosystem and proven enterprise use, but the codebase is PHP with a custom ORM, the REST API is limited, and there is no modern AI/agent integration story. Not suitable as a foundation layer for agent-first workflows.

**Odoo CRM** is a module inside a full ERP. Resource requirements are massive, the OWL JS framework creates lock-in, and the integration path into a Python agent runtime is indirect. For CRM-only use it is severe overkill.

**Atomic CRM** (MIT) is interesting as a lightweight alternative — it is ~15,000 lines total, built on React/shadcn/Supabase, and has a native MCP server. If ATLAS needs a no-AGPL, ultra-thin CRM substrate, Atomic is the fallback. Trade-off: far less feature depth, smaller community, and Supabase dependency adds managed infrastructure.

---

## Risks and Constraints

### License: AGPL-3.0 contamination risk

AGPL-3.0 requires that any modified version of Twenty used to provide a networked service to others must release modifications as open source. For ATLAS internal use (agents operating against a self-hosted Twenty instance), AGPL does not restrict ATLAS code — ATLAS is not modifying or distributing Twenty, it is calling its API. ATLAS code that calls Twenty's API is not a derivative work of Twenty.

Risk materializes if: (a) ATLAS forks and embeds Twenty code into the ATLAS codebase, or (b) ATLAS bundles and ships Twenty as part of a product offered to third parties. Neither applies to the current ATLAS architecture (Hermes foundation + external services).

**Verdict:** AGPL is not a blocker for ATLAS's intended use pattern (API integration, self-hosted by Davi/L2).

### Enterprise features are gated (proprietary)

Files marked `/* @license Enterprise */` (the `twenty-ee` package) cover SSO, advanced RBAC, and lifecycle permissions. These require a commercial subscription. The AGPL core covers all object management, API, webhooks, workflows, and MCP. ATLAS does not need enterprise features at current scope.

### Twenty-postgres image with pg_graphql dependency

The `pg_graphql` extension is required by the twenty-postgres image. Confirmed issue (#8032) shows `pg_graphql` is not available in some registries (docker.io latest tag). Resolution: use the official `twentycrm/twenty-postgres` image, not a generic Postgres image. External Postgres deployments must install pg_graphql manually.

### API rate limit: 100 req/min (cloud)

For self-hosted instances this limit is not enforced by default. ATLAS agents hitting a self-hosted Twenty instance can run at whatever rate the Postgres/NestJS backend handles. This eliminates rate-limit concerns for internal agent use.

### No retry guarantee on webhooks

Webhook delivery failure is logged but retry behavior is undocumented. ATLAS must treat Twenty webhooks as best-effort and design the event consumer to be idempotent. For reliability, ATLAS can supplement webhooks with periodic polling via the Core API.

### Helm charts are community-maintained, not first-party

Kubernetes deployment relies on community charts. For small-scale (single-node, Docker Compose) ATLAS deployment this is not a concern. For multi-node production Kubernetes this requires additional validation.

### NestJS/TypeScript stack is not in ATLAS core runtime

ATLAS core is Python (Hermes foundation). Twenty runs as a separate service; ATLAS calls it over HTTP. There is no language-level integration concern — this is a service boundary, not a library dependency. The MCP server pattern (D-017 architecture) means ATLAS agents can call Twenty tools without writing any HTTP client code directly.

### Breaking changes pre-v2.1.0

The team held back production designation until v2.1.0 explicitly because earlier versions had frequent breaking changes. As of April 2026 this has stabilized. Pin to `v2.1.x` or later for any ATLAS deployment.

---

## Recommendation

Adopt Twenty as the ATLAS CRM foundation layer for contact memory, relationship tracking, outreach/Pulse, and deal pipeline.

**Classification:** External service pillar (same pattern as FreeLLMAPI in D-015/D-017).

Twenty runs as a self-hosted sidecar service. ATLAS communicates with it via:
1. GraphQL or REST Core API for record read/write (contacts, companies, opportunities, tasks, notes)
2. Metadata API for programmatic custom object provisioning on ATLAS deployment
3. MCP server for direct agent tool integration (aligns with D-017 MCP-first approach)
4. Webhooks for event-driven triggers into the ATLAS agent loop

Do not vendor or fork Twenty. Do not embed Twenty code into the ATLAS codebase. Preserve the clean service boundary: ATLAS owns agent runtime, policy, audit, wiki; Twenty owns CRM data, relationship graph, and outreach task state.

Integration path:

1. Phase 11 (CRM via Twenty — canonical numbering per D-021 §2): add Docker Compose service entry for Twenty alongside the ATLAS stack. A profile-gated compose entry may land earlier for spikes.
2. Provision ATLAS-specific custom objects via Metadata API on first deploy: `AgentInteraction`, `OutreachCampaign`, `ContactSignal` (names TBD).
3. Add `atlas_core.crm` connector module wrapping Twenty's Core API — thin HTTP client, not a full ORM.
4. Wire the community MCP server (`mhenry3164/twenty-crm-mcp-server`) into the ATLAS MCP tool registry (D-017 model router pattern extended to CRM tools).
5. Add webhook receiver in the ATLAS API layer (Phase 7) to consume `person.updated`, `task.created`, `opportunity.updated` events.
6. Defer enterprise features (SSO, advanced RBAC) — AGPL core covers all needed functionality.

---

## Open Questions

1. **Custom object naming convention** — What ATLAS-specific objects should be provisioned in Twenty's schema on deploy? Candidates: `AgentInteraction` (log of which agent touched which contact), `MissionContext` (links a CRM record to an active ATLAS mission), `OutreachCampaign`. Needs product definition before Phase 11 (CRM) planning.

2. **Data residency and PII policy** — Twenty stores contact PII in Postgres. ATLAS policy labels (D-017) include `no-sensitive-data` for free-tier routes. Contacts in Twenty are by definition sensitive. Confirm that no ATLAS agent routes contact data through FreeLLMAPI or any `free-tier-ok` model path.

3. **Webhook endpoint exposure** — ATLAS webhook receiver for Twenty events must be accessible from the Twenty container. In a local/Docker Compose setup this is straightforward (shared Docker network). For production deployments on separate hosts, a publicly accessible or VPN-internal URL is required. Architecture decision needed in Phase 7.

4. **pg_graphql version pin** — Confirm the exact Twenty Postgres image tag to use for self-hosting to avoid the pg_graphql availability issue (#8032). Recommended: do not use `latest`; pin to the same version as the Twenty server image.

5. **Atomic CRM as a lightweight fallback** — If AGPL licensing concern escalates (e.g., ATLAS becomes a distributed product), Atomic CRM (MIT) is the fallback. Its shallower feature set and Supabase dependency make it second choice, but the option should be formally noted in the eventual ADR.

6. **Email/calendar sync scope** — Twenty's email/calendar sync only covers People, Companies, and Opportunities. If ATLAS needs inbound email as a trigger source for agent runs, a separate mail channel (already in Hermes foundation) is required. Twenty should not be treated as the email ingestion layer.

7. **Twenty v2.x API stability** — v2.0 landed April 2026 with breaking API changes from v1.x. Pin deployment at v2.1.0+ and track the changelog on any ATLAS phase that depends on Twenty before planning.

---

## Immediate ATLAS planning decision

Classify Twenty as: **CRM and contact-relationship foundation layer** (external self-hosted service pillar).

Do not classify it as: agent harness, memory layer, email server, or general data store.

Combined direction:

```text
L2/ATLAS CRM layer = Twenty self-hosted (service)
                   + atlas_core.crm connector (thin HTTP/MCP client, Python)
                   + ATLAS custom objects provisioned via Metadata API
                   + webhook receiver in Phase 7 API layer
```

This pillar is scoped to Phase 11 (CRM via Twenty; D-007 v2.0 items, D-021 §2 numbering). It has no dependency on current Phase 6 (wiki-runtime) or Phase 7 (API layer) completions, but Phase 7's webhook infrastructure is a prerequisite for the event-driven integration.
