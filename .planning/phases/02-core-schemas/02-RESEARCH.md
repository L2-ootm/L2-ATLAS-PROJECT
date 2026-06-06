# Phase 2: Core Domain Schemas & SQLite Migration — Research

**Researched:** 2026-06-06
**Domain:** Pydantic v2 domain models + SQLite DDL + Python package setup
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-003** (locked): SQLite/WAL/FTS5/sqlite-vec is MVP datastore. No Postgres.
- **D-012** (locked): Pydantic v2 is single schema source of truth; JSON Schema emitted for TS/Rust; SQLite DDL mirrors models. Column names in DDL match Pydantic field names 1:1.
- **D-011** (locked): Schemas at `packages/atlas-core/atlas_core/schemas/core.py`; migrations at `infra/migrations/0001_core.sql`.
- **D-013** (locked): Python for prototyping. All models use `ConfigDict(frozen=True)`. JSON-stable `model_dump()`. No dict[str, Any] in public fields. No new Python frameworks beyond pydantic/pytest/ruff/prompt_toolkit/rich.

### Claude's Discretion

- Field names and types for all 7 models (derived from donor modules + phase requirements).
- Internal structure of `packages/atlas-core/` (pyproject.toml format, `__init__.py` layout).
- SQLite column types, index strategy, FTS5 content table configuration.
- Test fixture structure within pytest.

### Deferred Ideas (OUT OF SCOPE)

- Service logic, CLI commands, API endpoints (Phases 4–7).
- Event bus wiring, database connection pool (Phase 4).
- Wiki service, ingest pipeline (Phase 6).
- CRM/Pulse models (v2.0).
- sqlite-vec loading logic (just ensure correct column types).
- Any model beyond Mission, Run, AuditEvent, ToolCall, Artifact, Source, WikiPage.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCHEMA-01 | Pydantic v2 models for Mission, Run, AuditEvent, ToolCall, Artifact, Source, WikiPage with correct fields, enums, FK relationships | Field-by-field derivation from donor modules + DIV-004 Hermes kwarg audit in this document |
| SCHEMA-02 | SQLite migration 0001_core.sql applies on fresh DB (WAL mode, foreign keys enforced, FTS5 index created) | SQLite 3.50.4 with FTS5 verified present on this machine; DDL patterns documented |
| SCHEMA-03 | model_json_schema() emits valid JSON Schema for all core Pydantic models (D-012 TS/Rust bridge) | Verified working: pydantic 2.13.4 on Python 3.11.15 emits correct schema |
</phase_requirements>

---

## Summary

Phase 2 produces two artifacts: `packages/atlas-core/atlas_core/schemas/core.py` (7 Pydantic v2 frozen models) and `infra/migrations/0001_core.sql` (matching DDL). These are pure data contracts — no service logic, no DB connections, no CLI.

The field-design challenge is reconciling three sources: (1) the donor `task_model.py` + `runtime/models.py` dataclasses from L2-Atlas, (2) the Hermes audit hook kwargs established by DIV-004 (`task_id`, `session_id`, `tool_call_id`, `duration_ms`), and (3) the downstream phase requirements (RUNTIME-03, WIKI-01..05, AUDIT-01..03) that will read these rows. Every field in every model must be derivable from these sources — no speculative fields.

The Python package environment is fully available: Python 3.11.15, pydantic 2.13.4, pytest 9.0.3, ruff 0.15.16, hatchling 1.30.1 all present and verified. SQLite 3.50.4 with FTS5 confirmed available on this machine. The package must be set up as an installable Python package under `packages/atlas-core/` using a `pyproject.toml` with hatchling backend and `pip install -e packages/atlas-core` for editable install.

**Primary recommendation:** Write models in a single file (`core.py`), derive all field names from donor modules and Hermes hook kwargs, keep FK references as plain `str` (not UUID type) for clean SQLite affinity, and write DDL column-by-column to mirror model fields exactly — no separate schema authoring.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pydantic model definitions | Python package (atlas-core) | — | D-012: single source of truth is Python |
| JSON Schema emission | Python package (atlas-core) | TS/Rust consumers | model_json_schema() is the bridge |
| SQLite DDL | infra/migrations/ | — | D-012: DDL mirrors models, not authored independently |
| Package installability | packages/atlas-core/pyproject.toml | — | must be importable by all services |
| Test validation | packages/atlas-core/tests/ | — | pytest validates import + schema + migration |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.13.4 [VERIFIED: PyPI registry] | Data models, JSON Schema emission, validation | D-012 locked; Rust-backed core; maps to Rust structs cleanly |
| pytest | 9.0.3 [VERIFIED: PyPI registry] | Test runner | D-013 locked; dev-only |
| ruff | 0.15.16 [VERIFIED: PyPI registry] | Linter + formatter | D-013 locked; dev-only |
| hatchling | 1.30.1 [VERIFIED: PyPI registry] | Build backend for pyproject.toml | PEP 517 standard; no dependencies beyond packaging |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlite3 | stdlib (3.50.4) [VERIFIED: local machine] | Migration application in tests | Only in test fixtures; no DB connection in atlas-core models |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hatchling | flit-core | flit requires `__version__` in module; hatchling is more flexible |
| hatchling | setuptools | setuptools not installed in the uv-managed env; hatchling confirmed installable |
| Literal[...] for enums | Python Enum subclass | Literal gives tighter JSON Schema `enum` arrays; Enum is serialized as string via pydantic but requires extra `use_enum_values=True` config |
| str for FK fields | uuid.UUID | UUID type adds json_schema_extra complexity and sqlite affinity friction; plain str is cleaner |

**Installation:**
```bash
pip install -e packages/atlas-core          # editable install (dev)
pip install -e "packages/atlas-core[dev]"   # includes pytest and ruff
```

---

## Package Legitimacy Audit

| Package | Registry | slopcheck | Disposition |
|---------|----------|-----------|-------------|
| pydantic | PyPI | [OK] | Approved |
| pytest | PyPI | [OK] | Approved |
| ruff | PyPI | [OK] | Approved |
| hatchling | PyPI | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

slopcheck 0.6.1 ran on all 4 packages against PyPI. All 4 returned [OK].

---

## Architecture Patterns

### System Architecture Diagram

```
Donor modules (L2-Atlas src/)
  task_model.py  ──────────────┐
  runtime/models.py ──────────►│   packages/atlas-core/
  logging/jsonl_logger.py ────►│   atlas_core/schemas/core.py
  execution/policy.py ────────►│   (7 Pydantic v2 frozen models)
                               │          │
Hermes hook kwargs (DIV-004)   │          │  model_json_schema()
  task_id, session_id,         │          ▼
  tool_call_id, duration_ms ──►│   JSON Schema (TS/Rust bridge)
                               │
                               │   infra/migrations/0001_core.sql
                               └──►(DDL mirrors model fields 1:1)
                                          │
                                          ▼
                                   SQLite :memory: / atlas.db
                                   (WAL, FK ON, FTS5 virtual table)
```

### Recommended Project Structure

```
packages/atlas-core/
├── pyproject.toml           # hatchling build backend, pydantic dep
├── atlas_core/
│   ├── __init__.py          # package version only
│   └── schemas/
│       ├── __init__.py      # re-exports all 7 models + enums
│       └── core.py          # all 7 Pydantic v2 models
└── tests/
    ├── conftest.py          # :memory: SQLite fixture
    └── test_schemas.py      # import, model_json_schema, migration tests

infra/
└── migrations/
    └── 0001_core.sql        # DDL for all 7 tables + FTS5
```

### Pattern 1: Frozen Pydantic v2 Model with JSON-Stable Serialization

All 7 models follow this pattern verbatim (D-013 migration contract).

```python
# Source: D-013-language-strategy.md + pydantic 2.x docs
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Optional
import datetime
import uuid


class Mission(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    intent: str = ""
    status: Literal["pending", "running", "succeeded", "failed", "cancelled"] = "pending"
    project: str = ""
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
```

Key rules:
- `frozen=True` on all models — maps to Rust `#[derive(Clone)]`, prevents accidental mutation.
- `str_strip_whitespace=True` on top-level models — prevents trailing whitespace drift in stored text.
- `datetime` fields always UTC — use `datetime.timezone.utc` in `default_factory`.
- FK fields are plain `str` — `run_id: str`, `mission_id: str`, not `uuid.UUID`.
- `Optional[X]` with `= None` for nullable fields.
- `Literal[...]` for status enums — emits `enum` in JSON Schema.

### Pattern 2: Field Serializer for datetime (JSON-Stable Output)

```python
# Source: D-013 rule: "model_dump() is the canonical wire format; no Python-specific types"
from pydantic import field_serializer
import datetime

class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    @field_serializer("timestamp")
    def serialize_timestamp(self, dt: datetime.datetime) -> str:
        return dt.isoformat()
```

`field_serializer` ensures `model_dump()` returns ISO 8601 strings, not `datetime` objects. This makes the output directly insertable into SQLite TEXT columns and serializable to JSON without `default=str`.

### Pattern 3: SQLite Type Affinity Mapping

```sql
-- Source: SQLite documentation + verified locally (sqlite3 3.50.4)
-- Python -> SQLite mapping for ATLAS schema:
--   str (id, FK, status enum) -> TEXT
--   datetime (ISO 8601 string)  -> TEXT
--   int                          -> INTEGER
--   bool (stored as 0/1)         -> INTEGER
--   float                        -> REAL
--   Optional[str] nullable       -> TEXT (no NOT NULL constraint)
--   dict/list (JSON payload)     -> TEXT (JSON1 functions work on TEXT)
```

Never use SQLite BLOB for UUIDs or datetimes — TEXT affinity allows index usage and human-readable dumps.

### Pattern 4: FTS5 Virtual Table with content= for wiki search

```sql
-- Source: SQLite FTS5 documentation + verified locally
CREATE VIRTUAL TABLE wiki_fts USING fts5(
    title,
    body,
    content=wiki_pages,
    content_rowid=rowid
);
```

`content=wiki_pages` makes FTS5 a content table backed by `wiki_pages`. This avoids storing text twice. The tradeoff: FTS index must be manually updated on INSERT/UPDATE/DELETE via triggers. For Phase 2 scope (DDL only), include the triggers stub or document that Phase 6 adds them.

### Anti-Patterns to Avoid

- **`dict[str, Any]` in public model fields:** Forbidden by D-013. Use a typed nested model or `str` for JSON payloads that will be deserialized at read time.
- **`Path` objects in Pydantic models:** `pathlib.Path` is not JSON-serializable without a custom serializer. Store paths as `str`. The donor models use `Path` — convert on port.
- **`model_rebuild()` calls:** Needed only for forward references. If using `from __future__ import annotations`, pydantic v2 handles string annotations lazily — call `model_rebuild()` at module bottom only if you have actual circular refs.
- **Separate DDL authoring:** Never write the DDL independently of the model. Write the model first, then derive each column name and type from the field. A column that doesn't correspond to a model field is a drift bug.
- **WAL mode in connection string:** `PRAGMA journal_mode=WAL` must be the FIRST pragma executed after opening the connection, before any DML. In tests, execute it before creating tables.

---

## Canonical Field Design (SCHEMA-01)

This is the definitive field list. Derived from: donor modules (verified above), Hermes DIV-004 audit, and downstream phase requirements (RUNTIME-03, WIKI-01..05, AUDIT-01..02).

### Mission

Sourced from: `task_model.py:Mission` + RUNTIME-01 (create mission via CLI/API)

| Field | Type | SQLite | Notes |
|-------|------|--------|-------|
| `id` | `str` | TEXT PK | UUID string |
| `title` | `str` | TEXT NOT NULL | |
| `intent` | `str` | TEXT NOT NULL DEFAULT '' | Freeform goal description |
| `status` | `Literal["pending","running","succeeded","failed","cancelled"]` | TEXT NOT NULL | |
| `project` | `str` | TEXT NOT NULL DEFAULT '' | From donor `Mission.project` |
| `created_at` | `datetime` | TEXT NOT NULL | ISO 8601 UTC |
| `updated_at` | `datetime` | TEXT NOT NULL | ISO 8601 UTC |

Donor fields dropped: `raw_line`, `line_number`, `source_path`, `tags`, `flags`, `section` — these are parser artifacts, not domain state. `steps` moved to a separate `MissionStep` model (not a Phase 2 schema — steps are ephemeral parse output, not persisted rows; only `Run` persists execution state).

### Run

Sourced from: RUNTIME-02 (execute mission), RUNTIME-04 (status/timestamps/summary)

| Field | Type | SQLite | Notes |
|-------|------|--------|-------|
| `id` | `str` | TEXT PK | UUID string |
| `mission_id` | `str` | TEXT NOT NULL | FK → missions.id |
| `session_id` | `Optional[str]` | TEXT | Hermes session_id kwarg (DIV-003 join key) |
| `status` | `Literal["running","succeeded","failed","cancelled"]` | TEXT NOT NULL | |
| `started_at` | `datetime` | TEXT NOT NULL | |
| `finished_at` | `Optional[datetime]` | TEXT | NULL while running |
| `summary` | `str` | TEXT NOT NULL DEFAULT '' | RUNTIME-04 |

### AuditEvent

Sourced from: `jsonl_logger.py` (timestamp/event/data pattern) + DIV-004 (Hermes kwargs) + D-002 (what to audit)

| Field | Type | SQLite | Notes |
|-------|------|--------|-------|
| `id` | `str` | TEXT PK | UUID string |
| `run_id` | `str` | TEXT NOT NULL | FK → runs.id |
| `task_id` | `Optional[str]` | TEXT | Hermes correlation key (DIV-004 — replaces `turn_id`) |
| `session_id` | `Optional[str]` | TEXT | Hermes session_id from hook kwarg |
| `tool_call_id` | `Optional[str]` | TEXT | Hermes tool_call_id from hook kwarg |
| `event_type` | `Literal["llm_call","tool_call","subagent_run","approval","artifact","wiki_update","memory_change","failure"]` | TEXT NOT NULL | D-002 audit taxonomy |
| `tool_name` | `Optional[str]` | TEXT | Set for tool_call events |
| `timestamp` | `datetime` | TEXT NOT NULL | |
| `duration_ms` | `Optional[int]` | INTEGER | Hermes post_tool_call kwarg |
| `data` | `str` | TEXT NOT NULL DEFAULT '{}' | JSON string (redacted via SECRET_PATTERNS) |
| `policy_result` | `Optional[str]` | TEXT | JSON of PolicyDecision when applicable |

`data` is a `str` typed field containing a JSON payload. This is intentional: (a) JSON1 functions work on SQLite TEXT, (b) avoids `dict[str, Any]` forbidden by D-013, (c) deserialized at read time in Phase 4.

### ToolCall

Sourced from: `runtime/models.py:CommandRequest + CommandResult` + RUNTIME-03

| Field | Type | SQLite | Notes |
|-------|------|--------|-------|
| `id` | `str` | TEXT PK | UUID string |
| `audit_event_id` | `str` | TEXT NOT NULL | FK → audit_events.id |
| `run_id` | `str` | TEXT NOT NULL | FK → runs.id (denormalized for query speed) |
| `tool_name` | `str` | TEXT NOT NULL | |
| `args` | `str` | TEXT NOT NULL DEFAULT '{}' | JSON string |
| `result` | `Optional[str]` | TEXT | JSON string |
| `exit_code` | `Optional[int]` | INTEGER | For shell commands |
| `stdout` | `Optional[str]` | TEXT | |
| `stderr` | `Optional[str]` | TEXT | |
| `duration_ms` | `Optional[int]` | INTEGER | |
| `policy_allowed` | `Optional[bool]` | INTEGER | 0/1 from PolicyDecision.allowed |
| `requires_approval` | `Optional[bool]` | INTEGER | 0/1 from PolicyDecision.requires_approval |
| `timestamp` | `datetime` | TEXT NOT NULL | |

### Artifact

Sourced from: DIV-002 (artifact capture via post_tool_call name filtering) + AUDIT-01/02

| Field | Type | SQLite | Notes |
|-------|------|--------|-------|
| `id` | `str` | TEXT PK | UUID string |
| `run_id` | `str` | TEXT NOT NULL | FK → runs.id |
| `audit_event_id` | `Optional[str]` | TEXT | FK → audit_events.id |
| `path` | `str` | TEXT NOT NULL | File path as string (D-013: no Path objects) |
| `artifact_type` | `Literal["file_write","file_edit","file_delete","unknown"]` | TEXT NOT NULL | |
| `sha256` | `Optional[str]` | TEXT | SHA-256 of content at capture time |
| `size_bytes` | `Optional[int]` | INTEGER | |
| `created_at` | `datetime` | TEXT NOT NULL | |

### Source

Sourced from: WIKI-01 (immutable raw copy, SHA-256 stamped, Source row)

| Field | Type | SQLite | Notes |
|-------|------|--------|-------|
| `id` | `str` | TEXT PK | UUID string |
| `path` | `str` | TEXT NOT NULL | Stored path (relative to project root) |
| `sha256` | `str` | TEXT NOT NULL | Content hash at ingest |
| `size_bytes` | `int` | INTEGER NOT NULL | |
| `mime_type` | `str` | TEXT NOT NULL DEFAULT 'text/plain'` | |
| `ingested_at` | `datetime` | TEXT NOT NULL | |
| `title` | `str` | TEXT NOT NULL DEFAULT ''` | Human-readable label |

### WikiPage

Sourced from: WIKI-02 (create/update page), WIKI-03 (FTS search), WIKI-04 (index.md consistency)

| Field | Type | SQLite | Notes |
|-------|------|--------|-------|
| `id` | `str` | TEXT PK | UUID string |
| `slug` | `str` | TEXT NOT NULL UNIQUE | URL-safe identifier |
| `title` | `str` | TEXT NOT NULL | |
| `body` | `str` | TEXT NOT NULL DEFAULT ''` | Markdown content |
| `source_id` | `Optional[str]` | TEXT | FK → sources.id (if derived from a Source) |
| `created_at` | `datetime` | TEXT NOT NULL | |
| `updated_at` | `datetime` | TEXT NOT NULL | |
| `version` | `int` | INTEGER NOT NULL DEFAULT 1` | Increment on each update |

FTS5 virtual table `wiki_fts` indexes `title` and `body` from this table.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON Schema generation | Manual schema dict | `Model.model_json_schema()` | Pydantic v2 generates correct draft-2020-12 schema with `$defs` for nested models |
| Datetime serialization | `str(dt)` or `repr(dt)` | `field_serializer` returning `.isoformat()` | `str(datetime)` output varies by platform; `.isoformat()` is always RFC 3339 |
| UUID generation | `uuid.uuid4()` inline | `Field(default_factory=lambda: str(uuid.uuid4()))` | factory runs per-instance; class-level default would share one UUID |
| SQLite WAL activation | Any ORM config | Raw `PRAGMA journal_mode=WAL` | D-013 bans ORMs; WAL is a one-liner |
| FTS5 content sync | Manual INSERT into fts table | `content=wiki_pages` with triggers | content table avoids duplication; triggers handle sync |
| Secret redaction | New pattern | `SECRET_PATTERNS` from `logging/jsonl_logger.py` | Donor module has two tested regex patterns; copy verbatim per FOUND-04 |

**Key insight:** Pydantic v2 is Rust-backed at its core (`pydantic-core 2.46.4`). The validation, serialization, and schema emission are already optimized — hand-rolling any of these produces slower, buggier output.

---

## Common Pitfalls

### Pitfall 1: `Path` Objects in Pydantic Models

**What goes wrong:** Pydantic v2 serializes `pathlib.Path` as a POSIX string on Linux/Mac but as a Windows path string on Windows. `model_dump()` returns a `PurePosixPath` or `WindowsPath` object (not a str), breaking JSON serialization and SQLite insertion.

**Why it happens:** Donor models (`task_model.py:Mission.source_path`, `runtime/models.py:CommandRequest.working_directory`) use `Path` directly. Porting them without conversion brings the type in.

**How to avoid:** Declare all path fields as `str`. Accept `str | Path` in validators if needed, cast to `str` in a `@field_validator`.

**Warning signs:** `TypeError: Object of type PosixPath is not JSON serializable` when calling `model_dump()` without `mode="json"`.

### Pitfall 2: `dict[str, Any]` in Public Fields

**What goes wrong:** D-013 explicitly forbids this. Pydantic v2 emits `{}` type in JSON Schema for untyped dicts, breaking TS/Rust code generation. Rust serde cannot deserialize `serde_json::Value` without losing type safety.

**Why it happens:** `runtime/models.py:TaskInput.metadata` is `dict[str, Any]`. Copy-paste ports it.

**How to avoid:** For the `data` field on `AuditEvent` and `args`/`result` on `ToolCall`, use `str` typed as JSON. Deserialize at read time in Phase 4.

**Warning signs:** JSON Schema for a model contains `{}` under any property — that's an `Any` type leaking through.

### Pitfall 3: Schema Drift Between Pydantic Fields and DDL Columns

**What goes wrong:** A field is renamed or added in Python but the SQL file is not updated, or vice versa. Phase 4 runs `INSERT INTO audit_events (...)` with a column list that doesn't match the table.

**Why it happens:** Two files maintaining the same schema independently.

**How to avoid:** Write the DDL as a direct transcription of the model: for each field in the model, write a column with the same name. The success criterion "column names in DDL match Pydantic field names 1:1" must be verified by a test (see Validation Architecture below).

**Warning signs:** `sqlite3.OperationalError: table audit_events has no column named X` at test time.

### Pitfall 4: Missing `PRAGMA foreign_keys = ON`

**What goes wrong:** SQLite does not enforce FK constraints by default. Tests pass even when FK values point to nonexistent rows. Phase 4 inserts `AuditEvent` with a bogus `run_id` and it succeeds silently.

**Why it happens:** It's not on by default and must be set per-connection.

**How to avoid:** First two lines of every migration test:
```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys = ON")
```

**Warning signs:** FK violations appear at Phase 5 runtime, not Phase 2 tests.

### Pitfall 5: FTS5 `content=` Table Requires Trigger Maintenance

**What goes wrong:** Inserting rows into `wiki_pages` does not update the FTS5 index when using `content=wiki_pages`. WIKI-03 full-text search returns no results.

**Why it happens:** SQLite FTS5 content tables are read-backed from the base table but not auto-synced on writes.

**How to avoid:** Phase 2 DDL must include INSERT/UPDATE/DELETE triggers or a comment noting Phase 6 adds them. Verify the virtual table creates without error; leave the trigger stubs as a documented gap.

**Warning signs:** `wiki_fts` table exists but `SELECT * FROM wiki_fts WHERE wiki_fts MATCH 'query'` returns 0 rows after INSERT.

### Pitfall 6: `uv` Environment Targeting

**What goes wrong:** `pip install` in this project targets `C:\Users\Davi\AppData\Local\hermes\hermes-agent\venv` (the active uv environment is the Hermes venv). `import atlas_core` fails because the editable install went to the wrong environment.

**Why it happens:** `uv pip install` defaults to the most recently activated environment. The project has no `.venv` yet.

**How to avoid:** Create a project-level venv first:
```bash
uv venv packages/atlas-core/.venv --python 3.11
uv pip install -e packages/atlas-core --python packages/atlas-core/.venv/Scripts/python.exe
```
Or use `uv run` with the project venv. Document the target environment in `packages/atlas-core/README` (no .md files required — just a comment in pyproject.toml).

---

## Code Examples

### pyproject.toml for atlas-core

```toml
# Source: hatchling docs + D-013 dependency budget
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "atlas-core"
version = "0.1.0"
description = "ATLAS domain schemas and shared contracts"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.0"]

[project.optional-dependencies]
dev = ["pytest>=9.0", "ruff>=0.15"]

[tool.hatch.build.targets.wheel]
packages = ["atlas_core"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "ANN"]
```

### Migration DDL skeleton

```sql
-- Source: SQLite WAL/FK/FTS5 documentation + verified on sqlite3 3.50.4
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS missions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    intent      TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',
    project     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    mission_id  TEXT NOT NULL REFERENCES missions(id),
    session_id  TEXT,
    status      TEXT NOT NULL DEFAULT 'running',
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    summary     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit_events (
    id            TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES runs(id),
    task_id       TEXT,
    session_id    TEXT,
    tool_call_id  TEXT,
    event_type    TEXT NOT NULL,
    tool_name     TEXT,
    timestamp     TEXT NOT NULL,
    duration_ms   INTEGER,
    data          TEXT NOT NULL DEFAULT '{}',
    policy_result TEXT
);

-- (tool_calls, artifacts, sources, wiki_pages tables follow same pattern)

CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
    title,
    body,
    content=wiki_pages,
    content_rowid=rowid
);
```

### pytest fixture for migration validation

```python
# Source: sqlite3 stdlib + pytest docs
import sqlite3
import pathlib
import pytest

MIGRATION_PATH = pathlib.Path(__file__).parent.parent.parent.parent / "infra" / "migrations" / "0001_core.sql"

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    yield conn
    conn.close()

def test_all_tables_created(db):
    expected = {"missions", "runs", "audit_events", "tool_calls", "artifacts", "sources", "wiki_pages"}
    rows = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    actual = {r[0] for r in rows}
    assert expected.issubset(actual)

def test_fts5_available(db):
    # Virtual tables appear as type='table' in sqlite_master
    row = db.execute("SELECT name FROM sqlite_master WHERE name='wiki_fts'").fetchone()
    assert row is not None, "wiki_fts FTS5 table not created"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 `validator` decorator | Pydantic v2 `field_validator` + `model_validator` | Pydantic 2.0 (2023) | v1 validators raise `ValidationError` with different structure; don't mix |
| `schema()` classmethod | `model_json_schema()` classmethod | Pydantic 2.0 | `schema()` removed in v2 |
| `dict()` instance method | `model_dump()` instance method | Pydantic 2.0 | `dict()` removed in v2 |
| `parse_obj()` | `model_validate()` | Pydantic 2.0 | `parse_obj()` removed in v2 |
| `__fields__` attribute | `model_fields` attribute | Pydantic 2.0 | needed for field introspection in schema-drift test |

**Deprecated/outdated:**
- `class Config:` (Pydantic v1 style): replaced by `model_config = ConfigDict(...)`. Do not use the old style — it is silently ignored in v2 if mixed incorrectly.
- `orm_mode = True`: replaced by `from_attributes = True` in `ConfigDict`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `MissionStep` (ephemeral parse artifact) is not persisted as a table in Phase 2 | Canonical Field Design | If Phase 5 needs step persistence, a `mission_steps` table must be added — low risk, additive |
| A2 | `ToolCall` rows are the canonical record of shell command execution; `AuditEvent` references them | Canonical Field Design | If Phase 4 decides AuditEvent is sufficient without a separate tool_calls table, `tool_calls` can be dropped — medium risk |
| A3 | `wiki_fts` trigger stubs are deferred to Phase 6 | Common Pitfalls | Phase 2 creates the virtual table; Phase 6 adds triggers. If WIKI-03 is blocked by missing triggers, Phase 6 must add them before wiki service tests pass — acceptable since WIKI-03 is Phase 6 scope |

---

## Open Questions

1. **`MissionStep` persistence**
   - What we know: Donor `task_model.py` treats steps as ephemeral (parsed from Markdown). Phase 2 success criteria do not list a `mission_steps` table.
   - What's unclear: RUNTIME-01 (create mission + persist) — does "persist" include steps?
   - Recommendation: Omit `mission_steps` table from Phase 2. Add in Phase 5 if the mission lifecycle needs it.

2. **FTS5 trigger stubs in 0001_core.sql**
   - What we know: FTS5 `content=` tables need triggers for index sync. Phase 2 scope is DDL only.
   - What's unclear: Should Phase 2 DDL include the trigger stubs (CREATE TRIGGER ... with no-op body) or leave a comment?
   - Recommendation: Include stub triggers with a `-- TODO Phase 6: sync logic` comment. This prevents Phase 6 from needing to run a second migration for triggers.

3. **uv environment strategy for atlas-core**
   - What we know: The current active uv env is the Hermes venv. Atlas-core needs its own venv or uses the root project environment.
   - What's unclear: Should there be a root `.venv` for the whole monorepo, or a per-package venv?
   - Recommendation: Create `packages/atlas-core/.venv` scoped to the package. This matches the polyglot monorepo model where services have independent Python envs.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All models + tests | ✓ | 3.11.15 | — |
| pydantic | atlas_core/schemas/core.py | ✓ | 2.13.4 (installed in Python 3.13 env) | — |
| sqlite3 | Migration tests | ✓ | 3.50.4 (stdlib) | — |
| FTS5 extension | SCHEMA-02 | ✓ | bundled in sqlite3 3.50.4 | Document as blocked if absent |
| pytest | tests/ | ✓ | 9.0.3 | — |
| ruff | linting | ✓ | 0.15.16 | — |
| hatchling | pyproject.toml build | ✓ | 1.30.1 | flit-core 3.12.0 (also available) |
| uv | package management | ✓ | 0.11.16 | pip directly |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

**Critical note on Python environment:** `pip install` currently defaults to the Hermes venv at `C:\Users\Davi\AppData\Local\hermes\hermes-agent\venv`. The planner must include a Wave 0 task to create `packages/atlas-core/.venv` before installing atlas-core in editable mode.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `packages/atlas-core/pyproject.toml` (`[tool.pytest.ini_options]`) — Wave 0 |
| Quick run command | `pytest packages/atlas-core/tests/ -x -q` |
| Full suite command | `pytest packages/atlas-core/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCHEMA-01 | `from atlas_core.schemas.core import Mission` succeeds | unit (import) | `pytest packages/atlas-core/tests/test_schemas.py::test_import -x` | ❌ Wave 0 |
| SCHEMA-01 | All 7 models instantiate with defaults | unit | `pytest packages/atlas-core/tests/test_schemas.py::test_model_instantiation -x` | ❌ Wave 0 |
| SCHEMA-01 | FK fields are plain `str`, no `Path` objects in model_dump() | unit | `pytest packages/atlas-core/tests/test_schemas.py::test_serialization_clean -x` | ❌ Wave 0 |
| SCHEMA-02 | `0001_core.sql` applies on `:memory:` without error | unit | `pytest packages/atlas-core/tests/test_migration.py::test_migration_applies -x` | ❌ Wave 0 |
| SCHEMA-02 | All 7 tables created | unit | `pytest packages/atlas-core/tests/test_migration.py::test_all_tables_created -x` | ❌ Wave 0 |
| SCHEMA-02 | FTS5 virtual table created | unit | `pytest packages/atlas-core/tests/test_migration.py::test_fts5_available -x` | ❌ Wave 0 |
| SCHEMA-02 | Column names match Pydantic field names 1:1 | unit | `pytest packages/atlas-core/tests/test_migration.py::test_column_names_match_fields -x` | ❌ Wave 0 |
| SCHEMA-03 | `Mission.model_json_schema()` emits valid JSON Schema | unit | `pytest packages/atlas-core/tests/test_schemas.py::test_json_schema_valid -x` | ❌ Wave 0 |
| SCHEMA-03 | All required fields present in schema | unit | `pytest packages/atlas-core/tests/test_schemas.py::test_json_schema_fields -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest packages/atlas-core/tests/ -x -q`
- **Per wave merge:** `pytest packages/atlas-core/tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `packages/atlas-core/.venv` — project-scoped venv, required before editable install
- [ ] `packages/atlas-core/pyproject.toml` — build config with hatchling + dev extras
- [ ] `packages/atlas-core/atlas_core/__init__.py` — package version marker
- [ ] `packages/atlas-core/atlas_core/schemas/__init__.py` — re-exports all 7 models
- [ ] `packages/atlas-core/tests/__init__.py` — empty
- [ ] `packages/atlas-core/tests/conftest.py` — `:memory:` SQLite fixture
- [ ] `packages/atlas-core/tests/test_schemas.py` — covers SCHEMA-01, SCHEMA-03
- [ ] `packages/atlas-core/tests/test_migration.py` — covers SCHEMA-02
- [ ] Install: `uv pip install -e "packages/atlas-core[dev]"` targeting the atlas-core venv

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (partial) | pydantic v2 strict validation on all model fields |
| V6 Cryptography | no | SHA-256 in `Source.sha256` is read-only storage, not hand-rolled crypto |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret leakage in AuditEvent.data | Information Disclosure | `SECRET_PATTERNS` redaction (from `jsonl_logger.py`) applied before storing `data` field |
| SQL injection via field values in Phase 4 | Tampering | Phase 2 produces schema only; Phase 4 must use parameterized queries — document this boundary |
| Schema drift enabling silent data corruption | Tampering | Test: `test_column_names_match_fields` — introspect `sqlite_master` columns against `model_fields` |

---

## Sources

### Primary (HIGH confidence)

- D-012-schema_source_of_truth.md — Pydantic v2 locked, DDL mirrors models, `model_json_schema()` bridge
- D-013-language-strategy.md — `frozen=True` mandate, `model_dump()` JSON-stable rule, dependency budget
- D-011-repo_layout.md — exact file paths for core.py and 0001_core.sql
- HERMES_FOUNDATION_AUDIT.md — DIV-004: `post_tool_call` kwargs are `task_id, session_id, tool_call_id, duration_ms`
- L2_ATLAS_MODULE_EXTRACTION_PLAN.md — donor field names from `task_model.py`, `runtime/models.py`, `logging/jsonl_logger.py`, `execution/policy.py`
- Verified: Python 3.11.15, pydantic 2.13.4, pytest 9.0.3, ruff 0.15.16, hatchling 1.30.1 on local machine
- Verified: sqlite3 3.50.4 with FTS5, WAL, FK all functional on `:memory:` connection

### Secondary (MEDIUM confidence)

- pydantic v2 migration guide (training knowledge + confirmed by live test): `model_dump()`, `model_json_schema()`, `ConfigDict(frozen=True)`, `field_serializer` all verified working on this machine
- SQLite FTS5 `content=` table pattern (training knowledge + confirmed by local test execution)

### Tertiary (LOW confidence)

None — all claims verified or cited from project decisions.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified via pip registry and local import
- Architecture: HIGH — field design derived directly from donor modules and locked decisions
- Pitfalls: HIGH — all pitfalls verified with live Python/SQLite tests on this machine
- Environment: HIGH — all tools probed with actual commands

**Research date:** 2026-06-06
**Valid until:** 2026-07-06 (pydantic and ruff release frequently; re-verify versions before install if > 30 days old)
