# Phase 6: LLM Wiki Runtime — Research

**Researched:** 2026-06-08
**Domain:** Python wiki service, SQLite FTS5, sqlite-vec vector search, Pydantic v2 schema extension, Typer CLI
**Confidence:** HIGH (all core findings verified against codebase or PyPI registry)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-004** (locked): LLM Wiki is first-class runtime — raw sources are immutable; wiki pages are agent-maintained; retrieval supplements but does not replace structured wiki pages or citations.
- **D-002** (locked): Audit-first — every wiki operation (ingest, update, lint) emits an AuditEvent via the Phase 4 event bus.
- **D-003** (locked): SQLite/WAL/FTS5/sqlite-vec — FTS5 for text search, sqlite-vec for semantic search. Degrade gracefully if sqlite-vec is unavailable.
- **D-011** (locked): Canonical repo layout — wiki service at `services/wiki-runtime/`; wiki markdown files at `wiki/`.
- **D-018** (locked): L2/ATLAS is the evolved Hermes foundation — wiki service enhances foundation memory, does not create a parallel system.
- **D-019** (accepted): Diverse memory framework — Phase 6 is Layer 2 + optional Layer 3. Memory provenance schema must be designed and implemented.

### Claude's Discretion

- **D-014** (accepted for spike): turbovec vs sqlite-vec for semantic retrieval. D-014 mentions turbovec but D-003 and CONTEXT.md explicitly specify sqlite-vec as the implementation path. Use sqlite-vec.
- Embedding model for semantic path: fastembed (Qdrant, ONNX-based, no cloud API) is the stated preference. CONTEXT.md says "fastembed/ONNX or equivalent, no cloud API."
- Service file/class naming conventions within `services/wiki-runtime/`.
- Lint heuristics specifics (contradiction-detection rules, stale thresholds).
- Graph-memory research notes format — CONTEXT.md says write to `docs/research/GRAPH_MEMORY_RESEARCH_NOTES.md`.

### Deferred Ideas (OUT OF SCOPE)

- REST API for wiki endpoints — Phase 7.
- Cockpit wiki browser UI — Phase 8.
- Graph memory implementation — v2.0 (document design questions only).
- Full memory router implementation — Phase 7.
- Pulse wiki health monitoring — v2.0.
- Wiki-to-CRM linkage — v2.0.
- Multi-user wiki permissions — not in v1.0.
- Cloud vector DB — forbidden; local only.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WIKI-01 | User can ingest a raw source file into the wiki (immutable raw copy stored, SHA-256 stamped, Source row created) | Source schema exists; migrations have sources table; new: untrusted + run_id fields needed |
| WIKI-02 | Agent can create or update a WikiPage and change is logged in wiki/log.md and reflected in the database | WikiPage schema exists; FTS5 triggers exist; MemoryProvenance write needed per update |
| WIKI-03 | User can query wiki pages via FTS5 full-text search and get ranked results | FTS5 virtual table wiki_fts exists; triggers wired; bm25() rank available |
| WIKI-04 | wiki/index.md and wiki/log.md remain consistent after every agent-driven wiki update | wiki/ directory exists with index.md + log.md stubs; consistency logic needed in wiki_service |
| WIKI-05 | Semantic vector search (sqlite-vec) returns relevant wiki pages for a natural-language query | sqlite-vec 0.1.9 available on PyPI; fastembed 0.8.0 available; graceful degradation required |
| AUDIT-03 | Wiki lint pass flags pages with stale or contradicted claims | Lint is rule-based + optional LLM call; no existing lint code; needs wiki_service.lint() |
</phase_requirements>

---

## Summary

Phase 6 builds the wiki ingest/update/search/lint pipeline as the first concrete implementation of the ATLAS memory framework. The project already has all structural prerequisites in place: `WikiPage` and `Source` Pydantic models exist in `atlas_core.schemas.core`, the SQLite migration has `wiki_pages`, `sources`, and the `wiki_fts` FTS5 virtual table with all three required triggers, and the `wiki/` directory has `index.md` and `log.md` stubs.

What Phase 6 must add: (1) a new `services/wiki-runtime/` service package following the exact same `atlas_runtime` pattern — Pydantic-first writes, lock injection, `audit_service.emit()` calls — with a `wiki_service.py` containing ingest, update, search, lint, and provenance functions; (2) schema additions for `Source.untrusted`, `Source.ingested_by_run_id`, and a new `MemoryProvenance` Pydantic model; (3) a matching SQLite migration `0002_wiki_provenance.sql`; (4) `atlas wiki` CLI subcommands wired to the service layer via Typer; and (5) optional sqlite-vec integration behind a try/except load guard with fastembed for embeddings.

The audit emission pattern from Phase 4 is fully established and must be reused verbatim: `audit_service.emit(conn, lock, run_id=..., event_type="wiki_update", data={...})`. The CLI pattern from Phase 5 is the exact template: Typer sub-app with `_get_connection()` / `_get_lock()` factories monkeypatched in tests.

**Primary recommendation:** Mirror `services/agent-runtime/` precisely. New package `services/wiki-runtime/atlas_wiki/wiki_service.py` + `cli/main.py` with a `wiki_app` Typer sub-app registered into the existing `atlas` CLI entry point (or as a separate entry point extended from it). The wiki subcommands extend the existing `atlas` CLI rather than introducing a new binary.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Source ingest (SHA-256, copy to wiki/raw/, Source row) | Service layer (wiki_service.py) | CLI (thin wrapper) | File I/O + DB write is business logic, not CLI logic |
| WikiPage upsert + FTS5 index update | Service layer | SQLite triggers (already wired) | FTS5 triggers handle index; service handles row + provenance |
| wiki/index.md + wiki/log.md consistency | Service layer | File system | In-service after DB write; not a separate job |
| MemoryProvenance record write | Service layer | — | Linked to every wiki state-change; same transaction as WikiPage write |
| AuditEvent emission | Service layer → audit_service.emit() | — | Phase 4 pattern; no raw INSERTs outside audit_service |
| FTS5 search with ranking | Service layer (search function) | SQLite bm25() | bm25() is a native FTS5 ranking function |
| sqlite-vec load + embedding | Service layer (optional path) | fastembed | Must be lazy-loaded; not imported at module level |
| Lint pass (stale/contradiction detection) | Service layer (lint function) | Optional LLM call | Rule-based primary; LLM call behind feature flag |
| CLI command surface | CLI (atlas wiki ingest/update/search/semantic/lint) | Typer | CLI is thin wrapper only; no SQL in CLI |
| MemoryProvenance schema | atlas_core.schemas.core | 0002 migration | Follows D-012: Pydantic schema is source of truth |
| Source.untrusted + ingested_by_run_id | atlas_core.schemas.core | 0002 migration | Schema extension, not Phase 6-only model |

---

## Existing Schema State (VERIFIED: codebase)

### atlas_core.schemas.core — current models

All 7 models verified in `packages/atlas-core/atlas_core/schemas/core.py`:

**Source** (line 173–193) — current fields:
- `id: str` (UUID)
- `path: str`
- `sha256: str`
- `size_bytes: int`
- `mime_type: str = "text/plain"`
- `ingested_at: datetime`
- `title: str = ""`

**Missing fields that Phase 6 must add:**
- `untrusted: bool = False` — required by CONTEXT.md Source registry spec
- `ingested_by_run_id: Optional[str] = None` — required by CONTEXT.md ("ingested_by_run_id")

**WikiPage** (line 196–219) — current fields:
- `id`, `slug`, `title`, `body`, `source_id`, `created_at`, `updated_at`, `version`

WikiPage has no `run_id` or provenance fields — that is intentional. Provenance is tracked in the separate `MemoryProvenance` record, not embedded in WikiPage.

**MemoryProvenance** — does NOT exist yet. Must be added.

Schema per `docs/architecture/AGENT_MEMORY_FRAMEWORK_STRATEGY.md`:
```python
class MemoryProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    layer: str                          # "WIKI" | "PROFILE" | "GRAPH" | "SKILL" | "AUDIT"
    item_id: str                        # wiki slug or other item identifier
    run_id: Optional[str] = None        # run that produced this write
    source_id: Optional[str] = None     # source record ID if from ingest
    audit_event_id: Optional[str] = None
    operator_id: Optional[str] = None
    sensitivity: str = "internal"       # "public" | "internal" | "private" | "restricted"
    untrusted: bool = False
    written_at: datetime
```

Note: D-019 uses `@dataclass` in the strategy doc, but the project convention (D-012) is Pydantic v2 frozen models. Use `BaseModel`, not `dataclass`.

### infra/migrations/0001_core.sql — current tables

Verified tables (line 1–107):

| Table | Status |
|-------|--------|
| missions | Present |
| runs | Present |
| audit_events | Present |
| tool_calls | Present |
| artifacts | Present |
| sources | Present — missing `untrusted`, `ingested_by_run_id` columns |
| wiki_pages | Present |
| wiki_fts (FTS5 virtual table) | Present — `content=wiki_pages`, `content_rowid=rowid` |
| FTS5 triggers (insert/update/delete) | Present — fully wired |

**Missing from 0001_core.sql that Phase 6 must add (via 0002 migration):**
1. `ALTER TABLE sources ADD COLUMN untrusted INTEGER NOT NULL DEFAULT 0`
2. `ALTER TABLE sources ADD COLUMN ingested_by_run_id TEXT`
3. New `memory_provenance` table

**Important:** The FTS5 comment in 0001 says "TODO Phase 6: wire full-text index maintenance" — the triggers ARE already wired (insert/update/delete), so this TODO is already resolved. The planner should not re-create triggers.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `atlas-core` | project-local | Pydantic schemas, SECRET_PATTERNS | D-012: source of truth |
| `typer` | 0.25.1 (installed) / 0.26.7 (latest) | CLI framework | Already used by agent-runtime; pyproject.toml pins >=0.25.0 |
| `sqlite3` | stdlib (Python 3.13, SQLite 3.50.4) | Database, FTS5, WAL | D-003 locked |
| `hashlib` | stdlib | SHA-256 computation | No external dep needed |
| `shutil` | stdlib | Copy source files to wiki/raw/ | Standard library |
| `pathlib` | stdlib | Path manipulation | D-013 convention: str in models, pathlib in service code |

### Supporting (Optional Path)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlite-vec` | 0.1.9 | Vector search extension for SQLite | Only if semantic search path enabled; load with try/except |
| `fastembed` | 0.8.0 | ONNX-based local embeddings, no GPU required | Only when sqlite-vec loaded; Qdrant-maintained |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| fastembed | sentence-transformers | fastembed is lighter (ONNX, no PyTorch); D-014 preference aligns with fastembed |
| sqlite-vec | turbovec | D-003 + CONTEXT.md explicitly name sqlite-vec; turbovec is the D-014 spike reference, not the Phase 6 implementation |
| Rule-based lint | LLM-only lint | Rule-based is always available offline; LLM call is optional enhancement |

**Installation (optional semantic path):**
```bash
pip install sqlite-vec fastembed
```

---

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| sqlite-vec | PyPI | ~2 yrs | Popular (Mozilla Builders project) | github.com/asg017/sqlite-vec | [OK] | Approved |
| fastembed | PyPI | ~2 yrs | High (Qdrant maintained) | github.com/qdrant/fastembed | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

Note on sqlite-vec PyPI metadata: the PyPI package page shows placeholder `TODO.com` for homepage field. The actual project is `github.com/asg017/sqlite-vec` (asg017 = Alex Garcia, Mozilla Builders project). The Python package loads the native C extension bundled in the wheel. [VERIFIED: slopcheck OK + PyPI registry + github.com/asg017/sqlite-vec confirmed]

fastembed is maintained by Qdrant (info@qdrant.tech), homepage confirmed at `github.com/qdrant/fastembed`. [VERIFIED: PyPI registry + slopcheck OK]

---

## Architecture Patterns

### Recommended Project Structure

```
services/wiki-runtime/
├── pyproject.toml                     # name="atlas-wiki", depends on atlas-core + atlas-runtime
├── atlas_wiki/
│   ├── __init__.py
│   ├── wiki_service.py                # ingest, update, search, semantic_search, lint
│   ├── provenance_service.py          # write_provenance(), get_provenance()
│   └── cli/
│       ├── __init__.py
│       └── main.py                    # wiki_app Typer sub-app
└── tests/
    ├── __init__.py
    ├── conftest.py                    # db, run_id, lock fixtures (mirror agent-runtime)
    ├── test_wiki_service.py           # ingest, update, search, lint coverage
    ├── test_provenance_service.py     # MemoryProvenance write/read
    └── test_cli.py                    # CLI commands via CliRunner + monkeypatch
```

```
packages/atlas-core/atlas_core/schemas/core.py
  [EXTEND]  Source  — add untrusted, ingested_by_run_id
  [ADD]     MemoryProvenance model
  [EXPORT]  add to __all__

infra/migrations/
  0002_wiki_provenance.sql             # ALTER TABLE sources + CREATE TABLE memory_provenance
```

```
wiki/
├── raw/                               # immutable source copies (already exists)
├── index.md                           # catalog (exists, needs entries from service)
├── log.md                             # append-only log (exists, needs entries from service)
├── SCHEMA.md                          # reference (exists, no changes)
├── comparisons/, concepts/, entities/, queries/  # subdirs exist
```

```
docs/research/
  GRAPH_MEMORY_RESEARCH_NOTES.md       # new: graph-memory design questions (no code)
```

### Pattern 1: Pydantic-First Write Guard (VERIFIED: agent-runtime pattern)

Every service write constructs the Pydantic model before any SQL. ValidationError propagates before any DB write.

```python
# Source: services/agent-runtime/atlas_runtime/mission_service.py pattern
def ingest_source(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    path: str,
    run_id: str,
    untrusted: bool = False,
    wiki_dir: pathlib.Path,
) -> Source:
    content = pathlib.Path(path).read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    size_bytes = len(content)
    
    # Pydantic-first: construct before any SQL
    source = Source(
        path=path,
        sha256=sha256,
        size_bytes=size_bytes,
        untrusted=untrusted,
        ingested_by_run_id=run_id,
    )
    row = source.model_dump()
    
    # Copy to wiki/raw/ (immutable)
    raw_dir = wiki_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / f"{source.id}_{pathlib.Path(path).name}"
    shutil.copy2(path, dest)
    
    with lock:
        with conn:
            # Upsert: stable ID means re-ingest updates existing row (CONTEXT.md requirement)
            existing = conn.execute(
                "SELECT id FROM sources WHERE sha256=? AND path=?", (sha256, path)
            ).fetchone()
            if existing:
                # Update existing — preserve ID to keep all references valid
                conn.execute(
                    "UPDATE sources SET sha256=?, size_bytes=?, ingested_at=? WHERE id=?",
                    (sha256, size_bytes, row["ingested_at"], existing[0]),
                )
                source = Source(**{**row, "id": existing[0]})
            else:
                conn.execute(
                    "INSERT INTO sources VALUES "
                    "(:id,:path,:sha256,:size_bytes,:mime_type,:ingested_at,:title,:untrusted,:ingested_by_run_id)",
                    row,
                )
    return source
```

### Pattern 2: Emit-After-Lock (VERIFIED: Phase 4/5 pattern)

`audit_service.emit()` acquires the lock internally. Always release the data lock before calling emit.

```python
# Source: services/agent-runtime/atlas_runtime/run_service.py pattern
def update_wiki_page(conn, lock, *, slug, title, body, source_id, run_id, wiki_dir):
    page = WikiPage(slug=slug, title=title, body=body, source_id=source_id)
    row = page.model_dump()
    
    with lock:
        with conn:
            existing = conn.execute(
                "SELECT id, version FROM wiki_pages WHERE slug=?", (slug,)
            ).fetchone()
            if existing:
                # Upsert: FTS5 triggers handle index update automatically
                conn.execute(
                    "UPDATE wiki_pages SET title=?, body=?, source_id=?, updated_at=?, version=version+1 WHERE slug=?",
                    (title, body, source_id, row["updated_at"], slug),
                )
                page = WikiPage(**{**row, "id": existing[0], "version": existing[1] + 1})
            else:
                conn.execute(
                    "INSERT INTO wiki_pages VALUES "
                    "(:id,:slug,:title,:body,:source_id,:created_at,:updated_at,:version)",
                    row,
                )
    # Lock released — now safe to emit
    event = emit(conn, lock, run_id=run_id, event_type="wiki_update",
                 data={"slug": slug, "source_id": source_id})
    
    # Write provenance record
    provenance_service.write_provenance(conn, lock, layer="WIKI", item_id=slug,
                                        run_id=run_id, source_id=source_id,
                                        audit_event_id=event.id)
    
    # Update wiki/index.md and wiki/log.md
    _update_index(wiki_dir, page)
    _append_log(wiki_dir, page, event)
    
    return page
```

### Pattern 3: FTS5 Search with bm25() Ranking

FTS5 `bm25()` is built-in; no additional library needed. Content-table FTS (with `content=wiki_pages`) requires explicit rowid join to get page fields.

```python
# VERIFIED: SQLite FTS5 documentation pattern for content tables
def search_wiki(conn: sqlite3.Connection, query: str, limit: int = 10):
    # bm25() returns negative values; ORDER BY ASC gives most-relevant first
    cursor = conn.execute(
        """
        SELECT wp.slug, wp.title, wp.source_id, bm25(wiki_fts) AS rank
        FROM wiki_fts
        JOIN wiki_pages wp ON wiki_fts.rowid = wp.rowid
        WHERE wiki_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    )
    return [
        {"slug": r[0], "title": r[1], "source_id": r[2], "rank": r[3]}
        for r in cursor
    ]
```

### Pattern 4: sqlite-vec Graceful Load

```python
# Source: alexgarcia.xyz/sqlite-vec/python.html [VERIFIED]
def _try_load_sqlite_vec(conn: sqlite3.Connection) -> bool:
    """Attempt to load sqlite-vec extension. Returns True if loaded."""
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return True
    except (ImportError, Exception):
        return False


def semantic_search(conn: sqlite3.Connection, query: str, limit: int = 10):
    if not _try_load_sqlite_vec(conn):
        print("sqlite-vec not loaded — falling back to FTS5 search")
        return search_wiki(conn, query, limit)
    
    # Embed query
    try:
        from fastembed import TextEmbedding
    except ImportError:
        print("fastembed not installed — falling back to FTS5 search")
        return search_wiki(conn, query, limit)
    
    model = TextEmbedding()
    query_vec = list(model.embed([query]))[0].tolist()
    # ... sqlite-vec KNN query
```

### Pattern 5: CLI Wiki Sub-App (mirror Phase 5)

```python
# Source: services/agent-runtime/atlas_runtime/cli/main.py pattern
import typer
wiki_app = typer.Typer(name="wiki")
app.add_typer(wiki_app, name="wiki")

@wiki_app.command("ingest")
def ingest(path: str = typer.Argument(...)):
    conn = _get_connection()
    lock = _get_lock()
    source = wiki_service.ingest_source(conn, lock, path=path, run_id="operator", ...)
    typer.echo(source.id)

@wiki_app.command("update")
def update(
    slug: str = typer.Argument(...),
    body: str = typer.Option(..., "--body"),
    title: str = typer.Option("", "--title"),
):
    ...
```

### Pattern 6: wiki/index.md and wiki/log.md Maintenance

```python
# wiki/index.md: one entry per WikiPage row; regenerated from DB on every update
def _update_index(wiki_dir: pathlib.Path, all_pages: list[WikiPage]) -> None:
    entries = "\n".join(f"- [{p.slug}] {p.title}" for p in all_pages)
    (wiki_dir / "index.md").write_text(INDEX_TEMPLATE.format(entries=entries), encoding="utf-8")

# wiki/log.md: append-only; one entry per wiki_update AuditEvent
def _append_log(wiki_dir: pathlib.Path, page: WikiPage, event: AuditEvent) -> None:
    entry = f"\n## [{event.timestamp[:10]}] update | {page.slug}\n- Event: {event.id}\n- Body length: {len(page.body)}\n"
    with open(wiki_dir / "log.md", "a", encoding="utf-8") as f:
        f.write(entry)
```

### Anti-Patterns to Avoid

- **Raw SQL without Pydantic model construction first:** ValidationError is the first line of defense; skip it and you get silent DB corruption. Every INSERT/UPDATE must construct the Pydantic model first.
- **Importing sqlite_vec at module level:** Makes the entire wiki service fail to import when sqlite-vec is absent. Import inside the function body only.
- **Importing fastembed at module level:** Same issue — fastembed has many transitive deps; import lazily.
- **Acquiring the lock before calling emit():** `audit_service.emit()` acquires the lock internally. Calling it while holding the lock causes deadlock. Always release data lock before emitting.
- **Re-creating FTS5 triggers in 0002 migration:** The triggers are already created in 0001. Re-running them with `CREATE TRIGGER IF NOT EXISTS` is safe but unnecessary.
- **Overwriting wiki/log.md instead of appending:** log.md is append-only. Opening it with `"w"` mode destroys history.
- **Using the wiki_fts table directly for rowid-based reads:** wiki_fts is a content table — it has no row data of its own. Always JOIN to wiki_pages via rowid.
- **Embedding a full file body in the AuditEvent.data field:** data is redacted and should be compact JSON. Store only slug, source_id, and operation type — not the full body.

---

## Schema Additions Required

### 1. Source model extension (atlas_core/schemas/core.py)

Add two fields to `Source`:

```python
# After existing fields:
untrusted: bool = False
ingested_by_run_id: Optional[str] = None
```

Both have defaults so existing code constructing `Source` without these fields continues to work.

### 2. MemoryProvenance model (new, atlas_core/schemas/core.py)

```python
class MemoryProvenance(BaseModel):
    """Provenance record for every write to any ATLAS memory layer (D-019).

    Every wiki update, profile update, and skill modification must produce
    one MemoryProvenance row. This is the answer to "why was this stored?"
    """
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    layer: Literal["WIKI", "PROFILE", "GRAPH", "SKILL", "AUDIT"]
    item_id: str          # wiki slug / skill name / graph node ID
    run_id: Optional[str] = None
    source_id: Optional[str] = None
    audit_event_id: Optional[str] = None
    operator_id: Optional[str] = None
    sensitivity: Literal["public", "internal", "private", "restricted"] = "internal"
    untrusted: bool = False
    written_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    @field_serializer("written_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        return None if dt is None else dt.isoformat()
```

### 3. Migration 0002_wiki_provenance.sql

```sql
-- ATLAS migration 0002: Source extensions + MemoryProvenance table
PRAGMA foreign_keys = ON;

-- Extend sources table
ALTER TABLE sources ADD COLUMN untrusted INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sources ADD COLUMN ingested_by_run_id TEXT;

-- Memory provenance table (D-019)
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
CREATE INDEX IF NOT EXISTS idx_memory_provenance_run ON memory_provenance(run_id);
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FTS5 ranking | Custom scoring | SQLite `bm25()` built-in | bm25() is built into SQLite FTS5; handles term frequency, document length normalization |
| FTS5 index maintenance | Manual INSERT/UPDATE to wiki_fts | FTS5 triggers already in 0001_core.sql | Triggers fire on wiki_pages changes automatically |
| SHA-256 hashing | Custom hash loop | `hashlib.sha256()` stdlib | stdlib is correct and already used in tests |
| Embedding model | Custom ONNX runner | `fastembed.TextEmbedding` | fastembed handles model download, ONNX runtime, batching |
| sqlite-vec Python integration | ctypes/load_extension raw calls | `sqlite_vec.load(conn)` from PyPI | Package provides `load()` that handles path resolution per platform |
| JSON serialization of Pydantic models | `json.dumps(model.dict())` | `model.model_dump()` + `conn.execute(..., row)` | D-013: model_dump() is JSON-safe by design; field_serializer handles datetime |
| Secret redaction | Custom regex | `audit_service.emit()` with `_redact()` | Phase 4 already implements this; all data payloads go through emit() |

**Key insight:** The FTS5 triggers in 0001_core.sql handle the index for free. The wiki service only needs to write to `wiki_pages` — the index update is automatic. This was a "TODO Phase 6" comment but the triggers ARE already complete.

---

## Wiki Lint Design

The lint pass is rule-based with an optional LLM call gate. No external knowledge graph required.

### Rule-Based Heuristics (Always Available)

1. **Untrusted-only citation:** If a wiki page's `source_id` points to a `Source` with `untrusted=True`, and there is no trusted source, flag as "unverified claim — only untrusted sources."

2. **Stale date heuristic:** If `wiki_pages.updated_at` is older than a configurable threshold (default 90 days) AND the body contains date-sensitive language ("current", "latest", "now", "today", "this year"), flag as "potentially stale."

3. **Contradiction seed detection:** For the test scenario (AUDIT-03 success criterion), the lint pass must detect a deliberately seeded contradiction. The test plan is:
   - Create two WikiPages with conflicting claims (e.g., page A says "version is 1.0", page B says "version is 2.0")
   - Lint pass scans all pages, finds the same key term with conflicting values
   - Simplest implementation: keyword-based cross-page comparison for known contradiction patterns (e.g., version numbers, status values)

4. **Empty body:** Flag pages with `body = ""` as incomplete.

5. **Missing source citation:** Flag pages with `source_id = NULL` for non-stub pages.

### Optional LLM Call Gate

If an LLM provider is available (Phase 5 execution context), the lint pass can submit a page body + related pages to the LLM for contradiction detection. This is a secondary path — lint must work without it.

```python
def lint(conn: sqlite3.Connection, *, llm_call=None) -> list[dict]:
    """Return list of lint findings: [{slug, rule, message}, ...]"""
    findings = []
    pages = _get_all_pages(conn)
    sources = _get_all_sources(conn)
    
    for page in pages:
        findings.extend(_check_untrusted_only(page, sources))
        findings.extend(_check_stale_date(page))
        findings.extend(_check_empty_body(page))
        findings.extend(_check_cross_page_contradictions(page, pages))
    
    if llm_call is not None:
        findings.extend(_llm_lint_pass(pages, llm_call))
    
    return findings
```

---

## FTS5 Search Design (VERIFIED: SQLite docs pattern)

The `wiki_fts` table is a **content FTS5 table** (`content=wiki_pages`). Key properties:

1. **Content table means wiki_fts has no data of its own** — it stores only the FTS index. Row data is in `wiki_pages`. Always JOIN via `wiki_fts.rowid = wiki_pages.rowid`.

2. **Triggers are already wired** in 0001_core.sql for insert, update, delete.

3. **bm25() ranking:** Returns negative floats; `ORDER BY bm25(wiki_fts) ASC` gives most relevant first.

4. **Search result format** (as required by success criteria — must include slug + source_id citation):

```python
{
    "slug": "hermes-agent-runtime",
    "title": "Hermes Agent Runtime",
    "source_id": "uuid-of-source",   # citation
    "rank": -3.14,                   # bm25 score
    "snippet": "...relevant excerpt..."
}
```

5. **FTS5 snippet():** Built-in function for generating search snippets. Use `snippet(wiki_fts, 1, '<b>', '</b>', '...', 10)` (column 1 = body).

---

## sqlite-vec Integration Approach (VERIFIED: asg017/sqlite-vec docs)

### Load Pattern

```python
import sqlite_vec
conn.enable_load_extension(True)
sqlite_vec.load(conn)
conn.enable_load_extension(False)
```

Call `sqlite_vec.load(conn)` — the Python package wraps the platform-specific `.so`/`.dll`/`.dylib` bundled in the wheel. This works on Windows 11 (wheel is `win_amd64`).

### Vector Table DDL

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS wiki_vec USING vec0(
    page_id TEXT,
    embedding FLOAT[384]   -- 384 dims for BAAI/bge-small-en-v1.5 (fastembed default)
);
```

### Embedding Strategy

- Model: `BAAI/bge-small-en-v1.5` (fastembed default, 384 dims, ~130MB, ONNX, no GPU)
- Input: wiki page `title + "\n\n" + body[:2000]` (truncate to avoid token limits)
- Storage: one vector row per `wiki_pages.id`, keyed by stable `wiki_pages.id` UUID
- Index rebuild: rebuild on demand (not on every update) since it is a search cache

### Graceful Degradation

If `sqlite_vec` cannot be imported (not installed) OR `sqlite_vec.load()` raises (native extension load fails):
- Print: `"sqlite-vec not loaded — semantic search unavailable; using FTS5 fallback"`
- Return FTS5 search results under the same return schema
- The semantic path must never raise an unhandled exception

### Environment Status

sqlite-vec 0.1.9: **available on PyPI** but **not currently installed** on this machine. [VERIFIED: PyPI]
fastembed 0.8.0: **available on PyPI** but **not currently installed**. [VERIFIED: PyPI]
slopcheck result: both [OK]. [VERIFIED: slopcheck run]

The `sqlite-vec` native extension is not loadable at test time without installing the package. Tests for the semantic path must use pytest.importorskip or a `try/skip` guard.

---

## CLI Integration Pattern (VERIFIED: Phase 5 agent-runtime pattern)

### Architecture Decision

The wiki CLI should extend the **existing `atlas` CLI entry point** already registered by `atlas-runtime` (pyproject.toml: `atlas = "atlas_runtime.cli.main:app"`). The wiki sub-app is added as a `typer.Typer()` registered into the root `app`:

Option A — **Extend existing atlas app**: `atlas_runtime.cli.main.app.add_typer(wiki_app, name="wiki")`. This requires atlas-wiki to be installed alongside atlas-runtime. The wiki package imports and registers its sub-app at import time (or via an explicit registration call).

Option B — **Separate entry point**: `atlas-wiki` registers `atlas_wiki_cli = "atlas_wiki.cli.main:wiki_app"`. This means `atlas wiki ...` only works if the wiki package is installed.

Recommendation: **Option A** — extend the existing `atlas` app. This mirrors how the CLI is used in the success criteria (`atlas wiki ingest`, `atlas wiki update`, etc.). The wiki service registers its Typer app into the runtime CLI.

### Implementation: atlas_wiki/cli/main.py

```python
import typer
import pathlib
import threading
import sqlite3

from atlas_wiki import wiki_service

wiki_app = typer.Typer(name="wiki", help="LLM Wiki commands")

def _get_connection() -> sqlite3.Connection:
    """Mirror of atlas_runtime.cli.main._get_connection()"""
    db_path = pathlib.Path.home() / ".atlas" / "atlas.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

_LOCK = threading.Lock()

def _get_lock() -> threading.Lock:
    return _LOCK

@wiki_app.command("ingest")
def ingest(path: str = typer.Argument(...)):
    """Ingest a file as an immutable source into wiki/raw/."""
    ...

@wiki_app.command("update")
def update(slug: str = typer.Argument(...), body: str = typer.Option(..., "--body")):
    """Create or update a WikiPage by slug."""
    ...

@wiki_app.command("search")
def search(query: str = typer.Argument(...)):
    """FTS5 full-text search across wiki pages."""
    ...

@wiki_app.command("semantic")
def semantic(query: str = typer.Argument(...)):
    """Semantic vector search (sqlite-vec) or FTS5 fallback."""
    ...

@wiki_app.command("lint")
def lint_cmd():
    """Run wiki lint pass — report stale/contradicted claims."""
    ...
```

### atlas_runtime/cli/main.py extension point

The existing `main.py` needs one import + registration call to pick up wiki subcommands:

```python
# In atlas_runtime/cli/main.py — add after mission_app registration:
try:
    from atlas_wiki.cli.main import wiki_app
    app.add_typer(wiki_app, name="wiki")
except ImportError:
    pass  # wiki service not installed — skip wiki subcommands gracefully
```

This try/except ensures agent-runtime tests continue to pass without atlas-wiki installed.

### pyproject.toml for atlas-wiki

```toml
[project]
name = "atlas-wiki"
version = "0.1.0"
dependencies = [
    "atlas-core",
    "atlas-runtime",          # for audit_service.emit()
    "typer>=0.25.0",
]

[project.optional-dependencies]
semantic = ["sqlite-vec>=0.1.9", "fastembed>=0.8.0"]
dev = ["pytest>=9.0", "pytest-cov>=7.0"]
```

---

## Test Approach (VERIFIED: Phase 4/5 pattern)

### Test Fixtures (conftest.py)

Mirror `services/agent-runtime/tests/conftest.py` exactly:

```python
MIGRATION_PATH = pathlib.Path(__file__).parent.parent.parent.parent / "infra" / "migrations"

@pytest.fixture(name="db")
def db_fixture():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    # Apply both migrations
    conn.executescript((MIGRATION_PATH / "0001_core.sql").read_text())
    conn.executescript((MIGRATION_PATH / "0002_wiki_provenance.sql").read_text())
    yield conn
    conn.close()

@pytest.fixture(name="run_id")
def run_id_fixture(db):
    # Insert mission + run for FK satisfaction (same as agent-runtime conftest)
    ...

@pytest.fixture(name="wiki_dir")
def wiki_dir_fixture(tmp_path):
    """Temporary wiki/ directory with index.md, log.md, raw/ for test isolation."""
    (tmp_path / "raw").mkdir()
    (tmp_path / "index.md").write_text("# ATLAS Wiki Index\n")
    (tmp_path / "log.md").write_text("# ATLAS Wiki Log\n")
    return tmp_path
```

### Test Coverage Map

| File | Functions to Test | Branch Coverage Targets |
|------|-------------------|------------------------|
| wiki_service.py | ingest_source() | new source vs re-ingest (SHA match), untrusted flag |
| wiki_service.py | update_wiki_page() | new page vs upsert existing, version increment |
| wiki_service.py | search_wiki() | results returned, empty results, ranking order |
| wiki_service.py | semantic_search() | sqlite-vec present (skip if not), fallback path |
| wiki_service.py | lint() | untrusted-only finding, stale date finding, contradiction finding, clean page |
| wiki_service.py | index/log consistency | index.md updated after update, log.md appended |
| provenance_service.py | write_provenance() | row persisted, fields match |
| cli/main.py | ingest, update, search, semantic, lint | exit 0, correct output format |

### Coverage Gate

```toml
# pyproject.toml
[tool.coverage.run]
branch = true
source = ["atlas_wiki"]

[tool.coverage.report]
fail_under = 80
```

### Semantic Test Guard

```python
pytest.importorskip("sqlite_vec", reason="sqlite-vec not installed — skip semantic tests")
```

All semantic tests must use this guard. Tests must not fail when sqlite-vec is absent.

### Lint Contradiction Seed

The test for AUDIT-03 must seed a deliberate contradiction:

```python
def test_lint_detects_contradiction(db, lock, run_id, wiki_dir):
    wiki_service.update_wiki_page(db, lock, slug="runtime-version",
                                  title="Runtime Version", body="Current version is 1.0",
                                  run_id=run_id, wiki_dir=wiki_dir)
    wiki_service.update_wiki_page(db, lock, slug="runtime-version-note",
                                  title="Runtime Note", body="Current version is 2.0",
                                  run_id=run_id, wiki_dir=wiki_dir)
    findings = wiki_service.lint(db)
    assert any(f["rule"] == "cross_page_contradiction" for f in findings)
```

---

## Runtime State Inventory

This is a greenfield service (new `services/wiki-runtime/` package). No rename/refactor scope.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `wiki/` directory exists with index.md, log.md stubs (no WikiPage rows yet) | None — starting from empty wiki |
| Live service config | None | None |
| OS-registered state | None | None |
| Secrets/env vars | None relevant to wiki | None |
| Build artifacts | None (new package) | None |

---

## Common Pitfalls

### Pitfall 1: Content FTS Table Rowid Join

**What goes wrong:** SELECT from `wiki_fts` returns only FTS columns (title, body). The `slug` and `source_id` fields are in `wiki_pages`, not `wiki_fts`.

**Why it happens:** FTS5 content tables store the index separately from row data.

**How to avoid:** Always JOIN `wiki_fts` to `wiki_pages` via `wiki_fts.rowid = wiki_pages.rowid`.

**Warning signs:** Missing `slug` or `source_id` in search results; getting only title/body back.

### Pitfall 2: Lock Deadlock with emit()

**What goes wrong:** Calling `audit_service.emit()` while holding the `with lock:` context causes deadlock because `emit()` tries to acquire the same lock.

**Why it happens:** `emit()` acquires `lock` internally (see `audit_service.py` line 157: `with lock:`).

**How to avoid:** Always call `emit()` after the `with lock: with conn:` block exits. See Phase 5 `run_service.py` for the canonical pattern (emit call at line 83+, outside lock).

**Warning signs:** Hanging test, deadlock in concurrent test scenario.

### Pitfall 3: sqlite-vec Top-Level Import

**What goes wrong:** `import sqlite_vec` at module top level causes `ImportError` for every user who hasn't installed the optional semantic path.

**How to avoid:** Import inside the function body, wrapped in try/except.

**Warning signs:** `ImportError: No module named 'sqlite_vec'` when running `atlas wiki ingest` or any other non-semantic command.

### Pitfall 4: Source ID Instability on Re-ingest

**What goes wrong:** Re-ingesting the same file creates a new UUID, breaking all WikiPage.source_id and AuditEvent references to the old source.

**Why it happens:** Default `Source()` generates a new UUID on each construction.

**How to avoid:** Before inserting, check `SELECT id FROM sources WHERE sha256=? AND path=?`. If exists, update in place with the same id.

**Warning signs:** Growing sources table with duplicate SHA256 hashes; dangling source_id references.

### Pitfall 5: FTS5 Trigger Duplication

**What goes wrong:** 0002 migration attempts to recreate wiki_fts triggers, causing conflicts or silent double-indexing.

**How to avoid:** 0002 migration touches only `sources` and `memory_provenance`. Do NOT include FTS5 trigger DDL in 0002.

**Warning signs:** "table wiki_fts_insert already exists" migration error.

### Pitfall 6: wiki/log.md Write Mode

**What goes wrong:** Opening `log.md` with `open(..., "w")` truncates the existing log on every wiki update.

**How to avoid:** Always use `open(..., "a")` for log.md. Use `"w"` only for index.md (which is regenerated from DB state).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.x + pytest-cov 7.x |
| Config file | `services/wiki-runtime/pyproject.toml` (to be created in Wave 0) |
| Quick run command | `pytest services/wiki-runtime/tests/ -x -q` |
| Full suite command | `pytest services/wiki-runtime/tests/ --cov=atlas_wiki --cov-report=term-missing --cov-fail-under=80` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WIKI-01 | ingest_source creates Source row + copies to wiki/raw/ | unit | `pytest tests/test_wiki_service.py::test_ingest_source_creates_row -x` | Wave 0 |
| WIKI-01 | ingest emits wiki_update AuditEvent | unit | `pytest tests/test_wiki_service.py::test_ingest_emits_audit_event -x` | Wave 0 |
| WIKI-01 | re-ingest same file preserves source ID | unit | `pytest tests/test_wiki_service.py::test_reingest_preserves_source_id -x` | Wave 0 |
| WIKI-02 | update_wiki_page upserts row + logs + indexes | unit | `pytest tests/test_wiki_service.py::test_update_wiki_page_upsert -x` | Wave 0 |
| WIKI-02 | update_wiki_page writes MemoryProvenance record | unit | `pytest tests/test_wiki_service.py::test_update_writes_provenance -x` | Wave 0 |
| WIKI-03 | search_wiki returns ranked FTS5 results with slug + source_id | unit | `pytest tests/test_wiki_service.py::test_search_returns_ranked_results -x` | Wave 0 |
| WIKI-04 | index.md updated after every wiki page update | unit | `pytest tests/test_wiki_service.py::test_index_updated_after_update -x` | Wave 0 |
| WIKI-04 | log.md appended after every wiki update | unit | `pytest tests/test_wiki_service.py::test_log_appended_after_update -x` | Wave 0 |
| WIKI-05 | semantic_search falls back to FTS5 when sqlite-vec absent | unit | `pytest tests/test_wiki_service.py::test_semantic_fallback -x` | Wave 0 |
| WIKI-05 | semantic_search returns results via sqlite-vec when present | unit | `pytest tests/test_wiki_service.py::test_semantic_with_sqlite_vec -x` (skip if absent) | Wave 0 |
| AUDIT-03 | lint detects untrusted-only citation | unit | `pytest tests/test_wiki_service.py::test_lint_untrusted_source -x` | Wave 0 |
| AUDIT-03 | lint detects cross-page contradiction (seeded) | unit | `pytest tests/test_wiki_service.py::test_lint_detects_contradiction -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest services/wiki-runtime/tests/ -x -q`
- **Per wave merge:** `pytest services/wiki-runtime/tests/ --cov=atlas_wiki --cov-fail-under=80`
- **Phase gate:** Full suite green + coverage ≥ 80% before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `services/wiki-runtime/tests/conftest.py` — db, run_id, lock, wiki_dir fixtures
- [ ] `services/wiki-runtime/tests/test_wiki_service.py` — all 12 test stubs (xfail until Wave 1)
- [ ] `services/wiki-runtime/tests/test_cli.py` — CLI stubs via CliRunner + monkeypatch
- [ ] `services/wiki-runtime/pyproject.toml` — package scaffold
- [ ] `infra/migrations/0002_wiki_provenance.sql` — schema additions
- [ ] `packages/atlas-core/atlas_core/schemas/core.py` — Source field additions + MemoryProvenance model

---

## Security Domain

security_enforcement is enabled (config.json: `"security_enforcement": true`, ASVS level 1).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | CLI is single-operator, no auth surface in this phase |
| V3 Session Management | No | No sessions in wiki service |
| V4 Access Control | Partial | untrusted flag on Source; lint pass flags untrusted-only pages |
| V5 Input Validation | Yes | Pydantic v2 models validate all inputs before SQL; slug sanitization |
| V6 Cryptography | Yes | SHA-256 via hashlib stdlib (correct); never hand-roll |
| V7 Error Handling | Yes | No raw exception propagation to CLI; explicit ValueError + typer.Exit(1) |
| V8 Data Protection | Yes | SECRET_PATTERNS redaction in audit_service.emit() covers wiki event data |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal in ingest path | Tampering | Validate path is within workspace before copy; reject absolute paths outside project root |
| FTS5 injection via search query | Tampering | Parameterized query (`?` placeholder) — not string interpolation |
| Untrusted content injected without marking | Information Disclosure | untrusted=True required for any external-origin source; lint flags unverified pages |
| Slug collision / homoglyph slug | Tampering | Slug stored as UNIQUE in wiki_pages; Pydantic str_strip_whitespace=True; normalize to lowercase-hyphen |
| Large file ingest DoS | Availability | size_bytes stored; lint/ingest should warn on files > threshold (e.g. 10MB) |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All service code | Yes | 3.13.13 | — |
| SQLite FTS5 | WIKI-03 search | Yes | 3.50.4 | — |
| sqlite-vec extension | WIKI-05 semantic | No (not installed) | 0.1.9 on PyPI | FTS5 fallback (required by design) |
| fastembed | WIKI-05 embedding | No (not installed) | 0.8.0 on PyPI | FTS5 fallback |
| pytest 9.x | Testing | Yes (agent-runtime has it) | 9.0.2 | — |
| pytest-cov 7.x | Coverage gate | Yes (agent-runtime has it) | Present | — |

**Missing dependencies with no fallback:** None — all blockers have either fallbacks or are installable.

**Missing dependencies with fallback:** sqlite-vec and fastembed are optional; the service degrades to FTS5 search with a clear diagnostic message.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FTS5 triggers hand-maintained | Triggers already in 0001_core.sql | Phase 2 | Zero wiki-service code needed for FTS index maintenance |
| MemoryProvenance as dataclass | Pydantic v2 frozen model | Phase 6 (new) | Consistent with D-012; model_json_schema() works for TS/Rust bridge |
| Source with no trust metadata | Source.untrusted + ingested_by_run_id | Phase 6 (addition) | Enables lint + memory router policy enforcement |

**Deprecated/outdated:**
- The "TODO Phase 6: wire full-text index maintenance" comment in 0001_core.sql: the triggers ARE wired. The TODO is stale. Do not act on it.

---

## Graph Memory Research (Out of Scope — Document Only)

Per CONTEXT.md, Phase 6 must create `docs/research/GRAPH_MEMORY_RESEARCH_NOTES.md` with these open design questions (no code):

1. How should mission → run → artifact → source relationships be represented as a graph? (nodes: Mission, Run, Artifact, Source, WikiPage; edges: produced_by, referenced_by, sourced_from)
2. What graph schema serves "which decisions led to this wiki page?" (tracing AuditEvent → WikiPage → Source chain)
3. Can Graphify-style extraction produce meaningful edges from existing ATLAS artifacts? (existing `.planning/graphs/` pattern)
4. What storage backend: dedicated SQLite graph table (adjacency list) vs. embedded graph library vs. Graphify `.json` format?

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The existing `atlas` CLI entry point can be extended by importing wiki_app from atlas_wiki and calling app.add_typer() | CLI Integration Pattern | If not, wiki needs its own entry point — minor refactor, not blocking |
| A2 | fastembed default model is BAAI/bge-small-en-v1.5 (384 dims) | sqlite-vec Integration | If default model changes dimension, vector table DDL needs updating |
| A3 | `sqlite_vec.load(conn)` works correctly on Windows 11 with the win_amd64 wheel | sqlite-vec Integration | sqlite-vec might require different load path on Windows — graceful degradation covers this |

All core findings (schema state, migration state, FTS5 trigger presence, audit_service pattern, CLI pattern, test fixture pattern) are VERIFIED against the codebase.

---

## Open Questions (RESOLVED)

1. **Where does `atlas wiki` entry point live?**
   - What we know: agent-runtime pyproject.toml registers `atlas = "atlas_runtime.cli.main:app"`. wiki-runtime is a separate package.
   - What's unclear: whether wiki-runtime's pyproject.toml adds a second `atlas` script (collision) or injects into the existing one at import time.
   - Recommendation: The `try: from atlas_wiki.cli.main import wiki_app; app.add_typer(wiki_app, name="wiki")` pattern in atlas_runtime/cli/main.py is the cleanest approach. The planner must include the main.py edit in the atlas-runtime package as part of Wave 1.
   - **RESOLVED:** Plan 06-05 implements the try/except import registration in atlas_runtime/cli/main.py. The wiki_app Typer sub-app is registered at import time; no second entry point is added. Collision risk eliminated.

2. **0001 migration already applied to production databases — how does 0002 apply?**
   - What we know: conftest.py in tests applies both migrations sequentially. Production has no automated migration runner yet (Phase 7 introduces the API).
   - What's unclear: whether the CLI `_get_connection()` should auto-apply pending migrations.
   - Recommendation: Add a `_apply_migrations(conn)` helper to the CLI that runs all `infra/migrations/00XX_*.sql` files in order, skipping already-applied ones (track via a `schema_migrations` table). Keep it simple — no full migration framework.
   - **RESOLVED:** Deferred to Phase 7. For Phase 6, tests apply 0002 migration via conftest fixtures directly (db fixture calls executescript on both 0001 and 0002 in order against :memory: SQLite). No production migration runner is implemented in this phase. The CLI _get_connection() connects to the file-backed DB without auto-applying migrations; operators apply 0002 manually before first use.

3. **embedding dim for sqlite-vec vector table**
   - What we know: fastembed default is BAAI/bge-small-en-v1.5, 384 dims.
   - What's unclear: whether CONTEXT.md's "fastembed/ONNX or equivalent" allows a different model.
   - Recommendation: Use 384 dims with BAAI/bge-small-en-v1.5 as the default; make the dimension configurable via a constant.
   - **RESOLVED:** Use 384 dims with BAAI/bge-small-en-v1.5 as the default (fastembed default). Dimension exposed as a module-level constant EMBEDDING_DIM = 384 in wiki_service.py so it can be overridden without touching SQL DDL.

---

## Sources

### Primary (HIGH confidence)
- `packages/atlas-core/atlas_core/schemas/core.py` — verified all 7 existing models, field names, types
- `infra/migrations/0001_core.sql` — verified all 7 tables, FTS5 virtual table, all 3 triggers
- `services/agent-runtime/atlas_runtime/audit_service.py` — verified emit() pattern, lock acquisition, _redact()
- `services/agent-runtime/atlas_runtime/cli/main.py` — verified Typer sub-app pattern, _get_connection()/_get_lock()
- `services/agent-runtime/tests/conftest.py` — verified db/run_id/lock fixture pattern
- `services/agent-runtime/pyproject.toml` — verified dependencies, coverage config, entry point
- `docs/decisions/D-019-diverse-agent-memory-framework.md` — verified MemoryProvenance schema spec
- `docs/architecture/AGENT_MEMORY_FRAMEWORK_STRATEGY.md` — verified memory layer roles, MemoryProvenance fields
- `.planning/phases/06-wiki-runtime/CONTEXT.md` — verified all locked decisions and success criteria
- PyPI registry: sqlite-vec 0.1.9 [VERIFIED: PyPI + slopcheck OK]
- PyPI registry: fastembed 0.8.0 by Qdrant [VERIFIED: PyPI + slopcheck OK]
- alexgarcia.xyz/sqlite-vec/python.html — sqlite_vec.load(conn) API [VERIFIED: official docs]
- Python 3.13 on-machine: FTS5 available (SQLite 3.50.4) [VERIFIED: runtime check]

### Secondary (MEDIUM confidence)
- github.com/asg017/sqlite-vec — project identity confirmed (asg017 = Alex Garcia, Mozilla Builders) [VERIFIED: WebSearch + GitHub]

### Tertiary (LOW confidence)
- fastembed default model BAAI/bge-small-en-v1.5 with 384 dims — [ASSUMED] based on fastembed documentation pattern; dimension must be verified before writing vector table DDL

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified on PyPI registry + slopcheck
- Architecture: HIGH — direct codebase inspection of Phase 4/5 patterns
- Schema additions: HIGH — verified against live schema files
- FTS5 patterns: HIGH — verified triggers exist in migration
- sqlite-vec integration: MEDIUM — package verified, Windows loading not tested at runtime (graceful degradation required)
- Lint heuristics: MEDIUM — design is sound, specific thresholds are discretionary

**Research date:** 2026-06-08
**Valid until:** 2026-09-08 (stable domain — SQLite FTS5 and sqlite-vec APIs are stable; fastembed may have minor API changes)
