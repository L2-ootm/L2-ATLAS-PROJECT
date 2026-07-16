# Modular Cashflow Universal — Relatório: Onboarding, Expansão Internacional, Resiliência, PLG, Marketplace, Reporting

> Generated 2026-07-09 · 42 findings files totais · 590+ fontes · workspace: research/modular-cashflow/

## Executive Summary

**Onboarding**: Ghost converteu 1.000% mais com progress bar de 5 passos. Meta: <5 minutos para primeira invoice. 60-85% setup completion é healthy. Industry-based COA auto-generation elimina o friction #1. Import wizard deve suportar QuickBooks, Xero, FreshBooks, CSV com auto-column-mapping. Bank connection é o maior drop-off (17% abandonment) — oferecer fallback manual. Checklist 5-7 items maximiza completion via Zeigarnik effect.

**Expansão Internacional**: LatAm-first强烈推荐 (IFRS compartilhado, VAT systems, instant payments). EU oferece PSD2 passport (1 licença = 27 países) mas GDPR é caro. US requer 50+ state MTLs — universo regulatório diferente. IFRS é padrão global; US GAAP é outlier — design for IFRS first. Data residency requer isolamento arquitetural por região. Multi-entity obrigatório desde o dia 1.

**Resiliência**: Patroni com synchronous replication (quorum mode) = zero data loss + automatic failover. Circuit breakers NÃO tripam em 4xx (business validation) — só em infrastructure failures (5xx, timeout). Todas retryable operations DEVEM ser idempotent. Error budget policy: <25% budget → freeze non-critical deploys. Multi-region: active-warm standby com async replication + manual approval para failover.

**PLG**: Invoice-as-viral-vector = strongest PLG play (cada invoice enviada é canal de acquisition). Activation signals: first invoice, bank connected, team invited. PLG 2.0 (2026): API/MCP-first architecture é table stakes. PQL model bridges SMB self-serve → enterprise sales. Net Dollar Retention >120% = north star metric. Time-to-value benchmark dropped para 60 segundos.

**Marketplace**: Shopify 0% on first $1M e Xero 0% aceleram adoption. Seed com 15-20 plugins essenciais. 0% commission até ~50 active plugins, depois 15% em paid plugins. SDK: extension points + sandboxed data access + event system + SemVer. Mandatory security review antes de listing é non-negotiable. 3-tier certification: Community/Verified/Certified.

**Reporting**: IFRS balance sheet orders by liquidity (least→most); US GAAP reverses. Consolidation elimina ALL intragroup balances + unrealized profit. XBRL taxonomy usa 5 linkbases. Template engine: YAML/JSON → calculation → renderer → distribution. Drill-down: summary → line item → account group → ledger → journal entry → source document. SPED usa fixed-width TXT; DCTF usa XML — format-specific renderers.

---

## 1. Onboarding & Setup Wizard

### 1.1 Setup Flow (5 steps)

```
Step 1: Industry selection → auto-generate COA (Restaurant → 45 contas pré-built)
Step 2: Tax regime selection (MEI/ME/EPP/Lucro Presumido/Lucro Real)
Step 3: Invoice template customization (logo, colors, payment terms)
Step 4: Bank connection (Open Finance / manual entry fallback)
Step 5: First invoice creation (activation event — "magic action")
```

### 1.2 Time-to-Value Targets

| Métrica | Target | Benchmark |
|---|---|---|
| Time to first invoice | <5 minutos | Stripe: <3 min |
| Setup completion | 60-85% | Healthy range |
| Activation rate | >40% | Trial → first key action |
| Bank connection drop-off | <17% | Industry average |

### 1.3 Import Wizard

```
Select source (QuickBooks / Xero / FreshBooks / CSV)
  → Upload file
  → Auto-detect columns + preview mapping
  → User confirms/adjusts mapping
  → Validate (duplicates, balance check)
  → Import with progress bar
  → Summary: X records imported, Y duplicates skipped, Z errors
```

### 1.4 Checklist (Zeigarnik Effect)

```
□ Complete profile (company info)
□ Create first invoice
□ Connect bank account
□ Add first client
□ Set up invoice template
□ Invite team member
□ Run first report
```

5-7 items máximo. Completion unlocks advanced features.

### 1.5 Trust Building

- Explain WHY data is needed antes de pedir informações sensíveis (Mint pattern)
- Show security badges, certifications, encryption info
- Offer manual entry fallback para bank connection

---

## 2. Expansão Internacional

### 2.1 Roadmap Recomendado

| Fase | Mercado | Razão |
|---|---|---|
| 1 | Brasil | Home market, Pix nativo |
| 2 | Mexico, Colombia | IFRS compartilhado, VAT similar, LatAm culture |
| 3 | Portugal, Spain | LatAm bridge, EU access |
| 4 | EU (via PSD2 passport) | 1 licença = 27 países |
| 5 | US | 50+ state MTLs, universo diferente |

### 2.2 Comparativo por País

| Aspecto | Brasil | Mexico | Colombia | US | EU |
|---|---|---|---|---|---|
| Accounting | BR GAAP → IFRS | IFRS | IFRS | US GAAP | IFRS |
| Tax system | 9+ impostos | IVA 16% | IVA 19% | Sales tax (50 states) | VAT 20-27% |
| Instant payment | Pix (200M users) | CoDi/DiMo | PSE | FedNow | SEPA Instant |
| Data residency | LGPD | LFPDPPP | Law 1581 | CCPA/state laws | GDPR |
| Regulatory | Simple | Moderate | Moderate | Complex (50 states) | Complex (27 countries) |

### 2.3 Multi-Currency Architecture

```sql
-- Base currency configuration per entity
CREATE TABLE entity_config (
    entity_id UUID PRIMARY KEY,
    base_currency TEXT NOT NULL DEFAULT 'BRL',
    reporting_currency TEXT NOT NULL DEFAULT 'USD',
    consolidation_currency TEXT DEFAULT 'USD',
    fx_rate_source TEXT DEFAULT 'BCB' -- BCB, ECB, Fed
);

-- FX rates (multi-source)
CREATE TABLE fx_rates (
    id UUID PRIMARY KEY,
    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    rate NUMERIC(18,8) NOT NULL,
    source TEXT NOT NULL,
    effective_date DATE NOT NULL,
    UNIQUE(base_currency, quote_currency, source, effective_date)
);
```

### 2.4 Data Residency

| Região | Requisito | Arquitetura |
|---|---|---|
| Brasil | LGPD | DB primário no Brasil |
| EU | GDPR | DB separado na EU |
| US | CCPA/state laws | DB nos EUA |
| Global | Variável | Multi-region com routing |

---

## 3. Resiliência de Infraestrutura

### 3.1 SLA/SLO/SLI

| Nível | Target | Downtime/ano |
|---|---|---|
| 99.9% | SLI: successful requests | 8,76 horas |
| 99.95% | SLO: transaction success | 4,38 horas |
| 99.99% | SLA: core transactions | 52,6 minutos |

### 3.2 PostgreSQL HA com Patroni

```
Primary (synchronous replication)
  → Replica 1 (sync, quorum member)
  → Replica 2 (sync, quorum member)
  → Replica 3 (async, read-only)

Failover automático via etcd/consul cluster
Zero data loss com synchronous quorum mode
```

### 3.3 Circuit Breaker Pattern

```typescript
const circuitBreaker = new CircuitBreaker({
  failureThreshold: 5,        // 5 failures para trip
  successThreshold: 3,        // 3 successes para half-open
  timeout: 30000,             // 30s timeout
  excludeStatusCodes: [400, 401, 403, 404, 422], // NÃO trip em 4xx
  retryTimeout: 60000,        // 60s antes de retry
});
```

### 3.4 Graceful Degradation

| Componente | Failure | Impact | Degradation |
|---|---|---|---|
| Core transactions | Down | CRITICAL | Alert + manual |
| Payment gateway | Down | HIGH | Queue payments |
| Analytics | Down | LOW | Skip, retry later |
| Notifications | Down | LOW | Queue for later |
| AI categorization | Down | LOW | Fallback to rules |

### 3.5 Error Budget Policy

```
SLO: 99.95% successful transactions
Error budget: 0.05% = ~22 minutos/mês

If remaining budget < 25%:
  → Freeze non-critical deploys
  → Focus on reliability improvements
  → No new features until budget recovered
```

### 3.6 Multi-Region

- **Active-warm standby**: primary + warm standby em região secundária
- **Async replication**: <1 second lag
- **Failover**: manual approval (regulatory requirement para dados financeiros)
- **DNS routing**: route53/geolocation routing para failover

---

## 4. Product-Led Growth (PLG)

### 4.1 Invoice-as-Viral-Vector

Cada invoice enviada é um canal de acquisition:
```
Usuário cria invoice → envia para cliente
  → Cliente vê "Powered by L2 Cashflow"
  → Cliente clica → landing page → signup
  → Ciclo se repete
```

### 4.2 Activation Signals (PQL Indicators)

| Signal | Weight | When |
|---|---|---|
| First invoice created | 30% | Within 24h |
| Bank account connected | 25% | Within 72h |
| Team member invited | 20% | Within 1 week |
| Second invoice sent | 15% | Within 2 weeks |
| Report generated | 10% | Within 1 month |

### 4.3 PLG Funnel

```
Visitor → Signup (free) → Activate (first invoice) → Convert (paid) → Expand (more modules/users) → Advocate (referral)
```

### 4.4 PLG 2.0 (2026)

- API/MCP-first architecture é table stakes
- Machine-readable pricing (API-first)
- Moat = proprietary domain context, not UI
- Agentic PLG: AI assistants onboard users

### 4.5 Metrics Framework

| Métrica | Target | Fórmula |
|---|---|---|
| Activation rate | >40% | Users completing magic action / signups |
| Time-to-value | <5 min | Time from signup to first invoice |
| Conversion rate | >5% | Paid / Free signups |
| Net Dollar Retention | >120% | (Starting MRR + expansion - contraction - churn) / Starting MRR |
| Viral coefficient | >0.5 | Invites sent per user × conversion rate |

---

## 5. Plugin Marketplace

### 5.1 Revenue Share

| Fase | Commission | Target |
|---|---|---|
| Seed (0-50 plugins) | 0% | Attract developers |
| Growth (50-200) | 15% em paid | Monetize ecosystem |
| Mature (200+) | 15-20% | Industry standard |

### 5.2 SDK Design

```typescript
// Plugin SDK structure
interface CashflowPlugin {
  manifest: PluginManifest;        // metadata, dependencies, permissions
  activate(ctx: PluginContext): void;  // called on load
  deactivate(): void;              // called on unload
  onEvent(event: FinancialEvent): Promise<Action[]>;  // event handlers
  contributes: {
    routes: RouteConfig[];         // UI routes
    sidebar: SidebarConfig[];      // navigation items
    api: ApiConfig[];              // API endpoints
    reports: ReportConfig[];       // report templates
  };
}
```

### 5.3 Quality Assurance

```
Plugin submitted → Automated checks (lint, test, security scan)
  → Sandbox testing (run in isolated environment)
  → Manual review (security + UX)
  → Certification (Community / Verified / Certified)
  → Published to marketplace
```

### 5.4 Certification Tiers

| Tier | Requisitos | Benefits |
|---|---|---|
| Community | Passes automated checks | Basic listing |
| Verified | + Manual review + 10+ installs | Featured in search |
| Certified | + 100+ installs + 4.5+ rating + SLA commitment | Top placement + co-marketing |

### 5.5 Deprecation Policy

- 6-month deprecation window for breaking changes
- Compatibility matrices publicadas
- Migration guides para cada breaking change

---

## 6. Reporting Avançado

### 6.1 Standard Financial Statements

**Balance Sheet (IFRS)**:
```
Assets
  Non-current assets
    Property, plant and equipment
    Intangible assets
    Financial assets
  Current assets
    Inventories
    Trade and other receivables
    Cash and cash equivalents

Liabilities
  Current liabilities
    Trade and other payables
    Current tax liabilities
  Non-current liabilities
    Long-term borrowings
    Deferred tax liabilities

Equity
  Share capital
  Retained earnings
  Other comprehensive income
```

**US GAAP reverses**: Current assets first, then non-current.

### 6.2 Consolidation

```
Entity A (parent)
  + Entity B (subsidiary)
  + Entity C (subsidiary)
  = Consolidated
    - Eliminate: intercompany receivables/payables
    - Eliminate: intercompany revenue/expense
    - Eliminate: unrealized profit on intragroup transactions
    - Add: minority interests
    - Translate: foreign subsidiaries at closing rate
```

### 6.3 XBRL Taxonomy

5 linkbases:
1. **Label**: human-readable names for concepts
2. **Reference**: links to IFRS/GAAP standard paragraphs
3. **Calculation**: mathematical relationships (A + B = C)
4. **Definition**: hierarchical relationships
5. **Presentation**: display ordering and grouping

### 6.4 Report Engine Architecture

```
YAML/JSON Template
  → Calculation Engine (formulas, aggregations)
  → Data Provider (query database, apply filters)
  → Renderer (PDF, Excel, HTML, XBRL)
  → Distribution (email, API, download)
```

### 6.5 Drill-Down Path

```
Summary (Balance Sheet total)
  → Line Item (Total Assets)
    → Account Group (Current Assets)
      → Account (Cash and equivalents)
        → Ledger (account transactions)
          → Journal Entry (specific entry)
            → Source Document (invoice, receipt)
```

Cada nível carrega drill-path metadata para navegação.

### 6.6 Brazilian Regulatory Reports

| Formato | Uso | Generator |
|---|---|---|
| SPED TXT (fixed-width) | ECD, ECF, EFD | Format-specific renderer |
| SPED XML | DCTF | XML renderer |
| NFe XML | Nota Fiscal | XML signing + SEFAZ |
| NFS-e XML | Serviço | ABRASF renderer |

---

## 7. Números Finais — 7 Rodadas

| Rodada | Findings | Fontes | Escopo |
|---|---|---|---|
| 1 | F1-F6 | 72 | Módulos, indústrias, concorrentes, compliance, features, integrações |
| 2 | F7-F12 | 84 | Database, events, plugins, SPED/NFe, API, UI config |
| 3 | F13-F18 | 90 | Security, performance, DevOps, migration, testing, mobile |
| 4 | F19-F24 | 84 | Accounting standards, SaaS metrics, localization, automation, marketplace, DX |
| 5 | F25-F30 | 90 | Competitive, AI/ML, analytics, collaboration, a11y, contracts |
| 6 | F31-F36 | 90 | Pricing, treasury, budgeting, payroll, data governance, ESG |
| 7 | F37-F42 | 84 | Onboarding, international expansion, resilience, PLG, plugin marketplace, reporting |
| **Total** | **42 findings files** | **590+ fontes** | **Cobertura completa** |

### 42 dimensões cobertas

1-36: (anteriores)
37. Onboarding & setup wizard (UX, import, templates, checklists, analytics)
38. Expansão internacional (LatAm-first, multi-currency, data residency, regulatory)
39. Resiliência (HA, Patroni, circuit breakers, graceful degradation, multi-region)
40. Product-Led Growth (invoice-as-viral, PQL, activation, metrics)
41. Plugin marketplace (SDK, revenue share, certification, governance)
42. Reporting avançado (statements, consolidation, XBRL, drill-down, regulatory)

---

## Open Questions Restantes

1. **Pricing final**: testar com usuários reais
2. **AI roadmap**: categorização como quick win
3. **Real-time collaboration**: Yjs desde início?
4. **Open-source %**: quanto open-source vs proprietary?
5. **Go-to-market**: MEIs primeiro ou empresas médias?
6. **Multi-tenant**: shared DB ou dedicated para enterprise?
7. **Marketplace seed**: quais 15-20 plugins construir primeiro?
8. **Resiliência**: quando implementar Patroni (desde início ou depois)?
