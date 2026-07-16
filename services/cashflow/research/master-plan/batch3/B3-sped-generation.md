# B3 — SPED Generation System: Master Plan

> Date: 2026-07-10
> Scope: L2 Cashflow — ECD, ECF, EFD-Contribuições, EFD-ICMS/IPI file generation
> Baseline: GL schema (B2-gl-implementation.md), compliance phases (B1-compliance-order.md)
> Constraint: Phase 3 of compliance roadmap (30-40 days total)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Record Format Specification](#2-record-format-specification)
3. [ECD — Escrituração Contábil Digital](#3-ecd--escrituração-contábil-digital)
4. [ECF — Escrituração Contábil Fiscal](#4-ecf--escrituração-contábil-fiscal)
5. [EFD-Contribuições — PIS/COFINS](#5-efd-contribuições--pis-cofins)
6. [EFD-ICMS/IPI](#6-efd-icmsipi)
7. [Validation Engine](#7-validation-engine)
8. [SEFAZ Validator Integration](#8-sefaz-validator-integration)
9. [Incremental Generation Strategy](#9-incremental-generation-strategy)
10. [API Design](#10-api-design)
11. [Testing Strategy](#11-testing-strategy)
12. [Effort Estimates](#12-effort-estimates)
13. [Data Flow Diagram](#13-data-flow-diagram)

---

## 1. Architecture Overview

### 1.1 Three-Layer Design

```
┌──────────────────────────────────────────────────────────────┐
│                    SPED GENERATION ENGINE                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │  Record Layer    │  │  Block Layer     │  │  File Layer   │ │
│  │  (per-record     │  │  (block assembly │  │  (file-level  │ │
│  │   generators)    │  │   + closure)     │  │   assembly)   │ │
│  │                  │  │                  │  │               │ │
│  │  • register_0000 │  │  • bloco_0       │  │  • assembler  │ │
│  │  • register_0150 │  │  • bloco_c       │  │  • header     │ │
│  │  • register_0500 │  │  • bloco_e       │  │  • totalizer  │ │
│  │  • register_100  │  │  • bloco_g       │  │  • validator  │ │
│  │  • register_c100 │  │  • bloco_h       │  │  • writer     │ │
│  │  • register_m100 │  │  • bloco_i       │  │               │ │
│  │  • ...           │  │  • bloco_j       │  │               │ │
│  │  • register_e110 │  │  • bloco_m       │  │               │ │
│  └────────┬────────┘  └────────┬─────────┘  └───────┬───────┘ │
│           │                    │                     │         │
│  ┌────────┴────────────────────┴─────────────────────┴───────┐ │
│  │              Data Extraction Layer                        │ │
│  │  (queries GL, AP, AR, Tax Engine, NFe tables)            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              Validation Layer                             │ │
│  │  (schema, business rules, totalization, cross-file)      │ │
│  └───────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 Core Abstractions

```typescript
// --- Record Definition ---
interface SpedRecord {
  register_code: string;          // e.g. "0000", "C100", "M100"
  block_code: string;             // e.g. "0", "C", "M"
  fields: SpedField[];
  order: number;                  // sequential within block
}

interface SpedField {
  name: string;                   // e.g. "IND_SIT_ESPECIAL"
  position: number;               // 1-based field position
  type: 'numeric' | 'text' | 'date' | 'code';
  max_length: number;             // max characters
  required: boolean;
  default_value?: string;
  description: string;
}

// --- Block Definition ---
interface SpedBlock {
  code: string;                   // "0", "A", "C", "D", "E", "F", "G", "H", "I", "J", "K", "1", "9"
  name: string;                   // "Bloco 0", "Bloco A", ...
  records: SpedRecord[];
  open_record: string;            // e.g. "0001"
  close_record: string;           // e.g. "0990"
  totalize_record?: string;       // e.g. "0900" (block totalization)
}

// --- File Assembly ---
interface SpedFile {
  type: 'ECD' | 'ECF' | 'EFD_CONTRIBUICOES' | 'EFD_ICMS_IPI';
  blocks: SpedBlock[];
  totalization_record: string;    // "9999"
  hash_record: string;            // "9999" with hash value
}
```

### 1.3 Module Structure

```
lib/sped/
├── core/
│   ├── types.ts                  # SpedRecord, SpedField, SpedBlock, SpedFile
│   ├── field-formatter.ts        # formatField(value, type, max_length)
│   ├── record-builder.ts         # buildRecord(code, fields) → pipe-delimited string
│   ├── block-assembler.ts        # assembleBlock(records) → block string + totals
│   ├── file-assembler.ts         # assembleFile(blocks) → complete file
│   ├── validator.ts              # validateFile(file) → ValidationResult
│   └── hash-calculator.ts        # calcHash(file_content) → MD5/SHA256
│
├── extractors/                   # Data extraction from GL/AP/AR/Tax
│   ├── gl-extractor.ts           # Journal entries, balances, COA
│   ├── ap-extractor.ts           # Vendor bills, payments
│   ├── ar-extractor.ts           # Customer invoices, receipts
│   ├── tax-extractor.ts          # Tax calculations (PIS/COFINS, ICMS, IPI)
│   ├── nfe-extractor.ts          # NFe data (NF-e, NFC-e, CT-e)
│   └── participants-extractor.ts # CNPJ/participant data
│
├── records/
│   ├── common/
│   │   ├── r0000.ts              # Abertura (all files)
│   │   ├── r0150.ts              # Participantes
│   │   ├── r0190.ts              # Unidades de Medida
│   │   ├── r0200.ts              # Tabela de Itens
│   │   ├── r0990.ts              # Fechamento Bloco 0
│   │   └── r9999.ts              # Totalização (all files)
│   │
│   ├── ecd/
│   │   ├── r0500.ts              # Plano de Contas
│   │   ├── r0300.ts              # Plano de Contas Referencial
│   │   ├── r1000.ts              # Abertura Bloco I
│   │   ├── rI200.ts              # Razão (Lançamentos)
│   │   ├── rI300.ts              # Balancetes/Análises
│   │   ├── rI350.ts              # Balancetes de Verificação
│   │   ├── rI500.ts              # Balanço Patrimonial
│   │   ├── rI510.ts              # Demonstração do Resultado (DRE)
│   │   ├── rI600.ts              # Demonstração do Lucro/Lucro Prejuízo
│   │   ├── rI990.ts              # Fechamento Bloco I
│   │   ├── rJ001.ts              # Abertura Bloco J
│   │   ├── rJ100.ts              # Balanço Patrimonial (formato II)
│   │   ├── rJ150.ts              # DRE (formato II)
│   │   ├── rJ900.ts              # Fechamento Bloco J
│   │   └── rJ990.ts              # Fechamento Bloco J (total)
│   │
│   ├── ecf/
│   │   ├── r0300.ts              # Identificação
│   │   ├── r0305.ts              # Composição da Receita
│   │   ├── r0400.ts              # Tabela de Cadastro
│   │   ├── r0460.ts              # Tabela de Redução
│   │   ├── r0500.ts              # Plano de Contas (ECF)
│   │   ├── r0600.ts              # Centro de Custos
│   │   ├── rA001.ts              # Abertura Bloco A
│   │   ├── rA010.ts              # Identificação do Estabelecimento
│   │   ├── rA100.ts              # Documento - Receita (NF)
│   │   ├── rA111.ts              # Processo Referenciado
│   │   ├── rA120.ts              # Informações Adicionais
│   │   ├── rA170.ts              # Composição da Receita (Itens)
│   │   ├── rC001.ts              # Abertura Bloco C
│   │   ├── rC100.ts              # Nota Fiscal
│   │   ├── rC170.ts              # Itens do Documento
│   │   ├── rC180.ts              # Consolidação
│   │   ├── rC190.ts              # Registros Analíticos
│   │   ├── rC380.ts              # Resumo Diário NF-e
│   │   ├── rC390.ts              # Registros Analíticos
│   │   ├── rC400.ts              # ECF Equipamento
│   │   ├── rC405.ts              # Redução Z
│   │   ├── rC420.ts              # Resumo Diário
│   │   ├── rC425.ts              # Resumo Diário (Itens)
│   │   ├── rC490.ts              # Consolidação
│   │   ├── rC495.ts              # ICMS-ST (equipamentos)
│   │   ├── rC800.ts              # Cupom Fiscal Eletrônico (SAT)
│   │   ├── rC810.ts              # Detalhamento CF-e-SAT
│   │   ├── rC820.ts              # ICMS-ST CF-e-SAT
│   │   ├── rC860.ts              # Identificação do ECF
│   │   ├── rC870.ts              # Resumo Diário CF-e-SAT
│   │   ├── rC880.ts              # Consolidação CF-e-SAT
│   │   ├── rC890.ts              # ICMS-ST CF-e-SAT
│   │   ├── rD001.ts              # Abertura Bloco D
│   │   ├── rD100.ts              # CT-e (Conhecimento de Transporte)
│   │   ├── rD101.ts              # Composição do Frete
│   │   ├── rD190.ts              # Registros Analíticos CT-e
│   │   ├── rD300.ts              # Resumo Diário CT-e
│   │   ├── rD350.ts              # Resumo Diário ECF
│   │   ├── rD355.ts              # Redução Z
│   │   ├── rD360.ts              # Pagamento
│   │   ├── rD370.ts              # Composição do Frete
│   │   ├── rD390.ts              # Registros Analíticos
│   │   ├── rD400.ts              # Resumo Diário NFS-e
│   │   ├── rD410.ts              # Consolidação NFS-e
│   │   ├── rD411.ts              # NFS-e (Itens)
│   │   ├── rD420.ts              # Consolidação NFS-e (valores)
│   │   ├── rD500.ts              # Resumo Diário NF-e/SN
│   │   ├── rD510.ts              # Itens
│   │   ├── rD530.ts              # Consolidação
│   │   ├── rD590.ts              # Registros Analíticos
│   │   ├── rD600.ts              # Consolidação NFS-e (serviços)
│   │   ├── rD610.ts              # Itens
│   │   ├── rD690.ts              # Registros Analíticos
│   │   ├── rD695.ts              # Consolidação NFS-e
│   │   ├── rD696.ts              # NFS-e (detalhamento)
│   │   ├── rD697.ts              # NFS-e (composição)
│   │   ├── rE001.ts              # Abertura Bloco E
│   │   ├── rE100.ts              # ICMS - Operações Próprias
│   │   ├── rE110.ts              # Apuração ICMS
│   │   ├── rE111.ts              # Ajustes da Apuração ICMS
│   │   ├── rE112.ts              # Informações Adicionais
│   │   ├── rE113.ts              # Informações Adicionais (Itens)
│   │   ├── rE115.ts              # Informações Adicionais
│   │   ├── rE116.ts              # Obrigações Recolhidas
│   │   ├── rE200.ts              # ICMS-ST por UF
│   │   ├── rE210.ts              # Apuração ICMS-ST
│   │   ├── rE220.ts              # Ajustes ICMS-ST
│   │   ├── rE230.ts              # Informações Adicionais ICMS-ST
│   │   ├── rE240.ts              # Informações Adicionais ICMS-ST
│   │   ├── rE250.ts              # Obrigações ICMS-ST
│   │   ├── rE300.ts              # DIFAL - Operações Interestaduais
│   │   ├── rE310.ts              # Apuração DIFAL
│   │   ├── rE311.ts              # Ajustes DIFAL
│   │   ├── rE312.ts              # Informações Adicionais DIFAL
│   │   ├── rE313.ts              # Informações Adicionais DIFAL
│   │   ├── rE316.ts              # Obrigações DIFAL
│   │   ├── rE500.ts              # IPI - Operações Próprias
│   │   ├── rE510.ts              # Consolidação IPI
│   │   ├── rE520.ts              # Apuração IPI
│   │   ├── rE521.ts              # Ajustes IPI
│   │   ├── rE530.ts              # Informações Adicionais IPI
│   │   ├── rF001.ts              # Abertura Bloco F
│   │   ├── rF100.ts              # Documentos - Outros
│   │   ├── rF111.ts              # Processo Referenciado
│   │   ├── rF120.ts              # Bens Incorporados
│   │   ├── rF129.ts              # Processo Referenciado
│   │   ├── rF130.ts              # Bens Incorporados (ST)
│   │   ├── rF139.ts              # Processo Referenciado
│   │   ├── rF150.ts              # Crédito Presumido
│   │   ├── rF200.ts              # Operações Ativo Imobilizado
│   │   ├── rF205.ts              # Recuperação de Crédito
│   │   ├── rF210.ts              # Custo/Depreciação
│   │   ├── rF211.ts              # Processo Referenciado
│   │   ├── rF500.ts              # Consolidação Operações Imobilizadas
│   │   ├── rF509.ts              # Processo Referenciado
│   │   ├── rF510.ts              # Consolidação (ST)
│   │   ├── rF519.ts              # Processo Referenciado
│   │   ├── rF525.ts              # Composição da Receita
│   │   ├── rF550.ts              # Consolidação (Custo)
│   │   ├── rF559.ts              # Processo Referenciado
│   │   ├── rF560.ts              # Consolidação (Custo ST)
│   │   ├── rF569.ts              # Processo Referenciado
│   │   ├── rF600.ts              # Retenções na Fonte
│   │   ├── rF700.ts              # Deduções Diversas
│   │   ├── rF800.ts              # Créditos Diversos
│   │   ├── rF990.ts              # Fechamento Bloco F
│   │   ├── rG001.ts              # Abertura Bloco G
│   │   ├── rG110.ts              # Controle do Crédito de ICMS
│   │   ├── rG125.ts              # Movimentação do Crédito
│   │   ├── rG126.ts              # Consolidação
│   │   ├── rG130.ts              # Informações Adicionais
│   │   ├── rG140.ts              # Detalhamento
│   │   ├── rG990.ts              # Fechamento Bloco G
│   │   ├── rH001.ts              # Abertura Bloco H
│   │   ├── rH005.ts              # Inventario Físico
│   │   ├── rH010.ts              # Itens do Inventario
│   │   ├── rH020.ts              # Informações Adicionais
│   │   ├── rH030.ts              # Valores do Inventario
│   │   ├── rH990.ts              # Fechamento Bloco H
│   │   └── r9900.ts              # Registros do Arquivo (totalizadores)
│   │
│   └── efd-icms-ipi/
│       ├── r001.ts               # Abertura Bloco 0
│       ├── r002.ts               # Registros Extemporâneos
│       ├── r100.ts               # Documentos de Importação
│       ├── r101.ts               # Processo Referenciado
│       ├── r110.ts               # Processo Referenciado
│       ├── r111.ts               # Processo Referenciado
│       ├── r112.ts               # Processo Referenciado
│       ├── r113.ts               # Processo Referenciado
│       ├── r114.ts               # Processo Referenciado
│       ├── r115.ts               # Informações Adicionais
│       ├── r116.ts               # Informações Adicionais
│       ├── r120.ts               # Bens Incorporados
│       ├── r129.ts               # Processo Referenciado
│       ├── r130.ts               # Itens de Importação
│       ├── r140.ts               # Detalhamento
│       ├── r150.ts               # Documento de Importação
│       ├── r190.ts               # Registros Analíticos
│       ├── r191.ts               # Informações Adicionais
│       ├── r195.ts               # Informações Adicionais
│       ├── r197.ts               # Detalhamento
│       ├── r200.ts               # Identificação do Documento
│       ├── r201.ts               # Itens do Documento
│       ├── r205.ts               # Consolidação
│       ├── r210.ts               # Registros Analíticos
│       ├── r211.ts               # Processo Referenciado
│       ├── r220.ts               # Resumo Diário
│       ├── r221.ts               # Itens
│       ├── r230.ts               # Detalhamento
│       ├── r231.ts               # Itens
│       ├── r235.ts               # Itens
│       ├── r240.ts               # Consolidação NFS-e
│       ├── r241.ts               # NFS-e (detalhamento)
│       ├── r250.ts               # Resumo Diário NFS-e
│       ├── r251.ts               # NFS-e (Itens)
│       ├── r255.ts               # NFS-e (composição)
│       ├── r300.ts               # Resumo Diário (NFC-e)
│       ├── r310.ts               # Detalhamento
│       ├── r320.ts               # Consolidação
│       ├── r350.ts               # Resumo Diário (ECF)
│       ├── r370.ts               # Composição do Frete
│       ├── r380.ts               # Detalhamento
│       ├── r390.ts               # Registros Analíticos
│       ├── r400.ts               # Resumo NFS-e
│       ├── r410.ts               # Itens NFS-e
│       ├── r420.ts               # Valores NFS-e
│       ├── r500.ts               # Documentos de Saída
│       ├── r510.ts               # Itens de Saída
│       ├── r530.ts               # Consolidação de Saída
│       ├── r590.ts               # Registros Analíticos (saída)
│       ├── r600.ts               # Consolidação NFS-e (serviços)
│       ├── r610.ts               # NFS-e (Itens)
│       ├── r690.ts               # Registros Analíticos (serviços)
│       ├── r695.ts               # Consolidação NFS-e
│       ├── r696.ts               # NFS-e (detalhamento)
│       ├── r697.ts               # NFS-e (composição)
│       ├── r700.ts               # Resumo NFS-e (serviços)
│       ├── r701.ts               # NFS-e (Itens)
│       ├── r720.ts               # Resumo NFS-e (composição)
│       ├── r730.ts               # Resumo NFS-e (detalhamento)
│       ├── r731.ts               # NFS-e (Itens)
│       ├── r735.ts               # Resumo NFS-e (composição)
│       ├── r737.ts               # NFS-e (Itens)
│       ├── r750.ts               # Consolidação NFS-e
│       ├── r751.ts               # NFS-e (Itens)
│       ├── r760.ts               # Resumo NFS-e
│       ├── r761.ts               # NFS-e (Itens)
│       ├── r900.ts               # Apuração do ICMS
│       ├── r990.ts               # Fechamento Bloco 0 (EFD)
│       └── r9900.ts              # Registros do Arquivo
│
├── generators/
│   ├── ecd-generator.ts          # ECD orchestrator
│   ├── ecf-generator.ts          # ECF orchestrator
│   ├── efd-contribuicoes.ts      # EFD-Contribuições orchestrator
│   └── efd-icms-ipi.ts           # EFD-ICMS/IPI orchestrator
│
└── utils/
    ├── cnpf-cnpj.ts             # CNPJ/CPF validation and formatting
    ├── date-utils.ts            # Date formatting for SPED (YYYYMMDD)
    ├── numeric-utils.ts         # Numeric formatting (point decimal, no thousands)
    └── string-utils.ts          # Pipe delimiter, escape, truncation
```

---

## 2. Record Format Specification

### 2.1 Universal Format Rules

| Rule | Value |
|------|-------|
| **Delimiter** | Pipe `\|` (U+007C) |
| **Line terminator** | `\r\n` (CRLF) |
| **Encoding** | ISO-8859-1 (Latin-1) — not UTF-8 |
| **First line** | Record `0000` (header) |
| **Last line** | Record `9999` (totalization) |
| **Field order** | Strictly sequential per layout table |
| **Empty fields** | Empty string between pipes: `\|\|` |
| **Trailing delimiter** | NO trailing pipe at end of line |
| **Field positions** | 1-based, zero-padded for numeric, left-padded for codes |

### 2.2 Field Type Formatting

```typescript
// field-formatter.ts

function formatField(value: any, field: SpedField): string {
  if (value === null || value === undefined || value === '') {
    if (field.required) throw new SpedError(`Required field ${field.name} is empty`);
    return '';  // empty = between pipes
  }

  switch (field.type) {
    case 'date':
      // Format: YYYYMMDD (e.g. "20260701")
      return formatDate(value, 'YYYYMMDD');

    case 'numeric':
      // Format: integer part + "," + 2 decimal places (Brazilian convention)
      // No thousands separator, no currency symbol
      // Example: 1234567.89 → "1234567,89"
      // Example: 0.00 → "0,00"
      return formatNumeric(value, field.max_length);

    case 'code':
      // Alphanumeric, trimmed to max_length
      return String(value).trim().substring(0, field.max_length);

    case 'text':
      // Text, trimmed, no pipe characters allowed
      return String(value).trim()
        .replace(/\|/g, '')     // strip pipes
        .substring(0, field.max_length);

    default:
      return String(value);
  }
}

function formatNumeric(value: number, maxLength: number): string {
  // SPED uses Brazilian decimal format: comma for decimal, no thousands sep
  // Two decimal places always
  const formatted = value.toFixed(2).replace('.', ',');
  return formatted;
}

function formatDate(date: Date | string, format: string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}${mm}${dd}`;
}
```

### 2.3 Numeric Field Constraints

| SPED Type | Description | Format |
|-----------|-------------|--------|
| `N` | Numeric (integer or decimal) | Comma decimal, 2 places default |
| `V` | Value (monetary) | Comma decimal, 2 places |
| `C` | Code (alphanumeric) | Trimmed to max_length |
| `D` | Date | YYYYMMDD |
| `AN` | Alphanumeric | Trimmed to max_length |

**Examples**:
- `00000,00` → zero value
- `1234567,89` → R$ 1.234.567,89
- `20260701` → July 1, 2026
- `1.1.01.001` → account code (dots preserved)

---

## 3. ECD — Escrituração Contábil Digital

### 3.1 Block Structure

| Block | Name | Records | Purpose |
|-------|------|---------|---------|
| **0** | Abertura e Identificação | 0000, 0001, 0990 | File header, opening identification |
| **A** | Documentos Fiscais | A001, A990 | Fiscal documents (not used in ECD) |
| **C** | Documentos Fiscais - Mercadorias | C001, C990 | Not used in ECD |
| **D** | Documentos Fiscais - Serviços | D001, D990 | Not used in ECD |
| **E** | Apuração do IRPJ/CSLL | E001, E100-E990 | Tax base calculation |
| **G** | Controle de Crédito de ICMS | G001, G990 | ICMS credit control |
| **H** | Inventário Físico | H001, H005, H010, H990 | Physical inventory |
| **I** | Escrituração Contábil | I001, I200, I300, I350, I500, I510, I600, I990 | GL entries, trial balance, DRE |
| **J** | Demonstrações Contábeis | J001, J100, J150, J900, J990 | Financial statements |
| **9** | Totalização | 9900, 9990, 9999 | File totals, hash |

### 3.2 Record 0000 — Abertura do Arquivo

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `COD_VER` | N | 3 | Version: `003` (ECF) or `006` (ECD) |
| 2 | `COD_FIN` | N | 1 | Finalidade: `00`=Orig, `01`=Subst, `02`=1a Subst, `03`=Corr |
| 3 | `DT_INIC` | D | 8 | Data início: YYYYMMDD |
| 4 | `DT_FIN` | D | 8 | Data fim: YYYYMMDD |
| 5 | `NOME` | AN | 100 | Nome Empresarial |
| 6 | `CNPJ` | N | 14 | CNPJ |
| 7 | `UF` | AN | 2 | UF (sigla) |
| 8 | `COD_MUN` | N | 7 | Código IBGE município |
| 9 | `IM` | AN | 14 | Inscrição Municipal |
| 10 | `IE` | AN | 14 | Inscrição Estadual |
| 11 | `COD_FIN` | N | 1 | Finalidade: `00`=Orig, `01`=Subst, `02`=1a Subst, `03`=Corr |
| 12 | `IND_SIT_ESP` | N | 1 | `0`=Normal, `1`=Extinta, `2`=Fusão, `3`=Incorporação |
| 13 | `NUM_REC_ANTERIOR` | AN | 41 | Número Recibo Anterior (if substituting) |
| 14 | `IND_NAT_PJ` | N | 1 | Natureza Jurídica |
| 15 | `IND_ATIV` | N | 1 | Atividade Preponderante |
| 16 | `NUM_REC` | AN | 41 | Número Recibo Entrega |

**Data sources**:
- `COD_VER`, `COD_FIN`, `DT_INIC`, `DT_FIN`: from generation request
- `NOME`, `CNPJ`, `UF`, `COD_MUN`, `IM`, `IE`: from company config (`gl_companies`)
- `IND_SIT_ESP`: from company status (normal/liquidated/merged)
- `NUM_REC_ANTERIOR`: from previous ECD file record
- `IND_NAT_PJ`, `IND_ATIV`: from CNPJ lookup (BrasilAPI)

### 3.3 Record 0150 — Participantes

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `COD_PART` | AN | 60 | Código do Participante |
| 2 | `NOME` | AN | 100 | Nome/Razão Social |
| 3 | `COD_PAIS` | N | 5 | Código País (BACEN) |
| 4 | `CNPJ` | N | 14 | CNPJ |
| 5 | `CPF` | N | 11 | CPF |
| 6 | `IE` | AN | 14 | Inscrição Estadual |
| 7 | `COD_MUN` | N | 7 | Código IBGE |
| 8 | `SUFRAMA` | AN | 9 | Inscrição SUFRAMA |
| 9 | `ENDereco` | AN | 60 | Logradouro |
| 10 | `NUM` | AN | 10 | Número |
| 11 | `COMPL` | AN | 60 | Complemento |
| 12 | `BAIRRO` | AN | 60 | Bairro |

**Data sources**: `gl_participants` table (extracted from AP/AR/NFe vendor/customer data)

### 3.4 Record 0500 — Plano de Contas

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `DT_ALT` | D | 8 | Data Alteração |
| 2 | `COD_NAT_CC` | AN | 2 | Natureza: `A`=Ativo, `B`=Passivo, `C`=Patrimônio Líq., `D`=Resultado, `E`=Compensação, `F`=Receita, `G`=Despesa |
| 3 | `IND_CTA` | AN | 1 | `A`=Analítica, `S`=Sintética |
| 4 | `Nivel` | N | 5 | Nível (1-6) |
| 5 | `COD_CTA` | AN | 60 | Código da Conta |
| 6 | `NOME` | NOME | 100 | Nome da Conta |

**Data sources**: `gl_accounts` table, mapped to SPED `COD_NAT_CC` categories:
- `asset` → `A`
- `liability` → `B`
- `equity` → `C`
- `revenue` → `F`
- `expense` → `G`

### 3.5 Record I200 — Razão (Lançamentos Contábeis)

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `DT_LANC` | D | 8 | Data do Lançamento |
| 2 | `COD_CTA_DEB` | AN | 60 | Código Conta Débito |
| 3 | `COD_CTA_CRED` | AN | 60 | Código Conta Crédito |
| 4 | `VL_LANC` | N | 21,2 | Valor do Lançamento |
| 5 | `HIST` | AN | 200 | Histórico |
| 6 | `COD_PART` | AN | 60 | Código Participante (optional) |

**Data sources**: `gl_journal_entry_lines` joined with `gl_journal_entries` and `gl_accounts`, filtered by period

### 3.6 Record I350 — Balancetes de Verificação

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `DT_BCO` | D | 8 | Data do Balancete |
| 2 | `COD_CTA` | AN | 60 | Código da Conta |
| 3 | `SALDO_INI` | N | 21,2 | Saldo Inicial (D=positivo, C=negativo) |
| 4 | `DEB` | N | 21,2 | Débitos |
| 5 | `CRED` | N | 21,2 | Créditos |
| 6 | `SALDO_FIN` | N | 21,2 | Saldo Final |

**Data sources**: `mv_account_balances` materialized view, per account per period

### 3.7 Record I500 — Balanço Patrimonial

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `DT_BCO` | D | 8 | Data de Referência |
| 2 | `IND_TIP_BCO` | N | 1 | Tipo: `0`=Mensal, `1`=Anual |
| 3 | `NIVEL` | AN | 1 | Nível do BP |
| 4 | `COD_CTA` | AN | 60 | Código da Conta |
| 5 | `NOME_CTA` | AN | 100 | Nome da Conta |
| 6 | `VL_CTA` | N | 21,2 | Valor da Conta |

**Data sources**: GL balances at period end, grouped by account hierarchy level

### 3.8 Record I510 — DRE (Demonstração do Resultado)

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `DT_BCO` | D | 8 | Data de Referência |
| 2 | `IND_TIP_BCO` | N | 1 | Tipo: `0`=Mensal, `1`=Anual |
| 3 | `NIVEL` | AN | 1 | Nível da DRE |
| 4 | `COD_CTA` | AN | 60 | Código da Conta |
| 5 | `NOME_CTA` | AN | 100 | Nome da Conta |
| 6 | `VL_CTA` | N | 21,2 | Valor da Conta |

**Data sources**: Revenue and expense accounts from GL, structured per DRE layout:
- Receita Bruta (revenue accounts)
- (-) Deduções da Receita (taxes on revenue, returns)
- (=) Receita Líquida
- (-) Custos dos Serviços/Produtos
- (=) Lucro Bruto
- (-) Despesas Operacionais
- (=) EBITDA
- (-) Depreciação/Amortização
- (=) LAIR
- (-) IRPJ/CSLL
- (=) Lucro Líquido

### 3.9 Record 9999 — Totalização do Arquivo

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `QTD_LIN` | N | 20 | Quantidade total de linhas |

**Data sources**: Count of all records in file (including header and totalization)

---

## 4. ECF — Escrituração Contábil Fiscal

### 4.1 Block Structure

| Block | Name | Records | Purpose |
|-------|------|---------|---------|
| **0** | Abertura e Identificação | 0000, 0001, 0300, 0305, 0400, 0460, 0500, 0600, 0990 | Header, tables, tables |
| **A** | Documentos Fiscais - Receita | A001, A010, A100, A111, A120, A170, A990 | Service invoices (NF-e service) |
| **C** | Documentos Fiscais - Mercadorias | C001, C100, C170, C180, C190, C380, C390, C400, C405, C420, C425, C490, C495, C800, C810, C820, C860, C870, C880, C890, C990 | Merchandise NF-e, NFC-e, ECF |
| **D** | Documentos Fiscais - Serviços | D001, D100, D101, D190, D300, D350, D355, D360, D370, D390, D400, D410, D411, D420, D500, D510, D530, D590, D600, D610, D690, D695, D696, D697, D990 | CT-e, NFS-e |
| **E** | Apuração do ICMS/IPI | E001, E100-E990 | Tax apuração |
| **F** | Controle de Crédito | F001, F100-F990 | Fixed assets, credit control |
| **G** | Controle de Crédito de ICMS | G001, G990 | ICMS credit |
| **H** | Inventário Físico | H001, H005, H010, H020, H030, H990 | Physical inventory |
| **I** | Demais Documentos e Operações | I001, I990 | Other documents |
| **K** | Controle de Saldos de Apuração | K001, K010, K100, K200, K210, K215, K220, K230, K235, K250, K255, K260, K265, K270, K275, K280, K290, K291, K292, K300, K301, K302, K990 | Inventory control |
| **1** | Composição da Receita | 1001, 1010, 1990 | Revenue composition |
| **9** | Totalização | 9001, 9900, 9990, 9999 | File totals |

### 4.2 Record C100 — Documento NF-e

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `IND_OPER` | AN | 1 | `0`=Entrada, `1`=Saída |
| 2 | `IND_EMIT` | AN | 1 | `0`=Própria, `1`=Terceiros |
| 3 | `COD_PART` | AN | 60 | Código Participante |
| 4 | `COD_MOD` | AN | 2 | Modelo Documento: `55`=NF-e, `65`=NFC-e |
| 5 | `SER` | AN | 3 | Série |
| 6 | `SUB` | N | 3 | Subsérie |
| 7 | `NUM_DOC` | N | 9 | Número Documento |
| 8 | `DT_DOC` | D | 8 | Data Emissão |
| 9 | `DT_E_S` | D | 8 | Data Entrada/Saída |
| 10 | `VL_DOC` | N | 21,2 | Valor Documento |
| 11 | `IND_PGTO` | AN | 1 | Forma Pagamento: `0`=Pgto Vista, `1`=Pgto Prazo, `2`=Outros |
| 12 | `VL_DESC` | N | 21,2 | Valor Desconto |
| 13 | `VL_ABAT_NTRIB` | N | 21,2 | Abatimento Não Tributado |
| 14 | `VL_MERC` | N | 21,2 | Valor Mercadorias |
| 15 | `IND_FRT` | AN | 1 | Frete: `0`=Por Conta Destinatário, `1`=Por Conta Emitente |
| 16 | `VL_SEG` | N | 21,2 | Valor Seguro |
| 17 | `VL_OUTR_DESP` | N | 21,2 | Outras Despesas Acessórias |
| 18 | `VL_BC_ICMS` | N | 21,2 | Base Cálculo ICMS |
| 19 | `VL_ICMS` | N | 21,2 | Valor ICMS |
| 20 | `VL_ICMS_ST` | N | 21,2 | Valor ICMS-ST |
| 21 | `VL_IPI` | N | 21,2 | Valor IPI |
| 22 | `VL_PIS` | N | 21,2 | Valor PIS |
| 23 | `VL_COFINS` | N | 21,2 | Valor COFINS |

**Data sources**: `nfe_documents` joined with `gl_journal_entry_lines` (subledger_type = 'nfe')

### 4.3 Record C170 — Itens do Documento

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `NUM_ITEM` | N | 3 | Número Item |
| 2 | `COD_ITEM` | AN | 60 | Código Item |
| 3 | `DESCR_COMPL` | AN | 120 | Descrição Complementar |
| 4 | `QTD` | N | 12,6 | Quantidade |
| 5 | `UNID` | AN | 6 | Unidade |
| 6 | `VL_ITEM` | N | 21,2 | Valor Item |
| 7 | `VL_DESC` | N | 21,2 | Desconto |
| 8 | `IND_MOV` | AN | 1 | `0`=Sim, `1`=Não |
| 9 | `CST_ICMS` | AN | 3 | CST ICMS |
| 10 | `CFOP` | N | 4 | CFOP |
| 11 | `COD_NAT` | AN | 10 | Natureza da Operação |
| 12 | `VL_BC_ICMS` | N | 21,2 | Base Cálculo ICMS |
| 13 | `ALIQ_ICMS` | N | 6,2 | Alíquota ICMS |
| 14 | `VL_ICMS` | N | 21,2 | Valor ICMS |
| 15 | `VL_BC_ICMS_ST` | N | 21,2 | Base Cálculo ICMS-ST |
| 16 | `ALIQ_ICMS_ST` | N | 6,2 | Alíquota ICMS-ST |
| 17 | `VL_ICMS_ST` | N | 21,2 | Valor ICMS-ST |
| 18 | `VL_BC_IPI` | N | 21,2 | Base Cálculo IPI |
| 19 | `ALIQ_IPI` | N | 6,2 | Alíquota IPI |
| 20 | `VL_IPI` | N | 21,2 | Valor IPI |
| 21 | `CST_PIS` | AN | 2 | CST PIS |
| 22 | `VL_BC_PIS` | N | 21,2 | Base Cálculo PIS |
| 23 | `ALIQ_PIS` | N | 6,2 | Alíquota PIS |
| 24 | `VL_PIS` | N | 21,2 | Valor PIS |
| 25 | `CST_COFINS` | AN | 2 | CST COFINS |
| 26 | `VL_BC_COFINS` | N | 21,2 | Base Cálculo COFINS |
| 27 | `ALIQ_COFINS` | N | 6,2 | Alíquota COFINS |
| 28 | `VL_COFINS` | N | 21,2 | Valor COFINS |

**Data sources**: `nfe_items` (NF-e line items) with tax breakdown

### 4.4 Record E110 — Apuração do ICMS Operações Próprias

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `VL_TOT_DEBITOS` | N | 21,2 | Total Débitos |
| 2 | `VL_AJ_DEBITOS` | N | 21,2 | Ajustes Débitos |
| 3 | `VL_TOT_AJ_DEBITOS` | N | 21,2 | Total Ajustes Débitos |
| 4 | `VL_ESTORNOS_DEB` | N | 21,2 | Estornos Débitos |
| 5 | `VL_TOT_CREDITOS` | N | 21,2 | Total Créditos |
| 6 | `VL_AJ_CREDITOS` | N | 21,2 | Ajustes Créditos |
| 7 | `VL_TOT_AJ_CREDITOS` | N | 21,2 | Total Ajustes Créditos |
| 8 | `VL_ESTORNOS_CRED` | N | 21,2 | Estornos Créditos |
| 9 | `VL_SLD_CREDOR_ANT` | N | 21,2 | Saldo Credor Anterior |
| 10 | `VL_SLD_APURADO` | N | 21,2 | Saldo Apurado (= C - D + CAj - DAj + SCred - SEstC + SEstD) |
| 11 | `VL_TOT_DED` | N | 21,2 | Total Deduções |
| 12 | `VL_ICMS_RECOLHER` | N | 21,2 | ICMS a Recolher (= SLD - DED) |
| 13 | `VL_SLD_CREDOR_TRANSPORTAR` | N | 21,2 | Saldo Credor a Transportar |
| 14 | `DEB_ESP` | N | 21,2 | Débitos Especiais |

**Data sources**: Aggregation from `nfe_documents` + `nfe_items` grouped by CFOP:
- Debit side: CFOP 1xxx, 2xxx, 3xxx, 5xxx, 6xxx (saídas)
- Credit side: CFOP 1xxx, 2xxx, 3xxx (entradas)

### 4.5 Record E200/E210 — ICMS-ST

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| E200:1 | `UF` | AN | 2 | UF de destino |
| E200:2 | `DT_INIC` | D | 8 | Data início |
| E200:3 | `DT_FIN` | D | 8 | Data fim |
| E210:1 | `IND_MOV_ST` | N | 1 | `0`=Sem movimento, `1`=Com movimento |
| E210:2 | `VL_SLD_CRED_ANT_ST` | N | 21,2 | Saldo Credor Anterior ST |
| E210:3 | `VL_DEVOL_ST` | N | 21,2 | Devoluções ST |
| E210:4 | `VL_RESSARC_ST` | N | 21,2 | Ressarcimentos ST |
| E210:5 | `VL_OUT_CRED_ST` | N | 21,2 | Outros Créditos ST |
| E210:6 | `VL_AJ_CREDITOS_ST` | N | 21,2 | Ajustes Créditos ST |
| E210:7 | `VL_RETENCAO_ST` | N | 21,2 | Retenções ST |
| E210:8 | `VL_OUT_DEB_ST` | N | 21,2 | Outros Débitos ST |
| E210:9 | `VL_AJ_DEBITOS_ST` | N | 21,2 | Ajustes Débitos ST |
| E210:10 | `VL_SLD_DEV_ANT_ST` | N | 21,2 | Saldo Devedor Anterior ST |
| E210:11 | `VL_DEDUCAO_ST` | N | 21,2 | Deduções ST |
| E210:12 | `VL_ICMS_RECOL_ST` | N | 21,2 | ICMS a Recolher ST |
| E210:13 | `VL_SLD_CRED_ST_TRANSPORTAR` | N | 21,2 | Saldo Credor ST Transportar |
| E210:14 | `DEB_ESP_ST` | N | 21,2 | Débitos Especiais ST |

**Data sources**: NFe items with ICMS-ST (CST 10, 30, 40, 50, 60, 70, 90), grouped by UF

### 4.6 Record E500/E520 — IPI

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| E500:1 | `IND_APUR_IPI` | N | 1 | `0`=Mensal, `1`=Trimensal |
| E500:2 | `DT_INIC` | D | 8 | Data início |
| E500:3 | `DT_FIN` | D | 8 | Data fim |
| E520:1 | `VL_SD_ANT_IPI` | N | 21,2 | Saldo Anterior IPI |
| E520:2 | `VL_DEB_IPI` | N | 21,2 | Débitos IPI |
| E520:3 | `VL_CRED_IPI` | N | 21,2 | Créditos IPI |
| E520:4 | `VL_OD_IPI` | N | 21,2 | Outros Débitos IPI |
| E520:5 | `VL_OC_IPI` | N | 21,2 | Outros Créditos IPI |
| E520:6 | `VL_SC_IPI` | N | 21,2 | Saldo Credor IPI |
| E520:7 | `VL_SD_IPI` | N | 21,2 | Saldo Devedor IPI (= DEB + OD - CRED - OC + SD_ANT) |
| E520:8 | `VL_REC_IPI` | N | 21,2 | IPI a Recolher |

**Data sources**: NFe items with IPI (IPI applies to industrial products), grouped by CST_IPI

---

## 5. EFD-Contribuições — PIS/COFINS

### 5.1 Block Structure

| Block | Name | Records | Purpose |
|-------|------|---------|---------|
| **0** | Abertura e Identificação | 0000, 0001, 0990 | Header |
| **A** | Documentos Fiscais - Receita | A001, A010, A100, A110, A111, A112, A120, A170, A990 | Service invoices |
| **C** | Documentos Fiscais - Mercadorias | C001, C100, C101, C105, C110, C111, C112, C113, C114, C116, C120, C130, C160, C165, C170, C171, C172, C173, C174, C175, C176, C177, C178, C179, C180, C181, C182, C183, C185, C186, C188, C190, C191, C195, C197, C380, C381, C382, C385, C395, C396, C400, C405, C481, C485, C489, C490, C491, C495, C499, C800, C810, C815, C850, C855, C857, C860, C870, C880, C890, C895, C897, C990 | NF-e merchandise |
| **D** | Documentos Fiscais - Serviços | D001, D100, D101, D105, D111, D200, D201, D205, D209, D300, D309, D350, D359, D360, D365, D370, D390, D400, D410, D411, D420, D500, D501, D505, D509, D600, D601, D605, D609, D695, D696, D697, D990 | CT-e, NFS-e |
| **F** | Demais Documentos e Operações | F001, F010, F100, F111, F120, F129, F130, F139, F150, F200, F205, F210, F211, F500, F509, F510, F519, F525, F550, F559, F560, F569, F600, F700, F800, F990 | Other documents, fixed assets |
| **M** | Apuração da Contribuição | M001, M100, M105, M110, M115, M200, M205, M210, M211, M215, M220, M225, M230, M300, M350, M400, M410, M500, M505, M510, M515, M600, M605, M610, M611, M615, M620, M625, M630, M700, M800, M810, M990 | PIS/COFINS apuração |
| **P** | Apuração da Contribuição (Simples) | P001, P100, P110, P199, P200, P210, P990 | Simples Nacional |
| **1** | Composição da Receita | 1001, 1010, 1011, 1020, 1050, 1100, 1101, 1102, 1200, 1210, 1220, 1300, 1500, 1510, 1600, 1700, 1800, 1809, 1810, 1900, 1910, 1920, 1921, 1922, 1923, 1925, 1926, 1960, 1970, 1975, 1980, 1990 | Revenue composition |
| **9** | Totalização | 9001, 9900, 9990, 9999 | Totals |

### 5.2 Record M100 — Crédito de PIS/PASEP

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `COD_CRED` | N | 3 | Código de Crédito: `101`=Não Cumulativo (Produção), `102`=Não Cumulativo (Revenda), `103`=Não Cumulativo (Agricultura), `104`=Não Cumulativo (Outros), `201`=Cumulativo (Produção), `202`=Cumulativo (Revenda), `203`=Cumulativo (Agricultura), `204`=Cumulativo (Outros) |
| 2 | `IND_CRED_ORI` | N | 1 | Indicador Origem: `0`=Operação Própria, `1`=Rateio |
| 3 | `VL_BC_PIS` | N | 21,2 | Base Cálculo PIS |
| 4 | `ALIQ_PIS` | N | 8,4 | Alíquota PIS |
| 5 | `QUANT_BC_PIS` | N | 21,6 | Quantidade (if by quantity) |
| 6 | `ALIQ_PIS_QUANT` | N | 21,6 | Alíquota PIS (quantity) |
| 7 | `VL_CRED` | N | 21,2 | Valor Crédito (= BC × Alíquota or Qtd × Alíq) |
| 8 | `VL_AJ_USOS` | N | 21,2 | Ajustes de Uso |
| 9 | `VL_CRED_AJ` | N | 21,2 | Ajustes de Crédito |
| 10 | `VL_CRED_DIFER` | N | 21,2 | Crédito a Diferir |
| 11 | `VL_CRED_DISP` | N | 21,2 | Crédito Disponível |
| 12 | `IND_DESC_CRED` | N | 1 | `0`=Integral, `1`=Parcial |
| 13 | `VL_CRED_DESC` | N | 21,2 | Crédito Utilizado (descontado) |
| 14 | `SLD_CRED` | N | 21,2 | Saldo Credor |

**Data sources**: NFe items (entries) with PIS credit codes:
- Non-cumulative regime: PIS 1.65% on purchases
- Cumulative regime: PIS 0.65% on purchases

### 5.3 Record M200 — Consolidação da Contribuição para o PIS/PASEP

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `VL_TOT_CONT_NC_PER` | N | 21,2 | Total Contribuição NC (débito normal) |
| 2 | `VL_TOT_CRED_DESC` | N | 21,2 | Total Créditos Descontados |
| 3 | `VL_TOT_CRED_DESC_ANT` | N | 21,2 | Total Créditos Anteriores |
| 4 | `VL_TOT_CONT_NC_DEV` | N | 21,2 | Total Contribuição NC (devoluções) |
| 5 | `VL_RET_NC` | N | 21,2 | Retenções NC |
| 6 | `VL_OUT_DED_NC` | N | 21,2 | Outras Deduções NC |
| 7 | `VL_CONT_NC_REC` | N | 21,2 | Contribuição NC a Recolher |
| 8 | `VL_TOT_CONT_CUM_PER` | N | 21,2 | Total Contribuição Cumulativa |
| 9 | `VL_RET_CUM` | N | 21,2 | Retenções Cumulativas |
| 10 | `VL_OUT_DED_CUM` | N | 21,2 | Outras Deduções Cumulativas |
| 11 | `VL_CONT_CUM_REC` | N | 21,2 | Contribuição Cumulativa a Recolher |
| 12 | `VL_TOT_CONT_REC` | N | 21,2 | Total Contribuição a Recolher |

**Data sources**: Sum of M100 credits, plus output PIS from sales (C100 documents, CFOP 5xxx/6xxx)

### 5.4 Record M500 — Crédito de COFINS

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `COD_CRED` | N | 3 | Código de Crédito: `301`=Não Cumulativo, `302`=Cumulativo, `303`=Não Cumulativo (Importação), `304`=Cumulativo (Importação) |
| 2 | `IND_CRED_ORI` | N | 1 | Indicador Origem |
| 3 | `VL_BC_COFINS` | N | 21,2 | Base Cálculo COFINS |
| 4 | `ALIQ_COFINS` | N | 8,4 | Alíquota COFINS |
| 5 | `QUANT_BC_COFINS` | N | 21,6 | Quantidade |
| 6 | `ALIQ_COFINS_QUANT` | N | 21,6 | Alíquota COFINS (quantity) |
| 7 | `VL_CRED` | N | 21,2 | Valor Crédito |
| 8 | `VL_AJ_USOS` | N | 21,2 | Ajustes de Uso |
| 9 | `VL_CRED_AJ` | N | 21,2 | Ajustes de Crédito |
| 10 | `VL_CRED_DIFER` | N | 21,2 | Crédito a Diferir |
| 11 | `VL_CRED_DISP` | N | 21,2 | Crédito Disponível |
| 12 | `IND_DESC_CRED` | N | 1 | `0`=Integral, `1`=Parcial |
| 13 | `VL_CRED_DESC` | N | 21,2 | Crédito Utilizado |
| 14 | `SLD_CRED` | N | 21,2 | Saldo Credor |

**Data sources**: Same as M100 but for COFINS:
- Non-cumulative regime: COFINS 7.6% on purchases
- Cumulative regime: COFINS 3.0% on purchases

### 5.5 Record M600 — Consolidação da Contribuição para a Seguridade Social - COFINS

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 1 | `VL_TOT_CONT_NC_PER` | N | 21,2 | Total Contribuição NC |
| 2 | `VL_TOT_CRED_DESC` | N | 21,2 | Total Créditos Descontados |
| 3 | `VL_TOT_CRED_DESC_ANT` | N | 21,2 | Total Créditos Anteriores |
| 4 | `VL_TOT_CONT_NC_DEV` | N | 21,2 | Total Contribuição NC (devoluções) |
| 5 | `VL_RET_NC` | N | 21,2 | Retenções NC |
| 6 | `VL_OUT_DED_NC` | N | 21,2 | Outras Deduções NC |
| 7 | `VL_CONT_NC_REC` | N | 21,2 | Contribuição NC a Recolher |
| 8 | `VL_TOT_CONT_CUM_PER` | N | 21,2 | Total Contribuição Cumulativa |
| 9 | `VL_RET_CUM` | N | 21,2 | Retenções Cumulativas |
| 10 | `VL_OUT_DED_CUM` | N | 21,2 | Outras Deduções Cumulativas |
| 11 | `VL_CONT_CUM_REC` | N | 21,2 | Contribuição Cumulativa a Recolher |
| 12 | `VL_TOT_CONT_REC` | N | 21,2 | Total Contribuição a Recolher |

**Data sources**: Same structure as M200 but for COFINS values

### 5.6 PIS/COFINS Rate Summary

| Regime | Tax | Rate | When |
|--------|-----|------|------|
| Não-cumulativo | PIS | 1.65% | Industrial/resale companies |
| Não-cumulativo | COFINS | 7.60% | Industrial/resale companies |
| Cumulativo | PIS | 0.65% | Service companies, small business |
| Cumulativo | COFINS | 3.00% | Service companies, small business |
| Importação | PIS | 1.65% | Import operations |
| Importação | COFINS | 7.60% | Import operations |

---

## 6. EFD-ICMS/IPI

### 6.1 Block Structure

| Block | Name | Records | Purpose |
|-------|------|---------|---------|
| **0** | Abertura e Identificação | 0001, 0002, 0005, 0015, 0100, 0200, 0220, 0300, 0305, 0400, 0450, 0460, 0465, 0470, 0500, 0510, 0600, 0990 | Header, tables |
| **C** | Documentos Fiscais - Mercadorias | C001, C100, C101, C105, C110, C111, C112, C113, C114, C116, C120, C130, C140, C141, C160, C165, C170, C171, C172, C173, C174, C175, C176, C177, C178, C179, C180, C181, C182, C183, C185, C186, C188, C190, C191, C195, C197, C380, C381, C382, C385, C395, C396, C400, C405, C481, C485, C489, C490, C491, C495, C499, C500, C501, C505, C509, C600, C601, C605, C609, C700, C790, C791, C800, C810, C815, C850, C855, C857, C860, C870, C880, C890, C895, C897, C900, C990 | NF-e merchandise |
| **D** | Documentos Fiscais - Serviços | D001, D100, D101, D105, D111, D200, D201, D205, D209, D300, D309, D350, D359, D360, D365, D370, D390, D400, D410, D411, D420, D500, D501, D505, D509, D600, D601, D605, D609, D695, D696, D697, D990 | CT-e, NFS-e |
| **E** | Apuração do ICMS e do IPI | E001, E100, E110, E111, E112, E113, E115, E116, E200, E210, E220, E230, E240, E250, E300, E310, E311, E312, E313, E316, E500, E510, E520, E521, E530, E990 | ICMS/IPI apuração |
| **G** | Controle do Crédito de ICMS do Ativo Permanente | G001, G110, G125, G126, G130, G140, G990 | Fixed assets ICMS credit |
| **H** | Inventário Físico | H001, H005, H010, H020, H030, H990 | Physical inventory |
| **K** | Controle de Saldos de Apuração do ICMS e do IPI | K001, K010, K100, K200, K210, K215, K220, K230, K235, K250, K255, K260, K265, K270, K275, K280, K290, K291, K292, K300, K301, K302, K990 | Inventory control |
| **1** | Composição da Receita | 1001, 1010, 1011, 1020, 1050, 1100, 1101, 1102, 1200, 1210, 1220, 1300, 1500, 1510, 1600, 1700, 1800, 1809, 1810, 1900, 1910, 1920, 1921, 1922, 1923, 1925, 1926, 1960, 1970, 1975, 1980, 1990 | Revenue composition |
| **9** | Totalização | 9001, 9900, 9990, 9999 | Totals |

### 6.2 Record C100 — Nota Fiscal (EFD-ICMS/IPI)

Same structure as ECF C100 (Section 4.2), but with additional EFD-specific fields:

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 24 | `VL_BC_ICMS_ST` | N | 21,2 | Base Cálculo ICMS-ST |
| 25 | `VL_ICMS_ST` | N | 21,2 | Valor ICMS-ST |
| 26 | `VL_IPI` | N | 21,2 | Valor IPI |
| 27 | `VL_PIS` | N | 21,2 | Valor PIS |
| 28 | `VL_COFINS` | N | 21,2 | Valor COFINS |

**Data sources**: `nfe_documents` with state-specific tax breakdown

### 6.3 Record E110 — Apuração ICMS Operações Próprias

Same as ECF E110 (Section 4.4), but with additional fields for EFD-ICMS/IPI:

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| 14 | `DEB_ESP` | N | 21,2 | Débitos Especiais |
| 15 | `VL_AJ_DEBITOS_AJ` | N | 21,2 | Ajustes Débitos (Ajustes Apuração) |
| 16 | `VL_AJ_CREDITOS_AJ` | N | 21,2 | Ajustes Créditos (Ajustes Apuração) |
| 17 | `VL_RETENCAO` | N | 21,2 | Retenções |
| 18 | `VL_OUT_DEB` | N | 21,2 | Outros Débitos |
| 19 | `VL_OUT_CRED` | N | 21,2 | Outros Créditos |
| 20 | `VL_SLD_DEV_ANT` | N | 21,2 | Saldo Devedor Anterior |
| 21 | `VL_DEDUCAO` | N | 21,2 | Deduções |
| 22 | `VL_ICMS_RECOL` | N | 21,2 | ICMS a Recolher |
| 23 | `VL_SLD_CRED_TRANSPORTAR` | N | 21,2 | Saldo Credor Transportar |
| 24 | `DEB_ESP` | N | 21,2 | Débitos Especiais |

**Data sources**: Aggregation from NFe items by CFOP:
- **Debit (1xxx, 2xxx, 3xxx)**: output operations
- **Credit (1xxx, 2xxx, 3xxx)**: input operations (with ICMS credit)
- **Adjustments**: manual entries, DIFAL, ST adjustments

### 6.4 Record E500/E520 — Apuração IPI

Same as ECF E500/E520 (Section 4.6). IPI apuração is monthly for industrial companies.

### 6.5 Record E300/E310 — DIFAL

| Field | Code | Type | Max | Description |
|-------|------|------|-----|-------------|
| E300:1 | `UF_OR` | AN | 2 | UF Origem |
| E300:2 | `UF_DEST` | AN | 2 | UF Destino |
| E300:3 | `DT_INIC` | D | 8 | Data início |
| E300:4 | `DT_FIN` | D | 8 | Data fim |
| E310:1 | `IND_MOV_DIFAL` | N | 1 | `0`=Sem, `1`=Com |
| E310:2 | `VL_SLD_CRED_ANT_DIFAL` | N | 21,2 | Saldo Credor Anterior |
| E310:3 | `VL_TOT_DEBITOS_DIFAL` | N | 21,2 | Total Débitos DIFAL |
| E310:4 | `VL_OUT_DEB_DIFAL` | N | 21,2 | Outros Débitos DIFAL |
| E310:5 | `VL_TOT_CREDITOS_DIFAL` | N | 21,2 | Total Créditos DIFAL |
| E310:6 | `VL_OUT_CRED_DIFAL` | N | 21,2 | Outros Créditos DIFAL |
| E310:7 | `VL_SLD_DEV_ANT_DIFAL` | N | 21,2 | Saldo Devedor Anterior |
| E310:8 | `VL_DEDUCAO_DIFAL` | N | 21,2 | Deduções DIFAL |
| E310:9 | `VL_RECOL` | N | 21,2 | DIFAL a Recolher |
| E310:10 | `VL_SLD_CRED_TRANSPORTAR_DIFAL` | N | 21,2 | Saldo Credor Transportar |
| E310:11 | `DEB_ESP_DIFAL` | N | 21,2 | Débitos Especiais DIFAL |

**Data sources**: Interestadual operations (CFOP 2xxx, 6xxx between different UFs):
- DIFAL = BC × (alíquota interna - alíquota interestadual)
- Alíquotas interestaduais: 4% (Sul/Sudeste), 7% (demais → Sul/Sudeste), 12%, 17%

---

## 7. Validation Engine

### 7.1 Validation Layers

```
┌─────────────────────────────────────────┐
│  Layer 1: Format Validation             │
│  - Field length checks                  │
│  - Date format (YYYYMMDD)               │
│  - Numeric format (comma decimal)       │
│  - Required fields present              │
│  - No pipe characters in text fields    │
├─────────────────────────────────────────┤
│  Layer 2: Structural Validation         │
│  - Record ordering within blocks        │
│  - Block open/close records present     │
│  - Totalization records correct         │
│  - x990 records present for each block  │
│  - 9999 total line count matches        │
├─────────────────────────────────────────┤
│  Layer 3: Business Rule Validation      │
│  - Debit/Credit balance in E110         │
│  - PIS/COFINS rate consistency         │
│  - CFOP/CST combinations valid         │
│  - Participant CNPJ/CPF valid           │
│  - Account hierarchy valid              │
├─────────────────────────────────────────┤
│  Layer 4: Cross-Record Validation       │
│  - C100 totals = sum of C170            │
│  - M100 credits × rate = M100 VL_CRED   │
│  - M200 = sum of M100 for period        │
│  - E110 debit/credit sums match docs    │
│  - I510 DRE = calculated from balances  │
├─────────────────────────────────────────┤
│  Layer 5: Cross-File Validation         │
│  - ECD matches EFD-Contribuições        │
│  - ECD matches EFD-ICMS/IPI            │
│  - GL balances reconcile across files   │
└─────────────────────────────────────────┘
```

### 7.2 Block Closure Records (x990)

Every SPED file must have closure records for each block:

```
0990  | {qtd_reg_0}          // Total records in Block 0
C990  | {qtd_reg_c}          // Total records in Block C
D990  | {qtd_reg_d}          // Total records in Block D
E990  | {qtd_reg_e}          // Total records in Block E
F990  | {qtd_reg_f}          // Total records in Block F
G990  | {qtd_reg_g}          // Total records in Block G
H990  | {qtd_reg_h}          // Total records in Block H
I990  | {qtd_reg_i}          // Total records in Block I
J990  | {qtd_reg_j}          // Total records in Block J
K990  | {qtd_reg_k}          // Total records in Block K
1990  | {qtd_reg_1}          // Total records in Block 1
9990  | {qtd_reg_9}          // Total records in Block 9
```

### 7.3 Totalization (9999)

```
9999 | {total_line_count}   // Total lines including 0000 and 9999
```

The total includes:
- Record 0000 (line 1)
- All data records
- All x990 closure records
- Record 9999 (last line)

### 7.4 Validation Interface

```typescript
interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  summary: {
    total_records: number;
    records_by_block: Record<string, number>;
    totalization_check: boolean;
    hash: string;
  };
}

interface ValidationError {
  code: string;           // e.g. "E110_DEBIT_CREDIT_MISMATCH"
  severity: 'error';      // blocks submission
  record: string;         // e.g. "E110"
  field?: string;
  message: string;
  line_number?: number;
}

interface ValidationWarning {
  code: string;           // e.g. "MISSING_ADJUSTMENT"
  severity: 'warning';    // advisory, doesn't block
  record: string;
  message: string;
}
```

---

## 8. SEFAZ Validator Integration

### 8.1 Official Validation Tools

SEFAZ provides official validation programs for each SPED type:

| SPED Type | Official Tool | Download |
|-----------|--------------|----------|
| **ECD** | Validador ECD (Win32) | SEFAZ website → Programas → SPED |
| **ECF** | Validador ECF (Win32) | SEFAZ website → Programas → SPED |
| **EFD-Contribuições** | Validador EFD-Contribuições (Win32) | SEFAZ website → Programas → SPED |
| **EFD-ICMS/IPI** | Validador EFD-ICMS/IPI (Win32) | SEFAZ website → Programas → SPED |

### 8.2 Integration Strategy

```typescript
// validator.ts

interface SpedValidatorAdapter {
  validate(filePath: string, fileType: SpedFileType): Promise<ValidationResult>;
}

class SpedValidatorAdapter implements SpedValidatorAdapter {
  private validatorPath: Map<SpedFileType, string>;

  constructor(config: ValidatorConfig) {
    this.validatorPath = new Map([
      ['ECD', config.ecdValidatorPath],
      ['ECF', config.ecfValidatorPath],
      ['EFD_CONTRIBUICOES', config.efdContribuicoesPath],
      ['EFD_ICMS_IPI', config.efdIcmsIpiPath],
    ]);
  }

  async validate(filePath: string, fileType: SpedFileType): Promise<ValidationResult> {
    const validatorPath = this.validatorPath.get(fileType);
    if (!validatorPath) {
      throw new Error(`No validator configured for ${fileType}`);
    }

    // Run SEFAZ validator (Wine on Linux, or native on Windows)
    const result = await execFile(validatorPath, [filePath], {
      timeout: 120_000,
      encoding: 'latin1',
    });

    // Parse validator output
    return this.parseValidatorOutput(result.stdout, result.stderr);
  }

  private parseValidatorOutput(stdout: string, stderr: string): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];

    // SEFAZ validator outputs error lines like:
    // "ERRO: [E110] Saldo apurado não confere"
    // "AVISO: [0150] Participante sem IE"

    for (const line of stdout.split('\n')) {
      if (line.startsWith('ERRO:')) {
        errors.push(this.parseError(line));
      } else if (line.startsWith('AVISO:')) {
        warnings.push(this.parseWarning(line));
      }
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
      summary: {
        total_records: 0,
        records_by_block: {},
        totalization_check: errors.length === 0,
        hash: '',
      },
    };
  }
}
```

### 8.3 Wine Integration (Linux)

On Linux servers, run SEFAZ Win32 validators via Wine:

```bash
# Install Wine
apt-get install wine64

# Run ECD validator
wine /opt/sefaz/SPEDValidaECD.exe /path/to/sped_file.txt

# Run EFD-ICMS/IPI validator
wine /opt/sefaz/SPEDValidaEFD.exe /path/to/sped_file.txt
```

### 8.4 Programa Gerador (Gerador de Escrituração)

SEFAZ also provides "Programa Gerador" tools that can validate AND generate the official SPED file format. Integration options:

1. **Export → Validate**: Generate SPED via our engine, then validate with SEFAZ tool
2. **Export → Import → Gerador**: Export accounting data as CSV, import into Gerador program
3. **Native validation**: Build our own validation matching SEFAZ rules (preferred for automation)

**Recommended approach**: Native validation (Layer 1-4 above) + SEFAZ validator as final check before submission.

---

## 9. Incremental Generation Strategy

### 9.1 Period-Based Generation

SPED files are generated for specific fiscal periods:

| SPED Type | Period | Deadline |
|-----------|--------|----------|
| ECD | Annual (or monthly) | Last business day of 7th month after fiscal year end |
| ECF | Annual | Last business day of 7th month after fiscal year end |
| EFD-Contribuições | Monthly | 15th of 2nd month after reference month |
| EFD-ICMS/IPI | Monthly | 15th of 2nd month after reference month |

### 9.2 Generation Flow

```typescript
async function generateSped(
  request: SpedGenerationRequest
): Promise<SpedGenerationResult> {
  const { type, tenantId, periodStart, periodEnd, options } = request;

  // 1. Validate period is closed
  const period = await validatePeriod(tenantId, periodStart, periodEnd);
  if (period.status !== 'hard_closed') {
    throw new SpedError('Period must be hard-closed before SPED generation');
  }

  // 2. Extract data from GL/AP/AR/Tax
  const extractor = getExtractor(type);
  const data = await extractor.extract(tenantId, periodStart, periodEnd, options);

  // 3. Generate records
  const generator = getGenerator(type);
  const records = await generator.generate(data, options);

  // 4. Assemble file
  const assembler = new SpedFileAssembler();
  const fileContent = assembler.assemble(records);

  // 5. Validate
  const validator = new SpedValidator();
  const validation = await validator.validate(fileContent, type);

  if (!validation.valid && !options.forceGenerate) {
    throw new SpedValidationError(validation.errors);
  }

  // 6. Save to storage
  const savedFile = await saveSpedFile(fileContent, {
    tenantId,
    type,
    periodStart,
    periodEnd,
    validation,
  });

  return {
    fileId: savedFile.id,
    fileName: savedFile.name,
    validation,
    hash: validation.summary.hash,
    lineCount: validation.summary.total_records,
  };
}
```

### 9.3 Data Extraction Queries

**GL Balances for ECD**:
```sql
SELECT
  a.code AS account_code,
  a.name AS account_name,
  p.name AS period_name,
  COALESCE(mb.total_debit, 0) AS total_debit,
  COALESCE(mb.total_credit, 0) AS total_credit,
  COALESCE(mb.balance, 0) AS balance,
  a.normal_balance
FROM gl_accounts a
CROSS JOIN gl_periods p
LEFT JOIN mv_account_balances mb
  ON mb.account_id = a.id
  AND mb.period_id = p.id
WHERE p.start_date >= :periodStart
  AND p.end_date <= :periodEnd
  AND a.is_leaf = 1
  AND a.is_active = 1
ORDER BY a.code, p.period_number;
```

**Journal Entries for ECD I200**:
```sql
SELECT
  je.entry_date,
  a_deb.code AS account_debit,
  a_cred.code AS account_credit,
  jel.debit AS amount,
  je.description AS history,
  jel.subledger_type,
  jel.subledger_id
FROM gl_journal_entry_lines jel
JOIN gl_journal_entries je ON je.id = jel.journal_entry_id
JOIN gl_accounts a_deb ON a_deb.id = jel.account_id AND jel.debit > 0
JOIN gl_accounts a_cred ON a_cred.id = jel.account_id AND jel.credit > 0
WHERE je.status = 'posted'
  AND je.entry_date >= :periodStart
  AND je.entry_date <= :periodEnd
ORDER BY je.entry_date, je.entry_number;
```

**NFe Documents for EFD-ICMS/IPI**:
```sql
SELECT
  nf.id AS nfe_id,
  nf.document_number,
  nf.issue_date,
  nf.entry_date,
  nf.total_value,
  nf.icms_base,
  nf.icms_value,
  nf.ipi_value,
  nf.pis_value,
  nf.cofins_value,
  nf.destination_state,
  nf.operation_cfop,
  nf.participant_cnpj
FROM nfe_documents nf
WHERE nf.issue_date >= :periodStart
  AND nf.issue_date <= :periodEnd
  AND nf.status = 'authorized'
ORDER BY nf.issue_date, nf.document_number;
```

**NFe Items for C170**:
```sql
SELECT
  ni.line_number,
  ni.product_code,
  ni.description,
  ni.quantity,
  ni.unit,
  ni.unit_value,
  ni.total_value,
  ni.discount_value,
  ni.icms_cst,
  ni.icms_cfop,
  ni.icms_base,
  ni.icms_rate,
  ni.icms_value,
  ni.ipi_base,
  ni.ipi_rate,
  ni.ipi_value,
  ni.pis_cst,
  ni.pis_base,
  ni.pis_rate,
  ni.pis_value,
  ni.cofins_cst,
  ni.cofins_base,
  ni.cofins_rate,
  ni.cofins_value
FROM nfe_items ni
JOIN nfe_documents nf ON nf.id = ni.nfe_id
WHERE nf.issue_date >= :periodStart
  AND nf.issue_date <= :periodEnd
  AND nf.status = 'authorized'
ORDER BY nf.issue_date, nf.document_number, ni.line_number;
```

### 9.4 Incremental vs Full Generation

| Scenario | Strategy |
|----------|----------|
| First generation | Full extraction for period |
| Data correction | Regenerate only affected block(s) |
| Period extension | Generate new period, merge with existing |
| Substitution | Full regeneration with `COD_FIN = 01` (substituição) |
| Correction | Full regeneration with `COD_FIN = 03` (correção) |

**Caching strategy**:
- Cache extracted data per period (invalidated on data changes)
- Cache generated records (reused for corrections)
- Cache assembled file (for download without regeneration)

---

## 10. API Design

### 10.1 Endpoints

```
POST   /api/sped/generate              # Generate SPED file
POST   /api/sped/validate              # Validate SPED file
GET    /api/sped/{fileId}              # Get SPED metadata
GET    /api/sped/{fileId}/download     # Download SPED file
GET    /api/sped/{fileId}/validation   # Get validation results
DELETE /api/sped/{fileId}              # Delete SPED file
GET    /api/sped/list                  # List SPED files (with filters)
POST   /api/sped/{fileId}/resubmit     # Re-submit to SEFAZ
```

### 10.2 Generate SPED

```typescript
// POST /api/sped/generate
interface GenerateSpedRequest {
  type: 'ECD' | 'ECF' | 'EFD_CONTRIBUICOES' | 'EFD_ICMS_IPI';
  period_start: string;    // YYYY-MM-DD
  period_end: string;      // YYYY-MM-DD
  finality?: 'original' | 'substitution' | 'correction' | 'first_substitution';
  options?: {
    include_adjustments?: boolean;   // Include adjusting entries
    include_closing?: boolean;       // Include closing entries
    exclude_draft?: boolean;         // Exclude draft entries
    custom_mappings?: Record<string, string>;  // Account/CFOP overrides
    force_generate?: boolean;        // Generate despite validation errors
  };
}

// Response: 202 Accepted (async generation)
{
  "job_id": "sped_job_abc123",
  "status": "processing",
  "estimated_completion": "2026-07-10T14:30:00Z"
}

// Webhook callback when complete:
{
  "event": "sped.completed",
  "job_id": "sped_job_abc123",
  "file_id": "sped_file_xyz789",
  "validation": {
    "valid": true,
    "errors": [],
    "warnings": [],
    "summary": {
      "total_records": 1247,
      "records_by_block": { "0": 15, "C": 892, "E": 45, "9": 3 },
      "hash": "a1b2c3d4e5f6"
    }
  }
}
```

### 10.3 Validate SPED

```typescript
// POST /api/sped/validate
interface ValidateSpedRequest {
  file_id?: string;        // Validate existing file
  file_content?: string;   // Or validate raw content
  type: 'ECD' | 'ECF' | 'EFD_CONTRIBUICOES' | 'EFD_ICMS_IPI';
  run_sefaz_validator?: boolean;  // Also run official validator
}

// Response: 200 OK
{
  "valid": true,
  "errors": [],
  "warnings": [
    {
      "code": "MISSING_ADJUSTMENT",
      "severity": "warning",
      "record": "E110",
      "message": "No adjustment records found for ICMS apuração"
    }
  ],
  "summary": {
    "total_records": 1247,
    "records_by_block": { "0": 15, "C": 892, "E": 45, "9": 3 },
    "totalization_check": true,
    "hash": "a1b2c3d4e5f6",
    "sefaz_validation": {
      "passed": true,
      "errors": [],
      "warnings": []
    }
  }
}
```

### 10.4 Download SPED

```typescript
// GET /api/sped/{fileId}/download
// Response: 200 OK, Content-Type: text/plain; charset=iso-8859-1
// Content-Disposition: attachment; filename="EFD_ICMS_IPI_01_2026.txt"
```

---

## 11. Testing Strategy

### 11.1 Golden Master Tests

Each SPED type needs golden master tests with known-correct outputs:

```
tests/sped/
├── fixtures/
│   ├── ecd/
│   │   ├── company_config.json
│   │   ├── gl_accounts.json
│   │   ├── journal_entries.json
│   │   ├── account_balances.json
│   │   └── expected_ecd_output.txt       # Golden master
│   │
│   ├── ecf/
│   │   ├── company_config.json
│   │   ├── nfe_documents.json
│   │   ├── expected_ecf_output.txt
│   │
│   ├── efd_contribuicoes/
│   │   ├── company_config.json
│   │   ├── nfe_documents.json
│   │   ├── expected_efd_contrib_output.txt
│   │
│   └── efd_icms_ipi/
│       ├── company_config.json
│       ├── nfe_documents.json
│       ├── expected_efd_icms_output.txt
│
├── unit/
│   ├── field-formatter.test.ts
│   ├── record-builder.test.ts
│   ├── block-assembler.test.ts
│   └── date-utils.test.ts
│
├── integration/
│   ├── ecd-generator.test.ts
│   ├── ecf-generator.test.ts
│   ├── efd-contribuicoes-generator.test.ts
│   └── efd-icms-ipi-generator.test.ts
│
├── golden-master/
│   ├── ecd-golden.test.ts              # Compare output to golden file
│   ├── ecf-golden.test.ts
│   ├── efd-contribuicoes-golden.test.ts
│   └── efd-icms-ipi-golden.test.ts
│
├── validation/
│   ├── structural-validation.test.ts
│   ├── business-rule-validation.test.ts
│   ├── cross-record-validation.test.ts
│   └── sefaz-validator.test.ts
│
└── edge-cases/
    ├── empty-period.test.ts
    ├── single-document.test.ts
    ├── maximum-records.test.ts
    └── special-characters.test.ts
```

### 11.2 Test Patterns

**Golden Master Test**:
```typescript
describe('ECD Golden Master', () => {
  it('should generate correct ECD for standard fiscal year', async () => {
    // Load fixture data
    const fixture = loadFixture('ecd/standard_year');
    
    // Generate ECD
    const result = await generateECD(fixture);
    
    // Compare line by line
    const expected = readGoldenFile('ecd/expected_ecd_output.txt');
    expect(result.content).toEqual(expected);
  });

  it('should generate correct ECD with adjusting entries', async () => {
    const fixture = loadFixture('ecd/with_adjustments');
    const result = await generateECD(fixture);
    const expected = readGoldenFile('ecd/expected_ecd_adjustments.txt');
    expect(result.content).toEqual(expected);
  });
});
```

**Validation Test**:
```typescript
describe('E110 Validation', () => {
  it('should detect debit/credit mismatch', async () => {
    const file = generateFileWithMismatchedE110();
    const result = await validateFile(file, 'EFD_ICMS_IPI');
    
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual(
      expect.objectContaining({
        code: 'E110_DEBIT_CREDIT_MISMATCH',
        severity: 'error',
      })
    );
  });

  it('should validate correct apuração', async () => {
    const fixture = loadFixture('efd_icms_ipi/correct_apuracao');
    const file = await generateEFD_ICMS_IPI(fixture);
    const result = await validateFile(file, 'EFD_ICMS_IPI');
    
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });
});
```

### 11.3 Test Data Requirements

| Test Case | Company Type | Documents | Complexity |
|-----------|-------------|-----------|------------|
| Standard year | Lucro Real | 100 NF-e | Low |
| Multiple states | Lucro Real | 500 NF-e, 5 states | Medium |
| Simples Nacional | Simples | 200 NF-e | Low |
| Import operations | Lucro Real | 50 import NF-e | Medium |
| ST/DIFAL | Lucro Real | 200 NF-e, 3 states | High |
| Adjustment period | Lucro Real | 100 + 20 adjustments | Medium |
| Year-end closing | Lucro Real | 1200 NF-e (annual) | High |

---

## 12. Effort Estimates

### 12.1 Per SPED Type

| SPED Type | Records | Complexity | Effort (days) | Dependencies |
|-----------|---------|------------|---------------|--------------|
| **EFD-Contribuições** | ~50 records | Medium | 10-12 | GL, NFe, Tax Engine |
| **EFD-ICMS/IPI** | ~120 records | High | 10-12 | GL, NFe, Tax Engine, ST/DIFAL |
| **ECD** | ~30 records | Medium | 8-10 | GL (primary), EFD-Contribuições, EFD-ICMS/IPI |
| **ECF** | ~80 records | Medium-Low | 5-7 | ECD |
| **Validation** | — | Medium | 5-7 | All SPED types |
| **Total** | — | — | **38-48** | — |

### 12.2 Breakdown by Component

| Component | Effort (days) | Notes |
|-----------|---------------|-------|
| Core framework (types, formatter, assembler) | 3-4 | Reusable across all SPED types |
| EFD-Contribuições records | 4-5 | M100/M200/M500/M600 are most complex |
| EFD-ICMS/IPI records | 5-6 | C100/C170/E110 are most complex |
| ECD records | 4-5 | I200/I350/I500/I510 are key |
| ECF records | 3-4 | Simpler, builds on ECD |
| Data extractors (GL, NFe, Tax) | 4-5 | SQL queries, data transformation |
| Validation engine | 3-4 | 5-layer validation |
| API endpoints | 3-4 | Generate, validate, download |
| Testing (unit + golden master) | 5-6 | Critical for compliance |
| SEFAZ validator integration | 2-3 | Wine setup, output parsing |
| **Total** | **36-46** | — |

### 12.3 Phase Dependencies

```
Phase 1: GL Implementation (B2) — prerequisite
    ↓
Phase 2: NFe Integration (Batch 2) — prerequisite
    ↓
Phase 3: SPED Generation (this plan)
    ├── Week 1-2: Core framework + EFD-Contribuições
    ├── Week 3-4: EFD-ICMS/IPI + ECD
    ├── Week 5: ECF + Validation engine
    ├── Week 6: API + Testing
    └── Week 7: SEFAZ integration + Edge cases
```

---

## 13. Data Flow Diagram

```
                    ┌─────────────────────┐
                    │   GL Module (B2)    │
                    │  ┌───────────────┐  │
                    │  │ gl_accounts   │  │
                    │  │ gl_entries    │  │
                    │  │ gl_balances   │  │
                    │  └───────┬───────┘  │
                    └──────────┼──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   NFe Module (B2)   │
                    │  ┌───────────────┐  │
                    │  │ nfe_documents │  │
                    │  │ nfe_items     │  │
                    │  │ nfe_taxes     │  │
                    │  └───────┬───────┘  │
                    └──────────┼──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Tax Engine (B1)    │
                    │  ┌───────────────┐  │
                    │  │ tax_calc      │  │
                    │  │ tax_rates     │  │
                    │  │ tax_periods   │  │
                    │  └───────┬───────┘  │
                    └──────────┼──────────┘
                               │
              ┌────────────────▼────────────────┐
              │      SPED Generation Engine      │
              │                                  │
              │  ┌──────────────────────────┐   │
              │  │    Data Extraction        │   │
              │  │  GL → Account balances    │   │
              │  │  NFe → Documents/items    │   │
              │  │  Tax → Rates/apuração     │   │
              │  └────────────┬─────────────┘   │
              │               │                 │
              │  ┌────────────▼─────────────┐   │
              │  │    Record Generation      │   │
              │  │  ECD: I200, I350, I500   │   │
              │  │  ECF: C100, C170, E110   │   │
              │  │  EFD: M100, M200, M500   │   │
              │  │  ICMS: C100, E110, E300  │   │
              │  └────────────┬─────────────┘   │
              │               │                 │
              │  ┌────────────▼─────────────┐   │
              │  │    Block Assembly         │   │
              │  │  Group by block           │   │
              │  │  Add open/close records   │   │
              │  │  Calculate x990 totals    │   │
              │  └────────────┬─────────────┘   │
              │               │                 │
              │  ┌────────────▼─────────────┐   │
              │  │    File Assembly          │   │
              │  │  Concatenate blocks       │   │
              │  │  Add 0000 header          │   │
              │  │  Add 9999 totalization    │   │
              │  │  Calculate hash           │   │
              │  └────────────┬─────────────┘   │
              │               │                 │
              │  ┌────────────▼─────────────┐   │
              │  │    Validation             │   │
              │  │  Format validation        │   │
              │  │  Structural validation    │   │
              │  │  Business rule validation │   │
              │  │  Cross-record validation  │   │
              │  │  SEFAZ validator (opt.)   │   │
              │  └────────────┬─────────────┘   │
              │               │                 │
              └───────────────┼─────────────────┘
                              │
              ┌───────────────▼─────────────────┐
              │          SPED File Output        │
              │                                  │
              │  ECD:  /sped/ecd/2026/01.txt     │
              │  ECF:  /sped/ecf/2026/01.txt     │
              │  EFD:  /sped/efd/2026/01.txt     │
              │  ICMS: /sped/icms/2026/01.txt    │
              │                                  │
              │  Metadata:                       │
              │  - file_id, file_name            │
              │  - validation status             │
              │  - hash, line count              │
              │  - generation timestamp          │
              └──────────────────────────────────┘
```

---

## Appendix A: Common SPED Error Codes

| Code | Description | Severity | Fix |
|------|-------------|----------|-----|
| `SPED001` | Record 0000 missing | Error | Add header record |
| `SPED002` | Record 9999 missing | Error | Add totalization record |
| `SPED003` | Block x990 missing | Error | Add block closure record |
| `SPED004` | Record ordering violation | Error | Reorder records per layout |
| `SPED005` | Field exceeds max length | Error | Truncate or fix data |
| `SPED006` | Invalid date format | Error | Use YYYYMMDD |
| `SPED007` | Required field empty | Error | Populate field |
| `SPED008` | Invalid CNPJ/CPF | Error | Fix participant document |
| `SPED009` | Line count mismatch | Error | Fix 9999 totalization |
| `E11001` | ICMS debit/credit mismatch | Error | Review apuração |
| `E11002` | ICMS saldo calculation error | Error | Check E110 formula |
| `M10001` | PIS credit × rate mismatch | Error | Check M100 calculation |
| `M20001` | PIS totalization error | Error | Review M200 |
| `C10001` | C100 total ≠ sum C170 | Error | Verify line item totals |
| `C17001` | Invalid CST/CFOP combination | Error | Review tax configuration |

---

## Appendix B: SPED File Naming Convention

```
{TYPE}_{UF}_{REFERENCE_MONTH}_{REFERENCE_YEAR}.{EXT}

Examples:
  ECD_BR_12_2026.txt                    # ECD for Dec 2026
  ECF_BR_12_2026.txt                    # ECF for Dec 2026
  EFD_CONTRIBUICOES_SP_01_2026.txt      # EFD-Contribuições for Jan 2026
  EFD_ICMS_IPI_SP_01_2026.txt          # EFD-ICMS/IPI for Jan 2026
```

---

## Appendix C: Reference Standards

| Document | Description |
|----------|-------------|
| **IN RFB 2.004/2021** | ECD layout and rules |
| **IN RFB 2.005/2021** | ECF layout and rules |
| **IN RFB 2.110/2022** | EFD-Contribuições layout |
| **Convênio ICMS 143/2018** | EFD-ICMS/IPI layout |
| **Manual de Orientação do Contribuinte (MOC)** | Official SEFAZ guidance for each SPED type |
| **Nota Técnica** | SEFAZ technical notes for SPED updates |

---

*Document version: 1.0*
*Generated: 2026-07-10*
*Part of: L2 Cashflow Master Plan — Batch 3 (Compliance & Integrations)*
