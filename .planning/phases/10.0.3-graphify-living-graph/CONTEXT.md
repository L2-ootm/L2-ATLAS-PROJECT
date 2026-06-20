# Living Graph — Context Document

**Date:** 2026-06-19
**Source:** Full codebase analysis (5 parallel explore agents)

---

## What the Operator Wants

> "Estou tentando transformar ele num sistema vivo que pareça realmente conexões de neurônios, com nebula de tempestade dos arquivos mais acessados, para depois integrar isso com um LLM Wiki RAG, vetorização de memória e esse tipo de coisa"

Translation: Transform the Graphify system into a living system that looks like real neuron connections, with nebula storms for the most-accessed files, then integrate with LLM Wiki RAG, memory vectorization, and similar capabilities.

---

## Current Graphify — What Exists

### Backend (Python)
- **graph_service.py** (335 lines): Walks markdown directories, builds `{nodes, links}` JSON
- **4 scopes**: atlas (.planning/), global (repo), projects (sibling L2), obsidian (vault)
- **Node budget**: 400-600 nodes per scope
- **Node types**: docs, folders, classified by directory (phase, milestone, prep, research) and filename (roadmap, state, project, requirements)
- **Edge types**: contains, link, wikilink, decision, phase
- **No SQLite integration**: reads filesystem, not the database
- **No incremental updates**: full rescan on every request
- **No temporal data**: no timestamps, no versioning, no history

### Gateway (Rust)
- **GET /v1/graph?scope={scope}**: dispatches to Python CLI, 180s timeout
- **No caching**: every request spawns Python process
- **No write operations**: graph is read-only

### UI (React/Three.js)
- **3d-force-graph**: 3D force-directed layout
- **UnrealBloom**: post-processing glow (strength 0.72)
- **Electricity particles**: directional particles on cross-reference links
- **Storm Activity**: WebGL lightning shader overlay
- **Minimap**: secondary WebGL renderer (168x116px)
- **Search**: label-only (exact → substring)
- **Inspector**: node details + neighbor list
- **4 tabs**: Global, Projects, Obsidian, **Agent Context (LOCKED)**
- **943 lines** in Graph.tsx

### What's Missing for "Living Graph"

| Category | Gap | Impact |
|----------|-----|--------|
| **Runtime entities** | Nodes are files, not missions/runs/wiki/audit | Can't show operational context |
| **Incremental updates** | Full rescan on every request | Slow, no real-time feel |
| **Activity tracking** | No access counts, no hot/cold | Can't drive nebula effects |
| **Semantic edges** | No embedding similarity | Missing knowledge relationships |
| **Temporal data** | No timestamps, no history | Can't show evolution |
| **Wiki integration** | Graph reads files, wiki reads SQLite | Two disconnected systems |
| **Agent Context tab** | Locked in UI | Most valuable view inaccessible |
| **Living animation** | Static spheres, straight lines | Doesn't look like neurons |
| **Graph persistence** | Ephemeral JSON, no SQLite tables | No queries, no history |
| **Subgraph filtering** | Full scope only, no focus | Overwhelming at scale |

---

## Related Systems

### Wiki Service (wiki_service.py, 494 lines)
- FTS5 full-text search with BM25 ranking
- Optional semantic search (sqlite-vec + fastembed, graceful degradation)
- Provenance tracking (D-019): every wiki write linked to Run, Source, AuditEvent
- Wiki linting (empty body, untrusted, stale, contradictions)
- **Independent from graph_service** — different data sources, no cross-reference

### Audit Service (audit_service.py)
- Every state transition emits AuditEvent
- Events linked to Runs, which link to Missions
- Secret redaction before storage
- Export as JSONL
- **Not wired into graph** — audit events are not graph nodes

### Memory Provenance (provenance_service.py, 85 lines)
- MemoryProvenance records link memory writes to: Run, Source, AuditEvent, Operator
- Layers: WIKI, PROFILE, GRAPH, SKILL, AUDIT
- **Exists but not used by graph** — the provenance chain is the key to "which decisions led here?"

### 6-Layer Memory Framework (D-019)
- Layer 1: Hermes Profile/Session (available)
- Layer 2: LLM Wiki (implemented)
- Layer 3: Semantic Retrieval (optional/degraded)
- **Layer 4: Graph Memory (research only, v2.0 scope)**
- Layer 5: Audit/Event (available)
- Layer 6: Skill/Procedure (planned)

The living graph IS Layer 4 — the relationship-aware memory that connects all other layers.

---

## Visual Language — What Already Exists

### Topo Engine (topoEngine.ts)
- Canvas-less SVG contour renderer (marching squares)
- Hover reactivity (cursor-driven bulge)
- Typing trails (decaying glow)
- Sonar pings (expanding ring pulse)
- 6 tones: info, ai, good, warn, bad, atlas
- Used as background in TopoField, GlassTopo, TopoInput, RunDetail

### Glass Effects (glass.ts)
- SVG feDisplacementMap for real refraction
- Frosted backdrop-filter + specular sweep
- Liquid bend: topo field warps through glass like a thick lens

### Lightning (Lightning.tsx)
- WebGL FBM noise shader
- Configurable hue, speed, intensity
- Used as "Storm Activity" overlay on graph

### Starfield (filigree.tsx)
- Canvas-based slow-drifting star points
- Used on Dashboard hero

### Brand (AtlasMark, Wordmark)
- Celestial-heraldic aesthetic
- Astrolabe globe, constellation nodes, bronze cradle
- Cinzel typeface, ivory-to-bronze gradient

---

## Key Design Decisions to Make

1. **D-025: Graph storage** — SQLite adjacency list (recommended, extends D-003) vs embedded library vs JSON
2. **D-026: Update strategy** — Event-driven (audit events trigger graph mutations) vs periodic batch vs on-demand
3. **D-027: Entity schema** — What node types, edge types, metadata fields
4. **D-028: Visual language** — How to translate "neuron" metaphor into Three.js primitives
5. **Rust vs Python** — D-022 says Rust-first for new infrastructure. Build graph engine in Rust from start, or Python first?

---

## Files That Will Change

| File | Change Type | Reason |
|------|-------------|--------|
| `packages/atlas-core/atlas_core/schemas/graph.py` | NEW | Graph node/edge Pydantic models |
| `infra/migrations/0009_graph_memory.sql` | NEW | graph_nodes + graph_edges tables |
| `services/agent-runtime/atlas_runtime/graph_engine.py` | NEW | GraphEngine class |
| `services/agent-runtime/atlas_runtime/graph_extractors/*.py` | NEW | Entity extractors |
| `services/agent-runtime/atlas_runtime/graph_service.py` | MODIFY | Delegate to GraphEngine |
| `services/agent-runtime/atlas_runtime/cli/main.py` | MODIFY | New graph subcommands |
| `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs` | MODIFY | New graph endpoints |
| `services/web-ui-react/src/lib/api.ts` | MODIFY | New graph API functions |
| `services/web-ui-react/src/routes/Graph.tsx` | MODIFY | Living visuals, Agent Context tab |
| `services/agent-runtime/tests/test_graph_*.py` | NEW/MODIFY | New test coverage |

---

## Testing Evidence

### Existing Tests
- `test_graph_service.py` (51 lines, 2 tests): empty graph + nodes-links-refs
- `tests/api.rs` (827 lines, 30+ tests): gateway integration (includes graph endpoint)
- `tests/contract.rs` (182 lines): D-012 cross-language schema validation

### Test Gaps
- No tests for graph engine queries (neighborhood, path, hubs)
- No tests for entity extractors
- No tests for activity scoring
- No visual regression tests for living effects
- No performance benchmarks for animated 3D rendering

---

## Operator Context

The operator has been building ahead of the official v1.0.5 spine on phase 10.0.3 (cockpit redesign). The React pivot (D-023) is in progress with `services/web-ui-react`. The graph visualization is one of the most visually impressive features in the cockpit — the bloom, particles, and storm effects already create a premium feel. The living graph work would be a natural extension of the current cockpit redesign phase, adding runtime intelligence to an already-polished visual system.

The operator's vision of "neuron connections" and "nebula storms" maps directly to:
- **Neuron connections** = entity nodes with curved dendrite links + synaptic flash on activity
- **Nebula storms** = cluster glow proportional to activity_score + Lightning shader intensity
- **Memory integration** = wiki/audit/provenance wired as graph edges
- **RAG integration** = semantic edges from embeddings + graph neighborhoods as retrieval context
