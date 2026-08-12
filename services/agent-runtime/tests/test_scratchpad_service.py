"""Tests for the agent scratchpad: TTL policies, sweeping, pinning, the tool."""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading

import pytest

from atlas_runtime import scratchpad_bridge, scratchpad_service


def test_write_derives_a_readable_id_and_converges(db, lock) -> None:
    first = scratchpad_service.write_entry(
        db, lock, title="Current plan", body="step 1", scope="global", ttl_policy="permanent"
    )
    assert first["id"] == "current-plan"
    second = scratchpad_service.write_entry(
        db, lock, title="Current plan", body="step 2", scope="global", ttl_policy="permanent"
    )
    assert second["id"] == "current-plan" and second["body"] == "step 2"
    assert len(scratchpad_service.list_entries(db)) == 1


def test_append_extends_the_body(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="Findings", body="one", scope="global", ttl_policy="permanent"
    )
    entry = scratchpad_service.write_entry(
        db, lock, title="Findings", body="two", scope="global", ttl_policy="permanent",
        append=True,
    )
    assert entry["body"] == "one\ntwo"


def test_run_scope_without_a_run_degrades(db, lock) -> None:
    # A run-scoped entry with no run id could never be swept by its own policy.
    entry = scratchpad_service.write_entry(db, lock, title="orphan", scope="run")
    assert entry["scope"] == "global"


def test_invalid_inputs_rejected(db, lock) -> None:
    with pytest.raises(scratchpad_service.ScratchpadError, match="kind"):
        scratchpad_service.write_entry(db, lock, title="x", kind="nonsense")
    with pytest.raises(scratchpad_service.ScratchpadError, match="ttl"):
        scratchpad_service.write_entry(db, lock, title="x", ttl_policy="forever")
    with pytest.raises(scratchpad_service.ScratchpadError, match="title is required"):
        scratchpad_service.write_entry(db, lock, title="   ")
    with pytest.raises(scratchpad_service.ScratchpadError, match="exceeds"):
        scratchpad_service.write_entry(
            db, lock, title="big", body="x" * (scratchpad_service.MAX_BODY_BYTES + 1)
        )


def test_hours_ttl_expires_and_is_swept(db, lock) -> None:
    entry = scratchpad_service.write_entry(
        db, lock, title="short lived", scope="global", ttl_policy="hours",
        expires_in_hours=1,
    )
    assert entry["expires_at"] is not None
    # Backdate the expiry rather than sleeping.
    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).isoformat()
    with conn_write(db, lock):
        db.execute("UPDATE scratchpad_entries SET expires_at=? WHERE id=?", (past, entry["id"]))
    removed = scratchpad_service.sweep(db, lock)
    assert removed["expired"] == 1
    assert scratchpad_service.get_entry(db, entry["id"]) is None


def conn_write(db: sqlite3.Connection, lock: threading.Lock):
    """Tiny helper mirroring the service's write discipline in tests."""

    class _Ctx:
        def __enter__(self):
            lock.acquire()
            db.execute("BEGIN")
            return db

        def __exit__(self, *exc):
            db.commit()
            lock.release()
            return False

    return _Ctx()


def test_pinned_entries_survive_every_sweep(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="keep me", scope="global", ttl_policy="next_startup"
    )
    scratchpad_service.set_pinned(db, lock, entry_id="keep-me", pinned=True)
    scratchpad_service.write_entry(
        db, lock, title="drop me", scope="global", ttl_policy="next_startup"
    )
    removed = scratchpad_service.sweep(db, lock, startup=True)
    assert removed["startup"] == 1
    assert scratchpad_service.get_entry(db, "keep-me") is not None
    assert scratchpad_service.get_entry(db, "drop-me") is None


def test_run_and_session_sweeps_are_scoped(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="run note", scope="run", ttl_policy="run", run_id="run-1"
    )
    scratchpad_service.write_entry(
        db, lock, title="other run", scope="run", ttl_policy="run", run_id="run-2"
    )
    scratchpad_service.write_entry(
        db, lock, title="session note", scope="session", ttl_policy="session",
        session_id="sess-1",
    )
    removed = scratchpad_service.sweep(db, lock, run_id="run-1")
    assert removed["run"] == 1
    assert scratchpad_service.get_entry(db, "other-run") is not None
    assert scratchpad_service.get_entry(db, "session-note") is not None

    scratchpad_service.sweep(db, lock, session_id="sess-1")
    assert scratchpad_service.get_entry(db, "session-note") is None


def test_permanent_entries_are_never_swept(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="doctrine", scope="global", ttl_policy="permanent"
    )
    scratchpad_service.sweep(db, lock, startup=True)
    assert scratchpad_service.get_entry(db, "doctrine") is not None


def test_stats_report_kinds_and_policies(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="a", kind="plan", scope="global", ttl_policy="permanent"
    )
    scratchpad_service.write_entry(
        db, lock, title="b", kind="tool", scope="global", ttl_policy="next_startup"
    )
    stats = scratchpad_service.stats(db)
    assert stats["total"] == 2
    assert stats["by_kind"] == {"plan": 1, "tool": 1}
    assert stats["by_ttl"] == {"permanent": 1, "next_startup": 1}


# --- the agent tool ---------------------------------------------------------


@pytest.fixture()
def bound(monkeypatch, db, lock):
    monkeypatch.setattr(scratchpad_bridge, "_shared_state", lambda: (db, lock))
    monkeypatch.setattr(scratchpad_bridge, "_binding", lambda *a, **k: ("run-9", "sess-9"))
    return scratchpad_bridge


def _call(bridge, **kwargs) -> dict:
    return json.loads(bridge.atlas_scratchpad_tool(kwargs))


def test_tool_write_read_list_remove(bound) -> None:
    written = _call(bound, op="write", title="Plan", body="do the thing", kind="plan")
    assert written["ok"] and written["entry"]["run_id"] == "run-9"

    read = _call(bound, op="read", id="plan")
    assert read["entry"]["body"] == "do the thing"

    listed = _call(bound, op="list")
    assert listed["count"] == 1
    # The list view is an index, not a dump: bodies stay out of it.
    assert "body" not in listed["entries"][0] and listed["entries"][0]["chars"] == 12

    appended = _call(bound, op="append", title="Plan", body="and the next")
    assert appended["entry"]["body"].endswith("and the next")

    removed = _call(bound, op="remove", id="plan")
    assert removed["removed"] is True


def test_tool_errors_are_returned_not_raised(bound) -> None:
    missing = _call(bound, op="read", id="ghost")
    assert missing["ok"] is False and "ghost" in missing["error"]

    bad_kind = _call(bound, op="write", title="x", kind="weapon")
    assert bad_kind["ok"] is False and "kind" in bad_kind["error"]

    unknown_op = _call(bound, op="detonate")
    assert unknown_op["ok"] is False
