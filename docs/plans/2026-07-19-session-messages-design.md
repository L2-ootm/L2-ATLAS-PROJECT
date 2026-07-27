# Session Messages — Server-Side Conversation History Design

## Problem

ATLAS stores audit_events (raw tool/LLM events), runs (execution records), and surface_sessions (session metadata). Conversation messages exist only in browser localStorage with a 150-message cap. No server-side conversation history exists, making search impossible across sessions and losing history on tab close.

## Migration: 0030_session_messages.sql

### Tables

**session_messages** — one row per conversation message:
- `id` (TEXT PK), `surface_session_id` (FK → surface_sessions), `run_id` (FK → runs, nullable)
- `role` (system/user/assistant/tool), `content` (TEXT), `token_count` (pre-computed)
- `tool_call_id`, `tool_name` (structured tool metadata, separate from FTS)
- `seq` (INTEGER, monotonic per session) — enables windowed retrieval
- `created_at` (TEXT, ISO-8601)

**session_messages_fts** — FTS5 virtual table indexed on `content || tool_name`. Trigger-synced on insert/update/delete, following the Hermes hermes_state.py pattern.

**compaction_artifacts** — audit trail for compaction events:
- Records which message range was compacted, original/summary token counts
- Stores the summary content and model used for provenance

### Indexes

| Index | Columns | Purpose |
|-------|---------|---------|
| `idx_session_messages_session_seq` | `(surface_session_id, seq)` UNIQUE | Windowed retrieval (tail-N, range) |
| `idx_session_messages_run_id` | `(run_id)` | Run-level message queries |
| `idx_session_messages_created_at` | `(created_at)` | Time-range queries |
| `idx_compaction_artifacts_session` | `(surface_session_id)` | Compaction history per session |
| `idx_compaction_artifacts_compacted_at` | `(compacted_at)` | Time-based cleanup |

## Compaction Algorithm

**Trigger**: When total `token_count` across all messages in a session exceeds the threshold (default: 128,000 tokens, configurable via `session.compaction_threshold`).

**Head protection**: First 4 messages are always retained (system prompt + initial context).

**Tail protection**: Last 8 messages are always retained (recent conversational context).

**Middle slice**: Messages between head and tail are candidates for compaction. The algorithm selects the oldest contiguous block that, when summarized, brings total tokens below 80% of threshold (hysteresis to prevent thrashing).

**Summarization model**: Uses the session's configured auxiliary model (falls back to session model). Template:
```
Summarize this conversation segment for context preservation.
Include: key decisions, file paths modified, bugs found, user preferences stated.
Omit: tool output details, repetitive confirmations, system messages.
```

**Replacement**: Compacted messages are deleted, replaced by a single synthetic assistant message containing the summary. The compaction_artifact row preserves the original range for audit.

## Persistence API: Agent → DB → Cockpit

**Write path** (agent runtime):
1. Agent emits message via `audit_service.emit` or direct insert
2. `session_message_service.insert_message()` assigns `seq` (SELECT MAX(seq)+1), computes `token_count`, inserts row
3. After insert, check if compaction threshold exceeded → trigger compaction if needed
4. FTS5 triggers auto-update the search index

**Read path** (cockpit):
1. Cockpit requests messages: `GET /api/sessions/{id}/messages?limit=50&offset=0`
2. Service queries `session_messages WHERE surface_session_id = ? ORDER BY seq DESC LIMIT ? OFFSET ?`
3. FTS search: `SELECT ... FROM session_messages_fts WHERE content MATCH ? ...`
4. Response includes `has_more` flag for infinite scroll

**Real-time** (SSE): New messages are pushed via the existing audit_events SSE stream, extended with a `kind: "session_message"` event type.

## localStorage → Server Migration

**Phase 1 (deploy)**: Server accepts messages but does not require them. Cockpit falls back to localStorage if server returns empty.

**Phase 2 (migration)**: On first session load after upgrade, cockpit reads localStorage, POSTs batch to `POST /api/sessions/{id}/messages/migrate`. Server upserts (idempotent by content hash).

**Phase 3 (cutover)**: After migration flag is set per-session, cockpit stops reading localStorage for that session. Server becomes source of truth.

**Cleanup**: After 30 days (configurable), old localStorage entries are deleted. localStorage cap raised to 500 as buffer during migration window.
