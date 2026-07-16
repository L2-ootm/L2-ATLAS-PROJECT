# B2: Accounts Payable, Accounts Receivable & Invoicing — Implementation Plan

**Date**: 2026-07-10
**Scope**: AP/AR sub-ledgers, invoicing state machine, payment recording, aging, three-way matching, credit management, recurring invoices, GL integration hooks
**Depends on**: GL/COA (Batch 2 sibling — `B2-gl-coa.md`)
**Baseline**: 42-module architecture, Phase 3+4 build order (AP/AR at Level 2, Invoicing at Level 3)

---

## 0. Current State Summary

| What exists | What's missing |
|---|---|
| `Invoice` table: id, clientId, amount, status (pendente/pago/atrasado), dueDate, paidDate | Vendor management, bill tracking, payment schedules |
| Basic CRUD via `IInvoiceRepository` | Aging buckets, dunning, credit limits |
| `InvoiceStatus` = 3 values (pendente/pago/atrasado) | Full state machine (draft→finalized→sent→paid→voided) |
| No payment recording (just paidDate toggle) | Partial payments, overpayments, payment allocations |
| No GL integration | Journal entry posting on invoice/payment events |
| `invoice_line_items` table (schema only, unwired) | Line items integration with invoice generation |
| `billing_events` table (schema only) | Event sourcing for financial transactions |

**Key gap**: The current `Invoice` is a flat tracking record, not a financial instrument. It cannot support accrual accounting, payment allocation, or aging.

---

## 1. AP Data Model

### 1.1 Vendors

```sql
CREATE TABLE vendors (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,              -- multi-tenant FK (Phase 1)
  display_name    TEXT NOT NULL,
  legal_name      TEXT,
  tax_id          TEXT,                       -- CNPJ/CPF
  email           TEXT,
  phone           TEXT,
  address_json    JSONB,                      -- { street, number, complement, neighborhood, city, state, zip, country }
  bank_details    JSONB,                      -- { bank_code, agency, account, pix_key, pix_type }
  payment_terms   TEXT DEFAULT 'net_30',       -- net_15, net_30, net_60, custom
  custom_terms_days INTEGER,
  currency        TEXT DEFAULT 'BRL',
  credit_limit_brl NUMERIC DEFAULT 0,
  notes           TEXT,
  active          INTEGER DEFAULT 1,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_vendors_tenant ON vendors(tenant_id);
CREATE INDEX idx_vendors_active ON vendors(tenant_id, active);
```

### 1.2 Bills (Accounts Payable)

```sql
CREATE TABLE bills (
  id                  TEXT PRIMARY KEY,
  tenant_id           TEXT NOT NULL,
  vendor_id           TEXT NOT NULL REFERENCES vendors(id),
  bill_number         TEXT,                    -- vendor's invoice/reference number
  po_id               TEXT,                    -- link to purchase_order if three-way matching
  receipt_id          TEXT,                    -- link to goods_receipt if three-way matching
  description         TEXT,
  bill_date           TEXT NOT NULL,           -- vendor's invoice date
  due_date            TEXT NOT NULL,
  currency            TEXT DEFAULT 'BRL',
  subtotal_brl        NUMERIC DEFAULT 0,       -- sum of line items before tax
  tax_amount_brl      NUMERIC DEFAULT 0,       -- calculated or manual tax
  total_brl           NUMERIC DEFAULT 0,       -- subtotal + tax
  amount_paid_brl     NUMERIC DEFAULT 0,       -- running total of applied payments
  balance_brl         NUMERIC GENERATED ALWAYS AS (total_brl - amount_paid_brl) STORED,
  status              TEXT DEFAULT 'draft',    -- draft → pending_approval → approved → partially_paid → paid → voided
  approval_status     TEXT DEFAULT 'none',     -- none, pending, approved, rejected
  approved_by         TEXT,
  approved_at         TIMESTAMP WITH TIME ZONE,
  aging_bucket        TEXT DEFAULT 'current',  -- computed: current, 1-30, 31-60, 61-90, 90+
  gl_journal_entry_id TEXT,                    -- FK to journal_entries (GL module)
  notes               TEXT,
  attachment_urls     JSONB,                   -- array of document URLs
  created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_bills_tenant ON bills(tenant_id);
CREATE INDEX idx_bills_vendor ON bills(vendor_id);
CREATE INDEX idx_bills_status ON bills(tenant_id, status);
CREATE INDEX idx_bills_due_date ON bills(tenant_id, due_date);
CREATE INDEX idx_bills_aging ON bills(tenant_id, aging_bucket);
```

### 1.3 Bill Line Items

```sql
CREATE TABLE bill_line_items (
  id              TEXT PRIMARY KEY,
  bill_id         TEXT NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
  line_number     INTEGER NOT NULL,
  description     TEXT,
  quantity        NUMERIC DEFAULT 1,
  unit_price_brl  NUMERIC DEFAULT 0,
  discount_brl    NUMERIC DEFAULT 0,
  tax_rate_pct    NUMERIC DEFAULT 0,
  tax_amount_brl  NUMERIC DEFAULT 0,
  total_brl       NUMERIC NOT NULL,           -- (qty * unit_price - discount) + tax
  expense_category TEXT,                      -- maps to ExpenseCategory for auto-categorization
  cost_center_id  TEXT,                       -- optional, for Phase 5 Cost Centers
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_bill_line_items_bill ON bill_line_items(bill_id);
```

### 1.4 Payment Schedule (for split payments / installments)

```sql
CREATE TABLE payment_schedules (
  id              TEXT PRIMARY KEY,
  bill_id         TEXT NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
  installment_no  INTEGER NOT NULL,
  due_date        TEXT NOT NULL,
  amount_brl      NUMERIC NOT NULL,
  status          TEXT DEFAULT 'pending',     -- pending → partially_paid → paid → overdue
  amount_paid_brl NUMERIC DEFAULT 0,
  paid_date       TEXT,
  notes           TEXT,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payment_schedules_bill ON payment_schedules(bill_id);
CREATE INDEX idx_payment_schedules_due ON payment_schedules(due_date);
```

### 1.5 AP Aging Bucket Computation

Aging is computed dynamically from `bill.due_date` and the reference date (default: today):

```sql
-- AP Aging query: runs as RPC or repository method
SELECT
  vendor_id,
  vendor_name,
  SUM(CASE WHEN days_overdue <= 0 THEN balance_brl ELSE 0 END) AS current_amount,
  SUM(CASE WHEN days_overdue BETWEEN 1 AND 30 THEN balance_brl ELSE 0 END) AS days_1_30,
  SUM(CASE WHEN days_overdue BETWEEN 31 AND 60 THEN balance_brl ELSE 0 END) AS days_31_60,
  SUM(CASE WHEN days_overdue BETWEEN 61 AND 90 THEN balance_brl ELSE 0 END) AS days_61_90,
  SUM(CASE WHEN days_overdue > 90 THEN balance_brl ELSE 0 END) AS days_90_plus,
  SUM(balance_brl) AS total_outstanding
FROM (
  SELECT
    b.id,
    b.vendor_id,
    v.display_name AS vendor_name,
    b.balance_brl,
    EXTRACT(DAY FROM (CURRENT_DATE::timestamp - b.due_date::timestamp)) AS days_overdue
  FROM bills b
  JOIN vendors v ON v.id = b.vendor_id
  WHERE b.tenant_id = $1
    AND b.status NOT IN ('paid', 'voided')
    AND b.balance_brl > 0
) sub
GROUP BY vendor_id, vendor_name
ORDER BY total_outstanding DESC;
```

Aging buckets are also denormalized on the `bills` table (`aging_bucket` column) for fast dashboard filtering, recomputed by a nightly job or on payment/approval events.

---

## 2. AR Data Model

### 2.1 Customers (extends existing `client_accounts`)

The existing `client_accounts` table serves as the customer entity. We add AR-specific columns:

```sql
ALTER TABLE client_accounts ADD COLUMN IF NOT EXISTS payment_terms TEXT DEFAULT 'net_30';
ALTER TABLE client_accounts ADD COLUMN IF NOT EXISTS credit_limit_brl NUMERIC DEFAULT 0;
ALTER TABLE client_accounts ADD COLUMN IF NOT EXISTS credit_used_brl NUMERIC DEFAULT 0;
ALTER TABLE client_accounts ADD COLUMN IF NOT EXISTS credit_status TEXT DEFAULT 'active';  -- active, hold, suspended
ALTER TABLE client_accounts ADD COLUMN IF NOT EXISTS dunning_status TEXT DEFAULT 'none';   -- none, first_notice, second_notice, final_notice, collections
ALTER TABLE client_accounts ADD COLUMN IF NOT EXISTS dunning_last_sent_at TIMESTAMP WITH TIME ZONE;
```

### 2.2 Customer Invoices (replaces flat `invoice` table)

```sql
CREATE TABLE customer_invoices (
  id                  TEXT PRIMARY KEY,
  tenant_id           TEXT NOT NULL,
  customer_id         TEXT NOT NULL REFERENCES client_accounts(id),
  contract_id         TEXT REFERENCES contracts(id),
  invoice_number      TEXT NOT NULL,           -- sequential, tenant-scoped (e.g., INV-2026-00001)
  subscription_id     TEXT REFERENCES plus_subscriptions(id),
  description         TEXT,
  invoice_date        TEXT NOT NULL,           -- issue date
  due_date            TEXT NOT NULL,
  currency            TEXT DEFAULT 'BRL',
  subtotal_brl        NUMERIC DEFAULT 0,
  discount_brl        NUMERIC DEFAULT 0,
  tax_amount_brl      NUMERIC DEFAULT 0,
  total_brl           NUMERIC DEFAULT 0,
  amount_paid_brl     NUMERIC DEFAULT 0,
  balance_brl         NUMERIC GENERATED ALWAYS AS (total_brl - amount_paid_brl) STORED,
  status              TEXT DEFAULT 'draft',    -- draft → finalized → sent → partially_paid → paid → voided
  finalized_at        TIMESTAMP WITH TIME ZONE,
  sent_at             TIMESTAMP WITH TIME ZONE,
  sent_via            TEXT,                    -- email, whatsapp, portal
  paid_at             TIMESTAMP WITH TIME ZONE,
  voided_at           TIMESTAMP WITH TIME ZONE,
  void_reason         TEXT,
  aging_bucket        TEXT DEFAULT 'current',
  gl_journal_entry_id TEXT,
  credit_hold         INTEGER DEFAULT 0,       -- 1 = held due to credit limit
  notes               TEXT,
  attachment_urls     JSONB,
  created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customer_invoices_tenant ON customer_invoices(tenant_id);
CREATE INDEX idx_customer_invoices_customer ON customer_invoices(customer_id);
CREATE INDEX idx_customer_invoices_status ON customer_invoices(tenant_id, status);
CREATE INDEX idx_customer_invoices_due_date ON customer_invoices(tenant_id, due_date);
CREATE INDEX idx_customer_invoices_number ON customer_invoices(tenant_id, invoice_number);
CREATE INDEX idx_customer_invoices_aging ON customer_invoices(tenant_id, aging_bucket);
```

### 2.3 Customer Invoice Line Items

```sql
CREATE TABLE customer_invoice_line_items (
  id              TEXT PRIMARY KEY,
  invoice_id      TEXT NOT NULL REFERENCES customer_invoices(id) ON DELETE CASCADE,
  line_number     INTEGER NOT NULL,
  description     TEXT,
  quantity        NUMERIC DEFAULT 1,
  unit_price_brl  NUMERIC DEFAULT 0,
  discount_brl    NUMERIC DEFAULT 0,
  tax_rate_pct    NUMERIC DEFAULT 0,
  tax_amount_brl  NUMERIC DEFAULT 0,
  total_brl       NUMERIC NOT NULL,
  revenue_account TEXT,                       -- COA account code for revenue recognition
  cost_center_id  TEXT,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customer_invoice_line_items_invoice ON customer_invoice_line_items(invoice_id);
```

### 2.4 AR Aging Bucket Computation

Same structure as AP, inverted direction:

```sql
SELECT
  customer_id,
  customer_name,
  SUM(CASE WHEN days_until_due >= 0 THEN balance_brl ELSE 0 END) AS current_amount,
  SUM(CASE WHEN days_overdue BETWEEN 1 AND 30 THEN balance_brl ELSE 0 END) AS days_1_30,
  SUM(CASE WHEN days_overdue BETWEEN 31 AND 60 THEN balance_brl ELSE 0 END) AS days_31_60,
  SUM(CASE WHEN days_overdue BETWEEN 61 AND 90 THEN balance_brl ELSE 0 END) AS days_61_90,
  SUM(CASE WHEN days_overdue > 90 THEN balance_brl ELSE 0 END) AS days_90_plus,
  SUM(balance_brl) AS total_outstanding
FROM (
  SELECT
    ci.id,
    ci.customer_id,
    ca.name AS customer_name,
    ci.balance_brl,
    CASE
      WHEN ci.due_date >= CURRENT_DATE THEN 0
      ELSE EXTRACT(DAY FROM (CURRENT_DATE::timestamp - ci.due_date::timestamp))::integer
    END AS days_overdue,
    CASE
      WHEN ci.due_date >= CURRENT_DATE THEN EXTRACT(DAY FROM (ci.due_date::timestamp - CURRENT_DATE::timestamp))::integer
      ELSE 0
    END AS days_until_due
  FROM customer_invoices ci
  JOIN client_accounts ca ON ca.id = ci.customer_id
  WHERE ci.tenant_id = $1
    AND ci.status NOT IN ('paid', 'voided')
    AND ci.balance_brl > 0
) sub
GROUP BY customer_id, customer_name
ORDER BY total_outstanding DESC;
```

### 2.5 Dunning Levels

```sql
CREATE TABLE dunning_actions (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  customer_id     TEXT NOT NULL REFERENCES client_accounts(id),
  invoice_id      TEXT REFERENCES customer_invoices(id),
  dunning_level   TEXT NOT NULL,               -- first_notice, second_notice, final_notice, collections
  action_type     TEXT NOT NULL,               -- email_sent, whatsapp_sent, letter_sent, escalated
  message_template TEXT,
  sent_at         TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  sent_by         TEXT,                        -- system (auto) or user_id
  notes           TEXT,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dunning_actions_customer ON dunning_actions(customer_id);
CREATE INDEX idx_dunning_actions_invoice ON dunning_actions(invoice_id);
```

**Dunning escalation rules** (configurable per tenant):

| Days overdue | Level | Action |
|---|---|---|
| 1-15 | First notice | Auto-email reminder |
| 16-30 | Second notice | Auto-email + WhatsApp |
| 31-60 | Final notice | Letter + hold future orders |
| 61+ | Collections | Escalate to collections workflow |

---

## 3. Invoicing Flow (State Machine)

### 3.1 Invoice States

```
draft → finalized → sent → partially_paid → paid
                                  ↑              ↑
                                  └──────────────┘
                                  │
                          sent (re-sent)
                          
draft / finalized / sent → voided (at any point before paid)
```

**State definitions:**

| State | Meaning | Allowed transitions |
|---|---|---|
| `draft` | Editable, not yet issued | → `finalized`, → `voided` |
| `finalized` | Locked, numbers assigned, GL preview created | → `sent`, → `voided` |
| `sent` | Delivered to customer | → `partially_paid`, → `paid`, → `voided` |
| `partially_paid` | Some payments applied, balance > 0 | → `paid` |
| `paid` | Full balance settled | (terminal) |
| `voided` | Cancelled, reverses any GL entries | (terminal) |

### 3.2 State Transition Rules

```typescript
type InvoiceState = 'draft' | 'finalized' | 'sent' | 'partially_paid' | 'paid' | 'voided';

const VALID_TRANSITIONS: Record<InvoiceState, InvoiceState[]> = {
  draft:           ['finalized', 'voided'],
  finalized:       ['sent', 'voided'],
  sent:            ['partially_paid', 'paid', 'voided'],
  partially_paid:  ['paid', 'voided'],
  paid:            [],                          // terminal
  voided:          [],                          // terminal
};
```

**Guard conditions per transition:**

| Transition | Guards |
|---|---|
| draft → finalized | invoice_number assigned, at least 1 line item, total > 0, customer exists |
| finalized → sent | sent_via specified, contact email/phone exists |
| sent → partially_paid | payment applied, amount < balance |
| partially_paid → paid | payment applied, amount >= remaining balance |
| any → voided | void_reason required, no payments after void (or reverse them) |

### 3.3 Legacy Migration

The existing `invoice` table is migrated into `customer_invoices`:

| Old column | New column | Transformation |
|---|---|---|
| `clientId` | `customer_id` | Direct map to `client_accounts.id` via name match |
| `clientName` | (dropped) | Resolved via FK |
| `description` | `description` | Direct map |
| `amount` | `total_brl` | Direct map |
| `issueDate` | `invoice_date` | Direct map |
| `dueDate` | `due_date` | Direct map |
| `paidDate` | `paid_at` | Direct map |
| `status: pendente` | `status: sent` | Mapped |
| `status: pago` | `status: paid` | Mapped |
| `status: atrasado` | `status: sent` | Recomputed via aging |

---

## 4. Payment Recording

### 4.1 Payments Table (shared by AP and AR)

```sql
CREATE TABLE payments (
  id                  TEXT PRIMARY KEY,
  tenant_id           TEXT NOT NULL,
  payment_type        TEXT NOT NULL,           -- 'payable' (AP) or 'receivable' (AR)
  direction           TEXT NOT NULL,           -- 'outgoing' (AP) or 'incoming' (AR)
  vendor_id           TEXT REFERENCES vendors(id),
  customer_id         TEXT REFERENCES client_accounts(id),
  payment_date        TEXT NOT NULL,
  amount_brl          NUMERIC NOT NULL,
  payment_method      TEXT NOT NULL,           -- pix, boleto, transfer, credit_card, cash, check
  reference_number    TEXT,                    -- bank transaction ID, pix key, etc.
  bank_account_id     TEXT,                    -- FK to future bank_accounts table
  currency            TEXT DEFAULT 'BRL',
  exchange_rate       NUMERIC DEFAULT 1,
  gl_journal_entry_id TEXT,
  notes               TEXT,
  created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payments_tenant ON payments(tenant_id);
CREATE INDEX idx_payments_type ON payments(tenant_id, payment_type);
CREATE INDEX idx_payments_customer ON payments(customer_id);
CREATE INDEX idx_payments_vendor ON payments(vendor_id);
CREATE INDEX idx_payments_date ON payments(tenant_id, payment_date);
```

### 4.2 Payment Allocations (links payments to invoices/bills)

```sql
CREATE TABLE payment_allocations (
  id              TEXT PRIMARY KEY,
  payment_id      TEXT NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
  bill_id         TEXT REFERENCES bills(id),
  invoice_id      TEXT REFERENCES customer_invoices(id),
  allocated_brl   NUMERIC NOT NULL,            -- amount of this payment applied to this bill/invoice
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  -- constraint: exactly one of bill_id or invoice_id must be non-null
  CONSTRAINT chk_allocation_target CHECK (
    (bill_id IS NOT NULL AND invoice_id IS NULL) OR
    (bill_id IS NULL AND invoice_id IS NOT NULL)
  )
);

CREATE INDEX idx_payment_allocations_payment ON payment_allocations(payment_id);
CREATE INDEX idx_payment_allocations_bill ON payment_allocations(bill_id);
CREATE INDEX idx_payment_allocations_invoice ON payment_allocations(invoice_id);
```

### 4.3 Payment Recording Flow

**Receiving a payment (AR):**

1. Create `payments` record with `direction = 'incoming'`, `customer_id = X`, `amount = Y`
2. Create `payment_allocations` — distribute Y across open invoices for that customer:
   - Oldest invoices first (FIFO) by default
   - Or manual allocation if user specifies which invoices
3. Update each invoice: `amount_paid_brl += allocated_amount`, recompute `balance_brl`
4. If invoice `balance_brl = 0`: transition to `paid`
5. If invoice `balance_brl > 0`: transition to `partially_paid`
6. Update customer: `credit_used_brl -= payment_amount` (frees credit)
7. Post GL journal entry (see Section 10)

**Making a payment (AP):**

1. Create `payments` record with `direction = 'outgoing'`, `vendor_id = X`, `amount = Y`
2. Create `payment_allocations` — distribute Y across open bills for that vendor
3. Update each bill: `amount_paid_brl += allocated_amount`, recompute `balance_brl`
4. If bill `balance_brl = 0`: transition to `paid`
5. If bill `balance_brl > 0`: transition to `partially_paid`
6. Post GL journal entry

**Overpayment handling:**

- If payment amount > total of allocated invoices/bills:
  - Apply to allocated invoices/bills first
  - Remaining amount stored as `credit_balance` on the customer/vendor
  - `customer_accounts.credit_used_brl` is reduced accordingly
  - Future invoices automatically apply from credit balance first

**Partial payment handling:**

- Each allocation records exactly how much of the payment goes to which invoice/bill
- Invoice/bill status transitions to `partially_paid` when balance > 0 after allocation
- Payment schedule installments are checked: if an installment is fully covered, it marks as `paid`

---

## 5. Aging Reports

### 5.1 AR Aging Dashboard SQL

```sql
-- AR Aging Summary (totals only)
SELECT
  SUM(balance_brl) FILTER (WHERE days_overdue <= 0) AS current_total,
  SUM(balance_brl) FILTER (WHERE days_overdue BETWEEN 1 AND 30) AS d1_30_total,
  SUM(balance_brl) FILTER (WHERE days_overdue BETWEEN 31 AND 60) AS d31_60_total,
  SUM(balance_brl) FILTER (WHERE days_overdue BETWEEN 61 AND 90) AS d61_90_total,
  SUM(balance_brl) FILTER (WHERE days_overdue > 90) AS d90_plus_total,
  SUM(balance_brl) AS grand_total,
  COUNT(*) FILTER (WHERE days_overdue > 30) AS invoices_overdue_count
FROM (
  SELECT ci.balance_brl,
    EXTRACT(DAY FROM (CURRENT_DATE::timestamp - ci.due_date::timestamp))::integer AS days_overdue
  FROM customer_invoices ci
  WHERE ci.tenant_id = $1
    AND ci.status NOT IN ('paid', 'voided')
    AND ci.balance_brl > 0
) sub;
```

```sql
-- AR Aging Detail (per customer, for drill-down)
SELECT
  ci.id AS invoice_id,
  ci.invoice_number,
  ca.name AS customer_name,
  ci.total_brl,
  ci.amount_paid_brl,
  ci.balance_brl,
  ci.due_date,
  EXTRACT(DAY FROM (CURRENT_DATE::timestamp - ci.due_date::timestamp))::integer AS days_overdue,
  CASE
    WHEN ci.due_date >= CURRENT_DATE THEN 'current'
    WHEN EXTRACT(DAY FROM (CURRENT_DATE::timestamp - ci.due_date::timestamp)) <= 30 THEN '1-30'
    WHEN EXTRACT(DAY FROM (CURRENT_DATE::timestamp - ci.due_date::timestamp)) <= 60 THEN '31-60'
    WHEN EXTRACT(DAY FROM (CURRENT_DATE::timestamp - ci.due_date::timestamp)) <= 90 THEN '61-90'
    ELSE '90+'
  END AS aging_bucket
FROM customer_invoices ci
JOIN client_accounts ca ON ca.id = ci.customer_id
WHERE ci.tenant_id = $1
  AND ci.status NOT IN ('paid', 'voided')
  AND ci.balance_brl > 0
ORDER BY days_overdue DESC;
```

### 5.2 AP Aging Dashboard SQL

```sql
-- AP Aging Summary
SELECT
  SUM(balance_brl) FILTER (WHERE days_overdue <= 0) AS current_total,
  SUM(balance_brl) FILTER (WHERE days_overdue BETWEEN 1 AND 30) AS d1_30_total,
  SUM(balance_brl) FILTER (WHERE days_overdue BETWEEN 31 AND 60) AS d31_60_total,
  SUM(balance_brl) FILTER (WHERE days_overdue BETWEEN 61 AND 90) AS d61_90_total,
  SUM(balance_brl) FILTER (WHERE days_overdue > 90) AS d90_plus_total,
  SUM(balance_brl) AS grand_total
FROM (
  SELECT b.balance_brl,
    EXTRACT(DAY FROM (CURRENT_DATE::timestamp - b.due_date::timestamp))::integer AS days_overdue
  FROM bills b
  WHERE b.tenant_id = $1
    AND b.status NOT IN ('paid', 'voided')
    AND b.balance_brl > 0
) sub;
```

### 5.3 Dashboard Visualization

```
┌─────────────────────────────────────────────────────────────────┐
│  ACCOUNTS RECEIVABLE AGING                                      │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────┤
│ Current  │  1-30    │  31-60   │  61-90   │  90+     │  Total   │
│ R$ 45,200│ R$ 12,800│ R$  8,400│ R$  3,100│ R$  1,500│ R$ 71,000│
│   63.7%  │  18.0%   │  11.8%   │   4.4%   │   2.1%   │  100%    │
├──────────┴──────────┴──────────┴──────────┴──────────┴──────────┤
│  [Bar chart: horizontal stacked bars per customer]              │
│  [Line chart: aging trend over last 6 months]                   │
│  [Table: top 10 overdue customers with drill-down]              │
└─────────────────────────────────────────────────────────────────┘
```

Widget components:
- **Summary cards**: Total outstanding, current, 1-30, 31-60, 61-90, 90+ as stat cards
- **Stacked bar chart**: Per-customer aging breakdown (horizontal bars, color-coded by bucket)
- **Trend line**: 6-month aging trend (total outstanding per bucket over time)
- **Drill-down table**: Click a bucket → list of invoices in that bucket, sortable by amount/date

---

## 6. Three-Way Matching (AP)

### 6.1 Purchase Orders

```sql
CREATE TABLE purchase_orders (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  po_number       TEXT NOT NULL,               -- sequential, tenant-scoped (PO-2026-00001)
  vendor_id       TEXT NOT NULL REFERENCES vendors(id),
  description     TEXT,
  order_date      TEXT NOT NULL,
  expected_date   TEXT,
  status          TEXT DEFAULT 'draft',        -- draft → submitted → partially_received → received → closed → cancelled
  subtotal_brl    NUMERIC DEFAULT 0,
  tax_amount_brl  NUMERIC DEFAULT 0,
  total_brl       NUMERIC DEFAULT 0,
  approved_by     TEXT,
  approved_at     TIMESTAMP WITH TIME ZONE,
  notes           TEXT,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE po_line_items (
  id              TEXT PRIMARY KEY,
  po_id           TEXT NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
  line_number     INTEGER NOT NULL,
  description     TEXT,
  quantity        NUMERIC NOT NULL,
  unit_price_brl  NUMERIC NOT NULL,
  quantity_received NUMERIC DEFAULT 0,
  quantity_billed NUMERIC DEFAULT 0,
  total_brl       NUMERIC NOT NULL,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 6.2 Goods Receipts

```sql
CREATE TABLE goods_receipts (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  po_id           TEXT NOT NULL REFERENCES purchase_orders(id),
  receipt_number  TEXT,
  receipt_date    TEXT NOT NULL,
  received_by     TEXT,
  notes           TEXT,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE goods_receipt_line_items (
  id                TEXT PRIMARY KEY,
  receipt_id        TEXT NOT NULL REFERENCES goods_receipts(id) ON DELETE CASCADE,
  po_line_item_id   TEXT NOT NULL REFERENCES po_line_items(id),
  quantity_received NUMERIC NOT NULL,
  condition         TEXT DEFAULT 'good',       -- good, damaged, partial
  notes             TEXT,
  created_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 6.3 Matching Logic

Three-way matching compares:

1. **PO line item**: ordered quantity × unit price = PO total
2. **Goods receipt line item**: received quantity (must be ≤ ordered quantity)
3. **Bill line item**: billed quantity × unit price (must match received quantity × PO unit price, within tolerance)

**Tolerance thresholds** (configurable per tenant):

| Field | Default tolerance | Behavior on exceed |
|---|---|---|
| Quantity | 0% (exact match) | Block approval, require manual override |
| Unit price | 2% | Block if >2% variance, warn if ≤2% |
| Total amount | 5% (BRL) | Block if >5% variance |

**Matching status on bill:**

```sql
ALTER TABLE bills ADD COLUMN IF NOT EXISTS match_status TEXT DEFAULT 'unmatched';
-- Values: unmatched, partially_matched, matched, variance_exceeded
```

**Auto-matching flow:**

1. Bill is created with `po_id` set
2. System queries `po_line_items` where `po_id = bill.po_id`
3. For each bill line item, find matching PO line item by description + quantity
4. Compare unit prices within tolerance
5. If all lines match: `match_status = 'matched'`
6. If some lines match: `match_status = 'partially_matched'`
7. If any line exceeds tolerance: `match_status = 'variance_exceeded'`, block approval

---

## 7. Credit Management

### 7.1 Credit Check Logic

```typescript
interface CreditCheckResult {
  allowed: boolean;
  currentCredit: number;
  creditLimit: number;
  creditUsed: number;
  availableCredit: number;
  reason?: string;
}

function checkCustomerCredit(
  customer: ClientAccount,
  newInvoiceAmount: number
): CreditCheckResult {
  const available = customer.credit_limit_brl - customer.credit_used_brl;
  return {
    allowed: available >= newInvoiceAmount,
    currentCredit: customer.credit_limit_brl,
    creditLimit: customer.credit_limit_brl,
    creditUsed: customer.credit_used_brl,
    availableCredit: available,
    reason: available < newInvoiceAmount
      ? `Invoice amount R$ ${newInvoiceAmount} exceeds available credit R$ ${available}`
      : undefined,
  };
}
```

### 7.2 Credit Actions

| Action | Trigger | Effect |
|---|---|---|
| `hold` | Credit limit exceeded, or manual | `credit_status = 'hold'`, block new invoices |
| `release` | Payment received reducing balance below limit, or manual | `credit_status = 'active'` |
| `increase` | Manual credit limit increase | Update `credit_limit_brl` |
| `decrease` | Manual credit limit decrease | Update `credit_limit_brl`, re-check existing open invoices |

### 7.3 Credit Hold Impact

When `credit_status = 'hold'`:
- New invoice creation is blocked (finalization fails guard)
- Existing invoices remain unaffected
- User sees "Credit Hold" badge on customer profile
- Dunning escalations continue independently

---

## 8. Recurring Invoices

### 8.1 Recurring Invoice Templates

```sql
CREATE TABLE recurring_invoice_templates (
  id                TEXT PRIMARY KEY,
  tenant_id         TEXT NOT NULL,
  customer_id       TEXT NOT NULL REFERENCES client_accounts(id),
  contract_id       TEXT REFERENCES contracts(id),
  template_name     TEXT NOT NULL,
  description       TEXT,
  frequency         TEXT NOT NULL,              -- monthly, quarterly, semi_annual, annual
  frequency_interval INTEGER DEFAULT 1,         -- every N periods
  day_of_month      INTEGER DEFAULT 1,          -- which day to generate (1-28)
  currency          TEXT DEFAULT 'BRL',
  subtotal_brl      NUMERIC DEFAULT 0,
  discount_brl      NUMERIC DEFAULT 0,
  tax_rate_pct      NUMERIC DEFAULT 0,
  payment_terms     TEXT DEFAULT 'net_30',
  auto_send         INTEGER DEFAULT 0,          -- 1 = auto-email on generation
  active            INTEGER DEFAULT 1,
  next_run_date     TEXT,                       -- computed: next generation date
  last_run_date     TEXT,
  created_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE recurring_invoice_template_lines (
  id              TEXT PRIMARY KEY,
  template_id     TEXT NOT NULL REFERENCES recurring_invoice_templates(id) ON DELETE CASCADE,
  line_number     INTEGER NOT NULL,
  description     TEXT,
  quantity        NUMERIC DEFAULT 1,
  unit_price_brl  NUMERIC DEFAULT 0,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 8.2 Generation Job

Runs daily (cron or Inngest):

```sql
-- Find templates due for generation
SELECT * FROM recurring_invoice_templates
WHERE active = 1
  AND next_run_date <= CURRENT_DATE;
```

**Per template:**

1. Create `customer_invoices` record in `draft` state
2. Copy line items from template
3. Assign `invoice_number` (sequential)
4. Apply customer credit check → if blocked, set `credit_hold = 1` and skip auto-send
5. If `auto_send = 1` and no credit hold: transition draft → finalized → sent
6. Update `next_run_date` based on frequency:
   - monthly: add 1 month to current `next_run_date`
   - quarterly: add 3 months
   - semi_annual: add 6 months
   - annual: add 1 year
7. Set `last_run_date = CURRENT_DATE`

---

## 9. GL Integration

### 9.1 Journal Entry Posting

Every invoice, bill, and payment generates a balanced journal entry. The GL module provides a `create_journal_entry` function that AP/AR/Invoicing call.

**AP Bill approved:**
```
Dr. Expense/Asset Account     R$ 1,000
    Cr. Accounts Payable                    R$ 1,000
```

**AP Payment made:**
```
Dr. Accounts Payable          R$ 1,000
    Cr. Bank/Cash Account                   R$ 1,000
```

**AR Invoice finalized:**
```
Dr. Accounts Receivable       R$ 2,500
    Cr. Revenue Account                     R$ 2,500
```

**AR Payment received:**
```
Dr. Bank/Cash Account         R$ 2,500
    Cr. Accounts Receivable                 R$ 2,500
```

**Invoice voided (reversal):**
```
Dr. Revenue Account            R$ 2,500
    Cr. Accounts Receivable                 R$ 2,500
```

**Payment voided (reversal):**
```
Dr. Accounts Receivable        R$ 2,500
    Cr. Bank/Cash Account                   R$ 2,500
```

### 9.2 GL Interface Contract

```typescript
interface JournalEntryLine {
  account_code: string;      // COA account code
  debit_brl: number;
  credit_brl: number;
  description?: string;
  reference_type: string;    // 'bill', 'invoice', 'payment'
  reference_id: string;      // ID of the source document
}

interface CreateJournalEntryRequest {
  tenant_id: string;
  entry_date: string;
  entry_type: string;        // 'ap_bill', 'ap_payment', 'ar_invoice', 'ar_payment', 'reversal'
  source_module: string;     // 'accounts_payable', 'accounts_receivable', 'invoicing'
  source_id: string;         // bill/invoice/payment ID
  lines: JournalEntryLine[];
  memo?: string;
}

interface JournalEntryResponse {
  id: string;
  entry_number: string;
  status: 'posted' | 'pending';
  balanced: boolean;
}
```

### 9.3 GL Dependency Note

The GL module is built by a sibling agent in this same batch. The interface contract above defines what AP/AR/Invoicing expects from GL. If GL is not yet available:

- Define a `GLStub` that logs journal entries to a `pending_journal_entries` table
- When GL is wired, backfill pending entries
- All financial data (invoices, bills, payments) is stored independently of GL — GL is a reporting/audit layer, not the source of truth for AP/AR balances

---

## 10. API Endpoints

### 10.1 Vendors (AP)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/vendors` | List vendors (filterable: active, search) |
| `GET` | `/api/vendors/:id` | Get vendor by ID |
| `POST` | `/api/vendors` | Create vendor |
| `PUT` | `/api/vendors/:id` | Update vendor |
| `DELETE` | `/api/vendors/:id` | Soft-delete (set active=0) |

### 10.2 Bills (AP)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/bills` | List bills (filterable: status, vendor, aging_bucket, date range) |
| `GET` | `/api/bills/:id` | Get bill with line items |
| `POST` | `/api/bills` | Create bill (draft) |
| `PUT` | `/api/bills/:id` | Update bill (draft only) |
| `DELETE` | `/api/bills/:id` | Delete bill (draft only) |
| `POST` | `/api/bills/:id/finalize` | Approve bill (draft → approved) |
| `POST` | `/api/bills/:id/pay` | Record payment against bill |
| `POST` | `/api/bills/:id/void` | Void bill |
| `GET` | `/api/bills/:id/match` | Run three-way match check |
| `GET` | `/api/bills/aging` | AP aging report (summary + detail) |

### 10.3 Customer Invoices (AR + Invoicing)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/invoices` | List customer invoices (filterable: status, customer, aging, date range) |
| `GET` | `/api/invoices/:id` | Get invoice with line items + payments |
| `POST` | `/api/invoices` | Create invoice (draft) |
| `PUT` | `/api/invoices/:id` | Update invoice (draft only) |
| `DELETE` | `/api/invoices/:id` | Delete invoice (draft only) |
| `POST` | `/api/invoices/:id/finalize` | Finalize invoice (assign number, lock) |
| `POST` | `/api/invoices/:id/send` | Send invoice (email/whatsapp/portal) |
| `POST` | `/api/invoices/:id/pay` | Record payment against invoice |
| `POST` | `/api/invoices/:id/void` | Void invoice (with reversal) |
| `GET` | `/api/invoices/aging` | AR aging report |
| `GET` | `/api/invoices/number/next` | Get next invoice number |

### 10.4 Payments (shared)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/payments` | List payments (filterable: type, date range, customer/vendor) |
| `GET` | `/api/payments/:id` | Get payment with allocations |
| `POST` | `/api/payments` | Record payment (auto-allocate or manual) |
| `POST` | `/api/payments/:id/allocate` | Adjust allocation |
| `POST` | `/api/payments/:id/void` | Void payment (reverse allocations) |

### 10.5 Recurring Templates

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/recurring-invoices` | List templates |
| `POST` | `/api/recurring-invoices` | Create template |
| `PUT` | `/api/recurring-invoices/:id` | Update template |
| `DELETE` | `/api/recurring-invoices/:id` | Deactivate template |
| `POST` | `/api/recurring-invoices/:id/run-now` | Force immediate generation |

### 10.6 Purchase Orders (Three-Way Matching)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/purchase-orders` | List POs |
| `POST` | `/api/purchase-orders` | Create PO |
| `POST` | `/api/purchase-orders/:id/approve` | Approve PO |
| `POST` | `/api/purchase-orders/:id/receive` | Record goods receipt |
| `POST` | `/api/purchase-orders/:id/close` | Close PO |

### 10.7 Credit Management

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/customers/:id/credit` | Get credit status |
| `POST` | `/api/customers/:id/credit/hold` | Place credit hold |
| `POST` | `/api/customers/:id/credit/release` | Release credit hold |
| `PUT` | `/api/customers/:id/credit/limit` | Update credit limit |

### 10.8 Server Actions (Next.js)

Extend `app/actions.ts` with typed actions:

```typescript
// Vendor actions
getVendors(), addVendor(), updateVendor(), deleteVendor()

// Bill actions
getBills(), addBill(), updateBill(), deleteBill()
finalizeBill(), payBill(), voidBill(), matchBill()

// Customer invoice actions
getCustomerInvoices(), addCustomerInvoice(), updateCustomerInvoice(), deleteCustomerInvoice()
finalizeInvoice(), sendInvoice(), payInvoice(), voidInvoice()

// Payment actions
getPayments(), addPayment(), allocatePayment(), voidPayment()

// Aging actions
getAPAging(), getARAging()

// Recurring actions
getRecurringTemplates(), addRecurringTemplate(), updateRecurringTemplate(), runRecurringTemplate()

// PO actions
getPurchaseOrders(), addPurchaseOrder(), approvePurchaseOrder(), receivePurchaseOrder()
```

---

## 11. Effort Estimate

### 11.1 Sub-Feature Breakdown

| # | Sub-Feature | Effort (dev-days) | Depends On | Notes |
|---|---|---|---|---|
| 1 | **Vendor model + CRUD** | 3 | — | Schema, repository (SQLite + Supabase), API, UI |
| 2 | **Bill model + CRUD** | 4 | — | Schema, repository, line items, API, UI |
| 3 | **Payment schedule model** | 2 | Bills | Installment tracking |
| 4 | **Invoice state machine** | 3 | — | State transitions, guards, validation |
| 5 | **Customer invoice model + CRUD** | 5 | State machine | Replaces legacy invoice, line items, migration script |
| 6 | **Payment recording + allocation** | 5 | Bills, Invoices | Shared payments table, FIFO allocation, partial/overpayment |
| 7 | **Aging computation (AP)** | 2 | Bills | SQL queries, bucket assignment, nightly recomputation |
| 8 | **Aging computation (AR)** | 2 | Invoices | SQL queries, bucket assignment |
| 9 | **Aging dashboard widgets** | 3 | Aging computation | Summary cards, bar charts, drill-down tables |
| 10 | **Dunning system** | 3 | AR aging | Dunning levels, auto-email templates, escalation logic |
| 11 | **Three-way matching** | 5 | Bills, Vendor | PO model, goods receipt, matching algorithm, tolerance config |
| 12 | **Credit management** | 3 | Customer invoices | Credit limits, hold/release, credit check on invoice creation |
| 13 | **Recurring invoice templates** | 4 | Customer invoices | Template model, generation job, frequency logic |
| 14 | **GL integration hooks** | 3 | GL module (sibling) | Journal entry posting, reversal on void, pending queue |
| 15 | **Legacy invoice migration** | 2 | Customer invoices | Data migration script, mapping old status → new state machine |
| 16 | **MCP tools expansion** | 2 | All above | get_vendors, get_bills, get_customer_invoices, get_payments, get_aging |
| 17 | **Webhook events** | 1 | All above | bill.created/paid/overdue, invoice.finalized/sent/paid/voided, payment.recorded |
| 18 | **Tests (unit + integration)** | 5 | All above | State machine tests, allocation logic, aging SQL, matching |
| **Total** | | **57 dev-days** | | ~11.4 weeks (1 dev) or ~3.8 weeks (3 parallel devs) |

### 11.2 Parallelization Opportunities

| Stream | Sub-Features | Days |
|---|---|---|
| **A: AP core** | 1, 2, 3, 7, 11 | 19 |
| **B: AR + Invoicing** | 4, 5, 8, 9, 12 | 18 |
| **C: Payments + automation** | 6, 10, 13, 14, 15, 16, 17, 18 | 21 |

With 3 developers in parallel: **~7-8 weeks** (accounting for integration overhead).

### 11.3 Phase Alignment

Per `B1-module-dependencies.md`, AP/AR/Invoicing are **Phase 3+4** modules:

- Phase 2: GL (prerequisite — being built by sibling agent)
- Phase 3: AP, AR (parallel with Fiscal Year)
- Phase 4: Invoicing, Payments, Expenses (depends on AP + AR + GL)

This batch 2 plan covers Phase 3+4 in one shot since AP, AR, and Invoicing are tightly coupled.

---

## 12. Implementation Sequence

### Wave 1 (Weeks 1-2): Foundation
- Vendor model + CRUD
- Bill model + CRUD (with line items)
- Invoice state machine
- Customer invoice model + CRUD (with line items, replacing legacy)
- GL interface contract + stub

### Wave 2 (Weeks 3-4): Payments + Aging
- Payment recording + allocation engine
- Payment schedule model
- Aging computation (AP + AR)
- Aging dashboard widgets
- Legacy invoice migration script

### Wave 3 (Weeks 5-6): Automation + Matching
- Three-way matching (PO, receipt, bill)
- Dunning system
- Credit management
- Recurring invoice templates + generation job

### Wave 4 (Weeks 7-8): Integration + Polish
- GL integration hooks (wire to real GL when available)
- MCP tools expansion
- Webhook events
- Full test suite (unit + integration)
- Performance tuning (indexes, query optimization)

---

## 13. Open Questions

1. **Invoice numbering format**: Sequential per tenant (INV-2026-00001) or configurable prefix? → Recommend configurable prefix with sequential counter, tenant-scoped.
2. **Multi-currency on bills**: Phase 2 (P2.17) adds multi-currency. For now, all amounts are BRL. Should the data model include `currency` columns even if only BRL is supported? → Yes, include columns for future-proofing.
3. **Tax calculation on invoices**: The Tax Engine module (Phase 5) handles ICMS/ISS/PIS. For now, tax is manual entry on line items. When Tax Engine ships, it auto-computes. → Design for manual-first, auto-later.
4. **Bank reconciliation dependency**: Payments record `bank_account_id` but bank_accounts table comes in the Bank Reconciliation module. → Use nullable FK, wire when Bank Rec ships.
5. **Approval workflow for bills**: The Approval module (Phase 5) adds multi-level approval. For now, single-user approval (`approved_by` field). → Design for single approval, extend later.
