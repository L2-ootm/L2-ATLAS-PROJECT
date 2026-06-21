"""ATLAS wiki service — ingest, update, search, lint (Phase 6).

Design constraints:
- T-06-05: pathlib.Path(path).resolve().is_file() check before copy (path traversal guard)
- T-06-06: Parameterized queries — never string interpolation in FTS5 search
- T-06-07: AuditEvent.data contains only slug + source_id + op — not body content
- T-06-08: emit() always called AFTER exiting with lock: block (emit-after-lock pattern)
- T-06-SC: sqlite_vec and fastembed imported inside semantic_search() only — never at module level
"""
from __future__ import annotations

import datetime
import hashlib
import pathlib
import re
import shutil
import sqlite3
import threading
from typing import Optional

from atlas_core.schemas.core import AuditEvent, Source, WikiPage
from atlas_runtime.audit_service import emit

# NOTE: DO NOT import sqlite_vec or fastembed at module level — ever.
# These are optional heavy dependencies that must be loaded lazily inside
# semantic_search() inside try/except blocks.

from atlas_wiki import provenance_service


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

OPERATOR_RUN_ID = "operator"


def _ensure_operator_run(conn: sqlite3.Connection, lock: threading.Lock) -> None:
    """Idempotently create the synthetic operator mission/run pair.

    Operator-initiated wiki writes carry run_id="operator", but
    audit_events.run_id is NOT NULL REFERENCES runs(id). On a fresh database
    no such run exists, so every operator write would fail the foreign key
    check. Bootstrap the pseudo-run lazily rather than relaxing the schema —
    the audit chain stays referentially intact.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO missions(id, title, intent, status, project, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    OPERATOR_RUN_ID,
                    "Operator console",
                    "Synthetic mission for operator-initiated writes outside agent runs",
                    "archived",
                    "",
                    now,
                    now,
                ),
            )
            conn.execute(
                "INSERT OR IGNORE INTO runs(id, mission_id, session_id, status, started_at, summary) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    OPERATOR_RUN_ID,
                    OPERATOR_RUN_ID,
                    OPERATOR_RUN_ID,
                    "completed",
                    now,
                    "Synthetic run recording operator-initiated writes",
                ),
            )


def _update_index(wiki_dir: pathlib.Path, conn: sqlite3.Connection) -> None:
    """Rewrite wiki_dir/index.md from DB state — all pages ordered by slug."""
    rows = conn.execute(
        "SELECT slug, title FROM wiki_pages ORDER BY slug"
    ).fetchall()
    lines = ["# ATLAS Wiki Index\n\n"]
    for slug, title in rows:
        lines.append(f"- [{slug}] {title}\n")
    (wiki_dir / "index.md").write_text("".join(lines), encoding="utf-8")


def _append_log(wiki_dir: pathlib.Path, page: WikiPage, event: AuditEvent) -> None:
    """Append an entry to wiki_dir/log.md — always 'a' mode, never 'w'."""
    date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    entry = (
        f"\n## [{date_str}] wiki_update | {page.slug}\n"
        f"- Event: {event.id}\n"
        f"- Body length: {len(page.body)}\n"
    )
    with open(wiki_dir / "log.md", "a", encoding="utf-8") as fh:
        fh.write(entry)


# ---------------------------------------------------------------------------
# Semantic embedding infrastructure (Phase B, B-WP4)
# ---------------------------------------------------------------------------
#
# Embeddings are optional: the heavy deps (sqlite-vec, fastembed) load lazily and
# every entry point degrades to a no-op / FTS5 fallback when they are absent. The
# `wiki_vec` vec0 table is created HERE in Python (after loading the extension),
# never via a SQL migration — the migration runner has no extension loaded.

_EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"  # fastembed default, 384-dim
_EMBED_DIM = 384
_EMBED_MODEL = None  # lazily-constructed TextEmbedding singleton


def _get_embedder():
    """Lazily construct and cache the embedding model (heavy; downloads on first use)."""
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        from fastembed import TextEmbedding  # type: ignore[import]

        _EMBED_MODEL = TextEmbedding()
    return _EMBED_MODEL


def _embed(text: str):
    """Return the embedding vector (numpy array) for `text`."""
    return list(_get_embedder().embed([text]))[0]


def _ensure_vec_table(conn: sqlite3.Connection) -> bool:
    """Load sqlite-vec and create `wiki_vec` if needed. Returns True when the
    semantic store is available on this connection, False otherwise (deps absent)."""
    try:
        import sqlite_vec  # type: ignore[import]

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS wiki_vec USING vec0(embedding float[{_EMBED_DIM}])"
        )
        return True
    except Exception:
        return False


def _index_embedding(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    page_id: str,
    body: str,
) -> bool:
    """Best-effort: compute and store the embedding for one page (keyed by the
    wiki_pages rowid) and stamp `wiki_embeddings_meta`. Never raises — a missing
    optional dep or an embed failure must not fail the page write."""
    try:
        if not _ensure_vec_table(conn):
            return False
        row = conn.execute("SELECT rowid FROM wiki_pages WHERE id=?", (page_id,)).fetchone()
        if row is None:
            return False
        rowid = row[0]
        vector = _embed(body)
        body_sha = hashlib.sha256((body or "").encode("utf-8")).hexdigest()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with lock:
            with conn:
                # vec0 has no UPSERT — replace any existing vector for this rowid.
                conn.execute("DELETE FROM wiki_vec WHERE rowid=?", (rowid,))
                conn.execute(
                    "INSERT INTO wiki_vec(rowid, embedding) VALUES (?, ?)",
                    (rowid, vector.tobytes()),
                )
                conn.execute(
                    "INSERT INTO wiki_embeddings_meta(page_id, model, dim, body_sha, embedded_at) "
                    "VALUES (?,?,?,?,?) ON CONFLICT(page_id) DO UPDATE SET "
                    "model=excluded.model, dim=excluded.dim, body_sha=excluded.body_sha, "
                    "embedded_at=excluded.embedded_at",
                    (page_id, _EMBED_MODEL_NAME, _EMBED_DIM, body_sha, now),
                )
        return True
    except Exception as exc:  # noqa: BLE001 — embeddings are best-effort
        print(f"wiki embedding skipped ({type(exc).__name__}: {exc})")
        return False


def reindex(conn: sqlite3.Connection, lock: threading.Lock) -> int:
    """(Re)embed every wiki page whose stored embedding is missing or stale.

    Returns the number of pages (re)embedded. No-op (0) when the semantic deps are
    unavailable. Staleness is detected by comparing the page body SHA against
    `wiki_embeddings_meta.body_sha`."""
    if not _ensure_vec_table(conn):
        return 0
    try:
        meta = {
            r[0]: r[1]
            for r in conn.execute("SELECT page_id, body_sha FROM wiki_embeddings_meta").fetchall()
        }
    except sqlite3.Error:
        meta = {}
    count = 0
    for page_id, body in conn.execute("SELECT id, body FROM wiki_pages").fetchall():
        body_sha = hashlib.sha256((body or "").encode("utf-8")).hexdigest()
        if meta.get(page_id) == body_sha:
            continue
        if _index_embedding(conn, lock, page_id=page_id, body=body or ""):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ingest_source(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    path: str,
    run_id: str,
    untrusted: bool = False,
    wiki_dir: pathlib.Path,
) -> Source:
    """Ingest a source file into the wiki and return the constructed Source.

    Steps:
    1. Validate path exists and is a file (T-06-05 path traversal guard).
    2. Read bytes, compute SHA-256, construct Source model (Pydantic-first).
    3. Copy file to wiki_dir/raw/{source.id}_{filename}.
    4. Inside with lock: with conn: — upsert sources row (preserves ID on re-ingest).
    5. After lock exits, emit wiki_update AuditEvent (T-06-08 emit-after-lock).
    6. Return Source.
    """
    # Operator-initiated writes need the synthetic operator run to satisfy
    # audit_events.run_id FK on fresh databases.
    if run_id == OPERATOR_RUN_ID:
        _ensure_operator_run(conn, lock)

    # Step 1: path traversal guard (T-06-05)
    resolved = pathlib.Path(path).resolve()
    if not resolved.is_file():
        raise ValueError(f"ingest_source: path does not exist or is not a file: {path!r}")

    # Step 2: read bytes and construct Source model before any SQL (Pydantic-first)
    content = resolved.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    size_bytes = len(content)

    if size_bytes > 10 * 1024 * 1024:
        print(f"WARNING: ingest_source: file size {size_bytes} bytes exceeds 10MB — consider chunking")

    source = Source(
        path=str(resolved),
        sha256=sha256,
        size_bytes=size_bytes,
        untrusted=untrusted,
        ingested_by_run_id=run_id,
    )

    # Step 3: copy file to wiki_dir/raw/ BEFORE acquiring lock
    # (_get_wiki_dir only creates wiki_dir itself — raw/ may not exist yet)
    raw_dest = wiki_dir / "raw" / f"{source.id}_{resolved.name}"
    raw_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(resolved), str(raw_dest))

    # Step 4: upsert sources row inside lock (preserve ID on re-ingest)
    # Check: SELECT id FROM sources WHERE sha256=? AND path=?
    # If found, use existing id; if not found, INSERT new row.
    final_source_id = source.id
    with lock:
        with conn:
            existing = conn.execute(
                "SELECT id FROM sources WHERE sha256=? AND path=?",
                (sha256, str(resolved)),
            ).fetchone()
            if existing:
                # Re-ingest: preserve stable ID, do not create duplicate row
                final_source_id = existing[0]
            else:
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO sources(id, path, sha256, size_bytes, mime_type, ingested_at, title, untrusted, ingested_by_run_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        source.id,
                        str(resolved),
                        sha256,
                        size_bytes,
                        source.mime_type,
                        now,
                        source.title,
                        1 if untrusted else 0,
                        run_id,
                    ),
                )
    # Lock released — now safe to call emit() (T-06-08)
    emit(
        conn,
        lock,
        run_id=run_id,
        event_type="wiki_update",
        # T-06-07: data dict does not include file body content
        data={"slug": None, "source_id": final_source_id, "op": "ingest"},
    )

    # Return Source with stable ID
    if final_source_id != source.id:
        # Re-ingest path: rebuild Source with existing id for return value consistency
        source = Source(
            id=final_source_id,
            path=str(resolved),
            sha256=sha256,
            size_bytes=size_bytes,
            untrusted=untrusted,
            ingested_by_run_id=run_id,
        )

    return source


def update_wiki_page(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    slug: str,
    title: str,
    body: str,
    source_id: Optional[str] = None,
    run_id: str,
    wiki_dir: pathlib.Path,
) -> WikiPage:
    """Create or update a wiki page and return the constructed WikiPage.

    Steps:
    1. Normalize slug (lowercase, strip, replace spaces with hyphens).
    2. Construct WikiPage model before any SQL (Pydantic-first).
    3. Inside with lock: with conn: — upsert wiki_pages row (increment version on update).
    4. After lock exits, emit wiki_update AuditEvent (T-06-08 emit-after-lock).
    5. After emit, call provenance_service.write_provenance().
    6. Update wiki/index.md and append to wiki/log.md.
    7. Return WikiPage.
    """
    # Operator-initiated writes need the synthetic operator run to satisfy
    # audit_events.run_id FK on fresh databases.
    if run_id == OPERATOR_RUN_ID:
        _ensure_operator_run(conn, lock)

    # Step 1: slug normalization
    slug = slug.lower().strip().replace(" ", "-")

    # Step 2: construct WikiPage model before any SQL (Pydantic-first)
    page = WikiPage(
        slug=slug,
        title=title,
        body=body,
        source_id=source_id,
    )

    # Step 3: upsert wiki_pages inside lock
    final_page_id = page.id
    final_version = page.version
    with lock:
        with conn:
            existing = conn.execute(
                "SELECT id, version FROM wiki_pages WHERE slug=?",
                (slug,),
            ).fetchone()
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if existing:
                existing_id, existing_version = existing
                final_version = existing_version + 1
                final_page_id = existing_id
                conn.execute(
                    "UPDATE wiki_pages SET title=?, body=?, source_id=?, updated_at=?, version=? WHERE id=?",
                    (title, body, source_id, now, final_version, existing_id),
                )
            else:
                conn.execute(
                    "INSERT INTO wiki_pages(id, slug, title, body, source_id, created_at, updated_at, version) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (page.id, slug, title, body, source_id, now, now, 1),
                )
    # Lock released — now safe to call emit() (T-06-08)
    event = emit(
        conn,
        lock,
        run_id=run_id,
        event_type="wiki_update",
        # T-06-07: no body content in audit data
        data={"slug": slug, "source_id": source_id, "op": "update"},
    )

    # After emit, write provenance record
    provenance_service.write_provenance(
        conn,
        lock,
        layer="WIKI",
        item_id=slug,
        run_id=run_id,
        source_id=source_id,
        audit_event_id=event.id,
    )

    # Rebuild page with correct id and version for return
    return_page = WikiPage(
        id=final_page_id,
        slug=slug,
        title=title,
        body=body,
        source_id=source_id,
        version=final_version,
    )

    # Update index.md and append to log.md
    _update_index(wiki_dir, conn)
    _append_log(wiki_dir, return_page, event)

    # Best-effort semantic index (B-WP4): compute + store the page embedding so
    # semantic_search works. A missing optional dep is a silent no-op — the page
    # write has already succeeded and must not depend on embeddings.
    _index_embedding(conn, lock, page_id=final_page_id, body=body)

    return return_page


def search_wiki(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Full-text search the wiki using FTS5 and return matching page dicts.

    Uses the FTS5 rowid JOIN to wiki_pages — never SELECT from wiki_fts alone
    as it is a content table with no stored row data.

    T-06-06: query is always parameterized — never string-interpolated.
    """
    # Wrap query in double-quotes to treat it as a phrase/prefix search and avoid
    # FTS5 mis-parsing hyphens as the exclude operator (Rule 1 bug fix).
    # Escape any literal double-quotes in the query to avoid FTS5 syntax errors.
    safe_query = '"' + query.replace('"', '""') + '"'

    # FTS5 rowid JOIN pattern (required — content table has no stored data)
    cursor = conn.execute(
        "SELECT wp.slug, wp.title, wp.source_id, bm25(wiki_fts) AS rank "
        "FROM wiki_fts "
        "JOIN wiki_pages wp ON wiki_fts.rowid = wp.rowid "
        "WHERE wiki_fts MATCH ? "
        "ORDER BY rank "  # bm25() returns negative; ASC = most relevant first
        "LIMIT ?",
        (safe_query, limit),
    )
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor]


def semantic_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Semantic vector search the wiki — falls back to FTS5 when sqlite_vec absent.

    T-06-SC: sqlite_vec and fastembed imports are inside this function body
    inside try/except — never at module level.
    """
    # Load sqlite-vec + ensure the wiki_vec table (shared with the write path).
    if not _ensure_vec_table(conn):
        print(
            "sqlite-vec not loaded — semantic search unavailable; using FTS5 fallback"
        )
        return search_wiki(conn, query, limit)

    # Full semantic search path (sqlite_vec + fastembed available). Reuses the
    # cached embedder; vec0 KNN is `embedding MATCH ? ORDER BY distance LIMIT k`.
    try:
        embedding = _embed(query)
        # vec0 KNN requires an explicit `k = ?` constraint (not a plain LIMIT) when
        # the vec table is joined to metadata.
        cursor = conn.execute(
            "SELECT wp.id, wp.slug, wp.title, wp.source_id, wv.distance "
            "FROM wiki_vec wv "
            "JOIN wiki_pages wp ON wv.rowid = wp.rowid "
            "WHERE wv.embedding MATCH ? AND k = ? "
            "ORDER BY wv.distance",
            (embedding.tobytes(), limit),
        )
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor]
    except Exception:
        print("semantic search query failed — using FTS5 fallback")
        return search_wiki(conn, query, limit)


def lint(
    conn: sqlite3.Connection,
) -> list[dict]:
    """Lint wiki pages for structural issues and return a list of issue dicts.

    Each dict has: slug (str), rule (str), message (str).

    Rules:
    - empty_body: body is empty or len(body.strip()) < 20
    - untrusted_only: page's source is marked untrusted=1
    - stale_date: body contains dated "as of YYYY-MM-DD" > 90 days ago, or
                  body mentions current/latest/now/today and page is > 90 days old
    - cross_page_contradiction: two pages state "X is Y" with same X but different Y
    """
    findings: list[dict] = []
    ninety_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=90)

    # Fetch all pages with source trust info
    rows = conn.execute(
        "SELECT wp.slug, wp.body, wp.updated_at, s.untrusted "
        "FROM wiki_pages wp "
        "LEFT JOIN sources s ON wp.source_id = s.id "
        "ORDER BY wp.slug"
    ).fetchall()

    # Rule: empty_body
    for slug, body, updated_at, untrusted in rows:
        if not body or len(body.strip()) < 20:
            findings.append({
                "slug": slug,
                "rule": "empty_body",
                "message": f"Page body is empty or too short (len={len((body or '').strip())})",
            })

    # Rule: untrusted_only
    for slug, body, updated_at, untrusted in rows:
        if untrusted == 1:
            findings.append({
                "slug": slug,
                "rule": "untrusted_only",
                "message": "Page source is marked as untrusted",
            })

    # Rule: stale_date
    stale_date_pat = re.compile(r"as of (\d{4}-\d{2}-\d{2})", re.IGNORECASE)
    current_terms_pat = re.compile(r"\b(current|latest|now|today)\b", re.IGNORECASE)
    for slug, body, updated_at_str, untrusted in rows:
        if not body:
            continue
        # Check explicit "as of YYYY-MM-DD" dates
        for m in stale_date_pat.finditer(body):
            try:
                ref_date = datetime.datetime.fromisoformat(m.group(1)).replace(
                    tzinfo=datetime.timezone.utc
                )
                if ref_date < ninety_days_ago:
                    findings.append({
                        "slug": slug,
                        "rule": "stale_date",
                        "message": f"Page references date {m.group(1)} which is older than 90 days",
                    })
                    break
            except ValueError:
                pass
        # Check current/latest/now/today with old updated_at
        if current_terms_pat.search(body) and updated_at_str:
            try:
                updated_at = datetime.datetime.fromisoformat(updated_at_str)
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=datetime.timezone.utc)
                if updated_at < ninety_days_ago:
                    findings.append({
                        "slug": slug,
                        "rule": "stale_date",
                        "message": "Page uses current/latest/now/today language but was last updated > 90 days ago",
                    })
            except ValueError:
                pass

    # Rule: cross_page_contradiction
    # Extract "X is Y" / "X version is Y" patterns across all pages
    # Pattern: "version is <value>" — detect same subject with different values
    version_pat = re.compile(r"version\s+is\s+(\S+)", re.IGNORECASE)
    version_values: dict[str, tuple[str, str]] = {}  # value -> (first_slug, first_body)
    for slug, body, updated_at_str, untrusted in rows:
        if not body:
            continue
        for m in version_pat.finditer(body):
            val = m.group(1).rstrip(".,;")
            # Check for contradictions: same subject "version" with different values
            for existing_val, (existing_slug, _) in list(version_values.items()):
                if existing_val != val and existing_slug != slug:
                    findings.append({
                        "slug": slug,
                        "rule": "cross_page_contradiction",
                        "message": (
                            f"Contradiction: '{slug}' states 'version is {val}' "
                            f"but '{existing_slug}' states 'version is {existing_val}'"
                        ),
                    })
            if val not in version_values:
                version_values[val] = (slug, body)

    return findings
