-- 0019 — performance indexes (2026-07-10 deep-audit F3).
-- audit_events(run_id): the gateway SSE stream polls
--   WHERE run_id = ? AND rowid > ? ORDER BY rowid
-- every 500ms; without this index that is a full table scan. A plain
-- run_id index suffices — SQLite index entries end with the rowid, so the
-- planner does a covering (run_id=? AND rowid>?) search. An explicit
-- (run_id, rowid) index is invalid here (TEXT primary key, no rowid alias).
CREATE INDEX IF NOT EXISTS idx_audit_events_run_id ON audit_events(run_id);

-- runs(mission_id): get_mission()/mission run listings join runs by mission.
CREATE INDEX IF NOT EXISTS idx_runs_mission_id ON runs(mission_id);
