# BRIEF — L2 CASHFLOW

> Versão: 1.0 | Data: 2026-07-11
> Status: Em produção | Equipe: Davi + Artur (L2 Systems)
> Este documento é a referência primária para colaboradores.

---

## O QUE É

O **L2 Cashflow** é o módulo de gestão financeira e FinOps da L2 Systems. Ele começou como um fluxo de caixa simples entre sócios e evoluiu para uma **plataforma de FinOps para operações de IA** — o tipo de sistema que uma empresa de tecnologia precisa para controlar quanto gasta com modelos de linguagem, quanto fatura por cliente, e quanto lucro sobra no final do mês.

Hoje ele opera **em produção** dentro do ecossistema L2 ATLAS.

---

## O QUE JÁ FAZ (Estado Atual)

### Gestão Financeira Base

- **Clientes**: cadastro, contratos mensais, controle de pagamento recorrente, alertas de vencimento
- **Faturas**: emissão, acompanhamento (pendente → pago → atrasado), automação de status
- **Despesas**: categorizadas (Software, Marketing, Equipamento, Infraestrutura, Pessoal, Outros), recorrentes ou avulsas, ربط a cliente ou não
- **Carteira de Sócios**: injeções e retiradas de Artur e Davi com saldo atualizado

### FinOps (Operações de IA)

- **Rastreamento de tokens**: cada chamada a um modelo de IA é registrada com input tokens, output tokens, cache hit/miss, custo em USD e BRL
- **Rate cards por modelo**: tabela com preço por 1M de tokens input/output/cache, contexto máximo, flags de suporte (tools, caching, JSON mode)
- **Custo normalizado**: `normalizer.ts` calcula o custo exato de cada evento de uso usando os rate cards do banco — com fallback se o modelo não estiver catalogado
- **Degradação ativa**: motor que monitora o gasto por usuário e, quando estoura o limite (R$25 warning / R$35 hard cap), envia um webhook para o roteador do ATLAS rebaixar o modelo do usuário para algo mais barato
- **Forecasting**: projeção de custo mensal baseada na média diária, com alertas verde/amarelo/vermelho

### Billing B2B2C (Plus)

- Assinaturas premium de usuários finais
- Split de receita: taxa do gateway (~5%) → L2 (~30%) → cliente (~70%)
- Gateways: Stripe, Hotmart

### Integração com L2 ATLAS

O Cashflow não é isolado — ele conversa com o ATLAS por dois canais:

| Canal | Como funciona | Uso |
|-------|--------------|-----|
| **MCP** (Model Context Protocol) | O ATLAS chama ferramentas do Cashflow via HTTP+JSON tipado com Zod | Queries: listar clientes, ver resumo, consultar uso de IA |
| **Webhooks** | O Cashflow dispara eventos push para o ATLAS quando algo relevante acontece | Notificações: fatura paga, orçamento exceeded, usuário degradado |

### Relatórios Enterprise

- **P&L por cliente**: receita contratada vs custo de IA vs margem
- **Cost Explorer**: custo por modelo, top 10 usuários por gasto, taxa de cache hit
- **Forecast**: projeção do fim do mês + simulador de margem com ajustes
- **Relatório Comercial**: receita total + Plus, margem bruta e líquida
- **Relatório Operacional**: sessões, tokens, custo médio por sessão

---

## COMO FUNCIONA (Arquitetura Técnica)

### Stack

```
Next.js 16 (App Router) + React 19 + TypeScript 5
SQLite (dev) ← Trocável → PostgreSQL/Supabase (prod)
Tailwind CSS 4 + CSS oklch
Lucide React (ícones) + Recharts (gráficos)
MCP SDK 1.29 (integração com Atlas)
better-sqlite3 12.6 (banco local)
Supabase JS 2.108 (banco cloud)
```

### Camadas

```
[UI — páginas React + Server Actions]
        ↓
[app/actions.ts — Server Actions com revalidatePath]
        ↓
[lib/repositories/ — Interface de acesso a dados]
        ↓
[SQLite | Supabase — Dual backend selezionável por env]
```

### Dual Backend

O mesmo código funciona com dois bancos. A seleção é automática:

```
ATLAS_CASHFLOW_DB=local   → SQLite (desenvolvimento)
ATLAS_CASHFLOW_DB=supabase → Supabase (produção)
(sem variável) → auto-detect pelas env vars)
```

Cada repositório existe em duas implementações: `lib/repositories/sqlite/` e `lib/repositories/supabase/`. Ambas implementam a mesma interface (`IClientRepository`, `IExpenseRepository`, etc.).

### Tabelas do Banco (17)

```
Base:         Client | Invoice | Expense | Partner | PartnerTransaction | AITokenLog
Enterprise:   client_accounts | contracts | plans | user_entitlements
              usage_events | model_rate_cards | search_rate_cards
              research_jobs | invoice_line_items | plus_subscriptions
              billing_events | system_users | audit_log
```

A tabela `usage_events` é o centro do FinOps — cada linha é um evento de uso de IA com custo breakdown completo.

### API Routes

| Route | Método | Função |
|-------|--------|--------|
| `/api/atlas` | GET/POST | REST API inbound para L2 Atlas |
| `/api/mcp` | GET/POST/DELETE | Transport MCP (7 ferramentas) |
| `/api/webhooks/tokens` | POST | Receiver de eventos de uso IA |
| `/api/engine/evaluate` | POST | Motor de degradação ativa |

### Server Actions

Funções `"use server"` para operações CRUD com cache revalidation automático. Uma ação por entidade (getClients, addClient, updateClient, deleteClient, etc.).

---

## O QUE VAMOS FAZER (Roadmap Planejado)

O master plan completo está em `research/master-plan/MASTER-PLAN.md`. Abaixo, a síntese.

### Fase 1 — Fundações

Antes de qualquer coisa nova, o sistema atual precisa de fundamentos que hoje estão fracos ou faltando:

- **Auth + RBAC**: sistema de autenticação e permissões por função (admin, contador, visualizador, etc.)
- **Chart of Accounts**: plano de contas estruturado para contabilidade
- **Double-entry General Ledger**: livro razão com lançamentos em duality (débito = crédito) — é a peça mais crítica, 28 módulos dependem dela
- **Multi-Tenancy**: isolamento por tenant com PostgreSQL Row Level Security (RLS) — o `client_accounts` já é a entidade de tenant, só precisa de promoção
- **Plugin System**: esqueleto para módulos carregáveis dinamicamente
- **Event Sourcing (prototype)**: append-only journal como trilha de auditoria

### Fase 2 — Módulos Core

- **Accounts Payable**: contas a pagar com state machine (draft → finalized → sent → paid → voided)
- **Accounts Receivable**: contas a receber com os mesmos estados
- **Invoicing**: geração de notas fiscais com itens de linha
- **Fiscal Year**: gestão de exercícios com travas de período
- **Expenses**: reescrita sobre o GL com categorização avançada
- **Payments**: execução de pagamentos (Pix, boleto básico)

### Fase 3 — Compliance Brasil (Diferencial Competitivo)

Esta é a fase mais longa e mais valiosa. É onde o cashflow se diferencia de qualquer ferramenta genérica.

- **Tax Engine**: motor de impostos com regras versionadas (IRPJ, CSLL, INSS, Simples Nacional, PIS/COFINS) — configurável por datas de vigência
- **NFS-e (São Paulo)**: integração com a cidade de SP via padrão ABRASF 2.03
- **NFe**: integração com SEFAZ (SVRS primeiro, estados depois)
- **SPED**: geração de EFD-Contribuições, EFD-ICMS/IPI, ECD, ECF
- **eSocial**: S-1200 (folha) + S-1299 (fechamento)
- **LGPD**: consentimento, retenção, erasure

### Fase 4 — Pagamentos e Reconciliação

- **Bank Reconciliation**: matching automático de transações bancárias
- **Payment Gateways**: Asaas, PagSeguro, Mercado Pago, Stripe
- **Banking Integration**: via Belvo para agregação de contas
- **CNAB 240/400 + OFX**: importação de extratos bancários
- **Recurring Billing**: faturamento recorrente automático

### Fase 5 — Enterprise e Multi-Entidade

- **Multi-Entity**: consolidação de múltiplas empresas com transferência entre elas
- **Analytics/BI**: dashboards operacionais e comerciais (DuckDB embedded + Metabase SDK)
- **Security Hardening**: envelope encryption (AES-256-GCM), PCI SAQ A-EP, pentest
- **Performance**: otimização de queries, materialized views, PgBouncer

### Fase 6 — Crescimento e Marketplace

- **Marketplace SDK**: plugin system público para terceiros
- **Seed plugins (15-20)**: primeira leva de plugins próprios
- **PLG Engine**: invoice-as-viral-vector — cada fatura emitida é um canal de aquisição
- **Onboarding Wizard**: wizard de 5 etapas para novos tenants (< 5 min até primeira fatura)
- **Pricing**: Free / R$79 / R$199 / R$499 + módulos adicionais

### Fase 7 — Escala e Otimização

- **Full Test Suite**: suite completa (detalhado na próxima seção)
- **Load Testing**: 100K entradas de journal, 10 tenants simultâneos
- **Multi-Currency**: suporte a múltiplas moedas com fontes de câmbio (BCB, ECB)
- **Rust Cementation**: componentes críticos migrados para Rust (decisão D-022)

---

## CRITICAL PATH

```
Auth → General Ledger → Tax Engine → NFe/SPED → Multi-Entity → Marketplace
  5 níveis de dependência | 42 módulos | 10 são XL complexity
```

O **General Ledger é o gargalo #1**: 28 módulos dependem dele. Se ele estiver errado, 70% do sistema está errado. É onde a qualidade precisa ser absoluta.

---

## TESTES (Estratégia Planejada)

> Zero testes existem hoje. Este é o maior risco do projeto.
> A estratégia está documentada em `research/master-plan/batch4/B4-testing-strategy.md`.

### Pirâmide de Testes

```
                    ┌──────────────┐
                    │  E2E (5%)    │  Playwright — fluxos críticos
                    ├──────────────┤
                    │ Integration  │  API + DB + wiring (15%)
                    ├──────────────┤
                    │   Unit (80%) │  Funções puras, cálculos, lógica
                    └──────────────┘
```

### Unit Tests (Prioridade Máxima)

Arquivos críticos que precisam de testes primeiro:

| Arquivo | Por quê |
|---------|---------|
| `lib/tax.ts` | Cálculos de MEI — implicação legal |
| `lib/engine/normalizer.ts` | Custo de IA por modelo — impacto financeiro direto |
| `lib/forecast.ts` | Projeções de fluxo de caixa — decisões de negócio |
| `lib/engine/degradation.ts` | Lógica de degradação — previne custos explode |
| `lib/webhooks/dispatcher.ts` | payload shape, retry behavior |

Cada módulo financeiro com cálculos usa **property-based testing** (`fast-check`) para verificar invariantes como "percentUsed sempre em [0, 100]" ou "custo sempre ≥ 0".

### Golden Master Tests

Relatórios financeiros e outputs de forecast usam **golden masters** — snapshot do output esperado, fail on drift. Fluxo:

```
1. Mudança intencional → rodar com UPDATE_GOLDEN_MASTERS=1
2. Commit do snapshot atualizado + justificativa
3. CI sem o flag → fail se output mudou
```

### Contract Tests

Cada implementação de repositório (SQLite + Supabase) roda os **mesmos testes de contrato** — garante que ambas as versões se comportam igual.

### E2E Critical Flows

Seis fluxos Playwright que cobrem o caminho feliz de cada domínio:

1. Criação de fatura → pagamento → reconciliation
2. Despesa recorrente → projeção mensal
3. Carteira de sócio → injeção → retirada → saldo
4. Degradação ativa → webhook disparado ao exceder limite
5. Forecast de fluxo de caixa → 6 meses de projeção
6. Cálculo de imposto MEI → valor DAS

### Refactors Necessários Antes de Testar

O código atual tem deps diretas que impedem testes. Quatro refactors pequeños e não-breaking:

| Arquivo | Mudança | Por quê |
|---------|---------|---------|
| `lib/db/index.ts` | Aceitar `Database` injetado | SQLite in-memory nos testes |
| `lib/engine/normalizer.ts` | Aceitar Supabase client como param | Mock na unit |
| `lib/engine/degradation.ts` | Aceitar client + dispatcher como param | Mock na unit |
| `lib/webhooks/dispatcher.ts` | Aceitar `fetch` como param ou usar `vi.stubGlobal` | Mock na unit |

### Estimativa de Esforço (testes)

| Fase | Horas |
|------|-------|
| Setup (vitest + playwright + CI) | 28h |
| Unit tests — arquivos críticos | ~20h |
| Integration tests — repositories + API | ~20h |
| E2E tests — 6 fluxos críticos | ~16h |
| Contract tests + golden masters | ~10h |
| **Total primeira rodada** | **~94h** |
| Manutenção por sprint | ~9h |

---

## O QUE NÃO ESTÁ NESTE BRIEF

- **Decisões arquiteturais detalhadas**: estão em `research/master-plan/MASTER-PLAN.md` (Decision Log, Risk Register, Open Questions)
- **Pesquisa modular cashflow**: está em `research/modular-cashflow/REPORT.md` + 42 findings
- **Estratégia de testes completa**: está em `research/master-plan/batch4/B4-testing-strategy.md`
- **Código do relatório técnico**: está em `docs/compose/reports/cashflow-code-report.md`

---

*Para dúvidas: leia o MASTER-PLAN.md primeiro. Se não encontrar, pergunte.*