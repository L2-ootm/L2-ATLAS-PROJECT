# L2 BOT - Instructions

This document provides instructions on how to set up, run, and use the L2 BOT.

## 1. Setup

### 1.1. Prerequisites

- Python 3.8+
- PostgreSQL database
- Discord Bot Token
- Discord OAuth2 Credentials
- Asaas API Key
- OpenRouter API Key

### 1.2. Environment Variables

Create a `.env` file in the root directory of the project and populate it with the following information:

```
# Discord Bot Token
DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN"

# Discord OAuth2 Credentials
DISCORD_CLIENT_ID="YOUR_DISCORD_CLIENT_ID"
DISCORD_CLIENT_SECRET="YOUR_DISCORD_CLIENT_SECRET"
DISCORD_REDIRECT_URI="http://localhost:5000/callback"

# Asaas API Key
ASAAS_API_KEY="YOUR_ASAAS_API_KEY"

# OpenRouter API Key
OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY"

# Quart Secret Key (for web sessions, generate a random string)
QUART_SECRET_KEY="YOUR_SUPER_SECRET_KEY"

# Discord Guild ID (for instant slash command updates on your test server)
DISCORD_GUILD_ID="YOUR_DISCORD_SERVER_ID"

# Database Connection URL (PostgreSQL)
DATABASE_URL="postgresql://user:password@host:port/database"
```