-- 0025_graph_scopes.sql — operator-defined Graphify scopes (custom graph tabs).
--
-- The built-in scopes (atlas/global/projects/obsidian) were hardcoded to the
-- original operator's folders. Custom scopes let any user point a graph tab at
-- their own folder: kind 'markdown' builds one corpus graph of the folder,
-- kind 'projects' builds one cluster per child directory (a projects overview).

CREATE TABLE IF NOT EXISTS graph_scopes (
    id          TEXT PRIMARY KEY,          -- slug derived from the label
    label       TEXT NOT NULL,
    root_path   TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'markdown',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
