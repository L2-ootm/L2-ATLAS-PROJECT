# ATLAS bundled modules

Each subdirectory containing a `module.yaml` is a manifest module. Modules
here ship with the checkout; operator/agent-installed modules live in
`<ATLAS home>/modules/`. Design contracts:
`docs/plans/2026-07-16-module-framework-design.md` (v1) and
`docs/plans/2026-08-12-module-capabilities-v2-and-outreach-design.md` (v2).

| Module | What it is |
|---|---|
| `gsd` | Goal · Slice · Deliver — the L2 execution doctrine as slash commands |
| `outreach` | Evidence-gated outbound: research, gates, drafting, CRM (see its README) |
| `admissions` | The college application campaign, read from Pattern Forge rather than stored here (see its README) |

All ship **inactive**. A bundled module is an offer, not a default.

## Registry control

```powershell
atlas module list                # id, status, name
atlas module sync                # discover manifests + register their MCP servers
atlas module activate <id>       # capabilities go live everywhere
atlas module deactivate <id>     # capabilities retract; data survives
atlas module info <id>           # the full capability surface
atlas module context <id> [cid]  # exactly what a run would be given
atlas module create <id>         # scaffold a new module (the self-wiring path)
atlas module records list <id> <collection>
```

## What a module may declare

Capabilities are **declarative in every version** — a module is data, and ATLAS
is the only thing that executes. No module code runs anywhere.

| Capability | Effect when the module is active |
|---|---|
| `commands` | Slash commands in the WebUI palette, chat, and the terminal |
| `pages` | Cockpit pages at `/m/<id>`, rendered by ATLAS-owned components |
| `context` | Doctrine injected into every run (`always`), on matching terms (`matched`), or on request (`on_demand`) |
| `collections` | Typed record schemas backed by `module_records`; the agent reads/writes them with `atlas_module` |
| `workflows` | Named plays the agent fetches and executes itself |
| `mcp` | MCP servers registered in the ATLAS registry — always disabled until an operator enables them |

Page block kinds: `heading`, `markdown`, `metrics`, `actions`, `tabs`,
`records`, `stat_row`, `divider`. Unknown kinds render as a labeled placeholder,
so a newer manifest degrades gracefully on an older build.

## Budgets and guardrails

- Injected doctrine is capped per file (`max_tokens`, default 700) and per run
  (`context.module_token_budget`, default 1,800) — activating a module cannot
  starve retrieval.
- Records: 64 KB per payload, 5,000 rows per collection.
- Doctrine paths must stay inside the module directory.
- MCP `env` values must be `${VAR}` references; a literal-looking credential is
  rejected at sync.
- Deactivating a module hides its commands, doctrine, records and MCP servers.
  Nothing is deleted.
