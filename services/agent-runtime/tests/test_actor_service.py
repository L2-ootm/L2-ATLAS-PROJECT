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

import pytest

from atlas_runtime import actor_service
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


# --- CASE-04: steering, log tailing, opt-in parent wakeup ---------------------


def test_steering_is_ordered_and_delivered_at_most_once(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"], pid=1)
    actor_service.enqueue_steering(db, lock, actor["id"], message="first")
    actor_service.enqueue_steering(db, lock, actor["id"], message="second")

    drained = actor_service.drain_steering(db, lock, actor["id"])
    assert [d["message"] for d in drained] == ["first", "second"]
    assert [d["seq"] for d in drained] == [1, 2]
    assert actor_service.drain_steering(db, lock, actor["id"]) == []


def test_delivered_steering_is_kept_for_audit_not_deleted(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"], pid=1)
    actor_service.enqueue_steering(db, lock, actor["id"], message="redirect")
    actor_service.drain_steering(db, lock, actor["id"])
    row = db.execute(
        "SELECT status, message FROM actor_steering WHERE actor_id=?", (actor["id"],)
    ).fetchone()
    assert row == ("delivered", "redirect")


def test_steering_rejects_empty_terminal_and_unknown(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"], pid=1)
    with pytest.raises(ValueError, match="non-empty"):
        actor_service.enqueue_steering(db, lock, actor["id"], message="   ")
    with pytest.raises(ValueError, match="unknown actor"):
        actor_service.enqueue_steering(db, lock, "actor-nope", message="hi")
    actor_service.complete_actor(db, lock, actor["id"], result_preview="done")
    with pytest.raises(ValueError, match="nothing to steer"):
        actor_service.enqueue_steering(db, lock, actor["id"], message="late")


def test_attach_child_run_links_a_live_actor_to_its_audit_trail(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"], pid=1)
    assert actor_service.attach_child_run(db, lock, actor["id"], run_id) is True
    assert actor_service.get_actor(db, actor["id"])["child_run_id"] == run_id


def test_attach_child_run_refuses_a_terminal_actor(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id)
    actor_service.mark_running(db, lock, actor["id"], pid=1)
    actor_service.complete_actor(db, lock, actor["id"], result_preview="done")
    assert actor_service.attach_child_run(db, lock, actor["id"], run_id) is False


def test_worker_records_the_child_run_before_it_finishes(db, lock, run_id) -> None:
    """op=logs on a live actor needs the link to exist while it is still working."""
    seen: dict = {}
    actor, _ = _spawn(db, lock, run_id)

    class _Peeking:
        def execute(self, conn, lock_, *, mission_id, run_id, prompt, cancel_token=None):  # noqa: ANN001
            seen["child_run_id"] = actor_service.get_actor(conn, actor["id"])["child_run_id"]
            return RunOutcome(status="succeeded", summary="ok")

    run_actor(db, lock, actor["id"], agent_factory=lambda name: _Peeking())
    assert seen["child_run_id"], "child_run_id was still unset while the actor ran"


def test_wakeup_starts_a_follow_up_run_in_the_parent_session(
    db, lock, run_id, surface_session, monkeypatch
) -> None:
    monkeypatch.delenv("ATLAS_WAKEUP_RUN", raising=False)
    db.execute("UPDATE surface_sessions SET state='active' WHERE id=?", (surface_session,))
    db.commit()
    actor, _ = _spawn(
        db, lock, run_id, mode="detached", session_id=surface_session, wakeup_parent=True,
    )
    runtime = _FakeRuntime(RunOutcome(status="succeeded", summary="found the cause"))
    run_actor(db, lock, actor["id"], agent_factory=lambda name: runtime)

    # Two prompts: the actor's own goal, then the wakeup turn in the parent session.
    assert len(runtime.prompts) == 2
    assert "A background actor you started has finished" in runtime.prompts[1]
    assert "found the cause" in runtime.prompts[1]
    follow_up = db.execute(
        "SELECT COUNT(*) FROM runs WHERE session_id=? AND id!=?", (surface_session, run_id)
    ).fetchone()[0]
    assert follow_up >= 1


def test_wakeup_consumes_the_delivery_so_it_is_not_announced_twice(
    db, lock, run_id, surface_session, monkeypatch
) -> None:
    monkeypatch.delenv("ATLAS_WAKEUP_RUN", raising=False)
    db.execute("UPDATE surface_sessions SET state='active' WHERE id=?", (surface_session,))
    db.commit()
    actor, _ = _spawn(
        db, lock, run_id, mode="detached", session_id=surface_session, wakeup_parent=True,
    )
    run_actor(
        db, lock, actor["id"],
        agent_factory=lambda name: _FakeRuntime(RunOutcome(status="succeeded", summary="r")),
    )
    status = db.execute(
        "SELECT status FROM actor_deliveries WHERE actor_id=?", (actor["id"],)
    ).fetchone()[0]
    assert status == "consumed"


def test_wakeup_is_suppressed_inside_a_wakeup_chain(
    db, lock, run_id, surface_session, monkeypatch
) -> None:
    """One follow-up turn, not a self-triggering loop."""
    monkeypatch.setenv("ATLAS_WAKEUP_RUN", "1")
    db.execute("UPDATE surface_sessions SET state='active' WHERE id=?", (surface_session,))
    db.commit()
    actor, _ = _spawn(
        db, lock, run_id, mode="detached", session_id=surface_session, wakeup_parent=True,
    )
    runtime = _FakeRuntime(RunOutcome(status="succeeded", summary="r"))
    run_actor(db, lock, actor["id"], agent_factory=lambda name: runtime)
    assert len(runtime.prompts) == 1


def test_wakeup_skipped_when_the_session_is_no_longer_live(
    db, lock, run_id, surface_session, monkeypatch
) -> None:
    monkeypatch.delenv("ATLAS_WAKEUP_RUN", raising=False)
    db.execute("UPDATE surface_sessions SET state='completed' WHERE id=?", (surface_session,))
    db.commit()
    actor, _ = _spawn(
        db, lock, run_id, mode="detached", session_id=surface_session, wakeup_parent=True,
    )
    runtime = _FakeRuntime(RunOutcome(status="succeeded", summary="r"))
    run_actor(db, lock, actor["id"], agent_factory=lambda name: runtime)
    assert len(runtime.prompts) == 1


def test_no_wakeup_leaves_the_delivery_pending_for_the_inbox(
    db, lock, run_id, surface_session, monkeypatch
) -> None:
    monkeypatch.delenv("ATLAS_WAKEUP_RUN", raising=False)
    actor, _ = _spawn(db, lock, run_id, mode="detached", session_id=surface_session)
    runtime = _FakeRuntime(RunOutcome(status="succeeded", summary="r"))
    run_actor(db, lock, actor["id"], agent_factory=lambda name: runtime)
    assert len(runtime.prompts) == 1
    status = db.execute(
        "SELECT status FROM actor_deliveries WHERE actor_id=?", (actor["id"],)
    ).fetchone()[0]
    assert status == "pending"
