#!/usr/bin/env python3
"""Fresh-install e2e smoke test for ATLAS (Phase 10.0.2).

Proves the one-command install path's core promise on a throwaway,
clean environment, without Docker: setup -> db init --demo -> atlas up ->
atlas doctor -> a mock-mode mission run, end-to-end, against a temp DB and a
temp ATLAS_HOME.

Why this calls service functions directly (the `db`/`demo_seed`/`gateway_control`
/`cockpit_control`/agents modules) instead of subprocess-invoking the `atlas`
CLI: `db.connect()`, `gateway_control.PID_FILE`, and `cockpit_control.PID_FILE`
all hardcode `pathlib.Path.home() / ".atlas"` and do NOT honor the `ATLAS_HOME`
env var override (a known, documented landmine — see project memory
`cli-db-path-not-atlas-home`). A real `atlas` subprocess call would silently
mutate the operator's actual `~/.atlas/atlas.db`, which this smoke must never
do. Calling the same underlying functions the CLI dispatches to (against an
explicit temp-DB connection) exercises the identical code paths while staying
fully isolated, mirroring scripts/fresh_db_smoke.py's proven approach.

Exit 0 = smoke passed. Non-zero = a failure, with the failing step printed.

Usage (from repo root):
    python scripts/fresh_install_smoke.py
"""
from __future__ import annotations

import os
import pathlib
import sqlite3
import sys
import tempfile
import threading
from typing import Callable, Optional

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "infra" / "migrations"

# Make the runtime importable without an editable install being on PATH.
sys.path.insert(0, str(REPO_ROOT / "services" / "agent-runtime"))
sys.path.insert(0, str(REPO_ROOT / "services" / "wiki-runtime"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "atlas-core"))


def main(
    *,
    gateway_health_ok: Optional[Callable[[], bool]] = None,
    cockpit_health_ok: Optional[Callable[[], bool]] = None,
) -> int:
    """Run the full smoke sequence against a throwaway temp DB + ATLAS_HOME.

    `gateway_health_ok` / `cockpit_health_ok` are injectable so tests can
    simulate a failed `atlas up` without needing a real gateway/cockpit
    process running on this machine.
    """
    lock = threading.Lock()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        atlas_home = pathlib.Path(tmp) / "atlas-home"
        atlas_home.mkdir(parents=True, exist_ok=True)
        db_path = atlas_home / "atlas.db"

        # Point ATLAS_HOME at the temp dir for the duration of this process so
        # any ATLAS_HOME-aware module (config_service, demo_seed's wiki dir
        # resolution) stays isolated too, even though db.connect() itself
        # needs the explicit path override below (see module docstring).
        prior_home = os.environ.get("ATLAS_HOME")
        os.environ["ATLAS_HOME"] = str(atlas_home)
        try:
            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                return _run_steps(
                    conn,
                    lock,
                    gateway_health_ok=gateway_health_ok,
                    cockpit_health_ok=cockpit_health_ok,
                )
            finally:
                conn.close()
        finally:
            if prior_home is None:
                os.environ.pop("ATLAS_HOME", None)
            else:
                os.environ["ATLAS_HOME"] = prior_home


def _run_steps(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    gateway_health_ok: Optional[Callable[[], bool]],
    cockpit_health_ok: Optional[Callable[[], bool]],
) -> int:
    from atlas_runtime import db, demo_seed, run_executor
    from atlas_runtime.agents import get_agent

    # [1] db init --demo: apply migrations, then seed the demo mission/run/wiki.
    applied = db.apply_migrations(conn, migrations_dir=MIGRATIONS_DIR)
    print(f"[1] migrations applied: {', '.join(applied) if applied else '(none pending)'}")
    if not applied:
        print("FAIL: step 1 (db init) - no migrations found", file=sys.stderr)
        return 1

    seed_result = demo_seed.seed_demo_data(conn, lock)
    print(f"[1] demo seed: {seed_result}")
    if not seed_result.get("created", False) and "mission_id" not in seed_result:
        print(f"FAIL: step 1 (db init --demo) - seed did not report a mission: {seed_result}", file=sys.stderr)
        return 1

    # [2] atlas up: gateway + cockpit health, via the same health_ok probes
    # `atlas up`/`atlas doctor` use (injectable here so tests can simulate a
    # failed boot without a real process).
    if gateway_health_ok is None:
        from atlas_runtime import gateway_control

        gateway_health_ok = gateway_control.health_ok
    if cockpit_health_ok is None:
        from atlas_runtime import cockpit_control

        cockpit_health_ok = cockpit_control.health_ok

    gateway_up = gateway_health_ok()
    cockpit_up = cockpit_health_ok()
    print(f"[2] atlas up: gateway={'ok' if gateway_up else 'down'} cockpit={'ok' if cockpit_up else 'down'}")
    if not (gateway_up and cockpit_up):
        print(
            "FAIL: step 2 (atlas up) - gateway/cockpit did not report healthy "
            "(expected on a machine with no gateway/cockpit running; this is "
            "the failure path the second behavior test exercises)",
            file=sys.stderr,
        )
        return 1

    # [3] atlas doctor: db + config + gateway + cockpit + provider, mirroring
    # cli/doctor.py's aggregate check (independent try/except per check there;
    # here we assert the migration-status portion directly against our temp DB).
    pending = [version for version, ok in db.migration_status(conn, migrations_dir=MIGRATIONS_DIR) if not ok]
    print(f"[3] atlas doctor: db={'ok' if not pending else 'pending ' + ','.join(pending)}")
    if pending:
        print(f"FAIL: step 3 (atlas doctor) - pending migrations: {pending}", file=sys.stderr)
        return 1

    # [4] a mock-mode mission run: no provider credentials are set in this
    # temp ATLAS_HOME, so NativeAtlasAgent.execute() routes to the
    # deterministic mock provider (agents/mock.py) automatically.
    from atlas_runtime import mission_service, run_service

    mission = mission_service.create_mission(
        conn, lock, title="Fresh Install Smoke Mission", intent="Phase 10.0.2 fresh-install smoke",
    )
    run = run_service.start_run(conn, lock, mission_id=mission.id)
    outcome = run_executor.execute_run(
        conn, lock, agent=get_agent("native"), mission_id=mission.id, run_id=run.id,
        prompt="Fresh-install smoke: confirm the mock-mode run pipeline works end-to-end.",
    )
    print(f"[4] mock-mode mission run: status={outcome.status} summary={outcome.summary!r}")
    if outcome.status != "succeeded":
        print(f"FAIL: step 4 (mock-mode mission run) - outcome was {outcome.status!r}", file=sys.stderr)
        return 1

    print("\nSMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
