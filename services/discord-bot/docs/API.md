# 📚 API Documentation

## Overview

L2 BOT exposes two API layers:
1. **Internal Bot API** (Port 8081) - For web dashboard communication
2. **Supabase Integration** - For cloud data persistence

---

## Internal Bot API

Base URL: `http://localhost:8081`

### Endpoints

#### `GET /api/status`

Returns bot status information.

**Response:**
```json
{
  "status": "online",
  "guilds": 5,
  "latency_ms": 42
}
```

---

#### `GET /api/guilds`

Returns list of guilds the bot is in.

**Response:**
```json
{
  "guilds": [
    {
      "id": "1058835686385532969",
      "name": "L2 Systems",
      "member_count": 150
    }
  ]
}
```

---

#### `GET /api/guild/<guild_id>/channels`

Returns channels for a specific guild.

**Parameters:**
| Name | Type | Description |
|:-----|:-----|:------------|
| `guild_id` | string | Discord guild ID |

**Response:**
```json
{
  "channels": [
    {
      "id": "1234567890",
      "name": "command-center",
      "type": "text"
    }
  ]
}
```

---

#### `POST /api/channel/<channel_id>/send`

Sends a message to a specific channel.

**Parameters:**
| Name | Type | Description |
|:-----|:-----|:------------|
| `channel_id` | string | Discord channel ID |

**Body:**
```json
{
  "content": "Hello from the API!"
}
```

**Response:**
```json
{
  "success": true,
  "message_id": "1234567890"
}
```

---

## Supabase Schema

### `sys_trace_stream`

Real-time system log stream.

| Column | Type | Description |
|:-------|:-----|:------------|
| `id` | serial | Primary key |
| `created_at` | timestamp | Log timestamp |
| `level` | text | Log level (info, warning, error, etc.) |
| `message` | text | Log message |
| `metadata` | jsonb | Additional data |

### `audit_logs`

User action audit trail.

| Column | Type | Description |
|:-------|:-----|:------------|
| `id` | serial | Primary key |
| `user_id` | bigint | Discord user ID |
| `action` | text | Action performed |
| `details` | jsonb | Action details |
| `created_at` | timestamp | Timestamp |

### `clients`

Client/customer information.

| Column | Type | Description |
|:-------|:-----|:------------|
| `id` | serial | Primary key |
| `name` | text | Client name |
| `email` | text | Contact email |
| `discord_id` | bigint | Discord user ID |
| `plan` | text | Subscription plan |
| `created_at` | timestamp | Join date |

---

## Discord Slash Commands

### AI Commands

| Command | Parameters | Permission | Description |
|:--------|:-----------|:-----------|:------------|
| `/ask` | `question: string` | Everyone | Query AI assistant |
| `/logs` | `limit: int = 5` | Admin | View system logs |

### E-commerce Commands

| Command | Parameters | Permission | Description |
|:--------|:-----------|:-----------|:------------|
| `/buy` | `product: string` | Everyone | Purchase product |
| `/payment-status` | `payment_id: string` | Everyone | Check payment |

### Admin Commands

| Command | Parameters | Permission | Description |
|:--------|:-----------|:-----------|:------------|
| `/add-role` | `user: User, role: Role` | Admin | Assign role |
| `/remove-role` | `user: User, role: Role` | Admin | Remove role |
| `/deploy_infrastructure` | - | Admin | Reorganize server |

### Ticket Commands

| Command | Parameters | Permission | Description |
|:--------|:-----------|:-----------|:------------|
| `/new-ticket` | `subject: string` | Everyone | Create ticket |
| `/close-ticket` | - | Admin | Close ticket |

---

## RAG System

### Query Flow

```
User Query
    ↓
[Embedding Model: all-MiniLM-L6-v2]
    ↓
[ChromaDB Vector Search]
    ↓
[Context Retrieval]
    ↓
[System Prompt + Context + Query]
    ↓
[LLM: Devstral 2 via OpenRouter]
    ↓
Response
```

### Adding Documents

Place documents in `knowledge_base/` folder and run:

```bash
python load_documents.py
```

---

## Error Codes

| Code | Description |
|:-----|:------------|
| `E001` | API key not configured |
| `E002` | Supabase client not initialized |
| `E003` | Discord API rate limit |
| `E004` | Database connection failed |
| `E005` | Permission denied |
