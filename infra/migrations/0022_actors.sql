-- 0022: durable actor supervisor (subagent orchestration design 2026-07-16).
-- actors: one row per spawned child agent. Flat, serializable state machine:
--   queued -> running -> completed | failed | cancelled | orphaned
-- actor_deliveries: durable completion inbox with a short claim lease so a
-- parent receives each detached result exactly once, surviving crashes
-- between claim and acknowledge.

CREATE TABLE IF NOT EXISTS actors (
    id               TEXT PRIMARY KEY,
    parent_run_id    TEXT NOT NULL REFERENCES runs(id),
    parent_actor_id  TEXT,
    session_id       TEXT,
    idempotency_key  TEXT NOT NULL UNIQUE,
    role             TEXT NOT NULL DEFAULT 'worker',
    goal             TEXT NOT NULL,
    model            TEXT,
    mode             TEXT NOT NULL DEFAULT 'joined'
                     CHECK (mode IN ('joined', 'detached')),
    status           TEXT NOT NULL DEFAULT 'queued'
                     CHECK (status IN ('queued', 'running', 'completed',
                                       'failed', 'cancelled', 'orphaned')),
    workspace_root   TEXT,
    depth            INTEGER NOT NULL DEFAULT 1,
    child_run_id     TEXT,
    pid              INTEGER,
    owner_token      TEXT,
    heartbeat_at     TEXT,
    result_preview   TEXT,
    error            TEXT,
    created_at       TEXT NOT NULL,
    started_at       TEXT,
    finished_at      TEXT,
    updated_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_actors_parent_run ON actors(parent_run_id);
CREATE INDEX IF NOT EXISTS idx_actors_status ON actors(status);
CREATE INDEX IF NOT EXISTS idx_actors_session ON actors(session_id);

-- Terminal actors are immutable: transitions are monotonic and repeated
-- completion/cancellation must be a no-op in the service layer (which checks
-- status before writing); this trigger backstops any path that forgets.
-- Keep the BEGIN...END body intact — db.py runs executescript and must not
-- ;-split trigger bodies.
CREATE TRIGGER IF NOT EXISTS actors_terminal_immutable
BEFORE UPDATE ON actors
WHEN OLD.status IN ('completed', 'failed', 'cancelled', 'orphaned')
BEGIN
    SELECT RAISE(ABORT, 'terminal actors are immutable');
END;

CREATE TABLE IF NOT EXISTS actor_deliveries (
    actor_id       TEXT PRIMARY KEY REFERENCES actors(id),
    parent_run_id  TEXT NOT NULL,
    session_id     TEXT,
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'claimed', 'delivered', 'consumed')),
    claim_token    TEXT,
    claimed_at     TEXT,
    delivered_at   TEXT,
    payload        TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_actor_deliveries_status
    ON actor_deliveries(status);
CREATE INDEX IF NOT EXISTS idx_actor_deliveries_parent_run
    ON actor_deliveries(parent_run_id);
