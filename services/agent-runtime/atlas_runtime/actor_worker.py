"""Actor worker — detached child process executing one durable actor.

Launched hidden with only the actor ID on argv (`python -m
atlas_runtime.actor_worker <actor_id>`); the goal is read from SQLite,
avoiding command-line leakage and quoting failures. The worker marks the
actor running, heartbeats every 5 seconds, creates a normal child
mission+run (full audit/evidence stays in ordinary run data), drives the
selected AgentRuntime, and writes the terminal actor state + one pending
delivery atomically via actor_service.

`run_actor()` is the unit-testable in-process core; `launch_actor_worker()`
is the detached spawn (cockpit_control's Windows flag triad / POSIX
start_new_session). A launch failure becomes a durable failed actor, never a
missing response.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
import sys
import threading
import uuid
from typing import Any, Callable, Optional

from atlas_runtime import actor_service
from atlas_runtime import db as atlas_db
from atlas_runtime.mission_service import create_mission
from atlas_runtime.run_service import complete_run, start_run

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 5.0

DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def launch_actor_worker(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    db_path: Optional[str] = None,
) -> Optional[int]:
    """Spawn the hidden detached worker for an actor. Returns the pid.

    Only the actor id rides argv. The DB location rides ATLAS_DB so the child
    opens the same store regardless of its own cwd. Spawn failure transitions
    the actor to failed durably and returns None.
    """
    cmd = [sys.executable, "-m", "atlas_runtime.actor_worker", actor_id]
    env = dict(os.environ)
    env["ATLAS_DB"] = db_path or str(atlas_db.default_db_path())
    # The child recognizes steering aimed at itself by this id (actor_bridge's
    # pre_llm_call drain). argv already carries it, but the harness runs several
    # frames below main() and env is how the rest of the runtime is configured.
    env["ATLAS_ACTOR_ID"] = actor_id
    try:
        if os.name == "nt":
            proc = subprocess.Popen(  # noqa: S603
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                env=env,
                creationflags=DETACHED_PROCESS
                | CREATE_NEW_PROCESS_GROUP
                | CREATE_NO_WINDOW,
            )
        else:  # pragma: no cover - POSIX path exercised in CI only
            proc = subprocess.Popen(  # noqa: S603
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                env=env,
                start_new_session=True,
            )
        return proc.pid
    except Exception as exc:  # noqa: BLE001 — durable failure, not an exception
        logger.warning("actor worker launch failed for %s: %s", actor_id, exc)
        actor_service.fail_actor(
            conn, lock, actor_id, error=f"worker launch failed: {exc}"
        )
        return None


def terminate_actor_pids(actors: list[dict[str, Any]]) -> None:
    """Best-effort kill of cancelled actors' worker processes."""
    for actor in actors:
        pid = actor.get("pid")
        if not pid:
            continue
        try:
            if os.name == "nt":
                subprocess.run(  # noqa: S603
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    creationflags=CREATE_NO_WINDOW,
                    check=False,
                )
            else:  # pragma: no cover - POSIX only
                os.kill(int(pid), 15)
        except Exception as exc:  # noqa: BLE001
            logger.debug("terminate pid %s failed: %s", pid, exc)


# Set in the environment of any process executing a wakeup follow-up run. It is
# inherited by every actor worker that run spawns, which is what bounds the
# chain: a wakeup can start one follow-up turn, and nothing that turn spawns can
# start another. Without it, two actors each waking the parent, whose turns each
# spawn more waking actors, is an unbounded self-triggering loop.
WAKEUP_ENV_FLAG = "ATLAS_WAKEUP_RUN"

# Live surface-session states — a completion is only worth waking a session that
# still exists. Mirrors surface_session_service's non-terminal set.
_LIVE_SESSION_STATES = ("starting", "active", "suspended", "resuming")


def _wake_parent(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    agent_factory: Optional[Callable[[str], Any]] = None,
    delivery_lease_seconds: float = 60.0,
) -> Optional[str]:
    """Start a follow-up run in the parent's session announcing this completion.

    A detached actor's result otherwise sits in `actor_deliveries` until the
    parent happens to take another turn — which, once the parent run has ended,
    only happens when a human types something. For unattended work that is the
    difference between "finished" and "finished and acted on".

    Executed here, in the worker, because the worker is the only process still
    alive at completion time; the parent run's process is gone. Returns the new
    run id, or None when the wakeup was not applicable (not requested, chained,
    or the session is no longer live) — all of which are normal, not failures.
    """
    actor = actor_service.get_actor(conn, actor_id)
    if actor is None or not actor.get("wakeup_parent"):
        return None
    if os.environ.get(WAKEUP_ENV_FLAG):
        logger.info("actor %s: wakeup suppressed (already inside a wakeup chain)", actor_id)
        return None
    session_id = actor.get("session_id")
    if not session_id:
        return None
    row = conn.execute(
        "SELECT state FROM surface_sessions WHERE id=?", (session_id,)
    ).fetchone()
    if row is None or row[0] not in _LIVE_SESSION_STATES:
        logger.info("actor %s: wakeup skipped, session not live", actor_id)
        return None

    claim_token = str(uuid.uuid4())
    delivery = actor_service.claim_delivery(
        conn,
        lock,
        actor_id,
        claim_token=claim_token,
        lease_seconds=delivery_lease_seconds,
    )
    if delivery is None:
        return None

    # Stable IDs are the correlation contract. A retry after mission/run
    # creation observes these same rows instead of manufacturing a duplicate.
    mission_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"atlas:actor-wakeup:{actor_id}:mission")
    )
    run_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"atlas:actor-wakeup:{actor_id}:run")
    )
    renew_stop = threading.Event()

    def _renew_claim() -> None:
        interval = max(0.01, delivery_lease_seconds / 3.0)
        while not renew_stop.wait(interval):
            try:
                if not actor_service.renew_delivery_claim(
                    conn, lock, actor_id, claim_token=claim_token
                ):
                    return
            except Exception as exc:  # noqa: BLE001 — main path owns recovery
                logger.debug("actor %s delivery lease renewal failed: %s", actor_id, exc)

    renewer = threading.Thread(
        target=_renew_claim,
        name=f"actor-delivery-{actor_id[:12]}",
        daemon=True,
    )
    renewer.start()
    os.environ[WAKEUP_ENV_FLAG] = "1"
    try:
        status = delivery.get("status") or actor["status"]
        detail = delivery.get("result_preview") or delivery.get("error") or ""
        prompt = (
            f"A background actor you started has finished.\n\n"
            f"- actor: {actor_id}\n"
            f"- status: {status}\n"
            f"- goal: {actor.get('goal') or ''}\n"
            f"- result: {detail}\n\n"
            "Continue the work this result unblocks. If it failed, decide whether to "
            "retry differently or report the blocker; do not silently repeat it."
        )
        if agent_factory is None:
            from atlas_runtime.agents import get_agent as agent_factory  # noqa: PLC0415

        mission = create_mission(
            conn, lock,
            title=f"actor wakeup: {str(actor.get('goal') or '')[:48]}",
            intent=prompt,
            origin="system",
            mission_id=mission_id,
        )
        run = start_run(
            conn, lock,
            mission_id=mission.id,
            session_id=session_id,
            agent_runtime="native",
            run_id=run_id,
        )
        if run.status in ("succeeded", "failed", "cancelled"):
            # Recovery from an older terminal/correlated run: no model replay.
            consumed = actor_service.consume_claimed_delivery(
                conn,
                lock,
                actor_id,
                claim_token=claim_token,
                followup_run_id=run.id,
            )
            return run.id if consumed else None
        outcome = agent_factory("native").execute(
            conn, lock, mission_id=mission.id, run_id=run.id, prompt=prompt
        )
        complete_run(
            conn, lock,
            run_id=run.id, mission_id=mission.id,
            status=outcome.status, summary=outcome.summary,
            delivery_actor_id=actor_id,
            delivery_claim_token=claim_token,
        )
        renew_stop.set()
        renewer.join(timeout=max(0.05, delivery_lease_seconds))
        return run.id
    except Exception as exc:  # noqa: BLE001 — the actor already finished cleanly
        logger.warning("actor %s wakeup run failed: %s", actor_id, exc)
        renew_stop.set()
        renewer.join(timeout=max(0.05, delivery_lease_seconds))
        actor_service.release_delivery_claim(
            conn, lock, actor_id, claim_token=claim_token
        )
        return None
    finally:
        renew_stop.set()
        os.environ.pop(WAKEUP_ENV_FLAG, None)


def run_actor(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    actor_id: str,
    *,
    agent_factory: Optional[Callable[[str], Any]] = None,
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
) -> bool:
    """Execute one actor in this process. Returns True on a terminal write.

    The child work is an ordinary mission+run so all evidence lands in the
    normal audit/run tables; the actor row stores only a bounded preview.
    """
    actor = actor_service.get_actor(conn, actor_id)
    if actor is None:
        logger.error("actor %s not found", actor_id)
        return False
    if actor["status"] != "queued":
        logger.info("actor %s already %s — nothing to do", actor_id, actor["status"])
        return False
    owner_token = str(uuid.uuid4())
    if not actor_service.mark_running(
        conn, lock, actor_id, pid=os.getpid(), owner_token=owner_token
    ):
        return False

    stop = threading.Event()

    def _beat() -> None:
        while not stop.wait(heartbeat_seconds):
            try:
                actor_service.heartbeat_actor(conn, lock, actor_id)
            except Exception as exc:  # noqa: BLE001
                logger.debug("actor heartbeat failed: %s", exc)

    beater = threading.Thread(target=_beat, name=f"actor-hb-{actor_id[:12]}", daemon=True)
    beater.start()
    try:
        if agent_factory is None:
            from atlas_runtime.agents import get_agent as agent_factory  # noqa: PLC0415

        workspace = actor.get("workspace_root")
        if workspace and os.path.isdir(workspace):
            os.chdir(workspace)

        mission = create_mission(
            conn, lock,
            title=f"actor: {actor['goal'][:64]}",
            intent=actor["goal"],
            origin="system",
        )
        run = start_run(
            conn, lock,
            mission_id=mission.id,
            session_id=actor.get("session_id"),
            agent_runtime="native",
        )
        # Link the actor to its run NOW, not at completion: until this exists
        # nothing connects a working actor to the audit trail carrying its
        # activity, so `op=logs` on a live actor had nothing to read.
        actor_service.attach_child_run(conn, lock, actor_id, run.id)
        runtime = agent_factory("native")
        outcome = runtime.execute(
            conn, lock,
            mission_id=mission.id,
            run_id=run.id,
            prompt=actor["goal"],
        )
        complete_run(
            conn, lock,
            run_id=run.id,
            mission_id=mission.id,
            status=outcome.status,
            summary=outcome.summary,
        )
        if outcome.status == "succeeded":
            actor_service.complete_actor(
                conn, lock, actor_id,
                result_preview=outcome.summary,
                child_run_id=run.id,
            )
        else:
            actor_service.fail_actor(
                conn, lock, actor_id,
                error=outcome.summary or outcome.stop_reason or "child run failed",
                child_run_id=run.id,
            )
        # Stop heartbeating before the wakeup drives a whole second run on this
        # connection: the actor is terminal, so the beat is already a no-op, and
        # two threads interleaving execute() on one sqlite3 connection raises
        # "bad parameter or other API misuse" (same hazard wait_for_actor
        # documents). The finally below is idempotent.
        stop.set()
        # After the terminal write, so a wakeup failure can never leave the
        # actor itself un-finalized.
        _wake_parent(conn, lock, actor_id, agent_factory=agent_factory)
        return True
    except Exception as exc:  # noqa: BLE001 — durable failure, never crash silent
        logger.warning("actor %s execution failed: %s", actor_id, exc)
        actor_service.fail_actor(conn, lock, actor_id, error=str(exc))
        return True
    finally:
        stop.set()


def main(argv: Optional[list[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1 or not args[0].strip():
        print("usage: python -m atlas_runtime.actor_worker <actor_id>", file=sys.stderr)
        return 2
    actor_id = args[0].strip()
    conn = atlas_db.connect()
    lock = threading.Lock()
    try:
        ok = run_actor(conn, lock, actor_id)
        return 0 if ok else 1
    finally:
        conn.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
