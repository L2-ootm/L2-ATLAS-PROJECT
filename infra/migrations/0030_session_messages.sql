-- 0030_session_messages.sql — server-side conversation history for ATLAS.
--
-- Problem: messages currently live only in browser localStorage (150 cap).
-- No server-side conversation history exists. This migration adds:
--   1. session_messages — ordered conversation history per surface session
--   2. FTS5 index — full-text search across message content
--   3. compaction_artifacts — compressed summaries replacing old message runs
--   4. Performance indexes for retrieval patterns
--
-- Design references:
--   - Hermes hermes_state.py messages table + FTS5 (content-sync triggers)
--   - ATLAS 0016_surface_sessions.sql (FK to surface_sessions)
--   - ATLAS 0027_retention_compression.sql (mission_compressions precedent)
--   - ATLAS 0028_agent_teams.sql (team_chat_messages seq pattern)

PRAGMA foreign_keys = ON;

-- ──────────────────────────────────────────────────────────────────────
-- 1. session_messages — one row per conversation message
-- ──────────────────────────────────────────────────────────────────────
-- Role vocabulary aligns with OpenAI chat format and Hermes message roles:
--   system, user, assistant, tool
--
-- seq is monotonic per surface_session_id (assigned at insert time).
-- The unique index on (surface_session_id, seq) enforces ordering and
-- enables efficient windowed retrieval (tail-N, range scans).
--
-- token_count is pre-computed at write time (no re-tokenization on read).
-- content is the full message text; tool metadata (tool_call_id, tool_name)
-- is stored separately for structured queries without polluting FTS.

CREATE TABLE IF NOT EXISTS session_messages (
    id                  TEXT PRIMARY KEY,
    surface_session_id  TEXT NOT NULL REFERENCES surface_sessions(id),
    run_id              TEXT REFERENCES runs(id),
    role                TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content             TEXT NOT NULL DEFAULT '',
    token_count         INTEGER NOT NULL DEFAULT 0,
    tool_call_id        TEXT,
    tool_name           TEXT,
    metadata_json       TEXT DEFAULT '{}',
    created_at          TEXT NOT NULL,
    seq                 INTEGER NOT NULL
);

-- Ordering + windowed retrieval: WHERE surface_session_id = ? ORDER BY seq DESC LIMIT N
CREATE UNIQUE INDEX IF NOT EXISTS idx_session_messages_session_seq
    ON session_messages(surface_session_id, seq);

-- Run-level queries: "show me all messages for this run"
CREATE INDEX IF NOT EXISTS idx_session_messages_run_id
    ON session_messages(run_id);

-- Time-range queries: "messages between timestamp A and B"
CREATE INDEX IF NOT EXISTS idx_session_messages_created_at
    ON session_messages(created_at);

-- ──────────────────────────────────────────────────────────────────────
-- 2. FTS5 full-text search index
-- ──────────────────────────────────────────────────────────────────────
-- Mirrors Hermes hermes_state.py FTS5 pattern: inline-content virtual table
-- with trigger-synced inserts. Indexes content + tool_name for searchability.
--
-- The content column is the primary search target; tool_name is appended
-- so "grep for tool X in session Y" works via FTS5 MATCH.

CREATE VIRTUAL TABLE IF NOT EXISTS session_messages_fts USING fts5(
    content,
    content=session_messages,
    content_rowid=rowid
);

-- FTS5 sync triggers — keep index consistent on insert/update/delete.
-- Trigger bodies must stay in one statement (no ;-split) per executescript
-- convention established in 0001_core.sql wiki_fts triggers.

CREATE TRIGGER IF NOT EXISTS session_messages_fts_insert
AFTER INSERT ON session_messages
BEGIN
    INSERT INTO session_messages_fts(rowid, content)
    VALUES (new.rowid, new.content || ' ' || COALESCE(new.tool_name, ''));
END;

CREATE TRIGGER IF NOT EXISTS session_messages_fts_delete
AFTER DELETE ON session_messages
BEGIN
    INSERT INTO session_messages_fts(session_messages_fts, rowid, content)
    VALUES ('delete', old.rowid, old.content || ' ' || COALESCE(old.tool_name, ''));
END;

CREATE TRIGGER IF NOT EXISTS session_messages_fts_update
AFTER UPDATE ON session_messages
BEGIN
    INSERT INTO session_messages_fts(session_messages_fts, rowid, content)
    VALUES ('delete', old.rowid, old.content || ' ' || COALESCE(old.tool_name, ''));
    INSERT INTO session_messages_fts(rowid, content)
    VALUES (new.rowid, new.content || ' ' || COALESCE(new.tool_name, ''));
END;

-- ──────────────────────────────────────────────────────────────────────
-- 3. compaction_artifacts — compressed summaries of compacted messages
-- ──────────────────────────────────────────────────────────────────────
-- When a session exceeds the token threshold, the compaction algorithm:
--   1. Selects a middle slice of messages (protecting head + tail)
--   2. Summarizing them via the configured model
--   3. Replacing them with a single synthetic "system" summary message
--   4. Recording the compaction artifact here for audit + restore
--
-- This follows the 0027 mission_compressions pattern: one row per
-- compaction event, with provenance metadata for debugging.

CREATE TABLE IF NOT EXISTS compaction_artifacts (
    id                      TEXT PRIMARY KEY,
    surface_session_id      TEXT NOT NULL REFERENCES surface_sessions(id),
    compacted_message_start INTEGER NOT NULL,
    compacted_message_end   INTEGER NOT NULL,
    original_message_count  INTEGER NOT NULL,
    original_token_count    INTEGER NOT NULL,
    summary_token_count     INTEGER NOT NULL,
    summary_content         TEXT NOT NULL,
    model_used              TEXT NOT NULL,
    compacted_at            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_compaction_artifacts_session
    ON compaction_artifacts(surface_session_id);

CREATE INDEX IF NOT EXISTS idx_compaction_artifacts_compacted_at
    ON compaction_artifacts(compacted_at);
