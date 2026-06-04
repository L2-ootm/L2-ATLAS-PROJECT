# Estratégia desktop nativa em Rust para o L2 ATLAS

## Recomendação executiva

A melhor estratégia para o ATLAS é **não** construir um “app GUI que chama Hermes como subprocesso opaco”, e sim evoluir o próprio Hermes para virar o **atlas-core**, um runtime headless e persistente, enquanto o desktop vira um cliente nativo especializado em latência, captura, voz, aprovações e presença no sistema operacional. Essa separação respeita o que o Hermes já faz bem — delegação de subagentes com contexto isolado, override de modelo/provedor e scheduler/cron embutido — e evita recriar no frontend aquilo que já existe no runtime. citeturn21view0turn21view1turn20search0

Para a camada desktop, eu recomendo uma arquitetura **Rust-first, Slint-first, WebUI-separate**. Em termos práticos: use **Slint** como toolkit nativo principal para palette, popovers, prompts de aprovação, settings e pequenos painéis; use **APIs nativas + winit/wgpu** apenas onde overlay, captura, z-order, click-through, PipeWire/Wayland e Win32 exigirem controle fino; mantenha o **cockpit web** como browser-first e só empacote esse cockpit com **Tauri** mais tarde, se houver ganho real de distribuição; e trate **Electron** apenas como baseline negativo, porque ele embute Chromium e Node.js e herda a arquitetura multiprocesso do Chromium, enquanto Tauri usa WebViews do sistema e Slint compila UI nativa. citeturn37search0turn37search1turn22view1turn19view1turn33search0turn33search8

Também recomendo separar a voz em dois planos. O plano “always-on” e barato deve ficar em Rust/ONNX, com VAD, hotkey e KWS leves; o plano “transcrição séria” deve ficar isolado em um worker dedicado, porque o ecossistema de **faster-whisper**, **Whisper** e **Parakeet/NeMo** traz dependências e matrizes de aceleração que você não quer misturar ao processo de UI. Para o MVP, o default mais pragmático é **faster-whisper**; para um caminho RTX/NVIDIA de alto desempenho, **Parakeet**; e para caminhos realmente nativos e embutíveis em Rust, **sherpa-onnx** para VAD/KWS/streaming ASR/TTS. citeturn12view0turn12view1turn25view1turn25view3turn12view7turn34view0

## Matriz comparativa de UI em Rust

As opções relevantes para o ATLAS se dividem em três grupos. O primeiro é o de toolkits Rust reais: **Slint**, **egui** e **iced**. O segundo é o de blocos de baixo nível: **wgpu/winit** e as APIs nativas de sistema. O terceiro é o de shells web com backend Rust, onde **Tauri** é a opção séria e **Electron** é o baseline de custo alto. Slint se apresenta como toolkit declarativo para GUIs nativas em desktop/mobile/embedded; egui é immediate-mode puro em Rust e tem integração com AccessKit via eframe; iced é multiplataforma e type-safe, mas a própria documentação o chama de software experimental. citeturn37search0turn37search1turn17search9turn18view0turn36search2turn36search9

Para ATLAS, isso importa porque immediate-mode é ótimo para painéis de inspeção e ferramentas de operador, mas menos natural quando você quer shell desktop polido, acessível e estável por anos. Além disso, o AccessKit lista integração já existente com **egui** e **Slint**, enquanto o iced não aparece nessa lista. Isso não torna o iced inviável, mas torna seu risco de produto maior para um cockpit que precisa parecer “serious software” e não protótipo. citeturn18view1turn18view0turn36search9

Do lado dos shells web, Tauri é tecnicamente muito melhor alinhado ao ATLAS do que Electron porque aproveita **WebView2 no Windows** e **WebKit/WKWebView no Linux/macOS**, em vez de carregar um Chromium completo dentro do binário; além disso, ele tem um sistema explícito de permissions/capabilities e suporte formal a sidecars. Mas a própria documentação de Tauri deixa claro que o event system não é para tráfego de alta taxa/baixa latência e que, no Linux, as versões de WebKitGTK variam por distro. Ou seja: **Tauri serve para empacotar o cockpit**, não para virar a base do overlay/voz/imediatismo. citeturn22view1turn11view2turn19view0turn19view1turn22view0

| Opção | Leitura arquitetural | Onde brilha no ATLAS | Limitação decisiva | Papel recomendado |
|---|---|---|---|---|
| **Slint** | Toolkit declarativo, nativo, voltado a desktop/mobile/embedded | Palette, popovers, prompts de aprovação, mini painéis, settings, shell nativo enxuto | Overlay Wayland/Win32 muito específico ainda pode exigir escape hatch nativo | **Escolha principal para a UI nativa** |
| **egui** | Immediate-mode puro em Rust | Ferramentas internas de operador, inspeção, debug views, utilitários rápidos | Docs em “heavy development” e ergonomia menos ideal para shell polido de produto | **Útil como UI secundária de tooling**, não como shell principal |
| **iced** | GUI reativa/type-safe multiplataforma | Apps desktop Rust puros com modelo Elm-like | A própria docs dizem que é “experimental software” | **Não recomendada como base principal hoje** |
| **custom wgpu + winit** | Base gráfica/loop de janela, não um toolkit de widgets | HUDs altamente customizados, renderização rica, superfícies especiais | Você herda IME, acessibilidade, foco, widgets, menus, drag, hit-testing | **Use só onde overlay exigir controle absoluto** |
| **APIs nativas** | Win32/WinUI no Windows; GTK/libadwaita/Qt etc. no Linux | Integração profunda com SO, z-order, captura, notificações, input | Alto custo de manutenção e risco de bifurcar a base entre Windows/Linux | **Use como camada adaptadora, não como estratégia geral** |
| **Tauri thin shell** | Shell de WebView com backend Rust e capabilities | Empacotar o cockpit web local, menus, tray, distribution story | WebView, IPC JSON/eventos, restrições de throughput e variabilidade no Linux | **Opcional para o cockpit; não para overlay/voz** |
| **Electron** | Chromium + Node embutidos, modelo multiprocesso estilo browser | Só quando a prioridade absoluta for reutilizar stack web e aceitar custo alto | Vai na direção oposta da meta de RAM/latência do ATLAS | **Evitar** |

A decisão prática, portanto, é simples: **Slint como padrão; winit/native APIs nas bordas; Tauri apenas como casca opcional do cockpit; Electron descartado; egui reservado para tooling interno**. citeturn37search0turn18view0turn19view1turn33search8

## Metas de desempenho

As metas abaixo são **metas de produto propostas**, não garantias de framework. Eu as separaria por processo, porque misturar “UI nativa”, “cockpit web” e “worker de voz” em um único orçamento leva a decisões ruins.

| Métrica | Meta proposta para MVP | Meta proposta para V1 | Observação |
|---|---|---|---|
| **Cold start do atlas-native até ícone na bandeja** | `< 500 ms p50`, `< 900 ms p95` | `< 350 ms p50`, `< 700 ms p95` | Sem pré-carregar o cockpit web |
| **Abertura da command palette por hotkey** | `< 70 ms p95` | `< 50 ms p95` | Da tecla à primeira pintura |
| **Prompt de aprovação aparecer** | `< 100 ms p95` | `< 80 ms p95` | A partir do evento vindo do core |
| **Overlay/HUD redraw** | 60 FPS quando visível | 60 FPS sustentados | Zero redraw quando oculto |
| **RAM idle do atlas-native** | `< 90 MB p50`, `< 140 MB p95` | `< 70 MB p50`, `< 120 MB p95` | Sem worker de fala carregado |
| **RAM do atlas-native com overlay visível** | `< 150 MB p95` | `< 120 MB p95` | Inclui um HUD e uma janela de approval |
| **CPU idle do atlas-native** | `< 1%` média | `< 0,5%` média | Sem captura/voz sempre ligada |
| **CPU em modo ‘armed’ com VAD/KWS** | `< 3%` média em notebook comum | `< 2%` média | Sem inferência pesada ativa |
| **STT parcial após início da fala** | `< 350 ms` GPU / `< 800 ms` CPU | `< 250 ms` GPU / `< 600 ms` CPU | Para comandos curtos |
| **STT final após fim da fala** | `< 800 ms` GPU / `< 1,5 s` CPU | `< 500 ms` GPU / `< 1,0 s` CPU | Frases curtas |
| **TTS até primeiro áudio** | `< 250 ms` quente / `< 600 ms` frio | `< 150 ms` quente / `< 400 ms` frio | Local/offline |
| **Cockpit web local até FMP** | `< 2,0 s p95` | `< 1,5 s p95` | Processo separado ou browser já aberto |

Em termos de orçamento, eu deixaria três budgets independentes. **atlas-native** tem budget duro e pequeno. **atlas-web** pode ser mais pesado, porque é uma superfície de dashboards/tabelas/logs. **atlas-speech-worker** tem budget elasticamente maior, porque o custo real depende de modelos carregados, aceleração disponível e quantização. O erro clássico aqui seria tentar fazer o processo que pinta uma approval toast também carregar um stack Whisper/NeMo/CUDA. Isso é justamente o que o desenho em sidecar/worker evita. citeturn19view1turn24view4turn25view3turn11view8

## Arquitetura nativa

O desenho recomendado para o ATLAS desktop é um **3+1**:

```text
atlas-core                atlas-native                atlas-web
(Hermes estendido)        (Rust, user-session)        (browser ou shell opcional)
headless, persistente     sempre ativo                dashboards e cockpit
│                         │                           │
├─ scheduler / pulse      ├─ tray / hotkeys          ├─ runs / audit / wiki / CRM
├─ memory / wiki / CRM    ├─ command palette         ├─ dashboards / briefings
├─ subagents / model routing ├─ overlays / approvals ├─ diff review / search
├─ audit log / state      ├─ notifications           └─ integrações e administração
├─ tool execution         ├─ mic / capture / context
└─ IPC server             └─ speech router
                               │
                               └─ atlas-speech-worker
                                  (faster-whisper / Parakeet / sherpa-onnx)
```

O **atlas-core** deve ser um fork/evolução do Hermes, não um wrapper em torno dele. O motivo é simples: Hermes já tem runtime de agente, sessões, perfis, cron, toolsets, delegação com isolamento de contexto e possibilidade de usar modelos/provedores diferentes nos subagentes. Para ATLAS, o trabalho certo não é substituir isso desde o desktop; é acrescentar **event journal, approval state machine, pulse engine, wiki/CRM state, policy tags e contratos de UI** em cima desse núcleo. citeturn21view0turn21view1turn20search7

No plano de IPC, eu recomendo **pipe local tipado e autenticado**, não localhost TCP para operações privilegiadas. Em Windows, isso significa **Named Pipe** com ACL restrita ao SID do usuário atual; em Linux, **Unix Domain Socket** dentro de `XDG_RUNTIME_DIR` com permissões `0600`. O wire format deve ser binário e versionado — protobuf é a escolha mais pragmática por ser fácil de compartilhar entre Rust e Python — enquanto a trilha de auditoria continua em formato amigável a replay e inspeção, como JSONL/SQLite. Isso conversa bem com a disciplina de logs e recovery já presente no histórico do projeto.  

O stream em si deve ser explicitamente separado por criticidade. **Eventos confiáveis**: approvals, tool-results, state transitions, alerts, permission grants. **Eventos de alta frequência e tolerantes a perda**: speech partials, progress ticks, telemetry curta, overlay hints. Essa distinção é importante porque, se ATLAS usar um shell Tauri mais tarde, a própria documentação do Tauri diz que o event system foi pensado para pequenas quantidades de dados e padrão multi-consumer, não para baixa latência / alto throughput; para streaming, o caminho documentado é channels. citeturn19view1

As aprovações devem passar por um fluxo nativo, não por modal web. Minha recomendação é que o core emita um `ApprovalRequest` assinado por política, com resumo curto, risco, alvos, diff/preview e prazo. O desktop devolve um `Grant`, `Deny` ou `Escalate`, também registrado no journal. Operações de risco maior podem exigir **reconfirmação contextual**: por exemplo, “abrir diff”, “mostrar comando”, “explicar por que será feito”, e só então aprovar. Esse é o lugar certo para incorporar as políticas seguras herdadas do L2-Atlas antigo.

## Fronteira entre WebUI e nativo

A fronteira correta entre WebUI e nativo no ATLAS não é “o que dá para fazer em React”. É **o que precisa de latência, presença de SO e ergonomia imediata** versus **o que precisa de densidade informacional e navegação rica**.

| WebUI cockpit | Nativo desktop |
|---|---|
| Missões, runs, timeline, auditoria detalhada | Hotkeys globais, palette, bandeja, notificações |
| Wiki persistente, CRM, relacionamentos, diffs, pesquisas | Approvals rápidos, HUD de status, contexto ativo |
| Dashboards de pulse, briefings, integrações, setup denso | Microfone, captura de tela/janela, recorte de contexto |
| Visualização remota em browser, links, compartilhamento | Voz em tempo real, TTS local, indicadores de privacidade |
| Ferramentas com tabela, filtros, múltiplos painéis | Precisão de z-order, focus, OS APIs e presença contínua |

Isso significa que o **cockpit deve ser browser-first** por padrão. O item “Abrir Cockpit” do tray abre o browser do usuário em `localhost` ou numa URL remota autenticada do próprio ATLAS. Se, mais tarde, houver valor real em empacotar isso como app desktop, aí sim vale um shell Tauri. O ganho dessa abordagem é manter o processo nativo pequeno e evitar que a inicialização do sistema dependa do custo de um WebView. Ao mesmo tempo, Tauri continua útil como opção futura porque consegue usar WebView do sistema, capabilities por janela e sidecars formalizados. citeturn22view1turn11view2turn19view0

Também é importante não despejar telemetria fina no layer web. Logs de passo a passo, frames do HUD, speech partials e indicadores de presença devem ficar no desktop nativo; a WebUI só recebe estados consolidados e páginas de leitura. Isso reduz jitter, simplifica segurança e evita que o cockpit vire dono do runtime de interação.

## Pipeline de STT/TTS

O pipeline de voz do ATLAS deve ter **duas velocidades**. A primeira é o plano “always-on/control plane”: hotkey, VAD, wake word opcional, partials curtos, TTS rápido, tudo sem travar o shell. A segunda é o plano “serious transcription”: workers dedicados, com aceleração e modelos maiores, isolados do processo de UI.

No gatilho, o **MVP deve começar com push-to-talk e hotkey global**, não wake word por padrão. Em Windows, o caminho mais simples é `RegisterHotKey`, e quando for preciso maior fidelidade de input, a própria documentação da Microsoft aponta **Raw Input** como caminho robusto para receber input bruto de HID; a documentação dos low-level keyboard hooks diz explicitamente que, na maioria dos casos, é melhor monitorar raw input do que depender de low-level hooks. Em Linux, o cenário muda: o crate `global_hotkey` suporta Linux **X11 only**, então Wayland pede outro caminho, como o **GlobalShortcuts portal**; e, em Hyprland, o XDPH já expõe screensharing e global shortcuts. citeturn27view5turn30search1turn14search3turn27view3turn11view3turn31view0

No reconhecimento, o **default do MVP deve ser faster-whisper**. O projeto o descreve como uma reimplementação de Whisper em CTranslate2, com benchmarks próprios mostrando até 4x mais velocidade com menos memória, além de suporte a quantização INT8 em CPU/GPU. Ele também tem VAD integrado, word timestamps e um deployment um pouco mais simples do que o `openai-whisper` clássico, porque usa PyAV e não exige FFmpeg instalado no sistema. Já o Whisper “puro” continua importante como baseline de qualidade e compatibilidade: é multilíngue, foi treinado em 680 mil horas de dados e expõe um espectro claro de modelos e requisitos de VRAM — de ~1 GB nos modelos tiny/base a ~10 GB no large, com `turbo` em ~6 GB. citeturn12view0turn24view4turn23view3turn12view1turn24view1turn9search11

Para um caminho premium em NVIDIA, **Parakeet** merece entrar, mas como **perfil de hardware**, não como dependência universal. O **Parakeet TDT 0.6B v2** é excelente para inglês, com timestamps e throughput muito alto; já o **Parakeet-RNNT-1.1B** suporta 25 idiomas, incluindo **pt-BR**, o que o torna muito mais relevante para um produto real do que o TDT inglês-only. O problema é operacional: NeMo/NIM/RTX são uma aposta ótima para máquinas certas, mas um péssimo denominador comum para Windows+Linux genéricos. E o modelo multitalker/streaming da NVIDIA exige **uma instância por locutor**, o que o empurra naturalmente para roadmap posterior. citeturn25view1turn25view2turn25view3turn25view4

Para o plano sempre ligado e Rust-native, o caminho mais elegante hoje é **sherpa-onnx**. As bindings oficiais em Rust já cobrem **streaming ASR, offline TTS, VAD, keyword spotting, diarização e denoising**, com linking estático por padrão. A documentação também mostra `OnlineRecognizer`, `KeywordSpotter`, `VoiceActivityDetector` e `OfflineTts`, o que faz dele um encaixe natural para a borda “sempre ativa, baixa latência, offline, embutível” do ATLAS. O projeto ainda cataloga modelos de TTS/ASR/VAD/KWS, inclusive ecosistema Piper/VITS/Matcha/Kokoro via ONNX. citeturn12view7turn23view5turn23view6turn23view7turn34view0turn26view1

A política de aceleração deve ser simples. **NVIDIA**: faster-whisper/Parakeet em worker dedicado. **Windows sem NVIDIA**: para modelos ONNX, prefira a estratégia **Windows ML**, porque a própria Microsoft posiciona Windows ML como a camada unificada/high-performance para inferência local em NPU/GPU/CPU com runtimes e execution providers gerenciados pelo sistema; já o DirectML EP continua suportado, mas está em sustained engineering, com desenvolvimento novo migrando para Windows ML. **Linux sem NVIDIA**: ONNX CPU first; aceleração específica só quando trouxer benefício líquido real. E, seja qual for o backend, preserve **fallback de CPU** sempre. citeturn11view8turn11view7turn11view9

No TTS, eu recomendaria **local por padrão**. O MVP não precisa de voz “showroom”; precisa de voz rápida, privada e previsível. Piper é um candidato forte para isso, e o sherpa-onnx já oferece TTS offline integrado e ecossistema de modelos por ONNX. O shell nativo deve fazer streaming do áudio em chunks e começar a tocar assim que o primeiro buffer útil sair, em vez de esperar o texto inteiro. Cloud TTS pode existir depois, como rota opcional por política/performance, nunca como dependência da experiência básica. citeturn12view4turn12view7turn26view1

## Modelo de overlay e auditoria de Odysseus

O overlay do ATLAS deve ser um **HUD operativo**, não uma mini área de trabalho. Ele precisa ocupar pouco espaço mental e desaparecer rápido. Eu desenharia cinco superfícies nativas:

| Superfície | Trigger | Conteúdo | Duração/persistência |
|---|---|---|---|
| **Command palette** | Hotkey global | Busca de ações, entidades, runs, pessoas, missões | Persistente até ação/cancelamento |
| **Approval prompt** | Evento do core | Resumo, risco, alvo, diff/preview, botões claros | Modal curto, prioridade alta |
| **Run chip / pulse chip** | Execução ativa | Estado, progresso, erro, SLA, fonte do modelo | Flutuante e compacta |
| **Voice orb / transcript strip** | PTT ou wake | VAD, parcial de STT, rota local/cloud, mute | Visível só durante voz |
| **Context capture strip** | Captura ativa | O que está sendo capturado, janela alvo, privacidade | Sempre explícita enquanto ativa |

Em Windows, isso pede janelas com semântica explícita de overlay: **topmost**, potencialmente **layered**, muitas vezes **tool window** e **no-activate**, controladas por Win32/Windows-rs. `SetWindowPos(HWND_TOPMOST)` dá o comportamento de ficar acima das janelas normais, e as extended window styles documentam `WS_EX_LAYERED`, `WS_EX_TOOLWINDOW` e `WS_EX_NOACTIVATE`. Para screen/window capture, o caminho correto é o **GraphicsCapturePicker**, que usa UI segura do sistema e ainda desenha a conhecida borda amarela no item capturado — um excelente indicador de privacidade que o ATLAS deve respeitar e complementar, não esconder. citeturn27view4turn32view0turn11view6turn18view3

Em Linux/Wayland, o desenho muda. Para HUDs “presos ao desktop” em compositores wlroots/Hyprland-like, o protocolo certo é o **layer-shell**, que cria superfícies com z-depth definido e semântica de input própria. Para compartilhamento de janelas/telas, o caminho robusto é o **ScreenCast portal**; para atalhos globais, o **GlobalShortcuts portal**; e para cenários mais avançados de captura de input, o **InputCapture portal**, sempre lembrando que, em Wayland, é o compositor que decide quando ativar a captura. No Hyprland, o **xdg-desktop-portal-hyprland** já implementa screensharing e global shortcuts, e sua própria wiki documenta que SHM é mais lento que DMA-BUF quando entra como fallback — detalhe importante para uso real em overlay/captura. citeturn11view4turn15search0turn11view3turn27view0turn31view0

Sobre o **Odysseus**, meu resumo é: vale a pena estudá-lo como **referência conceitual de workspace/ops console**, mas não como arquitetura a copiar. Há três ideias muito boas ali: a disciplina de **security policy/threat model** como documentação de produto; a divisão explícita entre **admin** e **non-admin** capabilities; e a decisão de tratar várias superfícies externas como **untrusted context** com hardening contra prompt injection. Tudo isso combina muito bem com o ATLAS. citeturn8view2turn8view1turn8view7

Mas os riscos documentados pelo próprio projeto são exatamente os que o ATLAS não deve importar. O threat model admite que Odysseus é pensado para usuários confiáveis em rede privada, “treat it like an admin console”, com shell, filesystem, email e MCP liberados para admin; também documenta como known gap a ausência de sandbox real para shell/filesystem. O roadmap, por sua vez, lista contexto/prompt bloat, necessidade de smoke tests cross-platform, fragilidade de layout/CSS e necessidade de audit de integrações. Em outras palavras: **a disciplina documental é excelente; a fronteira de confiança é permissiva demais para o ATLAS; e a dívida de confiabilidade é um alerta importante**. citeturn8view2turn8view4turn7view0

## Riscos e plano MVP

Os principais riscos do desktop ATLAS não são “qual toolkit tem widget bonito”. Eles são **fragmentação de plataforma, acoplamento incorreto de processos, e vazamento de privilégios**.

| Risco | Por que importa | Mitigação recomendada |
|---|---|---|
| **Wayland não se comporta como X11** | Global hotkeys e captura global não podem depender só de crates X11; o crate `global_hotkey` documenta Linux/X11 only, enquanto Wayland empurra para portais/suporte do compositor | Ter backend Wayland explícito desde o início: GlobalShortcuts + ScreenCast + InputCapture + adaptações Hyprland/XDPH |
| **Shell web virando caminho crítico** | Tauri depende de WebViews do sistema e, no Linux, WebKitGTK varia por distro; isso é ruim para overlay/voz/hotkeys críticos | Browser-first para cockpit; processo nativo separado para latência/imediatismo |
| **Matriz CUDA/cuDNN quebrando UX** | O faster-whisper documenta dependência atual de CUDA 12/cuDNN 9 nas versões recentes do CTranslate2 | Isolar ASR pesado em worker próprio; detectar hardware; fallback CPU sempre pronto |
| **Apostar demais em DirectML específico** | ONNX Runtime diz que o DirectML EP segue suportado, mas desenvolvimento novo migrou para Windows ML | Em Windows, preferir Windows ML para caminhos ONNX quando viável |
| **Context/prompt bloat em runtime de agente** | O próprio roadmap do Odysseus lista isso como problema real; e ATLAS será ainda mais amplo em wiki/CRM/pulse | Tool disclosure progressivo, controle de contexto por superfície e resumo/auditoria de eventos |
| **Ferramentas privilegiadas expostas ao conteúdo externo** | O threat model do Odysseus mostra exatamente essa classe de risco com prompt injection e shell/admin tools | Enforcement por política no core, approvals nativos, rotulagem de conteúdo não confiável, sandbox de tool execution |

citeturn27view3turn11view3turn22view0turn24view4turn11view7turn11view8turn7view0turn8view1

O **MVP** que eu faria é enxuto e agressivamente focado no que o ATLAS precisa para “parecer sistema operacional” em vez de “parecer dashboard”.

| Fase | Entrega | Escopo |
|---|---|---|
| **MVP de fundação** | `atlas-core` sobre Hermes | Event journal, approval API, pulse hooks, scheduler preservando cron do Hermes, delegação preservando subagentes/model routing |
| **MVP desktop** | `atlas-native` em Rust + Slint | Tray, hotkey global, command palette, approval prompt, notificações, run chip |
| **MVP voz** | Worker local pragmático | faster-whisper como default; sherpa-onnx para VAD/KWS/TTS leve; PTT por padrão |
| **MVP cockpit** | WebUI browser-first | Runs, audit, pulse, wiki básica, CRM mínimo, integrações essenciais |
| **MVP plataforma** | Windows first-class + Linux first-class com tiers | Windows completo; Linux com X11 e Wayland básicos; Hyprland validado cedo para share/shortcuts |
| **Depois do MVP** | Roadmap premium | Wake word sempre ligado, overlay mais rico, caret/window anchoring, Parakeet para perfis RTX, shell Tauri opcional do cockpit, multitalker/diarização, captura contextual avançada |

Esse roadmap funciona porque reaproveita o que Hermes já oferece, mantém a UI nativa pequena, e adia as partes de maior entropia — wake word sempre ligado, overlay sofisticado em Wayland, Parakeet multitalker, shell web empacotado — para quando o núcleo de ATLAS já estiver estável. Em outras palavras: **primeiro faça o desktop ser rápido, auditável e confiável; depois faça-o ser bonito; por último faça-o ser mágico**. citeturn21view0turn21view1turn19view1turn25view4