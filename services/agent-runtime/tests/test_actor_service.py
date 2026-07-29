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
import time

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


def test_single_delivery_claim_is_cas_and_stale_lease_recovers(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id, mode="detached")
    actor_service.mark_running(db, lock, actor["id"])
    actor_service.complete_actor(db, lock, actor["id"], result_preview="x")

    first = actor_service.claim_delivery(
        db, lock, actor["id"], claim_token="first", lease_seconds=60
    )
    assert first is not None
    assert (
        actor_service.claim_delivery(
            db, lock, actor["id"], claim_token="second", lease_seconds=60
        )
        is None
    )
    past = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=120)
    ).isoformat()
    with db:
        db.execute(
            "UPDATE actor_deliveries SET claimed_at=? WHERE actor_id=?",
            (past, actor["id"]),
        )
    recovered = actor_service.claim_delivery(
        db, lock, actor["id"], claim_token="second", lease_seconds=60
    )
    assert recovered is not None
    assert not actor_service.release_delivery_claim(
        db, lock, actor["id"], claim_token="first"
    )
    assert actor_service.release_delivery_claim(
        db, lock, actor["id"], claim_token="second"
    )


def test_explicit_wait_cannot_steal_a_live_delivery_claim(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id, mode="detached")
    actor_service.mark_running(db, lock, actor["id"])
    actor_service.complete_actor(db, lock, actor["id"], result_preview="x")
    assert actor_service.claim_delivery(
        db, lock, actor["id"], claim_token="wakeup"
    )
    assert actor_service.consume_delivery(db, lock, actor["id"]) is None
    assert db.execute(
        "SELECT status, claim_token FROM actor_deliveries WHERE actor_id=?",
        (actor["id"],),
    ).fetchone() == ("claimed", "wakeup")


def test_two_workers_racing_single_delivery_have_one_winner(db, lock, run_id) -> None:
    actor, _ = _spawn(db, lock, run_id, mode="detached")
    actor_service.mark_running(db, lock, actor["id"])
    actor_service.complete_actor(db, lock, actor["id"], result_preview="x")
    barrier = threading.Barrier(2)
    results: list[bool] = []

    def _race(token: str) -> None:
        barrier.wait()
        claimed = actor_service.claim_delivery(
            db, lock, actor["id"], claim_token=token
        )
        results.append(claimed is not None)

    threads = [
        threading.Thread(target=_race, args=("one",)),
        threading.Thread(target=_race, args=("two",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [False, True]


# --- orphan recovery ---------------------------------------------------------


def test_actor_history_reloads_after_service_restart_by_session_and_parent_run(
    db, lock, run_id, tmp_path
) -> None:
    parent, _ = _spawn(
        db,
        lock,
        run_id,
        idempotency_key="history-parent",
        session_id="surface-history",
    )
    child, _ = _spawn(
        db,
        lock,
        run_id,
        idempotency_key="history-child",
        session_id="surface-history",
        parent_actor_id=parent["id"],
        depth=2,
    )
    actor_service.mark_running(db, lock, parent["id"], pid=111)
    actor_service.attach_child_run(db, lock, parent["id"], run_id)
    actor_service.complete_actor(
        db, lock, parent["id"], result_preview="durable result", child_run_id=run_id
    )
    actor_service.cancel_actor(db, lock, child["id"])

    restored_path = tmp_path / "actor-history.db"
    restored = sqlite3.connect(restored_path)
    db.backup(restored)
    restored.close()

    reopened = sqlite3.connect(restored_path)
    try:
        by_session = actor_service.load_actor_history(
            reopened, session_id="surface-history"
        )
        by_parent = actor_service.load_actor_history(
            reopened, parent_run_id=run_id
        )
    finally:
        reopened.close()

    assert [actor["id"] for actor in by_session] == [parent["id"], child["id"]]
    assert [actor["id"] for actor in by_parent] == [parent["id"], child["id"]]
    assert by_session[0]["child_run_id"] == run_id
    assert by_session[0]["status"] == "completed"
    assert by_session[1]["parent_actor_id"] == parent["id"]
    assert by_session[1]["status"] == "cancelled"


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


def test_read_only_actor_mutation_records_incident_before_blocked_completion(
    db, lock, run_id, surface_session
) -> None:
    db.execute(
        "UPDATE surface_sessions SET permission_mode='read_only', state='active'"
        " WHERE id=?",
        (surface_session,),
    )
    actor, _ = _spawn(
        db,
        lock,
        run_id,
        goal="inspect without changes",
        session_id=surface_session,
    )

    class _MutatingRuntime:
        def execute(
            self,
            conn,
            lock_,
            *,
            mission_id,
            run_id,
            prompt,
            cancel_token=None,
        ):  # noqa: ANN001
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO evidence_change_sets"
                "(id,run_id,session_id,actor_id,coverage,status,redaction_count,created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    "read-only-change",
                    run_id,
                    surface_session,
                    actor["id"],
                    "complete",
                    "captured",
                    0,
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO evidence_file_changes"
                "(id,change_set_id,path,operation,availability,before_bytes,after_bytes,"
                " additions,deletions,binary,generated,redaction_count)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "read-only-file",
                    "read-only-change",
                    "mutated.txt",
                    "create",
                    "available",
                    0,
                    1,
                    1,
                    0,
                    0,
                    0,
                    0,
                ),
            )
            conn.commit()
            return RunOutcome(status="succeeded", summary="claimed success")

    assert run_actor(
        db,
        lock,
        actor["id"],
        agent_factory=lambda _name: _MutatingRuntime(),
    )
    final = actor_service.get_actor(db, actor["id"])
    assert final["status"] == "failed"
    assert "read-only mutation" in final["error"]
    child = db.execute(
        "SELECT status FROM runs WHERE id=?", (final["child_run_id"],)
    ).fetchone()
    assert child[0] == "failed"
    events = db.execute(
        "SELECT event_type, policy_result, data FROM audit_events"
        " WHERE task_id=? ORDER BY rowid",
        (actor["id"],),
    ).fetchall()
    incident_index = next(
        index
        for index, event in enumerate(events)
        if event[0] == "failure" and event[1] == "denied"
    )
    assert all(
        json.loads(event[2]).get("status") != "succeeded"
        for event in events[: incident_index + 1]
    )


def test_parent_actor_aggregate_references_each_child_change_set_once(
    db, lock, run_id, monkeypatch
) -> None:
    parent, _ = _spawn(db, lock, run_id, idempotency_key="aggregate-parent")
    child, _ = _spawn(
        db,
        lock,
        run_id,
        idempotency_key="aggregate-child",
        parent_actor_id=parent["id"],
        depth=2,
    )
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO evidence_change_sets"
        "(id,run_id,actor_id,coverage,status,redaction_count,created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        ("child-change", run_id, child["id"], "complete", "captured", 0, now),
    )
    observed = {}

    def aggregate(**kwargs):
        observed.update(kwargs)
        from atlas_runtime.evidence_bridge import AggregationReceipt

        return AggregationReceipt(
            change_set_id="aggregate-parent",
            coverage="complete",
            status="captured",
            child_count=1,
            file_count=1,
            additions=1,
            deletions=0,
            redaction_count=0,
        )

    monkeypatch.setattr(
        actor_service.change_reconciliation,
        "persist_reference_aggregation",
        aggregate,
    )
    assert actor_service.complete_actor(db, lock, parent["id"], result_preview="done")
    assert observed["child_change_set_ids"] == ["child-change"]


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


def _completed_wakeup_actor(db, lock, run_id, surface_session):
    db.execute(
        "UPDATE surface_sessions SET state='active' WHERE id=?", (surface_session,)
    )
    db.commit()
    actor, _ = _spawn(
        db,
        lock,
        run_id,
        mode="detached",
        session_id=surface_session,
        wakeup_parent=True,
    )
    actor_service.mark_running(db, lock, actor["id"])
    actor_service.complete_actor(db, lock, actor["id"], result_preview="ready")
    return actor


@pytest.mark.parametrize("failure_point", ["mission", "run", "resolution", "model", "finalize"])
def test_wakeup_failure_releases_delivery_for_retry(
    db, lock, run_id, surface_session, monkeypatch, failure_point
) -> None:
    monkeypatch.delenv("ATLAS_WAKEUP_RUN", raising=False)
    actor = _completed_wakeup_actor(db, lock, run_id, surface_session)

    if failure_point == "mission":
        monkeypatch.setattr(
            actor_worker,
            "create_mission",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("mission")),
        )
        factory = lambda name: _FakeRuntime(  # noqa: E731
            RunOutcome(status="succeeded", summary="ok")
        )
    elif failure_point == "run":
        monkeypatch.setattr(
            actor_worker,
            "start_run",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("run")),
        )
        factory = lambda name: _FakeRuntime(  # noqa: E731
            RunOutcome(status="succeeded", summary="ok")
        )
    elif failure_point == "resolution":
        def factory(name):
            raise RuntimeError("resolution")
    elif failure_point == "model":
        class _ExplodingRuntime:
            def execute(self, *args, **kwargs):
                raise RuntimeError("model")

        factory = lambda name: _ExplodingRuntime()  # noqa: E731
    else:
        monkeypatch.setattr(
            actor_worker,
            "complete_run",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("finalize")),
        )
        factory = lambda name: _FakeRuntime(  # noqa: E731
            RunOutcome(status="succeeded", summary="ok")
        )

    assert actor_worker._wake_parent(
        db, lock, actor["id"], agent_factory=factory
    ) is None
    delivery = db.execute(
        "SELECT status, claim_token, claimed_at FROM actor_deliveries WHERE actor_id=?",
        (actor["id"],),
    ).fetchone()
    assert delivery == ("pending", None, None)


def test_wakeup_terminal_and_delivery_consume_are_one_transaction(
    db, lock, run_id, surface_session, monkeypatch
) -> None:
    monkeypatch.delenv("ATLAS_WAKEUP_RUN", raising=False)
    actor = _completed_wakeup_actor(db, lock, run_id, surface_session)
    db.execute(
        "CREATE TRIGGER reject_actor_delivery_consume "
        "BEFORE UPDATE OF status ON actor_deliveries "
        "WHEN NEW.status='consumed' "
        "BEGIN SELECT RAISE(ABORT, 'injected finalization failure'); END"
    )
    db.commit()

    result = actor_worker._wake_parent(
        db,
        lock,
        actor["id"],
        agent_factory=lambda name: _FakeRuntime(
            RunOutcome(status="succeeded", summary="ok")
        ),
    )
    assert result is None
    run_status, mission_id = db.execute(
        "SELECT status, mission_id FROM runs "
        "WHERE id!=? ORDER BY started_at DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    mission_status = db.execute(
        "SELECT status FROM missions WHERE id=?", (mission_id,)
    ).fetchone()[0]
    delivery_status = db.execute(
        "SELECT status FROM actor_deliveries WHERE actor_id=?", (actor["id"],)
    ).fetchone()[0]
    assert (run_status, mission_status, delivery_status) == (
        "running",
        "running",
        "pending",
    )


def test_wakeup_renews_lease_while_model_is_active(
    db, lock, run_id, surface_session, monkeypatch
) -> None:
    monkeypatch.delenv("ATLAS_WAKEUP_RUN", raising=False)
    actor = _completed_wakeup_actor(db, lock, run_id, surface_session)
    competing_claims: list[object] = []

    class _SlowRuntime:
        def execute(self, *args, **kwargs):
            def _compete() -> None:
                time.sleep(0.07)
                competing_claims.append(
                    actor_service.claim_delivery(
                        db,
                        lock,
                        actor["id"],
                        claim_token="competitor",
                        lease_seconds=0.03,
                    )
                )

            contender = threading.Thread(target=_compete)
            contender.start()
            time.sleep(0.12)
            contender.join()
            return RunOutcome(status="succeeded", summary="ok")

    result = actor_worker._wake_parent(
        db,
        lock,
        actor["id"],
        agent_factory=lambda name: _SlowRuntime(),
        delivery_lease_seconds=0.03,
    )
    assert result is not None
    assert competing_claims == [None]


def test_repeated_wakeup_after_success_reuses_no_work(
    db, lock, run_id, surface_session, monkeypatch
) -> None:
    monkeypatch.delenv("ATLAS_WAKEUP_RUN", raising=False)
    actor = _completed_wakeup_actor(db, lock, run_id, surface_session)
    runtime = _FakeRuntime(RunOutcome(status="succeeded", summary="ok"))
    first = actor_worker._wake_parent(
        db, lock, actor["id"], agent_factory=lambda name: runtime
    )
    second = actor_worker._wake_parent(
        db, lock, actor["id"], agent_factory=lambda name: runtime
    )
    assert first is not None
    assert second is None
    assert len(runtime.prompts) == 1
    assert db.execute(
        "SELECT COUNT(*) FROM missions WHERE title LIKE 'actor wakeup:%'"
    ).fetchone()[0] == 1


def test_failed_model_retry_reuses_correlated_mission_and_run(
    db, lock, run_id, surface_session, monkeypatch
) -> None:
    monkeypatch.delenv("ATLAS_WAKEUP_RUN", raising=False)
    actor = _completed_wakeup_actor(db, lock, run_id, surface_session)

    class _ExplodingRuntime:
        def execute(self, *args, **kwargs):
            raise RuntimeError("model interrupted")

    assert actor_worker._wake_parent(
        db, lock, actor["id"], agent_factory=lambda name: _ExplodingRuntime()
    ) is None
    correlated_before = db.execute(
        "SELECT id, mission_id FROM runs WHERE id!=?", (run_id,)
    ).fetchone()

    recovered = actor_worker._wake_parent(
        db,
        lock,
        actor["id"],
        agent_factory=lambda name: _FakeRuntime(
            RunOutcome(status="succeeded", summary="recovered")
        ),
    )
    assert recovered == correlated_before[0]
    assert db.execute(
        "SELECT COUNT(*) FROM runs WHERE mission_id=?", (correlated_before[1],)
    ).fetchone()[0] == 1
    assert db.execute(
        "SELECT status FROM actor_deliveries WHERE actor_id=?", (actor["id"],)
    ).fetchone()[0] == "consumed"
