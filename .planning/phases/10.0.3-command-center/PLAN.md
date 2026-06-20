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
| **WP-1** | **Async run executor** (background execution) | **STARTED** | The autonomous backbone: a run starts, returns `run_id` immediately, executes in a background thread, emits audit/SSE, completes. In-process daemon thread (single-operator scale, existing `threading.Lock` + SQLite WAL). New `run_executor.py`. |
| WP-2 | `Focus` entity + `focus_service` + migration 0009 + gateway CRUD | TODO | Command Center core data (current focus, framework, priorities, drivers). Follows the P3 `Project` pattern. New schema → through the runner. |
| WP-3 | Context-assembly step (Intelligence Layer **[A]**) | TODO | Before a `claude_code` run, materialize secret-redacted, provenance-tagged context (Focus + Project + recent runs/audit summary + linked wiki) into the agent's working context. `SECRET_PATTERNS` redaction; `MemoryProvenance` tags. |
| WP-4 | Command Center dashboard (CC-1 UI) | TODO | `/command` React route: Current Focus, framework, priorities, quick-capture, live activity feed (reuses `useRunStream`+SSE). |
| WP-5 | Compounding loop (output→input) | TODO | Run outcome/artifacts auto-update Focus context + wiki, so the next run inherits them. |
| WP-6 | Named operations presets (**[B]**, daily agent commands) | TODO | Saved (focus + agent + prompt) presets the operator triggers from the dashboard; risk-gated; spawn mission+run. |
| WP-7 | Tests across the slice | ongoing | TDD per WP; pytest (agent-runtime/core) + cargo (gateway) + tsc/build + Playwright. |

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
