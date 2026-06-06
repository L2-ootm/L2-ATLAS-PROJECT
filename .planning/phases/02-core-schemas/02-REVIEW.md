# Phase 02 Code Review

**Depth:** standard
**Files reviewed:** 9
**Date:** 2026-06-05

## Summary

| Severity | Count |
|----------|-------|
| Critical | 1 |
| Warning  | 5 |
| Info     | 4 |

The implementation is structurally sound: models are frozen, datetime serialization is correct, D-012 column mapping is enforced by drift tests, and the FTS5 content-table triggers are internally consistent. The one critical issue is a meaningful gap in `SECRET_PATTERNS` coverage — JSON-formatted payloads are not redacted. Five warnings cover: a dead `None` branch in non-optional serializers (copy-paste hazard), no JSON-validity guard on `data`/`args` fields, unvalidated `sha256` format, `str_strip_whitespace` silently trimming path fields, and a fragile FK test structure. Four info items cover: duplicated migration path constant, missing column-drift tests for 3 of 7 models, missing FK enforcement tests for 5 of 7 FK relationships, and a fixture return-type annotation mismatch.

---

## Findings

### [CRITICAL] SECRET_PATTERNS does not match JSON key-value notation (core.py:26)

**File:** `packages/atlas-core/atlas_core/schemas/core.py`, line 26

The first pattern `\b(token|api[_-]?key|secret|password)=([^\s&]+)` only matches URL-querystring-style `key=value` pairs. `AuditEvent.data` and `ToolCall.args`/`result` are documented as JSON strings; JSON uses `"key": "value"` notation. A payload like `{"token": "sk-abc123"}` or `{"api_key": "xyz"}` passes through SECRET_PATTERNS without redaction. Phase 4 is explicitly responsible for applying these patterns before writing to SQLite, so this gap means secrets in JSON payloads will be stored in plaintext.

**Fix:** Add a second form matching JSON-style notation:

```python
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(token|api[_-]?key|secret|password)=([^\s&]+)"),
    re.compile(r'(?i)"(token|api[_-]?key|secret|password)"\s*:\s*"([^"]+)"'),
    re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._~+/=-]+)"),
)
```

The replacement value should substitute `"\1": "[REDACTED]"` (preserving the key) rather than dropping the token entirely, to maintain valid JSON structure after redaction.

---

### [WARNING] Non-optional datetime fields have dead `None` branch in serializer (core.py:54, 75, 113, 144, 168, 191, 217)

**File:** `packages/atlas-core/atlas_core/schemas/core.py`, multiple lines

`Mission.created_at`, `Mission.updated_at`, `Run.started_at`, `AuditEvent.timestamp`, `ToolCall.timestamp`, `Artifact.created_at`, `Source.ingested_at`, `WikiPage.created_at`, `WikiPage.updated_at` are all typed `datetime.datetime` (non-optional). Their `field_serializer` signatures accept `datetime.datetime | None` and return `str | None`, with an explicit `None` guard. This dead branch is a copy-paste artifact from `Run.finished_at` (which is genuinely optional). It introduces misleading type noise — callers of `model_dump()` will see `str | None` in IDE inference for fields that can never be `None`.

**Fix:** Split serializers: non-optional fields return `str`, optional fields return `str | None`. Alternatively, use a single serializer per model applied only to genuinely-nullable fields.

```python
# Non-optional field serializer
@field_serializer("created_at", "updated_at")
def serialize_dt(self, dt: datetime.datetime) -> str:
    return dt.isoformat()

# Optional field serializer (Run.finished_at only)
@field_serializer("finished_at")
def serialize_finished_at(self, dt: datetime.datetime | None) -> str | None:
    return None if dt is None else dt.isoformat()
```

---

### [WARNING] No JSON validity validation on `data`, `args`, `result` fields (core.py:109, 131, 134)

**File:** `packages/atlas-core/atlas_core/schemas/core.py`, lines 109, 131, 134

`AuditEvent.data`, `ToolCall.args`, and `ToolCall.result` are documented as "JSON strings" but are typed `str` with no validator. An empty string `""`, a bare value `"null"`, or malformed JSON `"{incomplete"` are all accepted silently. Phase 4 code populating these fields could write invalid JSON into SQLite with no schema-level guard, causing downstream parse failures.

**Fix:** Add a `field_validator` that calls `json.loads` and raises `ValueError` on parse failure:

```python
from pydantic import field_validator
import json

@field_validator("data", "args", mode="before")
@classmethod
def must_be_valid_json(cls, v: str) -> str:
    try:
        json.loads(v)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Field must be valid JSON: {exc}") from exc
    return v
```

`result` may legitimately be non-JSON (e.g., raw stdout), so validate only `data` and `args`.

---

### [WARNING] `Artifact.sha256` and `Source.sha256` accept arbitrary strings with no format guard (core.py:161, 182)

**File:** `packages/atlas-core/atlas_core/schemas/core.py`, lines 161, 182

Both `sha256` fields are typed `str` (one optional, one required) with no length or character-set constraint. A caller can store `"not-a-hash"`, a truncated value, or an empty string. This creates silent corruption in content-addressable lookups.

**Fix:** Add a pattern validator:

```python
import re
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")

@field_validator("sha256", mode="before")
@classmethod
def validate_sha256(cls, v: str | None) -> str | None:
    if v is not None and not _SHA256_RE.match(v):
        raise ValueError(f"sha256 must be a 64-character lowercase hex string, got: {v!r}")
    return v
```

---

### [WARNING] `str_strip_whitespace=True` silently mutates path strings (core.py:154, 178)

**File:** `packages/atlas-core/atlas_core/schemas/core.py`, lines 154, 178

`Artifact` and `Source` both set `str_strip_whitespace=True` globally via `ConfigDict`. The `path` field on both models is a filesystem path. If a caller passes a path with leading/trailing whitespace (e.g., from string interpolation), it is silently trimmed. The mutated value is stored in the model and written to SQLite without any indication that the input was modified. This can cause silent mismatches if the original string is compared against the stored value.

**Fix:** Either document this behavior explicitly in the field definition, or add a `@field_validator` for `path` that rejects (rather than silently trims) paths with surrounding whitespace to surface programmer errors early.

---

### [WARNING] FK enforcement test is fragile — commit inside `pytest.raises` block (test_migration.py:142-145)

**File:** `packages/atlas-core/tests/test_migration.py`, lines 142–145

```python
with pytest.raises(sqlite3.IntegrityError):
    db.execute("INSERT INTO runs ...", (...))
    db.commit()  # <-- inside the raises block
```

SQLite raises `IntegrityError` on `execute()` for immediate FK violations, so this passes today. However, if FK checking were deferred (e.g., `PRAGMA defer_foreign_keys = ON` or a future schema change adding `DEFERRABLE INITIALLY DEFERRED`), the error would move to `commit()`. In that case the test would still pass, but it would be testing the wrong line. More importantly, if the error is ever raised from neither line (e.g., FK checks disabled), the test would fail at `db.commit()` for a different reason.

**Fix:** Separate the execute and commit, and assert the error is raised from the execute:

```python
with pytest.raises(sqlite3.IntegrityError):
    db.execute(
        "INSERT INTO runs (id, mission_id, status, started_at) VALUES (?, ?, 'running', '2026-01-01T00:00:00')",
        (str(uuid.uuid4()), fake_mission_id),
    )
db.rollback()
```

---

### [INFO] `MIGRATION_PATH` constant is duplicated across two files (conftest.py:17-22, test_migration.py:11-16)

**File:** `packages/atlas-core/tests/conftest.py` lines 17–22 and `packages/atlas-core/tests/test_migration.py` lines 11–16

The same four-parent path construction is copy-pasted verbatim. If the migration file moves, both must be updated in sync.

**Fix:** Define `MIGRATION_PATH` only in `conftest.py` and expose it as a module-level constant or via a fixture parameter. `test_migration.py` can then import it directly: `from tests.conftest import MIGRATION_PATH` (or use a `pytest` session-scoped fixture that returns the path).

---

### [INFO] Column-name drift tests cover only 4 of 7 models (test_migration.py:101-130)

**File:** `packages/atlas-core/tests/test_migration.py`, lines 101–130

D-012 requires 1:1 column-name parity between DDL and `model_fields`. Drift tests exist for `Mission`, `Run`, `AuditEvent`, and `WikiPage`. `ToolCall`, `Artifact`, and `Source` have no corresponding drift test. Schema changes to those three models will not be caught automatically.

**Fix:** Add `test_column_names_match_fields_tool_call`, `test_column_names_match_fields_artifact`, and `test_column_names_match_fields_source` following the existing pattern.

---

### [INFO] FK enforcement tests cover only 1 of 6 FK relationships (test_migration.py:138-145)

**File:** `packages/atlas-core/tests/test_migration.py`, lines 138–145

Only the `runs.mission_id → missions.id` FK is tested. The following FKs have no enforcement test:
- `audit_events.run_id → runs.id`
- `tool_calls.audit_event_id → audit_events.id`
- `tool_calls.run_id → runs.id`
- `artifacts.run_id → runs.id`
- `wiki_pages.source_id → sources.id`

A migration error that accidentally drops `REFERENCES` from any of these would go undetected.

**Fix:** Add one `test_fk_enforcement_*` test per untested FK, following the pattern of the existing test.

---

### [INFO] Fixture return type annotation is incorrect (conftest.py:26)

**File:** `packages/atlas-core/tests/conftest.py`, line 26

The fixture is annotated `-> sqlite3.Connection` but it uses `yield`, making it a generator. The `# type: ignore[return]` suppresses the resulting mypy error. The correct annotation is `Generator[sqlite3.Connection, None, None]` (from `collections.abc`) or `Iterator[sqlite3.Connection]`.

**Fix:**

```python
from collections.abc import Generator

@pytest.fixture(name="db")
def db_fixture() -> Generator[sqlite3.Connection, None, None]:
    ...
```

---

_Reviewed: 2026-06-05_
_Reviewer: Claude (adversarial standard review)_
_Depth: standard_
