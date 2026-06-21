-- 0011_wiki_embeddings_meta.sql — semantic-search bookkeeping (Phase B, B-WP4).
--
-- Tracks which wiki page has an embedding, under which model/dim, and the body
-- hash it was computed from — so `atlas wiki reindex` can detect stale or missing
-- embeddings and repair only what changed.
--
-- The embedding vectors themselves live in a `vec0` virtual table (`wiki_vec`)
-- that is created lazily in Python AFTER loading the sqlite-vec extension
-- (wiki_service._ensure_vec_table). It is deliberately NOT created here: the
-- migration runner uses a plain connection with no extension loaded, so a
-- `CREATE VIRTUAL TABLE ... USING vec0(...)` statement would fail at apply time.
--
-- Idempotent (CREATE … IF NOT EXISTS). page_id mirrors wiki_pages.id (not
-- FK-enforced, consistent with the project's v1 deferral convention).

CREATE TABLE IF NOT EXISTS wiki_embeddings_meta (
    page_id     TEXT PRIMARY KEY,
    model       TEXT NOT NULL,
    dim         INTEGER NOT NULL,
    body_sha    TEXT NOT NULL,
    embedded_at TEXT NOT NULL
);
