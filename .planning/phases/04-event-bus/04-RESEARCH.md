# Phase 4: ATLAS Event Bus & Audit Core — Research

**Researched:** 2026-06-07
**Domain:** Python async event bus, Hermes plugin hooks, SQLite/WAL audit writes, secret redaction, JSONL export
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-001** (locked): Hermes used directly via plugin/hook — event bus must NOT edit cli.py or run_agent.py.
- **D-002** (locked): Audit-first runtime — every LLM call, tool call, subagent run, approval, external action, and artifact emits a structured AuditEvent row.
- **D-003** (locked): SQLite/WAL — all audit writes must use WAL mode for concurrency safety.
- **D-011** (locked): Canonical repo layout — event bus lives in `services/agent-runtime/`.
- **D-012** (locked): Pydantic v2 is schema source of truth — all writes go through model layer, no raw SQL with unchecked literals.

### Claude's Discretion
- Internal service layer design for `audit_service.py` (emit, get_events_for_run, export_jsonl).
- Directory sub-structure inside `services/agent-runtime/`.
- Test fixture design for mock Hermes runs.
- SQLite connection management strategy (connection-per-call vs. shared connection + queue).

### Deferred Ideas (OUT OF SCOPE)
- Mission state machine (Phase 5).
- Wiki pipeline (Phase 6).
- Full REST API endpoints (Phase 7 — AUDIT-01 here means internal service layer only, not HTTP).
- CRM/Pulse event types (v2.0).
- Consumer fanout, webhooks.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RUNTIME-03 | Every LLM call, tool call, subagent run, approval, external action, and artifact emits a structured AuditEvent row | Hermes plugin hooks cover all these events; post_tool_call covers tool calls + artifacts (by tool name filter); post_api_request covers LLM calls; subagent_stop covers subagent runs; pre/post_approval_request covers approvals |
| AUDIT-01 | User can retrieve the full ordered audit trail for any Run from the API | `get_events_for_run(run_id)` service method queries `audit_events` table ordered by `timestamp`; no HTTP endpoint in this phase |
| AUDIT-02 | Audit trail is exportable as JSONL | `export_jsonl(run_id, dest)` service method streams `model.model_dump_json()` lines to file or buffer |
</phase_requirements>

---

## Summary

Phase 4 builds the structured audit event bus by attaching an ATLAS plugin to Hermes via the existing plugin/hook system — no edits to Hermes core files are required. The Phase 1 audit delivered an authoritative YES verdict: `hermes_cli/plugins.py` defines 17 named hooks and a `PluginContext` facade; the Langfuse observability plugin in `plugins/observability/langfuse/` is a complete reference implementation that registers `pre_tool_call`, `post_tool_call`, `pre_llm_call`, `post_llm_call`, `pre_api_request`, and `post_api_request` hooks — exactly the set ATLAS needs. The `post_tool_call` hook delivers `(tool_name, args, result, task_id, session_id, tool_call_id, duration_ms)` kwargs; `post_api_request` delivers `(task_id, session_id, model, provider, api_call_count, usage, finish_reason, duration_ms, ...)`. Artifact capture requires filtering `post_tool_call.tool_name` against known write-tools (Write, Edit, MultiEdit, etc.) per DIV-002.

The Phase 2 output is ready: `atlas_core.schemas.core` exports frozen Pydantic v2 `AuditEvent`, `ToolCall`, and `SECRET_PATTERNS`. Crucially, `SECRET_PATTERNS` already contains all three patterns including the JSON key-value pattern `(?i)"(token|api[_-]?key|secret|password)"\s*:\s*"([^"]+)"` — **HB-04-01 is already resolved in core.py**. HB-04-02 (raw SQL bypass risk) is addressed architecturally: all writes route through `model.model_dump()` then parameterized INSERT.

The service layer (`audit_service.py`) needs three public functions: `emit()` (validate via Pydantic, redact, write transactionally), `get_events_for_run()` (SELECT ordered by timestamp), and `export_jsonl()` (stream `model_dump_json()` lines). SQLite threadsafety is 3 (serialized) on this machine (Python 3.11, SQLite 3.50.4), so a `threading.Lock` around the connection is sufficient; a dedicated writer thread with `queue.Queue` is optional but cleaner for hook callbacks that fire in arbitrary threads.

**Primary recommendation:** Build the ATLAS audit plugin as a Hermes user-path plugin at `~/.hermes/plugins/atlas_audit/` (no env var required) with a `register(ctx)` entry point. The service layer and plugin live in `services/agent-runtime/`. Tests mock Hermes hooks directly — no live Hermes process needed.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Hook callbacks (pre/post_tool_call, post_api_request, etc.) | Hermes Plugin Layer | — | Hermes fires hooks; ATLAS plugin registers callbacks via `ctx.register_hook()` |
| AuditEvent + ToolCall persistence | `audit_service.py` (Python service) | SQLite/WAL | Service owns the write boundary; Pydantic enforces schema before SQLite INSERT |
| Secret redaction | `audit_service.py` (before emit) | `atlas_core.schemas.core.SECRET_PATTERNS` | Redaction applied to `data`, `args`, `result` fields before model construction |
| Event retrieval (ordered trail) | `audit_service.py` (get_events_for_run) | SQLite query | SELECT ordered by timestamp; no HTTP layer in this phase |
| JSONL export | `audit_service.py` (export_jsonl) | File I/O | Streams `AuditEvent.model_dump_json()` per line |
| Artifact detection | Plugin callback (post_tool_call filter) | `audit_service.py` (emit artifact event) | Filter on `tool_name` in known write-tool set; delegate write to service |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pydantic` | 2.13.4 (installed) | Model validation, serialization, secret guard | D-012 locked; already installed and tested in Phase 2 |
| `sqlite3` | stdlib (SQLite 3.50.4) | Audit persistence | D-003 locked; no extra deps |
| `threading` | stdlib | Lock for connection safety | threadsafety=3 — single Lock sufficient |
| `queue` | stdlib | Writer queue (optional but recommended) | Decouples hook callbacks from DB writes |
| `json` | stdlib | Serialize AuditEvent.data, ToolCall.args/result | D-013: data fields are JSON strings, not dicts |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 9.0.2 (installed) | Test framework | Already established in Phase 2 |
| `re` | stdlib | Secret pattern matching | SECRET_PATTERNS already compiled in atlas_core |
| `pathlib` | stdlib | DB file path resolution | Consistent with Phase 2 pattern |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `sqlite3` | `aiosqlite` | aiosqlite adds async, but Hermes hooks are synchronous callbacks — stdlib + threading lock is simpler and sufficient |
| threading.Lock | asyncio.Lock | N/A — hook callbacks are not async; no async runtime in scope for this phase |
| queue.Queue writer | Direct write per hook | Direct write is simpler but ties hook callback latency to DB write latency; queue decouples them |

**Installation:** No new packages required. All dependencies are stdlib or already installed (`pydantic`).

---

## Package Legitimacy Audit

No external packages are added in this phase. All dependencies are Python stdlib (`sqlite3`, `threading`, `queue`, `json`, `re`, `pathlib`) or `pydantic` which was already installed and verified in Phase 2.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Hermes runtime (live process)
  │
  ├── invoke_hook("post_tool_call", tool_name=..., args=..., result=...,
  │               task_id=..., session_id=..., tool_call_id=..., duration_ms=...)
  │
  ├── invoke_hook("post_api_request", task_id=..., session_id=..., model=...,
  │               usage=..., finish_reason=..., api_duration=...)
  │
  ├── invoke_hook("subagent_stop", parent_session_id=..., child_role=...,
  │               child_status=..., duration_ms=...)
  │
  └── invoke_hook("pre/post_approval_request", ...)

        ↓ (registered via ctx.register_hook in atlas_audit plugin)

ATLAS Audit Plugin  (~/.hermes/plugins/atlas_audit/__init__.py)
  ├── on_post_tool_call()     → classifies: tool_call or artifact
  ├── on_post_api_request()   → event_type=llm_call
  ├── on_subagent_stop()      → event_type=subagent_run
  └── on_post_approval()      → event_type=approval

        ↓ (calls)

audit_service.emit(run_id, event_type, ...)
  ├── Redact: apply SECRET_PATTERNS to data/args/result strings
  ├── Construct: AuditEvent(**fields) — Pydantic validates, rejects bad enums
  ├── Optionally construct: ToolCall(**fields) linked to AuditEvent.id
  └── Write transactionally:
        BEGIN / INSERT audit_events / INSERT tool_calls (if applicable) / COMMIT
        (on failure: ROLLBACK — no orphaned rows)

        ↓ (persisted to)

SQLite (WAL mode, FK ON)
  ├── audit_events table
  └── tool_calls table

        ↑ (read by)

audit_service.get_events_for_run(run_id)
  └── SELECT * FROM audit_events WHERE run_id=? ORDER BY timestamp ASC

audit_service.export_jsonl(run_id, dest)
  └── Streams AuditEvent.model_dump_json() + "\n" per row
```

### Recommended Project Structure

```
services/agent-runtime/
├── atlas_audit/               # Hermes plugin package (symlinked or installed at ~/.hermes/plugins/)
│   ├── __init__.py            # register(ctx) entry point + hook callbacks
│   └── plugin.yaml            # Plugin manifest (name, version, hooks list)
├── atlas_runtime/
│   └── audit_service.py       # emit(), get_events_for_run(), export_jsonl()
├── tests/
│   ├── conftest.py            # db fixture (mirrors Phase 2 pattern), mock_run fixture
│   ├── test_audit_service.py  # Unit tests for emit, get_events, export_jsonl
│   └── test_atlas_audit_plugin.py  # Tests for hook callbacks (no live Hermes required)
└── pyproject.toml             # Package config (depends on atlas-core)
```

**Note:** The plugin is installed at `~/.hermes/plugins/atlas_audit/` (user path, always loaded, no env var). During development, a symlink from `~/.hermes/plugins/atlas_audit` to `services/agent-runtime/atlas_audit/` is the simplest setup.

### Pattern 1: Hermes Plugin Registration

**What:** The `register(ctx)` function is the sole entry point Hermes calls when loading the plugin. Hooks registered here fire on every matching event.

**When to use:** Single entry point; all hook registrations happen here.

```python
# Source: _EXTERNAL_REPOS/hermes-agent/plugins/observability/langfuse/__init__.py:995-1004
# and _EXTERNAL_REPOS/hermes-agent/hermes_cli/plugins.py:936-950 (register_hook implementation)

def register(ctx) -> None:
    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("post_api_request", on_post_api_request)   # llm_call events
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)        # tool_call + artifact events
    ctx.register_hook("subagent_stop", on_subagent_stop)          # subagent_run events
    ctx.register_hook("post_approval_response", on_post_approval) # approval events
```

**Key insight:** `invoke_hook` wraps every callback in try/except — a misbehaving ATLAS plugin will log a warning but will never crash the Hermes agent loop. [VERIFIED: _EXTERNAL_REPOS/hermes-agent/hermes_cli/plugins.py:1557-1568]

### Pattern 2: Hook Callback Signatures (exact kwargs from Hermes source)

**post_tool_call kwargs** (from `model_tools.py:852-860` and `hooks.py:120-128`):
```python
# Source: _EXTERNAL_REPOS/hermes-agent/hermes_cli/hooks.py:120-128 (authoritative synthetic payloads)
def on_post_tool_call(
    *,
    tool_name: str = "",
    args: Any = None,           # dict or None
    result: Any = None,         # str or dict
    task_id: str = "",          # use as AuditEvent.task_id (DIV-004)
    session_id: str = "",
    tool_call_id: str = "",
    duration_ms: int = 0,
    **_: Any,                   # forward-compat: ignore unknown kwargs
) -> None:
    ...
```

**post_api_request kwargs** (from `hooks.py:161-177`):
```python
def on_post_api_request(
    *,
    task_id: str = "",
    session_id: str = "",
    model: str = "",
    provider: str = "",
    api_call_count: int = 0,
    api_duration: float = 0.0,  # seconds — convert to duration_ms
    finish_reason: str = "",
    usage: dict = None,         # {"input_tokens": N, "output_tokens": N}
    **_: Any,
) -> None:
    ...
```

**subagent_stop kwargs** (from `hooks.py:178-184`):
```python
def on_subagent_stop(
    *,
    parent_session_id: str = "",
    child_role: Any = None,
    child_summary: str = "",
    child_status: str = "",
    duration_ms: int = 0,
    **_: Any,
) -> None:
    ...
```

**IMPORTANT (DIV-004):** Hermes fires `task_id`, not `turn_id`. ATLAS `AuditEvent.task_id` maps to the Hermes `task_id` kwarg value.

### Pattern 3: Transactional Audit Write

**What:** Emit one AuditEvent row; if it is a tool call, also emit one ToolCall row in the same transaction. Fail atomically.

```python
# Source: atlas_core/schemas/core.py (Phase 2 output) + stdlib sqlite3
import json
import re
import sqlite3
from atlas_core.schemas.core import AuditEvent, ToolCall, SECRET_PATTERNS

def _redact(text: str) -> str:
    """Apply all SECRET_PATTERNS to a JSON string before persistence."""
    for pat in SECRET_PATTERNS:
        text = pat.sub(lambda m: m.group(0).replace(m.group(2), "[REDACTED]"), text)
    return text

def emit(conn: sqlite3.Connection, lock: threading.Lock, *, run_id: str, event_type: str,
         task_id: str | None = None, session_id: str | None = None,
         tool_call_id: str | None = None, tool_name: str | None = None,
         data: dict | None = None, duration_ms: int | None = None,
         tool_call_kwargs: dict | None = None) -> AuditEvent:
    data_str = _redact(json.dumps(data or {}))
    event = AuditEvent(
        run_id=run_id,
        event_type=event_type,
        task_id=task_id,
        session_id=session_id,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        data=data_str,
        duration_ms=duration_ms,
    )
    row = event.model_dump()

    tc: ToolCall | None = None
    if tool_call_kwargs is not None:
        tc_kwargs = dict(tool_call_kwargs)
        for field in ("args", "result"):
            if isinstance(tc_kwargs.get(field), str):
                tc_kwargs[field] = _redact(tc_kwargs[field])
        tc = ToolCall(audit_event_id=event.id, run_id=run_id, **tc_kwargs)

    with lock:
        with conn:  # context manager: BEGIN / COMMIT or ROLLBACK
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
    return event
```

**Why `with conn`:** Python's `sqlite3.Connection` context manager commits on success and rolls back on exception — no orphaned rows on partial failure. [ASSUMED — stdlib sqlite3 context manager behavior, but verified against Python 3.11 docs pattern]

### Pattern 4: JSONL Export

```python
# Source: design from AuditEvent.model_dump_json() (Pydantic v2 stdlib)
import io

def export_jsonl(conn: sqlite3.Connection, run_id: str, dest: io.TextIOBase | None = None) -> str:
    """Export ordered audit trail as JSONL. Returns the JSONL string if dest is None."""
    cursor = conn.execute(
        "SELECT * FROM audit_events WHERE run_id=? ORDER BY timestamp ASC",
        (run_id,)
    )
    cols = [d[0] for d in cursor.description]
    lines = []
    for row in cursor:
        d = dict(zip(cols, row))
        event = AuditEvent(**d)
        line = event.model_dump_json()
        lines.append(line)
        if dest is not None:
            dest.write(line + "\n")
    return "\n".join(lines)
```

### Pattern 5: Artifact Detection by Tool Name

Per DIV-002, ATLAS identifies artifact-creation events by filtering `post_tool_call.tool_name`:

```python
# Source: docs/decisions/DIV-002-artifact-capture.md (Phase 1 output)
_ARTIFACT_TOOLS = frozenset({
    "write_file", "edit_file", "multi_edit",  # canonical Hermes names
    "Write", "Edit", "MultiEdit",             # alternative casing observed in Hermes
})

def _is_artifact_tool(tool_name: str) -> bool:
    return tool_name in _ARTIFACT_TOOLS
```

**Note:** The exact set of write-tool names must be validated against the live Hermes tool registry at execution time. The canonical list is a starting point.

### Pattern 6: Mock Hermes Hook Testing (no live Hermes process)

```python
# Pattern for testing hook callbacks without spawning Hermes
# Directly call the hook function with the same kwargs Hermes would pass

from atlas_audit import on_post_tool_call, on_post_api_request

def test_tool_call_emits_audit_row(db, run_id):
    # Inject run_id into plugin module state (or pass via closure)
    on_post_tool_call(
        tool_name="terminal",
        args={"command": "ls"},
        result='{"output": "file.txt"}',
        task_id="task-123",
        session_id="sess-abc",
        tool_call_id="tc-001",
        duration_ms=42,
    )
    rows = db.execute(
        "SELECT * FROM audit_events WHERE event_type='tool_call'"
    ).fetchall()
    assert len(rows) == 1
```

### Anti-Patterns to Avoid

- **Raw SQL with string interpolation for enum values:** Bypasses Pydantic validation. Hermes hook may pass an unexpected `event_type`; constructing an `AuditEvent` first lets Pydantic reject it before it reaches SQLite. [VERIFIED: HB-04-02 constraint]
- **Sharing a sqlite3.Connection across threads without a lock:** `sqlite3.threadsafety=3` (serialized) means the module is thread-safe but individual connections are not shared by default. Use `check_same_thread=False` only when paired with an explicit threading.Lock.
- **Catching all exceptions silently in hook callbacks:** Hermes already wraps callbacks in try/except. Log errors; don't swallow them entirely or debugging becomes impossible.
- **Storing `dict` in AuditEvent.data:** The schema requires `data: str` (JSON string). Always call `json.dumps()` before constructing the model. [VERIFIED: atlas_core/schemas/core.py:110]
- **Using `post_llm_call` instead of `post_api_request` for token/model metadata:** `post_api_request` carries `usage`, `model`, `provider`, `finish_reason`; `post_llm_call` carries less. Register both for compatibility but prefer `post_api_request` data when both fire.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema validation before DB write | Custom field checker | Pydantic `AuditEvent(**kwargs)` | Validates enums, field types, required fields; D-012 locked |
| Secret redaction | New regex engine | `SECRET_PATTERNS` from `atlas_core.schemas.core` | Already covers URL querystring, JSON key-value, Bearer token — adding patterns is an atlas_core concern |
| Transactional write rollback | Manual BEGIN/ROLLBACK | `with conn:` context manager | stdlib sqlite3 CM handles commit/rollback correctly |
| JSON serialization of AuditEvent | Custom serializer | `model.model_dump_json()` | Pydantic handles datetime → ISO 8601 via `field_serializer`; D-013 compliant |
| Plugin discovery | Custom loader | Hermes user-path (`~/.hermes/plugins/`) | Already supported; no env var required |

**Key insight:** The Pydantic model layer is the only write-boundary guard for enum integrity (SQLite stores TEXT with no enum constraint). Bypassing it even once allows corrupt `event_type` values to enter the database silently.

---

## Common Pitfalls

### Pitfall 1: HB-04-01 — SECRET_PATTERNS JSON Pattern (ALREADY RESOLVED)

**What goes wrong:** `atlas_core/schemas/core.py` `SECRET_PATTERNS` misses JSON key-value payloads like `{"token": "sk-abc123"}`, allowing raw secrets to persist.
**Why it happens:** Original pattern set only covered URL querystring (`key=value`) and Bearer token formats.
**Current state:** **RESOLVED in Phase 2.** Verified by direct inspection: `SECRET_PATTERNS` in `core.py` already contains pattern[1] = `(?i)"(token|api[_-]?key|secret|password)"\s*:\s*"([^"]+)"`. Redaction test against `{"token": "sk-abc123"}` returns `{"token": "[REDACTED]"}`. No code change needed for HB-04-01.
**Warning signs:** If `SECRET_PATTERNS` is re-exported from a different module, verify the JSON pattern is present there too.

### Pitfall 2: HB-04-02 — Raw SQL Bypasses Pydantic Enum Guard

**What goes wrong:** A raw `INSERT INTO audit_events VALUES (...)` with an unchecked `event_type` literal stores an invalid enum value silently. SQLite TEXT columns have no CHECK constraint on `event_type`.
**Why it happens:** Convenience — skipping model construction feels faster. The bug is only caught when the row is deserialized later (or never caught at all).
**How to avoid:** Always construct `AuditEvent(**kwargs)` before any INSERT. The `Literal[...]` type annotation on `event_type` causes Pydantic to raise `ValidationError` on invalid values.
**Warning signs:** Any code path with `conn.execute("INSERT INTO audit_events ...")` that does not first construct an `AuditEvent` model.

### Pitfall 3: task_id vs turn_id Confusion (DIV-004)

**What goes wrong:** Plans reference `turn_id` as a correlation key; Hermes `post_tool_call` emits `task_id`. No `turn_id` exists in the hook kwargs.
**Why it happens:** Early ATLAS design assumed `turn_id`; Phase 1 audit corrected this via DIV-004.
**How to avoid:** Use `task_id` (not `turn_id`) throughout. `AuditEvent.task_id` maps to Hermes `task_id`. [VERIFIED: HERMES_FOUNDATION_AUDIT.md DIV-004]

### Pitfall 4: Plugin Not Loading (User Path vs. Project Path)

**What goes wrong:** ATLAS plugin placed at `./.hermes/plugins/atlas_audit/` doesn't load without `HERMES_ENABLE_PROJECT_PLUGINS=1` env var.
**Why it happens:** Project plugin path is gated by env var; user plugin path is not.
**How to avoid:** Install at `~/.hermes/plugins/atlas_audit/` (user path, priority 3, always loaded). For development, use a symlink. [VERIFIED: HERMES_FOUNDATION_AUDIT.md — Plugin Discovery Paths table]

### Pitfall 5: plugin.yaml hooks List

**What goes wrong:** Registering a hook in `register(ctx)` but not listing it in `plugin.yaml` `hooks:` causes the plugin manager to log a warning and may skip loading hooks in some Hermes versions.
**How to avoid:** Keep `plugin.yaml` `hooks:` in sync with every `ctx.register_hook()` call in `register()`. [VERIFIED: langfuse/plugin.yaml and __init__.py match exactly]

### Pitfall 6: Artifact Tool Name Set Drift

**What goes wrong:** Hermes tool names for file writes (`Write`, `write_file`, etc.) differ across Hermes versions. Using a hardcoded set misses new tools or matches wrong ones.
**How to avoid:** At plugin load time, probe the Hermes tool registry (if accessible via `ctx`) or load tool names from a configurable set. Document the tool name set used as a versioned assumption.

### Pitfall 7: Connection Thread Safety Without Lock

**What goes wrong:** `sqlite3.connect(..., check_same_thread=False)` without a threading.Lock causes `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread` or silent data corruption under concurrent hook callbacks.
**How to avoid:** Pass `check_same_thread=False` AND acquire a `threading.Lock` before every `conn.execute()`. [VERIFIED: Python 3.11 sqlite3 docs — threadsafety=3 means module-level safety only]

---

## Code Examples

### Verified: Redaction Function Test

```python
# Verified by direct execution against installed atlas_core (Python 3.11)
import json, sys
sys.path.insert(0, 'packages/atlas-core')
from atlas_core.schemas.core import SECRET_PATTERNS

def redact(text: str) -> str:
    for pat in SECRET_PATTERNS:
        text = pat.sub(lambda m: m.group(0).replace(m.group(2), "[REDACTED]"), text)
    return text

payload = json.dumps({"token": "sk-abc123", "normal_key": "value"})
result = redact(payload)
# result == '{"token": "[REDACTED]", "normal_key": "value"}'
```

### Verified: Pydantic AuditEvent Enum Guard

```python
from pydantic import ValidationError
from atlas_core.schemas.core import AuditEvent

try:
    AuditEvent(run_id="r1", event_type="invalid_type")  # raises ValidationError
except ValidationError as e:
    pass  # invalid enum caught before DB write — HB-04-02 satisfied
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| In-process logging to flat files | Structured SQLite audit rows via Pydantic models | Phase 2 locked | Every event queryable, exportable, schema-validated |
| Custom observability middleware | Hermes plugin hook system | Phase 1 audit | No in-core edits required; 17 hooks cover all observable events |
| `turn_id` as correlation key | `task_id` from Hermes kwargs | DIV-004 (Phase 1) | AuditEvent.task_id maps to Hermes task_id directly |
| Separate redaction module | SECRET_PATTERNS in atlas_core.schemas.core | Phase 2 HB-04-01 fix | Single source of truth; applies at emit boundary |

**Deprecated/outdated:**
- `turn_id` field: superseded by `task_id` (DIV-004). The `AuditEvent.task_id` column stores the Hermes `task_id` value.
- Project plugin path (`./.hermes/plugins/`): requires env var; use user path (`~/.hermes/plugins/`) for ATLAS.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `with conn:` (sqlite3 Connection as context manager) commits on success and rolls back on exception — no manual BEGIN/ROLLBACK needed | Pattern 3: Transactional Write | If wrong, partial failures could leave orphaned rows; fix by explicit `conn.commit()` / `conn.rollback()` |
| A2 | Hermes write-tool names include `Write`, `Edit`, `MultiEdit`, `write_file`, `edit_file`, `multi_edit` | Pattern 5: Artifact Detection | If Hermes uses different names, artifact events are missed; fix by probing tool registry at plugin load |
| A3 | `post_api_request` is the preferred hook for `llm_call` events (vs `post_llm_call`) based on langfuse plugin comment | Pattern 2: Hook Callback Signatures | If `post_api_request` doesn't fire in all Hermes configurations, register both hooks as fallback |

---

## Open Questions

1. **Hermes write-tool canonical names**
   - What we know: DIV-002 establishes that artifact detection filters `post_tool_call.tool_name` against known write-tool names.
   - What's unclear: The exact tool name set in the Hermes tool registry at the pinned SHA has not been enumerated.
   - Recommendation: At Wave 1 of planning, scan `_EXTERNAL_REPOS/hermes-agent/tools/` for file-write tool registrations and enumerate names. Commit the authoritative set to the plugin module.

2. **Run ID injection into plugin callbacks**
   - What we know: Hook callbacks receive `session_id` from Hermes; `run_id` is an ATLAS concept that maps to a `Run` row.
   - What's unclear: How does the plugin know which `run_id` to emit against? ATLAS needs a "current run" context at callback time.
   - Recommendation: The plugin holds a module-level `_CURRENT_RUN: dict[str, str]` mapping `session_id → run_id`. `on_session_start` registers the mapping; `on_session_end` removes it. This requires ATLAS to call `start_run()` before invoking Hermes (Phase 5 concern), but the plugin must be designed to handle this from Phase 4.

3. **`post_api_request` presence in all Hermes configurations**
   - What we know: Langfuse plugin registers both `pre_api_request`/`post_api_request` AND `pre_llm_call`/`post_llm_call` for version compatibility.
   - Recommendation: Register both `post_api_request` and `post_llm_call` in the ATLAS plugin; deduplicate by checking if an event for the same `task_id` + `api_call_count` was already emitted.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | All service code | ✓ | 3.11.15 | — |
| pydantic 2.x | Schema validation, model_dump_json | ✓ | 2.13.4 | — |
| SQLite (stdlib) | Audit persistence | ✓ | 3.50.4 | — |
| pytest | Tests | ✓ | 9.0.2 | — |
| Hermes clone at SHA e8b9369a9 | Plugin registration testing | ✓ | 0.14.0 at `_EXTERNAL_REPOS/hermes-agent/` | — |
| `~/.hermes/plugins/` directory | Plugin install path | [ASSUMED] | — | Create at Wave 0 setup |

**Missing dependencies with no fallback:** None — all required tools are available.
**Missing dependencies with fallback:** `~/.hermes/plugins/` may not exist yet; Wave 0 task must `mkdir -p ~/.hermes/plugins/`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `services/agent-runtime/pyproject.toml` (to be created Wave 0) |
| Quick run command | `pytest services/agent-runtime/tests/ -x -q` |
| Full suite command | `pytest packages/atlas-core/tests/ services/agent-runtime/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RUNTIME-03 | post_tool_call hook emits AuditEvent + ToolCall rows | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_emit_tool_call -x` | ❌ Wave 0 |
| RUNTIME-03 | post_api_request hook emits llm_call AuditEvent row | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_emit_llm_call -x` | ❌ Wave 0 |
| RUNTIME-03 | post_tool_call with write-tool name emits artifact AuditEvent | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_emit_artifact -x` | ❌ Wave 0 |
| RUNTIME-03 | Secret patterns redact JSON key-value before persistence | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_redaction -x` | ❌ Wave 0 |
| RUNTIME-03 | Partial failure (invalid event_type) does not persist orphaned row | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_emit_invalid_type -x` | ❌ Wave 0 |
| AUDIT-01 | get_events_for_run returns ordered AuditEvent list | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_get_events_ordered -x` | ❌ Wave 0 |
| AUDIT-02 | export_jsonl produces valid JSONL with all fields | unit | `pytest services/agent-runtime/tests/test_audit_service.py::test_export_jsonl -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest services/agent-runtime/tests/ -x -q`
- **Per wave merge:** `pytest packages/atlas-core/tests/ services/agent-runtime/tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `services/agent-runtime/pyproject.toml` — package scaffold, depends on atlas-core
- [ ] `services/agent-runtime/tests/conftest.py` — `db` fixture (reuse/mirror Phase 2 pattern), `run_id` fixture
- [ ] `services/agent-runtime/tests/test_audit_service.py` — covers RUNTIME-03, AUDIT-01, AUDIT-02
- [ ] `services/agent-runtime/tests/test_atlas_audit_plugin.py` — hook callback integration (mock Hermes invoke_hook)
- [ ] `~/.hermes/plugins/atlas_audit/` directory — plugin install path

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Pydantic v2 model validation on every write (HB-04-02); SECRET_PATTERNS redaction on data fields (HB-04-01) |
| V6 Cryptography | no | — |
| V7 Error Handling / Logging | yes | Hermes wraps hook callbacks in try/except; ATLAS must log errors, not swallow silently |

### Known Threat Patterns for Hermes plugin + SQLite

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret exfiltration via AuditEvent.data | Information Disclosure | SECRET_PATTERNS redaction applied before model construction; all 3 patterns verified in core.py |
| Invalid enum value stored in SQLite | Tampering | Pydantic AuditEvent construction before INSERT — ValidationError raised on invalid event_type |
| Hook callback crashing Hermes runtime | Denial of Service | Hermes try/except wrapper; ATLAS callbacks must not raise (log and return on error) |
| SQL injection via tool_name / args | Tampering | All INSERTs use parameterized queries via `model.model_dump()` dict — no string interpolation |
| Orphaned audit rows on partial transaction failure | Tampering / Data Integrity | `with conn:` context manager ensures atomic commit/rollback per emit() call |

---

## Sources

### Primary (HIGH confidence)
- `_EXTERNAL_REPOS/hermes-agent/hermes_cli/plugins.py` — `VALID_HOOKS`, `PluginContext.register_hook()`, `invoke_hook()`, plugin discovery paths, try/except wrapper
- `_EXTERNAL_REPOS/hermes-agent/plugins/observability/langfuse/__init__.py` — complete reference implementation of `register(ctx)` + all hook callback signatures
- `_EXTERNAL_REPOS/hermes-agent/hermes_cli/hooks.py` — authoritative synthetic hook payloads (exact kwargs Hermes passes to each hook)
- `packages/atlas-core/atlas_core/schemas/core.py` — Phase 2 output; AuditEvent, ToolCall, SECRET_PATTERNS (3 patterns verified by execution)
- `infra/migrations/0001_core.sql` — Phase 2 output; audit_events + tool_calls DDL
- `docs/research/HERMES_FOUNDATION_AUDIT.md` — YES verdict, DIV-001 through DIV-004 resolution
- `docs/decisions/DIV-002-artifact-capture.md`, `DIV-004-turn-id-propagation.md` — plugin-tier decisions

### Secondary (MEDIUM confidence)
- `packages/atlas-core/tests/conftest.py` — db fixture pattern reusable in Phase 4 tests
- `_EXTERNAL_REPOS/hermes-agent/plugins/observability/langfuse/plugin.yaml` — plugin.yaml manifest structure

### Tertiary (LOW confidence / assumed)
- A3: `post_api_request` fires in all Hermes configurations — inferred from langfuse plugin comment but not verified across all Hermes entry points

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies are stdlib or Phase 2 verified pydantic; no new packages
- Architecture: HIGH — hook signatures verified from Hermes source + synthetic payload fixtures; service layer pattern follows established sqlite3 + Pydantic conventions
- Pitfalls: HIGH — HB-04-01 and HB-04-02 from prior phase reviews; DIV-003/DIV-004 from Phase 1 audit; hook loading from Phase 1 discovery paths table

**Research date:** 2026-06-07
**Valid until:** 2026-08-07 (Hermes pinned at SHA e8b9369a9 — stable until pin changes)
