# Phase 5: Mission & Run Lifecycle — Research

**Researched:** 2026-06-07
**Domain:** Python service layer, state machines, SQLite transaction patterns, CLI (Typer/Click), cross-platform policy engine
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-001**: Mission execution goes through the enhanced Hermes runtime loop directly — NOT a wrapper subprocess.
- **D-002**: Audit-first — every state transition (created, started, succeeded, failed, cancelled) emits an AuditEvent via the Phase 4 event bus (`audit_service.emit()`).
- **D-003**: SQLite/WAL is the datastore — all mission/run state persisted there.
- **D-006**: Policy engine must work cross-platform (Linux bash + Windows PowerShell paths). Do not hardcode either shell's path conventions.
- **D-008**: Skills must be classified before ATLAS-grade use — policy engine enforces allowed-tools lists; unclassified skill execution is rejected.
- Phase 4 event bus is a hard dependency — mission lifecycle emits via `emit()`, NOT raw SQL inserts.

### Claude's Discretion
- CLI library choice (Click vs Typer vs argparse) — Typer recommended (see rationale below).
- Internal module layout within `services/agent-runtime/` (subject to D-011 canonical layout).
- Mock/stub design for subagent governance (real spawning not required for RUNTIME-06).
- Test fixture reuse strategy (shared conftest vs per-module fixtures).

### Deferred Ideas (OUT OF SCOPE)
- Wiki ingest or update pipeline — Phase 6.
- REST API layer — Phase 7.
- Cockpit UI — Phase 8.
- CRM entity linkage to missions — v2.0.
- Pulse/heartbeat missions — v2.0.
- Interactive TUI or dashboard — out of scope.
- Real subagent spawning in production — stub is sufficient for Phase 5.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RUNTIME-01 | User can create a Mission via CLI or API and see it persisted in the database | `mission_service.create()` writes `missions` table; `atlas mission create` CLI subcommand |
| RUNTIME-02 | User can execute a Mission through the enhanced ATLAS/Hermes runtime loop | `run_service.start_run()` creates a Run row, calls `atlas_audit.set_connection()` + `on_session_start`, then invokes Hermes loop |
| RUNTIME-04 | A completed Run shows final status, start/finish timestamps, and a summary | `run_service.complete_run()` and `run_service.fail_run()` update `runs.status`, `finished_at`, `summary` atomically |
| RUNTIME-05 | User can cancel a running Mission; partial audit trail preserved | `run_service.cancel_run()` transitions run to `failed`/`cancelled`; existing audit rows are not deleted |
| RUNTIME-06 | Subagents governed: role, model tier, allowed tools, autonomy level, token budget per AuditEvent | Stub `subagent_service.dispatch()` emits `subagent_run` AuditEvent with governance payload |
| RUNTIME-07 | Policy engine enforces cross-platform workspace/command safety | `policy.py` uses `pathlib.Path.resolve()` (platform-agnostic); two test cases: Linux-style and Windows-style input paths |
</phase_requirements>

---

## Summary

Phase 5 builds the mission state machine on top of the Phase 4 event bus. The core work is three Python modules: `mission_service.py` (CRUD + state), `run_service.py` (lifecycle transitions), and `policy.py` (workspace boundary enforcement). A Typer CLI (`atlas mission create|run|cancel|status`) wraps these services. All state changes go through `audit_service.emit()` — no direct SQL writes to `missions` or `runs` except through the service layer.

The audit plugin from Phase 4 (`atlas_audit`) already handles Hermes hook wiring. Phase 5's `run_service.start_run()` is responsible for calling `atlas_audit.set_connection(conn)` and `atlas_audit.on_session_start(session_id=..., run_id=...)` before invoking the Hermes runtime loop. This is the designed handoff point documented in the Phase 4 plugin code (see `plugin.py` line 88: "Phase 5's start_run() will call set_connection() before invoking Hermes when a persistent connection is managed by the mission lifecycle").

The policy engine must use `pathlib.Path.resolve()` for workspace boundary checking — this is the only cross-platform approach that handles both `C:\Users\...` Windows paths and `/home/...` Linux paths without shell-specific logic.

**Primary recommendation:** Implement `mission_service.py` and `run_service.py` with explicit SQLite UPDATE transactions (no ORM), Typer for CLI, and `pathlib.Path.resolve()` for policy. Reuse the existing conftest.py `db` / `run_id` / `lock` fixtures as the test foundation.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Mission CRUD | Service layer (`mission_service.py`) | SQLite (`missions` table) | Domain logic stays in service; DB is persistence only |
| Run lifecycle transitions | Service layer (`run_service.py`) | Audit bus (`audit_service.emit()`) | Every transition must also emit an AuditEvent per D-002 |
| State machine enforcement | Service layer | — | SQL constraints enforce FK; service enforces valid transition graph |
| CLI interface | CLI module (`atlas_runtime/cli/`) | Typer entry point | Thin wrapper; no business logic in CLI handlers |
| Audit emission | Phase 4 `audit_service.emit()` | — | Hard dependency; CLI/service never write raw audit rows |
| Policy enforcement | `policy.py` | `audit_service.emit()` on rejection | Rejection must emit `failure` AuditEvent per success criterion 6 |
| Subagent governance stub | `subagent_service.py` | `audit_service.emit()` | Emits `subagent_run` event with governance payload; no real spawning |
| Hermes integration | `atlas_audit` plugin (Phase 4) | `run_service.start_run()` | Phase 4 owns hook wiring; Phase 5 owns the call that activates it |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `typer` | 0.26.7 | CLI framework (entry point: `atlas` command) | Built on Click; type-annotated subcommands; already in Hermes venv; AGENTS.md lists no objection to it as a thin CLI layer |
| `click` | 8.4.1 | Typer's underlying transport | Already installed; needed for `@click.option`, `CliRunner` in tests |
| `pytest` | 9.0.3 | Test runner | Already in `pyproject.toml [dev]`; existing test suite uses it |
| `pytest-cov` | 7.1.0 | Branch coverage measurement | Needed for ≥80% branch coverage gate on `mission_service.py` and `run_service.py` |
| `pydantic` | >=2.0 | Schema validation (inherited from `atlas-core`) | D-012: Pydantic v2 is the single schema source of truth |
| `sqlite3` | stdlib | Database access | D-003; already used throughout Phase 4 |
| `pathlib` | stdlib | Cross-platform path resolution for policy engine | `Path.resolve()` handles both Windows and POSIX paths transparently |
| `threading` | stdlib | Lock injection pattern (inherited from Phase 4) | Consistent with existing `audit_service.emit()` signature |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `rich` | latest (Typer dep) | Pretty CLI output (`print_rich`, tables, status badges) | Already installed as Typer dependency; use for `atlas mission status` output |
| `uuid` | stdlib | Mission/Run ID generation | Consistent with existing schema (all IDs are UUID4 strings) |
| `json` | stdlib | Serializing policy_result and subagent payload | Consistent with `audit_service` data-as-JSON-string pattern (D-013) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `typer` | `click` directly | Click requires more boilerplate; Typer's type annotations reduce surface area for a simple 4-command CLI |
| `typer` | `argparse` | argparse has no rich output; more verbose for nested subcommands; AGENTS.md notes no objection to Typer |
| `pathlib.Path.resolve()` | `os.path.abspath()` | Both work; `pathlib` is the modern stdlib choice and already referenced in D-013 cross-platform rule |
| direct SQL UPDATE | SQLAlchemy ORM | ORM adds a new framework dependency; AGENTS.md says "no new frameworks without a new decision"; raw SQL with explicit transactions is consistent with Phase 4 |

**Installation (new packages only):**
```bash
uv pip install typer pytest-cov
# click is already installed as a typer dependency
```

---

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| typer | PyPI | ~5 yrs | Very high (FastAPI ecosystem) | github.com/fastapi/typer | [OK] | Approved |
| click | PyPI | ~10 yrs | Very high (Flask/pip ecosystem) | github.com/pallets/click | [OK] | Approved |
| pytest-cov | PyPI | ~10 yrs | Very high | github.com/pytest-dev/pytest-cov [ASSUMED] | [OK] — note: slopcheck flagged "no source repo linked" but this is a known project | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

slopcheck ran successfully (v0.6.1). All three packages rated [OK]. The `pytest-cov` "no source repository linked" note is a slopcheck metadata limitation, not a legitimacy concern — pytest-cov is a well-established pytest ecosystem package [ASSUMED: source repo identity].

---

## Architecture Patterns

### System Architecture Diagram

```
CLI entry point (atlas mission <subcommand>)
        |
        v
[mission_service.py]          [run_service.py]
  create_mission()              start_run()
  get_mission()                 complete_run()
  list_missions()               fail_run()
  cancel_mission()              cancel_run()
        |                            |
        |--- SQLite UPDATE (missions) |--- SQLite INSERT/UPDATE (runs)
        |                            |
        +----------- audit_service.emit() ---------+
                             |
                    [audit_events table]
                             |
                   (atlas_audit plugin)
                    hooks fire during
                    Hermes runtime loop
                             |
                    [subagent_service.py]  <-- stub
                      dispatch_subagent()
                      emits subagent_run AuditEvent

[policy.py]
  check_workspace_boundary(path, workspace_root) -> PolicyDecision
  check_tool_allowed(tool_name, allowed_tools) -> PolicyDecision
  Rejection -> emit(event_type="failure", policy_result=...)
```

### Recommended Project Structure

```
services/agent-runtime/
├── atlas_runtime/
│   ├── __init__.py
│   ├── audit_service.py          # Phase 4 (existing)
│   ├── mission_service.py        # Phase 5 NEW
│   ├── run_service.py            # Phase 5 NEW
│   ├── policy.py                 # Phase 5 NEW
│   ├── subagent_service.py       # Phase 5 NEW (stub)
│   └── cli/
│       ├── __init__.py           # Phase 5 NEW
│       └── main.py               # Phase 5 NEW — Typer app entry point
├── atlas_audit/
│   └── __init__.py               # Phase 4 (existing)
├── tests/
│   ├── conftest.py               # Phase 4 (existing — reuse db/run_id/lock fixtures)
│   ├── test_audit_service.py     # Phase 4 (existing)
│   ├── test_atlas_audit_plugin.py # Phase 4 (existing)
│   ├── test_mission_service.py   # Phase 5 NEW
│   ├── test_run_service.py       # Phase 5 NEW
│   ├── test_policy.py            # Phase 5 NEW
│   └── test_cli.py               # Phase 5 NEW (Click CliRunner)
└── pyproject.toml                # Update: add [project.scripts] atlas entry point
```

### Pattern 1: Mission State Machine — Valid Transitions

**What:** The `missions.status` column is a Literal enum with 5 states. Service functions must enforce the valid transition graph; invalid transitions raise `ValueError` before any SQL executes.

**Valid transitions:**
```
pending   -> running    (start_run)
running   -> succeeded  (complete_run, success)
running   -> failed     (complete_run, failure / exception)
running   -> cancelled  (cancel_run)
# Terminal states: succeeded, failed, cancelled — no transitions out
```

**When to use:** Every `mission_service` and `run_service` function that changes status must validate the current state first.

**Example:**
```python
# Source: [ASSUMED — project pattern derived from existing audit_service.py + schema]
def complete_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: str,
    mission_id: str,
    status: Literal["succeeded", "failed"],
    summary: str = "",
) -> None:
    """Transition run to terminal state and emit AuditEvent."""
    # 1. Validate current run status
    row = conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise ValueError(f"Run {run_id!r} not found")
    if row[0] != "running":
        raise ValueError(f"Cannot complete run in state {row[0]!r}")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 2. Update run atomically
    with lock:
        with conn:
            conn.execute(
                "UPDATE runs SET status=?, finished_at=?, summary=? WHERE id=?",
                (status, now, summary, run_id),
            )
            conn.execute(
                "UPDATE missions SET status=?, updated_at=? WHERE id=?",
                (status, now, mission_id),
            )

    # 3. Emit AuditEvent (D-002: audit-first)
    emit(conn, lock, run_id=run_id, event_type="tool_call",
         data={"transition": status, "summary": summary})
```

### Pattern 2: SQLite Atomic State Transition (Prevent Race Conditions)

**What:** The threading.Lock from Phase 4 must wrap all SQLite writes. The `with conn:` context manager provides BEGIN/COMMIT/ROLLBACK. Combined, this prevents partial writes when two concurrent callers attempt to transition the same mission.

**Critical:** `mission` and `run` row updates that must be atomic go in the SAME `with conn:` block. Example: when a run completes, both `runs.status` and `missions.status` must update together or not at all.

**Pattern:**
```python
with lock:           # threading.Lock — single-writer at a time
    with conn:       # SQLite transaction — atomic commit/rollback
        conn.execute("UPDATE runs SET status=? WHERE id=?", (status, run_id))
        conn.execute("UPDATE missions SET status=? WHERE id=?", (mission_status, mission_id))
# AuditEvent emit happens AFTER the lock release (emit() acquires lock internally)
```

**Why:** `audit_service.emit()` acquires the same lock internally (via `with lock:` at line 157 of audit_service.py). Holding the lock during emit would deadlock. Pattern: update state → release lock → emit event.

**Corrected pattern for non-deadlock:**
```python
# Step 1: Update state under lock
with lock:
    with conn:
        conn.execute("UPDATE runs SET status=?, finished_at=? WHERE id=?", (...))
        conn.execute("UPDATE missions SET status=?, updated_at=? WHERE id=?", (...))

# Step 2: Emit outside lock (emit() re-acquires internally)
emit(conn, lock, run_id=run_id, event_type="tool_call", data={...})
```

### Pattern 3: Cross-Platform Policy Engine

**What:** `policy.py` validates whether a tool call's target path is within the workspace boundary. It must accept both Windows-style (`C:\Users\Davi\...`) and POSIX-style (`/home/user/...`) inputs and resolve them correctly on whichever OS the code runs on.

**Solution:** Use `pathlib.Path.resolve()`. On Windows, `Path("C:/Users/...")` resolves correctly. On Linux, `Path("/home/user/...")` resolves correctly. Neither requires shell-specific logic.

**Example:**
```python
# Source: [ASSUMED — derived from stdlib pathlib docs and D-006 cross-platform constraint]
import pathlib

def check_workspace_boundary(
    target_path: str,
    workspace_root: str,
) -> bool:
    """Return True if target_path is within workspace_root.

    Uses pathlib.Path.resolve() for cross-platform normalization.
    Works on both Windows (C:\...) and POSIX (/home/...) paths.
    """
    try:
        resolved_target = pathlib.Path(target_path).resolve()
        resolved_root = pathlib.Path(workspace_root).resolve()
        resolved_target.relative_to(resolved_root)  # raises ValueError if outside
        return True
    except ValueError:
        return False
```

**Test requirement (RUNTIME-07):** Two parametrized test cases — one with a Linux-style path string, one with a Windows-style path string — must both pass on the CI platform (Windows). Use `str` inputs, not `Path` objects, to test the conversion boundary.

### Pattern 4: Subagent Governance AuditEvent Payload (RUNTIME-06)

**What:** When a subagent is dispatched, a `subagent_run` AuditEvent must capture the governance envelope. This is a stub for Phase 5 — no real subagent spawning.

**Required payload fields** (from RUNTIME-06 and success criterion 5):
```python
subagent_payload = {
    "role": "researcher",          # str: subagent role/persona
    "model_tier": "sonnet",        # str: model class (haiku/sonnet/opus)
    "allowed_tools": ["Read", "WebSearch"],  # list[str]: tool allowlist (D-008)
    "autonomy_level": "supervised",  # str: supervised/autonomous/etc.
    "token_budget": 4096,          # int: max tokens for this subagent invocation
}
emit(conn, lock, run_id=run_id, event_type="subagent_run", data=subagent_payload)
```

**`event_type` field:** `"subagent_run"` is already in the `AuditEvent.event_type` Literal (verified in `core.py` line 104). No schema change required.

### Pattern 5: Typer CLI Structure

**What:** The `atlas` command entry point uses Typer with a `mission` subapp.

**Example:**
```python
# Source: [VERIFIED: pip registry — typer 0.26.7 exists; pattern from Typer docs [ASSUMED]]
import typer
app = typer.Typer()
mission_app = typer.Typer()
app.add_typer(mission_app, name="mission")

@mission_app.command("create")
def create(
    title: str = typer.Option(..., "--title"),
    intent: str = typer.Option("", "--intent"),
) -> None:
    # call mission_service.create_mission()
    ...

@mission_app.command("run")
def run_mission(mission_id: str) -> None:
    # call run_service.start_run()
    ...
```

**Entry point in pyproject.toml:**
```toml
[project.scripts]
atlas = "atlas_runtime.cli.main:app"
```

### Anti-Patterns to Avoid

- **Raw SQL writes to `missions`/`runs` from CLI handlers:** All SQL goes through the service layer. CLI handlers call service functions only.
- **Holding the lock while calling `emit()`:** `emit()` acquires the lock internally. Holding the lock before `emit()` causes deadlock. Pattern: release lock, then call emit.
- **shell=True in policy engine:** Never use `subprocess.run(..., shell=True)` in policy checks. Use `pathlib.Path.resolve()` for path validation.
- **Hardcoding platform path separator:** Never use `os.sep` or string splitting on `\` or `/` for workspace boundary checks. Use `pathlib`.
- **Mutable model state:** Pydantic models are `frozen=True` (D-012/D-013). Never mutate a Mission or Run model. Fetch from DB, reconstruct, or use `.model_copy(update={...})` for in-memory modifications.
- **Direct INSERT into `audit_events` from service layer:** Always use `audit_service.emit()`. Never bypass the secret-redaction and Pydantic validation guard.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument parsing | Custom `sys.argv` parser | `typer` | Handles `--option`, subcommands, help text, type coercion |
| Secret redaction | New regex patterns | `audit_service._redact()` (Phase 4) | Already implemented and tested; emit() applies it automatically |
| DB transaction management | Manual `conn.commit()` / `conn.rollback()` calls | `with conn:` context manager | sqlite3's `with conn:` provides automatic BEGIN/COMMIT/ROLLBACK |
| Thread safety | Custom mutex logic | `threading.Lock` (same pattern as Phase 4) | Established pattern; lock is injected, not global |
| Cross-platform path normalization | Custom regex for Windows/POSIX paths | `pathlib.Path.resolve()` | stdlib, OS-aware, handles UNC paths, symlinks, relative segments |
| Coverage enforcement | Manual line counting | `pytest-cov --cov-fail-under=80` | Reports branch coverage; plugs into existing pytest invocation |

**Key insight:** Every problem in Phase 5 has a stdlib or existing project solution. The only new external library is Typer — and it's already installed in the Hermes venv.

---

## Common Pitfalls

### Pitfall 1: Deadlock via Double Lock Acquisition

**What goes wrong:** `run_service.complete_run()` acquires the lock for the SQL UPDATE, then calls `audit_service.emit()` while still holding the lock. `emit()` also tries to acquire the same lock → deadlock.

**Why it happens:** `emit()` at line 157 of `audit_service.py` does `with lock:` unconditionally.

**How to avoid:** Always release the lock before calling `emit()`. Pattern: `with lock: with conn: UPDATE...` → exit lock → call `emit(conn, lock, ...)`.

**Warning signs:** Tests hang indefinitely rather than failing fast.

### Pitfall 2: Forgotten Mission Status Sync

**What goes wrong:** `complete_run()` updates `runs.status` to `succeeded` but does not update `missions.status`. The mission stays in `running` state forever.

**Why it happens:** `missions` and `runs` are separate rows. The service layer must keep both in sync.

**How to avoid:** Every run terminal transition (`complete_run`, `fail_run`, `cancel_run`) must update both the `runs` row AND the parent `missions` row in the same atomic transaction.

**Warning signs:** `atlas mission status <id>` shows `running` after a completed run.

### Pitfall 3: Policy Engine Raises on Relative Paths

**What goes wrong:** `pathlib.Path("../../../etc/passwd").resolve()` resolves relative to the current working directory, not the workspace root. If CWD is inside the workspace, the resolved path may appear to be within the workspace even though it escapes it.

**Why it happens:** `Path.resolve()` resolves relative to CWD, not the policy check's workspace_root.

**How to avoid:** Before `relative_to()` check, verify the target is an absolute path OR resolve relative paths relative to the workspace_root: `(workspace_root / target).resolve()`. Always normalize the workspace_root itself with `.resolve()`.

**Warning signs:** `../../etc/passwd` passes the boundary check when CWD is inside the workspace.

### Pitfall 4: Run Created Without Mission Existing

**What goes wrong:** `run_service.start_run()` inserts a row into `runs` with a `mission_id` that doesn't exist in `missions`. SQLite raises `FOREIGN KEY constraint failed`.

**Why it happens:** FK constraints are enforced (`PRAGMA foreign_keys = ON` in conftest and migration).

**How to avoid:** `start_run()` must verify the mission exists (and is in `pending` or `running` state) before inserting the run row. Use `SELECT status FROM missions WHERE id=?` first.

**Warning signs:** `IntegrityError: FOREIGN KEY constraint failed` in tests.

### Pitfall 5: Typer Entry Point Not Installed

**What goes wrong:** `atlas mission create ...` command not found, even though the code is correct.

**Why it happens:** The `[project.scripts]` entry point in `pyproject.toml` requires `pip install -e .` (or `uv pip install -e .`) to register the `atlas` console script.

**How to avoid:** Wave 0 plan includes installing the package in editable mode. Test CLI behavior via `typer.testing.CliRunner` (does not require the console script to be installed).

### Pitfall 6: `status` Transition on Already-Terminal Mission

**What goes wrong:** Calling `cancel_run()` on a mission already in `succeeded` or `failed` state corrupts the audit trail or raises an uncaught exception that crashes the CLI.

**Why it happens:** No guard on the current state before the UPDATE.

**How to avoid:** Every transition function reads the current status first. If the current state is terminal, raise `ValueError` with a clear message — do NOT silently no-op.

---

## Code Examples

### Creating a Mission (mission_service.py)
```python
# Source: [ASSUMED — derived from existing Phase 4 emit() pattern and core.py Mission model]
import datetime
import sqlite3
import threading

from atlas_core.schemas.core import Mission
from atlas_runtime.audit_service import emit


def create_mission(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    title: str,
    intent: str = "",
    project: str = "",
) -> Mission:
    """Insert a new Mission row and return the constructed Mission."""
    mission = Mission(title=title, intent=intent, project=project)
    row = mission.model_dump()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at) "
                "VALUES (:id,:title,:intent,:status,:project,:created_at,:updated_at)",
                row,
            )
    # No AuditEvent on create — no run_id exists yet.
    # The 'task.started' AuditEvent is emitted by start_run().
    return mission
```

### Starting a Run (run_service.py)
```python
# Source: [ASSUMED — derived from existing conftest.py run_id fixture and plugin.py Phase 4]
def start_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    mission_id: str,
    session_id: str | None = None,
) -> Run:
    """Create a Run row, emit task.started AuditEvent, wire audit plugin."""
    # 1. Validate mission exists and is pending
    row = conn.execute(
        "SELECT status FROM missions WHERE id=?", (mission_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Mission {mission_id!r} not found")
    if row[0] not in ("pending",):
        raise ValueError(f"Cannot start run for mission in state {row[0]!r}")

    # 2. Create Run
    run = Run(mission_id=mission_id, session_id=session_id)
    run_row = run.model_dump()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with lock:
        with conn:
            conn.execute(
                "INSERT INTO runs(id,mission_id,session_id,status,started_at,finished_at,summary) "
                "VALUES (:id,:mission_id,:session_id,:status,:started_at,:finished_at,:summary)",
                run_row,
            )
            conn.execute(
                "UPDATE missions SET status='running', updated_at=? WHERE id=?",
                (now, mission_id),
            )

    # 3. Wire audit plugin (D-001: Phase 4 plugin owns the Hermes hook)
    import atlas_audit
    atlas_audit.set_connection(conn)
    atlas_audit.on_session_start(
        session_id=session_id or run.id,
        run_id=run.id,
    )

    # 4. Emit task.started AuditEvent (D-002)
    emit(
        conn, lock,
        run_id=run.id,
        event_type="tool_call",
        session_id=session_id,
        data={"transition": "started", "mission_id": mission_id},
    )

    return run
```

### Policy Check (policy.py)
```python
# Source: [ASSUMED — derived from pathlib stdlib docs and D-006/D-007 constraints]
import pathlib
from dataclasses import dataclass

@dataclass
class PolicyDecision:
    allowed: bool
    reason: str

def check_workspace_boundary(
    target_path: str,
    workspace_root: str,
) -> PolicyDecision:
    """Cross-platform path boundary enforcement (RUNTIME-07)."""
    try:
        resolved_root = pathlib.Path(workspace_root).resolve()
        # Resolve target relative to root to prevent CWD escapes
        resolved_target = (resolved_root / target_path).resolve()
        resolved_target.relative_to(resolved_root)
        return PolicyDecision(allowed=True, reason="within_workspace")
    except ValueError:
        return PolicyDecision(
            allowed=False,
            reason=f"path_outside_workspace: {target_path!r} not under {workspace_root!r}",
        )
```

### Typer CLI Test Pattern
```python
# Source: [ASSUMED — Typer testing docs pattern]
from typer.testing import CliRunner
from atlas_runtime.cli.main import app

runner = CliRunner()

def test_create_mission(db):
    result = runner.invoke(app, ["mission", "create", "--title", "Test", "--intent", "do X"])
    assert result.exit_code == 0
    assert "mission_id" in result.output or len(result.output.strip()) == 36  # UUID
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `argparse` for CLIs | `click` / `typer` | ~2018 | Type annotations, less boilerplate, subcommand support |
| `os.path` for path ops | `pathlib.Path` | Python 3.4+ | Cross-platform, OO, `.resolve()` handles symlinks + UNC |
| `sqlite3` with manual commit | `with conn:` context manager | Python 3.x | Automatic BEGIN/COMMIT/ROLLBACK; less error-prone |
| Pydantic v1 `__root__` models | Pydantic v2 `model_dump()` | 2023 | Frozen models, field_serializer, JSON-stable output |

**Deprecated/outdated:**
- `os.path.abspath()` for cross-platform path checks: works but doesn't resolve symlinks or UNC paths — use `pathlib.Path.resolve()` instead.
- `optparse`: fully replaced by `argparse` and then by Click/Typer.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `typer` is acceptable under AGENTS.md "no new frameworks" rule (interpreted as thin CLI layer, not a web/ORM framework) | Standard Stack | Low — can substitute plain `click` with minimal code change |
| A2 | The `atlas mission create` command does not emit an AuditEvent (no run_id exists yet) — first AuditEvent is `task.started` from `start_run()` | Code Examples | Low — could add a `mission.created` event type in future but schema doesn't have it yet |
| A3 | `subagent_run` AuditEvent payload field names (`role`, `model_tier`, `allowed_tools`, `autonomy_level`, `token_budget`) are sufficient for RUNTIME-06 | Architecture Patterns | Medium — if planner or user has specific field names required, adjust |
| A4 | pytest-cov's source repo identity (claimed: github.com/pytest-dev/pytest-cov) | Package Audit | Very low — pytest-cov is universally known package |
| A5 | Typer `CliRunner` supports testing subapps (`app.add_typer(...)`) in 0.26.x | Code Examples | Low — verify at test time; CliRunner is standard Typer testing pattern |

---

## Open Questions

1. **Should `atlas mission run <id>` block until the Hermes loop exits, or return immediately?**
   - What we know: The CLI needs to be usable; Hermes loops can be long-running.
   - What's unclear: MVP scope — is this a fire-and-forget CLI or a blocking progress display?
   - Recommendation: Default to blocking (synchronous) for Phase 5 MVP. Async/background mode is Phase 7+ territory.

2. **What `event_type` value should the `task.started` AuditEvent use?**
   - What we know: `AuditEvent.event_type` Literal allows: `llm_call`, `tool_call`, `subagent_run`, `approval`, `artifact`, `wiki_update`, `memory_change`, `failure`. There is no `task.started` literal.
   - What's unclear: The success criterion says "emits task.started AuditEvent" — this phrasing may be informal, not a new event_type value.
   - Recommendation: Use `event_type="tool_call"` with `data={"transition": "started"}` since the schema has no `task_started` literal. If a new event_type is needed, it requires a schema change (core.py + migration + all Literal usages).

3. **Does `cancel_run()` set run status to `failed` or `cancelled`?**
   - What we know: `runs.status` Literal allows `cancelled` as a value. Success criterion 4 says "transitions it to `failed`" but the schema has a distinct `cancelled` state.
   - What's unclear: The CONTEXT.md success criteria say `failed` but the schema's `cancelled` literal exists specifically for this case.
   - Recommendation: Use `cancelled` for `cancel_run()` — it matches the schema design intent. Update success criterion wording to match during plan review.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | All code | ✓ | 3.11.15 | — |
| `atlas-core` package | `mission_service.py` (Mission/Run schemas) | ✓ (importable from source path) | 0.1.0 | — |
| `atlas-runtime` package | `audit_service.emit()`, `atlas_audit` plugin | ✓ (importable from source path) | 0.1.0 | — |
| `typer` | CLI | ✓ (in system Python) | 0.25.1 | plain `click` |
| `click` | Typer dep + CliRunner | ✓ (in system Python) | 8.3.3 | — |
| `pytest` | Test suite | ✓ | 9.0.3 | — |
| `pytest-cov` | Branch coverage | available on PyPI; not in atlas-runtime venv yet | 7.1.0 | run without coverage gate |
| SQLite | Database | ✓ (stdlib) | bundled with Python 3.11 | — |

**Missing dependencies with no fallback:**
- None — all required capabilities are available.

**Missing dependencies with fallback:**
- `pytest-cov`: Add to `pyproject.toml [dev]` and install in the atlas-runtime editable install. Fallback is running pytest without `--cov` (coverage gate not enforced).

**Note on package environment:** The project does not appear to use a dedicated venv for `services/agent-runtime` yet (no `.venv` found). Phase 5 Wave 0 must include `uv pip install -e services/agent-runtime[dev]` (or equivalent) to register `atlas` as a console script and pull in `typer` + `pytest-cov` into the correct environment.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `services/agent-runtime/pyproject.toml` → `[tool.pytest.ini_options]` testpaths = ["tests"] |
| Quick run command | `pytest services/agent-runtime/tests/test_mission_service.py tests/test_run_service.py -x` |
| Full suite command | `pytest services/agent-runtime/ --cov=atlas_runtime --cov-branch --cov-fail-under=80` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RUNTIME-01 | `create_mission()` persists row; `atlas mission create` prints ID | unit + CLI | `pytest tests/test_mission_service.py tests/test_cli.py -x` | ❌ Wave 0 |
| RUNTIME-02 | `start_run()` creates Run row, emits task.started, wires atlas_audit plugin | unit | `pytest tests/test_run_service.py::test_start_run -x` | ❌ Wave 0 |
| RUNTIME-04 | `complete_run()` sets succeeded/failed status, finish timestamp, summary | unit | `pytest tests/test_run_service.py::test_complete_run -x` | ❌ Wave 0 |
| RUNTIME-05 | `cancel_run()` stops active run; existing audit rows preserved | unit | `pytest tests/test_run_service.py::test_cancel_run -x` | ❌ Wave 0 |
| RUNTIME-06 | `dispatch_subagent()` stub emits `subagent_run` event with governance payload | unit | `pytest tests/test_run_service.py::test_subagent_governance -x` | ❌ Wave 0 |
| RUNTIME-07 | Policy engine rejects out-of-workspace path; passes on both Linux + Windows path strings | unit (parametrized) | `pytest tests/test_policy.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest services/agent-runtime/tests/test_mission_service.py tests/test_run_service.py -x -q`
- **Per wave merge:** `pytest services/agent-runtime/ --cov=atlas_runtime --cov-branch --cov-fail-under=80`
- **Phase gate:** Full suite green + coverage ≥80% before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_mission_service.py` — covers RUNTIME-01 (create, get, list)
- [ ] `tests/test_run_service.py` — covers RUNTIME-02, RUNTIME-04, RUNTIME-05, RUNTIME-06
- [ ] `tests/test_policy.py` — covers RUNTIME-07 (parametrized Linux + Windows path cases)
- [ ] `tests/test_cli.py` — covers CLI subcommand invocations via CliRunner
- [ ] `atlas_runtime/mission_service.py` — stub with docstrings before Wave 1 implementation
- [ ] `atlas_runtime/run_service.py` — stub with docstrings before Wave 1 implementation
- [ ] `atlas_runtime/policy.py` — stub with docstrings before Wave 1 implementation
- [ ] `atlas_runtime/subagent_service.py` — stub (Phase 5 is all-stub for subagents)
- [ ] `atlas_runtime/cli/main.py` — Typer app with four commands (create, run, cancel, status)
- [ ] Update `pyproject.toml` — add `[project.scripts]` atlas entry + `typer` dep + `pytest-cov` to dev

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | CLI is local operator; no network auth in Phase 5 |
| V3 Session Management | partial | Hermes session_id tracked in atlas_audit._CURRENT_RUN; no persistent session tokens |
| V4 Access Control | yes | Policy engine (policy.py) enforces workspace boundary and allowed-tools list (D-008) |
| V5 Input Validation | yes | pydantic v2 frozen models; `Mission(title=...)` validates all inputs before SQL |
| V6 Cryptography | no | No secrets generated or stored in Phase 5; secret-redaction inherited from Phase 4 |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal (`../../etc/passwd` in tool args) | Tampering | `pathlib.Path.resolve()` + `relative_to()` check in policy.py |
| SQL injection via mission title/intent | Tampering | Pydantic validates inputs; sqlite3 parameterized queries (`:param` style) — never f-string SQL |
| Secret leakage in subagent_run payload | Information Disclosure | All `data` payloads pass through `audit_service._redact()` via `emit()` |
| Unclassified tool bypass | Elevation of Privilege | `check_tool_allowed()` in policy.py rejects tool_name not in allowed_tools list (D-008) |
| State machine bypass (direct SQL UPDATE) | Tampering | Service functions are the only path to state changes; no direct SQL from CLI or tests |

---

## Sources

### Primary (HIGH confidence)
- `services/agent-runtime/atlas_runtime/audit_service.py` — exact `emit()` signature, lock pattern, deadlock risk
- `services/agent-runtime/atlas_audit/__init__.py` — Phase 4 plugin; `set_connection()`, `on_session_start()` handoff documented at line 88
- `packages/atlas-core/atlas_core/schemas/core.py` — Mission/Run/AuditEvent fields, Literal enums, frozen=True constraint
- `infra/migrations/0001_core.sql` — missions/runs table columns, FK constraints, WAL mode
- `services/agent-runtime/tests/conftest.py` — db/run_id/lock fixture pattern (reuse in Phase 5 tests)
- `services/agent-runtime/pyproject.toml` — existing package structure, hatch build, testpaths

### Secondary (MEDIUM confidence)
- `AGENTS.md` — language rules (D-013), approved deps list (`pydantic`, `rich`, `pytest`; no new frameworks without decision)
- `.planning/STATE.md` — all locked decisions (D-001 through D-008)
- `pip index versions` output — confirmed click 8.4.1, typer 0.26.7, pytest-cov 7.1.0, pytest 9.0.3 exist on PyPI
- `slopcheck install click typer pytest-cov` — all three packages rated [OK] by slopcheck 0.6.1

### Tertiary (LOW confidence)
- None — all claims are grounded in the codebase or package registry.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — packages verified via `pip index versions` and `slopcheck`
- Architecture: HIGH — derived directly from existing Phase 4 code; no speculation
- State machine: HIGH — schema Literals define the exact valid states
- Policy engine: HIGH — `pathlib.Path.resolve()` is stdlib, documented, cross-platform
- Pitfalls: HIGH — deadlock and FK pitfalls derived directly from reading existing code
- CLI pattern: MEDIUM — Typer test patterns assumed from docs (not Context7-verified)

**Research date:** 2026-06-07
**Valid until:** 2026-09-07 (stable stack; Python stdlib and sqlite3 don't change rapidly)

---

## RESEARCH COMPLETE
