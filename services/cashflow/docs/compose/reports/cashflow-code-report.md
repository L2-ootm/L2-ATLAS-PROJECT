# RELATÓRIO TÉCNICO — L2 CASHFLOW

> Gerado em: 2026-07-11
> Projeto: L2 ATLAS / services/cashflow
> Público: colaborador de código

---

## 1. VISÃO GERAL

O **L2 Cashflow** é o módulo de gestão financeira e FinOps da L2 Systems — uma plataforma completa que começou como um sistema simples de fluxo de caixa entre sócios (Artur e Davi) e evoluiu para um **motor de FinOps para operações de IA**.

Ele cuida de:

- **Financeiro base**: clientes, despesas, faturas, fluxo de caixa
- **FinOps de IA**: rastreamento de tokens, custo por modelo, margem por cliente, rate cards
- **Billing B2B2C**: assinaturas Plus, split de receita com gateways
- **Degradação ativa**: orçamentos por usuário, alertas e rebaixamento automático de modelo
- **Relatórios**: P&L, forecast, relatório comercial e operacional (exportáveis)
- **Integração com L2 Atlas**: via MCP (Model Context Protocol) + webhooks

---

## 2. STACK TECNOLÓGICA

| Camada | Tecnologia | Versão |
|--------|-----------|--------|
| Runtime | Node.js | 20+ |
| Framework | Next.js (App Router) | 16.1.6 |
| UI | React + Tailwind CSS 4 + Framer Motion | 19.2.3 |
| Banco local | SQLite (better-sqlite3) | 12.6.2 |
| Banco cloud | PostgreSQL (Supabase) | — |
| Estilização | Tailwind 4 + PostCSS + CSS oklch | — |
| Ícones | Lucide React | — |
| Gráficos | Recharts | — |
| Exportação | jsPDF + docx | — |
| MCP | @modelcontextprotocol/sdk | 1.29 |
| TypeScript | Strict mode | 5 |

**Dependências a notar:**
- `@opengsd/gsd-core` — workflow engine da GSD
- `clsx` + `tailwind-merge` — composição de classes
- `jspdf-autotable` — tabelas em PDF

---

## 3. ARQUITETURA

### 3.1 Fluxo da aplicação

```
[Navegador] → Next.js App Router (SSR/CSR)
                  │
                  ├── Páginas (app/*/page.tsx)
                  │      └── use client → actions.ts → repositories → banco
                  │
                  ├── API REST (/api/atlas, /api/engine, /api/webhooks)
                  │      └── repositories → banco
                  │
                  └── MCP Server (/api/mcp)
                         └── MCP tools → repositories → banco
```

### 3.2 Camadas

```
Presentation (pages/components)
      ↓
Actions (app/actions.ts) — server actions com revalidatePath
      ↓
Repositories (lib/repositories/) — interface + SQLite | Supabase
      ↓
Database (lib/db/ + supabase/)
```

### 3.3 Dual-backend (SQLite ↔ Supabase)

O sistema opera com **dois backends intercambiáveis**. A seleção é feita automaticamente:

```
forced = process.env.ATLAS_CASHFLOW_DB?.toLowerCase()
useSupabase = forced === 'supabase' || (forced !== 'local' && isSupabaseConfigured())
```

- `ATLAS_CASHFLOW_DB=local` → força SQLite
- `ATLAS_CASHFLOW_DB=supabase` → força Supabase
- Sem variável → auto-detect (Supabase se `NEXT_PUBLIC_SUPABASE_URL` + `ANON_KEY` existirem)

Ambos os backends são **non-destructive**: toda criação de tabela usa `IF NOT EXISTS`.

### 3.4 Diretórios

```
/
├── app/                    # Next.js App Router
│   ├── page.tsx            # Redirect → /dashboard
│   ├── layout.tsx          # Root layout (Sidebar, TopoField, NeuralOverlay)
│   ├── dashboard/          # Dashboard principal
│   ├── clientes/           # Gestão de clientes
│   ├── contratos/          # Contratos (expiração, renovação)
│   ├── faturas/            # Faturamento
│   ├── despesas/           # Despesas
│   ├── relatorios/         # Relatórios financeiros
│   ├── fluxo-caixa/        # Projeções
│   ├── socios/             # Carteiras dos sócios
│   ├── enterprise/         # FinOps corporativo
│   │   ├── pnl/            # P&L por cliente
│   │   ├── forecast/       # Forecast de custos + alertas
│   │   ├── billing/        # Assinaturas Plus
│   │   ├── explorer/       # Explorador de custos IA
│   │   ├── reports/        # Relatórios consolidados
│   │   ├── audit/          # RBAC + audit log
│   │   └── research/       # Centro de pesquisa
│   └── api/                # API routes
│       ├── atlas/          # REST para L2 Atlas
│       ├── mcp/            # MCP transport
│       ├── tokens/         # Log de uso IA
│       ├── webhooks/       # Webhook receiver
│       └── engine/         # Degradação ativa
├── lib/                    # Core
│   ├── types.ts            # Modelos (Client, Expense, Invoice, etc)
│   ├── utils.ts            # formatCurrency, formatDate, generateId
│   ├── supabase.ts         # Cliente Supabase singleton
│   ├── repositories/       # DAL
│   │   ├── types.ts        # Interfaces (IClientRepository, etc)
│   │   ├── index.ts        # Barrel + seleção de backend
│   │   ├── sqlite/         # Implementações SQLite
│   │   └── supabase/       # Implementações Supabase
│   ├── db/                 # Schema + enterprise
│   │   ├── index.ts        # SQLite schema completo
│   │   ├── enterprise.ts   # Funções enterprise (P&L, forecast, etc)
│   │   ├── seed-rates.ts   # Seed de rate cards
│   │   └── audit.ts        # Audit log
│   ├── engine/             # Motores
│   │   ├── degradation.ts  # Degradação ativa
│   │   └── normalizer.ts   # Rate card math
│   ├── webhooks/           # Webhook dispatcher
│   │   ├── types.ts        # Tipos dos eventos
│   │   └── dispatcher.ts   # HTTP POST fire-and-forget
│   └── mcp/
│       └── server.ts       # Servidor MCP com 7 tools
├── components/             # Componentes React
├── supabase/               # Schema SQL + RPC functions
├── public/                 # Assets estáticos
├── scripts/                # Scripts auxiliares
└── research/               # Documentação de planejamento
```

---

## 4. MODELOS DE DADOS

### 4.1 Domínio Core (lib/types.ts)

**Client**
```
id, name, service (SaaS/Consultoria/etc), monthlyPayment, startDate,
contractMonths (0 = mês a mês), active, notes, phone?
```

**Expense**
```
id, clientId?, category (Software|Marketing|Equipamento|Infraestrutura|Pessoal|Outros),
description, amount, date, recurring
```

**Invoice**
```
id, clientId, clientName (desnormalizado), description, amount,
issueDate, dueDate, paidDate?, status (pendente|pago|atrasado)
```

**PartnerWallet**
```
id ('artur' | 'davi'), name, balance
```

**PartnerTransaction**
```
id, partnerId, type (injection|withdrawal|adjustment), amount, date, description
```

### 4.2 Domínio Enterprise (lib/repositories/types.ts)

**UsageEvent** — o registro mais importante do FinOps:
```
id, client_id, user_id?, session_id?, event_type, plan_at_time?,
route?, model_provider?, model_name?,
input_tokens, output_tokens, cache_hit_tokens, cache_miss_tokens,
tool_calls, search_requests, retrieval_chunks,
cost_usd, cost_brl, revenue_attributed_brl, margin_attributed_brl,
metadata_json?, created_at?
```

**ResearchJob**
```
id, client_id, requested_by_user_id?, query, normalized_query?,
topic?, priority (low|normal|high), status (pending|completed|failed),
provider_used?, cost_brl, result_quality?,
converted_to_knowledge_pack (bool), created_at, completed_at?
```

### 4.3 Schema SQLite (17 tabelas + enterprise)

O schema completo está em `lib/db/index.ts` e inclui:

**Base:**
- `Client`, `Invoice`, `Expense`, `Partner`, `PartnerTransaction`, `AITokenLog`

**Enterprise:**
- `client_accounts` — contas corporativas (cnpj, segmento, receita estimada)
- `contracts` — contratos com orçamentos de IA (target/warning/hard_cap brl)
- `plans` — planos de assinatura com limites por usuário
- `user_entitlements` — permissões e limites por usuário
- `usage_events` — ledger de uso de IA (core FinOps)
- `model_rate_cards` — tabela de preços por modelo (input, output, cache)
- `search_rate_cards` — custos de busca (Tavily, Perplexity)
- `research_jobs` — jobs de pesquisa com ROI tracking
- `invoice_line_items` — itens detalhados de fatura
- `plus_subscriptions` — assinaturas B2B2C
- `billing_events` — eventos de pagamento com split
- `system_users` — usuários internos (RBAC)
- `audit_log` — trilha de auditoria

---

## 5. REPOSITORIES (DAL)

### 5.1 Contratos (lib/repositories/types.ts)

| Interface | Métodos |
|-----------|---------|
| `IClientRepository` | getAll, getActive, getById, create, update, delete |
| `IExpenseRepository` | getAll, getById, getByMonth, getByClient, create, update, delete |
| `IInvoiceRepository` | getAll, getById, getByStatus, getOverdue, create, update, delete |
| `IPartnerRepository` | getWallets, getWalletById, updateWalletBalance, getTransactions, addTransaction |
| `IUsageRepository` | getAll(limit), getByClient(clientId, limit), log(data) |
| `IResearchRepository` | create, updateStatus, markAsKnowledgePack, getJobsByClient, getJobById, getAll, getROIStats |

### 5.2 Implementações

Cada interface tem duas implementações completas:
- **SQLite**: `lib/repositories/sqlite/{client,expense,invoice,partner,usage,research}.ts`
- **Supabase**: `lib/repositories/supabase/{client,expense,invoice,partner,usage,research}.ts`

### 5.3 Seleção (lib/repositories/index.ts)

Singleton instances criadas na inicialização:

```ts
export const clientRepo: IClientRepository = useSupabase
  ? new SupabaseClientRepository()
  : new SqliteClientRepository();
// ... para cada repositório
```

Também exporta `getFinancialSummary()` (agregado usado pelo MCP).

---

## 6. API ROUTES

### 6.1 POST /api/atlas — REST Inbound

Autenticação: Bearer token (`L2_ATLAS_API_KEY`). Ações:

| Action | Params | Descrição |
|--------|--------|-----------|
| `ping` | — | Health check |
| `get_clients` | `{ activeOnly?: bool }` | Lista clientes |
| `get_expenses` | `{ month?, clientId? }` | Lista despesas |
| `get_invoices` | `{ status? }` | Lista faturas |
| `get_financial_summary` | — | Resumo financeiro |
| `get_ai_usage` | `{ clientId?, limit? }` | Eventos de uso IA |

### 6.2 GET/POST/DELETE /api/mcp — MCP Transport

Transporta o protocolo MCP via **Streamable HTTP** (Web Standard). Autenticação: Bearer token.

**Tools expostas** (7):
1. `get_clients` — filtra ativos ou todos
2. `get_client_by_id` — busca por ID
3. `get_financial_summary` — resumo agregado do mês
4. `get_invoices` — por status ou todas
5. `get_expenses` — por mês, cliente ou todas
6. `add_expense` — registra nova despesa
7. `get_ai_usage` — eventos de IA por cliente

### 6.3 POST /api/webhooks/tokens — Webhook Receiver

Recebe eventos de uso de IA de sistemas externos. Insere em `usage_events`. Aceita payload com `client_id`, `user_id`, `input_tokens`, `output_tokens`, `cost_usd`, `cost_brl`, etc. Compatibilidade reversa com campos legados (`tokensPrompt`, `tokensCompletion`, `costUsd`).

### 6.4 POST /api/engine/evaluate — Degradação Ativa

Autenticação: Bearer (`CRON_SECRET`). Avalia risco de estouro de orçamento por usuário. Dispara webhooks para o L2 Atlas.

### 6.5 Server Actions (app/actions.ts)

Funções `"use server"` para operações CRUD:

| Função | Entidade | Revalida |
|--------|----------|----------|
| getClients, getActiveClients, addClient, updateClient, deleteClient | Client | /clientes |
| getExpenses, addExpense, updateExpense, deleteExpense | Expense | /despesas |
| getInvoices, addInvoice, updateInvoice, deleteInvoice | Invoice | /faturas |
| getPartnerWallets, updatePartnerWallet, getPartnerTransactions, addPartnerTransaction | Partner | /socios |

---

## 7. MCP SERVER (Model Context Protocol)

O servidor MCP (`lib/mcp/server.ts`) é o principal canal de integração com o **L2 Atlas**. Ele expõe ferramentas tipadas com Zod para consulta de dados financeiros:

```ts
server.tool('get_clients', 'descrição', schema, handler)
```

Características:
- **Stateless**: nova instância por request
- **Streamable HTTP**: suporte a JSON e SSE
- **Autenticação**: Bearer token compartilhado com L2 Atlas
- **Idempotente**: todas as tools são queries (exceto add_expense)

---

## 8. ENTERPRISE FINOPS

O módulo enterprise (`lib/db/enterprise.ts`) implementa as funcionalidades mais pesadas, todas com fallback local (SQLite) quando Supabase não está configurado.

### 8.1 P&L por Cliente
- `getClientPnL(clientId, year, month)` — receita contratada vs custo IA
- Margem percentual, alerta se abaixo do mínimo

### 8.2 Cost Explorer
- `getCostExplorerMetrics(clientId, year, month)` — custo por modelo, top 10 usuários, cache hit/miss

### 8.3 Forecast + Alertas
- `getForecastData(clientId, year, month)` — projeção de custo mensal baseada em média diária
- Sistema de alerta em 3 níveis: 🟢 verde / 🟡 amarelo / 🔴 vermelho
- Simulador de margem: `simulateMargin(params)` — ajusta custo por sessão, alunos e cache

### 8.4 Billing Plus
- Assinaturas B2B2C com split de receita (gateway ~5%, L2 ~30%, cliente ~70%)
- Stripe/Hotmart como gateways
- `getBillingMetrics(clientId, year, month)`

### 8.5 Relatórios
- **Comercial** (`getCommercialReport`): receita contratada + Plus, margem bruta/líquida
- **Operacional** (`getOperationalReport`): sessões, tokens, cache, breakdown por modelo

### 8.6 Research ROI
- `getROIStats` — calcula ROI de pesquisa: `packs * 5 * avgCostPerSearch`

---

## 9. DEGRADATION ENGINE

`lib/engine/degradation.ts` — motor de degradação ativa que avalia risco por usuário:

1. Busca `usage_events` do mês para o usuário
2. Soma `cost_brl`
3. Compara com limites (hard-coded: warning R$25, cap R$35)
4. Dispara webhooks:
   - `budget.warning` (≥ R$25)
   - `user.degraded` (≥ R$35) com `suggested_action: 'force_flash_models_only'`

O `normalizer.ts` calcula o custo exato usando `model_rate_cards`, com fallback para blended rate se o modelo não for encontrado:

```ts
fallbackInputPrice = $1.00/1M tokens
fallbackOutputPrice = $2.00/1M tokens
```

---

## 10. WEBHOOKS (OUTBOUND)

Sistema de notificação para o L2 Atlas.

**Eventos** (23 tipos):
- CRUD: `client.*`, `expense.*`, `invoice.*`
- Financeiro: `invoice.paid`, `invoice.overdue`, `partner.transaction`
- IA: `usage.logged`
- Alerta: `budget.warning`, `budget.exceeded`, `user.degraded`

**Características:**
- Fire-and-forget (não bloqueia operações)
- Timeout de 10s via AbortSignal
- Cabeçalhos: Authorization, X-Webhook-Event, X-Webhook-Id, X-Webhook-Source
- ID único por delivery (`whk_<timestamp>_<random>`)

---

## 11. SUPABASE (RPC FUNCTIONS)

O schema Supabase (`supabase/schema.sql`) replica as tabelas SQLite e adiciona **6 RPC functions** em PL/pgSQL para agregações server-side:

| Função | Retorno | Uso |
|--------|---------|-----|
| `get_client_pnl` | JSONB | P&L por cliente |
| `get_cost_explorer_metrics` | JSONB | Custo por modelo, top users, cache |
| `get_billing_metrics` | JSONB | Métricas de billing |
| `get_forecast_data` | JSONB | Dados de forecast |
| `get_operational_report` | JSONB | Relatório operacional |
| `get_commercial_report` | JSONB | Relatório comercial |

Cada RPC aceita `p_client_id TEXT, p_month_prefix TEXT` e faz agregações diretamente no banco.

---

## 12. UI / FRONTEND

### 12.1 Design System
- **Tema escuro** com cores oklch
- Variáveis CSS: `--atlas-celestial`, `--sig-crimson`, `--l2-fg-*`, `--emerald-*`
- Fonte: Inter (sans) + JetBrains Mono (mono) via next/font
- Componente TopoField — campo topográfico animado (SVG contour engine)
- PWA: manifest.json, apple-touch-icon, service worker

### 12.2 Dashboard
- StatCards: faturamento, despesas, lucro, clientes ativos
- GoalRings: anéis de progresso para receita vs meta
- ExpenseDonutChart: gráfico de despesas por categoria
- TokenHeatmap: heatmap de uso de tokens por cliente
- LiveCommandFeed: feed de atividade recente
- Alertas: faturas atrasadas + contratos próximos do vencimento

### 12.3 Componentes principais
- `Sidebar` — navegação lateral
- `TopoField` — fundo topográfico animado
- `NeuralCommandOverlay` — overlay de comando neural
- `MonthSelector` — seletor de mês
- `ServerMonthSelector` — contraparte server-side
- `TokenTracking` — rastreamento de tokens IA

---

## 13. CONFIGURAÇÃO

### Variáveis de ambiente

```
# Banco de dados
NEXT_PUBLIC_SUPABASE_URL      # URL do projeto Supabase
NEXT_PUBLIC_SUPABASE_ANON_KEY # Chave anônima Supabase
ATLAS_CASHFLOW_DB             # Força backend: 'local' | 'supabase'

# Integração L2 Atlas
L2_ATLAS_API_KEY              # Bearer token para APIs
L2_ATLAS_WEBHOOK_URL          # URL de destino dos webhooks

# Motor de degradação
CRON_SECRET                   # Auth para /api/engine/evaluate

# Câmbio
FX_RATE_USD_BRL               # Padrão: 5.50
```

### Constantes (hard-coded)

```
DAS_MEI_MENSAL    = R$ 71,60
LIMITE_ANUAL_MEI  = R$ 81.000
DEGRADATION_WARN  = R$ 25,00
DEGRADATION_CAP   = R$ 35,00
```

---

## 14. PADRÕES DE CÓDIGO

### Repository Pattern
Interfaces definem contratos, implementações segregadas por backend. Sem DI container — módulos importam singletons diretamente.

### Server Actions
Toda mutação server-side usa `"use server"` + `revalidatePath()` para refresh de cache.

### Non-destructive Migrations
`CREATE TABLE IF NOT EXISTS` em todo schema. Seguro para dev e prod.

### Fire-and-Forget Webhooks
Webhooks nunca bloqueiam a operação principal. Falhas são logadas, não propagadas.

### Fallback Local para Enterprise
Toda função enterprise (`getClientPnL`, `getForecastData`, etc.) tem fallback SQLite quando Supabase não está configurado.

### Stateless MCP
Servidor MCP recriado a cada request — sem sessão, sem estado.

---

## 15. PONTOS DE ATENÇÃO

### Ausência de Testes
Zero arquivos de teste encontrados (`*.test.ts`, `*.spec.ts`). Todo o código está em produção sem cobertura automatizada.

### Type Safety Parcial
Server actions (`app/actions.ts`) usam `data: any` nos parâmetros — sem validação de tipos na camada de entrada.

### Hard-coded Values
- Limites de degradação (R$ 25 / R$ 35) estão hard-coded no motor
- Client ID fixo `'tds-enterprise-001'` nas páginas enterprise
- Alguns valores de MEI fixos no código

### Dual-backend Complexity
Manter duas implementações (SQLite + Supabase) para cada repositório dobra a superfície de manutenção. As RPC functions Supabase têm lógica que parcialmente duplica o código TypeScript.

### Sem Rate Limiting ou Idempotency Keys
A API `/api/webhooks/tokens` não tem proteção contra duplicatas. Webhooks outbound têm ID único mas não há verificação de idempotência no receiver.

---

## 16. COMO RODAR LOCALMENTE

```bash
# Instalar dependências
cd services/cashflow
npm install

# Desenvolvimento (SQLite local, sem Supabase)
npm run dev

# Forçar backend Supabase
ATLAS_CASHFLOW_DB=supabase npm run dev

# Build produção
npm run build
npm start
```

O SQLite cria o arquivo `dev.db` automaticamente no `cwd` com todas as tabelas.

---

## 17. FLUXOS PRINCIPAIS PARA COMEÇAR

1. **Entender o modelo de dados**: `lib/types.ts` → modelos core, `lib/repositories/types.ts` → models enterprise
2. **Ver o schema completo**: `lib/db/index.ts` → 17 tabelas SQLite
3. **Explorar a seleção de backend**: `lib/repositories/index.ts` → como SQLite/Supabase são escolhidos
4. **Estudar o MCP**: `lib/mcp/server.ts` → interface do L2 Atlas com o cashflow
5. **Ver a lógica enterprise**: `lib/db/enterprise.ts` → P&L, forecast, billing, relatórios
6. **Analisar a degradação**: `lib/engine/degradation.ts` → motor de FinOps ativo
7. **Webhooks**: `lib/webhooks/` → integração outbound com Atlas
8. **Frontend**: `app/dashboard/page.tsx` → entry point da UI

---

*Este relatório foi gerado por análise automatizada do código-fonte. Para dúvidas ou contribuições, consulte o repositório L2 ATLAS.*
