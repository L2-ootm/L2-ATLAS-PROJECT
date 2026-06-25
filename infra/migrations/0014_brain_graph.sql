-- 0014_brain_graph.sql — durable bounded evidence graph (Phase 10.2).

CREATE TABLE IF NOT EXISTS brain_nodes (
    id              TEXT PRIMARY KEY,
    entity_type     TEXT NOT NULL,
    label           TEXT NOT NULL,
    project_id      TEXT,
    source_id       TEXT NOT NULL,
    source_version  TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    confidence      REAL NOT NULL,
    metadata_json   TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_brain_nodes_project_type
    ON brain_nodes(project_id, entity_type, updated_at);

CREATE TABLE IF NOT EXISTS brain_edges (
    source_id       TEXT NOT NULL,
    target_id       TEXT NOT NULL,
    relation        TEXT NOT NULL,
    project_id      TEXT,
    confidence      REAL NOT NULL DEFAULT 1.0,
    metadata_json   TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(source_id, target_id, relation),
    FOREIGN KEY(source_id) REFERENCES brain_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY(target_id) REFERENCES brain_nodes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_brain_edges_source
    ON brain_edges(source_id, project_id, relation);
CREATE INDEX IF NOT EXISTS idx_brain_edges_target
    ON brain_edges(target_id, project_id, relation);
