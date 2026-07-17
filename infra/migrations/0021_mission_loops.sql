-- 0021_mission_loops.sql — durable long-horizon mission judge loop.
--
-- A mission remains the execution aggregate and each attempt remains a normal
-- run. These tables only add loop policy/state and immutable per-run verdicts.

CREATE TABLE IF NOT EXISTS mission_loops (
    mission_id                  TEXT PRIMARY KEY REFERENCES missions(id),
    session_id                  TEXT,
    objective                   TEXT NOT NULL,
    state                       TEXT NOT NULL DEFAULT 'active',
    max_runs                    INTEGER NOT NULL DEFAULT 12,
    runs_used                   INTEGER NOT NULL DEFAULT 0,
    judge_model                 TEXT NOT NULL DEFAULT '',
    consecutive_parse_failures  INTEGER NOT NULL DEFAULT 0,
    last_run_id                 TEXT,
    last_verdict                TEXT NOT NULL DEFAULT '',
    last_reason                 TEXT NOT NULL DEFAULT '',
    created_at                  TEXT NOT NULL,
    updated_at                  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mission_loops_state
    ON mission_loops(state);

CREATE TABLE IF NOT EXISTS run_judgements (
    id              TEXT PRIMARY KEY,
    mission_id      TEXT NOT NULL REFERENCES missions(id),
    run_id          TEXT NOT NULL UNIQUE REFERENCES runs(id),
    verdict         TEXT NOT NULL,
    reason          TEXT NOT NULL DEFAULT '',
    parse_failed    INTEGER NOT NULL DEFAULT 0,
    model_provider  TEXT NOT NULL DEFAULT '',
    model_id        TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_judgements_mission
    ON run_judgements(mission_id, created_at);

