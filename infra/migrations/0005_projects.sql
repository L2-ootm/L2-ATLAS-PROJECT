-- ATLAS migration 0005: Projects (folder-backed working directories) + mission linkage (P3)
-- ADDITIVE MIGRATION — mirrors the 0002 pattern: CREATE TABLE IF NOT EXISTS for new
-- tables/indexes (re-apply safe) plus a bare ADD COLUMN for the linkage (applied once
-- on a fresh DB, per the fresh-machine bootstrap convention in docs/operations/RUNNING.md).
PRAGMA foreign_keys = ON;

-- A Project maps a name to a working directory on disk. Missions belonging to a
-- project execute with root_path as their working directory (P3 / cloud-later).
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    root_path   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Link missions to a project (nullable FK; the legacy free-text `project` tag from
-- 0001 is retained for back-compat). SQLite permits a REFERENCES clause on ADD COLUMN
-- because the column defaults to NULL.
ALTER TABLE missions ADD COLUMN project_id TEXT REFERENCES projects(id);

CREATE INDEX IF NOT EXISTS idx_missions_project_id ON missions(project_id);
CREATE INDEX IF NOT EXISTS idx_projects_root_path  ON projects(root_path);
