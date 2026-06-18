-- ATLAS migration 0006: per-run agent runtime selector (P4 — modular agents)
-- ADDITIVE MIGRATION — mirrors the 0005 pattern: a bare ADD COLUMN with a constant
-- DEFAULT, applied once on a fresh DB per the fresh-machine bootstrap convention in
-- docs/operations/RUNNING.md. SQLite allows NOT NULL on ADD COLUMN when a constant
-- DEFAULT is supplied, so existing rows backfill to 'native'.
PRAGMA foreign_keys = ON;

-- Records which AgentRuntime executed a run: 'native' (in-process / Hermes path)
-- or 'claude_code' (Claude Agent SDK on the operator's local Claude Code session).
ALTER TABLE runs ADD COLUMN agent_runtime TEXT NOT NULL DEFAULT 'native';

CREATE INDEX IF NOT EXISTS idx_runs_agent_runtime ON runs(agent_runtime);
