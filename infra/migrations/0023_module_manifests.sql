-- 0023: manifest-driven module registry (module framework design 2026-07-16).
-- ADDITIVE — extends the 0007 modules table so discovered, user-created
-- modules (module.yaml manifests) live in the same registry as the seeded
-- built-ins. db.py's tolerant runner skips duplicate-column errors on re-apply.
--
-- version/source_path/manifest_json describe a discovered manifest module
-- (empty for legacy seeded rows). missing=1 marks modules whose source
-- directory vanished: state preserved, capabilities hidden.

ALTER TABLE modules ADD COLUMN version TEXT NOT NULL DEFAULT '';
ALTER TABLE modules ADD COLUMN source_path TEXT NOT NULL DEFAULT '';
ALTER TABLE modules ADD COLUMN manifest_json TEXT NOT NULL DEFAULT '';
ALTER TABLE modules ADD COLUMN missing INTEGER NOT NULL DEFAULT 0;
ALTER TABLE modules ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';
