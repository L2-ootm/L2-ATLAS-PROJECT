-- 0024_mission_execution_kind.sql — separate user-facing Missions from
-- compatibility execution records used by chat and synthetic audit anchors.

ALTER TABLE missions ADD COLUMN record_kind TEXT NOT NULL DEFAULT 'mission'
    CHECK (record_kind IN ('mission', 'chat', 'system'));

-- Synthetic audit anchor, never an operator Mission.
UPDATE missions SET record_kind = 'system' WHERE id = 'operator';

-- Prior WebUI/Console prompt runs were attached to their surface session.
-- Command Center launches are intentionally not surface-attached.
UPDATE missions
SET record_kind = 'chat'
WHERE id IN (
    SELECT DISTINCT mission_id
    FROM runs
    WHERE session_id IS NOT NULL
)
AND id <> 'operator';

CREATE INDEX IF NOT EXISTS idx_missions_record_kind_created
    ON missions(record_kind, created_at DESC);
