# 🏗️ Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           L2 BOT ARCHITECTURE                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   DISCORD API   │────▶│   L2 BOT CORE   │◀────│   WEB DASHBOARD │
│                 │◀────│   (bot/main.py) │────▶│   (web/main.py) │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                 │                       │
                                 │ Port 8081             │ Port 5000
                                 ▼                       │
                        ┌─────────────────┐              │
                        │   Internal API  │◀─────────────┘
                        │   (bot/api.py)  │
                        └────────┬────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│     COGS      │       │   RAG SYSTEM  │       │   DATABASE    │
│ (bot/cogs/)   │       │  (bot/rag.py) │       │   LAYER       │
├───────────────┤       ├───────────────┤       ├───────────────┤
│ • ai.py       │       │ • Embeddings  │       │ • SQLite      │
│ • ecommerce   │       │ • ChromaDB    │       │   (local)     │
│ • roles       │       │ • LLM         │       │ • Supabase    │
│ • tickets     │       │   (Devstral2) │       │   (cloud)     │
│ • logger      │       │               │       │               │
│ • infra       │       │               │       │               │
└───────────────┘       └───────┬───────┘       └───────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   OPENROUTER    │
                       │     API         │
                       │ (external LLM)  │
                       └─────────────────┘
```

---

## Data Flow

### AI Query Flow

```
User Message
     │
     ▼
┌─────────────────┐
│ Intent Detection│
│ (triggers check)│
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐
│ RAG   │ │Supabase│
│Context│ │ Logs  │
└───┬───┘ └───┬───┘
    │         │
    └────┬────┘
         ▼
┌─────────────────┐
│  System Prompt  │
│  + Context      │
│  + Logs         │
│  + Query        │
└────────┬────────┘
         ▼
┌─────────────────┐
│   OpenRouter    │
│   (Devstral 2)  │
└────────┬────────┘
         ▼
    Response
```

### Log Streaming Flow

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   External    │────▶│   Supabase    │────▶│  Logger Cog   │
│   Systems     │     │sys_trace_stream│    │  (Polling)    │
└───────────────┘     └───────────────┘     └───────┬───────┘
                                                    │
                                                    ▼
                                           ┌───────────────┐
                                           │ Discord       │
                                           │ Log Channels  │
                                           ├───────────────┤
                                           │ #info         │
                                           │ #success      │
                                           │ #warning      │
                                           │ #error        │
                                           │ #critical     │
                                           └───────────────┘
```

---

## Component Details

### Bot Core (`bot/main.py`)

| Component | Responsibility |
|:----------|:---------------|
| `L2Bot` class | Main bot instance |
| `setup_hook()` | Initialize Supabase, load cogs |
| `on_ready()` | Startup confirmation |
| Internal API | REST interface for web |

### RAG System (`bot/rag.py`)

| Component | Responsibility |
|:----------|:---------------|
| `KeyManager` | API key rotation |
| `RAGSystem` | Query orchestration |
| Embeddings | Document vectorization |
| ChromaDB | Vector storage/retrieval |
| Context injection | Supabase logs, RAG docs |

### Web Dashboard (`web/main.py`)

| Route | Purpose |
|:------|:--------|
| `/` | Index page |
| `/login` | OAuth2 initiation |
| `/callback` | OAuth2 callback |
| `/dashboard` | Main dashboard |
| `/api/*` | REST endpoints |

---

## Security Model

```
┌─────────────────────────────────────────────────┐
│                 SECURITY LAYERS                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │ Layer 1: Discord Permissions            │   │
│  │ • Guild-level roles                     │   │
│  │ • Channel-level overwrites              │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │ Layer 2: Command Permissions            │   │
│  │ • @app_commands.checks.has_permissions  │   │
│  │ • @commands.is_owner                    │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │ Layer 3: API Authentication             │   │
│  │ • Discord OAuth2 for web                │   │
│  │ • Session-based auth                    │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │ Layer 4: Environment Secrets            │   │
│  │ • .env file (gitignored)                │   │
│  │ • Key rotation support                  │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## Future: Agent Tools Architecture

```
User Request
     │
     ▼
┌─────────────────┐
│  Agent Loop     │
│  (ReAct)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM + Tools    │
│  (Function Call)│
└────────┬────────┘
         │
    ┌────┴────────────────────┐
    ▼         ▼               ▼
┌───────┐ ┌───────┐     ┌───────────┐
│send_  │ │read_  │     │summarize_ │
│message│ │channel│     │channel    │
└───────┘ └───────┘     └───────────┘
    │         │               │
    └────┬────┴───────────────┘
         ▼
   Tool Execution
         │
         ▼
   Response / Loop
```
