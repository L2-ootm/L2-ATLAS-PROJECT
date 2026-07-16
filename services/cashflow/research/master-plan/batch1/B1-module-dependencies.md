# B1 — Module Dependency Graph & Build Order

> 42 modules · 7 layers · Generated 2026-07-10
> Sources: F1-F42 findings, REPORT.md, Acumatica/NetSuite/Odoo architecture patterns

---

## 1. Module Dependency Matrix

### Legend

- **R** = Required dependency (must exist before this module)
- **O** = Optional dependency (enhances functionality, not blocking)
- **D** = Downstream dependents (what depends on THIS module)
- **C** = Complexity: S (small), M (medium), L (large), XL (extra-large)

---

### CORE LAYER (10 modules)

#### Auth
| Field | Value |
|-------|-------|
| Required | (none) |
| Optional | (none) |
| Downstream | Approvals, Notifications, Multi-Entity, Banking/Open Finance, Payment Gateways, Payroll, Workflow Engine, Audit Trail |
| Complexity | M |

#### Chart of Accounts
| Field | Value |
|-------|-------|
| Required | (none) |
| Optional | (none) |
| Downstream | General Ledger, Accounts Payable, Accounts Receivable, Expenses, Bank Reconciliation, Tax Engine, Budget, Multi-GAAP, Multi-Entity, Cost Centers, Fixed Assets, Auto-Categorization, Accounting |
| Complexity | M |

#### General Ledger
| Field | Value |
|-------|-------|
| Required | Chart of Accounts |
| Optional | (none) |
| Downstream | Fiscal Year, Accounts Payable, Accounts Receivable, Invoicing, Payments, Expenses, Bank Reconciliation, Tax Engine, SPED, Audit Trail, Multi-GAAP, Cash Flow Forecast, Budget, Multi-Entity, Multi-Currency, Revenue Rec, Fixed Assets, Cost Centers, Lease, AI Forecast, Auto-Categorization, Anomaly Detection, Manufacturing, Healthcare, Agriculture, Services, Accounting, Government APIs |
| Complexity | XL |

#### Fiscal Year
| Field | Value |
|-------|-------|
| Required | General Ledger |
| Optional | (none) |
| Downstream | SPED, Audit Trail, Multi-GAAP, Budget, Multi-Entity, Multi-Currency, Fixed Assets |
| Complexity | S |

#### Accounts Payable
| Field | Value |
|-------|-------|
| Required | General Ledger, Chart of Accounts |
| Optional | (none) |
| Downstream | Payments, Expenses, Tax Engine, Inventory, Marketplace, E-commerce |
| Complexity | L |

#### Accounts Receivable
| Field | Value |
|-------|-------|
| Required | General Ledger, Chart of Accounts |
| Optional | (none) |
| Downstream | Invoicing, Payments, Tax Engine, Receipts, Revenue Rec, Inventory, Healthcare |
| Complexity | L |

#### Invoicing
| Field | Value |
|-------|-------|
| Required | Accounts Receivable, General Ledger |
| Optional | (none) |
| Downstream | NFe/NFS-e/CT-e, Payments, Revenue Rec, Payment Gateways, Recurring Billing, Retail, SaaS, Services, E-commerce |
| Complexity | L |

#### Payments
| Field | Value |
|-------|-------|
| Required | Accounts Payable, Accounts Receivable, General Ledger |
| Optional | (none) |
| Downstream | Bank Reconciliation, Cash Flow Forecast, Receipts, NFe/NFS-e/CT-e, Payment Gateways, Recurring Billing, Anomaly Detection, Retail, Marketplace, E-commerce |
| Complexity | XL |

#### Expenses
| Field | Value |
|-------|-------|
| Required | Accounts Payable, General Ledger |
| Optional | (none) |
| Downstream | Auto-Categorization |
| Complexity | M |

#### Bank Reconciliation
| Field | Value |
|-------|-------|
| Required | General Ledger, Payments, Chart of Accounts |
| Optional | (none) |
| Downstream | Cash Flow Forecast, Receipts, Banking/Open Finance, Anomaly Detection |
| Complexity | L |

---

### COMPLIANCE LAYER (6 modules)

#### Tax Engine
| Field | Value |
|-------|-------|
| Required | General Ledger, Accounts Payable, Chart of Accounts |
| Optional | (none) |
| Downstream | NFe/NFS-e/CT-e, SPED, Tax Calendar, Fixed Assets, Transfer Pricing, Government APIs, Payroll |
| Complexity | XL |

#### NFe/NFS-e/CT-e
| Field | Value |
|-------|-------|
| Required | Tax Engine, Invoicing, General Ledger |
| Optional | Payments |
| Downstream | Government APIs |
| Complexity | XL |

#### SPED
| Field | Value |
|-------|-------|
| Required | Tax Engine, General Ledger, Fiscal Year |
| Optional | (none) |
| Downstream | Government APIs |
| Complexity | XL |

#### Tax Calendar
| Field | Value |
|-------|-------|
| Required | Tax Engine |
| Optional | Fiscal Year |
| Downstream | (leaf) |
| Complexity | S |

#### Audit Trail
| Field | Value |
|-------|-------|
| Required | Auth, General Ledger, Fiscal Year |
| Optional | (none) |
| Downstream | Approvals |
| Complexity | M |

#### Multi-GAAP
| Field | Value |
|-------|-------|
| Required | General Ledger, Fiscal Year, Chart of Accounts |
| Optional | (none) |
| Downstream | Accounting |
| Complexity | L |

---

### OPERATIONS LAYER (5 modules)

#### Cash Flow Forecast
| Field | Value |
|-------|-------|
| Required | General Ledger, Bank Reconciliation, Payments |
| Optional | (none) |
| Downstream | AI Forecast |
| Complexity | L |

#### Receipts
| Field | Value |
|-------|-------|
| Required | Accounts Receivable, Payments, Bank Reconciliation |
| Optional | (none) |
| Downstream | AI Forecast |
| Complexity | M |

#### Budget
| Field | Value |
|-------|-------|
| Required | General Ledger, Chart of Accounts, Fiscal Year |
| Optional | (none) |
| Downstream | (leaf) |
| Complexity | M |

#### Approvals
| Field | Value |
|-------|-------|
| Required | Auth, Audit Trail |
| Optional | (none) |
| Downstream | Workflow Engine |
| Complexity | M |

#### Notifications
| Field | Value |
|-------|-------|
| Required | Auth |
| Optional | (none) |
| Downstream | Workflow Engine |
| Complexity | S |

---

### ADVANCED LAYER (9 modules)

#### Multi-Entity
| Field | Value |
|-------|-------|
| Required | General Ledger, Chart of Accounts, Auth, Fiscal Year |
| Optional | (none) |
| Downstream | Transfer Pricing, Marketplace, Real Estate, Healthcare |
| Complexity | XL |

#### Multi-Currency
| Field | Value |
|-------|-------|
| Required | General Ledger, Payments, Fiscal Year |
| Optional | (none) |
| Downstream | Transfer Pricing, Retail, Marketplace, Agriculture |
| Complexity | L |

#### Revenue Rec
| Field | Value |
|-------|-------|
| Required | General Ledger, Accounts Receivable, Invoicing |
| Optional | (none) |
| Downstream | Deferred Revenue, SaaS |
| Complexity | XL |

#### Deferred Revenue
| Field | Value |
|-------|-------|
| Required | Revenue Rec |
| Optional | (none) |
| Downstream | SaaS, Recurring Billing |
| Complexity | L |

#### Fixed Assets
| Field | Value |
|-------|-------|
| Required | General Ledger, Chart of Accounts, Fiscal Year, Tax Engine |
| Optional | (none) |
| Downstream | Lease, Manufacturing |
| Complexity | L |

#### Inventory
| Field | Value |
|-------|-------|
| Required | Cost Centers, Accounts Payable, Accounts Receivable |
| Optional | General Ledger |
| Downstream | Retail, Manufacturing, Agriculture, E-commerce |
| Complexity | XL |

#### Cost Centers
| Field | Value |
|-------|-------|
| Required | General Ledger, Chart of Accounts |
| Optional | (none) |
| Downstream | Inventory, Manufacturing, Services |
| Complexity | M |

#### Lease
| Field | Value |
|-------|-------|
| Required | Fixed Assets, General Ledger |
| Optional | (none) |
| Downstream | Real Estate |
| Complexity | L |

#### Transfer Pricing
| Field | Value |
|-------|-------|
| Required | Multi-Entity, Multi-Currency, Tax Engine |
| Optional | (none) |
| Downstream | (leaf) |
| Complexity | L |

---

### INDUSTRY LAYER (8 modules)

#### Retail
| Field | Value |
|-------|-------|
| Required | Inventory, Multi-Currency, Payments, Invoicing |
| Optional | E-commerce |
| Downstream | (leaf) |
| Complexity | L |

#### SaaS
| Field | Value |
|-------|-------|
| Required | Revenue Rec, Deferred Revenue, Invoicing |
| Optional | Recurring Billing |
| Downstream | (leaf) |
| Complexity | L |

#### Manufacturing
| Field | Value |
|-------|-------|
| Required | Inventory, Cost Centers, General Ledger |
| Optional | Fixed Assets |
| Downstream | (leaf) |
| Complexity | XL |

#### Marketplace
| Field | Value |
|-------|-------|
| Required | Multi-Entity, Multi-Currency, Payments, Accounts Payable |
| Optional | E-commerce |
| Downstream | (leaf) |
| Complexity | XL |

#### Real Estate
| Field | Value |
|-------|-------|
| Required | Lease, Multi-Entity, General Ledger |
| Optional | (none) |
| Downstream | (leaf) |
| Complexity | L |

#### Healthcare
| Field | Value |
|-------|-------|
| Required | Multi-Entity, Accounts Receivable, General Ledger |
| Optional | (none) |
| Downstream | (leaf) |
| Complexity | L |

#### Agriculture
| Field | Value |
|-------|-------|
| Required | Inventory, Multi-Currency, General Ledger |
| Optional | (none) |
| Downstream | (leaf) |
| Complexity | L |

#### Services
| Field | Value |
|-------|-------|
| Required | Cost Centers, Invoicing, General Ledger |
| Optional | Budget |
| Downstream | (leaf) |
| Complexity | M |

---

### INTEGRATIONS LAYER (6 modules)

#### Banking/Open Finance
| Field | Value |
|-------|-------|
| Required | Bank Reconciliation, Payments, Auth |
| Optional | Multi-Currency |
| Downstream | (leaf) |
| Complexity | XL |

#### Payment Gateways
| Field | Value |
|-------|-------|
| Required | Payments, Invoicing, Auth |
| Optional | Multi-Currency |
| Downstream | (leaf) |
| Complexity | L |

#### Government APIs
| Field | Value |
|-------|-------|
| Required | Tax Engine, NFe/NFS-e/CT-e, SPED |
| Optional | (none) |
| Downstream | (leaf) |
| Complexity | XL |

#### Accounting (Export)
| Field | Value |
|-------|-------|
| Required | General Ledger, Chart of Accounts, Multi-GAAP |
| Optional | (none) |
| Downstream | (leaf) |
| Complexity | M |

#### E-commerce
| Field | Value |
|-------|-------|
| Required | Invoicing, Payments, Inventory |
| Optional | Multi-Currency |
| Downstream | (leaf) |
| Complexity | L |

#### Payroll
| Field | Value |
|-------|-------|
| Required | Tax Engine, General Ledger, Auth |
| Optional | (none) |
| Downstream | (leaf) |
| Complexity | L |

---

### AUTOMATION LAYER (5 modules)

#### Recurring Billing
| Field | Value |
|-------|-------|
| Required | Invoicing, Payments |
| Optional | Deferred Revenue |
| Downstream | (leaf) |
| Complexity | M |

#### Auto-Categorization
| Field | Value |
|-------|-------|
| Required | Expenses, General Ledger, Chart of Accounts |
| Optional | (none) |
| Downstream | (leaf) |
| Complexity | M |

#### Anomaly Detection
| Field | Value |
|-------|-------|
| Required | Bank Reconciliation, Payments, General Ledger |
| Optional | (none) |
| Downstream | (leaf) |
| Complexity | L |

#### AI Forecast
| Field | Value |
|-------|-------|
| Required | Cash Flow Forecast, General Ledger, Receipts |
| Optional | Budget |
| Downstream | (leaf) |
| Complexity | L |

#### Workflow Engine
| Field | Value |
|-------|-------|
| Required | Approvals, Notifications, Auth |
| Optional | (none) |
| Downstream | (leaf) |
| Complexity | L |

---

## 2. Dependency Graph (Textual DAG)

```
LEVEL 0 — Foundation (no dependencies)
├── Auth
└── Chart of Accounts

LEVEL 1 — Core Ledger
└── General Ledger ──→ [Chart of Accounts]

LEVEL 2 — Fiscal + Sub-ledgers
├── Fiscal Year ──→ [General Ledger]
├── Accounts Payable ──→ [General Ledger, Chart of Accounts]
└── Accounts Receivable ──→ [General Ledger, Chart of Accounts]

LEVEL 3 — Transactions
├── Invoicing ──→ [Accounts Receivable, General Ledger]
├── Payments ──→ [Accounts Payable, Accounts Receivable, General Ledger]
└── Expenses ──→ [Accounts Payable, General Ledger]

LEVEL 4 — Compliance + Ops Foundation
├── Bank Reconciliation ──→ [General Ledger, Payments, Chart of Accounts]
├── Tax Engine ──→ [General Ledger, Accounts Payable, Chart of Accounts]
├── Audit Trail ──→ [Auth, General Ledger, Fiscal Year]
├── Multi-GAAP ──→ [General Ledger, Fiscal Year, Chart of Accounts]
└── Notifications ──→ [Auth]

LEVEL 5 — Compliance + Operations
├── NFe/NFS-e/CT-e ──→ [Tax Engine, Invoicing, General Ledger]
├── SPED ──→ [Tax Engine, General Ledger, Fiscal Year]
├── Tax Calendar ──→ [Tax Engine]
├── Cash Flow Forecast ──→ [General Ledger, Bank Reconciliation, Payments]
├── Receipts ──→ [Accounts Receivable, Payments, Bank Reconciliation]
├── Budget ──→ [General Ledger, Chart of Accounts, Fiscal Year]
├── Approvals ──→ [Auth, Audit Trail]
├── Cost Centers ──→ [General Ledger, Chart of Accounts]
└── Multi-Entity ──→ [General Ledger, Chart of Accounts, Auth, Fiscal Year]

LEVEL 6 — Advanced + Integrations
├── Multi-Currency ──→ [General Ledger, Payments, Fiscal Year]
├── Revenue Rec ──→ [General Ledger, Accounts Receivable, Invoicing]
├── Fixed Assets ──→ [General Ledger, Chart of Accounts, Fiscal Year, Tax Engine]
├── Government APIs ──→ [Tax Engine, NFe/NFS-e/CT-e, SPED]
├── Accounting ──→ [General Ledger, Chart of Accounts, Multi-GAAP]
├── Payroll ──→ [Tax Engine, General Ledger, Auth]
├── Banking/Open Finance ──→ [Bank Reconciliation, Payments, Auth]
├── Payment Gateways ──→ [Payments, Invoicing, Auth]
├── Workflow Engine ──→ [Approvals, Notifications, Auth]
└── Auto-Categorization ──→ [Expenses, General Ledger, Chart of Accounts]

LEVEL 7 — Deep Advanced + Integrations
├── Deferred Revenue ──→ [Revenue Rec]
├── Inventory ──→ [Cost Centers, Accounts Payable, Accounts Receivable]
├── Lease ──→ [Fixed Assets, General Ledger]
├── Transfer Pricing ──→ [Multi-Entity, Multi-Currency, Tax Engine]
├── Anomaly Detection ──→ [Bank Reconciliation, Payments, General Ledger]
├── AI Forecast ──→ [Cash Flow Forecast, General Ledger, Receipts]
├── Recurring Billing ──→ [Invoicing, Payments]
└── E-commerce ──→ [Invoicing, Payments, Inventory]

LEVEL 8 — Industry
├── Retail ──→ [Inventory, Multi-Currency, Payments, Invoicing]
├── SaaS ──→ [Revenue Rec, Deferred Revenue, Invoicing]
├── Manufacturing ──→ [Inventory, Cost Centers, General Ledger]
├── Marketplace ──→ [Multi-Entity, Multi-Currency, Payments, Accounts Payable]
├── Real Estate ──→ [Lease, Multi-Entity, General Ledger]
├── Healthcare ──→ [Multi-Entity, Accounts Receivable, General Ledger]
├── Agriculture ──→ [Inventory, Multi-Currency, General Ledger]
└── Services ──→ [Cost Centers, Invoicing, General Ledger]
```

---

## 3. Topological Build Order (Phases)

### Phase 1 — Foundation (4 modules, parallel)
```
Auth · Chart of Accounts
```
No dependencies. Both can be built simultaneously.

### Phase 2 — Core Ledger (1 module)
```
General Ledger
```
Depends on: Chart of Accounts. This is the single most critical module — everything flows through it.

### Phase 3 — Fiscal + Sub-ledgers (3 modules, parallel)
```
Fiscal Year · Accounts Payable · Accounts Receivable
```
All depend on General Ledger only. Build simultaneously.

### Phase 4 — Transactions (3 modules, parallel)
```
Invoicing · Payments · Expenses
```
Invoicing depends on AR + GL. Payments depends on AP + AR + GL. Expenses depends on AP + GL. All can run in parallel since their dependencies are already met.

### Phase 5 — Compliance + Ops Foundation (5 modules, parallel)
```
Bank Reconciliation · Tax Engine · Audit Trail · Multi-GAAP · Notifications
```
Bank Rec depends on GL + Payments + COA. Tax Engine depends on GL + AP + COA. Audit Trail depends on Auth + GL + FY. Multi-GAAP depends on GL + FY + COA. Notifications depends on Auth only. All dependencies met by end of Phase 4. Build simultaneously.

### Phase 6 — Compliance + Operations + Foundations (9 modules, parallel)
```
NFe/NFS-e/CT-e · SPED · Tax Calendar · Cash Flow Forecast · Receipts · Budget · Approvals · Cost Centers · Multi-Entity
```
All dependencies satisfied by Phases 1-5. Build simultaneously.

### Phase 7 — Advanced + Integrations (10 modules, parallel)
```
Multi-Currency · Revenue Rec · Fixed Assets · Government APIs · Accounting · Payroll · Banking/Open Finance · Payment Gateways · Workflow Engine · Auto-Categorization
```
All dependencies satisfied by Phases 1-6. Build simultaneously.

### Phase 8 — Deep Advanced (8 modules, parallel)
```
Deferred Revenue · Inventory · Lease · Transfer Pricing · Anomaly Detection · AI Forecast · Recurring Billing · E-commerce
```
Deferred Revenue needs Revenue Rec (Phase 7). Inventory needs Cost Centers (Phase 6). Lease needs Fixed Assets (Phase 7). Transfer Pricing needs Multi-Entity + Multi-Currency (Phase 7). All others need Phase 7 modules. Build simultaneously.

### Phase 9 — Industry (8 modules, parallel)
```
Retail · SaaS · Manufacturing · Marketplace · Real Estate · Healthcare · Agriculture · Services
```
All depend on Phase 7-8 modules. Build simultaneously.

---

## 4. Critical Path

The **longest dependency chain** determines minimum build time:

```
Auth (L0)
  → General Ledger (L1)
    → Tax Engine (L4)
      → NFe/NFS-e/CT-e (L5)
        → Government APIs (L6)
          → (terminal)

ALTERNATIVE CRITICAL PATH (longest):
Chart of Accounts (L0)
  → General Ledger (L1)
    → Fiscal Year (L2)
      → Audit Trail (L4)
        → Approvals (L5)
          → Workflow Engine (L6)
            → (terminal)

ACTUAL CRITICAL PATH (deepest chain):
Auth (L0)
  → General Ledger (L1)
    → Tax Engine (L4)
      → Transfer Pricing (L7)
        → Marketplace (L8)
          → (terminal)

Chain length: 5 modules, 5 dependency levels
```

**Critical path modules** (any delay here delays the entire project):
1. Auth
2. General Ledger
3. Tax Engine
4. Transfer Pricing / Marketplace chain

**Second critical path** (parallel risk):
1. Chart of Accounts
2. General Ledger
3. Fiscal Year
4. Multi-Entity
5. Multi-Currency
6. Transfer Pricing

---

## 5. Parallelization Opportunities

### Maximum Parallelism per Phase

| Phase | Modules | Max Parallel Streams |
|-------|---------|---------------------|
| 1 | 4 | 4 (Auth + COA are independent) |
| 2 | 1 | 1 (GL blocks everything) |
| 3 | 3 | 3 (FY, AP, AR are independent) |
| 4 | 3 | 3 (Invoicing, Payments, Expenses) |
| 5 | 5 | 5 (all independent after Phase 4) |
| 6 | 9 | 9 (all independent after Phase 5) |
| 7 | 10 | 10 (all independent after Phase 6) |
| 8 | 8 | 8 (all independent after Phase 7) |
| 9 | 8 | 8 (all independent after Phase 8) |

### Team Allocation (suggested)

With **3 parallel developer streams**:

| Stream A (Core) | Stream B (Compliance) | Stream C (Ops/Adv) |
|------------------|----------------------|---------------------|
| Auth | — | Chart of Accounts |
| General Ledger | — | — |
| Fiscal Year | Tax Engine | Accounts Payable |
| Payments | NFe/NFS-e/CT-e | Accounts Receivable |
| Bank Reconciliation | SPED | Invoicing |
| Cash Flow Forecast | Tax Calendar | Expenses |
| Receipts | Government APIs | Budget |
| Multi-Currency | — | Cost Centers |
| Inventory | — | Multi-Entity |
| Fixed Assets | — | Revenue Rec |
| Lease | — | Deferred Revenue |
| Industry modules | Integrations | Advanced modules |

---

## 6. MVP Module Set

The **smallest set that gives a usable product** for a Brazilian business:

### MVP Core (12 modules)
| Module | Why MVP |
|--------|---------|
| Auth | Security foundation |
| Chart of Accounts | Account structure |
| General Ledger | Central ledger |
| Fiscal Year | Period management |
| Accounts Payable | Pay suppliers |
| Accounts Receivable | Collect from customers |
| Invoicing | Issue invoices (NF-e) |
| Payments | Execute payments (Pix/boleto) |
| Expenses | Track expenses |
| Bank Reconciliation | Match bank statements |
| Tax Engine | Calculate taxes |
| NFe/NFS-e/CT-e | Legal invoice compliance |

### MVP Extensions (3 modules, high value)
| Module | Why |
|--------|-----|
| Notifications | Payment reminders, alerts |
| Cash Flow Forecast | Basic treasury visibility |
| Budget | Basic planning |

### MVP Total: 15 modules
### MVP Build Time Estimate: Phases 1-6 (6 phases)

### What MVP Delivers
- Full double-entry bookkeeping
- Invoice creation and sending (NF-e/NFS-e/CT-e compliant)
- Payment processing (Pix, boleto)
- Expense tracking
- Bank reconciliation
- Tax calculation
- Basic cash flow forecasting
- Basic budgeting
- Notification system

### What MVP Does NOT Deliver
- Multi-entity / consolidation
- Multi-currency
- Revenue recognition
- Industry-specific features
- AI-powered automation
- Advanced integrations (Open Finance, e-commerce)
- SPED filing (Phase 6+)

---

## 7. Risk Analysis

### Highest-Risk Modules (by complexity + dependency count)

| Module | Complexity | Deps | Risk |
|--------|-----------|------|------|
| General Ledger | XL | 1 | **CRITICAL** — everything depends on it |
| Tax Engine | XL | 3 | **CRITICAL** — compliance gate |
| NFe/NFS-e/CT-e | XL | 3 | **CRITICAL** — legal requirement in Brazil |
| SPED | XL | 3 | **HIGH** — 4 separate book formats |
| Payments | XL | 3 | **HIGH** — money movement, zero tolerance for bugs |
| Multi-Entity | XL | 4 | **HIGH** — complex consolidation logic |
| Inventory | XL | 3 | **HIGH** — valuation methods, COGS |
| Marketplace | XL | 4 | **HIGH** — escrow, split payments |
| Manufacturing | XL | 3 | **MEDIUM** — BOM, COGS tracking |
| Banking/Open Finance | XL | 3 | **MEDIUM** — regulatory, ITP license |

### Dependency Bottlenecks

Modules with the most downstream dependents (bottleneck risk):

| Module | Downstream Count |
|--------|-----------------|
| General Ledger | 28 modules |
| Chart of Accounts | 13 modules |
| Auth | 8 modules |
| Payments | 9 modules |
| Invoicing | 9 modules |
| Tax Engine | 6 modules |
| Accounts Payable | 6 modules |
| Accounts Receivable | 6 modules |

**General Ledger is the #1 bottleneck.** Any delay in GL cascades to 28 downstream modules. Prioritize GL quality and completeness above all else.

---

## 8. Summary Statistics

| Metric | Value |
|--------|-------|
| Total modules | 42 |
| Build phases | 9 |
| Critical path length | 5 modules |
| Max parallel per phase | 10 (Phase 7) |
| MVP modules | 15 |
| XL modules | 10 |
| L modules | 14 |
| M modules | 12 |
| S modules | 6 |
| Leaf modules (no downstream) | 14 |
| Bottleneck modules (5+ downstream) | 8 |
