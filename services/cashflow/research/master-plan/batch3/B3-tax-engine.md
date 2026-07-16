# B3 — Tax Engine Implementation Plan

> Date: 2026-07-10
> Scope: L2 Cashflow — Tax Engine module (the #2 bottleneck, 6 downstream dependents)
> Baseline: Next.js 16 + React 19 + SQLite/Supabase, 17+ tables, repository pattern
> Constraint: D-022 (Rust-first for new infra) applies to Phase 2 cementing; this plan covers the TypeScript/Next.js prototype
> Current state: `lib/tax.ts` has MEI-only DAS calculation (38 lines)

---

## 0. Why Tax Engine is Critical

Tax Engine has **6 downstream dependents**: NFe/NFS-e/CT-e, SPED, Tax Calendar, Fixed Assets, Transfer Pricing, Government APIs, Payroll. It sits on the **critical path** (Auth → GL → Tax Engine → Transfer Pricing → Marketplace). It is rated **XL complexity** — the same tier as General Ledger, NFe, SPED, and Payments.

Current state: `lib/tax.ts` handles only MEI fixed DAS (R$71.60/month). The full tax engine must handle 4 regimes, 5 annexes, 9+ individual taxes, annual table updates, and the incoming CBS/IBS reform.

---

## 1. Architecture Decision: Hybrid Rule-Based + Calculation Engine

### Options Evaluated

| | Pure Rule Engine (JSONB rules) | Pure Calculation Engine (hardcoded) | Hybrid |
|---|---|---|---|
| **How it works** | Tax rules stored as JSONB with effective dates; interpreter evaluates rules at runtime | Each regime is a TypeScript module with explicit calculation logic | Calculation modules for core math; rule-driven config for rates/thresholds/updates |
| **Pros** | Easy annual table updates (insert new rows), CBS/IBS transition = new rules, auditable, version-controlled | Maximum performance, type-safe, easy to test, no interpreter overhead | Best of both: fast core math + flexible config for rate changes |
| **Cons** | Interpreter complexity, hard to debug, performance overhead | Annual table updates require code changes + deployment, hard to add new regimes | Two systems to maintain |
| **CBS/IBS readiness** | Excellent — just add new rule sets | Poor — requires code rewrite | Good — add new regime module + config |

### Decision: Hybrid

**Rationale**: Brazilian tax rules change annually (Simples Nacional tables, PIS/COFINS rates, IRPJ/CSLL thresholds). The CBS/IBS reform (LC 214/2025) will introduce a completely new tax structure through 2033. A pure calculation engine would require code deployments for every rate change. A pure rule engine adds unnecessary interpreter complexity for well-defined mathematical formulas.

**The hybrid approach**:
- **Calculation layer**: TypeScript modules with explicit math for each regime (Simples Nacional, Lucro Presumido, Lucro Real). Type-safe, testable, fast.
- **Configuration layer**: JSONB/stored tables for rates, thresholds, annexes, effective dates. Updated via admin UI or annual migration scripts. No code deployment needed for rate changes.
- **Regime router**: Dispatches to the correct calculation module based on company's `regime_tributario`.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                  API / UI Layer                      │
│  POST /api/v1/tax/calculate                          │
│  POST /api/v1/tax/das/generate                       │
│  GET  /api/v1/tax/summary                            │
│  PUT  /api/v1/tax/tables/:year                       │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              Tax Engine Core                         │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ Regime       │  │ Tax Table    │  │ DAS/DARF   │ │
│  │ Router       │  │ Resolver     │  │ Generator  │ │
│  └──────┬──────┘  └──────┬───────┘  └─────┬──────┘ │
│         │                │                 │        │
│  ┌──────▼────────────────▼─────────────────▼──────┐ │
│  │          Calculation Modules                    │ │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────────┐ │ │
│  │  │ Simples  │ │ Lucro    │ │ Lucro          │ │ │
│  │  │ Nacional │ │ Presumido│ │ Real           │ │ │
│  │  └──────────┘ └──────────┘ └────────────────┘ │ │
│  │  ┌──────────┐ ┌──────────────────────────────┐ │ │
│  │  │ MEI      │ │ CBS/IBS (future)             │ │ │
│  │  └──────────┘ └──────────────────────────────┘ │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              Data Layer                              │
│  tax_tables (faixas, alíquotas, parcelas)            │
│  tax_calculations (audit log)                        │
│  tax_calendar (deadlines)                            │
│  company_tax_profile (regime, CNAE, Fator R)         │
└─────────────────────────────────────────────────────┘
```

---

## 2. Simples Nacional — Full Implementation

### 2.1 Annex Structure (Lei Complementar 123/2006)

| Annex | Activity Type | Rates Range | CNAE Groups |
|-------|---------------|-------------|-------------|
| I | Comércio (Commerce) | 4.00% — 19.00% | 45-47 (trade) |
| II | Indústria (Industry) | 4.50% — 30.00% | 05-33 (manufacturing) |
| III | Serviços em geral (Services, general) | 6.00% — 33.00% | 40-43, 46, 49-96 (with Fator R ≥ 28%) |
| IV | Serviços de construção (Construction) | 4.50% — 33.000% | 41-43 (construction) |
| V | Serviços especializados (Specialized services) | 15.50% — 30.500% | 40-43, 46, 49-96 (with Fator R < 28%) |

### 2.2 Fator R Calculation

```
Fator R = (Folha de Pagamento últimos 12 meses) / (Receita Bruta últimos 12 meses)

Folha de Pagamento includes:
  - Salários (CLT)
  - Pró-labore
  - 13º salário
  - FGTS (8%)
  - INSS patronal (20%)
  - Encargos sociais obrigatórios

Rules:
  - Fator R >= 28% → Use Anexo III (lower rates)
  - Fator R < 28% → Use Anexo V (higher rates)
  - Only applies to companies whose CNAE primary is in Services (Anexos III/V)
  - Commerce (Anexo I) and Industry (Anexo II) are not affected by Fator R
  - Construction (Anexo IV) is not affected by Fator R
```

### 2.3 Progressive Rate Calculation

The Simples Nacional uses a **progressive rate** formula, NOT a marginal rate:

```
Given:
  RBT12 = Receita Bruta dos últimos 12 meses
  Faixa = Find row in Annex table where RBT12 falls
  Alíquota Nominal = Rate for that faixa
  Parcela a Deduzir = Fixed deduction for that faixa

Alíquota Efetiva = ((RBT12 × Alíquota Nominal) - Parcela a Deduzir) / RBT12

DAS Mensal = (RBT12 × Alíquota Efetiva) / 12
```

**Important**: The effective rate is applied to the ENTIRE RBT12, not just the marginal portion. This is different from IRPF/IRPJ progressive brackets.

### 2.4 Sample Rate Table — Anexo III (Services, 2025)

| Faixa | RBT12 Limite | Alíquota Nominal | Parcela a Deduzir |
|-------|-------------|------------------|-------------------|
| 1ª | até R$ 180.000,00 | 6,00% | R$ 0,00 |
| 2ª | até R$ 360.000,00 | 11,20% | R$ 9.360,00 |
| 3ª | até R$ 720.000,00 | 13,50% | R$ 17.640,00 |
| 4ª | até R$ 1.800.000,00 | 16,00% | R$ 35.640,00 |
| 5ª | até R$ 3.600.000,00 | 21,00% | R$ 125.640,00 |
| 6ª | até R$ 4.800.000,00 | 33,00% | R$ 648.000,00 |

### 2.5 Implementation

```typescript
// lib/tax/simples-nacional.ts

import { Decimal } from 'decimal.js';

interface SimplesFaixa {
  faixa: number;
  limite: Decimal;           // RBT12 upper limit
  aliquotaNominal: Decimal;  // Nominal rate (e.g., 0.06 for 6%)
  parcelaDeduzir: Decimal;   // Fixed deduction amount
}

interface SimplesAnnex {
  annex: number;             // I-V
  faixas: SimplesFaixa[];
}

function calcularSimplesNacional(
  receitaBruta12: Decimal,
  annex: SimplesAnnex,
): Decimal {
  // Find correct faixa
  const faixa = annex.faixas.find(f => receitaBruta12.lte(f.limite));
  if (!faixa) throw new Error('Receita bruta exceeds Simples Nacional limit');

  // Progressive rate formula
  const aliquotaEfetiva = receitaBruta12
    .times(faixa.aliquotaNominal)
    .minus(faixa.parcelaDeduzir)
    .div(receitaBruta12);

  // Monthly DAS
  return receitaBruta12.times(aliquotaEfetiva).div(12).toDecimalPlaces(2);
}
```

### 2.6 Sublimite de Faturamento (EPP)

EPP companies in certain states have a sublimite below the national R$ 4.8M limit:

| State Group | Sublimite |
|-------------|-----------|
| SP, RJ, MG, SC, PR, RS, ES | R$ 4.800.000,00 |
| MA, CE, PB, PE, BA, AL, SE, RN, PI | R$ 3.600.000,00 |
| AM, PA, AP, RR, RO, TO, AC | R$ 3.600.000,00 |
| GO, MT, MS, DF | R$ 3.600.000,00 |

Companies above the state sublimite but below R$ 4.8M must recollect ICMS/ISS directly to the state/municipality.

---

## 3. Lucro Presumido — Full Implementation

### 3.1 Base de Cálculo Presumida

| Activity | Presumed Base | Rate |
|----------|--------------|------|
| Services | 32% of gross revenue | — |
| Commerce | 8% of gross revenue | — |
| Industry + Commerce | 32% (services) + 8% (commerce) | — |

### 3.2 Taxes on Presumed Base

| Tax | Rate | Calculation |
|-----|------|-------------|
| **IRPJ** | 15% | Presumed Base × 15% |
| **IRPJ Adicional** | 10% | (Presumed Base - R$ 20.000/month × 12) × 10% (if annual presumed base > R$ 240.000) |
| **CSLL** | 9% | Presumed Base × 9% (services: 32%; commerce: 8%) |
| **PIS (cumulativo)** | 0,65% | Gross Revenue × 0.65% |
| **COFINS (cumulativo)** | 3,00% | Gross Revenue × 3.00% |

### 3.3 Quarterly vs Annual Calculation

- **IRPJ**: Can be calculated quarterly (trimestral) or annually (anual com antecipações)
  - Quarterly: base = 3 months revenue × presumed %
  - Annual: base = 12 months revenue × presumed %, with monthly anti-cipations
- **CSLL**: Same quarterly/annual option
- **PIS/COFINS**: Monthly, cumulative regime (for Lucro Presumido)

### 3.4 DARF Generation

DAS (Simples Nacional) vs DARF (Lucro Presumido/Lucro Real):
- IRPJ → DARF code 1708
- CSLL → DARF code 2172
- PIS → DARF code 5952
- COFINS → DARF code 2669
- Each has its own due date (typically last business day of month following the period)

### 3.5 Implementation

```typescript
// lib/tax/lucro-presumido.ts

interface LucroPresumidoInput {
  receitaBrutaServicos: Decimal;
  receitaBrutaComercio: Decimal;
  periodo: 'trimestral' | 'anual';
  meses: number; // 3 for trimestral, 12 for annual
  folhaPagamento?: Decimal; // needed for CSLL if applicable
}

interface LucroPresumidoOutput {
  baseServicos: Decimal;
  baseComercio: Decimal;
  irpj: Decimal;
  irpjAdicional: Decimal;
  csll: Decimal;
  pis: Decimal;
  cofins: Decimal;
  totalTributos: Decimal;
  darfCodes: { codigo: string; vencimento: Date; valor: Decimal }[];
}
```

---

## 4. Lucro Real — Full Implementation

### 4.1 Base de Cálculo

```
Lucro Real = Lucro Líquido (contábil)
           + Adições (non-deductible expenses)
           - Exclusões (non-taxable revenue)
           = Lucro Real Ajustado

Lucro Real Negativo → Prejuízo acumulado (loss carryforward)
```

### 4.2 Taxes on Lucro Real

| Tax | Rate | Calculation |
|-----|------|-------------|
| **IRPJ** | 15% | Lucro Real × 15% |
| **IRPJ Adicional** | 10% | (Lucro Real - R$ 20.000/month × 12) × 10% (if > R$ 240.000/year) |
| **CSLL** | 9% | Lucro Real × 9% |
| **PIS (não-cumulativo)** | 1,65% | Gross Revenue × 1.65% (with credits on inputs) |
| **COFINS (não-cumulativo)** | 7,60% | Gross Revenue × 7.60% (with credits on inputs) |

### 4.3 PIS/COFINS Non-Cumulative Credits

Unlike Lucro Presumido (cumulative), Lucro Real allows credit recovery:

**PIS/COFINS Credits on**:
- Goods purchased for resale
- Inputs used in production/services
- Rent and lease payments
- Energy costs
- Depreciation of fixed assets
- Transportation costs (freight)

**PIS/COFINS Credits Rates**:
- PIS credit: 1.65%
- COFINS credit: 7.60%

### 4.4 Loss Carryforward (Prejuízo Acumulado)

```
- Losses can be carried forward for up to 30% of taxable income in each period
- Accumulated losses have no expiration
- Loss offset is mandatory (must offset before calculating IRPJ/CSLL)
- Limit: 30% × Lucro Real do período = maximum loss offset
```

### 4.5 Implementation

```typescript
// lib/tax/lucro-real.ts

interface LucroRealInput {
  lucroLiquido: Decimal;
  adicoes: Decimal[];          // Non-deductible items
  exclusoes: Decimal[];        // Non-taxable items
  receitaBruta: Decimal;       // For PIS/COFINS
  creditosPis: Decimal;        // PIS credits on inputs
  creditosCofins: Decimal;     // COFINS credits on inputs
  prejuizoAcumulado: Decimal;  // Loss carryforward
  periodo: 'trimestral' | 'anual';
  meses: number;
}

interface LucroRealOutput {
  lucroReal: Decimal;
  irpj: Decimal;
  irpjAdicional: Decimal;
  csll: Decimal;
  pisBruto: Decimal;
  pisCreditos: Decimal;
  pisLiquido: Decimal;
  cofinsBruto: Decimal;
  cofinsCreditos: Decimal;
  cofinsLiquido: Decimal;
  prejuizoUtilizado: Decimal;
  prejuizoRemanescente: Decimal;
  totalTributos: Decimal;
  darfCodes: { codigo: string; vencimento: Date; valor: Decimal }[];
}
```

---

## 5. Tax Tables — Storage and Update Strategy

### 5.1 Schema

```sql
-- Tax table versions (annual updates)
CREATE TABLE IF NOT EXISTS tax_table_version (
  id              TEXT PRIMARY KEY,
  year            INTEGER NOT NULL,           -- e.g., 2025
  regime          TEXT NOT NULL,              -- 'simples_nacional', 'lucro_presumido', 'lucro_real', 'mei'
  effective_from  DATE NOT NULL,
  effective_to    DATE,
  source_url      TEXT,                       -- Receita Federal reference
  created_at      TIMESTAMP DEFAULT NOW(),
  UNIQUE(year, regime)
);

-- Simples Nacional annexes with faixas
CREATE TABLE IF NOT EXISTS tax_simples_faixa (
  id              TEXT PRIMARY KEY,
  version_id      TEXT NOT NULL REFERENCES tax_table_version(id),
  annex           INTEGER NOT NULL CHECK (annex BETWEEN 1 AND 5),
  faixa           INTEGER NOT NULL,
  rbt12_limite    NUMERIC NOT NULL,           -- Upper limit of revenue bracket
  aliquota_nominal NUMERIC NOT NULL,          -- Nominal rate (e.g., 0.06)
  parcela_deduzir  NUMERIC NOT NULL DEFAULT 0, -- Fixed deduction
  created_at      TIMESTAMP DEFAULT NOW()
);

-- MEI fixed values by CNAE group
CREATE TABLE IF NOT EXISTS tax_mei_value (
  id              TEXT PRIMARY KEY,
  version_id      TEXT NOT NULL REFERENCES tax_table_version(id),
  cnae_group      TEXT NOT NULL,              -- 'comercio', 'industria', 'servicos', 'servicos_comercio'
  das_mensal      NUMERIC NOT NULL,           -- Monthly DAS value
  created_at      TIMESTAMP DEFAULT NOW()
);

-- Lucro Presumido rates
CREATE TABLE IF NOT EXISTS tax_presumido_rate (
  id              TEXT PRIMARY KEY,
  version_id      TEXT NOT NULL REFERENCES tax_table_version(id),
  activity_type   TEXT NOT NULL,              -- 'servicos', 'comercio'
  presumed_base   NUMERIC NOT NULL,          -- e.g., 0.32 for 32%
  irpj_rate       NUMERIC NOT NULL DEFAULT 0.15,
  irpj_adicional_rate NUMERIC NOT NULL DEFAULT 0.10,
  irpj_adicional_threshold NUMERIC NOT NULL DEFAULT 20000,
  csll_rate       NUMERIC NOT NULL DEFAULT 0.09,
  pis_cumulativo   NUMERIC NOT NULL DEFAULT 0.0065,
  cofins_cumulativo NUMERIC NOT NULL DEFAULT 0.03,
  created_at      TIMESTAMP DEFAULT NOW()
);

-- Lucro Real rates
CREATE TABLE IF NOT EXISTS tax_real_rate (
  id              TEXT PRIMARY KEY,
  version_id      TEXT NOT NULL REFERENCES tax_table_version(id),
  irpj_rate       NUMERIC NOT NULL DEFAULT 0.15,
  irpj_adicional_rate NUMERIC NOT NULL DEFAULT 0.10,
  irpj_adicional_threshold NUMERIC NOT NULL DEFAULT 20000,
  csll_rate       NUMERIC NOT NULL DEFAULT 0.09,
  pis_nao_cumulativo NUMERIC NOT NULL DEFAULT 0.0165,
  cofins_nao_cumulativo NUMERIC NOT NULL DEFAULT 0.076,
  pis_cumulativo   NUMERIC NOT NULL DEFAULT 0.0065,
  cofins_cumulativo NUMERIC NOT NULL DEFAULT 0.03,
  loss_carryforward_limit NUMERIC NOT NULL DEFAULT 0.30, -- 30% of taxable income
  created_at      TIMESTAMP DEFAULT NOW()
);

-- Tax calculation audit log
CREATE TABLE IF NOT EXISTS tax_calculation (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  company_id      TEXT NOT NULL,
  regime          TEXT NOT NULL,
  period          TEXT NOT NULL,              -- '2025-01', '2025-Q1', '2025'
  input_data      JSONB NOT NULL,            -- Full input snapshot
  output_data     JSONB NOT NULL,            -- Full output snapshot
  version_id      TEXT REFERENCES tax_table_version(id),
  calculated_at   TIMESTAMP DEFAULT NOW(),
  calculated_by   TEXT
);
```

### 5.2 Update Process

**Annual update workflow** (typically January for the new year):

1. Receita Federal publishes new tables (usually late December)
2. Admin creates new `tax_table_version` record for the year
3. Admin inserts new faixas/rates for the new year
4. System validates: all annexes have faixas, rates are within expected ranges
5. Old version remains available for historical calculations
6. System uses latest active version for new calculations

**Key design principles**:
- Never delete old table versions (audit trail)
- Version by year, not by individual rate change
- All calculations reference the `version_id` used at calculation time
- Admin UI for table management (no code deployment needed)

---

## 6. Tax Calculation Pipeline

### 6.1 Input Model

```typescript
interface TaxCalculationInput {
  companyId: string;
  regime: 'mei' | 'simples_nacional' | 'lucro_presumido' | 'lucro_real';
  period: string;               // '2025-01' or '2025-Q1' or '2025'
  
  // Revenue data
  receitaBrutaServicos: Decimal;
  receitaBrutaComercio: Decimal;
  receitaBrutaIndustria: Decimal;
  
  // Payroll data (for Fator R)
  folhaPagamento12?: Decimal;   // Last 12 months payroll
  
  // Expense data (for Lucro Real)
  despesasDedutiveis?: Decimal;
  receitasNaoTributaveis?: Decimal;
  despesasNaoDedutiveis?: Decimal;
  
  // PIS/COFINS credits (for Lucro Real não-cumulativo)
  creditosPis?: Decimal;
  creditosCofins?: Decimal;
  
  // Loss carryforward (for Lucro Real)
  prejuizoAcumulado?: Decimal;
  
  // Company profile
  cnaePrimario: string;
  uf: string;                   // State (for sublimite)
}
```

### 6.2 Processing Pipeline

```
Input (revenue, expenses, regime)
    │
    ▼
┌─────────────────────────┐
│  1. Validate Input       │  Check required fields, data types, ranges
└──────────┬──────────────┘
           │
┌──────────▼──────────────┐
│  2. Resolve Tax Tables   │  Load faixas/rates for company's year + regime
└──────────┬──────────────┘
           │
┌──────────▼──────────────┐
│  3. Route by Regime      │  Dispatch to correct calculation module
│  ┌──────────────────┐   │
│  │ MEI → fixed value │   │
│  │ SN  → annex calc  │   │
│  │ LP  → presumed    │   │
│  │ LR  → actual      │   │
│  └──────────────────┘   │
└──────────┬──────────────┘
           │
┌──────────▼──────────────┐
│  4. Calculate Taxes      │  Per-regime calculation logic
│  - IRPJ/CSLL            │
│  - PIS/COFINS           │
│  - ICMS/ISS (if NFe)    │
│  - INSS/FGTS (if payroll)│
└──────────┬──────────────┘
           │
┌──────────▼──────────────┐
│  5. Generate Payment Doc │  DAS (Simples) or DARF (Presumido/Real)
└──────────┬──────────────┘
           │
┌──────────▼──────────────┐
│  6. Audit & Store        │  Log full input/output to tax_calculation
└──────────┬──────────────┘
           │
           ▼
Output (tax amounts, DAS/DARF, audit trail)
```

### 6.3 Output Model

```typescript
interface TaxCalculationOutput {
  calculationId: string;
  companyId: string;
  regime: string;
  period: string;
  
  // Tax breakdown
  tributos: {
    irpj: Decimal;
    irpjAdicional: Decimal;
    csll: Decimal;
    pis: Decimal;
    cofins: Decimal;
    icms?: Decimal;
    iss?: Decimal;
  };
  
  // Payment document
  documentoPagamento: {
    tipo: 'das' | 'darf';
    codigo: string;           // DARF code or DAS reference
    valorTotal: Decimal;
    dataVencimento: Date;
    competencia: string;
  };
  
  // Effective rate
  aliquotaEfetiva: Decimal;  // Total tax / gross revenue
  
  // Metadata
  versionId: string;         // Tax table version used
  calculatedAt: Date;
}
```

---

## 7. Tax Calendar Integration

### 7.1 Deadlines by Regime

| Regime | Document | Due Date |
|--------|----------|----------|
| **MEI** | DAS MEI | Dia 20 do mês seguinte |
| **Simples Nacional** | DAS SN | Dia 15 do mês seguinte |
| **Lucro Presumido** | DARF IRPJ/CSLL | Último dia útil do mês seguinte (trimestral) |
| **Lucro Presumido** | DARF PIS/COFINS | Dia 25 do mês seguinte |
| **Lucro Real** | DARF IRPJ/CSLL | Último dia útil do mês seguinte (trimestral) |
| **Lucro Real** | DARF PIS/COFINS | Dia 25 do mês seguinte |
| **All** | DCTFWeb | Último dia útil do mês seguinte |
| **All** | eSocial S-1299 | Último dia útil do mês seguinte |
| **All** | SPED ECD | Último dia útil de julho |
| **All** | SPED ECF | Último dia útil de julho |

### 7.2 Calendar Schema

```sql
CREATE TABLE IF NOT EXISTS tax_calendar (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  company_id      TEXT NOT NULL,
  regime          TEXT NOT NULL,
  evento          TEXT NOT NULL,              -- 'das_mei', 'das_sn', 'darf_irpj', etc.
  competencia     TEXT NOT NULL,              -- '2025-01'
  data_vencimento DATE NOT NULL,
  data_pagamento  DATE,
  status          TEXT DEFAULT 'pendente',    -- 'pendente', 'pago', 'atrasado', 'isento'
  valor           NUMERIC,
  notas           TEXT,
  created_at      TIMESTAMP DEFAULT NOW()
);
```

### 7.3 Automated Reminders

Using Inngest (per B1-tech-stack.md decision):
- **7 days before**: Warning notification ("DAS vence em 7 dias")
- **3 days before**: Urgent notification ("DAS vence em 3 dias")
- **1 day before**: Critical notification ("DAS vence amanhã")
- **On due date**: Final notification + auto-mark as pending
- **1 day after**: Overdue alert ("DAS em atraso — multa aplicável")

---

## 8. API Endpoints

### 8.1 Calculate Tax

```typescript
POST /api/v1/tax/calculate
Body: TaxCalculationInput
Response: TaxCalculationOutput

// Example request
{
  "companyId": "comp_abc123",
  "regime": "simples_nacional",
  "period": "2025-03",
  "receitaBrutaServicos": 250000.00,
  "receitaBrutaComercio": 0,
  "folhaPagamento12": 80000.00,
  "cnaePrimario": "6201-5/01",
  "uf": "SP"
}

// Example response
{
  "calculationId": "tax_xyz789",
  "tributos": {
    "irpj": 0,          // Simples Nacional includes all
    "irpjAdicional": 0,
    "csll": 0,
    "pis": 0,
    "cofins": 0,
    "icms": 0,
    "iss": 0
  },
  "documentoPagamento": {
    "tipo": "das",
    "valorTotal": 18140.00,
    "dataVencimento": "2025-04-15",
    "competencia": "2025-03"
  },
  "aliquotaEfetiva": 0.08696
}
```

### 8.2 Generate DAS

```typescript
POST /api/v1/tax/das/generate
Body: { companyId: string, competencia: string }
Response: { dasPdfUrl: string, dasXml: string, valorTotal: number }
```

### 8.3 Get Tax Summary

```typescript
GET /api/v1/tax/summary?companyId=comp_abc123&year=2025
Response: {
  regime: string;
  totalTributosAno: number;
  aliquotaEfetivaMedia: number;
  pagamentosRealizados: number;
  pagamentosPendentes: number;
  historicoMensal: Array<{
    competencia: string;
    valor: number;
    status: string;
  }>;
}
```

### 8.4 Update Tax Tables

```typescript
PUT /api/v1/tax/tables/:year
Body: { annexes: SimplesAnnex[], meiValues: MEIValue[], rates: TaxRates }
Response: { versionId: string, createdAt: Date }
```

### 8.5 Server Actions (Next.js)

```typescript
// app/actions/tax.ts
'use server'

export async function calcularTributos(input: TaxCalculationInput) {
  // Validates, calculates, stores audit log, returns result
}

export async function gerarDAS(companyId: string, competencia: string) {
  // Generates DAS payment document (PDF)
}

export async function obterResumoTributario(companyId: string, year: number) {
  // Returns tax summary with historical data
}
```

---

## 9. Testing Strategy

### 9.1 Unit Tests — Parametric Against Known Outputs

Using Vitest (per B1-tech-stack.md decision):

```typescript
// tests/tax/simples-nacional.test.ts

import { describe, it, expect } from 'vitest';
import { calcularSimplesNacional } from '@/lib/tax/simples-nacional';
import Decimal from 'decimal.js';

describe('Simples Nacional — Anexo III', () => {
  const annexIII = loadAnnexIII(2025); // Load from test fixture

  it.each([
    // [receitaBruta12, expectedDAS]
    [50000, 250],      // Faixa 1: 6% nominal, 0% deduction
    [180000, 900],     // Faixa 1 limit: 6% nominal
    [250000, 1510],    // Faixa 2: 11.2% nominal, R$9360 deduction
    [360000, 2640],    // Faixa 2 limit
    [500000, 4937.50], // Faixa 3: 13.5% nominal, R$17640 deduction
    [720000, 7830],    // Faixa 3 limit
    [1000000, 12180],  // Faixa 4: 16% nominal, R$35640 deduction
    [1800000, 23400],  // Faixa 4 limit
    [2500000, 39166.67], // Faixa 5: 21% nominal, R$125640 deduction
    [3600000, 58200],  // Faixa 5 limit
    [4200000, 100800], // Faixa 6: 33% nominal, R$648000 deduction
  ])('RBT12 R$%i → DAS R$%i', (receita, expected) => {
    const result = calcularSimplesNacional(
      new Decimal(receita),
      annexIII
    );
    expect(result.toNumber()).toBeCloseTo(expected, 2);
  });
});

describe('Simples Nacional — Fator R', () => {
  it('Fator R >= 28% uses Anexo III', () => {
    const folha = new Decimal(80000);  // R$80K payroll
    const receita = new Decimal(250000); // R$250K revenue
    const fatorR = folha.div(receita);   // 32%
    expect(fatorR.gte(0.28)).toBe(true);
    // Should use Anexo III (lower rates)
  });

  it('Fator R < 28% uses Anexo V', () => {
    const folha = new Decimal(30000);  // R$30K payroll
    const receita = new Decimal(250000); // R$250K revenue
    const fatorR = folha.div(receita);   // 12%
    expect(fatorR.lt(0.28)).toBe(true);
    // Should use Anexo V (higher rates)
  });
});
```

### 9.2 Property-Based Tests

```typescript
// tests/tax/invariants.test.ts

import { forAll } from 'vitest-fast-check';
import Decimal from 'decimal.js';

describe('Tax calculation invariants', () => {
  it('total taxes never exceed gross revenue', () => {
    forAll(arbRevenue(), (receita) => {
      const resultado = calcularTributos(regime, receita);
      expect(resultado.totalTributos.lte(receita)).toBe(true);
    });
  });

  it('effective rate is always between 0% and 100%', () => {
    forAll(arbRevenue(), (receita) => {
      const resultado = calcularTributos(regime, receita);
      expect(resultado.aliquotaEfetiva.gte(0)).toBe(true);
      expect(resultado.aliquotaEfetiva.lte(1)).toBe(true);
    });
  });

  it('DAS/DARF values are always positive', () => {
    forAll(arbRevenue(), (receita) => {
      const resultado = calcularTributos(regime, receita);
      expect(resultado.documentoPagamento.valorTotal.gt(0)).toBe(true);
    });
  });
});
```

### 9.3 Golden Master Tests

```typescript
// tests/tax/golden-master.test.ts

import { readFileSync } from 'fs';
import { calcularSimplesNacional } from '@/lib/tax/simples-nacional';

// Test data from Receita Federal official tables
const testData = JSON.parse(
  readFileSync('tests/fixtures/simples-nacional-2025.json', 'utf-8')
);

describe('Golden Master — Simples Nacional 2025', () => {
  testData.forEach(({ annex, faixa, rbt12, expectedDAS }) => {
    it(`Anexo ${annex} faixa ${faixa}: RBT12 R$${rbt12}`, () => {
      const result = calcularSimplesNacional(
        new Decimal(rbt12),
        loadAnnex(annex, 2025)
      );
      expect(result.toFixed(2)).toBe(expectedDAS.toFixed(2));
    });
  });
});
```

### 9.4 Test Data Sources

- **Receita Federal Simples Nacional tables**: Published annually at `receita.fazenda.gov.br/SimplesNacional/`
- **DARF codes and due dates**: Published in IN RFB 1.700/2017 and updates
- **Cross-validation**: Compare output against Excel spreadsheets from accounting firms (common practice in Brazil)
- **Edge cases**: Zero revenue, maximum revenue for each faixa, boundary values between faixas

---

## 10. CBS/IBS Transition Preparation

### 10.1 Reform Overview (LC 214/2025)

The Brazilian tax reform replaces PIS/COFINS/ICMS/ISS with:
- **CBS** (Contribuição sobre Bens e Serviços): Federal tax, replacing PIS + COFINS
- **IBS** (Imposto sobre Bens e Serviços): State/municipal tax, replacing ICMS + ISS

**Transition period**: 2026-2033 (rates gradually shift from old to new)

### 10.2 Transition Rates

| Year | CBS Rate | IBS Rate | PIS/COFINS | ICMS/ISS |
|------|----------|----------|------------|----------|
| 2026 | 0.9% | 0.6% | 95% of old rate | 95% of old rate |
| 2027 | 1.8% | 1.2% | 80% of old rate | 80% of old rate |
| 2028 | 2.7% | 1.8% | 65% of old rate | 65% of old rate |
| 2029 | 3.6% | 2.4% | 50% of old rate | 50% of old rate |
| 2030 | 4.5% | 3.0% | 35% of old rate | 35% of old rate |
| 2031 | 5.5% | 3.5% | 20% of old rate | 20% of old rate |
| 2032 | 6.5% | 4.0% | 5% of old rate | 5% of old rate |
| 2033 | 8.0% (full) | 5.0% (full) | 0% (eliminated) | 0% (eliminated) |

*Note: Exact rates are still being regulated. These are approximate based on LC 214.*

### 10.3 Architecture Readiness

The hybrid architecture handles CBS/IBS through:

1. **New regime modules**: Add `cbs-ibs` regime to the regime router
2. **New tax table version**: 2026+ versions include CBS/IBS rates alongside legacy rates
3. **Dual-calculation mode**: During transition, calculate both old and new taxes
4. **Credit system**: CBS/IBS has its own credit rules (different from PIS/COFINS)
5. **Cash basis option**: CBS/IBS allows cash-basis accounting (new for Brazil)

### 10.4 Implementation Path

```
Phase 1 (2026): Add CBS/IBS as a "read-only" calculation alongside existing regime
  - Calculate what CBS/IBS would be for comparison
  - Store both results for audit trail
  - No payment generation yet (transition rates are informational)

Phase 2 (2027-2030): Full dual-mode
  - Generate payment documents for both old and new taxes
  - Credit system for CBS/IBS input credits
  - Cash vs accrual basis selection

Phase 3 (2031-2033): Migration
  - Gradually shift payment to CBS/IBS only
  - Deprecate PIS/COFINS/ICMS/ISS modules
  - Final cutover when old taxes reach 0%
```

---

## 11. Effort Estimate

| Sub-Feature | Effort (days) | Dependencies | Priority |
|-------------|--------------|--------------|----------|
| **Tax table schema + migration** | 3-4 | GL schema (B2) | P0 |
| **Regime router + config resolver** | 2-3 | Tax table schema | P0 |
| **MEI DAS (extend existing)** | 1-2 | Regime router | P0 |
| **Simples Nacional — Anexo I-II** | 3-4 | Regime router | P0 |
| **Simples Nacional — Anexo III-V** | 3-4 | Anexo I-II (same pattern) | P0 |
| **Fator R calculation** | 1-2 | Simples Nacional | P0 |
| **Sublimite handling** | 1-2 | Simples Nacional | P1 |
| **Lucro Presumido — IRPJ/CSLL** | 3-4 | Regime router | P0 |
| **Lucro Presumido — PIS/COFINS** | 2-3 | IRPJ/CSLL | P0 |
| **Lucro Presumido — DARF generation** | 2-3 | PIS/COFINS | P1 |
| **Lucro Real — IRPJ/CSLL + deductions** | 4-5 | Regime router | P1 |
| **Lucro Real — PIS/COFINS não-cumulativo** | 3-4 | Lucro Real IRPJ/CSLL | P1 |
| **Lucro Real — Loss carryforward** | 1-2 | Lucro Real | P1 |
| **Tax calendar + reminders** | 2-3 | Tax engine core | P1 |
| **API endpoints** | 3-4 | All calculation modules | P0 |
| **Admin UI for tax tables** | 2-3 | Tax table schema | P1 |
| **Unit tests (parametric)** | 3-4 | All calculation modules | P0 |
| **Property-based tests** | 2-3 | Unit tests | P1 |
| **Golden master tests** | 2-3 | Unit tests | P1 |
| **CBS/IBS transition prep** | 3-4 | Tax engine core | P2 |
| **Documentation + handoff** | 1-2 | All above | P1 |

### Summary

| Phase | Scope | Effort |
|-------|-------|--------|
| **MVP** | MEI + Simples Nacional (all annexes) + Lucro Presumido + API + tests | 25-35 days |
| **Full** | Lucro Real + Tax Calendar + Admin UI + DARF + CBS/IBS prep | +15-20 days |
| **Total** | Complete tax engine | **40-55 days** |

### Parallelization

The tax engine can be developed in parallel with:
- NFe/NFS-e (depends on tax engine for tax calculations)
- SPED (depends on tax engine for PIS/COFINS/IRPJ/CSLL values)
- Tax Calendar (thin module on top of tax engine)

**Critical path impact**: Tax Engine blocks NFe, SPED, Transfer Pricing, Government APIs, Payroll. Starting tax engine early (concurrent with GL Phase 4-5) is essential.

---

## 12. File Structure

```
lib/tax/
├── index.ts                    # Main entry point, regime router
├── types.ts                    # Shared types (TaxCalculationInput, Output, etc.)
├── mei.ts                      # MEI DAS calculation
├── simples-nacional.ts         # Simples Nacional calculation
├── simples-nacional-annexes.ts # Annex I-V data (loaded from DB)
├── fator-r.ts                  # Fator R calculation
├── lucro-presumido.ts          # Lucro Presumido calculation
├── lucro-real.ts               # Lucro Real calculation
├── darf.ts                     # DARF generation
├── das.ts                      # DAS generation
├── calendar.ts                 # Tax calendar logic
├── tables.ts                   # Tax table resolver (load from DB)
└── cbs-ibs.ts                  # CBS/IBS transition (future)

app/api/v1/tax/
├── calculate/route.ts          # POST /api/v1/tax/calculate
├── das/generate/route.ts       # POST /api/v1/tax/das/generate
├── summary/route.ts            # GET /api/v1/tax/summary
└── tables/[year]/route.ts      # PUT /api/v1/tax/tables/:year

app/actions/
└── tax.ts                      # Server Actions for tax operations

supabase/migrations/
└── 007_tax_engine.sql          # Tax tables schema migration

tests/tax/
├── simples-nacional.test.ts    # Simples Nacional parametric tests
├── lucro-presumido.test.ts     # Lucro Presumido tests
├── lucro-real.test.ts          # Lucro Real tests
├── invariants.test.ts          # Property-based tests
├── golden-master.test.ts       # Golden master tests
└── fixtures/
    ├── simples-nacional-2025.json
    ├── lucro-presumido-2025.json
    └── lucro-real-2025.json
```

---

## 13. Decision Record

### D-TAX-001: Hybrid architecture (not pure rule engine)
**Decision**: Hybrid approach with calculation modules + config-driven rates.
**Rationale**: Brazilian tax rates change annually; CBS/IBS transition requires flexibility. But core math is well-defined and benefits from type safety and testability.
**Trade-off**: Two systems to maintain (modules + config), but each is simple in isolation.

### D-TAX-002: Simples Nacional first (not Lucro Presumido)
**Decision**: Implement MEI + Simples Nacional before Lucro Presumido/Lucro Real.
**Rationale**: 19M+ MEIs + 6M+ MEs = largest market segment. Simples Nacional is the most common regime for small businesses. Faster time-to-market.
**Trade-off**: Enterprise customers (Lucro Presumido/Real) must wait, but validates core engine with simpler cases first.

### D-TAX-003: Decimal everywhere (not float)
**Decision**: Use `Decimal.js` for all tax calculations. Never `number` or `float`.
**Rationale**: Financial calculations require exact precision. Floating-point errors compound across calculations and produce incorrect tax amounts. Banker's rounding (ROUND_HALF_EVEN) for final values.
**Trade-off**: Slightly more verbose code, but non-negotiable for financial accuracy.

### D-TAX-004: Version-controlled tax tables
**Decision**: Tax tables are versioned by year, stored in DB, never hardcoded.
**Rationale**: Annual updates are a fact of Brazilian tax law. Version control provides audit trail, enables historical calculations, and allows parallel year support (e.g., fiscal year ≠ calendar year).
**Trade-off**: Extra schema complexity, but eliminates deployment for rate changes.

### D-TAX-005: CBS/IBS as additive (not replacement)
**Decision**: CBS/IBS starts as a parallel calculation, not a replacement.
**Rationale**: The transition spans 2026-2033. Early implementation should calculate both old and new taxes for comparison, not force migration. Gradual cutover as old taxes phase out.
**Trade-off**: More code during transition, but de-risks the most complex tax reform in Brazilian history.

---

## Appendix A: DARF Codes Reference

| DARF Code | Tax | Description |
|-----------|-----|-------------|
| 1708 | IRPJ | Imposto de Renda Pessoa Jurídica |
| 2172 | CSLL | Contribuição Social sobre o Lucro Líquido |
| 5952 | PIS | Programa de Integração Social |
| 2669 | COFINS | Contribuição para Financiamento da Seguridade Social |
| 8045 | INSS Patronal | Contribuição Previdenciária Patronal |
| 2634 | FGTS | Fundo de Garantia do Tempo de Serviço |

---

## Appendix B: Simples Nacional Annex I Complete Table (2025)

| Faixa | RBT12 Limite | Alíquota Nominal | Parcela a Deduzir |
|-------|-------------|------------------|-------------------|
| 1ª | até R$ 180.000,00 | 4,00% | R$ 0,00 |
| 2ª | até R$ 360.000,00 | 7,30% | R$ 5.940,00 |
| 3ª | até R$ 720.000,00 | 9,50% | R$ 13.860,00 |
| 4ª | até R$ 1.800.000,00 | 10,70% | R$ 22.500,00 |
| 5ª | até R$ 3.600.000,00 | 14,30% | R$ 87.300,00 |
| 6ª | até R$ 4.800.000,00 | 19,00% | R$ 378.000,00 |

## Appendix C: Simples Nacional Annex V Complete Table (2025)

| Faixa | RBT12 Limite | Alíquota Nominal | Parcela a Deduzir |
|-------|-------------|------------------|-------------------|
| 1ª | até R$ 180.000,00 | 15,50% | R$ 0,00 |
| 2ª | até R$ 360.000,00 | 18,00% | R$ 4.500,00 |
| 3ª | até R$ 720.000,00 | 19,50% | R$ 9.900,00 |
| 4ª | até R$ 1.800.000,00 | 20,50% | R$ 17.100,00 |
| 5ª | até R$ 3.600.000,00 | 23,00% | R$ 62.100,00 |
| 6ª | até R$ 4.800.000,00 | 30,50% | R$ 540.000,00 |
