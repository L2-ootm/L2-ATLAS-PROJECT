# Knowledge-graph control — design and execution plan

**Date:** 2026-08-12 (target architecture revised same day — see §0)
**Operator goal:** "we need more control over the knowledge graph, for user and
agent." Both halves matter: the agent must be able to *correct* what it knows,
and the operator must be able to *see and steer* it.

## 0. Target architecture — a registry of member graphs

**Operator's framing, and the one this plan builds to:** the knowledge graph is
*a group of graphs* that compose into the major brain, every member queryable
and manageable by the agent. Not "two graphs that happen to share a UI."

A **member graph** is anything that can produce `{nodes, links}` and be named:

| Member kind | Source | Durable? | Writable? |
|---|---|---|---|
| `brain` | `brain_nodes`/`brain_edges` (0014) | yes | yes |
| `markdown` | a folder's `*.md` corpus | no — derived | no |
| `projects` | one cluster per child directory | no — derived | no |
| *(future)* `code` | the codebase-memory symbol graph | external | no |

The composite brain is the union of the members plus **cross-graph edges**
between them. That last part is what makes it one brain rather than a tab strip:
a Brain *entity* linked to the *document* that evidences it, addressed as
`graph_id::node_id`.

**What this reframing changed.** The first draft of this plan treated Graphify
and Brain as two unrelated things converging only in the cockpit view. Under the
registry model the gap is wider than WP-1 closed: the agent can *manage*
Graphify scopes (`list_scopes`/`add_scope`/`remove_scope`/`set_scope_root`) but
**cannot read a single node out of one** — every read op goes to the Brain. It
can register a folder it will never be able to query. That is now WP-2; the
former WP-2 (gateway routes) moves down.

## 1. What exists (verified 2026-08-12, not inferred)

The two implemented members are different *kinds* of graph, which is exactly why
they compose rather than merge:

| | Graphify | Brain |
|---|---|---|
| Shape | document-reference graph | typed-entity graph |
| Nodes | one per `*.md`, plus folder hubs and a root hub | typed entities with confidence + provenance |
| Edges | containment, relative md links, `[[wikilinks]]`, `D-0NN` mentions, `Phase N.N` mentions | typed relations |
| Storage | none — rebuilt from disk each call, capped 400–600 nodes | `brain_nodes` / `brain_edges` (migration 0014) |
| Source | `.planning/`, whole repo, sibling projects, an Obsidian vault, custom folders | written by the agent during runs |
| Code | `graph_service.py`, `graph_scope_service.py` | `brain_service.py`, `graph_bridge.py` |
| Operator surface | `atlas graph *` CLI, `/v1/graph*` routes, cockpit 3D view | `atlas brain *` CLI (WP-1) |
| Agent surface | scope management only — **no reads** | `atlas_graph` — the rest |
| Mutable? | no (derived) | yes |

The Graphify view is the one the cockpit renders. The Brain graph is the one
that actually accumulates knowledge — and until WP-1 it was **append-only and
invisible**: no delete, no correction, no inventory, no CLI, no route, no view.

## 2. Design commitments

Decisions worth not relitigating in a later session:

1. **Members compose; their storage does not merge.** Derived members must stay
   disposable and re-derivable from their source; the Brain must stay
   authoritative. One store would make one of those false. Composition happens
   at the query layer (fan-out) and through cross-graph edges — never by copying
   documents into `brain_nodes`.
2. **Cross-graph addressing is `graph_id::node_id`.** Derived members have no
   stable key beyond a path, so the member id has to be part of the address. A
   cross-graph edge whose far side has vanished from disk is a *dangling* edge to
   be reported, never an error that fails a query — derived members change under
   you by design, and a knowledge graph that breaks when a file is renamed is
   worse than one that admits it lost a reference.
3. **One tool, one uniform vocabulary.** Every member answers the same read ops
   (`search`, `explain`, `neighbors`) through `atlas_graph` with a `graph`
   argument. Adding a per-member tool for each new source would make the tool
   catalogue grow with the registry and force the agent to learn a new dialect
   per source.
4. **`id == node_id_for(entity_type, label)` is an invariant, not a convention.**
   `add_node` derives ids from type+label so repeat calls converge. Any rename
   must therefore re-key the row and rewrite its edges; renaming in place would
   make the next `add_node` silently create a duplicate.
5. **Destructive ops return what they destroyed.** `forget` emits the node plus
   its incident edges. That makes the run transcript an undo log without paying
   for a tombstone table or a soft-delete flag on every read path.
6. **Already-gone is success for `unlink`, an error for `forget`.** Unlink is a
   retry-safe convergence op; forget on a missing node means the caller's model
   of the graph is wrong and should hear about it.
7. **Curation is not gated behind confirmation for the agent, and is for the
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

### WP-2 — The registry: agent reads across every member — **NEXT**

The sharpest gap. The agent can register a Graphify scope and then never query
it. Give `atlas_graph` a `graph` argument that routes the existing read ops to
any member, defaulting to `brain` so every current call keeps working:

- `op=graphs` — list members: id, kind, source, node/link counts, health
  (folder missing? empty corpus? pre-0025 DB?).
- `op=search|explain|neighbors` gain `graph=<member id>`. For derived members
  these run over the built `{nodes, links}` rather than SQL.
- `op=search` with `graph="*"` — fan out across every member, each result
  tagged with the member it came from. This is the composite-brain query.

Shape: a `graph_registry.py` that resolves a member id to a uniform reader
(`brain` → `brain_service`; `markdown`/`projects` → `graph_service.build_graph`
/ `build_custom_graph`) and caches derived builds briefly — the cockpit already
learned that rebuilding on every call is too slow (see the `graphCache` in
`lib/api.ts`), and the agent will fan out across members far more often than a
human clicks a tab.

Also lift `VALID_KINDS` (`markdown|projects`) so `brain` is a registerable kind
rather than a special case the registry has to branch on.

Acceptance: from a cold run the agent can `op=graphs`, pick a member it has
never seen, `op=search` inside it, and get document nodes back; `graph="*"`
returns hits from both a derived member and the Brain in one call. Tests in
`tests/test_graph_registry.py` + `tests/test_graph_bridge.py`.

### WP-3 — Cross-graph edges

What makes the members one brain: let a Brain entity link to a node in a derived
member — `concept:retry-safety` → `atlas::phases/10.2/PLAN.md`. Store as a normal
`brain_edges` row whose target is a `graph_id::node_id` address (design
commitment 2), with a `kind` marking it cross-graph.

Dangling targets (the file moved or was deleted) are **reported, not fatal**:
`op=explain` returns the edge with `"dangling": true`, and the WP-6 review queue
surfaces them for the operator to re-point or drop.

Acceptance: an agent can cite the document that evidences an entity, and that
citation survives a rebuild of the derived member. A deleted source file leaves
a visible dangling edge, not a crash.

### WP-4 — Gateway routes (`/v1/brain/*`, `/v1/graphs`)

The gateway is dispatch-only (D-022) and shells out to the CLI, which is why
every `atlas brain` command prints JSON. Mirror the `/v1/graph/scopes` handler
shape in `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs`:

- `GET /v1/brain/stats`, `GET /v1/brain/nodes` (`?type=&project=&limit=`),
  `GET /v1/brain/nodes/{id}` (node + edges), `GET /v1/brain/search?q=`
- `POST /v1/brain/nodes`, `PATCH /v1/brain/nodes/{id}`,
  `DELETE /v1/brain/nodes/{id}` (dispatches `forget --yes`)
- `POST /v1/brain/edges`, `DELETE /v1/brain/edges`
- `GET /v1/brain/export`, `POST /v1/brain/import`
- `GET /v1/graphs` — the registry listing from WP-2, for the cockpit tab strip

Acceptance: `native/atlas-core-rs/crates/atlas-gateway/tests/api.rs` covers each
route; the gateway binary is rebuilt (a stale binary silently serves the old
route table — see the run recipe).

### WP-5 — Cockpit Brain panel

A curation surface in `services/web-ui-react/src/routes/Graph.tsx`: node list
with type/project filters, node detail with edges and provenance
(`source_id` = which run asserted this), inline edit of label/summary/
confidence, and delete with the undo payload shown. Client in `lib/api.ts`
beside the existing graph helpers.

Acceptance: an operator can find a wrong fact and fix or remove it without
touching a terminal.

### WP-6 — Brain as a rendered member + review queue

Render the durable graph in the existing 3D view: `graph_service` grows a `brain`
member that reads `brain_nodes`/`brain_edges` and emits the same `{nodes, links}`
contract, coloured by `entity_type`, sized by degree. Requires the builder to
take a connection — today it is filesystem-only. Cross-graph edges (WP-3) draw as
links *between* member clusters, which is the picture that makes the composite
brain legible.

Same surface carries the review queue: nothing ages today, so rank by confidence
and `updated_at` — low confidence + stale + never re-asserted = a candidate for
the operator to confirm or forget, alongside dangling cross-graph edges. Decay is
a *ranking* input, never an automatic delete; silently dropping knowledge is the
failure mode this whole plan exists to prevent.

Acceptance: the tab strip gains "Brain"; nodes click through to the WP-5 detail
panel; the review queue lists stale nodes and dangling edges.

### WP-7 — Provenance, audit, and retrieval feedback

Graph writes record `source_id` but emit no audit event, so there is no timeline
of how the graph changed. Emit `AuditEvent` on add_node/link/update/forget and
surface a per-node history in the detail panel.

Then close the loop: `memory_router`'s brain-graph retriever pulls nodes matching
the Focus terms. Feed corrections back — a node the operator forgot must leave
retrieval immediately, a confidence edit must reorder it, and once WP-2 lands the
retriever should draw from *every* member, not only the Brain. Add an eval that
asserts a corrected fact changes what the next run is told.

## 4. Ordering

**WP-2 first** — it is the registry itself, and WP-3/WP-4/WP-6 all assume a
member abstraction exists. Then WP-3 (cross-graph edges) since WP-6's picture and
review queue depend on them. WP-4 → WP-5 unlock the operator half in that order
(routes gate the UI). WP-6 needs WP-3 and WP-5. WP-7 is last: its retrieval half
only pays off once every member is queryable.

## 5. Hard rules carried from the standing loop prompt

- Never edit `foundation/atlas-hermes/` (D-001) — every fix is an ATLAS-side adapter.
- Run pytest from `services/agent-runtime`, never the repo root.
- Rebuild the gateway binary after touching its route table, or the change is invisible.
