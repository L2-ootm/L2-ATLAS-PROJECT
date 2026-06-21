<!-- GSD:project-start source:PROJECT.md -->
## Project

**L2-BOT // Core System**

L2-BOT is an integrated, agentic Discord assistant and administration platform. It enables seamless conversation ("Ghost Mode"), automated server layout organization, ticket support, and e-commerce catalogs. It is managed via an external Quart web dashboard using Discord OAuth2 login.

**Core Value:** The system allows users to seamlessly manage, structure, and orchestrate Discord servers using an advanced AI agent powered by tool calling and rich context verification, without requiring manual administrative overhead.

### Constraints

- **Tech Stack:** Python 3.10+, discord.py, Quart, SQLite. Blocking synchronous functions are prohibited inside async task loops.
- **Runtime Environment:** Windows local environment for development, meaning no local AI model deployment (e.g. Ollama/vLLM) is configured for this phase.
- **Security:** Secret keys (Tokens, client secrets, API keys) must remain strictly in the `.env` environment configuration.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.10+ - All backend bot logic, cogs, managers, database client, and web dashboard backend.
- JavaScript - Frontend client-side scripting (`dashboard.js`, `marked.min.js`) for the Quart web dashboard.
- SQL - SQLite schema definition (`schema.sql`).
- HTML/CSS - Web interface design (`dashboard.html` and custom vanilla CSS).
## Runtime
- Python 3.10+ (Local interpreter runtime).
- Browser client runtime for the Web Dashboard.
- pip - Managed via `requirements.txt`.
- No lockfile present.
## Frameworks
- discord.py 2.x (async version) - Main gateway interface for Discord bot capabilities, cogs, event listeners, and slash commands.
- Quart 0.19+ - Asynchronous web microframework (async alternative to Flask) running the admin dashboard.
- None - No automated testing framework or test suites are integrated into the repository.
- None - Built directly using standard Python module executions (`python -m bot.main`).
## Key Dependencies
- `openai` (AsyncOpenAI) - Communicates with OpenRouter endpoints to trigger LLM completions using Mistral's `devstral-2512:free` model.
- `chromadb` - Persistent vector database for agent memories (`l2_memories` and `l2_facts`) and document retrieval (`l2_docs`).
- `sentence-transformers` - Generates vector embeddings locally using the `all-MiniLM-L6-v2` transformer model.
- `aiosqlite` - Asynchronous wrapper for SQLite, providing non-blocking local SQL queries for support ticketing.
- `supabase` (Supabase client) - Handles cloud telemetry log retrieval from the `sys_trace_stream` table and writes audit logs.
- `aiohttp` - Non-blocking async client/server HTTP routing, running the internal bot API on port 8081 and fetching remote endpoints (e.g. Catbox.moe).
- `requests-oauthlib` - Manages Discord OAuth2 login flows for the dashboard.
- `python-dotenv` - Environment configuration loader.
## Configuration
- Configuration via `.env` file containing tokens:
- No custom compiler or build configurations.
## Platform Requirements
- Windows, macOS, or Linux with Python 3.10+ installed.
- Standard VPS (Virtual Private Server) target.
- Host configuration: requires port 5000 exposed for dashboard access and 8081 bound locally for bot-dashboard API bridge.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Code Style
- Python 3.10+ is standard. All Python files must adhere to standard PEP 8 naming and formatting practices (snake_case for functions/variables, PascalCase for classes).
- **Mandatory async programming** is enforced throughout the codebase due to the nature of `discord.py` and `Quart`. Synchronous code blocks (blocking calls) must be avoided within command contexts to keep the bot responsive.
- Standard requests must use `aiohttp.ClientSession` or the asynchronous client of respective SDKs, never standard blocking `requests`.
## Coding Patterns
- All command groupings are encapsulated as `discord.ext.commands.Cog` subclasses.
- Cogs are dynamically loaded at startup using `setup_hook` in the `L2Bot` client class.
- Interaction endpoints (Slash Commands) are mapped using the `@app_commands.command` decorator.
- All local database operations must be routed via `DatabaseManager` (`database/database.py`).
- SQL transactions are managed asynchronously using `aiosqlite`.
- Direct synchronous calls to database files are forbidden.
- Local print statements are used for debugging, but actual production audits are logged remotely using `SupabaseManager` (`bot/supabase_manager.py`) which posts logs to the `audit_logs` table.
## Error Handling
- Embed errors and trace logs are handled by wrapping commands in `try/except` structures, catching exceptions (like `discord.Forbidden` or `discord.HTTPException`), and notifying the user using ephemeral responses or alerting the staff channels via the logging cog.
- The `ToolExecutor` wraps all agent tool executions inside `try/except` blocks, parsing failures and returning structured responses:
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Architectural Pattern
```
```
## Component Layers
### 1. Ingestion / Gateway Layer
- **Discord Gateway Connector (`bot/main.py`)**: Runs the `discord.py` event loop, managing active websocket gateway sessions with Discord.
- **Discord Cogs (`bot/cogs/`)**: Modular commands and event listeners:
### 2. Cognitive Agent Loop (The Brain)
- **Agent Orchestrator (`bot/agent.py` - `L2Agent`)**: Implements a ReAct (Reasoning and Action) loop using Mistral's Devstral-2 model.
### 3. Web Dashboard Backend
- **Quart App (`web/main.py`)**: Non-blocking web server that runs parallel to the bot.
- **Bot-Dashboard API (`bot/api.py`)**: Local web server hosted on port `8081` inside the bot process, providing internal routes (fetching guilds, checking admin credentials, sending embeds) to keep the web application synchronized with the active bot state without direct memory sharing.
### 4. Storage & Persistence Layer
- **SQLite (`database.db`)**: Primary relational database containing support tickets, orders, payments, and users. SQLite execution is handled via async queries in `database/database.py`.
- **ChromaDB (`chroma_db/`)**: Vector base for storing semantic facts and conversational memories.
- **JSON files (`data/`)**: Local catalog registry and shopping carts.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
