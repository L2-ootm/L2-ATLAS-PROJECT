-- 0032: truthful team lifecycle and verified cancellation cleanup.
--
-- These columns are additive so historical team/run attribution remains intact.
-- Existing CHECK constraints are deliberately left unchanged.

ALTER TABLE teams ADD COLUMN archived_at TEXT;

ALTER TABLE team_runs ADD COLUMN cancel_requested_at TEXT;
ALTER TABLE team_runs ADD COLUMN worker_pid INTEGER;
ALTER TABLE team_runs ADD COLUMN cleanup_status TEXT NOT NULL DEFAULT 'not_requested';
ALTER TABLE team_runs ADD COLUMN cleanup_error TEXT;

CREATE INDEX IF NOT EXISTS idx_teams_archived_at ON teams(archived_at);
CREATE INDEX IF NOT EXISTS idx_team_runs_worker_pid ON team_runs(worker_pid);
