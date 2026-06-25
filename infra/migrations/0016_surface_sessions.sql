-- 0016_surface_sessions.sql — persisted surface session identity + lifecycle (SURF-01).
--
-- Mirrors atlas_core.schemas.surface_session.SurfaceSession field-for-field.
-- The session->run link is SOFT (no FK on runs.session_id): existing runs carry
-- arbitrary/None session_id, mirroring the tool_approvals stored-not-FK precedent
-- (RESEARCH OQ-3). Terminal rows are DB-immutable via a BEFORE UPDATE trigger so the
-- guarantee survives buggy callers (T-10.3-01-IMMUT).

CREATE TABLE IF NOT EXISTS surface_sessions (
    id                      TEXT PRIMARY KEY,
    surface_kind            TEXT NOT NULL,
    surface_session_id      TEXT NOT NULL,
    workspace_kind          TEXT NOT NULL,
    workspace_root          TEXT NOT NULL,
    project_id              TEXT,
    mission_id              TEXT,
    run_id                  TEXT,
    agent                   TEXT NOT NULL,
    model_provider          TEXT NOT NULL,
    model_id                TEXT NOT NULL,
    permission_mode         TEXT NOT NULL,
    prompt_version          TEXT NOT NULL,
    tool_catalog_version    TEXT NOT NULL,
    context_policy_version  TEXT NOT NULL,
    state                   TEXT NOT NULL DEFAULT 'starting',
    owner_token             TEXT NOT NULL DEFAULT '',
    owner_pid               INTEGER,
    heartbeat_at            TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_surface_sessions_state
    ON surface_sessions(state);

-- Terminal sessions are immutable: any UPDATE on a completed/failed/reclaimed row
-- aborts. Keep the BEGIN...END body intact — db.py runs executescript and must not
-- ;-split trigger bodies.
CREATE TRIGGER IF NOT EXISTS surface_sessions_terminal_immutable
BEFORE UPDATE ON surface_sessions
WHEN OLD.state IN ('completed', 'failed', 'reclaimed')
BEGIN
    SELECT RAISE(ABORT, 'terminal surface sessions are immutable');
END;
