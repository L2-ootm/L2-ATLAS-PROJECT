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
