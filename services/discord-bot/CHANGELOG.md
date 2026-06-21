# 🔄 Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.1.0] - 2026-01-15

### Added
- **Infrastructure Management** (`/deploy_infrastructure`)
  - Shift Down and Inject algorithm for server reorganization
  - New L2 category structure (MAINFRAME, FACTORY, NEURAL, DOGFOODING, UPLINK)
  - Automatic channel creation with welcome messages
  - `📜・protocols` channel with syntax guide
  - `🔗・utility-hub` channel as navigation center

- **Channel Welcome Messages**
  - Professional onboarding messages in Portuguese-BR
  - Purpose explanation for each channel
  - Usage templates and guidelines
  - First message auto-pinned

- **AI Protocol Compliance**
  - Bot now follows L2 formatting protocols
  - Emoji status indicators (🔴🟡🟢⚙️💡)
  - Structured response formatting

### Changed
- **AI Model**: Migrated from `x-ai/grok-4.1-fast:free` to `mistralai/devstral-2512:free`
  - Better support for agentic coding
  - Function calling capability
  - 256K context window

### Fixed
- Forum channel creation (using `guild.create_forum()`)
- Category positioning logic

---

## [1.0.0] - 2026-01-01

### Added
- Initial release
- Discord bot with slash commands
- AI assistant with RAG system
- E-commerce with Asaas integration
- Role management system
- Ticket system
- Web dashboard with Discord OAuth2
- Logger cog for Supabase log streaming
- Supabase manager for cloud data

---

## Planned

### [1.2.0] - Agent Tools
- AI agent with Discord tools
- `send_message`, `read_channel`, `summarize_channel` tools
- Configuration management via chat
- Permission-based tool access
- Audit logging for AI actions
