# Estratégia de mercado e engenharia para o L2 ATLAS

O L2 ATLAS deve ser tratado como uma nova categoria de produto: um **cockpit operacional para humanos + agentes**, com execução, memória, auditoria, wiki persistente, rotina de pulse e contexto relacional em um único sistema. Isso importa porque o mercado já saiu da fase “copilot bonito” e entrou na fase “como colocar agentes dentro do trabalho real”: a McKinsey reporta investimento quase universal em IA, mas só 1% das empresas se considera madura em implantação; a Microsoft descreve a passagem para “hybrid teams” de humanos e agentes e diz que 81% dos líderes esperam agentes moderada ou extensivamente integrados à estratégia de IA em 12–18 meses. Em outras palavras: existe demanda, mas a maturidade operacional ainda é baixa. citeturn31view0turn31view1

A oportunidade do ATLAS não é ser “mais um builder de agentes”, “mais um chat com arquivos” ou “mais um CRM com IA”. O espaço vazio está em **orquestrar trabalho real com memória operacional, evidência imutável, aprovações, observabilidade e baixa latência**, sem cair em stacks inchadas. Minha recomendação, portanto, é: **forkar e endurecer o Hermes como fundação**, adicionar uma camada Atlas com os objetos de produto certos, expor isso por um WebUI excelente e por interfaces locais rápidas, e empacotar o sistema com disciplina de software tradicional. citeturn9view0turn20view1turn20view2turn20view5turn20view6turn32view6turn32view7

## Tese de mercado

O mercado visível hoje está fragmentado em seis caixas. A primeira é a dos **builders de automação e agentes**: Lindy, Relevance AI, Gumloop, n8n e Dify vendem agentes, workflows, integrações e automações recorrentes. A segunda é a dos **hubs de chat e conhecimento**, como Open WebUI, Notion AI e NotebookLM. A terceira é a dos **frameworks e IDEs de orquestração**, como CrewAI e LangGraph Studio. A quarta é a dos **CRMs extensíveis**, como Twenty. A quinta é a dos **coding agents**, onde Claude Code e Codex brigam pela superfície do terminal, IDE e desktop. A sexta é a dos **gateways e harnesses locais**, onde OpenClaw e Hermes já oferecem sessões, skills, canais, ferramentas e execução. O mercado, portanto, é grande — mas ninguém domina o conjunto “execução + memória + evidência + relacionamento + cockpit”. citeturn15view1turn15view2turn29view1turn22search14turn26view2turn21view1turn38view0turn16view0turn30search5turn30search2turn15view3turn9view14turn9view15turn37view0turn9view0

Essa fragmentação cria uma leitura estratégica importante. Os vencedores atuais vendem **partes** do problema: Lindy vende o assistente de trabalho; Gumloop e n8n vendem o canvas de automação; Dify vende a plataforma de app/agent workflow; Open WebUI vende a interface unificada; Notion e NotebookLM vendem pesquisa e conhecimento; Twenty vende o grafo comercial; Claude Code e Codex vendem execução em código; OpenClaw e Hermes vendem o runtime/gateway. O ATLAS só vira categoria própria se o centro do produto for outro: **missões, runs, pulse, wiki viva, grafo relacional e aprovação auditável**. Essa é a diferença entre “ferramenta de IA” e “sistema operacional de operação”. A inferência aqui é direta a partir do posicionamento oficial dessas plataformas e do tipo de workflow que cada uma enfatiza. citeturn15view0turn28view0turn29view0turn9view6turn26view4turn21view1turn38view1turn16view2turn30search7turn9view10turn15view4turn25view2turn25view1turn37view1turn20view1

### Matriz competitiva

| Produto | Categoria | Posição oficial | Leitura para o ATLAS | Fontes |
|---|---|---|---|---|
| Lindy | Assistente de trabalho | Focado em inbox, calendário, reuniões, follow-ups e briefings diários. | É benchmark de “AI executive assistant”, mas não é um cockpit operacional com runtime, wiki e CRM unidos. | citeturn15view1turn15view0 |
| Relevance AI | Builder low/no-code | “AI Workforce” para GTM e high-growth teams, com workforces, ferramentas, conhecimento e monitoramento. | Forte em times de receita e automação visual; menos convincente como OS pessoal/local de operação. | citeturn15view2turn28view0turn28view1 |
| Gumloop | Builder no-code | Agentes e workflows drag-and-drop, com triggers recorrentes e por evento, e superfícies em Slack/Teams/email. | Muito bom em automação acionada por triggers; menos forte em memória operacional durável, auditoria profunda e modelo de dados próprio. | citeturn9view4turn29view0turn29view1 |
| n8n AI Agents | Automação para times técnicos | Workflows e agentes “you can see and control”, fair-code, self-host, canvas rastreável. | Excelente para integrar apps e processos; ruim como cockpit opinado de missão, wiki, CRM e aprovação humana. | citeturn22search14turn9view6turn22search0 |
| Dify | Plataforma agentic/RAG | Workflow visual, RAG, plugins, observability e self-host. | É mais plataforma de builder/ops do que produto operador. O self-host oficial já implica 13 containers e base mais pesada que o baseline desejado para o ATLAS. | citeturn26view2turn26view3turn26view4turn26view1turn26view0 |
| Open WebUI | Hub de interface e conhecimento | Interface unificada para modelos, knowledge/RAG, notes, channels e Open Terminal. | É um ótimo benchmark de cockpit de chat e knowledge, mas o eixo ainda é “interface de chat”, não “sistema operacional de empresa”. | citeturn21view1turn9view8 |
| CrewAI | Framework/control plane | Multi-agent com guardrails, memory, knowledge e observability; control plane para produção. | Fala mais com builders e infra teams do que com operadores/founders que querem um cockpit pronto. | citeturn30search5turn30search7turn30search3 |
| LangGraph Studio | Framework/IDE | IDE especializada para visualizar, interagir e debugar sistemas agentic; runtime com durable execution e human-in-the-loop. | Forte como base de engenharia; fraco como produto final para founder ops e small-company cockpit. | citeturn30search2turn30search4turn9view10 |
| Twenty | CRM open source | CRM self-hostável, extensível via TypeScript packages, APIs/webhooks/OAuth e “AI agents”. | Excelente benchmark para entidades comerciais e extensibilidade, mas não resolve runtime de agentes nem knowledge/pulse. | citeturn9view11turn15view3turn15view4 |
| Notion AI | Workspace/enterprise search | Notion Agent, Custom Agents, Enterprise Search, AI Meeting Notes e Research Mode. | Muito forte em busca e relatórios sobre dados conectados; mais fraco em execução auditável, subagentes e desktop nativo rápido. | citeturn38view0turn38view1turn15view6 |
| NotebookLM | Pesquisa orientada por fontes | Pesquisa e síntese sobre fontes enviadas, com citações, guias, áudio e foco em privacidade. | Excelente benchmark de UX de pesquisa grounded; não é runtime de operação contínua nem sistema de relacionamento. | citeturn16view0turn16view2turn16view3 |
| Claude Code | Coding agent | Agente de código local no terminal/desktop/IDE/Slack, com permissões antes de alterar arquivos ou rodar comandos. | Benchmark de UX local, aprovações e superfície multiambiente; escopo centrado em código, não em operação da empresa. | citeturn9view14turn25view2 |
| Codex | Coding agent local + cloud | CLI local, app/IDE e agente cloud paralelo em sandboxes; skills padronizadas. | Benchmark de agent loop, contexto e execução paralela; ainda é produto de engenharia de software, não cockpit operativo completo. | citeturn9view15turn9view16turn25view0turn25view1 |
| OpenClaw | Gateway pessoal self-hosted | Gateway multi-canal self-hosted para agentes, com skills em Markdown e foco em controle local. | Muito relevante como benchmark de gateway, skills e canais; ainda não é cockpit empresarial com wiki/CRM/pulse como centro. | citeturn37view0turn37view1turn37view2 |
| Hermes | Harness/runtime de agentes | Perfis independentes, skills, memory, context files, delegação, cron, MCP, voz, ~64 tools e TUI/CLI. | É o concorrente adjacente mais importante e a melhor fundação técnica para o ATLAS; o trabalho do ATLAS é transformá-lo em produto operacional. | citeturn9view1turn9view2turn20view0turn20view1turn20view2turn20view5turn20view6 |

O resumo competitivo é simples: **ATLAS não deve entrar no mercado pela porta “visual agent builder” nem pela porta “chat with files”**. Essas portas já estão congestionadas. A porta correta é a do **cockpit operacional mission-centric**, porque ela combina capacidades que hoje aparecem espalhadas em produtos diferentes e as amarra em uma única rotina diária de trabalho. citeturn29view1turn21view1turn38view1turn15view3turn9view14turn9view0

## Wedge de produto

### Primeiro comprador

O primeiro comprador deve ser o **founder técnico / AI operator de time pequeno**, seguido por **agências AI-heavy** e pequenos times de produto/dev com alto grau de autonomia. Esse segmento é o melhor wedge porque já vive o problema inteiro: inbox, agenda, reuniões, Slack/Discord, GitHub, docs, clientes, prospects, follow-ups e automações quebradas em ferramentas diferentes. Também é o segmento mais capaz de aceitar um produto com configuração inicial, CLI/TUI, self-host opcional e integrações avançadas. Isso combina com o posicionamento atual de n8n para times técnicos, com a abertura do Twenty para agências e com a tendência de human-agent teams descrita pela Microsoft. citeturn22search14turn15view4turn31view1

Eu **não** começaria por enterprise tradicional. Embora Notion, Relevance AI, Dify e CrewAI já falem com compradores corporativos, esse caminho exige mais conformidade, suporte, procurement e integração formal do que um produto novo precisa no primeiro ship. Também **não** começaria por usuário puramente “coding agent”, porque esse espaço já está fortemente disputado por Claude Code e Codex. O wedge de ATLAS é maior do que desenvolvimento, mas menor do que “plataforma enterprise genérica”: é o operador que precisa tocar empresa, produto, contexto e execução a partir de um único cockpit. citeturn15view2turn26view2turn30search7turn38view0turn9view14turn9view15

### Menor demo indispensável

A menor demo que faz alguém dizer **“eu preciso disso”** não é uma conversa com ferramentas. É o seguinte loop fechado:

1. O usuário conecta Gmail ou Outlook, calendário, Slack ou Discord, GitHub, uma fonte comercial simples e uma pasta ou repo de documentos.
2. O ATLAS entrega um **briefing de abertura do dia** com prioridades, reuniões com dossiê, mensagens que exigem resposta, PRs/issues críticas, oportunidades em risco e checks de pulse. Lindy já mostrou que briefings e automação de agenda/inbox são altamente desejáveis; Gumloop mostra que triggers recorrentes e por evento são parte do hábito; Hermes já oferece cron, delegação, memória e sessões para sustentar esse loop. citeturn15view0turn29view0turn9view2turn20view1  
3. Cada item do briefing aparece ligado a uma **missão** com evidência clicável, uma página de wiki viva e entidades relacionais envolvidas. Essa parte procura combinar a força de pesquisa grounded de NotebookLM com a busca conectada e o Research Mode do Notion, mas dentro de um runtime permanente. citeturn16view0turn16view2turn38view1turn38view0  
4. O sistema propõe ações concretas: rascunhar e-mail, abrir issue, atualizar touchpoint no CRM, preparar reunião, registrar decisão na wiki, rodar subagente de pesquisa, ou agendar rechecagem. Isso pega o melhor de Claude Code e Codex no padrão “propor, pedir permissão, executar, registrar”, mas aplicado à operação da empresa, não só ao código. citeturn9view14turn25view1turn9view15  
5. O usuário aprova uma ou duas ações; o ATLAS executa e grava **audit trail completo** de input, ferramentas, aprovação, output e efeito externo.  
6. No fim do dia, o ATLAS gera um **closing brief** e agenda os próximos pulses.

Se essa demo funcionar bem, o comprador entende instantaneamente o valor: **menos troca de contexto, menos esquecimento, mais follow-through e mais confiança**. Se a demo for apenas “chat com ferramentas” ou “canvas com nós”, o usuário verá ATLAS como substituto parcial de Open WebUI, Gumloop, n8n ou Dify — e não como categoria própria. citeturn21view1turn29view1turn22search14turn26view2

### Objetos centrais do produto

Para evitar que o produto vire um dashboard amorfo, o ATLAS deve ter cinco objetos centrais desde o início:

- **Missão**: objetivo operacional com status, owner, contexto, evidência, próximos passos e entidades relacionadas.  
- **Run**: uma execução específica de agente ou subagente, com logs, ferramentas usadas, custo, latência e resultado.  
- **Pulse**: verificação agendada ou acionada por evento que produz briefing, alerta ou anomalia.  
- **Wiki viva**: página Markdown mantida pelo agente, sempre ligada a fontes imutáveis e com contradições/staleness explícitas.  
- **Relationship graph**: pessoas, organizações, oportunidades e touchpoints conectados a missões, runs e wiki.

Esses cinco objetos são, na prática, a barreira defensável do produto: eles unem o que hoje está separado entre CRM, notes, RAG, automação e runtime.

## Recomendação de stack técnico

### Decisão de arquitetura

A decisão principal é esta: **o ATLAS deve ser um fork produtizado do Hermes, não uma aplicação separada que “chama Hermes” por fora**. Hermes já entrega perfis independentes, memory persistente, skills com progressive disclosure, context files, delegação/subagentes, cron, MCP, TUI/CLI e um conjunto amplo de ferramentas. Reescrever isso do zero no primeiro ciclo destruiria velocidade; tratá-lo como caixa-preta destruiria a chance de fazer ATLAS virar plataforma própria. citeturn9view1turn9view2turn20view1turn20view2turn20view5turn20view6

Ao mesmo tempo, o ATLAS não deve aceitar que o runtime Python seja o centro de tudo para sempre. A arquitetura recomendada é de **dois planos**: um plano de runtime herdado do Hermes para agent loop, skills, providers e ferramentas; e um plano de controle em Rust para experiência local, API do cockpit, governança, indexing e desktop nativo. O arranjo correto é este:

```text
CLI/TUI ─┐
WebUI ───┼──> atlasd               ──> SQLite local ou Postgres team
Desktop ─┘     Rust control plane      + FTS/embeddings + event log
                │
                ├──> Atlas data model: missions, runs, pulse, wiki, CRM
                │
                └──> Hermes runtime workers
                     Python harness + tools + providers + subagents
```

Esse desenho preserva o leverage do Hermes e prepara uma evolução séria para desktop, baixíssima latência e controle fino de permissões, sem forçar uma reescrita prematura do agent harness. A própria Tauri v2 já foi desenhada para capacidades/permissions, IPC por message passing, sidecars e atualizações assinadas; Electron, ao contrário, carrega a arquitetura multi-processo do Chromium e exige uma disciplina de segurança muito mais pesada para conteúdo remoto. citeturn32view6turn32view8turn32view9turn34view0turn34view1turn32view7turn33view8

### Stack recomendada

**Fundação de runtime.** Faça do Hermes forkado o repositório canônico do runtime. Preserve perfis, cron, skills, sessões, provider routing, MCP e TUI. Estenda apenas onde o ATLAS precisa de semântica própria: missão, run, pulse, wiki, approvals, relation runtime e eventing. A convergência entre Hermes skills e o padrão de Agent Skills do Codex é especialmente útil: manter skills em Markdown e aderir ao máximo possível a esse ecossistema aumenta portabilidade e reduz lock-in de autoria. citeturn20view0turn20view1turn25view0

**Plano de controle em Rust.** O `atlasd` deve ser um daemon Rust usando Tokio e Axum. Tokio oferece runtime assíncrono com I/O, timers, filesystem e scheduling; Axum oferece roteamento e middleware sobre Tower, o que ajuda bastante para tracing, auth, timeouts e policy enforcement. Esse daemon vira o ponto único para o WebUI, para a shell desktop e para o índice local. citeturn33view7turn33view6

**WebUI.** Recomendo **React + TypeScript + Vite**, em SPA operacional, não SSR-first. O cockpit precisa de tabelas grandes, timelines, diffs, inspector de run, wiki editor com preview, entity panes e streaming de eventos. O WebUI deve falar **somente** com o `atlasd`; não deve falar direto com provider API, banco ou runtime Python.

**Desktop.** Recomendo **Tauri v2** como shell desktop futura e, quando ela existir, que seja realmente fina: janela principal do cockpit, tray, command palette, notificações, overlay, hotkeys e sidecars estritamente permitidos por capability. Tauri usa a WebView do sistema e binário Rust compilado, o que é coerente com a meta de não embarcar Chromium por padrão. citeturn32view6turn32view8

**Banco e busca.** Para single-user e dogfood, o padrão deve ser **SQLite + WAL + FTS5**. SQLite FTS5 já oferece full-text search eficiente; WAL é persistente e bom para o padrão de um escritor/muitos leitores típico do cockpit local. Para team mode, o alvo deve ser **Postgres com RLS e pgvector**. Em outras palavras: local-first com SQLite; multiusuário com Postgres; nenhum vector database separado no v1. Se o corpus local crescer muito ou a busca lexical ficar limitante, adicione **Tantivy** como índice secundário em Rust — não como dependência obrigatória. citeturn32view0turn32view1turn32view2turn32view3turn32view4

**Objeto canônico e storage.** Fontes brutas devem ser armazenadas fora do banco, em diretório imutável e endereçado por hash; o banco guarda metadados e offset/proveniência. A wiki deve permanecer em **Markdown canônico**. RAG precisa ser tratado como mecanismo de recuperação, não como verdade do sistema.

**Fila e scheduler.** Não introduza Redis, NATS ou infraestrutura distribuída no primeiro ship. Use **scheduler e fila baseados em banco** para runs assíncronos, re-tentativa, leases e visibility timeout. Reaproveite o cron do Hermes onde isso acelerar o time-to-market, mas normalize toda execução para o mesmo modelo de run e event log.

**IPC.** Entre WebUI e `atlasd`, use HTTP local + SSE ou WebSocket para streaming. Entre `atlasd` e runtime Hermes, use JSON-RPC em Unix domain socket/named pipe ou loopback autenticado, com contratos explícitos de evento. Para a shell desktop, use o IPC nativo do Tauri e sidecars só com capacidades estritamente declaradas. citeturn32view9turn34view0

**Empacotamento.** Para o primeiro ciclo, não force bundling completo do runtime Python dentro da app desktop. É melhor shippar primeiro **CLI/TUI + serviço local + WebUI** e deixar a shell desktop como etapa seguinte. Quando a desktop entrar, use o updater assinado do Tauri. citeturn34view1

### O que evitar

Evite três anti-padrões.

Primeiro, **Electron como baseline**. Electron herda a arquitetura multi-processo do Chromium e sua própria documentação mantém um checklist longo de hardening para conteúdo remoto, IPC e sessões; isso não significa que Electron seja inútil, mas sim que ele não é o ponto de partida ideal para um produto cujo diferencial promete baixo consumo, rapidez e feeling nativo. Tauri parte de outra base. citeturn32view7turn33view8turn32view6

Segundo, **stack de plataforma pesada no v1**. O quickstart self-host do Dify sobe 13 containers e sua documentação pede pelo menos 4 GiB de RAM, recomendando 8 GiB iniciais de memória virtual no Mac. Esse tipo de footprint pode ser aceitável para uma plataforma de builder, mas é o baseline errado para um cockpit pessoal/pequeno time que quer parecer software sério e leve. citeturn26view1turn26view0

Terceiro, **RAG como centro do produto**. NotebookLM e Notion já definem bem o benchmark de experiência grounded por fontes, e Open WebUI já entrega um hub de chat/knowledge bastante extensível. Se o ATLAS entrar pela porta “tenho um chat com documentos”, ele perde a narrativa imediatamente. O centro tem de ser operação, não busca. citeturn16view0turn16view2turn38view1turn21view1

## Padrões de engenharia e metas de performance

### Fronteiras do monorepo

A organização do repositório precisa reduzir acoplamento entre linguagens e tornar o caminho de upstream do Hermes gerenciável. A estrutura recomendada é:

- `runtime/hermes/` para o fork do Hermes e patches próximos ao harness.  
- `runtime/atlas_ext/` para missões, wiki, pulse, relation runtime, approvals e políticas.  
- `crates/atlasd/` para daemon Rust, API, indexação, auth local, notificações e integração futura com desktop.  
- `apps/web/` para o cockpit TypeScript.  
- `schemas/` para contratos de evento, auditoria, entities e payloads de tool/runs.  
- `tests/e2e/` para cenários reais cross-component.  
- `ops/` para packaging, migrations, fixtures, perf gates e release automation.

A regra de ouro deve ser: **UI não fala direto com runtime nem banco**; **runtime não define sozinho o modelo operacional**; **toda escrita observável gera evento e materialização**.

### Standards obrigatórios

O padrão de engenharia que eu recomendo para o ATLAS é conservador, explícito e auditável.

**Fork-first, wrapper-never.** Patches genéricos e correções de fundação devem ser candidatos a upstream no Hermes; tudo que for específico de produto Atlas fica em módulos Atlas. Isso diminui o risco de divergência insolúvel com upstream, especialmente porque o Hermes está evoluindo muito rápido: a release v0.11.0 consolidou uma TUI Ink/React e um volume de mudanças muito alto em pouco tempo. citeturn20view0

**Audit-first design.** Todo write path relevante precisa produzir um evento estruturado: quem pediu, que contexto foi usado, que ferramenta foi chamada, o que foi aprovado, qual foi o efeito externo e como reverter. Isso vale mais do que “memória” no marketing, porque é o que torna o sistema confiável para operação real. CrewAI, n8n e Dify todos enfatizam observability/tracing; o ATLAS precisa tratar isso como coluna vertebral, não como add-on. citeturn30search7turn22search14turn17search2

**SQL explícito.** Use SQLx no lado Rust e evite ORM pesado. SQLx valida queries em tempo de compilação contra o banco; isso é muito valioso em um produto com muitos writes críticos, migrações e superfícies multi-entidade. citeturn32view5

**Testes rápidos e isolados.** Use `cargo-nextest` no plano Rust, porque ele oferece isolamento por teste e pode ser até 3x mais rápido que `cargo test`. No plano Python/Hermes, mantenha contract tests para eventos, ferramenta autorizada/não autorizada, approvals, recovery e compatibilidade de perfis. citeturn33view2

**Tracing estruturado desde o dia zero.** Em Rust, use `tracing` para spans/eventos; em Python, normalize logs para o mesmo schema. Sem isso, debugging assíncrono e multiagente degrada muito rápido. citeturn33view3

**Perf gates por PR.** Todo PR relevante deve carregar benchmarks de: cold start, memória idle, latência de busca, latência de open mission/run, custo de context packing e custo de render de telas densas. Quando houver regressão acima do budget, o build falha.

**Cross-platform CI obrigatória.** Teste Linux, macOS e Windows com matrix builds no GitHub Actions. ATLAS não pode descobrir portabilidade na mão do usuário. citeturn33view5

**Perf profiling contínuo.** Flamegraphs precisam entrar no fluxo normal de regressão; não só quando der problema. citeturn33view4

**Context discipline.** O Hermes já usa skills em progressive disclosure para poupar tokens, e o time do Codex documenta explicitamente que o crescimento do contexto é uma das responsabilidades centrais do harness. O ATLAS deve tornar isso política de produto: contexto curto por padrão, wiki condensada por missão, deltas por run e escalonamento só quando necessário. citeturn20view1turn25view1

### Orçamentos de performance

Os budgets abaixo são recomendações de produto, não garantias de fornecedor. Eles servem para impedir deriva de arquitetura.

| Métrica | Budget recomendado |
|---|---|
| Cold start do CLI/TUI para prompt interativo | até 500 ms em máquina de desenvolvimento moderna |
| Startup do serviço local para primeira resposta de healthcheck | até 800 ms |
| Primeira pintura útil do WebUI local | até 1,5 s |
| Busca local em missões/wiki/runs com 100k itens | p95 até 150 ms |
| Abertura de página de missão com timeline e evidência | p95 até 300 ms |
| Append de evento de auditoria | mediana até 10 ms |
| Memória idle da shell desktop futura | até 120 MB |
| Memória idle do runtime local Hermes/Atlas por perfil ativo | até 250 MB |
| Stack local completa single-user em idle | até 500 MB |
| Hotkey para overlay visível na futura shell desktop | até 100 ms |
| Aprovação local de ação para execução | até 150 ms |
| Contexto padrão por missão ativa | alvo de 8k–20k tokens; hard cap de 40k antes de escalonar modelo |

A interpretação estratégica desses budgets é tão importante quanto os números: **ATLAS não precisa ser “mínimo” em funcionalidades; ele precisa ser mínimo em desperdício**.

## Segurança, privacidade e riscos

### Baseline

A baseline correta de segurança para o ATLAS é **least privilege + isolamento + aprovação + proveniência**.

No desktop e no plano de controle, use o modelo de **capabilities/permissions do Tauri**. O frontend não deve ter acesso automático ao IPC; acesso a comandos e sidecars precisa ser liberado por janela/webview e por permissão explícita. O próprio Tauri enquadra isso como boundary de segurança. citeturn32view8turn32view9

Para segredos locais, use **OS credential store** via `keyring`; para segredos de time e CI, use **SOPS + age**. O `keyring` resolve integração com stores nativos; o `age` permite criptografia por múltiplos destinatários; o SOPS mantém arquivos versionáveis sem plaintext no repositório. citeturn32view10turn33view0turn33view1

No modo team, use **Postgres com RLS ligado por padrão**. Isso não substitui auth de aplicação, mas cria uma segunda camada útil para dados de missão, entidades relacionais e auditoria. citeturn32view2

No runtime, trate qualquer extensão executável como superfície hostil até prova em contrário. A documentação do Open WebUI é direta: permitir que usuário crie ou importe ferramentas é praticamente equivalente a dar shell access ao servidor. A documentação do n8n também é clara ao recomendar task runners externos para produção e houve advisories recentes mostrando que usuários com permissão de editar workflows puderam executar comandos arbitrários no host em certos modos do Code node. O ATLAS deve aprender com isso e **nunca** normalizar execução arbitrária in-process de código não confiável no host principal. citeturn21view0turn23search1turn23search3turn23search5

Em execução de ferramentas, a política padrão deve ser de quatro níveis:

| Classe | Exemplos | Política padrão |
|---|---|---|
| Leitura segura | busca, leitura de wiki, leitura de CRM, leitura de arquivos em root permitido | liberado por perfil |
| Sugestão sem efeito externo | rascunho de e-mail, issue draft, resumo, proposta de atualização | liberado com preview |
| Escrita externa | enviar e-mail, alterar calendário, atualizar CRM, abrir PR, criar ticket | requer aprovação |
| Execução privilegiada | shell com write, SSH, browser autenticado crítico, acesso a segredos | perfil dedicado + sandbox + aprovação forte |

O Hermes já oferece backends de terminal como `docker`, `ssh`, `modal` e outros; isso deve ser convertido em política de risco no ATLAS, não em detalhe de configuração obscuro. Para tarefas não confiáveis, o backend default deve ser contêiner ou host remoto isolado; “local” deve ser reservado para perfis confiáveis. citeturn20view2

### Principais riscos e mitigação

| Risco | Impacto | Mitigação recomendada |
|---|---|---|
| **Deriva de escopo** para virar builder genérico, chat hub ou CRM com IA | O produto perde diferenciação e entra em mercados congestionados | Fixar os cinco objetos centrais e medir roadmap pelo loop “brief → approve → execute → audit → remember” |
| **Divergência do fork do Hermes** | Atualizações difíceis, bugs herdados, custo alto de manutenção | Manter trilha explícita de upstream sync, contract tests e PRs upstream para correções genéricas |
| **Instabilidade de base** em áreas de cron/MCP/perfis | Quebra justamente da automação contínua, que é central para pulse | Criar suíte própria de compatibilidade; o próprio Hermes teve issue pública de P1 em 2026 sobre MCP ausente em sessões de cron, o que é um bom sinal de que o hardening local é obrigatório. | citeturn35view0turn20view0 |
| **Superfície de plugins/skills/MCP** | Exfiltração, abuso de tools, supply-chain ruim | Allowlist, manifests revisados, install rights admin-only, sandbox obrigatório, perfis separados, logs completos |
| **Stack pesada demais** | Produto contradiz promessa de performance | SQLite local-first, zero Redis/NATS/K8s no v1, Tauri em vez de Electron, índice opcional e não obrigatório |
| **Wiki virar RAG confuso** | Respostas sem confiança, contradições e dados envelhecidos | Fontes brutas imutáveis, wiki Markdown canônica, lint de contradição, stale flags, origem clicável por afirmação |
| **Desktop virar atraso de roadmap** | 90 dias se perdem em packaging e engine nativa | Tratar desktop como sidecar/prova de interface no ciclo inicial; ship principal deve ser CLI/TUI + serviço local + WebUI |
| **Custos e latência de modelo** | Unit economics ruins, UX inconsistente | Routing por função: modelos baratos para trabalho mecânico, modelos fortes para revisão/arquitetura, locais para privacidade, fallback explícito |

### Questões em aberto

Há três pontos que eu trataria como abertos, não como impeditivos:

1. **Qual parte do runtime deve sair de Python primeiro**: na minha leitura, não o agent loop inteiro, mas sim o plano de controle, indexação e desktop.  
2. **Quão cedo vale empacotar desktop completo**: a resposta provável é “depois do wedge validar”, porque o risco de packaging é real.  
3. **Quão profundo será o componente CRM no v1**: se ele tentar competir com CRM completo cedo demais, atrasa o produto; se ficar só como grafo leve de relações e touchpoints, ajuda muito o cockpit.

## Roadmap e validação

### Plano de 90 dias

O objetivo do ciclo de 90 dias deve ser: **colocar um founder técnico para operar o próprio dia dentro do ATLAS**, com confiança suficiente para aprovar ações reais.

| Janela | Objetivo | Entregáveis | Critério de saída |
|---|---|---|---|
| **Primeiro mês** | Fundar a espinha dorsal | Fork do Hermes estabelecido; schema de missões/runs/pulse/wiki/entities; event log; SQLite + FTS5; WebUI inicial read-only; extensão da TUI existente; health/perf baselines | Um run real do Hermes aparece no cockpit com log, custo, evidência e ligação a missão |
| **Segundo mês** | Fechar o primeiro loop de valor | Briefing diário; mission view; wiki viva com proveniência; approvals; relation runtime leve; pulse scheduler; provider routing por política; CI cross-platform e perf gates | Davi/L2 usa o sistema diariamente para briefing, follow-up e pesquisa com pelo menos uma ação aprovada por dia |
| **Terceiro mês** | Polir e transformar em piloto | Instalação local razoável; templates de missão; fluxo de onboarding; dashboards de runs/pulse; export/import; hardening de política; design-partner pack; sidecar desktop mínimo opcional para notificações/hotkeys | 5–8 design partners conseguem usar por uma semana com taxa de retenção e feedback positivo sobre valor central |

Os **não-objetivos** do ciclo devem ser tão explícitos quanto os objetivos: nada de marketplace aberto, nada de CRM full-suite, nada de desktop nativo completo com voice stack total, nada de “visual builder universal”. O produto só deve começar a expandir depois de provar o loop núcleo.

### Dogfood e design partners

O dogfood com Davi/L2 deve acontecer em três trilhas reais, não demos artificiais:

**Founder ops.** Briefing diário, triagem de inbox, dossiê pré-reunião, follow-ups e touches em pessoas/oportunidades.  
**Research ops.** Missões de pesquisa com wiki viva, fonte imutável, contradições e open questions.  
**Repo/exec ops.** PRs, issues, roadmap, decisões e briefing de engenharia.

As métricas que importam nesse estágio são pragmáticas:

- quantas missões reais são abertas e revisitadas por semana;  
- quantos briefs viram ação aprovada;  
- quanto tempo o usuário economiza em troca de contexto;  
- quantas páginas de wiki permanecem úteis depois de uma semana;  
- quantos pulses produzem sinal útil versus ruído;  
- p95 de busca, abertura de missão e render do cockpit;  
- memória idle e cold start;  
- taxa de erro/retry e taxa de reversão de ação.

Depois do dogfood, os design partners ideais são **5–8 contas** divididas entre founders técnicos, agências de automação/AI e pequenos times produto/dev. O pitch não deve ser “plataforma de agentes”; deve ser: **“um cockpit único para lembrar, planejar, executar, auditar e acompanhar a operação da sua empresa.”** Isso conversa diretamente com a tese de human-agent teams e com a lacuna prática de maturidade apontada por McKinsey. citeturn31view1turn31view0

O critério real de validação não é NPS genérico. É este: **o usuário volta ao ATLAS para começar o dia**. Se isso acontecer, há wedge. Se ele volta só para “perguntar coisas”, o produto virou chat. Se ele volta só para “disparar automações”, o produto virou builder. O comportamento certo é: abrir o dia, entender o estado do negócio, aprovar ações, acompanhar runs e não perder contexto.

Em resumo, o caminho mais forte para o L2 ATLAS é: **Hermes por dentro, Atlas por cima, Rust no plano de controle, WebUI impecável, desktop fino quando fizer sentido, dados locais por padrão, auditoria em tudo, e foco obsessivo em missão + evidência + follow-through**. Essa combinação é tecnicamente crível, diferenciada frente ao mercado atual e suficientemente estreita para chegar a um primeiro ship útil em 90 dias.