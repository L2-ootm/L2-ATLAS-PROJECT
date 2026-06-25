"""Pytest configuration and shared fixtures for agent-runtime tests."""

# MIGRATION_PATH depth explanation:
# conftest.py lives at: services/agent-runtime/tests/conftest.py
# .parent        = services/agent-runtime/tests/
# .parent.parent = services/agent-runtime/
# .parent x3     = services/
# .parent x4     = <project root>
# So 4 parents up from __file__ = project root
# Then / "infra" / "migrations" / "0001_core.sql"
# Note: plan spec said 3 hops but was counting directory transitions, not .parent calls.
# Correct value is 4 (verified: migration exists at 4-hop path).

import pathlib
import sqlite3
import threading
import uuid

import pytest

MIGRATIONS_DIR = (
    pathlib.Path(__file__).parent.parent.parent.parent / "infra" / "migrations"
)


@pytest.fixture(name="db")
def db_fixture() -> sqlite3.Connection:  # type: ignore[return]
    """In-memory SQLite with WAL mode, FK enforcement, and ALL migrations applied.

    Applies every infra/migrations/*.sql in sorted order so the fixture reflects
    the current schema (project_id, provenance, registry, …) — the same path the
    fresh-machine bootstrap uses. Raises pytest.fail if no migrations are found,
    rather than silently returning an empty database (which would cause downstream
    tests to fail with misleading 'no such table' errors instead of a clear cause).
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migrations:
        pytest.fail(
            f"No migrations found in: {MIGRATIONS_DIR}\n"
            "Ensure infra/migrations/*.sql exist before running tests."
        )
    for sql_path in migrations:
        conn.executescript(sql_path.read_text(encoding="utf-8"))
    yield conn
    conn.close()


@pytest.fixture(name="run_id")
def run_id_fixture(db: sqlite3.Connection) -> str:
    """A stable run_id for test isolation.

    Inserts a minimal mission + run row into the in-memory DB so that
    FK constraints on audit_events.run_id and tool_calls.run_id are satisfied
    when PRAGMA foreign_keys = ON is active.
    """
    import datetime

    mission_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (mission_id, "test-mission", "", "pending", "", now, now),
    )
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, mission_id, None, "running", now, None, ""),
    )
    db.commit()

    return run_id


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    """A threading.Lock for audit_service concurrency tests."""
    return threading.Lock()


@pytest.fixture(name="surface_session")
def surface_session_fixture(db: sqlite3.Connection) -> str:
    """A persisted minimal surface_sessions row; yields its id.

    Mirrors the run_id fixture: inserts one valid 'starting' session so transition
    tests have a row to act on. Migration 0016 is applied by the all-migrations db
    fixture.
    """
    import datetime

    session_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    db.execute(
        "INSERT INTO surface_sessions"
        "(id, surface_kind, surface_session_id, workspace_kind, workspace_root, "
        "agent, model_provider, model_id, permission_mode, prompt_version, "
        "tool_catalog_version, context_policy_version, state, heartbeat_at, "
        "created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            session_id, "cli", "surf-1", "global", "/tmp/atlas",
            "atlas", "anthropic", "claude-opus-4", "ask", "1.0.0",
            "1.0.0", "1.0.0", "starting", now, now, now,
        ),
    )
    db.commit()

    return session_id


@pytest.fixture(name="mock_gh")
def mock_gh_fixture(monkeypatch):
    """Patch subprocess.run so the github adapter never shells out to real `gh`.

    Returns an installer: `mock_gh(stdout=..., returncode=..., stderr=...)`.
    Phase 10.0.4 tool-adapter tests use this to exercise the gh argv path and the
    honest-failure case (returncode != 0 -> ToolResult(ok=False)) without network.
    """
    import subprocess

    def _install(stdout: str = "{}", returncode: int = 0, stderr: str = ""):
        calls: list[list[str]] = []

        def fake_run(cmd, *a, **kw):  # noqa: ANN001
            calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

        monkeypatch.setattr(subprocess, "run", fake_run)
        return calls

    return _install


@pytest.fixture(name="mock_urlopen")
def mock_urlopen_fixture(monkeypatch):
    """Patch urllib.request.urlopen for the web_fetch / webhook_notify adapters.

    Returns an installer: `mock_urlopen(body=b"...", status=200)`. The fake
    response supports context-manager use and chunked `.read(n)` so the size-cap
    path in web_fetch is exercisable.
    """
    import urllib.request

    def _install(body: bytes = b"{}", status: int = 200, headers=None):  # noqa: ANN001
        class _Resp:
            def __init__(self) -> None:
                self._buf = body
                self._pos = 0
                self.status = status
                self.headers = headers or {"Content-Type": "application/json"}

            def read(self, n: int = -1) -> bytes:
                if n is None or n < 0:
                    chunk = self._buf[self._pos:]
                    self._pos = len(self._buf)
                    return chunk
                chunk = self._buf[self._pos:self._pos + n]
                self._pos += len(chunk)
                return chunk

            def getcode(self) -> int:
                return self.status

            def __enter__(self):  # noqa: ANN001
                return self

            def __exit__(self, *exc):  # noqa: ANN001
                return False

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())

    return _install


class _OfflineHarness:
    """Deterministic stand-in for the foundation AIAgent — no network. Returns a
    completed result so executor/daemon lifecycle tests resolve 'native' to a
    succeeding run without invoking the real harness or any provider."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    def run_conversation(self, user_message: str, system_message=None):  # noqa: ANN001
        return {
            "final_response": "[offline] native runtime executed",
            "messages": [],
            "api_calls": 0,
            "completed": True,
            "failed": False,
            "error": None,
        }


@pytest.fixture(autouse=True)
def _offline_native_harness(monkeypatch) -> None:
    """Autouse: never let the real native harness reach the network during tests.

    Patches the NativeAtlasAgent default factory to an offline echo harness. Tests
    that inject their own `agent_factory` bypass this entirely; lifecycle tests
    that resolve 'native' from the registry get the deterministic offline harness.
    """
    from atlas_runtime.agents import native

    monkeypatch.setattr(
        native,
        "_default_factory",
        lambda session_id, max_iterations, **_kw: _OfflineHarness(session_id),
    )
