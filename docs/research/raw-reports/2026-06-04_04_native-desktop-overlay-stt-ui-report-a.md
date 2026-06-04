# Estratégia nativa de desktop para o L2 ATLAS

## Recomendação executiva

A melhor estratégia para o ATLAS é **separar claramente cockpit e sidecar**. O cockpit continua sendo **WebUI-first** para dashboards, runs, auditoria, wiki, CRM, integrações e superfícies densas de informação. O sidecar nativo fica responsável por tudo que precisa ser **instantâneo, leve, sempre disponível e profundamente integrado ao sistema operacional**: hotkeys globais, command palette, overlay/HUD, tray, prompts de aprovação, captura contextual e pipeline local de voz. Essa separação combina bem com a base do Hermes, que já possui múltiplos pontos de entrada, sessões, ferramentas, memória, perfis e gateway, sem forçar o desktop a virar o runtime inteiro do agente. citeturn19view0turn19view2turn19view3

Minha recomendação concreta é: **Slint como toolkit principal das superfícies nativas do usuário**, **Rust residente como sidecar/daemon**, e **Tauri apenas como casca opcional do cockpit WebUI**, nunca como núcleo do overlay. O motivo é simples. Slint foi desenhado para footprint baixo, UI declarativa compilada para código nativo e múltiplos renderers; Tauri é ótimo para empacotar uma interface HTML usando o WebView do sistema e manter binários pequenos, mas continua sendo WebView-centric; Electron, por sua vez, embute Chromium + Node.js e herda a arquitetura multiprocessada do Chromium, com um renderer separado para cada janela, o que vai na direção oposta da filosofia de desempenho do ATLAS. citeturn33view2turn33view1turn34view3turn35view0turn35view1

Para Linux, o desktop nativo deve ser tratado como **dois problemas diferentes**: X11 e Wayland. Em Wayland, janelas comuns não resolvem o problema de overlay de forma confiável; o caminho correto para HUD real é **layer-shell** ou integração específica com o compositor. Em paralelo, hotkeys globais e screen capture devem passar por **portais XDG** e, no caso de Hyprland, podem aproveitar tanto o `xdg-desktop-portal-hyprland` quanto o protocolo próprio de atalhos globais. Em outras palavras: **Windows primeiro para GA**, **Linux X11 + Hyprland como beta dirigido**, e suporte Wayland genérico tratado como superfície de compatibilidade, não como pressuposto “já resolvido”. citeturn23view0turn27view0turn27view1turn27view2turn24search11turn26search12

No pipeline de voz, o caminho mais pragmático para MVP é: **push-to-talk como padrão**, **faster-whisper/CTranslate2 em máquinas com GPU adequada**, **whisper.cpp como fallback on-device e de baixo acoplamento**, **Parakeet como trilha posterior para streaming parcial mais forte**, e **Piper/Kokoro-ONNX para TTS local**. O Hermes já demonstra STT local, endpointing e TTS em streaming por sentença; o ATLAS deve **reaproveitar a lógica de produto**, mas mover o laço de microfone, hotkeys, buffer de áudio e playback para o lado nativo em Rust, onde latência e consumo são mais previsíveis. citeturn19view1turn20view0turn20view1turn21view0turn21view1turn21view2turn40view0turn40view1

O resumo decisório é este: **não usar Electron**, **não tentar recriar o cockpit inteiro em UI nativa**, **não depender de Tauri para overlay/HUD**, **não pôr wake word no MVP**, e **não acoplar UX instantânea ao processo Python do runtime**. O sidecar deve ser um componente de primeira classe, residente, rápido e austero; o cockpit WebUI continua sendo o lugar da profundidade operacional. citeturn34view3turn35view0turn35view1turn19view0turn19view2

## Matriz de UI em Rust e metas de desempenho

### Matriz comparativa de UI em Rust

| Opção | Adequação para ATLAS | Onde eu usaria | Onde eu evitaria |
|---|---|---|---|
| **Slint** | **Escolha principal** | Palette, tray windows, approval prompts, HUDs nativos, sidecar leve | Overlay Wayland “de verdade” sem camada baixa adicional |
| **egui** | Boa escolha secundária | Ferramentas internas, inspetores, utilitários de operador, protótipos rápidos | Shell principal de produto e UI “premium” pública |
| **iced** | Viável, mas não a melhor aposta | Apps tradicionais stateful, superfícies com arquitetura Elm-like | MVP central do ATLAS, especialmente para overlay e acessibilidade |
| **custom wgpu** | Excelente como escape hatch | Renderer especializado, visualizações próprias, overlay extremo | App inteiro, principalmente no MVP |
| **APIs nativas por plataforma** | Forte por SO, fraco para produto único | App Windows-only ou Linux-only | Código compartilhado do ATLAS desktop |
| **Tauri thin shell** | Útil como opcional | Empacotar cockpit WebUI, menus/tray simples, janela desktop do cockpit | Núcleo do sidecar, overlay, hotkeys/Wayland hard mode |
| **Electron** | Baseline negativa | Quase nunca neste contexto | Praticamente todo o desktop do ATLAS |

A leitura da matriz é direta. **Slint** oferece exatamente o tipo de fundamento que o ATLAS precisa: UI declarativa compilada para máquina nativa, baixo consumo, renderers múltiplos e aceleração por GPU quando necessário. A documentação da própria Slint enfatiza footprint baixo, acesso a APIs do sistema, múltiplos métodos de rendering e, em 2026, a integração com Servo já demonstrava aceleração por hardware também no Windows, o que mostra maturidade crescente em cenários de desktop reais. O principal cuidado é que Wayland/layer-shell continua sendo um capítulo separado, e a Slint ainda exige revisão cuidadosa de licença/empacotamento logo no início do projeto. citeturn33view2turn33view1turn33view0

**egui** é extremamente atraente para painéis de operador e ferramentas internas porque é immediate mode, vive confortavelmente em UIs altamente interativas e roda na cadência de refresh da tela. Além disso, já possui integração opcional com AccessKit, o que ajuda em acessibilidade. O problema é outro: a própria documentação ressalta desenvolvimento pesado com breaking changes, e a estética/ergonomia padrão tende a “ferramental” mais do que “produto nativo polido”. Para o ATLAS, isso a coloca como excelente segundo toolkit, não como superfície principal. citeturn34view0turn37search0turn37search4

**iced** tem méritos importantes: API reativa inspirada em Elm, suporte a tarefas assíncronas, métricas e time-travel no debug, além de renderers baseados em `wgpu` e software fallback. Mas há dois sinais que pesam contra usá-la como aposta central do ATLAS neste momento: a própria documentação a chama de **experimental software**, e o trabalho de acessibilidade ainda aparece como tema em aberto. Para uma empresa cockpit séria, isso é aceitável em componentes ou produtos internos; para o núcleo do sidecar, é risco desnecessário. citeturn34view1turn34view2turn38search0

**Custom `wgpu`** é a opção de máximo controle. A crate `wgpu` é segura, cross-platform e já sustenta casos de alto desempenho fora do mundo “app GUI puro”. Mas essa liberdade cobra caro: você passa a ser dono de composição, widgets, foco, acessibilidade, hit-testing, navegação de teclado e uma grande fatia da ergonomia do app. Minha recomendação é usar `wgpu` apenas como **camada de escape** para superfícies muito especiais — por exemplo, um overlay com rendering próprio, visualização temporal de áudio ou um compositor interno de run status. citeturn8search8turn37search7

**APIs nativas por plataforma** são tentadoras. A Microsoft recomenda WinUI para Windows moderno, e GTK4/libadwaita são blocos sólidos no ecossistema GNOME. O problema é estratégico: o ATLAS não é um app “Windows puro” nem um app “GNOME puro”; é um produto operacional com cockpit WebUI e sidecar cross-platform. Entrar em WinUI de um lado e GTK/libadwaita do outro seria vender desempenho comprando duplicação arquitetural e divergência de UX. citeturn8search1turn8search5turn8search2turn8search3turn8search6

**Tauri** é útil, mas no lugar certo. A arquitetura oficial deixa claro que ele usa o WebView do sistema, não embute um runtime inteiro como Electron, e a camada de segurança enfatiza fronteiras de confiança e IPC bem definidos. Isso o torna uma ótima casca opcional para o cockpit WebUI. Mas, na fronteira de overlay/Wayland, a própria stack subjacente mostra limites: `tao` marca `always_on_top` como não suportado no Linux/Wayland, e a janela transparente click-through continua sendo um caso com arestas. Para o ATLAS: **use Tauri para a janela do cockpit, não para o coração do sidecar**. citeturn34view3turn36view0turn36view2turn36view3turn24search11

### Metas de desempenho

As metas abaixo não são “benchmarks de documentação”; são **alvos de produto** coerentes com a estratégia recomendada acima e com o que sabemos sobre custos de WebView, overlay nativo e pipelines locais de inferência. Elas assumem sidecar residente, lazy-loading de workers de modelo e separação entre cockpit WebUI e surfaces de imediatismo. Os benchmarks oficiais de `faster-whisper`, as propriedades de `whisper.cpp`, o suporte de streaming do Parakeet e a abrangência de aceleração via ONNX/DirectML justificam um desenho com workers especializados em vez de um app monolítico sempre pesado. citeturn21view0turn21view1turn21view2turn21view3

| Métrica | Meta recomendada | Teto aceitável | Observação de produto |
|---|---:|---:|---|
| Sidecar visível após cold start | **≤ 300 ms** | 500 ms | janela/ícone/tray prontos, sem carregar modelos pesados |
| Hotkey → command palette pintada | **≤ 50 ms p50** | 100 ms p95 | sensação de instantaneidade |
| Idle RAM do sidecar residente | **40–80 MB** | 120 MB | sem modelos carregados |
| Idle CPU médio | **< 1%** | 2% | máquina “quieta” quando ATLAS está ocioso |
| Evento de runtime → approval prompt visível | **≤ 75 ms** | 150 ms | aprovações precisam parecer síncronas |
| Overlay/HUD frame budget | **60 fps garantidos** | 16,7 ms/frame | 120 Hz quando o compositor permitir |
| Primeiro parcial de STT | **≤ 300 ms GPU** | 800 ms CPU | para push-to-talk e ditado curto |
| Finalização STT após fim da fala | **≤ 700 ms GPU** | 1,5 s CPU | sem parecer “travado” |
| Primeiro chunk de TTS | **≤ 250 ms local** | 500 ms remoto | playback deve começar cedo |
| Captura contextual já autorizada → pronta | **≤ 150 ms** | 300 ms | picker/portal fora do budget |

Essas metas implicam algumas regras duras. O sidecar residente **não deve** carregar `large-v3` ou qualquer pipeline grande de STT em background. Workers de voz precisam ser **ativados sob demanda**, cacheados com parcimônia e descartáveis. O processo que segura hotkeys, tray, overlay e aprovação deve continuar magro mesmo quando o operador nunca usa voz no dia. Isso é mais compatível com um sidecar Rust + workers de inferência do que com uma shell WebView generalista sempre ativa. citeturn21view0turn21view1turn34view3turn35view1

## Arquitetura nativa

### Arquitetura nativa

A arquitetura do Hermes já ajuda a definir a divisão correta de responsabilidades. A documentação mostra que o sistema gira em torno de um `AIAgent` com múltiplos entry points — CLI, gateway, API server, ACP, biblioteca Python — e que os perfis isolam estado, memória, sessões, skills, cron e gateway, mas **não** equivalem a sandbox de filesystem. Além disso, cada perfil pode ter seu próprio processo de gateway. Para o ATLAS, isso sugere uma conclusão importante: o desktop não deve tentar “ser o Hermes”; ele deve ser um **broker nativo de baixa latência** na frente do Hermes/ATLAS runtime. citeturn19view0turn19view2

A proposta que melhor equilibra desempenho, auditabilidade e manutenção é um arranjo de **três processos lógicos**, com dois deles podendo ser um único binário multipapel no MVP:

```text
┌─────────────────────────────────────────────────────────────┐
│                    atlas-desktop                           │
│      Rust residente: hotkeys, tray, overlay, approvals,   │
│      áudio, STT/TTS workers, capture adapters, notif.     │
└───────────────┬───────────────────────┬────────────────────┘
                │ IPC local seguro      │ SSE/WebSocket local
                │                       │
        ┌───────▼────────┐      ┌──────▼─────────┐
        │ atlas-runtime   │      │ atlas-web      │
        │ Hermes/ATLAS    │      │ cockpit WebUI  │
        │ Python service  │      │ browser/Tauri  │
        └─────────────────┘      └────────────────┘
```

O `atlas-desktop` deve ser o processo residente. Ele segura hotkeys globais, loop de janela, tray, notificações, palette, approval prompts, áudio, workers leves e o broker de IPC. O `atlas-runtime` roda o Hermes/ATLAS propriamente dito, com perfis, run graph, memória, wiki, CRM e automações. O `atlas-web` serve o cockpit em browser comum ou numa wrapper Tauri opcional. Este desenho preserva o Hermes como fundamento vivo, mas remove do processo Python toda a responsabilidade que precisa responder em dezenas de milissegundos. citeturn19view0turn19view2turn34view3

Para IPC, eu recomendo **pipes locais tipados e versionados**, não um amontoado de chamadas localhost ad hoc. Em Windows, isso significa **Named Pipes com ACL restrita ao usuário atual**; em Linux, **Unix Domain Socket em `XDG_RUNTIME_DIR` com permissão 0600**. O protocolo pode ser gRPC ou um framing binário simples com Protobuf/MessagePack, mas precisa carregar **capabilities explícitas**, correlation IDs, backpressure e eventos assináveis. O motivo é o mesmo que a documentação de segurança do Tauri e o threat model do Odysseus deixam evidente: a fronteira entre UI e core privilegiado precisa ser desenhada como fronteira de confiança real, não como “só um detalhe interno”. citeturn36view0turn14view0

Também recomendo um **event stream unificado**. Toda ação relevante — `run.started`, `tool.requested`, `approval.required`, `approval.granted`, `capture.started`, `stt.partial`, `tts.started`, `pulse.alert` — deve existir como evento formal com schema estável. A WebUI e o sidecar nativo consomem o mesmo stream. Para persistência, o ideal é um journal local robusto, com escrita sequencial e consultas rápidas, seguido de exportação para JSONL quando necessário. Isso entrega exatamente o que o ATLAS quer: execução, auditoria e observabilidade no mesmo tecido operacional. A lógica de eventos já combina com o modo como o Hermes organiza sessões/gateways e com a disciplina explícita de threat model e pairing vem do Odysseus. citeturn19view3turn16view0turn14view0

As aprovações devem ser tratadas como **produto nativo de segurança**, não como um modal HTML qualquer. Quando o runtime pedir permissão para action sensível, o sidecar nativo transforma isso em um prompt com descritor claro, risco, diff ou preview, timeout, escolha de escopo e emissão de um **approval ticket** curto, vinculando usuário, ação, recurso e janela temporal. O runtime só executa a ação mediante ticket válido. Isso fecha duas portas de problema: spoofing visual e bypass acidental de política por um frontend web comprometido ou confuso. citeturn36view0turn20view1turn14view0

### Fronteira entre WebUI e nativo

A regra prática é esta: **tudo que precisa parecer imediato ou tocar uma permissão de SO pertence ao nativo**. Isso inclui hotkeys globais, palette, mic, reprodução TTS, notificações, tray, overlays, picker de captura, indicadores de privacidade, prompts de aprovação e leitura de contexto “ao redor do operador” — janela ativa, app atual, clipboard, seleção, resumo de captura. Esses elementos são justamente os que se beneficiam de latency budget curto e de controle fino de janelas e loops do sistema. citeturn22view0turn22view4turn27view0turn26search6

Em contrapartida, **tudo que é denso, navegável, auditável e orientado a múltiplos painéis pertence ao cockpit WebUI**. Missões, histórico de runs, wiki, CRM/relacionamentos, páginas de integração, tabelas de logs, relatórios de research, dashboards e configurações complexas rendem muito melhor em WebUI. O próprio Tauri pode ser usado como wrapper desktop dessa camada, porque aí ele está no seu melhor papel: prender um cockpit HTML ao desktop, usando o WebView do sistema e as APIs de janela/tray quando isso for útil. citeturn34view3turn36view2turn36view3

A fronteira também precisa ser **unidirecional em privilégios**. A WebUI não deve se tornar dona direta de microfone, screen capture ou hotkeys. Ela pede, o sidecar decide, executa e publica resultado. Isso segue a mesma lógica que o Tauri descreve para trust boundaries e a mesma prudência que as APIs modernas de captura no Windows e os portais do Linux impõem: permissão é parte da arquitetura, não um detalhe de implementação. citeturn36view0turn22view0turn22view4

## Pipeline de STT/TTS

O Hermes já mostra duas ideias corretas que o ATLAS deve preservar: **silence detection/endpointing local** e **TTS em streaming por sentença**. Hoje, a documentação do Hermes descreve confirmação de fala, corte após silêncio contínuo e reprodução de TTS conforme o texto vai saindo; também descreve prioridade de STT local com `faster-whisper`. A diferença é que, no ATLAS, essas capacidades devem ser movidas para um pipeline residente em Rust, em vez de depender apenas do loop de voz do CLI ou de mensagens. citeturn19view1turn20view0turn20view1

O desenho recomendado é: captura de áudio para ring buffer, pré-processamento leve, gate de atividade de fala, worker de STT, camada de estabilização de parciais e despacho do resultado para palette/comando. No MVP, a ativação deve ser **push-to-talk** e **toggle-to-talk**. Em Windows, o gatilho pode usar `RegisterHotKey`; em Linux/Wayland, o caminho correto é o portal `GlobalShortcuts` e, em Hyprland, o protocolo próprio de atalhos globais. Isso reduz custo contínuo de CPU, simplifica privacidade e evita abrir a caixa de Pandora de wake word cedo demais. citeturn26search6turn27view0turn27view2

Para STT, eu recomendaria três trilhas. A primeira, **padrão de produção**, é `faster-whisper` sobre CTranslate2 em GPUs adequadas. O repositório oficial informa que a implementação pode ser até 4x mais rápida que `openai/whisper` com menos memória, e mostra benchmarks concretos inclusive com quantização int8. A segunda trilha, **fallback de portabilidade**, é `whisper.cpp`, que oferece inferência CPU-only, quantização, VAD, suporte amplo de plataformas e até um exemplo oficial de streaming em microfone a cada 500 ms. A terceira trilha, **futura para dictation/streaming forte**, é Parakeet TDT, cujo material oficial mostra inferência em modo chunked streaming. Em resumo: `faster-whisper` para throughput, `whisper.cpp` para robustez edge/offline, `Parakeet` para live streaming premium. citeturn21view0turn21view1turn31view0turn21view2turn31view1

No Windows, vale introduzir desde cedo uma abstração de backends para inferência ONNX, mas **não prender o design a DirectML puro**. A documentação oficial do ONNX Runtime diz que o Execution Provider de DirectML continua suportado, porém em sustained engineering, e aponta WinML como direção de evolução para deploys Windows baseados em ONNX Runtime. Então a decisão correta não é “usar DirectML em tudo”; é **modelar um backend Windows GPU que possa rodar em WinML/DirectML conforme o worker e o modelo pedirem**, com CUDA como primeira escolha quando disponível e CPU como base universal. citeturn21view3

Para TTS, o padrão local mais pragmático é **Piper ou Kokoro-ONNX**. Piper continua sendo uma referência de TTS local rápido, mas o repositório original foi arquivado e o desenvolvimento migrou, o que introduz um risco claro de vendor/maintenance. Kokoro-ONNX, por outro lado, já apresenta múltiplas vozes e idiomas, footprint reduzido em versões quantizadas e integração simples com ONNX Runtime. Minha recomendação é: **MVP com Piper por maturidade operacional e licenciamento simples do histórico**, desde que o ATLAS faça fork/vendor; **Kokoro como trilha posterior de qualidade**, especialmente para vozes mais agradáveis e footprint controlado. citeturn40view0turn40view1

O pipeline de playback deve ser **interruptível, baseado em fila curta e orientado a streaming**. O runtime produz texto; o sidecar segmenta em sentenças ou cláusulas estáveis; o worker de TTS gera blocos curtos; o player nativo inicia sem esperar o texto inteiro. Essa ideia já existe no Hermes, e funciona bem para ATLAS porque preserva a sensação de “agente presente” sem transformar o desktop inteiro num app de voz. citeturn19view1turn20view0

A última peça é o ciclo de vida dos modelos. Modelos de STT/TTS **não podem ficar residentes por padrão** no mesmo processo que segura hotkeys, approvals e tray. Workers sob demanda, preload opcional após o primeiro uso e descarte agressivo quando ocioso são fundamentais para cumprir os budgets de RAM definidos antes. O que precisa estar sempre vivo é a camada de input, evento e UI — não os pesos do modelo. citeturn21view0turn21view1

## Modelo de UX de overlay

O overlay do ATLAS não deve tentar ser “um mini desktop inteiro flutuante”. O modelo correto é **palette-first, HUD-second**. O coração do sidecar é uma command palette que aparece instantaneamente, aceita texto e voz, entende contexto operacional e envia ações para o runtime. O HUD existe para status, aprovação, captura e briefings curtos — não para substituir páginas ricas do cockpit. Essa divisão é mais leve, mais auditável e mais coerente com a diferença entre sidecar e WebUI. citeturn34view3turn19view0

A **command palette** deve abrir por hotkey global, centralizada, com foco direto de teclado e input de voz opcional. Ela mostra ações recentes, missões em andamento, entidades relevantes e “chips” de contexto como projeto, app atual, janela ativa e modo de privacidade. Em Windows, esse gatilho usa a infra normal de hotkeys globais; em Wayland, deve passar pela sessão de `GlobalShortcuts` ou pelo protocolo do compositor, nunca por um keylogger improvisado. citeturn26search6turn27view0turn27view2

O **listening HUD** deve ser mínimo: um strip ou orb pequeno com três estados claros — ouvindo, transcrevendo, enviando. É um caso clássico de superfície que precisa ser nativa, porque depende de latência curta, de pintura discreta e de foco reversível. Em Windows, isso casa bem com janelas topmost/layered; em Wayland, janelas comuns não bastam e o caminho robusto é layer-shell para surfaces de overlay reais. citeturn28search2turn29search3turn23view0turn24search11

Os **approval prompts** devem ser a face visível da política operacional do ATLAS. Eles precisam exibir ação proposta, por que o agente quer executá-la, impacto potencial, recurso afetado, opção de “aprovar uma vez”, “aprovar para esta run” ou “negar”. Essas janelas não devem parecer genéricas demais, para reduzir spoofing, e não devem bloquear o sistema inteiro como modal hard. Elas são pequenas peças de trust UX. A boa referência aqui não é um dialog box genérico, e sim a combinação entre o modo de aprovações do Hermes e a clareza de fronteira do threat model do Odysseus. citeturn20view1turn14view0

O **run dock** é o quarto elemento do overlay. Ele mostra qual agente está rodando, qual modelo está ativo, qual ferramenta está em uso, custo/tempo acumulado, pontos de bloqueio e uma ação forte de parar/pausar. Esse dock pode ficar recolhido na borda da tela e expandir quando há progresso, falha ou pedido de intervenção. É melhor tratá-lo como componente de status contínuo do que como janela tradicional. citeturn19view0turn19view3

A **captura contextual** precisa ser deliberada e visível. Em Windows, `Windows.Graphics.Capture` chama UI segura do sistema para o usuário escolher janela ou monitor, e ainda desenha uma borda colorida ao redor do item capturado. Em Linux/Wayland, o caminho correto é `ScreenCast`/`Screenshot` via portal, com seleção de fontes, sessão e restore tokens quando necessário. Para o ATLAS, isso significa: nada de captura silenciosa implícita no MVP; sempre picker, sempre indicador de privacidade, sempre contexto claro do que está sendo compartilhado. citeturn22view0turn22view1turn22view3turn22view4

Por fim, o overlay precisa exibir **indicadores permanentes de privacidade**: microfone ativo, captura ativa, local-only vs cloud, egress de rede, modo de logs, e se o operador está compartilhando janela, monitor ou só texto/clipboard. Isso não é excesso de zelo. Em um produto que quer lembrar, agir e capturar contexto, sinais de confiança têm de ser parte da UX principal. As APIs modernas de captura em Windows e Linux já andam nessa direção; o ATLAS deve reforçar essa visibilidade, não escondê-la. citeturn22view0turn22view4

## Windows, Linux e Odysseus

### Windows e Linux

**Windows** é o alvo mais forte para o primeiro desktop sidecar do ATLAS. O ecossistema de hotkeys globais, janelas topmost, layered windows e APIs modernas de captura é estável, documentado e maduro. `RegisterHotKey` resolve o gatilho global; `HWND_TOPMOST` e layered windows resolvem boa parte da mecânica de HUD; `Windows.Graphics.Capture` traz picker seguro e indicador visual; e `Desktop Duplication API` pode ficar reservado para cenários avançados de captura de alta frequência. Além disso, o backend ONNX/DirectML/WinML dá uma história decente para máquinas sem CUDA. citeturn26search6turn28search2turn29search3turn22view0turn22view2turn21view3

Em **Linux**, a situação é mais fragmentada. Em X11, atalhos globais e certos padrões de overlay ainda são mais simples, mas o futuro do desktop Linux é Wayland. Em Wayland, o que interessa ao ATLAS é aceitar a realidade: hotkeys e captura passam por portais/compositor, e overlay real pede `wlr-layer-shell` ou equivalente. O portal `GlobalShortcuts` já define sessões e sinais de ativação; o portal `ScreenCast` já define sessões, fontes e persistência; e o projeto `xdg-desktop-portal-hyprland` declara explicitamente suporte a screensharing e global shortcuts no ecossistema Hyprland. Isso faz do **Hyprland um bom alvo beta para operadores avançados**, muito mais do que um “Linux genérico” abstrato. citeturn27view0turn22view4turn27view1turn27view2turn23view0turn26search12

A implicação prática é esta: o ATLAS desktop deve nascer com **matriz oficial de suporte**, não com promessa vaga. Algo como “Windows 11 suportado de verdade; Linux X11 suportado; Hyprland suportado em beta; outros Wayland compositors com degradação funcional previsível”. Isso é muito melhor do que vender uma compatibilidade falsa com “Linux” e depois descobrir, tarde demais, que `always_on_top`, click-through e hotkeys se comportam de forma diferente em cada compositor. citeturn24search11turn27view0turn23view0

### Resumo da auditoria do Odysseus

Como referência conceitual, o **Odysseus** é útil porque explicita um espaço de produto próximo: um workspace de IA self-hosted, local-first, com UI tipo ChatGPT/Claude, chat, agente, cookbook de modelos, deep research, documentos, memória, email, notas, calendário e suporte móvel/PWA. O repositório também mostra um stack fortemente web/service-oriented, com `FastAPI`, `uvicorn`, `chromadb-client`, `fastembed`, `caldav` e `mcp`, o que o posiciona claramente como workspace self-hosted, não como sidecar nativo de baixa latência. citeturn14view2turn15view0

Há ideias muito boas para adaptar. A melhor delas é o **threat model explícito**: o documento descreve o produto como console de administração com acesso local privilegiado, define fronteiras de confiança, distingue admin de non-admin e chama atenção para o risco de prompt injection vindo de conteúdo não confiável. A segunda boa ideia é o **companion bridge** com pareamento por token de uso único e postura de CSRF clara. A terceira é o **“cookbook” orientado ao hardware**, que reconhece que UX de inferência local melhora muito quando o sistema recomenda modelos e backends adequados à máquina. citeturn14view0turn16view0turn14view1

Mas também há lições negativas. O próprio roadmap do Odysseus admite bugs, comportamento estranho de CSS/layout, necessidade de smoke tests multiplataforma e confiabilidade irregular do cookbook em máquinas diferentes. Isso evidencia um risco clássico de workspaces AI ricos: quando tudo vira uma grande aplicação web local com integrações demais, o projeto cresce rápido em superfície antes de estabilizar a fundação operacional. Para o ATLAS, o aprendizado é claro: **copiar ideias de produto, não a forma arquitetural**. O cockpit WebUI pode absorver boas ideias do Odysseus; o sidecar nativo do ATLAS deve seguir outro caminho. citeturn14view1turn15view0

## Riscos

**Fragmentação de Wayland e sobreposição real.** Em Wayland, `always_on_top` em stacks como `tao/winit` não resolve o caso de HUD universal, e hotkeys globais portáveis continuam dependentes de portal/compositor. Mitigação: layer-shell como caminho nobre; portal fallback como degradação; suporte oficial explícito por compositor, começando por Hyprland e X11. citeturn24search11turn23view0turn27view0turn27view1

**Misturar demais o runtime Python com UX de baixa latência.** O Hermes é um ótimo fundamento de agente, mas seus perfis/gateways/processos mostram que o papel do runtime já é amplo. Se o desktop depender diretamente dele para hotkeys, aprovação e áudio em tempo real, o ATLAS vai carregar latência e fragilidade desnecessárias. Mitigação: broker residente em Rust entre operador e runtime. citeturn19view0turn19view2turn19view3

**Superfície de ataque em captura, aprovação e automação.** O threat model do Odysseus deixa claro o que acontece quando um workspace local possui poderes administrativos amplos. O ATLAS vai além, porque quer overlay, captura e voz. Mitigação: threat model formal desde o início, prompts nativos, tickets de aprovação, capability scoping no IPC e indicadores constantes de privacidade. citeturn14view0turn36view0turn22view0turn22view4

**Empacotamento de modelos e footprint.** `faster-whisper` pode ser muito eficiente, mas modelos grandes continuam pesados; `whisper.cpp` melhora portabilidade, mas qualidade/latência variam por dispositivo; Piper tem risco de manutenção por repositório arquivado. Mitigação: workers sob demanda, presets por hardware, fallback explícito, versionamento de assets e vendor/fork dos componentes críticos de voz. citeturn21view0turn21view1turn40view0

**Acessibilidade e navegação por teclado em toolkits customizados.** `egui` já se beneficia de AccessKit, mas `iced` ainda trata acessibilidade como área em aberto, e qualquer fuga para `wgpu` puro aumenta o trabalho manual. Mitigação: escolher Slint como base pública, manter AccessKit no radar, e tratar acessibilidade como critério de arquitetura, não como trabalho de pós-MVP. citeturn37search0turn38search0turn37search7

**Deriva entre cockpit e sidecar.** Se WebUI e nativo implementarem estados, ações e regras diferentes, o produto vira dois ATLAS. Mitigação: um só event schema, uma só policy layer, um só model de approval e contratos de capability comuns entre sidecar, runtime e WebUI. citeturn36view0turn19view3

## Plano de MVP

**MVP de fundação.** Entregar `atlas-desktop` em Rust como processo residente com tray, hotkey global, command palette, notificações nativas, prompts de aprovação, stream de eventos e integração local com `atlas-runtime`. O cockpit continua browser-first; opcionalmente ganha um wrapper Tauri simples como “janela oficial” do produto. Nesta fase, o foco deve ser **Windows primeiro**, com Linux rodando sem promessas fortes de overlay avançado. citeturn34view3turn36view2turn26search6turn19view0

**MVP de voz.** Adicionar push-to-talk, buffer de áudio, STT com `faster-whisper` e `whisper.cpp` fallback, além de TTS local inicial. O comportamento de streaming por sentença já conhecido no Hermes deve ser reproduzido no sidecar, mas com telemetria local de latência e descarte de workers ociosos. Nesta fase, vale incluir só o mínimo de UX: listening strip, parciais, interrupção de TTS e colagem do texto final na palette. citeturn19view1turn20view0turn21view0turn21view1turn40view0turn40view1

**MVP de captura e contexto.** Implementar captura explícita de janela/monitor por picker do sistema, clipboard/context chips e associação com runs/approvals. Em Windows, usar `Windows.Graphics.Capture`; em Linux/Wayland, usar `ScreenCast`/`Screenshot` via portal. Nada de captura contínua silenciosa ainda. O objetivo aqui é colocar o operador no controle e construir a gramática de contexto do ATLAS sem abrir dívida de privacidade. citeturn22view0turn22view3turn22view4

**MVP de Linux dirigido.** Tornar X11 suportado o bastante para palette/tray e abrir beta oficial de Hyprland com portais e, quando necessário, surfaces layer-shell. Não prometer suporte homogêneo a todos os compositors Wayland no início. A documentação de instalação e de “known-good environments” deve ser parte do produto, não um apêndice. citeturn27view1turn23view0turn27view0

**Roadmap posterior.** Depois do MVP, entram: wake word opcional com indicador permanente; worker Parakeet para streaming parcial premium; camada Windows ONNX/WinML mais madura; overlay click-through avançado por plataforma; briefings “Pulse” em HUD; pareamento seguro com companion móvel seguindo a lógica de token temporário vista no Odysseus; e, mais à frente, eventual embedding de superfícies web específicas em shell nativo caso a trilha Slint+Servo amadureça o suficiente para produção. citeturn21view2turn21view3turn16view0turn33view0

O corte entre MVP e “depois” deve ser defendido com disciplina. **Não** coloque wake word, overlay universal Wayland, captura contínua, cockpit nativo completo e múltiplos backends de voz pesados na primeira entrega. O que valida o desktop do ATLAS não é a quantidade de features; é provar, cedo, que ele é **mais rápido, mais leve, mais confiável e mais operável** do que uma wrapper WebView inchada. citeturn34view3turn35view0turn35view1