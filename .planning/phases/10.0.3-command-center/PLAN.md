# 10.0.3 — Autonomous Loop & Command Center (scoped plan)

Status: **ALL WPs COMPLETE** · 2026-06-20 · scope inside phase 10.0.3
(operator-directed, ahead of the v1.0.5 spine).

## What this is

The **autonomous loop** = ATLAS feeds a pluggable agent its live, audited context,
the agent **executes in the background** (not blocking on the CLI), and the run's
outcome **feeds back** into the operator's Focus/goals so the next run inherits it.
The **Command Center** = the execution-first dashboard surface over that loop.

## Work Packages — All Complete

| WP | Title | State | Commit | What |
|----|-------|-------|--------|------|
| **WP-0** | Migration runner `atlas db init` | **DONE** | `72a4151` | Idempotent migration system, absorbs ALTER drift |
| **WP-1a** | Async run executor (subprocess) | **DONE** | `b2411d4`,`a2d4ea2` | `run_executor.py` + gateway `execute:true` flag |
| **WP-1b** | In-process executor daemon | **DONE** | `6434fc0` | ThreadingHTTPServer on port 8585 |
| **WP-2** | Focus entity + gateway CRUD | **DONE** | `ea01d4a`,`2def537` | Focus model + service + CLI + 4 gateway endpoints |
| **WP-3** | Context assembly (Intelligence Layer [A]) | **DONE** | `fc75374` | Secret-redacted brief with provenance |
| **WP-4** | Command Center dashboard | **DONE** | `fd18b03` | `/command` route, Focus card, launch run, activity feed |
| **WP-5** | Compounding loop | **DONE** | `c64027c` | Observations feed back to next context |
| **WP-6** | Named operations | **DONE** | `5dda19c`,`1710019` | 4 premade instructions with write-back contract |
| **WP-7** | Tests | **DONE** | multiple | 20+ new tests across agents, goals, context, executor |

## Loop-Engineering Slice — All Complete

| WP | Title | State | Commit | What |
|----|-------|-------|--------|------|
| **LE-0** | Execution spike | **DONE** | — | Foundation harness imports and runs |
| **LE-1** | Goal hierarchy model | **DONE** | `acb8d58` | Goal/Task/Observation + migration 0010 |
| **LE-2** | Gateway goal CRUD | **DONE** | `0df97bd` | 6 endpoints: tree, goals, tasks, observations |
| **LE-3** | Real execution + safety | **DONE** | `5a75e12` | NativeAtlasAgent wired to harness, stop conditions, claim taxonomy |
| **LE-4** | Loop synthesis | **DONE** | `c64027c` | Goal tree + observations + operating contract in context |
| **LE-5** | Goal-tree UI | **DONE** | `918d4b2` | Recursive tree, inline add, click-to-advance |

## Constraints honored

- D-001 (no foundation edits) · D-002 (audit-first) · D-012/13 (Pydantic source of truth; additive migrations)
- D-022 (Rust gateway; Python agent-runtime) · risk-gated hybrid (internal auto-run; outward → approval)
- Secrets only in auth store, redacted from agent context

## Verification gates

- agent-runtime pytest green (64+ tests + 20 new), atlas-core pytest 33+
- `cargo test -p atlas-gateway` green, web tsc/lint/build green
- Live E2E: native run executed, compounding observation written, goal tree rendered

## Deferred (explicitly out of this slice)

- ATLAS-owned auth store (paused phase 10.1)
- CC-3 metrics-next-to-AI
- Modular DB backend (Supabase/Postgres)
- Graph living-visuals (in `10.0.3-graphify-living-graph` backlog)
- Console hyprland BSP auto-tiling (one outstanding UI ask)
- Channel cockpit UI (System page expansion)
- Setup wizard (`atlas setup`)
