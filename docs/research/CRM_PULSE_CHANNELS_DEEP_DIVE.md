# CRM, Pulse & Channels — Research Intake

Date: 2026-06-06
Resolution: D-010 (missing CRM/Pulse/Channels research)
Phase: 3 — Research Closure

## 1. Purpose and Scope

This document closes D-010 (missing CRM/Pulse/Channels research).

- CRM is v2 scope only (D-007 locked). This document does NOT design CRM for v1.
- Pulse/heartbeat monitors depend on Phase 4 (AuditEvent bus) and Phase 6 (Wiki runtime) — cannot be built until both phases complete.
- Channels (WhatsApp/Discord) are listed as "too risky before runtime is proven" in REQUIREMENTS.md. Research must answer ToS and approval questions before any implementation begins.
- STT/TTS/overlay is explicitly OUT OF SCOPE (D-009 locked).

Milestone v2.0 requirements addressed: PULSE-01, PULSE-02, CRM-01, CRM-02.

## 2. What We Know

### CRM

Research recommends NOT forking Twenty CRM. Twenty 2.0 uses PostgreSQL + TypeScript SDK + MCP server — too heavy for the ATLAS v1 SQLite stack. The architecture is impressive but misaligned: Twenty assumes a cloud-hosted, PostgreSQL-backed multi-tenant SaaS; ATLAS is a local-first, SQLite-backed operator cockpit.

ATLAS CRM should start with minimal AI-native primitives: Contact, Organization, Opportunity — linked to wiki and missions per CRM-01/CRM-02. The core data model minimum as a starting point (not locked schema): Contact (name, email, org, notes, mission_ids), Organization (name, contacts), Opportunity (org, status, value, mission_ids). These are intentionally simple — the research brief below asks the deep-dive agent to propose extension patterns.

### Pulse

Pulse is a periodic briefing aggregating: repo state, open missions, wiki health, inbox state, deadlines. Heartbeat monitors run on cron and emit AuditEvents (PULSE-02). Pulse cannot be scoped for v1 because its inputs (audit stream from Phase 4, wiki from Phase 6, mission lifecycle from Phase 5) do not exist until Phase 6 completes. The dependency chain is strict: Phase 4 → Phase 5 → Phase 6 → Pulse. Any attempt to build Pulse before Phase 6 ships will fail due to missing data sources.

### Channels

L2-BOT has Discord and channel management patterns that could serve as reference implementations (from DEEP_RESEARCH_BACKLOG.md R7). WhatsApp integration carries ToS risk. The official Meta Business API vs the unofficial Baileys library is an unresolved question — and the answer has legal, not just technical, implications. Channels are listed as "too risky before runtime is proven" in the REQUIREMENTS.md out-of-scope section. The risk is not technical difficulty but regulatory/ToS compliance for outbound messaging at scale.

## 3. Open Questions

### CRM Open Questions

1. Should ATLAS CRM link to missions by mission_id FK, or should CRM entities be wiki pages with a `crm:` namespace?
2. What is the minimum viable Contact schema that doesn't constrain future extension (Twenty-style metadata fields)?
3. Should CRM records be audited via the AuditEvent bus, or have a separate change log?
4. Does ATLAS CRM need duplicate detection at v2, or is that post-v2?
5. What import path enables populating the CRM from existing contacts (CSV, Google Contacts, vCard)?

### Pulse Open Questions

6. What exactly triggers a Pulse briefing — time schedule, mission completion, or explicit request?
7. What is the output format: markdown wiki page, push notification, CLI print, or all three?
8. What data sources does Pulse aggregate: wiki freshness, open missions, calendar (if integrated), repo state?
9. How does Pulse interact with the audit stream — does it produce AuditEvents, consume them, or both?

### Channels Open Questions

10. Which messaging channels are in v2 scope: WhatsApp only, Discord only, or both?
11. For WhatsApp: official Meta Business API vs unofficial client library — which is ToS-safe for the target use case?
12. What is the approval flow for outbound channel messages — every message requires human approval or only first contact?
13. How are channel conversations stored: as wiki pages, as AuditEvents, or in a separate channels table?
14. What privacy model governs conversation storage and retention?

These questions must be resolved before any v2 CRM/Pulse/Channels implementation begins. The research brief in Section 5 provides the scope for a future deep-dive agent to answer them.

## 4. MVP Boundary

| Feature | v1 Scope | v2 Scope | Notes |
|---------|----------|----------|-------|
| CRM Contact model | OUT — not in MVP | IN (CRM-01) | Linked to missions by mission_id or wiki namespace (open question) |
| CRM Organization model | OUT | IN (CRM-01) | Part of minimal CRM primitive set |
| CRM Opportunity model | OUT | IN (CRM-01) | Part of minimal CRM primitive set |
| CRM linkage to missions | OUT | IN (CRM-02) | Linkage model is open question |
| CRM duplicate detection | OUT | OUT (post-v2) | Too complex for initial v2 scope |
| CRM import (CSV/vCard) | OUT | TBD | Depends on open question resolution |
| Pulse briefing (cron-triggered) | OUT — requires Phase 4+5+6 | IN (PULSE-01, PULSE-02) | Cannot build before Phase 6 completes |
| Pulse output format | OUT | TBD | Open question to resolve |
| WhatsApp integration | OUT — ToS risk unresolved | TBD for v2 | Requires explicit Meta API decision first |
| Discord integration | OUT | TBD for v2 | Existing L2-BOT patterns available |
| Multi-channel simultaneously | OUT | OUT (post-v2) | One channel only at v2 |
| Automated outbound without approval | OUT | OUT | Hard constraint — human approval always required |
| STT/TTS/overlay | OUT (D-009) | Milestone 2 | Separate from CRM/Pulse/Channels |

The v2 scope above is the intended scope definition for Milestone v2.0, not a commitment. Each IN item requires the corresponding open questions to be resolved before a build phase begins.

## 5. Research Brief

### Research Brief: CRM/Pulse/Channels Deep Dive (v2 Milestone)

**Mission:** Resolve the open questions in Section 3 sufficiently to produce implementation-ready decisions for ATLAS Milestone v2.0.

**Constraints (non-negotiable):**
- CRM: ATLAS uses SQLite, not PostgreSQL. Do NOT design for Postgres or Twenty CRM's data model.
- CRM: Must be Pydantic v2 compatible (D-012) — schema source of truth is atlas_core.schemas.
- Channels/WhatsApp: Do NOT recommend unofficial Baileys library without a ToS analysis. The Meta Business API is the starting assumption.
- STT/TTS/overlay: OUT OF SCOPE (D-009).
- Electron: OUT OF SCOPE (D-005).

**Research tasks (prioritized):**

1. CRM linkage model: Evaluate FK mission_id column vs wiki-namespace entity representation. Produce a recommendation with tradeoffs.
2. Contact schema: Propose a minimum viable Contact schema that supports future extension (metadata/custom field pattern). Reference Twenty 2.0's extension approach as a prior art comparison point — do NOT copy their schema.
3. CRM audit integration: Determine whether CRM records should emit AuditEvents via the Phase 4 bus or maintain a separate change log. Recommend with rationale.
4. Pulse trigger and format: Recommend one trigger mechanism (cron/event/explicit) and one output format (wiki page/CLI/notification) for PULSE-01. Both can be extended later — pick the simplest first.
5. WhatsApp ToS analysis: Produce a legal/ToS risk assessment of the official Meta Business API for L2's use case. Answer: which account tier is required, what volume limits apply, and what approval flow is mandated for outbound messages.
6. Channel storage model: Recommend whether channel conversations are stored as wiki pages, AuditEvents, or a separate channels table. Justify the choice against the Phase 2 schema.

**Deliverables:**
- A decision record for each of the 6 research tasks above (one recommendation per task, with rationale and tradeoffs).
- Updated REQUIREMENTS.md with v2 requirement IDs (CRM-01 through CRM-N, PULSE-01 through PULSE-N, CHANNELS-01 if applicable) once the scope is confirmed.

**NOT in scope for this research brief:**
- Any v1 implementation.
- Multi-tenant CRM.
- Postgres migration.
- More than one channel integration.
- Automated outbound messaging.
- STT/TTS (D-009).

## 6. Phase Dependencies

The following phase chain must complete before any CRM/Pulse/Channels feature can be built:

- Phase 4 (ATLAS Event Bus) — AuditEvent bus required by Pulse and CRM audit integration
- Phase 5 (Mission & Run Lifecycle) — mission lifecycle required for CRM-to-mission linkage
- Phase 6 (LLM Wiki Runtime) — wiki runtime required for Pulse data aggregation and optional CRM wiki-namespace model
- Phase 7 (API Gateway) — typed REST API required for CRM/Channels API surface

All of Phases 4–7 must be complete before v2 CRM/Pulse work begins.

## 7. Sources

- docs/research/DEEP_RESEARCH_BACKLOG.md — R5 (Pulse), R6 (CRM/Twenty), R7 (WhatsApp/Channels)
- .planning/REQUIREMENTS.md — Future Requirements section (PULSE-01, PULSE-02, CRM-01, CRM-02)
- docs/decisions/2026-06-04_DECISION_REGISTER.md — D-007 (CRM later), D-010 (missing research)
- .planning/phases/03-research-closure/03-RESEARCH.md — RESEARCH-02 pre-analysis
- docs/research/2026-06-04_RESEARCH_SYNTHESIS.md — cross-report CRM/Pulse/Channels state
