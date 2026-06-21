"""
L2 SYSTEMS // Channel Welcome Messages
All messages in Portuguese-BR with professional Discord formatting.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# PROTOCOLS CHANNEL - Full Syntax Guide
# ═══════════════════════════════════════════════════════════════════════════════

PROTOCOLS_MESSAGES = [
    # Message 1: Header
    """# 📜 L2 PROTOCOLS // v.1.0
## GUIA DE SINTAXE E FORMATAÇÃO PROFISSIONAL

> A clareza na comunicação assíncrona é **inegociável**. Este guia define o padrão visual para mensagens dentro do ecossistema L2. O objetivo é maximizar a relação **sinal/ruído**.

*Ler uma mensagem no Mainframe deve ser tão eficiente quanto ler um log de sistema limpo.*""",

    # Message 2: Basic Toolkit
    """## 🛠️ O TOOLKIT BÁSICO

Dominar estas quatro ferramentas é **obrigatório** para todo co-founder.

### 1️⃣ **Negrito (Bold)**
- **Sintaxe:** Usar asteriscos duplos. `**Texto**`
- **Uso L2:** Apenas para **Títulos**, **Cabeçalhos de Seção** ou **Alertas Críticos**. Não use para ênfase comum no meio de frases.

### 2️⃣ *Itálico (Italic)*
- **Sintaxe:** Usar asteriscos simples. `*Texto*`
- **Uso L2:** Para ênfase sutil, notas secundárias ou termos em outro idioma que não sejam técnicos. *(Ex: status quo)*.

### 3️⃣ `Monospace (Código)`
- **Sintaxe:** Usar crases. `` `Texto` ``
- **Uso L2 (CRÍTICO):** Obrigatório para **qualquer** dado técnico. IDs, URLs, trechos de código, chaves de API, valores monetários exatos, ou nomes de variáveis.
- **Exemplo:** O cliente ID `cli_99823` reportou erro no endpoint `/v1/webhooks`.

### 4️⃣ ~~Tachado (Strikethrough)~~
- **Sintaxe:** Usar til duplo. `~~Texto~~`
- **Uso L2:** Para indicar tarefas concluídas em uma lista ou informações depreciadas que não devem ser apagadas para manter o histórico.""",

    # Message 3: Structure & Hierarchy
    """## 📐 ESTRUTURA E HIERARQUIA

> Uma mensagem longa sem estrutura **será ignorada**.

### A. Listas e Bullets
Use hífen `-` ou emojis técnicos (▪️, ▫️, 👉) para quebrar a complexidade.
- Evite blocos de texto com mais de 4 linhas.
- Se tem mais de 2 itens, vira uma lista.

### B. Citações (Quotes)
Use o sinal de maior `>` para responder a pontos específicos ou trazer contexto externo.
> "O cliente disse que o sistema caiu."

Na verdade, os logs mostram que a internet deles caiu.

### C. Espaçamento (Respiro)
Use linhas em branco para separar seções distintas de uma mesma mensagem. O espaço em branco é **funcional**.""",

    # Message 4: Emoji Protocol
    """## 🚨 PROTOCOLO DE EMOJIS (STATUS)

> Emojis na L2 **não são decoração**. São indicadores visuais de estado.

| Emoji | Status | Uso |
|:---:|:---:|:---|
| 🔴 | **CRÍTICO/BLOCANTE** | Exige atenção imediata. (Ex: Sistema fora do ar) |
| 🟡 | **ATENÇÃO/RISCO** | Algo que pode virar problema se ignorado. |
| 🟢 | **RESOLVIDO/ESTÁVEL** | Confirmação de conclusão ou boas notícias. |
| ⚙️ | **EM PROGRESSO** | Task sendo executada ativamente. |
| 💡 | **INSIGHT/IDEIA** | Sugestão estratégica sem ação imediata. |
| 🚀 | **LANÇAMENTO** | Deploy ou release de feature. |
| 📌 | **PINADO/IMPORTANTE** | Informação que deve ser referenciada depois. |""",

    # Message 5: Practical Example
    """## 💠 EXEMPLO PRÁTICO (Template de Update)

*Como um update diário deve parecer no canal Mainframe:*

```
📊 DAILY UPDATE // 24.05.23

🎯 Foco Principal
Finalizar a migração do banco de dados do Cliente X e estabilizar o novo Agente de Voz Vapi.

⚙️ Operacional (Hyper-Automation)
▪️ O fluxo n8n-sync-estoque-v3 apresentou falha de autenticação às 14h.
▪️ Correção aplicada e em monitoramento. 🟡 Risco médio de reincidência.

💸 Revenue
▪️ Proposta enviada para o lead TechCorp Solutions. Valor: R$ 12.5k/mês.
▪️ 🟢 Cliente Y fez o upsell para o plano Enterprise.

🚨 Bloqueios
Preciso da validação do @Nome no novo script de onboarding.
```

---
*Este documento é vivo. Sugestões de melhoria são bem-vindas no canal* `#l2-os-feedback`."""
]


# ═══════════════════════════════════════════════════════════════════════════════
# MAINFRAME CHANNELS
# ═══════════════════════════════════════════════════════════════════════════════

CHANNEL_MESSAGES = {
    "📢・announcements": [
        """# 📢 ANNOUNCEMENTS
## Centro de Comunicação Oficial

> Este canal é reservado para **comunicados oficiais** da L2 Systems.

### 🎯 Propósito
- Anúncios de novos clientes e contratos fechados
- Atualizações críticas de infraestrutura
- Marcos importantes da empresa
- Mudanças estratégicas

### 📋 Regras
- ❌ **Não poste aqui** — apenas liderança
- ✅ Use reações para confirmar leitura
- 💬 Discussões vão para `#command-center`

*Notificações deste canal são obrigatórias para todos os membros.*"""
    ],

    "💼・war-room": [
        """# 💼 WAR ROOM
## Sala de Decisões Estratégicas

> Acesso restrito aos **Co-Founders**. Discussões confidenciais e de alto impacto.

### 🎯 Propósito
- Decisões financeiras críticas
- Negociações sensíveis com clientes
- Planejamento estratégico trimestral
- Discussões sobre equity e investimentos

### ⚠️ Protocolo
- 🔒 **CONFIDENCIAL** — Nada daqui sai daqui
- 📝 Todas as decisões devem ser documentadas
- ⏰ Respostas em até 24h são esperadas

*Se chegou aqui, você faz parte do núcleo. Aja como tal.*"""
    ],

    "💸・revenue-stream": [
        """# 💸 REVENUE STREAM
## Monitoramento de Receita em Tempo Real

> Este canal é o **dashboard financeiro** da L2 em formato de chat.

### 🎯 Propósito
- Webhooks de novas vendas
- Alertas de churn e inadimplência
- Upsells e renovações de contrato
- Métricas de MRR/ARR

### 📊 Formato de Update
```
💰 [NOVA VENDA]
Cliente: Nome da Empresa
Plano: Enterprise
Valor: R$ X.XXX/mês
Recorrência: Mensal
```

### 🔔 Notificações
- 🟢 Nova venda → Celebrar
- 🟡 Pagamento atrasado → Atenção
- 🔴 Churn confirmado → Post-mortem obrigatório

*Cada número aqui é combustível para a máquina.*"""
    ],

    "📡・command-center": [
        """# 📡 COMMAND CENTER
## Central de Comando Operacional

> O **hub principal** de comunicação da equipe. Aqui é onde as coisas acontecem.

### 🎯 Propósito
- Discussões gerais de operação
- Coordenação de tarefas entre equipes
- Updates rápidos de status
- Perguntas que precisam de resposta rápida

### 📋 Boas Práticas
- Use threads para discussões longas
- Mencione `@` apenas quando for realmente necessário
- Mantenha o contexto — links e referências são bem-vindos
- Siga o protocolo de formatação (veja `#protocols`)

### ⚡ Tempo de Resposta Esperado
| Prioridade | Tempo |
|:---:|:---:|
| 🔴 Crítico | < 30 min |
| 🟡 Importante | < 2 horas |
| 🟢 Normal | < 24 horas |

*Este é o coração da operação. Mantenha-o limpo e funcional.*"""
    ],

    "📜・protocols": PROTOCOLS_MESSAGES,  # Uses the full protocols messages

    "🔗・utility-hub": [
        """# 🔗 UTILITY HUB
## Central de Navegação & Recursos

> O **ponto de conexão** entre todas as categorias do ecossistema L2.

### 🗺️ MAPA DO SERVIDOR

**🏛️ MAINFRAME** — *Gestão & Comunicação*
- `#announcements` → Comunicados oficiais
- `#protocols` → Guia de formatação
- `#war-room` → Decisões estratégicas 🔒
- `#revenue-stream` → Dashboard financeiro
- `#command-center` → Hub operacional

**⚙️ FACTORY** — *Desenvolvimento & DevOps*
- `#active-builds` → Projetos em andamento
- `#n8n-workflows` → Automações
- `#code-repository` → Snippets de código
- `#debug-forum` → Troubleshooting

**🧠 NEURAL** — *IA & Conhecimento*
- `#prompt-engineering` → Engenharia de prompts
- `#agents-logs` → Monitoramento de agentes
- `#knowledge-base` → Documentação

**🧪 DOGFOODING** — *Melhoria Contínua*
- `#l2-os-feedback` → Feedback interno
- `#internal-tickets` → Bugs & issues

**🔊 UPLINK** — *Comunicação por Voz*
- `Board Meeting` → Reuniões formais
- `Deep Work` → Foco profundo""",

        """### ⚡ QUICK ACTIONS

| Precisa de... | Vá para... |
|:---|:---|
| Postar um update | `#command-center` |
| Reportar um bug | `#internal-tickets` |
| Compartilhar código | `#code-repository` |
| Ver logs de agentes | `#agents-logs` |
| Documentar algo | `#knowledge-base` |
| Dar um feedback | `#l2-os-feedback` |
| Regras de formatação | `#protocols` |

### 🤖 COMANDOS DO BOT

```
/ask [pergunta]    → Consultar a IA L2-ORACLE
/logs [n]          → Ver últimos N logs do sistema
/deploy_infrastructure → Reorganizar servidor
```

### 📌 RECURSOS FIXADOS

*Use este canal para fixar links importantes, documentos de referência, e recursos úteis que servem a múltiplas categorias.*

---
*Este é o hub central. Se não sabe onde ir, comece aqui.*"""
    ],
    # FACTORY CHANNELS
    # ═══════════════════════════════════════════════════════════════════════════════

    "🔨・active-builds": [
        """# 🔨 ACTIVE BUILDS
## Projetos em Construção

> Acompanhe em tempo real o que está sendo **desenvolvido agora**.

### 🎯 Propósito
- Status de projetos em andamento
- Sprints e milestones atuais
- Blockers técnicos
- Requests de code review

### 📋 Formato de Update
```
🔨 [BUILD UPDATE]
Projeto: Nome do Projeto
Status: ⚙️ Em Progresso | 🟡 Bloqueado | 🟢 Concluído
Sprint: X/Y
Próximo milestone: [Data]
Notas: ...
```

### 🏷️ Tags de Status
- `[WIP]` — Work in Progress
- `[REVIEW]` — Aguardando Review
- `[BLOCKED]` — Bloqueado por dependência
- `[SHIPPED]` — Entregue

*Transparência no progresso evita surpresas no deadline.*"""
    ],

    "⚡・n8n-workflows": [
        """# ⚡ N8N WORKFLOWS
## Automações & Integrações

> Repositório visual de **fluxos de automação** n8n e similares.

### 🎯 Propósito
- Compartilhar screenshots de workflows
- Exportar JSONs de automações úteis
- Documentar integrações entre sistemas
- Troubleshooting de fluxos

### 📋 Formato de Post
```
⚡ [WORKFLOW]
Nome: sync-estoque-v3
Trigger: Webhook / Cron / Manual
Sistemas: Shopify → n8n → Google Sheets
Status: 🟢 Produção | 🟡 Teste | ⚙️ Dev
```

### 📎 Anexos Recomendados
- 🖼️ Screenshot do fluxo
- 📄 JSON exportado (em code block)
- 📝 Notas de implementação

*Automatize uma vez, colha os frutos para sempre.*"""
    ],

    "🐍・code-repository": [
        """# 🐍 CODE REPOSITORY
## Snippets & Soluções Técnicas

> Biblioteca interna de **código reutilizável**.

### 🎯 Propósito
- Snippets Python/JavaScript/Shell úteis
- Soluções para problemas recorrentes
- Scripts de automação
- Configurações de ambiente

### 📋 Formato de Post
```python
# 🐍 [SNIPPET] Nome descritivo
# Autor: @seu_nome
# Uso: Descreva quando usar

def exemplo():
    pass
```

### 🏷️ Categorias
- `[UTIL]` — Utilidades gerais
- `[API]` — Integrações com APIs
- `[DB]` — Operações de banco de dados
- `[SCRAPER]` — Web scraping
- `[DEVOPS]` — Infraestrutura

*Código bom é código que não precisa ser reescrito.*"""
    ],

    # ═══════════════════════════════════════════════════════════════════════════════
    # NEURAL CHANNELS
    # ═══════════════════════════════════════════════════════════════════════════════

    "🤖・agents-logs": [
        """# 🤖 AGENTS LOGS
## Monitoramento de Agentes IA

> Logs e métricas dos **agentes autônomos** em operação.

### 🎯 Propósito
- Logs de execução de agentes Vapi/OpenAI
- Métricas de performance (latência, tokens, custo)
- Alertas de falhas e anomalias
- Análise de conversas

### 📊 Formato de Log
```
🤖 [AGENT LOG]
Agente: voice-agent-vendas-v2
Timestamp: 2024-01-15 14:32:00
Duração: 3m 42s
Tokens: 1,247
Custo: $0.02
Status: 🟢 Sucesso | 🟡 Parcial | 🔴 Falha
```

### 🚨 Alertas Automáticos
- 🔴 Timeout de resposta > 10s
- 🟡 Custo por call > $0.10
- 🟢 Call concluída com sucesso

*Agentes são funcionários 24/7. Monitore-os como tal.*"""
    ],

    "📚・knowledge-base": [
        """# 📚 KNOWLEDGE BASE
## Repositório de Conhecimento

> A **memória institucional** da L2 Systems.

### 🎯 Propósito
- Documentação técnica
- Tutoriais e guias internos
- Links para recursos externos úteis
- Lições aprendidas (post-mortems)

### 📂 Categorias
- `[DOC]` — Documentação técnica
- `[GUIDE]` — Tutorial passo-a-passo
- `[LINK]` — Recurso externo valioso
- `[LESSON]` — Lição aprendida

### 📋 Formato de Post
```
📚 [DOC] Título do Documento
Categoria: Técnica / Processo / Estratégia
Última atualização: DD/MM/AAAA
Link: [se aplicável]

Resumo: Breve descrição do conteúdo...
```

*Conhecimento não documentado é conhecimento perdido.*"""
    ],

    # ═══════════════════════════════════════════════════════════════════════════════
    # DOGFOODING CHANNELS
    # ═══════════════════════════════════════════════════════════════════════════════

    "💠・l2-os-feedback": [
        """# 💠 L2-OS FEEDBACK
## Melhoria Contínua Interna

> **Dogfooding** — Usamos nossas próprias ferramentas e melhoramos elas aqui.

### 🎯 Propósito
- Feedback sobre ferramentas internas L2
- Sugestões de melhoria de processos
- Ideias para novos recursos
- Críticas construtivas à operação

### 📋 Formato de Feedback
```
💠 [FEEDBACK]
Sistema/Processo: Nome
Tipo: 🐛 Bug | 💡 Sugestão | ⚡ Melhoria
Prioridade: 🔴 Alta | 🟡 Média | 🟢 Baixa

Descrição: O que você observou...
Sugestão: Como poderia ser melhor...
```

### 🎯 Regra de Ouro
> "Se algo te incomoda duas vezes, vira feedback."

*Somos nossos primeiros clientes. Exija excelência.*"""
    ],

    "🐛・internal-tickets": [
        """# 🐛 INTERNAL TICKETS
## Rastreamento de Bugs & Issues

> Reporte e acompanhe **problemas técnicos** da infraestrutura L2.

### 🎯 Propósito
- Reporte de bugs encontrados
- Tracking de issues em aberto
- Priorização de correções
- Histórico de problemas resolvidos

### 📋 Formato de Ticket
```
🐛 [TICKET] #XXX
Sistema: Nome do sistema afetado
Severidade: 🔴 Crítico | 🟡 Médio | 🟢 Baixo
Reportado por: @nome
Status: 🆕 Novo | ⚙️ Em Análise | 🔧 Corrigindo | ✅ Resolvido

Descrição: O que aconteceu...
Passos para reproduzir:
1. ...
2. ...

Comportamento esperado: ...
Comportamento atual: ...
```

### ⚡ SLA de Resposta
| Severidade | Resposta | Resolução |
|:---:|:---:|:---:|
| 🔴 Crítico | 1 hora | 4 horas |
| 🟡 Médio | 4 horas | 24 horas |
| 🟢 Baixo | 24 horas | 1 semana |

*Bugs não reportados são bugs que nunca serão corrigidos.*"""
    ]
}


async def send_welcome_messages(channel, channel_name: str):
    """
    Sends the welcome messages for a specific channel.
    Returns True if messages were sent, False if channel already had messages.
    """
    # Check if channel already has pinned messages or any messages (to avoid duplicates)
    try:
        pins = await channel.pins()
        if pins:
            return False  # Already initialized
        
        # Get the last message to check if channel is empty
        async for msg in channel.history(limit=1):
            return False  # Channel has messages, skip
    except:
        pass  # If we can't check, proceed anyway
    
    messages_to_send = CHANNEL_MESSAGES.get(channel_name, None)
    if not messages_to_send:
        return False
    
    sent_messages = []
    for msg_content in messages_to_send:
        try:
            sent_msg = await channel.send(msg_content)
            sent_messages.append(sent_msg)
        except Exception as e:
            print(f"Failed to send welcome message to {channel_name}: {e}")
    
    # Pin the first message
    if sent_messages:
        try:
            await sent_messages[0].pin()
        except:
            pass
    
    return True
