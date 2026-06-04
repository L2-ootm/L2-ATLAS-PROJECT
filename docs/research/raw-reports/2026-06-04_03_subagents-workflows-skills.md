# Arquitetura de subagentes, workflows, skills e autoaperfeiçoamento para o L2 ATLAS

## Resumo executivo

Partindo do contexto do briefing, a melhor forma de estruturar o ATLAS não é como “um agente com muitos prompts”, mas como um sistema operacional de agentes com três camadas bem separadas: papéis duráveis com estado próprio, subagentes efêmeros para trabalho focado, e filas duráveis para trabalho que precisa sobreviver a reinícios, revisão humana e auditoria. Essa direção combina bem com o que o Hermes já oferece hoje — perfis independentes, delegação com contexto isolado, cron, MCP, skills on-demand e um quadro Kanban multiagente com persistência em SQLite — sem transformar o produto em um wrapper frágil sobre um subprocesso externo. citeturn33view3turn6view0turn21view1turn10view2

A decisão arquitetural mais importante é distinguir **workflow** de **agente**. Anthropic define workflows como caminhos pré-codificados que orquestram LLMs e ferramentas, enquanto agentes são sistemas em que o modelo decide dinamicamente como trabalhar; a mesma publicação recomenda começar pelo desenho mais simples possível e só aumentar a autonomia quando houver ganho real, porque sistemas agentic normalmente trocam previsibilidade por custo e latência. Para o ATLAS, isso implica um princípio claro: **workflow-first, agent-when-needed**. citeturn18view0turn18view1turn18view2

A proposta deste relatório é, portanto, a seguinte: o ATLAS deve usar o Hermes como núcleo de runtime e perfis; deve tratar skills como memória procedural sob demanda; deve introduzir um artefato novo e de primeira classe chamado **workflow versionado**, com schema, gates, verificações e política de risco; e deve impedir que o loop de autoaperfeiçoamento escreva diretamente em comportamento de produção. Hermes já possui self-improvement por skills e um curator que arquiva skill drift; OpenClaw já demonstra o padrão correto para mudanças governadas com o Skill Workshop, no qual o agente propõe e um humano aprova antes de alterar `SKILL.md`. citeturn8search0turn6view3turn9view3turn14search0

A consequência prática é simples: ATLAS não deve promover “autonomia máxima”; deve promover **autonomia governada**. O runtime precisa favorecer least privilege, toolsets mínimos por papel, separação explícita entre trabalho síncrono e trabalho durável, revisão em duas etapas para execução não trivial, trilha de auditoria por run, e promoção controlada de skills e workflows para packs de produção. Isso se alinha tanto às lições operacionais da Anthropic sobre sistemas multiagente quanto às recomendações da NIST e da OWASP para governança, medição, gestão contínua de risco, defesa contra prompt injection, isolamento de memória e contenção de ferramentas. citeturn18view4turn25view4turn25view0turn25view1turn25view2

## Taxonomia de agentes

### Papéis duráveis

No ATLAS, “agente” não deve ser apenas um prompt diferente. Os papéis centrais devem existir como **profiles** do Hermes, porque perfis já isolam `config.yaml`, `.env`, memória, sessões, skills, cron jobs, logs e estado de gateway. Isso dá ao produto um modelo operacional limpo: cada papel importante possui identidade, memória e ferramentas próprias, e o sistema sabe exatamente onde termina a responsabilidade de um papel e começa a de outro. O próprio Hermes já usa descrições de profile para roteamento em worker Kanban. citeturn33view3turn33view0

O **orquestrador** deve ser um profile durável e restrito. Sua função não é “fazer tudo”; sua função é decompor missão, estimar risco, escolher workflow, decidir se a execução será síncrona (`delegate_task`), durável (Kanban), ou agendada (`cronjob`), e depois julgar resultados. Quanto menos o orquestrador editar arquivo e quanto menos acesso direto ele tiver a segredos e canais externos, melhor. Anthropic relata que sistemas multiagente pioram rapidamente quando o coordenador delega demais, delega mal ou mantém loops de pesquisa excessivos; o orquestrador do ATLAS precisa ser explicitamente treinado para **delegar pouco, delegar bem e parar cedo**. citeturn18view4turn20view0

O **coder** deve ser um papel focado em workspace, com acesso a `terminal` e `file`, e quase sempre trabalhar sobre tarefas especificadas e não sobre pedidos vagos. Hermes já fornece um padrão útil no skill “Subagent Driven Development”: fresh subagent por tarefa e revisão em duas etapas, primeiro conformidade de especificação, depois qualidade de código. Essa deve ser a política-padrão do ATLAS para implementação relevante em repositórios. citeturn22view0turn20view0

O **researcher** deve operar com contexto enxuto, forte disciplina de fontes e quase nenhum poder de mutação. O desenho correto é `web` + leitura de arquivos + produção de sumários estruturados e evidência, porque o Hermes já suporta subagentes com toolsets restritos e retorno apenas de resumo final ao pai, o que evita contaminar a janela de contexto do orquestrador com tool output bruto. A Anthropic recomenda exatamente esse padrão para pesquisa complexa: subagentes especializados exploram bastante e retornam saídas condensadas para síntese. citeturn6view0turn20view0turn18view3

O **clerk** deve ser o papel mais barato e mais mecânico do sistema. Ele serve para normalizar dados, preencher CRM, reclassificar tickets, converter formatos, extrair campos, preparar artefatos, registrar touchpoints e fazer housekeeping. Em vez de raciocínio profundo, ele precisa de schemas rígidos, saídas previsíveis e forte validação. Anthropic observa que muitos problemas não precisam de agentes completos e podem ser resolvidos com workflows simples; o clerk é justamente o papel onde o ATLAS ganha confiabilidade e custo baixo ao evitar “inteligência teatral” desnecessária. citeturn18view0

O **reviewer** deve ser separado do executor. Em ATLAS, revisão não é um “modo” do mesmo agente que acabou de agir; é um papel distinto. O reviewer deve existir em pelo menos duas variantes: **spec reviewer**, que mede aderência a requisitos e escopo, e **quality reviewer**, que mede robustez, clareza, cobertura, risco e consistência com padrões do projeto. Esse desenho é coerente com o skill de Subagent Driven Development do Hermes e com o GSD, que enfatiza gates e verificação explícita. citeturn22view0turn15view2

O **security auditor** deve ser outro papel próprio, com acesso preferencialmente somente-leitura ao artefato produzido, scanners e políticas. Seu trabalho é procurar segredos inadvertidos, comandos perigosos, escopo excessivo, dependências não autorizadas, e sinais de prompt injection ou exfiltração em workflows e skills. Hermes e OWASP já convergem nisso: conteúdo externo é não confiável por padrão, memory deve ser saneada antes de persistir, e execução sensível exige aprovação e least privilege fora do LLM. citeturn25view0turn25view1turn6view1turn19view0

O **ops agent** deve ser pensado como um worker durável, não como um subagente casual. Para health checks, pulse, heartbeats, briefings, monitoração e runbooks programados, o caminho natural é `cronjob` ou um worker Kanban persistente, porque o Hermes deixa claro que jobs de cron rodam em sessões frescas, sem memória do chat atual, e que `delegate_task` é síncrono e descartado se o pai for interrompido. citeturn10view4turn20view0

O **CRM agent** deve ser um papel misto: clerk quando estiver higienizando e estruturando dados; reviewer quando estiver consolidando contexto de relacionamento; e local/private quando lidar com dados pessoais, histórico de canais, oportunidades ou anotações sensíveis. Ele não deve ter acesso livre a terminal nem navegar sem necessidade. A boa arquitetura aqui é papel estreito, schema de entrada/saída rígido e política forte de classificação de dados. As recomendações de OWASP para isolamento de memória, limites de retenção e auditoria de conteúdo persistido encaixam diretamente. citeturn25view0

O **local/private agent** não é um “tipo de tarefa”; é um **domínio de execução**. Sempre que a missão cruzar dados muito sensíveis, segredos, logs privados de canal, CRM confidencial, rascunhos estratégicos ou base documental que não possa sair da máquina, o trabalho deve migrar para um profile ou endpoint local/privado. Hermes já suporta override de `delegation.base_url`, `delegation.api_key` e `delegation.model` para endpoints OpenAI-compatíveis, inclusive locais, o que torna esse papel operacionalmente viável sem forçar uma arquitetura paralela. citeturn26view0turn26view2

### Papéis efêmeros

Os papéis acima são duráveis. Já os **subagentes efêmeros** existem por run e morrem ao final dele. O Hermes já define esse mecanismo com clareza: `delegate_task` cria filhos com conversa isolada, terminal próprio, toolsets restritos e retorno apenas do sumário final. Em ATLAS, isso deve virar uma regra simples: use profile durável para identidade e responsabilidade; use subagente efêmero para execução focal de uma etapa que não precisa sobreviver sozinha. citeturn6view0turn20view0

### Ciclo de execução

O ciclo-padrão de subagente no ATLAS deve ser: **missão → especificação → atribuição → permissões mínimas → execução → revisão → verificação → registro**. O pai nunca deve delegar uma mensagem vaga como “corrige aquilo”; o contexto precisa incluir caminhos, critérios, escopo, restrições e forma do resultado. O Hermes documenta esse problema explicitamente: subagentes começam do zero e não conhecem a conversa anterior; se o contexto for ruim, a delegação sai ruim. citeturn20view0

Depois da atribuição, o sistema deve escolher o menor toolset que resolva a tarefa. O próprio Hermes recomenda essa contenção: `["web"]` para pesquisa, `["file"]` para análise de leitura, `["terminal","file"]` para código, e só usar combinações mais amplas quando necessário. Essa política reduz custo, reduz acidentes e reduz superfície de ataque. citeturn20view0turn6view0

A saída do executor não deve ser tratada como verdade final. Para todo trabalho não trivial, o padrão do ATLAS deve ser o do Hermes “Subagent Driven Development”: primeiro um revisor de conformidade com a especificação original; depois um revisor de qualidade; depois, se necessário, um auditor de segurança; e só então promoção do artefato ao estado “done”. Essa separação é especialmente importante porque OWASP inclui excessive agency e overreliance entre riscos reais de sistemas baseados em LLM. citeturn22view0turn25view2

Se a tarefa precisa de interação humana, sobrevivência a reinício, troca de contexto entre papéis, dependências entre tarefas ou descoberta futura, o ATLAS não deve usar `delegate_task`; deve usar uma fila durável. O Kanban do Hermes já distingue bem esses casos: `delegate_task` é uma function call; Kanban é uma work queue em SQLite onde cada handoff vira uma linha auditável, com comentários como protocolo interagente, dependências e estados explícitos. citeturn21view1turn21view2turn21view3

## Política de roteamento de modelos

O Hermes já oferece a base certa para roteamento fino: há **slot principal** para o modelo que “pensa” com o usuário, **slots auxiliares** para tarefas menores como compressão, visão e sumarização, override específico para subagentes via `delegation.provider` e `delegation.model`, roteamento por provider via OpenRouter e cadeias de fallback que também funcionam em subagentes e cron. Isso é suficiente para o ATLAS implementar roteamento sem reescrever a fundação do runtime. citeturn10view1turn10view0turn26view0turn28view0

A política recomendada para o ATLAS é usar três famílias de execução: **barato/fraco**, **forte**, e **local/privado**. A regra de entrada não deve ser “qual modelo o usuário prefere”, e sim “qual o menor nível de capacidade que atende risco, latência, privacidade e contexto”. Anthropic recomenda esse minimalismo de complexidade por padrão; o Hermes já permite que o modelo principal fique em um tier e os subagentes em outro. citeturn18view0turn26view0

O tier **barato/fraco** é para trabalho mecânico, reversível e de baixa ambiguidade: extração estruturada, classificação, reescrita de campos, normalização de CRM, triagem de tarefas, sumarização de logs, geração de rascunhos internos, inspeções simples, preenchimento de schemas, housekeeping e lint operacional. Ele também é adequado quando há alto paralelismo e pouco risco por item. Em Hermes, isso casa bem com subagentes estreitos, `execute_code` para cadeias mecânicas de muitas tool calls, e modelos auxiliares dedicados para compressão, web extract e skill search. citeturn20view0turn10view1turn28view0

O tier **forte** é para arquitetura, revisão, pesquisa difícil, síntese com múltiplas fontes, decisões de produto, mudanças multiarquivo, outputs externos e qualquer tarefa em que erro seja caro, difícil de reverter ou reputacionalmente sensível. Também é o tier correto para o orquestrador e para reviewers de alta criticidade. Anthropic enfatiza que workflows e agentes devem ganhar complexidade só quando houver justificativa; em ATLAS isso significa reservar modelos fortes para pontos de alto leverage, e não dissipá-los em backoffice mecânico. citeturn18view0turn18view1

O tier **local/privado** deve ser obrigatório quando o dado não puder sair do perímetro. Isso inclui: segredos, documentos internos sensíveis, dados pessoais, anotações privadas, histórico de canais internos, CRM confidencial, e qualquer missão com política “no cloud”. Hermes suporta exatamente essa saída operacional por meio de endpoint direto em `base_url`, inclusive local, mantendo o mesmo contrato de ferramentas e delegação. O papel local/private do ATLAS deve ser tratado como uma fronteira de compliance, não como “opção exótica”. citeturn26view0turn26view2turn28view0

Os critérios decididores devem ser explícitos. **Custo**: se o trabalho é altamente paralelo e homogêneo, prefira barato/fraco. **Latência**: se o valor está em responder rápido e corrigir depois, barato/fraco ou local leve. **Privacidade**: se a classificação de dados proíbe saída, local/privado. **Risco**: se há impacto em código, segurança, finanças, reputação ou comunicação externa, forte. **Tamanho de contexto**: se o input bruto ameaça o budget do modelo, quebre via subagentes, compressão e artifacts, não apenas via modelo maior. Anthropic destaca que subagentes são uma maneira direta de contornar limites de contexto, e o Hermes já separa prompt estável, contexto e memória para favorecer caching e clareza semântica. citeturn18view3turn17view0

Para modelos locais menores, a política de contexto do ATLAS precisa ser agressiva. O GSD documenta um perfil mínimo que reduz overhead de prompt cold-start de aproximadamente 12 mil para cerca de 700 tokens, e o Hermes oferece profiles sem skills bundladas, progressive disclosure de skills e limites configuráveis de leitura de arquivo. Em outras palavras: **não compense um catálogo inchado com um contexto maior; reduza o catálogo**. citeturn15view3turn31view0turn19view0

Também convém impor uma regra de roteamento por profundidade. Hermes já mostra que custo cresce multiplicativamente com `max_concurrent_children` e `max_spawn_depth`; um desenho 3×3×3 pode chegar a 27 folhas paralelas. O ATLAS deve começar com profundidade plana para quase tudo, permitir um segundo nível apenas em workflows aprovados, e bloquear árvores profundas fora de pesquisa e avaliação controlada. citeturn26view0turn26view2

## Esquema de workflows e skills

A distinção que o ATLAS precisa tornar explícita é esta: **skill não é workflow**. No próprio Hermes, skill é memória procedural — “como fazer” — enquanto memory é conhecimento factual — “o que é”. Já Anthropic diferencia workflows de agentes pela origem do controle: workflows seguem caminhos pré-definidos; agentes decidem dinamicamente como proceder. O ATLAS deve preservar essas três coisas como artefatos distintos: facts, skills e workflows. citeturn13view0turn18view0

Em termos práticos, o ATLAS deve adotar pelo menos cinco artefatos de primeira classe: **profile**, **skill**, **workflow**, **pack** e **run record**. O profile representa identidade, padrão de ferramentas, modelo e memória durável. O skill representa procedimento reusável com frontmatter, referências e verificação. O workflow representa uma máquina de execução tipada: etapas, papéis, gates, contratos de entrada e saída, política de custo e risco. O pack é uma distribuição versionada desses objetos. O run record é a fotografia imutável da execução real. Essa separação torna o sistema mais auditável, mais testável e menos dependente de “prompt implícito”. A própria documentação do Hermes e do OpenClaw já aponta para frontmatter estruturado, metadata de runtime, requisitos de ambiente e organização versionável. citeturn13view1turn3view4turn9view4turn31view0

O schema recomendado para skills no ATLAS deve estender, e não substituir, o que Hermes e OpenClaw já fazem bem. Ambos já trabalham com `name`, `description`, `version` e blocos de metadata; OpenClaw adiciona `requires.env`, `requires.bins`, `primaryEnv` e declarações verificáveis de runtime, enquanto o Hermes já suporta tags, categoria, config settings, referências e progressive disclosure. Portanto, o caminho correto é um frontmatter compatível, com um namespace adicional `metadata.atlas`. citeturn13view1turn3view4turn31view0

Exemplo sintético de frontmatter recomendado para um skill do ATLAS:

```yaml
---
name: crm-touchpoint-normalizer
description: Use quando for preciso normalizar touchpoints de CRM em schema canônico.
version: 1.0.0
author: L2 Systems
license: MIT
metadata:
  hermes:
    tags: [crm, normalization, clerk]
    category: business-ops
  atlas:
    class: skill
    pack: business-ops
    autonomy_level: supervised
    risk_level: low
    public_safe: false
    role_hints: [clerk, crm-agent]
    data_scopes: [crm_internal, pii]
    model_policy: cheap
    review_policy: optional
    required_tools: [file]
    required_secrets: []
    input_schema: schemas/crm-touchpoint-input.json
    output_schema: schemas/crm-touchpoint-output.json
    verifiers:
      - type: json_schema
        ref: schemas/crm-touchpoint-output.json
    provenance:
      source_type: internal
      source_ref: l2-agent-skills
      imported_from: null
---
```

Para **workflows**, o ATLAS deve introduzir um schema próprio, porque um workflow precisa guardar algo que `SKILL.md` não guarda bem: grafo de etapas, papéis, gates, retries, budgets, aprovadores e critérios de promoção. Em outras palavras, skill continua sendo documentação executável; workflow passa a ser **contrato operacional**. Isso está alinhado com o funcionamento real do GSD, que trabalha com desenho de fase, critérios de aceitação, AI-SPEC, avaliação e verificação, e com o skill do Hermes adaptado do GSD para execução com revisão em duas etapas. citeturn15view1turn15view2turn22view0

Exemplo sintético de workflow do ATLAS:

```yaml
kind: workflow
name: implement-feature-with-review
version: 1.0.0
pack: developer-operator
public_safe: true
autonomy_level: supervised
risk_level: medium

entrypoint:
  role: orchestrator
  model_policy: strong

budgets:
  max_parallel_children: 3
  max_spawn_depth: 1
  max_total_tokens: 250000
  max_cost_usd: 8.00
  deadline_minutes: 45

inputs:
  schema: schemas/feature-request.json

steps:
  - id: specify
    role: orchestrator
    action: create_spec
    output: spec.md

  - id: implement
    role: coder
    action: delegate_task
    toolsets: [terminal, file]
    requires: [specify]
    output: diff.patch

  - id: spec_review
    role: reviewer
    action: review_spec_compliance
    toolsets: [file]
    requires: [implement]

  - id: quality_review
    role: reviewer
    action: review_quality
    toolsets: [file]
    requires: [spec_review]

  - id: security_review
    role: security-auditor
    action: review_security
    toolsets: [file]
    requires: [quality_review]

gates:
  - on: spec_review
    pass: next
    fail: send_back_to implement
  - on: quality_review
    pass: next
    fail: send_back_to implement
  - on: security_review
    pass: complete
    fail: block

outputs:
  schema: schemas/workflow-result.json

audit:
  persist_prompt_hash: true
  persist_tool_calls: true
  persist_artifact_hashes: true
  retain_intermediate_artifacts: true
```

Há um segundo ganho importante nesse desenho: **controle de prompt e contexto**. O Hermes usa skills com progressive disclosure e só carrega o conteúdo completo quando necessário; além disso, uma lista de skills custa muito menos que o conteúdo integral de todas elas. Já o OpenClaw documenta que skills elegíveis viram um bloco XML compacto no system prompt e que o custo cresce por skill visível. O ATLAS deve usar isso como disciplina de produto: packs pequenos, descrições curtas, referências externas, e nada de “catálogo universal” exposto em todo run. citeturn31view0turn9view2

O campo **`public_safe`** deve ser obrigatório em skills e workflows. A semântica recomendada é simples: `true` significa que o artefato pode ser distribuído em repositórios públicos, demos públicas e packs compartilháveis sem exposição de dados internos; `false` significa que o artefato pressupõe contexto, segredos, padrões operacionais ou políticas que devem permanecer privados. Isso é especialmente relevante porque Hermes já suporta profile distributions e taps de skills, e OpenClaw/ClawHub já trabalham com registries públicos e trusted/community sources. O `public_safe` do ATLAS deve virar um filtro duro de publicação e promoção. citeturn3view6turn32view2turn27view0

## Estratégia de importação dos ativos existentes

Como parte dos ativos L2 descritos no briefing parece ser interna ou pouco documentada publicamente, a estratégia correta aqui é **importação governada por classes de origem**, e não “copiar tudo para o novo runtime”. O ATLAS deve aproveitar o máximo possível do que já existe no Hermes e dos formatos SKILL.md já consolidados, mas tratar todo legado como fonte a ser normalizada, testada e rotulada por risco.

A classe mais simples é **Hermes nativo → ATLAS**. Skills do Hermes, profiles, cron jobs, MCP configs e plugins já estão no ecossistema certo. O ideal é manter compatibilidade total e apenas acrescentar metadata ATLAS, manifests de pack, budgets e políticas de review. Isso também vale para distribuições de profile: o Hermes já define profile distributions como um repositório Git que empacota personalidade, skills, cron, MCP e config sem misturar API keys, memórias e sessões do operador final. Para o ATLAS, isso é a base natural de packs distribuíveis. citeturn3view6turn10view5

A segunda classe é **OpenClaw → Hermes/ATLAS**. Aqui vale explorar o que já existe: o Hermes já possui `hermes claw migrate`, que importa elementos de persona, memória, instruções de workspace, skills e parte da configuração OpenClaw, com preview completo antes de aplicar, backup pré-migração e relatório do que ficou pendente. O ATLAS deve reutilizar esse caminho como baseline de ingestão, mas sem promover automaticamente para produção. Todo skill vindo de OpenClaw deve entrar em **quarentena de importação**, com provenance, hash, fonte, licença, dependências, bins, env vars, nível de confiança e diff contra o upstream. citeturn24view0turn24view1

Para skills OpenClaw e artefatos ClawHub, o ponto crítico é preservar **metadados de runtime e segurança**. ClawHub explicita que skills declaram requisitos de ambiente e que sua análise de segurança verifica se a declaração bate com o comportamento real; OpenClaw, por sua vez, aplica gating, allowlists e injeção de env apenas no run elegível. O importador do ATLAS deve mapear automaticamente `requires.env`, `requires.bins`, `primaryEnv` e similares para o schema `metadata.atlas`, e falhar fechando quando a skill exigir permissões amplas demais ou pouco declaradas. citeturn9view4turn27view0turn9view1

A terceira classe é **GSD/OpenClaw-GSD → workflows do ATLAS**. GSD não deve ser importado como um monte de skills soltas. O design dele é explicitamente spec-first, com AI-SPEC, especialistas paralelos, critérios de avaliação, quality gates e verificação posterior. Isso é workflow, não skill atômica. A importação correta é transformar comandos e runbooks GSD em **workflow packs** do ATLAS, preservando fases, gates, critérios de aceitação, fluxo de paralelismo, documentação de decisão e revisão remediadora. citeturn15view1turn15view2turn15view3

A quarta classe é **ativos L2 próprios → ATLAS draft lane**. Para `l2-agent-skills`, `L2 MIND`, `L2-BOT`, `L2-Atlas`, `L2-NODEX`, `L2-KNOWLEDGE-ROUTER` e padrões de Command Center/Personal Data KB mencionados no briefing, a recomendação é uniformizar tudo em uma esteira com quatro destinos possíveis: **skill**, **workflow**, **plugin/MCP adapter** ou **policy pack**. Em especial, `L2 MIND` parece fazer mais sentido como biblioteca de decisão e revisão, não como executor autônomo; `L2-BOT` parece mais adequado como adapter de gateway/runbook; e o velho `L2-Atlas` deve influenciar conventions de missão, heartbeat/pulse, políticas de execução segura e formato de logs, não virar uma cópia estrutural do produto novo.

A distribuição final deve ocorrer em **packs**. Minha recomendação é começar com cinco: **Core ATLAS**, contendo orquestração, revisão, auditoria e utilidades-base; **Developer Operator**, com workflows de planejamento, implementação, review e repo ops; **L2 Systems**, com runbooks e convenções internas; **Business Ops**, com CRM, touchpoints, briefings, pipeline e acompanhamento; e **Personal/Private**, excluído de qualquer publicação pública, com workflows e skills que tocam dados pessoais e contextos privados. Como o Hermes já suporta taps, trust levels e profile distributions, o ATLAS pode usar esses mecanismos como transporte e acrescentar sua própria camada de validação e promoção. citeturn32view2turn31view2turn3view6

## Governança de autoaperfeiçoamento

O Hermes já demonstra que autoaperfeiçoamento é viável no runtime: há loop de learning, nudges para memória e skill, `skill_manage` para criação/edição, e um curator que move skills por estados `active → stale → archived`, sem auto-deletar. Mas esse comportamento, do jeito que está, é ótimo para uso pessoal e rápido; para um cockpit sério como o ATLAS, ele precisa de **governança de promoção**. citeturn8search0turn16view1turn6view3

A regra mais importante deve ser: **agentes podem escrever em draft; não podem escrever direto em produção**. O melhor padrão observável hoje é o OpenClaw Skill Workshop, em que o agente gera proposta e o humano aprova antes de modificar arquivos ativos. O ATLAS deve levar esse princípio para além de skills e aplicá-lo também a workflows, runbooks, políticas de roteamento e packs. Em termos de UX e operação, isso significa uma fila de propostas com diff, motivação, impacto esperado, permissões requeridas, testes, score de risco e proveniência. citeturn9view3turn14search0

A governança pode ser organizada nos quatro verbos do NIST AI RMF: **Govern**, **Map**, **Measure**, **Manage**. Govern: definir quem pode propor, revisar, aprovar e promover. Map: classificar o tipo da mudança, escopo, dados afetados, ferramentas requeridas e risco. Measure: medir qualidade, custo, sucesso, regressão, hallucinatory rate, falhas de segurança, override humano e adoção. Manage: promover, reverter, arquivar ou bloquear. A NIST enfatiza que essas funções são contínuas ao longo do ciclo de vida e não um checklist pontual. citeturn25view4turn25view3

Nem todo tipo de persistência precisa do mesmo rigor. **Memory factual** pode aceitar automatização maior, desde que passe por sanitização, TTL, limites de tamanho, isolamento por usuário/sessão e auditoria de conteúdo sensível — exatamente como recomenda a OWASP para memory & context security. **Skill draft** pode ser criado automaticamente, mas só em lane de rascunho. **Workflow** já merece revisão humana quase sempre. **Política de segurança, permissões, segredos e roteamento de produção** nunca deve ser auto-promovida. citeturn25view0turn19view0

Também é importante separar **curadoria** de **promoção**. A curadoria lida com duplicação, staleness, arquivamento e limpeza de catálogo; o curator do Hermes já faz isso para skills agent-authored e nunca auto-apaga. A promoção, no entanto, precisa de testes, changelog, versionamento de pack, assinatura e rollout progressivo. Em ATLAS, um artefato pode ser “útil o suficiente para guardar” sem ainda ser “seguro o bastante para virar padrão de produção”. citeturn6view3

Uma boa política de promoção seria exigir, no mínimo: descrição clara do problema resolvido; schema de entrada e saída; toolsets e segredos declarados; exemplos de uso; verificador automático; diff legível; score de risco; evidência de uso ou necessidade; e, para workflows, pelo menos um replay ou dry-run aprovado. Para third-party skills, o ATLAS deve aproveitar os conceitos de trust level e security scanning já documentados no Hermes skills hub: `builtin`, `official`, `trusted`, `community`, com `dangerous` não promovível por override simples. citeturn32view1turn32view2

## Requisitos de interface e operação

O cockpit do ATLAS deve fazer uma distinção visual e operacional entre **run efêmero**, **fila durável** e **automação agendada**. Isso não é cosmético; é uma fronteira de modelo mental. O Hermes já estabelece que `delegate_task` é síncrono e volátil, Kanban é durável e visível para múltiplos papéis, e cron roda em fresh sessions separadas do chat atual. A interface do ATLAS deve materializar essa diferença desde o topo da tela. citeturn20view0turn21view1turn10view4

A primeira superfície obrigatória é o **run graph**. Cada missão deve mostrar árvore de orquestração, incluindo pai, filhos, profundidade, papel, modelo, provider, toolsets, custo, tempo, artifacts e veredictos de review. O Hermes já mostra que subagentes têm contexto isolado e resumem de volta; o ATLAS precisa mostrar esse isolamento ao operador, para que ele saiba o que realmente entrou em contexto e o que ficou encapsulado. citeturn6view0turn20view0

A segunda superfície obrigatória é o **board de trabalho**. A implementação mais pragmática é inspirar-se diretamente no Kanban do Hermes: estados `triage`, `todo`, `ready`, `running`, `blocked`, `done`, `archived`, dependências parent→child, comentários como protocolo interagente, e workspaces explícitos por tarefa. O valor aqui é menos “gestão visual” e mais auditabilidade operacional: trabalho que cruza agentes e humanos precisa de linha do tempo, ownership e retomada. citeturn21view0turn21view1

A terceira superfície é o **centro de aprovações**. Hermeticamente, ATLAS precisa unificar: comandos perigosos, execuções host, alteração de skills/workflows, instalação de artefatos third-party, leitura de diretórios sensíveis, uso de segredos, publicação externa e promotion de pack. Hermes já possui prompt de aprovação para comandos perigosos; OpenClaw mostra um modelo maduro em que política efetiva é o resultado mais estrito entre policy, allowlist e aprovação local. Esse é o comportamento certo para o ATLAS. citeturn6view1turn30view0

A quarta superfície é o **registro de skills e workflows**. O operador precisa ver: schema, frontmatter, required tools, required secrets, trust level, provenance, links para upstream, hash, changelog, quarentena, diff da proposta e status de revisão. O Hermes já mantém `quarantine/`, `audit.log` e trust levels para skills hub; ClawHub já trabalha com metadata de runtime e análise de segurança. O ATLAS deve trazer essa semântica para sua própria registry UI. citeturn32view0turn32view2turn27view0

A quinta superfície é o **painel de orçamento**. O Hermes já expõe analytics de uso de modelos com ranking por tokens, custo e badges de capacidade. O ATLAS deve estender isso para visão operacional: custo por papel, custo por missão, custo por workflow, custo desperdiçado com retries, taxa de fallback, latência até primeiro tool call, latência até primeiro token e orçamento remanescente por run. Sem esse painel, o sistema inevitavelmente degrada para “multiagente bonito e caro”. citeturn10view1turn28view0

Na CLI/TUI, a prioridade deve ser velocidade e legibilidade. A interface textual do ATLAS deve mostrar papel ativo, classificação de risco, modelo corrente, policy de ferramentas, se o run está em modo síncrono ou durável, e atalhos instantâneos para aprovar, bloquear, reenfileirar, promover ou arquivar. O objetivo não é reproduzir todo o WebUI; é dar ao operador um cockpit de baixa latência que respeite a filosofia de “software sério”, ao mesmo tempo em que o WebUI oferece board, diffs, histórico e analytics.

## Riscos de segurança e plano de MVP

### Riscos prioritários

O primeiro risco é **runaway delegation**. Anthropic relata explicitamente que seus primeiros agentes chegaram a abrir 50 subagentes para consultas simples, a procurar infinitamente por fontes inexistentes e a se distrair com atualizações excessivas; Hermes, por sua vez, documenta que profundidade e concorrência fazem o custo crescer multiplicativamente. Em ATLAS, mitigação significa caps duros por workflow, profundidade 1 por padrão, budgets por run e um orquestrador treinado para parar. citeturn18view4turn26view0

O segundo risco é **prompt injection e contaminação de contexto/memória**. OWASP recomenda tratar todo dado externo como não confiável — usuário, documentos, emails, páginas web, APIs —, usar delimitação clara entre instrução e dado, filtrar padrões de injeção e validar o que entra em memória. O Hermes já faz varredura de context files para padrões de prompt injection e limita retornos de leitura de arquivo para evitar inundação de contexto. O ATLAS deve ampliar isso para ingestão de skills, respostas de pesquisa, memória persistida e anotações de CRM. citeturn25view1turn25view0turn17view0turn19view0

O terceiro risco é **tool misuse e privilege escalation**. OWASP lista excessive agency, insecure plugin design e insecure output handling entre riscos centrais. OpenClaw demonstra uma prática operacional forte: policy efetiva mais estrita, allowlists por agente, aprovação local no host e rejeição fail-closed quando há mismatch. O ATLAS deve adotar exatamente essa filosofia: capabilities mínimas por papel, comandos allowlisted quando possível, dois níveis de gate para execuções perigosas e nenhuma confiança em controle “só por prompt”. citeturn25view2turn25view0turn30view0

O quarto risco é **supply chain e skill drift**. Skills de comunidade, plugins de terceiros e workflows herdados acumulam dependências, permissões implícitas e drift de documentação. Hermes já introduz trust levels, scanner de segurança no install, quarentena e rechecagem de drift upstream; ClawHub já faz análise de segurança sobre o que a skill declara precisar para rodar. O ATLAS não deve ter instalação “livre” em produção: tudo de fora entra em staging, com provenance e revalidação periódica. citeturn32view1turn32view2turn27view0

O quinto risco é **overreliance humana**. A OWASP também chama atenção para isso: se o operador passa a confiar que “o reviewer viu, então está certo”, o sistema se torna burocrático e inseguro ao mesmo tempo. Por isso o ATLAS precisa registrar veredicto, confiança, evidência, artefatos inspecionados e quem aprovou o quê. Revisão sem audit trail não reduz risco; apenas o desloca. citeturn25view2turn25view4

### Plano de MVP

O **primeiro estágio** do MVP deve focar no núcleo governado de orquestração: roles como profiles do Hermes, `delegation.provider/model` configurados por papel, logs de run com parent/child IDs, toolsets mínimos e uma camada ATLAS de metadata para skills e workflows. Já aqui vale bloquear profundidade > 1 por padrão e separar claramente execuções síncronas de tarefas duráveis. citeturn33view3turn26view0turn20view0

O **segundo estágio** deve introduzir o **engine de workflow**. Isso inclui parser do schema de workflow, gates de spec/quality/security, artifacts versionados, board durável inspirado no Kanban do Hermes e telas de aprovação. A meta não é “mais autonomia”; é **reprodutibilidade operacional**. Se o mesmo workflow não puder ser reexecutado, auditado e comparado entre versões, ele ainda não deveria estar em produção. citeturn21view1turn22view0

O **terceiro estágio** deve atacar a **importação governada**. Primeiro Hermes nativo, depois importação OpenClaw via baseline de migração existente, depois workflows GSD como packs, e só então os ativos L2 internos. Toda importação deve passar por quarentena, policy mapping, teste de schema, diff review e classificação em `public_safe`/`private_only`. Nesse estágio também deve nascer o registry UI. citeturn24view0turn24view1turn15view1turn32view0

O **quarto estágio** deve habilitar o **autoaperfeiçoamento seguro**: proposal queue, lanes draft/staging/prod, eval harness, curator ATLAS, métricas de promoção e rollback por pack. Hermes já prova a viabilidade do loop de aprendizado e do curator; o ATLAS precisa adicionar gates de promoção e regras de não autoescrita em produção. citeturn16view1turn6view3turn9view3

O que **não** deve entrar no MVP é igualmente importante: árvores profundas de agentes por padrão, instalação direta de community skills em packs produtivos, auto-promoção de workflow, acesso amplo de terminal para todos os papéis, e misturar CRM/PII com research web sem classificação explícita. Se o ATLAS resistir a essas tentações no começo, ele terá uma base muito mais estável para crescer sem virar uma colcha de retalhos agentic. citeturn18view2turn25view0turn25view2

Em suma, a forma mais sólida de construir o ATLAS a partir do Hermes é esta: **profiles duráveis para papéis, subagentes efêmeros para foco, board durável para coordenação, workflows tipados para execução, skills como memória procedural on-demand, e autoaperfeiçoamento restrito a uma esteira de proposta, teste, revisão e promoção**. Isso preserva o que o Hermes já faz bem, aproveita lições de GSD e OpenClaw, e coloca o produto numa trajetória mais próxima de um verdadeiro cockpit operacional do que de um mero chatbot com ferramentas. citeturn33view3turn6view0turn3view6turn15view3turn9view3