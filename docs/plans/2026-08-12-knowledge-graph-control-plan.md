# Knowledge-graph control — design and execution plan

**Date:** 2026-08-12
**Operator goal:** "we need more control over the knowledge graph, for user and
agent." Both halves matter: the agent must be able to *correct* what it knows,
and the operator must be able to *see and steer* it.

## 1. What exists (verified 2026-08-12, not inferred)

ATLAS has **two** graphs, and they are unrelated:

| | Graphify | Brain |
|---|---|---|
| Storage | none — rebuilt from disk each call | `brain_nodes` / `brain_edges` (migration 0014) |
| Source | markdown corpus (`.planning/`, repo, sibling projects, an Obsidian vault) | written by the agent during runs |
| Code | `graph_service.py`, `graph_scope_service.py` | `brain_service.py`, `graph_bridge.py` |
| Operator surface | `atlas graph *` CLI, `/v1/graph*` routes, cockpit 3D view | `atlas brain *` CLI (WP-1) |
| Agent surface | `atlas_graph` op=list_scopes/add_scope | `atlas_graph` — the rest |
| Mutable? | no (derived) | yes |

The Graphify view is the one the cockpit renders. The Brain graph is the one
that actually accumulates knowledge — and until WP-1 it was **append-only and
invisible**: no delete, no correction, no inventory, no CLI, no route, no view.

## 2. Design commitments

Decisions worth not relitigating in a later session:

1. **The two graphs converge in the view, not in the store.** Graphify is
   derived from files and must stay disposable; the Brain graph is durable and
   must stay authoritative. Merging their storage would make one of those false.
   WP-5 renders the Brain graph as another Graphify *scope* — one picture, two
   sources.
2. **`id == node_id_for(entity_type, label)` is an invariant, not a convention.**
   `add_node` derives ids from type+label so repeat calls converge. Any rename
   must therefore re-key the row and rewrite its edges; renaming in place would
   make the next `add_node` silently create a duplicate.
3. **Destructive ops return what they destroyed.** `forget` emits the node plus
   its incident edges. That makes the run transcript an undo log without paying
   for a tombstone table or a soft-delete flag on every read path.
4. **Already-gone is success for `unlink`, an error for `forget`.** Unlink is a
   retry-safe convergence op; forget on a missing node means the caller's model
   of the graph is wrong and should hear about it.
5. **Curation is not gated behind confirmation for the agent, and is for the
   operator.** The agent's writes are provenance-stamped and reversible from its
   own output; a human at a terminal gets `--yes` because a mistyped id there has
   no transcript to recover from.

## 3. Work packages

### WP-1 — Correctability + operator CLI — **DONE** (`98603031`)

`brain_service`: `list_nodes`, `edges_for`, `stats`, `update_node` (re-keying),
`delete_node` (undo record), `delete_edge`, `export_graph`, `import_graph`.
`atlas_graph`: `list`, `stats`, `neighbors`, `path`, `update`, `forget`,
`unlink`, `remove_scope`, `set_scope_root`.
`atlas brain`: `stats|list|search|show|add|link|update|forget|unlink|path|export|import`.

Verified: agent-runtime suite **1464 passed, 0 failed**; real-DB smoke covering
add → link → rename (edge followed the re-key) → export → forget guard → forget
→ import restore.

### WP-2 — Gateway routes (`/v1/brain/*`)

The gateway is dispatch-only (D-022) and shells out to the CLI, which is why
every `atlas brain` command prints JSON. Mirror the `/v1/graph/scopes` handler
shape in `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs`:

- `GET /v1/brain/stats`, `GET /v1/brain/nodes` (`?type=&project=&limit=`),
  `GET /v1/brain/nodes/{id}` (node + edges), `GET /v1/brain/search?q=`
- `POST /v1/brain/nodes`, `PATCH /v1/brain/nodes/{id}`,
  `DELETE /v1/brain/nodes/{id}` (dispatches `forget --yes`)
- `POST /v1/brain/edges`, `DELETE /v1/brain/edges`
- `GET /v1/brain/export`, `POST /v1/brain/import`

Acceptance: `native/atlas-core-rs/crates/atlas-gateway/tests/api.rs` covers each
route; the gateway binary is rebuilt (a stale binary silently serves the old
route table — see the run recipe).

### WP-3 — Cockpit Brain panel

A curation surface in `services/web-ui-react/src/routes/Graph.tsx`: node list
with type/project filters, node detail with edges and provenance
(`source_id` = which run asserted this), inline edit of label/summary/
confidence, and delete with the undo payload shown. Client in `lib/api.ts`
beside the existing graph helpers.

Acceptance: an operator can find a wrong fact and fix or remove it without
touching a terminal.

### WP-4 — Brain as a Graphify scope

Render the durable graph in the existing 3D view: a `brain` scope in
`graph_service.build_graph` that reads `brain_nodes`/`brain_edges` and emits the
same `{nodes, links}` contract, coloured by `entity_type`, sized by degree.
Requires the graph builder to take a connection — today it is filesystem-only.

Acceptance: the Graphify tab strip gains "Brain"; nodes are clickable through to
the WP-3 detail panel.

### WP-5 — Provenance and audit

Graph writes currently record `source_id` but emit no audit event, so there is
no timeline of how the graph changed. Emit `AuditEvent` on
add_node/link/update/forget and surface a per-node history in the detail panel.

### WP-6 — Decay and review queue

Nothing ages. Add a review surface driven by confidence and `updated_at`: low
confidence + stale + never re-asserted = a candidate for the operator to confirm
or forget. Decay is a *ranking* input, never an automatic delete — silently
dropping knowledge is the failure mode this whole plan exists to prevent.

### WP-7 — Retrieval closes the loop

`memory_router`'s brain-graph retriever pulls nodes matching the Focus terms.
Once curation exists, feed corrections back: a node the operator forgot must
leave retrieval immediately, and a confidence edit must reorder it. Add an eval
that asserts a corrected fact changes what the next run is told.

## 4. Ordering

WP-2 → WP-3 → WP-4 unlock the operator half and should go in that order (the
routes gate the UI, the UI gates the view integration). WP-5 → WP-7 deepen the
agent half and can be interleaved. WP-6 depends on WP-5's history.

## 5. Hard rules carried from the standing loop prompt

- Never edit `foundation/atlas-hermes/` (D-001) — every fix is an ATLAS-side adapter.
- Run pytest from `services/agent-runtime`, never the repo root.
- Rebuild the gateway binary after touching its route table, or the change is invisible.
