# Modular Cashflow Universal — Relatório Completo de Módulos

> Generated 2026-07-09 · depth: deep · 72 sources · workspace: research/modular-cashflow/

## Executive Summary

- **Core inegociável**: General Ledger, Chart of Accounts, Accounts Payable, Accounts Receivable, Bank Reconciliation, Fiscal Year, Double-Entry Bookkeeping — todo negócio precisa disso [1][4][6][7][8][9]
- **COA é jurisdiction-dependent**: França/Alemanha definem COA nacional; EUA/UK não — o sistema precisa suportar COA customizável por país [5][12]
- **7 classes de contas** para compliance IFRS/GAAP: Assets, Liabilities, Equity, Revenue, Expenses, Other Income/Expenses, Intercompany [5]
- **8+ indústrias** têm módulos financeiros únicos não-negociáveis: retail (inventory+POS), SaaS (MRR/churn), manufacturing (BOM+COGS), marketplace (escrow+split), real estate (rent+deposits), healthcare (claims), agriculture (index-based insurance), services (project billing) [F2]
- **7 plataformas analisadas**: Xero, FreshBooks, Wave, Nubank, Mercado Pago, PagBank, QuickBooks — todas incluem Invoicing+Payments como MVP; Payroll e Reporting avançado são add-ons pagos [F3]
- **Fintechs brasileiras** (Nubank, Mercado Pago, PagBank) bundam serviços bancários (conta, cartão, crédito, investimentos) junto com pagamentos — modelo fundamentalmente diferente de plataformas US/UK [F3]
- **Brasil exige 4 livros fiscais SPED** (ECD, ECF, EFD-Contribuições, EFD-ICMS IPI), cada um com validador/gerador próprio [F4]
- **Reforma tributária 2026** substitui PIS/COFINS/ICMS/ISS por CBS/IBS dual VAT — sistemas financeiros precisam de plano de transição [F4]
- **SOX Sections 302/404** criam requisitos duros de audit trail, segregation of duties, e compliance reporting automatizado para empresas públicas dos EUA [F4]
- **IFRS é obrigatório em 140+ jurisdições** — plataforma universal precisa de multi-GAAP reporting [F4]
- **NetSuite ARM** é o padrão canônico para ASC 606: revenue arrangements → elements → rules → plans → journal entries [F5]
- **Acumatica** é referência de arquitetura modular: 18+ módulos independentes (GL, AP, AR, Cash, Fixed Assets, Tax, Currency, Deferred Revenue, Recurring Revenue, Contract Management) [F5]
- **Multi-entity** suporta entidades ilimitadas com COA compartilhado, transações intercompany automatizadas, e eliminações consolidadas [F5]
- **Open Finance Brasil** exige licença ITP para iniciação de pagamento; Pix via Open Finance tem 20% mais conversão que QR code tradicional [F6]
- **eSocial v.S-1.3** com CNPJ alfanumérico entra em produção em 01/07/2026; NFS-e descontinua API antiga em 15/07/2026 [F6]

---

## Background & Scope

O L2 Cashflow é um sistema financeiro interno (Next.js + SQLite/Supabase) originalmente desenhado para a L2 Systems. O objetivo é evoluir para uma **plataforma financeira modular e universal**, configurável sob demanda para qualquer tipo de negócio — de freelancer a corporação multi-entidade.

Escopo desta pesquisa: catálogo completo de módulos, features, integrações e requisitos de compliance para cobrir absolutamente qualquer negócio imaginável.

---

## 1. Módulos Core — Fundação Universal

Todo negócio, independentemente de porte ou indústria, precisa destes módulos:

### 1.1 General Ledger (Razão Geral)
- Central de registro — todos os sub-ledgers (AP, AR, caixa, ativos fixos) postam nele [F1#1]
- Alimenta balanço patrimonial e demonstração de resultados [F1#3]
- Dividido em 7 categorias: Assets, Liabilities, Owner's Equity, Revenue, Expenses, Gains, Losses [F1#2]

### 1.2 Chart of Accounts (Plano de Contas)
- Lista de contas financeiras com códigos de referência, agrupadas por categorias [F1#4]
- Compliance IFRS/GAAP requer 7 classes: Assets, Liabilities, Equity, Revenue, Expenses, Other Income/Expenses, Intercompany [F1#5]
- **Jurisdiction-dependent**: França, Alemanha, Espanha, Suécia definem COA nacional; EUA e UK não [F1#12]
- **Design recommendation**: COA customizável com templates por país/regime tributário

### 1.3 Accounts Payable (Contas a Pagar)
- Three-way match: invoice × packing slip × purchase order [F1#6]
- Fluxo: fornecedor → nota → aprovação → agendamento → pagamento
- Features necessárias: aging schedule, agendamento de pagamentos, recorrência, multi-moeda

### 1.4 Accounts Receivable (Contas a Receber)
- Claims legalmente executáveis para pagamento [F1#7]
- Dois métodos de mensuração: allowance method vs. direct write-off [F1#7]
- Features: aging schedule, cobrança recorrente, dunning automático, conciliação

### 1.5 Bank Reconciliation (Conciliação Bancária)
- Compara livros da empresa com extratos bancários [F1#8]
- 3 tipos de discrepancy: timing differences, transações registradas só no banco, erros [F1#8]
- **Features**: importação OFX/CNAB, matching automático, alertas de divergência

### 1.6 Fiscal Year Management (Gestão de Exercício Fiscal)
- Prerrequisito para qualquer engine de cálculo de impostos [F1#11]
- ~65% das empresas públicas dos EUA usam calendário Jan-Dez [F1#10]
- **Features**: exercício fiscal customizável, fechamento mensal/anual, bloqueio de períodos

### 1.7 Double-Entry Bookkeeping (Partida Dobrada)
- Obrigatório por lei para empresas públicas (US GAAP, UK Companies Act 2006) [F1#9]
- Mantém equação: Assets = Liabilities + Equity
- **Design recommendation**: implementar como core, não opcional

---

## 2. Módulos Operacionais — Gerenciamento do Dia a Dia

### 2.1 Invoicing & Billing (Faturamento)
- **MVP universal**: toda plataforma analisada inclui faturamento como core [F3]
- Níveis: fatura avulsa, fatura recorrente, fatura baseada em projeto, fatura baseada em uso
- Gate de pricing: FreshBooks limita por nº de clientes (5/50/unlimited) [F3#4]

### 2.2 Payments & Checkout (Pagamentos)
- **MVP universal**: todo gateway de pagamento é essencial [F3]
- Brasil: Pix, boleto, cartão de crédito/débito, assinatura recorrente
- Internacional: Stripe, wire transfer, ACH, SEPA
- Split payments para marketplaces [F2#8]

### 2.3 Expense Management (Gestão de Despesas)
- Categorias: Software, Marketing, Equipamento, Infraestrutura, Pessoal, Outros
- Features: recorrência, rateio por centro de custo, aprovação, conciliação com extrato

### 2.4 Receipt & Document Management (Gestão de Documentos)
- Wave: captura digital de recibos é feature Pro ($19/mo) [F3#5]
- NF-e, NFS-e, CT-e como documentos fiscais eletrônicos [F4#5]
- **Features**: OCR de recibos, arquivo digital, vinculação a transações

### 2.5 Cash Flow Forecasting (Previsão de Fluxo de Caixa)
- Xero oferece 180-day cash flow forecast no plano Established [F3#1]
- **Features**: projeção baseada em faturas reais, cenários (melhor/pior caso), alertas de saldo baixo

---

## 3. Módulos de Compliance & Fiscal

### 3.1 Tax Calculation Engine (Motor de Impostos)
- **Brasil — 6 regimes tributários** com cálculos distintos [F4#2][F4#4]:
  - MEI (SIMEI): DAS mensal fixo + DASN anual
  - ME (Simples Nacional): faixas progressivas
  - EPP (Simples Nacional): faixas diferentes
  - Lucro Presumido: base de cálculo presumida
  - Lucro Real: lucro efetivo
  - SA: lucro real com obrigações adicionais
- **Reforma tributária 2026**: PIS/COFINS/ICMS/ISS → CBS/IBS dual VAT [F4#9]
- **Internacional**: VAT (EU), GST (India), Sales Tax (US state-by-state)

### 3.2 Electronic Invoicing (Nota Fiscal Eletrônica)
- **3 tipos distintos** no Brasil, cada um com SEFAZ própria [F4#5]:
  - NFe: mercadorias (nfe.fazenda.gov.br)
  - NFS-e: serviços (nfse.gov.br, padrão ABRASF)
  - CT-e: transporte (cte.fazenda.gov.br)
- NFS-e descontinua API antiga em 15/07/2026 [F6#6]

### 3.3 Fiscal Books (Livros Fiscais — SPED)
- **4 módulos obrigatórios** no Brasil [F4#1]:
  - ECD (Escrituração Contábil Digital): contabilidade
  - ECF (Escrituração Contábil Fiscal): apuração de impostos
  - EFD-Contribuições: PIS/COFINS
  - EFD-ICMS IPI: ICMS e IPI
- Cada um com programa validador/gerador próprio da Receita Federal

### 3.4 Tax Calendar & Deadlines (Calendário Fiscal)
- Alertas automáticos para vencimentos: DAS, DASN, SPED, NFe, eSocial
- Bloqueio de operações em dias de fechamento fiscal

### 3.5 Audit Trail & Access Control (Trilha de Auditoria)
- **SOX Sections 302/404**: CEO/CFO certification + internal controls assessment [F4#6][F4#7]
- Requisitos: log de todas as ações, segregation of duties, aprovações em cascata
- RBAC granular: permissão por módulo, por ação, por entidade

### 3.6 Multi-GAAP Reporting
- **IFRS obrigatório em 140+ jurisdições** [F4#8]
- Brasil: Brazilian GAAP + possibilidade de IFRS para empresas listadas
- EUA: US GAAP + SOX compliance
- **Design**: engine de reporting que gera demonstrações em múltiplos padrões

---

## 4. Módulos Avançados — Enterprise

### 4.1 Multi-Entity & Intercompany (Multi-Entidade)
- Acumatica: entidades ilimitadas, COA compartilhado, transações intercompany automatizadas [F5#3]
- Sage Intacct: entity-level budgeting, allocation rules, eliminações automáticas [F5#11]
- **Features**: consolidação, eliminações intercompany, due-to/due-from, transfer pricing

### 4.2 Multi-Currency & FX (Multi-Moeda)
- Acumatica: computa automaticamente ganhos/perdas de câmbio realizados e não realizados, reavaliação de contas, tradução de demonstrações (FASB-52) [F5#4]
- **Features**: moedas ilimitadas, taxas de câmbio multi-fonte, hedge accounting, translation adjustments

### 4.3 Revenue Recognition (Reconhecimento de Receita)
- **ASC 606 / IFRS 15**: modelo de 5 passos [F5#10]:
  1. Identificação do contrato
  2. Identificação de obrigações de desempenho
  3. Determinação do preço da transação (incluindo consideração variável)
  4. Alocação baseada em SSP (Standalone Selling Price)
  5. Reconhecimento no ponto no tempo ou ao longo do tempo
- NetSuite ARM: revenue arrangements → elements → rules → plans → journal entries [F5#1][F5#2]

### 4.4 Deferred Revenue (Receita Diferida)
- Odoo 18.0: deferred revenues e deferred expenses como features nativas [F5#7]
- Acumatica: Deferred Revenue Accounting como módulo separado [F5#12]
- **Features**: schedules de reconhecimento automático, reclassificação, auditoria

### 4.5 Fixed Assets & Depreciation (Ativos Fixos)
- Acumatica: 8+ métodos de depreciação (ACRS, MACRS, straight-line, declining-balance, sum-of-years-digits, remaining value, flat rate) [F5#5]
- Múltiplos livros de depreciação independentes do GL [F5#6]
- **Features**: baixa de ativos, transferência, impairment, specials (Section 179 IRS)

### 4.6 Inventory Valuation (Valuação de Estoque)
- Odoo 18.0: FIFO, LIFO, FEFO como opções nativas [F5#8]
- Manufacturing: BOM hierárquico com rollup de custos [F2#7]
- **Features**: custo padrão vs. custo real, valuation adjustments, cycle counting

### 4.7 Cost Centers & Profit Centers
- Dimensional reporting por centro de custo, projeto, departamento, produto
- Sage Intacct: dimensional GL [F5#11]
- Acumatica: subaccount structure [F5#12]

### 4.8 Lease Accounting (Contratos de Arrendamento)
- ASC 842 / IFRS 16: reconhecimento de right-of-use assets e liabilities
- **Gap de pesquisa**: não foi possível aprofundar — módulo crítico para empresas com imóveis/equipamentos alugados

### 4.9 Transfer Pricing
- Preciso para empresas com operações em múltiplos países
- **Gap de pesquisa**: não foi coberto em profundidade nesta rodada

---

## 5. Módulos por Indústria

### 5.1 Retail & E-commerce
- POS integrado com inventário [F2#1]
- Perishable goods tracking, customer credit [F2#2]
- Multi-outlet com centralização instantânea [F2#3]
- Integrações: Shopify, WooCommerce, VTEX, Mercado Livre [F6#8]

### 5.2 SaaS & Subscription
- MRR/ARR tracking, churn, expansion revenue [F2#4]
- Tiered pricing, usage-based billing [F2#5]
- Dunning automático, billing dunning, payment retry
- Métricas: LTV, CAC, payback period, net revenue retention

### 5.3 Manufacturing
- COGS com 3 componentes (material + mão de obra + overhead) [F2#6]
- BOM hierárquico com variantes configuráveis [F2#7]
- Variance tracking (custo padrão vs. real)
- Work orders, routings, capacity planning

### 5.4 Marketplace
- Escrow com disbursement condicional [F2#8]
- Split payments (gateway fee → platform → seller)
- Settlement timing, seller onboarding, KYC
- Integrações: Stripe Connect, Mercado Pago Split

### 5.5 Real Estate & Property Management
- Rent collection com security deposit tracking [F2#9]
- Late-fee enforcement, lease-term-aware billing
- Fee structures: % of rent (8-12%), flat-fee, hybrid, guaranteed-rent [F2#10]
- CAM (Common Area Maintenance) reconciliation

### 5.6 Healthcare
- Insurance claims adjudication pipeline [F2#11]
- Subrogation, fraud detection, leak detection
- Patient billing, payment plans, collections

### 5.7 Agriculture
- Index-based crop insurance (climate triggers) [F2#12]
- Commodity tracking, seasonal billing
- Cooperative settlement models

### 5.8 Professional Services
- Project-based billing (hourly, fixed-fee, retainer)
- Time tracking, expense reimbursement
- Project profitability analysis
- WIP (Work in Progress) revenue recognition

---

## 6. Ecossistema de Integrações

### 6.1 Banking & Open Finance
- **Open Finance Brasil**: BCB regulation, licença ITP para iniciação de pagamento [F6#1][F6#2]
- Pix via Open Finance: 20% mais conversão que QR code [F6#3]
- Belvo: banking data, employment data, fiscal data, account verification [F6#9]
- Importação: OFX, CNAB (240/400), CSV

### 6.2 Payment Gateways
- **Brasil**: PagSeguro, Mercado Pago, Iugu, Asaas, Stripe Brasil
- **Internacional**: Stripe, Adyen, Square
- Asaas: API documentada + Discord community [F6#12]
- Mercado Pago: 7+ plataformas e-commerce [F6#8]

### 6.3 Government APIs
- **eSocial**: layout v.S-1.3 com CNPJ alfanumérico, produção 01/07/2026 [F6#4]
- **NFS-e**: API descontinuada em 15/07/2026, novo layout DANFSE [F6#6]
- **Receita Federal**: validação de CNPJ via dados públicos [F6#11]
- **SEFAZ**: autorização de NFe/NFS-e/CT-e

### 6.4 Accounting Software Bridges
- Integrações com Dominio, Tiny ERP, Bling (Brasil)
- QuickBooks, Xero, Sage (internacional)
- Exportação: XML, CSV, ofx, SPED

### 6.5 E-commerce
- Shopify, WooCommerce, VTEX, Loja Integrada, PrestaShop [F6#8]
- Sincronização de pedidos, pagamentos, taxas

### 6.6 Payroll & HR
- eSocial (obrigatório no Brasil)
- Integração com sistemas de folha
- FGTS, INSS, IRRF

---

## 7. Automação & Inteligência

### 7.1 Recurring Billing & Dunning
- Faturamento automático com retry em falha
- Dunning emails/WhatsApp em cascata
- Pause/cancelamento automático após X falhas

### 7.2 Auto-Categorization
- Wave: auto-merge e categorização de transações bancárias (Pro tier) [F3#6]
- ML-based categorização de despesas por descrição/vendor

### 7.3 Smart Alerts
- "Fatura vence amanhã"
- "Contrato vence em 30 dias"
- "Despesa do mês excedeu orçamento em 20%"
- "Saldo projetado ficará negativo em 15 dias"

### 7.4 Anomaly Detection
- Transações atípicas (valor, frequência, vendor)
- Duplicatas detectadas automaticamente
- Padrões suspeitos de fraude

### 7.5 Cash Flow AI Forecasting
- Projeção baseada em faturas reais + sazonalidade + tendência
- Cenários: best case, worst case, most likely
- What-if simulation (sliders para custo, receita, crescimento)

---

## 8. Arquitetura Modular — Taxonomia Completa

### 8.1 Estrutura de Módulos Proposta

```
cashflow/
├── core/                          # SEMPRE presente
│   ├── general-ledger/            # Razão geral + partidas dobradas
│   ├── chart-of-accounts/         # Plano de contas customizável
│   ├── accounts-payable/          # Contas a pagar
│   ├── accounts-receivable/       # Contas a receber
│   ├── bank-reconciliation/       # Conciliação bancária
│   ├── fiscal-year/               # Gestão de exercício fiscal
│   ├── invoicing/                 # Faturamento
│   ├── payments/                  # Pagamentos (Pix, cartão, boleto)
│   ├── expenses/                  # Gestão de despesas
│   └── auth/                      # Login + RBAC básico
│
├── compliance/                    # Fiscal & regulatório
│   ├── tax-engine/                # Motor de cálculo de impostos
│   ├── electronic-invoicing/      # NFe, NFS-e, CT-e
│   ├── fiscal-books/              # SPED (ECD, ECF, EFD)
│   ├── tax-calendar/              # Calendário de vencimentos
│   ├── audit-trail/               # Trilha de auditoria completa
│   └── multi-gaap/                # Reporting multi-standards
│
├── operations/                    # Operações do dia a dia
│   ├── cash-flow-forecast/        # Previsão de fluxo de caixa
│   ├── receipt-management/        # Gestão de recibos/documentos
│   ├── budget/                    # Orçamento por centro de custo
│   ├── approval-workflows/        # Aprovações em cascata
│   └── notifications/             # Alertas email/WhatsApp
│
├── advanced/                      # Enterprise
│   ├── multi-entity/              # Multi-entidade + intercompany
│   ├── multi-currency/            # Multi-moeda + FX
│   ├── revenue-recognition/       # ASC 606 / IFRS 15
│   ├── deferred-revenue/          # Receita diferida
│   ├── fixed-assets/              # Ativos fixos + depreciação
│   ├── inventory/                 # Estoque + valuation
│   ├── cost-centers/              # Centros de custo/lucro
│   ├── lease-accounting/          # ASC 842 / IFRS 16
│   └── transfer-pricing/          # Preços de transferência
│
├── industry/                      # Específico por indústria
│   ├── retail/                    # POS + inventory + perishables
│   ├── saas/                      # MRR + churn + subscription
│   ├── manufacturing/             # BOM + COGS + work orders
│   ├── marketplace/               # Escrow + split + settlement
│   ├── real-estate/               # Rent + deposits + CAM
│   ├── healthcare/                # Claims + adjudication
│   ├── agriculture/               # Commodity + seasonal
│   └── services/                  # Project billing + time tracking
│
├── integrations/                  # Ecossistema externo
│   ├── banking/                   # Open Finance, OFX, CNAB
│   ├── payment-gateways/          # Stripe, PagSeguro, Mercado Pago
│   ├── government/                # eSocial, SEFAZ, Receita Federal
│   ├── accounting/                # Dominio, Tiny, QuickBooks
│   ├── ecommerce/                 # Shopify, WooCommerce, VTEX
│   └── payroll/                   # Folha de pagamento
│
├── automation/                    # Inteligência
│   ├── recurring-billing/         # Cobrança recorrente + dunning
│   ├── auto-categorization/       # Categorização automática
│   ├── anomaly-detection/         # Detecção de anomalias
│   ├── ai-forecast/               # Previsão com IA
│   └── workflow-engine/           # Automações customizáveis
│
└── finops-ai/                     # Específico L2 (AI cost tracking)
    ├── usage-events/              # Ledger de tokens/custos
    ├── model-rate-cards/          # Tabela de preços LLM
    ├── cost-explorer/             # Análise de custos AI
    └── budget-alerts/             # Alertas de budget AI
```

### 8.2 Setup Wizard — Questionário de Configuração

| # | Pergunta | Opções | Módulos ativados |
|---|---|---|---|
| 1 | Tipo de empresa? | Serviços / Produtos / SaaS / Marketplace / Indústria / Imobiliária / Saúde / Agronegócio | industry/* |
| 2 | Regime tributário? | MEI / ME (Simples) / EPP / Lucro Presumido / Lucro Real / LTDA / SA | compliance/tax-engine |
| 3 | Precisa de NFe/NFS-e? | Sim / Não | compliance/electronic-invoicing |
| 4 | Multi-entidade/holding? | Sim / Não | advanced/multi-entity |
| 5 | Multi-moeda? | Sim / Não | advanced/multi-currency |
| 6 | Cobrança recorrente? | Sim / Não | automation/recurring-billing |
| 7 | Orçamento por centro de custo? | Sim / Não | operations/budget |
| 8 | Fluxo de caixa com previsão? | Sim / Não | operations/cash-flow-forecast |
| 9 | Ativos fixos/depreciação? | Sim / Não | advanced/fixed-assets |
| 10 | Estoque? | Sim / Não | advanced/inventory |
| 11 | Integração bancária? | Sim / Não | integrations/banking |
| 12 | Pagamentos online? | Sim / Não | integrations/payment-gateways |
| 13 | eSocial/folha? | Sim / Não | integrations/payroll |
| 14 | Relatórios para clientes? | Sim / Não | operations/reports (core) |
| 15 | Divisão entre sócios? | Sim / Não | core/partners (L2 legacy) |
| 16 | Tracking de custos AI? | Sim / Não | finops-ai |

### 8.3 Regras de Ativação

- **Core**: sempre ativo, 10 tabelas mínimas
- **Compliance**: depende de #2 (regime tributário) + #3 (NFe/NFS-e)
- **Advanced**: cada módulo ativado independentemente
- **Industry**: apenas 1 ativo por vez (ou combinável com aviso)
- **Integrations**: cada uma ativada independentemente
- **Automation**: disponíveis para todos, mas features avançadas em tier Pro

---

## 9. Tabela Resumo — Módulos vs. Porte do Negócio

| Módulo | Freelancer | MEI/ME | Empresa Média | Enterprise | Holding |
|---|---|---|---|---|---|
| General Ledger | Opcional | Sim | Sim | Sim | Sim |
| Chart of Accounts | Básico | Nacional | Custom | Multi-entity | Multi-entity |
| AP/AR | AR only | Sim | Sim | Sim | Sim + Intercompany |
| Bank Reconciliation | Manual | CSV | OFX/CNAB | API banking | Multi-bank |
| Invoicing | Sim | Sim | Sim | Sim | Sim |
| Payments | Pix link | Pix/Boleto | Gateway | Multi-gateway | Multi-gateway |
| Tax Engine | MEI DAS | Simples | Presumido/Real | Multi-regime | Multi-entity |
| NFe/NFS-e | NFS-e MEI | NFS-e | NFe + NFS-e | NFe + NFS-e + CT-e | Multi-CNPJ |
| SPED | Não | EFD simplificado | ECD + ECF + EFD | Todos 4 | Consolidação |
| Multi-Entity | Não | Não | Opcional | Sim | Sim |
| Multi-Currency | Não | Não | Opcional | Sim | Sim |
| Revenue Rec. | Não | Não | Básico | ASC 606 | Consolidado |
| Fixed Assets | Não | Não | Sim | Sim + multi-book | Sim |
| Inventory | Não | Não | Sim | FIFO/LIFO/FEFO | Multi-warehouse |
| Audit Trail | Não | Básico | Sim | SOX | SOX + intercompany |

---

## 10. Open Questions

1. **ASC 842 / IFRS 16 (Lease Accounting)**: não foi pesquisado em profundidade — módulo crítico para empresas com imóveis/equipamentos alugados. Cobertura insuficiente [speculative].
2. **Transfer Pricing**: módulo enterprise para operações cross-border não coberto nesta rodada.
3. **Cost Center / Profit Center architecture**: diferença entre dimensional GL (Sage Intacct) vs. subaccount structure (Acumatica) — precisa de decisão arquitetural.
4. **QuickBooks Online**: pricing page inacessível durante pesquisa — tiers Simple Start/Essentials/Plus/Advanced documentados indiretamente mas sem feature mapping oficial.
5. **Multi-GAAP simultaneous reporting**: como implementar engine que gera demonstrações em Brazilian GAAP + IFRS + US GAAP simultaneamente?
6. **CBS/IBS transition timeline**: reforma tributária brasileira tem prazo de implementação gradual — como planejar módulo de compliance para transição?

---

## Sources

[1] General Ledger — https://en.wikipedia.org/wiki/General_ledger (accessed 2026-07-09)
[2] Chart of Accounts — https://en.wikipedia.org/wiki/Chart_of_accounts (accessed 2026-07-09)
[3] Accounts Payable — https://en.wikipedia.org/wiki/Accounts_payable (accessed 2026-07-09)
[4] Accounts Receivable — https://en.wikipedia.org/wiki/Accounts_receivable (accessed 2026-07-09)
[5] Bank Reconciliation — https://en.wikipedia.org/wiki/Bank_reconciliation (accessed 2026-07-09)
[6] Double-Entry Bookkeeping — https://en.wikipedia.org/wiki/Double-entry_bookkeeping (accessed 2026-07-09)
[7] Fiscal Year — https://en.wikipedia.org/wiki/Fiscal_year (accessed 2026-07-09)
[8] Point-of-Sale — https://en.wikipedia.org/wiki/Point-of-sale (accessed 2026-07-09)
[9] Revenue Stream (MRR) — https://en.wikipedia.org/wiki/Revenue_stream (accessed 2026-07-09)
[10] Subscription Business Model — https://en.wikipedia.org/wiki/Subscription_business_model (accessed 2026-07-09)
[11] Cost of Goods Sold — https://en.wikipedia.org/wiki/Cost_of_goods_sold (accessed 2026-07-09)
[12] Bill of Materials — https://en.wikipedia.org/wiki/Bill_of_materials (accessed 2026-07-09)
[13] Escrow — https://en.wikipedia.org/wiki/Escrow (accessed 2026-07-09)
[14] Property Management — https://en.wikipedia.org/wiki/Property_management (accessed 2026-07-09)
[15] Insurance — https://en.wikipedia.org/wiki/Insurance (accessed 2026-07-09)
[16] Xero Pricing — https://www.xero.com/us/pricing-plans/ (accessed 2026-07-09)
[17] Xero App Store — https://apps.xero.com/ (accessed 2026-07-09)
[18] FreshBooks Pricing — https://www.freshbooks.com/pricing (accessed 2026-07-09)
[19] Wave Pricing — https://www.waveapps.com/pricing (accessed 2026-07-09)
[20] Nubank Business — https://nubank.com.br/empresas/ (accessed 2026-07-09)
[21] Mercado Pago Business — https://www.mercadopago.com.br/empresas (accessed 2026-07-09)
[22] PagBank Business — https://pagbank.com.br/para-seu-negocio (accessed 2026-07-09)
[23] SPED Downloads — https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/download/sped (accessed 2026-07-09)
[24] Simples Nacional — https://www8.receita.fazenda.gov.br/SimplesNacional/ (accessed 2026-07-09)
[25] MEI Portal — https://www.gov.br/empresas-e-negocios/pt-br/empreendedor (accessed 2026-07-09)
[26] Sarbanes-Oxley Act — https://en.wikipedia.org/wiki/Sarbanes%E2%80%93Oxley_Act (accessed 2026-07-09)
[27] IFRS Standards — https://www.ifrs.org/content/ifrs/home/issued-standards/list-of-standards/ifrs-17-insurance-contracts.html (accessed 2026-07-09)
[28] Receita Federal Reforma Tributária — https://www.gov.br/receitafederal/pt-br/servicos/reforma-tributaria (accessed 2026-07-09)
[29] NetSuite ARM — https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_4328435538.html (accessed 2026-07-09)
[30] Acumatica Intercompany — https://www.acumatica.com/cloud-erp-software/inter-company-accounting/ (accessed 2026-07-09)
[31] Acumatica Currency — https://www.acumatica.com/cloud-erp-software/financial-management/currency-management/ (accessed 2026-07-09)
[32] Acumatica Fixed Assets — https://www.acumatica.com/cloud-erp-software/financial-management/fixed-assets/ (accessed 2026-07-09)
[33] Acumatica Financial Management — https://www.acumatica.com/cloud-erp-software/financial-management/ (accessed 2026-07-09)
[34] Odoo 18.0 Accounting — https://www.odoo.com/documentation/18.0/applications/finance/accounting/reporting.html (accessed 2026-07-09)
[35] NetSuite Revenue Recognition — https://www.randgroup.com/insights/oracle-netsuite/erp/netsuite-revenue-recognition-under-asc-606/ (accessed 2026-07-09)
[36] Sage Intacct Multi-Entity — https://www.erpresearch.com/en-us/blog/best-erp-for-multi-entity-businesses (accessed 2026-07-09)
[37] Belvo Open Finance — https://belvo.com/blog/what-is-open-finance-payment-initiation-and-why-you-should-care-in-2023/ (accessed 2026-07-09)
[38] eSocial Portal — https://www.gov.br/esocial/pt-br (accessed 2026-07-09)
[39] NFS-e Portal — https://www.gov.br/nfse/pt-br (accessed 2026-07-09)
[40] Mercado Pago Developers — https://www.mercadopago.com.br/developers/en/docs (accessed 2026-07-09)
[41] Asaas Docs — https://docs.asaas.com/ (accessed 2026-07-09)
[42] Receita Federal CNPJ — https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/cnpj (accessed 2026-07-09)
