-- ATLAS migration 0008: mission archive retention metadata.
-- ADDITIVE + NON-DESTRUCTIVE. Archived missions keep their audit trail until a
-- retention sweep deletes the mission plus dependent run/audit/artifact rows.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS mission_archive (
    mission_id   TEXT PRIMARY KEY REFERENCES missions(id) ON DELETE CASCADE,
    archived_at  TEXT NOT NULL,
    delete_after TEXT NOT NULL
);
