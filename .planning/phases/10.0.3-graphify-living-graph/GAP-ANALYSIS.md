# Graphify Gap Analysis — Deep Code Audit

**Date:** 2026-06-19
**Scope:** Full codebase analysis of the Graphify knowledge graph system
**Status:** Read-only audit, no changes made

---

## Executive Summary

Graphify is a **polished but structurally limited** knowledge graph visualization. It scans static markdown files and renders a 3D force-directed graph. The system has strong visual bones (bloom, electricity particles, storm overlay, minimap) but zero runtime integration. The "living graph" vision — neuron connections, nebula storms, wiki/memory integration — requires transforming it from a file scanner into a runtime-aware, event-driven, semantically rich graph system.

---

## Current State — What Exists

### Backend Pipeline

| Layer | File | Lines | Status |
|-------|------|-------|--------|
| Graph builder | `services/agent-runtime/atlas_runtime/graph_service.py` | 335 | **Implemented** |
| CLI | `services/agent-runtime/atlas_runtime/cli/main.py:133-156` | 23 | **Implemented** |
| Gateway endpoint | `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:626-646` | 20 | **Implemented** |
| API client | `services/web-ui-react/src/lib/api.ts:260-304` | 44 | **Implemented** |
| 3D visualization | `services/web-ui-react/src/routes/Graph.tsx` | 943 | **Implemented** |
| Tests | `services/agent-runtime/tests/test_graph_service.py` | 51 | **2 tests** |

### Data Flow (Current)

```
User clicks REBUILD
  → React: getGraph(scope, force=true)
  → Rust gateway: dispatch_atlas_with_timeout(["graph", "build", ...])
  → Python CLI: atlas graph build --root . --scope {scope}
  → graph_service.build_graph(): walks .md files, builds nodes[] + links[]
  → JSON response → 3D force-graph render
```

**Every request triggers a full filesystem rescan.** No incremental updates, no caching at gateway level, no event-driven invalidation.

### Graph Output Format

```python
{
  "nodes": [{"id": str, "label": str, "kind": str, "group": str, "size": int}],
  "links": [{"source": str, "target": str, "kind": str}],
  "root": str, "scope": str,
  "counts": {"nodes": int, "links": int}
}
```

Node IDs are relative POSIX paths. Link kinds: `contains`, `link`, `wikilink`, `decision`, `phase`.

### 4 Scopes

| Scope | Corpus | Cap | Purpose |
|-------|--------|-----|---------|
| `atlas` | `.planning/**/*.md` | 400 | Planning graph |
| `global` | All repo `*.md` | 460 | Full repo graph |
| `projects` | Sibling L2 project `*.md` | 520 | Cross-project graph |
| `obsidian` | Obsidian vault `*.md` | 600 | Knowledge base graph |

### UI Features (Graph.tsx)

- 3D force-directed layout (Three.js + `3d-force-graph`)
- UnrealBloom post-processing (strength 0.72, threshold 0.5, radius 0.3)
- Directional "electricity" particles on cross-reference links
- "Storm Activity" lightning overlay (WebGL FBM noise shader)
- Minimap (secondary WebGL renderer, 168x116px, ~15fps)
- Node search (exact → substring label → substring ID)
- Node inspector panel (kind, label, path, neighbor list)
- 4 scope tabs (Global, Projects, Obsidian, **Agent Context — LOCKED**)
- Graph statistics (nodes, edges, communities, density, avg degree)
- Zoom controls (fit, in 0.78x, out 1.28x)
- Rebuild button (force rescan)

---

## Gap Categories

### GAP-1: No Runtime Entity Integration

**Current:** Graph nodes are markdown files. No connection to SQLite-stored entities (missions, runs, audit_events, wiki_pages, sources, memory_provenance).

**Needed:** Nodes should represent runtime entities with UUID-based IDs, not file paths. The graph should answer: "What decisions led to this wiki page?", "Which runs touched this mission?", "What sources back this claim?"

**Evidence:** `graph_service.py` never imports or reads from SQLite. `wiki_service.py` and `run_service.py` are independent. `MemoryProvenance` model exists but is not wired into graph construction.

**Impact:** The graph is a file explorer, not a knowledge system.

---

### GAP-2: No Incremental Updates / Event-Driven Invalidation

**Current:** Full filesystem rescan on every request. No filesystem watcher, no diffing, no event-driven cache invalidation.

**Needed:** Filesystem watcher (e.g., `watchfiles` Python or `notify` Rust) that invalidates graph cache on file changes. Incremental diff updates — add/remove/modify nodes and links without full rebuild.

**Evidence:** Gateway has no graph cache (`lib.rs:626-646`). Every `GET /v1/graph` spawns a Python CLI process. Client caches per scope but `force=true` bypasses.

**Impact:** O(n) filesystem scan on every UI interaction. Slow for large vaults (600-node cap).

---

### GAP-3: No Temporal Dimension

**Current:** No timestamps, no versioning, no history of graph changes. The "Updated Xm ago" label reflects client fetch time, not data change time.

**Needed:** `created_at` / `modified_at` per node, graph snapshots over time, temporal queries ("what changed since last run?").

**Evidence:** Node format has no timestamp fields. `graph_service.py` reads file content but doesn't store modification times.

**Impact:** No ability to show graph evolution, detect drift, or support time-based queries.

---

### GAP-4: No Semantic Edges

**Current:** All edges are structural (file-to-file via markdown links, wikilinks, decision/phase references). No content-level relationships.

**Needed:** Embedding-based similarity, entity co-occurrence, topic model links. The "neuron" metaphor requires synaptic weights, not binary connections.

**Evidence:** No embedding infrastructure in graph pipeline. `fastembed` is optional in wiki-service but not used by graph. No entity extraction from content.

**Impact:** Graph shows file structure, not knowledge relationships.

---

### GAP-5: No Weight/Strength/Activity

**Current:** All edges are binary. No recency weighting, frequency, access count, or confidence. No concept of "hot" vs "cold" nodes.

**Needed:** Node weight by access frequency (for nebula/storm effects), edge strength by co-occurrence, temporal decay. The "nebula of most-accessed files" requires activity metrics.

**Evidence:** `size` field is raw byte length, not activity. No access tracking in graph pipeline.

**Impact:** Cannot differentiate important nodes from peripheral ones. No basis for visual hierarchy.

---

### GAP-6: No Agent Context Tab

**Current:** The "Agent Context" tab in Graph.tsx is locked (`live: false`). Label says "Coming soon — wires to agent context, wiki, RAG & memory."

**Needed:** This tab should be the primary view — showing the runtime knowledge graph with wiki pages, audit events, mission context, and memory provenance.

**Evidence:** `Graph.tsx:46-50` — tab is disabled. No API endpoint for agent-context graph.

**Impact:** The most valuable graph view is inaccessible.

---

### GAP-7: No Graph Mutations from UI

**Current:** Graph is read-only. No way to create, annotate, or pin nodes/edges from the cockpit.

**Needed:** Operator can annotate nodes, pin important relationships, manually create edges, mark nodes as "trusted" or "needs review."

**Evidence:** No mutation endpoints in gateway. No write operations in graph_service.

**Impact:** Graph is passive visualization, not an interactive knowledge tool.

---

### GAP-8: No Wiki/Memory Integration

**Current:** Graph service reads markdown files, not wiki_pages table. Wiki pages with FTS5 search and semantic search are independent systems.

**Needed:** Graph should traverse wiki pages, link to their sources, show provenance chains, and surface semantic search results as graph nodes.

**Evidence:** `wiki_service.py` operates on SQLite. `graph_service.py` operates on filesystem. No cross-reference between them.

**Impact:** Two knowledge systems that don't talk to each other.

---

### GAP-9: No Graph Persistence / Snapshots

**Current:** `--write` flag caches to `.planning/graphs/graph.json` but gateway never reads from it. No graph tables in SQLite.

**Needed:** SQLite graph tables (`graph_nodes`, `graph_edges`) for persistent graph state, incremental updates, and historical snapshots.

**Evidence:** Research notes (Q4) list SQLite adjacency list as leading candidate but no migration exists.

**Impact:** Graph state is ephemeral. No history, no diffing, no query.

---

### GAP-10: No Cross-Scope Linking

**Current:** Each scope is independent. The `projects` scope sees wikilinks within sibling projects but does not link to nodes in `global` or `obsidian`.

**Needed:** Unified view that can project nodes from multiple scopes with cross-references. A wiki page in `obsidian` that references a decision in `atlas` should show that edge.

**Evidence:** `build_graph()` dispatches to scope-specific builders. No cross-scope join logic.

**Impact:** Fragmented knowledge views. No holistic picture.

---

### GAP-11: No Subgraph Filtering

**Current:** UI loads the full scope. Search is label-only, not graph-structural.

**Needed:** Filter by kind, group, neighborhood depth, or custom query. "Show me all decisions connected to this mission" requires structural filtering.

**Evidence:** `Graph.tsx` search is `nodes.find(n => n.label.includes(query))`. No graph traversal queries.

**Impact:** Large graphs are overwhelming. No way to focus on relevant subgraph.

---

### GAP-12: No Integration with Audit Trail

**Current:** Graph nodes (decisions, phases, states) do not link to run events, audit entries, or mission history.

**Needed:** A decision node should show which runs implemented it. A phase node should show its audit timeline. A mission node should show its full execution trace.

**Evidence:** `audit_events` table has no graph edges. `graph_service.py` doesn't read audit data.

**Impact:** No operational context in the knowledge graph.

---

### GAP-13: No Graph Export

**Current:** No GEXF, GraphML, or Cypher export. Only internal JSON format.

**Needed:** Export for external analysis (Gephi, Neo4j, networkx), sharing, and archival.

**Evidence:** No export endpoints or functions.

**Impact:** Graph data is locked in the application.

---

### GAP-14: No Living Visual Effects (Neuron/Nebula)

**Current:** Nodes are static spheres. Links are straight lines. No pulsing, breathing, or growth animation. No depth-of-field. No organic layout.

**Needed:** The "living neuron" metaphor requires:
- Pulsing radius animation (soma)
- Dendrite-like curved links (Bezier/arc paths)
- Synaptic flash on signal arrival
- Node firing/inactive/refractory states
- Color cycling (polarization animation)
- Depth-of-field blur on distant nodes
- Nebula glow for high-activity clusters

**Evidence:** `3d-force-graph` renders static spheres. No animation hooks in current code. `ogl` (WebGL abstraction) is installed but unused.

**Impact:** Graph looks like a static network diagram, not a living system.

---

### GAP-15: No RAG Integration

**Current:** No connection between graph nodes and LLM retrieval-augmented generation. Wiki semantic search is independent.

**Needed:** Graph should surface RAG results as nodes, show embedding clusters, and provide context for LLM queries. The graph becomes a visual interface for the memory system.

**Evidence:** `semantic_search()` in wiki_service is independent. No graph API for RAG context.

**Impact:** No visual memory interface for the AI operator.

---

## Priority Matrix

| Gap | Impact | Effort | Priority |
|-----|--------|--------|----------|
| GAP-1 (Runtime entities) | Critical | High | P0 |
| GAP-8 (Wiki/memory integration) | Critical | High | P0 |
| GAP-6 (Agent Context tab) | Critical | Medium | P0 |
| GAP-9 (Graph persistence) | High | Medium | P1 |
| GAP-2 (Incremental updates) | High | Medium | P1 |
| GAP-5 (Activity/weight) | High | Low | P1 |
| GAP-14 (Living visual effects) | High | High | P1 |
| GAP-4 (Semantic edges) | High | High | P2 |
| GAP-3 (Temporal dimension) | Medium | Low | P2 |
| GAP-12 (Audit trail integration) | Medium | Medium | P2 |
| GAP-11 (Subgraph filtering) | Medium | Medium | P2 |
| GAP-15 (RAG integration) | Medium | High | P2 |
| GAP-7 (Graph mutations) | Low | Medium | P3 |
| GAP-10 (Cross-scope linking) | Low | High | P3 |
| GAP-13 (Graph export) | Low | Low | P3 |

---

## Architecture Assessment

### What's Strong

1. **Clean data flow:** Python service → Rust gateway → React UI is a solid pattern. The CLI dispatch from Rust is pragmatic and auditable.
2. **Scope system:** 4 scopes with budget caps is well-designed. Prevents browser overload.
3. **Visual foundation:** Bloom, particles, storm overlay, minimap — the visual language is already premium.
4. **D-012 contract enforcement:** Cross-language schema validation ensures Python/Rust stay in sync.
5. **Test pattern:** `test_graph_service.py` uses in-memory SQLite + real file system. Good isolation.

### What Needs Rework

1. **graph_service.py is a file scanner, not a graph database.** The entire service needs to become a SQLite-backed graph builder with incremental updates.
2. **No separation between graph data and graph visualization.** The 3D renderer and the data pipeline are tightly coupled through the JSON format. Need a graph API layer.
3. **Gateway has no caching.** Every request spawns Python. Need either gateway-level cache or Rust-native graph builder (D-022 cementation).
4. **No graph schema.** Node/edge types are implicit in code constants. Need explicit Pydantic models for graph nodes and edges (extending atlas-core).

### Recommended Architecture (Living Graph)

```
┌─────────────────────────────────────────────────────┐
│                  Graphify Engine                     │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ File     │  │ SQLite   │  │ Embedding        │  │
│  │ Scanner  │  │ Graph    │  │ Service          │  │
│  │ (current)│  │ Builder  │  │ (fastembed)      │  │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       │              │                 │             │
│       └──────────────┼─────────────────┘             │
│                      ▼                               │
│            ┌─────────────────┐                       │
│            │  Graph Store    │                       │
│            │  (SQLite + FTS5)│                       │
│            └────────┬────────┘                       │
│                     ▼                                │
│            ┌─────────────────┐                       │
│            │  Graph API      │                       │
│            │  (incremental,  │                       │
│            │   cached,       │                       │
│            │   subscription) │                       │
│            └────────┬────────┘                       │
└─────────────────────┼───────────────────────────────┘
                      ▼
            ┌─────────────────┐
            │  Rust Gateway   │
            │  /v1/graph/*    │
            └────────┬────────┘
                     ▼
            ┌─────────────────┐
            │  React UI       │
            │  (living 3D)    │
            └─────────────────┘
```

---

## Recommendations

### Phase 1: Foundation (Week 1-2)
- Design graph node/edge Pydantic models in atlas-core
- Create SQLite migration for graph_nodes + graph_edges
- Wire graph_service to read from SQLite instead of filesystem
- Implement basic graph queries (neighbors, subgraph, path)

### Phase 2: Runtime Integration (Week 2-3)
- Build entity extractors: missions → nodes, runs → nodes, audit_events → edges, wiki_pages → nodes
- Wire MemoryProvenance into graph edge construction
- Implement the Agent Context tab with runtime entity graph
- Add activity tracking (access counts, timestamps)

### Phase 3: Living Visuals (Week 3-4)
- Implement node animation (pulse, breathe, fire)
- Add curved link rendering (Bezier/arc paths)
- Build synaptic flash effects
- Add depth-of-field and nebula glow for hot clusters
- Wire activity data to visual intensity

### Phase 4: Intelligence (Week 4-5)
- Add embedding-based semantic edges
- Implement subgraph filtering API
- Build graph-to-RAG bridge
- Add temporal queries and graph snapshots
