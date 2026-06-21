# 🗺️ L2 BOT Roadmap

## Versão Atual: v1.2.0

### ✅ Implementado

- [x] **AI Agent com Tools** — Function calling para ações no Discord
- [x] **14 Ferramentas** — send, read, summarize, pin, thread, search, config, memory
- [x] **Chat Mode** — Sessão de conversa contínua com `/chat`
- [x] **Memória Permanente** — ChromaDB para armazenamento persistente
- [x] **Sumarização Avançada** — Até 1000 msgs, 3 meses de histórico
- [x] **Infraestrutura** — `/deploy_infrastructure` para reorganizar servidor

---

## 🚧 Em Desenvolvimento

### v1.3.0 — Image Generation Tools

#### Geração de Imagens via OpenRouter

| Funcionalidade | Descrição |
|:---------------|:----------|
| **`generate_image`** | Gera imagem direto do prompt do usuário |
| **`enhance_prompt`** | IA de texto melhora/expande o prompt antes de enviar |
| **`auto_image`** | IA decide automaticamente se deve gerar imagem ou não |

**Fluxo:**
```
User: "cria uma logo para L2 Systems"
       ↓
   1. Se prompt direto → generate_image(prompt)
   2. Se precisa melhorar → enhance_prompt(prompt) → generate_image(enhanced)
   3. Se auto → AI decide se gera ou não
```

**Modelo de Imagem (a definir):**
```
# Opções OpenRouter para imagem:
- midjourney/imagine (se disponível)
- stability-ai/sdxl (se disponível)
- openai/dall-e-3 (pago)
- Outro: _______________
```

**Parâmetros do Tool:**
```python
{
    "name": "generate_image",
    "parameters": {
        "prompt": "descrição da imagem",
        "style": "realistic | artistic | logo | icon | photo",
        "size": "1024x1024 | 512x512 | landscape | portrait",
        "enhance": true  # se deve melhorar prompt automaticamente
    }
}
```

---

## 📋 Backlog (Futuro)

### v1.4.0 — Voice & Audio
- [ ] Voice channels monitoring
- [ ] Text-to-speech responses
- [ ] Audio summarization (transcrição)

### v1.5.0 — Automações Avançadas
- [ ] Scheduled tasks (cron jobs)
- [ ] Triggers automáticos (ex: "quando alguém mencionar X, fazer Y")
- [ ] Workflows configuráveis via chat

### v1.6.0 — Analytics & Reports
- [ ] Dashboard de atividade do servidor
- [ ] Relatórios semanais automáticos
- [ ] Métricas de uso dos tools

### v1.7.0 — Multi-Guild
- [ ] Suporte a múltiplos servidores
- [ ] Configurações per-guild
- [ ] Sincronização de memória entre servidores

---

## 🔧 Melhorias Técnicas

- [ ] Rate limiting mais robusto para tools
- [ ] Cache de respostas frequentes
- [ ] Fallback de modelos (se Devstral falhar, usar outro)
- [ ] Logs mais detalhados no Supabase
- [ ] Testes automatizados

---

## 💡 Ideias (Não Priorizadas)

- Integração com Notion
- Integração com GitHub (criar issues, PRs)
- Integração com Asaas (já parcial)
- Web dashboard com analytics
- Mobile app para controle remoto
- Integração com calendário (Google/Outlook)

---

## 📝 Notas

**Modelo de Imagem:**
> O modelo de imagem será definido depois. Verificar disponibilidade no OpenRouter e custos.

**Prioridade:**
1. Image Generation (v1.3.0)
2. Automações (v1.5.0)
3. Analytics (v1.6.0)

---

*Última atualização: 2026-01-15*
