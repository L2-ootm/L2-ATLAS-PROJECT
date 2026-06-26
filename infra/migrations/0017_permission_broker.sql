-- 0017_permission_broker.sql — surface-scoped permission broker foundation (PERM-01).
--
-- Purely ADDITIVE extension of 0013_tool_approvals: surface anchor + expiry + nonce
-- columns on tool_approvals, a scoped pending index, and two new tables
-- (approval_channels, session_allow_rules). No table is dropped or rewritten.
--
-- Soft-FK precedent (0013/0016): surface_session_id is STORED + INDEXED, NOT
-- REFERENCES-enforced. Legacy 'operator'/NULL rows must survive under
-- PRAGMA foreign_keys=ON, so adding a REFERENCES constraint here is forbidden.
-- All new columns are nullable so existing rows load with NULL surface fields.
--
-- executescript caveat: db.py applies this via executescript and swallows
-- 'duplicate column name' (so the bare ADD COLUMN statements are idempotent on a
-- drifted DB). Do NOT ;-split any trigger BEGIN..END body — keep it intact.

-- Surface anchor + lifecycle columns (additive, idempotent). All nullable.
ALTER TABLE tool_approvals ADD COLUMN surface_session_id TEXT;
ALTER TABLE tool_approvals ADD COLUMN surface_kind TEXT;
ALTER TABLE tool_approvals ADD COLUMN workspace_root TEXT;
ALTER TABLE tool_approvals ADD COLUMN expiry_at TEXT;
ALTER TABLE tool_approvals ADD COLUMN decision TEXT;
ALTER TABLE tool_approvals ADD COLUMN nonce TEXT;
ALTER TABLE tool_approvals ADD COLUMN args_normalized TEXT;

-- Scoped actionable lookup: the broker lists pending, non-expired approvals for a
-- single surface session (PERM-02/04). Composite over (session, status, expiry).
CREATE INDEX IF NOT EXISTS idx_tool_approvals_surface
    ON tool_approvals(surface_session_id, status, expiry_at);

-- approval_channels — presence of an unrevoked row is the PERM-05 fail-closed gate
-- for headless ('api') surfaces. One row per surface session (TEXT PK).
CREATE TABLE IF NOT EXISTS approval_channels (
    surface_session_id  TEXT PRIMARY KEY,
    surface_kind        TEXT NOT NULL,
    registered_at       TEXT NOT NULL,
    revoked_at          TEXT
);

-- session_allow_rules — PERM-07 scope-bound allow store. Every rule is anchored to
-- one surface_session_id + workspace_root + surface_kind + tool_name + arg_pattern;
-- there is NO global policy row. rule_kind is allow_once|allow_session|allow_always.
-- surface_session_id is stored, NOT REFERENCES-enforced (soft FK, 0013/0016).
CREATE TABLE IF NOT EXISTS session_allow_rules (
    id                  TEXT PRIMARY KEY,
    surface_session_id  TEXT NOT NULL,
    workspace_root      TEXT NOT NULL,
    surface_kind        TEXT NOT NULL,
    tool_name           TEXT NOT NULL,
    arg_pattern         TEXT NOT NULL,
    rule_kind           TEXT NOT NULL,
    created_at          TEXT NOT NULL
);

-- Non-unique scope index: rules are resolved per session, never globally.
CREATE INDEX IF NOT EXISTS idx_session_allow_rules_session
    ON session_allow_rules(surface_session_id);

-- Terminal approvals are DB-immutable: any UPDATE on an executed/rejected/failed row
-- aborts so the at-most-once decision survives buggy callers (T-10.5-02-TRIGGER).
-- Keep the BEGIN..END body intact — db.py runs executescript and must not ;-split it.
CREATE TRIGGER IF NOT EXISTS tool_approvals_terminal_immutable
BEFORE UPDATE ON tool_approvals
WHEN OLD.status IN ('executed', 'rejected', 'failed')
BEGIN
    SELECT RAISE(ABORT, 'terminal tool approvals are immutable');
END;
