# EVAL — codebase-memory-mcp as the Architecture Explorer backend

Date: 2026-07-12 · Follow-up to `ULTRARESEARCH-webui-vision-gaps-repos-2026-07-11.md` (priority 5).
Method: live probes against the indexed ATLAS repo (project key
`C-Users-Davi-Desktop-Projects-L2-ATLAS-PROJECT`) via the MCP tools in-session.

## Verdict

**Viable as the data backend, not as-is.** Symbol search and call tracing are
production-quality today. The architecture-overview and route surfaces need
scoping/filtering before they can drive a UI, and the SPA cannot talk to the
MCP directly — a thin gateway proxy (`/v1/graph/*`) is the right integration
shape. Recommend a scoped v1: Explorer = search box + symbol detail + call
trace panel, deferring cluster/route visualizations.

## Probe results (verified)

| Surface | Result | Explorer fitness |
|---|---|---|
| `index_status` | ready; 94,456 nodes / 412,555 edges | OK; index predates today's commits (staleness is a real concern — `detect_changes` exists for incremental refresh) |
| `search_graph` (BM25) | "workspace boundary policy check" → `policy.check_workspace_boundary` as top hit with exact file/line; `file_pattern`, `label`, pagination (`total`/`has_more`) all work | **Strong.** Best primitive; powers the Explorer search box directly |
| `trace_path` (calls) | inbound trace of `check_workspace_boundary` → its wrapper caller with hop counts | **Good.** Powers a caller/callee panel; also has `data_flow` and `cross_service` modes (unprobed) |
| `get_architecture` (clusters) | Leiden clusters returned, but **all top-12 clusters label as `foundation`** (vendored Hermes) — the vendored tree dominates and drowns ATLAS-specific structure | Needs exclusion of `foundation/` + vendored trees before it is presentable |
| `get_architecture` (packages) | Mostly single-node external deps (charmbracelet, aiohttp, …) with zero fan-in/out | Not useful as-is |
| Route nodes | 682 total, noisy: test-fixture URLs and garbage (`/>/g`, `//evil.com`) as Route nodes; the real `/v1/*` subset is 133 routes but synthesized from call sites — `method: ANY`, empty `file_path` | Usable only with a `/v1/`-prefix filter; not authoritative for the API surface (the gateway's own router is) |

## Integration architecture

The cockpit is a browser SPA — it cannot speak MCP stdio. Options considered:

1. **Gateway proxy `/v1/graph/*` → MCP server (recommended).** Follows the
   multi-surface-one-runtime principle; gateway already owns loopback trust,
   and every surface (TUI included) gets graph queries for free. Endpoints
   needed for v1: `search`, `symbol` (snippet), `trace`.
2. Direct SPA → codebase-memory HTTP UI on `:9749`. Zero work but bypasses the
   gateway, couples the cockpit to a third-party local service, unclear API
   stability. Acceptable only as an interim link-out ("open graph UI" button).
3. Re-implement graph reads in the gateway. Rejected — duplicates a working
   indexer.

## v1 scope proposal (next session, not started)

- Gateway: `/v1/graph/search`, `/v1/graph/trace` proxying the local MCP;
  return 503 with remediation when the MCP server is not running.
- Cockpit: Architecture Explorer route = search input → ranked symbol list
  (name, label, file:line) → detail pane with code snippet + inbound/outbound
  call trace. Reuse the Graph route's force-graph vendor chunk only if the
  trace visualization earns it; a list-based trace is cheaper and likely clearer.
- Precondition fixes: exclude `foundation/`, `_EXTERNAL_REPOS/`, and test
  fixtures from Explorer-facing queries (`file_pattern` filters suffice —
  no re-index needed); refresh the index (`detect_changes`) at session start.

## Open questions

- Does the `:9749` UI expose a stable HTTP API the gateway can proxy, or does
  the gateway need to spawn/own an MCP client connection? (Inspect before
  building `/v1/graph`.)
- Index refresh policy: on gateway boot, on demand, or scheduled?
- Whether `semantic_query` (vector mode) is enabled for this index — would
  improve vocabulary bridging in the search box.
