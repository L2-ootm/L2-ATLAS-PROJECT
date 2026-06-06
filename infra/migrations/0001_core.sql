-- ATLAS core schema migration 0001 — generated from atlas_core.schemas.core (D-012)
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS missions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    intent      TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',
    project     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    mission_id  TEXT NOT NULL REFERENCES missions(id),
    session_id  TEXT,
    status      TEXT NOT NULL DEFAULT 'running',
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    summary     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit_events (
    id            TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES runs(id),
    task_id       TEXT,
    session_id    TEXT,
    tool_call_id  TEXT,
    event_type    TEXT NOT NULL,
    tool_name     TEXT,
    timestamp     TEXT NOT NULL,
    duration_ms   INTEGER,
    data          TEXT NOT NULL DEFAULT '{}',
    policy_result TEXT
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id                TEXT PRIMARY KEY,
    audit_event_id    TEXT NOT NULL REFERENCES audit_events(id),
    run_id            TEXT NOT NULL REFERENCES runs(id),
    tool_name         TEXT NOT NULL,
    args              TEXT NOT NULL DEFAULT '{}',
    result            TEXT,
    exit_code         INTEGER,
    stdout            TEXT,
    stderr            TEXT,
    duration_ms       INTEGER,
    policy_allowed    INTEGER,
    requires_approval INTEGER,
    timestamp         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    id             TEXT PRIMARY KEY,
    run_id         TEXT NOT NULL REFERENCES runs(id),
    audit_event_id TEXT REFERENCES audit_events(id),
    path           TEXT NOT NULL,
    artifact_type  TEXT NOT NULL,
    sha256         TEXT,
    size_bytes     INTEGER,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id          TEXT PRIMARY KEY,
    path        TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    size_bytes  INTEGER NOT NULL,
    mime_type   TEXT NOT NULL DEFAULT 'text/plain',
    ingested_at TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS wiki_pages (
    id         TEXT PRIMARY KEY,
    slug       TEXT NOT NULL UNIQUE,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL DEFAULT '',
    source_id  TEXT REFERENCES sources(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version    INTEGER NOT NULL DEFAULT 1
);

CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
    title,
    body,
    content=wiki_pages,
    content_rowid=rowid
);

-- FTS5 trigger stubs — TODO Phase 6: wire full-text index maintenance
CREATE TRIGGER IF NOT EXISTS wiki_fts_insert AFTER INSERT ON wiki_pages BEGIN
    INSERT INTO wiki_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
END;

CREATE TRIGGER IF NOT EXISTS wiki_fts_update AFTER UPDATE ON wiki_pages BEGIN
    INSERT INTO wiki_fts(wiki_fts, rowid, title, body) VALUES ('delete', old.rowid, old.title, old.body);
    INSERT INTO wiki_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
END;

CREATE TRIGGER IF NOT EXISTS wiki_fts_delete AFTER DELETE ON wiki_pages BEGIN
    INSERT INTO wiki_fts(wiki_fts, rowid, title, body) VALUES ('delete', old.rowid, old.title, old.body);
END;
