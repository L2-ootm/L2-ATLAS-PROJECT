# Phase 4: ATLAS Event Bus & Audit Core - Pattern Map

**Mapped:** 2026-06-07
**Files analyzed:** 7 new files
**Analogs found:** 7 / 7

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `services/agent-runtime/atlas_audit/__init__.py` | plugin | event-driven | `_EXTERNAL_REPOS/hermes-agent/plugins/observability/langfuse/__init__.py` | exact |
| `services/agent-runtime/atlas_audit/plugin.yaml` | config | — | `_EXTERNAL_REPOS/hermes-agent/plugins/observability/langfuse/plugin.yaml` | exact |
| `services/agent-runtime/atlas_runtime/audit_service.py` | service | CRUD + file-I/O | `packages/atlas-core/atlas_core/schemas/core.py` + stdlib sqlite3 pattern from RESEARCH.md | role-match |
| `services/agent-runtime/pyproject.toml` | config | — | `packages/atlas-core/pyproject.toml` (see note) | role-match |
| `services/agent-runtime/tests/conftest.py` | test | — | `packages/atlas-core/tests/conftest.py` | exact |
| `services/agent-runtime/tests/test_audit_service.py` | test | CRUD | `packages/atlas-core/tests/conftest.py` (fixture pattern) | role-match |
| `services/agent-runtime/tests/test_atlas_audit_plugin.py` | test | event-driven | `_EXTERNAL_REPOS/hermes-agent/hermes_cli/hooks.py` `_DEFAULT_PAYLOADS` | role-match |

---

## Pattern Assignments

### `services/agent-runtime/atlas_audit/__init__.py` (plugin, event-driven)

**Analog:** `_EXTERNAL_REPOS/hermes-agent/plugins/observability/langfuse/__init__.py`

**Imports pattern** (lines 23-34):
```python
from __future__ import annotations

import json
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)
```

**Module-level state pattern** (lines 55-57):
```python
_STATE_LOCK = threading.Lock()
_TRACE_STATE: Dict[str, TraceState] = {}
_LANGFUSE_CLIENT = None
```
ATLAS equivalent — replace with:
```python
_STATE_LOCK = threading.Lock()
_CURRENT_RUN: dict[str, str] = {}   # session_id -> run_id mapping
```

**register() entry point** (lines 995-1004):
```python
def register(ctx) -> None:
    # Register for both hook name variants so the plugin works across
    # Hermes versions.  pre_api_request / post_api_request fire per API
    # call (preferred); pre_llm_call / post_llm_call fire once per turn.
    ctx.register_hook("pre_api_request", on_pre_llm_request)
    ctx.register_hook("post_api_request", on_post_llm_call)
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("post_llm_call", on_post_llm_call)
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)
```
ATLAS will add `subagent_stop` and `post_approval_response` hooks to this list.

**Hook callback signature — post_tool_call** (lines 947-948):
```python
def on_post_tool_call(*, tool_name: str = "", args: Any = None, result: Any = None,
                      task_id: str = "", session_id: str = "", tool_call_id: str = "", **_: Any) -> None:
```
Note: ATLAS must also accept `duration_ms: int = 0` (present in `_DEFAULT_PAYLOADS`, line 127).

**Hook callback signature — post_api_request / on_post_llm_call** (lines 801-808):
```python
def on_post_llm_call(*, task_id: str = "", session_id: str = "", provider: str = "", base_url: str = "",
                     api_mode: str = "", model: str = "", api_call_count: int = 0,
                     assistant_message: Any = None, response: Any = None,
                     api_duration: float = 0.0, finish_reason: str = "",
                     usage: Any = None, assistant_content_chars: int = 0,
                     assistant_tool_call_count: int = 0, assistant_response: Any = None,
                     **_: Any) -> None:
```
ATLAS uses `api_duration` (float, seconds) — convert to `duration_ms = int(api_duration * 1000)`.

**Fail-open error pattern** (lines 636-637):
```python
    except Exception as exc:  # pragma: no cover - fail-open
        _debug(f"end observation failed: {exc}")
```
ATLAS equivalent — every hook callback wraps its body in try/except, logs via `logger.warning`, and returns without re-raising. Hermes already catches exceptions from callbacks (verified: `hermes_cli/plugins.py:1557-1568`), but defense in depth is appropriate.

**Hook state lookup pattern** (lines 952-965) — for session_id-keyed state:
```python
    task_key = _trace_key(task_id, session_id)
    with _STATE_LOCK:
        state = _TRACE_STATE.get(task_key)
        if state is None:
            return
```
ATLAS uses `_CURRENT_RUN.get(session_id)` to resolve `run_id` at callback time.

---

### `services/agent-runtime/atlas_audit/plugin.yaml` (config)

**Analog:** `_EXTERNAL_REPOS/hermes-agent/plugins/observability/langfuse/plugin.yaml` (lines 1-15):
```yaml
name: langfuse
version: "1.0.0"
description: "Optional Langfuse observability for Hermes — traces conversations, LLM calls, and tool usage. Opt-in via `hermes plugins enable observability/langfuse` (or check the box in `hermes plugins`)."
author: NousResearch
requires_env:
  - HERMES_LANGFUSE_PUBLIC_KEY
  - HERMES_LANGFUSE_SECRET_KEY
hooks:
  - pre_api_request
  - post_api_request
  - pre_llm_call
  - post_llm_call
  - pre_tool_call
  - post_tool_call
```

ATLAS version — omit `requires_env` (no credentials needed), set hooks to exactly the set registered in `register()`:
```yaml
name: atlas_audit
version: "0.1.0"
description: "ATLAS structured audit event bus — persists every Hermes action as an AuditEvent row in SQLite."
author: L2-ootm
hooks:
  - post_api_request
  - post_llm_call
  - post_tool_call
  - subagent_stop
  - post_approval_response
```
**Critical:** `hooks:` list must stay in sync with every `ctx.register_hook()` call in `register()`. Mismatch causes Hermes to log a warning and may skip hook loading.

---

### `services/agent-runtime/atlas_runtime/audit_service.py` (service, CRUD + file-I/O)

**Analog:** `packages/atlas-core/atlas_core/schemas/core.py` for model usage; RESEARCH.md Pattern 3 for transactional write; Pattern 4 for JSONL export. No exact service file analog exists in the codebase yet — this is the first service layer.

**Imports pattern** — derive from `schemas/core.py` (lines 10-17) + stdlib:
```python
from __future__ import annotations

import io
import json
import logging
import sqlite3
import threading
from typing import Any, Optional

from atlas_core.schemas.core import AuditEvent, ToolCall, SECRET_PATTERNS

logger = logging.getLogger(__name__)
```

**Pydantic model construction pattern** (schemas/core.py lines 80-115 — AuditEvent):
```python
# AuditEvent fields (all optional except run_id and event_type):
event = AuditEvent(
    run_id=run_id,           # str, required
    event_type=event_type,   # Literal["llm_call","tool_call","subagent_run","approval","artifact","wiki_update","memory_change","failure"]
    task_id=task_id,         # Optional[str]
    session_id=session_id,   # Optional[str]
    tool_call_id=tool_call_id,  # Optional[str]
    tool_name=tool_name,     # Optional[str]
    data=data_str,           # str — JSON string, NOT dict (D-013)
    duration_ms=duration_ms, # Optional[int]
)
# model_dump() returns JSON-safe dict (datetime serialized to ISO 8601 by field_serializer)
row = event.model_dump()
```

**ToolCall field alignment** (schemas/core.py lines 118-147):
```python
tc = ToolCall(
    audit_event_id=event.id,
    run_id=run_id,
    tool_name=tool_name,
    args=args_str,         # str — JSON string (D-013), redacted
    result=result_str,     # Optional[str] — JSON string, redacted
    duration_ms=duration_ms,
)
```

**Secret redaction pattern** (schemas/core.py lines 25-29 — SECRET_PATTERNS):
```python
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(token|api[_-]?key|secret|password)=([^\s&]+)"),          # URL querystring
    re.compile(r'(?i)"(token|api[_-]?key|secret|password)"\s*:\s*"([^"]+)"'),    # JSON key-value (HB-04-01)
    re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._~+/=-]+)"),                       # Bearer token
)
```
Apply as:
```python
def _redact(text: str) -> str:
    for pat in SECRET_PATTERNS:
        text = pat.sub(lambda m: m.group(0).replace(m.group(2), "[REDACTED]"), text)
    return text
```

**Transactional write pattern** (RESEARCH.md Pattern 3 — no existing analog, use stdlib sqlite3):
```python
# conn.execute uses positional named parameters from model_dump() dict
# "with conn:" = sqlite3 context manager: COMMIT on success, ROLLBACK on exception
with lock:
    with conn:
        conn.execute(
            "INSERT INTO audit_events VALUES "
            "(:id,:run_id,:task_id,:session_id,:tool_call_id,"
            ":event_type,:tool_name,:timestamp,:duration_ms,:data,:policy_result)",
            row,
        )
        if tc is not None:
            conn.execute(
                "INSERT INTO tool_calls VALUES "
                "(:id,:audit_event_id,:run_id,:tool_name,:args,:result,"
                ":exit_code,:stdout,:stderr,:duration_ms,:policy_allowed,"
                ":requires_approval,:timestamp)",
                tc.model_dump(),
            )
```
Column order must match `infra/migrations/0001_core.sql` exactly (verified lines 26-37 and 39-53).

**INSERT column order from DDL** (`infra/migrations/0001_core.sql` lines 26-37):
```sql
-- audit_events: id, run_id, task_id, session_id, tool_call_id, event_type,
--               tool_name, timestamp, duration_ms, data, policy_result
-- tool_calls:   id, audit_event_id, run_id, tool_name, args, result,
--               exit_code, stdout, stderr, duration_ms, policy_allowed,
--               requires_approval, timestamp
```

**JSONL export pattern** (RESEARCH.md Pattern 4):
```python
def export_jsonl(conn: sqlite3.Connection, run_id: str,
                 dest: io.TextIOBase | None = None) -> str:
    cursor = conn.execute(
        "SELECT * FROM audit_events WHERE run_id=? ORDER BY timestamp ASC",
        (run_id,)
    )
    cols = [d[0] for d in cursor.description]
    lines = []
    for row in cursor:
        d = dict(zip(cols, row))
        event = AuditEvent(**d)         # re-validate on read
        line = event.model_dump_json()  # Pydantic v2 serializes datetime → ISO 8601
        lines.append(line)
        if dest is not None:
            dest.write(line + "\n")
    return "\n".join(lines)
```

**model_dump_json() behavior** — `field_serializer("timestamp")` on `AuditEvent` (schemas/core.py lines 113-115) ensures datetime is serialized to ISO 8601 string in both `model_dump()` and `model_dump_json()`. No custom serializer needed in the service.

---

### `services/agent-runtime/tests/conftest.py` (test config)

**Analog:** `packages/atlas-core/tests/conftest.py` (lines 1-42) — copy this pattern exactly, adjusting MIGRATION_PATH depth.

**db fixture pattern** (lines 25-42):
```python
import pathlib
import sqlite3
import pytest

MIGRATION_PATH = (
    pathlib.Path(__file__).parent.parent.parent   # repo root from services/agent-runtime/tests/
    / "infra"
    / "migrations"
    / "0001_core.sql"
)

@pytest.fixture(name="db")
def db_fixture() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    if MIGRATION_PATH.exists():
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        conn.executescript(sql)
    yield conn
    conn.close()
```
**Path depth adjustment:** `packages/atlas-core/tests/conftest.py` uses 4 `.parent` hops. From `services/agent-runtime/tests/conftest.py`, it is 3 hops to repo root (`tests/ -> agent-runtime/ -> services/ -> root`).

**Additional fixtures to add** (no analog — new):
```python
import uuid

@pytest.fixture(name="run_id")
def run_id_fixture() -> str:
    """A stable run_id for test isolation."""
    return str(uuid.uuid4())

@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    return threading.Lock()
```

---

### `services/agent-runtime/tests/test_audit_service.py` (test, CRUD)

**Analog:** `packages/atlas-core/tests/conftest.py` for db fixture usage; RESEARCH.md Pattern 6 for test structure.

**Test structure pattern** — use `db`, `run_id`, `lock` fixtures; call service functions directly:
```python
from atlas_runtime.audit_service import emit, get_events_for_run, export_jsonl

def test_emit_tool_call(db, run_id, lock):
    event = emit(db, lock, run_id=run_id, event_type="tool_call",
                 task_id="task-123", session_id="sess-abc",
                 tool_call_id="tc-001", tool_name="terminal",
                 data={"cmd": "ls"}, duration_ms=42,
                 tool_call_kwargs={"tool_name": "terminal",
                                   "args": {"command": "ls"},
                                   "result": '{"output": "file.txt"}'})
    rows = db.execute("SELECT * FROM audit_events WHERE run_id=?", (run_id,)).fetchall()
    assert len(rows) == 1
    tc_rows = db.execute("SELECT * FROM tool_calls WHERE run_id=?", (run_id,)).fetchall()
    assert len(tc_rows) == 1
```

**Invalid enum guard test** (RESEARCH.md — HB-04-02):
```python
from pydantic import ValidationError
import pytest

def test_emit_invalid_event_type_raises(db, run_id, lock):
    with pytest.raises(ValidationError):
        emit(db, lock, run_id=run_id, event_type="not_a_real_type")
    rows = db.execute("SELECT * FROM audit_events WHERE run_id=?", (run_id,)).fetchall()
    assert len(rows) == 0   # no orphaned row
```

**Redaction test** (RESEARCH.md Code Examples — verified by execution):
```python
def test_emit_redacts_secret_in_data(db, run_id, lock):
    event = emit(db, lock, run_id=run_id, event_type="llm_call",
                 data={"token": "sk-abc123", "normal_key": "value"})
    row = db.execute("SELECT data FROM audit_events WHERE id=?", (event.id,)).fetchone()
    assert "sk-abc123" not in row[0]
    assert "[REDACTED]" in row[0]
```

---

### `services/agent-runtime/tests/test_atlas_audit_plugin.py` (test, event-driven)

**Analog:** `_EXTERNAL_REPOS/hermes-agent/hermes_cli/hooks.py` `_DEFAULT_PAYLOADS` (lines 112-185) — these are the exact kwargs Hermes passes; use them verbatim as test inputs.

**Hook callback test pattern** (RESEARCH.md Pattern 6):
```python
from atlas_audit import on_post_tool_call, on_post_api_request, on_subagent_stop

# Inject run_id into plugin state before calling hook:
# atlas_audit._CURRENT_RUN["test-session"] = run_id

def test_post_tool_call_emits_audit_and_tool_call_rows(db, run_id):
    # payload matches _DEFAULT_PAYLOADS["post_tool_call"] exactly
    on_post_tool_call(
        tool_name="terminal",
        args={"command": "echo hello"},
        session_id="test-session",
        task_id="test-task",
        tool_call_id="test-call",
        result='{"output": "hello"}',
        duration_ms=42,
    )
    audit_rows = db.execute(
        "SELECT * FROM audit_events WHERE event_type='tool_call'"
    ).fetchall()
    assert len(audit_rows) == 1
```

**Synthetic payloads for post_api_request** (hooks.py lines 161-177):
```python
_POST_API_REQUEST_PAYLOAD = {
    "session_id": "test-session",
    "task_id": "test-task",
    "model": "claude-sonnet-4-6",
    "provider": "anthropic",
    "api_call_count": 1,
    "api_duration": 1.234,        # seconds — plugin converts to duration_ms=1234
    "finish_reason": "stop",
    "usage": {"input_tokens": 2048, "output_tokens": 512},
    "assistant_content_chars": 1200,
    "assistant_tool_call_count": 0,
}
```

**Synthetic payload for subagent_stop** (hooks.py lines 178-184):
```python
_SUBAGENT_STOP_PAYLOAD = {
    "parent_session_id": "parent-sess",
    "child_role": None,
    "child_summary": "Synthetic summary for hooks test",
    "child_status": "completed",
    "duration_ms": 1234,
}
```

---

## Shared Patterns

### Pydantic v2 Model Construction (HB-04-02 guard)
**Source:** `packages/atlas-core/atlas_core/schemas/core.py` lines 80-115
**Apply to:** `audit_service.py` — every write path

Always construct `AuditEvent(**kwargs)` before any INSERT. `Literal[...]` on `event_type` (line 95-104) causes `ValidationError` on invalid values. The `model_dump()` dict (line 88 `ConfigDict(frozen=True)`) is JSON-safe — `datetime` serialized to ISO 8601 via `field_serializer`.

```python
# AuditEvent.event_type valid values (core.py lines 95-104):
Literal[
    "llm_call", "tool_call", "subagent_run", "approval",
    "artifact", "wiki_update", "memory_change", "failure",
]
```

### Secret Redaction (HB-04-01 — RESOLVED)
**Source:** `packages/atlas-core/atlas_core/schemas/core.py` lines 25-29
**Apply to:** `audit_service.emit()` — applied to `data`, `args`, `result` before model construction

All three patterns are present and verified: URL querystring, JSON key-value, Bearer token. Apply via group(2) replacement to preserve JSON structure.

### SQLite WAL + FK Pattern
**Source:** `packages/atlas-core/tests/conftest.py` lines 32-34; `infra/migrations/0001_core.sql` line 1-2
**Apply to:** `db.py` (connection management) and `tests/conftest.py`

```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys = ON")
```
Production connection must also pass `check_same_thread=False` when used across threads:
```python
conn = sqlite3.connect(db_path, check_same_thread=False)
```
Pair with `threading.Lock` — never share connection across threads without the lock.

### Transactional Atomic Write
**Source:** stdlib `sqlite3` — `with conn:` context manager
**Apply to:** `audit_service.emit()`

`with conn:` commits on clean exit, rolls back on exception. No manual `BEGIN`/`COMMIT`/`ROLLBACK` needed. All writes for one `emit()` call (AuditEvent + optional ToolCall) go in a single `with conn:` block.

### Fail-Open Hook Callbacks
**Source:** `_EXTERNAL_REPOS/hermes-agent/plugins/observability/langfuse/__init__.py` lines 636-637
**Apply to:** All hook callbacks in `atlas_audit/__init__.py`

```python
def on_post_tool_call(*, tool_name: str = "", ..., **_: Any) -> None:
    try:
        # ... emit logic ...
    except Exception as exc:
        logger.warning("atlas_audit: on_post_tool_call failed: %s", exc)
        return   # never re-raise — Hermes wraps callbacks but ATLAS adds defense in depth
```

### Forward-Compat Hook Signature
**Source:** `_EXTERNAL_REPOS/hermes-agent/plugins/observability/langfuse/__init__.py` lines 947-948
**Apply to:** All hook callbacks in `atlas_audit/__init__.py`

Every callback must accept `**_: Any` to absorb unknown kwargs added by future Hermes versions:
```python
def on_post_tool_call(*, tool_name: str = "", args: Any = None, result: Any = None,
                      task_id: str = "", session_id: str = "", tool_call_id: str = "",
                      duration_ms: int = 0, **_: Any) -> None:
```

### D-013: data Fields Are JSON Strings
**Source:** `packages/atlas-core/atlas_core/schemas/core.py` line 110 (`data: str = "{}"`)
**Apply to:** `audit_service.emit()`, `atlas_audit/__init__.py` (all hook callbacks)

Never pass a `dict` to `AuditEvent.data` or `ToolCall.args`/`ToolCall.result`. Always `json.dumps()` first, then `_redact()`, then pass the string:
```python
data_str = _redact(json.dumps(data or {}))
args_str = _redact(json.dumps(args) if isinstance(args, dict) else (args or "{}"))
result_str = _redact(json.dumps(result) if isinstance(result, dict) else (result or "null"))
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `services/agent-runtime/atlas_runtime/db.py` | utility | — | No connection-management module exists yet in this project. Use `sqlite3.connect` directly in `audit_service.py` and accept `conn` + `lock` as parameters (dependency injection). No separate db.py needed for this phase. |
| `services/agent-runtime/pyproject.toml` | config | — | `packages/atlas-core/pyproject.toml` is the closest analog but was not loaded (not required). Follow same pattern: `[project]` with `dependencies = ["atlas-core @ ../../packages/atlas-core"]`, `[tool.pytest.ini_options]` pointing at `tests/`. |

---

## Metadata

**Analog search scope:** `packages/atlas-core/`, `_EXTERNAL_REPOS/hermes-agent/plugins/observability/langfuse/`, `_EXTERNAL_REPOS/hermes-agent/hermes_cli/hooks.py`, `infra/migrations/`, `services/agent-runtime/` (empty)
**Files scanned:** 6 source files read in full
**Pattern extraction date:** 2026-06-07

### Key Constraints for Planner

1. **HB-04-01 resolved:** `SECRET_PATTERNS[1]` in `core.py` (line 27) already covers JSON key-value. No code change needed; planner should verify the import path is correct.
2. **HB-04-02:** Every `conn.execute("INSERT INTO audit_events ...")` call must be preceded by `AuditEvent(**kwargs)` construction. No exceptions.
3. **Column order in INSERT:** Named parameter style (`:field_name`) is safe against column reordering, but column count must match DDL. Verified from `0001_core.sql`: audit_events has 11 columns, tool_calls has 13.
4. **task_id not turn_id:** DIV-004 — `AuditEvent.task_id` stores the Hermes `task_id` kwarg value. No `turn_id` field exists anywhere.
5. **Plugin install path:** `~/.hermes/plugins/atlas_audit/` (user path, no env var required). Symlink from repo during development.
6. **plugin.yaml hooks list must match register() exactly:** Mismatch causes Hermes warning and potential hook skip.
