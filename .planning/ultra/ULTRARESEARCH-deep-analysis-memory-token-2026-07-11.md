# Deep Analysis: RTK + codebase-memory-mcp + TencentDB-Agent-Memory

**Date:** 2026-07-11  
**Purpose:** Rigorous technical analysis for ATLAS integration

---

## 1. rtk-ai/rtk — Token Compression Proxy

### Architecture
- **Language:** Rust (93.4%), single static binary
- **Dependencies:** Zero runtime deps (ripgrep optional for some filters)
- **Build:** Cargo, LTO-optimized, cross-compiled for macOS/Linux/Windows
- **Binary size:** ~15MB
- **Overhead:** <10ms per command

### How It Works
RTK intercepts shell commands via an auto-rewrite hook (PreToolUse for Claude Code, plugin APIs for others). It applies 4 strategies per command type:
1. **Smart Filtering** — removes comments, whitespace, boilerplate
2. **Grouping** — aggregates similar items (files by directory, errors by type)
3. **Truncation** — keeps relevant context, cuts redundancy
4. **Deduplication** — collapses repeated log lines with counts

### Supported Commands (100+)
- **Git:** status, log, diff, add, commit, push, pull — 80-92% savings
- **Test runners:** jest, vitest, pytest, go test, cargo test — 90% savings
- **Build/lint:** eslint, tsc, cargo build, ruff check — 80% savings
- **Files:** ls, read, find, grep — 70-80% savings
- **Docker/K8s:** ps, images, logs, kubectl — 80% savings
- **AWS:** sts, ec2, lambda, logs, cloudformation — significant savings
- **Package managers:** pnpm, pip, bundle — variable savings

### Configuration
- `~/.config/rtk/config.toml` — exclude commands, tee mode
- `rtk gain` — analytics dashboard (token savings over time)
- `rtk discover` — finds missed savings opportunities
- Global flags: `-u` ultra-compact, `-v` verbose

### Quality
- **Tests:** 1,330 commits, active CI (GitHub Actions)
- **Security:** Semgrep scanning, no secrets handling
- **Maintenance:** Very active (242 releases, 4.4k forks)
- **Windows:** Full native support since v0.37.2 (binary hook, no shell needed)

### ATLAS Fit
- **Gap addressed:** No performance benchmarking, no token optimization
- **Integration:** Ship `rtk.exe` alongside `atlas-gateway.exe`. `atlas up` manages it as sidecar. `atlas doctor` checks version.
- **Effort:** LOW — already has `rtk init --agent hermes` support
- **License:** Apache-2.0 (compatible with MIT)

### Risk
- **Supply chain:** Single binary, no transitive deps — LOW risk
- **Maintenance:** Very active, 280+ contributors — LOW risk
- **Breaking changes:** Stable API (CLI interface) — LOW risk
- **Windows:** Native support confirmed — LOW risk

---

## 2. DeusData/codebase-memory-mcp — Code Intelligence

### Architecture
- **Language:** Pure C (88.3%) + C++ (9.8%), single static binary
- **Dependencies:** Zero runtime deps (all vendored at compile time)
- **Storage:** SQLite (WAL mode, ACID) at `~/.cache/codebase-memory-mcp/`
- **Indexing:** RAM-first pipeline with LZ4 compression, in-memory SQLite, single dump
- **Parsing:** 158 vendored tree-sitter grammars compiled into binary

### How It Works
1. **Discovery:** File discovery via .gitignore/.cbmignore, symlink handling
2. **Parsing:** Tree-sitter AST extraction for all 158 languages
3. **Hybrid LSP:** Type-aware resolution for 12 languages (Python, TS/JS, Go, Rust, Java, C#, PHP, C/C++, Kotlin, Perl) — runs alongside tree-sitter
4. **Graph construction:** Nodes (Function, Class, Route, Resource) + Edges (CALLS, IMPORTS, HTTP_CALLS, DATA_FLOWS, SIMILAR_TO)
5. **Querying:** Cypher-like queries, BM25 full-text, semantic search (bundled Nomic embeddings), structural search

### MCP Tools (14)
- `index_repository` — full/medium/fast/cross-repo-intelligence modes
- `search_graph` — BM25 + name_pattern + semantic_query
- `query_graph` — Cypher queries
- `trace_path` — calls/data_flow/cross_service modes
- `get_code_snippet` — source code reader
- `get_architecture` — packages, services, Leiden clusters
- `detect_changes` — git diff impact mapping
- `manage_adr` — Architecture Decision Records
- `search_code` — graph-augmented grep
- `list_projects`, `delete_project`, `index_status`
- `ingest_traces` — runtime trace ingestion

### Performance
- **Linux kernel (28M LOC, 75K files):** 3 min full index, 1m12s fast
- **Django:** ~6s (49K nodes, 196K edges)
- **Cypher query:** <1ms
- **Token efficiency:** 3,400 tokens vs 412,000 via file-by-file (99.2% reduction)

### Quality
- **Tests:** 5,604 tests passing
- **Security:** SLSA Level 3, Sigstore cosign, VirusTotal scanned, CodeQL SAST
- **Maintenance:** 1,520 commits, 2.4k forks, very active
- **arXiv paper:** 2603.27277 — peer-reviewed benchmarks

### ATLAS Fit
- **Gap addressed:** ATLAS Brain graph is manual (brain_nodes/brain_edges). This makes it automatic.
- **Integration options:**
  - (a) Ship binary as sidecar, query via MCP
  - (b) Port indexing pipeline into ATLAS Brain retriever
  - (c) Use for development-time codebase understanding only
- **Recommended:** Option (a) — ship as sidecar, register as ATLAS tool
- **Effort:** MEDIUM — binary is self-contained, need tool manifest entry + adapter
- **License:** MIT

### Risk
- **Supply chain:** Single binary, all vendored — LOW risk
- **Windows:** Pre-built binary available — LOW risk
- **SQLite conflict:** ATLAS uses its own SQLite DB, codebase-memory uses separate cache — NO conflict
- **Maintenance:** Very active, well-funded — LOW risk

---

## 3. TencentCloud/TencentDB-Agent-Memory — Agent Memory

### Architecture
- **Language:** TypeScript (84.2%), Python (7.5%)
- **Storage:** SQLite + sqlite-vec (local backend, zero external deps)
- **Gateway:** Standalone HTTP server on :8420
- **Plugin system:** OpenClaw plugin + Hermes Gateway adapter

### 4-Tier Memory Pipeline
1. **L0 Conversation** — Raw dialogue capture (database-backed)
2. **L1 Atom** — Atomic facts extracted every N turns (hybrid BM25+vector+RRF retrieval)
3. **L2 Scenario** — Scene blocks aggregated from atoms (plain Markdown files)
4. **L3 Persona** — User profile distilled from scenarios (human-readable)

### Symbolic Short-Term Memory
- **Mermaid canvas** — task state transitions encoded in high-density Mermaid syntax
- **Context offloading** — full tool logs → external files, only lightweight graph in context
- **node_id tracing** — Agent reasons over symbol graph, drills down via node_id

### Benchmarks
- **WideSearch:** 33% → 50% pass rate (+51.52%), 221M → 85M tokens (-61.38%)
- **SWE-bench:** 58.4% → 64.2% (+9.93%), 3.4B → 2.4B tokens (-33.09%)
- **PersonaMem:** 48% → 76% (+59%)

### Hermes Integration (Already Exists)
- Plugin at `hermes-plugin/memory/memory_tencentdb/`
- Provider config: `memory.provider: memory_tencentdb`
- Gateway auto-discovery on first conversation
- Supports both standalone gateway and plugin-attached modes

### Configuration
- `storeBackend`: sqlite (default)
- `recall.strategy`: hybrid (keyword + embedding + RRF)
- `pipeline.everyNConversations`: 5 (extraction cadence)
- `offload.enabled`: false (short-term compression toggle)
- `embedding.*`: remote embedding service config (optional)

### Quality
- **Tests:** Vitest unit + E2E
- **Security:** Gateway API key auth (optional), CORS config, constant-time comparison
- **Maintenance:** 98 commits, 781 forks, backed by Tencent
- **OpenClaw compatibility:** First-class plugin

### ATLAS Fit
- **Gap addressed:** ATLAS has FTS5 wiki + basic Brain graph, but NO long-term structured memory
- **Integration:** Install Hermes plugin into ATLAS foundation. Wire to existing SQLite.
- **Effort:** MEDIUM — plugin exists, needs configuration + testing with ATLAS agent loop
- **License:** MIT

### Risk
- **Tencent backing:** Corporate sponsor — MEDIUM risk (could pivot to commercial)
- **OpenClaw dependency:** Plugin format tied to OpenClaw/Hermes — LOW risk (ATLAS vendors Hermes)
- **SQLite conflict:** Uses separate `~/.openclaw/memory-tdai/` — NO conflict with ATLAS DB
- **Maintenance:** Active but not frenetic — LOW risk

---

*Analysis complete. All 3 repos are HIGH FIT for ATLAS with LOW-MEDIUM integration risk.*
