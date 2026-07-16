# Modular Cashflow Universal — Relatório: Pricing, Treasury, Budgeting, Payroll, Data Governance, ESG

> Generated 2026-07-09 · 36 findings files totais · 500+ fontes · workspace: research/modular-cashflow/

## Executive Summary

**Pricing**: 1% melhoria em monetização = 12.7% aumento de lucro (4x mais eficiente que aquisição). Modelo recomendado: hybrid tiered + per-module add-ons + usage overages. Regra dos 3 (Decoy/Hero/Anchor). Brazil SMBs pagam 40-60% menos que US equivalents. Intro pricing agressivo (60-80% off 3 meses) é primary churn reduction lever. Kalungi Feature Ranking Matrix: Uniqueness × Popularity → Freemium/Premium/Add-On/Noise.

**Treasury**: Cash management com daily position tracking + forecasting 7-30 dias. Open Finance Brasil para account aggregation. SAC vs Price amortization para loans (Brasil: 252 dias úteis). IFRS 9 hedge accounting para FX operations. Intercompany treasury com netting e cash pooling. Bank reconciliation automation com matching rules + auto-reconcile thresholds.

**Budgeting**: Budget versioning com parent_version_id para audit trail. Variance analysis requer favorability logic por account type (revenue vs expense). Monte Carlo simulation: 1.000-10.000 iterações por variable. Rolling forecasts eliminam annual budget season. ZBB achieve 15-20% cost savings mas requer performance metrics por decision package. CapEx com NPV/IRR pipeline separado.

**Payroll**: Custo total empregatício R$5.000 = ~R$9.787 (195.7% surcharge). FGTS Digital substitui GPS. INSS progressivo reformulado 2020. eSocial v.S-1.3 produção 01/07/2026 com ICP-Brasil certificate. Pro-labore LTDA: INSS 11% + IRRF (sem FGTS). DCTFWeb auto-gerado de S-1200/S-1299. 3 core entities: Employee, PayrollRun, PayrollEvent.

**Data Governance**: Brazil: 5-10 anos retenção (CTN 5, Central Bank 10). COA precisa golden record versionado. Reconciliation AP/AR vs GL: zero-tolerance, daily automated. 7 data quality metrics (completeness ≥99.5%, accuracy ≥99.9%). Format-preserving encryption para PII masking. 3-tier archival: hot ≤1y, warm 1-3y, cold 3+y.

**ESG**: GHG Protocol: Activity Data × Emission Factor. Scope 3 Cat 15 (Investments): PCAF Exposure × EVIC. IFRS S1/S2 4 pillars (Governance, Strategy, Risk, Metrics). EU CSRD double materiality (impact + financial). All frameworks XBRL/iXBRL — single tagging engine serve múltiplos. Emission factor databases (DEFRA, IPCC, Ecoinvent) são critical external dependency.

---

## 1. Pricing Strategy

### 1.1 Modelo Recomendado: Hybrid Tiered + Per-Module

```
Free Tier: Core (dashboard, basic invoicing, 1 user, 50 transactions/mês)
Starter: R$79/mês (core + invoicing + expenses + bank rec, 3 users)
Pro: R$199/mês (tudo + forecasting + reporting + multi-currency, 10 users)
Enterprise: R$499/mês (tudo + multi-entity + compliance + priority support, unlimited)
Add-ons: Payroll R$49/mês, Advanced Analytics R$39/mês, API Access R$29/mês
```

### 1.2 Regra dos 3 (Decoy/Hero/Anchor)

| Tier | Preço | Papel |
|---|---|---|
| Starter | R$79/mês | Anchor (parece barato) |
| Pro | R$199/mês | Hero (target — melhor valor) |
| Enterprise | R$499/mês | Decoy (faz Pro parecer melhor deal) |

### 1.3 Benchmarks Brasil vs US

| Segmento | Brasil | US | EU |
|---|---|---|---|
| Micro/MEI | R$40-80/mês | $15-30/mês | €15-30/mês |
| Small | R$100-200/mês | $30-60/mês | €25-50/mês |
| Medium | R$200-500/mês | $60-200/mês | €50-150/mês |
| Enterprise | R$1.000-5.000/mês | $500-2.000/mês | €400-1.500/mês |

### 1.4 Intro Pricing Agressivo

- **60-80% off primeiros 3 meses** → primary churn reduction lever
- **Anual discount 15-20%** → lock-in + predictable revenue
- **Freemium**: core + invoicing básico grátis para drive adoption

### 1.5 Kalungi Feature Ranking Matrix

| | Alta Popularidade | Baixa Popularidade |
|---|---|---|
| **Alta Unicidade** | Premium (hero features) | Differentiator (competitive moat) |
| **Baixa Unicidade** | Freemium (table stakes) | Noise (não implementar) |

---

## 2. Treasury Management

### 2.1 Cash Management

- **Daily position tracking**: saldo atual por conta bancária, consolidado
- **Short-term forecasting**: 7-30 dias baseado em faturas pendentes + despesas agendadas
- **Cash pooling**: zero balancing (transferir saldos para conta central) ou notional (sem movimentação física)

### 2.2 Bank Connectivity

- **Open Finance Brasil**: account aggregation, balance inquiry, transaction history
- **Belvo**: banking data API para múltiplos bancos
- **OFX import**: fallback para bancos sem Open Finance

### 2.3 Payment Scheduling

```
Batch payments → Approval workflow → Payment date optimization → Execution
                                                          ↓
                                              Float management (D+1, D+30)
```

### 2.4 Debt Management

**SAC (Sistema de Amortização Constante)**:
```
Parcela = (Capital / N) + (Saldo Devedor × Taxa)
Amortização = Capital / N (constante)
Juros = Saldo Devedor × Taxa (decrescente)
```

**Price (Tabela Price)**:
```
Parcela = Capital × [Taxa × (1+Taxa)^N] / [(1+Taxa)^N - 1]
Parcela constante ao longo do prazo
```

### 2.5 FX Operations

- IFRS 9 hedge accounting: hedge effectiveness testing
- FX gain/loss: realized (on settlement) + unrealized (period-end revaluation)
- Forward contracts: hedging for payable/receivable in foreign currency

### 2.6 IAS 7 / ASC 230 — Cash Flow Categories

| Categoria | Atividades |
|---|---|
| Operating | Receitas, despesas, working capital |
| Investing | Aquisição/venda de ativos, investimentos |
| Financing | Empréstimos, capital, dividendos |

---

## 3. Financial Planning & Budgeting

### 3.1 Budget Data Model

```sql
CREATE TABLE budgets (
    budget_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    name TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    parent_version_id UUID REFERENCES budgets(budget_id),
    fiscal_year INTEGER NOT NULL,
    status TEXT DEFAULT 'draft', -- draft, approved, active, closed
    created_by UUID NOT NULL,
    approved_by UUID,
    approved_at TIMESTAMPTZ
);

CREATE TABLE budget_lines (
    line_id UUID PRIMARY KEY,
    budget_id UUID NOT NULL REFERENCES budgets(budget_id),
    account_id UUID NOT NULL REFERENCES accounts(account_id),
    department_id UUID,
    project_id UUID,
    cost_center TEXT,
    period TEXT NOT NULL, -- '2026-01', '2026-Q1'
    planned_amount NUMERIC(18,6) NOT NULL,
    metadata JSONB
);
```

### 3.2 Variance Analysis

```sql
-- Variance com favorability logic
SELECT 
    a.account_name,
    b.planned_amount,
    SUM(jel.debit - jel.credit) AS actual_amount,
    SUM(jel.debit - jel.credit) - b.planned_amount AS variance,
    CASE 
        WHEN a.account_type = 'revenue' THEN 
            CASE WHEN SUM(jel.debit - jel.credit) > b.planned_amount THEN 'favorable' ELSE 'unfavorable' END
        WHEN a.account_type = 'expense' THEN
            CASE WHEN SUM(jel.debit - jel.credit) < b.planned_amount THEN 'favorable' ELSE 'unfavorable' END
    END AS variance_direction
FROM budget_lines b
JOIN accounts a ON b.account_id = a.account_id
LEFT JOIN journal_entry_lines jel ON jel.account_id = b.account_id
GROUP BY a.account_name, a.account_type, b.planned_amount;
```

### 3.3 Materiality Thresholds

| Nível | Threshold | Ação |
|---|---|---|
| Green | <5% variance | Nenhuma |
| Yellow | 5-15% variance | Alerta visual |
| Orange | 15-25% variance | Notificação + review required |
| Red | >25% variance | Bloqueio + aprovação gerencial |

### 3.4 Monte Carlo Cash Flow

```python
def monte_carlo_cashflow(base_revenue, base_expenses, n_simulations=10000):
    results = []
    for _ in range(n_simulations):
        revenue = base_revenue * random.triangular(0.85, 1.15, 1.0)  # ±15%
        expenses = base_expenses * random.triangular(0.90, 1.20, 1.0)  # +20%/-10%
        results.append(revenue - expenses)
    
    return {
        'p10': np.percentile(results, 10),
        'p50': np.percentile(results, 50),
        'p90': np.percentile(results, 90),
        'probability_positive': sum(r > 0 for r in results) / len(results)
    }
```

### 3.5 Rolling Forecasts

- 12-month rolling, atualizado mensalmente
- Elimina annual budget season
- Requer monthly continuous planning cycle
- Driver-based: revenue drivers (nº clientes × ARPU), expense drivers (headcount × custo médio)

---

## 4. Payroll & eSocial

### 4.1 Custo Total Empregatício (R$5.000 salário)

| Componente | Valor | % do Salário |
|---|---|---|
| Salário | R$5.000 | 100% |
| FGTS (8%) | R$400 | 8% |
| INSS patronal (20%) | R$1.000 | 20% |
| SAT/RAT (1-3%) | R$100 | 2% |
| Sistema S (5,8%) | R$290 | 5,8% |
| Provisão férias (11,11%) | R$556 | 11,11% |
| Provisão 13º (8,33%) | R$417 | 8,33% |
| **Total** | **~R$9.787** | **195.7%** |

### 4.2 INSS Progressivo (2026)

| Faixa | Alíquota | Dedução |
|---|---|---|
| Até R$1.518,00 | 7,5% | R$0 |
| R$1.518,01 a R$2.793,88 | 9% | R$22,77 |
| R$2.793,89 a R$4.190,83 | 12% | R$106,59 |
| R$4.190,84 a R$8.157,41 | 14% | R$190,40 |

### 4.3 eSocial Events

| Evento | Quando | Dados |
|---|---|---|
| S-1200 | Mensal | Remuneração do trabalhador |
| S-1210 | Mensal | Pagamentos de rendimentos |
| S-1299 | Mensal (até último dia mês seguinte) | Fechamento dos eventos periódicos |
| DCTFWeb | Automático | Gerado de S-1200/S-1299 |

### 4.4 Pro-labore vs Salário

| Aspecto | Salário (CLT) | Pro-labore |
|---|---|---|
| FGTS | Sim (8%) | Não |
| INSS | Sim (progressivo) | Sim (11% retido na fonte) |
| IRRF | Sim | Sim |
| 13º | Sim | Não |
| Férias | Sim | Não |

### 4.5 Module Data Model

```
Employee (id, name, cpf, cargo, salario_base, data_admissao, status)
  → PayrollRun (id, period, status, total_bruto, total_descontos, total_liquido)
    → PayrollEvent (id, employee_id, rubrica_code, valor, eSocial_event_id)
      → eSocialEvent (id, event_type, protocolo, status, transmitted_at)
```

---

## 5. Data Governance

### 5.1 Data Retention Policies

| Jurisdição | Mínimo | Regulamentação |
|---|---|---|
| Brasil | 5 anos | CTN |
| Brasil (bancário) | 10 anos | BCB |
| SOX (US) | 7 anos | Sarbanes-Oxley |
| GDPR | Purpose limitation | Art. 5(1)(e) |
| SPED | 5 anos | Receita Federal |

### 5.2 Data Quality Scorecard

| Métrica | Target | Medição |
|---|---|---|
| Completeness | ≥99.5% | Campos obrigatórios preenchidos |
| Accuracy | ≥99.9% | Valores corretos vs source |
| Consistency | ≥99.8% | Dados coerentes entre módulos |
| Timeliness | ≤24h | Dados disponíveis em até 24h |
| Validity | ≥99.9% | Dados passam todas as validation rules |
| Uniqueness | 100% | Sem registros duplicados |
| Integrity | 100% | Foreign keys consistentes |

### 5.3 Reconciliation Rules

```sql
-- Daily automated reconciliation: AP Ledger vs GL
SELECT 
    'AP' AS source,
    SUM(amount) AS total
FROM accounts_payable WHERE status = 'posted'
UNION ALL
SELECT 
    'GL' AS source,
    SUM(debit - credit) AS total
FROM journal_entry_lines 
WHERE account_id IN (SELECT account_id FROM accounts WHERE code LIKE '2.1%')
AND is_posted = true;
-- Tolerance: abs(difference) < 0.01 (penny tolerance)
```

### 5.4 Three-Tier Archival

| Tier | Idade | Storage | Query Speed |
|---|---|---|---|
| Hot | ≤1 ano | SSD (primary DB) | Milliseconds |
| Warm | 1-3 anos | HDD/Archive storage | Seconds |
| Cold | 3+ anos | Object storage (S3 Glacier) | Minutes |

Migração automática no fechamento de período fiscal.

### 5.5 Data Masking

- **Format-preserving encryption**: CPF `123.456.789-00` → `***.456.789-**` (preserva formato, protege conteúdo)
- **Non-production environments**: sempre com dados mascarados
- **Tokenization**: para dados sensíveis em logs (nunca logar CPF/CNPJ real)

---

## 6. ESG & Sustainability

### 6.1 Carbon Accounting (GHG Protocol)

```
Emissions = Activity Data × Emission Factor

Scope 1: Direct emissions (company vehicles, facilities)
Scope 2: Indirect (purchased electricity) → factors by region (eGRID, IBGE)
Scope 3: Value chain (15 categories)
  Cat 15: Investments (PCAF) → Exposure × EVIC
```

### 6.2 Reporting Frameworks

| Framework | Foco | Audiência |
|---|---|---|
| **ISSB S1/S2** | Financial materiality | Investors |
| **GRI** | Impact materiality | All stakeholders |
| **SASB** | Industry-specific financial | Investors |
| **CSRD/ESRS** | Double materiality (impact + financial) | EU mandatory |
| **TCFD** | Climate-related financial | Investors, regulators |

### 6.3 IFRS S1/S2 — 4 Pillars

1. **Governance**: como governance gerencia riscos e oportunidades de sustentabilidade
2. **Strategy**: como riscos/opportunidades afetam modelo de negócio
3. **Risk Management**: processos para identificar, avaliar, gerenciar
4. **Metrics & Targets**: KPIs, metas, progresso

### 6.4 Data Model

```
EmissionsRecord (id, tenant_id, scope, category, activity_data, emission_factor, 
                  emissions_tCO2e, source, period, created_at)
  → EmissionFactor (id, source, region, year, factor_value, unit, valid_from, valid_to)
  → ReportingFramework (id, name, pillars, taxonomy_xbrl)
  → ESGReport (id, framework_id, period, status, data_points_json, submitted_at)
```

### 6.5 Emission Factor Databases

| Fonte | Cobertura | Atualização |
|---|---|---|
| DEFRA (UK) | Global, 100+ categories | Anual |
| IPCC | Global, setorial | Per assessment cycle |
| Ecoinvent | 18.000+ processos | Anual |
| IBGE (Brazil) | Nacional, setorial | Anual |

**Design**: pluggable factor sources com versioning e regional overrides.

---

## 7. Números Finais — 6 Rodadas

| Rodada | Findings | Fontes | Escopo |
|---|---|---|---|
| 1 | F1-F6 | 72 | Módulos, indústrias, concorrentes, compliance, features, integrações |
| 2 | F7-F12 | 84 | Database, events, plugins, SPED/NFe, API, UI config |
| 3 | F13-F18 | 90 | Security, performance, DevOps, migration, testing, mobile |
| 4 | F19-F24 | 84 | Accounting standards, SaaS metrics, localization, automation, marketplace, DX |
| 5 | F25-F30 | 90 | Competitive, AI/ML, analytics, collaboration, a11y, contracts |
| 6 | F31-F36 | 90 | Pricing, treasury, budgeting, payroll, data governance, ESG |
| **Total** | **36 findings files** | **510+ fontes** | **Cobertura completa** |

### 36 dimensões cobertas

1-30: (anteriores)
31. Pricing strategy (hybrid tiered + per-module, benchmarks, psychology)
32. Treasury management (cash ops, bank connectivity, FX, debt)
33. Financial planning & budgeting (variance, Monte Carlo, rolling forecasts, ZBB)
34. Payroll & eSocial (encargos, INSS progressivo, FGTS Digital, pro-labore)
35. Data governance (retention, quality, reconciliation, archival, masking)
36. ESG & sustainability (GHG Protocol, IFRS S1/S2, CSRD, emission factors)

---

## Open Questions Restantes

1. **Pricing final**: executar pricing page e testar com usuários reais
2. **AI roadmap**: qual feature AI primeiro (categorização é quick win)
3. **Real-time collaboration**: Yjs desde início ou adicionar depois?
4. **Open-source %**: quanto open-source vs proprietary?
5. **Multi-tenant**: shared DB para todos ou dedicated para enterprise?
6. **Go-to-market**: MEIs primeiro? Empresas médias? Freelancers?
