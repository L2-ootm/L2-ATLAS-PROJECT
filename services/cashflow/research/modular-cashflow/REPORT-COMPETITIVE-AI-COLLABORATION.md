# Modular Cashflow Universal — Relatório: Competitivo, AI/ML, Analytics, Colaboração, Acessibilidade, Contratos

> Generated 2026-07-09 · 30 findings files totais · 400+ fontes · workspace: research/modular-cashflow/

## Executive Summary

**Competitivo**: Nenhuma plataforma oferece cashflow-first design (todas são accounting-first). Brasil tem zero integração NF-e nativa, suporte a regimes tributários, ou Boleto/Pix como first-class citizens de plataformas internacionais. Modular pay-per-module pricing não existe — todos usam tiers forçados com limites artificiais. Sweet spot Brasil: R$50-150/mês micro/pequena, R$200-500/média, zero pricing per-user.

**AI/ML**: Categorização automática: DistilBERT híbrido 95%+, Random Forest 99.15%. Forecast: LSTM > ARIMA/Prophet para padrões não-lineares; Prophet melhor para dados explicáveis com sazonalidade; ensemble (XGBoost+LSTM+Prophet) recomendado. Anomaly detection: Federated Learning F1=0.903 (vs 0.643 local). LLM guardrail: sempre separar sugestão do LLM da execução do sistema via verificação programática.

**Analytics**: Metabase SDK para embedded analytics (component-level React, multi-tenancy built-in). Cube.js como semantic layer (measures/dimensions definidos uma vez, servidos via REST/GraphQL/WebSocket). Debezium CDC para data warehouse sync em real-time. ECharts para waterfall charts nativos.

**Colaboração**: CRDTs (Yjs) para dados financeiros estruturados + server-side invariant validation (não OT). 3-tier locking: optimistic para edits rotineiros, advisory locks para operações de período, serializable transactions para consistency checks. Nunca last-write-wins para dados financeiros — sempre user-resolved conflicts com audit trail.

**Acessibilidade**: WCAG 3.3.4 (Error Prevention for Legal/Financial) é Level AA — requer transações reversíveis/reviewáveis/confirmáveis. Financial color coding precisa de 3 sinais não-cor: text labels, icons, pattern fills. ARIA grid pattern para tabelas financeiras interativas. axe-core captura ~57%, teste manual com NVDA/VoiceOver obrigatório para ~43% restante.

**Contratos**: 9 estágios de lifecycle management. Data model: Contract → Party → Clause → Term → Obligation → SLA → PaymentSchedule → RenewalConfig. SLA monitoring com cálculo tiered de penalidades. Renewal automation com notificações 90 dias antes da expiração. Risk scoring 0-100 baseado em financial + term + obligation + SLA factors.

---

## 1. Análise Competitiva — Gaps de Mercado

### 1.1 5 Gaps que o Cashflow Preenche

| Gap | Descrição | Concorrentes afetados |
|---|---|---|
| **Cashflow-first** | Nenhuma plataforma é cashflow-first — todas são accounting-first com bolt-on reporting | QuickBooks, Xero, FreshBooks |
| **Brazil-native** | Zero integração NF-e, regimes tributários, Boleto/Pix como first-class | Todas as internacionais |
| **Modular pricing** | Pay-per-module não existe — todos usam tiers com limites artificiais | Todas |
| **Open-source + cloud-native** | ERPNext é ERP-heavy, não cashflow-focused | ERPNext, Odoo |
| **AI-powered** | Brex prova que 71% de expenses handled by AI é table stakes | Todas exceto Brex |

### 1.2 Pricing Comparison

| Plataforma | Tier inicial | Tier médio | Tier avançado | Per-user? |
|---|---|---|---|---|
| QuickBooks | ~R$100/mês | ~R$200/mês | ~R$400/mês | Sim (até 5 users) |
| Xero | ~R$130/mês | ~R$230/mês | ~R$390/mês | Não (unlimited) |
| FreshBooks | ~R$60/mês | ~R$115/mês | ~R$200/mês | Sim (5/50/unlimited) |
| Wave | Gratuito | R$19/mês (Pro) | — | Não |
| ERPNext | Gratuito (self-host) | Cloud ~$50/user | — | Sim |

### 1.3 Sweet Spot Brasil

- **Micro/pequena (MEI/ME)**: R$50-150/mês — zero expectativa de per-user pricing
- **Média (EPP/LTDA)**: R$200-500/mês — espera NF-e + SPED + relatórios
- **Enterprise (SA)**: R$1.000-5.000/mês — multi-entity + consolidação + compliance completo

### 1.4 Open-Source Gap

ERPNext é o único open-source relevante mas:
- ERP-heavy, não cashflow-focused
- Implementação complexa para uso simples
- Zero suporte a NF-e/NFS-e brasileiras
- **Oportunidade**: open-source + cloud-native + cashflow-focused + Brazil-native

---

## 2. AI/ML no Financeiro

### 2.1 Categorização Automática de Transações

| Modelo | Accuracy | Quando usar |
|---|---|---|
| **Rule-based** | 70-80% | Regras simples (vendor matching) |
| **Random Forest** | 99.15% | Dados estruturados, features claras |
| **DistilBERT híbrido** | 95%+ | Descrições de texto livre |
| **Commercial (Navan)** | 97%+ | Após 3 meses de learning |

**Padrão recomendado**: ML + confidence scoring + human-in-the-loop para 5-8% de itens low-confidence.

### 2.2 Cash Flow Forecasting

| Modelo | Melhor para | Limitações |
|---|---|---|
| **ARIMA** | Dados com tendências lineares | Não captura não-linearidades |
| **Prophet** | Dados com sazonalidade, explicabilidade | Não é bom para horizontes longos |
| **LSTM** | Padrões não-lineares, horizontes longos | Requer muitos dados, difícil de explicar |
| **Ensemble (XGBoost+LSTM+Prophet)** | Produção | Complexidade de implementação |

**Fonte**: CashLens 2026, Springer 92-citation comparison study.

### 2.3 Anomaly Detection

- **Z-score/IQR**: simples, bom para baseline
- **Isolation Forest**: ML não-supervisionado, bom para datasets grandes
- **Autoencoders**: melhor para padrões complexos
- **Federated Learning**: F1=0.903 cross-institutional (vs 0.643 local) — privacy-preserving

### 2.4 LLM Integration

```
User query → LLM generates SQL/analysis
  → Programmatic verification layer (validates SQL safety, checks results)
  → Database execution (with audit trail)
  → LLM formats response
  → User sees result + source references
```

**Guardrail**: sempre separar sugestão do LLM da execução do sistema. Nunca executar SQL gerado por LLM sem verificação programática.

### 2.5 Smart Reconciliation

- Fuzzy matching: Levenshtein distance, Jaro-Winkler
- ML-based matching: treinar em pares matcheados historical
- Confidence scoring: 0.0-1.0, threshold para auto-match vs manual review
- Handle partial matches: payment split across multiple invoices

---

## 3. Analytics & BI

### 3.1 Embedded Analytics Stack Recomendado

```
Metabase SDK (embedded dashboards)
  → Cube.js (semantic layer — measures, dimensions, pre-aggregations)
  → DuckDB/ClickHouse (OLAP queries)
  → Debezium CDC (PostgreSQL → data warehouse)
  → BullMQ (async processing)
```

### 3.2 Cube.js Semantic Layer

```yaml
cubes:
  - name: JournalEntries
    sql: "SELECT * FROM journal_entries WHERE tenant_id = '{tenant_id}'"
    measures:
      - name: totalDebits
        sql: "SUM(debit)"
        type: sum
      - name: totalCredits
        sql: "SUM(credit)"
        type: sum
      - name: netAmount
        sql: "SUM(debit - credit)"
        type: sum
    dimensions:
      - name: accountType
        sql: "account_type"
        type: string
      - name: postingDate
        sql: "posting_date"
        type: time
```

Define measures/dimensions uma vez, serve via REST/GraphQL/WebSocket. Pre-aggregations resolvem performance OLAP.

### 3.3 Data Export

| Formato | Quando | Biblioteca |
|---|---|---|
| CSV | Análise externa, importação | Native |
| Excel | Relatórios para clientes | ExcelJS |
| PDF | Documentos oficiais | jsPDF + AutoTable |
| API | Integração programática | REST/GraphQL |

### 3.4 Financial Visualization

| Tipo de Chart | Uso | Biblioteca |
|---|---|---|
| Waterfall | Cash flow build-up, P&L bridging | ECharts (nativo) |
| Sparklines | Trend inline em tabelas | Recharts |
| Heatmap | Daily cash positions, sazonalidade | ECharts |
| Sankey | Fund flow, cost allocation | ECharts |
| Gauge | KPI thresholds | Recharts |

### 3.5 Scheduled Reports

- Cron-based: relatório mensal no dia 5 do mês seguinte
- Event-triggered: "budget exceeded" → relatório automático
- Delivery: email (SendGrid), Slack webhook, API endpoint

---

## 4. Colaboração em Tempo Real

### 4.1 CRDTs vs OT para Dados Financeiros

| Abordagem | Melhor para | Financeiro? |
|---|---|---|
| **OT** | Text editing (Google Docs) | Não — dados estruturados |
| **CRDTs (Yjs)** | Dados estruturados, offline-first | Sim — Y.Map por registro |
| **Server-side validation** | Invariantes (debits == credits) | Obrigatório |

**Padrão**: CRDTs (Yjs) para sync + server-side invariant validation para integridade.

### 4.2 3-Tier Locking

| Tier | Mecanismo | Quando |
|---|---|---|
| **Optimistic** | Version column (updated_at) | Edits rotineiros |
| **Advisory** | `pg_advisory_lock` | Operações de período (close) |
| **Serializable** | Transaction isolation level | Consistency checks |

### 4.3 Period Closing Multi-User

```
1. All users notified: "Período 2026-06 será fechado em 3 dias"
2. Lock new transactions: no new entries after deadline
3. Module-parallel close: cada módulo fecha independentemente
   - Invoicing: todas faturas emitidas
   - AP: todas despesas registradas
   - Bank: todas conciliações completas
4. Sequential approval chain: accountant → controller → CFO
5. Period locked: advisory lock, no edits permitted
6. Post-close: reports generated, archive created
```

### 4.4 Conflict Resolution

- **Nunca** last-write-wins para dados financeiros
- **Sempre** user-resolved conflicts com audit trail
- Yjs Awareness CRDT para presence (cursors, edit indicators) — efêmero, não persistido

### 4.5 Permission-Based Collaboration

```sql
-- PostgreSQL RLS + per-module permissions
CREATE POLICY period_access ON journal_entries
    USING (
        tenant_id = current_setting('app.tenant_id')::uuid
        AND fiscal_period IN (
            SELECT period FROM user_period_access
            WHERE user_id = current_setting('app.user_id')::uuid
            AND can_edit = true
        )
    );
```

---

## 5. Acessibilidade (WCAG 2.1 AA)

### 5.1 WCAG 3.3.4 — Error Prevention for Financial

Level AA obrigatório para transações financeiras:
- **Reversível**: toda transação pode ser revertida
- **Reviewável**: usuário pode revisar antes de confirmar
- **Confirmável**: confirmação explícita antes de submeter

### 5.2 Financial Color Coding

**Regra**: 3 sinais não-cor obrigatórios:
1. **Text labels**: `+$1,200` / `-$800`
2. **Icons**: `▲` / `▼`
3. **Pattern fills**: hatching para chart bars

**Safe palette**:
- Positive: `#006400` (contrast 7.1:1 vs white)
- Negative: `#8B0000` (contrast 6.6:1 vs white)
- Evitar: light green/red que falham contrast

### 5.3 ARIA para Tabelas Financeiras

```html
<table role="grid" aria-label="Journal Entries">
  <thead>
    <tr>
      <th aria-sort="ascending" scope="col">Date</th>
      <th aria-sort="none" scope="col">Account</th>
      <th scope="col">Debit</th>
      <th scope="col">Credit</th>
    </tr>
  </thead>
  <!-- roving tabindex para navegação por teclado -->
</table>
```

### 5.4 Live Regions

```html
<!-- Para atualizações de saldo em tempo real -->
<div aria-live="polite" aria-atomic="true" role="status">
  Balance updated: $12,345.67
</div>
```

Throttle: 3-5s intervals para não overwhelming screen reader users.

### 5.5 Testing

| Ferramenta | Coverage | Tipo |
|---|---|---|
| axe-core | ~57% issues | Automated |
| Lighthouse | ~40% issues | Automated |
| Manual keyboard | ~43% issues | Manual |
| NVDA / VoiceOver | ~43% issues | Manual |

**axe-core + manual testing obrigatório** — automated sozinho não cobre logical order, live regions, modal focus traps.

---

## 6. Gestão de Contratos

### 6.1 Contract Lifecycle (9 estágios)

```
Creation → Negotiation → Approval → Execution → Active → Amendment → Renewal → Suspension → Termination
```

Cada estágio com data model específico e status transitions.

### 6.2 Data Model

```
Contract
  ├── Party (roles: client, vendor, partner)
  ├── Clause (library of reusable clauses)
  ├── Term (payment terms, SLA terms, penalty terms)
  ├── Obligation (what each party must do)
  ├── SLA (service level metrics + thresholds)
  ├── PaymentSchedule (milestone, progress, or retainer)
  ├── RenewalConfig (auto-renew, opt-in, notice period)
  ├── Amendment (versioned changes to contract)
  └── Document (PDF, signed versions)
```

### 6.3 Digital Signatures

- **DocuSign**: market leader, API robusta, envelope/document/recipient pattern
- **PandaDoc**: melhor para proposals + contracts
- **HelloSign (Dropbox)**: simpler, mais barato
- Padrão comum: create envelope → add documents → add recipients → send → track status

### 6.4 SLA Monitoring

```
SLA breach levels:
  Warning: 80% of threshold → email alert
  Minor: 100% of threshold → penalty calculation starts
  Major: 150% of threshold → escalation to management
  Critical: 200% of threshold → contract review trigger
```

### 6.5 Contract-to-Cash

| Billing Model | Link | Quando |
|---|---|---|
| Milestone | Contract milestones → Invoices | Projects |
| Progress | % completion → Invoices | Construction, consulting |
| Retainer | Monthly recurring → Auto-invoices | Services |
| Subscription | Plan billing → Auto-invoices | SaaS |

### 6.6 Renewal Automation

```
-90 days: "Contract X expiring in 90 days" → email to account manager
-60 days: "Renewal proposal needed" → task created
-30 days: "Please confirm renewal" → email to client
-7 days: "Final reminder" → escalation
-0 days: Auto-renew OR expire based on config
```

### 6.7 Risk Scoring (0-100)

| Factor | Peso | Critérios |
|---|---|---|
| Financial | 30% | Valor total, histórico de pagamento |
| Term | 20% | Penalidades, multa rescisória |
| Obligation | 20% | Compliance de obrigações |
| SLA | 15% | Histórico de breaches |
| Amendment | 15% | Número e severidade de amendments |

---

## 7. Números Finais — 5 Rodadas

| Rodada | Findings | Fontes | Escopo |
|---|---|---|---|
| 1 (Panorâmica) | F1-F6 | 72 | Módulos, indústrias, concorrentes, compliance, features, integrações |
| 2 (Técnica) | F7-F12 | 84 | Database, events, plugins, SPED/NFe, API, UI config |
| 3 (Infra) | F13-F18 | 90 | Security, performance, DevOps, migration, testing, mobile |
| 4 (Negócio) | F19-F24 | 84 | Accounting standards, SaaS metrics, localization, automation, marketplace, DX |
| 5 (Inteligência) | F25-F30 | 90 | Competitive, AI/ML, analytics, collaboration, a11y, contracts |
| **Total** | **30 findings files** | **420+ fontes** | **Cobertura completa** |

### 30 dimensões cobertas

1-24: (anteriores)
25. Análise competitiva e gaps de mercado
26. AI/ML financeiro (categorização, forecasting, anomaly detection, LLM)
27. Analytics & BI (embedded, semantic layer, OLAP, export, visualization)
28. Colaboração em tempo real (CRDTs, locking, period closing, conflicts)
29. Acessibilidade (WCAG 2.1 AA, ARIA, color coding, testing)
30. Gestão de contratos (CLM, digital signatures, SLA, renewal, risk scoring)

---

## Open Questions Restantes

1. **Pricing strategy**: modelo final de pricing (freemium? per-module? usage-based?)
2. **Go-to-market**: target market inicial e estratégia de aquisição
3. **Real-time collaboration**: implementar Yjs desde o início ou adicionar depois?
4. **AI roadmap**: qual AI feature implementar primeiro (categorização? forecasting? anomaly?)
5. **Open-source strategy**: quanto do código open-source vs. proprietary?
6. **Multi-tenant architecture**: shared database vs. dedicated para enterprise clients?
