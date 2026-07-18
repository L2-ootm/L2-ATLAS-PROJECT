"""Tests for team_run_service.py: the group-chat message log and buffer."""
from __future__ import annotations

import sqlite3
import threading

import pytest

from atlas_runtime import team_run_service, team_service


def _make_team(db: sqlite3.Connection, lock: threading.Lock) -> dict:
    researcher = team_service.create_preset(
        db, lock, name="researcher", role_label="researcher",
        goal_template="Research {topic}.",
    )
    writer = team_service.create_preset(
        db, lock, name="writer", role_label="writer", goal_template="Write it up.",
    )
    team = team_service.create_team(db, lock, name="content-team")
    return team_service.set_team_members(db, lock, team["id"], [researcher["id"], writer["id"]])


def test_parse_target_extracts_mention() -> None:
    target, content = team_run_service.parse_target("@writer: please draft the intro")
    assert target == "writer"
    assert content == "please draft the intro"


def test_parse_target_defaults_to_all() -> None:
    target, content = team_run_service.parse_target("no mention here")
    assert target == "all"
    assert content == "no mention here"


def test_is_done_signal() -> None:
    assert team_run_service.is_done_signal("done") is True
    assert team_run_service.is_done_signal("  DONE  ") is True
    assert team_run_service.is_done_signal("not done yet") is False


def test_create_team_run_seeds_kickoff_message(db: sqlite3.Connection, lock: threading.Lock) -> None:
    team = _make_team(db, lock)
    run = team_run_service.create_team_run(
        db, lock, team_id=team["id"], kickoff_message="Investigate the outage."
    )
    assert run["status"] == "queued"
    assert run["max_rounds"] == team_run_service.DEFAULT_MAX_ROUNDS
    messages = team_run_service.list_messages(db, run["id"])
    assert len(messages) == 1
    assert messages[0]["content"] == "Investigate the outage."
    assert messages[0]["target"] == "all"
    assert messages[0]["seq"] == 1


def test_create_team_run_rejects_empty_kickoff(db: sqlite3.Connection, lock: threading.Lock) -> None:
    team = _make_team(db, lock)
    with pytest.raises(ValueError):
        team_run_service.create_team_run(db, lock, team_id=team["id"], kickoff_message="   ")


def test_create_team_run_rejects_team_without_members(db: sqlite3.Connection, lock: threading.Lock) -> None:
    team = team_service.create_team(db, lock, name="empty-team")
    with pytest.raises(ValueError):
        team_run_service.create_team_run(db, lock, team_id=team["id"], kickoff_message="hi")


def test_create_team_run_rejects_out_of_range_max_rounds(db: sqlite3.Connection, lock: threading.Lock) -> None:
    team = _make_team(db, lock)
    with pytest.raises(ValueError):
        team_run_service.create_team_run(
            db, lock, team_id=team["id"], kickoff_message="hi", max_rounds=0
        )
    with pytest.raises(ValueError):
        team_run_service.create_team_run(
            db, lock, team_id=team["id"], kickoff_message="hi",
            max_rounds=team_run_service.MAX_ROUNDS_CAP + 1,
        )


def test_mark_running_then_finish_is_monotonic(db: sqlite3.Connection, lock: threading.Lock) -> None:
    team = _make_team(db, lock)
    run = team_run_service.create_team_run(db, lock, team_id=team["id"], kickoff_message="hi")
    assert team_run_service.mark_team_run_running(db, lock, run["id"]) is True
    assert team_run_service.mark_team_run_running(db, lock, run["id"]) is False  # already running
    assert team_run_service.finish_team_run(db, lock, run["id"], status="completed") is True
    assert team_run_service.finish_team_run(db, lock, run["id"], status="failed") is False
    refreshed = team_run_service.get_team_run(db, run["id"])
    assert refreshed["status"] == "completed"


def test_append_message_increments_seq_and_parses_mention(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    team = _make_team(db, lock)
    run = team_run_service.create_team_run(db, lock, team_id=team["id"], kickoff_message="hi")
    msg = team_run_service.append_message(
        db, lock, run["id"], round_no=1, sender_role="researcher",
        sender_actor_id="actor-1", content="@writer: findings are ready",
    )
    assert msg["seq"] == 2
    assert msg["target"] == "writer"
    assert msg["content"] == "findings are ready"


def test_build_inbox_filters_by_target_and_cursor(db: sqlite3.Connection, lock: threading.Lock) -> None:
    team = _make_team(db, lock)
    run = team_run_service.create_team_run(db, lock, team_id=team["id"], kickoff_message="kickoff")
    team_run_service.append_message(
        db, lock, run["id"], round_no=1, sender_role="researcher",
        sender_actor_id="actor-1", content="broadcast to everyone",
    )
    team_run_service.append_message(
        db, lock, run["id"], round_no=1, sender_role="researcher",
        sender_actor_id="actor-1", content="@writer: just for you",
    )
    writer_inbox = team_run_service.build_inbox(db, run["id"], role_label="writer", since_seq=0)
    assert [m["content"] for m in writer_inbox] == ["kickoff", "broadcast to everyone", "just for you"]

    reviewer_inbox = team_run_service.build_inbox(db, run["id"], role_label="reviewer", since_seq=0)
    assert [m["content"] for m in reviewer_inbox] == ["kickoff", "broadcast to everyone"]

    # cursor excludes already-seen messages
    later = team_run_service.build_inbox(db, run["id"], role_label="writer", since_seq=2)
    assert [m["content"] for m in later] == ["just for you"]


def test_render_inbox_formats_lines() -> None:
    inbox = [
        {"sender_role": "orchestrator", "sender_actor_id": None, "content": "kickoff"},
        {"sender_role": "researcher", "sender_actor_id": "actor-1", "content": "found it"},
    ]
    text = team_run_service.render_inbox(inbox)
    assert "[orchestrator]: kickoff" in text
    assert "[researcher]: found it" in text


def test_render_inbox_empty_is_empty_string() -> None:
    assert team_run_service.render_inbox([]) == ""
