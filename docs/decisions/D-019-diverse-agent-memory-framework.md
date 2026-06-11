# D-019 — Diverse Efficient Agent Memory Framework

**Date:** 2026-06-08
**Status:** Accepted
**Scope:** L2/ATLAS harness memory architecture — all phases.
**Reference:** `docs/architecture/AGENT_MEMORY_FRAMEWORK_STRATEGY.md`, `docs/architecture/DIVERSE_AGENT_MEMORY_FRAMEWORK.md`
**Foundation principle:** `docs/architecture/HERMES_FIRST_FOUNDATION_PRINCIPLE.md`, D-018

---

## Decision

ATLAS memory will combine Hermes memory, LLM Wiki, local semantic retrieval, graph memory, audit/event memory, and skill memory under a policy-governed memory router.

This is implemented from within the evolved Hermes/L2 foundation, not as an add-on service.

---

## Memory Architecture

```
Hermes profile + session memory     (Layer 1 — preserve from Hermes)
LLM Wiki compiled knowledge         (Layer 2 — enhance in L2/ATLAS foundation)
Local semantic retrieval            (Layer 3 — enhance in L2/ATLAS foundation)
Graph memory                        (Layer 4 — L2 product module)
Audit/event memory                  (Layer 5 — enhance in L2/ATLAS foundation)
Skill/procedure memory              (Layer 6 — enhance in L2/ATLAS foundation)
      ↓
Memory router: task intent + policy + sensitivity + source scope
      ↓
Compressed, cited, provenance-labeled context package
```

---

## Rationale

Most agent harnesses provide one or two of these layers, and none with full provenance, policy labels, or operator visibility. ATLAS' multi-layer, policy-governed memory is a meaningful differentiator for an operator-grade harness.

The goal is not "more context" but better selected, more trustworthy, and more efficient memory:
- Retrieved items carry citations. Agents cannot cite a vector chunk ID; they must cite a wiki slug or source record.
- Sensitive memory is blocked from reaching untrusted/experimental providers.
- Every memory write is linked to an AuditEvent.
- External/untrusted content is wrapped before injection (Odysseus `untrusted_context_message` pattern).
- The operator can inspect, query, and correct any memory item.

---

## Layer Summary

| Layer | Purpose | First implementation |
|-------|---------|---------------------|
| 1. Hermes profile/session | User profile, preferences, session recall | Available (preserve) |
| 2. LLM Wiki | Curated, linted, source-traced project knowledge | Phase 6 |
| 3. Semantic retrieval | Local vector search over wiki/sources | Phase 6 (optional) |
| 4. Graph memory | Relationship-aware traversal — entities, missions, decisions | v2.0 (research in Phase 6) |
| 5. Audit/event | Operational memory, run replay, provenance | Available (Phase 4) |
| 6. Skill/procedure | Reusable workflows, classified skill packs | Phase 9 |

---

## Memory Router

`atlas_core.memory_router.select(context: MemoryRequest) -> MemoryPackage`

Routing decisions are based on: task intent, policy labels, sensitivity classification, and source scope. Full routing table in `docs/architecture/AGENT_MEMORY_FRAMEWORK_STRATEGY.md`.

---

## Non-Negotiable Controls

| Control | Enforcement |
|---------|------------|
| Every memory write has provenance | `MemoryProvenance` record linked to run_id / source_id / AuditEvent |
| Sensitive memory requires policy labels | Written at ingestion time; enforced by router |
| External content marked untrusted | `untrusted: true` on any externally-sourced item; router applies wrapper |
| Vector retrieval does not replace citations | Router returns item_id + citation alongside content |
| Graph edges require source backing | No hallucinated relationships stored as facts |
| Memory is compact | Router compresses and deduplicates before injection; token budget tracked |
| Private memory stays local | No cloud sync without explicit operator action |
| Memory is inspectable and correctable | Phase 7 API: `GET /memory/items/{id}`, `DELETE`, `PATCH` |

---

## Phase Impact

| Phase | Required by this decision |
|-------|--------------------------|
| Phase 6 | Implement Layer 2 (wiki) and Layer 3 (semantic, optional). Add memory provenance schema. Add audit-linked memory updates. Begin graph-memory research. |
| Phase 7 | Expose memory router API: `/memory/query`, `/memory/items`, `/memory/provenance`. |
| Phase 8 | Cockpit memory surface: source browser, wiki browser, inspection, correction, retrieval diagnostics. |
| Phase 9 | Layer 6: skill/procedure memory with classification and provenance. |
| v2.0 | Layer 4: full graph memory with OpenGraph/Graphify. |

---

## Non-Goals

- Do not implement graph memory in Phase 6 (research only).
- Do not build a cloud vector DB requirement — local/sqlite-vec only.
- Do not inject full-text raw context — compressed packages only.
- Do not duplicate Hermes profile/session memory — enhance it, do not replace it.
- Do not allow anonymous memory writes without provenance.
