-- 0009_focus.sql — Command Center Focus entity (CC-1, phase 10.0.3-command-center).
--
-- The operator's current working focus: title, framework, priorities, drivers.
-- A single row is 'active' at a time (the Current Focus); promoting a new one
-- archives the prior (enforced in focus_service). priorities/drivers are JSON
-- array strings (mirrors audit_events.data). DDL mirrors atlas_core.schemas.Focus 1:1.
--
-- Idempotent (CREATE … IF NOT EXISTS). project_id is NOT FK-enforced in v1
-- (mirrors missions.project_id / SCHEMA-04 deferral).

CREATE TABLE IF NOT EXISTS focus (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    framework   TEXT NOT NULL DEFAULT '',
    priorities  TEXT NOT NULL DEFAULT '[]',
    drivers     TEXT NOT NULL DEFAULT '[]',
    project_id  TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_focus_status ON focus(status);
