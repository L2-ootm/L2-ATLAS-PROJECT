-- ATLAS migration 0002: Source trust metadata + MemoryProvenance table (D-019 Phase 6)
PRAGMA foreign_keys = ON;

-- Extend sources table with trust and run-linkage metadata
ALTER TABLE sources ADD COLUMN untrusted INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sources ADD COLUMN ingested_by_run_id TEXT;

-- Provenance record for every write to any ATLAS memory layer (D-019)
CREATE TABLE IF NOT EXISTS memory_provenance (
    id               TEXT PRIMARY KEY,
    layer            TEXT NOT NULL,
    item_id          TEXT NOT NULL,
    run_id           TEXT,
    source_id        TEXT REFERENCES sources(id),
    audit_event_id   TEXT REFERENCES audit_events(id),
    operator_id      TEXT,
    sensitivity      TEXT NOT NULL DEFAULT 'internal',
    untrusted        INTEGER NOT NULL DEFAULT 0,
    written_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_provenance_item ON memory_provenance(item_id);
CREATE INDEX IF NOT EXISTS idx_memory_provenance_run  ON memory_provenance(run_id);
