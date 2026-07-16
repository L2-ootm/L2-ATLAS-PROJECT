# B1: Technology Stack Decisions — L2 Cashflow Modular Platform

> Decision date: 2026-07-10 · Scope: All platform layers · D-022 applies (Rust-first for new infrastructure)

## Current State Summary

- **Runtime**: Next.js 16.1.6 + React 19.2.3 + Tailwind 4.2.1
- **Database**: better-sqlite3 (dev) + Supabase PostgreSQL (production, deferred)
- **Backend logic**: Next.js Server Actions + API Routes
- **Data access**: Repository pattern with SQLite/Supabase backends (already abstracted)
- **Deployment**: Vercel (cron jobs configured)
- **Existing tables**: 17+ tables with full Supabase DDL + RPC functions

---

## 1. Database

### Options

| | PostgreSQL (production) | SQLite (dev only) | Hybrid (current) |
|---|---|---|---|
| **Pros** | RLS for multi-tenancy, LISTEN/NOTIFY, materialized views, JSONB, full-text search, mature tooling | Zero-config, file-based, fast for single-user dev | Best of both: SQLite dev speed + PG production parity |
| **Cons** | Requires hosted instance or self-host | No RLS, no concurrency, no multi-user, limited type system | Schema drift risk between backends |
| **Migration** | N/A (target) | N/A (dev only) | Current approach — refine it |

### Decision: Hybrid — PostgreSQL (Supabase) for production, SQLite for local dev

**Rationale**: The repository abstraction (`lib/repositories/`) already exists and works. The 17-table schema in `supabase/schema.sql` is production-ready. SQLite serves as the zero-config dev backend.

**Migration path**:
1. Keep current repository abstraction intact
2. Add Drizzle ORM as the query layer (replaces raw better-sqlite3 + Supabase client)
3. Drizzle supports both SQLite and PostgreSQL from the same schema definition
4. Migration tooling: `drizzle-kit generate` → SQL files → apply to both backends
5. Phase 1: Drizzle for new modules only. Phase 2: Migrate existing repositories. Phase 3: Deprecate raw SQL.

**Effort**: 2-3 days for Drizzle setup, 1 week to migrate existing repositories.

**Supabase vs self-hosted**: Supabase wins for L2. Free tier covers MVP, managed RLS, built-in auth, edge functions if needed later. Self-hosted only if vendor lock-in becomes a real constraint (unlikely for financial SaaS).

---

## 2. Backend Runtime

### Options

| | Next.js API Routes (current) | Separate Rust axum backend | Python FastAPI |
|---|---|---|---|
| **Pros** | Already in place, Server Actions work, no extra deployment | D-022 compliance, maximum performance for financial computations, type safety | D-022 prototype language, fast dev, good ORM ecosystem |
| **Cons** | Tied to Next.js lifecycle, cold starts on Vercel, limited background processing | New deployment target, two processes to maintain, initial dev cost | GIL limits concurrency, two runtimes to maintain, not D-022 cement target |
| **Migration** | N/A (current) | Significant refactor | Moderate refactor |

### Decision: Keep Next.js for API layer NOW, extract critical paths to Rust axum later

**Rationale**: The D-022 rule says "Prototype in Python, Cement in Rust." The current Next.js stack IS the prototype. For the modular platform:

- **Phase 1 (MVP)**: Next.js API Routes + Server Actions remain the API surface. The repository abstraction already isolates data access. No need to split the runtime yet.
- **Phase 2 (cementing)**: Extract the financial engine (GL, journal entries, tax calculations, SPED generation) into a Rust axum microservice. Next.js frontend calls the Rust service via internal HTTP/gRPC.
- **Phase 3 (production)**: Rust handles all write-heavy financial operations. Next.js handles read-heavy dashboard/API. Clear separation.

**Migration path**: The repository pattern already supports this. When Rust service is ready, add a new backend implementation that talks to Rust via HTTP instead of directly to the database.

**Effort**: Phase 1 = 0 days (already done). Phase 2 = 2-3 weeks for Rust financial engine.

---

## 3. Event System

### Options

| | Redis Streams | In-process EventEmitter | PostgreSQL LISTEN/NOTIFY |
|---|---|---|---|
| **Pros** | Persistent, consumer groups, replay, battle-tested at scale | Zero dependencies, instant, perfect for single-process | No extra infra, ties to existing PG, reliable |
| **Cons** | Extra dependency (Redis), operational overhead | Lost on restart, no cross-process, no replay | Limited throughput, no consumer groups, complex |
| **Migration** | New dependency | Already available in Node.js | New PG function |

### Decision: PostgreSQL LISTEN/NOTIFY for MVP, Redis Streams for production

**Rationale**: For the modular platform MVP, LISTEN/NOTIFY is sufficient:
- No extra infrastructure to manage
- Works with Supabase (which supports it natively)
- Good enough for <1000 events/sec (financial platforms rarely exceed this)
- The modular system needs events for: `invoice.paid`, `payment.received`, `journal_entry.posted`, etc.

**When to upgrade to Redis Streams**: When you need:
- Cross-service event routing (separate Rust service + Next.js)
- Event replay for debugging/audit
- Consumer groups for parallel processing
- Event retention > seconds

**Migration path**: Define an `EventBus` interface. Implement `PgEventBus` (LISTEN/NOTIFY) for MVP, `RedisEventBus` for production. Same interface, swap at config time.

**Effort**: 2-3 days for PgEventBus, 1 week for Redis Streams.

---

## 4. Plugin System

### Options

| | Dynamic JS/TS imports | WASM modules | Process isolation (child_process/worker_threads) |
|---|---|---|---|
| **Pros** | Native to Node.js, fast loading, full API access | Language-agnostic, sandboxed, portable | True isolation, crash-proof, multi-language |
| **Cons** | No isolation (crash = app crash), shared memory, TS compilation needed | Limited APIs, build complexity, debug harder | Heavy overhead, complex IPC, slow startup |
| **Migration** | Natural for Next.js | Requires build pipeline | Requires architecture redesign |

### Decision: Dynamic JS/TS imports with manifest-driven loading (Phase 1), WASM for untrusted modules (Phase 3)

**Rationale**: The technical report recommends Odoo-style TOML manifests with contribution points. For L2's modular system:

**Phase 1 — Dynamic imports**:
```typescript
// Plugin loader reads manifest, resolves modules
const mod = await import(`@cashflow/mod-${manifest.name}`);
mod.register({ events, api, sidebar });
```
- Modules are npm packages with a `cashflow.toml` manifest
- `contributes.routes`, `contributes.sidebar`, `contributes.events_*` registered at startup
- Lifecycle hooks: `pre_init` → `activate` → `deactivate`

**Phase 2 — Worker threads**: For CPU-heavy modules (tax calculations, SPED generation), run in `worker_threads` to prevent blocking the event loop.

**Phase 3 — WASM**: For third-party/marketplace modules where sandboxing matters. Rust modules compile to WASM and run in a sandboxed runtime (Wasmer/Wasmtime).

**Migration path**: Build the manifest parser + loader first (1 week). Then migrate existing features into the first module (`cashflow-core`).

**Effort**: 1 week for manifest parser + loader. 2 weeks to convert existing features to modules.

---

## 5. Caching

### Options

| | Redis | In-memory (Map/LRU) | PostgreSQL materialized views |
|---|---|---|---|
| **Pros** | Shared across processes, TTL, pub/sub, persistence | Zero latency, zero config | Tied to data source, auto-refresh possible |
| **Cons** | Extra dependency, network latency | Per-process, lost on restart, memory pressure | Refresh cost, stale reads, limited flexibility |
| **Migration** | New dependency | Already available | New PG objects |

### Decision: PostgreSQL materialized views for dashboard data, in-memory LRU for API responses

**Rationale**:
- The existing Supabase schema already has RPC functions that compute aggregates (PnL, billing, cost explorer). These become materialized views.
- Dashboard data (which changes every 10-60 seconds) benefits from PG materialized views with `REFRESH MATERIALIZED VIEW CONCURRENTLY`.
- API response caching: Use `stale-while-revalidate` pattern with in-memory cache (e.g., `lru-cache` package). No Redis needed for MVP.
- Redis caching only when you have multiple application instances (which won't happen until Phase 3+).

**Migration path**: The existing RPC functions (`get_cost_explorer_metrics`, `get_client_pnl`, etc.) become materialized views. Add `REFRESH` calls on write events.

**Effort**: 2-3 days to convert RPCs to materialized views. 1 day for in-memory cache layer.

---

## 6. Background Jobs

### Options

| | Vercel Cron (current) | BullMQ (Redis-backed) | Inngest |
|---|---|---|---|
| **Pros** | Already configured, zero setup, serverless | Durable, retries, priorities, scheduling, mature | Event-driven, built-in retries, step functions, hosted |
| **Cons** | 1-min minimum interval, no state, no retries, execution limit | Requires Redis, operational overhead | Vendor dependency, cost at scale, learning curve |
| **Migration** | N/A (current) | New infrastructure | API integration |

### Decision: Inngest for Phase 1-2, evaluate Temporal for Phase 3

**Rationale**: The platform needs background jobs for:
- Tax calculations (SPED generation, monthly close)
- Invoice generation/reminders
- Bank reconciliation
- Anomaly detection
- Usage aggregation

**Why Inngest over BullMQ**:
- No Redis dependency (simpler ops for L2's current scale)
- Event-driven model fits the modular architecture perfectly
- Built-in step functions for multi-step workflows (payment → journal entry → reconciliation)
- Free tier covers MVP (100K events/month)
- Works with Next.js API Routes (no separate worker process)
- The `vercel.json` cron can be replaced with Inngest scheduled functions

**When to evaluate Temporal**: When you need:
- Complex saga workflows with compensation (multi-entity consolidation)
- Cross-service orchestration (Next.js + Rust service)
- Long-running workflows (days/weeks)
- Visibility and replay for compliance

**Migration path**: Replace `vercel.json` cron with Inngest scheduled functions. The `engine/evaluate` endpoint becomes an Inngest step function.

**Effort**: 1-2 days to set up Inngest, 1 week to migrate existing cron jobs.

---

## 7. Search

### Options

| | PostgreSQL full-text search (tsvector) | Meilisearch | Typesense |
|---|---|---|---|
| **Pros** | Zero infra, good enough for structured data, already in PG | Typo-tolerant, fast, easy API, filters/sorting built-in | Open-source, fast, typo-tolerant |
| **Cons** | Limited ranking, no typo tolerance, complex queries | Extra service, sync complexity | Extra service, less mature than Meilisearch |
| **Migration** | Add tsvector columns | New dependency | New dependency |

### Decision: PostgreSQL tsvector for Phase 1, Meilisearch for Phase 3

**Rationale**: For a financial platform, search is primarily:
- Client lookup (by name, CNPJ, segment)
- Invoice search (by status, date range, amount)
- Journal entry search (by description, account, date)

These are structured queries, not full-text search. PostgreSQL's `ILIKE`, `WHERE` clauses, and GIN indexes on tsvector columns are sufficient for MVP.

**When to add Meilisearch**: When you need:
- Natural language search across documents/invoices
- Faceted search (filter by multiple dimensions simultaneously)
- Typo tolerance for client names
- Search across non-structured data (notes, descriptions)

**Migration path**: Add `tsvector` columns for description fields. Create GIN indexes. Add search API endpoints that use `plainto_tsquery`.

**Effort**: 2-3 days for PG search setup. 1 week for Meilisearch integration (when needed).

---

## 8. Real-time

### Options

| | WebSocket | Server-Sent Events (SSE) | Polling |
|---|---|---|---|
| **Pros** | Bidirectional, low latency, efficient | Simpler, auto-reconnect, HTTP/2 compatible, no extra infra | Simplest, works everywhere, no state |
| **Cons** | Complex connection management, scaling harder, stateful | Unidirectional only, connection limits | Wasteful, higher latency, battery drain |
| **Migration** | New infrastructure | Native to Next.js (Route Handlers) | Already works |

### Decision: SSE for dashboard updates (Phase 1), WebSocket for collaboration (Phase 2)

**Rationale**:
- Dashboard real-time: When an invoice is paid or usage event arrives, the dashboard needs to update. SSE is perfect — unidirectional, auto-reconnect, works with Vercel/serverless.
- The modular platform needs real-time for: live PnL updates, usage event streaming, approval notifications, budget alerts.

**SSE implementation**: Next.js API Route returns `text/event-stream`. Client uses `EventSource` API.

**WebSocket for Phase 2**: When you need:
- Multi-user collaboration (multiple accountants editing the same journal entry)
- Chat/notifications with low latency
- Live cursor presence in shared views

**Migration path**: Add SSE endpoint for `events` stream. Frontend uses `EventSource` to subscribe. Simple and incremental.

**Effort**: 1-2 days for SSE setup. 1 week for WebSocket (when needed).

---

## 9. PDF Generation

### Options

| | jsPDF + AutoTable (current) | React-PDF (@react-pdf/renderer) | Headless Chrome (Puppeteer/Playwright) |
|---|---|---|---|
| **Pros** | Already in use, client-side, fast, simple API | Declarative, design-system aligned, SSR-capable | Pixel-perfect, handles complex layouts, HTML→PDF |
| **Cons** | Limited styling, no complex layouts, font issues | Build complexity, SSR limitations, slower | Heavy dependency, slow, overkill for simple PDFs |
| **Migration** | N/A (current) | Replace jsPDF calls | New infrastructure |

### Decision: jsPDF + AutoTable for invoices/receipts, React-PDF for financial statements

**Rationale**: The current `package.json` already has `jspdf` and `jspdf-autotable`. Keep using them for:
- **Invoices/receipts**: Simple tabular data, fast generation, client-side
- **Quick exports**: Any data table export

Use React-PDF for:
- **Financial statements** (DRE, Balanço Patrimonial): Complex layouts, multi-page, design-system aligned
- **SPED reports**: Need precise formatting
- **Custom reports**: When design quality matters

**Skip headless Chrome**: Overkill for financial PDFs. React-PDF covers the complex cases. jsPDF covers the simple ones.

**Migration path**: Keep existing jsPDF usage. Add React-PDF for new report types. Both can coexist.

**Effort**: 0 days for jsPDF (already done). 2-3 days to set up React-PDF for financial statements.

---

## 10. Testing

### Options

| | Jest | Vitest | pytest (Python) |
|---|---|---|---|
| **Pros** | Mature, wide ecosystem, snapshots, mocking | Vite-native, fast, ESM-first, Jest-compatible API | Python standard, good for data/business logic |
| **Cons** | Slow with large codebases, CommonJS quirks | Newer, smaller ecosystem | Requires Python runtime, not D-022 cement target |
| **Migration** | Already standard | Drop-in replacement | N/A |

### Decision: Vitest for unit/integration tests, Playwright for E2E

**Rationale**:
- **Vitest** over Jest: Faster (Vite-native), ESM-first (matches Next.js 16), compatible Jest API (easy migration), better DX.
- **Playwright** for E2E: Already in the project (`.playwright-cli/` directory exists). Use it for critical user flows: invoice creation, payment processing, report generation.

**Test categories**:
1. **Unit tests** (Vitest): Repository implementations, tax calculations, date utils, validation
2. **Integration tests** (Vitest): API routes, Server Actions, database operations
3. **E2E tests** (Playwright): Critical user journeys, cross-module workflows
4. **Property-based tests** (Vitest + fast-check): Financial calculations, journal entry balancing

**Migration path**: Install Vitest alongside Jest initially. Migrate test files one-by-one. Vitest's Jest-compatible API means most tests work with minimal changes.

**Effort**: 1 day to set up Vitest. Ongoing test writing. E2E tests for critical flows = 1 week.

---

## Decision Summary Table

| Layer | Decision | Confidence | Migration Effort |
|---|---|---|---|
| **Database** | PostgreSQL (Supabase) + SQLite (dev), Drizzle ORM | High | 1-2 weeks |
| **Backend runtime** | Next.js (now) → Rust axum (Phase 2) | High | Phase 2: 2-3 weeks |
| **Event system** | PG LISTEN/NOTIFY (MVP) → Redis Streams (production) | Medium | 2-3 days |
| **Plugin system** | Dynamic imports + TOML manifests | High | 1-2 weeks |
| **Caching** | PG materialized views + in-memory LRU | High | 2-3 days |
| **Background jobs** | Inngest → Temporal (Phase 3) | Medium | 1-2 days |
| **Search** | PG tsvector (MVP) → Meilisearch (Phase 3) | Medium | 2-3 days |
| **Real-time** | SSE (MVP) → WebSocket (Phase 2) | High | 1-2 days |
| **PDF generation** | jsPDF (simple) + React-PDF (complex) | High | 2-3 days |
| **Testing** | Vitest + Playwright | High | 1 day setup |

## Total Estimated Migration Effort

- **Phase 1 (MVP foundation)**: 2-3 weeks
- **Phase 2 (Rust cementing)**: 2-3 weeks
- **Phase 3 (Production hardening)**: 1-2 weeks
- **Total**: 5-8 weeks for complete stack migration

## Key Principles

1. **No premature abstraction**: Keep the repository pattern, don't add ORMs/abstractions until they're needed.
2. **D-022 compliance**: Rust-first for new infrastructure. Current Next.js is the prototype.
3. **Incremental migration**: Each decision has a clear upgrade path. Don't boil the ocean.
4. **Supabase as managed PostgreSQL**: Use Supabase's managed features (RLS, auth, edge functions) rather than building them.
5. **Event-driven architecture**: Every module communicates via events. This is the foundation for the plugin system.
