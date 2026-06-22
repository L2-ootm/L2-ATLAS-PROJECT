-- 0013_tool_approvals.sql — gated write/shell tool calls (Phase 10.0.4).
--
-- Mirrors atlas_core.schemas.tool.ToolApproval 1:1 and generalizes the Phase C
-- discord_approvals pattern to all tools. A row is created `pending` by
-- `tool_service.invoke` when policy.decide returns requires_approval (write/shell
-- risk_level); `tool_service.approve` runs the deferred adapter and flips it to
-- `executed` (or `failed`); `reject` flips it to `rejected`. Every executed call
-- also emits an audit_events row (event_type tool_completed/tool_failed) — that
-- is the FK-bearing trail; this table is the operator-facing queue, so run_id is
-- stored but NOT FK-enforced here.
--
-- Idempotent (CREATE … IF NOT EXISTS). `args` and `result` are JSON strings
-- (D-013); `args` is secret-redacted before insert (tool_service).

CREATE TABLE IF NOT EXISTS tool_approvals (
    id            TEXT PRIMARY KEY,
    tool_name     TEXT NOT NULL,
    risk_level    TEXT NOT NULL,
    args          TEXT NOT NULL DEFAULT '{}',
    summary       TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pending',
    reason        TEXT,
    result        TEXT,
    run_id        TEXT NOT NULL DEFAULT 'operator',
    requested_at  TEXT NOT NULL,
    decided_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_tool_approvals_status
    ON tool_approvals(status, requested_at);
