"""Team run worker — the round-robin driver that turns team members via the
existing durable actor supervisor.

Launched detached (`python -m atlas_runtime.team_run_worker <team_run_id>`),
mirroring actor_worker.py's process model. Unlike actor_worker (one OS
process per actor), this process drives every member's turn in-process by
calling actor_worker.run_actor() directly — the team run is already the
detached unit of work, so spawning a further nested subprocess per turn
would only add process-launch latency with no isolation benefit. Each
turn's real work (mission/run/agent execution) still happens inside
run_actor's own child mission+run, so evidence is not commingled across
members or rounds.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sqlite3
import sys
import threading
from typing import Optional

from atlas_runtime import actor_service
from atlas_runtime import db as atlas_db
from atlas_runtime import team_run_service, team_service
from atlas_runtime.actor_worker import run_actor
from atlas_runtime.mission_service import create_mission
from atlas_runtime.run_service import complete_run, start_run

logger = logging.getLogger(__name__)

DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def launch_team_run_worker(
    team_run_id: str, *, db_path: Optional[str] = None
) -> Optional[int]:
    """Spawn the hidden detached worker for a team run. Returns the pid."""
    cmd = [sys.executable, "-m", "atlas_runtime.team_run_worker", team_run_id]
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
        logger.warning("team run worker launch failed for %s: %s", team_run_id, exc)
        return None


def run_team_run(conn: sqlite3.Connection, lock: threading.Lock, team_run_id: str) -> bool:
    """Drive one team run to completion. Returns True on a terminal write."""
    run = team_run_service.get_team_run(conn, team_run_id)
    if run is None:
        logger.error("team run %s not found", team_run_id)
        return False
    if run["status"] != "queued":
        logger.info("team run %s already %s — nothing to do", team_run_id, run["status"])
        return False

    team = team_service.get_team(conn, run["team_id"])
    members = team["members"] if team else []
    if not members:
        team_run_service.mark_team_run_running(conn, lock, team_run_id)
        team_run_service.finish_team_run(conn, lock, team_run_id, status="failed")
        return True

    kickoff = team_run_service.list_messages(conn, team_run_id)
    kickoff_text = kickoff[0]["content"] if kickoff else team["name"]

    parent_run_id = run.get("parent_run_id")
    mission = None
    if not parent_run_id:
        mission = create_mission(
            conn, lock,
            title=f"team run: {team['name']}"[:200],
            intent=kickoff_text,
            origin="system",
        )
        anchor_run = start_run(conn, lock, mission_id=mission.id, agent_runtime="native")
        parent_run_id = anchor_run.id

    if not team_run_service.mark_team_run_running(
        conn, lock, team_run_id, parent_run_id=parent_run_id
    ):
        return False

    cursors: dict[str, int] = {member["id"]: 0 for member in members}
    max_rounds = run["max_rounds"]
    final_status = "completed"
    try:
        for round_no in range(1, max_rounds + 1):
            team_run_service.set_current_round(conn, lock, team_run_id, round_no)
            done = False
            for member in members:
                inbox = team_run_service.build_inbox(
                    conn, team_run_id,
                    role_label=member["role_label"],
                    since_seq=cursors[member["id"]],
                )
                if inbox:
                    cursors[member["id"]] = inbox[-1]["seq"]
                goal = member["goal_template"] + team_run_service.render_inbox(inbox)
                actor, created = actor_service.spawn_actor(
                    conn, lock,
                    parent_run_id=parent_run_id,
                    goal=goal,
                    mode="joined",
                    role=member["role_label"],
                    model=member.get("model"),
                    idempotency_key=f"{team_run_id}:{round_no}:{member['id']}",
                )
                if created:
                    run_actor(conn, lock, actor["id"])
                actor = actor_service.get_actor(conn, actor["id"]) or actor
                content = actor.get("result_preview") or actor.get("error") or "(no output)"
                team_run_service.append_message(
                    conn, lock, team_run_id,
                    round_no=round_no,
                    sender_role=member["role_label"],
                    sender_actor_id=actor["id"],
                    content=content,
                )
                if team_run_service.is_done_signal(content):
                    done = True
                    break
            if done:
                break
    except Exception as exc:  # noqa: BLE001 — durable failure, never crash silent
        logger.warning("team run %s failed: %s", team_run_id, exc)
        final_status = "failed"

    team_run_service.finish_team_run(conn, lock, team_run_id, status=final_status)
    if mission is not None:
        complete_run(
            conn, lock,
            run_id=parent_run_id,
            mission_id=mission.id,
            status="succeeded" if final_status == "completed" else "failed",
            summary=f"team run {team_run_id} {final_status}",
        )
    return True


def main(argv: Optional[list[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1 or not args[0].strip():
        print("usage: python -m atlas_runtime.team_run_worker <team_run_id>", file=sys.stderr)
        return 2
    team_run_id = args[0].strip()
    conn = atlas_db.connect()
    lock = threading.Lock()
    try:
        ok = run_team_run(conn, lock, team_run_id)
        return 0 if ok else 1
    finally:
        conn.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = ["launch_team_run_worker", "run_team_run", "main"]
