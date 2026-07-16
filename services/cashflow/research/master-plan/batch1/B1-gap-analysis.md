# B1: Gap Analysis — L2 Cashflow Current vs Target State

**Date**: 2026-07-09
**Scope**: Universal modular financial platform (42-module architecture)
**Baseline**: Next.js 16 + React 19 + SQLite/Supabase internal tool

---

## 1. WHAT EXISTS TODAY

### 1.1 Database Schema (17 tables + 2 system tables)

| Table | Purpose | Completeness |
|-------|---------|--------------|
| `Client` | Basic client CRUD (name, service, payment, dates) | MVP — no multi-entity, no parent/child |
| `Invoice` | Simple invoices (amount, status, dates) | MVP — no line items integration, no NF-e |
| `Expense` | Expenses (category, amount, recurring flag) | MVP — no vendor management, no approval workflow |
| `Partner` / `PartnerTransaction` | Partner wallets and capital injection/withdrawal | MVP — no equity tracking, no distribution rules |
| `AITokenLog` | Legacy AI token logging | Deprecated — superseded by `usage_events` |
| `client_accounts` | Enterprise client accounts (CNPJ, segment, revenue) | Partial — exists but not wired to core Client table |
| `contracts` | Client contracts with AI budget caps | Partial — schema exists, limited CRUD |
| `plans` | Client plans with entitlements | Partial — schema exists, limited CRUD |
| `user_entitlements` | Per-user AI limits and caps | Partial — schema exists, degradation engine uses hardcoded values |
| `usage_events` | AI usage events with token/cost tracking | Functional — webhook receiver works |
| `model_rate_cards` | Model pricing data | Schema only — no auto-sync, no CRUD UI |
| `search_rate_cards` | Search product pricing | Schema only — no auto-sync, no CRUD UI |
| `research_jobs` | Research job tracking | Functional — basic CRUD via repositories |
| `invoice_line_items` | Billing line items | Schema only — no generation pipeline |
| `plus_subscriptions` | Plus subscription management | Partial — insert/read only, no gateway integration |
| `billing_events` | Billing event log | Schema only — no production writes |
| `system_users` | System user auth (email, role, password_hash) | Schema only — no auth middleware, no session management |
| `audit_log` | Audit trail | Schema only — no writes from application code |

### 1.2 Data Layer (6 repositories, dual-backend)

| Repository | SQLite | Supabase | Interface |
|------------|--------|----------|-----------|
| Client | Full CRUD | Full CRUD | IClientRepository |
| Expense | Full CRUD | Full CRUD | IExpenseRepository |
| Invoice | Full CRUD + getOverdue/getByStatus | Full CRUD | IInvoiceRepository |
| Partner | Wallets + Transactions | Wallets + Transactions | IPartnerRepository |
| Usage | getAll/getByClient/log | getAll/getByClient/log | IUsageRepository |
| Research | Full CRUD + ROI stats | Full CRUD + ROI stats | IResearchRepository |

**Not wired to repositories**: `client_accounts`, `contracts`, `plans`, `user_entitlements`, `invoice_line_items`, `plus_subscriptions`, `billing_events`, `system_users`, `audit_log`, `model_rate_cards`, `search_rate_cards`. These are accessed directly via Supabase client in `lib/db/enterprise.ts`.

### 1.3 Pages (15 routes)

| Route | Purpose | Status |
|-------|---------|--------|
| `/` | Landing/home | Minimal |
| `/dashboard` | Main dashboard with stats | Functional |
| `/clientes` | Client management (CRUD) | Functional |
| `/despesas` | Expense management (CRUD) | Functional |
| `/faturas` | Invoice management (CRUD) | Functional |
| `/socios` | Partner wallets/transactions | Functional |
| `/relatorios` | Basic reports | Functional |
| `/fluxo-caixa` | Cash flow view | Functional |
| `/contratos` | Contract management | Partial |
| `/enterprise/billing` | Plus billing metrics | Functional |
| `/enterprise/pnl` | Profit & Loss dashboard | Functional |
| `/enterprise/forecast` | Cost forecast + margin simulator | Functional |
| `/enterprise/explorer` | Cost explorer (by model/user) | Functional |
| `/enterprise/audit` | Audit dashboard | Partial |
| `/enterprise/research` | Research metrics | Functional |
| `/enterprise/reports` | Commercial/operational reports | Functional |

### 1.4 APIs

| Endpoint | Purpose | Auth |
|----------|---------|------|
| `POST /api/webhooks/tokens` | Inbound token usage webhook | None (open) |
| `GET/POST /api/atlas` | REST API for L2 Atlas integration | Bearer token |
| `POST /api/engine/evaluate` | Student risk degradation evaluation | Bearer token (CRON_SECRET) |
| `POST /api/mcp` | MCP server endpoint | None |
| `GET /api/tokens` | Token endpoint | Unknown |

### 1.5 MCP Tools (7 tools)

1. `get_clients` — List/filter clients
2. `get_client_by_id` — Single client lookup
3. `get_financial_summary` — Monthly revenue/expenses/balance
4. `get_invoices` — List/filter invoices by status
5. `get_expenses` — List/filter expenses by month/client
6. `add_expense` — Create expense
7. `get_ai_usage` — List AI usage events

### 1.6 Enterprise Engine

- `getClientPnL()` — Profit & Loss per client/month
- `getCostExplorerMetrics()` — Cost by model and by user
- `getBillingMetrics()` — Plus subscription billing metrics
- `getForecastData()` — Daily avg cost, margin projection, budget alerts
- `simulateMargin()` — What-if margin simulator
- `getCommercialReport()` — Revenue breakdown with Plus
- `getOperationalReport()` — Token/cost/cache analytics
- `evaluateStudentRisk()` — Active degradation engine (hardcoded caps)

### 1.7 Webhook System

- **Outbound**: 14 event types (client/expense/invoice/partner CRUD, usage, budget, degradation)
- **Inbound**: Token usage ingestion via `POST /api/webhooks/tokens`
- **Dispatcher**: Fire-and-forget, 10s timeout, no retry queue

---

## 2. WHAT'S MISSING (42-Module Architecture)

### 2.1 Core Financial Infrastructure (P0)

| Module | Description | Status | Effort |
|--------|-------------|--------|--------|
| **Chart of Accounts** | Hierarchical account tree (assets, liabilities, equity, revenue, expenses) | Missing entirely | 1-2 weeks |
| **Double-Entry Bookkeeping** | Transaction pairs, journal entries, balanced books | Missing entirely | 2-3 weeks |
| **Multi-Currency** | Currency conversion, FX rates, multi-currency accounts | Missing entirely | 1-2 weeks |
| **Financial Periods** | Fiscal year, closing procedures, period locks | Missing entirely | 1 week |
| **Tax Engine** | ICMS, ISS, PIS/COFINS, IRPJ, CSLL calculations | Partial (`lib/tax.ts` exists, unverified) | 2-3 weeks |

### 2.2 Revenue Management (P0-P1)

| Module | Description | Status | Effort |
|--------|-------------|--------|--------|
| **Subscription Lifecycle** | Plan changes, upgrades/downgrades, proration, trials | Schema exists (`plans`, `plus_subscriptions`), no lifecycle logic | 2-3 weeks |
| **Usage-Based Billing** | Metered billing, tiered pricing, overage calculation | Schema exists (`usage_events`), no billing pipeline | 2-3 weeks |
| **Invoice Generation** | PDF generation, NF-e/NFS-e integration, auto-invoicing | Basic CRUD only, no generation | 3-4 weeks |
| **Payment Gateway** | Stripe/PagSeguro integration, payment links, webhooks | No integration, schema exists | 3-4 weeks |
| **Revenue Recognition** | ASC 606 / CPC 47 compliance, deferred revenue | Missing entirely | 2-3 weeks |

### 2.3 Expense Management (P1)

| Module | Description | Status | Effort |
|--------|-------------|--------|--------|
| **Vendor Management** | Vendor profiles, payment terms, bank details | Missing entirely | 1 week |
| **Bill Payments** | AP automation, payment scheduling, batch payments | Missing entirely | 2-3 weeks |
| **Purchase Orders** | PO creation, approval workflows, 3-way matching | Missing entirely | 2-3 weeks |
| **Expense Reports** | Employee expense submission, receipt OCR, approval | Missing entirely | 2-3 weeks |
| **Approval Workflows** | Multi-level approval chains for expenses/invoices | Missing entirely | 1-2 weeks |

### 2.4 Treasury & Cash Management (P1)

| Module | Description | Status | Effort |
|--------|-------------|--------|--------|
| **Bank Account Management** | Multi-account tracking, reconciliation | Missing entirely | 1-2 weeks |
| **Cash Flow Forecasting** | Advanced projection with seasonality, ML | Basic daily-avg forecast exists, no ML | 2-3 weeks |
| **Intercompany Transfers** | Transfer between entities, elimination entries | Missing entirely | 1-2 weeks |
| **Multi-Entity Consolidation** | Consolidated financials across entities | Missing entirely | 3-4 weeks |

### 2.5 Compliance & Governance (P1)

| Module | Description | Status | Effort |
|--------|-------------|--------|--------|
| **RBAC** | Role-based access control, permissions matrix | `system_users` schema exists, no auth middleware | 2-3 weeks |
| **Multi-Tenancy** | Data isolation, tenant-scoped queries | No tenant isolation — all data is shared | 3-4 weeks |
| **Audit Trail Enhancement** | Immutable audit log with write triggers | `audit_log` schema exists, no writes | 1 week |
| **SOX/Internal Controls** | Segregation of duties, approval gates | Missing entirely | 2-3 weeks |
| **Data Export** | PDF/CSV/Excel export for all reports | Missing entirely | 1-2 weeks |

### 2.6 Integrations (P2)

| Module | Description | Status | Effort |
|--------|-------------|--------|--------|
| **Accounting Software Sync** | TOTVS, QuickBooks, Conta Azul integration | Missing entirely | 3-4 weeks |
| **Open Finance API** | Brazilian open banking data retrieval | Missing entirely | 2-3 weeks |
| **Tax Authority APIs** | NF-e, NFS-e, SPED generation | Missing entirely | 4-5 weeks |
| **Banking APIs** | Account balance, transaction fetch | Missing entirely | 2-3 weeks |

### 2.7 AI/ML Capabilities (P2)

| Module | Description | Status | Effort |
|--------|-------------|--------|--------|
| **Anomaly Detection** | Unusual spending/usage pattern detection | Missing entirely | 2-3 weeks |
| **Predictive Analytics** | Revenue/expense forecasting with ML | Basic projection exists, no ML | 3-4 weeks |
| **Auto-Categorization** | AI-powered expense/income categorization | Missing entirely | 1-2 weeks |
| **Smart Reconciliation** | Bank statement matching to transactions | Missing entirely | 2-3 weeks |

### 2.8 Reporting & Analytics (P1)

| Module | Description | Status | Effort |
|--------|-------------|--------|--------|
| **Financial Statements** | DRE, Balance Sheet, Cash Flow Statement | Missing entirely | 3-4 weeks |
| **Tax Reporting** | Tax obligations, DARF, DCTF generation | Missing entirely | 2-3 weeks |
| **Management Reports** | KPI dashboards, trend analysis, benchmarks | Partial (enterprise pages exist) | 1-2 weeks |
| **Ad-Hoc Analytics** | Query builder, custom report generation | Missing entirely | 2-3 weeks |

---

## 3. WHAT NEEDS REWRITING

| Component | Current State | Issue | Rewrite Scope |
|-----------|---------------|-------|---------------|
| `lib/db/index.ts` | SQLite schema in `initDB()` | 17+ tables in one monolithic function; no migrations, no versioning, no index optimization | Full rewrite → migration system (Drizzle/Kysely) |
| `lib/db/enterprise.ts` | 652-line God module | Mixes business logic, data access, and computation; dual Supabase/SQLite paths create divergence | Split into domain services + repository pattern |
| `lib/repositories/` | 6 repository interfaces | Only covers 6 of 17+ tables; remaining 11 tables accessed via raw Supabase client | Extend or replace with unified data layer |
| `app/actions.ts` | Server Actions with `any` types | No validation, no authorization, `data: any` parameters | Type-safe actions with Zod validation |
| `lib/engine/degradation.ts` | Hardcoded `hardCapBrl = 35.00` | Should read from `user_entitlements` table; only Supabase path | Rewrite to use entitlements + support SQLite |
| `lib/webhooks/dispatcher.ts` | Fire-and-forget, no retry | Webhooks silently fail; no delivery tracking, no retry queue | Add retry + dead letter queue + delivery log |
| `lib/mcp/server.ts` | 7 read-heavy tools | No write tools for contracts/plans/entitlements; no enterprise data access | Extend to full CRUD + enterprise tools |
| `app/api/atlas/route.ts` | Manual switch/case routing | Duplicates MCP tool logic; no validation layer | Unify with MCP server or generate from shared spec |
| `app/api/engine/evaluate/route.ts` | Cron-style endpoint | No scheduling mechanism; relies on external cron | Integrate with job scheduler (BullMQ/cron) |
| `lib/forecast.ts` | Simple daily-avg projection | No seasonality, no confidence intervals, no ML | Replace with proper forecasting engine |

---

## 4. PRIORITY CLASSIFICATION

### P0 — Must Have for MVP (Universal Platform Foundation)

| # | Gap | Effort | Blocks |
|---|-----|--------|--------|
| 1 | Migration system (replace monolithic `initDB`) | 1 week | Everything |
| 2 | Chart of Accounts + Double-Entry Ledger | 2-3 weeks | All financial reporting |
| 3 | Multi-tenancy data isolation | 3-4 weeks | Every feature |
| 4 | RBAC + Auth middleware | 2-3 weeks | Every feature |
| 5 | Tax engine (ICMS/ISS/PIS/COFINS) | 2-3 weeks | Invoice generation |
| 6 | Subscription lifecycle engine | 2-3 weeks | Billing, revenue recognition |
| 7 | Unified data layer (all 17+ tables in repositories) | 2 weeks | All features |
| **P0 Total** | | **13-19 weeks** | |

### P1 — Needed for Launch

| # | Gap | Effort | Blocks |
|---|-----|--------|--------|
| 8 | Invoice generation (NF-e/NFS-e) | 3-4 weeks | Client delivery |
| 9 | Payment gateway integration | 3-4 weeks | Revenue collection |
| 10 | Vendor management + Bill payments | 2-3 weeks | Expense maturity |
| 11 | Financial statements (DRE, Balance Sheet) | 3-4 weeks | Compliance |
| 12 | Audit trail write triggers | 1 week | Compliance |
| 13 | Approval workflows | 1-2 weeks | Expense/PO maturity |
| 14 | Webhook retry + delivery tracking | 1 week | Reliability |
| 15 | MCP tools expansion (enterprise CRUD) | 1 week | Atlas integration |
| 16 | Type-safe server actions (Zod validation) | 1-2 weeks | Data integrity |
| **P1 Total** | | **16-21 weeks** | |

### P2 — Nice to Have

| # | Gap | Effort | Blocks |
|---|-----|--------|--------|
| 17 | Multi-currency support | 1-2 weeks | International clients |
| 18 | Cash flow forecasting (ML) | 2-3 weeks | Advanced analytics |
| 19 | Anomaly detection | 2-3 weeks | Fraud prevention |
| 20 | Auto-categorization (AI) | 1-2 weeks | Operational efficiency |
| 21 | Accounting software sync | 3-4 weeks | Ecosystem integration |
| 22 | Open Finance / Banking APIs | 2-3 weeks | Real-time data |
| 23 | Revenue recognition (ASC 606) | 2-3 weeks | GAAP compliance |
| 24 | Ad-hoc analytics / query builder | 2-3 weeks | Power users |
| **P2 Total** | | **16-23 weeks** | |

---

## 5. DEPENDENCY MAP

```
P0.1 Migration System
  └─→ P0.2 Chart of Accounts + Ledger
  └─→ P0.3 Multi-Tenancy
  └─→ P0.4 RBAC + Auth

P0.3 Multi-Tenancy + P0.4 RBAC
  └─→ P0.5 Tax Engine
  └─→ P0.6 Subscription Lifecycle
  └─→ P0.7 Unified Data Layer

P0.5 Tax Engine
  └─→ P1.8 Invoice Generation (NF-e)

P0.6 Subscription Lifecycle
  └─→ P1.9 Payment Gateway
  └─→ P1.15 MCP Expansion

P0.7 Unified Data Layer
  └─→ P1.10 Vendor Management
  └─→ P1.11 Financial Statements
  └─→ P1.12 Audit Trail
  └─→ P1.13 Approval Workflows
  └─→ P1.16 Type-Safe Actions

P1.8 Invoice Generation
  └─→ P2.23 Revenue Recognition

P1.11 Financial Statements
  └─→ P2.17 Multi-Currency
  └─→ P2.24 Ad-Hoc Analytics

P0.7 Unified Data Layer + P1.11
  └─→ P2.18 Cash Flow Forecasting (ML)
  └─→ P2.19 Anomaly Detection
  └─→ P2.20 Auto-Categorization
```

**Critical path**: P0.1 → P0.3+P0.4 → P0.7 → P1.8/P1.9 (minimum viable universal platform)
**Estimated critical path**: 16-22 weeks (3-5 months)

---

## 6. RISK REGISTER

| Risk | Impact | Mitigation |
|------|--------|------------|
| SQLite → production DB migration breaks existing data | High | Migration-first approach; SQLite remains dev-only |
| Supabase RPC functions diverge from local SQLite logic | Medium | Unify via repository pattern; deprecate direct Supabase calls in `enterprise.ts` |
| Hardcoded values in degradation engine | High | Wire to `user_entitlements` table immediately |
| No auth on token webhook endpoint | High | Add API key validation before any multi-tenant work |
| `app/actions.ts` uses `any` types everywhere | Medium | Zod schema validation on every action |
| Webhook fire-and-forget loses events | Medium | Add delivery queue + dead letter log |
| 42-module scope creep | High | Strict P0 → P1 → P2 sequencing; ship P0 foundation first |

---

## 7. RECOMMENDATION

**Phase 1 (Weeks 1-5): Foundation**
- Migration system (Drizzle ORM)
- Multi-tenancy schema
- RBAC + auth middleware
- Unified repository layer for all 17+ tables

**Phase 2 (Weeks 6-10): Core Financial**
- Chart of Accounts + double-entry ledger
- Tax engine (Brazilian tax rules)
- Subscription lifecycle
- Invoice generation pipeline

**Phase 3 (Weeks 11-16): Launch Features**
- Payment gateway (Stripe/PagSeguro)
- Financial statements (DRE, Balance Sheet)
- Vendor management + bill payments
- MCP tools expansion

**Phase 4 (Weeks 17-22): Intelligence**
- ML forecasting
- Anomaly detection
- Auto-categorization
- Advanced integrations

Total estimated effort: **45-63 weeks** (9-13 months) for full 42-module platform.
Minimum viable universal platform (P0+P1): **29-40 weeks** (6-8 months).
