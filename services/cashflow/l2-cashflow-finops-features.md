# Documentação de Features: L2 Cashflow — FinOps de IA

Este documento descreve detalhadamente todas as funcionalidades adicionadas ao **L2 Cashflow** durante a sua evolução de um sistema financeiro tradicional para uma plataforma moderna de **FinOps B2B para Inteligência Artificial**.

A arquitetura do projeto foi expandida em 8 fases sucessivas. Abaixo, detalhamos cada recurso, o que ele faz e **o porquê** da sua existência.

---

## 1. Migração para SQLite Robusto (Fase 1)
**O que foi feito:** Substituímos o armazenamento de dados sensíveis e críticos de arquivos JSON planos para um banco de dados relacional (SQLite via `better-sqlite3`). Criamos tabelas bem definidas (`client_accounts`, `contracts`, `usage_events`, etc.) usando chaves estrangeiras (`FOREIGN KEY`) e deleções em cascata (`ON DELETE CASCADE`).
**Por que foi feito:** JSON é inadequado para sistemas com alta concorrência e relacionamentos complexos. Ao gerir custos de IA por tokens e eventos (que podem gerar centenas de transações por minuto), precisávamos de integridade referencial, velocidade para agregar dados via SQL (ex: `SUM(cost)`), e prevenção contra corrupção de dados. O SQLite oferece a robustez necessária sem a complexidade de gerir um servidor de banco separado na nuvem neste estágio do projeto.

---

## 2. AI Usage Ledger & Webhook de Consumo (Fase 2)
**O que foi feito:** Criamos a tabela `usage_events` para ser o "livro-razão" de todas as chamadas de IA. Refatoramos a rota `app/api/webhooks/tokens/route.ts` para que recebesse *payloads* enriquecidos contendo número de tokens (input/output/cache), ID do aluno (`user_id`), tipo do modelo (ex: GPT-4o, Claude), custo em dólares/reais e rota acessada. 
**Por que foi feito:** Para cobrar clientes corporativos de forma justa e otimizar custos, precisamos de granularidade extrema. Não basta saber que "gastamos 100 dólares". Precisamos saber **quem** gastou, em **qual feature** e com **qual modelo**. Essa infraestrutura é o alicerce que alimenta todos os gráficos e cálculos do resto do sistema.

---

## 3. Enterprise P&L — Profit & Loss (Fase 3)
**O que foi feito:** Uma nova tela (`/enterprise/pnl`) que cruza a **receita contratada** de um cliente Enterprise (ex: TDS) com o **custo de IA realizado** para aquele cliente no mês. Ela calcula e exibe em tempo real a **Margem Livre** (lucro líquido) daquela operação. Também possui um sistema de alerta que fica vermelho (ATENÇÃO) caso a margem atinja níveis abaixo da "Margem Mínima Alvo" definida no contrato.
**Por que foi feito:** O maior medo de operações com LLMs é o custo variável destruir o lucro fixo (modelo SaaS). Essa tela resolve o problema da "caixa-preta", permitindo que os gestores da L2 visualizem a saúde financeira de um cliente com um simples olhar, evitando surpresas no final do mês.

---

## 4. AI Cost Explorer (Fase 4)
**O que foi feito:** Um dashboard investigativo (`/enterprise/explorer`) para entender *como* o dinheiro da IA está sendo gasto. Ele possui:
- Gráficos de rosca mostrando o **Custo por Modelo de IA**.
- Gráfico de **Eficiência de Cache** (Hit vs Miss).
- Tabela listando o **Top 10 Alunos Deficitários** (usuários que mais consumiram tokens).
**Por que foi feito:** Se o P&L da Fase 3 ficar "vermelho", o gestor precisa saber a causa raiz. O Cost Explorer diz exatamente para onde o dinheiro está vazando. Mostrar a eficiência do cache ajuda os engenheiros a validarem se suas estratégias de prompt-caching estão funcionando. Descobrir os "Alunos Deficitários" permite aplicar limites individuais e combater abusos.

---

## 5. Billing Plus & Entitlements (Fase 5)
**O que foi feito:** Adicionamos o modelo de negócio **B2B2C** no qual os alunos finais podem assinar planos Premium (ex: LeticIA Plus) via Stripe ou Hotmart. O sistema captura esse pagamento e automaticamente faz o "Split": separa a taxa do gateway (ex: 4.99%), e do valor líquido, direciona a parcela da L2 (ex: 30%) e a do Cliente/Escola (ex: 70%).
**Por que foi feito:** IA é cara e, eventualmente, não dá para oferecer tudo de graça para o aluno final. O Billing Plus abre uma nova linha de receita para a L2 e transforma um centro de custo para o cliente em um potencial centro de lucro, onde a escola passa a ganhar dinheiro com as assinaturas premium dos alunos.

---

## 6. Forecast, Simulador & Alertas (Fase 6)
**O que foi feito:** Uma nova tela (`/enterprise/forecast`) que rastreia o custo diário, projeta matematicamente quanto será o custo no último dia do mês e exibe o preenchimento de uma **Barra de Budget**. Além disso, contém um **Simulador Interativo** com sliders para testar "o que aconteceria" se o custo por sessão caísse ou os alunos aumentassem.
**Por que foi feito:** FinOps não é só olhar para o passado, é prevenir o futuro. Projetar o custo permite intervir (desligar modelos caros, avisar o cliente) *antes* do budget acabar. O simulador é uma poderosa ferramenta comercial e estratégica para ajudar os líderes da L2 a desenharem novos planos e preverem impactos de aumento de tráfego.

---

## 7. Relatórios Consolidados e Exportação (Fase 7)
**O que foi feito:** Um painel (`/enterprise/reports`) dividido em abas (Comercial vs Operacional) gerando um consolidado automático. Adicionamos a funcionalidade de exportação crua (CSV) e impressão formal (`PDF`) estilizada especificamente para remover menus irrelevantes.
**Por que foi feito:** Para comunicação externa. No final do mês, a L2 precisa enviar para a TDS (e outros clientes) um relatório transparente provando o quanto foi economizado com cache, quantos tokens foram gastos e quanto a escola vai receber do repasse das assinaturas Plus.

---

## 8. Segurança e Auditoria - RBAC (Fase 8)
**O que foi feito:** A criação das bases de usuários do sistema interno da L2 com papéis definidos (`admin`, `manager`, `viewer`) e o módulo de auditoria (`audit_log`), que possui uma tela (`/enterprise/audit`) com filtros refinados sobre quem fez o que, quando, e qual era o IP.
**Por que foi feito:** A partir do momento em que o sistema lida com dados financeiros, assinaturas, divisões de lucro e orçamentos que podem desligar serviços, a governança torna-se inegociável. Se um contrato tiver sua "Margem Mínima" alterada misteriosamente, o log de auditoria revela qual usuário fez isso, garantindo transparência técnica e proteção legal para a L2 Systems.
