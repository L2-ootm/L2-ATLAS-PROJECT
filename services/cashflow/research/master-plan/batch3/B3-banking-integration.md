# B3: Banking Integration Layer — Implementation Plan

> Date: 2026-07-10 · Scope: Banking integrations (Open Finance, Belvo, OFX/CNAB, multi-bank)
> Depends on: Payments (XL), Bank Reconciliation (L), GL/COA (XL)
> Downstream: Cash Flow Forecast, Treasury, Anomaly Detection, Dashboard

---

## 1. Open Finance Brasil

### 1.1 What It Is

Open Finance Brasil (OFB) is the Brazilian open banking framework mandated by BACEN (Banco Central do Brasil). It allows fintechs and licensed institutions to access banking data (accounts, balances, transactions, credit products, investments) via standardized APIs — **with explicit user consent**.

Phase 4 (credit data sharing) went live January 2024. Phase 5 (insurance/pensions) is rolling out 2025-2026. L2 Cashflow targets **Phase 1-3 data** (accounts, balances, transactions) since those are the most useful for cashflow management.

### 1.2 API Phases

| Phase | Data | Status | L2 Relevance |
|-------|------|--------|--------------|
| **Phase 1** | Accounts, balances, transaction history | Live | Core — account aggregation |
| **Phase 2** | Credit cards, loans, financing | Live | Useful for debt visibility |
| **Phase 3** | Investments, insurance | Live | Nice-to-have for treasury |
| **Phase 4** | Credit data sharing | Live | Skip for now |
| **Phase 5** | Insurance/pensions | Rolling out | Skip for now |

### 1.3 Consent Flow (Critical Path)

```
User initiates connection
       │
       ▼
L2 Cashflow ──► BACEN Directory ──► Consenting Institution (bank)
       │              │                      │
       │              │   redirect URI        │
       │              └──────────────────────┘
       │
       ▼
User authenticates with bank (bank's own login flow)
       │
       ▼
User reviews consent scopes:
  - Listar contas (account listing)
  - Saldos (balances)
  - Extratos (transactions)
  - Dados de produto (product data)
       │
       ▼
User approves consent
       │
       ▼
Bank redirects to L2 Cashflow callback with authorization code
       │
       ▼
L2 exchanges authorization code for access token
       │
       ▼
L2 can now call bank APIs using access token
       │
       ▼
Consent expires after configured period (max 12 months)
User can revoke at any time via BACEN portal
```

### 1.4 API Specification

The OFB API is RESTful, OAuth 2.0 + mTLS (mutual TLS). Endpoints vary by participant but follow FEBRABAN standards:

```
Base URL: https://api.{participant}.com.br/open-banking/{product}/v1

# Account listing
GET /accounts
GET /accounts/{accountId}

# Balances
GET /accounts/{accountId}/balances

# Transactions
GET /accounts/{accountId}/transactions
  ?from=2026-01-01
  &to=2026-07-10
  &pagination=50

# Pagination
GET /accounts/{accountId}/transactions?cursor={next_cursor}
```

### 1.5 Integration Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  L2 Cashflow     │────►│  Open Finance    │────►│  Bank APIs      │
│  (Banking Module)│     │  Gateway (proxy) │     │  (Banco do      │
│                  │     │                  │     │   Brasil, BB,   │
│  - Consent mgr   │     │  - OAuth + mTLS  │     │   Itaú, etc.)   │
│  - Token refresh │     │  - Rate limiting │     │                 │
│  - Data normaliz.│     │  - Caching       │     └─────────────────┘
└──────────────────┘     └──────────────────┘
        │
        ▼
  ┌──────────────┐
  │  PostgreSQL   │
  │  - consents   │
  │  - accounts   │
  │  - balances   │
  │  - transactions│
  └──────────────┘
```

### 1.6 Data Model (Open Finance specific)

```sql
-- Open Finance consent tracking
CREATE TABLE of_consents (
    consent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    consent_status TEXT NOT NULL DEFAULT 'pending',
        -- 'pending' | 'authorised' | 'rejected' | 'revoked' | 'expired'
    consent_type TEXT NOT NULL,             -- 'account' | 'balance' | 'transaction'
    bank_participant_id TEXT NOT NULL,      -- OFB participant identifier
    authorization_code TEXT,
    access_token TEXT,                      -- encrypted
    token_expires_at TIMESTAMPTZ,
    consent_expires_at TIMESTAMPTZ,
    refresh_token TEXT,                     -- encrypted
    scopes TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_of_consents_status ON of_consents (tenant_id, consent_status);
CREATE INDEX idx_of_consents_expires ON of_consents (token_expires_at) WHERE consent_status = 'authorised';

-- Open Finance accounts (auto-discovered via consent)
CREATE TABLE of_accounts (
    of_account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consent_id UUID NOT NULL REFERENCES of_consents(consent_id),
    tenant_id UUID NOT NULL,
    bank_account_id UUID REFERENCES bank_accounts(account_id),  -- manual link
    participant_id TEXT NOT NULL,          -- bank's OFB identifier
    account_id_external TEXT NOT NULL,     -- bank's account ID
    account_type TEXT,                     -- 'CONTA_DEPOSITO_VINCULADA', 'CONTA_DEPOSITO_A_VISTA', etc.
    account_subtype TEXT,
    branch_code TEXT,
    account_number TEXT,
    check_digit TEXT,
    currency TEXT DEFAULT 'BRL',
    status TEXT DEFAULT 'active',
    last_synced_at TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Open Finance balances (latest snapshot per account)
CREATE TABLE of_balances (
    balance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    of_account_id UUID NOT NULL REFERENCES of_accounts(of_account_id),
    tenant_id UUID NOT NULL,
    balance_type TEXT NOT NULL,             -- 'AVAILABLE' | 'BLOCKED' | 'FLOAT' | 'AUTO'
    amount NUMERIC(18,6) NOT NULL,
    currency TEXT DEFAULT 'BRL',
    synced_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_of_balances_account ON of_balances (of_account_id, balance_type);

-- Open Finance transactions
CREATE TABLE of_transactions (
    of_transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    of_account_id UUID NOT NULL REFERENCES of_accounts(of_account_id),
    tenant_id UUID NOT NULL,
    bank_transaction_id UUID REFERENCES bank_transactions(transaction_id),  -- link to reconciled
    transaction_id_external TEXT NOT NULL,  -- bank's transaction ID (unique per bank)
    transaction_type TEXT,                  -- 'CREDIT' | 'DEBIT'
    transaction_date DATE NOT NULL,
    value_date DATE,
    amount NUMERIC(18,6) NOT NULL,         -- positive = credit, negative = debit
    description TEXT,
    description_normalized TEXT,
    balance_after NUMERIC(18,6),
    details JSONB,                          -- bank-specific payload
    synced_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (of_account_id, transaction_id_external)
);

CREATE INDEX idx_of_tx_account_date ON of_transactions (of_account_id, transaction_date);
CREATE INDEX idx_of_tx_unmatched ON of_transactions (tenant_id) WHERE bank_transaction_id IS NULL;
```

### 1.7 Implementation Notes

- **mTLS**: Each participating institution requires client certificates. Register with BACEN's directory to get credentials.
- **Rate limits**: Vary by institution. Typically 10-50 requests/minute. Cache responses aggressively.
- **Token refresh**: Access tokens expire in ~30 minutes. Use refresh tokens (available for consents > 30 days).
- **Consent lifecycle**: Monitor expiry dates. Prompt user to re-consent before expiry (30 days notice).
- **Fallback**: Not all banks support OFB yet. For those, fall back to Belvo or manual OFX import.

---

## 2. Belvo Integration

### 2.1 What It Is

Belvo is a Latin American open finance API that aggregates banking data across 100+ institutions (Brazil, Mexico, Colombia). It abstracts away individual bank API differences and provides a unified interface. For L2 Cashflow, Belvo is the **primary aggregation backend** for banks that don't offer direct OFB APIs or when OFB is too complex.

### 2.2 Why Belvo Over Direct OFB

| Factor | Direct OFB | Belvo |
|--------|-----------|-------|
| Bank coverage | ~250 banks (growing) | 100+ institutions per country |
| Auth complexity | mTLS + OAuth per bank | Single API key |
| Consent management | Self-managed | Belvo manages consent flows |
| Data normalization | Manual per bank | Automatic |
| Transaction enrichment | No | Belvo enriches merchant data |
| Cost | Free (regulatory) | Per-request pricing |
| Latency | Direct | +50-200ms (Belvo proxy) |

**Decision**: Belvo for MVP. OFB direct for Phase 2 when volume justifies it.

### 2.3 Belvo API Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  L2 Cashflow │────►│  Belvo API   │────►│  Bank APIs   │
│              │     │  (REST)      │     │  (Brazilian  │
│  - Connect   │     │              │     │   banks)     │
│  - Sync      │     │  - Auth      │     │              │
│  - Webhooks  │     │  - Normalize │     └──────────────┘
└──────────────┘     └──────────────┘
```

### 2.4 Belvo Endpoints

```typescript
// Belvo API reference (REST, JSON)
const BELVO_BASE = 'https://api.belvo.com';

// 1. Create Link (connect a bank account)
// POST /links
{
  institution: 'bradesco',        // institution slug
  username: 'user_bank_login',
  password: 'user_bank_password', // or use OAuth redirect
  credentials_type: 'personal',   // 'personal' | 'business'
}

// 2. Get Accounts
// GET /accounts?link={link_id}
// Returns: accounts, balances, routing info

// 3. Get Balances
// GET /balances?link={link_id}&account={account_id}

// 4. Get Transactions
// GET /transactions?link={link_id}&account={account_id}&date_from=2026-01-01&date_to=2026-07-10

// 5. Webhook (for real-time updates)
// POST {your_webhook_url}
// Events: 'link.CREATED', 'link.UPDATED', 'link.EXPIRED'
```

### 2.5 Belvo Data Model

```sql
-- Belvo connection links
CREATE TABLE belvo_links (
    link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    belvo_link_id TEXT NOT NULL UNIQUE,       -- Belvo's link identifier
    institution_slug TEXT NOT NULL,            -- 'bradesco', 'itau', 'bb', etc.
    institution_name TEXT,
    status TEXT DEFAULT 'active',             -- 'active' | 'expired' | 'error' | 'pending'
    credentials_encrypted JSONB,              -- encrypted bank credentials
    last_sync_at TIMESTAMPTZ,
    next_refresh_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Belvo accounts (auto-discovered)
CREATE TABLE belvo_accounts (
    belvo_account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    link_id UUID NOT NULL REFERENCES belvo_links(link_id),
    tenant_id UUID NOT NULL,
    bank_account_id UUID REFERENCES bank_accounts(account_id),  -- manual link
    belvo_account_id_external TEXT NOT NULL,
    account_type TEXT,                         -- 'CHECKING' | 'SAVINGS' | 'INVESTMENT'
    account_number TEXT,
    agency TEXT,
    currency TEXT DEFAULT 'BRL',
    balance_available NUMERIC(18,6),
    balance_blocked NUMERIC(18,6),
    balance_float NUMERIC(18,6),
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Belvo transactions
CREATE TABLE belvo_transactions (
    belvo_transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    belvo_account_id UUID NOT NULL REFERENCES belvo_accounts(belvo_account_id),
    tenant_id UUID NOT NULL,
    bank_transaction_id UUID REFERENCES bank_transactions(transaction_id),
    belvo_tx_id_external TEXT NOT NULL,
    transaction_date DATE NOT NULL,
    amount NUMERIC(18,6) NOT NULL,
    description TEXT,
    description_normalized TEXT,
    category TEXT,                             -- Belvo's enriched category
    merchant_name TEXT,                        -- enriched merchant
    type TEXT,                                 -- 'INFLOW' | 'OUTFLOW'
    raw_data JSONB,                           -- full Belvo response
    synced_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (belvo_account_id, belvo_tx_id_external)
);

CREATE INDEX idx_belvo_tx_account_date ON belvo_transactions (belvo_account_id, transaction_date);
```

### 2.6 Belvo Webhook Handler

```typescript
// app/api/webhooks/belvo/route.ts

export async function POST(req: Request) {
  const payload = await req.json();

  // Verify Belvo webhook signature (X-Webhook-Signature header)
  const signature = req.headers.get('x-webhook-signature');
  if (!verifyBelvoSignature(payload, signature)) {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 401 });
  }

  switch (payload.event) {
    case 'link.CREATED':
      // Link was created successfully — trigger initial sync
      await syncBelvoLink(payload.data.link_id);
      break;

    case 'link.UPDATED':
      // Link updated (new data available) — trigger incremental sync
      await syncBelvoTransactions(payload.data.link_id);
      break;

    case 'link.EXPIRED':
      // Link expired — notify user to re-authenticate
      await markBelvoLinkExpired(payload.data.link_id);
      await notifyUserLinkExpired(payload.data.link_id);
      break;
  }

  return NextResponse.json({ received: true });
}
```

### 2.7 Implementation Notes

- **Credentials encryption**: Bank credentials must be encrypted at rest (AES-256-GCM). Use Supabase vault or application-level encryption.
- **Sync strategy**: Initial sync pulls last 90 days. Subsequent syncs pull delta (last sync date forward).
- **Rate limits**: Belvo free tier: 100 API calls/month. Paid tier: unlimited.
- **Error handling**: Bank may require 2FA mid-sync. Belvo handles this via webhook. Surface to user.

---

## 3. OFX Import

### 3.1 What It Is

OFX (Open Financial Exchange) is the standard format for bank statement exports in Brazil and globally. Users download an `.ofx` file from their bank's internet banking and upload it to L2 Cashflow.

### 3.2 OFX File Structure

```xml
<?OFX OFXHEADER="200" VERSION="200" SECURITY="NONE" ENCODING="USASCII" CHARSET="1252" COMPRESSION="NONE">
<OFX>
  <SIGNONMSGSRSV1>
    <SONRS>
      <STATUS><CODE>0<SEVERITY>INFO</STATUS>
      <DTSERVER>20260710120000[-3:BRT]
      <LANGUAGE>POR
    </SONRS>
  </SIGNONMSGSRSV1>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <CURDEF>BRL
        <BANKACCTFROM>
          <BANKID>237          <!-- Bradesco -->
          <ACCTID>12345-6
          <ACCTTYPE>CHECKING
        </BANKACCTFROM>
        <BANKTRANLIST>
          <DTPOSTED>20260701120000[-3:BRT]
          <TRNAMT>-1500.00
          <FITID>202607010001
          <NAME>PAGAMENTO FORNECEDOR
          <MEMO>PIX PARA CNPJ 12.345.678/0001-99
          </TRNAMT>
          </BANKTRANLIST>
        <LEDGERBAL>
          <BALAMT>25000.00
          <DTASOF>20260710120000[-3:BRT]
        </LEDGERBAL>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
```

### 3.3 Parser Implementation

```typescript
// lib/banking/parsers/ofx.ts

import { parse as ofxParse } from 'ofx-parser';  // npm: ofx-parser

export interface OfxTransaction {
  fitId: string;              // Financial Institution Transaction ID
  name: string;               // transaction name/description
  memo?: string;              // additional memo
  amount: number;             // negative = debit, positive = credit
  date: Date;                 // transaction date (posted)
  type: 'CREDIT' | 'DEBIT' | 'OTHER';
  checkNumber?: string;
}

export interface OfxAccount {
  bankId: string;             // BACEN bank code
  accountId: string;          // account number
  accountType: string;        // CHECKING, SAVINGS, etc.
  currency: string;           // BRL
  balance: number;            // ledger balance
  balanceDate: Date;
  transactions: OfxTransaction[];
}

export async function parseOfxFile(fileContent: string): Promise<OfxAccount> {
  const result = await ofxParse(fileContent);

  const stmt = result.bankStatement;

  return {
    bankId: stmt.account.bankId,
    accountId: stmt.account.accountId,
    accountType: stmt.account.accountType,
    currency: stmt.header?.currency || 'BRL',
    balance: stmt.ledgerBalance.amount,
    balanceDate: new Date(stmt.ledgerBalance.asOfDate),
    transactions: stmt.transactions.map(tx => ({
      fitId: tx.id,
      name: (tx.name || tx.memo || '').trim(),
      memo: tx.memo,
      amount: tx.amount,
      date: new Date(tx.postedAt || tx.availableAt),
      type: tx.amount > 0 ? 'CREDIT' : 'DEBIT',
      checkNumber: tx.checkNumber,
    })),
  };
}

export function normalizeOfxDescription(desc: string): string {
  return desc
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')  // remove accents
    .toUpperCase()
    .replace(/[^\w\s]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}
```

### 3.4 Bank-Specific OFX Variations

| Bank | .ofx Extension | Encoding | Special Fields |
|------|---------------|----------|----------------|
| Bradesco | `.ofx` | ISO-8859-1 | Contains `CNPJPART` (CNPJ of beneficiary) |
| Itaú | `.ofx` | UTF-8 | Contains `CNPJ` in `<NAME>` field |
| Banco do Brasil | `.OFX` | UTF-8 | Contains `HISTORICO` (history code) |
| Santander | `.ofx` | ISO-8859-1 | Contains `COMPL` (complement field) |
| Caixa | `.ofx` | UTF-8 | Standard OFX, minimal extra fields |

### 3.5 Import Flow

```
User uploads .ofx file
       │
       ▼
Parse OFX (ofx-parser)
       │
       ▼
Match account (bank_id + account_id) to bank_accounts table
  └─► If no match: prompt user to link to existing account or create new
       │
       ▼
Deduplicate (by fitId — already imported?)
       │
       ▼
Insert into bank_transactions
       │
       ▼
Run auto-matching against open payments/invoices
       │
       ▼
Update bank_accounts.current_balance from OFX ledger balance
```

---

## 4. CNAB 240 Import

### 4.1 What It Is

CNAB (Comunicações Normatizadas Bancárias) is the Brazilian interbank communication standard. CNAB 240 is the modern format used by most banks for electronic file exchange. Each line is exactly 240 characters wide.

### 4.2 Record Structure

```
CNAB 240 Record Layout:
┌─────────────────────────────────────────────────────────┐
│ Position │ Length │ Description                          │
├──────────┼────────┼─────────────────────────────────────┤
│   1-  3  │   3    │ Bank Code (BACEN)                   │
│   4-  7  │   4    │ Service Code                        │
│   8- 10  │   3    │ Fill (complementary)                │
│  11- 13  │   3    │ Record Type (0-9)                   │
│  14- 16  │   3    │ Movement Type                       │
│  ...     │  ...   │ ... (varies by segment)             │
└─────────────────────────────────────────────────────────┘

Record Types:
  0 = File Header
  1 = Initial Balance (segment A)
  2 = Segment B (payment detail - boleto)
  3 = Segment J (payment detail - Pix/transfer)
  4 = Segment K (payment detail - supplement)
  5 = File Trailer
  9 = Record Trailer
```

### 4.3 File Structure

```
Line 1:  Record Type 0 — File Header
  - Bank code, company name, CNPJ, file generation date
Line 2:  Record Type 1 — Header of Lot (batch header)
  - Service type, lot purpose (payment = 20, collection = 30)
Lines 3+: Record Types 3+ — Transaction Details (per payment)
  - Segment A: payer/payee info, amounts
  - Segment B: boleto-specific (due date, barcode)
  - Segment J: Pix/transfer-specific (key, bank, account)
  - Segment K: complementary info (sacador-avalista)
Last Line: Record Type 9 — File Trailer
  - Total records, total amounts, hash totals
```

### 4.4 Parser Implementation

```typescript
// lib/banking/parsers/cnab240.ts

const CNAB240_LINE_LENGTH = 240;

interface Cnab240FileHeader {
  bankCode: string;
  companyCode: string;
  companyName: string;
  companyCnpj: string;
  generationDate: Date;
  creditDate: Date;
  recordCount: number;
}

interface Cnab240Transaction {
  segment: 'A' | 'B' | 'J' | 'K';
  movementType: string;          // '00'=inclusion, '09'=exclusion, '31'=complement
  branchCode: string;
  accountNumber: string;
  accountComplement: string;
  amount: number;
  effectiveDate: Date;
  description: string;
  documentNumber: string;

  // Segment B specific (boleto)
  dueDate?: Date;
  barcode?: string;
  digitableLine?: string;
  nossoNumero?: string;

  // Segment J specific (Pix/transfer)
  pixKey?: string;
  pixKeyType?: string;
  destBankCode?: string;
  destBranchCode?: string;
  destAccountNumber?: string;
  destCpfCnpj?: string;
  destName?: string;
}

export function parseCnab240File(content: string): {
  header: Cnab240FileHeader;
  transactions: Cnab240Transaction[];
} {
  const lines = content.split(/\r?\n/).filter(l => l.trim().length > 0);
  const header = parseCnab240Header(lines[0]);
  const transactions: Cnab240Transaction[] = [];

  for (let i = 1; i < lines.length - 1; i++) {
    const line = lines[i];
    if (line.length < CNAB240_LINE_LENGTH) continue;

    const recordType = line.substring(10, 13).trim();

    if (recordType === '3') {
      const segment = line.substring(13, 14).trim();
      transactions.push(parseCnab240Segment(line, segment as 'A' | 'B' | 'J' | 'K'));
    }
  }

  return { header, transactions };
}

function parseCnab240Header(line: string): Cnab240FileHeader {
  return {
    bankCode: line.substring(0, 3).trim(),
    companyCode: line.substring(3, 7).trim(),
    companyName: line.substring(32, 52).trim(),
    companyCnpj: line.substring(18, 32).trim(),
    generationDate: parseCnabDate(line.substring(143, 151)),
    creditDate: parseCnabDate(line.substring(151, 159)),
    recordCount: parseInt(line.substring(228, 234)) || 0,
  };
}

function parseCnab240Segment(line: string, segment: 'A' | 'B' | 'J' | 'K'): Cnab240Transaction {
  const tx: Cnab240Transaction = {
    segment,
    movementType: line.substring(14, 17).trim(),
    branchCode: line.substring(17, 21).trim(),
    accountNumber: line.substring(21, 29).trim(),
    accountComplement: line.substring(29, 34).trim(),
    amount: parseCnabAmount(line.substring(19, 33)),
    effectiveDate: parseCnabDate(line.substring(92, 100)),
    description: line.substring(100, 140).trim(),
    documentNumber: line.substring(34, 44).trim(),
  };

  if (segment === 'B') {
    tx.dueDate = parseCnabDate(line.substring(68, 76));
    tx.barcode = line.substring(76, 120).trim();
    tx.nossoNumero = line.substring(44, 64).trim();
  }

  if (segment === 'J') {
    tx.pixKey = line.substring(100, 140).trim();
    tx.pixKeyType = line.substring(44, 46).trim();
    tx.destBankCode = line.substring(16, 19).trim();
    tx.destBranchCode = line.substring(21, 25).trim();
    tx.destAccountNumber = line.substring(25, 37).trim();
    tx.destCpfCnpj = line.substring(5, 18).trim();
    tx.destName = line.substring(76, 106).trim();
  }

  return tx;
}

function parseCnabDate(dateStr: string): Date {
  const day = parseInt(dateStr.substring(0, 2));
  const month = parseInt(dateStr.substring(2, 4));
  const year = parseInt(dateStr.substring(4, 8));
  return new Date(year, month - 1, day);
}

function parseCnabAmount(amountStr: string): number {
  const cleaned = amountStr.replace(/\s/g, '').replace(/,/g, '');
  return parseInt(cleaned) / 100;
}
```

### 4.5 Bank-Specific Variations

| Bank | CNAB 240 Provider | Segment Variations | Notes |
|------|-------------------|-------------------|-------|
| Bradesco | Standard FEBRABAN | Standard | Segment J for Pix |
| Itaú | Standard FEBRABAN | Standard | Segment J uses different field positions |
| Banco do Brasil | Custom | Segment B/C/D (BB-specific) | BB uses its own segment naming |
| Santander | Standard FEBRABAN | Standard | Standard layout |
| Caixa | Custom | Segment B (CEF-specific) | CEF barcode has extra digits |

---

## 5. CNAB 400 Import

### 5.1 What It Is

CNAB 400 is the legacy bank statement format. Each line is exactly 400 characters wide. It was the predecessor to CNAB 240 and is still used by many smaller banks and for certain transaction types (boleto credits, card settlements).

### 5.2 Key Differences from CNAB 240

| Aspect | CNAB 240 | CNAB 400 |
|--------|----------|----------|
| Line width | 240 bytes | 400 bytes |
| Record types | 0-9 + segments A-K | 0-9 (simpler) |
| Header structure | File header + lot header | File header only |
| Transaction detail | Segmented (A/B/J/K) | Single-line per transaction |
| Boles support | Full (segment B) | Limited (positions vary) |
| Pix support | Yes (segment J) | No (Pix era format) |
| Modern use | Primary format | Legacy / boleto credits |

### 5.3 Parser Implementation

```typescript
// lib/banking/parsers/cnab400.ts

const CNAB400_LINE_LENGTH = 400;

interface Cnab400FileHeader {
  bankCode: string;
  companyName: string;
  companyCnpj: string;
  generationDate: Date;
  recordCount: number;
}

interface Cnab400Transaction {
  movementType: string;          // '002'=entry, '009'=deletion, '015'=return
  branchCode: string;
  accountNumber: string;
  accountComplement: string;
  amount: number;
  effectiveDate: Date;
  description: string;
  documentNumber: string;
  ispb: string;
  bankOrigin: string;

  // Boleto-specific
  dueDate?: Date;
  ourNumber?: string;
  carteira?: string;
  digitableLine?: string;
  sacadoName?: string;
  sacadoCpfCnpj?: string;
}

export function parseCnab400File(content: string): {
  header: Cnab400FileHeader;
  transactions: Cnab400Transaction[];
} {
  const lines = content.split(/\r?\n/).filter(l => l.trim().length > 0);
  const header = parseCnab400Header(lines[0]);
  const transactions: Cnab400Transaction[] = [];

  for (let i = 1; i < lines.length - 1; i++) {
    const line = lines[i];
    if (line.length < CNAB400_LINE_LENGTH) continue;

    const recordType = line.substring(0, 1).trim();

    if (recordType === '1') {
      transactions.push(parseCnab400Transaction(line));
    }
  }

  return { header, transactions };
}

function parseCnab400Header(line: string): Cnab400FileHeader {
  return {
    bankCode: line.substring(0, 3).trim(),
    companyName: line.substring(46, 76).trim(),
    companyCnpj: line.substring(18, 32).trim(),
    generationDate: parseCnabDate(line.substring(95, 103)),
    recordCount: parseInt(line.substring(392, 400)) || 0,
  };
}

function parseCnab400Transaction(line: string): Cnab400Transaction {
  return {
    movementType: line.substring(8, 11).trim(),
    branchCode: line.substring(17, 21).trim(),
    accountNumber: line.substring(21, 29).trim(),
    accountComplement: line.substring(29, 34).trim(),
    amount: parseCnabAmount(line.substring(152, 167)),
    effectiveDate: parseCnabDate(line.substring(114, 122)),
    description: line.substring(240, 270).trim(),
    documentNumber: line.substring(37, 47).trim(),
    ispb: line.substring(11, 17).trim(),
    bankOrigin: line.substring(0, 3).trim(),
    dueDate: parseCnabDate(line.substring(110, 118)),
    ourNumber: line.substring(47, 57).trim(),
    carteira: line.substring(82, 85).trim(),
    sacadoName: line.substring(270, 300).trim(),
    sacadoCpfCnpj: line.substring(300, 314).trim(),
  };
}
```

### 5.4 Bank-Specific CNAB 400 Variations

| Bank | CNAB 400 Layout | Field Positions | Notes |
|------|----------------|-----------------|-------|
| Bradesco | Standard + custom | Positions 100-139: complement | Bradesco uses own complement format |
| Itaú | Standard + custom | Positions 100-149: own fields | Itaú has proprietary additions |
| Santander | Standard | Standard FEBRABAN | Closest to standard |
| Caixa | Custom | Positions 115-149: CEF-specific | CEF has own layout |

---

## 6. Bank Account Management

### 6.1 Multi-Bank Connectivity Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 L2 Cashflow Banking Layer                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  Manual   │  │  OFX     │  │  Belvo   │  │  OFB   │ │
│  │  Import   │  │  Upload  │  │  API     │  │  API   │ │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └───┬────┘ │
│        │             │             │            │       │
│        └─────────────┴─────────────┴────────────┘       │
│                          │                              │
│                    ┌─────▼──────┐                       │
│                    │  Normalizer │                       │
│                    │  (standard │                       │
│                    │   format)  │                       │
│                    └─────┬──────┘                       │
│                          │                              │
│                    ┌─────▼──────┐                       │
│                    │ bank_      │                       │
│                    │ transactions│                       │
│                    └─────┬──────┘                       │
│                          │                              │
│                    ┌─────▼──────┐                       │
│                    │  Matching  │                       │
│                    │  Engine    │                       │
│                    └─────┬──────┘                       │
│                          │                              │
│                    ┌─────▼──────┐                       │
│                    │  GL/Recon  │                       │
│                    └────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

### 6.2 Unified Bank Transaction Model

All import methods (OFX, CNAB 240, CNAB 400, Belvo, OFB) normalize into the same `bank_transactions` table:

```typescript
// lib/banking/normalizer.ts

interface NormalizedBankTransaction {
  bank_account_id: string;
  tenant_id: string;
  transaction_date: Date;
  value_date?: Date;
  description: string;
  description_normalized: string;
  amount: number;              // positive = credit, negative = debit
  balance?: number;
  transaction_type: 'credit' | 'debit' | 'transfer_in' | 'transfer_out';
  document_number?: string;
  source_format: 'ofx' | 'cnab240' | 'cnab400' | 'belvo' | 'ofb';
  source_id: string;           // fitId, belvo_tx_id, etc.
  metadata: JSONB;
}

export function normalizeTransaction(
  raw: OfxTransaction | Cnab240Transaction | Cnab400Transaction | BelvoTransaction | OfbTransaction,
  sourceFormat: string
): NormalizedBankTransaction {
  // All parsers produce a common shape that maps to bank_transactions
  return {
    bank_account_id: raw.bank_account_id,
    tenant_id: raw.tenant_id,
    transaction_date: raw.date,
    value_date: raw.value_date,
    description: raw.description,
    description_normalized: normalizeDescription(raw.description),
    amount: raw.amount,
    balance: raw.balance,
    transaction_type: classifyTransactionType(raw.amount),
    document_number: raw.document_number,
    source_format: sourceFormat,
    source_id: raw.source_id,
    metadata: raw.metadata,
  };
}
```

### 6.3 Balance Aggregation

```typescript
// lib/banking/balance.ts

interface BankBalanceSummary {
  tenant_id: string;
  total_balance: number;          // sum of all bank account balances
  accounts: {
    account_id: string;
    account_name: string;
    bank_code: string;
    bank_name: string;
    balance: number;
    last_synced: Date;
    source: 'manual' | 'ofx' | 'belvo' | 'ofb';
  }[];
  last_updated: Date;
}

export async function getBankBalanceSummary(tenantId: string): Promise<BankBalanceSummary> {
  const accounts = await bankAccountRepo.findByTenant(tenantId);

  return {
    tenant_id: tenantId,
    total_balance: accounts.reduce((sum, a) => sum + a.current_balance, 0),
    accounts: accounts.map(a => ({
      account_id: a.account_id,
      account_name: a.account_name,
      bank_code: a.bank_code,
      bank_name: a.bank_name,
      balance: a.current_balance,
      last_synced: a.last_sync_at,
      source: determineSource(a),
    })),
    last_updated: new Date(),
  };
}
```

---

## 7. Automated Import

### 7.1 Scheduled Import Architecture

```
┌──────────────────────────────────────────────────────┐
│  Inngest Scheduled Function: bank-sync               │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Every 4 hours (configurable per tenant):            │
│                                                      │
│  1. Check active Belvo links                         │
│     └─► Call Belvo API for each link                 │
│         └─► Get new transactions (delta)             │
│                                                      │
│  2. Check active OFB consents                        │
│     └─► Call OFB API for each consent                │
│         └─► Get new transactions (delta)             │
│                                                      │
│  3. Normalize all transactions                       │
│     └─► Insert into bank_transactions                │
│                                                      │
│  4. Run auto-matching                                │
│     └─► Match against open payments/invoices         │
│                                                      │
│  5. Emit events                                      │
│     └─► bank.transaction.imported                    │
│     └─► bank.balance.updated                         │
│                                                      │
│  Error handling:                                     │
│  - API failure: retry 3x with exponential backoff    │
│  - Auth failure: mark link/expired, notify user      │
│  - Partial failure: import what succeeded, retry rest│
└──────────────────────────────────────────────────────┘
```

### 7.2 Duplicate Detection

```typescript
// lib/banking/dedup.ts

export async function deduplicateTransactions(
  transactions: NormalizedBankTransaction[],
  tenantId: string
): Promise<{ unique: NormalizedBankTransaction[]; duplicates: number }> {
  const unique: NormalizedBankTransaction[] = [];
  let duplicates = 0;

  for (const tx of transactions) {
    const exists = await db.query(
      `SELECT 1 FROM bank_transactions
       WHERE tenant_id = $1
         AND bank_account_id = $2
         AND source_id = $3
         AND source_format = $4`,
      [tenantId, tx.bank_account_id, tx.source_id, tx.source_format]
    );

    if (exists.rowCount === 0) {
      unique.push(tx);
    } else {
      duplicates++;
    }
  }

  return { unique, duplicates };
}
```

### 7.3 Error Handling

```typescript
// lib/banking/error-handler.ts

interface ImportError {
  bank_account_id: string;
  source_format: string;
  error_type: 'parse_error' | 'auth_expired' | 'api_error' | 'duplicate' | 'unknown';
  error_message: string;
  raw_line?: number;
  retry_count: number;
  next_retry_at?: Date;
}

export async function handleImportError(error: ImportError): Promise<void> {
  // Log error
  await db.insert('import_errors', error);

  if (error.error_type === 'auth_expired') {
    // Notify user to re-authenticate
    await notifyUserBankAuthExpired(error.bank_account_id);
    // Mark link as expired
    await updateBankLinkStatus(error.bank_account_id, 'expired');
  }

  if (error.error_type === 'parse_error') {
    // Log for investigation, don't retry
    console.error(`Parse error on line ${error.raw_line}: ${error.error_message}`);
  }

  if (error.error_type === 'api_error' && error.retry_count < 3) {
    // Schedule retry with exponential backoff
    const delay = Math.pow(2, error.retry_count) * 60000; // 1min, 2min, 4min
    await scheduleRetry(error.bank_account_id, delay);
  }
}
```

---

## 8. Bank Reconciliation Integration

### 8.1 How Imported Data Feeds the Matching Engine

```
Bank Transaction Import
         │
         ▼
   Normalizer ──► bank_transactions (match_status = 'unmatched')
         │
         ▼
   Matching Engine (runs on import or on-demand)
         │
         ├── Phase 1: Exact Match (amount + date)
         │     └─► confidence 1.0
         │
         ├── Phase 2: Fuzzy Match (amount ± tolerance, date ± days)
         │     └─► confidence 0.7-0.99
         │
         └── Phase 3: Manual Queue
               └─► User reviews unmatched items
         │
         ▼
   Reconciliation Run
         │
         ├── Matches ──► reconciliation_matches (matched)
         ├── Unmatched bank ──► UI review queue
         └── Unmatched payments ──► UI review queue
         │
         ▼
   GL Update
         │
         ├── bank_accounts.current_balance = last statement balance
         ├── Journal entries posted for matched items
         └── Reconciliation report generated
```

### 8.2 Auto-Matching on Import

```typescript
// lib/banking/auto-match.ts

export async function autoMatchOnImport(
  importId: string,
  tenantId: string,
  bankAccountId: string
): Promise<AutoMatchResult> {
  const unmatched = await bankTransactionRepo.findUnmatched(importId);
  const openPayments = await paymentRepo.findUnmatched(bankAccountId, {
    startDate: subDays(new Date(), 90),
    endDate: addDays(new Date(), 7),
  });

  let exactMatches = 0;
  let fuzzyMatches = 0;
  let unmatchedCount = 0;

  for (const tx of unmatched) {
    // Phase 1: Exact
    const exact = findExactMatch(tx, openPayments);
    if (exact) {
      await recordMatch(tx.transaction_id, exact);
      exactMatches++;
      continue;
    }

    // Phase 2: Fuzzy
    const fuzzy = findFuzzyMatch(tx, openPayments, {
      amount_tolerance: 0.01,
      date_tolerance_days: 3,
      min_confidence: 0.70,
    });
    if (fuzzy) {
      await recordMatch(tx.transaction_id, fuzzy);
      fuzzyMatches++;
      continue;
    }

    unmatchedCount++;
  }

  return { exactMatches, fuzzyMatches, unmatchedCount };
}
```

---

## 9. API Endpoints

### 9.1 Banking Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/api/v1/banking/accounts` | List all bank accounts | `banking:read` |
| `POST` | `/api/v1/banking/accounts` | Create bank account | `banking:write` |
| `GET` | `/api/v1/banking/accounts/:id` | Get account details | `banking:read` |
| `PUT` | `/api/v1/banking/accounts/:id` | Update account | `banking:write` |
| `GET` | `/api/v1/banking/accounts/:id/balance` | Get current balance | `banking:read` |
| `GET` | `/api/v1/banking/summary` | Balance summary (all accounts) | `banking:read` |

### 9.2 Import Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/banking/accounts/:id/import` | Upload OFX/CNAB file | `banking:write` |
| `POST` | `/api/v1/banking/accounts/:id/import/schedule` | Schedule auto-import | `banking:write` |
| `GET` | `/api/v1/banking/accounts/:id/import-history` | Import history | `banking:read` |
| `GET` | `/api/v1/banking/accounts/:id/transactions` | List transactions | `banking:read` |

### 9.3 Open Finance / Belvo Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/banking/connect/open-finance` | Initiate OFB consent | `banking:write` |
| `POST` | `/api/v1/banking/connect/belvo` | Connect via Belvo | `banking:write` |
| `GET` | `/api/v1/banking/connections` | List active connections | `banking:read` |
| `DELETE` | `/api/v1/banking/connections/:id` | Disconnect / revoke consent | `banking:write` |
| `POST` | `/api/v1/banking/connections/:id/sync` | Force sync now | `banking:write` |

### 9.4 Reconciliation Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/banking/reconciliation/run` | Run auto-reconciliation | `reconciliation:write` |
| `GET` | `/api/v1/banking/reconciliation/runs` | List reconciliation runs | `reconciliation:read` |
| `GET` | `/api/v1/banking/reconciliation/runs/:id` | Get run details | `reconciliation:read` |
| `POST` | `/api/v1/banking/reconciliation/matches/:id/confirm` | Confirm manual match | `reconciliation:write` |

### 9.5 Webhook Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/webhooks/belvo` | Belvo webhook receiver | Signature verification |
| `POST` | `/api/v1/webhooks/ofb` | OFB webhook receiver | mTLS verification |

---

## 10. Security

### 10.1 Credential Storage

```typescript
// lib/banking/security.ts

import { encrypt, decrypt } from '@/lib/crypto'; // AES-256-GCM

// All bank credentials encrypted at rest
// Key hierarchy:
//   - Application key (in env, rotated quarterly)
//   - Per-tenant encryption key (derived via HKDF)
//   - Per-credential encryption (AES-256-GCM with random IV)

interface EncryptedCredential {
  iv: string;          // base64-encoded IV
  ciphertext: string;  // base64-encoded ciphertext
  tag: string;         // base64-encoded auth tag
  algorithm: 'aes-256-gcm';
  key_version: number;
}

export async function encryptCredential(
  plaintext: string,
  tenantId: string
): Promise<EncryptedCredential> {
  const tenantKey = await deriveTenantKey(tenantId);
  return encrypt(plaintext, tenantKey);
}

export async function decryptCredential(
  encrypted: EncryptedCredential,
  tenantId: string
): Promise<string> {
  const tenantKey = await deriveTenantKey(tenantId);
  return decrypt(encrypted, tenantKey);
}
```

### 10.2 API Key Management

```typescript
// Belvo API keys stored in environment
BELVO_SECRET_KEY_ID=xxx
BELVO_SECRET_KEY_PASSWORD=xxx
BELVO_ENV=sandbox | production

// Open Finance mTLS certificates stored in Supabase vault or
// encrypted in database (for multi-tenant: each tenant has own certs)
```

### 10.3 Data Encryption Rules

1. **Bank credentials** (login/password): AES-256-GCM, encrypted at rest, never logged
2. **API keys** (Belvo, OFB): Environment variables, never in DB
3. **mTLS certificates**: Supabase vault or encrypted JSONB column
4. **Tokens** (access/refresh): AES-256-GCM, encrypted at rest
5. **Transaction data**: Standard DB encryption (Supabase transparent encryption)
6. **PII** (CPF, CNPJ): Column-level encryption for sensitive fields

### 10.4 Audit Logging

```sql
CREATE TABLE banking_audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID,
    action TEXT NOT NULL,            -- 'connect' | 'disconnect' | 'import' | 'sync' | 'reconcile'
    resource_type TEXT NOT NULL,     -- 'bank_account' | 'connection' | 'transaction'
    resource_id UUID NOT NULL,
    details JSONB,                   -- sanitized (no credentials)
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_banking_audit_tenant ON banking_audit_log (tenant_id, created_at DESC);
```

---

## 11. Testing

### 11.1 Test Strategy

| Layer | Tool | What to Test |
|-------|------|-------------|
| OFX parser | Vitest | File parsing, edge cases, bank variations |
| CNAB 240 parser | Vitest | Fixed-width parsing, all record types |
| CNAB 400 parser | Vitest | Fixed-width parsing, legacy format |
| Belvo integration | Vitest + mock | API calls, webhook handling, error paths |
| OFB integration | Vitest + mock | OAuth flow, consent lifecycle, token refresh |
| Auto-matching | Vitest | Exact, fuzzy, edge cases (overlapping amounts) |
| Deduplication | Vitest + Supabase test DB | Idempotent imports |
| API endpoints | Playwright | End-to-end import flow |

### 11.2 OFX File Fixtures

```typescript
// __tests__/fixtures/ofx/

// bradesco-checking.ofx — Standard Bradesco checking account
// itau-savings.ofx — Itaú poupança with credit card
// bb-business.ofx — BB PJ with multiple transactions
// santander-foreign.ofx — Santander USD account
// empty-statement.ofx — Valid OFX with zero transactions
// malformed.ofx — Invalid XML structure
// duplicate-transactions.ofx — Same fitId repeated (dedup test)
```

### 11.3 CNAB File Fixtures

```typescript
// __tests__/fixtures/cnab/

// cnab240-bradesco-payment.txt — Bradesco payment file (segments A/B/J)
// cnab240-itau-collection.txt — Itaú collection file
// cnab240-bb-transfer.txt — BB transfer file
// cnab240-minimal.txt — Minimal valid CNAB 240
// cnab400-bradesco-statement.txt — Bradesco statement (legacy)
// cnab400-itau-collection.txt — Itaú collection (legacy)
// cnab400-minimal.txt — Minimal valid CNAB 400
```

### 11.4 Mock Bank Responses

```typescript
// __tests__/mocks/

// belvo-mock.ts — Mock Belvo API responses
//   - link.CREATED, link.UPDATED, link.EXPIRED
//   - accounts list, balances, transactions
//   - Error responses (401, 429, 500)

// ofb-mock.ts — Mock OFB API responses
//   - consent.authorised, consent.revoked
//   - accounts list, balances, transactions
//   - Token refresh flow
```

---

## 12. Effort Estimate

| Integration | Complexity | Estimated Effort | Priority |
|-------------|-----------|-----------------|----------|
| **OFX parser** | Low | 2-3 days | P0 — MVP |
| **CNAB 240 parser** | Medium | 3-5 days | P0 — MVP |
| **CNAB 400 parser** | Medium | 3-4 days | P1 — after MVP |
| **Bank account management** | Low | 2-3 days | P0 — MVP |
| **Belvo integration** | High | 1-2 weeks | P0 — MVP |
| **Open Finance Brasil** | Very High | 2-3 weeks | P1 — after Belvo |
| **Auto-matching engine** | Medium | 3-5 days | P0 — MVP |
| **Duplicate detection** | Low | 1-2 days | P0 — MVP |
| **Scheduled import (Inngest)** | Medium | 2-3 days | P1 — after MVP |
| **Error handling & retry** | Medium | 2-3 days | P1 — after MVP |
| **Security (encryption)** | Medium | 2-3 days | P0 — MVP |
| **Testing (fixtures + mocks)** | Medium | 3-5 days | P0 — MVP |
| **API endpoints** | Medium | 2-3 days | P0 — MVP |

### Total Effort

| Phase | Components | Effort |
|-------|-----------|--------|
| **MVP** | OFX parser, CNAB 240, bank accounts, Belvo, auto-matching, dedup, security, API, tests | 3-4 weeks |
| **Phase 2** | CNAB 400, scheduled imports, error handling, OFB integration | 2-3 weeks |
| **Total** | Full banking integration | 5-7 weeks |

### Recommended Sequence

1. **Week 1-2**: Bank account management + OFX parser + CNAB 240 parser + basic testing
2. **Week 3-4**: Belvo integration + auto-matching + security + API endpoints
3. **Week 5-6**: CNAB 400 + scheduled imports + error handling
4. **Week 7-8**: Open Finance Brasil (if needed)

---

## Appendix A: Dependency Map

```
Banking Integration
├── bank_accounts table (B2-payments-reconciliation)
├── bank_transactions table (B2-payments-reconciliation)
├── payments table (B2-payments-reconciliation)
├── reconciliation engine (B2-payments-reconciliation)
├── GL journal entries (B2-gl-implementation)
├── Chart of accounts (B2-gl-implementation)
├── Event bus (B1-tech-stack: Inngest)
└── Encryption service (new)
```

## Appendix B: Open Finance Brasil Resources

- [BACEN Open Finance Portal](https://openfinance.bcb.gov.br/)
- [FEBRABAN Open Finance API Spec](https://openfinancebrasil.org/)
- [OFB API Specification (Swagger)](https://openfinance.bcb.gov.br/swagger-ui.html)
- [Participant Directory](https://openfinance.bcb.gov.br/participants)

## Appendix C: Belvo Resources

- [Belvo API Docs](https://developer.belvo.com/)
- [Belvo Brazil Institutions](https://developer.belvo.com/docs/institutions-brazil)
- [Belvo Webhooks](https://developer.belvo.com/docs/webhooks)
