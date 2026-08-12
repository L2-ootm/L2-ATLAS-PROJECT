-- 0034: module capabilities v2 — typed records, MCP registry, agent scratchpad.
-- Contract: docs/plans/2026-08-12-module-capabilities-v2-and-outreach-design.md
--
-- Three tables, one theme: capability a module declares but ATLAS executes.
-- No per-module DDL — a module is data, so removing one must never require a
-- schema migration.

-- Typed record store behind every module collection (the CRM substrate).
-- (module_id, collection, id) is the natural key: ids are only unique inside
-- their collection, so two modules may both hold a "prospects/acme" row.
-- Rows outlive deactivation (toggling a module must not destroy operator data)
-- and outlive a soft delete (deleted_at set, payload retained for undo).
CREATE TABLE IF NOT EXISTS module_records (
    module_id      TEXT NOT NULL,
    collection     TEXT NOT NULL,
    id             TEXT NOT NULL,
    data_json      TEXT NOT NULL DEFAULT '{}',
    status         TEXT NOT NULL DEFAULT 'active'
                   CHECK(status IN ('active','archived')),
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    deleted_at     TEXT,
    created_by_run TEXT,
    updated_by_run TEXT,
    PRIMARY KEY (module_id, collection, id)
);

-- The board query: one collection of one module, live rows, newest first.
CREATE INDEX IF NOT EXISTS idx_module_records_scan
    ON module_records(module_id, collection, deleted_at, updated_at DESC);

-- MCP servers ATLAS knows about: declared by a module manifest or added by the
-- operator. Enabled rows are projected into the foundation config at run start
-- (managed_by='atlas'); rows the operator hand-authored in Hermes are never
-- imported, so ownership stays unambiguous in both directions.
CREATE TABLE IF NOT EXISTS mcp_servers (
    name            TEXT PRIMARY KEY,
    module_id       TEXT NOT NULL DEFAULT '',
    transport       TEXT NOT NULL DEFAULT 'stdio'
                    CHECK(transport IN ('stdio','http')),
    command         TEXT NOT NULL DEFAULT '',
    args_json       TEXT NOT NULL DEFAULT '[]',
    env_json        TEXT NOT NULL DEFAULT '{}',
    url             TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    enabled         INTEGER NOT NULL DEFAULT 0,
    managed_by      TEXT NOT NULL DEFAULT 'atlas',
    source          TEXT NOT NULL DEFAULT 'operator'
                    CHECK(source IN ('operator','module')),
    last_status     TEXT NOT NULL DEFAULT 'unknown'
                    CHECK(last_status IN ('unknown','ok','error','disabled')),
    last_checked_at TEXT,
    last_error      TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_enabled
    ON mcp_servers(enabled, name);

-- Agent scratchpad + the disposable-artifact substrate. Deliberately one table
-- for both: a scratch note and a throwaway generated tool differ only in kind
-- and TTL policy, and both need the same sweep. `pinned` survives every sweep
-- (the promotion path out of disposability).
CREATE TABLE IF NOT EXISTS scratchpad_entries (
    id           TEXT PRIMARY KEY,
    scope        TEXT NOT NULL DEFAULT 'run'
                 CHECK(scope IN ('run','session','project','global')),
    owner        TEXT NOT NULL DEFAULT '',
    run_id       TEXT,
    session_id   TEXT,
    kind         TEXT NOT NULL DEFAULT 'note'
                 CHECK(kind IN ('note','plan','finding','draft','artifact','tool')),
    title        TEXT NOT NULL DEFAULT '',
    body         TEXT NOT NULL DEFAULT '',
    path         TEXT NOT NULL DEFAULT '',
    ttl_policy   TEXT NOT NULL DEFAULT 'session'
                 CHECK(ttl_policy IN ('run','session','next_startup','hours','permanent')),
    expires_at   TEXT,
    pinned       INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scratchpad_scope
    ON scratchpad_entries(scope, owner, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_scratchpad_sweep
    ON scratchpad_entries(pinned, ttl_policy, expires_at);
