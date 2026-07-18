-- 0026: Add priority column to missions for parallel coordination.
-- Higher priority = launched first. 0 = normal, 2 = high, -1 = low.

ALTER TABLE missions ADD COLUMN priority INTEGER NOT NULL DEFAULT 0;
