# B5 — Onboarding Wizard Implementation Plan

> Date: 2026-07-10
> Scope: L2 Cashflow — 5-step onboarding wizard, import wizard, progress tracking, activation analytics
> Depends on: GL/COA (B2), AP/AR+Invoicing (B2), Tax Engine (B3), Banking Integration (B3), Multi-tenancy (B1)
> Constraint: Target <5 minutes to first invoice. Industry benchmarks: Stripe <3min, Ghost 5-step progress bar = 1000% conversion lift.
> Baseline: Next.js 16 + React 19, repository pattern, 17+ tables

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Step 1 — Industry Selection](#2-step-1--industry-selection)
3. [Step 2 — Tax Regime Selection](#3-step-2--tax-regime-selection)
4. [Step 3 — Invoice Template](#4-step-3--invoice-template)
5. [Step 4 — Bank Connection](#5-step-4--bank-connection)
6. [Step 5 — First Invoice Creation](#6-step-5--first-invoice-creation)
7. [Progress Tracking & Checklist](#7-progress-tracking--checklist)
8. [Import Wizard](#8-import-wizard)
9. [Analytics & Activation Metrics](#9-analytics--activation-metrics)
10. [API Endpoints](#10-api-endpoints)
11. [Data Model](#11-data-model)
12. [Effort Estimates](#12-effort-estimates)
13. [Data Flow Diagram](#13-data-flow-diagram)

---

## 1. Architecture Overview

### 1.1 Design Principles

- **Guided, not mandatory**: Every step except Step 1 (Industry) can be skipped. Unskipped steps unlock features progressively.
- **Stateless per step**: Each step writes to the setup_state table atomically. No partial-wizard corruption.
- **Parallel with import**: The import wizard (Section 8) is an alternative entry point. Users who import data skip the COA generation step but still select tax regime and template.
- **Feature unlocking**: Completing steps gates access to advanced features (e.g., bank connection gates cash flow forecasting, tax regime gates SPED generation).

### 1.2 Setup State Machine

```
┌─────────┐     ┌──────────────┐     ┌──────────────┐
│  START   │────►│ IN_PROGRESS  │────►│  COMPLETED   │
└─────────┘     └──────────────┘     └──────────────┘
                       │
                       ▼
                ┌──────────────┐
                │   PAUSED     │  (user left, returns later)
                └──────────────┘
```

Each step has its own state: `pending → in_progress → completed | skipped`

### 1.3 Component Tree

```
<OnboardingWizard>
  ├── <SetupProgressBar />         -- horizontal 5-step indicator
  ├── <StepContent />              -- renders active step
  │   ├── <IndustrySelection />    -- Step 1
  │   ├── <TaxRegimeSelection />   -- Step 2
  │   ├── <InvoiceTemplate />      -- Step 3
  │   ├── <BankConnection />       -- Step 4
  │   └── <FirstInvoice />         -- Step 5
  ├── <SetupChecklist />           -- sidebar checklist (Zeigarnik effect)
  └── <ImportWizardTrigger />      -- "Already have data? Import instead"
```

---

## 2. Step 1 — Industry Selection

### 2.1 UI Design

**Layout**: 3-column grid of industry cards (responsive → 2-col on tablet, 1-col on mobile).

**Industry cards** (12 pre-built options):

| Industry | Icon | CNAE Range | Accounts Generated | Templates |
|----------|------|------------|-------------------|-----------|
| **Restaurante / Food Service** | utensils | 56.1x-56.2x | 52 | Menu cost tracking, daily revenue |
| **Comercio Varejista (Retail)** | store | 45.x-47.x | 48 | POS integration, inventory COGS |
| **Construcao (Construction)** | hard-hat | 41.x-43.x | 55 | Project-based billing, progress billing |
| **Servicos Profissionais (Professional Services)** | briefcase | 69.x-74.x | 42 | Time-based billing, retainer |
| **Saude (Healthcare)** | heart | 86.x | 50 | Insurance billing, SUS reimbursement |
| **Educacao (Education)** | book | 85.x | 44 | Enrollment billing, scholarship tracking |
| **Tecnologia / SaaS** | code | 58.x-63.x | 40 | Subscription billing, MRR metrics |
| **Industria (Manufacturing)** | factory | 10.x-33.x | 58 | Raw material tracking, BOM costing |
| **Transporte / Logistica (Transport)** | truck | 49.x-53.x | 46 | Freight billing, fleet costs |
| **Imobiliaria (Real Estate)** | building | 68.x | 47 | Rental billing, condo fees |
| **Agronegocio (Agribusiness)** | leaf | 01.x-03.x | 54 | Seasonal revenue, rural tax |
| **Outro (Other)** | ellipsis | custom | 38 | Generic COA, user customizes |

**Selection interaction**:
- Click card → card expands with 1-line description + "Select" button
- Tooltip on hover: "We'll pre-configure your chart of accounts, categories, and invoice templates for [industry]"
- "Outro" opens a free-text field: "Describe your business" → AI-assisted COA suggestion via LLM endpoint

**After selection**: Confetti micro-animation + "Great choice! Setting up your accounts..." → 800ms skeleton loader while COA generates → auto-advance to Step 2.

### 2.2 COA Auto-Generation

When an industry is selected, the system calls `POST /api/v1/setup/generate-coa` with the industry code. This triggers:

1. **Base COA load**: 38 universal accounts (cash, bank, AR, AP, equity, retained earnings) always included.
2. **Industry overlay**: Industry-specific accounts loaded from `coa_templates` table.
3. **Category generation**: Expense categories and revenue categories derived from CNAE groups.
4. **Tax profile pre-fill**: Recommended tax regime, SPED obligations, and tax calendar events based on industry.
5. **Invoice template defaults**: Industry-appropriate line item descriptions, payment terms, tax rates.

**Example — Restaurant**:
```
Revenue accounts:
  3.1.01.001 - Receita de Alimentacao
  3.1.01.002 - Receita de Bebidas
  3.1.01.003 - Receita de Delivery
  3.1.02.001 - Comissoes Pagas (marketplace fees)

Expense accounts:
  4.1.01.001 - Custo de Insumos (food cost)
  4.1.01.002 - Custo de Bebidas
  4.1.02.001 - Folha de Pagamento
  4.1.03.001 - Aluguel
  4.1.03.002 - Energia / Agua
  4.1.04.001 - Marketing Digital
  4.1.04.002 - Delivery Fees (iFood, Rappi)
```

**Example — SaaS/Tech**:
```
Revenue accounts:
  3.1.01.001 - Receita de Assinatura (MRR)
  3.1.01.002 - Receita de Setup/Onboarding
  3.1.01.003 - Receita de API Usage

Expense accounts:
  4.1.01.001 - Infraestrutura Cloud (AWS/GCP)
  4.1.01.002 - Licencas de Software
  4.1.02.001 - Folha de Pagamento
  4.1.03.001 - Marketing / CAC
  4.1.04.001 - Suporte / CS
```

### 2.3 Data Collected

| Field | Source | Stored In |
|-------|--------|-----------|
| `industry_code` | User selection | `setup_state.steps.industry` |
| `cnae_primary` | Derived from industry | `company_tax_profile.cnae_primary` |
| `cnae_secondary` | Optional, user input | `company_tax_profile.cnae_secondary` |
| `company_size` | Radio: 1-5, 6-15, 16-50, 50+ | `company_profile.employee_range` |

### 2.4 System Configuration Triggered

- `gl_accounts` seeded from `coa_templates` + industry overlay
- `expense_categories` created (for auto-categorization)
- `revenue_categories` created (for revenue recognition)
- `invoice_line_item_templates` created (pre-filled descriptions)
- `tax_calendar_events` pre-populated for the year

---

## 3. Step 2 — Tax Regime Selection

### 3.1 UI Design

**Layout**: Vertical card stack with radio selection. Each card shows:
- Regime name + badge (recommended / most common)
- 2-line description
- Key rates summary (e.g., "Effective rate: 6-33% based on revenue")
- "Learn more" expandable section

**Regime cards**:

| Regime | Badge | Description | Best For |
|--------|-------|-------------|----------|
| **MEI** | Popular | Fixed monthly DAS, simplified obligations | Microempreendedor Individual, revenue <R$81k/yr |
| **Simples Nacional** | Most common | Progressive DAS based on revenue band | Small biz, revenue <R$4.8M/yr |
| **Lucro Presumido** | | Fixed percentage base for tax calculation | Mid-size, revenue <R$78M/yr |
| **Lucro Real** | Enterprise | Actual profit-based, full bookkeeping | Large biz, revenue >R$78M/yr, banks, holding |

**Recommended regime badge logic**:
- If industry = Restaurante AND size = 1-5 → Simples Nacional (Annex III) recommended
- If industry = Tecnologia AND size = 16-50 → Lucro Presumido recommended
- If size = 50+ → Lucro Real recommended
- Always show "Talk to your accountant" disclaimer

**On selection**: Show SPED obligations summary panel:
```
With Lucro Presumido, you'll need:
✓ DAS/DARF monthly payments (auto-calculated)
✓ EFD-Contribuições (monthly PIS/COFINS)
✓ ECF (annual fiscal bookkeeping)
✓ DCTF (monthly tax declaration)
✗ ECD (not required unless Lucro Real)
✗ SPED PIS/COFINS (non-cumulative only)
```

### 3.2 Tax Engine Configuration

The regime selection triggers configuration of the tax engine (from `B3-tax-engine.md`):

**MEI**:
- Fixed DAS: R$71.60/month (services) or varies by activity
- No PIS/COFINS separation
- No SPED obligations (only DAS payment)
- Tax calendar: 20th of each month

**Simples Nacional**:
- Annex selection based on CNAE primary code
- Fator R calculation prompt (if services annex): "What is your payroll vs. revenue ratio?"
- Progressive rate tables loaded for the year
- DAS generation enabled
- SPED obligations: EFD-ICMS/IPI (if commerce), no ECD/ECF for Simples

**Lucro Presumido**:
- Presumed base rates loaded (32% services, 8% commerce)
- DARF codes configured: 1708 (IRPJ), 2172 (CSLL), 5952 (PIS), 2669 (COFINS)
- Calculation period option: quarterly vs annual
- SPED obligations: EFD-Contribuições, ECF, DCTF

**Lucro Real**:
- Full PIS/COFINS non-cumulative rates (1.65% / 7.6%)
- Lucro real calculation from GL entries
- Loss carryforward tracking enabled
- SPED obligations: ECD, ECF, EFD-Contribuições, EFD-ICMS/IPI, DCTF

### 3.3 Data Collected

| Field | Source | Stored In |
|-------|--------|-----------|
| `regime_tributario` | User selection | `company_tax_profile.regime` |
| `fator_r_ratio` | Input (if Simples + services) | `company_tax_profile.fator_r` |
| `calculation_period` | quarterly / annual (if Presumido) | `company_tax_profile.calc_period` |
| `sped_obligations` | Auto-derived from regime | `company_tax_profile.sped_config` |

### 3.4 System Configuration Triggered

- `company_tax_profile` row created/updated
- Tax calculation module activated for the regime
- Tax calendar events generated for the fiscal year
- SPED obligation reminders scheduled
- Invoice tax fields configured (ICMS, PIS, COFINS, ISS as applicable)

---

## 4. Step 3 — Invoice Template

### 4.1 UI Design

**Layout**: Split view — left panel = form fields, right panel = live preview.

**Form fields**:

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| **Company Logo** | Drag-and-drop upload | None | PNG/JPG/SVG, max 2MB, auto-resize to 200px width |
| **Primary Color** | Color picker | #1a56db (blue) | Used for header bar, accent |
| **Secondary Color** | Color picker | #f3f4f6 (light gray) | Background, borders |
| **Company Name** | Text input | From profile | Displayed in header |
| **Company Address** | Textarea | From profile | Shown below header |
| **Company CNPJ** | Auto-filled | From profile | Required for NFe |
| **Invoice Title** | Text input | "FATURA" | Options: FATURA, NOTA FISCAL, RECIBO, CONTRATO |
| **Invoice Number Prefix** | Text input | "INV-" | e.g., "NF-" for NFe, "ORC-" for orçamento |
| **Invoice Number Next** | Number input | 1 | First invoice number |
| **Payment Terms** | Dropdown | net_30 | net_15, net_30, net_60, upon_receipt, custom |
| **Custom Payment Terms** | Text input | (empty) | Shown if custom selected: "3x 10/30/60" |
| **Late Fee** | Toggle + percentage | Off / 2% per month | Displayed in invoice footer |
| **Bank Details** | Auto-filled from Step 4 | Optional | PIX key, bank/agency/account |
| **Notes / Terms** | Textarea | Pre-filled by industry | Footer text: "Thank you for your business!" |
| **Tax Footer** | Auto-configured | From Step 2 | ISS/PIS/COFINS lines auto-generated |

### 4.2 Live Preview

The right panel shows a real-time invoice preview that updates as the user types:

```
┌──────────────────────────────────────────────┐
│  [LOGO]  COMPANY NAME                        │
│          CNPJ: XX.XXX.XXX/XXXX-XX            │
│          Rua Example, 123 - SP               │
│──────────────────────────────────────────────│
│  FATURA #INV-00001                           │
│  Data: 10/07/2026                            │
│  Vencimento: 09/08/2026                      │
│──────────────────────────────────────────────│
│  Cliente: [Client Name]                      │
│  CPF/CNPJ: XXX.XXX.XXX-XX                   │
│──────────────────────────────────────────────│
│  Qtd  Descrição              Valor Unit.  Total│
│  1    Consultoria mensal     R$ 5.000,00  R$ 5.000,00│
│  2    Relatório anual        R$ 2.000,00  R$ 4.000,00│
│──────────────────────────────────────────────│
│  Subtotal                              R$ 9.000,00│
│  Desconto (0%)                         R$    0,00│
│  ISS (5%)                              R$  450,00│
│  PIS (0,65%)                           R$   58,50│
│  COFINS (3%)                           R$  270,00│
│  Total                                 R$ 9.778,50│
│──────────────────────────────────────────────│
│  Pagamento: Boleto Bancário                 │
│  PIX: xxxxxx@empresa.com                   │
│  Banco: 001 / Ag: 0001 / Cc: 00000-0       │
│──────────────────────────────────────────────│
│  Multa de 2% + juros de 1% ao mês          │
│  sobre valores em atraso.                   │
│  Obrigado pela preferência!                 │
└──────────────────────────────────────────────┘
```

### 4.3 Logo Upload Flow

1. Drag-and-drop or click to select
2. Client-side validation: file type (PNG, JPG, SVG), max 2MB
3. Client-side resize to max 200px width (using canvas API, no server round-trip)
4. Upload to Supabase Storage bucket `tenant/{tenant_id}/invoices/logo.png`
5. Store URL in `invoice_templates.logo_url`
6. Show upload progress bar (typically <1s)

### 4.4 Payment Terms Logic

| Payment Term | Due Date Calculation | Late Fee Default |
|---|---|---|
| `net_15` | Invoice date + 15 days | 2% + 1%/month |
| `net_30` | Invoice date + 30 days | 2% + 1%/month |
| `net_60` | Invoice date + 60 days | 2% + 1%/month |
| `upon_receipt` | Invoice date (due immediately) | None |
| `custom` | User-specified | User-specified |

### 4.5 Data Collected

| Field | Stored In |
|-------|-----------|
| `logo_url` | `invoice_templates.logo_url` |
| `primary_color` | `invoice_templates.primary_color` |
| `secondary_color` | `invoice_templates.secondary_color` |
| `invoice_title` | `invoice_templates.title` |
| `number_prefix` | `invoice_templates.number_prefix` |
| `next_number` | `invoice_templates.next_number` |
| `payment_terms` | `invoice_templates.payment_terms` |
| `custom_terms_text` | `invoice_templates.custom_terms_text` |
| `late_fee_enabled` | `invoice_templates.late_fee_enabled` |
| `late_fee_rate` | `invoice_templates.late_fee_rate` |
| `footer_notes` | `invoice_templates.footer_notes` |

---

## 5. Step 4 — Bank Connection

### 5.1 UI Design

**Layout**: Two-column — left: Open Finance connection, right: manual entry fallback.

**Primary path (Open Finance)**:
```
┌─────────────────────────────────────────────┐
│  Connect Your Bank Account                   │
│                                             │
│  We use Open Finance Brasil (regulated by   │
│  BACEN) to securely import your transactions│
│  and balances. Your data is encrypted and   │
│  you can revoke access anytime.             │
│                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │  Banco do │ │   Itau   │ │ Bradesco │    │
│  │  Brasil   │ │          │ │          │    │
│  └──────────┘ └──────────┘ └──────────┘    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │  Santander│ │  Caixa   │ │  Inter   │    │
│  │          │ │          │ │          │    │
│  └──────────┘ └──────────┘ └──────────┘    │
│                                             │
│  [View all banks →]                         │
│                                             │
│  🔒 Powered by Open Finance Brasil          │
│  Regulated by Banco Central do Brasil       │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│  Or Add Accounts Manually                   │
│                                             │
│  [Bank Name] [Agency] [Account] [Balance]   │
│  + Add account                              │
└─────────────────────────────────────────────┘
```

**Open Finance consent flow** (from `B3-banking-integration.md`):

1. User clicks bank logo
2. Redirect to `consent.openfinance.bcb.gov.br` with L2 Cashflow's client ID
3. User authenticates with bank (bank's own login)
4. User reviews consent scopes:
   - Listar contas (account listing)
   - Saldos (balances)
   - Extratos (transactions)
5. User approves → bank redirects to L2 callback with authorization code
6. L2 exchanges code for access token (mTLS)
7. First sync: fetch accounts, balances, last 30 days of transactions
8. Show success: "Connected! Found 3 accounts, imported 142 transactions"

**Manual entry fallback** (critical — 17% abandonment on bank connection):

1. Form fields: Bank name (dropdown of top 20 Brazilian banks), Agency number, Account number, Account type (CC/CP/Poupanca), Current balance, Optional: PIX key
2. Validation: agency + account format per bank rules
3. Creates `bank_accounts` record without Open Finance consent
4. User manually uploads OFX file or CSV for transaction history

### 5.2 Security & Trust Signals

- "Encrypted with AES-256" badge
- "You can revoke access anytime" with link to BACEN portal
- "We never see your password" — bank authentication happens at the bank
- Trust badge: "Regulated by BACEN - Open Finance Brasil"
- Privacy policy link
- LGPD consent checkbox: "I authorize L2 Cashflow to access my financial data via Open Finance Brasil"

### 5.3 Data Collected

| Field | Source | Stored In |
|-------|--------|-----------|
| `bank_name` | Open Finance or manual | `bank_accounts.bank_name` |
| `account_number` | Open Finance or manual | `bank_accounts.account_number` |
| `agency_number` | Open Finance or manual | `bank_accounts.agency` |
| `account_type` | Open Finance or manual | `bank_accounts.account_type` |
| `consent_id` | Open Finance only | `of_consents.consent_id` |
| `access_token` | Open Finance only | `of_consents.access_token` (encrypted) |
| `initial_balance` | Open Finance or manual | `bank_accounts.initial_balance` |

---

## 6. Step 5 — First Invoice Creation

### 6.1 UI Design

**Layout**: Guided form with smart defaults from Steps 1-4. Split view with live preview.

This is the "magic moment" — the activation event. The UI is designed to minimize friction:

```
┌─────────────────────────────────────────────────────────┐
│  Create Your First Invoice                              │
│                                                         │
│  We've pre-filled everything based on your setup.      │
│  Just fill in the details and send!                     │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Client (required)                                  ││
│  │ [Add new client... or type to search]              ││
│  │                                                    ││
│  │ New client form (inline):                          ││
│  │   Name: _______________                            ││
│  │   CPF/CNPJ: _______________                        ││
│  │   Email: _______________                            ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Line Items                                         ││
│  │ ┌─────────────────────────────────────────────────┐││
│  │ │ [Pre-filled from industry template]            │││
│  │ │ Description: Consultoria mensal                 │││
│  │ │ Qty: 1    Unit Price: R$ 5.000,00    Total: R$ 5.000,00││
│  │ └─────────────────────────────────────────────────┘││
│  │ [+ Add line item]                                  ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Dates                                              ││
│  │ Invoice Date: [10/07/2026]  Due Date: [09/08/2026] ││
│  │ (net_30 from your payment terms)                   ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Preview: [Invoice #INV-00001]                      ││
│  │ (live preview panel)                               ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  [Save as Draft]  [Send Invoice →]  ← primary CTA     │
└─────────────────────────────────────────────────────────┘
```

### 6.2 Smart Defaults

| Field | Default Value | Source |
|-------|---------------|--------|
| Client name | Empty (required) | User input |
| Line item 1 | Industry template description | Step 1 COA template |
| Line item 1 price | Empty (user fills) | — |
| Quantity | 1 | Hardcoded default |
| Invoice date | Today | System |
| Due date | Today + payment_terms days | Step 3 template |
| Invoice number | prefix + next_number | Step 3 template |
| Tax rates | From tax regime config | Step 2 tax profile |
| Payment instructions | From bank connection | Step 4 bank details |

### 6.3 Activation Event Tracking

The "Send Invoice" action triggers the activation event pipeline:

```typescript
interface ActivationEvent {
  tenant_id: string;
  event_type: 'first_invoice_sent' | 'first_invoice_created' | 'setup_completed';
  event_timestamp: Date;
  setup_duration_seconds: number;          // time from wizard start to this event
  steps_completed: number;                 // out of 5
  steps_skipped: string[];                 // list of skipped step names
  industry_code: string;
  regime_tributario: string;
  bank_connected: boolean;
  import_used: boolean;                    // true if came through import wizard
}
```

**Events emitted**:
1. `setup.wizard.started` — when user enters wizard
2. `setup.step.completed` — per step completion
3. `setup.step.skipped` — per step skip
4. `setup.invoice.first_created` — draft saved
5. `setup.invoice.first_sent` — sent to client (the "magic moment")
6. `setup.completed` — all 5 steps done or skipped
7. `setup.wizard.abandoned` — user left mid-wizard (with last completed step)

### 6.4 Post-Activation

After the first invoice is sent:
- Show celebration screen: "Your first invoice is on its way!"
- Show stats: "Your invoice #INV-00001 for R$X,XXX.XX was sent to [Client]"
- CTA buttons: "View Dashboard" | "Create Another Invoice" | "Invite Team Member"
- Unlock advanced features progressively (see Section 7)

---

## 7. Progress Tracking & Checklist

### 7.1 Setup Progress Bar

A horizontal 5-step progress bar at the top of the wizard:

```
[1: Industry ✓]──[2: Tax Regime ✓]──[3: Template]──[4: Bank]──[5: First Invoice]
     completed        completed       current       pending     pending
```

- Steps show checkmark when completed, number when pending/current
- Clicking a completed step allows re-editing
- Clicking a pending step is disabled (sequential flow enforced)
- Color: completed = green (#22c55e), current = blue (#3b82f6), pending = gray (#d1d5db)

### 7.2 Post-Wizard Checklist (Sidebar)

After the wizard is completed (or when user returns to dashboard), a persistent sidebar checklist uses the Zeigarnik effect (unfinished tasks create psychological tension):

```
┌─────────────────────────────────────┐
│  Setup Checklist          3/7       │
│  ████████████░░░░░░░░░░░░ 43%      │
│                                     │
│  ✓ Complete company profile         │
│  ✓ Select industry                  │
│  ✓ Create first invoice             │
│  ○ Connect bank account             │
│  ○ Add first client                 │
│  ○ Set up invoice template          │
│  ○ Invite team member               │
│  ○ Run first report                 │
│                                     │
│  Complete setup to unlock:          │
│  • Cash flow forecasting            │
│  • Automated reconciliation         │
│  • SPED generation                  │
│  • Advanced reports                 │
└─────────────────────────────────────┘
```

### 7.3 Completion Percentage

```typescript
function calculateSetupCompletion(setupState: SetupState): number {
  const weights: Record<string, number> = {
    company_profile: 15,    // CNPJ, name, address
    industry_selection: 20, // COA generated
    tax_regime: 20,         // regime selected
    invoice_template: 15,   // template customized
    bank_connection: 15,    // bank connected (or manual entry)
    first_invoice: 10,      // first invoice created
    first_client: 5,        // first client added
  };

  let total = 0;
  for (const [step, weight] of Object.entries(weights)) {
    if (setupState.steps[step]?.status === 'completed') {
      total += weight;
    }
  }
  return Math.min(total, 100);
}
```

### 7.4 Feature Unlocking

| Completion | Unlocked Features |
|---|---|
| 20% (industry selected) | Basic invoicing, expense tracking |
| 40% (tax regime + template) | Tax calculations, SPED preview |
| 60% (bank connected) | Cash flow dashboard, bank reconciliation |
| 80% (first invoice sent) | AR aging, payment reminders |
| 100% (all steps done) | Full analytics, forecasting, team features |

### 7.5 Data Model — Setup State

```sql
CREATE TABLE setup_state (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL UNIQUE,           -- one setup per tenant
  status          TEXT NOT NULL DEFAULT 'in_progress', -- in_progress, paused, completed
  current_step    INTEGER DEFAULT 1,              -- 1-5
  completion_pct  INTEGER DEFAULT 0,              -- 0-100
  steps           JSONB NOT NULL DEFAULT '{}',    -- see schema below
  started_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  completed_at    TIMESTAMP WITH TIME ZONE,
  setup_duration_seconds INTEGER,                 -- time from start to completion
  import_used     INTEGER DEFAULT 0,              -- 1 if imported data
  abandoned_at    TIMESTAMP WITH TIME ZONE,       -- set when user leaves mid-wizard
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- steps JSONB schema:
-- {
--   "industry": { "status": "completed", "data": { "industry_code": "restaurant", "cnae_primary": "5611-2" }, "completed_at": "..." },
--   "tax_regime": { "status": "completed", "data": { "regime": "simples_nacional", "fator_r": 0.35 }, "completed_at": "..." },
--   "invoice_template": { "status": "in_progress", "data": null, "completed_at": null },
--   "bank_connection": { "status": "pending", "data": null, "completed_at": null },
--   "first_invoice": { "status": "pending", "data": null, "completed_at": null }
-- }

CREATE INDEX idx_setup_state_tenant ON setup_state(tenant_id);
CREATE INDEX idx_setup_state_status ON setup_state(status);
```

---

## 8. Import Wizard

### 8.1 Entry Points

1. **Onboarding wizard**: "Already have data? Import instead" link below Step 1
2. **Dashboard**: "Import Data" button in empty state
3. **Settings**: "Data Import" section

### 8.2 Source Selection

```
┌─────────────────────────────────────────────────┐
│  Import Your Data                               │
│                                                 │
│  Choose your current accounting software:       │
│                                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │QuickBooks│ │  Xero   │ │FreshBooks│          │
│  └─────────┘ └─────────┘ └─────────┘          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │  Nubank │ │  CSV    │ │  OFX    │          │
│  │(export) │ │ (any)   │ │ (bank)  │          │
│  └─────────┘ └─────────┘ └─────────┘          │
│                                                 │
│  "Not sure? Use CSV — we'll help map columns."  │
└─────────────────────────────────────────────────┘
```

### 8.3 CSV Import with Column Mapping

**Step 1: Upload**
- Drag-and-drop or file picker
- Accepted: .csv, .xlsx, .xls
- Max 50MB (approx 500k rows)
- Show file stats: "1,247 rows detected, 12 columns"

**Step 2: Auto-detect + Column Mapping**

System auto-detects columns by header name and content pattern:

| Detected Column | Maps To | Confidence |
|---|---|---|
| "Invoice #" / "Fatura" / "Number" | `invoice_number` | 95% |
| "Date" / "Data" / "Issue Date" | `invoice_date` | 98% |
| "Due Date" / "Vencimento" | `due_date` | 97% |
| "Client" / "Cliente" / "Customer" | `customer_name` | 94% |
| "Amount" / "Valor" / "Total" | `total_brl` | 96% |
| "Status" / "Situacao" | `status` | 88% |
| "Description" / "Descricao" | `description` | 90% |

**UI for mapping**:
```
┌─────────────────────────────────────────────────────────────┐
│  Map Your Columns                                           │
│                                                             │
│  Column 1: "Invoice #"        → [Invoice Number     ▼] ✓  │
│  Column 2: "Date"             → [Invoice Date       ▼] ✓  │
│  Column 3: "Due Date"         → [Due Date           ▼] ✓  │
│  Column 4: "Client"           → [Customer Name      ▼] ✓  │
│  Column 5: "Amount"           → [Total Amount       ▼] ✓  │
│  Column 6: "Status"           → [Status             ▼] ✓  │
│  Column 7: "Notes"            → [Description        ▼] ✓  │
│  Column 8: (skip)             → [Don't import       ▼]    │
│                                                             │
│  Preview (first 5 rows):                                   │
│  ┌──────┬────────────┬──────────┬─────────┬──────────┐     │
│  │ #    │ Date       │ Client   │ Amount  │ Status   │     │
│  ├──────┼────────────┼──────────┼─────────┼──────────┤     │
│  │ 0001 │ 2026-01-15 │ ABC Ltda │ 5.000   │ Pago     │     │
│  │ 0002 │ 2026-01-20 │ XYZ SA   │ 12.300  │ Pendente │     │
│  └──────┴────────────┴──────────┴─────────┴──────────┘     │
│                                                             │
│  [Validate Mapping]  [Import]                               │
└─────────────────────────────────────────────────────────────┘
```

**Step 3: Validation**

Pre-import validation checks:
1. **Duplicate detection**: Match on invoice_number + customer_name + amount
2. **Balance check**: Sum of all invoices should be reasonable (flag if >R$10M for a small business)
3. **Date range check**: Flag invoices older than 2 years
4. **Missing required fields**: invoice_number, date, amount are required
5. **Status mapping**: Map source statuses to L2 statuses (pendente→sent, pago→paid, atrasado→sent)

**Step 4: Import with Progress**

```
┌─────────────────────────────────────────────────┐
│  Importing...                                  │
│  ████████████████████░░░░░░░░ 78%              │
│                                                 │
│  Processing row 987 of 1,247...                 │
│                                                 │
│  ✓ 892 invoices imported                        │
│  ⚠ 23 duplicates skipped                        │
│  ✗ 12 rows had errors (view log)                │
└─────────────────────────────────────────────────┘
```

**Step 5: Summary**
```
┌─────────────────────────────────────────────────┐
│  Import Complete!                               │
│                                                 │
│  ✓ 892 invoices imported                        │
│  ✓ 156 customers created                        │
│  ⚠ 23 duplicates skipped (kept newer version)  │
│  ✗ 12 rows failed (see error log)              │
│                                                 │
│  [View Imported Data]  [Continue Setup]         │
└─────────────────────────────────────────────────┘
```

### 8.4 QuickBooks/Xero API Import

For QuickBooks and Xero, use their APIs instead of file upload:

**QuickBooks**:
1. User clicks "Connect QuickBooks"
2. Redirect to QuickBooks OAuth
3. On callback, fetch: invoices, customers, chart_of_accounts, payments
4. Map fields automatically (QuickBooks field names are well-documented)
5. Import in batches of 1000

**Xero**:
1. User clicks "Connect Xero"
2. Redirect to Xero OAuth (uses PKCE flow)
3. On callback, fetch: invoices, contacts, accounts, bank_transactions
4. Map fields automatically
5. Import in batches of 100

### 8.5 Data Collected

| Field | Source | Stored In |
|-------|--------|-----------|
| `import_source` | User selection | `import_logs.source` |
| `import_file_url` | Upload | `import_logs.file_url` |
| `column_mapping` | User confirmation | `import_logs.column_mapping` |
| `records_imported` | System count | `import_logs.imported_count` |
| `records_skipped` | System count | `import_logs.skipped_count` |
| `records_failed` | System count | `import_logs.failed_count` |

---

## 9. Analytics & Activation Metrics

### 9.1 Setup Completion Tracking

Track every wizard interaction for funnel analysis:

```typescript
interface SetupAnalyticsEvent {
  event_name: string;
  tenant_id: string;
  user_id: string;
  timestamp: Date;
  properties: Record<string, any>;
}
```

**Events tracked**:
| Event | Properties | Purpose |
|---|---|---|
| `setup.wizard.opened` | `source` (signup/return/dashboard) | Entry funnel |
| `setup.wizard.step_viewed` | `step_number`, `step_name` | Step engagement |
| `setup.wizard.step_completed` | `step_number`, `duration_seconds` | Step conversion |
| `setup.wizard.step_skipped` | `step_number`, `reason` (optional) | Skip analysis |
| `setup.wizard.back_clicked` | `from_step`, `to_step` | Navigation patterns |
| `setup.wizard.abandoned` | `last_step`, `duration_seconds`, `exit_page` | Drop-off analysis |
| `setup.wizard.completed` | `total_duration_seconds`, `steps_skipped` | Full funnel |
| `import.wizard.opened` | `source` | Import funnel |
| `import.wizard.file_uploaded` | `file_type`, `file_size_bytes`, `row_count` | File analysis |
| `import.wizard.mapping_adjusted` | `column`, `from_detection`, `to_user_choice` | Mapping accuracy |
| `import.wizard.completed` | `imported_count`, `skipped_count`, `failed_count` | Import success |
| `invoice.first_created` | `amount_brl`, `line_items_count` | Activation |
| `invoice.first_sent` | `amount_brl`, `send_method` | Magic moment |

### 9.2 Drop-off Analysis

Build a conversion funnel dashboard:

```
Wizard Start          100%  ████████████████████████████████████████████
Step 1: Industry       98%  ███████████████████████████████████████████
Step 2: Tax Regime     89%  ██████████████████████████████████████
Step 3: Template       76%  ████████████████████████████████
Step 4: Bank           58%  ████████████████████████  ← biggest drop-off
Step 5: First Invoice  52%  █████████████████████
Setup Complete         48%  ███████████████████
First Invoice Sent     42%  █████████████████
```

**Drop-off response strategies**:

| Step | Expected Drop-off | Mitigation |
|---|---|---|
| Step 1 → 2 | ~5% | Low friction, auto-advance |
| Step 2 → 3 | ~9% | Show "recommended" badge, simplify choices |
| Step 3 → 4 | ~13% | "Skip for now" prominent, reduce form fields |
| Step 4 → 5 | ~18% | Manual entry fallback, "do this later" option |
| Step 5 → complete | ~6% | Guided form with smart defaults |

### 9.3 Activation Metrics

**North star metrics**:

| Metric | Target | Definition |
|---|---|---|
| Time to first invoice | <5 minutes | wizard_start → first_invoice_sent |
| Setup completion rate | >60% | users who complete all 5 steps / users who start |
| Activation rate | >40% | users who send first invoice / users who start wizard |
| Day-7 retention | >50% | users active 7 days after setup |
| Import success rate | >90% | records imported / records uploaded |

**Cohort tracking**:
- Daily cohort: users who started wizard today
- Weekly cohort: users who completed setup this week
- Monthly cohort: activated users this month

### 9.4 Dashboard Queries

```sql
-- Setup completion funnel (last 30 days)
SELECT
  step_name,
  COUNT(DISTINCT tenant_id) AS started,
  COUNT(DISTINCT CASE WHEN status = 'completed' THEN tenant_id END) AS completed,
  ROUND(
    COUNT(DISTINCT CASE WHEN status = 'completed' THEN tenant_id END) * 100.0 /
    COUNT(DISTINCT tenant_id), 1
  ) AS completion_rate
FROM (
  SELECT
    tenant_id,
    jsonb_object_keys(steps) AS step_name,
    (steps -> jsonb_object_keys(steps) ->> 'status') AS status
  FROM setup_state
  WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
)
GROUP BY step_name
ORDER BY MIN(step_name);

-- Average time to complete setup
SELECT
  AVG(setup_duration_seconds) AS avg_seconds,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY setup_duration_seconds) AS median_seconds,
  PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY setup_duration_seconds) AS p90_seconds
FROM setup_state
WHERE status = 'completed'
  AND completed_at >= CURRENT_DATE - INTERVAL '30 days';

-- Drop-off points
SELECT
  current_step,
  COUNT(*) AS abandoned_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
FROM setup_state
WHERE status IN ('paused', 'in_progress')
  AND abandoned_at IS NOT NULL
  AND abandoned_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY current_step
ORDER BY current_step;
```

---

## 10. API Endpoints

### 10.1 Setup Status

```
GET /api/v1/setup/status
```

**Response**:
```json
{
  "status": "in_progress",
  "current_step": 3,
  "completion_pct": 40,
  "steps": {
    "industry": { "status": "completed", "data": { "industry_code": "restaurant" } },
    "tax_regime": { "status": "completed", "data": { "regime": "simples_nacional" } },
    "invoice_template": { "status": "in_progress", "data": null },
    "bank_connection": { "status": "pending", "data": null },
    "first_invoice": { "status": "pending", "data": null }
  },
  "unlocked_features": ["invoicing", "expense_tracking", "tax_calculations", "sped_preview"],
  "checklist": {
    "total": 7,
    "completed": 3,
    "items": [
      { "key": "company_profile", "label": "Complete company profile", "completed": true },
      { "key": "industry", "label": "Select industry", "completed": true },
      { "key": "first_invoice", "label": "Create first invoice", "completed": true },
      { "key": "bank_connection", "label": "Connect bank account", "completed": false },
      { "key": "first_client", "label": "Add first client", "completed": false },
      { "key": "invoice_template", "label": "Set up invoice template", "completed": false },
      { "key": "invite_team", "label": "Invite team member", "completed": false }
    ]
  }
}
```

### 10.2 Complete Step

```
POST /api/v1/setup/complete-step
```

**Request**:
```json
{
  "step": "industry",
  "data": {
    "industry_code": "restaurant",
    "cnae_primary": "5611-2",
    "company_size": "1-5"
  }
}
```

**Response**:
```json
{
  "ok": true,
  "step": "industry",
  "completion_pct": 20,
  "coa_generated": true,
  "accounts_created": 52,
  "categories_created": 15,
  "next_step": "tax_regime",
  "unlocked_features": ["invoicing", "expense_tracking"]
}
```

### 10.3 Skip Step

```
POST /api/v1/setup/skip-step
```

**Request**:
```json
{
  "step": "bank_connection",
  "reason": "will_connect_later"
}
```

**Response**:
```json
{
  "ok": true,
  "step": "bank_connection",
  "status": "skipped",
  "completion_pct": 60,
  "next_step": "first_invoice",
  "warning": "Cash flow forecasting requires bank connection. You can connect later in Settings."
}
```

### 10.4 Reset Setup

```
POST /api/v1/setup/reset
```

**Request**:
```json
{
  "confirm": true,
  "keep_data": true
}
```

**Behavior**:
- Resets `setup_state` to initial state
- Does NOT delete generated COA, invoices, or clients (if `keep_data: true`)
- If `keep_data: false`, rolls back all setup-generated data
- Re-emits `setup.wizard.opened` event

### 10.5 Generate COA

```
POST /api/v1/setup/generate-coa
```

**Request**:
```json
{
  "industry_code": "restaurant",
  "cnae_primary": "5611-2"
}
```

**Response**:
```json
{
  "ok": true,
  "accounts_created": 52,
  "categories_created": 15,
  "preview": {
    "revenue_accounts": ["3.1.01.001 - Receita de Alimentacao", "..."],
    "expense_accounts": ["4.1.01.001 - Custo de Insumos", "..."]
  }
}
```

### 10.6 Bank Connection

```
POST /api/v1/setup/connect-bank
```

**Request (Open Finance)**:
```json
{
  "method": "open_finance",
  "bank_participant_id": "bb"
}
```

**Response**:
```json
{
  "ok": true,
  "redirect_url": "https://consent.openfinance.bcb.gov.br/authorize?..."
}
```

**Request (Manual)**:
```json
{
  "method": "manual",
  "bank_name": "Banco do Brasil",
  "agency": "0001",
  "account_number": "12345-6",
  "account_type": "cc",
  "initial_balance": 15000.00
}
```

### 10.7 Import Data

```
POST /api/v1/setup/import
```

**Request**:
```json
{
  "source": "csv",
  "file_id": "upload-uuid-here",
  "column_mapping": {
    "invoice_number": "Column 1",
    "invoice_date": "Column 2",
    "due_date": "Column 3",
    "customer_name": "Column 4",
    "total_brl": "Column 5",
    "status": "Column 6",
    "description": "Column 7"
  }
}
```

**Response**:
```json
{
  "ok": true,
  "import_id": "imp-uuid-here",
  "status": "processing",
  "estimated_rows": 1247
}
```

```
GET /api/v1/setup/import/{import_id}/status
```

**Response**:
```json
{
  "status": "completed",
  "imported_count": 892,
  "skipped_count": 23,
  "failed_count": 12,
  "errors": [
    { "row": 45, "reason": "Missing required field: amount" },
    { "row": 1023, "reason": "Invalid date format: '13/13/2026'" }
  ]
}
```

---

## 11. Data Model

### 11.1 New Tables

```sql
-- COA Templates (seeded at deployment)
CREATE TABLE coa_templates (
  id              TEXT PRIMARY KEY,
  industry_code   TEXT NOT NULL,
  industry_name   TEXT NOT NULL,
  cnae_range      TEXT,                          -- e.g., '56.1x-56.2x'
  accounts_json   JSONB NOT NULL,                -- array of account definitions
  categories_json JSONB NOT NULL,                -- expense + revenue categories
  templates_json  JSONB,                         -- invoice line item templates
  tax_hints_json  JSONB,                         -- recommended regime, SPED hints
  version         INTEGER DEFAULT 1,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_coa_templates_industry ON coa_templates(industry_code);

-- Invoice Templates (per tenant)
CREATE TABLE invoice_templates (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  logo_url        TEXT,
  primary_color   TEXT DEFAULT '#1a56db',
  secondary_color TEXT DEFAULT '#f3f4f6',
  title           TEXT DEFAULT 'FATURA',
  number_prefix   TEXT DEFAULT 'INV-',
  next_number     INTEGER DEFAULT 1,
  payment_terms   TEXT DEFAULT 'net_30',
  custom_terms_text TEXT,
  late_fee_enabled INTEGER DEFAULT 0,
  late_fee_rate   NUMERIC DEFAULT 2.0,
  footer_notes    TEXT,
  is_default      INTEGER DEFAULT 1,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_invoice_templates_tenant ON invoice_templates(tenant_id);

-- Import Logs
CREATE TABLE import_logs (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  source          TEXT NOT NULL,                 -- 'quickbooks', 'xero', 'freshbooks', 'csv', 'ofx'
  file_url        TEXT,
  column_mapping  JSONB,
  status          TEXT DEFAULT 'pending',        -- pending, processing, completed, failed
  imported_count  INTEGER DEFAULT 0,
  skipped_count   INTEGER DEFAULT 0,
  failed_count    INTEGER DEFAULT 0,
  errors_json     JSONB,
  started_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  completed_at    TIMESTAMP WITH TIME ZONE,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_import_logs_tenant ON import_logs(tenant_id);
CREATE INDEX idx_import_logs_status ON import_logs(tenant_id, status);

-- Setup Analytics Events
CREATE TABLE setup_events (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  user_id         TEXT NOT NULL,
  event_name      TEXT NOT NULL,
  properties      JSONB DEFAULT '{}',
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_setup_events_tenant ON setup_events(tenant_id, created_at);
CREATE INDEX idx_setup_events_name ON setup_events(event_name, created_at);
```

### 11.2 Existing Tables Modified

```sql
-- Add setup_state to track wizard progress (already in Section 7.5)
-- Add invoice_template FK to customer_invoices
ALTER TABLE customer_invoices ADD COLUMN IF NOT EXISTS invoice_template_id TEXT REFERENCES invoice_templates(id);
```

---

## 12. Effort Estimates

### 12.1 Per-Component Breakdown

| Component | Frontend | Backend | Total | Complexity |
|---|---|---|---|---|
| **Setup Wizard Shell** (progress bar, step routing, state management) | 5 days | 2 days | 7 days | Medium |
| **Step 1: Industry Selection** (card grid, COA generation trigger) | 3 days | 3 days | 6 days | Medium |
| **Step 2: Tax Regime Selection** (radio cards, SPED preview) | 3 days | 4 days | 7 days | Medium-High |
| **Step 3: Invoice Template** (color picker, live preview, logo upload) | 5 days | 2 days | 7 days | Medium |
| **Step 4: Bank Connection** (Open Finance flow, manual fallback) | 4 days | 8 days | 12 days | High |
| **Step 5: First Invoice** (guided form, activation tracking) | 4 days | 3 days | 7 days | Medium |
| **Progress Checklist** (sidebar, feature unlocking, percentage) | 3 days | 2 days | 5 days | Low-Medium |
| **COA Template Engine** (12 industry templates, seed data) | — | 5 days | 5 days | Medium |
| **Import Wizard** (file upload, column mapping, validation) | 5 days | 5 days | 10 days | High |
| **QuickBooks/Xero API Import** (OAuth, data mapping, batch import) | 2 days | 8 days | 10 days | High |
| **Analytics & Metrics** (event tracking, funnel dashboard) | 3 days | 3 days | 6 days | Medium |
| **API Endpoints** (7 endpoints, validation, error handling) | — | 4 days | 4 days | Medium |
| **Testing** (unit, integration, E2E) | 3 days | 3 days | 6 days | Medium |
| **Polish & QA** (animations, responsive, edge cases) | 3 days | 1 day | 4 days | Low |

### 12.2 Summary

| Category | Days |
|---|---|
| Frontend | 38 days |
| Backend | 51 days |
| **Total** | **89 days** |
| **With 20% buffer** | **107 days (~21 weeks)** |

### 12.3 Phased Rollout

| Phase | Scope | Duration | Dependencies |
|---|---|---|---|
| **Phase 1** | Wizard shell + Step 1 (Industry) + COA engine | 3 weeks | GL/COA from B2 |
| **Phase 2** | Steps 2-3 (Tax + Template) | 3 weeks | Tax Engine from B3 |
| **Phase 3** | Steps 4-5 (Bank + First Invoice) | 4 weeks | Banking from B3 |
| **Phase 4** | Import Wizard (CSV + QuickBooks/Xero) | 3 weeks | AP/AR from B2 |
| **Phase 5** | Analytics, checklist, feature unlocking | 2 weeks | All prior phases |
| **Phase 6** | Polish, QA, A/B testing | 1 week | All prior phases |

**Critical path**: GL/COA (B2) → Step 1 (COA templates) → Tax Engine (B3) → Step 2 → Steps 3-5 (parallel with Import Wizard)

---

## 13. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ONBOARDING WIZARD                                │
│                                                                         │
│  ┌──────────────┐                                                       │
│  │ Step 1:      │──► coa_templates (DB) ──► gl_accounts (seed)         │
│  │ Industry     │──► expense_categories (seed)                          │
│  │              │──► revenue_categories (seed)                           │
│  │              │──► invoice_line_item_templates (seed)                 │
│  └──────┬───────┘                                                       │
│         │                                                               │
│  ┌──────▼───────┐                                                       │
│  │ Step 2:      │──► company_tax_profile (create/update)                │
│  │ Tax Regime   │──► tax_calendar_events (generate)                     │
│  │              │──► sped_obligations (configure)                       │
│  └──────┬───────┘                                                       │
│         │                                                               │
│  ┌──────▼───────┐                                                       │
│  │ Step 3:      │──► invoice_templates (create)                         │
│  │ Template     │──► logo upload → Supabase Storage                     │
│  └──────┬───────┘                                                       │
│         │                                                               │
│  ┌──────▼───────┐                                                       │
│  │ Step 4:      │──► of_consents (Open Finance)                         │
│  │ Bank         │──► of_accounts (synced from bank)                     │
│  │              │──► bank_accounts (manual entry)                       │
│  └──────┬───────┘                                                       │
│         │                                                               │
│  ┌──────▼───────┐                                                       │
│  │ Step 5:      │──► customer_invoices (create first)                   │
│  │ First Invoice│──► customer_invoice_line_items (line items)           │
│  │              │──► client_accounts (create first client)              │
│  │              │──► setup_events (activation_event: first_invoice_sent)│
│  └──────────────┘                                                       │
│                                                                         │
│  ┌──────────────────────────────────────────────────┐                   │
│  │  Import Wizard (alternative path)                │                   │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐    │                   │
│  │  │ Upload   │──►│ Map      │──►│ Validate │    │                   │
│  │  │ File     │   │ Columns  │   │ & Import │    │                   │
│  │  └──────────┘   └──────────┘   └──────────┘    │                   │
│  │       │              │               │           │                   │
│  │       ▼              ▼               ▼           │                   │
│  │  import_logs    import_logs    customer_invoices │                   │
│  │                              client_accounts     │                   │
│  │                              gl_accounts         │                   │
│  └──────────────────────────────────────────────────┘                   │
│                                                                         │
│  ┌──────────────────────────────────────────────────┐                   │
│  │  Analytics Pipeline                              │                   │
│  │  setup_events ──► DuckDB ──► Metabase Dashboard  │                   │
│  │  (raw events)    (OLAP)    (funnel, cohorts)     │                   │
│  └──────────────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix A: Industry COA Template Count Reference

| Industry | Revenue Accts | Expense Accts | Asset Accts | Liability Accts | Total |
|---|---|---|---|---|---|
| Restaurant | 6 | 18 | 12 | 8 | 52 |
| Retail | 5 | 16 | 14 | 7 | 48 |
| Construction | 7 | 20 | 14 | 8 | 55 |
| Professional Services | 4 | 14 | 10 | 6 | 42 |
| Healthcare | 6 | 17 | 12 | 8 | 50 |
| Education | 5 | 15 | 11 | 7 | 44 |
| SaaS/Tech | 4 | 13 | 10 | 6 | 40 |
| Manufacturing | 8 | 22 | 16 | 8 | 58 |
| Transport | 5 | 16 | 12 | 7 | 46 |
| Real Estate | 6 | 16 | 13 | 8 | 47 |
| Agribusiness | 7 | 19 | 14 | 8 | 54 |
| Other (Generic) | 4 | 12 | 10 | 6 | 38 |

## Appendix B: CNAE Code Mapping

| Industry | Primary CNAE | Description |
|---|---|---|
| Restaurant | 5611-2 | Restaurantes e similares |
| Retail | 4711-3 | Comercio varejista de mercadorias em geral |
| Construction | 4120-4 | Construcao de edificios |
| Professional Services | 6911-7 | Servicos advocaticios |
| Healthcare | 8630-5 | Atividade ambulatorial com recursos para realizacao de procedimentos cirurgicos |
| Education | 8511-2 | Educacao infantil creche |
| SaaS/Tech | 5820-2 | Edicao de programas de computador sob encomenda |
| Manufacturing | 1011-2 | Abate de animais |
| Transport | 4930-2 | Transporte rodoviario de carga, exceto produtos perigosos e mudancas |
| Real Estate | 6810-2 | Compravenda e aluguel de imoveis |
| Agribusiness | 0111-3 | Cultivo de arroz |

## Appendix C: SPED Obligations by Regime

| Obligation | MEI | Simples Nacional | Lucro Presumido | Lucro Real |
|---|---|---|---|---|
| DAS/DARF | Monthly (fixed) | Monthly (progressive) | Monthly (per tax) | Monthly (per tax) |
| EFD-ICMS/IPI | No | If commerce | If commerce | If commerce |
| EFD-Contribuições | No | No | Yes (monthly) | Yes (monthly) |
| ECD | No | No | No | Yes (annual) |
| ECF | No | No | Yes (annual) | Yes (annual) |
| DCTF | No | No | Yes (monthly) | Yes (monthly) |
| DIRF | No | No | Yes (annual) | Yes (annual) |
| SPED PIS/COFINS | No | No | No (cumulative) | Yes (non-cumulative) |
