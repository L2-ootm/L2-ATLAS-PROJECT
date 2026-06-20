# Living Graph System — Design Specification

**Date:** 2026-06-19
**Author:** MiMoCode (analysis + design)
**Status:** DRAFT — Awaiting operator review
**Phase:** 10.0.3 (in-flight, ahead of spine)

---

## 1. Vision

Transform Graphify from a static markdown file scanner into a **living knowledge graph** — a runtime-aware, event-driven, semantically rich graph system that visualizes the ATLAS knowledge ecosystem as interconnected neurons with synaptic activity, nebula storms for high-traffic areas, and full integration with the wiki/memory/audit pipeline.

The graph becomes the **visual interface for the memory system** — not a separate visualization, but the primary way the operator navigates, understands, and interacts with the knowledge base.

---

## 2. Design Principles

1. **Graph as memory interface.** Every node is a real entity (mission, run, wiki page, decision, source, audit event). Every edge has a provenance chain. The graph IS the memory, not a representation of it.

2. **Living, not static.** Nodes pulse with activity. Links flash with synaptic signals. Hot clusters glow with nebula intensity. The graph breathes with the operational heartbeat of the system.

3. **SQLite-native.** All graph state lives in SQLite (D-003). No external graph database. Recursive CTEs for traversal. Consistent with the single-datastore architecture.

4. **Incremental, not episodic.** Graph updates are event-driven. File changes, audit events, wiki writes — each triggers targeted graph mutations, not full rescans.

5. **Embedding-aware.** Semantic similarity creates edges that structural analysis misses. The graph discovers relationships that the operator didn't know existed.

6. **Operator-interactive.** The operator can annotate, pin, filter, and query the graph. It's a tool, not a display.

---

## 3. Entity Model

### 3.1 Node Types

| Node Type | Source | ID | Fields |
|-----------|--------|----|--------|
| `mission` | missions table | UUID | label, status, created_at, updated_at, project_id |
| `run` | runs table | UUID | label, status, agent_runtime, started_at, completed_at, mission_id |
| `wiki_page` | wiki_pages table | UUID | slug, title, version, created_at, updated_at, source_id |
| `source` | sources table | UUID | path, sha256, size_bytes, ingested_at, untrusted |
| `decision` | ADR files (extracted) | `D-{n}` | title, status (accepted/locked), file_path, defined_at |
| `phase` | ROADMAP.md (extracted) | `P-{n}` | title, status, milestone, file_path |
| `audit_event` | audit_events table | UUID | event_type, timestamp, run_id, data_summary |
| `skill` | skills registry | slug | name, category, status, file_path |
| `artifact` | artifacts table | UUID | path, mime_type, size_bytes, run_id |
| `doc` | markdown files (extracted) | relative_path | title, kind, group, size_bytes, modified_at |
| `folder` | directory structure | `dir:{path}` | name, depth, file_count |

### 3.2 Edge Types

| Edge Type | Source | Meaning | Weight Basis |
|-----------|--------|---------|--------------|
| `contains` | directory structure | folder contains file/node | structural (binary) |
| `wikilink` | `[[...]]` references | wiki-style cross-reference | frequency |
| `markdown_link` | `[...](path)` references | explicit markdown link | frequency |
| `decision_ref` | `D-NNN` mentions | document references decision | frequency |
| `phase_ref` | `Phase N` mentions | document references phase | frequency |
| `produced_by` | FK: artifact.run_id | artifact produced by run | binary |
| `sourced_from` | FK: wiki_page.source_id | wiki page derived from source | binary |
| `triggered_by` | FK: run.mission_id | run triggered by mission | binary |
| `audit_link` | FK: audit_event.run_id | audit event belongs to run | binary |
| `provenance` | memory_provenance records | memory write traced to source/run | binary |
| `semantic` | embedding similarity | content-level similarity | cosine distance |
| `co_occurrence` | entity co-occurrence in text | entities mentioned together | frequency |
| `temporal` | time-proximity in runs | events happening in same time window | recency decay |

### 3.3 Graph Schema (Pydantic)

```python
# In packages/atlas-core/atlas_core/schemas/graph.py

class GraphNode(BaseModel, frozen=True):
    id: str                    # UUID or synthetic ID
    node_type: str             # mission|run|wiki_page|source|decision|phase|...
    label: str                 # Human-readable name
    metadata: dict[str, str]   # Type-specific fields (JSON-serializable)
    created_at: str            # ISO 8601
    modified_at: str           # ISO 8601
    activity_score: float      # 0.0-1.0, computed from access frequency + recency
    embedding: list[float] | None  # Optional vector for semantic queries

class GraphEdge(BaseModel, frozen=True):
    id: str                    # UUID
    source_id: str             # Node ID
    target_id: str             # Node ID
    edge_type: str             # contains|wikilink|semantic|provenance|...
    weight: float              # 0.0-1.0, strength/frequency
    metadata: dict[str, str]   # Type-specific fields
    created_at: str            # ISO 8601
    source_backed: bool        # True if edge has provenance chain (D-019)

class GraphSnapshot(BaseModel, frozen=True):
    id: str                    # UUID
    scope: str                 # atlas|global|projects|obsidian|agent_context
    node_count: int
    edge_count: int
    captured_at: str           # ISO 8601
    hash: str                  # Content hash for change detection
```

---

## 4. Storage Layer

### 4.1 SQLite Tables

```sql
-- Migration: 0009_graph_memory.sql

CREATE TABLE IF NOT EXISTS graph_nodes (
    id              TEXT PRIMARY KEY,
    node_type       TEXT NOT NULL,
    label           TEXT NOT NULL,
    metadata        TEXT NOT NULL DEFAULT '{}',  -- JSON
    created_at      TEXT NOT NULL,
    modified_at     TEXT NOT NULL,
    activity_score  REAL NOT NULL DEFAULT 0.0,
    embedding       BLOB,  -- Optional: sqlite-vec compatible
    scope           TEXT NOT NULL DEFAULT 'global'
);

CREATE INDEX idx_graph_nodes_type ON graph_nodes(node_type);
CREATE INDEX idx_graph_nodes_scope ON graph_nodes(scope);
CREATE INDEX idx_graph_nodes_activity ON graph_nodes(activity_score DESC);

CREATE TABLE IF NOT EXISTS graph_edges (
    id              TEXT PRIMARY KEY,
    source_id       TEXT NOT NULL REFERENCES graph_nodes(id),
    target_id       TEXT NOT NULL REFERENCES graph_nodes(id),
    edge_type       TEXT NOT NULL,
    weight          REAL NOT NULL DEFAULT 1.0,
    metadata        TEXT NOT NULL DEFAULT '{}',  -- JSON
    created_at      TEXT NOT NULL,
    source_backed   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_graph_edges_source ON graph_edges(source_id);
CREATE INDEX idx_graph_edges_target ON graph_edges(target_id);
CREATE INDEX idx_graph_edges_type ON graph_edges(edge_type);

CREATE TABLE IF NOT EXISTS graph_snapshots (
    id              TEXT PRIMARY KEY,
    scope           TEXT NOT NULL,
    node_count      INTEGER NOT NULL,
    edge_count      INTEGER NOT NULL,
    captured_at     TEXT NOT NULL,
    hash            TEXT NOT NULL
);

CREATE INDEX idx_graph_snapshots_scope ON graph_snapshots(scope);

-- FTS5 for graph node search
CREATE VIRTUAL TABLE IF NOT EXISTS graph_nodes_fts USING fts5(
    label,
    metadata,
    content=graph_nodes,
    content_rowid=rowid
);
```

### 4.2 Recursive CTE Queries

```sql
-- Find all nodes within N hops of a given node
WITH RECURSIVE neighborhood AS (
    SELECT id, 0 AS depth FROM graph_nodes WHERE id = :start_id
    UNION
    SELECT e.target_id, n.depth + 1
    FROM graph_edges e
    JOIN neighborhood n ON e.source_id = n.id
    WHERE n.depth < :max_depth
)
SELECT * FROM neighborhood;

-- Find shortest path between two nodes
WITH RECURSIVE path AS (
    SELECT id, id AS path_ids, 0 AS depth
    FROM graph_nodes WHERE id = :start_id
    UNION
    SELECT e.target_id, p.path_ids || '->' || e.target_id, p.depth + 1
    FROM graph_edges e
    JOIN path p ON e.source_id = p.id
    WHERE p.depth < 10
)
SELECT path_ids FROM path WHERE id = :end_id LIMIT 1;

-- Find most connected nodes (hubs)
SELECT n.id, n.label, n.node_type, COUNT(e.id) AS degree
FROM graph_nodes n
LEFT JOIN graph_edges e ON n.id = e.source_id OR n.id = e.target_id
GROUP BY n.id
ORDER BY degree DESC
LIMIT 20;
```

---

## 5. Graph Engine

### 5.1 Entity Extractors

Each extractor reads from a specific data source and produces graph nodes/edges:

| Extractor | Source | Produces |
|-----------|--------|----------|
| `MissionExtractor` | missions table | mission nodes + triggered_by edges to runs |
| `RunExtractor` | runs table | run nodes + audit_link edges to audit_events |
| `WikiExtractor` | wiki_pages + sources tables | wiki_page nodes + sourced_from edges + provenance edges |
| `DecisionExtractor` | ADR files (markdown scan) | decision nodes + decision_ref edges |
| `PhaseExtractor` | ROADMAP.md (markdown scan) | phase nodes + phase_ref edges |
| `AuditExtractor` | audit_events table | audit_event nodes + temporal edges |
| `FileExtractor` | filesystem (markdown) | doc nodes + wikilink/markdown_link edges |
| `SemanticExtractor` | embeddings (fastembed) | semantic edges between similar nodes |
| `ActivityExtractor` | access logs + timestamps | activity_score updates |

### 5.2 Graph Builder Pipeline

```
1. INCREMENTAL CHECK
   - Compare file mtimes / DB timestamps against last snapshot
   - Identify changed entities since last build

2. EXTRACT (per changed entity type)
   - Run relevant extractors
   - Produce new/updated nodes + edges

3. RESOLVE
   - Entity resolution: link extracted free-text terms to UUID nodes
   - Deduplication: merge nodes representing the same entity
   - Validate: ensure all edge endpoints exist

4. EMBED (optional, background)
   - Compute embeddings for new/updated wiki_page nodes
   - Find semantic neighbors via cosine similarity
   - Create/update semantic edges

5. PERSIST
   - Upsert nodes + edges into SQLite
   - Record snapshot
   - Emit audit event for graph mutation

6. NOTIFY
   - Push update to connected UI clients via SSE
```

### 5.3 Activity Scoring

```python
def compute_activity_score(node_id: str, conn: sqlite3.Connection) -> float:
    """Compute 0.0-1.0 activity score based on access frequency and recency."""
    row = conn.execute("""
        SELECT
            COUNT(ae.id) AS event_count,
            MAX(ae.timestamp) AS last_access,
            -- Decay: events lose weight exponentially over 30 days
            SUM(EXP(-0.1 * (julianday('now') - julianday(ae.timestamp)))) AS decayed_weight
        FROM audit_events ae
        WHERE ae.data LIKE '%' || :node_id || '%'
           OR ae.run_id IN (
               SELECT r.id FROM runs r
               WHERE r.mission_id = :node_id
                  OR r.id = :node_id
           )
    """, {"node_id": node_id}).fetchone()

    if not row or row["event_count"] == 0:
        return 0.0

    # Normalize: log-scaled event count * decayed weight
    raw = math.log1p(row["event_count"]) * row["decayed_weight"]
    # Clamp to 0.0-1.0 using sigmoid
    return 1.0 / (1.0 + math.exp(-raw + 3))  # Centered at ~3 events
```

---

## 6. Living Visual Effects

### 6.1 Node States

| State | Visual | Trigger |
|-------|--------|---------|
| **Resting** | Dim sphere, subtle pulse | Default state |
| **Active** | Bright glow, rapid pulse | Recent access (< 5 min) |
| **Firing** | Bright flash, expanding ring | New audit event or wiki write |
| **Refractory** | Fading afterglow | Post-firing cooldown (10s) |
| **Hot** | Nebula glow halo | High activity_score (> 0.7) |
| **Cold** | Near-invisible, no pulse | No activity for > 7 days |

### 6.2 Link Effects

| Effect | Visual | Trigger |
|--------|--------|---------|
| **Synaptic flash** | Bright particle burst along link | Signal propagation (event affecting connected node) |
| **Electricity** | Continuous particle flow | Persistent active connection |
| **Dendrite** | Curved Bezier path | Structural links (contains, wikilink) |
| **Axon** | Straight bright line | Semantic/provenance links |
| **Dormant** | Thin, dim line | No recent activity on link |

### 6.3 Nebula Storm

The "nebula" effect for high-activity clusters:
- Cluster nodes with `activity_score > 0.5` within 2 hops
- Apply `Lightning` shader with intensity proportional to cluster activity
- Add bloom glow around cluster centroid
- Particle density increases with cluster heat
- Color shifts from celestial blue (cool) to violet (hot) to error red (critical)

### 6.4 Implementation Approach

Use `3d-force-graph` custom node/link rendering:

```typescript
// Custom node sphere with animation
nodeThreeObject={(node) => {
  const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(nodeSize(node)),
    new THREE.MeshPhongMaterial({
      color: nodeColor(node),
      emissive: nodeEmissive(node),
      emissiveIntensity: activityToIntensity(node.activity_score),
      transparent: true,
      opacity: activityToOpacity(node.activity_score),
    })
  )
  // Pulse animation via requestAnimationFrame
  sphere.userData.animate = (time: number) => {
    const pulse = Math.sin(time * pulseSpeed(node)) * 0.1 + 1
    sphere.scale.setScalar(pulse)
    sphere.material.emissiveIntensity = activityToIntensity(node.activity_score) * pulse
  }
  return sphere
}}

// Custom link with curved path
linkThreeObject={(link) => {
  const curve = new THREE.QuadraticBezierCurve3(
    sourcePos, midPoint, targetPos
  )
  const geometry = new THREE.TubeGeometry(curve, 20, linkWidth, 8, false)
  return new THREE.Mesh(geometry, linkMaterial(link))
}}
```

---

## 7. API Surface

### 7.1 New Gateway Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/graph/entities` | GET | List all graph nodes (paginated, filterable) |
| `/v1/graph/entities/{id}` | GET | Get node + neighbors |
| `/v1/graph/edges` | GET | List edges (filterable by type, source, target) |
| `/v1/graph/subgraph` | POST | Get subgraph within N hops of given node(s) |
| `/v1/graph/path` | GET | Find shortest path between two nodes |
| `/v1/graph/hubs` | GET | Most connected nodes (hubs) |
| `/v1/graph/activity` | GET | Activity scores + hot clusters |
| `/v1/graph/snapshots` | GET | Historical graph snapshots |
| `/v1/graph/rebuild` | POST | Trigger incremental graph rebuild |
| `/v1/graph/export` | GET | Export as GEXF/GraphML |
| `/v1/graph/stream` | GET (SSE) | Real-time graph mutation stream |

### 7.2 Graph Query API (Python)

```python
# In services/agent-runtime/atlas_runtime/graph_engine.py

class GraphEngine:
    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock):
        self.conn = conn
        self.lock = lock

    def get_node(self, node_id: str) -> GraphNode | None: ...
    def get_neighbors(self, node_id: str, depth: int = 1, edge_types: list[str] | None = None) -> list[GraphNode]: ...
    def get_subgraph(self, node_ids: list[str], depth: int = 2) -> dict: ...
    def find_path(self, start_id: str, end_id: str, max_depth: int = 10) -> list[str] | None: ...
    def get_hubs(self, limit: int = 20) -> list[GraphNode]: ...
    def get_hot_clusters(self, threshold: float = 0.5) -> list[dict]: ...
    def search_nodes(self, query: str, node_types: list[str] | None = None) -> list[GraphNode]: ...
    def rebuild(self, scope: str, incremental: bool = True) -> dict: ...
    def export_gexf(self, scope: str) -> str: ...
```

---

## 8. Integration Points

### 8.1 Wiki Integration

- `update_wiki_page()` triggers graph mutation: upsert wiki_page node + sourced_from edge
- `search_wiki()` results include graph node IDs for visual navigation
- `semantic_search()` creates semantic edges between similar wiki pages
- Wiki lint results surface as graph node metadata (quality_score)

### 8.2 Audit Integration

- Every `emit()` in audit_service checks if affected nodes exist in graph
- New audit_event nodes linked to their run node
- Activity scores updated on each audit event
- Graph mutation itself emits an audit_event (audit of the audit)

### 8.3 Memory Provenance Integration

- `MemoryProvenance` records create `provenance` edges in graph
- "Which decisions led to this wiki page?" = traverse provenance edges from wiki_page node to decision nodes
- Memory router uses graph topology to select relevant context layers

### 8.4 Console Integration

- `context.graph` window in Console workbench shows mini-graph of current context
- Mission console shows mission node + connected entities
- Chat context includes graph neighborhood of current topic

### 8.5 RAG Integration

- Embedding service creates semantic edges between content-similar nodes
- Graph neighborhoods provide context for LLM retrieval
- "Related documents" sidebar in wiki pages uses graph traversal
- Memory router uses graph proximity to augment retrieval

---

## 9. Migration Strategy

### Phase 1: Foundation (Non-breaking)
- Add `graph_nodes` + `graph_edges` tables (migration 0009)
- Add `graph.py` schema to atlas-core
- Keep existing `graph_service.py` as fallback
- Add `graph_engine.py` alongside (new, reads from SQLite)

### Phase 2: Entity Wiring (Additive)
- Build extractors, wire to existing services
- Populate graph from existing data (missions, runs, wiki_pages, etc.)
- Enable Agent Context tab in UI (reads from new engine)

### Phase 3: Living Visuals (UI-only)
- Replace static 3D spheres with animated custom objects
- Add curved link rendering
- Wire activity scores to visual intensity
- Implement nebula storm for hot clusters

### Phase 4: Intelligence (Optional)
- Enable embedding-based semantic edges
- Implement subgraph filtering
- Build graph-to-RAG bridge
- Add export functionality

---

## 10. Testing Strategy

### Unit Tests
- GraphEngine CRUD operations (in-memory SQLite)
- Entity extractors (mock data sources)
- Activity score computation
- Graph query correctness (neighborhood, path, hubs)

### Integration Tests
- Full rebuild pipeline (extract → resolve → persist → query)
- Incremental update (change entity → verify graph mutation)
- Cross-scope linking (wiki_page in obsidian references decision in atlas)

### Contract Tests
- D-012 pattern: validate graph API responses against Pydantic schemas
- SSE stream format validation

### Visual Tests
- Playwright screenshots of living graph states (resting, active, firing, hot)
- Nebula storm visual regression tests

---

## 11. Dependencies

| Dependency | Purpose | Status |
|------------|---------|--------|
| `sqlite-vec` | Vector embeddings in SQLite | Optional (graceful degradation) |
| `fastembed` | Text embedding computation | Optional (graceful degradation) |
| `watchfiles` | Filesystem watching (Python) | New, for incremental updates |
| `three` + `3d-force-graph` | 3D visualization | Already installed |
| `ogl` | Lightweight WebGL (alternative renderer) | Already installed, unused |

---

## 12. Open Questions

1. **Embedding model choice.** fastembed defaults to BAAI/bge-small-en-v1.5. Is this appropriate for ATLAS domain content (planning docs, decisions, technical specs)?

2. **Graph size budget.** Current caps are 400-600 nodes. With runtime entities, the graph could grow much larger. What's the browser performance ceiling? Should we use LOD (level-of-detail) rendering?

3. **Real-time vs batch.** Should graph mutations happen synchronously on each audit event, or batched (e.g., every 5 seconds)? Batched reduces UI thrashing but adds latency.

4. **Rust cementation priority.** D-022 says Rust-first for new infrastructure. Should the graph engine be built in Rust from the start (adding to atlas-gateway crate), or built in Python first and cemented later?

5. **Console graph window.** The `context.graph` placeholder in Console.tsx — should this show a mini-graph of the current mission's entity neighborhood, or a full graph view in a smaller viewport?

6. **Export format priority.** GEXF (for Gephi), GraphML (general), or Cypher (for Neo4j)? Which is most useful for the operator's workflow?
