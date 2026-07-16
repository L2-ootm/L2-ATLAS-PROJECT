# Modular Cashflow Universal — Relatório: Padrões Contábeis, SaaS, Localização, Automação, Marketplace, DX

> Generated 2026-07-09 · 24 findings files totais · 300+ fontes · workspace: research/modular-cashflow/

## Executive Summary

**Padrões Contábeis**: Multi-GAAP via base ledger + standard adjustment layers + reporting views. IFRS 15 mapeia para 5 estágios de processamento de receita. COA universal com mapping tables para SKR03/04, PCG, ECF/CTB. IFRS 18 (2027) exige novos MPMs — plataforma precisa suportar desde o início.

**SaaS Metrics**: NRR > 100% = clientes existentes crescem mais que perdas (métrica #1 para valuation). Quick Ratio = (New+Expansion)/(Contraction+Churn), target >4.0. MRR events como deltas tipados (não snapshots) para watermark reconstruction. ASC 606 exige recognition ratável + deferred revenue como liability.

**Localização**: CLDR `alt="alphaNextToNumber"` para spacing de currency symbols. ICU number skeletons `:: sign-accounting` para negativos entre parênteses. Fiscal periods por local transaction time (não UTC). FormatJS (react-intl) tem implementação nativa em Rust — alinhado com D-022. Tax display: toggle configurable inclusive/exclusive.

**Automação**: Temporal.io para core financial workflow (durable execution + audit trail). Rules como JSONB versionado (rollback capability). Notification routing urgente: SMS+Push → Email+Push → Email+In-app → In-app only. Webhook HMAC-SHA256 + exponential backoff (7 attempts/24h).

**Marketplace**: Stripe Connect destination charges = fluxo mais limpo. Escrow via pending/available balance states. Brazil: CPF/CNPJ + liveness + UBO >25%. Separate charges para multi-party splits. Application fees como revenue mechanism.

**Developer Experience**: Speakeasy para SDK generation (TS/Python). Mercury sandbox model (signup separado, dados pré-seedados). Error responses com `doc_url` + `request_log_url` reduzem support burden.

---

## 1. Padrões Contábeis — IFRS/ASC Implementation

### 1.1 Multi-GAAP Architecture

```
Base Ledger (transações reais)
  → IFRS Adjustment Layer (reclassificações, provisões)
  → US GAAP Adjustment Layer (diferentes tratamentos)
  → Local GAAP Adjustment Layer (normas nacionais)
  → Reporting Views (demostrações financeiras por standard)
```

**Padrão comprovado**: base ledger única + camadas de ajuste por standard + views de reporting. Cada layer é uma tabela de ajustes que modifica os valores do base ledger para cada standard.

### 1.2 IFRS 15 — Revenue from Contracts

5 estágios de processamento:
1. **Contract identification**: critérios de identificação (direitos e obrigações mutuamente aceitos, consideração definida, capacidade de pagamento, termos comerciais com substância)
2. **Performance obligations**: identificar obrigações de desempenho distintas (bens/serviços separáveis)
3. **Transaction price**: estimar including variable consideration (descontos, rebate, penalties)
4. **Allocation**: alocar preço via SSP (Standalone Selling Price) — adjusted market, expected cost plus margin, residual
5. **Recognition**: point-in-time vs over-time (critérios: customer simultaneously receives and consumes, entity's performance creates/enhances asset customer controls, no alternative use + enforceable right to payment)

### 1.3 IFRS 16 — Leases

- Right-of-use asset + lease liability reconhecidos no balanço
- Lease liability = PV dos pagamentos de lease ao longo do prazo
- Exceções: short-term leases (<12 meses), low-value assets (<$5k)
- Modification accounting: revaluation do liability + adjustment do ROU asset

### 1.4 IFRS 17 — Insurance Contracts

3 modelos de medição:
- **GMM** (General Measurement Model): premium allocation approach simplificado
- **PAA** (Premium Allocation Approach): para contratos com prazo ≤12 meses
- **VFA** (Variable Fee Approach): para contratos com participações em resultados

Contractual Service Margin (CSM): lucro diferido reconhecido ao longo do período de serviço.

### 1.5 ASC 606 vs IFRS 15 Diferenças

- Principal vs agent: critérios levemente diferentes para determinar quem controla o bem/serviço
- Licensing: ASC 606 tem categorias específicas (right to access vs right to use)
- Contract cost capitalization: ASC 606 mais prescritivo sobre o que capitalizar
- **Implementação**: engine configurável com regras diferenciais por standard

### 1.6 IFRS 18 (2027)

- Novos Mandatory Performance Measures (MPMs) na DRE
- Disagregação obrigatória de receitas e despesas
- **Ação**: plataforma deve suportar IFRS 18 desde o início para evitar refactoring

### 1.7 COA Cross-National Mapping

```
Universal Internal COA (código interno)
  → Mapping Table → SKR03/04 (Alemanha)
  → Mapping Table → PCG (França)
  → Mapping Table → ECF/CTB (Brasil)
  → Mapping Table → US GAAP COA
```

Cada mapping é versionado com effective dates para suportar mudanças regulatórias.

---

## 2. SaaS Metrics & Subscription Billing

### 2.1 Core Metrics com Fórmulas

| Métrica | Fórmula | Target |
|---|---|---|
| **MRR** | Σ(receita mensal por cliente) | Crescente |
| **ARR** | MRR × 12 | — |
| **Churn Rate (logo)** | Clientes perdidos / Total clientes início do período | <5% mensal |
| **Churn Rate (revenue)** | MRR perdido / MRR início do período | <3% mensal |
| **NRR** | (MRR início - contraction - churn + expansion) / MRR início | >100% |
| **Quick Ratio** | (New MRR + Expansion MRR) / (Contraction MRR + Churned MRR) | >4.0 |
| **LTV** | ARPU / Revenue Churn Rate | >3× CAC |
| **CAC** | (Marketing + Sales spend) / Novos clientes | — |
| **Payback Period** | CAC / ARPU (meses) | <12 meses |

### 2.2 MRR Events (Deltas, não Snapshots)

```sql
CREATE TABLE mrr_events (
    event_id UUID PRIMARY KEY,
    client_id UUID NOT NULL,
    event_type TEXT NOT NULL, -- 'new', 'expansion', 'contraction', 'churn', 'reactivation'
    mrr_delta NUMERIC(18,6) NOT NULL, -- positivo para new/expansion, negativo para contraction/churn
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

Events como deltas tipados permitem reconstrução de waterfall de MRR para qualquer período.

### 2.3 ASC 606 para SaaS

- Revenue recognition: ratável sobre o período de serviço
- Deferred revenue: liability enquanto não reconhecida
- Journal entry mensal durante período de serviço:
  ```
  Dr. Deferred Revenue (liability)
  Cr. Revenue (revenue)
  ```
- MRR de contratos anuais: reconhece 1/12 por mês

### 2.4 Dunning Architecture

- Stripe Smart Retries: 8 tentativas em 2 semanas
- Hard decline codes (lost_card, stolen_card, expired_card) = não retryable
- Grace period: 3-7 dias B2B entre past_due e revocation de acesso
- Escalation: email → push → SMS → phone call (B2B high-value)

### 2.5 Subscription State Machine

```
trialing → active → past_due → paused → cancelled
                                      ↑
active ← reactivation ← cancelled ←──┘
active → past_due → grace_period → access_revoked
```

### 2.6 Usage Metering

- **Rating engines**: tiered (faixas), volume (total × preço da faixa), stairstep (escada)
- Event-based tracking: cada evento de uso é registrado com timestamp + tipo + quantidade
- Aggregation windows: diário, semanal, mensal — configurável por plano
- Module stateless: aceita (events, pricing_rules, period) → retorna valor

---

## 3. Localização & i18n

### 3.1 Number Formatting

| Locale | Exemplo | Separador decimal | Agrupamento |
|---|---|---|---|
| US | $1,234,567.89 | . | , |
| Brazil | R$ 1.234.567,89 | , | . |
| Germany | 1.234.567,89 € | , | . |
| India | ₹12,34,567.89 | . | irregular (3+2+2) |
| Japan | ¥1,234,567 | . | , |

**CLDR pattern**: `alt="alphaNextToNumber"` para spacing quando símbolo termina com letra (CA$ vs $).

### 3.2 Currency Formatting

- Símbolo antes ou depois varia por locale ($1,000 vs 1,000 $)
- Negativos: `-$1,000` (US) vs `(1.000,00)` (accounting) vs `-1.000,00 €` (Germany)
- ICU number skeletons: `:: sign-accounting` para negativos entre parênteses automaticamente

### 3.3 Date & Timezone

- **Storage**: UTC sempre
- **Display**: local transaction time (Paris midnight ≠ UTC midnight)
- **Fiscal periods**: determinados por local timezone, não UTC
- **Business days**: convenções variam por país (weekend, holidays)

### 3.4 RTL Support

- Tables: alinhamento invertido (números sempre à direita)
- Charts: mirror horizontal para trend charts
- Currency symbols: posição invertida
- Number rendering: Arabic numerals (não Eastern Arabic) para financeiro

### 3.5 Tax Display

| Region | Padrão | Implementação |
|---|---|---|
| EU | Tax-inclusive (preço final) | Toggle configurable |
| US | Tax-exclusive (preço + tax no checkout) | Default |
| Brazil | Embedded (impostos no preço) | Configurable |

### 3.6 i18n Framework

- **FormatJS (react-intl)**: implementação nativa em Rust (alinhado com D-022), usa `Intl.NumberFormat`
- **next-intl**: bom para Next.js App Router, mesmo engine subjacente
- **ICU MessageFormat**: padrão para plurais, selects, datagrams

---

## 4. Automação & Workflows

### 4.1 Workflow Engine Selection

| Engine | Melhor para | Overhead |
|---|---|---|
| **Temporal.io** | Core financial workflows (approvals, period close, multi-step transactions) | Alto (infra dedicada) |
| **Inngest** | Event-driven side effects (notifications, webhooks, async tasks) | Baixo (serverless) |
| **n8n** | Non-technical workflow building (Zapier-like) | Médio (self-hosted) |
| **Trigger.dev** | Background jobs com retry | Baixo (serverless) |

**Recomendação**: Temporal para core + Inngest para side effects.

### 4.2 Rule Engine

```json
{
  "rules": [
    {
      "id": "expense_approval_1",
      "condition": {
        "field": "amount",
        "operator": ">",
        "value": 10000
      },
      "action": {
        "type": "approval",
        "approvers": ["cfo"],
        "timeout_hours": 48,
        "escalation": ["ceo"]
      },
      "version": "1.0",
      "effective_from": "2026-01-01"
    }
  ]
}
```

Rules como JSONB versionado: rollback capability, UI configuration para não-técnicos, audit trail de mudanças.

### 4.3 Notification Routing

| Urgência | Canais | Exemplo |
|---|---|---|
| Crítica | SMS + Push | Pagamento falhou, fraude detectada |
| Alta | Email + Push | Fatura vence amanhã, aprovação pendente |
| Média | Email + In-app | Relatório mensal disponível |
| Baixa | In-app only | Atualização de sistema |

### 4.4 Webhook Management

- HMAC-SHA256 payload signing (obrigatório desde dia 1)
- Exponential backoff: 7 attempts em 24h
- Full request/response logging para debugging
- Replay functionality (até 30 dias)
- Webhook logs com payload inspector

---

## 5. Marketplace Economics

### 5.1 Stripe Connect Flow Models

| Model | Fluxo | Quando usar |
|---|---|---|
| **Direct charges** | Platform cobra → seller recebe direto | Seller tem própria conta Stripe |
| **Destination charges** | Platform cobra → transfere para seller | Mais comum, mais simples |
| **Separate charges + transfers** | Platform cobra → transferência separada | Multi-party splits |

### 5.2 Escrow Pattern

```
Pagamento recebido → Balance: pending (hold)
  → Condição atendida (entrega confirmada)
  → Balance: available (liberado)
  → Transferência para seller
```

Stripe: `pending` → `available` (configurable release timing).

### 5.3 Marketplace Accounting

```
Dr. Bank (valor total)
  Cr. Deferred Revenue (valor do seller — escrowed)
  Cr. Commission Revenue (taxa da plataforma)

Após release:
Dr. Deferred Revenue
  Cr. Bank (transferência para seller)
```

### 5.4 Brazil Marketplace Requirements

- CPF/CNPJ verification (obrigatório)
- Liveness checks (face match)
- UBO (Ultimate Beneficial Owner) verification para ownership >25%
- Nota fiscal para cada transação (NFe ou NFS-e)

### 5.5 Marketplace Metrics

| Métrica | Fórmula |
|---|---|
| **GMV** | Total de vendas brutas |
| **Take Rate** | Commission Revenue / GMV |
| **Net Revenue** | Commission Revenue - payment processing costs |
| **Seller Payouts** | GMV - Commission Revenue - refunds |

---

## 6. Developer Experience

### 6.1 SDK Generation

- **Speakeasy**: melhor para TS/Python — SDKs idiomáticos, debugáveis, publicáveis com docs auto-gerados
- **OpenAPI Generator**: alternativa open-source, suporta 40+ linguagens
- **Workflow**: OpenAPI spec → generate SDK → publish to npm/PyPI → version alongside API

### 6.2 Sandbox Environment

**Mercury model** (mais simples):
- Signup separado para sandbox
- Dados pré-seedados (contas fictícias, transações de exemplo)
- Base URL dedicada (sandbox.mercury.com)
- API keys sandbox vs production

### 6.3 Error Response

```json
{
  "error": {
    "type": "invalid_request_error",
    "code": "amount_mismatch",
    "message": "Debits (45000) != credits (50000)",
    "param": "lines[1].credit",
    "doc_url": "https://docs.cashflow.app/errors#amount_mismatch",
    "request_log_url": "https://dashboard.cashflow.app/logs/req_abc123"
  }
}
```

`doc_url` + `request_log_url` reduzem drasticamente o support burden.

### 6.4 Rate Limiting

- Per-key limits com burst handling
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Retry-After header no 429
- Quotas mensais por plano (free: 1k, pro: 100k, enterprise: ilimitado)

### 6.5 Versioning & Deprecation

- Sunset header: `Sunset: Sat, 01 Jan 2027 00:00:00 GMT`
- Migration guides para cada breaking change
- Compatibility matrix publicada
- 12 meses de suporte para versões deprecated

---

## 7. Números Finais — 4 Rodadas Completas

| Rodada | Findings | Fontes | Escopo |
|---|---|---|---|
| 1 (Panorâmica) | F1-F6 | 72 | Módulos, indústrias, concorrentes, compliance, features, integrações |
| 2 (Técnica) | F7-F12 | 84 | Database, events, plugins, SPED/NFe, API, UI config |
| 3 (Infra) | F13-F18 | 90 | Security, performance, DevOps, migration, testing, mobile |
| 4 (Negócio) | F19-F24 | 84 | Accounting standards, SaaS metrics, localization, automation, marketplace, DX |
| **Total** | **24 findings files** | **330+ fontes** | **Cobertura completa** |

### Dimensões cobertas (24)

1. Core modules (GL, COA, AP, AR, Bank Rec)
2. Industry-specific (retail, SaaS, manufacturing, marketplace, real estate, healthcare, agriculture, services)
3. Competitor architecture (Xero, FreshBooks, Wave, Nubank, Mercado Pago)
4. Compliance Brasil (SPED, NFe, NFS-e, eSocial, CNPJ, Simples)
5. Advanced features (multi-entity, multi-currency, revenue rec, fixed assets, inventory)
6. Integration ecosystem (Open Finance, payment gateways, government APIs)
7. Database schema (hybrid core+extension, event sourcing, CQRS, RLS)
8. Event-driven architecture (domain events, sagas, idempotency, Redis Streams)
9. Plugin/extension system (manifests, lifecycle, auto-install, SemVer)
10. API design (REST, GraphQL, pagination, versioning, webhooks)
11. Config-driven UI (JSON schema forms, dashboards, PDF, white-label)
12. Security (encryption, auth, RBAC, PCI, audit trail, LGPD)
13. Performance (indexing, caching, pooling, partitioning)
14. DevOps (Vercel, migrations, feature flags, backup/DR)
15. Data migration (OFX, CNAB, QuickBooks, Xero, idempotency)
16. Testing (property-based, golden master, time-travel, contract, compliance)
17. Mobile/PWA (Serwist, hybrid caching, IndexedDB, WebAuthn)
18. Accounting standards (IFRS 15/16/17/18, ASC 606, multi-GAAP)
19. SaaS metrics (MRR, churn, NRR, LTV, CAC, Quick Ratio)
20. Localization (number/currency/date formatting, RTL, timezone, tax display)
21. Workflow automation (Temporal, rules engine, notifications, webhooks)
22. Marketplace economics (Stripe Connect, escrow, settlement, KYC)
23. Developer experience (SDK generation, sandbox, error handling, versioning)
24. Subscription billing (models, dunning, lifecycle, usage metering)

---

## Open Questions Restantes

1. **Transfer pricing**: módulo enterprise não coberto
2. **IFRS 17 insurance**: implementação profunda não coberta
3. **Pricing model**: como precificar módulos (freemium vs tiered vs per-module)
4. **Competitive differentiation**: o que o cashflow faz que QuickBooks/Xero não fazem
5. **Go-to-market**: target market inicial (freelancers? MEIs? empresas médias?)
6. **Real-time collaboration**: múltiplos usuários editando o mesmo período fiscal simultaneamente
