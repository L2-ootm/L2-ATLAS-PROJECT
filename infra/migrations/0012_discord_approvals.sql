-- 0012_discord_approvals.sql — gated Discord write requests (Phase C).
--
-- Mirrors atlas_core.schemas.discord.DiscordApproval 1:1. A row is created
-- `pending` by `atlas discord propose`; `atlas discord approve` executes the
-- write via the sidecar and flips it to `executed` (or `failed`); `reject`
-- flips it to `rejected`. Every executed write also emits an audit_events row
-- with event_type='discord_action' (the FK-bearing trail); this table is the
-- operator-facing queue, so run_id is stored but NOT FK-enforced here — the
-- emitted audit event carries the runs(id) FK instead.
--
-- Idempotent (CREATE … IF NOT EXISTS). `params` and `result` are JSON strings
-- (D-013); `params` is secret-redacted before insert.

CREATE TABLE IF NOT EXISTS discord_approvals (
    id            TEXT PRIMARY KEY,
    action        TEXT NOT NULL,
    guild_id      TEXT NOT NULL,
    target_id     TEXT,
    params        TEXT NOT NULL DEFAULT '{}',
    summary       TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pending',
    reason        TEXT,
    result        TEXT,
    run_id        TEXT NOT NULL DEFAULT 'operator',
    requested_at  TEXT NOT NULL,
    decided_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_discord_approvals_status
    ON discord_approvals(status, requested_at);
