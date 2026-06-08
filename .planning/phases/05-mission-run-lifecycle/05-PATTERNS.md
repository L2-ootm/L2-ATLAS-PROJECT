# Phase 5: Mission & Run Lifecycle - Pattern Map

**Mapped:** 2026-06-07
**Files analyzed:** 11 (10 new + 1 modified)
**Analogs found:** 11 / 11

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `atlas_runtime/mission_service.py` | service | CRUD | `atlas_runtime/audit_service.py` | role-match (same lock/conn/emit pattern) |
| `atlas_runtime/run_service.py` | service | CRUD + event-driven | `atlas_runtime/audit_service.py` | role-match (same lock/conn/emit pattern) |
| `atlas_runtime/policy.py` | utility | request-response | `atlas_runtime/audit_service.py` (emit on failure) | partial-match |
| `atlas_runtime/subagent_service.py` | service | event-driven | `atlas_audit/__init__.py` (on_subagent_stop) | exact (same subagent_run event emission) |
| `atlas_runtime/cli/__init__.py` | config | — | `atlas_audit/__init__.py` (`__version__` init) | structural |
| `atlas_runtime/cli/main.py` | controller | request-response | `atlas_runtime/audit_service.py` (public API shape) | partial-match |
| `tests/test_mission_service.py` | test | CRUD | `tests/test_audit_service.py` | exact |
| `tests/test_run_service.py` | test | CRUD + event-driven | `tests/test_audit_service.py` | exact |
| `tests/test_policy.py` | test | request-response | `tests/test_audit_service.py` | role-match |
| `tests/test_cli.py` | test | request-response | `tests/test_audit_service.py` | role-match |
| `pyproject.toml` | config | — | `services/agent-runtime/pyproject.toml` | exact |

---

## Pattern Assignments

### `atlas_runtime/mission_service.py` (service, CRUD)

**Analog:** `services/agent-runtime/atlas_runtime/audit_service.py`

**Imports pattern** (audit_service.py lines 17-27):
```python
from __future__ import annotations

import datetime
import json
import sqlite3
import threading
import uuid
from typing import Optional

from atlas_core.schemas.core import Mission
from atlas_runtime.audit_service import emit
```

**Function signature pattern** (audit_service.py lines 63-77 — keyword-only args after `*`):
```python
def create_mission(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    title: str,
    intent: str = "",
    project: str = "",
) -> Mission:
```

**Core CRUD + lock pattern** (audit_service.py lines 156-172):
```python
# Step 1: Construct Pydantic model first — validates before any SQL
mission = Mission(title=title, intent=intent, project=project)
row = mission.model_dump()

# Step 2: Acquire lock, then write transactionally
with lock:
    with conn:  # BEGIN … COMMIT on success, ROLLBACK on exception
        conn.execute(
            "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at) "
            "VALUES (:id,:title,:intent,:status,:project,:created_at,:updated_at)",
            row,
        )
# No emit on create — no run_id exists yet
return mission
```

**Read-back pattern** (audit_service.py lines 185-206 — SELECT with column mapping):
```python
def get_mission(conn: sqlite3.Connection, mission_id: str) -> Optional[Mission]:
    cursor = conn.execute(
        "SELECT * FROM missions WHERE id=?", (mission_id,)
    )
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    if row is None:
        return None
    return Mission(**dict(zip(cols, row)))
```

**State guard pattern** (applied before every mutating function — derived from RESEARCH.md Pattern 1):
```python
# Read current state before any UPDATE
row = conn.execute("SELECT status FROM missions WHERE id=?", (mission_id,)).fetchone()
if row is None:
    raise ValueError(f"Mission {mission_id!r} not found")
if row[0] not in ("pending",):      # ← adjust per valid source states
    raise ValueError(f"Cannot transition mission in state {row[0]!r}")
```

**Emit-after-lock pattern** (RESEARCH.md Pattern 2 — avoids deadlock):
```python
# Step 1: Update state under lock
with lock:
    with conn:
        conn.execute("UPDATE missions SET status=?, updated_at=? WHERE id=?", (...))

# Step 2: Emit OUTSIDE lock — emit() acquires lock internally (audit_service.py line 157)
emit(conn, lock, run_id=run_id, event_type="tool_call", data={"transition": "..."})
```

---

### `atlas_runtime/run_service.py` (service, CRUD + event-driven)

**Analog:** `services/agent-runtime/atlas_runtime/audit_service.py`

**Imports pattern** (same as mission_service.py plus atlas_audit):
```python
from __future__ import annotations

import datetime
import sqlite3
import threading
from typing import Literal, Optional

from atlas_core.schemas.core import Run
from atlas_runtime.audit_service import emit
```

**Dual-table atomic update pattern** (RESEARCH.md Pattern 2 — both runs + missions updated atomically):
```python
with lock:
    with conn:  # Both UPDATEs commit together or roll back together
        conn.execute(
            "UPDATE runs SET status=?, finished_at=?, summary=? WHERE id=?",
            (status, now, summary, run_id),
        )
        conn.execute(
            "UPDATE missions SET status=?, updated_at=? WHERE id=?",
            (status, now, mission_id),
        )

# Emit AFTER releasing lock (audit_service.py line 157 re-acquires lock)
emit(conn, lock, run_id=run_id, event_type="tool_call", data={"transition": status, ...})
```

**atlas_audit plugin wiring** (atlas_audit/__init__.py lines 55-64 + 88-93):
```python
# Called by start_run() after inserting run row, before Hermes loop
import atlas_audit
atlas_audit.set_connection(conn)          # inject persistent connection
atlas_audit.on_session_start(
    session_id=session_id or run.id,
    run_id=run.id,
)
```

**FK pre-check pattern** (conftest.py lines 61-76 shows the required row structure):
```python
# Verify mission exists and is in a valid source state before INSERT into runs
row = conn.execute(
    "SELECT status FROM missions WHERE id=?", (mission_id,)
).fetchone()
if row is None:
    raise ValueError(f"Mission {mission_id!r} not found")
if row[0] != "pending":
    raise ValueError(f"Cannot start run for mission in state {row[0]!r}")
```

**Run INSERT column order** (migration 0001_core.sql lines 15-23):
```python
conn.execute(
    "INSERT INTO runs(id,mission_id,session_id,status,started_at,finished_at,summary) "
    "VALUES (:id,:mission_id,:session_id,:status,:started_at,:finished_at,:summary)",
    run.model_dump(),
)
```

---

### `atlas_runtime/policy.py` (utility, request-response)

**Analog:** No direct analog in codebase. Pattern derived from stdlib pathlib and emit() for failure events.

**Imports pattern:**
```python
from __future__ import annotations

import pathlib
import sqlite3
import threading
from dataclasses import dataclass
from typing import Optional

from atlas_runtime.audit_service import emit
```

**PolicyDecision dataclass** (RESEARCH.md Pattern 3):
```python
@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
```

**Cross-platform boundary check** (RESEARCH.md Pattern 3 — Pitfall 3 fix applied):
```python
def check_workspace_boundary(
    target_path: str,
    workspace_root: str,
) -> PolicyDecision:
    """Cross-platform path boundary enforcement (RUNTIME-07).

    Uses pathlib.Path.resolve() for Windows and POSIX path normalization.
    Resolves target relative to workspace_root to prevent CWD-escape attacks.
    """
    try:
        resolved_root = pathlib.Path(workspace_root).resolve()
        # Resolve relative to root — prevents ../../etc/passwd CWD escape
        resolved_target = (resolved_root / target_path).resolve()
        resolved_target.relative_to(resolved_root)  # raises ValueError if outside
        return PolicyDecision(allowed=True, reason="within_workspace")
    except ValueError:
        return PolicyDecision(
            allowed=False,
            reason=f"path_outside_workspace: {target_path!r} not under {workspace_root!r}",
        )
```

**Failure emit pattern** (success criterion 6 — emit on rejection; audit_service.py emit() signature):
```python
def check_workspace_boundary_and_emit(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    target_path: str,
    workspace_root: str,
) -> PolicyDecision:
    decision = check_workspace_boundary(target_path, workspace_root)
    if not decision.allowed:
        emit(
            conn, lock,
            run_id=run_id,
            event_type="failure",
            data={"reason": decision.reason, "target_path": target_path},
            policy_result=decision.reason,
        )
    return decision
```

**Tool allowlist check** (D-008 — reject unclassified tools):
```python
def check_tool_allowed(
    tool_name: str,
    allowed_tools: list[str],
) -> PolicyDecision:
    if tool_name in allowed_tools:
        return PolicyDecision(allowed=True, reason="tool_in_allowlist")
    return PolicyDecision(
        allowed=False,
        reason=f"tool_not_allowed: {tool_name!r} not in allowlist",
    )
```

---

### `atlas_runtime/subagent_service.py` (service, event-driven — stub)

**Analog:** `services/agent-runtime/atlas_audit/__init__.py` — specifically `on_subagent_stop()` (lines 270-318)

**Imports pattern** (atlas_audit/__init__.py lines 19-28):
```python
from __future__ import annotations

import sqlite3
import threading
from typing import Any

from atlas_runtime.audit_service import emit
```

**Subagent dispatch stub pattern** (analog: on_subagent_stop lines 270-318; RESEARCH.md Pattern 4):
```python
def dispatch_subagent(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: str,
    role: str,
    model_tier: str = "sonnet",
    allowed_tools: list[str] | None = None,
    autonomy_level: str = "supervised",
    token_budget: int = 4096,
) -> None:
    """Stub subagent dispatch — emits subagent_run AuditEvent (RUNTIME-06).

    Phase 5: No real subagent spawning. Emits governance envelope only.
    """
    payload = {
        "role": role,
        "model_tier": model_tier,
        "allowed_tools": allowed_tools or [],
        "autonomy_level": autonomy_level,
        "token_budget": token_budget,
    }
    # emit() handles JSON serialization and secret redaction (D-013)
    emit(
        conn, lock,
        run_id=run_id,
        event_type="subagent_run",
        data=payload,
    )
```

**Fail-open error guard pattern** (atlas_audit/__init__.py lines 141-179 — every hook wraps in try/except):
```python
    except Exception as exc:
        logger.warning("subagent_service: dispatch_subagent failed: %s", exc)
```

---

### `atlas_runtime/cli/__init__.py` (config)

**Analog:** `services/agent-runtime/atlas_audit/__init__.py` (lines 29-31)

**Pattern** (minimal init with version):
```python
"""ATLAS runtime CLI entry point package."""
__version__ = "0.1.0"
```

---

### `atlas_runtime/cli/main.py` (controller, request-response)

**Analog:** `services/agent-runtime/atlas_runtime/audit_service.py` (public API function structure)

**Imports pattern:**
```python
from __future__ import annotations

import sqlite3
import pathlib

import typer

from atlas_runtime import mission_service, run_service
```

**Typer app structure** (RESEARCH.md Pattern 5):
```python
app = typer.Typer()
mission_app = typer.Typer(name="mission")
app.add_typer(mission_app, name="mission")

@mission_app.command("create")
def create(
    title: str = typer.Option(..., "--title", help="Mission title"),
    intent: str = typer.Option("", "--intent", help="Mission intent"),
) -> None:
    """Create a Mission and print its ID."""
    # CLI handlers: thin wrappers only — no SQL, no emit() directly
    conn = _get_connection()
    lock = _get_lock()
    mission = mission_service.create_mission(conn, lock, title=title, intent=intent)
    typer.echo(mission.id)
```

**Connection factory** (consistent with audit_service.py dependency injection — conn/lock never global in service layer):
```python
def _get_connection() -> sqlite3.Connection:
    """Return a file-backed SQLite connection with WAL + FK enabled."""
    db_path = pathlib.Path.home() / ".atlas" / "atlas.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
```

---

### `tests/test_mission_service.py` (test, CRUD)

**Analog:** `services/agent-runtime/tests/test_audit_service.py`

**Fixture usage pattern** (test_audit_service.py lines 23-46 — fixtures from conftest.py injected by name):
```python
def test_create_mission(db, lock):
    """create_mission() persists a row in missions table with correct title."""
    from atlas_runtime.mission_service import create_mission

    mission = create_mission(db, lock, title="Test Mission", intent="do X")

    row = db.execute(
        "SELECT title, status FROM missions WHERE id=?", (mission.id,)
    ).fetchone()
    assert row is not None
    assert row[0] == "Test Mission"
    assert row[1] == "pending"
```

**Parametrize pattern** (test_audit_service.py lines 133-156):
```python
@pytest.mark.parametrize("status", ["succeeded", "failed"])
def test_complete_run_terminal_states(db, lock, status):
    """complete_run() accepts both terminal status values."""
    ...
```

**ValueError guard test pattern** (test_audit_service.py lines 164-173 — verify invalid transition raises):
```python
def test_cancel_already_succeeded_raises(db, lock):
    """cancel_run() on a succeeded run raises ValueError — no silent no-op."""
    with pytest.raises(ValueError, match="Cannot"):
        run_service.cancel_run(db, lock, run_id=..., mission_id=...)
```

**Row count assertion pattern** (test_audit_service.py lines 43-51):
```python
count = db.execute(
    "SELECT COUNT(*) FROM missions WHERE id=?", (mission.id,)
).fetchone()[0]
assert count == 1
```

---

### `tests/test_run_service.py` (test, CRUD + event-driven)

**Analog:** `services/agent-runtime/tests/test_audit_service.py`

**Pattern:** Same fixture injection (`db`, `lock`). Also needs a `mission_id` fixture because run tests must insert a mission first (conftest.py `run_id` fixture at lines 51-77 shows the pattern):

```python
# conftest.py run_id fixture pattern — test_run_service.py needs mission_id too
@pytest.fixture(name="mission_id")
def mission_id_fixture(db):
    import datetime, uuid
    mid = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (mid, "test-mission", "", "pending", "", now, now),
    )
    db.commit()
    return mid
```

**Audit row assertion after emit** (test_audit_service.py lines 43-51):
```python
def test_start_run_emits_task_started(db, lock, mission_id):
    run = run_service.start_run(db, lock, mission_id=mission_id)
    count = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=?", (run.id,)
    ).fetchone()[0]
    assert count >= 1
```

---

### `tests/test_policy.py` (test, request-response)

**Analog:** `services/agent-runtime/tests/test_audit_service.py` (structure); no fixtures needed for pure path tests.

**Parametrize pattern for RUNTIME-07** (test_audit_service.py lines 133-156 + RESEARCH.md requirement):
```python
import pytest
import pathlib
from atlas_runtime.policy import check_workspace_boundary, PolicyDecision

@pytest.mark.parametrize("target,expected_allowed", [
    # Linux-style path within workspace
    ("subdir/file.txt", True),
    # Linux-style traversal attempt
    ("../outside/file.txt", False),
    # Absolute path outside workspace (Windows-style string — tests conversion boundary)
    ("C:\\Users\\other\\file.txt", False),
    # Absolute path inside workspace root (POSIX string)
    (str(pathlib.Path.home()), False),   # only passes if home IS the workspace root
])
def test_workspace_boundary(tmp_path, target, expected_allowed):
    """Policy engine accepts in-workspace paths and rejects out-of-workspace paths.
    Uses str inputs (not Path objects) to test the string-to-Path conversion boundary.
    RUNTIME-07: must pass on both Windows (CI) and Linux.
    """
    decision = check_workspace_boundary(target, str(tmp_path))
    assert decision.allowed is expected_allowed
```

---

### `tests/test_cli.py` (test, request-response)

**Analog:** `services/agent-runtime/tests/test_audit_service.py` (structure)

**CliRunner pattern** (RESEARCH.md Pattern 5 — Typer testing):
```python
from typer.testing import CliRunner
from atlas_runtime.cli.main import app

runner = CliRunner()

def test_create_command_exits_zero(db, monkeypatch):
    """atlas mission create exits 0 and prints a UUID."""
    # Monkeypatch the connection factory so CLI uses the test in-memory db
    import atlas_runtime.cli.main as cli_main
    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    result = runner.invoke(app, ["mission", "create", "--title", "Test", "--intent", "do X"])
    assert result.exit_code == 0
    # Output should be a UUID4 (36 chars)
    assert len(result.output.strip()) == 36
```

---

### `pyproject.toml` (config modification)

**Analog:** `services/agent-runtime/pyproject.toml` (existing file, lines 1-24)

**Current state** (lines 1-24 — the full file):
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "atlas-runtime"
version = "0.1.0"
description = "ATLAS agent-runtime service layer"
requires-python = ">=3.11"
dependencies = [
    "atlas-core",
]

[project.optional-dependencies]
dev = ["pytest>=9.0"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.hatch.build.targets.wheel]
packages = ["atlas_runtime", "atlas_audit"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Required additions** (RESEARCH.md Pattern 5 + standard stack):
```toml
# Add after [project.optional-dependencies]:
[project.scripts]
atlas = "atlas_runtime.cli.main:app"

# Modify [project] dependencies to add typer:
dependencies = [
    "atlas-core",
    "typer>=0.25.0",
]

# Modify dev optional-dependencies to add pytest-cov:
[project.optional-dependencies]
dev = ["pytest>=9.0", "pytest-cov>=7.0"]

# Add coverage configuration:
[tool.coverage.run]
branch = true
source = ["atlas_runtime"]

[tool.coverage.report]
fail_under = 80
```

---

## Shared Patterns

### Lock + Connection Injection (applies to all service files)

**Source:** `services/agent-runtime/atlas_runtime/audit_service.py` lines 63-66
**Apply to:** `mission_service.py`, `run_service.py`, `subagent_service.py`

All public service functions receive `conn` and `lock` as positional args, all domain-specific args as keyword-only (after `*`). No global connection or lock state in the service layer.

```python
def service_function(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    # domain args here
) -> ReturnType:
```

### Pydantic-First Write Guard (applies to all service files)

**Source:** `services/agent-runtime/atlas_runtime/audit_service.py` lines 117-128
**Apply to:** `mission_service.py`, `run_service.py`

Construct the Pydantic model BEFORE any SQL. ValidationError propagates to caller; no SQL executes. Then call `model_dump()` to get the INSERT dict.

```python
# Pydantic validates first
model = SomeModel(field=value)
row = model.model_dump()  # datetime → ISO 8601 via field_serializer

with lock:
    with conn:
        conn.execute("INSERT INTO table VALUES (:id, :field)", row)
```

### Emit-After-Lock (applies to all service files that call emit)

**Source:** `services/agent-runtime/atlas_runtime/audit_service.py` line 157 (`with lock:` inside emit)
**Apply to:** `mission_service.py`, `run_service.py`, `subagent_service.py`, `policy.py` (failure events)

Never call `emit()` while holding the lock. `emit()` calls `with lock:` internally — holding the lock before calling emit causes deadlock. Pattern: exit the `with lock:` block, then call `emit()`.

```python
with lock:
    with conn:
        conn.execute("UPDATE ...")  # state change under lock
# lock is released here
emit(conn, lock, ...)              # emit re-acquires lock internally
```

### Frozen Model Pattern (applies to all files using Mission/Run)

**Source:** `packages/atlas-core/atlas_core/schemas/core.py` lines 40, 63 (`frozen=True`)
**Apply to:** All files that hold Mission or Run objects

Pydantic models are frozen. Never mutate in place. Use `model.model_copy(update={...})` for in-memory changes. For persisted changes, always UPDATE the DB row and re-fetch.

### Test Fixture Reuse (applies to all test files)

**Source:** `services/agent-runtime/tests/conftest.py` lines 29-83
**Apply to:** All test files in `tests/`

Import nothing from conftest — pytest injects `db`, `run_id`, `lock` fixtures by name. The `db` fixture provides in-memory SQLite with WAL + FK + migration applied. The `run_id` fixture provides a pre-seeded mission + run row for FK-safe audit event tests.

```python
# Test files: just use fixture names as parameters
def test_something(db, lock):           # db + lock only
def test_with_run(db, run_id, lock):    # existing run_id from conftest
```

---

## No Analog Found

All files have analogs. The following use partial analogs (same project, different role):

| File | Role | Closest Analog | Gap |
|---|---|---|---|
| `atlas_runtime/policy.py` | utility | `audit_service.py` (emit pattern only) | No existing policy/guard module in codebase; pathlib logic is novel |
| `atlas_runtime/cli/main.py` | controller | `audit_service.py` (function shape) | No existing Typer/Click CLI in codebase; Typer subapp pattern has no direct analog |

For these two files, planner should use RESEARCH.md Pattern 3 (policy) and Pattern 5 (Typer CLI) as the specification.

---

## Metadata

**Analog search scope:** `services/agent-runtime/`, `packages/atlas-core/`, `infra/migrations/`
**Files read:** 7 (audit_service.py, atlas_audit/__init__.py, tests/conftest.py, tests/test_audit_service.py, pyproject.toml, core.py, 0001_core.sql)
**Pattern extraction date:** 2026-06-07
