# 10.0.3 — Autonomous Loop & Command Center (scoped plan)

Status: planning + execution started · 2026-06-20 · scope inside phase 10.0.3
(operator-directed, ahead of the v1.0.5 spine). Autonomously planned per operator
"run the new phase for autonomous loop and command center… begin now."

## What this is

The **autonomous loop** = ATLAS feeds a pluggable agent (P4) its live, audited
context, the agent **executes in the background** (not blocking on the CLI), and
the run's outcome **feeds back** into the operator's Focus/wiki so the next run
inherits it. The **Command Center** = the execution-first dashboard surface over
that loop (Current Focus, framework, priorities, quick-capture, live activity).

Grounded in:
- `.planning/prep/intelligence-layer-alignment.md` (Command Center + Intelligence
  Layer tiers A/B/C/D; trust deltas: secret-redaction, audit/risk-gate, provenance).
- `.planning/prep/next-steps-db-runner-async-supabase.md` (runner → async executor
  → Command Center sequence; in-process executor decision).
- Current code: `run_service.py` lifecycle, `agents/` registry (P4 Native/ClaudeCode),
  gateway SSE `/v1/runs/{id}/stream`.

## Sequencing (prerequisite-correct)

| WP | Title | State | Notes |
|----|-------|-------|-------|
| **WP-0** | Migration runner `atlas db init` | **DONE** (`72a4151`) | Hard prereq for any new schema; absorbs non-idempotent ALTER drift. Verified this session. |
| **WP-1** | **Async run executor** (background execution) | **DONE — a + b** (`b2411d4`,`a2d4ea2`,`6434fc0`) | `run_executor.py` (execute_run / start_and_execute_async / await_run / active_run_ids). **CLI** `atlas run exec`. **(a)** gateway: `POST /v1/missions/{id}/run {execute:true}` spawns a detached `run exec` → background run, returns run_id immediately. **(b)** `atlas runtime serve` daemon hosts the in-process executor over HTTP (`POST /v1/runs/enqueue`). Both tested. |
| WP-2 | `Focus` entity + `focus_service` (+ migration 0009) | **DONE** (`ea01d4a`,`e564c4a`,`2def537`) | Model + `0009_focus.sql` + `focus_service.py` + `atlas focus create/show/list/archive` (JSON). **Gateway CRUD shipped** (`2def537`): `GET /v1/focus`, `GET /v1/focus/current`, `POST /v1/focus`, `POST /v1/focus/{id}/archive` per the P3 Project pattern (db.rs read fns + CLI-dispatch writes); 7 integration tests, gateway suite 50 green. |
| WP-3 | Context-assembly step (Intelligence Layer **[A]**) | **DONE** (`fc75374`,`e564c4a`) | `context_service.assemble_context()` — secret-redacted (SECRET_PATTERNS) brief of Current Focus + Project + recent runs, with provenance sources. Wired into `mission run --execute` and `run exec`. Wiki = gated extension. |
| WP-4 | Command Center dashboard (CC-1 UI) | **DONE** (`fd18b03`) | `/command` React route (COMMAND nav, MISSION pillar): Current Focus card (edit/archive), quick-capture → `createFocus`, **launch autonomous run** (agent + intent → `createMission` → `startRun(execute:true)`), live activity feed (`listRuns(20)` poll + reconnect). Poll-based feed (no SSE fan-out). tsc + vite build clean; eager import keeps three.js out of the bundle. Operator design-review checkpoint here. |
| WP-5 | Compounding loop (output→input) | **DONE** (`c64027c`) | `run_executor` appends a provenance-tracked `Observation` (source="compounding-loop", run_id) on terminal transition (skipped on mid-flight cancel; fail-open). `context_service` surfaces recent observations so the next run inherits them. |
| WP-6 | Named operations presets (**[B]**, daily agent commands) | **DONE** (`7ee90b6`,`5dda19c`,`1710019`) | Built-in **operation registry** (`operation_service`: elaborate / recon / blockers / decompose — all internal/reversible, auto-run). `build_intent` renders a "military-grade" instruction whose write-back block tells the agent to persist tasks/observations/sub-goals via the atlas CLI. `atlas operation list/prepare` CLI; gateway `GET /v1/operations` + `POST /v1/operations/{id}/run` (prepare → detached `run exec`). UI: per-goal ⚡ menu → `runOperation`. Verified live: UI click → running mission+run. |
| WP-7 | Tests across the slice | ongoing | TDD per WP; pytest (agent-runtime/core) + cargo (gateway) + tsc/build + Playwright. |

## Loop-engineering slice (operator-directed continuation, 2026-06-20)

Built end-to-end in sequence (spike → model → services → gateway → execution →
synthesis → compounding → UI). Goal: `NativeAtlasAgent` does real work and runs
are driven by a synthesized loop brief, not a bare title.

| WP | Title | State | Notes |
|----|-------|-------|-------|
| **LE-0** | Execution spike | **DONE** | Confirmed the foundation `AIAgent` imports from agent-runtime, constructs, and `run_conversation` returns `{final_response, messages, api_calls, completed, failed, error}`. Output needs a provider (`atlas-agent setup`); none → honest 403/failed. |
| **LE-1** | Goal hierarchy model | **DONE** (`acb8d58`) | `Goal`/`Task`/`Observation` frozen Pydantic + `0010_goal_model.sql` (goals self-nest via parent_goal_id). `goal_service` (CRUD + archive-cascade + `build_goal_tree`) + `atlas goal/task/observe` CLI. |
| **LE-2** | Gateway goal CRUD | **DONE** (`0df97bd`) | `GET /v1/focus/{id}/tree` (Rust tree build) + `POST /v1/goals`, `/v1/goals/{id}/archive`, `/v1/tasks`, `/v1/tasks/{id}/status`, `/v1/observations` (D-022 CLI-dispatch). |
| **LE-3** | Real execution + safety | **DONE** (`5a75e12`,`90cc86a`) | `NativeAtlasAgent` wired to the foundation harness (D-001: use, not edit). Layer 2 stop conditions (secret scan + max-runtime watchdog); Layer 3 claim taxonomy on `RunOutcome` (evidence/inferences/uncertainties/stop_reason). HTML error payloads collapsed. Autouse test fixture keeps the suite offline. |
| **LE-4** | Loop synthesis | **DONE** (`c64027c`) | `context_service.assemble_context` walks the goal tree + appends an Operating Contract (advance focus/goals, stay in workspace, classify claims, redact secrets). |
| **LE-5** | Goal-tree UI | **DONE** (`918d4b2`) | Command Center `GoalsPanel`: recursive tree, inline add goal/sub-goal/task, click-to-advance task status, archive, observations. Verified live against the rebuilt gateway. |

**Live E2E (capstone):** launched a native run from the gateway → real harness
executed → honest `failed` (no provider configured) → compounding observation
written. Confirms the loop is real, not theater. Verification: agent-runtime
133 / atlas-core 37 / gateway 52+3 green; tsc + vite build clean.

## Deferred (explicitly out of this slice)
- **ATLAS-owned auth store** (paused phase 10.1) → gates **CC-2** flagship
  integrations (GitHub/Workspace via MCP). No outward integration until it lands.
- **CC-3 metrics-next-to-AI** (live metrics ingested as entities).
- **Modular DB backend (Supabase/Postgres)** — only once credentials arrive;
  builds on the runner's portable `schema_migrations` contract.
- Per the operator: graph living-visuals (heat-map activity cloud, refined smoke)
  remain in the `10.0.3-graphify-living-graph` backlog; they consume this loop's
  activity data once WP-5 exists.

## Decisions to confirm (carried from prep)
- **D-async-model:** in-process daemon thread (recommended) vs a `run_queue`
  worker table. Start in-process; revisit if multi-worker is needed.
- **D-027 Focus schema:** fields for `Focus` (current focus, framework ref,
  priorities[], drivers[], updated_at, provenance). Frozen Pydantic + migration.
- **D-context-seed:** how context reaches the agent — generated `CLAUDE.md` in the
  project cwd vs SDK `options`/system-prompt. Lean: seed file in cwd (inspectable,
  audited) + SDK options for the structured bits.

## Constraints honored
- D-001 (no `foundation/` edits) · D-002 (audit-first: every transition emits) ·
  D-012/13 (Pydantic schema source of truth; additive migration via the runner) ·
  D-022 (SDK/MCP confined to Python agent-runtime; Rust = gateway) · risk-gated
  hybrid (reversible/internal autonomous; outward-facing → approval) · secrets only
  in the auth store, redacted from any agent context.

## Verification gates
- agent-runtime pytest green (prior 64+ tests + new), atlas-core pytest 33,
  `cargo test -p atlas-gateway` green, web tsc/lint/build green, Playwright for UI WPs.
