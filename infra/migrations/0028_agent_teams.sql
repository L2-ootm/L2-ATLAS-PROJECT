-- 0028: agent presets, teams, and round-robin group-chat runs.
-- See docs/plans/2026-07-18-agent-teams-and-group-chat-design.md.
--
-- agent_presets: a single reusable agent configuration (role/goal/model).
-- teams + team_members: a named, ordered roster of presets.
-- team_runs + team_chat_messages: one team invocation's shared, ordered,
-- cursor-consumed message log (the "group chat" buffer). Members take turns
-- via the existing actors table (spawn_actor/wait_for_actor, unchanged) —
-- this migration adds no new process/runtime table.

CREATE TABLE IF NOT EXISTS agent_presets (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    role_label    TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    goal_template TEXT NOT NULL,
    model         TEXT,
    provider      TEXT,
    mode          TEXT NOT NULL DEFAULT 'joined'
                  CHECK (mode IN ('joined', 'detached')),
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teams (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS team_members (
    team_id   TEXT NOT NULL REFERENCES teams(id),
    preset_id TEXT NOT NULL REFERENCES agent_presets(id),
    position  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (team_id, preset_id)
);

CREATE INDEX IF NOT EXISTS idx_team_members_team ON team_members(team_id);

CREATE TABLE IF NOT EXISTS team_runs (
    id             TEXT PRIMARY KEY,
    team_id        TEXT NOT NULL REFERENCES teams(id),
    parent_run_id  TEXT REFERENCES runs(id),
    mission_id     TEXT REFERENCES missions(id),
    status         TEXT NOT NULL DEFAULT 'queued'
                   CHECK (status IN ('queued', 'running', 'completed',
                                     'failed', 'cancelled')),
    max_rounds     INTEGER NOT NULL DEFAULT 6,
    current_round  INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    started_at     TEXT,
    finished_at    TEXT,
    updated_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_team_runs_team ON team_runs(team_id);
CREATE INDEX IF NOT EXISTS idx_team_runs_mission ON team_runs(mission_id);

CREATE TABLE IF NOT EXISTS team_chat_messages (
    id              TEXT PRIMARY KEY,
    team_run_id     TEXT NOT NULL REFERENCES team_runs(id),
    seq             INTEGER NOT NULL,
    round           INTEGER NOT NULL DEFAULT 0,
    sender_actor_id TEXT,
    sender_role     TEXT NOT NULL DEFAULT 'orchestrator',
    target          TEXT NOT NULL DEFAULT 'all',
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_team_chat_messages_run_seq
    ON team_chat_messages(team_run_id, seq);
