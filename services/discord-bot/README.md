# 🤖 L2 BOT // CORE SYSTEM

<div align="center">

![L2 Systems](https://img.shields.io/badge/L2-ONLINE-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/STATUS-OPERATIONAL-green?style=for-the-badge)
![AI Model](https://img.shields.io/badge/AI-DEVSTRAL_2-purple?style=for-the-badge)
![License](https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge)

**Next-Gen Agentic Discord Assistant**
*Seamless Chat • Creative Studio • E-commerce • Advanced Moderation*

[Features](#-features) • [Commands](#-command-reference) • [Setup](#-setup) • [Architecture](#-architecture)

</div>

---

## 📋 Overview

**L2 BOT** is not just a chatbot; it's an autonomous **AI Agent**. It doesn't rely on hardcoded commands for everything—instead, it uses a **Tool Use** architecture (Function Calling) to understand your intent and execute actions dynamically.

Whether you're managing a server, selling products, or generating art, you simply **talk** to the bot, and it figures out the rest.

---

## ✨ Features

### 👻 Ghost Mode Chat (Seamless)
No more spamming commands.
*   **Implicit Start**: Just type `l2 <message>` in any channel.
*   **Converational**: The bot remembers context (Threaded Memory).
*   **Silent Stop**: Say "bye" or "valeu" to end the session. No "Session Ended" spam.
*   **Pro Messenger**: Ask "Send an announcement to #general" and it just says "✅", keeping your chat clean.

### 🎨 Creative Suite
Powered by **Pollinations.ai (Flux Pro)**.
*   **Generation**: `/image` (with model selector: Flux, Realism, Anime, 3D).
*   **Editing**: `/image_edit` (attach an image + prompt to transform it).
*   **Smart Uploads**: Images are automatically uploaded to `catbox.moe` so they render properly in Discord embeds.
*   **Safety**: Admin controls for NSFW filters (`safe=false` support).

### 🛒 E-commerce Engine
A full shopping experience inside Discord.
*   **Catalog**: Interactive embeds in `#catalog` with `[Buy]` and `[Add to Cart]` buttons.
*   **Cart System**: Persistent shopping carts per user.
*   **Checkout**: Generates an invoice and opens a private ticket (`#order-user`).
*   **AI Salesman**: Ask "Do you have any swords?" and the AI will search the DB and sell it to you.
*   **Admin Tools**: `/shop_add_product`, `/shop_setup`, `/shop_publish`.

### 🛡️ Advanced Moderation & Forums
*   **Forum Native**: "Create a forum post in #ideas about X tagged Y". The bot intelligently handles Tags and Thread titles.
*   **Smart Purge**: "Delete the last 10 messages" or "Clear the last 2 hours" (Safe bulk delete).
*   **Temp Channels**: "Make a voice channel for 10 mins" (Auto-deletes).
*   **Role Manager**: Create/Edit/Assign roles via chat.

### 📊 Infrastructure & Logging
*   **Supabase Sync**: Real-time logging of all actions (`audit_logs`) and system traces (`sys_trace_stream`).
*   **Log Streaming**: Live updates in `#process-logs` (Info, Warn, Error).
*   **Config**: Dynamic configuration via `get_config` / `set_config`.

---

## 💻 Command Reference

While the AI handles most things, some Slash Commands are available for specific tasks:

| Command | Description |
|:--------|:------------|
| **/chat** | Manually start a chat session (if not using `l2` prefix) |
| **/image** | Generate an image with model selection |
| **/image_edit** | Transform an attached image |
| **/shop_publish** | [Admin] Post/Refresh the catalog in `#catalog` |
| **/shop_add_product** | [Admin] Add a new item to the store |
| **/shop_setup** | [Admin] Create Shop Categories/Channels |
| **/stop** | Silently end the current session |
| **/logs** | [Admin] View recent system logs |
| **/deploy_infrastructure** | [Admin] Reorganize server layout (L2 Standard) |

---

## 🏗️ Architecture

```
L2-BOT/
├── bot/
│   ├── agent.py                 # 🧠 The Brain (ReAct Loop)
│   ├── main.py                  # Entry Point
│   ├── memory.py                # Vector Memory (ChromaDB)
│   ├── supabase_manager.py      # Cloud Logging
│   ├── tools/                   # 🛠️ Agent Capabilities
│   │   ├── registry.py          # Tool Definitions (Schemas)
│   │   └── executor.py          # Implementation Logic
│   ├── cogs/                    # Discord Events
│   │   ├── ai.py                # Message Listener
│   │   ├── image_gen.py         # Creative Suite
│   │   └── ecommerce.py         # Shop System
│   └── managers/                # State Managers
│       ├── pollen_manager.py    # Image Quota
│       ├── product_manager.py   # Shop DB
│       └── temp_channels.py     # Channel Lifecycle
├── data/                        # Local Persistence (JSON)
└── web/                         # Dashboard (Optional)
```

---

## 🚀 Setup

### 1. Requirements
*   Python 3.10+
*   Discord Bot Token (with Message Content Intent)
*   OpenRouter API Key (for LLM)
*   Supabase Project (for Logging)

### 2. Environment Variables (.env)
```env
# Core
DISCORD_BOT_TOKEN=...
DISCORD_GUILD_ID=...

# AI
OPENROUTER_API_KEY_1=...

# Logging
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
```

### 3. Installation
```bash
# Clone
git clone https://github.com/L2-ootm/L2-BOT.git
cd L2-BOT

# Install
pip install -r requirements.txt

# Run
python -m bot.main
```

---

<div align="center">

**L2 SYSTEMS // ARCHITECTURE OF SCALE**

</div>
