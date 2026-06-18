# Next-Steps Handoff — Migration Runner → Async Executor → Modular DB (Supabase) → Command Center

Status: handoff / prep · 2026-06-18 · self-contained — the next agent run should be able to
execute from this doc **without re-deriving anything**. Branch at handoff: `feat/cockpit-p3-glass-p4`
(P3 + P4 landed, verified, committed; tree clean except intentional untracked `glasstopo-v2-modal.png`).

This doc was written to close the session fast. The investigation below is already done; what remains
is execution. Items are ordered by dependency — do them top to bottom.

---

## New operator direction (2026-06-18) — fold into the sequencing

The operator stated two forward requirements that reshape the DB layer work:

1. **Supabase integration is coming.** Credentials will be supplied later. ATLAS must be able to run
   its persistence either **locally (SQLite)** or **on Supabase (Postgres)** — operator's choice,
   modular, with **automatic migrations** on whichever backend is selected.
2. **A second L2 app, "cashflow"** (simple cash-management) will be brought in later and **wired up
   modularly** — same local-or-Supabase choice, same automatic-migration mechanism. So the migration
   machinery we build now should be designed to be **reusable across apps and across backends**, not
   hard-bound to ATLAS+SQLite.

Implication: **the migration runner (item 1 below) is the first brick of this modular DB layer.** Build
it with a clean backend seam now (SQLite-only implementation), so the Postgres/Supabase backend and a
second app can slot in later without a rewrite. Do **not** build the Postgres backend yet (no creds,
YAGNI) — just don't paint us into a SQLite-only corner.

---

## 1. Migration runner — `atlas db init` (DO THIS FIRST; hard prerequisite)

### The gap (verified this session)
- `_get_connection()` ([services/agent-runtime/atlas_runtime/cli/main.py:54](../../services/agent-runtime/atlas_runtime/cli/main.py#L54))
  opens `~/.atlas/atlas.db` with WAL+FK but **never applies migrations**. Nothing auto-bootstraps schema.
- Every consumer applies migrations ad hoc by blindly `executescript`-ing **all** `infra/migrations/*.sql`
  in sorted order with **no applied-tracker**: the agent-runtime test conftest
  ([services/agent-runtime/tests/conftest.py:39-46](../../services/agent-runtime/tests/conftest.py#L39-L46))
  and [scripts/fresh_db_smoke.py:35-41](../../scripts/fresh_db_smoke.py#L35-L41).
- Idempotency posture of the existing migrations (read them — confirmed):
  - `0001_core.sql` — all `CREATE TABLE/VIRTUAL TABLE/TRIGGER IF NOT EXISTS` → **re-run safe**. Contains
    FTS triggers with `BEGIN ... END` (internal semicolons — do NOT naively split this file on `;`).
  - `0002`, `0003`, `0004` — additive, `IF NOT EXISTS` style.
  - `0005_projects.sql` — `CREATE TABLE/INDEX IF NOT EXISTS` (safe) **plus a bare
    `ALTER TABLE missions ADD COLUMN project_id ...`** (line 20) → **NOT idempotent**.
  - `0006_agent_runtime.sql` — bare `ALTER TABLE runs ADD COLUMN agent_runtime ...` (line 10) +
    `CREATE INDEX IF NOT EXISTS` → **NOT idempotent**.
- Net failure mode: a previously-bootstrapped DB silently drifts (sits at an old migration level), and
  re-running the full set throws `duplicate column name` on the bare ALTERs. The operator's real
  `~/.atlas/atlas.db` had to be hand-patched (0005 then 0006) twice this session. Fresh machines have
  no bootstrap command at all.

### Design (decided — implement as-is)
New module **`services/agent-runtime/atlas_runtime/db.py`**. Public surface:

```
MIGRATIONS_DIR: Path            # resolved to <repo>/infra/migrations (single source; kill the
                                # duplicated path-resolution in conftest/smoke)
connect(db_path: str | None = None) -> sqlite3.Connection
                                # WAL + FK; default ~/.atlas/atlas.db; mkdir parents.
                                # Centralizes the logic currently inlined in cli/main.py:_get_connection.
ensure_migrations_table(conn)   # CREATE TABLE IF NOT EXISTS schema_migrations(
                                #   version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)
applied_versions(conn) -> set[str]
pending_migrations(conn, migrations_dir=MIGRATIONS_DIR) -> list[Path]
apply_migrations(conn, migrations_dir=MIGRATIONS_DIR) -> list[str]   # returns versions newly applied
migration_status(conn, migrations_dir=MIGRATIONS_DIR) -> list[tuple[str, bool]]  # (version, applied)
```

Key decisions:
- **Tracker table** `schema_migrations(version TEXT PK, applied_at TEXT NOT NULL)` is **runner-managed,
  not a numbered migration** (it must exist before we can read it). `version` = the **filename**
  (e.g. `"0006_agent_runtime.sql"`) — stable, human-readable, portable to Postgres later.
- **Explicit command, NOT auto-migrate-on-connect.** The Rust gateway also opens this DB; auto-DDL on
  every connect risks surprise schema changes and write races under the gateway. Migrations run only
  when the operator/CI/bootstrap calls `atlas db init`.
- **Legacy/drift tolerance (the crux).** For each file whose `version` is not in the tracker:
  - Happy path (fresh DB): `conn.executescript(sql)` — runs the whole file correctly, including the
    0001 FTS triggers. Then record the version.
  - On `sqlite3.OperationalError` containing `"duplicate column name"` (a drifted/hand-patched DB that
    already has the column): **fall back** to executing the file statement-by-statement, swallowing
    only the per-statement `"duplicate column name"` error and running the rest (so the trailing
    `CREATE INDEX IF NOT EXISTS` still applies). This split is safe **only on the fallback path** and
    **only for the bare-ALTER files (0005/0006), which contain no triggers**. Re-raise any other error.
    Either way, **stamp the version as applied** so the DB converges and future runs are clean.
  - This makes the runner correct for all three real cases: (a) fresh DB → apply all cleanly; (b)
    partially-drifted DB → apply only the pending ones; (c) fully hand-patched DB with empty tracker →
    swallow duplicate-column, stamp all, no error, columns intact.
- **Note for `executescript` + tracker atomicity:** `executescript` issues an implicit COMMIT, so the
  file-apply and the tracker INSERT are not one transaction. Acceptable: if the tracker INSERT fails
  after a successful apply, the next run re-applies, and `IF NOT EXISTS` / duplicate-column tolerance
  makes that a no-op. Record + `conn.commit()` immediately after each file.

### Backend seam (for Supabase later — design only, don't implement)
Keep all SQLite specifics (`executescript`, `sqlite3.OperationalError`, the duplicate-column string,
WAL pragma) **inside `db.py`** behind the function surface above. When Postgres lands: branch on a
backend selector (env / auth-store connection string), swap `connect()` for a psycopg connection, swap
`executescript` for psycopg `execute`, and resolve SQL dialect differences via either per-dialect
migration directories (`infra/migrations/sqlite/` vs `infra/migrations/postgres/`) or a translation
step. The `schema_migrations(version, applied_at)` contract is already portable. Add a docstring in
`db.py` naming this extension point so the next change is obvious.

### CLI wiring
Add a `db` Typer group in [cli/main.py](../../services/agent-runtime/atlas_runtime/cli/main.py):
- `atlas db init` (alias `migrate`) → `apply_migrations`, print each newly-applied version (or
  "already up to date").
- `atlas db status` → print each migration and `applied`/`pending`.
Refactor `_get_connection()` to delegate to `db.connect()` (single connection definition).

### Entropy reduction (do alongside — report-first, low risk)
- Route [scripts/fresh_db_smoke.py](../../scripts/fresh_db_smoke.py) through `db.apply_migrations`
  instead of its private `apply_migrations` (removes a second code path).
- Optionally route the agent-runtime `conftest.py` `db` fixture through `db.apply_migrations` too. It's
  a fresh `:memory:` DB each test, so the tracker is harmless; the only table-assertion in that suite
  is `test_conftest.py` checking `audit_events` exists (subset check — an extra `schema_migrations`
  table does not break it). **Leave atlas-core's `tests/test_migration.py` and its own conftest alone**
  — that suite deliberately applies **only 0001** and already encodes the `project_id`/`agent_runtime`
  additive exclusions; do not reroute it.

### Tests to write (`services/agent-runtime/tests/test_db_migrations.py`)
Use a **temp file DB** (real reopen scenario, not `:memory:`):
1. Fresh DB → `apply_migrations` returns all current files; a 2nd call returns `[]`; `schema_migrations`
   has one row per file; core tables + `projects` + `runs.agent_runtime` exist.
2. Drifted DB: apply 0001–0004 raw via `executescript`, empty tracker → `apply_migrations` applies only
   0005 & 0006; `missions.project_id` and `runs.agent_runtime` present.
3. Fully-patched-no-tracker DB: apply ALL files raw, empty tracker → `apply_migrations` swallows
   duplicate-column, stamps all, raises nothing, columns intact.
4. `migration_status` reflects applied vs pending correctly.

### Verification
- `cargo test` in `native/atlas-core-rs/` (should be unaffected — no Rust change).
- agent-runtime pytest (expect the prior 64 + new runner tests green).
- atlas-core pytest 33 (unaffected).
- Run `atlas db status` then `atlas db init` against the **real** `~/.atlas/atlas.db` — it's already at
  0006 from the hand-patch, so init should stamp all 6 as applied with zero errors and `status` should
  then show all applied. This closes the drift gap operationally.

---

## 2. Async / background run executor

### Why
The Rust gateway dispatches `atlas` via `dispatch_atlas()` with a **30s subprocess timeout** — it
cannot drive a long `claude_code` run. Today the gateway path is **record-only** (`POST .../run` records
`agent_runtime` but does not execute); the **CLI `--execute` flag is the only live executor and it runs
synchronously/blocking** ([cli/main.py:95-153](../../services/agent-runtime/atlas_runtime/cli/main.py#L95-L153)).

### Direction
Add background execution so a run can start, return its `run_id` immediately, execute asynchronously, and
stream its audit trail over the existing SSE plumbing the cockpit already uses (`useRunStream` /
`GET /v1/runs/{id}/events`). Decisions to make at planning time (note the tradeoffs, then pick):
- **In-process worker thread/pool inside agent-runtime** vs **a separate worker process / queue.** Given
  single-operator scale and the existing threading.Lock + SQLite WAL, an in-process background thread
  that the gateway (or a small `atlas` daemon) owns is the lowest-complexity first cut; a separate
  worker is the scale-out path. Recommend starting in-process, behind a service-layer function, to keep
  the gateway dispatch thin.
- Run lifecycle already supports this: status is `pending→running→succeeded/failed`; `complete_run` and
  `cancel_run` are guarded by the running-state precondition (idempotent, no double-terminal), and
  `cancel_run` exists for the cancellation path. Audit emit is fail-open + append-only.
- The gateway endpoint should enqueue + return `run_id` (202-style), not block on the 30s timeout.

This is a backend slice with its own GSD phase; the migration runner is **not** a prerequisite for it,
but doing the runner first keeps schema clean if the executor needs a new column (e.g. a queue/worker
status). Sequence runner → executor.

---

## 3. `claude-agent-sdk` install hardening (small)

`claude-agent-sdk` is currently present only in the `.venv`. It is declared as an **optional** dependency
`atlas-runtime[claude]` ([services/agent-runtime/pyproject.toml:23](../../services/agent-runtime/pyproject.toml#L23))
and lazy-imported in `agents/claude_code.py`, so native-only installs stay lean. Action: document in
`docs/operations/RUNNING.md` that any deployment intending to use the `claude_code` runtime must
`pip install 'atlas-runtime[claude]'` in the runtime's environment, and that it drives the operator's
**local Claude Code subscription session** (no API key). No code change required.

---

## 4. Command Center milestone (after 1–3; large, separate)

Design is already captured in **[.planning/prep/intelligence-layer-alignment.md](intelligence-layer-alignment.md)**
(Michaud "Obsidian-as-OS" → ATLAS alignment, tiered [A]/[B]/[C]/[D], trust deltas, fold-in). Highest-
leverage first artifact = the **Intelligence-Layer context-assembly step [A]**: before a `claude_code`
run, materialize the relevant ATLAS state (active Focus + framework, the run's Project, recent
runs/audit summary, linked wiki pages) into the agent's context — **secret-redacted via
`SECRET_PATTERNS`, provenance-tagged via `MemoryProvenance`, every agent write audited + risk-gated**,
so the agent never starts blank. Concrete starting artifacts (from that note's §"Next concrete
artifacts"):
1. `context_service` (or an assembly step in the run path) building the redacted, provenance-tagged
   agent context from Focus/Project/audit/wiki.
2. `Focus` entity (frozen Pydantic model in `packages/atlas-core/atlas_core/schemas/core.py`) +
   `focus_service.py` + gateway CRUD (`/v1/focus`) mirroring the Projects pattern + an **additive
   migration applied through the new runner**.
3. Named-operation preset entity (daily agent commands).
4. Wire run outcomes → Focus/wiki update (the output→input compounding loop).

Prerequisites for Command Center (unchanged, now partly addressed): migration runner (item 1 ✓ once
built), async executor (item 2), and the **ATLAS-owned auth store (paused phase 10.1)** — which is also
where the **Supabase connection credentials** from the new operator direction should live (never in
prompts, audit payloads, or committed files). CC-2's flagship Google Calendar MCP integration depends on
that auth store. **Note the convergence:** the auth store now serves both the integration credentials
*and* the Supabase backend connection string — pull it forward as a shared prerequisite.

---

## Recommended execution order for the next run
1. **Migration runner** (`atlas db init` + tests + entropy cleanup + run against real DB). Self-contained,
   high value, unblocks everything. Use `/gsd-plan-phase` if formalizing, or execute directly per this spec.
2. **Async run executor** (background execution + gateway enqueue + SSE).
3. **SDK install doc** (trivial, fold into either of the above commits or RUNNING.md).
4. **Modular DB backend (Supabase/Postgres)** — only once credentials arrive; build on the runner's
   backend seam. Likely its own GSD milestone alongside the cashflow app wiring.
5. **Command Center** — large milestone, gated on 1–2 and the auth store.

## Constraints to keep honoring
D-001 (no `foundation/` edits) · D-022 (SDK/MCP confined to Python agent-runtime; Rust = gateway) ·
D-012/13 (atlas-core schema is source of truth; any new entity = frozen Pydantic model + additive
migration **via the runner**) · audit-first, risk-gated, secrets only in the auth store · every
`ALTER ADD COLUMN` is non-idempotent in SQLite — the runner now absorbs that, but new bare-ALTER
migrations should still avoid triggers in the same file so the fallback split stays safe.
