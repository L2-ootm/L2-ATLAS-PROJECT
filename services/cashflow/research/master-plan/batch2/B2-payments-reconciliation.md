# B2: Payments Module + Bank Reconciliation — Implementation Plan

> Date: 2026-07-10 · Scope: Payments (XL) + Bank Reconciliation (L)
> Depends on: Accounts Payable (L), Accounts Receivable (L), General Ledger (XL), Chart of Accounts (M)
> Downstream: Cash Flow Forecast, Receipts, NFe/NFS-e/CT-e, Payment Gateways, Recurring Billing, Anomaly Detection, Banking/Open Finance

---

## 1. Payment Data Model

### 1.1 Core Tables

```sql
-- payments: central payment record
CREATE TABLE payments (
    payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    payment_number TEXT NOT NULL,          -- human-readable: PAY-2026-000001
    direction TEXT NOT NULL,               -- 'payable' | 'receivable'
    payment_method TEXT NOT NULL,          -- 'pix' | 'boleto' | 'card' | 'transfer' | 'cash' | 'check'
    status TEXT NOT NULL DEFAULT 'draft',  -- see §1.2 status machine
    
    -- parties
    payer_account_id UUID REFERENCES bank_accounts(account_id),
    payee_account_id UUID REFERENCES bank_accounts(account_id),
    vendor_id UUID,                        -- for payables (FK to vendor table, future)
    client_id UUID,                        -- for receivables (FK to client_accounts)
    
    -- amounts
    amount NUMERIC(18,6) NOT NULL CHECK (amount > 0),
    fee_amount NUMERIC(18,6) DEFAULT 0,
    discount_amount NUMERIC(18,6) DEFAULT 0,
    tax_amount NUMERIC(18,6) DEFAULT 0,
    net_amount NUMERIC(18,6) NOT NULL,     -- amount - fee - discount + tax
    currency TEXT DEFAULT 'BRL',
    
    -- references
    invoice_id UUID,                       -- FK to invoices (receivable)
    journal_entry_id UUID,                 -- FK to journal_entries (posted entry)
    purchase_order_id UUID,                -- FK to purchase_orders (payable, future)
    
    -- payment-specific data
    scheduled_date DATE,                   -- when to execute
    executed_date DATE,                    -- when actually executed
    settled_date DATE,                     -- when bank confirms settlement
    due_date DATE,                         -- for boleto
    
    -- method-specific payload (JSONB for flexibility)
    payment_details JSONB,                 -- see §1.3
    
    -- reconciliation
    reconciled BOOLEAN DEFAULT false,
    reconciled_at TIMESTAMPTZ,
    reconciliation_id UUID,                -- FK to reconciliation_runs
    
    -- approval
    approval_status TEXT DEFAULT 'draft',  -- 'draft' | 'pending_approval' | 'approved' | 'rejected'
    approved_by UUID,
    approved_at TIMESTAMPTZ,
    
    -- audit
    created_by UUID NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE (tenant_id, payment_number)
);

CREATE INDEX idx_payments_tenant_status ON payments (tenant_id, status);
CREATE INDEX idx_payments_tenant_date ON payments (tenant_id, executed_date);
CREATE INDEX idx_payments_tenant_method ON payments (tenant_id, payment_method);
CREATE INDEX idx_payments_reconciled ON payments (tenant_id, reconciled) WHERE reconciled = false;
```

### 1.2 Payment Status Machine

```
                    ┌──────────┐
                    │  draft   │
                    └────┬─────┘
                         │ submit for approval
                    ┌────▼──────────┐
              ┌─────│pending_approval│─────┐
              │     └────┬──────────┘     │
              │ reject   │ approve        │ expire
         ┌────▼───┐  ┌───▼──────┐    ┌───▼──────┐
         │rejected│  │ approved │    │ cancelled │
         └────────┘  └───┬──────┘    └──────────┘
                         │ execute payment
                    ┌────▼──────────┐
                    │  processing   │──── failure ────► failed
                    └────┬──────────┘
                         │ bank confirms
                    ┌────▼──────────┐
                    │   executed    │
                    └────┬──────────┘
                         │ settlement confirmed
                    ┌────▼──────────┐
                    │   settled     │
                    └────┬──────────┘
                         │ reconciled against bank statement
                    ┌────▼──────────┐
                    │  reconciled   │
                    └───────────────┘

Terminal states: rejected, cancelled, failed, reconciled
Non-terminal states: draft, pending_approval, approved, processing, executed, settled
```

### 1.3 Payment Details JSONB Schema (by method)

```typescript
// Pix payment details
interface PixPaymentDetails {
  type: 'pix';
  pix_key_type: 'cpf' | 'cnpj' | 'email' | 'phone' | 'random';  // chave Pix
  pix_key: string;
  qr_code_emv: string;           // EMV QR Code payload
  qr_code_image: string;         // base64 PNG of QR code
  pix_copy_paste: string;        // copy-paste string (copia-e-cola)
  end_to_end_id?: string;        // E2E ID from payment processor
  txid?: string;                 // transaction ID (25 chars max)
  expiration?: number;           // seconds until QR expires (default 3600)
  stq?: string;                  // SPI settlement token
}

// Boleto payment details
interface BoletoPaymentDetails {
  type: 'boleto';
  barcode: string;               // 44-digit barcode (boleto bancário)
  digitable_line: string;        // linha digitável (47 digits)
  convenio?: string;             // agreement number
  carteira?: string;             // wallet code
  nosso_numero?: string;         // our number (bank-specific)
  bank_code: string;             // 3-digit bank code (237=Bradesco, 001=BB, 341=Itaú)
  banco_beneficiario?: string;   // bank beneficiary code
  sacado_cpf_cnpj?: string;     // payer document
  aceite?: string;               // 'S' or 'N'
  especie?: string;              // document type code (DM=Duplicata Mercantil)
  instrucoes?: string;           // payment instructions
  url_pdf?: string;              // URL to download PDF
}

// Card payment details
interface CardPaymentDetails {
  type: 'card';
  gateway: string;               // 'stripe' | 'pagseguro' | 'mercadopago'
  gateway_payment_id: string;    // gateway's payment ID
  card_brand: string;            // 'visa' | 'mastercard' | 'elo' | 'amex'
  card_last_four: string;
  installments?: number;
  authorization_code?: string;
  capture_method?: 'automatic' | 'manual';
}

// Bank transfer details
interface TransferPaymentDetails {
  type: 'transfer';
  source_bank: string;           // bank code
  source_agency: string;         // branch number
  source_account: string;        // account number
  source_account_type: string;   // 'checking' | 'savings'
  dest_bank: string;
  dest_agency: string;
  dest_account: string;
  dest_account_type: string;
  dest_cpf_cnpj?: string;       // recipient document
  doc_number?: string;           // DOC/TED number
  ted_mode?: string;             // 'TED' | 'DOC' | 'PIX'
}
```

### 1.4 Bank Accounts Table

```sql
CREATE TABLE bank_accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    account_name TEXT NOT NULL,
    bank_code TEXT NOT NULL,               -- 3-digit BACEN code
    bank_name TEXT,
    agency TEXT NOT NULL,
    account_number TEXT NOT NULL,
    account_type TEXT DEFAULT 'checking',  -- 'checking' | 'savings'
    currency TEXT DEFAULT 'BRL',
    opening_balance NUMERIC(18,6) DEFAULT 0,
    current_balance NUMERIC(18,6) DEFAULT 0,  -- computed or maintained
    gl_account_id UUID REFERENCES accounts(account_id),  -- link to chart of accounts
    is_active BOOLEAN DEFAULT true,
    ofx_import_enabled BOOLEAN DEFAULT false,
    last_sync_at TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE (tenant_id, bank_code, agency, account_number)
);
```

### 1.5 Payment Schedules (Batch Payments)

```sql
CREATE TABLE payment_schedules (
    schedule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    schedule_name TEXT NOT NULL,
    frequency TEXT NOT NULL,               -- 'once' | 'weekly' | 'biweekly' | 'monthly' | 'quarterly'
    next_execution DATE,
    end_date DATE,                         -- optional end condition
    max_executions INTEGER,
    execution_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',          -- 'active' | 'paused' | 'completed' | 'cancelled'
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE schedule_items (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id UUID NOT NULL REFERENCES payment_schedules(schedule_id) ON DELETE CASCADE,
    vendor_id UUID,
    client_id UUID,
    description TEXT NOT NULL,
    amount NUMERIC(18,6) NOT NULL,
    payment_method TEXT NOT NULL,
    payment_details JSONB,
    invoice_id UUID,
    gl_account_id UUID,                    -- expense/revenue account
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 1.6 Refund / Credit Note Table

```sql
CREATE TABLE payment_refunds (
    refund_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    refund_number TEXT NOT NULL,           -- REF-2026-000001
    original_payment_id UUID NOT NULL REFERENCES payments(payment_id),
    amount NUMERIC(18,6) NOT NULL CHECK (amount > 0),
    reason TEXT NOT NULL,                  -- 'duplicate' | 'overcharge' | 'service_cancelled' | 'other'
    reason_notes TEXT,
    status TEXT DEFAULT 'draft',           -- 'draft' | 'pending_approval' | 'approved' | 'processing' | 'completed' | 'failed'
    journal_entry_id UUID,                 -- reversal journal entry
    refund_details JSONB,                  -- method-specific refund info
    approved_by UUID,
    approved_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by UUID NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 2. Payment Processing Flow

### 2.1 State Machine Implementation (Inngest Step Functions)

```typescript
// lib/payments/flow.ts

export async function processPayment(paymentId: string) {
  // Step 1: Validate and lock
  const payment = await paymentRepo.findById(paymentId);
  if (payment.status !== 'approved') throw new Error('Payment not approved');
  
  // Step 2: Execute based on method
  const result = await executePaymentMethod(payment);
  
  // Step 3: Record result
  if (result.success) {
    await paymentRepo.updateStatus(paymentId, 'executed', {
      executed_date: new Date(),
      'payment_details.end_to_end_id': result.transactionId,
    });
    
    // Step 4: Create journal entry (debit/credit)
    const journalEntry = await createPaymentJournalEntry(payment);
    
    // Step 5: Emit event for downstream modules
    await eventBus.publish('payment.executed', {
      payment_id: paymentId,
      journal_entry_id: journalEntry.id,
      amount: payment.amount,
      method: payment.payment_method,
    });
  } else {
    await paymentRepo.updateStatus(paymentId, 'failed', {
      'payment_details.error': result.error,
    });
    await eventBus.publish('payment.failed', {
      payment_id: paymentId,
      error: result.error,
    });
  }
}

async function executePaymentMethod(payment: Payment) {
  switch (payment.payment_method) {
    case 'pix':
      return await pixProvider.createPayment(payment);
    case 'boleto':
      return await boletoProvider.registerBoleto(payment);
    case 'card':
      return await cardProvider.charge(payment);
    case 'transfer':
      return await transferProvider.initiate(payment);
    default:
      return { success: true, transactionId: null }; // cash/check: no external call
  }
}
```

### 2.2 Inngest Integration

```typescript
// app/api/inngest/route.ts (new step function)

import { inngest } from '@/lib/inngest/client';

export const paymentProcessing = inngest.createFunction(
  { id: 'payment-processing' },
  { event: 'payment.approved' },
  async ({ event, step }) => {
    const { payment_id } = event.data;
    
    // Step 1: Execute payment
    const result = await step.run('execute-payment', () =>
      processPayment(payment_id)
    );
    
    // Step 2: If payment succeeded, schedule reconciliation check
    if (result?.success) {
      await step.run('check-settlement', () =>
        scheduleSettlementCheck(payment_id, 24) // check in 24h
      );
    }
    
    return result;
  }
);
```

### 2.3 Approval Workflow

```
Payment > R$ 10,000 ──► requires CFO approval
Payment > R$ 50,000 ──► requires CEO approval
Payment scheduled ──► auto-approved if < R$ 5,000 and method = pix/transfer
Batch payment ──► single approval for entire batch
```

Approval is tracked in the `payments.approval_status` field. Approved payments emit `payment.approved` event which triggers the Inngest processing function.

---

## 3. Pix Integration

### 3.1 Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  L2 Cashflow│────►│ Pix Provider │────►│ Banco Central    │
│  (Payments) │     │  (adapter)   │     │ (SPI/DICT)       │
└─────────────┘     └──────────────┘     └─────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Asaas         PagSeguro    Gerencianet
         (API)         (API)        (API)
```

### 3.2 Pix Provider Adapter Pattern

```typescript
// lib/payments/providers/pix/types.ts

interface PixProvider {
  // Create a Pix charge (static QR code for a fixed amount)
  createCharge(params: {
    amount: number;
    description: string;
    payer_cpf_cnpj?: string;
    expiration_seconds?: number;
  }): Promise<PixChargeResult>;
  
  // Create a Pix charge with dynamic amount (QR code generated at payment time)
  createDynamicCharge(params: {
    amount: number;
    description: string;
    txid: string;
  }): Promise<PixChargeResult>;
  
  // Check if payment was received (polling or webhook)
  checkPayment(txid: string): Promise<PixPaymentStatus>;
  
  // Get Pix key info (for QR code generation)
  getPixKey(): Promise<PixKeyInfo>;
}

interface PixChargeResult {
  success: boolean;
  txid: string;
  emv_qr_code: string;      // QR code payload for rendering
  copy_paste: string;        // copy-paste string
  qr_code_base64?: string;   // pre-rendered QR image
  expiration: Date;
  error?: string;
}

interface PixPaymentStatus {
  status: 'pending' | 'paid' | 'expired';
  paid_at?: Date;
  payer_name?: string;
  payer_cpf_cnpj?: string;
  end_to_end_id?: string;
  amount?: number;
}
```

### 3.3 QR Code Generation (client-side)

```typescript
// lib/payments/pix/qr-code.ts

import QRCode from 'qrcode';

export async function generatePixQrCode(emvPayload: string): Promise<string> {
  // Returns base64 PNG
  return QRCode.toDataURL(emvPayload, {
    errorCorrectionLevel: 'M',
    width: 300,
    margin: 2,
    color: {
      dark: '#000000',
      light: '#FFFFFF',
    },
  });
}
```

### 3.4 Pix Copy-Paste Format

The EMV QR Code payload for Pix follows the BR Code standard (similar to TLV encoding):

```
00 02 01           # Payload Format Indicator
01 02 12           # Point of Initiation Method (12 = dynamic, 11 = static)
26 XX              # Merchant Account Information
  00 14 br.gov.bcb.pix
  01 XX [pix_key]  # PIX key
27 XX              # Transaction Amount (optional for static)
52 04 0000         # Merchant Category Code
53 03 986          # Transaction Currency (986 = BRL)
54 XX [amount]     # Transaction Amount
58 02 BR           # Country Code
59 XX [city]       # Merchant City
60 XX [name]       # Merchant Name
62 XX              # Additional Data Field
  05 XX [txid]     # TXID
63 04 XXXX         # CRC16 (checksum)
```

### 3.5 Pix Webhook Handler

```typescript
// app/api/webhooks/pix/route.ts

export async function POST(req: Request) {
  const payload = await req.json();
  
  // Verify webhook signature
  if (!verifyPixWebhookSignature(req, payload)) {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 401 });
  }
  
  const { txid, status, amount, payer, end_to_end_id } = payload;
  
  if (status === 'paid') {
    // Find payment by txid
    const payment = await paymentRepo.findByPixTxid(txid);
    if (!payment) return NextResponse.json({ error: 'Payment not found' }, { status: 404 });
    
    // Update payment status
    await paymentRepo.updateStatus(payment.payment_id, 'executed', {
      executed_date: new Date(),
      'payment_details.end_to_end_id': end_to_end_id,
    });
    
    // Create journal entry
    await createPaymentJournalEntry(payment);
    
    // Emit event
    await eventBus.publish('payment.executed', {
      payment_id: payment.payment_id,
      method: 'pix',
      amount,
    });
  }
  
  return NextResponse.json({ received: true });
}
```

---

## 4. Boleto Generation

### 4.1 Boleto Bancário Structure

A boleto bancário in Brazil has:
- **44-digit barcode** (código de barras) — contains bank, amount, due date, and check digits
- **Digitable line** (linha digitável) — 47 digits, human-readable version of barcode
- **Registration** with the bank (boleto registrado) — allows tracking and automatic credit

```typescript
// lib/payments/boleto/barcode.ts

interface BoletoBarcode {
  bank_code: string;         // 3 digits
  currency_code: string;     // 9 = BRL
  due_date_factor: number;   // days since 07/10/1997
  amount: number;            // in cents, no decimal point
  free_field: string;        // 25 digits (varies by bank)
  check_digit: string;       // 1 digit (modulus 10/11)
}

// Calculate due date factor (days since 07/10/1997)
function dueDateFactor(dueDate: Date): number {
  const base = new Date(1997, 6, 10); // 07/10/1997
  return Math.floor((dueDate.getTime() - base.getTime()) / (1000 * 60 * 60 * 24));
}

// Generate boleto barcode for different banks
function generateBarcode(params: {
  bank_code: string;
  amount: number;        // in BRL
  due_date: Date;
  convenio?: string;
  carteira?: string;
  nosso_numero?: string;
  agencia?: string;
  conta?: string;
}): string {
  // Each bank has its own barcode layout
  // This is a simplified version — real implementation varies by bank
  const factor = dueDateFactor(params.due_date);
  const amountCents = Math.round(params.amount * 100);
  
  // Position 1-3: Bank code
  // Position 4: Currency (9 = BRL)
  // Position 5-6: Check digit (placeholder)
  // Position 7-14: Due date factor + amount
  // Position 15-44: Free field (bank-specific)
  
  const barcode = `${params.bank_code}9${String(factor).padStart(4, '0')}${String(amountCents).padStart(10, '0')}${params.free_field}`;
  
  // Calculate check digit (modulus 11)
  const checkDigit = calculateMod11CheckDigit(barcode);
  
  return barcode.substring(0, 4) + checkDigit + barcode.substring(5);
}
```

### 4.2 Bank-Specific Boleto Layouts

| Bank | Code | Barcode Layout (positions 20-44) | Check Digit |
|------|------|-----------------------------------|-------------|
| Bradesco | 237 | Agência(4) + Conta(8) + Carteira(2) + Nosso Número(12) | Mod 11 |
| Itaú Unibanco | 341 | Carteira(3) + Nosso Número(8) + Agência(4) + Conta(5) + Zero(3) | Mod 10 |
| Banco do Brasil | 001 | Convenio(7) + Nosso Número(10) + Agência(4) + Conta(8) + Tipo(1) | Mod 11 |
| Santander | 033 | Nosso Número(12) + Agência(4) + Conta(10) | Mod 10 |
| Caixa | 104 | Convenio(3) + Nosso Número(15) + Código CEF(3) + Livre(4) | Mod 11 |

### 4.3 Boleto Registration API

```typescript
// lib/payments/providers/boleto/types.ts

interface BoletoProvider {
  // Register a boleto with the bank
  register(params: {
    amount: number;
    due_date: Date;
    payer_name: string;
    payer_cpf_cnpj: string;
    payer_address?: string;
    description: string;
    instructions?: string;
  }): Promise<BoletoRegistrationResult>;
  
  // Check boleto status
  checkStatus(nosso_numero: string): Promise<BoletoStatus>;
  
  // Cancel a boleto (before due date)
  cancel(nosso_numero: string): Promise<boolean>;
  
  // Get boleto PDF
  getPdfUrl(nosso_numero: string): Promise<string>;
  
  // Generate PDF locally (for custom templates)
  generatePdf(boleto: BoletoRegistrationResult): Promise<Buffer>;
}

interface BoletoRegistrationResult {
  success: boolean;
  nosso_numero: string;
  barcode: string;
  digitable_line: string;
  bank_slip_url?: string;      // URL to bank's PDF
  bank_slip_base64?: string;   // PDF as base64
  our_number: string;
  error?: string;
}

interface BoletoStatus {
  status: 'pending' | 'paid' | 'overdue' | 'cancelled';
  paid_at?: Date;
  paid_amount?: number;
  payment_date?: Date;
}
```

### 4.4 Boleto PDF Generation (Custom Template)

```typescript
// lib/payments/boleto/pdf-generator.ts

import { jsPDF } from 'jspdf';
import 'jspdf-autotable';

export function generateBoletoPdf(boleto: BoletoData): Buffer {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: [230, 110] });
  
  // Boleto layout follows FEBRABAN specification
  // 3 sections: Sacado (payer), Cedente (beneficiary), Sacador-Avalista (guarantor)
  
  // Recorte guia (cut guide)
  doc.setFontSize(7);
  doc.text('Recorte na linha pontilhada', 10, 5);
  doc.setLineDashPattern([2, 2], 0);
  doc.line(10, 8, 220, 8);
  
  // Section 1: Payment info
  doc.setFontSize(10);
  doc.text(`Banco ${boleto.bank_name}`, 10, 15);
  doc.text(boleto.digitable_line.substring(0, 30), 10, 25);
  
  // Amount box
  doc.setFontSize(18);
  doc.text(`R$ ${boleto.amount.toFixed(2)}`, 150, 25);
  
  // Due date
  doc.setFontSize(9);
  doc.text('Data de Vencimento:', 10, 35);
  doc.text(boleto.due_date, 60, 35);
  
  // Beneficiary info
  doc.text('Cedente:', 10, 45);
  doc.text(boleto.beneficiary_name, 40, 45);
  doc.text('CNPJ:', 10, 55);
  doc.text(boleto.beneficiary_cnpj, 40, 55);
  
  // Our number
  doc.text('Nosso Número:', 10, 65);
  doc.text(boleto.our_number, 60, 65);
  
  // Payer info
  doc.text('Sacado:', 10, 80);
  doc.text(boleto.payer_name, 40, 80);
  doc.text(boleto.payer_cpf_cnpj, 10, 90);
  
  // Barcode (drawn as text — real implementation uses barcode library)
  doc.setFontSize(7);
  doc.text(boleto.barcode, 10, 100);
  
  return Buffer.from(doc.output('arraybuffer'));
}
```

---

## 5. Bank Reconciliation

### 5.1 Reconciliation Data Model

```sql
-- Bank statement imports
CREATE TABLE bank_statement_imports (
    import_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    bank_account_id UUID NOT NULL REFERENCES bank_accounts(account_id),
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,               -- 'ofx' | 'cnab240' | 'cnab400' | 'csv'
    statement_period_start DATE,
    statement_period_end DATE,
    total_transactions INTEGER DEFAULT 0,
    total_amount NUMERIC(18,6) DEFAULT 0,
    status TEXT DEFAULT 'imported',        -- 'imported' | 'processing' | 'completed' | 'error'
    imported_by UUID NOT NULL,
    imported_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    metadata JSONB
);

-- Individual bank statement transactions
CREATE TABLE bank_transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES bank_statement_imports(import_id),
    tenant_id UUID NOT NULL,
    bank_account_id UUID NOT NULL,
    transaction_date DATE NOT NULL,
    value_date DATE,
    description TEXT NOT NULL,
    description_normalized TEXT,           -- cleaned version for matching
    amount NUMERIC(18,6) NOT NULL,        -- positive = credit, negative = debit
    balance NUMERIC(18,6),                -- running balance after transaction
    transaction_type TEXT,                -- 'credit' | 'debit' | 'transfer_in' | 'transfer_out'
    document_number TEXT,                 -- bank document reference
    check_number TEXT,
    
    -- Matching
    match_status TEXT DEFAULT 'unmatched', -- 'unmatched' | 'auto_matched' | 'manual_matched' | 'ignored'
    matched_payment_id UUID REFERENCES payments(payment_id),
    matched_je_id UUID REFERENCES journal_entries(je_id),
    match_confidence NUMERIC(5,4),        -- 0.0000 to 1.0000
    match_rule TEXT,                       -- which rule matched
    matched_by UUID,                       -- user who manually matched
    matched_at TIMESTAMPTZ,
    
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_bank_tx_import ON bank_transactions (import_id);
CREATE INDEX idx_bank_tx_tenant_date ON bank_transactions (tenant_id, transaction_date);
CREATE INDEX idx_bank_tx_unmatched ON bank_transactions (tenant_id, match_status) WHERE match_status = 'unmatched';

-- Reconciliation runs
CREATE TABLE reconciliation_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    bank_account_id UUID NOT NULL,
    import_id UUID NOT NULL REFERENCES bank_statement_imports(import_id),
    run_date TIMESTAMPTZ DEFAULT now(),
    status TEXT DEFAULT 'in_progress',     -- 'in_progress' | 'completed' | 'review_required'
    
    -- Stats
    total_bank_transactions INTEGER DEFAULT 0,
    total_system_transactions INTEGER DEFAULT 0,
    auto_matched_count INTEGER DEFAULT 0,
    manual_matched_count INTEGER DEFAULT 0,
    unmatched_count INTEGER DEFAULT 0,
    discrepancy_count INTEGER DEFAULT 0,
    
    -- Thresholds used
    amount_tolerance NUMERIC(18,6) DEFAULT 0.01,
    date_tolerance_days INTEGER DEFAULT 3,
    
    completed_at TIMESTAMPTZ,
    metadata JSONB
);

-- Reconciliation match details
CREATE TABLE reconciliation_matches (
    match_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES reconciliation_runs(run_id),
    bank_transaction_id UUID NOT NULL REFERENCES bank_transactions(transaction_id),
    payment_id UUID REFERENCES payments(payment_id),
    journal_entry_id UUID REFERENCES journal_entries(je_id),
    match_type TEXT NOT NULL,              -- 'exact' | 'fuzzy' | 'manual'
    confidence NUMERIC(5,4),
    amount_difference NUMERIC(18,6) DEFAULT 0,
    date_difference_days INTEGER DEFAULT 0,
    matched_by UUID,                       -- null for auto, user ID for manual
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 5.2 OFX Import

```typescript
// lib/reconciliation/parsers/ofx.ts

import { OfxParser } from 'ofx-parser';

interface OfxTransaction {
  fitId: string;              // Financial Institution Transaction ID
  name: string;               // transaction name/description
  memo?: string;              // additional memo
  amount: number;             // negative = debit, positive = credit
  date: Date;                 // transaction date
  type: 'CREDIT' | 'DEBIT' | 'OTHER';
  checkNumber?: string;
}

export async function parseOfxFile(fileContent: string): Promise<OfxTransaction[]> {
  const parser = new OfxParser();
  const result = await parser.parse(fileContent);
  
  return result.account.transactions.map(tx => ({
    fitId: tx.fitId,
    name: tx.name || tx.memo || '',
    memo: tx.memo,
    amount: tx.amount,
    date: tx.datePosted || tx.dateAvailable,
    type: tx.amount > 0 ? 'CREDIT' : 'DEBIT',
    checkNumber: tx.checkNumber,
  }));
}

export function normalizeOfxDescription(desc: string): string {
  return desc
    .toUpperCase()
    .replace(/[^\w\s]/g, '')     // remove special chars
    .replace(/\s+/g, ' ')       // collapse whitespace
    .trim();
}
```

### 5.3 CNAB Import (CNAB240 / CNAB400)

```typescript
// lib/reconciliation/parsers/cnab.ts

interface CnabTransaction {
  branch: string;
  account: string;
  complement: string;
  movement_type: string;       // '01'=credit, '02'=debit, etc.
  date: Date;
  amount: number;
  description: string;
  document: string;
  origin: string;              // 'DOC' | 'TED' | 'PIX' | 'BOLETO'
}

export function parseCnab240(line: string): CnabTransaction {
  // CNAB240: 240-byte fixed-width records
  // Record type '3' = movement detail
  const segment = line.substring(13, 14); // J=bank slip, K=payment, etc.
  
  const transaction: CnabTransaction = {
    branch: line.substring(17, 21).trim(),
    account: line.substring(21, 29).trim(),
    complement: line.substring(29, 34).trim(),
    movement_type: line.substring(14, 16),
    date: parseCnabDate(line.substring(138, 146)),
    amount: parseCnabAmount(line.substring(152, 167)),
    description: line.substring(240).trim(),
    document: line.substring(37, 47).trim(),
    origin: parseOrigin(line),
  };
  
  return transaction;
}

export function parseCnab400(line: string): CnabTransaction {
  // CNAB400: 400-byte records (older format, still common)
  const transaction: CnabTransaction = {
    branch: line.substring(17, 21).trim(),
    account: line.substring(21, 29).trim(),
    complement: line.substring(29, 34).trim(),
    movement_type: line.substring(8, 11), // '002'=entry, '009'=deletion
    date: parseCnabDate(line.substring(114, 122)),
    amount: parseCnabAmount(line.substring(152, 167)),
    description: line.substring(240).trim(),
    document: line.substring(37, 47).trim(),
    origin: parseOrigin(line),
  };
  
  return transaction;
}

function parseCnabDate(dateStr: string): Date {
  // Format: ddmmyyyy
  const day = parseInt(dateStr.substring(0, 2));
  const month = parseInt(dateStr.substring(2, 4));
  const year = parseInt(dateStr.substring(4, 8));
  return new Date(year, month - 1, day);
}

function parseCnabAmount(amountStr: string): number {
  // CNAB amounts: right-aligned, no decimal point, 2 decimal places
  const cleaned = amountStr.replace(/\s/g, '').replace(/,/g, '');
  return parseInt(cleaned) / 100;
}
```

---

## 6. Matching Algorithms

### 6.1 Matching Pipeline

```
Bank Transaction ──► Phase 1: Exact Match ──► Phase 2: Fuzzy Match ──► Phase 3: Manual Queue
                      │                        │                        │
                      │ Match found?           │ Match found?           │ User matches
                      │ → auto_match           │ → auto_match           │ → manual_match
                      │   confidence: 1.0      │   confidence: 0.7-0.99 │   confidence: 1.0
                      │                        │                        │
                      ▼                        ▼                        ▼
                 Record match           Record match              Record match
```

### 6.2 Exact Match Algorithm

```typescript
// lib/reconciliation/matchers/exact.ts

interface MatchResult {
  payment_id: string;
  confidence: number;
  match_type: 'exact';
  amount_difference: number;
  date_difference_days: number;
}

export function findExactMatch(
  bankTx: BankTransaction,
  payments: Payment[]
): MatchResult | null {
  for (const payment of payments) {
    // Match 1: Same amount + same date (±0 days)
    if (
      Math.abs(payment.net_amount - Math.abs(bankTx.amount)) < 0.001 &&
      daysBetween(payment.executed_date, bankTx.transaction_date) === 0
    ) {
      return {
        payment_id: payment.payment_id,
        confidence: 1.0,
        match_type: 'exact',
        amount_difference: 0,
        date_difference_days: 0,
      };
    }
    
    // Match 2: Same amount + Pix E2E ID in description
    if (
      payment.payment_method === 'pix' &&
      payment.payment_details?.end_to_end_id &&
      bankTx.description.includes(payment.payment_details.end_to_end_id)
    ) {
      return {
        payment_id: payment.payment_id,
        confidence: 1.0,
        match_type: 'exact',
        amount_difference: 0,
        date_difference_days: daysBetween(payment.executed_date, bankTx.transaction_date),
      };
    }
    
    // Match 3: Same amount + boleto barcode in description
    if (
      payment.payment_method === 'boleto' &&
      payment.payment_details?.digitable_line &&
      bankTx.description.includes(payment.payment_details.digitable_line.substring(0, 20))
    ) {
      return {
        payment_id: payment.payment_id,
        confidence: 1.0,
        match_type: 'exact',
        amount_difference: 0,
        date_difference_days: daysBetween(payment.due_date, bankTx.transaction_date),
      };
    }
  }
  
  return null;
}
```

### 6.3 Fuzzy Match Algorithm

```typescript
// lib/reconciliation/matchers/fuzzy.ts

interface FuzzyMatchConfig {
  amount_tolerance: number;      // default: 0.01 (1 cent)
  date_tolerance_days: number;   // default: 3 days
  min_confidence: number;        // default: 0.70
}

export function findFuzzyMatch(
  bankTx: BankTransaction,
  payments: Payment[],
  config: FuzzyMatchConfig
): MatchResult | null {
  const candidates: MatchResult[] = [];
  
  for (const payment of payments) {
    const amountDiff = Math.abs(payment.net_amount - Math.abs(bankTx.amount));
    const dateDiff = daysBetween(payment.executed_date || payment.scheduled_date, bankTx.transaction_date);
    
    // Skip if outside tolerance
    if (amountDiff > config.amount_tolerance) continue;
    if (dateDiff > config.date_tolerance_days) continue;
    
    // Calculate confidence score
    let confidence = 0;
    
    // Amount match: closer = higher score
    const amountScore = 1 - (amountDiff / config.amount_tolerance);
    confidence += amountScore * 0.6;  // 60% weight for amount
    
    // Date match: closer = higher score
    const dateScore = 1 - (dateDiff / config.date_tolerance_days);
    confidence += dateScore * 0.25;  // 25% weight for date
    
    // Description similarity (Levenshtein-based)
    const descScore = calculateDescriptionSimilarity(
      bankTx.description_normalized,
      payment.description || ''
    );
    confidence += descScore * 0.15;  // 15% weight for description
    
    if (confidence >= config.min_confidence) {
      candidates.push({
        payment_id: payment.payment_id,
        confidence,
        match_type: 'fuzzy' as const,
        amount_difference: amountDiff,
        date_difference_days: dateDiff,
      });
    }
  }
  
  // Return best match
  candidates.sort((a, b) => b.confidence - a.confidence);
  return candidates[0] || null;
}

function calculateDescriptionSimilarity(a: string, b: string): number {
  // Simple Jaccard similarity on words
  const wordsA = new Set(a.toLowerCase().split(/\s+/));
  const wordsB = new Set(b.toLowerCase().split(/\s+/));
  const intersection = new Set([...wordsA].filter(x => wordsB.has(x)));
  const union = new Set([...wordsA, ...wordsB]);
  return union.size > 0 ? intersection.size / union.size : 0;
}
```

### 6.4 Smart Reconciliation Engine

```typescript
// lib/reconciliation/engine.ts

export async function runReconciliation(
  bankAccountId: string,
  importId: string,
  config: FuzzyMatchConfig = DEFAULT_CONFIG
): Promise<ReconciliationResult> {
  // 1. Load unmatched bank transactions
  const bankTxs = await bankTransactionRepo.findUnmatched(importId);
  
  // 2. Load unmatched payments (executed/settled in date range)
  const payments = await paymentRepo.findUnmatched(bankAccountId, {
    startDate: config.start_date,
    endDate: config.end_date,
  });
  
  const results: ReconciliationResult = {
    exact_matches: [],
    fuzzy_matches: [],
    unmatched_bank: [],
    unmatched_payments: [],
  };
  
  // 3. Phase 1: Exact matching
  for (const bankTx of bankTxs) {
    const match = findExactMatch(bankTx, payments);
    if (match) {
      results.exact_matches.push({ bank_tx: bankTx, ...match });
      await recordMatch(bankTx.transaction_id, match);
    } else {
      results.unmatched_bank.push(bankTx);
    }
  }
  
  // 4. Phase 2: Fuzzy matching (only on unmatched)
  const remainingPayments = payments.filter(
    p => !results.exact_matches.some(m => m.payment_id === p.payment_id)
  );
  
  for (const bankTx of results.unmatched_bank) {
    const match = findFuzzyMatch(bankTx, remainingPayments, config);
    if (match) {
      results.fuzzy_matches.push({ bank_tx: bankTx, ...match });
      await recordMatch(bankTx.transaction_id, match);
    }
  }
  
  // 5. Remaining unmatched
  results.unmatched_payments = remainingPayments.filter(
    p => !results.fuzzy_matches.some(m => m.payment_id === p.payment_id)
  );
  
  return results;
}
```

---

## 7. Reconciliation Reports

### 7.1 Report Data Structures

```typescript
interface ReconciliationReport {
  run_id: string;
  run_date: string;
  bank_account: string;
  period: { start: string; end: string };
  
  summary: {
    total_bank_transactions: number;
    total_system_transactions: number;
    auto_matched: number;
    manual_matched: number;
    unmatched_bank: number;
    unmatched_payments: number;
    total_matched_amount: number;
    total_discrepancy_amount: number;
    reconciliation_rate: number;  // percentage matched
  };
  
  matched: ReconciliationMatch[];
  unmatched_bank: UnmatchedBankTransaction[];
  unmatched_payments: UnmatchedPayment[];
  discrepancies: Discrepancy[];
}

interface ReconciliationMatch {
  bank_tx_id: string;
  bank_tx_date: string;
  bank_tx_description: string;
  bank_tx_amount: number;
  payment_id: string;
  payment_number: string;
  payment_method: string;
  payment_amount: number;
  match_type: 'exact' | 'fuzzy' | 'manual';
  confidence: number;
  amount_difference: number;
  date_difference_days: number;
}

interface Discrepancy {
  bank_tx_id: string;
  payment_id: string;
  discrepancy_type: 'amount_mismatch' | 'duplicate' | 'missing_payment' | 'missing_statement';
  amount: number;
  description: string;
}
```

### 7.2 SQL Views for Reporting

```sql
-- Reconciliation summary view
CREATE VIEW v_reconciliation_summary AS
SELECT
  rr.run_id,
  rr.tenant_id,
  rr.bank_account_id,
  ba.account_name,
  rr.run_date,
  rr.total_bank_transactions,
  rr.total_system_transactions,
  rr.auto_matched_count + rr.manual_matched_count AS total_matched,
  rr.unmatched_count,
  rr.discrepancy_count,
  ROUND(
    (rr.auto_matched_count + rr.manual_matched_count)::NUMERIC / 
    GREATEST(rr.total_bank_transactions, 1) * 100, 2
  ) AS reconciliation_rate_pct,
  COALESCE(SUM(rm.amount_difference), 0) AS total_amount_discrepancy
FROM reconciliation_runs rr
JOIN bank_accounts ba ON rr.bank_account_id = ba.account_id
LEFT JOIN reconciliation_matches rm ON rr.run_id = rm.run_id
GROUP BY rr.run_id, ba.account_name;

-- Unmatched bank transactions view
CREATE VIEW v_unmatched_bank_transactions AS
SELECT
  bt.transaction_id,
  bt.tenant_id,
  bt.bank_account_id,
  ba.account_name,
  bt.transaction_date,
  bt.description,
  bt.amount,
  bt.document_number,
  bt.match_status,
  bi.import_id,
  bi.file_name
FROM bank_transactions bt
JOIN bank_accounts ba ON bt.bank_account_id = ba.account_id
JOIN bank_statement_imports bi ON bt.import_id = bi.import_id
WHERE bt.match_status = 'unmatched'
ORDER BY bt.transaction_date DESC;

-- Daily reconciliation status
CREATE VIEW v_daily_reconciliation_status AS
SELECT
  bt.tenant_id,
  bt.bank_account_id,
  bt.transaction_date,
  COUNT(*) AS total_transactions,
  COUNT(CASE WHEN bt.match_status = 'auto_matched' THEN 1 END) AS auto_matched,
  COUNT(CASE WHEN bt.match_status = 'manual_matched' THEN 1 END) AS manual_matched,
  COUNT(CASE WHEN bt.match_status = 'unmatched' THEN 1 END) AS unmatched,
  SUM(bt.amount) AS total_amount,
  SUM(CASE WHEN bt.match_status != 'unmatched' THEN bt.amount ELSE 0 END) AS matched_amount
FROM bank_transactions bt
GROUP BY bt.tenant_id, bt.bank_account_id, bt.transaction_date;
```

---

## 8. Payment Scheduling

### 8.1 Batch Payment Processing

```typescript
// lib/payments/scheduler.ts

interface BatchPaymentRequest {
  schedule_id: string;
  execution_date: Date;
  items: {
    vendor_id: string;
    amount: number;
    payment_method: string;
    payment_details: JSON;
    invoice_id?: string;
    description: string;
  }[];
  approval_required?: boolean;
}

export async function executeBatchPayment(request: BatchPaymentRequest): Promise<BatchPaymentResult> {
  // 1. Create individual payment records
  const payments: Payment[] = [];
  for (const item of request.items) {
    const payment = await paymentRepo.create({
      payment_number: generatePaymentNumber(),
      direction: 'payable',
      payment_method: item.payment_method,
      status: 'draft',
      amount: item.amount,
      net_amount: item.amount,
      scheduled_date: request.execution_date,
      payment_details: item.payment_details,
      invoice_id: item.invoice_id,
      description: item.description,
    });
    payments.push(payment);
  }
  
  // 2. If approval required, submit all for approval
  if (request.approval_required) {
    for (const payment of payments) {
      await paymentRepo.updateStatus(payment.payment_id, 'pending_approval');
    }
    return { status: 'pending_approval', payment_ids: payments.map(p => p.payment_id) };
  }
  
  // 3. Auto-approve small amounts
  const BATCH_AUTO_APPROVE_LIMIT = 5000; // R$ 5,000
  const totalAmount = payments.reduce((sum, p) => sum + p.amount, 0);
  
  if (totalAmount <= BATCH_AUTO_APPROVE_LIMIT) {
    for (const payment of payments) {
      await paymentRepo.updateStatus(payment.payment_id, 'approved');
      await eventBus.publish('payment.approved', { payment_id: payment.payment_id });
    }
    return { status: 'auto_approved', payment_ids: payments.map(p => p.payment_id) };
  }
  
  // 4. Large batch — require approval
  for (const payment of payments) {
    await paymentRepo.updateStatus(payment.payment_id, 'pending_approval');
  }
  return { status: 'pending_approval', payment_ids: payments.map(p => p.payment_id) };
}
```

### 8.2 Payment Date Optimization

```typescript
// lib/payments/date-optimizer.ts

export function optimizePaymentDate(
  dueDate: Date,
  paymentMethod: string,
  bankHolidayCalendar: Date[]
): Date {
  let candidateDate = new Date(dueDate);
  
  // Never pay on weekends or bank holidays
  while (isWeekend(candidateDate) || isBankHoliday(candidateDate, bankHolidayCalendar)) {
    candidateDate.setDate(candidateDate.getDate() - 1); // pay earlier, not later
  }
  
  // For boleto: pay 1-2 days before due date to ensure credit on time
  if (paymentMethod === 'boleto') {
    candidateDate.setDate(candidateDate.getDate() - 1);
    while (isWeekend(candidateDate) || isBankHoliday(candidateDate, bankHolidayCalendar)) {
      candidateDate.setDate(candidateDate.getDate() - 1);
    }
  }
  
  // For Pix: can pay on due date (instant settlement)
  // For DOC: pay 1-2 days before (DOC has 1-day settlement)
  // For TED: can pay on due date (same-day settlement if before cut-off)
  
  return candidateDate;
}
```

---

## 9. Refund Handling

### 9.1 Refund Flow

```
Initiate Refund ──► Approval ──► Execute ──► Journal Entry (reversal) ──► Update Reconciliation

Refund types:
  - 'credit_note': issue credit note against original invoice
  - 'pix_refund': initiate Pix reversal via provider
  - 'boleto_refund': cannot reverse boleto — issue credit note + manual return
  - 'card_refund': initiate chargeback/refund via gateway
  - 'transfer_refund': initiate reverse transfer
```

### 9.2 Refund Journal Entry

```typescript
// lib/payments/refunds/journal-entry.ts

export async function createRefundJournalEntry(refund: Refund): Promise<JournalEntry> {
  const originalPayment = await paymentRepo.findById(refund.original_payment_id);
  
  // Reverse the original payment journal entry
  // Original: Dr. Expense/Asset  Cr. Bank
  // Reversal: Dr. Bank  Cr. Expense/Asset
  
  return await journalEntryRepo.create({
    tenant_id: refund.tenant_id,
    entry_date: new Date(),
    description: `Refund ${refund.refund_number} - ${refund.reason}`,
    source_module: 'payments',
    source_doc_id: refund.refund_id,
    reversal_of: originalPayment.journal_entry_id,
    is_posted: false,
    lines: [
      {
        account_id: originalPayment.payer_account_id, // bank account
        debit: refund.amount,
        credit: 0,
      },
      {
        account_id: originalPayment.gl_account_id, // original expense/revenue account
        debit: 0,
        credit: refund.amount,
      },
    ],
  });
}
```

### 9.3 Credit Note Generation

```typescript
// lib/payments/refunds/credit-note.ts

export async function generateCreditNote(refund: Refund): Promise<CreditNote> {
  const originalPayment = await paymentRepo.findById(refund.original_payment_id);
  
  return {
    credit_note_number: generateCreditNoteNumber(),
    tenant_id: refund.tenant_id,
    original_payment_id: refund.original_payment_id,
    original_payment_number: originalPayment.payment_number,
    amount: refund.amount,
    reason: refund.reason,
    reason_notes: refund.reason_notes,
    issued_date: new Date(),
    due_date: null, // credit notes don't have due dates
    status: 'issued',
    gl_account_id: originalPayment.gl_account_id,
    metadata: {
      refund_id: refund.refund_id,
      journal_entry_id: refund.journal_entry_id,
    },
  };
}
```

---

## 10. GL Integration

### 10.1 Payment Journal Entries

Every payment creates a double-entry journal entry:

```
Payment (expense/vendor payment):
  Dr. Expense Account / Accounts Payable    R$ X
  Cr. Bank Account                          R$ X

Payment (client receipt):
  Dr. Bank Account                          R$ X
  Cr. Accounts Receivable / Revenue         R$ X

Payment with fee (e.g., Pix fee):
  Dr. Expense Account                       R$ X
  Dr. Bank Charges Expense                  R$ 0.50
  Cr. Bank Account                          R$ X + 0.50

Refund:
  Dr. Bank Account                          R$ X
  Cr. Expense Account / Accounts Receivable R$ X
```

### 10.2 Bank Account Reconciliation Entries

```typescript
// lib/payments/gl-integration.ts

export async function createPaymentJournalEntry(payment: Payment): Promise<JournalEntry> {
  const lines: JournalEntryLine[] = [];
  
  if (payment.direction === 'payable') {
    // Paying a vendor
    lines.push({
      account_id: payment.expense_account_id, // or AP account
      debit: payment.net_amount,
      credit: 0,
    });
    if (payment.fee_amount > 0) {
      lines.push({
        account_id: BANK_CHARGES_ACCOUNT_ID,
        debit: payment.fee_amount,
        credit: 0,
      });
    }
    lines.push({
      account_id: payment.payer_account_id, // bank account
      debit: 0,
      credit: payment.net_amount + payment.fee_amount,
    });
  } else {
    // Receiving from client
    lines.push({
      account_id: payment.payer_account_id, // bank account
      debit: payment.net_amount,
      credit: 0,
    });
    if (payment.fee_amount > 0) {
      lines.push({
        account_id: BANK_CHARGES_ACCOUNT_ID,
        debit: payment.fee_amount,
        credit: 0,
      });
      lines.push({
        account_id: payment.revenue_account_id, // or AR account
        debit: 0,
        credit: payment.net_amount + payment.fee_amount,
      });
    } else {
      lines.push({
        account_id: payment.revenue_account_id,
        debit: 0,
        credit: payment.net_amount,
      });
    }
  }
  
  // Validate: debits must equal credits
  const totalDebits = lines.reduce((sum, l) => sum + l.debit, 0);
  const totalCredits = lines.reduce((sum, l) => sum + l.credit, 0);
  if (Math.abs(totalDebits - totalCredits) > 0.001) {
    throw new Error(`Journal entry unbalanced: debits=${totalDebits}, credits=${totalCredits}`);
  }
  
  return await journalEntryRepo.create({
    tenant_id: payment.tenant_id,
    entry_date: payment.executed_date || new Date(),
    description: `Payment ${payment.payment_number}`,
    source_module: 'payments',
    source_doc_id: payment.payment_id,
    is_posted: true,
    posted_at: new Date(),
    lines,
  });
}
```

### 10.3 Bank Balance Reconciliation

```sql
-- After importing bank statement and matching:
-- Update bank_accounts.current_balance to match last statement balance

UPDATE bank_accounts
SET current_balance = (
  SELECT bt.balance
  FROM bank_transactions bt
  WHERE bt.bank_account_id = bank_accounts.account_id
    AND bt.match_status != 'unmatched'
  ORDER BY bt.transaction_date DESC
  LIMIT 1
),
last_sync_at = now()
WHERE bank_accounts.account_id = ?;
```

---

## 11. API Endpoints

### 11.1 Payment Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/payments` | Create payment | `payments:write` |
| `GET` | `/api/v1/payments` | List payments (cursor pagination) | `payments:read` |
| `GET` | `/api/v1/payments/:id` | Get payment details | `payments:read` |
| `POST` | `/api/v1/payments/:id/submit` | Submit for approval | `payments:write` |
| `POST` | `/api/v1/payments/:id/approve` | Approve payment | `payments:approve` |
| `POST` | `/api/v1/payments/:id/reject` | Reject payment | `payments:approve` |
| `POST` | `/api/v1/payments/:id/execute` | Execute payment | `payments:execute` |
| `POST` | `/api/v1/payments/:id/cancel` | Cancel payment | `payments:write` |
| `POST` | `/api/v1/payments/:id/refund` | Initiate refund | `payments:write` |
| `GET` | `/api/v1/payments/:id/journal` | Get linked journal entry | `payments:read` |

### 11.2 Bank Account Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/api/v1/bank-accounts` | List bank accounts | `banking:read` |
| `POST` | `/api/v1/bank-accounts` | Create bank account | `banking:write` |
| `GET` | `/api/v1/bank-accounts/:id` | Get bank account details | `banking:read` |
| `GET` | `/api/v1/bank-accounts/:id/balance` | Get current balance | `banking:read` |

### 11.3 Bank Statement & Reconciliation Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/bank-accounts/:id/import` | Import OFX/CNAB file | `banking:write` |
| `GET` | `/api/v1/bank-accounts/:id/transactions` | List bank transactions | `banking:read` |
| `GET` | `/api/v1/bank-accounts/:id/import-history` | List import history | `banking:read` |
| `POST` | `/api/v1/reconciliation/run` | Run auto-reconciliation | `reconciliation:write` |
| `GET` | `/api/v1/reconciliation/runs` | List reconciliation runs | `reconciliation:read` |
| `GET` | `/api/v1/reconciliation/runs/:id` | Get run details + report | `reconciliation:read` |
| `POST` | `/api/v1/reconciliation/match` | Manual match (bank tx → payment) | `reconciliation:write` |
| `POST` | `/api/v1/reconciliation/unmatch` | Remove a match | `reconciliation:write` |
| `POST` | `/api/v1/reconciliation/ignore` | Ignore bank transaction | `reconciliation:write` |

### 11.4 Reconciliation Report Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/api/v1/reconciliation/reports/summary` | Reconciliation summary | `reconciliation:read` |
| `GET` | `/api/v1/reconciliation/reports/unmatched` | Unmatched transactions | `reconciliation:read` |
| `GET` | `/api/v1/reconciliation/reports/discrepancies` | Discrepancy report | `reconciliation:read` |
| `GET` | `/api/v1/reconciliation/reports/export` | Export report (CSV/PDF) | `reconciliation:read` |

### 11.5 Payment Schedule Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/api/v1/payment-schedules` | List schedules | `payments:read` |
| `POST` | `/api/v1/payment-schedules` | Create schedule | `payments:write` |
| `PUT` | `/api/v1/payment-schedules/:id` | Update schedule | `payments:write` |
| `POST` | `/api/v1/payment-schedules/:id/execute` | Execute batch | `payments:execute` |
| `POST` | `/api/v1/payment-schedules/:id/pause` | Pause schedule | `payments:write` |
| `POST` | `/api/v1/payment-schedules/:id/resume` | Resume schedule | `payments:write` |

### 11.6 Webhook Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/webhooks/pix` | Pix payment notification | HMAC signature |
| `POST` | `/api/webhooks/boleto` | Boleto payment notification | HMAC signature |
| `POST` | `/api/webhooks/card` | Card payment notification | HMAC signature |

### 11.7 API Request/Response Examples

```typescript
// POST /api/v1/payments
// Request
{
  direction: 'payable',
  payment_method: 'pix',
  amount: 1500.00,
  vendor_id: 'vnd_abc123',
  invoice_id: 'inv_xyz789',
  scheduled_date: '2026-07-15',
  payment_details: {
    type: 'pix',
    pix_key_type: 'cnpj',
    pix_key: '12345678000190',
  },
  description: 'Fornecedor ABC - Consultoria Jul/2026',
}

// Response
{
  payment_id: 'pay_def456',
  payment_number: 'PAY-2026-000042',
  status: 'draft',
  amount: 1500.00,
  net_amount: 1500.00,
  created_at: '2026-07-10T14:30:00Z',
}

// POST /api/v1/bank-accounts/:id/import (multipart/form-data)
// File: ofx file or CNAB240/CNAB400 file
// Response
{
  import_id: 'imp_ghi012',
  file_name: 'extrato_jul2026.ofx',
  file_type: 'ofx',
  total_transactions: 47,
  total_amount: 125430.89,
  status: 'imported',
}

// POST /api/v1/reconciliation/run
// Request
{
  bank_account_id: 'bank_jkl345',
  import_id: 'imp_ghi012',
  config: {
    amount_tolerance: 0.01,
    date_tolerance_days: 3,
  },
}
// Response
{
  run_id: 'rec_mno678',
  summary: {
    total_bank_transactions: 47,
    total_system_transactions: 52,
    auto_matched: 38,
    fuzzy_matched: 4,
    unmatched_bank: 5,
    unmatched_payments: 8,
    reconciliation_rate: 89.36,
  },
  status: 'completed',
}
```

---

## 12. Effort Estimate

### 12.1 Sub-Feature Breakdown

| # | Sub-Feature | Complexity | Effort (days) | Depends On | Notes |
|---|-------------|------------|---------------|------------|-------|
| 1 | **Payment data model** (schema + migrations) | M | 3 | — | Tables, indexes, Drizzle schema |
| 2 | **Payment CRUD + repository** | M | 5 | #1 | Full repository with dual-backend |
| 3 | **Payment status machine** | M | 3 | #2 | State transitions, validation |
| 4 | **Approval workflow** | M | 4 | #3 | Thresholds, approval UI, events |
| 5 | **Bank account management** | S | 2 | — | CRUD + balance tracking |
| 6 | **Pix provider adapter** | L | 8 | #1 | Asaas/PagSeguro API, QR code, webhooks |
| 7 | **Boleto generation** | L | 7 | #1 | Barcode calc, PDF, registration |
| 8 | **Card payment integration** | M | 5 | #1 | Stripe/PagSeguro adapter |
| 9 | **Transfer processing** | S | 3 | #1 | DOC/TED/PIX transfer |
| 10 | **Payment journal entries** | M | 4 | #1, GL module | Double-entry GL posting |
| 11 | **Refund + credit note** | M | 5 | #2, #10 | Reversal entries, approval |
| 12 | **OFX import parser** | M | 4 | #5 | OFX parsing + normalization |
| 13 | **CNAB240/400 parser** | L | 6 | #5 | Fixed-width parsing, bank-specific |
| 14 | **Bank transaction storage** | S | 2 | #12 or #13 | Schema + repository |
| 15 | **Exact match algorithm** | M | 3 | #14, #2 | Amount + date + reference matching |
| 16 | **Fuzzy match algorithm** | L | 5 | #15 | Tolerance, scoring, confidence |
| 17 | **Smart reconciliation engine** | L | 5 | #15, #16 | Orchestrates matching pipeline |
| 18 | **Manual matching UI** | M | 4 | #17 | Drag-and-drop, split matching |
| 19 | **Reconciliation reports** | M | 4 | #17 | Summary, unmatched, discrepancies |
| 20 | **Payment scheduling** | M | 5 | #2, #4 | Batch payments, date optimization |
| 21 | **Bank holiday calendar** | S | 1 | — | Feriados nacionais + estaduais |
| 22 | **API endpoints** (all) | M | 5 | #2-#20 | REST endpoints + validation |
| 23 | **Webhook handlers** (Pix/boleto/card) | M | 4 | #6, #7, #8 | Inbound payment notifications |
| 24 | **Inngest integration** | M | 3 | #2, #23 | Background payment processing |
| 25 | **UI: Payment list + details** | M | 4 | #22 | Table, filters, status badges |
| 26 | **UI: Payment create/edit** | M | 4 | #22 | Form with method-specific fields |
| 27 | **UI: Reconciliation dashboard** | L | 5 | #19, #22 | Split view, match queue, stats |
| 28 | **UI: Bank account management** | S | 2 | #22 | List, create, balance display |
| 29 | **Unit tests** | M | 5 | All | Match algorithms, status machine, parsers |
| 30 | **Integration tests** | M | 3 | All | API routes, reconciliation flow |

### 12.2 Summary

| Category | Days | % of Total |
|----------|------|-----------|
| Data Model + Schema | 5 | 3% |
| Payment Core (CRUD + Status + Approval) | 12 | 8% |
| Payment Methods (Pix + Boleto + Card + Transfer) | 23 | 15% |
| GL Integration (Journals + Refunds) | 9 | 6% |
| Bank Import (OFX + CNAB) | 12 | 8% |
| Reconciliation Engine + Matching | 22 | 14% |
| Reconciliation UI + Reports | 11 | 7% |
| Payment Scheduling | 6 | 4% |
| API Layer | 9 | 6% |
| UI (Payments + Reconciliation) | 15 | 10% |
| Testing | 8 | 5% |
| **Infrastructure/Inngest/Webhooks** | 10 | 7% |
| **TOTAL** | **~142 days** | **100%** |

### 12.3 Phasing Recommendation

**Phase A — Core (Weeks 1-4): 40 days**
- Data model, payment CRUD, status machine, approval workflow
- Bank account management
- OFX import, bank transaction storage
- Basic matching (exact only)
- API endpoints for payments + bank accounts
- Minimal UI

**Phase B — Payment Methods (Weeks 5-8): 35 days**
- Pix integration (QR code, copy-paste, webhooks)
- Boleto generation (barcode, PDF, registration)
- Card payment adapter
- Transfer processing
- Payment journal entries

**Phase C — Reconciliation (Weeks 9-12): 35 days**
- CNAB240/400 parser
- Fuzzy matching algorithm
- Smart reconciliation engine
- Manual matching UI
- Reconciliation reports + dashboard

**Phase D — Advanced (Weeks 13-16): 32 days**
- Refund + credit note flow
- Payment scheduling + batch payments
- Inngest integration
- Payment date optimization
- Comprehensive testing

**Total: ~16 weeks (4 months)**

### 12.4 Dependencies on Other Modules

```
Payments depends on:
  ├── Accounts Payable (AP) — vendor records, AP sub-ledger
  ├── Accounts Receivable (AR) — client records, AR sub-ledger
  ├── General Ledger (GL) — journal entries, account balances
  └── Chart of Accounts (COA) — expense/revenue/bank accounts

Bank Reconciliation depends on:
  ├── General Ledger (GL) — journal entry matching
  ├── Payments — payment records for matching
  └── Chart of Accounts (COA) — bank account GL mapping

Payments enables (downstream):
  ├── Bank Reconciliation
  ├── Cash Flow Forecast — paid/received amounts
  ├── Receipts — payment receipts
  ├── NFe/NFS-e/CT-e — payment reference
  ├── Payment Gateways — Stripe/PagSeguro integration
  ├── Recurring Billing — automated payments
  └── Anomaly Detection — unusual payment patterns
```

### 12.5 Risk Factors

| Risk | Impact | Mitigation |
|------|--------|------------|
| Pix API certification timeline | High | Start integration early; use sandbox for dev |
| Boleto barcode accuracy | High | Unit test all bank-specific layouts against reference data |
| CNAB format variations per bank | Medium | Start with top 5 banks (Bradesco, Itaú, BB, Santander, Caixa) |
| Payment security (PCI-DSS) | High | Never store card numbers; use tokenized gateway |
| Reconciliation false positives | Medium | Conservative thresholds; require manual review for fuzzy matches |
| GL integration blocking | High | Payments module requires GL to be functional first |

---

## 13. File Structure (Proposed)

```
services/cashflow/
├── lib/
│   ├── payments/
│   │   ├── types.ts                    # Payment, BankAccount, Refund types
│   │   ├── flow.ts                     # Payment processing state machine
│   │   ├── scheduler.ts                # Batch payment scheduling
│   │   ├── date-optimizer.ts           # Payment date optimization
│   │   ├── providers/
│   │   │   ├── pix/
│   │   │   │   ├── types.ts
│   │   │   │   ├── asaas.ts            # Asaas Pix adapter
│   │   │   │   └── pagseguro.ts        # PagSeguro Pix adapter
│   │   │   ├── boleto/
│   │   │   │   ├── types.ts
│   │   │   │   ├── barcode.ts          # Barcode generation
│   │   │   │   ├── pdf-generator.ts    # PDF generation
│   │   │   │   └── bradesco.ts         # Bank-specific adapter
│   │   │   ├── card/
│   │   │   │   ├── types.ts
│   │   │   │   └── stripe.ts           # Stripe adapter
│   │   │   └── transfer/
│   │   │       ├── types.ts
│   │   │       └── ted-doc.ts          # TED/DOC adapter
│   │   └── refunds/
│   │       ├── journal-entry.ts        # Reversal journal entries
│   │       └── credit-note.ts          # Credit note generation
│   ├── reconciliation/
│   │   ├── types.ts
│   │   ├── engine.ts                   # Reconciliation orchestrator
│   │   ├── matchers/
│   │   │   ├── exact.ts
│   │   │   ├── fuzzy.ts
│   │   │   └── manual.ts
│   │   ├── parsers/
│   │   │   ├── ofx.ts
│   │   │   ├── cnab.ts
│   │   │   └── csv.ts
│   │   └── reports/
│   │       ├── summary.ts
│   │       └── discrepancies.ts
│   └── repositories/
│       ├── payment-repository.ts       # Payment CRUD
│       ├── bank-account-repository.ts  # Bank account CRUD
│       └── reconciliation-repository.ts
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── payments/
│   │   │   │   ├── route.ts            # GET list, POST create
│   │   │   │   └── [id]/
│   │   │   │       ├── route.ts        # GET, POST update
│   │   │   │       ├── approve/route.ts
│   │   │   │       ├── execute/route.ts
│   │   │   │       ├── cancel/route.ts
│   │   │   │       └── refund/route.ts
│   │   │   ├── bank-accounts/
│   │   │   │   ├── route.ts
│   │   │   │   └── [id]/
│   │   │   │       ├── route.ts
│   │   │   │       ├── import/route.ts
│   │   │   │       └── transactions/route.ts
│   │   │   ├── reconciliation/
│   │   │   │   ├── run/route.ts
│   │   │   │   ├── runs/[id]/route.ts
│   │   │   │   ├── match/route.ts
│   │   │   │   └── reports/
│   │   │   │       ├── summary/route.ts
│   │   │   │       └── unmatched/route.ts
│   │   │   └── payment-schedules/
│   │   │       ├── route.ts
│   │   │       └── [id]/
│   │   │           └── execute/route.ts
│   │   └── webhooks/
│   │       ├── pix/route.ts
│   │       ├── boleto/route.ts
│   │       └── card/route.ts
│   ├── pagamentos/                     # Payments page
│   │   ├── page.tsx                    # Payment list
│   │   └── [id]/
│   │       └── page.tsx                # Payment details
│   ├── bancos/                         # Bank accounts page
│   │   ├── page.tsx
│   │   └── [id]/
│   │       └── page.tsx
│   └── conciliacao/                    # Reconciliation page
│       ├── page.tsx                    # Reconciliation dashboard
│       └── [runId]/
│           └── page.tsx                # Run details
├── supabase/
│   └── migrations/
│       └── YYYYMMDD_payments_reconciliation.sql
└── tests/
    ├── payments/
    │   ├── status-machine.test.ts
    │   ├── exact-match.test.ts
    │   ├── fuzzy-match.test.ts
    │   └── journal-entry.test.ts
    └── reconciliation/
        ├── ofx-parser.test.ts
        ├── cnab-parser.test.ts
        └── engine.test.ts
```

---

## Appendix A: BACEN Bank Codes (Top 20)

| Code | Bank |
|------|------|
| 001 | Banco do Brasil |
| 033 | Santander |
| 041 | Banco do Estado do Rio Grande do Sul (Banrisul) |
| 070 | Banco BRB |
| 077 | Banco Inter |
| 104 | Caixa Econômica Federal |
| 197 | Stone |
| 208 | BTG Pactual |
| 212 | Banco Original |
| 237 | Bradesco |
| 246 | ABC Brasil |
| 260 | Nu Pagamentos (Nubank) |
| 290 | PagSeguro |
| 318 | BMG |
| 336 | Banco C6 |
| 341 | Itaú Unibanco |
| 389 | Banco Mercantil |
| 422 | Banco Safra |
| 623 | Banco Pan |
| 707 | Banco Daycoval |

## Appendix B: Feriados Bancários 2026 (National)

| Date | Holiday |
|------|---------|
| 2026-01-01 | Ano Novo |
| 2026-04-02 | Sexta-feira Santa |
| 2026-04-21 | Tiradentes |
| 2026-05-01 | Dia do Trabalho |
| 2026-06-11 | Corpus Christi |
| 2026-09-07 | Independência |
| 2026-10-12 | Nossa Senhora Aparecida |
| 2026-11-02 | Finados |
| 2026-11-15 | Proclamação da República |
| 2026-11-20 | Black Friday (not official, but banking ops reduced) |
| 2026-12-25 | Natal |

## Appendix C: Module Manifest (cashflow.toml)

```toml
[module]
name = "cashflow-payments"
version = "1.0.0"
description = "Payment processing, Pix, boleto, and bank reconciliation"
category = "core"
author = "L2 Systems"

[dependencies]
cashflow-core = "^1.0"
cashflow-accounts = "^1.0"     # Chart of Accounts
cashflow-general-ledger = "^1.0"
cashflow-accounts-payable = "^1.0"
cashflow-accounts-receivable = "^1.0"

[contributes]
routes = ["/pagamentos", "/pagamentos/:id", "/bancos", "/bancos/:id", "/conciliacao", "/conciliacao/:runId"]
sidebar = { label = "Pagamentos", icon = "CreditCard", order = 15 }
sidebar_children = [
  { label = "Todos", path = "/pagamentos" },
  { label = "Bancos", path = "/bancos" },
  { label = "Conciliação", path = "/conciliacao" },
]
api_namespace = "/api/v1/payments"
events_published = ["payment.created", "payment.approved", "payment.executed", "payment.settled", "payment.failed", "payment.refunded", "reconciliation.completed"]
events_subscribed = ["invoice.paid", "invoice.voided"]
mcp_tools = ["get_payments", "get_bank_accounts", "run_reconciliation"]

[security]
permissions = ["payments:read", "payments:write", "payments:approve", "payments:execute", "banking:read", "banking:write", "reconciliation:read", "reconciliation:write"]
requires_role = ["admin", "accountant", "treasurer", "ar_clerk", "ap_clerk"]
```
