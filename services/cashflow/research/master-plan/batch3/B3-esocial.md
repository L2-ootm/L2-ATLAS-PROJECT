# B3 — eSocial Integration Design

> Date: 2026-07-10
> Scope: L2 Cashflow — eSocial events (S-1200, S-1210, S-1299), digital certificates, DCTFWeb
> Baseline: Next.js 16 + React 19 + SQLite/Supabase, repository pattern, Drizzle ORM
> Layout version: v.S-1.3 (CNPJ alfanumérico, production 01/07/2026)
> Compliance order: Phase 2 — Enterprise (B1-compliance-order.md §2.4)

---

## 0. eSocial Overview

eSocial is Brazil's unified digital bookkeeping system for labor, social security, and tax obligations. Every employer must submit periodic events reporting worker remuneration, payments, and period closing. Non-compliance triggers automatic penalties.

**Key dates**:
- Layout v.S-1.3 production start: **01/07/2026**
- S-1299 deadline: last day of month following the reference month
- eSocial replaces: CAGED, RAIS, DIRF, GFIP, DCTF (payroll portion)

**Three event types for L2 Cashflow MVP**:

| Event | Purpose | Deadline | Frequency |
|-------|---------|----------|-----------|
| S-1200 | Remuneração do trabalhador | Last day of month following reference | Monthly |
| S-1210 | Pagamentos de rendimentos do trabalho | Last day of month following reference | Monthly |
| S-1299 | Fechamento dos eventos periódicos | Last day of month following reference | Monthly |

---

## 1. Event Architecture

### 1.1 Submission Flow

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│ Payroll Data │───>│ Event Gen    │───>│ XML Builder  │───>│ XML Signer  │
│ (DB tables)  │    │ (S-1200/     │    │ (XSD valid)  │    │ (ICP-Brasil)│
│              │    │  S-1210)     │    │              │    │             │
└─────────────┘    └──────────────┘    └──────────────┘    └──────┬──────┘
                                                                  │
┌─────────────┐    ┌──────────────┐    ┌──────────────┐          │
│ DCTFWeb      │<───│ Period Close │<───│ eSocial API  │<─────────┘
│ (auto-gen)   │    │ (S-1299)     │    │ (WS submit)  │
└─────────────┘    └──────────────┘    └──────┬───────┘
                                              │
                                       ┌──────▼───────┐
                                       │ Response      │
                                       │ Handler       │
                                       │ (status/error)│
                                       └──────────────┘
```

### 1.2 Event Lifecycle States

```typescript
type EsocialEventStatus =
  | 'draft'          // Event created, not yet submitted
  | 'validating'     // XSD validation in progress
  | 'signing'        // Digital signature being applied
  | 'submitting'     // Sent to eSocial, awaiting response
  | 'accepted'       // Successfully processed
  | 'rejected'       // Rejected by eSocial (has error codes)
  | 'correction_in_progress' // Being corrected for resubmission
  | 'cancelled'      // Event cancelled (correction event sent)
  | 'timeout';       // No response within SLA
```

### 1.3 Event Sequencing Rules

```
S-1200 (one per worker per period)
  ↓ all workers processed
S-1299 (period closing)
  ↓ triggers
DCTFWeb (auto-generated)

S-1210 (can be submitted independently, but must match S-1200 data)
```

**Ordering enforcement**: S-1299 cannot be submitted until ALL S-1200 events for the period are in `accepted` status. The system validates this before allowing S-1299 generation.

### 1.4 Data Model

```sql
-- eSocial event envelope (tracks each submission)
CREATE TABLE esocial_events (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID NOT NULL,
  
  event_type            TEXT NOT NULL CHECK (event_type IN (
                          'S-1200', 'S-1210', 'S-1299',
                          'S-3000', 'S-3500'  -- future: corrections
                        )),
  
  -- Period reference
  reference_month       INTEGER NOT NULL CHECK (reference_month BETWEEN 1 AND 12),
  reference_year        INTEGER NOT NULL CHECK (reference_year BETWEEN 2000 AND 2099),
  
  -- Event metadata
  esocial_id            TEXT,               -- returned by eSocial after submission
  protocol_number       TEXT,               -- protocolo de envio
  receipt_number        TEXT,               -- recibo de entrega
  
  -- Status
  status                TEXT NOT NULL DEFAULT 'draft',
  submitted_at          TIMESTAMP WITH TIME ZONE,
  processed_at          TIMESTAMP WITH TIME ZONE,
  
  -- XML storage
  xml_content           TEXT NOT NULL,       -- generated XML
  xml_signed            TEXT,               -- signed XML (base64)
  xml_response          TEXT,               -- eSocial response XML
  
  -- Error handling
  error_codes           TEXT,               -- JSON array of eSocial error codes
  error_messages        TEXT,               -- human-readable error messages
  correction_count      INTEGER NOT NULL DEFAULT 0,
  
  -- DCTFWeb
  dctfweb_generated     INTEGER NOT NULL DEFAULT 0,
  dctfweb_protocol      TEXT,
  
  -- Audit
  created_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  
  -- One event per type per period per tenant
  UNIQUE (tenant_id, event_type, reference_month, reference_year)
);

CREATE INDEX idx_esocial_events_period ON esocial_events(reference_year, reference_month);
CREATE INDEX idx_esocial_events_status ON esocial_events(status);
CREATE INDEX idx_esocial_events_tenant ON esocial_events(tenant_id, reference_year, reference_month);

-- Individual worker remuneration records (S-1200 detail)
CREATE TABLE esocial_remuneracoes (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id              UUID NOT NULL REFERENCES esocial_events(id) ON DELETE CASCADE,
  
  -- Worker identification
  cpf_trab              TEXT NOT NULL,       -- CPF do trabalhador (11 digits)
  nis_trab              TEXT,               -- NIS/PIS/PASEP (optional for some regimes)
  matricula             TEXT,               -- matrícula na empresa
  
  -- Classificação
  ind_retificacao       INTEGER NOT NULL DEFAULT 0,  -- 0=original, 1=retificador
  ind_guia             INTEGER NOT NULL DEFAULT 1,   -- 1=grsp, 2=grrf
  nr_recibo            TEXT,               -- recibo original (for retificação)
  
  -- Período de apuração
  dt_inclusao          TEXT NOT NULL,       -- YYYY-MM-DD
  dt_inicio            TEXT NOT NULL,       -- YYYY-MM-DD (início do período)
  dt_fim               TEXT NOT NULL,       -- YYYY-MM-DD (fim do período)
  
  -- Remuneração total
  vr_remun_sufr        NUMERIC(14,2),      -- valor remuneração sujeita a FGTS
  vr_remun_nsufr       NUMERIC(14,2),      -- valor remuneração não sujeita a FGTS
  vr_total_nretido     NUMERIC(14,2),      -- valor total não retido
  
  -- Flags
  ind_simples          INTEGER NOT NULL DEFAULT 0,  -- 1=simples nacional
  ind_acordo           INTEGER NOT NULL DEFAULT 0,  -- 1=acordo trabalhista
  
  created_at           TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_esocial_remuneracoes_event ON esocial_remuneracoes(event_id);
CREATE INDEX idx_esocial_remuneracoes_cpf ON esocial_remuneracoes(cpf_trab);

-- Rubricas (earnings/deductions) per worker per event
CREATE TABLE esocial_rubricas (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  remuneracao_id        UUID NOT NULL REFERENCES esocial_remuneracoes(id) ON DELETE CASCADE,
  
  -- Rubrica identification
  cod_rubr              TEXT NOT NULL,       -- código da rubrica (employer-defined)
  ind_atipico           INTEGER NOT NULL DEFAULT 0,  -- 1=rubrica atípica
  descr_rubr            TEXT NOT NULL,       -- descrição da rubrica
  
  -- Valores
  vr_rubr               NUMERIC(14,2) NOT NULL,  -- valor da rubrica
  vr_rubr_aux           NUMERIC(14,2),       -- valor auxiliar (for calculations)
  
  -- Tipo
  tipo_valor            TEXT NOT NULL CHECK (tipo_valor IN (
                          'provento',     -- earnings
                          'desconto',     -- deductions
                          'base_calculo'  -- calculation base (info only)
                        )),
  
  -- Base de cálculo (when applicable)
  base_calculo          NUMERIC(14,2),       -- base for INSS/IRRF/FGTS calculation
  
  -- Tabela de rubricas reference
  tabela_rubrica_id     UUID,               -- FK to esocial_tabelas_rubricas
  
  created_at           TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_esocial_rubricas_rem ON esocial_rubricas(remuneracao_id);

-- Payment records (S-1210 detail)
CREATE TABLE esocial_pagamentos (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id              UUID NOT NULL REFERENCES esocial_events(id) ON DELETE CASCADE,
  
  -- Beneficiary
  cpf_benef             TEXT NOT NULL,       -- CPF do beneficiário
  nis_benef             TEXT,               -- NIS do beneficiário
  
  -- Pagamento
  dt_pagto              TEXT NOT NULL,       -- YYYY-MM-DD data do pagamento
  vr_liq                NUMERIC(14,2) NOT NULL, -- valor líquido
  vr_bruto              NUMERIC(14,2),      -- valor bruto
  vr_base_irrf          NUMERIC(14,2),      -- base cálculo IRRF
  vr_base_sSocial       NUMERIC(14,2),      -- base cálculo contribuição social
  
  -- IRPF
  cod_inc_irrf          TEXT NOT NULL,       -- código incidência IRRF
  cod_inc_irrf_desc     TEXT,               -- descrição
  
  -- Retenções
  vr_irrf               NUMERIC(14,2) DEFAULT 0,     -- IRRF retido
  vr_previdencia        NUMERIC(14,2) DEFAULT 0,     -- Previdência retida
  
  -- Metadata
  ind_nr_recibo        TEXT,               -- número recibo
  ind_tp_pgto          INTEGER NOT NULL DEFAULT 1,   -- 1=normal, 2=13º, 3=adiantamento
  
  created_at           TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_esocial_pagamentos_event ON esocial_pagamentos(event_id);
CREATE INDEX idx_esocial_pagamentos_cpf ON esocial_pagamentos(cpf_benef);

-- eSocial table of rubricas (employer catalog)
CREATE TABLE esocial_tabelas_rubricas (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID NOT NULL,
  
  cod_rubr              TEXT NOT NULL,
  descr_rubr            TEXT NOT NULL,
  tipo_valor            TEXT NOT NULL,       -- 'provento'|'desconto'|'base_calculo'
  
  -- FGTS/INSS/IRRF applicability
  fgts                  INTEGER NOT NULL DEFAULT 0,  -- 1=incide FGTS
  fgts_sindicato        INTEGER NOT NULL DEFAULT 0,
  inc_base_sSocial      INTEGER NOT NULL DEFAULT 1,  -- 1=incide na base contribuição social
  inc_base_irrf         INTEGER NOT NULL DEFAULT 0,  -- 1=incide na base IRRF
  
  -- Validity
  dt_inicio             TEXT NOT NULL,       -- YYYY-MM-DD
  dt_fim                TEXT,               -- YYYY-MM-DD (null = active)
  
  is_active             INTEGER NOT NULL DEFAULT 1,
  
  created_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  
  UNIQUE (tenant_id, cod_rubr)
);
```

---

## 2. S-1200 — Remuneração do Trabalhador

### 2.1 Required Data

**Per worker per period**:

| Field | Path | Type | Required | Description |
|-------|------|------|----------|-------------|
| `cpfTrab` | `evtRemun.CpfTrab` | string(11) | Yes | Worker CPF |
| `nisTrab` | `evtRemun.NisTrab` | string(11) | Conditional | NIS/PIS/PASEP (required for FGTS regime) |
| `matric` | `evtRemun.Matric` | string(30) | Yes | Employee ID |
| `dtInclusao` | `evtRemun.DtInclusao` | string(8) | Yes | Inclusion date YYYYMMDD |
| `dtInicio` | `evtRemun.DtInicio` | string(8) | Yes | Period start |
| `dtFim` | `evtRemun.DtFim` | string(8) | Yes | Period end |
| `vrRemunSufr` | `evtRemun.VrRemunSufr` | decimal(14,2) | Yes | FGTS-subject remuneration |
| `vrRemunNsufr` | `evtRemun.VrRemunNsufr` | decimal(14,2) | Yes | Non-FGTS remuneration |
| `indSimples` | `evtRemun.IndSimples` | integer | Yes | 0/1 Simples Nacional |
| `indAcordo` | `evtRemun.IndAcordo` | integer | Yes | 0/1 labor agreement |

**Per rubrica**:

| Field | Path | Type | Required | Description |
|-------|------|------|----------|-------------|
| `codRubr` | `evtRemun.ItensRemun.CodRubr` | string(30) | Yes | Rubric code |
| `indAtipico` | `evtRemun.ItensRemun.IndAtipico` | integer | Yes | 0/1 atypical |
| `vrRubr` | `evtRemun.ItensRemun.VrRubr` | decimal(14,2) | Yes | Rubric value |
| `descrRubr` | `evtRemun.ItensRemun.DescrRubr` | string(200) | Conditional | Description (when atypical) |

### 2.2 XML Schema (v.S-1.3)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<eSocial
  xmlns="http://www.esocial.gov.br/schema/lote/eventos/envio/1_1_1"
  xmlns:evt="http://www.esocial.gov.br/schema/evt/TabelasS-1200_v_S-1.3.0"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.esocial.gov.br/schema/lote/eventos/envio/1_1_1
                       events	SendBatch_v1_1_1.xsd">
  
  <envioLoteEventos>
    <grupoLote>
      <idLote>1</idLote>
      <evento Id="ID12345678901234567890">
        <eSocial xmlns="http://www.esocial.gov.br/schema/evt/TabelasS-1200_v_S-1.3.0">
          <evtRemun Id="ID12345678901234567890">
            <ideEmpregador>
              <tpInsc>1</tpInsc>                <!-- 1=CNPJ -->
              <nrInsc>12345678000195</nrInsc>   <!-- CNPJ (14 digits or alphanumeric in v.S-1.3) -->
              <indSemCnpj>false</indSemCnpj>
            </ideEmpregador>
            
            <ideEvento>
              <indApuracao>1</indApuracao>     <!-- 1=mensal -->
              <perApuracao>2026-07</perApuracao> <!-- YYYY-MM -->
            </ideEvento>
            
            <ideTrabalhador>
              <cpfTrab>12345678901</cpfTrab>
              <nisTrab>12345678901</nisTrab>
              <matric>EMP001</matric>
            </ideTrabalhador>
            
            <dtRemun>2026-07-31</dtRemun>
            
            <itensRemun>
              <item>
                <codRubr>SALARIO</codRubr>
                <indAtipico>N</indAtipico>
                <vrRubr>5000.00</vrRubr>
                <codDesc>01</codDesc>
                <indApuracao>1</indApuracao>
              </item>
              <item>
                <codRubr>HORAEXTRA</codRubr>
                <indAtipico>N</indAtipico>
                <vrRubr>800.00</vrRubr>
                <vrRubrAux>50.00</vrRubrAux>
                <codDesc>01</codDesc>
                <indApuracao>1</indApuracao>
              </item>
              <item>
                <codRubr>DESC-IRRF</codRubr>
                <indAtipico>N</indAtipico>
                <vrRubr>-450.00</vrRubr>
                <codDesc>01</codDesc>
                <indApuracao>1</indApuracao>
              </item>
            </itensRemun>
            
            <infoComplComplem>
              <indSimples>N</indSimples>
              <indAcordo>N</indAcordo>
            </infoComplComplem>
          </evtRemun>
        </eSocial>
      </evento>
    </grupoLote>
  </envioLoteEventos>
</eSocial>
```

### 2.3 XML Builder Implementation

```typescript
// lib/esocial/xml/s1200-builder.ts

interface S1200Input {
  employer: {
    cnpj: string;
    tipoInscricao: '1' | '2';  // 1=CNPJ, 2=CEI (deprecated)
  };
  period: {
    indApuracao: 1 | 2;  // 1=mensal, 2=decendial (rare)
    perApuracao: string;  // YYYY-MM
  };
  worker: {
    cpf: string;
    nis?: string;
    matricula: string;
  };
  dtRemun: string;  // YYYY-MM-DD
  rubricas: Array<{
    codRubr: string;
    indAtipico: 'S' | 'N';
    vrRubr: number;
    vrRubrAux?: number;
    codDesc?: string;
  }>;
  infoCompl?: {
    indSimples: 'S' | 'N';
    indAcordo: 'S' | 'N';
  };
}

export function buildS1200XML(input: S1200Input): string {
  const rubricas = input.rubricas.map(r => `
    <item>
      <codRubr>${escapeXml(r.codRubr)}</codRubr>
      <indAtipico>${r.indAtipico}</indAtipico>
      <vrRubr>${formatCurrency(r.vrRubr)}</vrRubr>
      ${r.vrRubrAux ? `<vrRubrAux>${formatCurrency(r.vrRubrAux)}</vrRubrAux>` : ''}
      ${r.codDesc ? `<codDesc>${escapeXml(r.codDesc)}</codDesc>` : ''}
      <indApuracao>${input.period.indApuracao}</indApuracao>
    </item>`).join('');

  return `<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/TabelasS-1200_v_S-1.3.0">
  <evtRemun Id="${generateEventId()}">
    <ideEmpregador>
      <tpInsc>${input.employer.tipoInscricao}</tpInsc>
      <nrInsc>${input.employer.cnpj}</nrInsc>
    </ideEmpregador>
    <ideEvento>
      <indApuracao>${input.period.indApuracao}</indApuracao>
      <perApuracao>${input.period.perApuracao}</perApuracao>
    </ideEvento>
    <ideTrabalhador>
      <cpfTrab>${input.worker.cpf}</cpfTrab>
      ${input.worker.nis ? `<nisTrab>${input.worker.nis}</nisTrab>` : ''}
      <matric>${escapeXml(input.worker.matricula)}</matric>
    </ideTrabalhador>
    <dtRemun>${input.dtRemun}</dtRemun>
    <itensRemun>${rubricas}
    </itensRemun>
    <infoComplComplem>
      <indSimples>${input.infoCompl?.indSimples ?? 'N'}</indSimples>
      <indAcordo>${input.infoCompl?.indAcordo ?? 'N'}</indAcordo>
    </infoComplComplem>
  </evtRemun>
</eSocial>`;
}
```

### 2.4 Payroll → S-1200 Data Mapping

```
payroll_entries                    →  esocial_remuneracoes + esocial_rubricas
─────────────────────────────────────────────────────────────────────────────
payroll_entries.worker_cpf         →  cpf_trab
payroll_entries.worker_nis         →  nis_trab
payroll_entries.employee_id        →  matricula
payroll_entries.period_start       →  dt_inicio
payroll_entries.period_end         →  dt_fim
payroll_entries.reference_month    →  reference_month + reference_year
payroll_entries.total_gross        →  vr_remun_sufr + rubricas (SALARIO)
payroll_entries.total_deductions   →  rubricas (DESC-*)
payroll_entries.total_extras       →  rubricas (HORAEXTRA, ADICIONAL)

rubricas from payroll_entries:
  payroll_entries.earnings[]       →  esocial_rubricas (tipo_valor='provento')
  payroll_entries.deductions[]     →  esocial_rubricas (tipo_valor='desconto')
```

**Critical validation**: Total of proventos must equal `vr_remun_sufr` (or split across sufr/n-sufr based on FGTS applicability).

---

## 3. S-1210 — Pagamentos de Rendimentos do Trabalho

### 3.1 Required Data

| Field | Path | Type | Required | Description |
|-------|------|------|----------|-------------|
| `cpfBenef` | `evtPag.CpfBenef` | string(11) | Yes | Beneficiary CPF |
| `dtPagto` | `evtPag.DtPagto` | string(8) | Yes | Payment date YYYYMMDD |
| `vrLiq` | `evtPag.VrLiq` | decimal(14,2) | Yes | Net payment value |
| `vrBruto` | `evtPag.VrBruto` | decimal(14,2) | Conditional | Gross value (for IRPF) |
| `vrBaseIRRF` | `evtPag.VrBaseIRRF` | decimal(14,2) | Conditional | IRPF base |
| `codIncIRRF` | `evtPag.CodIncIRRF` | string(4) | Yes | IRPF incidence code |
| `vrIRRF` | `evtPag.VrIRRF` | decimal(14,2) | Conditional | IRPF withheld |

### 3.2 XML Schema (v.S-1.3)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/TabelasS-1210_v_S-1.3.0">
  <evtPag Id="ID12345678901234567891">
    <ideEmpregador>
      <tpInsc>1</tpInsc>
      <nrInsc>12345678000195</nrInsc>
    </ideEmpregador>
    
    <ideEvento>
      <indApuracao>1</indApuracao>
      <perApuracao>2026-07</perApuracao>
    </ideEvento>
    
    <ideBenef>
      <cpfBenef>98765432100</cpfBenef>
      <nisBenef>98765432100</nisBenef>
      <nomeBenef>Maria Silva</nomeBenef>
    </ideBenef>
    
    <detPag>
      <codCateg>101</codCateg>               <!-- categoria trabalhador -->
      <dtPgto>2026-08-05</dtPgto>
      <vrLiq>4200.00</vrLiq>
      <vrBruto>5000.00</vrBruto>
      <vrBaseIRRF>4200.00</vrBaseIRRF>
    </detPag>
    
    <retPag>
      <codIncIRRF>01</codIncIRRF>            <!-- código incidência IRRF -->
      <vrIRRF>450.00</vrIRRF>
    </retPag>
    
    <infoPgto>
      <indResBr>0</indResBr>                 <!-- 0=residente, 1=BR -->
      <dtIngPais>2026-01-01</dtIngPais>      <!-- if foreign worker -->
    </infoPgto>
  </evtPag>
</eSocial>
```

### 3.3 CodIncIRRF Reference

| Code | Description |
|------|-------------|
| 01 | Remuneração pago por empresa obligation |
| 02 | Renda recebida de previdência complementar |
| 03 | Salário-família |
| 04 | Aposentadoria |
| 06 | Pensão alimentícia |
| 07 | Pro-labore |
| 09 | Outras remunerações |
| 13 | Rendimento de contrato de trabalho com pessoa física |

### 3.4 Payroll → S-1210 Data Mapping

```
payroll_entries                    →  esocial_pagamentos
─────────────────────────────────────────────────────────────────────────────
payroll_entries.worker_cpf         →  cpf_benef
payroll_entries.payment_date       →  dt_pagto
payroll_entries.net_amount         →  vr_liq
payroll_entries.gross_amount       →  vr_bruto
payroll_entries.irrf_base          →  vr_base_irrf
payroll_entries.irrf_withheld      →  vr_irrf
payroll_entries.irrf_incidence     →  cod_inc_irrf (from rubricas config)
```

---

## 4. S-1299 — Fechamento dos Eventos Periódicos

### 4.1 Purpose

S-1299 signals the closing of the period's events. After submission:
1. eSocial validates all S-1200 events for the period are complete
2. DCTFWeb is automatically generated from the data
3. The employer can no longer submit new S-1200 events for that period

### 4.2 Required Data

| Field | Path | Type | Required | Description |
|-------|------|------|----------|-------------|
| `dtFech` | `evtFech.DtFech` | string(8) | Yes | Closing date YYYYMMDD |
| `indRemun` | `evtFech.IndRemun` | integer | Yes | 0=só S-1200, 1=S-1200+S-1210 |
| `indGuia` | `evtFech.IndGuia` | integer | Conditional | GRSP/GRRF indicator |
| `indExcColid` | `evtFech.IndExcColid` | integer | No | 0/1 exclude collisions |
| `indAutoria` | `evtFech.IndAutoria` | integer | No | Authorizing entity indicator |

### 4.3 XML Schema (v.S-1.3)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/TabelasS-1299_v_S-1.3.0">
  <evtFech Id="ID12345678901234567892">
    <ideEmpregador>
      <tpInsc>1</tpInsc>
      <nrInsc>12345678000195</nrInsc>
    </ideEmpregador>
    
    <ideEvento>
      <indApuracao>1</indApuracao>
      <perApuracao>2026-07</perApuracao>
    </ideEvento>
    
    <dtFech>2026-08-05</dtFech>
    
    <infoFech>
      <indRemun>1</indRemun>                 <!-- inclui S-1210 -->
      <indGuia>0</indGuia>
      <indExcColid>0</indExcColid>
      <indAutoria>0</indAutoria>
    </infoFech>
  </evtFech>
</eSocial>
```

### 4.4 Deadline & DCTFWeb Integration

**Deadline**: Last day of the month following the reference month.
- Reference: July 2026 → Deadline: August 31, 2026
- Reference: December 2026 → Deadline: January 31, 2027

**DCTFWeb auto-generation**:
- After S-1299 is accepted, eSocial generates DCTFWeb automatically
- DCTFWeb contains: INSS, FGTS, IRRF totals per worker
- No separate filing needed — eSocial IS the source
- The employer receives a DCTFWeb receipt (recibo de entrega)
- DCTFWeb can be queried via eSocial API after S-1299 acceptance

**Implementation**:
```typescript
// lib/esocial/dctf-web.ts
export async function queryDCTFWeb(
  tenantId: string,
  referenceMonth: number,
  referenceYear: number
): Promise<DCTFWebResult> {
  const closing = await getClosingEvent(tenantId, referenceMonth, referenceYear);
  if (closing.status !== 'accepted') {
    throw new Error('S-1299 not yet accepted — DCTFWeb not available');
  }
  
  const response = await eSocialClient.consultarDCTFWeb({
    nrRec: closing.protocol_number,
    perApur: `${referenceYear}-${String(referenceMonth).padStart(2, '0')}`,
  });
  
  return {
    protocol: response.nrRec,
    status: response.status,
    contribuicoes: response.contribuicoes,  // INSS, FGTS, IRRF totals
    receipt: response.reciboEntrega,
  };
}
```

---

## 5. Digital Certificate — ICP-Brasil

### 5.1 Certificate Types

| Type | Storage | eSocial Support | Notes |
|------|---------|-----------------|-------|
| **A1** | File (.pfx/.p12) | Yes | Software certificate, 1-year validity, ideal for servers |
| **A3** | Hardware token/smart card | Yes | Requires PKCS#11 driver, user interaction, better security |
| **A4** | Cloud HSM | Yes (future) | Cloud-based, no local storage, enterprise use |

### 5.2 Certificate Loading

```typescript
// lib/esocial/certificate.ts

import { createCipheriv, randomBytes, pbkdf2Sync } from 'crypto';
import { pkcs12, pki } from 'node-forge';

interface CertificateData {
  certificate: Buffer;       // .pfx content
  password: string;          // certificate password
  label?: string;            // human-readable label
  expiresAt: Date;
  cnpj: string;              // bound to employer CNPJ
}

export async function loadPFXCertificate(
  pfxBuffer: Buffer,
  password: string
): Promise<CertificateData> {
  // Parse PKCS#12
  const p12Asn1 = pkcs12.fromAsn1(pfxBuffer);
  const p12 = pkcs12.pkcs12FromAsn1(p12Asn1, password);
  
  // Extract certificate and private key
  const certBags = p12.getBags({ bagType: pkcs12.oids.certBag });
  const keyBags = p12.getBags({ bagType: pkcs12.oids.pkcs8ShroudedKeyBag });
  
  const cert = certBags[0].cert;
  const key = keyBags[0].key;
  
  // Validate chain
  validateCertificateChain(cert);
  
  // Check expiry
  const expiresAt = new Date(cert.validity.notAfter);
  if (expiresAt < new Date()) {
    throw new Error('Certificate expired');
  }
  
  return {
    certificate: pfxBuffer,
    password,
    expiresAt,
    cnpj: extractCNPJFromCert(cert),
  };
}

// XML signing using ICP-Brasil
export function signXML(xmlContent: string, cert: CertificateData): string {
  // eSocial requires SHA-256 digest, enveloped signature
  const signature = {
    canonicalizationAlgorithm: 'http://www.w3.org/2001/10/xml-exc-c14n#',
    signatureAlgorithm: 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256',
    digestAlgorithm: 'http://www.w3.org/2001/04/xmlenc#sha256',
  };
  
  // Build SignedInfo
  const transforms = [
    'http://www.w3.org/2000/09/xmldsig#enveloped-signature',
    'http://www.w3.org/2001/10/xml-exc-c14n#',
  ];
  
  // Compute digest of the canonicalized XML
  const canonicalXml = canonicalize(xmlContent, transforms);
  const digestValue = sha256(canonicalXml);
  
  // Build SignedInfo and sign with private key
  const signedInfo = buildSignedInfo(digestValue, signature);
  const signatureValue = rsaSign(signedInfo, cert);
  
  // Build complete Signature element
  return insertSignatureIntoXml(xmlContent, {
    signatureValue,
    x509Certificate: cert.certificate.toString('base64'),
  });
}
```

### 5.3 Secure Storage

**Options**:

| Storage | Security | Complexity | Cost |
|---------|----------|------------|------|
| Encrypted file (AES-256-GCM) | Medium | Low | Free |
| Supabase Vault (encrypted column) | Medium-High | Low | Included |
| Cloud HSM (AWS KMS/GCP KMS) | High | High | ~$1/key/month |
| Database encrypted blob | Medium | Low | Free |

**Recommendation**: Start with Supabase encrypted column, migrate to Cloud HSM for enterprise.

```sql
-- Certificate storage (encrypted at rest via Supabase vault)
CREATE TABLE esocial_certificates (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID NOT NULL,
  
  label             TEXT NOT NULL,          -- "Certificado A1 - Empresa X"
  cnpj              TEXT NOT NULL,          -- bound CNPJ
  pfx_data_enc      TEXT NOT NULL,          -- encrypted PFX (Supabase vault)
  password_enc      TEXT NOT NULL,          -- encrypted password
  
  expires_at        TIMESTAMP WITH TIME ZONE NOT NULL,
  is_active         INTEGER NOT NULL DEFAULT 1,
  
  created_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 5.4 Certificate Renewal Workflow

1. **Alert 30 days before expiry** → email/dashboard notification
2. **Alert 7 days before expiry** → blocking warning on eSocial submission
3. **Upload new certificate** → validate chain, update encrypted storage
4. **Re-sign pending events** → events in `draft` status with expired cert
5. **Backup** → old certificate kept for 30 days for audit trail

---

## 6. Layout v.S-1.3 — CNPJ Alfanumérico

### 6.1 Changes from v.S-1.2

| Aspect | v.S-1.2 | v.S-1.3 (01/07/2026) |
|--------|---------|----------------------|
| CNPJ field | 14 numeric digits only | Alphanumeric (up to 14 chars, A-Z0-9) |
| `nrInsc` type | `string(14)` numeric | `string(14)` alphanumeric |
| Validation | 11-digit CPF / 14-digit CNPJ | Extended regex: `[A-Z0-9]{14}` |
| Production start | — | 01/07/2026 |
| Homologation support | — | Available from 01/04/2026 |

### 6.2 Impact on L2 Cashflow

```typescript
// lib/esocial/cnpj-validation.ts — v.S-1.3 compliant

// Old (v.S-1.2):
// const CNPJ_REGEX = /^\d{14}$/;

// New (v.S-1.3):
const CNPJ_ALFANUMERIC_REGEX = /^[A-Z0-9]{14}$/;

export function validateCNPJeSocial(cnpj: string): boolean {
  // Strip formatting (dots, slashes, dashes)
  const normalized = cnpj.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  
  // Length check
  if (normalized.length < 14) return false;
  
  // v.S-1.3: alphanumeric allowed
  if (!CNPJ_ALFANUMERIC_REGEX.test(normalized)) return false;
  
  // If all numeric, also validate check digits (legacy CNPJ)
  if (/^\d{14}$/.test(normalized)) {
    return validateCNPJCheckDigits(normalized);
  }
  
  // Alphanumeric: no check digit validation (new format)
  return true;
}

// Layout version selector
export function getLayoutVersion(referenceDate: Date): string {
  // v.S-1.3 production: 01/07/2026
  if (referenceDate >= new Date('2026-07-01')) {
    return 'v.S-1.3';
  }
  return 'v.S-1.2';
}
```

### 6.3 XML Namespace Updates

```typescript
// v.S-1.3 namespaces
const NAMESPACES = {
  S1200: 'http://www.esocial.gov.br/schema/evt/TabelasS-1200_v_S-1.3.0',
  S1210: 'http://www.esocial.gov.br/schema/evt/TabelasS-1210_v_S-1.3.0',
  S1299: 'http://www.esocial.gov.br/schema/evt/TabelasS-1299_v_S-1.3.0',
  envioLote: 'http://www.esocial.gov.br/schema/lote/eventos/envio/1_1_1',
};
```

---

## 7. DCTFWeb Integration

### 7.1 Auto-Generation Flow

```
S-1200 (worker 1) ──┐
S-1200 (worker 2) ──┤
S-1200 (worker N) ──┤
                    ├──> S-1299 (closing) ──> eSocial processes
S-1210 (payment 1) ─┤                          │
S-1210 (payment 2) ─┤                          ▼
                    │                    DCTFWeb generated
                    │                    (INSS + FGTS + IRRF)
                    │                          │
                    ▼                          ▼
              Query DCTFWeb            DCTFWeb receipt issued
```

### 7.2 DCTFWeb Content

DCTFWeb automatically aggregates from S-1200/S-1299:

| Contribution | Source | Formula |
|-------------|--------|---------|
| **INSS patronal** | S-1200 rubricas with `incBaseSocial=1` | 20% × base (up to teto) |
| **INSS terceiros** | S-1200 rubricas | 5.8% × base (Sistema S, SENAI, etc.) |
| **FGTS** | S-1200 rubricas with `fgts=1` | 8% × base |
| **IRRF** | S-1210 `vrIRRF` | Sum of all withholdings |

### 7.3 DCTFWeb Query API

```typescript
// lib/esocial/dctf-web.ts

interface DCTFWebContribution {
  tipo: 'INSS_PATRONAL' | 'INSS_TERCEIROS' | 'FGTS' | 'IRRF';
  baseCalculo: number;
  aliquota: number;
  valor: number;
  detalhes?: Array<{
    rubrica: string;
    valor: number;
  }>;
}

interface DCTFWebResult {
  protocol: string;
  status: 'pendente' | 'entregue' | 'retificado' | 'cancelado';
  contributions: DCTFWebContribution[];
  totalRecursos: number;      // total de recursos
  totalDescontos: number;     // total de descontos
  reciboEntrega: string;
  dataHoraRecibo: Date;
}

export async function getDCTFWeb(
  tenantId: string,
  referenceMonth: number,
  referenceYear: number
): Promise<DCTFWebResult> {
  // Verify S-1299 is accepted
  const closing = await esocialEventsRepository.findClosing(tenantId, referenceMonth, referenceYear);
  if (!closing || closing.status !== 'accepted') {
    throw new Error('S-1299 not accepted — DCTFWeb not yet available');
  }
  
  // Query eSocial for DCTFWeb
  const response = await eSocialClient.consultarDCTFWeb({
    tpAmbiente: getEnvironment(),  // 1=production, 2=homologation
    nrRec: closing.protocol_number,
    perApur: `${referenceYear}-${String(referenceMonth).padStart(2, '0')}`,
  });
  
  return parseDCTFWebResponse(response);
}
```

---

## 8. Payroll Module Integration

### 8.1 Data Flow Architecture

```
┌─────────────────────┐
│  Payroll Module      │
│  (future Phase)      │
│                      │
│  - contracts         │
│  - time sheets       │
│  - benefits          │
│  - deductions        │
│  - net calculation   │
└──────────┬──────────┘
           │
           │  payroll_entries (payroll_period_id, worker_cpf, amounts)
           ▼
┌─────────────────────┐
│  eSocial Adapter     │
│  lib/esocial/adapter │
│                      │
│  - validate data     │
│  - map rubricas      │
│  - generate XML      │
│  - sign & submit     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  eSocial Events      │
│  (esocial_events,    │
│   esocial_remuneracoes│
│   esocial_rubricas,  │
│   esocial_pagamentos)│
└─────────────────────┘
```

### 8.2 Adapter Interface

```typescript
// lib/esocial/adapter.ts

interface PayrollToESocialAdapter {
  // Map payroll period to S-1200
  generateS1200(tenantId: string, payrollPeriodId: string): Promise<S1200Input>;
  
  // Map payroll payments to S-1210
  generateS1210(tenantId: string, payrollPeriodId: string): Promise<S1210Input[]>;
  
  // Generate S-1299 closing
  generateS1299(tenantId: string, referenceMonth: number, referenceYear: number): Promise<S1299Input>;
  
  // Validate payroll data completeness for eSocial
  validateForESocial(payrollPeriodId: string): ValidationResult;
  
  // Map payroll rubricas to eSocial rubricas
  mapRubricas(payrollEntries: PayrollEntry[]): EsocialRubrica[];
}

export class DefaultPayrollAdapter implements PayrollToESocialAdapter {
  async generateS1200(tenantId: string, payrollPeriodId: string): Promise<S1200Input> {
    const entries = await payrollRepository.findByPeriod(payrollPeriodId);
    
    // Group by worker
    const byWorker = groupBy(entries, e => e.worker_cpf);
    
    const results: S1200Input[] = [];
    for (const [cpf, workerEntries] of byWorker) {
      const worker = await workerRepository.findByCpf(tenantId, cpf);
      
      results.push({
        employer: await getEmployerInfo(tenantId),
        period: {
          indApuracao: 1,
          perApuracao: formatPeriod(workerEntries[0].reference_month, workerEntries[0].reference_year),
        },
        worker: {
          cpf,
          nis: worker.nis,
          matricula: worker.employee_id,
        },
        dtRemun: lastDayOfMonth(workerEntries[0].reference_month, workerEntries[0].reference_year),
        rubricas: this.mapRubricas(workerEntries),
      });
    }
    
    return results;
  }
  
  mapRubricas(entries: PayrollEntry[]): EsocialRubrica[] {
    return entries.map(entry => ({
      codRubr: entry.rubrica_code,
      indAtipico: entry.is_atypical ? 'S' : 'N',
      vrRubr: entry.type === 'deduction' ? -entry.amount : entry.amount,
      vrRubrAux: entry.auxiliary_value,
      codDesc: entry.description_code,
    }));
  }
}
```

### 8.3 Rubrica Mapping Table

| Payroll Concept | eSocial codRubr | tipo_valor | fgts | incBaseSocial |
|----------------|-----------------|------------|------|---------------|
| Salário base | `SALARIO` | provento | 1 | 1 |
| Hora extra | `HORAEXTRA` | provento | 1 | 1 |
| Adicional noturno | `ADICNOT` | provento | 1 | 1 |
| Adicional insalubridade | `ADICINSAL` | provento | 1 | 1 |
| 13º salário | `DECIMO3` | provento | 1 | 1 |
| Férias | `FERIAS` | provento | 1 | 1 |
| 1/3 férias | `TERCOFER` | provento | 1 | 1 |
| INSS employee | `DESC-INSS` | desconto | 0 | 0 |
| IRRF | `DESC-IRRF` | desconto | 0 | 0 |
| FGTS employee (if applicable) | `DESC-FGTS` | desconto | 0 | 0 |
| Vale refeição | `VR` | provento | 0 | 0 |
| Vale transporte | `VT` | provento | 0 | 0 |

---

## 9. Error Handling & Correction Workflow

### 9.1 eSocial Error Codes (Common)

| Code | Description | Severity | Resolution |
|------|-------------|----------|------------|
| **101** | Versão do layout inválida | Fatal | Update to v.S-1.3 |
| **201** | Data inválida | Error | Fix date format (YYYY-MM-DD) |
| **301** | CPF inválido | Error | Validate CPF checksum |
| **302** | NIS inválido | Error | Validate NIS format |
| **401** | Valor inválido | Error | Fix numeric format (XX.XX) |
| **501** | Rubrica não encontrada | Warning | Register in tabelas_rubricas |
| **601** | Período fechado | Fatal | Cannot modify closed period |
| **701** | S-1200 não enviado para todos os trabalhadores | Error | Send missing S-1200 events |
| **801** | Assinatura digital inválida | Fatal | Check certificate validity |
| **901** | CNPJ não cadastrado | Fatal | Register CNPJ in eSocial |

### 9.2 Correction Workflow

```
                    ┌─────────────┐
                    │  Rejected   │
                    │  Event      │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Analyze    │
                    │  Error Codes│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Data Fix │ │ Config   │ │ System   │
        │ (user)   │ │ Fix      │ │ Fix      │
        │          │ │ (admin)  │ │ (dev)    │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             └────────────┼────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  Correction │
                   │  Event      │
                   │  (S-3000)   │
                   └──────┬──────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  Resubmit   │
                   └─────────────┘
```

### 9.3 Correction Event (S-3000)

When an event needs correction after acceptance, a **S-3000** (Exclusão/Cancelamento) event is submitted, followed by a new original event with the corrections.

```typescript
// lib/esocial/correction.ts

export async function correctEvent(
  originalEventId: string,
  corrections: Partial<EsocialEvent>,
  tenantId: string
): Promise<EsocialEvent> {
  const original = await esocialEventsRepository.findById(originalEventId);
  
  // Step 1: Submit S-3000 to cancel original
  const cancelEvent = await buildS3000(original);
  await submitEvent(cancelEvent, tenantId);
  
  // Step 2: Build corrected event with new ID
  const correctedEvent = await buildCorrectedEvent(original, corrections);
  
  // Step 3: Submit corrected event
  await submitEvent(correctedEvent, tenantId);
  
  // Step 4: Update original event status
  await esocialEventsRepository.updateStatus(originalEventId, 'cancelled');
  
  return correctedEvent;
}
```

### 9.4 Retry Policy

| Attempt | Delay | Action |
|---------|-------|--------|
| 1 | Immediate | Submit event |
| 2 | 30 seconds | Retry (transient error) |
| 3 | 5 minutes | Retry (server busy) |
| 4 | 1 hour | Retry (eSocial maintenance) |
| 5+ | Manual | Alert admin, manual intervention |

**Transient errors**: timeout, 5xx, connection reset
**Permanent errors**: 4xx, validation errors — no retry, flag for correction

---

## 10. API Endpoints

### 10.1 REST API Design

```typescript
// app/api/esocial/[action]/route.ts

// POST /api/esocial/submit
// Submit an event (S-1200, S-1210, S-1299)
POST /api/esocial/submit
Body: {
  event_type: 'S-1200' | 'S-1210' | 'S-1299';
  reference_month: number;
  reference_year: number;
  payroll_period_id?: string;  // link to payroll
  certificate_id?: string;     // certificate to use
}

Response: {
  event_id: string;
  status: 'submitting' | 'accepted' | 'rejected';
  protocol_number?: string;
  error_codes?: string[];
}

// GET /api/esocial/status/:eventId
// Query event status
GET /api/esocial/status/:eventId

Response: {
  event_id: string;
  event_type: string;
  status: string;
  esocial_id?: string;
  protocol_number?: string;
  submitted_at?: string;
  processed_at?: string;
  error_codes?: string[];
  correction_count: number;
}

// GET /api/esocial/dctfweb
// Get DCTFWeb for a period
GET /api/esocial/dctfweb?month=7&year=2026

Response: {
  protocol: string;
  status: string;
  contributions: Array<{
    tipo: string;
    base_calculo: number;
    aliquota: number;
    valor: number;
  }>;
  total_recursos: number;
  total_descontos: number;
}

// POST /api/esocial/correction
// Submit correction event
POST /api/esocial/correction
Body: {
  original_event_id: string;
  corrections: Record<string, any>;
}

// GET /api/esocial/payslip/:cpf
// Generate payslip from eSocial data
GET /api/esocial/payslip/:cpf?month=7&year=2026

Response: {
  worker: { cpf, nome, matricula };
  period: { month, year };
  earnings: Array<{ code, description, value }>;
  deductions: Array<{ code, description, value }>;
  totals: { gross, deductions, net };
  payment: { date, method, net_value };
}

// GET /api/esocial/calendar
// Get compliance deadlines
GET /api/esocial/calendar?year=2026

Response: {
  deadlines: Array<{
    month: number;
    year: number;
    event_type: string;
    deadline: string;
    status: 'pending' | 'submitted' | 'completed' | 'overdue';
  }>;
}

// POST /api/esocial/validate
// Validate payroll data for eSocial submission
POST /api/esocial/validate
Body: {
  payroll_period_id: string;
}

Response: {
  valid: boolean;
  errors: Array<{ code, message, severity }>;
  warnings: Array<{ code, message }>;
  workers_count: number;
  total_remuneracao: number;
}
```

### 10.2 Batch Processing

```typescript
// POST /api/esocial/batch-submit
// Submit all events for a period
POST /api/esocial/batch-submit
Body: {
  reference_month: number;
  reference_year: number;
  certificate_id: string;
  options: {
    include_s1210: boolean;    // include payment events
    auto_close: boolean;       // auto-submit S-1299 after all S-1200
    dry_run: boolean;          // validate only, don't submit
  };
}

Response: {
  batch_id: string;
  events: Array<{
    event_type: string;
    worker_cpf?: string;
    status: string;
    event_id: string;
  }>;
  summary: {
    total_events: number;
    accepted: number;
    rejected: number;
    pending: number;
  };
}
```

---

## 11. Testing Strategy

### 11.1 XML Schema Validation

```typescript
// tests/esocial/xml-validation.test.ts

import { validateS1200XML, validateS1210XML, validateS1299XML } from '@/lib/esocial/xml-validator';
import { parseS1200XML } from '@/lib/esocial/xml/s1200-builder';

describe('S-1200 XML Validation', () => {
  it('should generate valid XML for standard payroll', () => {
    const input = createTestS1200Input();
    const xml = buildS1200XML(input);
    
    const errors = validateS1200XML(xml);
    expect(errors).toHaveLength(0);
  });
  
  it('should reject XML with invalid CPF', () => {
    const input = createTestS1200Input();
    input.worker.cpf = '00000000000';  // invalid CPF
    
    const errors = validateS1200XML(buildS1200XML(input));
    expect(errors).toContainEqual(
      expect.objectContaining({ code: '301' })
    );
  });
  
  it('should support alphanumeric CNPJ in v.S-1.3', () => {
    const input = createTestS1200Input();
    input.employer.cnpj = 'ABC1234567890';  // alphanumeric
    
    const xml = buildS1200XML(input);
    expect(xml).toContain('<nrInsc>ABC1234567890</nrInsc>');
  });
});

describe('S-1210 XML Validation', () => {
  it('should generate valid XML with IRRF', () => {
    const input = createTestS1210Input();
    const xml = buildS1210XML(input);
    
    const errors = validateS1210XML(xml);
    expect(errors).toHaveLength(0);
  });
});
```

### 11.2 Mock eSocial Responses

```typescript
// tests/esocial/mocks/esocial-responses.ts

export const MOCK_ACCEPTED_RESPONSE = {
  retornoEnvioLoteEventos: {
    cdResposta: 201,
    mensagemResposta: 'Lote processado com sucesso',
    dhRecebimento: '2026-07-10T14:30:00',
    nrProtocolo: '1.1.2026.000000123456789',
    recibo: {
      nrRecibo: '1.1.2026.000000123456789',
      dhReg: '2026-07-10T14:30:00',
    },
  },
};

export const MOCK_REJECTED_RESPONSE = {
  retornoEnvioLoteEventos: {
    cdResposta: 401,
    mensagemResposta: 'Lote processado com erro',
    dhRecebimento: '2026-07-10T14:30:00',
    eventos: [
      {
        cdResposta: 401,
        ideContrib: { nrInsc: '12345678000195' },
        ocorrencias: [
          {
            tipo: 1,  // 1=erro, 2=aviso
            codigo: '301',
            descricao: 'CPF do trabalhador inválido',
            localizacao: '/eSocial/evtRemun/ideTrabalhador/cpfTrab',
          },
        ],
      },
    ],
  },
};

export const MOCK_DCTFWEB_RESPONSE = {
  retornoDCTFWeb: {
    nrRec: 'DCTF.2026.07.0001',
    perApur: '2026-07',
    situacao: 'entregue',
    contribuicoes: [
      { tipo: 'INSS_PATRONAL', baseCalculo: 50000, aliquota: 20, valor: 10000 },
      { tipo: 'FGTS', baseCalculo: 50000, aliquota: 8, valor: 4000 },
      { tipo: 'IRRF', baseCalculo: 42000, aliquota: null, valor: 4500 },
    ],
    reciboEntrega: 'REC.2026.07.0001',
    dhRecibo: '2026-08-05T10:00:00',
  },
};
```

### 11.3 Integration Tests

```typescript
// tests/esocial/integration.test.ts

describe('eSocial Integration', () => {
  it('should generate S-1200 from payroll and submit', async () => {
    // Setup: create worker, payroll entries, certificate
    const worker = await createTestWorker({ cpf: '12345678901' });
    const payroll = await createTestPayrollEntry({
      worker_id: worker.id,
      salary: 5000,
      overtime: 800,
      inss_employee: 400,
      irrf: 450,
    });
    const cert = await createTestCertificate();
    
    // Generate S-1200
    const s1200Input = await adapter.generateS1200(tenantId, payroll.period_id);
    expect(s1200Input.worker.cpf).toBe('12345678901');
    expect(s1200Input.rubricas).toHaveLength(4);
    
    // Build and validate XML
    const xml = buildS1200XML(s1200Input);
    const errors = validateS1200XML(xml);
    expect(errors).toHaveLength(0);
    
    // Mock submission
    mockESocialClient.acceptEvent();
    const result = await esocialService.submitEvent(s1200Input, cert);
    expect(result.status).toBe('accepted');
  });
  
  it('should reject S-1299 when S-1200 events are missing', async () => {
    // Only submit S-1200 for 3 of 5 workers
    await submitS1200ForWorkers(tenantId, 3);
    
    // Attempt S-1299
    await expect(
      esocialService.submitClosing(tenantId, 7, 2026)
    ).rejects.toThrow('2 workers missing S-1200 events');
  });
  
  it('should query DCTFWeb after S-1299 acceptance', async () => {
    await submitClosingAndAccept(tenantId, 7, 2026);
    
    const dctfweb = await esocialService.getDCTFWeb(tenantId, 7, 2026);
    expect(dctfweb.status).toBe('entregue');
    expect(dctfweb.contributions).toHaveLength(3);
  });
});
```

---

## 12. Effort Estimate

### 12.1 Per Event Type

| Component | Effort (days) | Priority | Dependencies |
|-----------|---------------|----------|--------------|
| **S-1200 Remuneração** | | | |
| XML builder + validation | 3 | P0 | None |
| Data model + migration | 2 | P0 | None |
| Payroll adapter | 2 | P0 | Payroll module |
| Submission flow | 2 | P0 | Certificate |
| **S-1200 Subtotal** | **9** | | |
| **S-1210 Pagamentos** | | | |
| XML builder + validation | 2 | P1 | None |
| Data model + migration | 1 | P1 | None |
| Payroll adapter | 1 | P1 | Payroll module |
| Submission flow | 1 | P1 | Certificate |
| **S-1210 Subtotal** | **5** | | |
| **S-1299 Fechamento** | | | |
| XML builder + validation | 1 | P0 | None |
| Closing logic (validate all S-1200) | 2 | P0 | S-1200 |
| Deadline management | 1 | P1 | None |
| **S-1299 Subtotal** | **4** | | |
| **Digital Certificate** | | | |
| PFX loading + validation | 2 | P0 | None |
| XML signing (ICP-Brasil) | 2 | P0 | Certificate |
| Secure storage | 1 | P0 | None |
| Renewal workflow | 1 | P2 | None |
| **Certificate Subtotal** | **6** | | |
| **DCTFWeb** | | | |
| Query integration | 1 | P1 | S-1299 accepted |
| Display/reporting | 1 | P2 | DCTFWeb query |
| **DCTFWeb Subtotal** | **2** | | |
| **Error Handling** | | | |
| Error code mapping | 1 | P1 | None |
| Correction workflow | 2 | P1 | None |
| Retry policy | 1 | P1 | None |
| **Error Subtotal** | **4** | | |
| **Layout v.S-1.3** | | | |
| Alphanumeric CNPJ | 1 | P0 | None |
| Namespace updates | 1 | P0 | None |
| **Layout Subtotal** | **2** | | |
| **Testing** | | | |
| XML schema tests | 2 | P0 | None |
| Mock responses | 1 | P0 | None |
| Integration tests | 2 | P0 | All |
| **Testing Subtotal** | **5** | | |
| **API Layer** | | | |
| REST endpoints | 2 | P0 | All |
| Batch processing | 2 | P1 | All |
| **API Subtotal** | **4** | | |

### 12.2 Summary

| Phase | Scope | Days | Weeks |
|-------|-------|------|-------|
| **MVP** | S-1200 + S-1299 + Certificate + Basic API | 18-22 | 3.5-4.5 |
| **Full** | + S-1210 + DCTFWeb + Error handling + Batch | 32-38 | 6.5-7.5 |
| **Total** | All components | **32-38** | **6.5-7.5** |

### 12.3 Risk Factors

| Risk | Impact | Mitigation |
|------|--------|------------|
| eSocial API changes (v.S-1.3 transition) | High | Abstract versioning, config-driven namespaces |
| Certificate expiry during testing | Medium | Mock certificates for dev, test with expired certs |
| Payroll module not ready | High | Mock payroll data for eSocial dev, adapter pattern isolates |
| DCTFWeb auto-generation timing | Low | Poll for DCTFWeb after S-1299, timeout handling |
| Complex rubrica mapping | Medium | Start with 10 common rubricas, expand incrementally |

---

## Appendix A: Key References

| Reference | URL / Document |
|-----------|---------------|
| eSocial Developer Portal | https://www.esocial.gov.br/empresas/eventos |
| Layout v.S-1.3 XSD | https://www.esocial.gov.br/schema/evt/TabelasS-1200_v_S-1.3.0.xsd |
| ICP-Brasil Documentation | http://www.iti.br/ |
| DCTFWeb Manual | https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/declaracoes-e-informacoes/dctfweb |
| eSocial Error Codes | eSocial Technical Manual, Chapter 8 |

---

## Appendix B: Rubrica Catalog (Default Set)

```typescript
// lib/esocial/rubricas/default-catalog.ts

export const DEFAULT_RUBRICAS: EsocialTabelaRubrica[] = [
  // Proventos
  { codRubr: 'SALARIO',     descrRubr: 'Salário base',           fgts: 1, incBaseSocial: 1, incBaseIrrf: 1, tipoValor: 'provento' },
  { codRubr: 'HORAEXTRA',   descrRubr: 'Hora extra 50%',         fgts: 1, incBaseSocial: 1, incBaseIrrf: 1, tipoValor: 'provento' },
  { codRubr: 'HORAEXTRA2',  descrRubr: 'Hora extra 100%',        fgts: 1, incBaseSocial: 1, incBaseIrrf: 1, tipoValor: 'provento' },
  { codRubr: 'ADICNOT',     descrRubr: 'Adicional noturno',      fgts: 1, incBaseSocial: 1, incBaseIrrf: 1, tipoValor: 'provento' },
  { codRubr: 'ADICINSAL',   descrRubr: 'Adicional insalubridade',fgts: 1, incBaseSocial: 1, incBaseIrrf: 1, tipoValor: 'provento' },
  { codRubr: 'ADICPERIC',   descrRubr: 'Adicional periculosidade',fgts: 1, incBaseSocial: 1, incBaseIrrf: 1, tipoValor: 'provento' },
  { codRubr: 'DECIMO3',     descrRubr: '13º salário',            fgts: 1, incBaseSocial: 1, incBaseIrrf: 1, tipoValor: 'provento' },
  { codRubr: 'FERIAS',      descrRubr: 'Férias',                 fgts: 1, incBaseSocial: 1, incBaseIrrf: 1, tipoValor: 'provento' },
  { codRubr: 'TERCOFER',    descrRubr: '1/3 de férias',          fgts: 1, incBaseSocial: 1, incBaseIrrf: 1, tipoValor: 'provento' },
  { codRubr: 'AVISOIND',    descrRubr: 'Aviso prévio indenizado',fgts: 1, incBaseSocial: 1, incBaseIrrf: 1, tipoValor: 'provento' },
  
  // Benefícios (sem incidência FGTS/INSS/IRRF)
  { codRubr: 'VR',           descrRubr: 'Vale refeição',         fgts: 0, incBaseSocial: 0, incBaseIrrf: 0, tipoValor: 'provento' },
  { codRubr: 'VT',           descrRubr: 'Vale transporte',       fgts: 0, incBaseSocial: 0, incBaseIrrf: 0, tipoValor: 'provento' },
  
  // Descontos
  { codRubr: 'DESC-INSS',   descrRubr: 'Contribuição INSS',     fgts: 0, incBaseSocial: 0, incBaseIrrf: 0, tipoValor: 'desconto' },
  { codRubr: 'DESC-IRRF',   descrRubr: 'Imposto de Renda',      fgts: 0, incBaseSocial: 0, incBaseIrrf: 0, tipoValor: 'desconto' },
  { codRubr: 'DESC-FGTS',   descrRubr: 'FGTS do empregado',     fgts: 0, incBaseSocial: 0, incBaseIrrf: 0, tipoValor: 'desconto' },
  { codRubr: 'DESC-SIND',   descrRubr: 'Contribuição sindical', fgts: 0, incBaseSocial: 0, incBaseIrrf: 0, tipoValor: 'desconto' },
];
```
