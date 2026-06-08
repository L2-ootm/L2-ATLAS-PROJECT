# Phase 6: LLM Wiki Runtime — Pattern Map

**Mapped:** 2026-06-08
**Files analyzed:** 13 new files + 1 modified file
**Analogs found:** 13 / 14

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `services/wiki-runtime/pyproject.toml` | config | — | `services/agent-runtime/pyproject.toml` | exact |
| `services/wiki-runtime/atlas_wiki/__init__.py` | config | — | `services/agent-runtime/atlas_runtime/__init__.py` | role-match |
| `services/wiki-runtime/atlas_wiki/wiki_service.py` | service | CRUD + file-I/O | `services/agent-runtime/atlas_runtime/mission_service.py` + `run_service.py` | role-match |
| `services/wiki-runtime/atlas_wiki/provenance_service.py` | service | CRUD | `services/agent-runtime/atlas_runtime/mission_service.py` | role-match |
| `services/wiki-runtime/atlas_wiki/cli/__init__.py` | config | — | `services/agent-runtime/atlas_runtime/cli/__init__.py` | role-match |
| `services/wiki-runtime/atlas_wiki/cli/main.py` | controller | request-response | `services/agent-runtime/atlas_runtime/cli/main.py` | exact |
| `services/wiki-runtime/tests/__init__.py` | config | — | `services/agent-runtime/tests/__init__.py` | role-match |
| `services/wiki-runtime/tests/conftest.py` | test | — | `services/agent-runtime/tests/conftest.py` | exact |
| `services/wiki-runtime/tests/test_wiki_service.py` | test | CRUD | `services/agent-runtime/tests/test_mission_service.py` | role-match |
| `services/wiki-runtime/tests/test_provenance_service.py` | test | CRUD | `services/agent-runtime/tests/test_mission_service.py` | role-match |
| `services/wiki-runtime/tests/test_cli.py` | test | request-response | `services/agent-runtime/tests/test_cli.py` | exact |
| `infra/migrations/0002_wiki_provenance.sql` | migration | — | `infra/migrations/0001_core.sql` | exact |
| `packages/atlas-core/atlas_core/schemas/core.py` (modify) | model | — | self (extend in-place) | exact |
| `docs/research/GRAPH_MEMORY_RESEARCH_NOTES.md` | docs | — | no analog — greenfield research doc | none |

---

## Pattern Assignments

### `services/wiki-runtime/pyproject.toml` (config)

**Analog:** `services/agent-runtime/pyproject.toml` (full file, 35 lines)

**Exact structure to copy and adapt** (lines 1–35):
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "atlas-wiki"           # change from "atlas-runtime"
version = "0.1.0"
description = "ATLAS wiki-runtime service layer"
requires-python = ">=3.11"
dependencies = [
    "atlas-core",
    "atlas-runtime",          # needed for audit_service.emit()
    "typer>=0.25.0",
]

# NOTE: no [project.scripts] entry — wiki_app registers into atlas-runtime's
# app via try/except import in atlas_runtime/cli/main.py (see CLI section)

[project.optional-dependencies]
semantic = ["sqlite-vec>=0.1.9", "fastembed>=0.8.0"]
dev = ["pytest>=9.0", "pytest-cov>=7.0"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.hatch.build.targets.wheel]
packages = ["atlas_wiki"]     # change from ["atlas_runtime", "atlas_audit"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.coverage.run]
branch = true
source = ["atlas_wiki"]       # change from "atlas_runtime"

[tool.coverage.report]
fail_under = 80
```

Key deltas from analog:
- `name` → `atlas-wiki`
- `dependencies` adds `atlas-runtime`; no `[project.scripts]` entry
- `optional-dependencies` adds `semantic` group
- `packages` → `["atlas_wiki"]`
- `source` → `["atlas_wiki"]`

---

### `services/wiki-runtime/atlas_wiki/wiki_service.py` (service, CRUD + file-I/O)

**Primary analog:** `services/agent-runtime/atlas_runtime/mission_service.py` (Pydantic-first write)
**Secondary analog:** `services/agent-runtime/atlas_runtime/run_service.py` (emit-after-lock)

**Imports pattern** — copy from `run_service.py` lines 1–29, adapt module names:
```python
from __future__ import annotations

import datetime
import hashlib
import pathlib
import shutil
import sqlite3
import threading
from typing import Optional

from atlas_core.schemas.core import Source, WikiPage, AuditEvent
from atlas_runtime.audit_service import emit
```

Note: `sqlite_vec` and `fastembed` must NOT appear at module top level — import inside function body only.

**Pydantic-first write guard** — exact pattern from `mission_service.py` lines 33–46:
```python
def create_mission(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    title: str,
    intent: str = "",
    project: str = "",
) -> Mission:
    # Pydantic-first: construct and validate before any SQL
    mission = Mission(title=title, intent=intent, project=project)
    row = mission.model_dump()

    with lock:
        with conn:
            conn.execute(
                "INSERT INTO missions"
                "(id, title, intent, status, project, created_at, updated_at) "
                "VALUES (:id, :title, :intent, :status, :project, :created_at, :updated_at)",
                row,
            )

    return mission
```

Apply identically for `ingest_source()` (constructs `Source` before SQL) and `update_wiki_page()` (constructs `WikiPage` before SQL).

**Emit-after-lock pattern** — exact pattern from `run_service.py` lines 49–88:
```python
    with lock:
        with conn:
            # ... all DB writes inside this block ...
            pass
    # Lock released — now safe to call emit() (which acquires lock internally)

    emit(
        conn,
        lock,
        run_id=run.id,
        event_type="tool_call",
        session_id=session_id,
        data={"transition": "started", "mission_id": mission_id},
    )
```

For wiki_service, use `event_type="wiki_update"` and `data={"slug": slug, "source_id": source_id}`.

**Read-back pattern** (used in `get_mission` lines 53–62 — apply to `get_page`, `get_source`):
```python
def get_mission(conn, mission_id):
    cursor = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,))
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    if row is None:
        return None
    return Mission(**dict(zip(cols, row)))
```

**Upsert re-ID pattern** (for re-ingest stable Source ID — per RESEARCH.md pitfall 4):
```python
    # After model construction:
    existing = conn.execute(
        "SELECT id FROM sources WHERE sha256=? AND path=?", (sha256, path)
    ).fetchone()
    if existing:
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
```

**Error handling pattern** — copy from `run_service.py` lines 51–58 (ValueError + state guard):
```python
    row = conn.execute("SELECT status FROM missions WHERE id=?", (mission_id,)).fetchone()
    if row is None:
        raise ValueError(f"Mission {mission_id!r} not found")
    if row[0] != "pending":
        raise ValueError(f"Cannot start run for mission in state {row[0]!r}")
```

---

### `services/wiki-runtime/atlas_wiki/provenance_service.py` (service, CRUD)

**Analog:** `services/agent-runtime/atlas_runtime/mission_service.py` (full pattern)

**Imports pattern** (adapt from `mission_service.py` lines 1–17):
```python
from __future__ import annotations

import sqlite3
import threading
from typing import Optional

from atlas_core.schemas.core import MemoryProvenance
```

**Core write pattern** — identical Pydantic-first + lock+conn block structure as `create_mission()`:
```python
def write_provenance(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    layer: str,
    item_id: str,
    run_id: Optional[str] = None,
    source_id: Optional[str] = None,
    audit_event_id: Optional[str] = None,
    operator_id: Optional[str] = None,
    sensitivity: str = "internal",
    untrusted: bool = False,
) -> MemoryProvenance:
    # Pydantic-first
    prov = MemoryProvenance(
        layer=layer, item_id=item_id, run_id=run_id,
        source_id=source_id, audit_event_id=audit_event_id,
        operator_id=operator_id, sensitivity=sensitivity, untrusted=untrusted,
    )
    row = prov.model_dump()

    with lock:
        with conn:
            conn.execute(
                "INSERT INTO memory_provenance VALUES "
                "(:id,:layer,:item_id,:run_id,:source_id,:audit_event_id,"
                ":operator_id,:sensitivity,:untrusted,:written_at)",
                row,
            )
    return prov
```

**Read pattern** — copy `get_mission()` structure with `dict(zip(cols, row))` reconstruction.

---

### `services/wiki-runtime/atlas_wiki/cli/main.py` (controller, request-response)

**Analog:** `services/agent-runtime/atlas_runtime/cli/main.py` (full file, 124 lines)

**Imports pattern** (lines 1–18):
```python
from __future__ import annotations

import pathlib
import sqlite3
import threading

import typer

from atlas_wiki import wiki_service, provenance_service
```

**App setup + sub-app registration** (lines 24–29):
```python
app = typer.Typer()
mission_app = typer.Typer(name="mission")
app.add_typer(mission_app, name="mission")
```

For wiki_cli, the `wiki_app` is a standalone Typer that gets injected into the parent:
```python
wiki_app = typer.Typer(name="wiki", help="LLM Wiki commands")
# NOT added to its own app here — added to atlas_runtime's app via try/except
```

**Connection + lock factories** — copy verbatim from lines 37–49:
```python
_LOCK = threading.Lock()

def _get_connection() -> sqlite3.Connection:
    """Return a file-backed SQLite connection with WAL + FK enabled."""
    db_path = pathlib.Path.home() / ".atlas" / "atlas.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _get_lock() -> threading.Lock:
    """Return the module-level threading.Lock singleton."""
    return _LOCK
```

**Command handler pattern** — copy from lines 57–66 (thin wrapper, service call, typer.echo):
```python
@mission_app.command("create")
def create(
    title: str = typer.Option(..., "--title", help="Mission title"),
    intent: str = typer.Option("", "--intent", help="Mission intent"),
) -> None:
    """Create a Mission and print its ID."""
    conn = _get_connection()
    lock = _get_lock()
    mission = mission_service.create_mission(conn, lock, title=title, intent=intent)
    typer.echo(mission.id)
```

**Error handling in command** — copy from lines 75–81:
```python
    try:
        run = run_service.start_run(conn, lock, mission_id=mission_id)
        typer.echo(run.id)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
```

**Extension point for atlas_runtime/cli/main.py** (one-time modification):
Add after the `mission_app` registration block (after line 26):
```python
try:
    from atlas_wiki.cli.main import wiki_app
    app.add_typer(wiki_app, name="wiki")
except ImportError:
    pass  # wiki service not installed — skip wiki subcommands gracefully
```

---

### `services/wiki-runtime/tests/conftest.py` (test fixture)

**Analog:** `services/agent-runtime/tests/conftest.py` (full file, 84 lines) — copy with two changes.

**MIGRATION_PATH pattern** (lines 21–26) — copy verbatim, then extend to apply BOTH migrations:
```python
MIGRATION_PATH = (
    pathlib.Path(__file__).parent.parent.parent.parent
    / "infra"
    / "migrations"
    / "0001_core.sql"
)
```

Wiki conftest applies both `0001_core.sql` AND `0002_wiki_provenance.sql`:
```python
MIGRATION_0001 = pathlib.Path(__file__).parent.parent.parent.parent / "infra" / "migrations" / "0001_core.sql"
MIGRATION_0002 = pathlib.Path(__file__).parent.parent.parent.parent / "infra" / "migrations" / "0002_wiki_provenance.sql"
```

**db_fixture** — copy lines 29–48 verbatim, extend to apply 0002:
```python
@pytest.fixture(name="db")
def db_fixture() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    if not MIGRATION_0001.exists():
        pytest.fail(f"Required migration not found: {MIGRATION_0001}")
    conn.executescript(MIGRATION_0001.read_text(encoding="utf-8"))
    conn.executescript(MIGRATION_0002.read_text(encoding="utf-8"))
    yield conn
    conn.close()
```

**run_id_fixture** — copy lines 51–77 verbatim (mission + run FK seed, no changes needed).

**lock_fixture** — copy lines 80–83 verbatim.

**Additional fixture for wiki tests** (no analog — new):
```python
@pytest.fixture(name="wiki_dir")
def wiki_dir_fixture(tmp_path: pathlib.Path) -> pathlib.Path:
    """Temporary wiki/ directory with index.md, log.md, raw/ for test isolation."""
    (tmp_path / "raw").mkdir()
    (tmp_path / "index.md").write_text("# ATLAS Wiki Index\n", encoding="utf-8")
    (tmp_path / "log.md").write_text("# ATLAS Wiki Log\n", encoding="utf-8")
    return tmp_path
```

---

### `services/wiki-runtime/tests/test_wiki_service.py` (test, CRUD)

**Analog:** `services/agent-runtime/tests/test_mission_service.py` (full file, 55 lines)

**Module docstring + imports pattern** (lines 1–9):
```python
"""Tests for atlas_wiki.wiki_service.

Fixtures from conftest.py (injected by name — do NOT import):
  db       — in-memory SQLite, WAL + FK ON + 0001+0002 migrations applied
  lock     — threading.Lock()
  run_id   — stable run_id with mission+run rows for FK satisfaction
  wiki_dir — tmp_path with index.md, log.md, raw/ stubs
"""
import pytest
from atlas_wiki import wiki_service
```

**Test function structure** — copy style from lines 12–54:
```python
def test_ingest_source_creates_row(db, lock, run_id, wiki_dir):
    """ingest_source() inserts exactly one row in the sources table."""
    source = wiki_service.ingest_source(db, lock, path=..., run_id=run_id,
                                        wiki_dir=wiki_dir)
    count = db.execute(
        "SELECT COUNT(*) FROM sources WHERE id=?", (source.id,)
    ).fetchone()[0]
    assert count == 1
```

**Semantic skip guard** (no analog — use importorskip):
```python
def test_semantic_with_sqlite_vec(db, lock, run_id, wiki_dir):
    sqlite_vec = pytest.importorskip("sqlite_vec", reason="sqlite-vec not installed — skip semantic tests")
    ...
```

---

### `services/wiki-runtime/tests/test_cli.py` (test, request-response)

**Analog:** `services/agent-runtime/tests/test_cli.py` (full file, 81 lines) — copy structure exactly.

**Runner setup + import pattern** (lines 14–19):
```python
import pytest
from typer.testing import CliRunner

from atlas_wiki.cli.main import wiki_app

runner = CliRunner()
```

**Monkeypatch pattern** — copy from lines 22–29 verbatim:
```python
def test_ingest_command_exits_zero(db, lock, monkeypatch, wiki_dir, tmp_path):
    """atlas wiki ingest <path> exits 0 and prints a 36-character UUID."""
    import atlas_wiki.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    # create a temp source file to ingest
    src = tmp_path / "test.txt"
    src.write_text("hello wiki", encoding="utf-8")
    result = runner.invoke(wiki_app, ["ingest", str(src)])
    assert result.exit_code == 0
    assert len(result.output.strip()) == 36
```

**Error exit pattern** — copy from lines 69–80:
```python
def test_search_no_results_exits_zero(db, lock, monkeypatch):
    """atlas wiki search returns exit 0 even with no results."""
    import atlas_wiki.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    result = runner.invoke(wiki_app, ["search", "nonexistent-query"])
    assert result.exit_code == 0
```

---

### `infra/migrations/0002_wiki_provenance.sql` (migration)

**Analog:** `infra/migrations/0001_core.sql` (full file, 107 lines)

**Header pattern** (lines 1–3):
```sql
-- ATLAS core schema migration 0001 — generated from atlas_core.schemas.core (D-012)
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
```

Copy header, change description. Then use ALTER TABLE (not CREATE TABLE) for existing `sources`:
```sql
-- ATLAS migration 0002: Source extensions + MemoryProvenance table
PRAGMA foreign_keys = ON;

-- Extend sources table (0001 has the base columns; 0002 adds trust metadata)
ALTER TABLE sources ADD COLUMN untrusted INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sources ADD COLUMN ingested_by_run_id TEXT;
```

Then CREATE TABLE with same style as 0001 (TEXT PRIMARY KEY, foreign key REFERENCES, indexes at bottom):
```sql
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
```

DO NOT include FTS5 trigger DDL — triggers are fully wired in 0001 (RESEARCH.md pitfall 5).

---

### `packages/atlas-core/atlas_core/schemas/core.py` (modify — extend Source, add MemoryProvenance)

**Analog:** self — exact existing file at `packages/atlas-core/atlas_core/schemas/core.py`

**Source model** (current, lines 173–194) — add two fields after `title`:
```python
class Source(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    path: str
    sha256: str
    size_bytes: int
    mime_type: str = "text/plain"
    ingested_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    title: str = ""
    # Phase 6 additions (D-019):
    untrusted: bool = False
    ingested_by_run_id: Optional[str] = None

    @field_serializer("ingested_at")
    def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
        return None if dt is None else dt.isoformat()
```

**MemoryProvenance model** (new — add after WikiPage, before `__all__`):

Copy `ConfigDict(frozen=True, str_strip_whitespace=True)` from every other model (line 40, 66, 88, etc.).
Copy `field_serializer("written_at")` pattern from `Mission.serialize_dt` (lines 54–57).
Copy `Field(default_factory=lambda: str(uuid.uuid4()))` for `id` from line 42.
Copy `Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))` for `written_at` from line 47.

```python
class MemoryProvenance(BaseModel):
    """Provenance record for every write to any ATLAS memory layer (D-019).

    Every wiki update, profile update, and skill modification must produce
    one MemoryProvenance row. This is the answer to "why was this stored?"
    """
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    layer: Literal["WIKI", "PROFILE", "GRAPH", "SKILL", "AUDIT"]
    item_id: str
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

**`__all__` extension** (current lines 222–231) — add `"MemoryProvenance"`:
```python
__all__ = [
    "Mission",
    "Run",
    "AuditEvent",
    "ToolCall",
    "Artifact",
    "Source",
    "WikiPage",
    "MemoryProvenance",   # add
    "SECRET_PATTERNS",
]
```

---

## Shared Patterns

### Pydantic-First Write Guard
**Source:** `services/agent-runtime/atlas_runtime/mission_service.py` lines 33–46
**Apply to:** All INSERT/UPDATE functions in `wiki_service.py` and `provenance_service.py`

Every function that writes to the DB must:
1. Construct the Pydantic model with `Model(**kwargs)` — ValidationError fires here
2. Call `model.model_dump()` to get a JSON-safe dict
3. Only then enter `with lock: with conn:` block
4. Pass the dict to `conn.execute(..., row)` using named `:field` placeholders

Never pass raw user inputs directly to SQL.

### Emit-After-Lock
**Source:** `services/agent-runtime/atlas_runtime/run_service.py` lines 49–88
**Apply to:** All state-mutating functions in `wiki_service.py`

`audit_service.emit()` acquires `lock` internally (see `audit_service.py` line 157: `with lock:`).
The data-write `with lock: with conn:` block MUST exit before calling `emit()`.
Comment every emit call site with: `# Lock released — now safe to call emit() (which acquires lock internally)`

### Connection + Lock Factory (monkeypatchable)
**Source:** `services/agent-runtime/atlas_runtime/cli/main.py` lines 29–49
**Apply to:** `atlas_wiki/cli/main.py`

Copy `_LOCK`, `_get_connection()`, and `_get_lock()` verbatim. These are the monkeypatch injection points for tests. Never call `sqlite3.connect()` directly inside a command handler.

### Model Serialization Convention (D-013)
**Source:** `packages/atlas-core/atlas_core/schemas/core.py` lines 54–57 (field_serializer)
**Apply to:** `MemoryProvenance` model

All datetime fields must have a `@field_serializer` that returns ISO 8601 string (not datetime object). This keeps `model_dump()` JSON-safe and consistent with the existing 7 models.

### Lock-Protected Connection Pattern
**Source:** `services/agent-runtime/atlas_runtime/mission_service.py` lines 37–44
**Apply to:** All DB write functions

```python
with lock:
    with conn:   # BEGIN … COMMIT / ROLLBACK
        conn.execute("INSERT ...", row)
```

`with conn:` uses SQLite's context manager to BEGIN/COMMIT. On exception it rolls back. Never use `conn.commit()` explicitly inside `with conn:`.

### CliRunner + Monkeypatch Test Pattern
**Source:** `services/agent-runtime/tests/test_cli.py` lines 22–29
**Apply to:** `services/wiki-runtime/tests/test_cli.py`

```python
import atlas_wiki.cli.main as cli_main
monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
result = runner.invoke(wiki_app, [...])
assert result.exit_code == 0
```

Always `import atlas_wiki.cli.main as cli_main` inside the test body (not at module level) so monkeypatch applies to the correct module reference.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `docs/research/GRAPH_MEMORY_RESEARCH_NOTES.md` | docs | — | No research note analog exists; greenfield doc per CONTEXT.md §"Graph-memory research" |

The graph memory notes file contains no code. Write it as plain Markdown with the four open design questions listed in RESEARCH.md §"Graph Memory Research".

---

## Critical Anti-Patterns (from RESEARCH.md — enforce in code review)

1. **Never import `sqlite_vec` or `fastembed` at module top level** — import inside function body inside `try/except ImportError`.
2. **Never call `emit()` while holding `with lock:`** — deadlock. Always release the data lock first.
3. **Never open `wiki/log.md` with `"w"` mode** — use `"a"` (append). `index.md` may use `"w"` (regenerated from DB each time).
4. **Never SELECT from `wiki_fts` without JOIN to `wiki_pages`** — `wiki_fts` is a content table with no row data. Always: `FROM wiki_fts JOIN wiki_pages wp ON wiki_fts.rowid = wp.rowid`.
5. **Never INSERT a new Source row without checking for existing sha256+path first** — re-ingest must preserve the existing `id` to keep all references valid.
6. **Never include FTS5 trigger DDL in 0002 migration** — triggers are fully wired in 0001.

---

## Metadata

**Analog search scope:** `services/agent-runtime/`, `packages/atlas-core/`, `infra/migrations/`
**Files scanned:** 9 (pyproject.toml, mission_service.py, run_service.py, audit_service.py, cli/main.py, tests/conftest.py, tests/test_cli.py, tests/test_mission_service.py, schemas/core.py, 0001_core.sql)
**Pattern extraction date:** 2026-06-08
