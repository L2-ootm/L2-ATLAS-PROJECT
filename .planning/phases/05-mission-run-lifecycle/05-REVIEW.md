---
phase: 05
status: has_findings
reviewed_at: 2026-06-08
depth: standard
files_reviewed: 6
files_reviewed_list:
  - services/agent-runtime/atlas_runtime/mission_service.py
  - services/agent-runtime/atlas_runtime/run_service.py
  - services/agent-runtime/atlas_runtime/policy.py
  - services/agent-runtime/atlas_runtime/subagent_service.py
  - services/agent-runtime/atlas_runtime/cli/main.py
  - services/agent-runtime/atlas_runtime/cli/__init__.py
findings:
  critical: 1
  warning: 5
  info: 2
  total: 8
---

# Phase 05 Code Review

## Summary

1 critical finding, 5 warnings, 2 info findings.

The emit-after-lock pattern is correctly applied throughout — no deadlock. SQL uses parameterized queries throughout — no injection. Pydantic-first write guard is upheld in all service functions. Dual-table atomicity in `complete_run` and `cancel_run` is correct. `cancel_run` correctly uses `"cancelled"` status.

The critical finding is a TOCTOU race condition across all three state-guarding functions: the status pre-condition check runs outside the lock, allowing another thread to interleave between the check and the write. Five warnings cover: raw SQL in the CLI handler, silent swallowing of audit failures in the subagent stub, a missing service-layer function that forces the CLI to bypass the service layer, unclosed DB connections per CLI invocation, and an unguarded `ImportError` path in `start_run`.

---

## Findings

### Critical

#### CR-01: TOCTOU race — status pre-condition checks outside the lock

**Files:**
- `services/agent-runtime/atlas_runtime/run_service.py:44-52` (`start_run`)
- `services/agent-runtime/atlas_runtime/run_service.py:108-116` (`complete_run`)
- `services/agent-runtime/atlas_runtime/run_service.py:170-178` (`cancel_run`)

**Issue:** In all three state-transition functions, the `SELECT status FROM runs/missions WHERE id=?` pre-condition check runs without holding the lock. The lock is only acquired later for the `UPDATE`. Between the check and the write, another thread (or the CLI's cancel loop) can change the row's status. This means two concurrent `complete_run` calls on the same run can both pass the `row[0] != "running"` guard and both execute the UPDATE, leaving the DB in an inconsistent state with two `finished_at` timestamps and two AuditEvents claiming terminal-state transitions.

The threading.Lock is injected precisely to prevent this. Moving the SELECT inside the `with lock:` block closes the window.

**Fix:** Move the status SELECT inside the lock so the check and the write are in the same critical section:

```python
# complete_run — corrected pattern (apply same fix to start_run and cancel_run)
with lock:
    with conn:
        row = conn.execute(
            "SELECT status FROM runs WHERE id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Run {run_id!r} not found")
        if row[0] != "running":
            raise ValueError(f"Cannot complete run in state {row[0]!r}")

        conn.execute(
            "UPDATE runs SET status=?, finished_at=?, summary=? WHERE id=?",
            (status, now, summary, run_id),
        )
        conn.execute(
            "UPDATE missions SET status=?, updated_at=? WHERE id=?",
            (status, now, mission_id),
        )
# emit() called after the lock block as before
```

Note: `now` must also be computed before or inside the lock block. Because `datetime.datetime.now(...)` is cheap and non-blocking, computing it just before `with lock:` is acceptable.

---

### Warning

#### WR-01: Raw SQL in CLI cancel handler — service layer bypass

**File:** `services/agent-runtime/atlas_runtime/cli/main.py:92-95`

**Issue:** The `cancel` command issues a raw `SELECT id, status FROM runs WHERE mission_id=? AND status='running'` query directly inside the CLI handler. The design constraint is explicit: "All SQL goes through the service layer. CLI handlers call service functions only." The CLI handler is querying the `runs` table directly instead of calling a service function.

This also means there is no `cancel_mission()` or `get_active_runs_for_mission()` function in `mission_service.py`, which was listed in the architecture responsibility map as a required service function.

**Fix:** Add a `get_active_runs` function to `run_service.py` (or `mission_service.py`) and call it from the CLI:

```python
# run_service.py — add:
def get_active_runs(
    conn: sqlite3.Connection,
    mission_id: str,
) -> list[Run]:
    """Return all running runs for a mission."""
    cursor = conn.execute(
        "SELECT * FROM runs WHERE mission_id=? AND status='running'",
        (mission_id,),
    )
    cols = [d[0] for d in cursor.description]
    return [Run(**dict(zip(cols, row))) for row in cursor]

# cli/main.py cancel command — replace direct SQL with:
runs = run_service.get_active_runs(conn, mission_id)
if not runs:
    typer.echo("no active run")
    return
for run in runs:
    run_service.cancel_run(conn, lock, run_id=run.id, mission_id=mission_id)
```

---

#### WR-02: Audit failures silently swallowed in subagent_service.dispatch_subagent

**File:** `services/agent-runtime/atlas_runtime/subagent_service.py:50-53`

**Issue:** The `try/except Exception` block catches all errors from `emit()` and logs only a warning. Per D-002 (audit-first), every state transition must emit an AuditEvent. Silently swallowing an `emit()` failure means subagent governance events can be lost without the caller knowing. A broken DB connection, a Pydantic validation error on the payload, or a schema mismatch would all be silently dropped. The docstring cites "fail-open error guard from 05-PATTERNS.md" but no such pattern was prescribed in 05-RESEARCH.md — the research explicitly requires the event to be captured.

**Fix:** Remove the silent swallow. Let `emit()` exceptions propagate to the caller so failures are surfaced:

```python
def dispatch_subagent(conn, lock, *, run_id, role, model_tier="sonnet",
                      allowed_tools=None, autonomy_level="supervised",
                      token_budget=4096) -> None:
    payload = {
        "role": role,
        "model_tier": model_tier,
        "allowed_tools": allowed_tools if allowed_tools is not None else [],
        "autonomy_level": autonomy_level,
        "token_budget": token_budget,
    }
    emit(conn, lock, run_id=run_id, event_type="subagent_run", data=payload)
```

If the caller needs fail-open behavior, that decision belongs at the call site, not inside the service function.

---

#### WR-03: ImportError from atlas_audit not caught in start_run

**File:** `services/agent-runtime/atlas_runtime/run_service.py:75-77`

**Issue:** `start_run` imports `atlas_audit` at function scope and calls `set_connection()` and `on_session_start()` after the DB transaction has already committed. If `atlas_audit` is not installed (e.g., running tests that only install `atlas_runtime` without the plugin), this raises `ImportError` — after the mission row has been updated to `running` and the run row has been inserted. The DB is now in a `running` state with no audit wiring and no `task.started` event, and the caller receives an exception.

**Fix:** Move the import to module level so the failure is caught at import time (not mid-transaction), or wrap with a clear exception:

```python
# Option A: module-level import (preferred — fails at startup, not mid-transaction)
import atlas_audit  # top of run_service.py

# Option B: wrap with a clear re-raise if deferred import is intentional
try:
    import atlas_audit
    atlas_audit.set_connection(conn)
    atlas_audit.on_session_start(session_id=session_id or run.id, run_id=run.id)
except ImportError as exc:
    raise RuntimeError(
        "atlas_audit plugin is required for run_service.start_run(). "
        "Install it with: pip install atlas-audit"
    ) from exc
```

Option A is cleaner. The deferred import pattern only makes sense if the import is optional, but the code has no fallback path when `atlas_audit` is absent.

---

#### WR-04: DB connection never closed per CLI invocation

**File:** `services/agent-runtime/atlas_runtime/cli/main.py:63-66, 74-76, 89-91, 111-113`

**Issue:** Every CLI command calls `_get_connection()` which opens a new SQLite connection but never closes it. In SQLite WAL mode, an unclosed connection holds a read lock on the WAL file. For a CLI process (short-lived), the OS reclaims the file descriptor on exit, but in WAL mode the WAL file is not checkpointed until the last reader closes. Repeated CLI invocations accumulate WAL file growth. Additionally, if any command raises an unhandled exception, the connection is not closed cleanly.

**Fix:** Use a context manager or explicit close:

```python
@mission_app.command("create")
def create(title: str = typer.Option(..., "--title"),
           intent: str = typer.Option("", "--intent")) -> None:
    conn = _get_connection()
    try:
        lock = _get_lock()
        mission = mission_service.create_mission(conn, lock, title=title, intent=intent)
        typer.echo(mission.id)
    finally:
        conn.close()
```

Apply the `try/finally: conn.close()` pattern to all four command handlers.

---

#### WR-05: status command reads DB without the lock

**File:** `services/agent-runtime/atlas_runtime/cli/main.py:113-114`

**Issue:** The `status` command opens a connection and reads from `missions` without calling `_get_lock()`. All other commands (create, run, cancel) at least call `_get_lock()`. While reads in SQLite WAL mode are generally safe without a lock, the inconsistency is a maintenance hazard — if `status` is later extended to write (e.g., to update `accessed_at`), the missing lock pattern will cause a write race. The lock injection pattern is the established contract for all DB operations in this codebase.

**Fix:** Add `lock = _get_lock()` to the `status` handler for consistency, and consider routing the read through `mission_service.get_mission()`:

```python
@mission_app.command("status")
def status(mission_id: str = typer.Argument(...)) -> None:
    conn = _get_connection()
    try:
        mission = mission_service.get_mission(conn, mission_id)
        if mission is None:
            typer.echo("not found")
            raise typer.Exit(1)
        typer.echo(mission.status)
    finally:
        conn.close()
```

---

### Info

#### IN-01: Mission create emits no AuditEvent — no run_id exists

**File:** `services/agent-runtime/atlas_runtime/mission_service.py:34-46`

**Issue:** `create_mission()` does not emit an AuditEvent because no `run_id` exists at mission creation time. This is intentional (noted in the code comment and confirmed by 05-RESEARCH.md assumption A2). However, D-002 states "every state transition emits an AuditEvent." Creating a mission is a state transition (nothing → pending). The code comment acknowledges this gap but treats it as acceptable.

This is not a bug for Phase 5 (the schema has no `mission.created` event_type and there is no run_id to attach it to), but it is a known coverage gap in the audit trail that should be tracked as technical debt.

**Fix:** No action required for Phase 5. Log as tech debt: add a `mission_created` event_type to `AuditEvent` schema in a future phase and emit it from `create_mission()`.

---

#### IN-02: check_tool_allowed has no emit-on-rejection variant

**File:** `services/agent-runtime/atlas_runtime/policy.py:97-111`

**Issue:** `check_workspace_boundary_and_emit` (which emits a `failure` AuditEvent on rejection) exists, but there is no `check_tool_allowed_and_emit` equivalent. Per success criterion 6 in CONTEXT.md, policy rejections should emit an AuditEvent. The tool allowlist check (D-008) currently returns a `PolicyDecision` without any audit emission on rejection.

**Fix:** Add a `check_tool_allowed_and_emit` function parallel to `check_workspace_boundary_and_emit`:

```python
def check_tool_allowed_and_emit(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    tool_name: str,
    allowed_tools: list[str],
) -> PolicyDecision:
    decision = check_tool_allowed(tool_name, allowed_tools)
    if not decision.allowed:
        emit(
            conn, lock,
            run_id=run_id,
            event_type="failure",
            data={"reason": decision.reason, "tool_name": tool_name},
            policy_result=decision.reason,
        )
    return decision
```

---

_Reviewed: 2026-06-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
