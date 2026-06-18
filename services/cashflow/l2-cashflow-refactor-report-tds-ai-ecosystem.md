# L2 CASHFLOW — Report de Refactor e Expansão para Clientes Enterprise, IA Operacional e Ecossistema TDS

**Data:** 2026-06-11  
**Preparado para:** time L2 / sócio responsável pelo L2 CASHFLOW  
**Origem estratégica:** discussão sobre TDS AI ECOSYSTEM, LeticIA, roteador de modelos, custos de API, planos Core/Plus, faturamento variável e margem mínima L2  
**Objetivo:** transformar o L2 CASHFLOW em um dashboard financeiro-operacional capaz de modelar, monitorar e proteger contratos grandes de IA, especialmente clientes educacionais como TDS.

---

## 0. Resumo executivo

O L2 CASHFLOW precisa deixar de ser apenas um painel de entradas, saídas e fluxo de caixa simples. Para suportar contratos como TDS, ele precisa virar um **sistema de inteligência financeira-operacional para produtos de IA**.

A nova versão precisa entender:

1. clientes grandes com contratos B2B;
2. planos de implantação, mensalidade, add-ons e revenue share;
3. custos variáveis de IA por cliente, aluno, plano, mensagem, sessão, turma, ferramenta e modelo;
4. uso de API gerido pela L2, mas cobrado dentro de franquia, excedente ou assinatura adicional;
5. assinaturas pagas pelo aluno para a TDS, com liberação técnica automática no sistema L2;
6. forecast de margem antes do custo explodir;
7. alertas financeiros e operacionais;
8. integração com gateways, Supabase, roteador de modelos, search providers, APIs de LLM, VPS/infra e sistemas externos;
9. lucro mínimo garantido por cliente, especialmente no caso da TDS: **mínimo livre desejado de R$ 4.500/mês**, mirando sempre acima disso.

A conclusão central é:

> O L2 CASHFLOW deve se tornar o cérebro financeiro do ecossistema L2, capaz de responder em tempo real: **quanto cada cliente está pagando, quanto está consumindo, qual margem real está sobrando, quais alunos/turmas/planos estão queimando custo, quando devemos degradar uso, cobrar excedente ou sugerir upgrade.**

---

## 1. Contexto do projeto TDS AI ECOSYSTEM

O projeto TDS AI ECOSYSTEM parte da ideia de evoluir a LeticIA, IA atual da TDS, de uma ferramenta isolada para uma **camada operacional de inteligência supervisionada**.

Essa camada envolve:

- IA para alunos;
- IA para equipe;
- suporte pedagógico;
- suporte comercial;
- dashboard de gestão;
- base de conhecimento;
- RAG/wiki;
- roteador de modelos;
- controle de créditos;
- ledger de uso;
- Hermes como orquestrador central;
- pesquisa mensal/semanal para atualizar knowledge packs;
- fallback para modelos mais baratos/gratuitos;
- controle de custo;
- planos pagos extras para alunos que querem uso avançado.

A TDS tem mais de 2.000 alunos, grande parte já usa a IA atual e o faturamento mensal estimado é superior a R$ 1.100.000. Isso muda completamente a escala do contrato: não é um chatbot pequeno, é uma operação educacional com IA como camada de produto.

O L2 CASHFLOW precisa estar pronto para modelar esse tipo de cliente.

---

## 2. Por que o L2 CASHFLOW precisa de refactor

O dashboard financeiro atual, se for focado apenas em fluxo de caixa tradicional, não será suficiente. Contratos de IA têm uma estrutura de custo diferente:

- custo variável por token;
- custo por output;
- custo por cache miss/cache hit;
- custo por pesquisa externa;
- custo por tool call;
- custo por storage;
- custo por fila/worker;
- custo por assinatura operacional;
- custo por aluno ativo;
- custo por plano;
- custo por cliente;
- custo por uso acima da franquia;
- custo por fallback;
- custo por auditoria premium;
- custo por modelos diferentes.

Além disso, a receita também deixa de ser simples:

- implantação inicial;
- mensalidade base;
- franquia de uso incluída;
- excedente variável;
- add-ons;
- assinatura Plus do aluno;
- revenue share;
- taxa por assinante ativo;
- pacotes pré-pagos;
- upgrades de plano;
- cobranças pontuais de curadoria, setup, pesquisa, integração ou expansão.

O L2 CASHFLOW precisa conseguir enxergar tudo isso junto.

---

## 3. Princípio central do novo L2 CASHFLOW

O sistema deve responder três perguntas a qualquer momento:

### 3.1 Estamos ganhando dinheiro?

Por cliente, por contrato, por plano, por aluno, por turma, por produto e por período.

### 3.2 Onde o custo está nascendo?

Modelo, aluno, turma, recurso, ferramenta, search, compaction, research loop, prompt, cache miss, output longo, uso abusivo, plano mal precificado etc.

### 3.3 O que precisa acontecer agora?

- manter normal;
- reduzir contexto;
- trocar modelo;
- ativar modo econômico;
- bloquear pesquisa externa;
- pedir aprovação de excedente;
- sugerir upgrade;
- emitir cobrança extra;
- revisar contrato;
- revisar plano;
- alertar time;
- alertar cliente.

---

## 4. Nova taxonomia financeira do L2 CASHFLOW

O sistema precisa separar claramente os seguintes objetos.

### 4.1 Cliente

Exemplo: `TDS`.

Campos importantes:

- nome;
- CNPJ;
- segmento;
- tipo de cliente;
- faturamento estimado;
- número de usuários/alunos;
- contrato ativo;
- plano ativo;
- responsável L2;
- responsável cliente;
- SLA;
- risco financeiro;
- risco técnico;
- margem mínima exigida;
- modelo de cobrança;
- status de relacionamento.

### 4.2 Contrato

Exemplo: `TDS AI ECOSYSTEM — Operation`.

Campos:

- tipo: piloto, operação, scale, enterprise;
- valor de setup;
- mensalidade;
- prazo;
- forma de pagamento;
- franquia de IA incluída;
- hard cap;
- excedente;
- margem mínima;
- regras de upgrade;
- regras de cancelamento;
- cláusula de variável;
- status.

### 4.3 Produto

Exemplos:

- L2 CASHFLOW;
- LeticIA Core;
- LeticIA Plus;
- Hermes Operations;
- AI Router;
- Research Loop;
- Dashboard TDS;
- Knowledge Packs;
- Integrations.

### 4.4 Plano

Exemplos:

- Pilot;
- Operation;
- Scale;
- Enterprise;
- Core;
- Plus;
- Pro;
- Research Pack;
- Advanced Pack.

### 4.5 Receita

Categorias:

- setup;
- implantação;
- mensalidade;
- assinatura por usuário;
- revenue share;
- pacote extra;
- excedente;
- consultoria;
- integração;
- suporte;
- manutenção;
- auditoria;
- pesquisa;
- curadoria.

### 4.6 Custo

Categorias:

- API LLM;
- API search;
- embeddings;
- storage;
- database;
- VPS;
- fila/Redis;
- gateway;
- impostos;
- ferramentas;
- assinaturas;
- manutenção;
- suporte;
- mão de obra;
- contingência;
- câmbio.

### 4.7 Uso

Categorias:

- mensagem;
- sessão;
- tool call;
- compaction;
- pesquisa;
- retrieval;
- cache hit;
- cache miss;
- resposta cacheada;
- fallback;
- handoff;
- auditoria;
- tarefa concluída;
- research gap;
- knowledge pack update.

---

## 5. Entidades técnicas que o CASHFLOW precisa conhecer

### 5.1 Client Account

Representa a empresa cliente.

```sql
client_accounts
- id
- name
- legal_name
- cnpj
- segment
- estimated_monthly_revenue_brl
- active_students
- total_users
- status
- created_at
- updated_at
```

### 5.2 Contract

```sql
contracts
- id
- client_id
- name
- contract_type
- start_date
- end_date
- setup_fee_brl
- monthly_fee_brl
- min_margin_brl
- ai_budget_target_brl
- ai_budget_warning_brl
- ai_budget_hard_cap_brl
- variable_billing_enabled
- status
- notes
```

### 5.3 Plan

```sql
plans
- id
- client_id
- name
- plan_type
- price_brl
- billing_cycle
- included_users
- included_messages
- included_advanced_sessions
- included_research_credits
- ai_cost_target_per_user_brl
- ai_cost_hard_cap_per_user_brl
- overage_policy
- status
```

### 5.4 Entitlement

Entitlement é o que o aluno realmente pode usar.

```sql
user_entitlements
- id
- client_id
- external_user_id
- internal_user_id
- plan
- status
- valid_until
- daily_message_limit
- daily_advanced_limit
- monthly_research_limit
- monthly_ai_budget_brl
- hard_cap_brl
- source
- external_subscription_id
- created_at
- updated_at
```

### 5.5 Usage Event

Todo uso relevante precisa virar evento.

```sql
usage_events
- id
- client_id
- user_id
- session_id
- event_type
- plan_at_time
- route
- model_provider
- model_name
- input_tokens
- output_tokens
- cache_hit_tokens
- cache_miss_tokens
- tool_calls
- search_requests
- retrieval_chunks
- cost_usd
- cost_brl
- revenue_attributed_brl
- margin_attributed_brl
- metadata_json
- created_at
```

### 5.6 Model Rate Card

```sql
model_rate_cards
- id
- provider
- model
- effective_from
- input_price_per_1m_usd
- output_price_per_1m_usd
- cache_hit_price_per_1m_usd
- cache_write_price_per_1m_usd
- context_window
- supports_tools
- supports_caching
- supports_json
- quality_tier
- reliability_score
- latency_score
- notes
```

### 5.7 Search Rate Card

```sql
search_rate_cards
- id
- provider
- product
- price_per_1000_requests_usd
- price_per_1m_tokens_usd
- free_quota
- quality_tier
- notes
```

### 5.8 Invoice Line Item

```sql
invoice_line_items
- id
- client_id
- contract_id
- period_start
- period_end
- category
- description
- quantity
- unit_price_brl
- total_brl
- source
- status
```

---

## 6. Fórmula financeira principal

O CASHFLOW precisa calcular margem assim:

```text
Receita total do cliente
- custo real de IA
- custo real de search
- custo de infra alocado
- custo de ferramentas alocado
- custo de gateway/impostos estimado
- custo de suporte/mão de obra alocado
= margem operacional estimada
```

E também:

```text
Margem livre L2
= receita recebida pela L2
- API paga pela L2
- infra paga pela L2
- ferramentas pagas pela L2
- reservas operacionais
```

Para TDS, regra mínima:

```text
margem_livre_mensal >= R$ 4.500
```

Mas a meta real deve ser:

```text
margem_livre_mensal >= R$ 8.000 a R$ 12.000 no plano Operation
```

---

## 7. Fórmula de custo de API

Custo por chamada:

```text
cost_usd =
(input_cache_miss_tokens / 1_000_000) * input_cache_miss_price
+ (input_cache_hit_tokens / 1_000_000) * input_cache_hit_price
+ (output_tokens / 1_000_000) * output_price
+ tool_cost
+ search_cost
+ embedding_cost
```

Convertendo:

```text
cost_brl = cost_usd * fx_rate_usd_brl
```

Custo por aluno/mês:

```text
student_ai_cost_month = soma(cost_brl de todos usage_events do aluno no período)
```

Custo por plano:

```text
plan_ai_cost_month = soma(cost_brl dos usuários com plan_at_time = plano)
```

Custo por cliente:

```text
client_ai_cost_month = soma(cost_brl de usage_events do client_id)
```

Margem por aluno Plus:

```text
plus_margin_per_student = l2_revenue_per_plus_student - ai_cost_per_plus_student - allocated_infra_per_student
```

---

## 8. Caso TDS: estrutura financeira que o CASHFLOW deve suportar

### 8.1 Fase 1 — Piloto

- Valor: **R$ 18.000**;
- pagamento: **R$ 9.000 no início + R$ 9.000 na entrega**;
- escopo controlado;
- objetivo: provar valor, medir uso, mapear dores, construir base inicial.

O CASHFLOW precisa registrar:

- valor contratado;
- sinais recebidos;
- custos do piloto;
- horas internas;
- APIs usadas;
- margem real;
- aprendizados para forecast pós-piloto.

### 8.2 Fase 2 — Operation

Referência:

- mensalidade: **R$ 22.000/mês**;
- Core para todos os alunos;
- RAG/wiki;
- dashboard;
- Hermes operacional;
- roteador;
- uso controlado;
- franquia de IA incluída;
- variável acima da franquia.

Orçamento interno recomendado:

| Item | Valor |
|---|---:|
| Receita mensal base | R$ 22.000 |
| API target | R$ 8.000–10.000 |
| Zona amarela de API | R$ 12.000 |
| Hard cap sem aprovação | R$ 15.000–16.000 |
| Infra + ferramentas | R$ 2.500–4.000 |
| Margem livre mínima | R$ 4.500 |
| Margem livre desejada | R$ 8.000–12.000 |

### 8.3 Fase 3 — Scale

- mensalidade: **R$ 35.000–45.000/mês**;
- mais uso avançado;
- mais pesquisa;
- mais Plus;
- mais integrações;
- mais SLA;
- dashboard mais completo.

### 8.4 Fase 4 — Enterprise

- mensalidade: **R$ 60.000+/mês**;
- uso pesado diário;
- múltiplos canais;
- plus/pro avançado;
- pesquisa profunda;
- auditoria premium;
- SLA e redundância.

---

## 9. LeticIA Plus: modelo B2B2C que o CASHFLOW precisa suportar

A nova ideia estratégica é permitir que a TDS venda um add-on de IA para alunos.

Estrutura:

- LeticIA Core: incluso para todos os alunos;
- LeticIA Plus: assinatura opcional do aluno;
- preço provável: **R$ 99/mês**;
- cobrança feita pela TDS;
- L2 recebe valor por assinante ativo ou revenue share;
- backend L2 libera entitlement automaticamente.

### 9.1 Modelo recomendado

```text
TDS cobra o aluno.
Gateway envia webhook.
L2 atualiza entitlement.
Chat libera recursos Plus.
L2 cobra TDS mensalmente por assinante ativo + excedentes.
```

### 9.2 Receita L2 por assinante

Modelo simples recomendado:

```text
L2 recebe R$ 39 por assinante Plus ativo/mês
```

Alternativa:

```text
L2 recebe 50% da sobra líquida do Plus, com mínimo de R$ 29 por assinante ativo
```

### 9.3 Simulação com R$ 39 por assinante

| Adoção | Assinantes | Receita L2/mês |
|---:|---:|---:|
| 5% | 100 | R$ 3.900 |
| 10% | 200 | R$ 7.800 |
| 20% | 400 | R$ 15.600 |
| 30% | 600 | R$ 23.400 |
| 50% | 1.000 | R$ 39.000 |

### 9.4 Simulação de margem por aluno Plus

| Tipo de uso Plus | Custo IA estimado/aluno/mês | Receita L2 por aluno | Sobra antes de infra alocada |
|---|---:|---:|---:|
| Light | R$ 6–9 | R$ 39 | R$ 30–33 |
| Normal | R$ 8–14 | R$ 39 | R$ 25–31 |
| Heavy | R$ 13–23 | R$ 39 | R$ 16–26 |
| Max controlado | R$ 18–35 | R$ 39 | R$ 4–21 |
| Uso abusivo | R$ 35+ | R$ 39 | risco, precisa cap |

Conclusão:

> Plus de R$ 99 é viável se a L2 receber algo como R$ 39 por assinante ativo e controlar custo médio de IA abaixo de R$ 20 por assinante. Acima de R$ 35, precisa degradar, cobrar extra ou mover para Pro.

---

## 10. Métricas específicas para Plus

O L2 CASHFLOW precisa mostrar:

- assinantes Plus ativos;
- novos assinantes;
- cancelamentos;
- churn;
- MRR Plus bruto;
- repasse L2;
- custo IA Plus;
- margem Plus;
- alunos Plus deficitários;
- alunos Plus rentáveis;
- uso médio por assinante;
- custo por sessão avançada;
- custo por essay;
- custo por research;
- uso de search;
- uso de modelos premium;
- consumo de crédito;
- previsão de hard cap.

### 10.1 Alertas Plus

| Condição | Ação |
|---|---|
| aluno Plus passou de R$ 20 de custo/mês | marcar zona amarela |
| aluno Plus passou de R$ 30 | reduzir modelos/contexto |
| aluno Plus passou de R$ 35 | hard cap / Pro / pacote extra |
| turma inteira subiu custo | investigar uso ou campanha |
| search explodiu | bloquear search externo livre |
| cache hit caiu | revisar prompt architecture |

---

## 11. Dashboard financeiro por aluno

O CASHFLOW precisa ter uma tela filtrável por aluno.

Campos:

- aluno;
- plano;
- status de pagamento;
- turma;
- mensagens no mês;
- sessões;
- sessões avançadas;
- essays;
- research requests;
- input tokens;
- output tokens;
- cache hit tokens;
- cache miss tokens;
- custo total;
- receita atribuída;
- margem;
- risco;
- último uso;
- motivo de custo alto;
- modelo mais usado;
- ferramenta mais usada;
- previsão até fim do mês.

Exemplo de tabela:

| Aluno | Plano | Custo IA | Receita atribuída | Margem | Status |
|---|---|---:|---:|---:|---|
| Aluno A | Core | R$ 2,10 | R$ 11,00 alocado | R$ 8,90 | saudável |
| Aluno B | Plus | R$ 13,80 | R$ 39,00 | R$ 25,20 | saudável |
| Aluno C | Plus | R$ 32,40 | R$ 39,00 | R$ 6,60 | zona amarela |
| Aluno D | Plus | R$ 44,00 | R$ 39,00 | -R$ 5,00 | bloquear/Pro |

---

## 12. Dashboard financeiro por cliente

Tela principal para clientes enterprise.

### 12.1 Cards principais

- Receita contratada mensal;
- receita recebida no mês;
- custo API;
- custo search;
- custo infra;
- custo ferramentas;
- margem livre;
- margem percentual;
- risco de excedente;
- forecast até fim do mês;
- status do hard cap.

### 12.2 Tabela por produto

| Produto | Receita | Custo IA | Infra | Margem | Status |
|---|---:|---:|---:|---:|---|
| Core | R$ 22.000 | R$ 8.400 | R$ 2.200 | R$ 11.400 | ok |
| Plus | R$ 15.600 | R$ 5.600 | R$ 500 | R$ 9.500 | ok |
| Research Extra | R$ 2.500 | R$ 700 | R$ 0 | R$ 1.800 | ok |

### 12.3 Forecast

O CASHFLOW deve projetar:

```text
forecast_month_end_cost = current_cost / elapsed_days * days_in_month
```

E também um forecast ponderado por dia da semana:

```text
weighted_forecast = média móvel ponderada por uso dos últimos 7/14/30 dias
```

---

## 13. Dashboard de API Cost Explorer

Esse módulo é obrigatório.

Filtros:

- cliente;
- produto;
- plano;
- aluno;
- turma;
- data;
- provedor;
- modelo;
- rota;
- tool;
- search provider;
- cache hit rate;
- sessão;
- tipo de tarefa.

Dimensões:

- input tokens;
- output tokens;
- cache hit;
- cache miss;
- custo input;
- custo output;
- custo search;
- custo total;
- latência;
- erros;
- retries;
- fallback;
- qualidade estimada.

Perguntas que a tela precisa responder:

1. Qual modelo está custando mais?
2. Qual aluno está custando mais?
3. Qual turma está custando mais?
4. Qual tarefa queima mais API?
5. O cache está funcionando?
6. O output está longo demais?
7. O roteador está escolhendo modelo caro sem necessidade?
8. O modo fallback está sendo usado demais?
9. Search externo está explodindo?
10. Qual seria a economia se trocássemos 20% de uma rota para modelo menor?

---

## 14. Dashboard de cache

Métricas:

- cache hit tokens;
- cache miss tokens;
- cache hit rate;
- economia estimada;
- prompts com baixo cache hit;
- rotas com melhor cache;
- modelos com caching ativo;
- modelos sem caching;
- system prompt drift;
- tool schema drift;
- chunk order instability.

### 14.1 Economia estimada por cache

```text
cache_savings = custo_se_tudo_fosse_cache_miss - custo_real_com_cache
```

Exemplo:

| Rota | Cache hit rate | Custo real | Custo sem cache | Economia |
|---|---:|---:|---:|---:|
| Core RAG | 72% | R$ 2.100 | R$ 5.800 | R$ 3.700 |
| Essay Plus | 48% | R$ 3.400 | R$ 5.200 | R$ 1.800 |
| Research | 20% | R$ 1.900 | R$ 2.300 | R$ 400 |

---

## 15. Dashboard de roteador de modelos

O L2 CASHFLOW deve consumir dados do router.

Rotas possíveis:

- cache próprio;
- RAG/wiki;
- free LLM;
- DeepSeek Flash;
- DeepSeek Pro;
- MiniMax M2.5;
- MiniMax M3;
- Gemini Flash/Lite;
- Claude Sonnet;
- Claude Opus;
- OpenRouter fallback;
- research provider;
- handoff humano.

Métricas:

- número de chamadas por rota;
- custo por rota;
- latência;
- taxa de erro;
- taxa de fallback;
- qualidade estimada;
- custo por tarefa resolvida;
- custo por sessão concluída;
- economia por roteamento.

---

## 16. Pesquisa externa e research pipeline

O sistema TDS precisa de pesquisa sobre universidades, requisitos, bolsas, essays e informações que mudam.

O CASHFLOW precisa medir:

- quantas pesquisas foram feitas;
- qual provedor foi usado;
- custo por pesquisa;
- custo por knowledge pack criado;
- custo por lacuna resolvida;
- quantas respostas reutilizaram aquele pack;
- economia gerada por reutilização.

### 16.1 Search providers possíveis

- Serper;
- Brave Search;
- Perplexity Search;
- Tavily;
- Gemini grounding;
- scraping/fetch oficial;
- pesquisa Hermes;
- fonte manual aprovada.

### 16.2 Fila de pesquisa

O CASHFLOW deve entender a fila:

```sql
research_jobs
- id
- client_id
- requested_by_user_id
- query
- normalized_query
- topic
- priority
- status
- provider_used
- cost_brl
- result_quality
- converted_to_knowledge_pack
- created_at
- completed_at
```

### 16.3 Métrica importante

```text
research_roi = vezes_reutilizado * custo_evado_de_live_search - custo_da_pesquisa_original
```

---

## 17. Estrutura de pagamento e automação de assinatura

### 17.1 Fluxo recomendado

```text
Aluno no chat tenta usar Plus
→ frontend mostra upgrade
→ checkout da TDS
→ aluno paga para TDS
→ gateway envia webhook
→ backend L2 valida evento
→ user_entitlements é atualizado
→ chat libera Plus automaticamente
→ CASHFLOW registra MRR, assinante, repasse e custo
```

### 17.2 Gateways possíveis

- Stripe Billing;
- Pagar.me;
- Asaas;
- Mercado Pago;
- gateway próprio da TDS;
- integração via CSV/API se TDS já tiver cobrança interna.

### 17.3 Eventos necessários

- subscription.created;
- subscription.active;
- invoice.paid/payment_received;
- payment_failed;
- past_due;
- subscription.canceled;
- chargeback;
- refund;
- trial_started;
- trial_ended;
- plan_changed.

### 17.4 Reconciliação

O CASHFLOW deve ter uma tela de reconciliação:

| Fonte | Número |
|---|---:|
| Assinantes ativos no gateway | 410 |
| Entitlements ativos no app | 408 |
| Diferença | 2 |
| Ação | investigar |

---

## 18. Billing engine da L2

O CASHFLOW deve gerar cobrança para a TDS com base em:

- mensalidade base;
- assinantes Plus ativos;
- excedente aprovado;
- pacotes extras;
- research packs;
- integrações;
- ajustes manuais.

Exemplo:

| Item | Quantidade | Valor unitário | Total |
|---|---:|---:|---:|
| Operation Core | 1 | R$ 22.000 | R$ 22.000 |
| Plus ativos | 400 | R$ 39 | R$ 15.600 |
| Research Extra | 1 | R$ 2.500 | R$ 2.500 |
| Excedente Advanced | 1 | R$ 3.000 | R$ 3.000 |
| Total |  |  | R$ 43.100 |

---

## 19. Proteção de margem

O sistema precisa proteger margem automaticamente.

### 19.1 Níveis de alerta

| Nível | Condição | Ação |
|---|---|---|
| Verde | custo dentro do target | operar normal |
| Amarelo | 70–85% do orçamento | alertar interno |
| Laranja | 85–100% | avisar cliente / reduzir rotas caras |
| Vermelho | 100–110% | economia automática |
| Crítico | 110%+ | aprovação, pacote extra ou hard cap |

### 19.2 Degradações possíveis

- reduzir contexto;
- reduzir output máximo;
- reduzir número de chunks RAG;
- trocar modelo;
- bloquear pesquisa externa;
- limitar compaction;
- limitar tool calls;
- usar free/low-cost;
- responder com modo essencial;
- enviar lacuna para Hermes loop;
- sugerir upgrade.

### 19.3 Regra mínima L2

```text
Nunca permitir que um cliente fique com margem livre projetada abaixo de R$ 4.500/mês sem alerta crítico.
```

---

## 20. Simulador financeiro

O L2 CASHFLOW precisa ter um simulador embutido.

Inputs:

- número de alunos;
- % uso Core;
- % Plus;
- mensagens por aluno/dia;
- sessões avançadas;
- custo médio por mensagem;
- cache hit rate;
- search por aluno;
- modelo mix;
- preço do plano;
- revenue share;
- mensalidade base;
- infra;
- câmbio.

Outputs:

- receita total;
- custo API;
- custo infra;
- custo search;
- margem;
- margem por aluno;
- break-even;
- preço mínimo recomendado;
- limite de uso recomendado;
- forecast de lucro.

### 20.1 Exemplo TDS Operation + Plus

Premissas:

| Item | Valor |
|---|---:|
| Mensalidade Core | R$ 22.000 |
| Alunos | 2.000 |
| Plus adoption | 20% |
| Plus ativos | 400 |
| L2 por Plus | R$ 39 |
| Receita Plus L2 | R$ 15.600 |
| Receita total L2 | R$ 37.600 |
| API Core | R$ 8.500 |
| API Plus | R$ 5.600 |
| Infra/ferramentas | R$ 3.000 |
| Custo total | R$ 17.100 |
| Margem livre | R$ 20.500 |

Conclusão:

> Com Plus adoption de 20%, o contrato TDS deixa de ser apenas saudável e passa a ser altamente interessante para a L2, desde que o custo médio do Plus fique controlado.

---

## 21. Infraestrutura e alocação de custo

O CASHFLOW deve alocar custos de infraestrutura por cliente.

### 21.1 Itens de infra

- VPS principal;
- worker VPS;
- load balancer;
- Supabase;
- Redis;
- storage;
- observabilidade;
- backups;
- CDN/WAF;
- domínio;
- ferramentas de erro/log;
- e-mail/notificação;
- filas.

### 21.2 Alocação

Opções:

1. por cliente;
2. por uso;
3. por número de usuários;
4. por proporção de requests;
5. por custo dedicado;
6. híbrido.

Para TDS, recomenda-se:

```text
infra_allocated_to_tds = infra_dedicada_tds + proporção_de_uso_da_infra_compartilhada
```

### 21.3 Uma VPS ou múltiplas?

Fase piloto:

- 1 VPS boa é suficiente;
- Supabase gerenciado;
- modelos externos;
- workers limitados.

Fase Operation:

- ainda pode ser 1 VPS robusta;
- separar containers;
- limites de CPU/RAM;
- fila durável;
- monitoramento.

Fase Scale:

- App VPS 1;
- App VPS 2;
- Worker VPS;
- Load balancer;
- Redis/queue;
- Supabase;
- storage;
- monitoramento.

O CASHFLOW precisa conseguir comparar os cenários.

---

## 22. Integrações externas necessárias

### 22.1 Gateways

- Stripe;
- Pagar.me;
- Asaas;
- Mercado Pago;
- gateway interno da TDS.

### 22.2 IA/modelos

- DeepSeek;
- OpenRouter;
- MiniMax;
- Mistral;
- Gemini;
- Anthropic/Claude;
- OpenAI;
- free/low-cost providers.

### 22.3 Pesquisa

- Perplexity;
- Tavily;
- Serper;
- Brave;
- Gemini grounding;
- crawlers/fetch oficial;
- base interna.

### 22.4 Dados internos

- Supabase;
- Postgres;
- Redis;
- S3-like storage;
- logs do router;
- CRM;
- LMS;
- planilhas;
- CSV imports;
- webhooks.

### 22.5 Observabilidade

- Sentry;
- OpenTelemetry;
- Grafana/Prometheus;
- Logtail/Better Stack;
- Cloudflare analytics.

---

## 23. Data pipeline ideal

```text
Model Router
→ Usage Event Collector
→ Cost Normalizer
→ FX Converter
→ Cost Ledger
→ Client P&L Engine
→ Alerts Engine
→ Billing Engine
→ Dashboard
```

Para assinaturas:

```text
Gateway/TDS Billing
→ Webhook Receiver
→ Subscription Sync
→ Entitlements
→ Revenue Ledger
→ Billing Reconciliation
→ Dashboard
```

Para pesquisa:

```text
Search Request
→ Search Queue
→ Provider Router
→ Search Result
→ Cost Event
→ Knowledge Pack
→ Reuse Analytics
```

---

## 24. Feature list do refactor

### 24.1 Must-have

- clientes enterprise;
- contratos;
- planos;
- receitas recorrentes;
- custos variáveis de API;
- rate card de modelos;
- cost ledger;
- usage events;
- margem por cliente;
- margem por aluno;
- alertas de hard cap;
- exportação de relatório;
- billing por assinante Plus;
- reconciliação de gateway.

### 24.2 Should-have

- simulador de cenários;
- forecast até fim do mês;
- cache analytics;
- search cost analytics;
- turma/cohort view;
- model router view;
- alertas por Slack/Discord/e-mail;
- invoice builder;
- importador CSV.

### 24.3 Could-have

- recomendações automáticas de preço;
- detecção de alunos deficitários;
- sugestão automática de upgrade;
- comparação de modelos;
- anomalia de custo;
- dashboard para cliente;
- margem por feature.

---

## 25. Telas recomendadas

### 25.1 Executive Overview

Visão geral:

- caixa atual;
- MRR;
- custo IA;
- margem total;
- top clientes;
- clientes em risco;
- forecast.

### 25.2 Client P&L

Por cliente:

- receita;
- custo;
- margem;
- uso;
- plano;
- alertas;
- previsão.

### 25.3 AI Cost Explorer

Por modelo, aluno, rota, tarefa, plano.

### 25.4 Student Unit Economics

Por aluno:

- custo;
- receita;
- margem;
- plano;
- limite;
- uso.

### 25.5 Subscription Operations

Assinaturas:

- ativos;
- past due;
- cancelados;
- churn;
- MRR;
- repasse.

### 25.6 Research Cost Center

Pesquisa:

- jobs;
- custo;
- provedores;
- reutilização;
- packs.

### 25.7 Model Router Analytics

Roteador:

- rotas;
- modelos;
- fallback;
- custo;
- qualidade.

### 25.8 Billing & Invoices

- faturas;
- itens;
- excedentes;
- pacotes;
- status.

### 25.9 Forecast Simulator

- simular TDS;
- simular Plus;
- simular API;
- simular câmbio;
- simular adoção.

---

## 26. Relatórios exportáveis

O L2 CASHFLOW precisa gerar:

1. relatório mensal interno;
2. relatório para cliente;
3. relatório de uso de IA;
4. relatório de margem;
5. relatório de excedente;
6. relatório Plus;
7. relatório de research;
8. relatório de forecast;
9. proposta comercial com base no uso real;
10. relatório de renegociação.

---

## 27. Segurança, LGPD e auditoria

Como o sistema lidará com aluno, histórico, custo e pagamento, precisa de:

- RBAC;
- audit log;
- mascaramento de PII;
- segregação por cliente;
- criptografia de secrets;
- webhook signature verification;
- logs sem dados sensíveis desnecessários;
- retenção configurável;
- export/delete por cliente quando necessário;
- controle de acesso para sócios, devs e cliente.

### 27.1 Roles

- admin L2;
- finance L2;
- engineering L2;
- client owner;
- client viewer;
- auditor;
- read-only.

---

## 28. Regras para não quebrar margem

1. Nenhum contrato enterprise deve ser criado sem `min_margin_brl`.
2. Nenhum plano de IA deve existir sem `ai_budget_target_brl` e `ai_budget_hard_cap_brl`.
3. Nenhum modelo deve ser usado sem rate card.
4. Nenhuma rota premium deve ser ativada sem custo estimado.
5. Nenhuma assinatura Plus deve ser liberada sem entitlement claro.
6. Nenhum excedente deve ser cobrado sem item de fatura.
7. Nenhum hard cap deve ser ultrapassado sem alerta.
8. Nenhum cliente deve ficar abaixo de R$ 4.500 livres sem alerta crítico.
9. Nenhum uso gratuito deve ser considerado garantia contratual.
10. Nenhum dashboard deve esconder custo real de API.

---

## 29. Roadmap de implementação

### Fase 0 — Modelagem

- definir schema;
- definir objetos financeiros;
- definir rate cards;
- definir ledger;
- definir fórmulas;
- definir telas.

### Fase 1 — Core Financeiro

- clientes;
- contratos;
- planos;
- receitas;
- custos manuais;
- margem;
- dashboard P&L.

### Fase 2 — AI Usage Ledger

- usage events;
- model rate cards;
- cost calculation;
- router integration;
- token analytics;
- per-student cost.

### Fase 3 — Billing & Entitlements

- gateway webhooks;
- assinaturas;
- entitlement sync;
- Plus active users;
- invoice builder.

### Fase 4 — Forecast & Alerts

- forecast de custo;
- hard cap;
- alertas;
- simulações;
- margem mínima.

### Fase 5 — Client/Enterprise Reports

- relatórios exportáveis;
- dashboard para cliente;
- relatórios de uso;
- renegociação baseada em dados.

---

## 30. Critérios de aceitação

O refactor será considerado bem-sucedido quando o L2 CASHFLOW conseguir:

1. cadastrar a TDS como cliente enterprise;
2. registrar piloto de R$ 18.000;
3. registrar mensalidade Operation de R$ 22.000;
4. simular 2.000 alunos;
5. registrar custo de API por aluno;
6. calcular custo por modelo;
7. calcular cache hit/miss;
8. calcular custo por search;
9. prever custo até fim do mês;
10. alertar quando a margem mínima estiver ameaçada;
11. registrar assinantes Plus;
12. calcular repasse L2 por assinante;
13. calcular margem Plus;
14. gerar fatura para TDS;
15. exportar relatório mensal;
16. suportar importação de dados externos;
17. suportar filtro por cliente, turma, aluno, plano, modelo e período.

---

## 31. Fontes e referências técnicas usadas como base

Estas fontes devem ser revisadas periodicamente, porque preços e limites mudam:

- Supabase Pricing: https://supabase.com/pricing
- Supabase Storage Pricing: https://supabase.com/docs/guides/storage/pricing
- Stripe Billing Webhooks: https://docs.stripe.com/billing/subscriptions/webhooks
- Pagar.me Webhooks: https://docs.pagar.me/docs/webhooks
- Asaas Assinaturas: https://docs.asaas.com/docs/criando-uma-assinatura
- Asaas Checkout Recorrente: https://docs.asaas.com/docs/checkout-com-assinatura-recorrente
- DeepSeek Pricing: https://api-docs.deepseek.com/quick_start/pricing
- OpenRouter Docs: https://openrouter.ai/docs
- Anthropic Pricing/Caching: https://docs.anthropic.com/
- Gemini API Pricing/Caching: https://ai.google.dev/gemini-api/docs/pricing
- Perplexity Pricing: https://docs.perplexity.ai/docs/getting-started/pricing
- Tavily API Credits: https://docs.tavily.com/documentation/api-credits

---

## 32. Conclusão final para o sócio

O L2 CASHFLOW precisa evoluir para o sistema financeiro central da L2. O tipo de contrato que estamos desenhando para a TDS não pode ser gerido em planilha simples nem em dashboard genérico de caixa.

A L2 passará a vender sistemas onde:

- a receita é recorrente;
- o custo é variável;
- o uso é imprevisível;
- a margem depende de arquitetura;
- o cliente pode vender add-ons para usuários finais;
- a L2 pode receber por contrato, por uso, por assinante e por excedente;
- os custos de API precisam ser entendidos em tempo real;
- o roteador de modelos precisa conversar com o financeiro;
- o financeiro precisa influenciar o roteador;
- o dashboard precisa proteger lucro antes que o custo estoure.

Para clientes como TDS, o CASHFLOW precisa ser capaz de dizer:

> “Este cliente paga X, consome Y, gera margem Z, tem risco W, e a próxima ação recomendada é manter, degradar, cobrar excedente, vender Plus, sugerir upgrade ou renegociar.”

A versão nova do L2 CASHFLOW deve ser construída como um **AI Finance Operations Dashboard**, não apenas como um controle de caixa.

---

## 33. Apêndice — síntese do modelo TDS para alimentar o CASHFLOW

### Estrutura comercial

| Camada | Valor |
|---|---:|
| Piloto | R$ 18.000 |
| Sinal | R$ 9.000 |
| Entrega | R$ 9.000 |
| Operation Core | R$ 22.000/mês |
| Scale | R$ 35.000–45.000/mês |
| Enterprise | R$ 60.000+/mês |
| LeticIA Plus aluno | R$ 99/mês |
| L2 por Plus ativo | R$ 39/mês sugerido |

### Estrutura de custo

| Item | Alvo |
|---|---:|
| API Core target | R$ 8.000–10.000/mês |
| API warning | R$ 12.000/mês |
| API hard cap | R$ 15.000–16.000/mês |
| Infra/ferramentas | R$ 2.500–4.000/mês |
| Margem mínima L2 | R$ 4.500/mês |
| Margem desejada L2 | R$ 8.000–12.000/mês |

### Estrutura Plus

| Uso Plus | Custo estimado/aluno/mês | Status |
|---|---:|---|
| Light | R$ 6–9 | ótimo |
| Normal | R$ 8–14 | ótimo |
| Heavy | R$ 13–23 | saudável |
| Max controlado | R$ 18–35 | precisa alerta |
| Abusivo | R$ 35+ | precisa Pro/extra/degradação |

### Fórmula de sobrevivência

```text
L2 lucro saudável = mensalidade base + receita Plus + variável - API - infra - ferramentas - suporte - reserva
```

### Regra final

> Salvar tudo barato. Enviar pouco. Cachear o estável. Recuperar só o necessário. Compactar no limite. Pesquisar por fila. Transformar pesquisa em base. Degradar com elegância. Cobrar excedente. Proteger margem.
