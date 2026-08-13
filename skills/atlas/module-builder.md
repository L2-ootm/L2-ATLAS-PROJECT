# Skill: module-builder

**Use when:** building or changing an ATLAS module — its manifest, slash
commands, cockpit pages, collections, doctrine, workflows or MCP servers.

Build a new ATLAS module the operator can toggle, without touching ATLAS
source. Contracts: `docs/plans/2026-07-16-module-framework-design.md` (v1) and
`docs/plans/2026-08-12-module-capabilities-v2-and-outreach-design.md` (v2).

## What a module can declare

A module is **data**; ATLAS is the only thing that executes. Never promise
behavior the manifest cannot express — record the gap instead.

- **`commands`** — slash commands in the WebUI palette/slash and the terminal.
  Name + description + prompt template (`$ARGUMENTS` carries operator input).
- **`pages`** — schema-driven cockpit pages. Blocks: `heading`, `markdown`,
  `metrics`, `actions`, `tabs`, `records` (bound to a collection), `stat_row`,
  `divider`.
- **`context`** — doctrine files injected into runs while the module is active:
  `inject: always` (every run), `matched` (when the run's terms overlap the
  declared `terms`), `on_demand` (only via `atlas_module op=context`). Keep
  `always` files short — they are in every prompt. Budget: `max_tokens` per
  file (default 700), 1,800 across all modules.
- **`collections`** — typed record schemas (the module's own durable data).
  Field types: `text`, `longtext`, `enum`, `number`, `date`, `bool`, `url`,
  `tags`, `ref`.
- **`workflows`** — named plays with ordered steps and a `done_when`. The agent
  fetches and executes them; they are procedure, not automation.
- **`mcp`** — MCP servers, always registered **disabled**. `env` values must be
  `${VAR}` references, never literal secrets.

## Procedure

1. Scaffold: `atlas module create <id> --name "<Display Name>"` — writes
   `<ATLAS home>/modules/<id>/module.yaml` plus `context/doctrine.md`, syncs,
   and activates.
2. Edit the manifest. One narrow job per command. Doctrine files hold the rules
   that must hold; workflows hold the procedure; collections hold what must
   survive the run.
3. Re-sync: `atlas module sync` (activation state is preserved). Fix every
   `problem:` line — it means the manifest was rejected and the capability is
   not live.
4. Verify end-to-end; do not assume:
   - `atlas module info <id>` lists the capabilities you expect;
   - `atlas module context <id>` prints exactly what a run will be given;
   - `GET /v1/commands` contains your command (collisions are dropped silently:
     built-ins and earlier modules win);
   - `/m/<id>` renders, and a `records` block shows real rows after you write one.
5. Exercise the data path once with `atlas_module op=create` before declaring
   the module done. A collection nobody has written to is untested.

## Using a module at runtime (as the agent)

- `atlas_module op=list` — what is active and what it offers. Check this before
  concluding a capability is missing.
- `atlas_module op=context module=<id> context_id=<cid>` — fetch on-demand
  doctrine rather than guessing.
- `atlas_module op=workflow module=<id> workflow_id=<wid>` — get the play, then
  follow it.
- `atlas_module op=query|create|update|delete` — the module's records. Write as
  the work happens, not at the end: a run that dies mid-task must leave its
  findings behind.

## Constraints

- Module ids and command names: `[a-z0-9-]`, lowercase. Collection, field and
  workflow ids: `[a-z0-9_]`.
- Doctrine paths must stay inside the module directory.
- Records: 64 KB per payload, 5,000 rows per collection.
- Do not edit ATLAS source, the registry DB, or another module's directory to
  make a module work.
- Deactivation must be lossless: a module's records survive it, so never store
  operator data anywhere but its collections.
