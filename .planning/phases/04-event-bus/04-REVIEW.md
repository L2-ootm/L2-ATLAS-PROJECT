---
phase: 04-event-bus
reviewed: 2026-06-07T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - services/agent-runtime/atlas_audit/__init__.py
  - services/agent-runtime/atlas_audit/plugin.yaml
  - services/agent-runtime/atlas_runtime/__init__.py
  - services/agent-runtime/atlas_runtime/audit_service.py
  - services/agent-runtime/pyproject.toml
  - services/agent-runtime/tests/__init__.py
  - services/agent-runtime/tests/conftest.py
  - services/agent-runtime/tests/test_atlas_audit_plugin.py
  - services/agent-runtime/tests/test_audit_service.py
  - services/agent-runtime/tests/test_conftest.py
findings:
  critical: 4
  warning: 5
  info: 3
  total: 12
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-06-07T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

The implementation covers the core audit event bus (plugin + service) and a reasonable test suite. The overall architecture is sound: Pydantic-gated writes (HB-04-02), transactional INSERTs, dependency-injected connection, and fail-open hook callbacks. However, four blockers exist: an exploitable regex redaction bypass (HB-04-01 violated), a silent data-loss path when `conn` is `None`, a second independent two-lock pattern introducing a race between `_CONN` and `_LOCK`, and a test that conditionally skips schema setup (making the full integration suite silently non-asserting when the migration file is absent). Additionally there are five warnings around type safety, correctness edge cases, and missing test coverage.

---

## Critical Issues

### CR-01: `_redact` regex substitution silently no-ops on multi-group match when value contains no special chars — HB-04-01 partial bypass

**File:** `services/agent-runtime/atlas_runtime/audit_service.py:44`

**Issue:** The lambda `lambda m: m.group(0).replace(m.group(2), "[REDACTED]")` uses `str.replace()` which replaces **all non-overlapping occurrences** of `m.group(2)` inside `m.group(0)`. If two different keys in the same JSON blob happen to share the same value string, `replace()` will clobber both even though only one matched. More critically: if `m.group(2)` is an empty string (which `[^\s&]+` prevents for pattern 1, but `[^"]+` does NOT prevent for pattern 2 — an empty JSON string `""token"": ""` produces group 2 = `""`), `str.replace("", "[REDACTED]")` inserts `[REDACTED]` between every character, corrupting the entire serialized JSON blob rather than redacting a single field. The correct fix is a back-reference substitution that replaces only the matched span.

```python
# CURRENT (broken for empty-value edge):
text = pat.sub(lambda m: m.group(0).replace(m.group(2), "[REDACTED]"), text)

# FIX — replace only the exact captured group 2 span using group indices:
def _replace_group2(m: re.Match) -> str:
    start, end = m.span(2)
    full_start = m.start()
    return m.group(0)[: start - full_start] + "[REDACTED]" + m.group(0)[end - full_start :]

for pat in SECRET_PATTERNS:
    text = pat.sub(_replace_group2, text)
```

Note: pattern 2 (`[^"]+`) does not prevent an empty-quoted value (`"token": ""`), so the empty-replacement path is reachable in production JSON.

---

### CR-02: `emit()` called with `_CONN = None` raises `AttributeError` inside the `with conn:` block — silent data loss in production

**File:** `services/agent-runtime/atlas_audit/__init__.py:155-170` (all hook callsites)

**Issue:** `_CONN` is `None` until `set_connection()` is called (or when it is reset in teardown). In a live Hermes session, if the plugin is loaded but `on_session_start` fires before the runtime has set up a real connection (i.e., `set_connection` is never called because production code never calls it — there is no `register()` path that initialises `_CONN`), every `emit(_CONN, _LOCK, ...)` call will pass `conn=None`. Inside `audit_service.emit`, `with lock: with conn:` will succeed on `with lock:` then raise `TypeError: 'NoneType' object does not support the context manager protocol` on `with conn:`. This exception is caught by the outer `try/except Exception` in the hook, logged as a warning, and silently swallowed — **every audit event is dropped for the entire session with no user-visible failure**. The plugin provides no mechanism to acquire or initialise a real connection at `register()` time, and there is no test covering the `_CONN=None` production path.

**Fix:** Add a connection initialiser called from `register()` (or at first `emit()` call), and guard `emit()` calls with an explicit `_CONN is None` check that logs a clear error rather than letting the failure route through the generic exception handler:

```python
def on_post_tool_call(...) -> None:
    try:
        if _CONN is None:
            logger.error("atlas_audit: no connection — audit event dropped (call set_connection first)")
            return
        ...
        emit(_CONN, _LOCK, ...)
    except Exception as exc:
        logger.warning("atlas_audit: on_post_tool_call failed: %s", exc)
```

More fundamentally, `register(ctx)` should open and configure the WAL-mode connection to the ATLAS database path, not leave `_CONN = None` indefinitely.

---

### CR-03: Two separate locks protect two separate objects — race condition between `_CONN` and `_LOCK`

**File:** `services/agent-runtime/atlas_audit/__init__.py:39-40`

**Issue:** The module defines two independent locks: `_STATE_LOCK` (guards `_CURRENT_RUN`) and `_LOCK` (passed to `emit()` to guard the SQLite connection). `_CONN` itself is a module global written by `set_connection()` with **no lock protection**. A concurrent thread calling `set_connection(None)` (e.g., test teardown) while another thread is mid-execution between the `with _STATE_LOCK:` block and the `emit(...)` call creates a TOCTOU window: `_CONN` is read as non-None at check time, then becomes `None` before `emit` acquires `_LOCK` and executes `with conn:`. The result is the same silent-drop as CR-02 but is non-deterministic and impossible to reproduce reliably.

**Fix:** Protect `_CONN` reads and writes with `_LOCK` (or a single dedicated lock), and snapshot the value under the lock before passing it to `emit()`:

```python
def on_post_tool_call(...) -> None:
    try:
        with _STATE_LOCK:
            run_id = _CURRENT_RUN.get(session_id)
        with _LOCK:
            conn_snapshot = _CONN
        if run_id is None or conn_snapshot is None:
            ...
            return
        emit(conn_snapshot, _LOCK, ...)
    except Exception as exc:
        ...
```

---

### CR-04: `conftest.db_fixture` silently skips schema creation when migration file is absent — test suite gives false-clean result

**File:** `services/agent-runtime/tests/conftest.py:38-40`

**Issue:** The `db` fixture applies the migration only `if MIGRATION_PATH.exists()`. When the migration file does not exist (CI clone without the `infra/` tree, partial checkout, path drift), `conn.executescript(sql)` is skipped and the in-memory DB has **no tables at all**. Every test that calls `emit()` or queries `audit_events` will then raise `sqlite3.OperationalError: no such table: audit_events`, which pytest catches as an error — but `test_conftest.py::test_db_fixture_returns_connection` will **pass** because it only asserts `isinstance(db, sqlite3.Connection)` before checking for the table (the table assertion at line 13 would fail, but only if the migration is absent). The fixture docstring says "migration is applied only when ... exists" as if this is intentional, but the downstream tests have no skip guard and will produce misleading errors rather than a clear "migration not found" failure.

**Fix:** Fail hard when the migration is missing rather than silently proceeding:

```python
if not MIGRATION_PATH.exists():
    pytest.fail(
        f"Required migration not found: {MIGRATION_PATH}\n"
        "Ensure infra/migrations/0001_core.sql exists before running tests."
    )
sql = MIGRATION_PATH.read_text(encoding="utf-8")
conn.executescript(sql)
```

---

## Warnings

### WR-01: `on_post_tool_call` double-serializes `args` when value is already a JSON string — malformed storage

**File:** `services/agent-runtime/atlas_audit/__init__.py:141-146`

**Issue:** The hook serializes `args` to a JSON string (`args_str = json.dumps(args)` when `isinstance(args, dict)`), then passes it as `tool_call_kwargs["args"]`. Inside `emit()`, `audit_service` runs the same logic again: if `args_val` is a `str` it calls `_redact(args_val)` directly (correct), but the prior `json.dumps` in the hook is redundant. When `args` is not a dict and not None (e.g., a plain string already from Hermes), the hook falls through to `args_str = args or "{}"`, which may produce a non-JSON string that `audit_service` will store as-is. If Hermes ever passes a non-dict non-JSON string, the stored value is not valid JSON, violating D-013.

**Fix:** Move all args/result serialization into `emit()` (it already handles it) and pass the raw value from the hook:

```python
# In on_post_tool_call — pass raw args/result; let emit() serialize:
emit(
    _CONN, _LOCK,
    ...,
    tool_call_kwargs={
        "tool_name": tool_name,
        "args": args,        # raw Any — emit() handles dict/str/None
        "result": result,    # raw Any — emit() handles dict/str/None
    },
)
```

---

### WR-02: `get_events_for_run` and `export_jsonl` both execute raw `SELECT *` without the shared `_LOCK` — concurrent writes can produce torn reads

**File:** `services/agent-runtime/atlas_runtime/audit_service.py:191-196` and `219-231`

**Issue:** Both read functions accept a bare `conn` but no `lock`. They execute a `SELECT *` on `audit_events` while `emit()` may be concurrently writing under `_LOCK`. SQLite's WAL mode allows concurrent readers + one writer, so the reads are not corrupted at the SQLite level. However, if the caller shares the same `sqlite3.Connection` object (as in all tests and the plugin), the Python `sqlite3` module serialises all operations on a single connection object through Python's GIL, but **does not provide its own mutex**. Concurrent calls to `conn.execute()` from different threads on the same `Connection` (with `check_same_thread=False`) can interleave at the C level in CPython, leading to `ProgrammingError: Cannot operate on a closed database` or result corruption in edge cases. The read functions should either accept a lock parameter or document the threading constraint explicitly.

**Fix:** Accept an optional lock and acquire it for reads, or document that callers must not share the connection across threads without external serialisation.

---

### WR-03: `export_jsonl` returns `""` for no-events case but the docstring says "Returns '' if no events exist" — JSONL consumers treat empty string differently from no output

**File:** `services/agent-runtime/atlas_runtime/audit_service.py:217-231`

**Issue:** `"\n".join([])` returns `""`. A JSONL consumer that iterates `output.splitlines()` gets zero lines — correct. But a consumer that checks `if output:` to detect "has data" will correctly treat `""` as empty. The real problem: if exactly one event exists, `"\n".join(["<line>"])` returns `"<line>"` with **no trailing newline**. Standard JSONL format requires each record to end with `\n`. The `dest.write(line + "\n")` path is correct, but the return value path omits the trailing newline, so callers reading the return value get a non-conforming JSONL string for the single-event case and all multi-event cases.

**Fix:**
```python
return "\n".join(lines) + ("\n" if lines else "")
# Or more explicitly:
return "".join(line + "\n" for line in lines)
```

---

### WR-04: `SECRET_PATTERNS[1]` (JSON key-value pattern) does not cover single-quoted JSON or numeric secret values

**File:** `packages/atlas-core/atlas_core/schemas/core.py:27`

**Issue:** Pattern 2 is `"(token|...)"\s*:\s*"([^"]+)"` — it requires double-quoted values and a non-empty value. An integer secret (`"token": 12345`) or a null secret (`"token": null`) will not be redacted. While `data` is always serialized through `json.dumps()` (which uses double quotes), tool `args` from Hermes may contain numeric API keys or tokens. The regex is also anchored to double quotes, so embedded JSON within a string (e.g., a stringified JSON payload in `result`) is not recursively redacted.

**Fix:** Extend pattern 2 to cover numeric values and document the known gap for nested JSON strings:

```python
re.compile(r'(?i)"(token|api[_-]?key|secret|password)"\s*:\s*("[^"]*"|\d+|null|true|false)'),
```

And add a test for numeric token values in `test_emit_redacts_secret_in_data`.

---

### WR-05: `on_subagent_stop` drops `session_id` and `task_id` from the emitted event — incomplete audit trail

**File:** `services/agent-runtime/atlas_audit/__init__.py:285-293`

**Issue:** The `emit()` call in `on_subagent_stop` passes neither `session_id` nor `task_id`:

```python
emit(
    _CONN, _LOCK,
    run_id=run_id,
    event_type="subagent_run",
    duration_ms=duration_ms,
    data=data,
)
```

Both fields are available in the hook signature (`parent_session_id` for session, and the `**_` catch-all may contain `task_id`). AuditEvent rows for subagent completions will have `session_id=NULL` and `task_id=NULL`, making it impossible to correlate them with the parent session or task in queries. This is an audit completeness gap, not merely cosmetic.

**Fix:**
```python
emit(
    _CONN, _LOCK,
    run_id=run_id,
    event_type="subagent_run",
    session_id=parent_session_id,
    duration_ms=duration_ms,
    data=data,
)
```

---

## Info

### IN-01: `_LOCK` (connection lock) is a module global but semantically belongs to the connection — creates confusion with `_STATE_LOCK`

**File:** `services/agent-runtime/atlas_audit/__init__.py:40`

**Issue:** Having two module-level locks (`_STATE_LOCK` for `_CURRENT_RUN` and `_LOCK` for the connection) with similar names but different semantics is a maintenance hazard. When `set_connection()` replaces `_CONN`, the old `_LOCK` continues to guard a connection that may no longer exist. A cleaner pattern would bundle them into a dataclass or use a single lock for both.

**Fix:** Rename `_LOCK` to `_CONN_LOCK` at minimum; longer term, bundle `(_CONN, _CONN_LOCK)` into a simple `_ConnState` dataclass protected by a single lock.

---

### IN-02: `pyproject.toml` does not pin `atlas-core` dependency — local editable installs may diverge

**File:** `services/agent-runtime/pyproject.toml:11`

**Issue:** `dependencies = ["atlas-core"]` with no version constraint. In a monorepo with hatchling direct references this is often intentional, but if `atlas-core` is bumped with a breaking schema change (e.g., adding a required AuditEvent field), `atlas-runtime` will break at runtime with no install-time warning. `pyproject.toml` also has no `atlas-audit` as a separate entry under `[project.entry-points."hermes.plugins"]` — the plugin is distributed as a wheel package but Hermes plugin discovery may require an entry point.

**Fix:** Add a version lower bound (`atlas-core>=0.1.0`) and consider whether a `[project.entry-points]` section is needed for Hermes to discover the plugin without manual `plugin.yaml` wiring.

---

### IN-03: `test_conftest.py::test_db_fixture_returns_connection` assertion at line 13 is post-hoc and does not assert WAL mode or FK enforcement

**File:** `services/agent-runtime/tests/test_conftest.py:7-13`

**Issue:** The test asserts the table exists but does not verify that `PRAGMA journal_mode` returned `"wal"` or that `PRAGMA foreign_keys` is `1`. These are two of the three requirements stated in the fixture docstring. If the `PRAGMA` calls silently fail (e.g., `:memory:` with WAL silently falls back to DELETE journal mode on some SQLite builds), the tests would pass while running under a different mode than production.

**Fix:** Add two additional assertions:
```python
mode = db.execute("PRAGMA journal_mode").fetchone()[0]
assert mode == "wal", f"Expected WAL journal mode, got {mode!r}"
fk = db.execute("PRAGMA foreign_keys").fetchone()[0]
assert fk == 1, "FK enforcement not active"
```

---

_Reviewed: 2026-06-07T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
