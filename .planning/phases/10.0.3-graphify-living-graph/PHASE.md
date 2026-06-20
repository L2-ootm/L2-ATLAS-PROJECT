# Phase 10.0.3-LG: Living Graph System

**Date:** 2026-06-19
**Milestone:** v1.0.5 Mass-Adoption Launch Wedge
**Parent Phase:** 10.0.3 (ATLAS Identity & Cockpit Redesign)
**Status:** PLANNED — awaiting operator approval

---

## Objective

Transform the Graphify knowledge graph from a static markdown file scanner into a **living, runtime-aware, semantically rich graph system** that visualizes the ATLAS knowledge ecosystem as interconnected neurons with synaptic activity and nebula storms for high-traffic areas.

## Success Criteria

1. Graph nodes represent real runtime entities (missions, runs, wiki pages, decisions, audit events) — not just markdown files
2. Graph updates incrementally on file changes, wiki writes, and audit events — no full rescans
3. Nodes pulse with activity, links flash with synaptic signals, hot clusters glow with nebula intensity
4. Agent Context tab is live and shows the runtime knowledge graph
5. Graph integrates with wiki/memory/audit pipeline via provenance chains
6. All graph state persists in SQLite with recursive CTE traversal support

## Non-Goals (This Phase)

- Full RAG integration (deferred to Phase 10.0.4+)
- Rust cementation of graph engine (deferred to D-022 L1)
- CRM/Pulse/Voice integration (v2.0 scope)
- Graph mutations from UI (operator annotation) — deferred

---

## Work Packages

### WP-1: Graph Schema & Storage (Foundation)

**Files to create/modify:**
- `packages/atlas-core/atlas_core/schemas/graph.py` — NEW: GraphNode, GraphEdge, GraphSnapshot Pydantic models
- `infra/migrations/0009_graph_memory.sql` — NEW: graph_nodes, graph_edges, graph_snapshots tables + FTS5
- `services/agent-runtime/atlas_runtime/graph_engine.py` — NEW: GraphEngine class with CRUD + queries

**Acceptance:**
- [ ] Pydantic models pass frozen + JSON-serialization tests
- [ ] Migration applies cleanly on fresh DB
- [ ] GraphEngine CRUD operations pass with in-memory SQLite
- [ ] Recursive CTE queries return correct results

**Estimated effort:** 2-3 days

---

### WP-2: Entity Extractors

**Files to create:**
- `services/agent-runtime/atlas_runtime/graph_extractors/__init__.py`
- `services/agent-runtime/atlas_runtime/graph_extractors/mission.py` — missions → nodes + triggered_by edges
- `services/agent-runtime/atlas_runtime/graph_extractors/run.py` — runs → nodes + audit_link edges
- `services/agent-runtime/atlas_runtime/graph_extractors/wiki.py` — wiki_pages + sources → nodes + sourced_from + provenance edges
- `services/agent-runtime/atlas_runtime/graph_extractors/decision.py` — ADR files → decision nodes + decision_ref edges
- `services/agent-runtime/atlas_runtime/graph_extractors/phase.py` — ROADMAP.md → phase nodes + phase_ref edges
- `services/agent-runtime/atlas_runtime/graph_extractors/audit.py` — audit_events → nodes + temporal edges
- `services/agent-runtime/atlas_runtime/graph_extractors/file.py` — markdown files → doc nodes + wikilink/markdown_link edges
- `services/agent-runtime/atlas_runtime/graph_extractors/activity.py` — access logs → activity_score updates

**Acceptance:**
- [ ] Each extractor produces valid GraphNode/GraphEdge instances
- [ ] Extractors handle empty/missing data gracefully
- [ ] Entity resolution links free-text terms to UUID nodes
- [ ] Integration tests verify full extraction pipeline

**Estimated effort:** 3-4 days

---

### WP-3: Graph Builder Pipeline

**Files to create/modify:**
- `services/agent-runtime/atlas_runtime/graph_engine.py` — ADD: rebuild() method with incremental check
- `services/agent-runtime/atlas_runtime/graph_service.py` — MODIFY: delegate to GraphEngine for SQLite-backed builds

**Acceptance:**
- [ ] `rebuild(scope, incremental=True)` skips unchanged entities
- [ ] `rebuild(scope, incremental=False)` full rebuild
- [ ] Existing `build_graph()` function still works (backward compatible)
- [ ] Graph mutations emit AuditEvents

**Estimated effort:** 2-3 days

---

### WP-4: Gateway Endpoints

**Files to modify:**
- `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs` — ADD: new graph endpoints

**New endpoints:**
- `GET /v1/graph/entities` — list nodes (paginated, filterable)
- `GET /v1/graph/entities/{id}` — get node + neighbors
- `GET /v1/graph/subgraph` — subgraph within N hops
- `GET /v1/graph/path` — shortest path
- `GET /v1/graph/hubs` — most connected nodes
- `GET /v1/graph/activity` — activity scores
- `POST /v1/graph/rebuild` — trigger rebuild

**Acceptance:**
- [ ] All endpoints return valid JSON matching Pydantic schemas
- [ ] D-012 contract tests pass
- [ ] Existing `/v1/graph` endpoint still works

**Estimated effort:** 2-3 days

---

### WP-5: Activity Scoring

**Files to create/modify:**
- `services/agent-runtime/atlas_runtime/graph_engine.py` — ADD: compute_activity_score()

**Acceptance:**
- [ ] Activity scores update on audit events
- [ ] Scores decay over time (30-day half-life)
- [ ] Hot clusters identified (score > 0.5 within 2 hops)

**Estimated effort:** 1 day

---

### WP-6: Agent Context Tab (UI)

**Files to modify:**
- `services/web-ui-react/src/lib/api.ts` — ADD: new graph API functions
- `services/web-ui-react/src/routes/Graph.tsx` — MODIFY: enable Agent Context tab, wire to new endpoints

**Acceptance:**
- [ ] Agent Context tab is live (no longer locked)
- [ ] Shows runtime entities (missions, runs, wiki pages, decisions)
- [ ] Node click shows entity details from SQLite
- [ ] Graph updates via SSE on rebuild

**Estimated effort:** 2-3 days

---

### WP-7: Living Visual Effects

**Files to modify:**
- `services/web-ui-react/src/routes/Graph.tsx` — MODIFY: custom node/link rendering

**Acceptance:**
- [ ] Nodes pulse with activity (requestAnimationFrame animation)
- [ ] Links render as curved Bezier paths (dendrites)
- [ ] Synaptic flash on node firing (new audit event)
- [ ] Nebula glow for hot clusters (activity_score > 0.7)
- [ ] Cold nodes are near-invisible
- [ ] Performance: 60fps at 500 nodes

**Estimated effort:** 3-4 days

---

### WP-8: Tests

**Files to create/modify:**
- `services/agent-runtime/tests/test_graph_engine.py` — NEW: engine CRUD + query tests
- `services/agent-runtime/tests/test_graph_extractors.py` — NEW: extractor tests
- `services/agent-runtime/tests/test_graph_service.py` — MODIFY: add integration tests
- `native/atlas-core-rs/crates/atlas-gateway/tests/api.rs` — ADD: new endpoint tests

**Acceptance:**
- [ ] Unit tests pass for all new modules
- [ ] Integration tests verify full pipeline
- [ ] Contract tests validate API responses
- [ ] Coverage ≥ 80% for new code

**Estimated effort:** 2-3 days

---

## Total Estimated Effort

**19-24 days** (approximately 4 weeks)

| WP | Days | Dependencies |
|----|------|--------------|
| WP-1: Schema & Storage | 2-3 | None |
| WP-2: Entity Extractors | 3-4 | WP-1 |
| WP-3: Builder Pipeline | 2-3 | WP-1, WP-2 |
| WP-4: Gateway Endpoints | 2-3 | WP-1 |
| WP-5: Activity Scoring | 1 | WP-1 |
| WP-6: Agent Context Tab | 2-3 | WP-4 |
| WP-7: Living Visuals | 3-4 | WP-6 |
| WP-8: Tests | 2-3 | All WPs |

**Parallelization opportunities:**
- WP-4 (gateway) can run in parallel with WP-2 (extractors) after WP-1
- WP-5 (activity) can run in parallel with WP-2
- WP-7 (visuals) can start after WP-6 is partially done

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Browser performance with 500+ animated nodes | Medium | High | LOD rendering, node batching, reduce animation on low-end devices |
| Embedding quality for ATLAS domain content | Medium | Medium | Start with FTS5-only, add embeddings as optional enhancement |
| Incremental update correctness | Low | High | Full rebuild as fallback, content hashing for change detection |
| Gateway endpoint latency | Low | Medium | Cache at gateway level, async rebuild |

---

## Dependencies on Other Phases

- **WP-1 depends on:** Migration 0008 (mission_archive) must be applied first
- **WP-4 depends on:** Existing gateway code (Phase 7) must be stable
- **WP-6 depends on:** React pivot (D-023) must be far enough along
- **WP-7 depends on:** Three.js + 3d-force-graph (already installed)

---

## ADR Candidates

This phase should produce decisions for:

1. **D-025: Graph storage backend** — SQLite adjacency list (recommended) vs embedded graph library vs JSON snapshots
2. **D-026: Graph update strategy** — Event-driven incremental vs periodic batch vs on-demand rebuild
3. **D-027: Graph entity schema** — Node/edge type definitions, metadata format, embedding storage
4. **D-028: Living visual language** — Animation states, color mapping, nebula effect parameters
