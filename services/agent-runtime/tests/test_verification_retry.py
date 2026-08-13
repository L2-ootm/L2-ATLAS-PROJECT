"""The enforced verification turn (WP-E).

`verification_gate` records that a run changed state and never checked it.
Recording is not fixing: the next run inherits a finding and the change it
describes is still unchecked. These tests cover the turn ATLAS spends acting on
its own verdict — when it fires, when it must not, and what it is allowed to
change about the run it corrects.

The fake harness leaves a real audit trail rather than only returning text,
because the trail is the only thing the gate reads. A fake that returns
"I tested it" would pass a test that proves nothing, which is the exact failure
mode the gate exists to catch.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading
import time
import uuid

from atlas_runtime import audit_service, verification_gate
from atlas_runtime.agents.native import NativeAtlasAgent
from atlas_runtime.audit_service import get_events_for_run


def _pending_mission(db: sqlite3.Connection) -> str:
    mid = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, ?, ?, 'pending', '', ?, ?)",
        (mid, "t", "do the thing", now, now),
    )
    db.commit()
    return mid


def _running_run(db: sqlite3.Connection, mission_id: str) -> str:
    rid = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, NULL, 'running', ?, NULL, '')",
        (rid, mission_id, now),
    )
    db.commit()
    return rid


class _TrailHarness:
    """A harness that leaves an audit trail, one scripted trail per turn.

    Each entry in `trails` is a list of (tool, args) pairs recorded as the
    native tool_requested/tool_completed shape when that turn runs.
    """

    def __init__(self, conn, lock, run_id, trails, *, responses=None, boom_on_turn=None):
        self._conn, self._lock, self._run_id = conn, lock, run_id
        self._trails = list(trails)
        self._responses = list(responses or [])
        self._boom_on_turn = boom_on_turn
        self.calls: list[str] = []

    def run_conversation(
        self,
        user_message: str,
        system_message=None,  # noqa: ANN001
        task_id=None,  # noqa: ANN001
        conversation_history=None,  # noqa: ANN001
        persist_user_message=None,  # noqa: ANN001
    ):
        turn = len(self.calls)
        self.calls.append(user_message)
        if self._boom_on_turn == turn:
            raise RuntimeError("harness exploded")
        trail = self._trails[turn] if turn < len(self._trails) else []
        for index, (tool, args) in enumerate(trail):
            _record_call(self._conn, self._lock, self._run_id, f"t{turn}-{index}", tool, args)
        response = (
            self._responses[turn] if turn < len(self._responses) else f"turn {turn} answer"
        )
        return {
            "final_response": response,
            "api_calls": 1,
            "completed": True,
            "failed": False,
            "error": None,
        }


def _record_call(conn, lock, run_id, call_id, tool, args, *, failed=False):
    audit_service.emit(
        conn, lock, run_id=run_id, event_type="tool_requested", tool_name=tool,
        data={"tool": tool, "call_id": call_id, "arguments": args},
    )
    audit_service.emit(
        conn, lock, run_id=run_id,
        event_type="tool_failed" if failed else "tool_completed", tool_name=tool,
        data={"tool": tool, "call_id": call_id, "is_error": failed},
    )


def _trail_agent(db, lock, run_id, trails, **kw):
    harness = _TrailHarness(db, lock, run_id, trails, **kw)
    return NativeAtlasAgent(agent_factory=lambda session_id: harness), harness


_WROTE = [("write_file", {"path": "src/thing.py"})]
_TESTED = [("terminal", {"command": "pytest -q"})]


def _retry_events(db, run_id):
    return [
        json.loads(event.data)
        for event in get_events_for_run(db, run_id)
        if event.event_type == "verification_retry"
    ]


# --- it fires, and it works -------------------------------------------------


def test_an_unverified_run_is_made_to_check_itself(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    """The point of the exercise: the gate's finding is acted on, not filed."""
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    agent, harness = _trail_agent(db, lock, rid, [_WROTE, _TESTED])

    agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="refactor it")

    assert len(harness.calls) == 2, "an unverified run must be given one more turn"
    assert "verification checkpoint" in harness.calls[1]
    # The demand names the change, so a generic answer cannot satisfy it.
    assert "src/thing.py" in harness.calls[1]

    assert verification_gate.classify_run(db, rid).state == "verified"
    completed = [e for e in _retry_events(db, rid) if e["phase"] == "completed"]
    assert completed and completed[0]["resolved"] is True
    assert completed[0]["state_before"] == "unverified"
    assert completed[0]["state_after"] == "verified"


def test_the_enforced_turn_does_not_rewrite_the_runs_answer(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    """The trail, not the story: the turn changes evidence, never the report."""
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    agent, _ = _trail_agent(
        db, lock, rid, [_WROTE, _TESTED],
        responses=["I refactored the parser.", "Tests pass."],
    )

    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="refactor it")

    assert outcome.summary == "I refactored the parser."


def test_the_demand_is_issued_once_even_when_ignored(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    """A model that will not verify on request is a finding, not a reason to loop."""
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    agent, harness = _trail_agent(db, lock, rid, [_WROTE, []])

    agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="refactor it")

    assert len(harness.calls) == 2
    completed = [e for e in _retry_events(db, rid) if e["phase"] == "completed"]
    assert completed and completed[0]["resolved"] is False
    assert completed[0]["state_after"] == "unverified"


# --- it stays out of the way ------------------------------------------------


def test_a_run_that_checked_itself_is_not_asked_again(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    agent, harness = _trail_agent(db, lock, rid, [_WROTE + _TESTED])

    agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="refactor it")

    assert len(harness.calls) == 1
    assert _retry_events(db, rid) == []


def test_a_read_only_run_is_not_asked_to_verify_nothing(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    agent, harness = _trail_agent(db, lock, rid, [[("read_file", {"path": "src/thing.py"})]])

    agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="what does this do?")

    assert len(harness.calls) == 1


def test_a_failing_check_is_not_re_demanded(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    """`contradicted` means a check ran and failed. Asking again argues, not verifies."""
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    harness = _TrailHarness(db, lock, rid, [])
    agent = NativeAtlasAgent(agent_factory=lambda session_id: harness)

    def _wrote_then_failed(*_a, **_kw):
        harness.calls.append("turn")
        _record_call(db, lock, rid, "w", "write_file", {"path": "src/a.py"})
        _record_call(db, lock, rid, "t", "terminal", {"command": "pytest -q"}, failed=True)
        return {"final_response": "done", "api_calls": 1, "completed": True,
                "failed": False, "error": None}

    harness.run_conversation = _wrote_then_failed  # type: ignore[method-assign]
    agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="refactor it")

    assert verification_gate.classify_run(db, rid).state == "contradicted"
    assert len(harness.calls) == 1


def test_the_enforced_turn_can_be_switched_off(
    db: sqlite3.Connection, lock: threading.Lock, monkeypatch
) -> None:
    monkeypatch.setenv("ATLAS_VERIFICATION_RETRY", "0")
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    agent, harness = _trail_agent(db, lock, rid, [_WROTE])

    agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="refactor it")

    assert len(harness.calls) == 1


def test_disabling_the_gate_disables_the_turn_built_on_it(
    db: sqlite3.Connection, lock: threading.Lock, monkeypatch
) -> None:
    monkeypatch.setenv("ATLAS_VERIFICATION_GATE", "0")
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    agent, harness = _trail_agent(db, lock, rid, [_WROTE])

    agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="refactor it")

    assert len(harness.calls) == 1


# --- it cannot make things worse --------------------------------------------


def test_a_cancelled_run_is_not_held_up_by_a_verification_turn(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    cancel = threading.Event()
    harness = _TrailHarness(db, lock, rid, [_WROTE])
    original = harness.run_conversation

    def _run_then_cancel(*a, **kw):
        result = original(*a, **kw)
        cancel.set()  # operator cancels while turn 1 is finishing
        return result

    harness.run_conversation = _run_then_cancel  # type: ignore[method-assign]
    agent = NativeAtlasAgent(agent_factory=lambda session_id: harness)

    agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="go", cancel_token=cancel)

    assert len(harness.calls) == 1


def test_a_run_out_of_time_does_not_start_another_turn(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    """The extra turn shares the run's budget; it never extends it.

    Driven through `_enforce_verification` with an explicit deadline rather than
    a tiny `max_runtime_s`, so the assertion is about the budget rule and not
    about whether a fake harness happens to outrun a millisecond.
    """
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    _record_call(db, lock, rid, "w", "write_file", {"path": "src/a.py"})
    harness = _TrailHarness(db, lock, rid, [])
    agent = NativeAtlasAgent(agent_factory=lambda session_id: harness)
    assert verification_gate.classify_run(db, rid).state == "unverified"

    agent._enforce_verification(
        db, lock, run_id=rid, agent=harness, system_message=None,
        deadline=time.monotonic() - 1.0,  # the run's budget is already gone
    )
    assert harness.calls == []

    # The budget is what stopped it, not a missing verdict: with time left, the
    # same state does produce the turn.
    agent._enforce_verification(
        db, lock, run_id=rid, agent=harness, system_message=None,
        deadline=time.monotonic() + 60.0,
    )
    assert len(harness.calls) == 1


def test_a_broken_verification_turn_leaves_the_run_alone(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    """A corrective that can fail a working run is worse than no corrective."""
    mid = _pending_mission(db)
    rid = _running_run(db, mid)
    agent, harness = _trail_agent(
        db, lock, rid, [_WROTE], responses=["I refactored the parser."], boom_on_turn=1,
    )

    outcome = agent.execute(db, lock, mission_id=mid, run_id=rid, prompt="refactor it")

    assert len(harness.calls) == 2, "the turn was attempted"
    assert outcome.status == "succeeded"
    assert outcome.summary == "I refactored the parser."
    assert [e for e in _retry_events(db, rid) if e["phase"] == "aborted"], (
        "a correction that did not land must say so in the trail"
    )
