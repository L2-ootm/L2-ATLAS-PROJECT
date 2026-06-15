#!/usr/bin/env python3
"""Fresh-DB bootstrap smoke test for ATLAS v1.0 (Phase 9.5).

Proves that a brand-new SQLite database, after applying every migration in
infra/migrations/ in order, supports the full core loop at the service layer:

    create mission -> start run -> emit audit events -> read events back
    -> register/list models -> complete run

It exercises the exact functions the `atlas` CLI and the Rust gateway call,
against a throwaway temp DB (never touches ~/.atlas/atlas.db).

Exit 0 = smoke passed. Non-zero = a failure with context.

Usage (from repo root):
    python scripts/fresh_db_smoke.py
"""
from __future__ import annotations

import pathlib
import sqlite3
import sys
import tempfile
import threading

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "infra" / "migrations"

# Make the runtime importable without an editable install being on PATH.
sys.path.insert(0, str(REPO_ROOT / "services" / "agent-runtime"))

from atlas_runtime import audit_service, mission_service, model_registry, run_service  # noqa: E402


def apply_migrations(conn: sqlite3.Connection) -> list[str]:
    applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
        applied.append(path.name)
    conn.commit()
    return applied


def main() -> int:
    lock = threading.Lock()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = pathlib.Path(tmp) / "atlas-smoke.db"
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            return _run_loop(conn, lock)
        finally:
            conn.close()


def _run_loop(conn: sqlite3.Connection, lock: threading.Lock) -> int:
    if True:
        applied = apply_migrations(conn)
        print(f"[1] migrations applied: {', '.join(applied)}")
        if not applied:
            print("FAIL: no migrations found", file=sys.stderr)
            return 1

        mission = mission_service.create_mission(
            conn, lock, title="Smoke Mission", intent="Phase 9.5 fresh-DB smoke"
        )
        print(f"[2] mission created: {mission.id}")

        run = run_service.start_run(conn, lock, mission_id=mission.id)
        print(f"[3] run started: {run.id}")

        audit_service.emit(
            conn, lock, run_id=run.id, event_type="tool_call",
            tool_name="mock", data={"phase": "9.5"},
        )
        audit_service.emit(
            conn, lock, run_id=run.id, event_type="llm_call",
            tool_name="mock", data={"tokens": 1},
        )
        events = audit_service.get_events_for_run(conn, run_id=run.id)
        print(f"[4] audit events read back: {len(events)}")
        if len(events) < 2:
            print("FAIL: expected >= 2 audit events", file=sys.stderr)
            return 1

        model_registry.ensure_schema(conn)
        models = model_registry.list_models(conn, active_only=False)
        print(f"[5] model registry queried OK (rows: {len(models)})")

        run_service.complete_run(
            conn, lock, run_id=run.id, mission_id=mission.id,
            status="succeeded", summary="smoke complete",
        )
        final = mission_service.get_mission(conn, mission_id=mission.id)
        print(f"[6] run completed; mission status: {final.status}")

        # FK integrity: every audit event must reference the real run.
        orphans = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE run_id NOT IN (SELECT id FROM runs)"
        ).fetchone()[0]
        if orphans:
            print(f"FAIL: {orphans} orphaned audit rows", file=sys.stderr)
            return 1
        print("[7] FK integrity OK; no orphaned audit rows")

    print("\nSMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
