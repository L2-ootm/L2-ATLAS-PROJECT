"""Tests for team_run_worker.py: the round-robin group-chat driver.

run_actor (real agent execution) is stubbed so these tests exercise the
scheduling/buffer logic — cursor tracking, DONE early-exit, max_rounds bound,
and failure handling — without needing a real provider or foundation.
"""
from __future__ import annotations

import sqlite3
import threading

import pytest

from atlas_runtime import actor_service, team_run_service, team_service, team_run_worker


def _make_team(db: sqlite3.Connection, lock: threading.Lock) -> dict:
    researcher = team_service.create_preset(
        db, lock, name="researcher", role_label="researcher",
        goal_template="Research the topic.",
    )
    writer = team_service.create_preset(
        db, lock, name="writer", role_label="writer", goal_template="Write it up.",
    )
    team = team_service.create_team(db, lock, name="content-team")
    return team_service.set_team_members(db, lock, team["id"], [researcher["id"], writer["id"]])


def _stub_run_actor(responses: list[str]):
    """Fake run_actor: completes the actor with the next scripted response."""
    calls = {"n": 0}

    def _fake(conn, lock, actor_id):
        content = responses[calls["n"]] if calls["n"] < len(responses) else "(no output)"
        calls["n"] += 1
        actor_service.mark_running(conn, lock, actor_id, pid=1)
        actor_service.complete_actor(conn, lock, actor_id, result_preview=content)
        return True

    return _fake


def test_run_team_run_exits_early_on_done_signal(
    db: sqlite3.Connection, lock: threading.Lock, monkeypatch
) -> None:
    team = _make_team(db, lock)
    run = team_run_service.create_team_run(
        db, lock, team_id=team["id"], kickoff_message="Investigate the outage.", max_rounds=5
    )
    monkeypatch.setattr(
        team_run_worker, "run_actor", _stub_run_actor(["some findings", "DONE"])
    )
    ok = team_run_worker.run_team_run(db, lock, run["id"])
    assert ok is True

    refreshed = team_run_service.get_team_run(db, run["id"])
    assert refreshed["status"] == "completed"
    assert refreshed["current_round"] == 1  # stopped within round 1, never reached round 2

    messages = team_run_service.list_messages(db, run["id"])
    # kickoff + researcher's finding + writer's DONE
    assert [m["content"] for m in messages] == [
        "Investigate the outage.", "some findings", "DONE",
    ]
    assert messages[1]["sender_role"] == "researcher"
    assert messages[2]["sender_role"] == "writer"


def test_run_team_run_exhausts_max_rounds_without_done(
    db: sqlite3.Connection, lock: threading.Lock, monkeypatch
) -> None:
    team = _make_team(db, lock)
    run = team_run_service.create_team_run(
        db, lock, team_id=team["id"], kickoff_message="hi", max_rounds=2
    )
    # Never emits DONE — 2 rounds x 2 members = 4 turns, then stop.
    monkeypatch.setattr(
        team_run_worker, "run_actor",
        _stub_run_actor(["r1", "w1", "r2", "w2"]),
    )
    ok = team_run_worker.run_team_run(db, lock, run["id"])
    assert ok is True
    refreshed = team_run_service.get_team_run(db, run["id"])
    assert refreshed["status"] == "completed"
    assert refreshed["current_round"] == 2
    messages = team_run_service.list_messages(db, run["id"])
    assert len(messages) == 5  # kickoff + 4 turns


def test_run_team_run_creates_anchor_mission_and_run(
    db: sqlite3.Connection, lock: threading.Lock, monkeypatch
) -> None:
    team = _make_team(db, lock)
    run = team_run_service.create_team_run(
        db, lock, team_id=team["id"], kickoff_message="hi", max_rounds=1
    )
    assert run["parent_run_id"] is None
    monkeypatch.setattr(team_run_worker, "run_actor", _stub_run_actor(["DONE"]))
    team_run_worker.run_team_run(db, lock, run["id"])
    refreshed = team_run_service.get_team_run(db, run["id"])
    assert refreshed["parent_run_id"] is not None
    anchor_run = db.execute(
        "SELECT status FROM runs WHERE id=?", (refreshed["parent_run_id"],)
    ).fetchone()
    assert anchor_run is not None
    assert anchor_run[0] == "succeeded"


def test_run_team_run_marks_failed_on_exception(
    db: sqlite3.Connection, lock: threading.Lock, monkeypatch
) -> None:
    team = _make_team(db, lock)
    run = team_run_service.create_team_run(db, lock, team_id=team["id"], kickoff_message="hi")

    def _boom(conn, lock, actor_id):
        raise RuntimeError("boom")

    monkeypatch.setattr(team_run_worker, "run_actor", _boom)
    ok = team_run_worker.run_team_run(db, lock, run["id"])
    assert ok is True
    refreshed = team_run_service.get_team_run(db, run["id"])
    assert refreshed["status"] == "failed"


def test_run_team_run_rejects_non_queued_run(db: sqlite3.Connection, lock: threading.Lock) -> None:
    team = _make_team(db, lock)
    run = team_run_service.create_team_run(db, lock, team_id=team["id"], kickoff_message="hi")
    team_run_service.mark_team_run_running(db, lock, run["id"], parent_run_id=None)
    assert team_run_worker.run_team_run(db, lock, run["id"]) is False


def test_run_team_run_missing_run_returns_false(db: sqlite3.Connection, lock: threading.Lock) -> None:
    assert team_run_worker.run_team_run(db, lock, "team-run-missing") is False
