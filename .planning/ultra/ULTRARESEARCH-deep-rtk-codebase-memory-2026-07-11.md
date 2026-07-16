# Deep Analysis: RTK + codebase-memory-mcp for ATLAS Integration

**Date:** 2026-07-11
**Analyst:** MiMo (automated deep research)
**ATLAS context:** Rust gateway (:8484), Python agent-runtime, 5 shipped tools (workspace, github, web_fetch, webhook_notify, golden_review_write), YAML manifests + Python adapters + registry binding, brain_nodes/brain_edges (manual), Hermes foundation.

---

## 1. RTK (rtk-ai/rtk)

### 1.1 Architecture

| Attribute | Detail |
|-----------|--------|
| **Language** | Rust 93.4%, Shell 4.4%, TypeScript 1.5%, Other 0.7% |
| **Tech stack** | Rust (edition 2021, MSRV 1.91), single binary |
| **Build system** | Cargo, release profile: opt-level=3, lto=true, codegen-units=1, strip=true, panic=abort |
| **Binary size** | ~4.1 MB stripped |
| **Startup overhead** | ~5-10ms cold start, ~5-15ms per command proxy overhead |
| **Dependencies** | clap 4, anyhow 1.0, regex 1, serde/serde_json 1, rusqlite 0.31 (bundled), chrono 0.4, sha2 0.10, ureq 2, colored 2, dirs 5, walkdir 2, ignore 0.4, toml 0.8, tempfile 3, flate2 1.0, quick-xml 0.37, which 8, getrandom 0.4, automod 1 |
| **Platform** | macOS (x86_64/aarch64), Linux (x86_64/aarch64), Windows (x86_64-pc-windows-msvc) |
| **License** | Apache-2.0 |
| **Latest version** | v0.43.0 (as of 2026-06-28) |

**Data flow:**
```
User/Agent -> rtk CLI (parse via Clap) -> Route to module -> Execute underlying tool via std::process::Command
-> Filter/compress output (12 strategies) -> Print filtered output -> Track savings in SQLite (~/.local/share/rtk/history.db)
```

**Module organization:** 64 modules total (42 command modules + 22 infrastructure modules), organized by ecosystem: git, js/ts, python, go, ruby, dotnet, cloud, system, rust.

**Filtering strategies (12):**
1. Stats extraction (git status/log)
2. Error-only filtering (test failures)
3. Grouping by pattern (lint errors by rule)
4. Deduplication (log lines)
5. Structure-only (JSON schema extraction)
6. Code filtering (strip comments/bodies, language-aware)
7. Failure focus (tests: show only failures)
8. Tree compression (directory listings)
9. Progress filtering (strip ANSI progress bars)
10. JSON/text dual mode (ruff, pip)
11. State machine parsing (pytest)
12. NDJSON streaming (go test)

### 1.2 API Surface

**CLI Commands:**
- `rtk <command>` -- proxy any supported command (100+)
- `rtk init -g [--agent <name>]` -- install hook for 15 agents
- `rtk gain [--graph|--history|--daily|--all]` -- token savings analytics
- `rtk discover [--all --since N]` -- find missed savings
- `rtk session` -- adoption across recent sessions
- `rtk smart <file>` -- 2-line heuristic code summary
- `rtk read <file> [-l aggressive]` -- smart file reading (signatures only mode)
- `rtk rewrite <command>` -- command rewriting API (used by Hermes plugin)
- `rtk telemetry enable|disable|forget|status` -- opt-in telemetry
- `rtk proxy <command>` -- raw passthrough + tracking
- `rtk summary <command>` -- heuristic summary
- `rtk err <command>` -- errors only from any command

**Global flags:**
- `-u, --ultra-compact` -- maximum compression (ASCII icons, inline)
- `-v, --verbose` -- debug levels (-v, -vv, -vvv)

**Configuration:** `~/.config/rtk/config.toml`
```toml
[hooks]
exclude_commands = ["curl", "playwright"]
[tee]
enabled = true
mode = "failures"
```

**Hermes integration:**
- Plugin at `~/.hermes/plugins/rtk-rewrite/`
- Python adapter: thin wrapper that calls `rtk rewrite` for command decision, mutates terminal tool payload
- Supports 15 agents: Claude Code, Copilot, Cursor, Gemini CLI, Codex, Windsurf, Cline/Roo Code, OpenCode, OpenClaw, Pi, Hermes, Kilo Code, Antigravity, Factory Droid
- Install: `rtk init --agent hermes`

**Telemetry env vars:** `RTK_TELEMETRY_DISABLED=1`

**Token savings:** 60-90% reduction on common dev commands (avg ~80% across a 30-min session).

### 1.3 Quality

| Metric | Value |
|--------|-------|
| **Stars** | 70.4k |
| **Forks** | 4.4k |
| **Commits** | 1,330 |
| **Open issues** | 775 |
| **Open PRs** | 794 |
| **Contributors** | 4 core (Patrick Szymkowiak, Florian Bruniaux, Adrien Eppling, Nicolas Le Cam) |
| **Releases** | 242 |
| **Test files** | 6 integration tests + unit tests via cargo test |
| **CI** | GitHub Actions (Security Check), Semgrep SAST |
| **Security** | SECURITY.md, .semgrep.yml, unsafe_code = deny in Cargo.toml |
| **Release cadence** | Very high (242 releases, rapid iteration) |
| **Maintained** | Yes, actively (latest release Jun 28 2026) |

**Security posture:**
- `unsafe_code = deny` and `warnings = deny` in Cargo.toml lint config
- Semgrep SAST scanning
- SECURITY.md with vulnerability reporting
- Telemetry is opt-in only (GDPR Art. 6, 7 compliant)
- No runtime dependencies (single binary)
- Release builds are stripped and use LTO

### 1.4 ATLAS Fit

| Aspect | Assessment |
|--------|------------|
| **Maps to component** | Gateway-side token compression proxy + Hermes plugin adapter |
| **Gap it fills** | Token cost reduction -- ATLAS agents currently receive raw command output (~118k tokens/30min). RTK would reduce this by 60-90%, saving API costs and improving context window utilization |
| **Integration difficulty** | LOW -- RTK already has a Hermes plugin. ATLAS vendors Hermes, so the plugin is directly available. Steps: (1) download RTK binary in installer, (2) run `rtk init --agent hermes`, (3) optionally add `atlas rtk status/gain` CLI subcommands |
| **License compatibility** | Apache-2.0 -- fully compatible with ATLAS |
| **Existing research** | Prior ULTRARESEARCH-atlas-integration-memory-token-2026-07-11.md already documents integration path |
| **Priority** | HIGH -- immediate cost savings, zero-risk integration via existing Hermes plugin |

**Integration plan:**
1. Add RTK binary to ATLAS installer scripts (PowerShell + bash)
2. Wire `rtk init --agent hermes` into `atlas up` bootstrap
3. Add `~/.config/rtk/config.toml` with `exclude_commands = ["atlas"]`
4. Optional: add `atlas rtk status/gain` CLI subcommands
5. Verify via token savings analytics

### 1.5 Risk

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Supply chain** | LOW -- single binary, no transitive deps | Pin release version, verify SHA-256 |
| **Maintenance** | LOW -- 70k+ stars, 242 releases, 4 core devs | High community investment |
| **Breaking changes** | LOW -- CLI contract stable across 242 releases | Pin version, test on upgrade |
| **Windows compatibility** | FULLY SUPPORTED -- native binary hook since v0.37.2 | Verified in README |
| **Hermes plugin drift** | MEDIUM -- plugin lives in RTK repo | Monitor upstream, fork if needed |
| **Token tracking privacy** | LOW -- telemetry opt-in only | Default off |

---

## 2. codebase-memory-mcp (DeusData/codebase-memory-mcp)

### 2.1 Architecture

| Attribute | Detail |
|-----------|--------|
| **Language** | C 88.3%, C++ 9.8%, Shell 0.8%, TypeScript 0.6%, Python 0.3%, PowerShell 0.1% |
| **Tech stack** | Pure C, tree-sitter AST, SQLite graph store, MCP JSON-RPC 2.0 |
| **Build system** | Makefile.cbm (custom), Nix flake, GitHub Actions CI |
| **Dependencies** | ZERO runtime -- all vendored: tree-sitter (158 grammars), mimalloc, SQLite, yyjson, LZ4, Nomic embeddings |
| **Binary** | Single static binary (macOS arm64/amd64, Linux arm64/amd64, Windows amd64) |
| **Persistence** | SQLite at `~/.cache/codebase-memory-mcp/`, WAL mode, ACID |
| **License** | MIT |
| **Latest version** | v0.9.0 (as of 2026-07-08) |
| **Distribution** | npm, PyPI, Homebrew, Scoop, Winget, Chocolatey, AUR, go install, manual |

**Data flow:**
```
Agent -> MCP stdio (JSON-RPC 2.0) -> MCP server (14 tools)
-> Pipeline: discover files -> tree-sitter parse (158 grammars) -> extract defs/calls/imports/HTTP routes
-> Hybrid LSP pass (12 languages: Python, TS/JS, PHP, C#, Go, C/C++, Java, Kotlin, Rust, Perl)
-> SQLite graph store (nodes, edges, Louvain clustering)
-> Background watcher (git polling, adaptive intervals) -> auto re-index
```

**Source structure:**
```
src/
  main.c              Entry point (MCP stdio + CLI + install/update/config)
  mcp/                MCP server (14 tools, JSON-RPC 2.0)
  cli/                Install/uninstall/update/config (10 agents, hooks)
  store/              SQLite graph storage (nodes, edges, traversal, search, Louvain)
  pipeline/           Multi-pass indexing (structure -> defs -> calls -> HTTP links)
  cypher/             Cypher query lexer, parser, planner, executor
  discover/           File discovery (.gitignore, .cbmignore)
  watcher/            Background auto-sync (git polling, adaptive intervals)
  traces/             Runtime trace ingestion
  ui/                 Embedded HTTP server + 3D graph visualization
  semantic/           Vector search (nomic-embed-code embeddings)
  simhash/            Near-clone detection (MinHash + LSH)
  graph_buffer/       Graph construction buffer
  foundation/         Platform abstractions
internal/cbm/
  vendored/           158 tree-sitter grammars (compiled into binary)
  lsp/                Hybrid LSP type resolution (12 languages)
  extract_*.c         AST extraction (calls, defs, imports, usages, channels)
  grammar_*.c         Per-language grammar C files (158 files)
```

**Indexing pipeline:**
1. RAM-first: all indexing in memory (LZ4 HC compressed read, in-memory SQLite)
2. Single dump at end; memory released after
3. LZ4 compression for in-memory graph
4. Fused Aho-Corasick pattern matching

### 2.2 API Surface

**14 MCP Tools:**

| Tool | Description |
|------|-------------|
| `index_repository` | Full/partial index of a codebase |
| `search_graph` | Structural search (regex name patterns, label filters, degree, file scoping) |
| `query_graph` | Cypher-like queries |
| `trace_path` | Call graph traversal (depth-limited BFS) |
| `get_code_snippet` | Extract code around a node |
| `get_graph_schema` | Node/edge types |
| `get_architecture` | Languages, packages, entry points, routes, hotspots, boundaries, layers, clusters |
| `search_code` | Graph-augmented grep over indexed files |
| `list_projects` | List indexed projects |
| `delete_project` | Remove project from store |
| `index_status` | Check indexing status |
| `detect_changes` | Map uncommitted changes to affected symbols with risk classification |
| `manage_adr` | Architecture Decision Records |
| `ingest_traces` | Runtime trace ingestion |

**CLI commands:**
- `codebase-memory-mcp` -- MCP server on stdin/stdout
- `codebase-memory-mcp cli <tool> [json]` -- single tool execution
- `codebase-memory-mcp install [--ui]` -- auto-detect agents, configure MCP entries
- `codebase-memory-mcp uninstall`
- `codebase-memory-mcp update`
- `codebase-memory-mcp config list|get|set|reset`
- `codebase-memory-mcp --ui=true --port=9749` -- 3D graph visualization
- `codebase-memory-mcp hook-augment`

**Config options:**
- `auto_index` (bool) -- auto-index on MCP session start
- `auto_index_limit` (int, default 50000) -- file limit for auto-index
- `auto_watch` (bool, default true) -- register with background watcher
- `extra_extensions` (JSON) -- map additional file extensions to languages

**Env vars:**
- `CBM_CACHE_DIR` -- custom cache directory
- `CBM_DIAGNOSTICS=1` -- enable diagnostics logging
- `CBM_LOG_LEVEL` -- log level
- `CBM_PROFILE` -- profiling
- `CBM_VARIANT=ui` -- npm/PyPI variant selector

**Edge types (selected):**
- CALLS, IMPORTS, DEFINES, IMPLEMENTS, INHERITS
- HTTP_CALLS, ASYNC_CALLS (cross-service)
- EMITS, LISTENS_ON (channels)
- DATA_FLOWS (arg-to-param mapping + field access chains)
- SIMILAR_TO (MinHash + LSH near-clone detection)
- SEMANTICALLY_RELATED (vocabulary-mismatch, score >= 0.80)
- CROSS_* (cross-repo edges)

### 2.3 Quality

| Metric | Value |
|--------|-------|
| **Stars** | 30.1k |
| **Forks** | 2.4k |
| **Commits** | 1,520 |
| **Open issues** | 167 |
| **Open PRs** | 53 |
| **Releases** | 36 |
| **Tests** | 5,604 passing |
| **Test files** | 80+ C test files covering: store, pipeline, extraction, LSP (12 langs), MCP, cypher, discovery, grammar, graph buffer, security |
| **CI** | GitHub Actions (dry-run.yml, build.yml), CodeQL SAST |
| **Security** | OpenSSF Scorecard, SLSA Level 3, VirusTotal (0/72 detections), Sigstore cosign, SHA-256 checksums, gitleaks |
| **Maintained** | Yes, very actively (latest release Jul 8 2026, 1,520 commits) |

**Security posture (exceptional):**
- VirusTotal: all binaries scanned by 70+ antivirus engines (zero detections)
- SLSA Level 3: cryptographic build provenance via GitHub Actions
- Sigstore cosign: keyless signatures on all artifacts
- SHA-256 checksums: verified by install scripts
- CodeQL SAST: blocks release on open alerts
- Zero runtime dependencies: all libraries vendored at compile time
- `.gitleaksignore` for secret scanning
- `.clang-format` + `.clang-tidy` + `.cppcheck` for C code quality

### 2.4 ATLAS Fit

| Aspect | Assessment |
|--------|------------|
| **Maps to component** | Brain graph / code intelligence layer -- directly addresses manual brain_nodes/brain_edges gap |
| **Gap it fills** | Automated code intelligence graph -- ATLAS currently has manual brain graph entries. CBM provides automated indexing of codebases into a persistent knowledge graph with 14 MCP tools, 158 language support, call graphs, dead code detection, impact analysis, Cypher queries. This is the missing code understanding layer for ATLAS operations. |
| **Integration difficulty** | MEDIUM -- CBM exposes MCP protocol (JSON-RPC 2.0). ATLAS gateway would need to either: (a) spawn CBM as a sidecar and communicate via MCP, or (b) call `codebase-memory-mcp cli <tool>` for single-shot queries. The Python adapter pattern in ATLAS tools/manifests/ would wrap CBM CLI calls. No C code modification needed -- use as external binary. |
| **License compatibility** | MIT -- fully compatible with ATLAS |
| **Priority** | HIGH -- fills the brain graph automation gap, enables code-aware operations |

**Integration plan:**
1. Add CBM binary to ATLAS installer (alongside RTK)
2. Create `atlas_runtime/tools/manifests/codebase_memory.yaml` manifest
3. Create `atlas_runtime/tools/adapters/codebase_memory.py` -- wraps `codebase-memory-mcp cli` calls
4. Register in tool registry
5. Wire `atlas up` to start CBM as sidecar (MCP stdio mode) or defer to CLI mode
6. Auto-index workspace on `atlas up` if CBM is available

**ATLAS-specific value:**
- Brain graph automation: `index_repository` builds the graph, `get_architecture` returns structural overview
- Impact analysis: `detect_changes` maps uncommitted diffs to affected symbols
- Dead code detection: finds functions with zero callers
- Cross-service linking: HTTP route -> call-site matching
- Cypher queries: flexible graph traversal
- 120x fewer tokens vs file-by-file exploration

### 2.5 Risk

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Supply chain** | LOW -- single static binary, all deps vendored | SLSA Level 3, VirusTotal, Sigstore, SHA-256 |
| **Maintenance** | LOW -- 30k+ stars, 1,520 commits, 5,604 tests | Very active development |
| **Breaking changes** | LOW -- MCP protocol stable, tool API well-defined | Pin version in installer |
| **Windows compatibility** | SUPPORTED -- Windows amd64, install.ps1, UTF-8 argv handling | Verified, dedicated Windows test files |
| **Binary size** | LOW -- larger than RTK (158 grammars compiled in) | Acceptable tradeoff for zero deps |
| **Memory usage** | MEDIUM -- RAM-first pipeline, large repos | Watcher uses supervised worker; index_limit configurable |
| **Language drift** | LOW -- 158 vendored grammars, regular updates | Grammars compiled into binary |
| **C codebase risk** | MEDIUM -- C harder to audit than Rust | Mitigated by 5,604 tests + CodeQL + cppcheck |

---

## 3. Comparative Matrix

| Dimension | RTK | codebase-memory-mcp |
|-----------|-----|---------------------|
| **Primary purpose** | Token compression proxy | Code intelligence graph |
| **Tech stack** | Rust | Pure C |
| **License** | Apache-2.0 | MIT |
| **Stars** | 70.4k | 30.1k |
| **Binary size** | ~4.1 MB | Larger (158 grammars) |
| **Tests** | 6 integration + unit | 5,604 passing |
| **ATLAS component** | Token layer (Hermes plugin) | Brain graph (code intelligence) |
| **Integration effort** | LOW (existing Hermes plugin) | MEDIUM (MCP sidecar or CLI wrapper) |
| **Immediate value** | Cost reduction (60-90%) | Code understanding automation |
| **License compat** | Apache-2.0 (OK) | MIT (OK) |
| **Windows** | Full native support | Full support (amd64) |
| **Supply chain** | Standard (single binary) | Excellent (SLSA3, VirusTotal, Sigstore) |

---

## 4. Combined Integration Architecture

```
ATLAS Agent Runtime (Python)
  |
  +-- Hermes Foundation (Python plugin host)
  |     |
  |     +-- RTK Plugin (~/.hermes/plugins/rtk-rewrite/)
  |           |
  |           +-- rtk rewrite (Rust binary) -> compact output
  |
  +-- Tool Registry (YAML manifests + Python adapters)
  |     |
  |     +-- workspace.yaml (existing)
  |     +-- github.yaml (existing)
  |     +-- web_fetch.yaml (existing)
  |     +-- webhook_notify.yaml (existing)
  |     +-- golden_review_write.yaml (existing)
  |     +-- codebase_memory.yaml (NEW)
  |           |
  |           +-- codebase_memory.py adapter
  |                 |
  |                 +-- codebase-memory-mcp cli <tool> (C binary)
  |
  +-- Brain Graph (currently manual brain_nodes/brain_edges)
        |
        +-- Automated by CBM: index_repository -> SQLite graph store
        +-- Queryable via: search_graph, trace_path, get_architecture, Cypher
```

**Token flow:**
```
Without RTK:
  Agent -> terminal tool -> raw output (~118k tokens/30min)

With RTK:
  Agent -> Hermes plugin intercepts -> rtk rewrite -> filtered output (~24k tokens/30min)
  Savings: ~80%
```

**Code intelligence flow:**
```
Without CBM:
  Agent -> grep/read files manually -> brain_nodes/brain_edges (manual) -> limited context

With CBM:
  Agent -> codebase_memory tool -> structured graph query -> full code intelligence
  - Architecture overview in one call
  - Call chain tracing across packages
  - Dead code detection
  - Impact analysis of changes
  - 120x fewer tokens than file-by-file exploration
```

---

## 5. Recommended Implementation Order

| Phase | Item | Effort | Value |
|-------|------|--------|-------|
| **Phase A** | RTK integration (Hermes plugin) | 1 day | Immediate 60-90% token savings |
| **Phase B** | CBM binary in installer | 0.5 day | Enables code intelligence |
| **Phase C** | CBM tool manifest + adapter | 2 days | Brain graph automation |
| **Phase D** | CBM auto-index on atlas up | 1 day | Seamless code awareness |
| **Phase E** | RTK analytics CLI (atlas rtk gain) | 0.5 day | Observability |
| **Phase F** | CBM graph visualization in cockpit UI | 3 days | Visual code exploration |

**Total estimated effort:** ~8 days for full integration.

---

## 6. Key Decisions Required

1. **CBM integration mode:** Sidecar (MCP stdio, persistent) vs CLI (single-shot). Recommendation: CLI mode initially (simpler, no sidecar management), migrate to sidecar when graph query latency matters.

2. **RTK version pinning:** Pin to specific release in installer vs track latest. Recommendation: Pin to specific release (e.g., v0.43.0), with explicit upgrade path.

3. **Brain graph migration:** Use CBM to replace manual brain_nodes/brain_edges, or keep both. Recommendation: Replace with CBM -- manual entries are error-prone and incomplete; CBM provides automated, comprehensive graph.

4. **Token budget:** RTK + CBM combined reduce token consumption by ~80% (RTK) + ~99% (CBM structural queries vs file-by-file). This significantly extends ATLAS agent context window utilization.

---

## 7. Open Questions

- Does ATLAS gateway (:8484) need to proxy CBM MCP traffic, or can Python adapter call CLI directly?
- Should CBM graph persist across ATLAS sessions (current: SQLite at ~/.cache/codebase-memory-mcp/)?
- How to handle multi-workspace scenarios (multiple repos indexed simultaneously)?
- RTK hook: should ATLAS exclude its own CLI commands from RTK rewriting?
