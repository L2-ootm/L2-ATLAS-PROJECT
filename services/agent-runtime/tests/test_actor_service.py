"""Durable actor supervisor tests — state machine, inbox lease, orphan sweep.

Covers the verification list in docs/plans/2026-07-16-subagent-orchestration-design.md:
duplicate spawn, monotonic terminal transitions, wait races, repeated cancel,
lease retry/ack, restart orphan reconciliation, and the worker's durable
failure paths (agent factory injected — no Hermes, no subprocess).
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading
from pathlib import Path

import pytest

from atlas_runtime import actor_service
from atlas_runtime import actor_worker
from atlas_runtime.actor_worker import run_actor
from atlas_runtime.agents.base import RunOutcome
from atlas_runtime.audit_service import get_events_for_run


def _spawn(db: sqlite3.Connection, lock: threading.Lock, run_id: str, **kw):
    defaults = dict(parent_run_id=run_id, goal="collect the evidence", mode="joined")
    defaults.update(kw)
    return actor_service.spawn_actor(db, lock, **defaults)


# --- spawn -------------------------------------------------------------------


def test_spawn_creates_queued_actor_and_audit(db, lock, run_id) -> None:
    actor, created = _spawn(db, lock, run_id)
    assert created and actor["status"] == "queued"
    events = get_events_for_run(db, run_id)
    sub = [e for e in events if e.event_type == "subagent_run"]
    assert len(sub) == 1
    payload = json.loads(sub[0].data)
    assert payload["phase"] == "queued"
    assert payload["subagent_id"] == actor["id"]
    assert payload["actor"] is True


def test_duplicate_spawn_returns_existing(db, lock, run_id) -> None:
    first, created1 = _spawn(db, lock, run_id)
    second, created2 = _spawn(db, lock, run_id)
    assert created1 and not created2
    assert first["id"] == second["id"]
    count = db.execute("SELECT COUNT(*) FROM actors").fetchone()[0]
    assert count == 1


def test_explicit_idempotency_key_allows_intentional_duplicates(db, lock, run_id) -> None:
    a, _ = _spawn(db, lock, run_id, idempotency_key="k1")
    b, _ = _spawn(db, lock, run_id, idempotency_key="k2")
    assert a["id"] != b["id"]


def test_spawn_rejects_empty_goal_and_bad_mode(db, lock, run_id) -> None:
    with pytest.raises(ValueError):
        _spawn(db, lock, run_id, goal="  ")
    with pytest.raises(ValueError):
        _spawn(db, lock, run_id, mode="sideways")
    with pytest.raises(ValueError):
        _spawn(db, lock, run_id, depth=actor_service.MAX_DEPTH + 1)


def test_spawn_uses_parent_run_surface_session(db, lock, run_id, surface_session) -> None:
    db.execute("UPDATE runs SET session_id=? WHERE id=?", (surface_session, run_id))
    db.commit()
    actor, _ = _spawn(db, lock, run_id, session_id="hermes-session")
    assert actor["session_id"] == surface_session


# --- transitions -------------------------------------------------------------


def test_lifecycle_and_monotonic_terminal(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    assert actor_service.mark_running(db, lock, actor["id"], pid=123, owner_token="t")
    assert not actor_service.mark_running(db, lock, actor["id"])  # not queued anymore
    assert actor_service.complete_actor(db, lock, actor["id"], result_preview="done")
    # repeated completion / late failure are no-ops
    assert not actor_service.complete_actor(db, lock, actor["id"])
    assert not actor_service.fail_actor(db, lock, actor["id"], error="late")
    final = actor_service.get_actor(db, actor["id"])
    assert final["status"] == "completed"
    assert final["result_preview"] == "done"


def test_terminal_trigger_backstop(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"])
    actor_service.complete_actor(db, lock, actor["id"])
    with pytest.raises(sqlite3.IntegrityError):
        with db:
            db.execute(
                "UPDATE actors SET status='running' WHERE id=?", (actor["id"],)
            )


def test_heartbeat_only_running(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    assert not actor_service.heartbeat_actor(db, lock, actor["id"])
    actor_service.mark_running(db, lock, actor["id"])
    assert actor_service.heartbeat_actor(db, lock, actor["id"])


def test_bind_child_run_emits_working_lifecycle(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"])
    assert actor_service.bind_child_run(db, lock, actor["id"], child_run_id=run_id)
    assert not actor_service.bind_child_run(db, lock, actor["id"], child_run_id="child-2")
    payloads = [
        json.loads(event.data)
        for event in get_events_for_run(db, run_id)
        if event.event_type == "subagent_run"
    ]
    assert payloads[-1]["phase"] == "working"
    assert payloads[-1]["child_run_id"] == run_id


# --- cancel ------------------------------------------------------------------


def test_cancel_is_recursive_and_idempotent(db, lock, run_id) -> None:
    parent, _ = _spawn(db, lock, run_id, idempotency_key="p")
    child, _ = _spawn(
        db, lock, run_id, idempotency_key="c",
        parent_actor_id=parent["id"], depth=2,
    )
    actor_service.mark_running(db, lock, parent["id"], pid=111)
    actor_service.mark_running(db, lock, child["id"], pid=222)
    cancelled = actor_service.cancel_actor(db, lock, parent["id"])
    assert {a["id"] for a in cancelled} == {parent["id"], child["id"]}
    # repeat is a no-op
    assert actor_service.cancel_actor(db, lock, parent["id"]) == []
    assert actor_service.get_actor(db, child["id"])["status"] == "cancelled"


def test_cancel_consumes_pending_delivery(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id, mode="detached")
    actor_service.mark_running(db, lock, actor["id"])
    actor_service.complete_actor(db, lock, actor["id"], result_preview="r")
    # completed actor: cancel is a no-op but the delivery already exists
    actor_service.cancel_actor(db, lock, actor["id"])
    claimed = actor_service.claim_deliveries(
        db, lock, parent_run_id=run_id, claim_token="t1"
    )
    assert len(claimed) == 1  # completed before cancel attempt — still delivered

    # a cancelled-in-flight actor never delivers
    second, _ = _spawn(db, lock, run_id, idempotency_key="second", mode="detached")
    actor_service.mark_running(db, lock, second["id"])
    actor_service.cancel_actor(db, lock, second["id"])
    claimed2 = actor_service.claim_deliveries(
        db, lock, parent_run_id=run_id, claim_token="t2"
    )
    assert claimed2 == []


# --- wait / delivery ---------------------------------------------------------


def test_wait_returns_completed_and_consumes(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"])
    actor_service.complete_actor(db, lock, actor["id"], result_preview="answer")
    joined = actor_service.wait_for_actor(db, lock, actor["id"], timeout_seconds=1)
    assert joined["status"] == "completed"
    assert joined["delivery"]["result_preview"] == "answer"
    # consumed: a later inbox claim cannot re-inject it
    claimed = actor_service.claim_deliveries(
        db, lock, parent_run_id=run_id, claim_token="t"
    )
    assert claimed == []


def test_wait_times_out_on_active_actor(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"])
    assert (
        actor_service.wait_for_actor(
            db, lock, actor["id"], timeout_seconds=0.05, poll_interval=0.01
        )
        is None
    )


def test_wait_closes_completion_race(db, lock, run_id) -> None:
    """Completion landing between reads is picked up by the poll loop."""
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"])

    def _complete_soon() -> None:
        actor_service.complete_actor(db, lock, actor["id"], result_preview="raced")

    t = threading.Timer(0.05, _complete_soon)
    t.start()
    joined = actor_service.wait_for_actor(
        db, lock, actor["id"], timeout_seconds=2, poll_interval=0.01
    )
    t.join()
    assert joined is not None and joined["status"] == "completed"


def test_claim_lease_and_acknowledge(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id, mode="detached")
    actor_service.mark_running(db, lock, actor["id"])
    actor_service.complete_actor(db, lock, actor["id"], result_preview="x")

    claimed = actor_service.claim_deliveries(
        db, lock, parent_run_id=run_id, claim_token="tok-1"
    )
    assert len(claimed) == 1
    # while the lease is live, nobody else can claim
    assert (
        actor_service.claim_deliveries(db, lock, parent_run_id=run_id, claim_token="tok-2")
        == []
    )
    assert actor_service.acknowledge_deliveries(db, lock, claim_token="tok-1") == 1
    # delivered: no further claims
    assert (
        actor_service.claim_deliveries(db, lock, parent_run_id=run_id, claim_token="tok-3")
        == []
    )


def test_expired_claim_is_reclaimable(db, lock, run_id) -> None:
    """Crash between claim and acknowledge: the lease expires and retries."""
    actor, _ = _spawn(db, lock, run_id, mode="detached")
    actor_service.mark_running(db, lock, actor["id"])
    actor_service.complete_actor(db, lock, actor["id"], result_preview="x")
    actor_service.claim_deliveries(db, lock, parent_run_id=run_id, claim_token="dead")
    # age the claim beyond the lease
    past = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=120)
    ).isoformat()
    with db:
        db.execute(
            "UPDATE actor_deliveries SET claimed_at=? WHERE actor_id=?",
            (past, actor["id"]),
        )
    reclaimed = actor_service.claim_deliveries(
        db, lock, parent_run_id=run_id, claim_token="alive", lease_seconds=60
    )
    assert len(reclaimed) == 1


# --- orphan recovery ---------------------------------------------------------


def test_orphan_reconciliation(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"])
    # age the heartbeat
    past = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=600)
    ).isoformat()
    with db:
        db.execute(
            "UPDATE actors SET heartbeat_at=? WHERE id=?", (past, actor["id"])
        )
    orphaned = actor_service.reconcile_orphan_actors(db, lock, ttl_seconds=90)
    assert orphaned == [actor["id"]]
    assert actor_service.get_actor(db, actor["id"])["status"] == "orphaned"
    # the parent learns via a delivery that is NOT a success
    claimed = actor_service.claim_deliveries(
        db, lock, parent_run_id=run_id, claim_token="t"
    )
    assert len(claimed) == 1 and claimed[0]["status"] == "orphaned"
    # idempotent
    assert actor_service.reconcile_orphan_actors(db, lock, ttl_seconds=90) == []


def test_fresh_actor_survives_sweep(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"])
    assert actor_service.reconcile_orphan_actors(db, lock, ttl_seconds=90) == []
    assert actor_service.get_actor(db, actor["id"])["status"] == "running"


# --- worker (injected agent, no subprocess) -----------------------------------


def test_windows_worker_launch_is_hidden_without_detached_process(
    db, lock, run_id, monkeypatch, tmp_path
) -> None:
    actor, _ = _spawn(db, lock, run_id)
    python = tmp_path / "python.exe"
    pythonw = tmp_path / "pythonw.exe"
    python.write_text("", encoding="utf-8")
    pythonw.write_text("", encoding="utf-8")
    observed = {}

    class _Proc:
        pid = 4321

    def _popen(cmd, **kwargs):
        observed["cmd"] = cmd
        observed.update(kwargs)
        return _Proc()

    monkeypatch.setattr(actor_worker.os, "name", "nt")
    monkeypatch.setattr(actor_worker.sys, "executable", str(python))
    monkeypatch.setattr(actor_worker.subprocess, "Popen", _popen)
    assert actor_worker.launch_actor_worker(db, lock, actor["id"], db_path=str(tmp_path / "atlas.db")) == 4321
    assert Path(observed["cmd"][0]).name == "pythonw.exe"
    assert observed["creationflags"] & actor_worker.CREATE_NO_WINDOW
    assert observed["creationflags"] & actor_worker.CREATE_NEW_PROCESS_GROUP
    assert not (observed["creationflags"] & 0x00000008)
    assert observed["close_fds"] is True


class _FakeRuntime:
    def __init__(self, outcome: RunOutcome) -> None:
        self._outcome = outcome
        self.prompts: list[str] = []

    def execute(self, conn, lock, *, mission_id, run_id, prompt, cancel_token=None):  # noqa: ANN001
        self.prompts.append(prompt)
        return self._outcome


def test_run_actor_success_completes_actor_and_child_run(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id, goal="summarize the repo")
    runtime = _FakeRuntime(RunOutcome(status="succeeded", summary="all good"))
    ok = run_actor(db, lock, actor["id"], agent_factory=lambda name: runtime)
    assert ok
    final = actor_service.get_actor(db, actor["id"])
    assert final["status"] == "completed"
    assert final["result_preview"] == "all good"
    assert runtime.prompts == ["summarize the repo"]
    child = db.execute(
        "SELECT status FROM runs WHERE id=?", (final["child_run_id"],)
    ).fetchone()
    assert child[0] == "succeeded"


def test_run_actor_applies_routed_provider_and_model(
    db, lock, run_id, monkeypatch
) -> None:
    actor, _ = _spawn(
        db, lock, run_id,
        goal="use the routed model",
        model="openai-codex/gpt-5.4-mini",
    )
    runtime = _FakeRuntime(RunOutcome(status="succeeded", summary="routed"))
    observed = {}

    def _native(**kwargs):
        observed.update(kwargs)
        return runtime

    monkeypatch.setattr("atlas_runtime.agents.native.NativeAtlasAgent", _native)
    assert run_actor(db, lock, actor["id"])
    assert observed == {"provider": "openai-codex", "model": "gpt-5.4-mini"}


def test_run_actor_failure_is_durable(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    runtime = _FakeRuntime(RunOutcome(status="failed", summary="boom"))
    assert run_actor(db, lock, actor["id"], agent_factory=lambda name: runtime)
    final = actor_service.get_actor(db, actor["id"])
    assert final["status"] == "failed"
    assert "boom" in final["error"]


def test_run_actor_exception_becomes_failed_actor(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)

    def _factory(name: str):
        raise RuntimeError("foundation missing")

    assert run_actor(db, lock, actor["id"], agent_factory=_factory)
    final = actor_service.get_actor(db, actor["id"])
    assert final["status"] == "failed"
    assert "foundation missing" in final["error"]


def test_run_actor_noops_on_non_queued(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"])
    assert not run_actor(db, lock, actor["id"], agent_factory=lambda n: None)
