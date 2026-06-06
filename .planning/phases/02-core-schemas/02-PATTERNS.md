# Phase 2: Core Domain Schemas & SQLite Migration - Pattern Map

**Mapped:** 2026-06-05
**Files analyzed:** 6 new files
**Analogs found:** 5 / 6 (1 file has no close project analog)

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `packages/atlas-core/atlas_core/schemas/core.py` | model | transform (dataclass→Pydantic v2) | `L2-Atlas/src/atlas_core/mission_control/task_model.py` + `runtime/models.py` | role-match (dataclass→Pydantic port) |
| `packages/atlas-core/atlas_core/__init__.py` | config | — | `L2-Atlas/src/atlas_core/mission_control/task_model.py` (`__all__` pattern) | partial |
| `packages/atlas-core/atlas_core/schemas/__init__.py` | config | — | `L2-Atlas/src/atlas_core/mission_control/task_model.py` (`__all__` re-export) | partial |
| `packages/atlas-core/pyproject.toml` | config | — | `_EXTERNAL_REPOS/hermes-agent/pyproject.toml` | role-match (different backend) |
| `infra/migrations/0001_core.sql` | migration | CRUD | `_EXTERNAL_REPOS/hermes-agent/tests/test_hermes_state.py` (SQLite schema pattern) | partial |
| `packages/atlas-core/tests/test_schemas.py` | test | request-response | `_EXTERNAL_REPOS/hermes-agent/tests/test_hermes_state.py` | role-match |

---

## Pattern Assignments

### `packages/atlas-core/atlas_core/schemas/core.py` (model, transform)

**Primary analog:** `C:\Users\Davi\Desktop\Projects\L2-Atlas\src\atlas_core\mission_control\task_model.py`
**Secondary analog:** `C:\Users\Davi\Desktop\Projects\L2-Atlas\src\atlas_core\runtime\models.py`
**Tertiary analog:** `C:\Users\Davi\Desktop\Projects\L2-Atlas\src\atlas_core\logging\jsonl_logger.py`

**Imports pattern** — copy module-level header, adapt for Pydantic v2 (task_model.py lines 1-6, adapted):

```python
from __future__ import annotations

import datetime
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer
```

Key import changes from donor:
- Drop `dataclasses`, `pathlib.Path`, `typing.Any`
- Add `pydantic.BaseModel`, `pydantic.ConfigDict`, `pydantic.Field`, `pydantic.field_serializer`
- `from __future__ import annotations` stays — Pydantic v2 handles string annotations lazily

**Frozen model pattern** — sourced from task_model.py lines 11-12, 21-22, 31-32 (`@dataclass(frozen=True)` → Pydantic equivalent):

```python
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

Rules applied:
- Every model: `model_config = ConfigDict(frozen=True, str_strip_whitespace=True)`
- `id` always: `Field(default_factory=lambda: str(uuid.uuid4()))` — factory per instance, NOT class-level default
- Status fields: `Literal[...]` not `Enum` — emits JSON Schema `enum` array
- FK fields: plain `str`, not `uuid.UUID` — SQLite TEXT affinity, no serializer complexity

**Field serializer pattern for datetime** — sourced from jsonl_logger.py line 27 (`datetime.now(UTC).isoformat()`), adapted for Pydantic v2:

```python
@field_serializer("timestamp", "created_at", "updated_at", "started_at", "finished_at",
                  "ingested_at")
def serialize_dt(self, dt: datetime.datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()
```

Apply this serializer to every model that has `datetime` fields. Without it, `model_dump()` returns a `datetime` object rather than an ISO 8601 string, breaking SQLite TEXT column insertion and JSON serialization.

**Path→str conversion pattern** — sourced from task_model.py line 43 (`source_path: Path`) and models.py lines 22, 37, 46 (`working_directory: Path`, `files_to_change: list[Path]`):

```python
# DONOR (do NOT port):
source_path: Path

# ATLAS-CORE (correct port):
path: str  # Store path as str — pathlib.Path is not JSON-serializable cross-platform
```

Every `Path` field in the donor modules must be declared `str` in the Pydantic models. No `@field_validator` needed unless accepting `Path` at construction time (Phase 2 does not accept external input — models are instantiated by internal code).

**dict[str, Any]→str pattern** — sourced from models.py line 21 (`metadata: dict[str, Any]`) and jsonl_logger.py line 27 (`data: Mapping[str, Any]`):

```python
# DONOR (do NOT port — D-013 forbids dict[str, Any] in public fields):
metadata: dict[str, Any] = field(default_factory=dict)

# ATLAS-CORE (correct port — JSON string):
data: str = "{}"   # JSON payload; deserialize at read time in Phase 4
args: str = "{}"   # ToolCall args
result: Optional[str] = None  # ToolCall result
```

**SECRET_PATTERNS constant** — copy verbatim from jsonl_logger.py lines 12-15:

```python
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(token|api[_-]?key|secret|password)=([^\s&]+)"),
    re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._~+/=-]+)"),
)
```

Place at module level in `core.py`. The `data` field on `AuditEvent` must have its content redacted through these patterns before storage (Phase 4 enforces; Phase 2 only declares the constant).

**PolicyDecision fields pattern** — sourced from execution/policy.py lines 17-20:

```python
# Donor PolicyDecision fields to carry into ToolCall:
allowed: bool          → policy_allowed: Optional[bool]
requires_approval: bool → requires_approval: Optional[bool]
reason: str            → (omit — redundant with AuditEvent.policy_result JSON)
```

**__all__ pattern** — copy from task_model.py lines 104-111:

```python
__all__ = [
    "Mission",
    "Run",
    "AuditEvent",
    "ToolCall",
    "Artifact",
    "Source",
    "WikiPage",
    "SECRET_PATTERNS",
]
```

---

### `packages/atlas-core/atlas_core/__init__.py` (config)

**Analog:** task_model.py module-level docstring + `__all__` pattern

No close project analog — all existing Python packages (Hermes) use `__init__.py` as a full re-export hub. For atlas-core, this file is a version marker only (D-013: minimal package footprint):

```python
"""ATLAS core domain schemas and shared contracts."""

__version__ = "0.1.0"
```

Do not re-export models here — that belongs in `schemas/__init__.py`.

---

### `packages/atlas-core/atlas_core/schemas/__init__.py` (config)

**Analog:** task_model.py lines 104-111 (`__all__` re-export)

Donor pattern (task_model.py lines 104-111):
```python
__all__ = [
    "KANBAN_SECTIONS",
    "Mission",
    "MissionBoard",
    ...
]
```

Port to schemas `__init__.py` as explicit re-exports:

```python
"""Atlas-core domain schemas — public API."""

from atlas_core.schemas.core import (
    Artifact,
    AuditEvent,
    Mission,
    Run,
    Source,
    ToolCall,
    WikiPage,
    SECRET_PATTERNS,
)

__all__ = [
    "Artifact",
    "AuditEvent",
    "Mission",
    "Run",
    "Source",
    "ToolCall",
    "WikiPage",
    "SECRET_PATTERNS",
]
```

---

### `packages/atlas-core/pyproject.toml` (config)

**Analog:** `_EXTERNAL_REPOS/hermes-agent/pyproject.toml` (lines 1-60)

Hermes uses `setuptools` backend — atlas-core uses `hatchling` (D-013 dependency budget, setuptools not confirmed in uv env). Key pattern differences:

```toml
# Hermes pattern (setuptools — do NOT copy):
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

# Atlas-core pattern (hatchling):
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Hermes exact-pin rationale (lines 19-32) is worth reading — atlas-core uses `>=` ranges for dev dependencies (pytest, ruff) since they are not shipped to users, but exact pin for `pydantic` in production deps:

```toml
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

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "ANN"]
```

---

### `infra/migrations/0001_core.sql` (migration, CRUD)

**Analog:** No direct SQL migration file exists in the project. Hermes `test_hermes_state.py` implies a SQLite schema but the DDL is internal to the `SessionDB` class, not a standalone SQL file.

**Pattern source:** RESEARCH.md Code Examples section (verified on sqlite3 3.50.4).

Critical ordering constraint (from RESEARCH.md Pitfall 4):
```sql
-- These two PRAGMAs MUST be first — before any CREATE TABLE
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
```

Column-naming rule (D-012 + RESEARCH.md Pitfall 3): every column name must exactly match the Pydantic field name. No aliases, no snake-to-camel conversion.

SQLite type affinity mapping (RESEARCH.md Pattern 3):
```
str (id, FK, status, JSON payloads) → TEXT
datetime (ISO 8601)                 → TEXT
int                                 → INTEGER
bool (0/1)                          → INTEGER
float                               → REAL
Optional[X]                         → omit NOT NULL constraint
```

FTS5 virtual table (RESEARCH.md Pattern 4):
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
    title,
    body,
    content=wiki_pages,
    content_rowid=rowid
);
-- TODO Phase 6: add INSERT/UPDATE/DELETE triggers to sync wiki_fts with wiki_pages
```

---

### `packages/atlas-core/tests/test_schemas.py` (test, request-response)

**Analog:** `_EXTERNAL_REPOS/hermes-agent/tests/test_hermes_state.py`

Hermes test structure pattern (test_hermes_state.py lines 1-17):
```python
"""Tests for <module> — <what it covers>."""

import pytest
from pathlib import Path

from hermes_state import SessionDB

@pytest.fixture()
def db(tmp_path):
    """Create a SessionDB with a temp database file."""
    db_path = tmp_path / "test_state.db"
    session_db = SessionDB(db_path=db_path)
    yield session_db
    session_db.close()
```

Adapt for atlas-core migration fixture (RESEARCH.md Code Examples):
```python
"""Tests for atlas_core.schemas.core — import, model_json_schema, and SQLite migration."""

import sqlite3
import pathlib
import pytest

MIGRATION_PATH = (
    pathlib.Path(__file__).parent.parent.parent.parent
    / "infra" / "migrations" / "0001_core.sql"
)

@pytest.fixture()
def db():
    """In-memory SQLite with WAL mode, FK enforcement, and core migration applied."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    yield conn
    conn.close()
```

Test naming convention from Hermes (`test_<subject>_<condition>`):
```python
def test_import():
    from atlas_core.schemas.core import Mission  # noqa: F401

def test_model_instantiation():
    from atlas_core.schemas.core import Mission
    m = Mission(title="test")
    assert m.id  # UUID string assigned

def test_serialization_clean():
    from atlas_core.schemas.core import Artifact
    import json
    a = Artifact(run_id="r1", path="/tmp/f", artifact_type="file_write")
    dumped = a.model_dump()
    json.dumps(dumped)  # must not raise TypeError

def test_json_schema_valid():
    from atlas_core.schemas.core import Mission
    schema = Mission.model_json_schema()
    assert "properties" in schema
    assert "title" in schema["properties"]

def test_all_tables_created(db):
    expected = {"missions", "runs", "audit_events", "tool_calls",
                "artifacts", "sources", "wiki_pages"}
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    actual = {r[0] for r in rows}
    assert expected.issubset(actual)

def test_fts5_available(db):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE name='wiki_fts'"
    ).fetchone()
    assert row is not None, "wiki_fts FTS5 virtual table not created"

def test_column_names_match_fields(db):
    from atlas_core.schemas.core import Mission
    cols = {
        row[1]
        for row in db.execute("PRAGMA table_info(missions)").fetchall()
    }
    model_fields = set(Mission.model_fields.keys())
    assert model_fields == cols, f"Drift: model={model_fields}, sql={cols}"
```

---

## Shared Patterns

### Frozen dataclass → Pydantic v2 port rule
**Source:** `L2-Atlas/src/atlas_core/mission_control/task_model.py` lines 11-12, 21-22
**Apply to:** All 7 models in `core.py`

Every donor `@dataclass(frozen=True)` becomes:
```python
class ModelName(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
```

### UTC datetime default factory
**Source:** `L2-Atlas/src/atlas_core/logging/jsonl_logger.py` line 27
**Apply to:** All models with `created_at`, `updated_at`, `started_at`, `timestamp`, `ingested_at`

```python
# Donor pattern:
datetime.now(UTC).isoformat()

# Pydantic field default_factory:
Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
```

Use `datetime.timezone.utc` (stdlib) not `UTC` from `datetime` — the latter requires `from datetime import UTC` which is Python 3.11+ only but less explicit.

### field_serializer for datetime→ISO string
**Source:** RESEARCH.md Pattern 2 (verified against pydantic 2.13.4)
**Apply to:** Every model with `datetime` typed fields

```python
@field_serializer("<field_name>")
def serialize_<field>(self, dt: datetime.datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()
```

One `field_serializer` per field (or list multiple field names in one decorator if pydantic version supports it).

### SECRET_PATTERNS redaction constant
**Source:** `L2-Atlas/src/atlas_core/logging/jsonl_logger.py` lines 12-15
**Apply to:** `core.py` module level — referenced by Phase 4 when writing `AuditEvent.data`

```python
import re

SECRET_PATTERNS = (
    re.compile(r"(?i)\b(token|api[_-]?key|secret|password)=([^\s&]+)"),
    re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._~+/=-]+)"),
)
```

Phase 2 declares the constant. Phase 4 uses it. Do not call it in Phase 2 model code.

### PolicyDecision field mapping
**Source:** `L2-Atlas/src/atlas_core/execution/policy.py` lines 17-20
**Apply to:** `ToolCall` model fields `policy_allowed` and `requires_approval`

```python
# Donor PolicyDecision:
allowed: bool
requires_approval: bool
reason: str

# ToolCall Pydantic fields (optional because not all tool calls go through policy):
policy_allowed: Optional[bool] = None       # SQLite: INTEGER (0/1)
requires_approval: Optional[bool] = None    # SQLite: INTEGER (0/1)
```

### __all__ export discipline
**Source:** `L2-Atlas/src/atlas_core/mission_control/task_model.py` lines 104-111
**Apply to:** `core.py` (module), `schemas/__init__.py` (package)

Every public name exported from every module. No implicit exports.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `infra/migrations/0001_core.sql` | migration | CRUD | No standalone SQL migration file exists anywhere in the project. Hermes uses an in-code DDL approach. Use RESEARCH.md Code Examples as the pattern source. |

---

## Metadata

**Analog search scope:** `L2-Atlas/src/atlas_core/` (donor project), `_EXTERNAL_REPOS/hermes-agent/` (Hermes codebase), `packages/atlas-core/` (target package — currently empty except `src/schemas/` stub)
**Files scanned:** 6 source files read in full
**Pattern extraction date:** 2026-06-05

**Key transformation from donor to target:**
- All `@dataclass(frozen=True)` → `class X(BaseModel): model_config = ConfigDict(frozen=True, str_strip_whitespace=True)`
- All `Path` fields → `str`
- All `dict[str, Any]` fields → `str` (JSON payload)
- All `datetime.now(UTC)` → `Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))`
- Add `@field_serializer` for every `datetime` field
- Copy `SECRET_PATTERNS` verbatim from `jsonl_logger.py`
- `policy_allowed` and `requires_approval` on `ToolCall` derived from `PolicyDecision.allowed` and `PolicyDecision.requires_approval`
