"""Cooperative cancellation tests (SURF-06, AUD-01, plan 10.3-04).

Covers the executor/native watchdog cancel token (Task 1) and the tool-gate
short-circuit (Task 2). Cancellation is cooperative — it takes effect at the next
ATLAS-owned checkpoint and emits a terminal audited outcome; never a hard kill.
"""
import datetime
import threading
import uuid

import pytest

from atlas_runtime import run_executor
from atlas_runtime import tool_service
from atlas_runtime.agents.native import NativeAtlasAgent


def _mission_and_run(db, lock):
    from atlas_runtime import run_service

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    mission_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (mission_id, "m", "", "pending", "", now, now),
    )
    db.commit()
    run = run_service.start_run(db, lock, mission_id=mission_id)
    return mission_id, run.id


class _BlockingHarness:
    """Stand-in foundation harness whose run_conversation blocks until released,
    so the watchdog poll-join observes a still-running worker."""

    def __init__(self, release: threading.Event) -> None:
        self._release = release

    def run_conversation(self, user_message, system_message=None):  # noqa: ANN001
        self._release.wait(timeout=5)
        return {
            "final_response": "done",
            "messages": [],
            "api_calls": 0,
            "completed": True,
            "failed": False,
            "error": None,
        }


# ---------------------------------------------------------------------------
# Task 1 — executor / native watchdog cancel token
# ---------------------------------------------------------------------------


def test_no_token_path_unchanged(db, lock) -> None:
    """With cancel_token=None the run completes normally (no regression)."""
    mission_id, run_id = _mission_and_run(db, lock)
    release = threading.Event()
    release.set()  # harness returns immediately
    agent = NativeAtlasAgent(agent_factory=lambda session_id: _BlockingHarness(release))
    outcome = run_executor.execute_run(
        db, lock, agent=agent, mission_id=mission_id, run_id=run_id, prompt="hi"
    )
    assert outcome.status == "succeeded"
    assert outcome.stop_reason is None


def test_setting_token_yields_cancelled_outcome_and_audit(db, lock) -> None:
    mission_id, run_id = _mission_and_run(db, lock)
    release = threading.Event()  # never released — harness stays blocked
    cancel = threading.Event()
    cancel.set()  # pre-set: the first watchdog poll observes the cancel
    agent = NativeAtlasAgent(agent_factory=lambda session_id: _BlockingHarness(release))
    outcome = run_executor.execute_run(
        db, lock, agent=agent, mission_id=mission_id, run_id=run_id, prompt="hi",
        cancel_token=cancel,
    )
    assert outcome.status == "failed"
    assert outcome.stop_reason == "cancelled"
    row = db.execute(
        "SELECT event_type FROM audit_events WHERE event_type='run_cancelled' AND run_id=?",
        (run_id,),
    ).fetchone()
    assert row is not None


def test_cancel_wins_terminal_not_clobbered(db, lock) -> None:
    """If the run was already cancelled (status='cancelled'), execute_run's terminal
    complete_run raises ValueError and the cancelled state is preserved."""
    from atlas_runtime import run_service

    mission_id, run_id = _mission_and_run(db, lock)
    run_service.cancel_run(db, lock, run_id=run_id, mission_id=mission_id)

    release = threading.Event()
    release.set()
    agent = NativeAtlasAgent(agent_factory=lambda session_id: _BlockingHarness(release))
    run_executor.execute_run(
        db, lock, agent=agent, mission_id=mission_id, run_id=run_id, prompt="hi"
    )
    status = db.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()[0]
    assert status == "cancelled"


# ---------------------------------------------------------------------------
# Task 2 — tool-gate cancel short-circuit
# ---------------------------------------------------------------------------


def test_tool_gate_short_circuits_on_set_token(db, lock, monkeypatch) -> None:
    """A pre-set cancel token in ctx makes tool_service.invoke return a cancelled
    ToolResult, emit a tool_failed cancellation audit, and NOT run the adapter."""
    ran = {"flag": False}

    def _adapter(args, ctx):  # noqa: ANN001
        ran["flag"] = True
        from atlas_core.schemas.tool import ToolResult

        return ToolResult(tool_name="probe", ok=True, output="ran")

    _install_stub_tool(monkeypatch, "probe", _adapter, risk_level="read")

    cancel = threading.Event()
    cancel.set()
    result = tool_service.invoke(
        db, lock, tool_name="probe", mode="read_only", ctx={"cancel_token": cancel}
    )
    assert result.ok is False
    assert result.error == "cancelled"
    assert ran["flag"] is False
    row = db.execute(
        "SELECT data FROM audit_events WHERE event_type='tool_failed' AND tool_name='probe'"
    ).fetchone()
    assert row is not None and "cancelled" in row[0]


def test_tool_gate_unset_token_runs_normally(db, lock, monkeypatch) -> None:
    ran = {"flag": False}

    def _adapter(args, ctx):  # noqa: ANN001
        ran["flag"] = True
        from atlas_core.schemas.tool import ToolResult

        return ToolResult(tool_name="probe", ok=True, output="ran")

    _install_stub_tool(monkeypatch, "probe", _adapter, risk_level="read")

    result = tool_service.invoke(
        db, lock, tool_name="probe", mode="read_only", ctx={"cancel_token": threading.Event()}
    )
    assert result.ok is True
    assert ran["flag"] is True


def _install_stub_tool(monkeypatch, name, adapter, *, risk_level):
    """Patch the tool registry so `name` resolves to (manifest, adapter)."""
    from atlas_runtime.tools import registry as registry_mod

    class _Manifest:
        def __init__(self) -> None:
            self.name = name
            self.risk_level = risk_level

    class _Reg:
        def resolve(self, tool_name):  # noqa: ANN001
            assert tool_name == name
            return _Manifest(), adapter

    monkeypatch.setattr(registry_mod, "get_registry", lambda: _Reg())
