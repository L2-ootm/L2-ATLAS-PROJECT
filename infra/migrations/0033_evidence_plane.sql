-- Evidence Plane: bounded, content-addressed file and full-result evidence.
-- Rust owns writes/diffing; SQLite remains the durable indexed authority.

CREATE TABLE IF NOT EXISTS evidence_blobs (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    chunk_size INTEGER NOT NULL DEFAULT 65536 CHECK(chunk_size = 65536),
    chunk_count INTEGER NOT NULL CHECK(chunk_count >= 0),
    availability TEXT NOT NULL CHECK(availability IN
        ('available','redacted','partial','unavailable','too_large')),
    redaction_count INTEGER NOT NULL DEFAULT 0 CHECK(redaction_count >= 0),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_blob_chunks (
    blob_id TEXT NOT NULL REFERENCES evidence_blobs(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK(chunk_index >= 0),
    content BLOB NOT NULL,
    PRIMARY KEY(blob_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS evidence_change_sets (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    session_id TEXT,
    team_run_id TEXT,
    turn_id TEXT,
    actor_id TEXT,
    parent_actor_id TEXT,
    tool_call_id TEXT,
    coverage TEXT NOT NULL CHECK(coverage IN
        ('complete','tool_only','partial','unavailable')),
    status TEXT NOT NULL CHECK(status IN
        ('captured','partial','unavailable','too_large')),
    redaction_count INTEGER NOT NULL DEFAULT 0 CHECK(redaction_count >= 0),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_file_changes (
    id TEXT PRIMARY KEY,
    change_set_id TEXT NOT NULL REFERENCES evidence_change_sets(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    old_path TEXT,
    operation TEXT NOT NULL CHECK(operation IN
        ('create','edit','delete','rename','mode','binary')),
    availability TEXT NOT NULL CHECK(availability IN
        ('available','redacted','partial','unavailable','too_large')),
    before_sha256 TEXT,
    after_sha256 TEXT,
    before_bytes INTEGER NOT NULL DEFAULT 0 CHECK(before_bytes >= 0),
    after_bytes INTEGER NOT NULL DEFAULT 0 CHECK(after_bytes >= 0),
    additions INTEGER NOT NULL DEFAULT 0 CHECK(additions >= 0),
    deletions INTEGER NOT NULL DEFAULT 0 CHECK(deletions >= 0),
    binary INTEGER NOT NULL DEFAULT 0 CHECK(binary IN (0,1)),
    generated INTEGER NOT NULL DEFAULT 0 CHECK(generated IN (0,1)),
    mode_before TEXT,
    mode_after TEXT,
    redaction_count INTEGER NOT NULL DEFAULT 0 CHECK(redaction_count >= 0),
    before_blob_id TEXT REFERENCES evidence_blobs(id),
    after_blob_id TEXT REFERENCES evidence_blobs(id),
    patch_blob_id TEXT REFERENCES evidence_blobs(id)
);

CREATE TABLE IF NOT EXISTS evidence_hunks (
    id TEXT PRIMARY KEY,
    file_change_id TEXT NOT NULL REFERENCES evidence_file_changes(id) ON DELETE CASCADE,
    hunk_index INTEGER NOT NULL CHECK(hunk_index >= 0),
    old_start INTEGER NOT NULL CHECK(old_start >= 0),
    old_lines INTEGER NOT NULL CHECK(old_lines >= 0),
    new_start INTEGER NOT NULL CHECK(new_start >= 0),
    new_lines INTEGER NOT NULL CHECK(new_lines >= 0),
    patch_start_byte INTEGER NOT NULL CHECK(patch_start_byte >= 0),
    patch_bytes INTEGER NOT NULL CHECK(patch_bytes >= 0),
    redacted INTEGER NOT NULL DEFAULT 0 CHECK(redacted IN (0,1)),
    UNIQUE(file_change_id, hunk_index)
);

CREATE TABLE IF NOT EXISTS evidence_child_refs (
    parent_change_set_id TEXT NOT NULL REFERENCES evidence_change_sets(id) ON DELETE CASCADE,
    child_change_set_id TEXT NOT NULL REFERENCES evidence_change_sets(id) ON DELETE CASCADE,
    actor_id TEXT,
    PRIMARY KEY(parent_change_set_id, child_change_set_id)
);

CREATE TABLE IF NOT EXISTS evidence_full_results (
    id TEXT PRIMARY KEY,
    owner_kind TEXT NOT NULL CHECK(owner_kind IN ('run','team_run','tool_call')),
    owner_id TEXT NOT NULL,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    team_run_id TEXT,
    tool_call_id TEXT,
    blob_id TEXT REFERENCES evidence_blobs(id),
    availability TEXT NOT NULL CHECK(availability IN
        ('available','redacted','unavailable','too_large')),
    preview TEXT NOT NULL,
    preview_bytes INTEGER NOT NULL CHECK(preview_bytes >= 0),
    full_bytes INTEGER NOT NULL CHECK(full_bytes >= 0),
    sha256 TEXT,
    media_type TEXT NOT NULL,
    redaction_count INTEGER NOT NULL DEFAULT 0 CHECK(redaction_count >= 0),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_change_sets_run_cursor
    ON evidence_change_sets(run_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_evidence_change_sets_session_cursor
    ON evidence_change_sets(session_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_evidence_change_sets_team_cursor
    ON evidence_change_sets(team_run_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_evidence_file_changes_set_cursor
    ON evidence_file_changes(change_set_id, id);
CREATE INDEX IF NOT EXISTS idx_evidence_hunks_file_cursor
    ON evidence_hunks(file_change_id, hunk_index);
CREATE INDEX IF NOT EXISTS idx_evidence_full_results_owner_cursor
    ON evidence_full_results(owner_kind, owner_id, created_at, id);
