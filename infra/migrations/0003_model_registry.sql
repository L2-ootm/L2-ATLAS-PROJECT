-- 0003: model registry for the AI router (D-017).
-- Mirrors atlas_runtime/model_registry.py ensure_schema(); both are
-- CREATE TABLE IF NOT EXISTS so apply order is idempotent.
-- The Rust gateway (D-022) reads this table directly for /models.

CREATE TABLE IF NOT EXISTS model_registry (
    model_id    TEXT PRIMARY KEY,
    provider    TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1
);
