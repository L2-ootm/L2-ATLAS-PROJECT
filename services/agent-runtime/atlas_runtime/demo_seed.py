"""demo_seed — idempotent demo mission+run+audit+wiki seed for `atlas db init
--demo`. Makes ATLAS demoable end-to-end with zero configured credentials
(pairs with the deterministic mock provider in agents/mock.py).

Idempotency: missions have no natural unique business key to `INSERT OR
IGNORE` on (confirmed: mission_service exposes only create_mission/
list_missions, no find_by_title), so a sentinel marker file
(~/.atlas/.demo_seeded, or under ATLAS_HOME if set) is the idempotency guard
— checked before any insert, written only after all inserts succeed.

Wiki dir resolution: deliberately does NOT use atlas_wiki's own
`_get_wiki_dir()` default (Path.cwd() / "wiki"), which would scatter demo
content wherever the CLI happened to be invoked from. Instead resolves under
ATLAS_HOME (or ~/.atlas if unset) so demo wiki content always lands in the
ATLAS-owned home and is trivially cleanable alongside the rest of ATLAS state.
"""
from __future__ import annotations

import logging
import os
import pathlib
import sqlite3
import tempfile
import threading

from atlas_runtime import audit_service, mission_service, run_service
from atlas_wiki import wiki_service

logger = logging.getLogger(__name__)

DEMO_MISSION_TITLE = "Demo Mission — ATLAS Quickstart"
DEMO_MISSION_INTENT = "Deterministic demo seed for the one-command install path"
DEMO_RUN_SUMMARY = "Demo mission completed via deterministic mock provider."

_DEMO_WIKI_CONTENT = """# ATLAS Quickstart Demo Note

This is a demo wiki entry seeded by `atlas db init --demo`. It demonstrates
the LLM Wiki runtime ingesting a source file end-to-end, with zero provider
credentials required (the mission/run pair that produced it ran through the
deterministic mock provider).

Re-running `atlas db init --demo` will not duplicate this entry — the seed is
idempotent, gated by a sentinel file under the ATLAS home directory.
"""


def _atlas_home() -> pathlib.Path:
    override = os.environ.get("ATLAS_HOME")
    return pathlib.Path(override) if override else pathlib.Path.home() / ".atlas"


def _wiki_dir() -> pathlib.Path:
    wiki_dir = _atlas_home() / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    return wiki_dir


def _sentinel_file() -> pathlib.Path:
    """ATLAS_HOME-aware sentinel path (mirrors _wiki_dir's resolution).

    Computed lazily, not as a module-level constant: a constant evaluated at
    import time would freeze in whatever ATLAS_HOME (or lack of it) was set
    when this module first loaded, so a later os.environ["ATLAS_HOME"]
    override (e.g. scripts/fresh_install_smoke.py's isolated temp home) would
    be silently ignored and this would fall through to the real
    ~/.atlas/.demo_seeded sentinel instead.
    """
    return _atlas_home() / ".demo_seeded"


def _safe_emit(conn: sqlite3.Connection, lock: threading.Lock, *, run_id: str, **kwargs) -> None:
    """Fail-open audit emission (mirrors NativeAtlasAgent._safe_emit) — a
    logging hiccup during seeding must never corrupt the sentinel state."""
    try:
        audit_service.emit(conn, lock, run_id=run_id, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("demo_seed audit emit failed: %s", exc)


def seed_demo_data(conn: sqlite3.Connection, lock: threading.Lock) -> dict:
    """Seed one demo mission+run+audit-trail+wiki entry, idempotently.

    Returns {"created": False, "reason": "already seeded"} if the sentinel
    file already exists (no-op, non-destructive). Otherwise creates the demo
    rows in the same call sequence proven by scripts/fresh_db_smoke.py, then
    writes the sentinel only after every insert succeeds.
    """
    sentinel = _sentinel_file()
    if sentinel.exists():
        return {"created": False, "reason": "already seeded"}

    mission = mission_service.create_mission(
        conn, lock, title=DEMO_MISSION_TITLE, intent=DEMO_MISSION_INTENT,
    )
    run = run_service.start_run(conn, lock, mission_id=mission.id)

    _safe_emit(
        conn, lock, run_id=run.id, event_type="tool_call",
        tool_name="mock", data={"phase": "demo_seed"},
    )
    _safe_emit(
        conn, lock, run_id=run.id, event_type="llm_call",
        tool_name="mock", data={"tokens": 1},
    )

    run_service.complete_run(
        conn, lock, run_id=run.id, mission_id=mission.id,
        status="succeeded", summary=DEMO_RUN_SUMMARY,
    )

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8",
        ) as tmp:
            tmp.write(_DEMO_WIKI_CONTENT)
            tmp_path = tmp.name

        wiki_service.ingest_source(
            conn, lock, path=tmp_path, run_id=run.id, untrusted=False,
            wiki_dir=_wiki_dir(),
        )
    finally:
        if tmp_path is not None:
            try:
                pathlib.Path(tmp_path).unlink(missing_ok=True)
            except OSError as exc:  # noqa: BLE001 — never block seeding on cleanup
                logger.warning("demo_seed temp file cleanup failed: %s", exc)

    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("seeded", encoding="utf-8")

    return {"created": True, "mission_id": mission.id}
