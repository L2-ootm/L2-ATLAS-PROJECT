# Outreach module

Evidence-gated outbound for ATLAS. The agent researches, verifies, scores,
gates, drafts, schedules and records; **a human sends**. Off by default.

```powershell
atlas module activate outreach   # doctrine, CRM and commands go live
atlas module info outreach       # the full capability surface
atlas module deactivate outreach # doctrine leaves the prompt; records survive
```

## What activating it changes

| Surface | Effect |
|---|---|
| Agent prompt | `context/doctrine.md` + `context/compliance.md` are injected into every run (~1,050 tokens, separately budgeted). Qualification and messaging doctrine appear when the run's terms match. |
| Agent tools | `atlas_module` reaches this module's records, workflows and on-demand doctrine. Nothing new is registered — the generic tool resolves the active manifest. |
| Slash commands | `/outreach`, `/outreach-research`, `/outreach-gate`, `/outreach-draft`, `/outreach-reply`, `/outreach-review`, `/outreach-crm` in the palette, chat and terminal. |
| Cockpit | `/m/outreach` renders the tabbed CRM (Today, Pipeline, Signals, Touches, Gates, Plays, Doctrine). |
| MCP | Two declared servers register **disabled**. Nothing runs until you enable one. |

## The data model

| Collection | What it holds |
|---|---|
| `prospects` | The registry — offer, gap hypothesis, tier, stage, score, next action, invalidated theses |
| `signals` | Evidence, each with `verified` / `reported` / `hypothesis` and a source URL |
| `touches` | Append-only contact ledger, in and out, with the reply class as `outcome` |
| `gates` | Gate decisions (0–5) with the evidence that decided them |
| `sequences` | Reusable plays, human-sent and agent-drafted, with measured reply rate |
| `objections` | What comes back, what it means underneath, the move that follows |
| `experiments` | One variable, one metric, one decision rule — the weekly review's output |

```powershell
atlas module records list outreach prospects
atlas module records set outreach prospects '{"name":"Acme","tier":"A"}'
atlas module records get outreach prospects acme
```

## Doctrine files

`context/` holds the operating rules. They are versioned with the module and
injected as **instructions** (the operator activating the module is the
authorization), unlike retrieved evidence.

| File | Injection |
|---|---|
| `doctrine.md` | always — the six pre-send questions, stages, evidence classes |
| `compliance.md` | always — the seven hard constraints, including "a human sends" |
| `qualification.md` | matched — tiers, the 5×20 score, gates 0–5, kill criteria |
| `messaging.md` | matched — first-message shape, follow-ups, reply classes, discovery |
| `research.md` | on demand — what a research pass must produce |
| `operating-rhythm.md` | on demand — daily queue, weekly review, cadence limits |

Edit a file, run `atlas module sync`, and the next run picks it up. Keep the
`always` files short: they are in every prompt.

## MCP servers

Both declarations are **templates** — verify the package or endpoint, provide
the credential as an environment variable, then enable:

```powershell
$env:FIRECRAWL_API_KEY = "..."     # referenced as ${FIRECRAWL_API_KEY}
atlas mcp list
atlas mcp enable outreach-web
atlas mcp test outreach-web
```

A server with an unresolved `${VAR}` is skipped at projection time and reported,
never silently launched. Deactivating the module retracts its servers from the
foundation config on the next run.

## What this module will not do

It does not send messages, run cold-DM automation, scrape behind a login,
invent numbers, or promise outcomes. Those are constraints in
`context/compliance.md`, injected into every run — not conventions.
