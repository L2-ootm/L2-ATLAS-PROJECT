# 10.0.3 — Memory Router (FTS5 retrieval → context assembly)

> Status: **planned** (in-flight, ahead-of-spine; sequence item #1 of the six-item scope).
> Owner concern: `services/agent-runtime` only. No foundation edits (D-001). No new gateway routes.

## Intent

`context_service.assemble_context()` today materializes Focus + goal tree + observations + project +
recent runs, but does **no retrieval**: it never pulls the operator's accumulated knowledge (LLM Wiki)
into the brief. Every run re-derives what is already written down. The memory router closes that gap —
the Intelligence Layer's retrieval half — by querying the existing FTS5 wiki search with a query built
from the live Focus + goals, and injecting the top-k relevant pages into the brief, secret-redacted and
provenance-tracked, under a token budget.

This is the D-019 "policy-governed memory router" first cut for context assembly (Layer 2/3 retrieval).

## Scope

**In scope:**
- Query construction from `focus.title` + open goal/task titles (and mission title when present).
- Call the `atlas-wiki` search service (FTS5, already built — D-019 06-03) for top-k relevant pages.
- Render a `## Relevant Knowledge` brief section: page title + snippet, ranked, redacted, capped by a
  configurable char/token budget so it never dominates the brief.
- Provenance: append `wiki:<page_id>` to `AgentContext.sources` for every injected page.
- Optional second source: recent **relevant** audit events (text match against the query) as a
  `## Recent Activity` hint — only if cheap; otherwise defer.
- Graceful gating: `atlas-wiki` is an optional package; when absent or empty, skip cleanly (mirror the
  existing optional-wiki posture noted in the module docstring).

**Out of scope (deferred):**
- Semantic / embedding retrieval (sqlite-vec / fastembed) — FTS5 first; embeddings are a follow-up.
- New gateway endpoints / UI (context is assembled server-side for runs; no surface change).
- Re-ranking models, query rewriting via an LLM.

## Approach (TDD)

1. Write tests in `test_context_service.py`: (a) with a seeded wiki + Focus, the brief contains the
   relevant page and a `wiki:<id>` source; (b) with no wiki package / no hits, the brief is unchanged
   and no error; (c) the injected knowledge respects the budget cap; (d) secrets in a wiki page are
   redacted before injection.
2. Build a `_relevant_knowledge(conn, query, budget)` helper that imports the wiki search lazily,
   queries FTS5, redacts, caps, returns rendered lines + sources.
3. Wire it into `assemble_context()` after the goal tree, before the operating contract.
4. Build the query from Focus + open goals (reuse `goal_service.build_goal_tree`).

## Acceptance

- `assemble_context()` emits `## Relevant Knowledge` with top-k redacted wiki pages when a wiki exists
  and a Focus is set; emits nothing (no error) when the wiki is absent/empty.
- Provenance `sources` includes `wiki:<id>` for each injected page.
- Injected knowledge is bounded by the budget; secrets are redacted.
- `agent-runtime` pytest green (existing + new tests).

## Notes
- Reuse `redact()` already in `context_service.py`. Reuse the wiki search API from the `atlas-wiki`
  package (confirm the exact function signature at execution time).
- Keep the brief readable: knowledge is a *hint section*, not a data dump — strict budget.
