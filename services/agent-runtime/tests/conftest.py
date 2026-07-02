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
    # check_same_thread=False: the shared connection + threading.Lock is the
    # production contract (audit_service: "may be shared across threads with
    # check_same_thread=False"). Concurrency tests (broker at-most-once TOCTOU)
    # drive this connection from worker threads, so it must not be thread-affine.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
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


# ---------------------------------------------------------------------------
# Phase 10.5 — permission broker test helpers (Wave 0, RED-first).
#
# These callables seed the rows the broker contract tests act on: an *active*
# surface session, a surface-anchored *pending* approval, and a registered
# *approval channel*. They depend on the migration 0017 schema additions
# (surface_session_id/surface_kind/workspace_root/expiry_at/decision/nonce/
# args_normalized on tool_approvals, plus the approval_channels table) which
# Wave 1 introduces — so calling them before 0017 lands raises sqlite3.Operational
# Error. That is the intended RED state for the Wave 0 plan; the helpers are
# plain installer callables (not autouse fixtures) so conftest import never fails.
#
# Liveness is set PURELY by a column UPDATE on surface_sessions.state — NEVER by
# probing a PID for liveness (PID-signal probing is broken on Windows; see the
# PATTERNS "do NOT build" table). stdlib only (sqlite3 via the passed conn,
# datetime, uuid).
# ---------------------------------------------------------------------------


@pytest.fixture(name="make_active_session")
def make_active_session_fixture(db: sqlite3.Connection, surface_session: str):
    """Return a callable that flips the `surface_session` row to state='active'.

    Authority in the broker requires `surface_sessions.state == 'active'`
    (PERM-02). This sets it via a direct column UPDATE and returns the session id
    so a test can claim against an authoritative owner.
    """

    def _activate(*, surface_session_id: str | None = None) -> str:
        sid = surface_session_id or surface_session
        db.execute(
            "UPDATE surface_sessions SET state='active' WHERE id=?",
            (sid,),
        )
        db.commit()
        return sid

    return _activate


@pytest.fixture(name="seed_pending_approval")
def seed_pending_approval_fixture(db: sqlite3.Connection):
    """Return a callable that INSERTs a surface-anchored `pending` tool_approvals row.

    The INSERT references the migration-0017 surface columns
    (surface_session_id, surface_kind, workspace_root, expiry_at, nonce,
    args_normalized) alongside the base 0013 columns, so it is RED until Wave 1.
    Returns the new approval id.
    """
    import datetime

    def _seed(
        conn: sqlite3.Connection = None,  # noqa: ANN001 — accept positional conn for parity
        *,
        surface_session_id: str,
        surface_kind: str = "cli",
        nonce: str,
        expiry_at: str,
        tool_name: str = "workspace",
        workspace_root: str = "/tmp/atlas",
        risk_level: str = "write",
        args_normalized: str = "{}",
        reason: str | None = None,
    ) -> str:
        target = conn if conn is not None else db
        approval_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        target.execute(
            "INSERT INTO tool_approvals"
            "(id, tool_name, risk_level, args, summary, status, reason, result, "
            "run_id, requested_at, decided_at, "
            "surface_session_id, surface_kind, workspace_root, expiry_at, "
            "decision, nonce, args_normalized) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                approval_id, tool_name, risk_level, args_normalized, "", "pending",
                reason, None, "operator", now, None,
                surface_session_id, surface_kind, workspace_root, expiry_at,
                None, nonce, args_normalized,
            ),
        )
        target.commit()
        return approval_id

    return _seed


@pytest.fixture(name="register_test_channel")
def register_test_channel_fixture(db: sqlite3.Connection):
    """Return a callable that INSERTs an unrevoked `approval_channels` row.

    A headless ('api') surface only produces a pending approval when an
    unrevoked approval_channels row exists for its session (PERM-05 fail-closed).
    RED until Wave 1 creates the approval_channels table.
    """
    import datetime

    def _register(
        conn: sqlite3.Connection = None,  # noqa: ANN001
        *,
        surface_session_id: str,
        surface_kind: str = "api",
    ) -> str:
        target = conn if conn is not None else db
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        target.execute(
            "INSERT INTO approval_channels"
            "(surface_session_id, surface_kind, registered_at, revoked_at) "
            "VALUES (?,?,?,?)",
            (surface_session_id, surface_kind, now, None),
        )
        target.commit()
        return surface_session_id

    return _register


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
    from atlas_runtime import function_router
    from atlas_runtime.agents import native

    monkeypatch.setattr(
        native,
        "_default_factory",
        lambda session_id, max_iterations, **_kw: _OfflineHarness(session_id),
    )
    # The run-boundary side-task autoconfig writes into the operator's real
    # foundation config store; tests must never touch it.
    monkeypatch.setattr(
        function_router,
        "apply_autoconfig",
        lambda *_a, **_kw: {"applied": False, "tasks": {}, "reason": "test-offline"},
    )
