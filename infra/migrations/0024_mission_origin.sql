-- 0024_mission_origin.sql — separate operator-authored missions from prompt wrappers.
--
-- Every surface prompt is executed as mission+run, so the missions table mixes
-- deliberate operator missions with per-prompt wrappers and machine-created
-- internals. `origin` makes the distinction explicit:
--   'operator' — authored intentionally (Missions page, Command Center launch,
--                /goal and /mission slash commands, CLI mission create)
--   'chat'     — auto-created wrapper for a chat/console/TUI prompt
--   'system'   — machine-created (premade operations, actor delegation,
--                the synthetic operator console mission)
--
-- Applied once via schema_migrations (db.apply_migrations); the ALTER is not
-- idempotent by itself, matching the 0005/0006/0023 precedent.

ALTER TABLE missions ADD COLUMN origin TEXT NOT NULL DEFAULT '';

-- Backfill (best-effort heuristics, documented order matters):
-- 1. Long-horizon judge-loop missions are operator goals.
UPDATE missions SET origin='operator'
 WHERE origin='' AND id IN (SELECT mission_id FROM mission_loops);

-- 2. The synthetic operator-console mission is system-internal.
UPDATE missions SET origin='system' WHERE origin='' AND id='operator';

-- 3. Prompt wrappers set title to the first line of the intent, so the intent
--    always starts with the title. Deliberate missions rarely do.
UPDATE missions SET origin='chat'
 WHERE origin='' AND intent <> '' AND substr(intent, 1, length(title)) = title;

-- 4. Everything else is treated as operator-authored.
UPDATE missions SET origin='operator' WHERE origin='';

CREATE INDEX IF NOT EXISTS idx_missions_origin ON missions(origin);
