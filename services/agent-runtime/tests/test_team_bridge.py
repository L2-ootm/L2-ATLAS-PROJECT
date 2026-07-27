"""Team bridge tests — the `atlas_team` tool contract (CASE-05).

atlas_audit's connection/session state is injected directly (its documented
test path, mirroring test_actor_bridge); the detached worker launch is
monkeypatched so no subprocess spawns.
"""
from __future__ import annotations

import json
import sqlite3
import threading

import pytest

import atlas_audit
from atlas_runtime import team_bridge, team_run_service, team_service


class _Agent:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id


@pytest.fixture()
def bound(db: sqlite3.Connection, lock: threading.Lock, run_id: str):
    atlas_audit.set_connection(db)
    atlas_audit.on_session_start(session_id="sess-1", run_id=run_id)
    yield _Agent("sess-1"), run_id
    atlas_audit.set_connection(None)


@pytest.fixture()
def team(db: sqlite3.Connection, lock: threading.Lock) -> dict:
    researcher = team_service.create_preset(
        db, lock, name="researcher", role_label="researcher",
        goal_template="Research {topic}.",
    )
    writer = team_service.create_preset(
        db, lock, name="writer", role_label="writer", goal_template="Write it up.",
    )
    created = team_service.create_team(db, lock, name="content-team")
    return team_service.set_team_members(
        db, lock, created["id"], [researcher["id"], writer["id"]]
    )


def _launched(monkeypatch) -> list[str]:
    launched: list[str] = []

    def _fake_launch(team_run_id, **kw):  # noqa: ANN001
        launched.append(team_run_id)
        return 4242

    monkeypatch.setattr(
        "atlas_runtime.team_run_worker.launch_team_run_worker", _fake_launch
    )
    return launched


def test_list_shows_teams_and_their_roster(bound, team) -> None:
    out = json.loads(team_bridge.atlas_team_tool(op="list"))
    assert out["ok"] is True
    assert [t["name"] for t in out["teams"]] == ["content-team"]
    assert [m["role_label"] for m in out["teams"][0]["members"]] == ["researcher", "writer"]


def test_list_with_no_teams_explains_where_they_come_from(bound) -> None:
    out = json.loads(team_bridge.atlas_team_tool(op="list"))
    assert out["ok"] is True
    assert out["teams"] == []
    assert "operator" in out["note"]


def test_run_starts_a_detached_worker_and_returns_immediately(
    bound, team, monkeypatch
) -> None:
    agent, _ = bound
    launched = _launched(monkeypatch)
    out = json.loads(
        team_bridge.atlas_team_tool(
            op="run", team_id=team["id"], message="draft the release notes",
            parent_agent=agent,
        )
    )
    assert out["ok"] is True
    assert out["status"] == "queued"
    assert launched == [out["team_run_id"]]


def test_run_anchors_the_team_run_to_the_calling_run(bound, team, monkeypatch) -> None:
    agent, run_id = bound
    _launched(monkeypatch)
    out = json.loads(
        team_bridge.atlas_team_tool(
            op="run", team_id=team["id"], message="go", parent_agent=agent
        )
    )
    stored = team_run_service.get_team_run(atlas_audit.get_connection(), out["team_run_id"])
    assert stored["parent_run_id"] == run_id


def test_run_failing_to_launch_does_not_leave_a_queued_orphan(
    bound, team, monkeypatch
) -> None:
    """A team run nothing owns is exactly the stale wait this must not create."""
    agent, _ = bound
    monkeypatch.setattr(
        "atlas_runtime.team_run_worker.launch_team_run_worker", lambda *a, **k: None
    )
    out = json.loads(
        team_bridge.atlas_team_tool(
            op="run", team_id=team["id"], message="go", parent_agent=agent
        )
    )
    assert out["ok"] is False
    stored = team_run_service.get_team_run(atlas_audit.get_connection(), out["team_run_id"])
    assert stored["status"] == "failed"


def test_run_requires_a_team_and_a_message(bound, team) -> None:
    no_team = json.loads(team_bridge.atlas_team_tool(op="run", message="go"))
    no_message = json.loads(team_bridge.atlas_team_tool(op="run", team_id=team["id"]))
    assert no_team["ok"] is False and "team_id" in no_team["error"]
    assert no_message["ok"] is False and "kickoff message" in no_message["error"]


def test_run_on_a_team_with_no_members_is_a_named_failure(bound, db, lock) -> None:
    empty = team_service.create_team(db, lock, name="empty-team")
    out = json.loads(
        team_bridge.atlas_team_tool(op="run", team_id=empty["id"], message="go")
    )
    assert out["ok"] is False
    assert "no members" in out["error"]


def test_messages_pages_from_a_cursor(bound, team, monkeypatch) -> None:
    agent, _ = bound
    _launched(monkeypatch)
    started = json.loads(
        team_bridge.atlas_team_tool(
            op="run", team_id=team["id"], message="kickoff text", parent_agent=agent
        )
    )
    conn, alock = atlas_audit.get_connection(), atlas_audit.get_lock()
    team_run_service.append_message(
        conn, alock, started["team_run_id"], round_no=1,
        sender_role="researcher", target="all", content="found three sources",
    )

    everything = json.loads(
        team_bridge.atlas_team_tool(op="messages", team_run_id=started["team_run_id"])
    )
    assert [m["content"] for m in everything["messages"]] == [
        "kickoff text", "found three sources",
    ]
    assert everything["next_since_seq"] == 2

    tail = json.loads(
        team_bridge.atlas_team_tool(
            op="messages", team_run_id=started["team_run_id"], since_seq=1
        )
    )
    assert [m["content"] for m in tail["messages"]] == ["found three sources"]


def test_cancel_is_idempotent(bound, team, monkeypatch) -> None:
    agent, _ = bound
    _launched(monkeypatch)
    started = json.loads(
        team_bridge.atlas_team_tool(
            op="run", team_id=team["id"], message="go", parent_agent=agent
        )
    )
    first = json.loads(
        team_bridge.atlas_team_tool(op="cancel", team_run_id=started["team_run_id"])
    )
    second = json.loads(
        team_bridge.atlas_team_tool(op="cancel", team_run_id=started["team_run_id"])
    )
    assert first["note"] == "cancelled"
    assert second["note"] == "already terminal"


def test_unknown_team_run_is_a_tool_error_not_an_exception(bound) -> None:
    for op in ("status", "messages", "cancel"):
        out = json.loads(team_bridge.atlas_team_tool(op=op, team_run_id="team-run-nope"))
        assert out["ok"] is False
        assert "unknown team run" in out["error"]


def test_unknown_op_is_reported(bound) -> None:
    out = json.loads(team_bridge.atlas_team_tool(op="delete"))
    assert out["ok"] is False
    assert "unknown op" in out["error"]


def test_tool_without_a_bound_connection_degrades(monkeypatch) -> None:
    monkeypatch.setattr(team_bridge, "_shared_state", lambda: (None, None))
    out = json.loads(team_bridge.atlas_team_tool(op="list"))
    assert out["ok"] is False
    assert "no ATLAS connection bound" in out["error"]


def test_composition_ops_are_not_exposed() -> None:
    """Team composition is operator configuration, deliberately out of reach."""
    ops = set(team_bridge.TOOL_SCHEMA["parameters"]["properties"]["op"]["enum"])
    assert ops == {"list", "run", "status", "messages", "cancel"}
