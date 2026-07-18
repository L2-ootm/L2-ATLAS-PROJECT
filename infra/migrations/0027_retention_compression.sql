-- 0027: Add mission_compressions table for data lifecycle management.
-- Stores compressed summaries of old archived missions to reduce storage.

CREATE TABLE IF NOT EXISTS mission_compressions (
    mission_id TEXT PRIMARY KEY REFERENCES missions(id),
    compressed_at TEXT NOT NULL,
    tool_call_count INTEGER DEFAULT 0,
    audit_event_count INTEGER DEFAULT 0,
    artifact_count INTEGER DEFAULT 0,
    summary_json TEXT DEFAULT '{}'
);
