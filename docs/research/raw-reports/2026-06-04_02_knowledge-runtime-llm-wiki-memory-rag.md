# Arquitetura do Knowledge Runtime do L2 ATLAS

## Resumo executivo

O ATLAS não deve ser projetado como um sistema de **RAG-only** que apenas busca chunks e monta respostas na hora. Para o caso de uso descrito no brief — operador/OS de empresa, memória persistente, auditoria, decisões, CRM, missões e monitoramento — o núcleo precisa ser um **runtime de conhecimento em camadas**: **fontes brutas imutáveis**, **registro operacional consultável**, **wiki Markdown mantida pelo agente** e **motores de recall** usados de forma seletiva. O paper original de RAG já apontava que atualização de conhecimento e proveniência continuam difíceis quando o sistema depende apenas de memória não paramétrica recuperada em tempo de inferência; trabalhos posteriores sobre MemGPT e Generative Agents mostram por que agentes persistentes precisam de memória hierárquica, reflexão e síntese acumulativa; e o STORM mostra que artefatos no estilo Wikipedia melhoram organização e cobertura em comparação com pipelines puramente orientados por recuperação. citeturn12view0turn13view0turn13view1turn12view3

Minha recomendação central é esta: **o “source of truth” humano do ATLAS deve ser uma wiki Markdown versionável; o “source of truth” operacional deve ser um SQLite em WAL com FTS5, registros de claims e índices; e o recall semântico deve ser auxiliar, não canônico**. Isso preserva o que já funciona no Hermes — sessões duráveis em SQLite, FTS5, plugins de memória, plugins de contexto, API de sessões, gateway de mensagens e cron — sem transformar o produto num dashboard pesado ou numa colagem de serviços frágeis. citeturn32view0turn16view0turn17search0turn5view7turn5view3

Em termos de decisão de stack, o melhor MVP para o brief é: **Markdown + SQLite FTS5/WAL + hashing de conteúdo + embeddings locais opcionais + citações/locators fortes + jobs de ingest/query/lint rodando sobre o runtime do Hermes**. Eu **não** começaria com Postgres/pgvector como núcleo local, e **não** começaria com graph DB como backbone da wiki; ambos são úteis depois, mas cedo demais aumentam custo operacional, superfície de falha e consumo de memória sem resolver o problema primário, que é transformar fontes heterogêneas em conhecimento mantido, auditável e barato de carregar em contexto. citeturn10view1turn10view0turn10view4turn10view5turn10view3

## Arquitetura de conhecimento

A diferença prática entre **RAG-only** e uma **LLM Wiki persistente** é simples: no RAG-only, o conhecimento “vive” principalmente no corpus bruto e nos índices; a cada pergunta, o sistema tenta recuperar trechos relevantes e sintetizar uma resposta temporária. Numa LLM Wiki persistente, o sistema também mantém um **artefato compilado de segunda ordem**: páginas de entidade, conceito, decisão, missão, comparação, workflow e fonte, todas com proveniência, status, confiança, contradições e revisão. Em outras palavras, o RAG resolve “o que devo puxar agora?”, enquanto a wiki resolve “o que a organização já aprendeu e quer preservar como conhecimento reutilizável?”. citeturn12view0turn13view0turn13view1turn12view3

Para o ATLAS, eu estruturaria o runtime em cinco planos que cooperam:

1. **Plano de captura**: recebe arquivos, URLs, repositórios, PDFs, chats, e-mails, registros de CRM, transcrições, imagens e outros ativos do brief, e os transforma em snapshots imutáveis.
2. **Plano de compilação**: extrai texto, entidades, claims, decisões, tarefas, datas, relações e resumos; resolve duplicatas; detecta possíveis contradições; e propõe patches na wiki.
3. **Plano da wiki**: mantém páginas Markdown legíveis por humanos e agentes, com frontmatter previsível e links internos estáveis.
4. **Plano de recall**: combina índice lexical, busca de sessão, embeddings e leitura seletiva de páginas/fontes brutas para responder consultas com o menor custo contextual possível.
5. **Plano de governança**: registra mudanças, drift, lints, permissões, sensibilidade, redactions, aprovações e trilha de auditoria. citeturn32view0turn16view0turn17search0turn31search0

No Hermes, isso encaixa melhor como **uma composição interna**, não como um app externo que “chama Hermes”. A forma mais alinhada com o brief é: **um Memory Provider Plugin do Hermes para recall cross-session**, **um Context Engine Plugin para política de seleção/compactação de contexto**, **jobs/cron para ingestões e lints**, e **superfícies de UI consumindo a API de sessões/jobs**. O próprio Hermes já separa plugin de memória e plugin de contexto, persiste sessões em SQLite/FTS5, expõe REST para sessões/jobs e usa o gateway para plataformas e cron; portanto, o caminho com menor atrito é estender essas superfícies. citeturn16view0turn17search0turn5view7turn5view3turn29search7

Também é importante **não confundir memória com wiki**. A memória curta/persistente do agente serve para preferências, contexto de usuário, fatos operacionais pequenos e continuidade de sessão; a wiki serve para conhecimento composto e auditável. O Hermes já trata memória embutida (`MEMORY.md`, `USER.md`) como uma camada pequena e curada, e só permite **um** provider externo ativo por vez; isso é mais um motivo para o ATLAS internalizar diferentes modos de conhecimento sob um mesmo runtime, em vez de depender de múltiplos “backends de memória” desconectados. citeturn5view0turn5view6turn29search7

Uma arquitetura de referência fica assim:

```text
Hermes Runtime
├─ Sessions / Gateway / Cron / Delegation / API
├─ ATLAS Memory Provider
├─ ATLAS Context Engine
└─ ATLAS Knowledge Runtime
   ├─ raw/        # blobs imutáveis + manifests + extracts
   ├─ wiki/       # páginas Markdown canônicas
   ├─ state/      # atlas.db, caches, embeddings, lint state
   ├─ inbox/      # itens aguardando ingestão/review
   └─ quarantine/ # conteúdo suspeito, corrompido ou sensível
```

Esse desenho preserva a filosofia do projeto: software sério, previsível, leve e auditável, com a maior parte do valor em arquivos e SQLite locais, e não em uma pilha distribuída pesada. O precedente técnico dentro do Hermes é forte: sessões já rodam em SQLite com WAL, FTS5, trigram, lineage e concorrência controlada por retries curtos. citeturn32view0

## Desenho de pastas, esquema e modelo de dados

A estrutura de diretórios que eu recomendo para o runtime de conhecimento é esta:

```text
atlas-knowledge/
├─ raw/
│  ├─ blobs/
│  │  └─ sha256/aa/bb/<full-hash>
│  ├─ manifests/
│  │  └─ <source_id>.json
│  ├─ revisions/
│  │  └─ <revision_id>/
│  │     ├─ metadata.json
│  │     ├─ extracted.md
│  │     ├─ segments.jsonl
│  │     ├─ entities.json
│  │     └─ attachments/
│  └─ imports/
├─ wiki/
│  ├─ SCHEMA.md
│  ├─ index.md
│  ├─ log.md
│  ├─ entities/
│  │  ├─ people/
│  │  ├─ orgs/
│  │  ├─ products/
│  │  └─ places/
│  ├─ concepts/
│  ├─ sources/
│  ├─ missions/
│  ├─ decisions/
│  ├─ workflows/
│  ├─ comparisons/
│  └─ queries/
├─ state/
│  ├─ atlas.db
│  ├─ caches/
│  ├─ embeddings/
│  └─ jobs/
├─ inbox/
└─ quarantine/
```

O princípio é: **o bruto é imutável; o derivado é reproduzível; o wiki é versionável; o banco é operacional**. A ideia de armazenamento por hash de conteúdo é uma boa escolha aqui porque permite deduplicação, auditoria e referência estável a blobs; o modelo de objetos do Git é a referência clássica de “content-addressable filesystem”. Do lado operacional, o uso de SQLite/WAL/FTS5 segue um padrão já comprovado no próprio Hermes para durabilidade, concorrência leve e recuperação local. citeturn22view0turn32view0

### Camada de fontes brutas

Cada item de entrada deve virar um **`source_id` estável** e um ou mais **`revision_id`**. O `source_id` representa o “assunto observado” — por exemplo, um repositório, uma thread de e-mails, um PDF, uma URL, uma conversa Hermes, uma oportunidade do CRM. O `revision_id` representa o snapshot específico que o ATLAS viu naquele momento. Isso evita sobrescrever o passado e facilita drift detection. Para fontes mutáveis da web, guarde também `etag`, `last_modified`, `canonical_url`, hash do corpo e data da captura. Para repositórios, guarde `repo_url`, `commit_sha`, `path` e, quando necessário, locators de linha. Para áudio/vídeo/transcrições, use `timestamp ranges` como locator. Para chats Hermes, referencie `session_id` e message IDs do `state.db`. citeturn32view0turn18view2

Eu manteria dois contratos rigorosos nessa camada. Primeiro: **o blob original nunca é alterado**; OCR, transcrição, extração de texto, captions de visão e parsing vivem como derivados ao lado, não em cima do original. Segundo: **todo derivado deve apontar para a revisão de origem**, com `parser_version`, `extractor_version` e hash do texto extraído, para que o runtime saiba quando uma melhoria do parser exige reprocessamento. Isso é especialmente importante para PDFs, imagens e transcrições, onde a fonte binária e a leitura textual nem sempre coincidem. citeturn22view0turn12view3

### Camada da wiki

A wiki é o artefato canônico “legível”. Ela deve conter, no mínimo, estes tipos de página do brief:

| Tipo de página | Função |
|---|---|
| `entity/*` | Pessoas, organizações, produtos, lugares, clientes, parceiros |
| `concept/*` | Conceitos, teses, frameworks, definições |
| `source/*` | Resumo estrutural de fontes importantes |
| `mission/*` | Objetivos, estado, contexto, bloqueios e próximos passos |
| `decision/*` | Decisões tomadas, razões, opções rejeitadas, impacto |
| `workflow/*` | Procedimentos operacionais reutilizáveis |
| `comparison/*` | Comparativos entre opções, stacks, vendors, estratégias |
| `query/*` | Respostas compostas valiosas que merecem reaproveitamento |

O frontmatter precisa ser previsível o suficiente para máquinas, mas curto o bastante para humanos. Um contrato base bom para quase todas as páginas é:

```yaml
---
id: ent_org_acme
type: entity/org
title: Acme
status: reviewed
confidence: medium
sensitivity: internal
owners: [atlas]
aliases: ["ACME Inc.", "Acme Ltd."]
source_refs: [src_web_acme_home, src_mail_acme_intro]
entity_refs: [ent_person_jane_doe]
tags: [crm, partner]
created_at: 2026-06-04
updated_at: 2026-06-04
last_verified_at: 2026-06-04
stale_after_days: 30
contradiction_state: clean
---
```

Eu recomendo que o **corpo** da página siga headings estáveis, por exemplo: `Resumo`, `Fatos principais`, `Evidência`, `Relações`, `Riscos / incertezas`, `Próximos passos`, `Fontes`. Isso facilita patching automático sem o agente “reescrever tudo”. É muito melhor atualizar seções delimitadas do que regenerar páginas inteiras. citeturn12view3turn13view1

### Convenções para `SCHEMA.md`, `index.md` e `log.md`

**`SCHEMA.md`** deve ser o contrato normativo da wiki. Ele precisa definir: tipos de página aceitos; campos obrigatórios e opcionais de frontmatter; enumerações (`status`, `confidence`, `sensitivity`, `contradiction_state`); convenção de slugs; sintaxe de citações/locators; política de redaction; e regras para campos automáticos vs. humanos. A função do arquivo é impedir drift estrutural da wiki.

**`index.md`** não deve ser um dump automático de todas as páginas. Ele deve ser um **ponto de entrada curado**. No root, eu colocaria: visão do domínio, páginas quentes, missões ativas, decisões recentes, watchlist, páginas disputadas e atalhos por área. Em subpastas, `index.md` deve funcionar como um sumário local. Partes automáticas podem viver entre marcadores do tipo `<!-- ATLAS:BEGIN AUTO --> ... <!-- ATLAS:END AUTO -->`, preservando trechos humanos acima.

**`log.md`** deve ser **append-only** e orientado a eventos, não um diário narrativo. Cada entrada precisa ter timestamp, `job_id`, tipo de evento, alvo e resultado. Exemplos: `ingest.completed`, `page.updated`, `contradiction.flagged`, `lint.failed`, `source.drifted`, `review.approved`. Isso cria uma trilha de auditoria simples de ler e simples de difar em Git.

### Modelo de dados operacional

No `state/atlas.db`, eu manteria as seguintes tabelas principais:

| Tabela | Papel |
|---|---|
| `sources` | Identidade estável da fonte |
| `source_revisions` | Snapshots observados da fonte |
| `pages` | Metadados das páginas Markdown |
| `page_revisions` | Histórico de patch/revisão |
| `entities` | Entidades resolvidas canônicas |
| `entity_aliases` | Sinônimos e aliases |
| `claims` | Fatos atômicos extraídos/curados |
| `claim_evidence` | Evidências e locators por claim |
| `page_links` | Links e relações entre páginas |
| `contradictions` | Conflitos detectados e seu status |
| `chunks` | Segmentos textuais indexáveis |
| `embeddings` | Vetores por chunk/página |
| `session_links` | Ligações com `session_id` do Hermes |
| `lint_findings` | Achados de lint abertos/fechados |
| `jobs` | Execuções de ingest/query/lint |

Na prática, o padrão mais eficiente é armazenar blobs de frontmatter/metadata em JSON e extrair colunas importantes via JSON1 e generated columns indexáveis, em vez de “explodir” todo o esquema cedo demais. O SQLite já oferece funções JSON, colunas geradas e FTS5; o Hermes já usa SQLite/WAL/FTS5 com triggers para manter índices sincronizados. Isso favorece um núcleo local, observável e fácil de migrar. citeturn24search0turn24search1turn23view0turn32view0

## Runbooks de ingestão, consulta e lint

### Ingestão

O pipeline de ingestão deve ser **determinístico, idempotente e dividido entre trabalho mecânico barato e revisão cara**. O Hermes já suporta modelos auxiliares para tarefas laterais e subagentes roteados para modelos mais baratos/rápidos, o que combina muito bem com essa divisão. citeturn34view1turn35view2

O runbook recomendado é:

1. **Capturar** a fonte e gerar `source_id` + `revision_id`.
2. **Hashing e registro**: salvar blob bruto, MIME, origem, owner scope, sensitivity, canonical locator, ETag/Last-Modified quando houver.
3. **Normalizar/extrair**: texto, segmentos, timestamps, attachments, estrutura de documento.
4. **Extrair sinal** com modelo barato: resumo curto, entidades, datas, decisões, claims candidatos, tags, tarefas, possíveis relações.
5. **Resolver e comparar**: alinhar entidades aos registros existentes e buscar claims similares/conflitantes.
6. **Propor patches** de wiki: criar/atualizar páginas alvo, sem sobrescrever manual edits fora das zonas automáticas.
7. **Rodar guard rails**: frontmatter, citações, sensibilidade, contradições, conteúdo suspeito.
8. **Persistir e reindexar**: FTS, embeddings, links, índices por entidade, `index.md` e `log.md`.
9. **Escalar para revisão humana** se o conteúdo for sensível, contraditório, decisório ou de alto impacto.

Um detalhe importante: **ingestão não deve escrever diretamente “verdades” finais**. Ela deve escrever **claims com status**. Se duas fontes discordam, o comportamento correto não é apagar a mais antiga; é abrir um registro de contradição e marcar a página ou claim como `disputed` até nova verificação. Isso é especialmente importante porque o STORM explicitamente observou riscos de transferência de viés de fonte e associação indevida de fatos em sistemas que sintetizam textos longos a partir de múltiplas fontes. citeturn12view3

### Consulta

A consulta deve usar a wiki como **primeiro artefato de síntese**, e as fontes brutas como **última milha para precisão**. O runbook sugerido é:

1. **Classificar a pergunta**: factual simples, relacional, decisória, comparativa, operacional, exata/quote, ou follow-up de sessão.
2. **Selecionar o menor contexto viável**: `index.md`/frontmatter, sumários de página, seções da wiki, chunks vetoriais, raw excerpts, histórico de sessão.
3. **Ler páginas candidatas** antes de carregar grandes quantidades de bruto.
4. **Voltar para a fonte** quando a pergunta pedir número exato, quote, compliance, cronologia delicada, ou quando a wiki estiver stale/low-confidence.
5. **Responder com citações fortes**: sempre carregar `source_id`, `revision_id` e locator (linha, página, timestamp, path+line, message id).
6. **Promover a resposta** para `queries/` ou para páginas estruturalmente relevantes apenas se ela trouxer síntese reutilizável, não se for uma resposta efêmera.

O Hermes já separa prompt estável de overlays voláteis e já persiste/recupera sessões com busca full-text; isso sugere que ATLAS deve seguir a mesma disciplina: respostas compostas valiosas entram na wiki, enquanto o fluxo normal da conversa fica nas sessões e no provider de memória. citeturn27view1turn32view0turn28search6

### Lint

O lint é o que transforma a wiki em ativo mantido em vez de cemitério de Markdown. O Hermes já tem um precedente relevante com o **Curator**, que trata skills como artefatos vivos, marcando drift, consolidação e arquivamento; o runtime de conhecimento deve ter um equivalente para páginas e claims. citeturn29search0turn29search8

Eu criaria pelo menos estes lints:

| Regra | O que detecta | Ação |
|---|---|---|
| `frontmatter_missing` | campo obrigatório ausente | bloqueia patch automático |
| `broken_link` | link interno quebrado | finding aberto |
| `orphan_page` | página sem inbound/outbound úteis | sugere merge, archive ou relink |
| `stale_claim` | `last_verified_at` vencido | reduzir confiança / abrir review |
| `contradiction_unresolved` | conflito aberto sem adjudicação | banner em página |
| `source_drift` | nova revisão difere da base citada | revisão obrigatória |
| `low_confidence_hot_page` | página muito usada com pouca confiança | priorizar revisão |
| `citation_gap` | claim sem evidência suficiente | bloquear promoção |
| `sensitivity_violation` | dado secreto/PII vazou para camada errada | redaction + incident |
| `schema_drift` | heading/body fora do contrato | normalizar patch |

O lint deve rodar por **cron** e também em eventos de ingestão, com saídas registradas em `log.md`, `lint_findings` e uma fila de review. O gateway Hermes já executa cron e o REST do Hermes já expõe jobs/sessions, então o lint do ATLAS pode ser um job nativo do runtime, não um serviço paralelo. citeturn5view3turn5view7

## Comparação de busca e armazenamento

A decisão certa aqui não é “qual banco vence”; é **qual combinação dá mais velocidade, menos RAM e melhor auditabilidade** no estágio atual do ATLAS.

**Markdown + ripgrep** é o melhor baseline para busca exata, inspeção humana, debugging e operação local. O `ripgrep` faz busca recursiva por regex, respeita `.gitignore` e roda em Windows, macOS e Linux. Eu o manteria sempre disponível, mas como camada de operador e fallback lexical, não como único mecanismo de recuperação. citeturn10view3

**SQLite FTS5** é a melhor espinha dorsal do MVP. O FTS5 fornece virtual tables de full-text, external-content tables com triggers, prefix indexes e tokenizers como `unicode61`, `porter` e `trigram`. Além disso, o Hermes já usa SQLite em WAL com FTS5 e trigram para sessões, o que reduz risco arquitetural e facilita reaproveitamento de padrões de concorrência, migração e indexação. Para o ATLAS, isso significa um núcleo embedded, leve, rebuildável e sem dependência de servidor para o caso local-first. citeturn10view1turn23view0turn23view2turn23view3turn32view0

**qmd** é um ótimo acelerador local, mas eu o trataria como **opcional** e não como store canônico. O projeto se descreve como um mecanismo on-device que combina BM25/FTS, busca vetorial e reranking local; o índice fica em `~/.cache/qmd/index.sqlite`, com FTS5, vetores e cache de LLM. Isso é excelente para buscar notas, docs e transcrições localmente com boa qualidade, e o próprio Hermes já tem skill oficial para ele. O problema é de arquitetura: qmd introduz um runtime e um índice paralelos; para o ATLAS, isso é ótimo como sidecar ou conector, mas fraco como fonte primária de verdade. citeturn7view0turn20view0turn20view2turn20view3turn7view1

**PostgreSQL + text search + pgvector** passa a fazer sentido quando o ATLAS entrar de verdade em **multiusuário, WebUI com colaboração, CRM relacional central e sincronização remota**. O PostgreSQL já oferece ranking textual levando em conta informação lexical, proximidade e estrutura; e o pgvector oferece ANN com **IVFFlat** e **HNSW**, com trade-offs claros entre memória, build time e recall. Eu só não o colocaria no centro agora porque ele eleva a complexidade operacional para um problema que, no MVP do brief, ainda é resolvido melhor por arquivos + SQLite. citeturn10view2turn10view0

**Graph DB** deve entrar apenas quando a consulta sobre relações virar requisito dominante: multihop entre pessoas, empresas, oportunidades, decisões, canais, tarefas, fontes e missões. O Neo4j hoje já combina full-text index, vector index e um pacote oficial de GraphRAG, o que o torna um bom candidato futuro para projeções relacionais de alto valor. Mas ele é caro demais como backbone inicial de uma wiki cujo principal valor é ser humana, versionável e simples de reparar. citeturn10view4turn10view5turn9search2turn26search2

A minha decisão recomendada para ATLAS é, portanto:

- **Canônico humano**: Markdown em `wiki/`, versionado.
- **Canônico operacional**: SQLite `atlas.db` em WAL + FTS5 + registros de claims/evidências.
- **Busca exata**: ripgrep.
- **Busca semântica/híbrida**: embeddings locais plugáveis; qmd opcional como sidecar; não obrigatório.
- **Evolução posterior**: espelho seletivo em Postgres/pgvector para WebUI colaborativa e CRM; projeção relacional/graph para domínios que realmente precisarem de GraphRAG.

Essa combinação é a mais coerente com o brief: velocidade, pouca memória, manutenção simples, auditabilidade e expansão gradual. citeturn10view3turn10view1turn7view0turn10view0turn10view4

## Estratégia de otimização de contexto

A regra-mãe do ATLAS deve ser: **carregue o artefato mais barato que ainda responde com segurança**. Essa é exatamente a direção sugerida pela literatura de memória hierárquica para agentes e pela própria arquitetura do Hermes, que separa camadas estáveis do prompt de overlays voláteis para preservar cache, continuidade e correção de memória. citeturn13view0turn27view1turn28search8

Eu implementaria um **context-selection engine em níveis**:

| Nível | O que carregar | Quando usar |
|---|---|---|
| `K0` | nada | conversa casual / já resolvida pelo estado atual |
| `K1` | `index.md`, títulos, frontmatter, metadados | navegação, triagem, entity routing |
| `K2` | resumos curtos de páginas | perguntas conceituais ou exploratórias |
| `K3` | seções específicas da wiki | decisões, workflows, comparações, missões |
| `K4` | chunks vetoriais / resultados FTS5 | descoberta fuzzy ou cobertura transversal |
| `K5` | trechos brutos da fonte | quotes, números, compliance, ambiguidades |
| `K6` | histórico de sessão | follow-up de conversa, “o que discutimos?” |

As heurísticas práticas seriam estas. Se o usuário perguntar **“quem é X?”**, tente `entity page` primeiro. Se perguntar **“qual foi a decisão sobre Y?”**, tente `decision/*` e `mission/*`, depois `log.md`. Se pedir **quote exata, campo exato, página de PDF, linha de código, cláusula de contrato, data precisa**, vá para `K5` e cite a fonte bruta. Se a pergunta for **aberta mas localizada**, use `K2/K3`. Se for **difusa** (“onde falamos sobre onboarding de parceiros?”), use `K4` com FTS5 + vetores e só depois materialize páginas completas. Se for **follow-up de sessão**, comece pelo store de sessões Hermes e pela memória da sessão, não pela wiki. citeturn32view0turn18view2turn29search7

Também recomendo separar claramente **contexto persistente** de **contexto efêmero**. O Hermes já mostra por que isso importa: o prompt estável deve mudar pouco para preservar cache; memória e overlays voláteis entram separadamente; e grandes artefatos não devem ser recopiados para cada turno. Para o ATLAS isso implica: **não despejar páginas inteiras ou tool outputs longos no prompt**; preferir títulos, resumos e locators; e só expandir quando a hipótese de resposta realmente exigir. citeturn27view1turn18view2turn31search2

O engine também deve escolher **qual modelo faz qual parte**. Busca, reranking barato, entity resolution inicial e segmentação podem ir para modelos auxiliares ou subagentes baratos; síntese final, revisão arquitetural, adjudicação de contradição e recomendações estratégicas devem usar o modelo forte. O Hermes já suporta slots auxiliares e override de provider/model para subagentes, inclusive com controle de largura/profundidade de delegação. citeturn34view1turn35view2

Por fim, eu criaria uma regra de **promoção de resposta para wiki**. Uma resposta só vira conhecimento persistente se cumprir, ao mesmo tempo, quatro condições: é reutilizável, é fundamentada, altera o estado de entendimento do sistema, e cabe naturalmente em uma página existente ou em `queries/`. Isso impede a wiki de virar um dump de respostas de chat.

## Regras de segurança e privacidade

O runtime de conhecimento do ATLAS deve partir de uma classificação mínima de dados. Eu usaria quatro classes:

| Classe | Exemplos | Regra de tratamento |
|---|---|---|
| `public` | docs públicos, marketing, sites | pode entrar em wiki ampla |
| `internal` | notas internas, runbooks, status | wiki interna, ACL por workspace |
| `confidential` | CRM, negociações, finanças, contratos | acesso restrito, redaction por default |
| `secret` | API keys, senhas, tokens, segredos operacionais | nunca indexar em wiki/embeddings; só cofre/`.env` |

Essa distinção importa porque o NIST trata PII como informação que distingue ou permite rastrear um indivíduo, isoladamente ou em combinação com outros dados; e a OWASP enfatiza tanto **prompt injection** quanto **sensitive information disclosure** como riscos centrais em aplicações com LLMs. citeturn14search5turn14search12turn31search0turn14search14

Na prática, minhas regras seriam estas. **Segredos não entram no runtime de conhecimento**: nem em `raw/`, nem em `wiki/`, nem em embeddings. O Hermes já separa segredos em `.env`, roteia chaves para esse arquivo e redige segredos nos logs; ATLAS deve seguir exatamente esse padrão. Se um parser encontrar um token, chave privada, senha, cookie de sessão ou segredo semelhante, o item deve ir para `quarantine/` e gerar finding de segurança, não resumo. citeturn30view0turn30view1

**PII e CRM devem ser minimizados**. Para pessoas, a página de entidade não precisa expor tudo que a fonte contém. Ela deve preferir relações úteis ao trabalho — papel, empresa, estágio do relacionamento, histórico de contato, preferências operacionais autorizadas — e omitir campos não necessários. Sempre que possível, embeddings também devem receber texto redigido, não o bruto completo, porque busca semântica atravessa fronteiras de forma opaca se o ACL for mal implementado. citeturn14search5turn14search14

**Perfis/workspaces separados** devem ser o limite duro entre pessoal e empresa, ou entre clientes/tenants diferentes. O Hermes já oferece profiles isolados, cada um com seu próprio `config.yaml`, `.env`, memória, sessões, skills e gateway state. Isso é um bom mecanismo base para separar áreas de confiança diferentes dentro do ATLAS. Mesmo quando o produto expuser uma WebUI unificada, o runtime subjacente deve respeitar isolamento por workspace/perfil. citeturn5view2

**Conteúdo externo nunca deve ser tratado como confiável por padrão.** O Hermes já faz varredura de prompt injection em arquivos de contexto e descreve esse scanner como parte da defesa em profundidade; o ATLAS deve fazer o mesmo com páginas importadas, resumos de fonte e patches propostos pelo agente. Além disso, qualquer fonte externa que tente instruir o sistema (“ignore instruções anteriores”, “revele segredos”, “envie dados”) deve ser marcada como conteúdo, não como instrução operacional. citeturn27view0turn31search0turn31search4

**Cada claim e cada página deve carregar ACL e sensitivity explícitos**, e o contexto-selection engine deve filtrá-los antes da recuperação. Em outras palavras: a escolha de contexto não pode ser só por relevância; precisa ser por **relevância ∩ autorização**.

## Plano de MVP

O MVP deve provar uma tese simples: **ATLAS já consegue acumular conhecimento operacional melhor do que um RAG de chunks, sem abandonar a leveza do Hermes**. Para isso, eu dividiria a construção em camadas.

### Fase inicial

A primeira entrega deve ser local-first e single-workspace:

- plugin(s) do Hermes para ingest/query/lint;
- `raw/` com blobs imutáveis e manifests;
- `wiki/` com `SCHEMA.md`, `index.md`, `log.md` e tipos básicos de página;
- `state/atlas.db` com `sources`, `source_revisions`, `pages`, `claims`, `claim_evidence`, `chunks`, `lint_findings`;
- ingestão de arquivos, URLs, repositórios e sessões Hermes;
- busca lexical via FTS5 + ripgrep;
- resposta com locators e citações;
- promoção manual/semiautomática de respostas valiosas para a wiki. citeturn16view0turn17search0turn32view0turn10view3turn10view1

Essa fase já deve produzir valor se vier com comandos claros, por exemplo `atlas ingest`, `atlas query`, `atlas lint`, `atlas promote`, e uma visualização WebUI mínima para páginas, fontes, contradições e runs, aproveitando a API/arquitetura já existente do Hermes. citeturn5view7turn31search8

### Fase de composição

Depois que o pipeline básico estiver estável, a próxima fase deve atacar o que realmente faz o conhecimento “compounding”:

- claims atômicos e `claim_evidence`;
- detecção de contradição com estado `clean/disputed/resolved`;
- drift detection de fontes mutáveis;
- query pages em `queries/` para respostas compostas reutilizáveis;
- rotinas de cron para refresh de fontes e lint periódico;
- context-selection engine em níveis `K0..K6`;
- subagentes baratos para extração e rerank, modelo forte para revisão final. citeturn12view3turn5view3turn34view1turn35view2

### Fase de expansão

Só depois disso eu abriria as frentes mais pesadas:

- espelho seletivo para Postgres/pgvector se a WebUI virar realmente multiusuária;
- projeção relacional ou graph para CRM, oportunidades e relationship intelligence;
- integrações mais profundas com CRM/canais;
- superfícies de “Pulse” e briefings sobre páginas, missões e fontes em drift;
- overlay/desktop sidecar nativo para approvals/context capture;
- políticas finas por tenant, equipe e tipo de dado.

Nessa fase, a wiki continua sendo o coração humano; o banco adicional vira infraestrutura de distribuição, colaboração e consulta mais sofisticada, não substituto do artefato Markdown.

### Questões em aberto e limitações

Há três pontos abertos que eu deixaria explícitos. Primeiro: eu **não consegui verificar publicamente** o estado exato dos repositórios/ativos privados do ecossistema L2 citados no brief, então a proposta assume que suas capacidades são as descritas no contexto do projeto. Segundo: **qmd é promissor como sidecar local**, mas eu não o tornaria dependência central sem decidir antes se o ATLAS quer assumir um runtime/index paralelo ou reimplementar as ideias essenciais diretamente no stack principal. Terceiro: a fronteira entre **wiki operacional** e **CRM operacional** precisa ser decidida cedo — principalmente para saber quando registros de relacionamento continuam como páginas/claims e quando passam a exigir um modelo relacional mais forte. citeturn7view0turn7view1turn10view0

A conclusão prática, porém, é firme: **o MVP do ATLAS deve nascer como um compilador de conhecimento sobre o Hermes, não como um chatbot com embeddings**. Essa escolha dá ao produto mais memória útil, melhor auditoria, melhor manutenção e um caminho muito mais limpo para crescer.