"""ATLAS DB layer — connection + migration runner (single source of truth).

Before this module, every consumer (CLI `_get_connection`, test conftests, the
fresh-DB smoke) opened SQLite and/or blindly `executescript`-ed all migrations
with no applied-tracker, so existing DBs silently drifted and re-applying the
non-idempotent `ALTER ADD COLUMN` migrations (0005/0006) raised `duplicate column
name`. This module fixes that with a versioned `schema_migrations` tracker and a
drift-tolerant apply path, exposed via `atlas db init` / `atlas db status`.

Backend seam (Supabase/Postgres later): all SQLite specifics (`executescript`,
schema preconditions for bare ADD COLUMN statements, the WAL pragma) are
confined to this module behind the function surface below. A Postgres backend
swaps `connect()` for a psycopg connection and `executescript` for `execute`,
resolving dialect via per-backend migration dirs; the `schema_migrations(version,
applied_at)` contract is already portable. Not implemented yet (no creds; YAGNI).
"""
from __future__ import annotations

import datetime
import os
import pathlib
import re
import sqlite3

# db.py lives at services/agent-runtime/atlas_runtime/db.py -> parents[3] = repo root.
MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parents[3] / "infra" / "migrations"
DEFAULT_DB_PATH = pathlib.Path.home() / ".atlas" / "atlas.db"
# Keep SQLite lock waits finite. Callers that can safely retry a write do so
# explicitly; callers that cannot receive an observable OperationalError
# instead of hanging indefinitely behind another process.
SQLITE_BUSY_TIMEOUT_MS = 250


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
    conn = sqlite3.connect(
        str(path),
        check_same_thread=False,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
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


_ADD_COLUMN = re.compile(
    r"(?im)^(?P<statement>\s*ALTER\s+TABLE\s+(?P<table>[A-Za-z_][A-Za-z0-9_]*)"
    r"\s+ADD\s+COLUMN\s+(?P<column>[A-Za-z_][A-Za-z0-9_]*)\b[^;]*;\s*)$"
)


def _prepare_migration_sql(conn: sqlite3.Connection, sql: str) -> str:
    """Make legacy bare ADD COLUMN statements explicitly idempotent.

    SQLite has no ``ADD COLUMN IF NOT EXISTS``. Inspecting the named table and
    removing only an already-satisfied whole ALTER statement is safer than
    swallowing a duplicate-column exception for the entire file: later
    statements in that file still run and the file is stamped only on success.
    """

    def replace_existing(match: re.Match[str]) -> str:
        table = match.group("table")
        column = match.group("column")
        columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        if column in columns:
            return f"-- already applied: {table}.{column}\n"
        return match.group("statement")

    return _ADD_COLUMN.sub(replace_existing, sql)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _apply_and_stamp_migration(
    conn: sqlite3.Connection, path: pathlib.Path, applied_at: str
) -> None:
    """Commit one migration file and its tracker row as one transaction."""
    # Migration files repeat this pragma, but SQLite ignores attempts to change
    # it inside a transaction. Set it before BEGIN so externally supplied
    # connections retain the same FK contract as db.connect().
    conn.execute("PRAGMA foreign_keys = ON")
    sql = _prepare_migration_sql(conn, path.read_text(encoding="utf-8"))
    script = (
        "BEGIN IMMEDIATE;\n"
        f"{sql}\n"
        "INSERT INTO schema_migrations(version, applied_at) VALUES "
        f"({_sql_literal(path.name)}, {_sql_literal(applied_at)});\n"
        "COMMIT;\n"
    )
    try:
        conn.executescript(script)
    except Exception:
        if conn.in_transaction:
            conn.rollback()
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
        _apply_and_stamp_migration(conn, path, now)
        applied_now.append(path.name)
    return applied_now


def migration_status(
    conn: sqlite3.Connection, migrations_dir: pathlib.Path = MIGRATIONS_DIR
) -> list[tuple[str, bool]]:
    """List (version, applied) for every migration file, in order."""
    done = applied_versions(conn)
    return [(p.name, p.name in done) for p in _migration_files(migrations_dir)]
