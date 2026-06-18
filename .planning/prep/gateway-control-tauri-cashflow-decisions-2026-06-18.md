# Gateway Control + Tauri Viability + Cashflow Integration — Design & Decisions

Status: design / decisions (prep) · 2026-06-18 · brainstorm output, operator-validated
Scope: (1) how the cockpit/operator starts the gateway when it's down, (2) whether to adopt
Tauri now, (3) how the L2-Cashflow app wires into ATLAS, (4) the modular local-or-Supabase DB
posture for both apps. Written under the **no-bloat doctrine** — every adoption must justify its
weight; defer complexity until it's earned.

---

## Context

- The React cockpit (`services/web-ui-react`) is a **plain Vite SPA** — no Tauri/Electron shell. It
  talks to the Rust gateway at hardcoded `127.0.0.1:8484` and shows GATEWAY · ONLINE/OFFLINE in the
  sidebar (poll of `/health` every 30s). The `/system` route is still `<Migrating>` (not built).
- The gateway is an **API-only** Rust binary (no static serving; CORS already whitelists
  `http://localhost:4173`, `http://127.0.0.1:4173`, and **`tauri://localhost`** —
  `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:705-712`). It is started **manually** today
  (`docs/operations/RUNNING.md` §2).
- A browser SPA is sandboxed: **it cannot spawn a local process**, and when the gateway is down there
  is no backend to call. So a literal in-browser "Start Gateway" button is impossible *in a plain
  browser tab* — it needs a process already running outside the browser (a desktop shell, a terminal,
  or an OS auto-start).
- The cockpit is mid-migration **Svelte (`services/web-ui`) → React (`services/web-ui-react`)**; many
  React routes are still `<Migrating>` placeholders served by the old Svelte cockpit.

---

## Decision 1 — Gateway-start spine: one primitive, three trigger surfaces (BUILD; operator-approved)

**Decision.** Add a single canonical lifecycle command to the existing Python `atlas` CLI:
`atlas gateway start | status | stop`. Everything else just triggers this one primitive — no
duplicated start logic anywhere.

- `start`: locate the `atlas-gateway` binary (env `ATLAS_GATEWAY_BIN`, else PATH, else the known
  `native/atlas-core-rs/target/release/` path), spawn it **detached**, write a PID file
  (`~/.atlas/gateway.pid`), poll `/health` until healthy or timeout, print the URL or a clear error.
  **Idempotent:** if `/health` already passes, it's a no-op ("already running").
- `status`: report `/health` + PID liveness. `stop`: read PID, terminate.

**Three surfaces trigger the same primitive:**
1. **Any terminal** — once the installer puts `atlas` on PATH, `atlas gateway start` works anywhere.
   This is the operator's "command anywhere" requirement *and* the browser-offline fallback (the UI
   shows this exact string with a copy button).
2. **The Tauri shell (later)** — `invoke('start_gateway')` shells out to the same primitive. Real
   in-app button. React feature-detects `window.__TAURI__`: in-shell → button; browser → copy-command.
3. **Login auto-start (optional)** — a Windows startup task runs the same primitive.

**Why this shape.** It satisfies "Tauri *and* web-UI-can-start *and* terminal-command *and* PATH"
with zero duplicated logic, and it makes Tauri non-blocking: the future shell button is a thin caller
of a primitive that already exists and is independently useful.

**UI deliverables alongside it:** build the real **System page** (replaces `<Migrating>`): gateway
status, DB status (reuse `/health`), version, and the start affordance (button in-shell / copy-command
in browser). Upgrade the sidebar OFFLINE dot to open the same panel.

---

## Decision 2 — Tauri: DEFER (lightweight, but premature now)

**Decision.** Do **not** build the Tauri shell yet. Build Decision 1's primitive + PATH + System
page/offline UX now; treat the desktop shell as a later, deliberate milestone.

**Analysis (no-bloat).**
- **For:** Tauri 2 uses the **system WebView2**, not a bundled Chromium (Electron) — a ~3–10 MB app,
  not ~150 MB. Its shell is **Rust**, fitting our existing gateway toolchain. The gateway already
  CORS-allows `tauri://localhost` (the door was intentionally left open). It is the architecturally
  correct home for a true in-app Start/supervise button, native window, installer-with-PATH, and
  auto-update.
- **Against (why defer):** it adds a whole desktop **build / bundle / sign / release / update**
  surface to maintain. The React cockpit is **incomplete** (Svelte→React migration in flight) —
  wrapping a moving target wastes churn. The immediate pain (gateway not running) is **fully** solved
  by the CLI primitive + PATH + offline UX at a fraction of the cost. Browser-served dev is simpler to
  iterate than a packaged desktop app.
- **Net:** Tauri is not runtime bloat, but adopting it *now* is **premature complexity**. Nothing is
  wasted by waiting — the future Tauri button calls the same `atlas gateway start` primitive we build
  now.

**Revisit when:** the React cockpit reaches feature parity (Svelte fully ported / no `<Migrating>`
routes). Then the shell wraps a finished product. Keep the `tauri://localhost` CORS allowance.

---

## Decision 3 — SUPERSEDED 2026-06-18 by Decision 3b (operator override)

> The operator directed that cashflow be made **part of ATLAS** — vendored into the repo (separate
> from its origin), integrated **visually and structurally**, and exposed as an **activatable module**
> toggled in the System page (not everyone needs it). Cashflow is an L2-owned project, so free use is
> granted. Decision 3 below (keep standalone, wire only via external contracts) is retained for the
> rationale but no longer the chosen path. See **Decision 3b**.

## Decision 3b — Cashflow: vendor as an activatable ATLAS module (CHOSEN)

**Decision.** Vendor L2-Cashflow into `services/cashflow` inside the ATLAS repo, **detached from its
original git remote** (copy tree, drop `.git`, strip bloat). It becomes a first-class but **optional
module**: off by default, **activated/deactivated from the System page**, persisted in the ATLAS DB
(`modules` table via the migration runner). When active it surfaces in the cockpit sidebar (visual
integration) and its backend wiring is live (structural integration).

**Why the override is acceptable under no-bloat:** cashflow is L2-owned and a real product surface the
operator wants in the cockpit; gating it behind an activation toggle keeps the default install lean
(the Next.js service isn't built/run unless activated). The cost is stack plurality in the monorepo
(Node alongside Rust/Python/Vite) — accepted deliberately, contained to `services/cashflow`.

**Shape:**
- **Module registry** — a `modules` table (id, name, status active|inactive, activated_at) +
  `module_service.py` (lock-injection pattern) + gateway CRUD (`/v1/modules`, toggle endpoint). The
  React **System page** lists modules with an activate toggle; the sidebar conditionally renders the
  Cashflow nav entry when active.
- **DB backend selectable** (Decision 4) — cashflow's existing repository-toggle becomes a real
  setting (`ATLAS_CASHFLOW_DB=local|supabase`, surfaced in the System page), with **non-destructive**
  initial migration (CREATE TABLE IF NOT EXISTS / additive only — never drops or truncates on setup).
- **Visual** — first cut: cockpit nav entry + a Cashflow route that hosts the vendored app (its own
  Next.js process when activated, reached from the cockpit). A deeper native React/Vite re-skin to the
  glass design system is a later milestone (large); flagged, not done now.
- **Integration** — the MCP/webhooks seams from Decision 3 still apply for agent actuation; vendoring
  doesn't remove them, it just colocates the code.

---

## Decision 3 (original, retained for rationale) — keep standalone, wire via contracts

**What cashflow is** (cloned for inspection at `c:\Users\Davi\Desktop\Projects\L2-Cashflow`,
repo `aDuque-L2/L2-Cashflow`, private): a **Next.js 16 (App Router) + React 19 + Tailwind 4**
finance app (PT-BR domain: clientes, contratos, despesas, faturas, sócios, fluxo-caixa, relatórios).
Stack facts that drive the decision:
- **DB modularity already exists**: a **repository-toggle** between `better-sqlite3` (local) and
  `@supabase/supabase-js` (remote), env-gated via `isSupabaseConfigured()` (`lib/supabase.ts`,
  `lib/repositories/index.ts`), with raw **`supabase/schema.sql`** (16.8 KB). **No Prisma / no ORM
  lock-in** — the `prisma_error.log` in the tree is dead cruft from an abandoned attempt.
- Already ships **`@modelcontextprotocol/sdk`** (an MCP surface, `lib/mcp`), **`lib/webhooks`**
  (`dispatcher.ts` + `types.ts`), a **FinOps engine** (`lib/engine`), `lib/forecast.ts`, `lib/tax.ts`,
  report generation (`docx`, `jspdf`), and **`@opengsd/gsd-core`** (L2 GSD as an npm dep).

**Decision.** Cashflow stays its **own L2 app/repo**; ATLAS wires to it through the integration
contract ATLAS is already building. Do **not** absorb a Next.js/Node app into ATLAS's
Rust+Python+Vite monorepo — that sprawls the stack and imports cashflow's cruft (anti-no-bloat).

**Wiring seams (reuse what both sides already have):**
- **MCP** — cashflow exposes MCP → ATLAS's `ClaudeCodeAgent` (P4) drives cashflow as **audited tool
  calls** through the existing AuditEvent bus + policy/approval gates. This makes **cashflow the
  flagship internal integration** — an L2 app standing in for / ahead of Google Calendar in the
  Command Center's "core loop → one flagship → fan out" sequence (`intelligence-layer-alignment.md`,
  CC-2).
- **Webhooks** — cashflow `lib/webhooks` ↔ ATLAS's signed (HMAC), idempotent inbound+outbound webhook
  contract (defined once, reused): cashflow events → ATLAS missions/dashboard; ATLAS → cashflow
  notifications. Apply the l2-idempotency-antifragility review when built.
- **Credentials** — live in the **ATLAS auth store** (paused phase 10.1, pulled forward as the shared
  prerequisite for both Supabase and integration creds), never in prompts or audit payloads.

---

## Decision 4 — Modular DB & migrations: each app native, share only Supabase + auth

The operator's requirement is "run locally **or** Supabase, with automatic migrations" for both ATLAS
and cashflow. Decision: **don't unify the migration engines** — that's needless coupling. Instead:

- **ATLAS** keeps its plan: the `atlas db init` migration runner (`schema_migrations` tracker + drift
  tolerance) with a **SQLite-now / Postgres-Supabase-later backend seam**
  (`next-steps-db-runner-async-supabase.md`).
- **Cashflow** keeps its **repository-toggle** (better-sqlite3 ↔ supabase-js) + `supabase/schema.sql`.
  It already does local-or-Supabase; leave it native.
- **The shared piece is the Supabase project + credential management**, not the schema or the runner.
  When Supabase creds arrive: both apps point at the same project; each runs its **own** migrations on
  the chosen backend; the auth store holds the connection secrets. "Automatic migrations" = each app
  applies its own pending migrations on boot/deploy against whichever backend is selected.

**Why:** two small, native, well-understood migration paths beat one forced abstraction spanning a
Rust/Python SQL runner and a Node repository toggle. Keeps each app independently deployable.

---

## Decision 5 — Cashflow repo hygiene (recommended; separate repo, needs go-ahead)

Before ATLAS leans on cashflow, recommend a cleanup commit + `.gitignore` on the **cashflow** repo:
- Remove tracked bloat: `tailwindcss-*.log` (×8, ~270 KB), `prisma_error.log`, committed `dev.db` +
  `dev.db-shm` + `dev.db-wal`, scratch `test-db.js` / `test-prisma.js` / `test-phase2.ts` /
  `update-budget.ts`, and the binary `.docx` report (move to docs or drop).
- `.gitignore`: `*.log`, `dev.db*`, `.env*`, `node_modules/`.
Not done in this session — it's a separate repo and outside the ATLAS tree; awaiting operator go-ahead.

---

## Sequencing (next concrete steps)

1. **Gateway-start spine** (Decision 1): `atlas gateway start|status|stop` in the Python CLI + PID
   file + idempotent health-poll + tests. Pairs with the **migration runner** (`atlas db init`) since
   both are `atlas`-CLI + PATH-install concerns — do them in the same install/bootstrap slice.
2. **System page + offline UX** (Decision 1 UI): real `/system` route; copy-command offline panel;
   sidebar OFFLINE → panel. Feature-detect `window.__TAURI__` (stub the in-shell branch for later).
3. **Install/PATH**: ensure `atlas` console script + the gateway binary are discoverable; document the
   PATH step in `docs/operations/RUNNING.md`. (Tauri's bundler owns this on Windows once the shell
   lands.)
4. **Cashflow integration** (Decision 3): after the auth store (10.1) — MCP-drive cashflow from the
   P4 agent as the flagship integration; then the webhook contract. Gate on cashflow repo hygiene.
5. **Tauri shell** (Decision 2): deferred until React cockpit parity; then the in-app Start button +
   supervision + bundled installer.

## Progress log (2026-06-18)

Built and verified this session (branch `feat/cockpit-p3-glass-p4`):

- **Visual fixes** (`d4c3085`) — clean modals + panels above terrain (glass canon).
- **Migration runner + gateway primitive** (`72a4151`) — `atlas_runtime/db.py`
  (`schema_migrations` tracker, idempotent + drift-tolerant + non-destructive apply),
  `atlas db init|status`; `atlas_runtime/gateway_control.py` + `atlas gateway
  start|status|stop`; smoke routed through the runner. Verified: agent-runtime 68→72
  pass; `atlas db init` adopted the real `~/.atlas/atlas.db` cleanly.
- **Cashflow vendored** (`2396007`) — `services/cashflow`, detached from origin, bloat
  stripped (incl. the OOXML skill pack), `VENDORED.md` + hardened `.gitignore`.
- **Module registry backend** (`2703bed`) — `atlas_core...Module`, `0007_modules.sql`
  (table + non-destructive cashflow seed), `module_service.py` (idempotent toggle),
  `atlas module list|activate|deactivate`. Verified: atlas-core 33, agent-runtime 72;
  real DB shows `cashflow  inactive`.

### UI + Rust slice — DONE 2026-06-18

- **Gateway endpoints** (`d4df150`) — `GET /v1/modules`, `POST
  /v1/modules/{id}/activate|deactivate` (writes dispatch to `atlas module …`, read
  back); `db.rs` list/get tolerant of a pre-0007 DB; `default_atlas_cli()` accepts a
  multi-token `ATLAS_CLI` and `gateway_control.start()` injects a working one so a
  primitive-started gateway dispatches writes before the PATH install. +2 Rust tests
  (cargo **42** pass). Live round-trip verified: start → activate → deactivate → stop.
- **System page + module UI** (`406095a`) — real `/system` route (gateway/DB status,
  offline `atlas gateway start` copy-panel with a Tauri-shell stub, modules list with
  activate/deactivate toggle); `api.ts` `listModules`/`setModuleActive`; Sidebar
  renders a dynamic MODULES section (Cashflow appears only when active); first-cut
  Cashflow route embeds the vendored Next.js app. tsc + eslint + vite build green.
- **Cashflow hygiene** (`<this commit>`) — dropped unimported scratch + historical
  reports from the vendored module.

### Cashflow DB backend + install — DONE 2026-06-18

- **Selectable backend** (`7f132ee`) — cashflow's repository layer now selects
  **local SQLite ↔ Supabase** at startup (auto-detect; `ATLAS_CASHFLOW_DB=local|
  supabase` override). Built the missing `lib/repositories/sqlite/` (6 repos) backed
  by the existing non-destructive `lib/db` schema; restored `lib/db` eager full schema
  (enterprise pages depend on it). Verified: tsc clean + live tsx round-trip on local.
- **Install / PATH** (`<docs commit>`) — RUNNING.md now uses `atlas db init` +
  `atlas gateway start`; `scripts/install-atlas-cli.ps1` is a one-shot editable
  install that puts `atlas` on PATH and bootstraps the DB (operator-run).

### Live cashflow process control — DONE 2026-06-18

- `cashflow_control.py` + `atlas cashflow start|status|stop` (`cb7fa34`): detached
  `npm run dev` with `ATLAS_CASHFLOW_DB`, PID/state file, health probe; taskkill /T
  drops the node tree on stop.
- Gateway `/v1/cashflow/status|start|stop` + System-page **Cashflow Process card**
  (`86e4a9e`): local|supabase segmented selector, Start/Stop, live status, Open link;
  backend locked while running. Verified **end-to-end live** through the gateway:
  start → :3000 UP → status running → stop → :3000 down. cargo 42; tsc/eslint/build clean.

### Still remaining

1. **Supabase path exercise:** the Supabase branch is built but untested until creds
   arrive (go into the auth store, then the cockpit can inject them at start).
2. **MCP/webhook agent actuation** of cashflow (the flagship-integration loop).
3. **Tauri shell** (Decision 2): deferred until React cockpit parity.

## Constraints honored

No-bloat (defer Tauri; no monorepo absorption; native migrations per app). D-001 (no `foundation/`
edits). D-022 (SDK/MCP confined to the Python agent-runtime; Rust stays the gateway). Audit-first +
risk-gated (cashflow actions route through the AuditEvent bus + policy gates). Secrets only in the
auth store. YAGNI (one start primitive; build the shell only when it wraps a finished cockpit).
