# B4 — Multi-Entity & Consolidation Implementation Plan

> Date: 2026-07-10
> Scope: L2 Cashflow — Multi-entity support for holding companies
> Baseline: Next.js 16 + React 19 + SQLite/Supabase, 17+ tables, repository pattern
> Constraint: D-022 (Rust-first for new infra) applies to Phase 2 cementing; this plan covers the TypeScript/Next.js prototype
> Current state: Single-entity schema; no intercompany or consolidation logic

---

## 0. Why Multi-Entity Matters

L2 Cashflow targets holding companies, holding-families, and groups with subsidiaries. Without multi-entity support, the platform is limited to standalone businesses. The feature set is the gateway to enterprise-tier accounts and higher ARPU.

**Core requirements**:
- Multiple legal entities under one tenant
- Shared chart of accounts with entity-specific overrides
- Intercompany transaction tracking with automatic elimination
- Consolidated financial statements (P&L, BS, CF)
- Minority interest calculation
- Transfer pricing documentation
- Staggered period closing per entity

---

## 1. Entity Data Model

### 1.1 Entity Table

```sql
CREATE TABLE IF NOT EXISTS entities (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  parent_entity_id TEXT REFERENCES entities(id),    -- NULL = root holding
  legal_name      TEXT NOT NULL,
  trade_name      TEXT,
  cnpj            TEXT UNIQUE,
  entity_type     TEXT NOT NULL DEFAULT 'subsidiary',  -- 'holding', 'subsidiary', 'branch', 'spv'
  tax_regime      TEXT DEFAULT 'lucro_real',         -- per entity
  functional_currency TEXT NOT NULL DEFAULT 'BRL',   -- ISO 4217
  reporting_currency  TEXT NOT NULL DEFAULT 'BRL',   -- group reporting currency
  ownership_pct   NUMERIC DEFAULT 100.00,            -- parent's ownership %
  consolidation_method TEXT DEFAULT 'full',           -- 'full', 'proportional', 'equity'
  fiscal_year_end INTEGER DEFAULT 12,                 -- month (1-12)
  active          INTEGER DEFAULT 1,
  address_json    JSONB,
  notes           TEXT,
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_entities_tenant ON entities(tenant_id);
CREATE INDEX idx_entities_parent ON entities(parent_entity_id);
```

### 1.2 Entity Relationship Diagram

```
┌─────────────────────┐
│    Holding (Root)     │
│  parent_entity_id=NULL│
│  entity_type='holding'│
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │              │
┌───▼────┐  ┌─────▼───┐
│ Sub A   │  │ Sub B    │  entity_type='subsidiary'
│ own=80% │  │ own=100% │
│ method= │  │ method=  │
│ full    │  │ full     │
└───┬─────┘  └─────┬───┘
    │               │
┌───▼────┐  ┌──────▼──┐
│ Sub A1  │  │ SPV C    │
│ own=60% │  │ own=51%  │
│ method= │  │ method=  │
│ partial │  │ equity   │
└─────────┘  └─────────┘
```

### 1.3 Consolidation Methods

| Method | When to use | Treatment |
|--------|-------------|-----------|
| **full** | Ownership ≥ 50% and control | 100% consolidation, eliminate intercompany, recognize NCI for minority % |
| **proportional** | Significant influence (20-50%) | Consolidate proportionally to ownership %, no NCI |
| **equity** | Non-controlling (< 20%) or no control | One-line equity method, no line-by-line consolidation |

### 1.4 Intercompany Account Mapping

```sql
CREATE TABLE IF NOT EXISTS intercompany_accounts (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  entity_a_id     TEXT NOT NULL REFERENCES entities(id),
  entity_b_id     TEXT NOT NULL REFERENCES entities(id),
  account_a_id    TEXT NOT NULL,                    -- COA account in entity A
  account_b_id    TEXT NOT NULL,                    -- COA account in entity B
  relationship    TEXT NOT NULL,                    -- 'due_to_due_from', 'revenue_expense', 'loan', 'dividend'
  active          INTEGER DEFAULT 1,
  created_at      TIMESTAMP DEFAULT NOW(),
  CHECK (entity_a_id <> entity_b_id)
);

CREATE INDEX idx_ic_accounts_entities ON intercompany_accounts(entity_a_id, entity_b_id);
```

**Key design decision**: Intercompany accounts are explicitly mapped, not inferred. This avoids false positives in elimination and makes the audit trail clear.

---

## 2. Shared Chart of Accounts (COA)

### 2.1 Architecture: Master COA + Entity Overrides

The COA is split into two layers:
1. **Master COA** — shared template, defined at tenant level
2. **Entity COA Override** — per-entity customization of the master

This means entities share a base structure but can specialize accounts for local tax/regulatory requirements.

### 2.2 Schema

```sql
-- Master COA (tenant-level template)
CREATE TABLE IF NOT EXISTS coa_master (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  account_code    TEXT NOT NULL,                    -- e.g., '1.1.01.001'
  account_name    TEXT NOT NULL,
  account_type    TEXT NOT NULL,                    -- 'asset', 'liability', 'equity', 'revenue', 'expense'
  parent_code     TEXT,                             -- hierarchy
  is_header       INTEGER DEFAULT 0,
  normal_balance  TEXT NOT NULL,                    -- 'debit', 'credit'
  is_intercompany INTEGER DEFAULT 0,               -- marks IC accounts
  active          INTEGER DEFAULT 1,
  created_at      TIMESTAMP DEFAULT NOW(),
  UNIQUE(tenant_id, account_code)
);

-- Entity-level override
CREATE TABLE IF NOT EXISTS coa_entity_override (
  id              TEXT PRIMARY KEY,
  entity_id       TEXT NOT NULL REFERENCES entities(id),
  master_account_id TEXT NOT NULL REFERENCES coa_master(id),
  override_name   TEXT,                            -- local account name (NULL = use master)
  override_type   TEXT,                            -- local account type (NULL = use master)
  local_code      TEXT,                            -- entity-specific code (e.g., for local reporting)
  is_active       INTEGER DEFAULT 1,
  is_intercompany INTEGER,                         -- override IC flag if needed
  created_at      TIMESTAMP DEFAULT NOW(),
  UNIQUE(entity_id, master_account_id)
);

CREATE INDEX idx_override_entity ON coa_entity_override(entity_id);
```

### 2.3 Resolution Logic

```typescript
// lib/coa/resolver.ts

interface ResolvedAccount {
  masterAccount: COAMaster;
  override: COAEntityOverride | null;
  effectiveName: string;
  effectiveType: string;
  isIntercompany: boolean;
  localCode: string | null;
}

function resolveAccount(master: COAMaster, override: COAEntityOverride | null): ResolvedAccount {
  return {
    masterAccount: master,
    override,
    effectiveName: override?.override_name ?? master.account_name,
    effectiveType: override?.override_type ?? master.account_type,
    isIntercompany: override?.is_intercompany ?? master.is_intercompany,
    localCode: override?.local_code ?? null,
  };
}
```

### 2.4 COA Versioning

```sql
CREATE TABLE IF NOT EXISTS coa_version (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  version_name    TEXT NOT NULL,                    -- '2025-BR', '2025-IFRS'
  effective_from  DATE NOT NULL,
  effective_to    DATE,
  created_at      TIMESTAMP DEFAULT NOW()
);
```

Account changes are versioned so historical reports use the COA structure in effect at the time.

---

## 3. Intercompany Transactions

### 3.1 Transaction Schema

```sql
CREATE TABLE IF NOT EXISTS intercompany_transactions (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  entity_debtor_id  TEXT NOT NULL REFERENCES entities(id),   -- entity that owes
  entity_creditor_id TEXT NOT NULL REFERENCES entities(id),  -- entity that is owed
  description     TEXT NOT NULL,
  amount          NUMERIC NOT NULL,
  currency        TEXT NOT NULL DEFAULT 'BRL',
  original_amount NUMERIC,                                   -- if FX conversion applied
  exchange_rate   NUMERIC,
  transaction_date TEXT NOT NULL,
  transaction_type TEXT NOT NULL,                            -- 'service_fee', 'loan', 'dividend', 'management_fee', 'cost_sharing', 'goods_sale'
  reference_number TEXT,
  account_debtor  TEXT NOT NULL,                             -- account code in debtor entity
  account_creditor TEXT NOT NULL,                            -- account code in creditor entity
  elimination_status TEXT DEFAULT 'pending',                 -- 'pending', 'eliminated', 'excluded'
  elimination_id  TEXT,                                      -- FK to elimination_entry
  status          TEXT DEFAULT 'pending',                    -- 'pending', 'confirmed', 'disputed', 'settled'
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW(),
  CHECK (entity_debtor_id <> entity_creditor_id)
);

CREATE INDEX idx_ic_tenant ON intercompany_transactions(tenant_id);
CREATE INDEX idx_ic_entities ON intercompany_transactions(entity_debtor_id, entity_creditor_id);
CREATE INDEX idx_ic_period ON intercompany_transactions(transaction_date, elimination_status);
```

### 3.2 Due-To / Due-From Entry Generation

When an intercompany transaction is confirmed, the system automatically posts double-entry to both entities:

```
Entity A (service provider)          Entity B (service receiver)
  Dr: Due from Entity B (1.2.05)      Dr: Expense - Service Fee (5.1.03)
  Cr: Revenue - IC Services (4.2.01)   Cr: Due to Entity A (2.1.04)
```

```typescript
// lib/intercompany/post-entries.ts

interface ICPosting {
  debtorEntity: string;
  creditorEntity: string;
  amount: Decimal;
  debtorDebitAccount: string;   // Due From
  debtorCreditAccount: string;  // IC Revenue
  creditorDebitAccount: string; // IC Expense
  creditorCreditAccount: string; // Due To
}

function generateICPostings(tx: IntercompanyTransaction): ICPosting[] {
  // Look up intercompany_accounts mapping
  const mapping = getICAccountMapping(tx.entity_debtor_id, tx.entity_creditor_id, tx.transaction_type);

  return [{
    debtorEntity: tx.entity_debtor_id,
    creditorEntity: tx.entity_creditor_id,
    amount: new Decimal(tx.amount),
    debtorDebitAccount: mapping.due_from_account,
    debtorCreditAccount: mapping.ic_revenue_account,
    creditorDebitAccount: mapping.ic_expense_account,
    creditorCreditAccount: mapping.due_to_account,
  }];
}
```

### 3.3 Elimination Entries

During consolidation, intercompany balances must be eliminated to avoid double-counting.

```sql
CREATE TABLE IF NOT EXISTS elimination_entries (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  consolidation_id TEXT NOT NULL,                   -- FK to consolidation_run
  entity_pair     TEXT NOT NULL,                    -- 'entity_a_id:entity_b_id'
  elimination_type TEXT NOT NULL,                   -- 'revenue_expense', 'balance_sheet', 'receivable_payable', 'dividend', 'investment'
  description     TEXT NOT NULL,
  debit_account   TEXT NOT NULL,
  credit_account  TEXT NOT NULL,
  amount          NUMERIC NOT NULL,
  currency        TEXT NOT NULL DEFAULT 'BRL',
  source_ic_tx_ids TEXT[],                          -- which IC transactions were eliminated
  created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_elim_consolidation ON elimination_entries(consolidation_id);
```

**Elimination types**:

| Type | What it eliminates | When |
|------|-------------------|------|
| `revenue_expense` | IC revenue + IC expense | P&L consolidation |
| `balance_sheet` | Due-to + Due-from | BS consolidation |
| `receivable_payable` | IC receivables + payables | Working capital |
| `dividend` | Intercompany dividends | Retained earnings |
| `investment` | Parent's investment in sub + sub's equity | Initial consolidation |

---

## 4. Consolidation Engine

### 4.1 Consolidation Run

```sql
CREATE TABLE IF NOT EXISTS consolidation_runs (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  period          TEXT NOT NULL,                    -- '2025-07'
  status          TEXT DEFAULT 'pending',           -- 'pending', 'in_progress', 'completed', 'failed'
  scope           JSONB NOT NULL,                   -- which entities, which method
  results         JSONB,                            -- final consolidated figures
  elimination_summary JSONB,                        -- total eliminations
  currency_rates  JSONB,                            -- rates used for translation
  started_at      TIMESTAMP,
  completed_at    TIMESTAMP,
  created_by      TEXT,
  created_at      TIMESTAMP DEFAULT NOW()
);
```

### 4.2 Consolidation Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                  Consolidation Pipeline                      │
│                                                             │
│  ┌─────────────┐                                           │
│  │ 1. Collect   │  Gather trial balance from each entity   │
│  │    TBs       │  for the consolidation period             │
│  └──────┬──────┘                                           │
│         │                                                   │
│  ┌──────▼──────┐                                           │
│  │ 2. Currency  │  Translate foreign subsidiary TBs        │
│  │    Translate │  from local → reporting currency          │
│  └──────┬──────┘                                           │
│         │                                                   │
│  ┌──────▼──────┐                                           │
│  │ 3. Eliminate │  Auto-generate elimination entries       │
│  │    IC        │  for matched IC pairs                    │
│  └──────┬──────┘                                           │
│         │                                                   │
│  ┌──────▼──────┐                                           │
│  │ 4. Minority  │  Calculate NCI share of sub's net income │
│  │    Interest  │  and equity                              │
│  └──────┬──────┘                                           │
│         │                                                   │
│  ┌──────▼──────┐                                           │
│  │ 5. Aggregate │  Sum remaining balances per COA line     │
│  │    Lines     │  applying consolidation method           │
│  └──────┬──────┘                                           │
│         │                                                   │
│  ┌──────▼──────┐                                           │
│  │ 6. Validate  │  Check: assets = liabilities + equity,   │
│  │    & Report  │  no orphan eliminations, audit trail     │
│  └──────┬──────┘                                           │
│         │                                                   │
│         ▼                                                   │
│  Consolidated Financial Statements                         │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Currency Translation

For foreign subsidiaries, the consolidation engine translates financial statements from local currency to group reporting currency.

**Method**: Current Rate Method (ASC 830 / IAS 21)

| Financial Statement Item | Translation Rate |
|--------------------------|-----------------|
| Assets | Closing rate (period-end) |
| Liabilities | Closing rate (period-end) |
| Revenue | Average rate for the period |
| Expenses (except depreciation) | Average rate for the period |
| Depreciation/Amortization | Historical rate (asset acquisition date) |
| Equity (paid-in capital) | Historical rate |
| Retained earnings | Computed (not translated directly) |
| Dividends | Rate at declaration date |

**Currency Translation Adjustment (CTA)**: The balancing figure goes to OCI (Other Comprehensive Income) in equity, not P&L.

```typescript
// lib/consolidation/currency-translate.ts

interface TranslationResult {
  translatedTB: TrialBalance;
  cta: Decimal;            // Currency Translation Adjustment
  rates: {
    closingRate: Decimal;
    averageRate: Decimal;
    historicalRates: Map<string, Decimal>;
  };
}

function translateTrialBalance(
  localTB: TrialBalance,
  reportingCurrency: string,
  rates: FXRateTable,
  period: string
): TranslationResult {
  let cta = new Decimal(0);

  const translatedLines = localTB.lines.map(line => {
    const rate = getRateForLineItem(line, rates, period);
    const translatedAmount = new Decimal(line.amount).times(rate);
    cta = cta.plus(translatedAmount.minus(new Decimal(line.amount)));
    return { ...line, amount: translatedAmount, originalAmount: line.amount };
  });

  return { translatedTB: { lines: translatedLines }, cta, rates: {} };
}
```

### 4.4 Minority Interest (Non-Controlling Interest)

When the parent owns less than 100% of a subsidiary, the minority portion of the sub's net income and equity must be recognized separately.

```typescript
// lib/consolidation/minority-interest.ts

interface MinorityInterestResult {
  netIncomeNCI: Decimal;     // NCI share of sub's net income
  equityNCI: Decimal;        // NCI share of sub's equity
  totalNCI: Decimal;
}

function calculateNCI(
  subNetIncome: Decimal,
  subEquity: Decimal,
  parentOwnershipPct: Decimal
): MinorityInterestResult {
  const ncPct = new Decimal(1).minus(parentOwnershipPct.div(100));

  return {
    netIncomeNCI: subNetIncome.times(ncPct),
    equityNCI: subEquity.times(ncPct),
    totalNCI: subNetIncome.times(ncPct).plus(subEquity.times(ncPct)),
  };
}
```

**Consolidated P&L placement**:
```
  Consolidated Net Income
    Attributable to parent shareholders
    Attributable to NCI         ← Minority interest line
```

**Consolidated BS placement**:
```
  Total Equity
    Parent shareholders' equity
    Non-controlling interest    ← Separate line in equity section
```

---

## 5. Transfer Pricing

### 5.1 Purpose

Transfer pricing ensures intercompany transactions are priced at arm's length — the price that unrelated parties would agree to. This is required for:
- Brazilian tax compliance (IN RFB 1.312/2012, Lei 14.596/2023)
- OECD Transfer Pricing Guidelines
- Defence file documentation

### 5.2 Transfer Pricing Rules Schema

```sql
CREATE TABLE IF NOT EXISTS transfer_pricing_rules (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  entity_a_id     TEXT NOT NULL REFERENCES entities(id),
  entity_b_id     TEXT NOT NULL REFERENCES entities(id),
  transaction_type TEXT NOT NULL,                   -- matches intercompany_transactions.transaction_type
  method          TEXT NOT NULL,                    -- 'cupp', 'cpm', 'resale_price', 'cost_plus', 'tnmm', 'profit_split'
  arm_length_min  NUMERIC,                          -- minimum acceptable rate/margin
  arm_length_max  NUMERIC,                          -- maximum acceptable rate/margin
  arm_length_target NUMERIC,                        -- target rate/margin
  benchmark_study JSONB,                            -- reference to comparable data
  effective_from  DATE NOT NULL,
  effective_to    DATE,
  notes           TEXT,
  created_at      TIMESTAMP DEFAULT NOW()
);
```

### 5.3 Transfer Pricing Methods

| Method | When to use | Calculation |
|--------|-------------|-------------|
| **CUP** (Comparable Uncontrolled Price) | Identical/uniform services, commodities | Compare IC price to market price |
| **Resale Price** | Distribution/resale of goods | Resale price × (1 - appropriate gross margin) |
| **Cost Plus** | Manufacturing, services | Cost of production × (1 + appropriate markup) |
| **TNMM** (Transactional Net Margin Method) | Most common, complex transactions | Net profit margin compared to comparables |
| **Profit Split** | Highly integrated operations | Split combined profit based on contribution |

### 5.4 TP Monitoring

```typescript
// lib/transfer-pricing/monitor.ts

interface TPMonitorResult {
  transactionType: string;
  method: string;
  actualRate: Decimal;
  armLengthRange: { min: Decimal; max: Decimal };
  isCompliant: boolean;
  deviationPct: Decimal;
}

function checkTPCompliance(
  tx: IntercompanyTransaction,
  rule: TransferPricingRule
): TPMonitorResult {
  const actualRate = calculateRate(tx, rule.method);
  const isCompliant = actualRate.gte(rule.arm_length_min) && actualRate.lte(rule.arm_length_max);
  const deviationPct = actualRate.minus(rule.arm_length_target).abs().div(rule.arm_length_target).times(100);

  return {
    transactionType: tx.transaction_type,
    method: rule.method,
    actualRate,
    armLengthRange: { min: rule.arm_length_min, max: rule.arm_length_max },
    isCompliant,
    deviationPct,
  };
}
```

---

## 6. Period Closing Per Entity

### 6.1 Staggered Close Workflow

Each entity closes independently. The holding closes only after all subsidiaries are closed.

```sql
CREATE TABLE IF NOT EXISTS entity_period_close (
  id              TEXT PRIMARY KEY,
  entity_id       TEXT NOT NULL REFERENCES entities(id),
  period          TEXT NOT NULL,                    -- '2025-07'
  status          TEXT DEFAULT 'open',              -- 'open', 'closing', 'closed', 'reopened'
  closed_by       TEXT,
  closed_at       TIMESTAMP,
  intercompany_reconciled INTEGER DEFAULT 0,        -- 1 = all IC balances matched
  reconciliation_summary JSONB,                     -- matched/unmatched counts
  close_notes     TEXT,
  created_at      TIMESTAMP DEFAULT NOW(),
  UNIQUE(entity_id, period)
);
```

### 6.2 Close Sequence

```
1. Entity A closes its period (books all regular entries)
2. Entity B closes its period
3. Entity C closes its period
4. System runs IC reconciliation — checks all IC pairs match
5. If unmatched: alert, block consolidation until resolved
6. All entities closed + IC matched → consolidation can proceed
7. Holding closes consolidated period
```

### 6.3 IC Reconciliation

```typescript
// lib/intercompany/reconcile.ts

interface ReconciliationResult {
  entityPair: string;
  entityA: {
    balance: Decimal;
    account: string;
  };
  entityB: {
    balance: Decimal;
    account: string;
  };
  difference: Decimal;
  isReconciled: boolean;
  unmatchedTransactions: IntercompanyTransaction[];
}

function reconcileICPair(
  entityA: string,
  entityB: string,
  period: string,
  txsA: IntercompanyTransaction[],
  txsB: IntercompanyTransaction[]
): ReconciliationResult {
  const balanceA = txsA.reduce((sum, tx) => {
    return tx.entity_debtor_id === entityA
      ? sum.plus(tx.amount)
      : sum.minus(tx.amount);
  }, new Decimal(0));

  const balanceB = txsB.reduce((sum, tx) => {
    return tx.entity_debtor_id === entityB
      ? sum.plus(tx.amount)
      : sum.minus(tx.amount);
  }, new Decimal(0));

  const difference = balanceA.minus(balanceB).abs();

  return {
    entityPair: `${entityA}:${entityB}`,
    entityA: { balance: balanceA, account: 'due_from' },
    entityB: { balance: balanceB, account: 'due_to' },
    difference,
    isReconciled: difference.isZero(),
    unmatchedTransactions: [], // filtered list
  };
}
```

---

## 7. Reporting

### 7.1 Per-Entity Reporting

Each entity generates its own financial statements from its trial balance. No changes needed from single-entity flow.

### 7.2 Consolidated P&L Structure

```
CONSOLIDATED PROFIT & LOSS STATEMENT
Period: July 2025

Revenue
  Revenue from external customers          XXX,XXX
  Intercompany revenue                    (XX,XXX)  ← eliminated
  Total Revenue                           XXX,XXX

Cost of Goods Sold
  Direct costs                            (XX,XXX)
  Intercompany COGS                       (XX,XXX)  ← eliminated
  Total COGS                              (XX,XXX)

Gross Profit                              XXX,XXX

Operating Expenses
  Salaries & benefits                     (XX,XXX)
  Depreciation & amortization             (XX,XXX)
  Intercompany service fees               (XX,XXX)  ← eliminated
  Other operating expenses                (XX,XXX)
  Total Operating Expenses                (XX,XXX)

Operating Income (EBIT)                    XXX,XXX

Other Income / (Expenses)
  Interest income                          X,XXX
  Interest expense                        (X,XXX)
  FX gains / (losses)                     (X,XXX)
  CTA (OCI)                               (X,XXX)  ← currency translation

Income Before Tax                         XXX,XXX

Income Tax                                (XX,XXX)

Consolidated Net Income                   XXX,XXX
  Attributable to parent shareholders    XX,XXX
  Attributable to NCI                     X,XXX    ← minority interest
```

### 7.3 Consolidated Balance Sheet Structure

```
CONSOLIDATED BALANCE SHEET
As of: July 31, 2025

ASSETS
  Current Assets
    Cash and equivalents                  XXX,XXX
    Accounts receivable                   XX,XXX
    Due from subsidiaries                 XX,XXX   ← eliminated
    Inventory                             XX,XXX
  Non-Current Assets
    Property, plant & equipment           XX,XXX
    Intangible assets                     XX,XXX
    Investment in subsidiaries            XX,XXX   ← eliminated
  Total Assets                            XXX,XXX

LIABILITIES
  Current Liabilities
    Accounts payable                      XX,XXX
    Due to subsidiaries                   XX,XXX   ← eliminated
    Tax liabilities                       XX,XXX
  Non-Current Liabilities
    Long-term debt                        XX,XXX
  Total Liabilities                       XXX,XXX

EQUITY
  Share capital                           XX,XXX
  Retained earnings                       XX,XXX
  Currency translation adjustment         (X,XXX)  ← OCI
  Non-controlling interests               X,XXX    ← minority interest
  Total Equity                            XXX,XXX

  Total Liabilities + Equity              XXX,XXX
```

### 7.4 Elimination Adjustments Report

A separate report shows all elimination entries applied during consolidation:

```
ELIMINATION ADJUSTMENTS
Period: July 2025

1. Revenue / Expense Elimination
   Entity A IC Revenue    -XX,XXX (Dr: 4.2.01)
   Entity B IC Expense    -XX,XXX (Cr: 5.1.03)

2. Balance Sheet Elimination
   Entity A Due From B    -XX,XXX (Cr: 1.2.05)
   Entity B Due To A      -XX,XXX (Dr: 2.1.04)

3. Investment Elimination (initial consolidation)
   Parent Investment      -XX,XXX (Dr: 1.3.01)
   Sub Equity             -XX,XXX (Cr: 3.1.01)

Total Eliminations:      -XXX,XXX
```

---

## 8. API Endpoints

### 8.1 Entity Management

```typescript
// POST /api/v1/entities
Body: {
  legal_name: string;
  trade_name?: string;
  cnpj?: string;
  entity_type: 'holding' | 'subsidiary' | 'branch' | 'spv';
  parent_entity_id?: string;
  ownership_pct?: number;
  functional_currency?: string;
  reporting_currency?: string;
  tax_regime?: string;
  consolidation_method?: string;
}
Response: Entity

// GET /api/v1/entities
Query: { tenant_id, active?, entity_type? }
Response: Entity[]

// GET /api/v1/entities/:id
Response: Entity

// GET /api/v1/entities/:id/hierarchy
Response: EntityTree (full org chart with ownership %)

// PUT /api/v1/entities/:id
Body: Partial<Entity>
Response: Entity
```

### 8.2 Intercompany Transactions

```typescript
// POST /api/v1/intercompany/transactions
Body: {
  entity_debtor_id: string;
  entity_creditor_id: string;
  description: string;
  amount: number;
  currency: string;
  transaction_date: string;
  transaction_type: string;
  reference_number?: string;
}
Response: IntercompanyTransaction

// GET /api/v1/intercompany/transactions
Query: { entity_id?, period?, status?, elimination_status? }
Response: IntercompanyTransaction[]

// POST /api/v1/intercompany/transactions/:id/confirm
Response: { entry_debtor_id, entry_creditor_id }

// GET /api/v1/intercompany/reconciliation
Query: { period, entity_pair? }
Response: ReconciliationResult[]
```

### 8.3 Consolidation

```typescript
// POST /api/v1/consolidation/run
Body: {
  period: string;                    // '2025-07'
  entity_ids?: string[];             // subset, or all if omitted
  scope?: {
    include_branches?: boolean;
    consolidation_level?: number;    // depth in hierarchy
  }
}
Response: ConsolidationRun

// GET /api/v1/consolidation/runs
Query: { period?, status? }
Response: ConsolidationRun[]

// GET /api/v1/consolidation/runs/:id
Response: ConsolidationRun (with full results)

// GET /api/v1/consolidation/runs/:id/eliminations
Response: EliminationEntry[]

// GET /api/v1/consolidation/runs/:id/report
Query: { type: 'pnl' | 'bs' | 'cf' | 'eliminations' }
Response: ConsolidatedReport
```

### 8.4 Transfer Pricing

```typescript
// POST /api/v1/transfer-pricing/rules
Body: TransferPricingRule
Response: TransferPricingRule

// GET /api/v1/transfer-pricing/compliance
Query: { period, entity_pair? }
Response: TPMonitorResult[]

// GET /api/v1/transfer-pricing/rules
Query: { entity_a_id?, entity_b_id?, transaction_type? }
Response: TransferPricingRule[]
```

### 8.5 Period Close

```typescript
// POST /api/v1/entities/:id/period/:period/close
Body: { notes?: string }
Response: EntityPeriodClose

// POST /api/v1/entities/:id/period/:period/reopen
Body: { reason: string }
Response: EntityPeriodClose

// GET /api/v1/entities/:id/period/:period/status
Response: EntityPeriodClose (with IC reconciliation)
```

---

## 9. Effort Estimate

| Sub-Feature | Effort (days) | Dependencies | Priority |
|-------------|--------------|--------------|----------|
| **Entity schema + CRUD API** | 3-4 | GL schema (B2) | P0 |
| **Entity hierarchy UI** | 2-3 | Entity schema | P0 |
| **Master COA + entity overrides** | 4-5 | Entity schema, GL (B2) | P0 |
| **COA resolver (effective account logic)** | 2-3 | Master COA | P0 |
| **Intercompany transaction schema** | 2-3 | Entity schema, GL (B2) | P0 |
| **IC posting engine (auto double-entry)** | 3-4 | IC transaction schema | P0 |
| **IC reconciliation logic** | 2-3 | IC posting engine | P0 |
| **IC reconciliation UI** | 2-3 | IC reconciliation logic | P1 |
| **Consolidation run schema** | 2-3 | Entity schema, IC schema | P0 |
| **Currency translation engine** | 3-4 | Consolidation schema | P1 |
| **Elimination entry generation** | 3-4 | IC posting engine, Consolidation schema | P0 |
| **Minority interest calculation** | 2-3 | Consolidation engine | P0 |
| **Consolidation pipeline orchestrator** | 4-5 | All above consolidation pieces | P0 |
| **Consolidated P&L report** | 2-3 | Consolidation pipeline | P0 |
| **Consolidated BS report** | 2-3 | Consolidation pipeline | P0 |
| **Consolidated CF report** | 3-4 | Consolidation pipeline | P1 |
| **Elimination adjustments report** | 1-2 | Elimination entries | P0 |
| **Transfer pricing rules schema** | 1-2 | Entity schema | P1 |
| **TP compliance monitor** | 2-3 | TP rules, IC transactions | P1 |
| **Period close per entity** | 3-4 | Entity schema, GL | P0 |
| **Consolidated period close** | 2-3 | Entity close, IC reconciliation | P0 |
| **Consolidation dashboard UI** | 4-5 | All APIs | P1 |
| **Unit tests** | 4-5 | All calculation modules | P0 |
| **Integration tests** | 3-4 | All modules | P0 |
| **Documentation + handoff** | 1-2 | All above | P1 |

### Summary

| Phase | Scope | Effort |
|-------|-------|--------|
| **MVP** | Entity CRUD + Shared COA + IC Transactions + IC Posting + Elimination + Basic Consolidation (P&L/BS) + Period Close + Tests | 45-60 days |
| **Full** | Currency Translation + Minority Interest + CF Report + Transfer Pricing + Consolidation Dashboard + IC Reconciliation UI | +25-35 days |
| **Total** | Complete multi-entity & consolidation | **70-95 days** |

### Parallelization

- **Entity + COA** can run in parallel with **IC transaction engine**
- **Consolidation pipeline** depends on both above
- **Transfer pricing** can start as soon as IC transactions are defined
- **Reporting** can start as soon as consolidation pipeline has a stub
- **Period close** is mostly independent once entity schema exists

---

## 10. File Structure

```
lib/entity/
├── index.ts                    # Main entry, entity CRUD
├── types.ts                    # Entity types
├── hierarchy.ts                # Org chart, ownership traversal
└── period-close.ts             # Per-entity close logic

lib/coa/
├── master.ts                   # Master COA CRUD
├── override.ts                 # Entity override CRUD
├── resolver.ts                 # Effective account resolution
└── versioning.ts               # COA version management

lib/intercompany/
├── transactions.ts             # IC transaction CRUD
├── post-entries.ts             # Auto double-entry generation
├── reconcile.ts                # IC reconciliation
└── types.ts                    # IC types

lib/consolidation/
├── pipeline.ts                 # Main orchestrator
├── currency-translate.ts       # FX translation
├── elimination.ts              # Elimination entry generation
├── minority-interest.ts        # NCI calculation
├── aggregate.ts                # Line-by-line aggregation
├── validate.ts                 # Post-consolidation checks
└── types.ts                    # Consolidation types

lib/transfer-pricing/
├── rules.ts                    # TP rule CRUD
├── monitor.ts                  # Compliance checking
├── methods.ts                  # CUP, TNMM, Cost Plus, etc.
└── types.ts                    # TP types

app/api/v1/entities/
├── route.ts                    # GET/POST /api/v1/entities
├── [id]/
│   ├── route.ts                # GET/PUT /api/v1/entities/:id
│   ├── hierarchy/route.ts      # GET /api/v1/entities/:id/hierarchy
│   └── period/[period]/
│       ├── close/route.ts      # POST .../close
│       ├── reopen/route.ts     # POST .../reopen
│       └── status/route.ts     # GET .../status

app/api/v1/intercompany/
├── transactions/route.ts       # GET/POST
├── transactions/[id]/confirm/route.ts
└── reconciliation/route.ts     # GET

app/api/v1/consolidation/
├── run/route.ts                # POST
├── runs/route.ts               # GET
├── runs/[id]/
│   ├── route.ts                # GET
│   ├── eliminations/route.ts   # GET
│   └── report/route.ts         # GET

app/api/v1/transfer-pricing/
├── rules/route.ts              # GET/POST
└── compliance/route.ts         # GET

app/actions/
├── entity.ts                   # Server Actions for entity ops
├── intercompany.ts             # Server Actions for IC ops
├── consolidation.ts            # Server Actions for consolidation
└── transfer-pricing.ts         # Server Actions for TP

supabase/migrations/
└── 008_multi_entity.sql        # All multi-entity tables

tests/entity/                   # Entity CRUD tests
tests/intercompany/             # IC posting, reconciliation tests
tests/consolidation/            # Elimination, translation, NCI tests
tests/transfer-pricing/         # TP compliance tests
tests/integration/              # End-to-end consolidation flow
```

---

## 11. Decision Record

### D-ME-001: Explicit IC account mapping (not auto-detection)
**Decision**: Intercompany accounts are explicitly mapped via `intercompany_accounts` table, not auto-detected from account names or balances.
**Rationale**: Auto-detection is fragile — IC relationships can involve many account pairs, and false positives in elimination are dangerous (eliminating non-IC balances silently). Explicit mapping makes the audit trail clear.
**Trade-off**: More setup per entity pair, but eliminates a class of silent consolidation errors.

### D-ME-002: Master COA + override pattern (not separate COAs)
**Decision**: Entities share a master COA with optional per-entity overrides, not completely independent COAs.
**Rationale**: Holding companies need consistent account structures for consolidation. If each entity had its own COA, mapping accounts across entities would be an ongoing nightmare. Overrides handle legitimate local needs (different tax accounts, local regulatory codes).
**Trade-off**: Slightly more complex COA resolution logic, but dramatically simpler consolidation and reporting.

### D-ME-003: Staggered close with IC reconciliation gate
**Decision**: Each entity closes independently, but consolidation is blocked until all IC pairs reconcile.
**Rationale**: Real holding companies have different close schedules (subsidiaries may close weeks apart). Forcing synchronous close would be impractical. But consolidating with unmatched IC balances produces wrong numbers. The gate ensures integrity.
**Trade-off**: Consolidation waits for the slowest entity, but the result is correct.

### D-ME-004: Current Rate Method for FX translation (not temporal)
**Decision**: Use Current Rate Method (ASC 830 / IAS 21) for foreign subsidiary translation, not the temporal method.
**Rationale**: Current Rate Method is the standard for subsidiaries operating in a foreign currency. The temporal method is used when the subsidiary's functional currency is the parent's currency — a rare case. Starting with Current Rate covers 90%+ of use cases.
**Trade-off**: If a customer needs temporal method later, it's an additive feature, not a replacement.

### D-ME-005: Consolidation as a pipeline, not a single transaction
**Decision**: Consolidation runs as a multi-step pipeline (collect → translate → eliminate → NCI → aggregate → validate), not a single database transaction.
**Rationale**: Consolidation for large groups with foreign subsidiaries can be slow. A pipeline allows partial progress visibility, resumability on failure, and step-by-step audit logging. Each step writes its results before the next step reads them.
**Trade-off**: More infrastructure (pipeline runner, intermediate storage), but better reliability and observability for a critical financial process.

---

## Appendix A: Sample Holding Structure

```
L2 Holding Ltda (CNPJ: 00.000.000/0001-00)
├── L2 Tecnologia Ltda (CNPJ: 11.111.111/0001-11) — 100% owned
│   ├── Func: Software development
│   ├── Currency: BRL
│   └── Consolidation: full
├── L2 International Inc (EIN: 12-3456789) — 80% owned
│   ├── Func: US sales office
│   ├── Currency: USD → BRL (group reporting)
│   └── Consolidation: full (NCI = 20%)
├── L2 Investimentos Ltda (CNPJ: 22.222.222/0001-22) — 60% owned
│   ├── Func: Investment vehicle
│   ├── Currency: BRL
│   └── Consolidation: proportional (60%)
└── L2 SPV I Ltda (CNPJ: 33.333.333/0001-33) — 51% owned
    ├── Func: Special purpose vehicle
    ├── Currency: BRL
    └── Consolidation: full (NCI = 49%)
```

## Appendix B: Intercompany Transaction Types

| Type | Description | Typical Accounts |
|------|-------------|-----------------|
| `service_fee` | Management fees, shared services | Due to/from + IC Expense/Revenue |
| `loan` | Intercompany lending | Loan receivable/payable + Interest |
| `dividend` | Profit distribution | Dividend receivable/payable |
| `cost_sharing` | Shared infrastructure costs | Cost allocation + Due to/from |
| `goods_sale` | Sale of goods between entities | IC Revenue + IC COGS |
| `royalty` | IP licensing fees | Royalty expense + Royalty revenue |
| `guarantee` | Intercompany guarantees | Contingent liability disclosure |
