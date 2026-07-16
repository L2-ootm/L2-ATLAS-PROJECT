# B2 — General Ledger + Chart of Accounts Implementation Plan

> Date: 2026-07-10
> Scope: L2 Cashflow — GL module (the #1 bottleneck, 28 downstream dependents)
> Baseline: Next.js 16 + React 19 + SQLite/Supabase, 17+ tables, repository pattern
> Constraint: D-022 (Rust-first for new infra) applies to Phase 2 cementing; this plan covers the TypeScript/Next.js prototype

---

## 0. Why GL is the #1 Priority

General Ledger has **28 downstream dependents** — the highest in the 42-module architecture. Every financial module (AP, AR, Invoicing, Payments, Tax Engine, SPED, Budget, Cash Flow Forecast, Bank Reconciliation, Revenue Recognition, Cost Centers, Multi-Entity, Multi-Currency, Fixed Assets, etc.) depends on GL. Any delay or quality issue in GL cascades to nearly every other module.

Current state: The system has a legacy `Client`/`Invoice`/`Expense` model with no double-entry enforcement, no account hierarchy, no period management. The GL module replaces this with proper accounting infrastructure.

---

## 1. Schema Design

### 1.1 Accounts (Chart of Accounts)

```sql
-- ======================================================================
-- CHART OF ACCOUNTS
-- ======================================================================
-- Each row is one account in the hierarchy. Tenanted via RLS (phase 2).
-- Account numbers follow Brazilian COA conventions: 4-digit base, extensible.

CREATE TABLE IF NOT EXISTS gl_accounts (
  id              TEXT PRIMARY KEY,                    -- UUID
  code            TEXT NOT NULL UNIQUE,                -- e.g. '1.1.01.001' (hierarchical number)
  name            TEXT NOT NULL,                       -- e.g. 'Caixa Geral'
  name_short      TEXT,                                -- abbreviated name for reports
  account_type    TEXT NOT NULL CHECK (account_type IN (
                    'asset', 'liability', 'equity',
                    'revenue', 'expense', 'contra_asset',
                    'contra_liability', 'contra_equity',
                    'contra_revenue', 'contra_expense'
                  )),
  normal_balance  TEXT NOT NULL CHECK (normal_balance IN ('debit', 'credit')),
  -- Normal balance must be consistent with account_type:
  --   asset/expense/contra_liability/contra_equity/contra_revenue → debit
  --   liability/equity/revenue/contra_asset/contra_expense → credit

  parent_id       TEXT REFERENCES gl_accounts(id) ON DELETE RESTRICT,
  -- Tree structure: parent_id IS NULL for root nodes

  is_leaf         INTEGER NOT NULL DEFAULT 1,          -- 1 = can post transactions, 0 = summary only
  is_active       INTEGER NOT NULL DEFAULT 1,
  is_system       INTEGER NOT NULL DEFAULT 0,          -- 1 = built-in (Caixa, Banco, etc.), cannot delete

  currency_code   TEXT NOT NULL DEFAULT 'BRL',         -- ISO 4217
  cost_center_id  TEXT,                                -- FK to cost_centers (Phase 5)

  metadata_json   TEXT,                                -- extensible attributes

  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

  -- Ensure code hierarchy matches parent_id hierarchy
  -- (enforced at application level; DB-level CHECK is too complex for SQLite)
  CONSTRAINT chk_leaf_no_children CHECK (
    (is_leaf = 1) OR (is_leaf = 0)
  )
);

-- Indexes for hierarchy traversal and lookup
CREATE INDEX IF NOT EXISTS idx_gl_accounts_parent ON gl_accounts(parent_id);
CREATE INDEX IF NOT EXISTS idx_gl_accounts_type ON gl_accounts(account_type);
CREATE INDEX IF NOT EXISTS idx_gl_accounts_code ON gl_accounts(code);
```

**Design rationale**:
- `code` is the human-readable account number (hierarchical, dot-separated). The Brazilian COA convention uses 4-digit groupings: `1.1.01.001` = Assets > Current > Cash > General Cash.
- `normal_balance` is derived from `account_type` at the application layer but stored redundantly for query convenience.
- `is_leaf` controls posting: only leaf accounts accept journal entry lines.
- `parent_id` forms the tree. Rollup queries use recursive CTEs.
- `is_system` prevents deletion of foundational accounts (Caixa, Banco, etc.).
- `cost_center_id` is a forward reference to Cost Centers module (Phase 5).

### 1.2 Journal Entries

```sql
-- ======================================================================
-- JOURNAL ENTRIES (the header)
-- ======================================================================
-- Each journal entry is an atomic, balanced transaction.
-- One entry = one business event (sale, purchase, payment, adjustment).

CREATE TABLE IF NOT EXISTS gl_journal_entries (
  id                TEXT PRIMARY KEY,                  -- UUID
  entry_number      TEXT NOT NULL UNIQUE,              -- sequential: 'JE-2026-000001'
  tenant_id         TEXT,                              -- for multi-tenancy (Phase 2)

  entry_date        TEXT NOT NULL,                     -- YYYY-MM-DD (business date)
  posting_date      TEXT NOT NULL,                     -- YYYY-MM-DD (when posted to GL)
  period_id         TEXT NOT NULL REFERENCES gl_periods(id),

  entry_type        TEXT NOT NULL CHECK (entry_type IN (
                      'standard',      -- normal journal entry
                      'adjusting',     -- period-end adjustments
                      'closing',       -- year-end closing
                      'reversing',     -- auto-reversal of adjusting entries
                      'recurring',     -- template for recurring entries
                      'opening'        -- opening balance entry for new period
                    )),

  description       TEXT NOT NULL,                     -- human-readable description
  reference_type    TEXT,                              -- e.g. 'invoice', 'expense', 'contract'
  reference_id      TEXT,                              -- ID of the referenced entity
  source            TEXT NOT NULL DEFAULT 'manual',    -- 'manual', 'api', 'migration', 'auto'

  -- Balance validation
  total_debit       NUMERIC NOT NULL DEFAULT 0,
  total_credit      NUMERIC NOT NULL DEFAULT 0,

  status            TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
                      'draft',        -- editable, not yet posted
                      'pending',      -- awaiting approval (optional)
                      'posted',       -- locked, affects account balances
                      'voided'        -- cancelled (never posted or reversed)
                    )),

  -- Reversal support
  reversal_of       TEXT REFERENCES gl_journal_entries(id),  -- FK to original entry
  is_reversal       INTEGER NOT NULL DEFAULT 0,              -- 1 if THIS is a reversal
  reversal_date     TEXT,                                    -- auto-reversal date (for adjusting entries)

  -- Approval workflow (Phase 3+)
  prepared_by       TEXT,                              -- user who created
  approved_by       TEXT,                              -- user who approved
  approved_at       TIMESTAMP WITH TIME ZONE,

  metadata_json     TEXT,

  created_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

  -- Double-entry invariant: total debits must equal total credits
  -- This is a conceptual constraint; enforced by trigger/application
  CONSTRAINT chk_balanced CHECK (total_debit = total_credit),
  CONSTRAINT chk_not_zero CHECK (total_debit > 0 AND total_credit > 0)
);

CREATE INDEX IF NOT EXISTS idx_gl_je_period ON gl_journal_entries(period_id);
CREATE INDEX IF NOT EXISTS idx_gl_je_status ON gl_journal_entries(status);
CREATE INDEX IF NOT EXISTS idx_gl_je_date ON gl_journal_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_gl_je_reference ON gl_journal_entries(reference_type, reference_id);
CREATE INDEX IF NOT EXISTS idx_gl_je_reversal ON gl_journal_entries(reversal_of);
```

### 1.3 Journal Entry Lines

```sql
-- ======================================================================
-- JOURNAL ENTRY LINES (the legs)
-- ======================================================================
-- Each line is one side of a double-entry transaction.
-- Every entry must have ≥2 lines; the sum of debits = sum of credits.

CREATE TABLE IF NOT EXISTS gl_journal_entry_lines (
  id                TEXT PRIMARY KEY,                  -- UUID
  journal_entry_id  TEXT NOT NULL REFERENCES gl_journal_entries(id) ON DELETE CASCADE,
  line_number       INTEGER NOT NULL,                 -- sequence within entry (1, 2, 3...)

  account_id        TEXT NOT NULL REFERENCES gl_accounts(id),

  -- Exactly one of debit/credit must be > 0, the other = 0
  debit             NUMERIC NOT NULL DEFAULT 0 CHECK (debit >= 0),
  credit            NUMERIC NOT NULL DEFAULT 0 CHECK (credit >= 0),

  description       TEXT,                              -- line-level description (optional)

  -- Sub-ledger references (for AP/AR/Bank Reconciliation linking)
  subledger_type    TEXT,                              -- 'ap_invoice', 'ar_invoice', 'bank_transaction'
  subledger_id      TEXT,

  cost_center_id    TEXT,                              -- per-line cost center override

  metadata_json     TEXT,

  created_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

  -- Each line must be either a debit or a credit, not both and not neither
  CONSTRAINT chk_debit_xor_credit CHECK (
    (debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)
  ),
  CONSTRAINT chk_positive_amounts CHECK (debit >= 0 AND credit >= 0),
  CONSTRAINT uq_je_line_number UNIQUE (journal_entry_id, line_number)
);

CREATE INDEX IF NOT EXISTS idx_gl_jel_entry ON gl_journal_entry_lines(journal_entry_id);
CREATE INDEX IF NOT EXISTS idx_gl_jel_account ON gl_journal_entry_lines(account_id);
CREATE INDEX IF NOT EXISTS idx_gl_jel_subledger ON gl_journal_entry_lines(subledger_type, subledger_id);
```

### 1.4 Periods (Fiscal Year + Period Management)

```sql
-- ======================================================================
-- FISCAL PERIODS
-- ======================================================================
-- Defines the accounting calendar. Each period can be open, soft-closed,
-- or hard-closed. Journal entries reference a period_id.

CREATE TABLE IF NOT EXISTS gl_periods (
  id              TEXT PRIMARY KEY,                    -- UUID
  fiscal_year_id  TEXT NOT NULL REFERENCES gl_fiscal_years(id),
  period_number   INTEGER NOT NULL,                   -- 1-13 (13th = adjustment period)
  name            TEXT NOT NULL,                       -- e.g. 'Jan/2026' or '01/2026'

  start_date      TEXT NOT NULL,                       -- YYYY-MM-DD
  end_date        TEXT NOT NULL,                       -- YYYY-MM-DD

  status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
                    'open',        -- transactions allowed
                    'soft_closed', -- adjustments allowed (adjusting/reversing entries)
                    'hard_closed'  -- no entries allowed at all
                  )),

  closed_by       TEXT,
  closed_at       TIMESTAMP WITH TIME ZONE,

  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT chk_period_dates CHECK (start_date <= end_date),
  CONSTRAINT uq_period_number UNIQUE (fiscal_year_id, period_number)
);

CREATE INDEX IF NOT EXISTS idx_gl_periods_year ON gl_periods(fiscal_year_id);
CREATE INDEX IF NOT EXISTS idx_gl_periods_status ON gl_periods(status);
CREATE INDEX IF NOT EXISTS idx_gl_periods_dates ON gl_periods(start_date, end_date);
```

### 1.5 Fiscal Years

```sql
-- ======================================================================
-- FISCAL YEARS
-- ======================================================================

CREATE TABLE IF NOT EXISTS gl_fiscal_years (
  id              TEXT PRIMARY KEY,                    -- UUID
  tenant_id       TEXT,                                -- for multi-tenancy
  year            INTEGER NOT NULL,                    -- e.g. 2026
  name            TEXT NOT NULL,                       -- e.g. 'Exercício 2026'

  start_date      TEXT NOT NULL,                       -- YYYY-MM-DD
  end_date        TEXT NOT NULL,                       -- YYYY-MM-DD

  status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
                    'open',
                    'closing',      -- year-end close in progress
                    'closed'        -- fully closed, opening balances carried forward
                  )),

  closed_by       TEXT,
  closed_at       TIMESTAMP WITH TIME ZONE,

  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT chk_fy_dates CHECK (start_date < end_date),
  CONSTRAINT uq_fiscal_year UNIQUE (tenant_id, year)
);
```

### 1.6 Account Balances (Materialized View)

```sql
-- ======================================================================
-- ACCOUNT BALANCES (materialized view for read optimization)
-- ======================================================================
-- This is a CQRS projection: write to journal_entry_lines, read from here.
-- Refreshed on every POST operation (or periodically for bulk imports).

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_account_balances AS
SELECT
  jel.account_id,
  je.period_id,
  SUM(jel.debit)  AS total_debit,
  SUM(jel.credit) AS total_credit,
  -- Balance depends on normal_balance of the account:
  --   debit-normal: debit - credit (positive = normal)
  --   credit-normal: credit - debit (positive = normal)
  CASE
    WHEN a.normal_balance = 'debit' THEN SUM(jel.debit) - SUM(jel.credit)
    ELSE SUM(jel.credit) - SUM(jel.debit)
  END AS balance,
  COUNT(jel.id) AS line_count
FROM gl_journal_entry_lines jel
JOIN gl_journal_entries je ON je.id = jel.journal_entry_id
JOIN gl_accounts a ON a.id = jel.account_id
WHERE je.status = 'posted'
GROUP BY jel.account_id, je.period_id, a.normal_balance;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_balances_account_period
  ON mv_account_balances(account_id, period_id);
```

**Refresh strategy** (see Section 6 for details): `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_account_balances` triggered after each POST operation. For SQLite dev backend, use a regular table with manual refresh.

---

## 2. Double-Entry Enforcement

Double-entry bookkeeping has two invariants:
1. **Line-level**: Each line is either a debit OR a credit (never both, never neither)
2. **Entry-level**: Sum of all debits = Sum of all credits across all lines

### 2.1 Layer 1: SQL CHECK Constraints (Database)

Already in schema above:
- `gl_journal_entry_lines`: `chk_debit_xor_credit` — `(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)`
- `gl_journal_entries`: `chk_balanced` — `total_debit = total_credit`
- `gl_journal_entries`: `chk_not_zero` — `total_debit > 0 AND total_credit > 0`

**Note on SQLite limitations**: SQLite supports CHECK constraints but NOT function-based CHECK constraints in all versions. The `chk_balanced` constraint will work on PostgreSQL (via Supabase) but should be validated at the application layer for SQLite dev mode. The PostgreSQL trigger (below) provides a stronger guarantee.

### 2.2 Layer 2: PostgreSQL Trigger (Production)

```sql
-- ======================================================================
-- BALANCE VALIDATION TRIGGER
-- ======================================================================
-- Runs AFTER INSERT/UPDATE/DELETE on gl_journal_entry_lines.
-- Recalculates totals on the parent journal entry and validates balance.

CREATE OR REPLACE FUNCTION fn_validate_journal_balance()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_je_id TEXT;
  v_total_debit NUMERIC;
  v_total_credit NUMERIC;
  v_line_count INTEGER;
  v_je_status TEXT;
BEGIN
  -- Determine which journal entry to validate
  v_je_id := COALESCE(NEW.journal_entry_id, OLD.journal_entry_id);

  -- Get the entry status
  SELECT status INTO v_je_status
  FROM gl_journal_entries WHERE id = v_je_id;

  -- Skip validation for voided entries
  IF v_je_status = 'voided' THEN
    RETURN COALESCE(NEW, OLD);
  END IF;

  -- Recalculate totals from lines
  SELECT
    COALESCE(SUM(debit), 0),
    COALESCE(SUM(credit), 0),
    COUNT(id)
  INTO v_total_debit, v_total_credit, v_line_count
  FROM gl_journal_entry_lines
  WHERE journal_entry_id = v_je_id;

  -- Must have at least 2 lines
  IF v_line_count < 2 THEN
    RAISE EXCEPTION 'Journal entry % must have at least 2 lines (has %)', v_je_id, v_line_count;
  END IF;

  -- Debits must equal credits
  IF v_total_debit != v_total_credit THEN
    RAISE EXCEPTION 'Journal entry % is not balanced: debits=%, credits=%', v_je_id, v_total_debit, v_total_credit;
  END IF;

  -- Must be non-zero
  IF v_total_debit = 0 OR v_total_credit = 0 THEN
    RAISE EXCEPTION 'Journal entry % has zero totals: debits=%, credits=%', v_je_id, v_total_debit, v_total_credit;
  END IF;

  -- Update the header
  UPDATE gl_journal_entries
  SET total_debit = v_total_debit,
      total_credit = v_total_credit,
      updated_at = CURRENT_TIMESTAMP
  WHERE id = v_je_id;

  RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE TRIGGER trg_validate_journal_balance
  AFTER INSERT OR UPDATE OR DELETE ON gl_journal_entry_lines
  FOR EACH ROW
  EXECUTE FUNCTION fn_validate_journal_balance();
```

### 2.3 Layer 3: Application-Level Validation (TypeScript)

```typescript
// lib/gl/validator.ts

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

export function validateJournalEntry(entry: {
  lines: Array<{ account_id: string; debit: number; credit: number }>;
  description: string;
}): ValidationResult {
  const errors: string[] = [];

  // Minimum 2 lines
  if (entry.lines.length < 2) {
    errors.push('Journal entry must have at least 2 lines');
  }

  // Each line: debit XOR credit
  for (const line of entry.lines) {
    const isDebit = line.debit > 0 && line.credit === 0;
    const isCredit = line.credit > 0 && line.debit === 0;
    if (!isDebit && !isCredit) {
      errors.push(`Line account ${line.account_id}: must be exactly debit or credit`);
    }
    if (line.debit < 0 || line.credit < 0) {
      errors.push(`Line account ${line.account_id}: amounts must be non-negative`);
    }
  }

  // Total debits = total credits
  const totalDebit = entry.lines.reduce((s, l) => s + l.debit, 0);
  const totalCredit = entry.lines.reduce((s, l) => s + l.credit, 0);
  if (totalDebit !== totalCredit) {
    errors.push(`Entry is not balanced: debits=${totalDebit}, credits=${totalCredit}`);
  }
  if (totalDebit === 0) {
    errors.push('Entry totals cannot be zero');
  }

  // Description required
  if (!entry.description || entry.description.trim().length === 0) {
    errors.push('Description is required');
  }

  return { valid: errors.length === 0, errors };
}
```

### 2.4 Enforcement Summary

| Layer | Scope | Catches |
|-------|-------|---------|
| SQL CHECK | Per-row (line) | Invalid debit/credit on a single line |
| PostgreSQL trigger | Per-entry (aggregate) | Unbalanced entries, <2 lines |
| Application (TypeScript) | Pre-submit | All of the above + UX feedback |
| SQLite dev mode | Application only | Same as TypeScript layer (no PG triggers) |

---

## 3. Account Hierarchy

### 3.1 Tree Structure

The hierarchy uses `parent_id` self-referencing FK. Root accounts (level 0) have `parent_id IS NULL`.

**Standard Brazilian COA structure**:

```
Level 0 (Root):     1          Ativo (Assets)
Level 1:            1.1        Ativo Circulante (Current Assets)
Level 2:            1.1.01     Disponibilidades (Cash & Equivalents)
Level 3 (Leaf):     1.1.01.001 Caixa Geral
Level 3 (Leaf):     1.1.01.002 Banco Itaú CC 12345
Level 2:            1.1.02     Contas a Receber (Receivables)
Level 3 (Leaf):     1.1.02.001 Clientes Nacionais

Level 0:            2          Passivo (Liabilities)
Level 1:            2.1        Passivo Circulante (Current Liabilities)
Level 2:            2.1.01     Fornecedores (Payables)
Level 3 (Leaf):     2.1.01.001 Fornecedores Nacionais

Level 0:            3          Patrimônio Líquido (Equity)
Level 1:            3.1        Capital Social
Level 3 (Leaf):     3.1.01.001 Capital Social Integralizado

Level 0:            4          Receitas (Revenue)
Level 1:            4.1        Receita Operacional
Level 3 (Leaf):     4.1.01.001 Receita de Serviços

Level 0:            5          Despesas (Expenses)
Level 1:            5.1        Despesas Operacionais
Level 2:            5.1.01     Despesas com Pessoal
Level 3 (Leaf):     5.1.01.001 Salários
```

### 3.2 Rollup Queries

**Recursive CTE for account tree**:

```sql
-- Get full account tree with path and level
WITH RECURSIVE account_tree AS (
  -- Base: root accounts
  SELECT
    id, code, name, parent_id, account_type, normal_balance,
    is_leaf, 0 AS level,
    code AS path,
    name AS full_name
  FROM gl_accounts
  WHERE parent_id IS NULL

  UNION ALL

  -- Recursive: children
  SELECT
    a.id, a.code, a.name, a.parent_id, a.account_type, a.normal_balance,
    a.is_leaf, at.level + 1,
    at.path || '.' || a.code,
    at.full_name || ' > ' || a.name
  FROM gl_accounts a
  JOIN account_tree at ON a.parent_id = at.id
)
SELECT * FROM account_tree ORDER BY path;
```

**Rollup balance query** (sum children into parent):

```sql
-- Get account balances rolled up to root level
WITH RECURSIVE account_hierarchy AS (
  SELECT id, parent_id, normal_balance FROM gl_accounts
  UNION ALL
  SELECT a.id, a.parent_id, a.normal_balance
  FROM gl_accounts a
  JOIN account_hierarchy ah ON a.parent_id = ah.id
)
SELECT
  ah.parent_id,
  SUM(mb.balance) AS total_balance
FROM account_hierarchy ah
JOIN mv_account_balances mb ON mb.account_id = ah.id
GROUP BY ah.parent_id;
```

### 3.3 COA by Jurisdiction

For multi-jurisdiction support (future multi-entity module), the COA can be scoped per `tenant_id` via RLS. Each tenant gets their own COA. The `gl_accounts` table will have a `tenant_id` column added in Phase 2 (multi-tenancy).

**Jurisdiction-specific accounts**: Brazilian tax-specific accounts (PIS, COFINS, ICMS, ISS) are pre-seeded per jurisdiction. The seed script generates accounts based on the company's tax regime (Simples Nacional, Lucro Presumido, Lucro Real).

### 3.4 Seed Data

```typescript
// lib/gl/seed-coa.ts

export const DEFAULT_COA = [
  // ASSETS
  { code: '1', name: 'Ativo', type: 'asset', normal: 'debit', leaf: false },
  { code: '1.1', name: 'Ativo Circulante', type: 'asset', normal: 'debit', leaf: false },
  { code: '1.1.01', name: 'Disponibilidades', type: 'asset', normal: 'debit', leaf: false },
  { code: '1.1.01.001', name: 'Caixa Geral', type: 'asset', normal: 'debit', leaf: true },
  { code: '1.1.01.002', name: 'Banco - Conta Corrente', type: 'asset', normal: 'debit', leaf: true },
  { code: '1.1.02', name: 'Contas a Receber', type: 'asset', normal: 'debit', leaf: false },
  { code: '1.1.02.001', name: 'Clientes', type: 'asset', normal: 'debit', leaf: true },
  { code: '1.1.03', name: 'Estoques', type: 'asset', normal: 'debit', leaf: false },
  { code: '1.2', name: 'Ativo Não Circulante', type: 'asset', normal: 'debit', leaf: false },
  { code: '1.2.01', name: 'Imobilizado', type: 'asset', normal: 'debit', leaf: false },
  { code: '1.2.01.001', name: 'Móveis e Utensílios', type: 'asset', normal: 'debit', leaf: true },
  { code: '1.2.01.002', name: 'Equipamentos de TI', type: 'asset', normal: 'debit', leaf: true },

  // LIABILITIES
  { code: '2', name: 'Passivo', type: 'liability', normal: 'credit', leaf: false },
  { code: '2.1', name: 'Passivo Circulante', type: 'liability', normal: 'credit', leaf: false },
  { code: '2.1.01', name: 'Fornecedores', type: 'liability', normal: 'credit', leaf: false },
  { code: '2.1.01.001', name: 'Fornecedores Nacionais', type: 'liability', normal: 'credit', leaf: true },
  { code: '2.1.02', name: 'Obrigações Tributárias', type: 'liability', normal: 'credit', leaf: false },
  { code: '2.1.02.001', name: 'ICMS a Recolher', type: 'liability', normal: 'credit', leaf: true },
  { code: '2.1.02.002', name: 'PIS a Recolher', type: 'liability', normal: 'credit', leaf: true },
  { code: '2.1.02.003', name: 'COFINS a Recolher', type: 'liability', normal: 'credit', leaf: true },
  { code: '2.1.02.004', name: 'ISS a Recolher', type: 'liability', normal: 'credit', leaf: true },
  { code: '2.1.02.005', name: 'IRPJ a Recolher', type: 'liability', normal: 'credit', leaf: true },
  { code: '2.1.02.006', name: 'CSLL a Recolher', type: 'liability', normal: 'credit', leaf: true },
  { code: '2.1.03', name: 'Empréstimos Circulantes', type: 'liability', normal: 'credit', leaf: false },
  { code: '2.2', name: 'Passivo Não Circulante', type: 'liability', normal: 'credit', leaf: false },

  // EQUITY
  { code: '3', name: 'Patrimônio Líquido', type: 'equity', normal: 'credit', leaf: false },
  { code: '3.1', name: 'Capital Social', type: 'equity', normal: 'credit', leaf: false },
  { code: '3.1.01.001', name: 'Capital Social Integralizado', type: 'equity', normal: 'credit', leaf: true },
  { code: '3.2', name: 'Reservas', type: 'equity', normal: 'credit', leaf: false },
  { code: '3.3', name: 'Lucros/Prejuízos Acumulados', type: 'equity', normal: 'credit', leaf: false },
  { code: '3.3.01.001', name: 'Lucros Acumulados', type: 'equity', normal: 'credit', leaf: true },

  // REVENUE
  { code: '4', name: 'Receitas', type: 'revenue', normal: 'credit', leaf: false },
  { code: '4.1', name: 'Receita Operacional', type: 'revenue', normal: 'credit', leaf: false },
  { code: '4.1.01.001', name: 'Receita de Serviços', type: 'revenue', normal: 'credit', leaf: true },
  { code: '4.1.02.001', name: 'Receita de Assinaturas', type: 'revenue', normal: 'credit', leaf: true },
  { code: '4.2', name: 'Receita Não Operacional', type: 'revenue', normal: 'credit', leaf: false },
  { code: '4.2.01.001', name: 'Receita Financeira', type: 'revenue', normal: 'credit', leaf: true },

  // EXPENSES
  { code: '5', name: 'Despesas', type: 'expense', normal: 'debit', leaf: false },
  { code: '5.1', name: 'Despesas Operacionais', type: 'expense', normal: 'debit', leaf: false },
  { code: '5.1.01', name: 'Despesas com Pessoal', type: 'expense', normal: 'debit', leaf: false },
  { code: '5.1.01.001', name: 'Salários', type: 'expense', normal: 'debit', leaf: true },
  { code: '5.1.01.002', name: 'Encargos Sociais', type: 'expense', normal: 'debit', leaf: true },
  { code: '5.1.02', name: 'Despesas Administrativas', type: 'expense', normal: 'debit', leaf: false },
  { code: '5.1.02.001', name: 'Aluguel', type: 'expense', normal: 'debit', leaf: true },
  { code: '5.1.02.002', name: 'Energia Elétrica', type: 'expense', normal: 'debit', leaf: true },
  { code: '5.1.02.003', name: 'Internet', type: 'expense', normal: 'debit', leaf: true },
  { code: '5.1.02.004', name: 'Software e Ferramentas', type: 'expense', normal: 'debit', leaf: true },
  { code: '5.1.03', name: 'Despesas Comerciais', type: 'expense', normal: 'debit', leaf: false },
  { code: '5.1.03.001', name: 'Marketing', type: 'expense', normal: 'debit', leaf: true },
  { code: '5.2', name: 'Despesas Financeiras', type: 'expense', normal: 'debit', leaf: false },
  { code: '5.2.01.001', name: 'Tarifas Bancárias', type: 'expense', normal: 'debit', leaf: true },
  { code: '5.3', name: 'Custo dos Serviços Prestados', type: 'expense', normal: 'debit', leaf: false },
  { code: '5.3.01.001', name: 'Custo de APIs de IA', type: 'expense', normal: 'debit', leaf: true },
];
```

---

## 4. Period Management

### 4.1 Fiscal Year Lifecycle

```
open → closing → closed
  │
  ├─ open: all entry types allowed
  ├─ closing: only adjusting/reversing entries allowed
  └─ closed: no entries allowed, balances carry forward
```

### 4.2 Period Lifecycle

```
open → soft_closed → hard_closed
  │
  ├─ open: all entry types allowed
  ├─ soft_closed: only adjusting/reversing entries allowed (period-end adjustments)
  └─ hard_closed: no entries allowed at all
```

### 4.3 Period Close Procedure

```typescript
// lib/gl/period-close.ts

export async function closePeriod(periodId: string, userId: string): Promise<void> {
  // 1. Validate: all entries in period are posted (no drafts)
  // 2. Run adjusting entries (depreciation, accruals, etc.)
  // 3. Validate: period is balanced (sum of all entries = 0 across BS accounts)
  // 4. Soft-close the period
  // 5. Auto-reverse any reversing entries
  // 6. Refresh materialized view
}
```

### 4.4 Year-End Close

```typescript
export async function closeFiscalYear(fiscalYearId: string, userId: string): Promise<void> {
  // 1. Close all remaining open periods
  // 2. Generate closing entries (zero out all P&L accounts to Retained Earnings)
  // 3. Generate opening balance entries for next year (carry forward BS accounts)
  // 4. Mark fiscal year as closed
  // 5. Create next fiscal year if not exists
}
```

### 4.5 Lock Mechanism

The period status is checked in the posting function:

```typescript
export async function postJournalEntry(entryId: string): Promise<void> {
  const entry = await journalEntryRepo.getById(entryId);

  // Check period is open
  const period = await periodRepo.getById(entry.period_id);
  if (period.status === 'hard_closed') {
    throw new Error(`Period ${period.name} is closed. Cannot post.`);
  }
  if (period.status === 'soft_closed' && entry.entry_type === 'standard') {
    throw new Error(`Period ${period.name} is soft-closed. Only adjusting entries allowed.`);
  }

  // ... proceed with posting
}
```

---

## 5. Reversal Entries

### 5.1 Reversal Types

| Type | When | How |
|------|------|-----|
| **Void** | Entry was draft, never posted | Simply delete or mark as `voided`. No accounting impact. |
| **Standard Reversal** | Posted entry has an error | Create a new entry with `reversal_of` pointing to original. Lines are opposite (debit↔credit). |
| **Auto-Reversal** | Adjusting entries at period end | Adjusting entries can have `reversal_date`. System auto-creates reversal on that date. |
| **Compensating Entry** | Period-end adjustments | Similar to auto-reversal but explicitly requested. |

### 5.2 Reversal Implementation

```typescript
// lib/gl/reversal.ts

export async function reverseJournalEntry(
  originalEntryId: string,
  reversalDate: string,
  description: string,
  userId: string
): Promise<string> {
  // 1. Load original entry + lines
  const original = await journalEntryRepo.getByIdWithLines(originalEntryId);

  if (original.status !== 'posted') {
    throw new Error('Can only reverse posted entries');
  }

  // 2. Check period is not hard-closed
  const period = await periodRepo.getById(original.period_id);
  if (period.status === 'hard_closed') {
    throw new Error('Cannot reverse entries in a hard-closed period');
  }

  // 3. Create reversal entry with opposite lines
  const reversalLines = original.lines.map((line, i) => ({
    account_id: line.account_id,
    debit: line.credit,   // swap
    credit: line.debit,   // swap
    description: `Reversal of: ${line.description || original.description}`,
    line_number: i + 1,
  }));

  // 4. Create the reversal entry
  const reversalEntry = await createJournalEntry({
    entry_date: reversalDate,
    posting_date: reversalDate,
    entry_type: 'standard',
    description: `Reversal: ${description || original.description}`,
    reference_type: 'journal_entry',
    reference_id: originalEntryId,
    source: 'manual',
    reversal_of: originalEntryId,
    is_reversal: true,
    lines: reversalLines,
  }, userId);

  // 5. Post the reversal
  await postJournalEntry(reversalEntry.id);

  return reversalEntry.id;
}
```

### 5.3 Auto-Reversal for Adjusting Entries

```typescript
// In the period-close process:
async function scheduleAutoReversals(periodId: string): Promise<void> {
  const adjustingEntries = await journalEntryRepo.getByPeriodAndType(periodId, 'adjusting');

  for (const entry of adjustingEntries) {
    if (entry.reversal_date) {
      // Create reversal entry for the reversal_date
      await reverseJournalEntry(
        entry.id,
        entry.reversal_date,
        `Auto-reversal of adjusting entry ${entry.entry_number}`,
        'system'
      );
    }
  }
}
```

---

## 6. Account Balances: Materialized View vs Live Aggregation

### 6.1 Strategy

| Approach | Pros | Cons | When to use |
|----------|------|------|-------------|
| **Materialized view** | Fast reads, pre-computed | Stale between refreshes, storage overhead | Dashboard, reports, financial statements |
| **Live aggregation** | Always fresh | Slow on large datasets, N+1 risk | Single-account lookup, real-time validation |
| **Hybrid** | Best of both | Complexity | Recommended approach |

### 6.2 Recommended: Hybrid

- **Materialized view** (`mv_account_balances`): For dashboard, reports, balance sheet, P&L
- **Live aggregation**: For single-account lookups, trial balance validation, real-time posting
- **Refresh trigger**: `REFRESH MATERIALIZED VIEW CONCURRENTLY` after every POST batch
- **In-memory cache**: For the current period's running balance (fast path)

### 6.3 Refresh Strategy

```typescript
// lib/gl/balance-service.ts

export async function refreshBalances(): Promise<void> {
  if (isSupabase) {
    // PostgreSQL: concurrent refresh (non-blocking)
    await supabase.rpc('refresh_account_balances');
  } else {
    // SQLite: rebuild from journal_entry_lines
    await rebuildBalancesSqlite();
  }
}

// Supabase RPC:
// CREATE OR REPLACE FUNCTION refresh_account_balances()
// RETURNS void AS $$
// BEGIN
//   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_account_balances;
// END;
// $$ LANGUAGE plpgsql;
```

### 6.4 Balance Query Patterns

```sql
-- Trial balance for a period
SELECT
  a.code, a.name, a.normal_balance,
  mb.total_debit, mb.total_credit, mb.balance
FROM mv_account_balances mb
JOIN gl_accounts a ON a.id = mb.account_id
WHERE mb.period_id = $1
ORDER BY a.code;

-- Balance sheet (assets = liabilities + equity)
SELECT
  a.account_type,
  SUM(mb.balance) AS total
FROM mv_account_balances mb
JOIN gl_accounts a ON a.id = mb.account_id
WHERE mb.period_id = $1
  AND a.account_type IN ('asset', 'liability', 'equity')
GROUP BY a.account_type;

-- P&L (revenue - expenses)
SELECT
  a.account_type,
  SUM(mb.balance) AS total
FROM mv_account_balances mb
JOIN gl_accounts a ON a.id = mb.account_id
WHERE mb.period_id = $1
  AND a.account_type IN ('revenue', 'expense')
GROUP BY a.account_type;
```

---

## 7. API Endpoints

All endpoints follow the existing pattern: Next.js API Routes under `app/api/gl/`.

### 7.1 Chart of Accounts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/gl/accounts` | List all accounts (tree structure) |
| `GET` | `/api/gl/accounts/:id` | Get account by ID |
| `GET` | `/api/gl/accounts/tree` | Get full tree with hierarchy |
| `POST` | `/api/gl/accounts` | Create account |
| `PUT` | `/api/gl/accounts/:id` | Update account |
| `DELETE` | `/api/gl/accounts/:id` | Delete account (leaf only, no transactions) |
| `POST` | `/api/gl/accounts/seed` | Seed default COA |
| `GET` | `/api/gl/accounts/:id/balance` | Get account balance (period-scoped) |

### 7.2 Journal Entries

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/gl/journal-entries` | List entries (filterable: period, status, type, date range) |
| `GET` | `/api/gl/journal-entries/:id` | Get entry with lines |
| `POST` | `/api/gl/journal-entries` | Create draft entry |
| `PUT` | `/api/gl/journal-entries/:id` | Update draft entry |
| `DELETE` | `/api/gl/journal-entries/:id` | Delete draft entry |
| `POST` | `/api/gl/journal-entries/:id/post` | Post entry (validates balance, locks entry) |
| `POST` | `/api/gl/journal-entries/:id/void` | Void entry (if draft or unposted) |
| `POST` | `/api/gl/journal-entries/:id/reverse` | Create reversal entry |
| `GET` | `/api/gl/journal-entries/:id/reversals` | List reversals of this entry |

### 7.3 Periods

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/gl/fiscal-years` | List fiscal years |
| `POST` | `/api/gl/fiscal-years` | Create fiscal year (auto-creates periods) |
| `POST` | `/api/gl/fiscal-years/:id/close` | Close fiscal year |
| `GET` | `/api/gl/periods` | List periods (filterable by fiscal year) |
| `GET` /api/gl/periods/:id` | Get period details |
| `POST` | `/api/gl/periods/:id/close` | Soft-close period |
| `POST` | `/api/gl/periods/:id/hard-close` | Hard-close period |
| `POST` | `/api/gl/periods/:id/open` | Re-open soft-closed period |

### 7.4 Balances & Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/gl/balances` | Get all account balances (period-scoped) |
| `GET` | `/api/gl/balances/trial` | Trial balance |
| `GET` | `/api/gl/balances/balance-sheet` | Balance sheet |
| `GET` | `/api/gl/balances/income-statement` | Income statement (DRE) |
| `POST` | `/api/gl/balances/refresh` | Force refresh materialized view |

### 7.5 API Response Shapes

```typescript
// POST /api/gl/journal-entries
interface CreateJournalEntryRequest {
  entry_date: string;           // YYYY-MM-DD
  posting_date?: string;        // defaults to entry_date
  entry_type: 'standard' | 'adjusting' | 'recurring';
  description: string;
  reference_type?: string;
  reference_id?: string;
  lines: Array<{
    account_id: string;
    debit: number;
    credit: number;
    description?: string;
    cost_center_id?: string;
  }>;
}

interface JournalEntryResponse {
  id: string;
  entry_number: string;
  entry_date: string;
  posting_date: string;
  description: string;
  entry_type: string;
  status: string;
  total_debit: number;
  total_credit: number;
  lines: Array<{
    id: string;
    line_number: number;
    account_id: string;
    account_code: string;
    account_name: string;
    debit: number;
    credit: number;
    description?: string;
  }>;
  created_at: string;
}
```

---

## 8. Event Sourcing

### 8.1 Decision: Partial Event Sourcing (Journal Entry Append-Only)

Full event sourcing for the entire GL is overkill and high-risk for a small team (see R2 in B1-risks-blockers.md). Instead, use **append-only journal entry logging** — a pragmatic middle ground.

### 8.2 What Gets Event-Sourced

| Component | Approach | Rationale |
|-----------|----------|-----------|
| Journal entries | Append-only log (`gl_journal_entry_log`) | Audit trail is critical for financial compliance |
| Account balances | CQRS projection (materialized view) | Read optimization |
| Period operations | Audit log entries | Track close/open operations |
| Account CRUD | Traditional CRUD | Simple, not audit-critical |

### 8.3 Journal Entry Event Log

```sql
CREATE TABLE IF NOT EXISTS gl_journal_entry_log (
  id              TEXT PRIMARY KEY,
  journal_entry_id TEXT NOT NULL,
  event_type      TEXT NOT NULL CHECK (event_type IN (
                    'created', 'updated', 'lines_added', 'lines_removed',
                    'posted', 'voided', 'reversed'
                  )),
  payload_json    TEXT NOT NULL,                       -- full snapshot or diff
  user_id         TEXT,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gl_je_log_entry ON gl_journal_entry_log(journal_entry_id);
CREATE INDEX IF NOT EXISTS idx_gl_je_log_type ON gl_journal_entry_log(event_type);
```

### 8.4 Event Emission

```typescript
// lib/gl/event-log.ts

export async function logJournalEvent(
  journalEntryId: string,
  eventType: string,
  payload: Record<string, unknown>,
  userId: string
): Promise<void> {
  await db.insert('gl_journal_entry_log', {
    id: generateId(),
    journal_entry_id: journalEntryId,
    event_type: eventType,
    payload_json: JSON.stringify(payload),
    user_id: userId,
  });
}

// Called in every state-changing operation:
await logJournalEvent(entryId, 'posted', { total_debit, total_credit, lines }, userId);
```

### 8.5 When to Upgrade to Full Event Sourcing

Full event sourcing (events as source of truth, projections rebuilt from events) becomes valuable when:
- Multi-entity consolidation requires replaying history
- Regulatory audit requires immutable, ordered event log
- The team has validated the append-only pattern works

Estimated trigger: after 6+ months of production use with the append-only approach.

---

## 9. Migration: Existing Journal Entries to New Schema

### 9.1 Current State

The existing system has no GL. Financial data lives in:
- `Client` table (revenue data via `monthlyPayment`)
- `Invoice` table (receivables)
- `Expense` table (expenses)
- `Partner` / `PartnerTransaction` (partner equity)

### 9.2 Migration Strategy: Soft Launch

Since there are no existing journal entries, this is a **greenfield migration** — not data migration. The strategy:

1. **Keep existing tables**: Don't drop `Client`, `Invoice`, `Expense`, `Partner`. They continue to work for the legacy UI.
2. **Add GL tables**: Create all GL tables alongside existing ones.
3. **Dual-write bridge**: When an invoice is created/paid or expense is created, also create a corresponding journal entry. This is the bridge between legacy and GL.
4. **Sync existing balances**: Seed opening balances from legacy data.

### 9.3 Dual-Write Bridge

```typescript
// lib/gl/bridge.ts

// When an invoice is paid:
export async function onInvoicePaid(invoice: Invoice): Promise<void> {
  // Debit: Banco (1.1.01.002)
  // Credit: Clientes (1.1.02.001)
  await createJournalEntry({
    entry_date: invoice.paidDate!,
    entry_type: 'standard',
    description: `Pagamento da fatura ${invoice.id} - ${invoice.clientName}`,
    reference_type: 'invoice',
    reference_id: invoice.id,
    source: 'auto',
    lines: [
      { account_id: BANK_ACCOUNT_ID, debit: invoice.amount, credit: 0 },
      { account_id: CLIENTS_ACCOUNT_ID, debit: 0, credit: invoice.amount },
    ],
  });
}

// When an expense is created:
export async function onExpenseCreated(expense: Expense): Promise<void> {
  // Debit: Despesa (5.1.x based on category)
  // Credit: Fornecedores (2.1.01.001) or Banco (1.1.01.002)
  const expenseAccountId = CATEGORY_TO_ACCOUNT[expense.category];
  await createJournalEntry({
    entry_date: expense.date,
    entry_type: 'standard',
    description: `Despesa: ${expense.description}`,
    reference_type: 'expense',
    reference_id: expense.id,
    source: 'auto',
    lines: [
      { account_id: expenseAccountId, debit: expense.amount, credit: 0 },
      { account_id: BANK_ACCOUNT_ID, debit: 0, credit: expense.amount },
    ],
  });
}
```

### 9.4 Opening Balances Migration

```typescript
// One-time migration script
export async function migrateOpeningBalances(): Promise<void> {
  // 1. Create fiscal year for current period
  const fy = await createFiscalYear(currentYear, startDate, endDate);

  // 2. Create opening balance entry
  const openingEntry = await createJournalEntry({
    entry_date: startDate,
    entry_type: 'opening',
    description: 'Saldos iniciais - migração do sistema legado',
    source: 'migration',
    lines: [
      // Total of all unpaid invoices → Debit Clientes
      // Total of all expenses → Debit respective expense accounts
      // Partner balances → Credit partner equity accounts
      // Revenue (total monthly payments) → Credit revenue accounts
    ],
  });

  await postJournalEntry(openingEntry.id);
}
```

### 9.5 Migration Timeline

| Step | Description | Effort |
|------|-------------|--------|
| 1 | Create GL tables + seed COA | 1 day |
| 2 | Implement journal entry CRUD + posting | 2 days |
| 3 | Implement dual-write bridge for invoices/expenses | 1 day |
| 4 | Create opening balance migration script | 0.5 day |
| 5 | Test with existing data | 0.5 day |
| **Total** | | **5 days** |

---

## 10. Testing

### 10.1 Property-Based Tests (Double-Entry Invariant)

Using `fast-check` with Vitest:

```typescript
// tests/gl/double-entry.test.ts

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { validateJournalEntry } from '../../lib/gl/validator';

describe('Double-entry invariant', () => {
  it('any random set of balanced lines passes validation', () => {
    fc.assert(
      fc.property(
        // Generate N random lines where total debit = total credit
        fc.array(
          fc.record({
            account_id: fc.uuid(),
            debit: fc.integer({ min: 0, max: 1000000 }),
            credit: fc.constant(0),
          }),
          { minLength: 2, maxLength: 20 }
        ),
        (lines) => {
          // Force balance: make last line credit = sum of debits
          const totalDebit = lines.reduce((s, l) => s + l.debit, 0);
          lines.push({
            account_id: 'balancing-account',
            debit: 0,
            credit: totalDebit,
          });

          const result = validateJournalEntry({
            lines,
            description: 'Test entry',
          });

          expect(result.valid).toBe(true);
        }
      ),
      { numRuns: 1000 }
    );
  });

  it('unbalanced entries always fail validation', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            account_id: fc.uuid(),
            debit: fc.integer({ min: 1, max: 1000000 }),
            credit: fc.constant(0),
          }),
          { minLength: 2, maxLength: 10 }
        ),
        (lines) => {
          // Remove the last line to unbalance
          lines.pop();

          const result = validateJournalEntry({
            lines,
            description: 'Test entry',
          });

          expect(result.valid).toBe(false);
        }
      ),
      { numRuns: 1000 }
    );
  });

  it('lines with both debit and credit always fail', () => {
    fc.assert(
      fc.property(
        fc.record({
          account_id: fc.uuid(),
          debit: fc.integer({ min: 1, max: 1000000 }),
          credit: fc.integer({ min: 1, max: 1000000 }),
        }),
        (line) => {
          const result = validateJournalEntry({
            lines: [line, { account_id: 'other', debit: 0, credit: line.debit }],
            description: 'Test entry',
          });

          expect(result.valid).toBe(false);
        }
      ),
      { numRuns: 500 }
    );
  });
});
```

### 10.2 Golden Master Tests (Balance Calculations)

```typescript
// tests/gl/balances.test.ts

import { describe, it, expect } from 'vitest';

// Golden master: known inputs → expected balance outputs
const GOLDEN_MASTER = {
  'single-debit-credit': {
    entries: [
      { debit: [{ account: '1.1.01.001', amount: 1000 }], credit: [{ account: '4.1.01.001', amount: 1000 }] },
    ],
    expected: {
      '1.1.01.001': { debit: 1000, credit: 0, balance: 1000 },
      '4.1.01.001': { debit: 0, credit: 1000, balance: 1000 },
    },
  },
  'multi-line-entry': {
    entries: [
      {
        debit: [
          { account: '1.1.01.002', amount: 5000 },
          { account: '5.1.02.004', amount: 500 },
        ],
        credit: [{ account: '2.1.01.001', amount: 5500 }],
      },
    ],
    expected: {
      '1.1.01.002': { debit: 5000, credit: 0, balance: 5000 },
      '5.1.02.004': { debit: 500, credit: 0, balance: 500 },
      '2.1.01.001': { debit: 0, credit: 5500, balance: 5500 },
    },
  },
  'reversal-entry': {
    entries: [
      { debit: [{ account: '1.1.01.001', amount: 1000 }], credit: [{ account: '4.1.01.001', amount: 1000 }] },
      { debit: [{ account: '4.1.01.001', amount: 1000 }], credit: [{ account: '1.1.01.001', amount: 1000 }] },
    ],
    expected: {
      '1.1.01.001': { debit: 1000, credit: 1000, balance: 0 },
      '4.1.01.001': { debit: 1000, credit: 1000, balance: 0 },
    },
  },
};

describe('Balance calculations (golden master)', () => {
  for (const [name, test] of Object.entries(GOLDEN_MASTER)) {
    it(name, async () => {
      // Post all entries, then verify balances match expected
      const balances = await computeBalances(test.entries);
      expect(balances).toEqual(test.expected);
    });
  }
});
```

### 10.3 Integration Tests

| Test | Scope | Type |
|------|-------|------|
| Create + post journal entry | GL CRUD + posting | Integration |
| Period close + auto-reversal | Period management | Integration |
| Balance refresh after posting | CQRS consistency | Integration |
| Reversal creates opposite entry | Reversal logic | Integration |
| Cannot post to closed period | Period lock | Integration |
| Opening balance migration | Migration | Integration |

### 10.4 E2E Tests (Playwright)

| Test | Flow |
|------|------|
| Create account → create entry → post → verify balance | Full GL workflow |
| Period close → verify trial balance → open next period | Period management |
| Invoice payment → auto-journal entry → verify accounts | Dual-write bridge |

---

## 11. Effort Estimate

### Phase-by-Phase Breakdown

| Sub-Feature | Effort (days) | Dependencies |
|-------------|---------------|--------------|
| **1. Schema + migrations** | 1 | None |
| **2. Account CRUD (repository + API)** | 2 | Schema |
| **3. Account hierarchy (tree queries, rollup)** | 1.5 | Account CRUD |
| **4. Journal entry CRUD (repository + API)** | 2 | Schema, Accounts |
| **5. Double-entry validation (DB + TS)** | 1 | Journal entries |
| **6. Posting workflow (post, void, status)** | 1.5 | Validation |
| **7. Period management (FY + periods)** | 2 | Schema |
| **8. Period close + year-end close** | 2 | Periods, posting |
| **9. Reversal entries** | 1.5 | Posting |
| **10. Balance materialized view + refresh** | 1.5 | Posting |
| **11. Balance queries (trial balance, BS, P&L)** | 1 | Balance view |
| **12. Seed COA data + migration script** | 1 | Accounts |
| **13. Dual-write bridge (invoices/expenses → GL)** | 1.5 | All above |
| **14. Event log (append-only)** | 1 | Journal entries |
| **15. Unit tests (property-based)** | 1.5 | Validator |
| **16. Integration tests** | 2 | All above |
| **17. E2E tests (Playwright)** | 1 | All above |
| **18. Documentation + ADR** | 0.5 | All above |
| **Total** | **23.5 days** | |

### Calendar Estimate

With **1 developer, full-time**: ~5 weeks
With **2 developers, parallel streams**: ~3 weeks
- Stream A: Schema + Accounts + Hierarchy + Periods
- Stream B: Journal entries + Validation + Posting + Balances
- Merge: Dual-write bridge + tests + docs

---

## 12. Blockers

### Must Exist Before GL Can Be Built

| # | Blocker | Current Status | Resolution |
|---|---------|---------------|------------|
| 1 | **Migration system** (replace monolithic `initDB()`) | Not started. Current: raw `CREATE TABLE IF NOT EXISTS` in `lib/db/index.ts` | Add Drizzle ORM or Kysely for schema migrations. 2-3 days. |
| 2 | **Repository pattern for GL** | Existing pattern in `lib/repositories/` provides template | Follow existing `IClientRepository` pattern. No new abstraction needed. |
| 3 | **UUID generation** | Current tables use TEXT PKs, not UUIDs | Add `uuid` package or use `crypto.randomUUID()`. 0.5 day. |
| 4 | **Multi-tenancy schema** | Not started. GL needs `tenant_id` for RLS | Add `tenant_id` column to all GL tables. RLS policies in Phase 2. 0.5 day. |
| 5 | **TypeScript types for GL entities** | Not started | Define `Account`, `JournalEntry`, `JournalEntryLine`, `Period` interfaces. 0.5 day. |

### Recommended Build Order

```
Week 1: Blockers + Schema + Account CRUD + Hierarchy
Week 2: Journal Entry CRUD + Validation + Posting
Week 3: Periods + Reversals + Balances
Week 4: Dual-Write Bridge + Seed Data + Migration
Week 5: Tests + Documentation + Review
```

### What Can Be Parallelized

- Account CRUD and Journal Entry CRUD are independent (different tables)
- Period management is independent of journal entries (only needed at posting time)
- Tests can be written alongside implementation

### What Must Be Sequential

- Validation → Posting (posting depends on validation)
- Posting → Balances (balances are projections of posted entries)
- All of the above → Dual-write bridge (bridge uses all GL operations)

---

## Appendix: Directory Structure

```
lib/gl/
├── types.ts                    # Account, JournalEntry, JournalEntryLine, Period interfaces
├── validator.ts                # Double-entry validation logic
├── account-service.ts          # Account CRUD + hierarchy queries
├── journal-service.ts          # Journal entry CRUD + posting + reversal
├── period-service.ts           # Fiscal year + period management + close
├── balance-service.ts          # Balance queries + materialized view refresh
├── event-log.ts                # Append-only event log
├── bridge.ts                   # Dual-write bridge (invoices/expenses → GL)
├── seed-coa.ts                 # Default Chart of Accounts data
├── period-close.ts             # Period close + year-end close procedures

app/api/gl/
├── accounts/
│   ├── route.ts                # GET (list), POST (create)
│   ├── [id]/route.ts           # GET, PUT, DELETE
│   ├── tree/route.ts           # GET tree
│   └── seed/route.ts           # POST seed
├── journal-entries/
│   ├── route.ts                # GET (list), POST (create)
│   ├── [id]/route.ts           # GET, PUT, DELETE
│   ├── [id]/post/route.ts      # POST (post entry)
│   ├── [id]/void/route.ts      # POST (void)
│   └── [id]/reverse/route.ts   # POST (reverse)
├── periods/
│   ├── route.ts                # GET (list)
│   ├── [id]/route.ts           # GET
│   ├── [id]/close/route.ts     # POST (soft close)
│   └── [id]/hard-close/route.ts # POST (hard close)
├── fiscal-years/
│   ├── route.ts                # GET, POST
│   └── [id]/close/route.ts     # POST (year-end close)
└── balances/
    ├── route.ts                # GET all balances
    ├── trial/route.ts          # GET trial balance
    ├── balance-sheet/route.ts  # GET balance sheet
    └── income-statement/route.ts # GET income statement

lib/repositories/gl/
├── types.ts                    # IGLAccountRepository, IGLJournalEntryRepository, etc.
├── sqlite/
│   ├── account.ts
│   ├── journal-entry.ts
│   ├── journal-entry-line.ts
│   └── period.ts
└── supabase/
    ├── account.ts
    ├── journal-entry.ts
    ├── journal-entry-line.ts
    └── period.ts

tests/gl/
├── double-entry.test.ts        # Property-based tests
├── validator.test.ts           # Unit tests for validation
├── balances.test.ts            # Golden master balance tests
├── journal-service.test.ts     # Integration tests
├── period-service.test.ts      # Integration tests
└── reversal.test.ts            # Integration tests
```
