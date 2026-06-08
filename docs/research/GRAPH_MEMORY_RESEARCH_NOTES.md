# ATLAS Graph Memory — Design Questions (v2.0 Scope)

**Phase:** 6 (research only — no implementation)
**Relates to:** D-019 Memory Framework Layer 4
**Status:** Open questions for v2.0

---

## Overview

This document captures design questions for ATLAS graph memory (Layer 4 of the D-019 diverse
memory framework). Phase 6 implements Layers 2 and 3 (Wiki + optional semantic retrieval).
Layer 4 graph memory is scoped to v2.0. These questions frame the design space without
committing to an implementation.

The MemoryProvenance model introduced in Phase 6 serves as the entry point for reconstructing
decision chains — a foundational prerequisite for graph memory queries.

---

## Design Questions

### Q1: Node/edge schema for mission → run → artifact → source relationships

What is the minimal graph schema that captures the full provenance chain for an ATLAS operation?

- What are the natural node types? Candidates: Mission, Run, AuditEvent, Artifact, Source, WikiPage
- What are the natural edge types? Candidates: produced_by, referenced_by, sourced_from, triggered_by, consumed_by
- Can these edges be derived from existing FK relationships in the SQLite schema (e.g., sources.run_id → runs.id), or do they require a separate extraction pass over the audit log?
- How should the graph handle versioned entities — WikiPage revisions, Source deduplication by SHA-256 — without creating phantom nodes?
- What is the minimal set of node/edge types required to answer "which runs produced this wiki page?"

### Q2: "Which decisions led to this wiki page?" traceability

The primary query motivating graph memory is backward traceability from a knowledge artifact to the decisions that produced it.

- The traceability chain is: AuditEvent → WikiPage → Source (via wiki ingest) and AuditEvent → Run → Mission (via execution)
- What metadata must be stored at write time to reconstruct this chain later? At minimum: wiki_page_id, source_id, run_id, mission_id, and audit_event_id in the MemoryProvenance record
- How does MemoryProvenance (Phase 6) serve as the entry point for this trace? The provenance record links a WikiPage update to a specific Run, making it the lowest-cost anchor for graph edge reconstruction
- Can the existing AuditEvent.payload field store enough context to reconstruct edges without a dedicated graph extraction pass?
- What is the acceptable latency for a "trace this wiki page to its origin" query at 1,000 pages / 10,000 audit events scale?

### Q3: Graphify-style extraction from existing ATLAS artifacts

ATLAS already uses the `.planning/graphs/graph.json` format (Graphify-style entity-relationship extraction). Can this pipeline be extended to production artifacts?

- The existing `.planning/graphs/` pattern extracts entities and relationships from planning documents using a Graphify-compatible JSON format
- Can the same extraction pipeline produce edges from wiki pages, audit events, and source documents without a separate graph database dependency?
- What entity resolution is needed to link Graphify-extracted terms (free-text entity names) to Mission/Source UUIDs stored in SQLite?
- Is the Graphify extraction approach complementary to a structured FK-based graph, or does it create a parallel schema with reconciliation overhead?
- What is the minimum extraction quality (precision/recall on entity linking) required for graph memory to be useful vs. noise-generating?

### Q4: Storage backend options

Three storage approaches are viable at ATLAS scale (single-operator, local, v1.0 SQLite constraint):

- **Option A: SQLite adjacency list table** — Add `graph_nodes` and `graph_edges` tables to the existing SQLite schema (consistent with D-003, no new dependency, queryable via standard SQL). Supports "which decisions led to this wiki page?" via a recursive CTE or multi-join query.
- **Option B: Embedded graph library** (networkx, igraph) — Richer graph algorithms (shortest path, centrality, reachability). Python-only; requires in-memory load on startup; not persistent without a separate serialization layer; adds a new required dependency.
- **Option C: Extend Graphify .json format** — Consistent with existing `.planning/graphs/` usage; zero new infrastructure; limited to static snapshots; no live query capability; no FK integrity.

Recommendation criterion: choose the option that adds least new infrastructure while supporting the "which decisions led to this wiki page?" query at the expected ATLAS v1.0 scale. Option A (SQLite adjacency list) is the leading candidate — it extends D-003 without new dependencies and supports recursive queries natively.

---

## Out of Scope (Phase 6)

The following are explicitly deferred to v2.0 and must not be implemented in Phase 6:

- Graph schema implementation (nodes/edges tables or adjacency list)
- Graph extraction pipeline from wiki pages, audit events, or source documents
- Graph query API (no new endpoints, no Python graph query functions)
- Graph visualization surface (no UI components or rendering logic)
- Graphify extraction integration into production artifact pipeline
- Memory router graph-layer policy (deferred to Phase 7 memory API)

---

## Next Steps (v2.0)

- Answer Q4 via a short spike: implement the "which decisions led to this wiki page?" query using Option A (SQLite adjacency list) on a representative dataset from Phase 6 test fixtures
- Design the node/edge schema based on Q1 findings, constrained to entities already in the SQLite schema
- Implement graph edge extraction from AuditEvent + WikiPage rows using MemoryProvenance as the anchor
- Expose the graph query as a Phase 7 API extension (e.g., GET /wiki/{page_id}/provenance/graph)
- Evaluate whether Graphify extraction adds value over FK-derived edges at ATLAS v1.0 artifact volume
