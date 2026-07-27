-- 0031_actor_steering.sql — mid-flight actor steering + opt-in parent wakeup (CASE-04).
--
-- Two gaps this closes:
--
--   1. A running actor could not be corrected. `atlas_actor` exposed only
--      run/spawn/status/wait/cancel, so an operator or parent agent watching a
--      child go the wrong way had exactly one lever: kill it and start over.
--      Steering messages are queued here and drained by the child itself at its
--      next model-call boundary (the same pre_llm_call seam the completion
--      inbox already uses), so no IPC or live process handle is needed and a
--      message survives a worker restart.
--
--   2. A detached actor's completion sat in actor_deliveries until the parent
--      happened to take another turn. `wakeup_parent` records, per actor, that
--      the operator asked for a follow-up run to be started in the parent's
--      session when the child finishes. Opt-in and off by default: it starts
--      agent execution nobody typed a prompt for.

PRAGMA foreign_keys = ON;

-- Bare ADD COLUMN is deliberately non-idempotent; db._apply_sql_tolerant
-- swallows "duplicate column name" for exactly this case (precedent: 0005, 0006).
ALTER TABLE actors ADD COLUMN wakeup_parent INTEGER NOT NULL DEFAULT 0;

-- Steering messages are append-only and delivered at most once. `seq` is
-- monotonic per actor so a drain can be ordered and a partial delivery is
-- resumable; status is the delivery latch rather than a DELETE, so the
-- transcript of what was injected into a child stays auditable.
CREATE TABLE IF NOT EXISTS actor_steering (
    id            TEXT PRIMARY KEY,
    actor_id      TEXT NOT NULL REFERENCES actors(id),
    seq           INTEGER NOT NULL,
    message       TEXT NOT NULL,
    origin        TEXT NOT NULL DEFAULT 'agent',
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'delivered')),
    created_at    TEXT NOT NULL,
    delivered_at  TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_steering_actor_seq
    ON actor_steering(actor_id, seq);

-- The drain query: pending messages for one actor, in order.
CREATE INDEX IF NOT EXISTS idx_actor_steering_pending
    ON actor_steering(actor_id, status);
