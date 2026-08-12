# Module Capabilities v2 + the Outreach Module

Date: 2026-08-12
Status: implementation contract (this session implements WP-1..WP-6)
Supersedes the "later slices" section of
`docs/plans/2026-07-16-module-framework-design.md` (v1 remains the base contract).

## Why

Module framework v1 is declarative and inert: a module contributes slash
commands and schema-driven pages, and nothing else. That is enough for a
launcher, not for a capability. The operator's ask is a module that carries
*plenty of capability* — data, doctrine, plays, integrations — and that the
agent can **read, call and mutate** while the module is active, without the
module executing arbitrary code inside ATLAS.

The first real consumer is **outreach**: L2 needs to run evidence-gated
prospecting (research → gate → send → reply → discovery → pilot) with the agent
doing the research, drafting, scoring and follow-up scheduling, and the operator
watching a CRM. That workload needs exactly the four things v1 lacks:
persistent typed records, injected doctrine, named workflows, and external
integrations (MCP).

## Design decisions

1. **Still manifest, not code.** No module ships executable code in v2 either.
   Capability comes from *declared data + ATLAS-owned execution*: ATLAS provides
   the record store, the schema validator, the prompt injection, the tool
   surface and the MCP supervision. A module declares what it wants; ATLAS is
   the only thing that runs. This keeps the plugin-store path open (a manifest
   can be reviewed; arbitrary code cannot).

2. **One generic agent tool, not one tool per module.** The agent gets
   `atlas_module` (mirroring `atlas_graph` / `atlas_actor` / `atlas_team`) whose
   op surface covers every active module. A new module therefore needs **zero**
   runtime changes to become agent-usable — that is the "dynamically injected or
   called by the agent when the module is active" requirement. Tool results
   always name the module, so the model cannot confuse two modules' records.

3. **Deactivated means invisible.** Every read path filters on
   `status='active' AND missing=0`: commands (v1 behavior), context injection,
   the record tool, and MCP projection. Deactivating a module removes its
   doctrine from the next run's prompt and its records from the tool surface
   without deleting anything. Records survive deactivation (the CRM is not
   destroyed by toggling a switch); they are simply unreachable until reactivated.

4. **Context injection is dynamic, budgeted, and never in the stable prompt.**
   Memory v2 fought hard to get the stable prompt down to ~1.5K chars. Module
   doctrine therefore lands in the *dynamic* context brief assembled by
   `context_service`, under an explicit per-module token budget, redacted like
   every other dynamic source. `inject: always | matched | on_demand` decides
   whether a file is always present, present only when the run's terms overlap
   the file's declared terms, or reachable only through
   `atlas_module op=context`.

5. **Module doctrine is operator-trusted, module records are not.** An operator
   activated the module, so its declared doctrine files are instructions for
   module work (delimited, labeled, scoped). Record content is data the agent
   itself wrote, so it is injected/returned as evidence, never as instruction.
   The distinction is carried in the markup (`<module-doctrine>` vs
   `<evidence>`), matching the existing evidence-not-instructions contract.

6. **MCP is an ATLAS registry projected onto the foundation.** ATLAS owns
   `mcp_servers` in SQLite (module-declared or operator-added). Enabled servers
   are projected into the Hermes config's `mcp_servers` map stamped
   `managed_by: atlas`, exactly as `function_router.apply_autoconfig()` projects
   aux model slots. D-001 holds: the foundation is used, never edited, and a
   hand-authored operator server is never clobbered. Projection is best-effort
   and never fails a run.

7. **Records are a store, not a database engine.** `module_records` is one
   generic table keyed `(module_id, collection, record_id)` with a JSON payload
   validated against the manifest's field list. This is deliberately unglamorous:
   modules come and go, and per-module DDL would make module removal a schema
   migration. Query support is bounded (filter by field equality/substring,
   status, sort, limit) — enough for a CRM board, deliberately not enough to
   need an index strategy per module.

## Manifest v2

```yaml
id: outreach
name: Outreach
version: 0.2.0
description: Evidence-gated outbound — research, gates, sequences, CRM.
author: L2 Systems
capabilities:
  commands:            # v1, unchanged
    - {name, description, template}

  context:             # NEW — doctrine injected when the module is active
    - id: doctrine
      title: Outreach doctrine
      path: context/doctrine.md
      inject: always            # always | matched | on_demand
      terms: [outreach, prospect]   # used when inject=matched
      max_tokens: 700

  collections:         # NEW — typed record store (the CRM)
    - id: prospects
      title: Prospects
      icon: users
      label_field: name
      fields:
        - {name: name,  type: text,   required: true}
        - {name: tier,  type: enum,   options: [S, A, B], default: B}
        - {name: stage, type: enum,   options: [research, ready, sent]}
        - {name: score, type: number, min: 0, max: 100}
        - {name: links, type: tags}
      sort: -updated_at

  workflows:           # NEW — named plays the agent can fetch and run
    - id: qualify
      title: Qualify a prospect
      description: Evidence gate before any message is drafted.
      inputs: [prospect]
      steps: ["…", "…"]
      done_when: "…"

  mcp:                 # NEW — external servers this module wants available
    - name: outreach-search
      transport: stdio          # stdio | http
      command: npx
      args: ["-y", "@some/mcp-server"]
      env: {API_KEY: "${OUTREACH_SEARCH_KEY}"}
      enabled: false            # opt-in; never auto-enabled by install
      description: Web research for prospect evidence.

  pages:               # v1 + new block kinds
    - id: main
      title: Outreach
      blocks:
        - {kind: tabs, tabs: [{id, label, blocks: [...]}]}
        - {kind: records, collection: prospects, columns: [name, tier, stage]}
        - {kind: stat_row, items: [{label, collection, filter}]}
```

Field types: `text`, `longtext`, `enum`, `number`, `date`, `bool`, `url`,
`tags`, `ref` (`ref_collection` names the target). Unknown types are rejected at
sync time so a broken manifest fails loudly at install, not at first write.

Page block kinds v2: v1's `heading`, `markdown`, `metrics`, `actions` plus
`tabs`, `records`, `stat_row`, `divider`. Unknown kinds still degrade to a
labeled placeholder.

## Storage (0034_module_capabilities.sql)

```
module_records(module_id, collection, id, data_json, status, created_at,
               updated_at, deleted_at, created_by_run, updated_by_run,
               PRIMARY KEY(module_id, collection, id))
  idx on (module_id, collection, status, updated_at)

mcp_servers(name PK, module_id, transport, command, args_json, env_json, url,
            description, enabled, managed_by, source, last_status,
            last_checked_at, last_error, created_at, updated_at)

scratchpad_entries(id PK, scope, owner, run_id, session_id, kind, title, body,
                   path, ttl_policy, expires_at, pinned, created_at, updated_at)
```

`scratchpad_entries` lands in the same migration because the scratchpad and the
future disposable-tool registry share one substrate: an owned, TTL'd, sweepable
artifact table (see `2026-08-12-atlas-self-extension-roadmap.md`).

## Surfaces

| Surface | v2 addition |
|---|---|
| Agent | `atlas_module` tool (list/describe/context/workflow/record CRUD/query/stats); active-module doctrine in the context brief |
| CLI | `atlas module info/context/workflows`, `atlas module records list/get/add/set/rm`, `atlas mcp list/add/enable/disable/sync/remove`, `atlas scratch list/add/get/rm/sweep` |
| Gateway | `GET /v1/modules/{id}/collections/{cid}/records`, `GET /v1/mcp` (reads from SQLite; writes dispatch to the CLI, per the existing gateway contract) |
| Cockpit | ModuleHost renders `tabs` / `records` / `stat_row`; records fetched live from the gateway |
| Terminal | unchanged (commands already merge) |

## Threat / failure notes

- **Prompt-budget blowout.** Per-file `max_tokens` (default 700) and a global
  module-context ceiling (`context.module_token_budget`, default 1,800) are
  enforced in `module_service.active_context_blocks()`. A module cannot starve
  retrieval.
- **Secret leakage via doctrine or records.** Both paths pass through
  `memory_router.redact()` before entering a prompt, same as every other source.
- **MCP env secrets.** `env` values support `${VAR}` indirection; ATLAS stores
  the reference, not the value, and resolves from the process env at projection
  time. A literal secret in a manifest is rejected at sync (SECRET_PATTERNS).
- **Runaway records.** Writes are capped (`max_records_per_collection`, default
  5,000) and payloads bounded (64 KB), so a looping agent cannot fill the DB.
- **Module id collisions.** Unchanged from v1: bundled wins, collision reported.

## Work packages

- **WP-1** manifest v2 + validation + `active_context_blocks()` (module_service)
- **WP-2** 0034 migration + `module_data_service` (typed CRUD/query)
- **WP-3** `module_bridge` (`atlas_module` tool) + prompt-compiler registration
- **WP-4** `mcp_service` + foundation projection + CLI
- **WP-5** `scratchpad_service` + `atlas_scratchpad` tool + TTL sweep
- **WP-6** `modules/outreach` (doctrine, collections, workflows, commands, pages)
- **WP-7** gateway records/mcp routes + ModuleHost v2 blocks
- **WP-8** docs: this contract, the self-extension roadmap, module README

## Non-goals (explicitly deferred)

- Module-provided *executable* tools (still the plugin-signing question).
- Per-module sidecar processes (the `service_supervision` path exists; nothing
  declares it yet).
- Cross-module joins or a query language over `module_records`.
- Automated outbound sending. The outreach module drafts, gates and records;
  a human sends. That is a doctrine constraint, not a missing feature — see the
  module's `context/compliance.md`.
