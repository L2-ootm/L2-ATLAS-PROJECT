# Modular Cashflow Universal — Relatório Técnico Profundo

> Generated 2026-07-09 · depth: deep · 144 sources (12 findings files) · workspace: research/modular-cashflow/

## Executive Summary

**Arquitetura**: O sistema modular precisa de 3 camadas — (1) Core compartilhado com GL/COA/journal entries, (2) Módulos ativáveis via manifest TOML com dependências SemVer, (3) Event bus para comunicação entre módulos.

**Database**: Schema híbrido — tabelas core compartilhadas + tabelas de extensão por módulo + JSONB metadata para atributos flexíveis. Event sourcing para o ledger principal (append-only audit trail). PostgreSQL RLS para multi-tenancy; SQLite com isolamento via application layer.

**Event-Driven**: CQRS separa writes (journal entries no event store) de reads (materialized views para dashboards). Event naming `{resource}.{action}`. Saga pattern para transações multi-step (payment → reconciliation → revenue recognition).

**Plugin System**: Manifest-driven com Odoo-style `depends` + VS Code-style contribution points + Cargo SemVer. Lifecycle hooks: pre_init → post_init → activate → deactivate → uninstall. Auto-install bridges para módulos que se conectam.

**Compliance Brasil**: SPED com 4 livros (ECD/ECF/EFD-Contribuições/EFD-ICMS IPI) em formato pipe-delimited. NFe 4.00 com XML signing + SOAP 1.2 + X.509 mutual TLS. eSocial com 4 eventos principais. CNPJ validation com modulus-11 alfanumérico.

**API**: REST para CRUD + webhooks; GraphQL read-only para dashboards. Cursor-based pagination (Stripe model). JWT claim para tenant identification. HMAC-SHA256 para webhook signatures.

**UI**: Config-driven sidebar a partir de module manifest. JSON Schema para form rendering dinâmico. Grafana-style dashboard JSON. CSS custom properties para white-labeling.

---

## 1. Arquitetura de Database Modular

### 1.1 Schema Híbrido (Core + Extension + JSONB)

**Padrão recomendado**: Tabelas core compartilhadas por todos os módulos + tabelas de extensão por módulo + coluna `metadata JSONB` para atributos flexíveis.

```sql
-- CORE: compartilhado por todos os módulos
CREATE TABLE accounts (
    account_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    account_type TEXT NOT NULL, -- asset, liability, equity, revenue, expense
    parent_id UUID REFERENCES accounts(account_id),
    is_active BOOLEAN DEFAULT true,
    currency TEXT DEFAULT 'BRL',
    metadata JSONB, -- atributos flexíveis por módulo
    UNIQUE (tenant_id, code)
);

CREATE TABLE journal_entries (
    je_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    entry_date DATE NOT NULL,
    fiscal_period TEXT NOT NULL,
    description TEXT,
    source_module TEXT, -- 'invoicing', 'payroll', 'treasury'
    source_doc_id UUID,
    reversal_of UUID REFERENCES journal_entries(je_id),
    is_posted BOOLEAN DEFAULT false,
    posted_at TIMESTAMPTZ,
    created_by UUID NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE journal_entry_lines (
    line_id UUID PRIMARY KEY,
    je_id UUID NOT NULL REFERENCES journal_entries(je_id),
    tenant_id UUID NOT NULL,
    account_id UUID NOT NULL REFERENCES accounts(account_id),
    debit NUMERIC(18,6) DEFAULT 0, -- NUNCA float
    credit NUMERIC(18,6) DEFAULT 0,
    party_id UUID,
    cost_center TEXT,
    metadata JSONB,
    CONSTRAINT chk_debit_credit CHECK (
        (debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)
    )
);

-- EXTENSÃO: cada módulo cria suas tabelas
-- Módulo invoicing:
CREATE TABLE invoices (
    invoice_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    account_id UUID REFERENCES accounts(account_id), -- FK para core
    customer_id UUID NOT NULL,
    amount NUMERIC(18,6) NOT NULL,
    status TEXT DEFAULT 'draft',
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Módulo fixed-assets:
CREATE TABLE fixed_assets (
    asset_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    account_id UUID REFERENCES accounts(account_id), -- FK para core
    depreciation_method TEXT,
    useful_life_months INTEGER,
    salvage_value NUMERIC(18,6),
    metadata JSONB
);
```

**Princípio**: Módulos referenciam tabelas core via FK, nunca outras tabelas de módulos. Cross-module data via event bus ou shared interfaces.

### 1.2 Event Sourcing para Ledger

```sql
CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id UUID NOT NULL,
    aggregate_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_version INTEGER NOT NULL DEFAULT 1,
    event_data JSONB NOT NULL,
    metadata JSONB, -- correlation_id, causation_id, user_id
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (aggregate_id, event_version) -- optimistic concurrency
);

CREATE INDEX idx_events_aggregate ON events (aggregate_id, event_version);
CREATE INDEX idx_events_type ON events (event_type);
CREATE INDEX idx_events_created ON events (created_at);
```

**Benefícios**: Audit trail imutável (exigência SOX/IFRS), reconstrução temporal ("qual era o saldo em 15/03?"), reversões como eventos compensatórios (nunca deletar).

### 1.3 CQRS — Materialized Views para Leitura

```sql
CREATE MATERIALIZED VIEW account_balances AS
SELECT 
    tenant_id, account_id,
    SUM(debit) - SUM(credit) AS balance,
    SUM(debit) AS total_debits,
    SUM(credit) AS total_credits
FROM journal_entry_lines jel
JOIN journal_entries je ON jel.je_id = je.je_id
WHERE je.is_posted = true
GROUP BY tenant_id, account_id;

-- Refresh após posting:
REFRESH MATERIALIZED VIEW CONCURRENTLY account_balances;
```

### 1.4 Multi-Tenancy

**PostgreSQL RLS** (produção):
```sql
ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON journal_entries
    USING (tenant_id = current_setting('app.tenant_id')::uuid);
-- App define: SET app.tenant_id = 'tenant-uuid';
```

**SQLite** (dev): isolamento via application layer — `WHERE tenant_id = ?` em toda query.

### 1.5 Lifecycle de Módulos no Database

```
UNINSTALLED → (install migration) → INSTALLED → (enable) → ENABLED
ENABLED → (disable) → DISABLED → (enable) → ENABLED
DISABLED → (uninstall migration) → UNINSTALLED
```

**Regra crítica**: Módulos que postam transações financeiras NUNCA devem ser desinstilados enquanto tiverem dados posted. Module registry table:

```sql
CREATE TABLE module_registry (
    module_id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    enabled BOOLEAN DEFAULT false,
    installed_at TIMESTAMPTZ,
    migration_state JSONB
);
```

---

## 2. Event-Driven Architecture

### 2.1 Domain Event Schema

```
invoice.created → invoice.finalized → invoice.paid → invoice.voided
payment.received → payment.processed → payment.failed → payment.refunded
journal_entry.created → journal_entry.posted → journal_entry.voided
reconciliation.completed
expense.categorized → expense.approved
```

**Event payload**:
```json
{
  "event_id": "uuid",
  "event_type": "invoice.paid",
  "version": "2026-07-01",
  "timestamp": "2026-07-09T10:30:00Z",
  "aggregate_type": "Invoice",
  "aggregate_id": "inv_abc123",
  "data": { "invoice_id": "inv_abc123", "amount": 1500.00, "currency": "BRL" },
  "metadata": { "correlation_id": "txn_12345", "user_id": "usr_abc" }
}
```

### 2.2 Saga Pattern para Transações Multi-Step

```
Payment Processing Saga:
  1. Payment received → emit payment.received
  2. Ledger creates journal entry → emit journal_entry.created
  3. Reconciliation matches payment → emit reconciliation.completed
  4. Revenue recognized → emit revenue.recognized
  5. Reporting updated → emit report.updated

Compensating actions:
  - journal_entry.posted → compensate: voidEntry()
  - reconciliation.completed → compensate: reverseReconciliation()
  - revenue.recognized → compensate: deferRevenue()
```

### 2.3 Idempotency

```sql
CREATE TABLE processed_events (
  event_id VARCHAR(255) PRIMARY KEY,
  event_type VARCHAR(100) NOT NULL,
  processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  result JSONB
);

-- Em transaction:
INSERT INTO processed_events (event_id, event_type, result)
VALUES ($1, $2, $3)
ON CONFLICT (event_id) DO NOTHING
RETURNING event_id;
-- Se 0 rows returned → já processado
```

### 2.4 Event Bus: Redis Streams

```typescript
// Publicar
await redis.xadd('financial_events', '*',
  'event_type', 'invoice.paid',
  'payload', JSON.stringify(eventData)
);

// Consumir com consumer group
await redis.xreadgroup('GROUP', 'ledger', 'consumer-1',
  'COUNT', 10, 'BLOCK', 5000,
  'STREAMS', 'financial_events', '>'
);
// Após processar:
await redis.xack('financial_events', 'ledger', eventId);
```

---

## 3. Plugin/Extension Architecture

### 3.1 Module Manifest (TOML)

```toml
[module]
name = "cashflow-invoicing"
version = "1.2.0"
description = "Faturamento e gestão de invoices"
category = "core"
author = "L2 Systems"

[dependencies]
cashflow-core = "^1.0"
cashflow-accounts = "^1.0"

[auto_install]
when = ["cashflow-core", "cashflow-accounts"] -- bridge module

[lifecycle]
pre_init = "validate_schema"
post_init = "seed_default_templates"
activate = "register_event_handlers"
deactivate = "stop_background_jobs"
uninstall = "archive_transactions"

[contributes]
routes = ["/invoices", "/invoices/new", "/invoices/:id"]
sidebar = { label = "Faturas", icon = "FileText", order = 10 }
api_namespace = "/api/v1/invoices"
events_published = ["invoice.created", "invoice.paid", "invoice.voided"]
events_subscribed = ["payment.received"]
mcp_tools = ["get_invoices", "add_expense"]

[security]
permissions = ["invoices:read", "invoices:write", "invoices:delete"]
requires_role = ["admin", "accountant", "ar_clerk"]
```

### 3.2 Odoo-Style Auto-Install Bridges

```toml
# cashflow-billing-bridge module
[module]
name = "cashflow-billing-bridge"
auto_install = true -- ativa automaticamente quando deps são atendidas

[dependencies]
cashflow-invoicing = "^1.0"
cashflow-payments = "^1.0"
-- Bridge conecta invoicing + payments automaticamente
```

### 3.3 VS Code-Style Contribution Points

Módulos declarativamente registram UI/behavior no manifest:
- `contributes.routes` — rotas da aplicação
- `contributes.sidebar` — itens de navegação
- `contributes.api_namespace` — endpoints da API
- `contributes.events_published` — eventos que emite
- `contributes.events_subscribed` — eventos que consome

### 3.4 Cargo-Style SemVer

```toml
[dependencies]
cashflow-core = "^1.0"    # >=1.0.0, <2.0.0
cashflow-reports = "~1.2"  # >=1.2.0, <1.3.0
banking-stripe = ">=2.0, <3"
```

**Lockfile**: `cashflow.lock` para reproducibilidade — crítico para audit trails financeiros.

### 3.5 Tiered Loading

| Tier | Quando | Exemplo |
|---|---|---|
| **Compile-time** | Core ledger, GL, journal entries | Sempre carregados |
| **Hot-loadable** | Integrações, relatórios | Carregados sob demanda |
| **Event-driven** | UI extensions, dashboard widgets | Ativados por eventos |

---

## 4. Compliance Fiscal Brasil — Specs Técnicas

### 4.1 SPED — Formato de Arquivo

**Estrutura**: Records delimitados por pipe (`|`), um record por linha.

**ECD (Escrituração Contábil Digital)** — Blocos:
- Bloco A: 0000 (abertura), 0150 (participantes), 0500 (plano de contas)
- Bloco C: 1001, 1800 (DRE)
- Bloco E: 3001 (razão), 3500 (balanço)
- Bloco J: 9900 (registros), 9999 (totalização)

**EFD-Contribuições** — Records principais:
- A100: documento NF, A170: itens
- M100: crédito PIS, M200: consolidação PIS
- M500: crédito COFINS, M600: consolidação COFINS
- Taxas: PIS não-cumulativo 1.65%, cumulativo 0.65%; COFINS não-cumulativo 7.6%, cumulativo 3.0%

**EFD-ICMS IPI** — Records:
- C100: NF entrada/saída, C170: itens
- E110: apuração ICMS, E200/E210: ICMS-ST
- E300: DIFAL, E500/E520: IPI

### 4.2 NFe 4.00 — XML Schema

**Chave de acesso (44 dígitos)**:
```
AAMM + UF(2) + CNPJ(14) + modelo(2) + série(3) + número(9) + emissão(1) + código_aleatório(8) + versão(2) + emissão_tipo(1)
```

**SEFAZ**: 15 autorizadores (SVAN, SVRS, SVC-AN, SVC-RS + 11 estaduais). SOAP 1.2 com X.509 mutual TLS.

**Web services**: NfeAutorizacao, NfeRetAutorizacao, NfeInutilizacao, NfeConsultaProtocolo, NfeStatusServico, NfeConsulta, RecepcaoEvento, NfeDistribuicaoDFe.

**Status codes**: 100=autorizado, 101=cancelamento homologado, 204=duplicidade, 999=erro não catalogado.

### 4.3 NFS-e — Variações Municipais

| Cidade | Padrão | Diferenças |
|---|---|---|
| São Paulo | ABRASF 2.03 | ISS 2-5% por CNAE, SEFAZ-SP |
| Rio de Janeiro | ABRASF 2.04 | RPS flow diferente |
| Belo Horizonte | ABRASF 2.03 | Regras específicas construção |
| Curitiba | ABRASF 2.02 | CodigoTributacaoMunicipio único |

### 4.4 eSocial — Eventos Principais

- **S-1200**: Remuneração do trabalhador (CPF, rubricas, valores)
- **S-1210**: Pagamentos (beneficiário, data, valor líquido, IRF)
- **S-1299**: Fechamento dos eventos periódicos (prazo: último dia do mês seguinte)
- Layout v.S-1.3 com CNPJ alfanumérico produção 01/07/2026

### 4.5 CNPJ — Algoritmo de Validação

```
v[1] = 5×c[1] + 4×c[2] + 3×c[3] + 2×c[4] + 9×c[5] + 8×c[6] + 7×c[7] + 6×c[8] + 5×c[9] + 4×c[10] + 3×c[11] + 2×c[12]
v[1] = 11 - (v[1] mod 11); if v[1] >= 10 then v[1] = 0

v[2] = 6×c[1] + 5×c[2] + 4×c[3] + 3×c[4] + 2×c[5] + 9×c[6] + 8×c[7] + 7×c[8] + 6×c[9] + 5×c[10] + 4×c[11] + 3×c[12] + 2×c[13]
v[2] = 11 - (v[2] mod 11); if v[2] >= 10 then v[2] = 0
```

**Alfanumérico (julho 2026)**: letras A-Z, valor = ASCII(char) - 48.

**BrasilAPI**: campos úteis — `regime_tributario`, `qsa` (sócios), `cnaes_secundarios`, `situacao_cadastral`.

### 4.6 DAS MEI

**Valores fixos anuais** (lookup por CNAE):
- Comércio: R$ 80.00/mês (ICMS R$75 + ISS R$5)
- Indústria: R$ 75.00/mês (ICMS R$75)
- Serviços: R$ 70.00/mês (ISS R$70)
- Serviços+Comércio: R$ 145.00/mês

### 4.7 Simples Nacional — Fator R

```
Fator R = (Folha de Pagamento últimos 12m) / (Receita Bruta últimos 12m)
Fator R >= 28% → Anexo III (taxas menores)
Fator R < 28% → Anexo V (taxas maiores)
```

### 4.8 ST/DIFAL

**DIFAL**: `BC × (aliquota_interna - aliquota_interestadual)`
- interestadual: 4% (Sul/Sudeste) ou 7% (demais → Sul/Sudeste) ou 12%

---

## 5. API Design

### 5.1 Endpoints REST

```
GET    /api/v1/invoices          — List (cursor pagination)
POST   /api/v1/invoices          — Create
GET    /api/v1/invoices/:id      — Retrieve
POST   /api/v1/invoices/:id      — Update (partial)
DELETE /api/v1/invoices/:id      — Cancel
POST   /api/v1/invoices/:id/pay  — Action: pay
POST   /api/v1/invoices/:id/void — Action: void
```

### 5.2 Pagination (Stripe Model)

```
GET /v1/invoices?limit=100&starting_after=in_abc123
Response: { "has_more": true, "data": [...] }
```

Cursor-based, nunca offset — estável para datasets grandes e mutáveis.

### 5.3 Versioning

- URL versioning (`/v1/`, `/v2/`) para breaking changes
- Header versioning (`Stripe-Version`) para patches
- Webhook payloads fixos na versão de criação

### 5.4 Tenant Identification

```json
// JWT claim
{ "sub": "user_abc", "tenant_id": "tenant_xyz", "scope": "invoices:read" }

// Fallback header
X-Tenant-ID: tenant_xyz789
```

### 5.5 Webhook Security

```
Stripe-Signature: t=1492774577,v1=5257a869e7...
```
- HMAC-SHA256 com timestamp
- Tolerância: 5 minutos
- Retry: 3 dias com exponential backoff

### 5.6 Error Response

```json
{
  "error": {
    "type": "invalid_request_error",
    "code": "amount_mismatch",
    "message": "Debits (45000) != credits (50000)",
    "param": "lines[1].credit",
    "doc_url": "https://docs.cashflow.app/errors#amount_mismatch"
  }
}
```

---

## 6. UI Configurável

### 6.1 Module Manifest → Dynamic Sidebar

```typescript
export const moduleManifest: NavModule[] = [
  { id: 'dashboard', label: 'Dashboard', icon: 'LayoutDashboard', path: '/dashboard', order: 1 },
  { id: 'journal', label: 'Razão Geral', icon: 'BookOpen', path: '/journal', order: 2,
    children: [
      { id: 'journal-new', label: 'Nova Entrada', path: '/journal/new', order: 1 },
      { id: 'journal-list', label: 'Todas', path: '/journal', order: 2 },
    ]
  },
  // ... carregado de cashflow.toml
]
```

### 6.2 JSON Schema para Forms

```typescript
const journalEntrySchema = [
  { $formkit: 'date', name: 'entry_date', label: 'Data', validation: 'required' },
  { $formkit: 'text', name: 'description', label: 'Descrição', validation: 'required' },
  {
    $el: 'div', for: ['line', 'index', '$lines'],
    children: [
      { $formkit: 'select', name: 'account', options: '$chartOfAccounts' },
      { $formkit: 'number', name: 'debit', label: 'Débito' },
      { $formkit: 'number', name: 'credit', label: 'Crédito' },
    ]
  }
]
```

### 6.3 Dashboard JSON (Grafana-Style)

```json
{
  "panels": [
    { "type": "stat", "title": "Receita Mensal", "gridPos": {"x":0,"y":0,"w":6,"h":4},
      "targets": [{"rawSql": "SELECT SUM(amount) FROM invoices WHERE status='paid'"}] },
    { "type": "timeseries", "title": "Fluxo de Caixa", "gridPos": {"x":6,"y":0,"w":12,"h":8} }
  ],
  "templating": { "list": [{ "name": "period", "type": "custom", "query": "monthly,quarterly" }] }
}
```

### 6.4 PDF Generation

- **Invoices/Receipts**: jsPDF + AutoTable (client-side, rápido)
- **Financial Statements**: React-PDF (declarativo, design-system aligned)
- **Negative numbers**: parênteses `(1.234,56)` ou vermelho

### 6.5 White-Labeling

```css
[data-brand="acme"] { --brand-primary: #e11d48; }
[data-brand="globex"] { --brand-primary: #059669; }
[data-theme="dark"] { --color-background: #0f172a; }
```

---

## 7. Taxonomia Completa de Módulos (42 módulos, 7 camadas)

| Camada | Módulos |
|---|---|
| **Core** (10) | General Ledger, Chart of Accounts, AP, AR, Bank Rec, Fiscal Year, Invoicing, Payments, Expenses, Auth |
| **Compliance** (6) | Tax Engine, NFe/NFS-e/CT-e, SPED, Tax Calendar, Audit Trail, Multi-GAAP |
| **Operations** (5) | Cash Flow Forecast, Receipts, Budget, Approvals, Notifications |
| **Advanced** (9) | Multi-Entity, Multi-Currency, Revenue Rec, Deferred Revenue, Fixed Assets, Inventory, Cost Centers, Lease, Transfer Pricing |
| **Industry** (8) | Retail, SaaS, Manufacturing, Marketplace, Real Estate, Healthcare, Agriculture, Services |
| **Integrations** (6) | Banking/Open Finance, Payment Gateways, Government APIs, Accounting, E-commerce, Payroll |
| **Automation** (5) | Recurring Billing, Auto-Categorization, Anomaly Detection, AI Forecast, Workflow Engine |

---

## Open Questions

1. **Event Sourcing vs Traditional Schema**: Prototype ambos para journal entries e comparar complexidade de código, performance de queries, e capability de audit.
2. **RLS vs Application-level**: Verificar se PostgreSQL RLS funciona com connection pooling (PgBouncer) — RLS requer `SET app.tenant_id` por connection.
3. **Simples Nacional tables**: As 5 tabelas dos anexos (I-V) com faixas, alíquotas nominais e parcelas a deduzir precisam de implementação exata — dados atualizados anualmente.
4. **NFS-e municipal**: 5.570 municípios com potencialmente 5.570 implementações diferentes — priorizar os 100+ maiores municípios.
5. **ASC 842/IFRS 16**: Lease accounting não coberto em profundidade — módulo crítico para empresas com imóveis alugados.
6. **Transfer Pricing**: módulo enterprise para operações cross-border sem cobertura nesta rodada.

---

## Sources

[1-12] F1: Core Financial Modules — Wikipedia (General Ledger, COA, AP, AR, Bank Reconciliation, Double-Entry, Fiscal Year)
[13-24] F2: Industry-Specific Modules — Wikipedia (POS, Revenue Stream, Subscription, COGS, BOM, Escrow, Property Management, Insurance)
[25-36] F3: Competitor Architecture — Xero, FreshBooks, Wave, Nubank, Mercado Pago, PagBank (pricing pages, feature lists)
[37-46] F4: Compliance — gov.br (SPED, Simples Nacional, MEI, SOX, IFRS, Receita Federal Reforma Tributária)
[47-58] F5: Advanced Features — Oracle NetSuite docs, Acumatica product pages, Odoo 18.0 docs, Sage Intacct
[59-70] F6: Integrations — Belvo, eSocial, NFS-e, Mercado Pago Developers, Asaas Docs, Receita Federal
[71-83] F7: Database Schema — Event Sourcing (microservices.io), CQRS (Microsoft Azure), Odoo ORM docs, PostgreSQL patterns
[84-98] F8: Event-Driven — Martin Fowler, microservices.io, Stripe docs, Redis docs
[99-113] F9: Plugin Architecture — Odoo manifests, WordPress hooks, VS Code extensions, Cargo deps, Shopify/Salesforce/Slack patterns
[114-128] F10: Brazilian Compliance — SPED formats, NFe XML schema, NFS-e ABRASF, eSocial events, CNPJ algorithm, Simples Nacional tables
[129-139] F11: API Design — Stripe API, Plaid API, Azure multitenant guide
[140-152] F12: Config-Driven UI — FormKit schema, Grafana dashboard JSON, React-PDF, CSS custom properties
