-- 0010_goal_model.sql — Command Center goal hierarchy (loop-engineering slice,
-- phase 10.0.3-command-center).
--
-- Focus → Goals → Tasks, plus Observations attached to goals/runs. Goals nest
-- via parent_goal_id (sub-goals). The context-assembly step walks this tree to
-- synthesize loop-engineered run instructions; the compounding loop appends
-- Observations on run completion. DDL mirrors atlas_core.schemas Goal/Task/
-- Observation 1:1.
--
-- Idempotent (CREATE … IF NOT EXISTS). focus_id/parent_goal_id/goal_id/run_id are
-- NOT FK-enforced in v1 (mirrors missions.project_id / SCHEMA-04 deferral).

CREATE TABLE IF NOT EXISTS goals (
    id              TEXT PRIMARY KEY,
    focus_id        TEXT,
    parent_goal_id  TEXT,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'open',
    position        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goals_focus ON goals(focus_id);
CREATE INDEX IF NOT EXISTS idx_goals_parent ON goals(parent_goal_id);
CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    goal_id     TEXT NOT NULL,
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'todo',
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_goal ON tasks(goal_id);

CREATE TABLE IF NOT EXISTS observations (
    id          TEXT PRIMARY KEY,
    goal_id     TEXT,
    run_id      TEXT,
    body        TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'operator',
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_observations_goal ON observations(goal_id);
CREATE INDEX IF NOT EXISTS idx_observations_run ON observations(run_id);
