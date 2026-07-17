# TODO — Graphify agent query plane

Status: operator-requested follow-up, 2026-07-16

## Problem

Graphify renders ATLAS knowledge in the cockpit, but the agent runtime has no
first-class query tool for that graph. ATLAS can therefore visualize its own
structure while being unable to inspect or reason across it during a run.

## Required slice

- Add an ATLAS-owned, read-first internal graph tool through the Hermes plugin
  seam; do not require codebase-memory MCP for the initial implementation.
- Provide compact operations for `search`, `get_node`, `neighbors`, `path`,
  `subgraph`, `content`, and `stats` with pagination and bounded result sizes.
- Every result carries stable node IDs, graph/scope identity, source provenance,
  update time, and enough content to follow up without raw database access.
- Dynamically expose the scopes already represented by the Graphify page:
  Global, Projects, Obsidian Vault, and Agent Context.
- Activate and implement the Agent Context tab instead of leaving it locked.
- Let the runtime discover available graphs/scopes at call time so newly added
  projects and rebuilt graphs do not require prompt-policy edits.
- Enforce workspace and privacy boundaries: a bound session sees its permitted
  project graph plus allowed global context; unbound sessions never gain broad
  filesystem access merely because a graph exists.
- Emit normal audit and surface events for every graph operation.
- Keep the query contract backend-neutral so codebase-memory MCP can become a
  later adapter without changing the agent-facing schema.

## Acceptance gates

1. The agent can list available graph scopes and their freshness.
2. It can search a concept, inspect matching node content, traverse neighbors,
   and explain the provenance chain in one run.
3. Global, Projects, Obsidian Vault, and Agent Context tabs return real data or
   an explicit empty/offline state—never a decorative or locked shell.
4. Bound/unbound privacy tests prove cross-project graph leakage is impossible.
5. Large graphs remain bounded through pagination, depth limits, and response
   budgets.
6. Tool calls and outputs appear in Ledger and live run telemetry.
