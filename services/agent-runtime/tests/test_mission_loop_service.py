from __future__ import annotations

import sqlite3
import threading

from atlas_runtime import mission_loop_service, mission_service, run_service
from atlas_runtime.agents import RunOutcome


def _mission(db: sqlite3.Connection, lock: threading.Lock, intent: str = "ship it") -> str:
    return mission_service.create_mission(db, lock, title="goal", intent=intent).id


def _finish(db: sqlite3.Connection, lock: threading.Lock, mission_id: str, session_id=None):
    run = run_service.start_run(db, lock, mission_id=mission_id, session_id=session_id)
    run_service.complete_run(
        db, lock, run_id=run.id, mission_id=mission_id, status="succeeded", summary="attempt"
    )
    return run


def test_continue_reopens_same_mission_and_records_receipt(db, lock) -> None:
    mission_id = _mission(db, lock)
    mission_loop_service.configure_loop(db, lock, mission_id=mission_id, max_runs=3)
    run = _finish(db, lock, mission_id)

    decision = mission_loop_service.evaluate_after_run(
        db,
        lock,
        mission_id=mission_id,
        run_id=run.id,
        run_status="succeeded",
        judge=lambda *_: ("continue", "more work", False, "p", "m"),
    )

    assert decision.action == "continue"
    assert db.execute("SELECT status FROM missions WHERE id=?", (mission_id,)).fetchone()[0] == "pending"
    row = db.execute(
        "SELECT verdict,reason,model_provider,model_id FROM run_judgements WHERE run_id=?",
        (run.id,),
    ).fetchone()
    assert row == ("continue", "more work", "p", "m")


def test_done_finishes_without_reopening(db, lock) -> None:
    mission_id = _mission(db, lock)
    mission_loop_service.configure_loop(db, lock, mission_id=mission_id)
    run = _finish(db, lock, mission_id)
    decision = mission_loop_service.evaluate_after_run(
        db, lock, mission_id=mission_id, run_id=run.id, run_status="succeeded",
        judge=lambda *_: ("done", "verified", False, "p", "m"),
    )
    assert decision.action == "done"
    assert mission_loop_service.get_loop(db, mission_id)["state"] == "done"
    assert db.execute("SELECT status FROM missions WHERE id=?", (mission_id,)).fetchone()[0] == "succeeded"


def test_budget_exhaustion_is_hard_stop(db, lock) -> None:
    mission_id = _mission(db, lock)
    mission_loop_service.configure_loop(db, lock, mission_id=mission_id, max_runs=1)
    run = _finish(db, lock, mission_id)
    decision = mission_loop_service.evaluate_after_run(
        db, lock, mission_id=mission_id, run_id=run.id, run_status="succeeded",
        judge=lambda *_: ("continue", "not yet", False, "p", "m"),
    )
    assert decision.action == "exhausted"
    assert mission_loop_service.get_loop(db, mission_id)["state"] == "exhausted"


def test_three_parse_failures_pause(db, lock) -> None:
    mission_id = _mission(db, lock)
    mission_loop_service.configure_loop(db, lock, mission_id=mission_id, max_runs=5)
    for expected_action in ("continue", "continue", "paused"):
        run = _finish(db, lock, mission_id)
        decision = mission_loop_service.evaluate_after_run(
            db, lock, mission_id=mission_id, run_id=run.id, run_status="succeeded",
            judge=lambda *_: ("continue", "invalid judge output", True, "p", "m"),
        )
        assert decision.action == expected_action
    assert mission_loop_service.get_loop(db, mission_id)["state"] == "paused"


def test_failed_run_stops_without_judge(db, lock) -> None:
    mission_id = _mission(db, lock)
    mission_loop_service.configure_loop(db, lock, mission_id=mission_id)
    run = run_service.start_run(db, lock, mission_id=mission_id)
    run_service.complete_run(db, lock, run_id=run.id, mission_id=mission_id, status="failed", summary="boom")
    called = False

    def judge(*_):
        nonlocal called
        called = True
        return "done", "", False, "p", "m"

    decision = mission_loop_service.evaluate_after_run(
        db, lock, mission_id=mission_id, run_id=run.id, run_status="failed", judge=judge
    )
    assert decision.action == "stopped"
    assert called is False
    assert mission_loop_service.get_loop(db, mission_id)["state"] == "failed"


def test_duplicate_evaluation_does_not_duplicate_receipt(db, lock) -> None:
    mission_id = _mission(db, lock)
    mission_loop_service.configure_loop(db, lock, mission_id=mission_id)
    run = _finish(db, lock, mission_id)
    def judge(*_):
        return "done", "yes", False, "p", "m"
    mission_loop_service.evaluate_after_run(
        db, lock, mission_id=mission_id, run_id=run.id, run_status="succeeded", judge=judge
    )
    mission_loop_service.evaluate_after_run(
        db, lock, mission_id=mission_id, run_id=run.id, run_status="succeeded", judge=judge
    )
    assert db.execute("SELECT COUNT(*) FROM run_judgements WHERE run_id=?", (run.id,)).fetchone()[0] == 1


def test_worker_chain_creates_two_runs_then_stops_on_done(db, lock, monkeypatch) -> None:
    from atlas_runtime import agents
    from atlas_runtime.cli import main as cli_main

    mission_id = _mission(db, lock, intent="finish the objective")
    mission_loop_service.configure_loop(db, lock, mission_id=mission_id, max_runs=4)
    first = run_service.start_run(db, lock, mission_id=mission_id)

    class _Agent:
        def execute(self, *args, **kwargs):
            return RunOutcome(status="succeeded", summary="attempt complete")

    verdicts = iter(
        [
            ("continue", "one more pass", False, "provider", "model"),
            ("done", "objective verified", False, "provider", "model"),
        ]
    )
    monkeypatch.setattr(agents, "get_agent", lambda _name: _Agent())
    monkeypatch.setattr(mission_loop_service, "_foundation_judge", lambda *_: next(verdicts))

    outcome = cli_main._execute_run_chain(
        db, lock, agent_name="native", mission_id=mission_id, run_id=first.id
    )

    assert outcome.status == "succeeded"
    assert db.execute("SELECT COUNT(*) FROM runs WHERE mission_id=?", (mission_id,)).fetchone()[0] == 2
    assert db.execute(
        "SELECT COUNT(*) FROM run_judgements WHERE mission_id=?", (mission_id,)
    ).fetchone()[0] == 2
    assert mission_loop_service.get_loop(db, mission_id)["state"] == "done"
