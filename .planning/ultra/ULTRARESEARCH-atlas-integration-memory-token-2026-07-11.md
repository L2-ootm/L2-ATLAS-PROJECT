# ATLAS Integration Specification: RTK, codebase-memory-mcp, TencentDB-Agent-Memory

> **Date**: 2026-07-11
> **Author**: ATLAS Architecture Analysis
> **Status**: DRAFT - Pending operator review
> **Scope**: Three external tool integrations into the ATLAS extensible harness

---

## Table of Contents

1. Architecture Summary
2. Tool 1: RTK (Token Compression Proxy)
3. Tool 2: codebase-memory-mcp (Code Intelligence)
4. Tool 3: TencentDB-Agent-Memory (Agent Memory)
5. Shared Concerns
6. Implementation Roadmap

---

## 1. Architecture Summary

### ATLAS Extensible Harness (from source analysis)

Every ATLAS tool integration follows a three-layer contract:

1. **Manifest** (tools/manifests/name.yaml) - declarative YAML, validated at load into frozen ToolManifest (Pydantic v2).
2. **Adapter** (tools/adapters/name.py) - Python module exposing run(args, ctx) -> ToolResult. Adapters perform NO policy checks.
3. **Registry binding** (tools/registry.py) - name: module.run added to _ADAPTERS dict.

Additional integration surfaces:
- **Sidecar control module** (name_control.py) - for long-lived processes: start/stop/status/health with PID files
- **CLI subcommand** (cli/name.py) - Typer app registered in cli/main.py, with --json output
- **Gateway routes** (Rust, lib.rs) - dispatch-only routes that shell out to the atlas CLI

### Safety Model

| risk_level | behavior |
|---|---|
| read | auto-allowed, runs immediately |
| write | requires explicit operator approval |
| shell | requires explicit operator approval |

### Key Files Referenced

| File | Role |
|---|---|
| atlas_runtime/tools/registry.py | Manifest load + adapter binding |
| atlas_runtime/tools/manifests/web_fetch.yaml | Reference manifest |
| atlas_runtime/tools/adapters/base.py | Adapter protocol |
| atlas_runtime/tools/adapters/web_fetch.py | Reference read adapter |
| atlas_runtime/tools/adapters/github.py | Reference CLI adapter |
| atlas_runtime/tool_service.py | Policy chokepoint |
| atlas_runtime/tool_catalog.py | Capability catalog |
| atlas_runtime/freellmapi_control.py | Reference sidecar control |
| atlas_runtime/cli/main.py | CLI entry point |
| atlas_runtime/cli/tools.py | Reference tool CLI |
| atlas_runtime/memory_router.py | MemoryRouter + Retriever protocol |
| atlas_runtime/context_service.py | Context assembly |
| atlas_runtime/gateway_control.py | Gateway lifecycle |
| atlas-gateway/src/lib.rs | Gateway HTTP routes |
| atlas_core/schemas/tool.py | ToolManifest, ToolResult schemas |
| docs/tools.md | Tool manifest docs |


---

## 2. Tool 1: RTK (Token Compression Proxy)

### 2.1 What RTK Does

RTK (Rust Token Killer) is a CLI proxy that reduces LLM token consumption by 60-90% on common dev commands. Single Rust binary, zero dependencies. Already supports Hermes as a plugin adapter.

**Key capabilities for ATLAS:**
- rtk git status/diff/log/push - compact git output
- rtk cargo test/build/clippy - compact Rust output
- rtk pytest - compact Python test output
- rtk gain / rtk discover - token savings analytics
- rtk read file - smart file reading (signatures only mode)
- rtk grep pattern . - grouped search results
- rtk summary cmd - heuristic summary of any command

### 2.2 Integration Type: Sidecar + Tool Adapter

RTK is a **sidecar** (long-lived binary, like freellmapi) AND provides **tool adapter** operations. It is NOT an MCP server - it is a standalone CLI binary.

**Integration approach:** Model after freellmapi_control.py for lifecycle management. Expose RTK operations as ATLAS tool adapters that shell out to the rtk binary.

### 2.3 Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| atlas_runtime/rtk_control.py | CREATE | Sidecar lifecycle |
| atlas_runtime/tools/manifests/rtk.yaml | CREATE | Tool manifest |
| atlas_runtime/tools/adapters/rtk.py | CREATE | Tool adapter |
| atlas_runtime/tools/registry.py | MODIFY | Add binding |
| atlas_runtime/cli/main.py | MODIFY | Register subcommand |
| atlas_runtime/cli/rtk.py | CREATE | CLI subcommands |
| atlas-gateway/src/lib.rs | MODIFY | Gateway routes |

### 2.4 Tool Manifest YAML

`yaml
name: rtk
description: Token compression proxy - filters and compresses command outputs.
risk_level: read
permissions: [net:none, fs:read]
inputs:
  - name: op
    required: true
    description: compress, gain, discover, version
  - name: command
    required: false
    description: Shell command to compress
  - name: ultra_compact
    required: false
    description: Use -u flag for extra savings
outputs: [content]
audit_events: [tool_requested, tool_completed, tool_failed]
`

### 2.5 Adapter Python Code

See full code at atlas_runtime/tools/adapters/rtk.py

**Key design points:**
- _resolve_rtk_bin() resolves binary via ATLAS_RTK_BIN env > PATH > ~/.local/bin/rtk
- run(args, ctx) dispatches to rtk CLI subcommands: compress, gain, discover, version
- For compress: splits command string into argv, passes through rtk
- Uses no_window_flags() for Windows subprocess handling
- Returns ToolResult with compressed output

### 2.6 Sidecar Control Module

See full code at atlas_runtime/rtk_control.py

**Key design points:**
- State file at ~/.atlas/rtk.json
- resolve_bin() for binary location
- health_ok() checks binary exists and --version runs
- get_version() returns RTK version string
- status() returns full status dict

### 2.7 CLI Subcommands

atlas rtk status [--json]  - binary availability and version
atlas rtk gain [--graph]  - token savings analytics
atlas rtk discover [--since N] - find missed savings opportunities

### 2.8 Gateway Routes

GET /v1/rtk/status - RTK binary status
GET /v1/rtk/gain - token savings analytics

### 2.9 Verification Steps

1. atlas rtk status - confirms binary found
2. atlas tools call -- rtk --args {op:compress, command:git status}
3. atlas tools list | grep rtk - confirms registered
4. curl http://127.0.0.1:8484/v1/rtk/status - gateway route works

### 2.10 Rollback Plan

1. Remove rtk.run from _ADAPTERS in tools/registry.py
2. Delete tools/manifests/rtk.yaml
3. Delete tools/adapters/rtk.py
4. Remove rtk_app from cli/main.py
5. Delete cli/rtk.py and rtk_control.py
6. Remove gateway routes from lib.rs
7. No database migrations required


---

## 3. Tool 2: codebase-memory-mcp (Code Intelligence)

### 3.1 What codebase-memory-mcp Does

High-performance code intelligence engine that indexes codebases into a persistent knowledge graph. Single static binary, 158 languages, sub-ms queries. MCP server with 14 tools.

**Key capabilities:**
- index_repository - full-index a codebase
- search_graph - structural search (regex, labels, degree)
- trace_path - resolve function call chains
- get_architecture - project overview
- semantic_query - vector search with bundled embeddings
- detect_dead_code - functions with zero callers
- detect_changes - impact of uncommitted changes
- cypher_query - Cypher-like graph queries

### 3.2 Integration Type: Sidecar + MCP Bridge + MemoryRouter Retriever

Three-pronged: (1) Sidecar lifecycle (cbm_control.py), (2) Tool adapter bridging to MCP CLI mode, (3) MemoryRouter CodebaseMemoryRetriever for agent context.

### 3.3 Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| atlas_runtime/cbm_control.py | CREATE | Sidecar lifecycle |
| atlas_runtime/tools/manifests/codebase_memory.yaml | CREATE | Tool manifest |
| atlas_runtime/tools/adapters/codebase_memory.py | CREATE | Tool adapter |
| atlas_runtime/memory_router.py | MODIFY | Add CodebaseMemoryRetriever |
| atlas_runtime/tools/registry.py | MODIFY | Add binding |
| atlas_runtime/cli/main.py | MODIFY | Register subcommand |
| atlas_runtime/cli/cbm.py | CREATE | CLI subcommands |
| atlas_runtime/config_service.py | MODIFY | Add enable_codebase_memory flag |
| atlas-gateway/src/lib.rs | MODIFY | Gateway routes |

### 3.4 Tool Manifest YAML

`yaml
name: codebase_memory
description: Code intelligence engine - indexes codebases into knowledge graph.
risk_level: read
permissions: [net:none, fs:read]
inputs:
  - name: op
    required: true
    description: index, search, trace, architecture, semantic, dead_code, changes, cypher, status
  - name: repo_path
    required: false
    description: Absolute path to repository
  - name: project
    required: false
    description: Project name
  - name: name_pattern
    required: false
    description: Regex pattern for name search
  - name: function_name
    required: false
    description: Function name for trace_path
  - name: query
    required: false
    description: Search query text
outputs: [content]
audit_events: [tool_requested, tool_completed, tool_failed]
`

### 3.5 Adapter Python Code

See full code at atlas_runtime/tools/adapters/codebase_memory.py

**Key design points:**
- _resolve_cbm_bin() resolves binary via ATLAS_CBM_BIN env > PATH > ~/.local/bin/codebase-memory-mcp
- _build_cli_args() maps ATLAS tool args to codebase-memory-mcp CLI tool + args
- run() shells out to: codebase-memory-mcp cli <tool_name> <json_args>
- 60s timeout (index can take minutes for large repos)

### 3.6 Sidecar Control Module

See full code at atlas_runtime/cbm_control.py

**Key design points:**
- State file at ~/.atlas/cbm.json
- resolve_bin() for binary location
- health_ok() checks list_projects CLI call works
- index_repo() triggers full repository index with 5min timeout

### 3.7 MemoryRouter Retriever

New class CodebaseMemoryRetriever in memory_router.py:
- Provides architecture overview from the code graph
- Degrades gracefully when CBM binary is absent
- Registered via enable_codebase_memory flag in default_router()
- Section: Code Intelligence (From the codebase knowledge graph)

### 3.8 CLI Subcommands

atlas cbm status [--json] - binary availability
atlas cbm index --repo PATH [--project NAME] - index repository
atlas cbm search --pattern REGEX [--label LABEL] - structural search
atlas cbm trace --function NAME [--direction both] [--depth 5] - call chains

### 3.9 Gateway Routes

GET /v1/cbm/status - CBM binary status
POST /v1/cbm/index - trigger repository index
POST /v1/cbm/search - structural graph search

### 3.10 Verification Steps

1. atlas cbm status - confirms binary found
2. atlas cbm index --repo /path/to/project - indexes project
3. atlas cbm search --pattern Handler - returns matching symbols
4. atlas tools list | grep codebase_memory - confirms registered
5. atlas mission run ID --show-context - verify Code Intelligence section

### 3.11 Rollback Plan

1. Remove binding from registry
2. Delete manifest, adapter, cli, control files
3. Remove CodebaseMemoryRetriever from memory_router.py
4. Revert default_router() signature
5. Remove gateway routes
6. No DB migrations required
