"""ATLAS DB layer — connection + migration runner (single source of truth).

Before this module, every consumer (CLI `_get_connection`, test conftests, the
fresh-DB smoke) opened SQLite and/or blindly `executescript`-ed all migrations
with no applied-tracker, so existing DBs silently drifted and re-applying the
non-idempotent `ALTER ADD COLUMN` migrations (0005/0006) raised `duplicate column
name`. This module fixes that with a versioned `schema_migrations` tracker and a
drift-tolerant apply path, exposed via `atlas db init` / `atlas db status`.

Backend seam (Supabase/Postgres later): all SQLite specifics (`executescript`,
`sqlite3.OperationalError`, the duplicate-column string, the WAL pragma) are
confined to this module behind the function surface below. A Postgres backend
swaps `connect()` for a psycopg connection and `executescript` for `execute`,
resolving dialect via per-backend migration dirs; the `schema_migrations(version,
applied_at)` contract is already portable. Not implemented yet (no creds; YAGNI).
"""
from __future__ import annotations

import datetime
import os
import pathlib
import sqlite3

# db.py lives at services/agent-runtime/atlas_runtime/db.py -> parents[3] = repo root.
MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parents[3] / "infra" / "migrations"
DEFAULT_DB_PATH = pathlib.Path.home() / ".atlas" / "atlas.db"


def default_db_path() -> pathlib.Path:
    """Resolve the DB path at call time: ATLAS_DB > ATLAS_HOME/atlas.db > ~/.atlas/atlas.db.

    Env-aware lazily (not a frozen import-time constant) so CLI processes the
    gateway dispatches with ATLAS_DB/ATLAS_HOME exported write to the same DB
    the gateway reads — previously the CLI always hit the real ~/.atlas/atlas.db,
    which made isolated smokes/E2E against a temp home impossible.
    """
    env_db = os.environ.get("ATLAS_DB", "").strip()
    if env_db:
        return pathlib.Path(env_db).expanduser()
    env_home = os.environ.get("ATLAS_HOME", "").strip()
    if env_home:
        return pathlib.Path(env_home).expanduser() / "atlas.db"
    return DEFAULT_DB_PATH


def connect(db_path: str | pathlib.Path | None = None) -> sqlite3.Connection:
    """File-backed SQLite connection with WAL + FK enforcement (default ~/.atlas/atlas.db)."""
    path = pathlib.Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "  version TEXT PRIMARY KEY,"
        "  applied_at TEXT NOT NULL"
        ")"
    )
    conn.commit()


def applied_versions(conn: sqlite3.Connection) -> set[str]:
    ensure_migrations_table(conn)
    return {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}


def _migration_files(migrations_dir: pathlib.Path) -> list[pathlib.Path]:
    return sorted(pathlib.Path(migrations_dir).glob("*.sql"))


def pending_migrations(
    conn: sqlite3.Connection, migrations_dir: pathlib.Path = MIGRATIONS_DIR
) -> list[pathlib.Path]:
    done = applied_versions(conn)
    return [p for p in _migration_files(migrations_dir) if p.name not in done]


def _apply_sql_tolerant(conn: sqlite3.Connection, sql: str) -> None:
    """Apply one migration script via `executescript`.

    The only non-idempotent statements across our migrations are bare
    `ALTER TABLE ... ADD COLUMN` (0005/0006); everything else is
    CREATE ... IF NOT EXISTS (re-run safe, including the 0001 FTS triggers).

    On a drifted/hand-patched DB that already has the added column,
    `executescript` raises 'duplicate column name'. We swallow that and stamp the
    file as applied: in the only situation it occurs the additive IF-NOT-EXISTS
    statements are already satisfied, so nothing is lost. We deliberately do NOT
    re-split-and-rerun the script — naive ';' splitting would corrupt files that
    contain trigger bodies (BEGIN ... END). Any other OperationalError re-raises.
    """
    try:
        conn.executescript(sql)
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


def apply_migrations(
    conn: sqlite3.Connection, migrations_dir: pathlib.Path = MIGRATIONS_DIR
) -> list[str]:
    """Apply every not-yet-tracked migration in order. Returns the versions newly applied.

    Idempotent: a second call is a no-op. Drift-tolerant: a legacy/hand-patched DB
    with an empty tracker is adopted (duplicate-column swallowed) and stamped, so
    it converges without data loss. Non-destructive: migrations are additive
    (CREATE ... IF NOT EXISTS / ADD COLUMN); the runner never drops or truncates.
    """
    ensure_migrations_table(conn)
    done = applied_versions(conn)
    applied_now: list[str] = []
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for path in _migration_files(migrations_dir):
        if path.name in done:
            continue
        _apply_sql_tolerant(conn, path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (path.name, now),
        )
        conn.commit()
        applied_now.append(path.name)
    return applied_now


def migration_status(
    conn: sqlite3.Connection, migrations_dir: pathlib.Path = MIGRATIONS_DIR
) -> list[tuple[str, bool]]:
    """List (version, applied) for every migration file, in order."""
    done = applied_versions(conn)
    return [(p.name, p.name in done) for p in _migration_files(migrations_dir)]
