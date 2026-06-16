-- 0004: provider/model_v2/route registry (PROV-01, MOD-03/04/05).
-- Mirrors atlas_core.schemas.registry_v2 / the 10.3 v2 discovery ensure_schema();
-- CREATE TABLE IF NOT EXISTS so apply order is idempotent.
--
-- ADDITIVE MIGRATION — this file never DROPs/ALTERs the legacy model_registry table
-- (created in 0003). The Rust gateway (D-022) reads model_registry directly for
-- /v1/models until the 10.3 reader cutover. Both tables coexist through 10.0–10.2.
--
-- Pragmas (WAL, foreign_keys) are declared once in 0001; do NOT redeclare here.

-- ---------------------------------------------------------------------------
-- 1. provider_registry — one row per known provider identity (PROV-01).
--    Distinct from credential (auth store), runtime, model, and route.
--    Logical FK: model_registry_v2.provider_id references this table, but FK
--    enforcement is NOT active in v1.1 (see no-FK note below).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS provider_registry (
    provider_id       TEXT PRIMARY KEY,
    display_name      TEXT,
    auth_type         TEXT,
    default_base_url  TEXT,
    api_modes_json    TEXT NOT NULL DEFAULT '{}',
    source            TEXT,
    status            TEXT,
    last_checked      TEXT,
    last_error        TEXT
);

-- ---------------------------------------------------------------------------
-- 2. model_registry_v2 — one row per (model, provider, source) triple.
--
--    COMPOSITE PK (model_id, provider_id, source) gives idempotent multi-source
--    discovery (MOD-03): the same model arriving from two sources (e.g. the
--    gateway sidecar + a manual import) gets two independent rows, never a
--    collision.
--
--    STATUS vs AUTH_STATUS are DISTINCT columns (MOD-05):
--      status      — model reachability/lifecycle: available | offline |
--                    unsupported | unknown
--      auth_status — credential state derived at discovery time from the file
--                    auth store: available | auth_present | needs_api_key |
--                    needs_login | offline | rate_limited | expired | unknown
--    auth_status is DERIVED (never a stored secret). Only provider_id + the
--    derived status live here; secret material lives solely in ~/.atlas/auth.json
--    (SEC-01, credential boundary — see CONTEXT Area 1/3).
--
--    DEACTIVATED_AT — nullable ISO-8601 timestamp for source-scoped soft-delete
--    (MOD-04). Setting deactivated_at for source=X never touches rows from
--    source=Y; one provider going offline cannot deactivate another source's
--    models. Soft-delete preserves routing history (mirrors v1 active=0 rationale
--    in atlas_runtime/model_registry.py).
--
--    IDEMPOTENT UPSERT CONTRACT (owned by 10.3, documented here to justify DDL):
--
--      INSERT INTO model_registry_v2
--        (model_id, provider_id, source, api_mode, status, auth_status,
--         context_window, metadata_json, first_seen, last_seen, deactivated_at)
--      VALUES (:model_id, :provider_id, :source, :api_mode, :status, :auth_status,
--              :context_window, :metadata_json, :now, :now, NULL)
--      ON CONFLICT(model_id, provider_id, source) DO UPDATE SET
--        api_mode       = excluded.api_mode,
--        status         = excluded.status,
--        auth_status    = excluded.auth_status,
--        context_window = excluded.context_window,
--        metadata_json  = excluded.metadata_json,
--        last_seen      = excluded.last_seen,
--        deactivated_at = NULL;
--        -- first_seen intentionally NOT in SET clause: preserve the original
--        -- discovery timestamp across all subsequent re-discoveries (MOD-03).
--
--    NO FOREIGN KEY on provider_id in v1.1: discovery may write a model row
--    before the provider_registry row exists (ordering not guaranteed). The
--    logical relationship is documented above; hard FK enforcement is deferred
--    to v1.2.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS model_registry_v2 (
    model_id        TEXT NOT NULL,
    provider_id     TEXT NOT NULL,
    source          TEXT NOT NULL,
    api_mode        TEXT,
    status          TEXT,
    auth_status     TEXT,
    context_window  INTEGER,
    metadata_json   TEXT NOT NULL DEFAULT '{}',
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    deactivated_at  TEXT,
    PRIMARY KEY(model_id, provider_id, source)
);

-- Indexes to support the source-scoped deactivation pass (10.3):
--   UPDATE model_registry_v2 SET deactivated_at=:now
--   WHERE source=:source AND deactivated_at IS NULL
--     AND (model_id, provider_id) NOT IN (<incoming-this-source>);
CREATE INDEX IF NOT EXISTS idx_mrv2_source
    ON model_registry_v2(source);

CREATE INDEX IF NOT EXISTS idx_mrv2_source_deact
    ON model_registry_v2(source, deactivated_at);

-- ---------------------------------------------------------------------------
-- 3. route_policy — task-class → provider/model routing map.
--
--    SCHEMA-ONLY IN v1.1 — no reader/writer is wired in this milestone.
--    Routing enforcement and the `atlas route` CLI are v1.2+ features
--    (ROUTE-01/02, deferred). This table is created now to avoid a separate
--    migration churn in v1.2. A future executor must NOT assume route_policy
--    is populated or consulted by any v1.1 code path (LANDMINE 4).
--
--    NO FOREIGN KEY on provider_id in v1.1: same rationale as model_registry_v2
--    above; hard FK deferred to v1.2.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS route_policy (
    task_class            TEXT PRIMARY KEY,
    provider_id           TEXT,
    model_id              TEXT,
    fallback_policy_json  TEXT NOT NULL DEFAULT '{}',
    updated_at            TEXT
);

-- ---------------------------------------------------------------------------
-- COMPAT VIEW NOTE (do NOT apply this DDL in 0004 — 10.3 cutover artifact only)
--
-- The Rust gateway list_models() reads named columns from model_registry:
--   SELECT model_id, provider, source, first_seen, last_seen, active
--   FROM model_registry ORDER BY model_id LIMIT ?1
-- (verified: native/atlas-core-rs/crates/atlas-gateway/src/db.rs:258)
--
-- At the 10.3 reader cutover, once the legacy model_registry table is renamed
-- or retired, the recommended drop-in replacement is:
--
-- CREATE VIEW model_registry AS
--   SELECT model_id,
--          provider_id AS provider,
--          source,
--          first_seen,
--          last_seen,
--          CASE WHEN deactivated_at IS NULL THEN 1 ELSE 0 END AS active
--   FROM model_registry_v2;
--
-- This view exposes the exact six named columns the gateway expects, making
-- the reader cutover transparent (no gateway code change required). It can
-- only land AFTER the 0003 model_registry table is retired, because a view
-- and a table cannot share the same name. Until then both tables coexist and
-- the gateway keeps reading the legacy table (0003) unchanged.
-- ---------------------------------------------------------------------------
