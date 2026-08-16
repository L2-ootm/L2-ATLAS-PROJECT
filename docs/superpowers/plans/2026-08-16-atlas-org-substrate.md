# ATLAS Org Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give ATLAS a standing organisational layer — departments, members, tiers, reporting lines, charters, lifecycle and a runtime mutation contract — above the per-run `actors` process table.

**Architecture:** Approach A: the org supersedes teams. `teams` becomes `departments` and `agent_presets` becomes `members` by additive `ALTER` then `RENAME`, so no data moves. A new `org_service.py` owns the invariants and mutations; `team_service.py` is reduced to a compatibility shim so the existing gateway routes, cockpit Teams tab and `atlas team *` CLI keep working unchanged. One new column on `actors` (`member_id`) binds a running process back to the member it is, which is what makes tiered authority checkable at all.

**Tech Stack:** Python 3.11, SQLite (raw `sqlite3`, lock-serialized writes), pytest, Typer CLI, Pydantic v2 config models. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-16-atlas-org-substrate-design.md`

## Global Constraints

- **Migration number is `0039`.** `0038_brain_node_provenance.sql` exists and is already applied to the live database.
- **A migration file on disk reaches the live `~/.atlas/atlas.db` within ~2h**, via the autonomous loop task, before any commit. Task 1 must complete and be reported before Task 2 creates the file.
- **Nothing is hard-deleted.** Dissolution is `lifecycle='dissolved'` + `archived_at`, never `DELETE`.
- **`member_id IS NULL` resolves to `worker` authority** — no org mutations. This is every cockpit, mission and CLI run today.
- **Equipping narrows, never widens.** A module is reachable when globally active AND (caller has no member context OR it is equipped to the caller's department).
- **No test may open a network socket.** Provider *configuration* validity only; the freellmapi sidecar is down by default.
- **The reaper is report-only** in this slice. It computes candidates and emits an audit event; it never dissolves.
- **Config knobs, not constants:** `org.reap_idle_days` default `14`, `org.promote_min_runs` default `3`.
- **Promotion vocabulary:** the gate emits `no_mutations | verified | contradicted | unverified | exempt`. There is no `fail`. Gate promotion requires ≥ `promote_min_runs` attributed completed runs, **≥1 `verified`**, **0 `contradicted`**.
- **Audit event types need two registrations before the first emit**: the `AuditEvent.event_type` Literal (`packages/atlas-core/atlas_core/schemas/core.py:319`) and the `surface_events.py` kind map. An unregistered type fails pydantic validation inside a fail-open emit and vanishes silently.
- Run the Python suite from `services/agent-runtime/`: `python -m pytest tests/ -q`. Lint with `ruff check .` from the repo root.

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/org_backfill_dryrun.py` | **new** — read-only probe over a copy of the live DB; reports what `0039`'s backfill would do. Task 1. |
| `infra/migrations/0039_org_substrate.sql` | **new** — the ALTER/RENAME/backfill DDL. Task 2. |
| `services/agent-runtime/atlas_runtime/org_service.py` | **new** — reads, invariants, mutations, authority resolution, promotion, reaper. The only module that writes `departments`/`members`. |
| `services/agent-runtime/atlas_runtime/org_bridge.py` | **new** — the `atlas_org` agent tool (one generic tool, `atlas_module` precedent). |
| `services/agent-runtime/atlas_runtime/team_service.py` | **modify** — reduced to a shim delegating to `org_service`, keeping every public name so `team_bridge`, `cli/main.py` and `team_run_worker` are untouched. |
| `services/agent-runtime/atlas_runtime/actor_service.py` | **modify** — `spawn_actor(member_id=…)`. |
| `services/agent-runtime/atlas_runtime/team_run_worker.py:133` | **modify** — pass `member_id`; stamp `last_active_at`. |
| `services/agent-runtime/atlas_runtime/module_service.py` | **modify** — `active_context_blocks(department_id=…)`, `equipped_module_ids()`. |
| `services/agent-runtime/atlas_runtime/context_service.py` | **modify** — resolve the run's department and pass it through. |
| `services/agent-runtime/atlas_runtime/runtime_daemon.py:99` | **modify** — reaper report on the startup hook. |
| `services/agent-runtime/atlas_runtime/agents/native.py:848` | **modify** — register the org bridge. |
| `services/agent-runtime/atlas_runtime/cli/main.py` | **modify** — `atlas org` sub-app. |
| `packages/atlas-core/atlas_core/schemas/control_plane.py` | **modify** — `OrgConfig`. |
| `packages/atlas-core/atlas_core/schemas/core.py:319` | **modify** — `org_mutation`, `org_reap_candidates` event types. |
| `services/agent-runtime/atlas_runtime/surface_events.py` | **modify** — map both to `tool_result`. |
| `services/agent-runtime/tests/test_org_migration.py` | **new** — backfill against a legacy-shaped DB. |
| `services/agent-runtime/tests/test_org_service.py` | **new** — invariants, authority, mutations, promotion, reaper, cascade. |
| `services/agent-runtime/tests/test_org_equipping.py` | **new** — narrowing rule + the no-member-context regression guard. |

**No Rust change is required.** The gateway's team routes shell out to the CLI (`dispatch_atlas(&state.atlas_cmd, &["team", "list"])`, `crates/atlas-gateway/src/lib.rs:1948`) rather than querying the tables, so the rename is invisible to it as long as `atlas team *` keeps working — which the shim guarantees.

---

## Task 1: Live-DB backfill dry-run probe

Spec §5 requires this **before** the migration file exists. Backfill rule 2 (a preset on two teams must be cloned) is a real-data condition; a fresh fixture contains exactly the rows whoever wrote it thought of.

**Files:**
- Create: `scripts/org_backfill_dryrun.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a printed report. No later task imports this module.

- [ ] **Step 1: Write the probe**

```python
"""Read-only dry-run of the 0039 org-substrate backfill.

Answers, against a COPY of the live database, the questions a fresh test
fixture cannot: how many presets sit on more than one team (and must be
cloned), how many sit on none, whether anything already looks like a chief,
and whether any name collision would break the UNIQUE constraints that
`agent_presets.name` and `teams.name` carry.

Read-only by construction: it copies the DB to a temp file and opens the copy.
Run it BEFORE infra/migrations/0039_org_substrate.sql exists on disk — the
autonomous loop applies migration files to the live database within ~2h.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import sqlite3
import tempfile


def _live_db() -> pathlib.Path:
    explicit = os.environ.get("ATLAS_DB", "").strip()
    if explicit:
        return pathlib.Path(explicit)
    home = os.environ.get("ATLAS_HOME", "").strip()
    root = pathlib.Path(home) if home else pathlib.Path.home() / ".atlas"
    return root / "atlas.db"


def main() -> int:
    src = _live_db()
    if not src.exists():
        print(f"no live database at {src} — nothing to probe")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        copy = pathlib.Path(tmp) / "atlas-copy.db"
        shutil.copy2(src, copy)
        conn = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
        try:
            teams = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
            presets = conn.execute("SELECT COUNT(*) FROM agent_presets").fetchone()[0]
            multi = conn.execute(
                "SELECT preset_id, COUNT(*) c FROM team_members"
                " GROUP BY preset_id HAVING c > 1"
            ).fetchall()
            orphans = conn.execute(
                "SELECT COUNT(*) FROM agent_presets p WHERE NOT EXISTS"
                " (SELECT 1 FROM team_members tm WHERE tm.preset_id = p.id)"
            ).fetchone()[0]
            chiefs = conn.execute(
                "SELECT id, name, role_label FROM agent_presets"
                " WHERE LOWER(role_label) LIKE '%chief%'"
            ).fetchall()
            clones = sum(count - 1 for _, count in multi)
            print(f"live db          : {src}")
            print(f"teams            : {teams}")
            print(f"presets          : {presets}")
            print(f"presets on >1 team: {len(multi)}  -> {clones} clone row(s) needed")
            for preset_id, count in multi:
                name = conn.execute(
                    "SELECT name FROM agent_presets WHERE id=?", (preset_id,)
                ).fetchone()
                print(f"    {preset_id}  {name[0] if name else '?'}  on {count} teams")
            print(f"presets on 0 teams: {orphans}  (become department_id NULL)")
            print(f"chief-ish presets : {len(chiefs)}")
            for row in chiefs:
                print(f"    {row[0]}  {row[1]}  role={row[2]}")
            print(
                "synthetic chief   : "
                + ("NOT needed" if chiefs else "WILL BE CREATED (backfill rule 5)")
            )
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it against the live database**

Run: `python scripts/org_backfill_dryrun.py`
Expected: a report. Record the actual numbers — Task 2's test fixture must contain at least one preset on two teams if the live DB has one, and the clone-naming rule must survive whatever names are really there.

- [ ] **Step 3: Commit**

```bash
git add scripts/org_backfill_dryrun.py
git commit -m "chore(org): dry-run what the org backfill would do to the live database"
```

---

## Task 2: Migration 0039 and its backfill

**Files:**
- Create: `infra/migrations/0039_org_substrate.sql`
- Create: `services/agent-runtime/tests/test_org_migration.py`

**Interfaces:**
- Consumes: Task 1's report (informational).
- Produces: tables `departments`, `members`, `department_modules`; column `actors.member_id`. Every later task reads these names.

The `db` fixture in `services/agent-runtime/tests/conftest.py` applies **all** migrations, so it cannot test a migration against legacy data. The test builds its own connection applying `0001`–`0038`, seeds the old shape, then applies `0039`.

- [ ] **Step 1: Write the failing test**

```python
"""0039 turns teams into departments without losing anyone."""
from __future__ import annotations

import pathlib
import sqlite3

import pytest

MIGRATIONS_DIR = (
    pathlib.Path(__file__).parent.parent.parent.parent / "infra" / "migrations"
)


def _legacy_db() -> sqlite3.Connection:
    """Every migration up to but excluding 0039 — the pre-org schema."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    for sql_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if sql_path.name.startswith("0039"):
            break
        conn.executescript(sql_path.read_text(encoding="utf-8"))
    return conn


def _apply_0039(conn: sqlite3.Connection) -> None:
    path = MIGRATIONS_DIR / "0039_org_substrate.sql"
    conn.executescript(path.read_text(encoding="utf-8"))


def _seed_legacy(conn: sqlite3.Connection) -> None:
    now = "2026-08-01T00:00:00+00:00"
    conn.executemany(
        "INSERT INTO teams(id, name, description, created_at, updated_at)"
        " VALUES (?,?,?,?,?)",
        [
            ("team-a", "Admissions", "", now, now),
            ("team-b", "Outreach", "", now, now),
        ],
    )
    conn.executemany(
        "INSERT INTO agent_presets(id, name, role_label, description,"
        " goal_template, model, provider, mode, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("p-solo", "Essay Reader", "reader", "", "Read essays.",
             None, None, "joined", now, now),
            ("p-shared", "Researcher", "researcher", "", "Research things.",
             None, None, "joined", now, now),
        ],
    )
    conn.executemany(
        "INSERT INTO team_members(team_id, preset_id, position) VALUES (?,?,?)",
        [
            ("team-a", "p-solo", 0),
            ("team-a", "p-shared", 1),
            ("team-b", "p-shared", 0),
        ],
    )
    conn.commit()


@pytest.fixture(name="migrated")
def migrated_fixture() -> sqlite3.Connection:
    conn = _legacy_db()
    _seed_legacy(conn)
    _apply_0039(conn)
    yield conn
    conn.close()


def test_teams_become_standing_departments(migrated: sqlite3.Connection) -> None:
    rows = migrated.execute(
        "SELECT name, lifecycle, created_by FROM departments ORDER BY name"
    ).fetchall()
    assert rows == [
        ("Admissions", "standing", "operator"),
        ("Outreach", "standing", "operator"),
    ]


def test_single_team_preset_lands_in_its_department(migrated: sqlite3.Connection) -> None:
    row = migrated.execute(
        "SELECT department_id, display_order, lifecycle FROM members WHERE id='p-solo'"
    ).fetchone()
    assert row == ("team-a", 0, "standing")


def test_preset_on_two_teams_is_cloned_once_per_department(
    migrated: sqlite3.Connection,
) -> None:
    rows = migrated.execute(
        "SELECT department_id, rationale FROM members"
        " WHERE id='p-shared' OR rationale LIKE 'migration clone from preset%'"
        " ORDER BY department_id"
    ).fetchall()
    departments = [r[0] for r in rows]
    assert departments == ["team-a", "team-b"]
    clone_rationales = [r[1] for r in rows if r[1]]
    assert clone_rationales == ["migration clone from preset p-shared"]


def test_clone_keeps_a_unique_name(migrated: sqlite3.Connection) -> None:
    names = [
        r[0]
        for r in migrated.execute(
            "SELECT name FROM members WHERE role_label='researcher' ORDER BY name"
        ).fetchall()
    ]
    assert len(names) == 2
    assert len(set(names)) == 2


def test_a_synthetic_chief_exists(migrated: sqlite3.Connection) -> None:
    row = migrated.execute(
        "SELECT department_id, parent_member_id, lifecycle FROM members"
        " WHERE tier='chief'"
    ).fetchall()
    assert len(row) == 1
    assert row[0] == (None, None, "standing")


def test_last_active_at_is_backfilled(migrated: sqlite3.Connection) -> None:
    nulls = migrated.execute(
        "SELECT COUNT(*) FROM departments WHERE last_active_at IS NULL"
    ).fetchone()[0]
    assert nulls == 0


def test_actors_gains_a_nullable_member_id(migrated: sqlite3.Connection) -> None:
    cols = {r[1] for r in migrated.execute("PRAGMA table_info(actors)").fetchall()}
    assert "member_id" in cols


def test_department_modules_exists(migrated: sqlite3.Connection) -> None:
    cols = {
        r[1] for r in migrated.execute("PRAGMA table_info(department_modules)").fetchall()
    }
    assert cols == {"department_id", "module_id", "equipped_at", "equipped_by"}


def test_legacy_team_members_is_left_in_place(migrated: sqlite3.Connection) -> None:
    # Frozen, not dropped: it is the only record of the pre-migration roster
    # and dropping it in the same migration that reads it removes the ability
    # to check the backfill against the live database afterwards.
    count = migrated.execute("SELECT COUNT(*) FROM team_members").fetchone()[0]
    assert count == 3
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_migration.py -q`
Expected: FAIL — `sqlite3.OperationalError: unable to open database file` or `FileNotFoundError` on `0039_org_substrate.sql`.

- [ ] **Step 3: Write the migration**

```sql
-- 0039: departments and members — the standing organisation above the run.
--
-- ATLAS had runs, per-run actors, and teams-as-flat-rosters. It had no notion
-- of who stands responsible for what between runs. `actors` is a process table
-- (parent_run_id NOT NULL, pid, heartbeat_at); a member is who works here, an
-- actor is what a member becomes while running.
--
-- Approach A (docs/superpowers/specs/2026-08-16-atlas-org-substrate-design.md):
-- the org SUPERSEDES teams rather than sitting beside it, because an additive
-- layer guarantees team/department semantic drift. Additive ALTERs first, then
-- RENAME, so nothing breaks mid-flight and no data moves.
--
-- Everything that predates this migration becomes `standing`: those teams and
-- presets predate the ephemeral concept and the operator already relies on them.
-- `team_members` is deliberately NOT dropped — it is the only record of the
-- pre-migration roster, and it is what makes the backfill checkable against the
-- live database after the fact. A later migration drops it.

-- departments (was: teams) --------------------------------------------------
ALTER TABLE teams ADD COLUMN charter        TEXT NOT NULL DEFAULT '';
ALTER TABLE teams ADD COLUMN lifecycle      TEXT NOT NULL DEFAULT 'ephemeral'
     CHECK (lifecycle IN ('ephemeral','standing','dissolved'));
ALTER TABLE teams ADD COLUMN created_by     TEXT NOT NULL DEFAULT 'operator'
     CHECK (created_by IN ('operator','chief','manager'));
ALTER TABLE teams ADD COLUMN origin_run_id  TEXT REFERENCES runs(id);
ALTER TABLE teams ADD COLUMN rationale      TEXT NOT NULL DEFAULT '';
ALTER TABLE teams ADD COLUMN promoted_at    TEXT;
ALTER TABLE teams ADD COLUMN promoted_by    TEXT;
ALTER TABLE teams ADD COLUMN last_active_at TEXT;
ALTER TABLE teams ADD COLUMN display_order  INTEGER NOT NULL DEFAULT 0;

UPDATE teams SET lifecycle='standing', last_active_at=updated_at;

ALTER TABLE teams RENAME TO departments;

-- members (was: agent_presets) ----------------------------------------------
ALTER TABLE agent_presets ADD COLUMN department_id    TEXT REFERENCES departments(id);
ALTER TABLE agent_presets ADD COLUMN tier             TEXT NOT NULL DEFAULT 'worker'
     CHECK (tier IN ('chief','manager','worker'));
ALTER TABLE agent_presets ADD COLUMN parent_member_id TEXT REFERENCES agent_presets(id);
ALTER TABLE agent_presets ADD COLUMN lifecycle        TEXT NOT NULL DEFAULT 'ephemeral'
     CHECK (lifecycle IN ('ephemeral','standing','dissolved'));
ALTER TABLE agent_presets ADD COLUMN created_by       TEXT NOT NULL DEFAULT 'operator'
     CHECK (created_by IN ('operator','chief','manager'));
ALTER TABLE agent_presets ADD COLUMN origin_run_id    TEXT REFERENCES runs(id);
ALTER TABLE agent_presets ADD COLUMN rationale        TEXT NOT NULL DEFAULT '';
ALTER TABLE agent_presets ADD COLUMN display_order    INTEGER NOT NULL DEFAULT 0;

UPDATE agent_presets SET lifecycle='standing';

-- Backfill rule 1: the first (lowest-position) roster row owns the preset.
UPDATE agent_presets
   SET department_id = (
        SELECT tm.team_id FROM team_members tm
         WHERE tm.preset_id = agent_presets.id
         ORDER BY tm.position ASC, tm.team_id ASC LIMIT 1),
       display_order = COALESCE((
        SELECT tm.position FROM team_members tm
         WHERE tm.preset_id = agent_presets.id
         ORDER BY tm.position ASC, tm.team_id ASC LIMIT 1), 0)
 WHERE EXISTS (SELECT 1 FROM team_members tm WHERE tm.preset_id = agent_presets.id);

-- Backfill rule 2: a preset on more than one team is cloned, one copy per
-- extra department. A member belongs to exactly one department, and picking
-- silently would lose the other roster. `name` is UNIQUE, so the clone is
-- suffixed with its department name.
INSERT INTO agent_presets(
    id, name, role_label, description, goal_template, model, provider, mode,
    created_at, updated_at, department_id, tier, parent_member_id, lifecycle,
    created_by, origin_run_id, rationale, display_order)
SELECT
    'member-clone-' || p.id || '-' || tm.team_id,
    p.name || ' (' || d.name || ')',
    p.role_label, p.description, p.goal_template, p.model, p.provider, p.mode,
    p.created_at, p.updated_at, tm.team_id, 'worker', NULL, 'standing',
    'operator', NULL, 'migration clone from preset ' || p.id, tm.position
  FROM team_members tm
  JOIN agent_presets p ON p.id = tm.preset_id
  JOIN departments   d ON d.id = tm.team_id
 WHERE tm.team_id <> p.department_id;

ALTER TABLE agent_presets RENAME TO members;

-- Backfill rule 5: exactly one chief, department-less and parent-less.
INSERT INTO members(
    id, name, role_label, description, goal_template, model, provider, mode,
    created_at, updated_at, department_id, tier, parent_member_id, lifecycle,
    created_by, origin_run_id, rationale, display_order)
SELECT
    'member-chief', 'Chief', 'chief', 'The standing head of the organisation.',
    'Decompose the mission across departments and hold each to its charter.',
    NULL, NULL, 'joined',
    (SELECT COALESCE(MIN(created_at), '1970-01-01T00:00:00+00:00') FROM members),
    (SELECT COALESCE(MIN(created_at), '1970-01-01T00:00:00+00:00') FROM members),
    NULL, 'chief', NULL, 'standing', 'operator', NULL, '', 0
 WHERE NOT EXISTS (SELECT 1 FROM members WHERE tier='chief');

-- the runtime binding: which member this process is
ALTER TABLE actors ADD COLUMN member_id TEXT REFERENCES members(id);

-- equipping: a department is equipped BY modules; it is not one.
-- module_id carries no FK on purpose — a module can go `missing` and the
-- equipment record must outlive that, exactly as module records do.
CREATE TABLE IF NOT EXISTS department_modules (
  department_id TEXT NOT NULL REFERENCES departments(id),
  module_id     TEXT NOT NULL,
  equipped_at   TEXT NOT NULL,
  equipped_by   TEXT NOT NULL,
  PRIMARY KEY (department_id, module_id)
);

CREATE INDEX IF NOT EXISTS idx_members_department    ON members(department_id);
CREATE INDEX IF NOT EXISTS idx_members_parent        ON members(parent_member_id);
CREATE INDEX IF NOT EXISTS idx_departments_lifecycle ON departments(lifecycle);
CREATE INDEX IF NOT EXISTS idx_actors_member         ON actors(member_id);
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_migration.py -q`
Expected: PASS, 9 tests.

- [ ] **Step 5: Run the whole suite — the rename touches every fixture**

Run: `cd services/agent-runtime && python -m pytest tests/ -q`
Expected: failures in team tests, because `team_service` still queries `teams`/`agent_presets`. That is Task 3. Record the failing test names; Task 3 must turn them all green without editing them.

- [ ] **Step 6: Commit**

```bash
git add infra/migrations/0039_org_substrate.sql services/agent-runtime/tests/test_org_migration.py
git commit -m "feat(org): departments and members, migrated from teams and presets"
```

---

## Task 3: `org_service` reads and invariants, `team_service` becomes a shim

**Files:**
- Create: `services/agent-runtime/atlas_runtime/org_service.py`
- Modify: `services/agent-runtime/atlas_runtime/team_service.py` (whole file)
- Create: `services/agent-runtime/tests/test_org_service.py`

**Interfaces:**
- Consumes: `departments`, `members` from Task 2.
- Produces:
  - `OrgLifecycleConflict(code: str, message: str)`
  - `get_department(conn, department_id) -> dict | None` (carries `members`)
  - `list_departments(conn, *, include_dissolved: bool = False) -> list[dict]`
  - `get_member(conn, member_id) -> dict | None`
  - `list_members(conn, *, department_id: str | None = None) -> list[dict]`
  - `chief(conn) -> dict | None`
  - `check_invariants(conn) -> list[str]` (empty list = healthy)
  - `set_department_members(conn, lock, department_id, member_ids) -> dict`

`team_service` keeps every name in its current `__all__` so `team_bridge.py:187`, `cli/main.py:1726-1875` and `team_run_worker.py:83` need no edit.

- [ ] **Step 1: Write the failing test**

```python
"""The org's standing structure: invariants, and orphans that do not vanish."""
from __future__ import annotations

import sqlite3
import threading

import pytest

from atlas_runtime import org_service


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    return threading.Lock()


def _seed_org(conn: sqlite3.Connection) -> None:
    now = "2026-08-16T00:00:00+00:00"
    conn.execute(
        "INSERT INTO departments(id, name, description, created_at, updated_at,"
        " charter, lifecycle, created_by, rationale, last_active_at, display_order)"
        " VALUES ('d1','Admissions','',?,?,'Read and rank applicants.',"
        " 'standing','operator','',?,0)",
        (now, now, now),
    )
    conn.executemany(
        "INSERT INTO members(id, name, role_label, description, goal_template,"
        " model, provider, mode, created_at, updated_at, department_id, tier,"
        " parent_member_id, lifecycle, created_by, rationale, display_order)"
        " VALUES (?,?,?,'',?,NULL,NULL,'joined',?,?,?,?,?,'standing','operator','',0)",
        [
            ("m-chief", "Chief", "chief", "Lead.", now, now, None, "chief", None),
            ("m-mgr", "Admissions Lead", "manager", "Manage.", now, now,
             "d1", "manager", "m-chief"),
            ("m-w1", "Essay Reader", "reader", "Read.", now, now,
             "d1", "worker", "m-mgr"),
        ],
    )
    conn.commit()


def test_healthy_org_has_no_invariant_violations(db: sqlite3.Connection) -> None:
    _seed_org(db)
    assert org_service.check_invariants(db) == []


def test_two_chiefs_is_a_violation(db: sqlite3.Connection) -> None:
    _seed_org(db)
    db.execute(
        "INSERT INTO members(id, name, role_label, description, goal_template,"
        " model, provider, mode, created_at, updated_at, tier, lifecycle,"
        " created_by, rationale, display_order)"
        " VALUES ('m-chief2','Other Chief','chief','','Lead.',NULL,NULL,'joined',"
        " '2026-08-16T00:00:00+00:00','2026-08-16T00:00:00+00:00','chief',"
        " 'standing','operator','',0)"
    )
    db.commit()
    assert any("chief" in v for v in org_service.check_invariants(db))


def test_worker_parented_outside_its_department_is_a_violation(
    db: sqlite3.Connection,
) -> None:
    _seed_org(db)
    now = "2026-08-16T00:00:00+00:00"
    db.execute(
        "INSERT INTO departments(id, name, description, created_at, updated_at,"
        " charter, lifecycle, created_by, rationale, last_active_at, display_order)"
        " VALUES ('d2','Outreach','',?,?,'','standing','operator','',?,0)",
        (now, now, now),
    )
    db.execute(
        "INSERT INTO members(id, name, role_label, description, goal_template,"
        " model, provider, mode, created_at, updated_at, department_id, tier,"
        " parent_member_id, lifecycle, created_by, rationale, display_order)"
        " VALUES ('m-w2','Stray','worker','','Work.',NULL,NULL,'joined',?,?,"
        " 'd2','worker','m-mgr','standing','operator','',0)",
        (now, now),
    )
    db.commit()
    assert any("m-w2" in v for v in org_service.check_invariants(db))


def test_unstaffed_department_has_no_manager_and_is_not_a_violation(
    db: sqlite3.Connection,
) -> None:
    """create_department and appoint_manager are separate operations."""
    now = "2026-08-16T00:00:00+00:00"
    db.execute(
        "INSERT INTO departments(id, name, description, created_at, updated_at,"
        " charter, lifecycle, created_by, rationale, last_active_at, display_order)"
        " VALUES ('d-empty','Forming','',?,?,'','ephemeral','chief','why',?,0)",
        (now, now, now),
    )
    db.commit()
    assert org_service.check_invariants(db) == []
    assert org_service.get_department(db, "d-empty")["addressable"] is False


def test_orphan_surfaces_at_department_root_rather_than_vanishing(
    db: sqlite3.Connection,
) -> None:
    """Ported from FounderOS hierarchy.ts:28 — the reason their chart never
    silently loses an agent."""
    _seed_org(db)
    db.execute("UPDATE members SET lifecycle='dissolved' WHERE id='m-mgr'")
    db.commit()
    dept = org_service.get_department(db, "d1")
    roots = [m["id"] for m in dept["members"] if m["parent_member_id"] is None]
    assert "m-w1" in roots


def test_list_departments_excludes_dissolved_by_default(db: sqlite3.Connection) -> None:
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='dissolved' WHERE id='d1'")
    db.commit()
    assert org_service.list_departments(db) == []
    assert len(org_service.list_departments(db, include_dissolved=True)) == 1
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_service.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'atlas_runtime.org_service'`.

- [ ] **Step 3: Write `org_service.py` reads and invariants**

```python
"""The standing organisation: departments, members, tiers, reporting lines.

A member is who works here; an actor is what a member becomes while running.
`actors` is a process table and stays one — this module owns the structure
above it, which survives between runs.

Approach A (docs/superpowers/specs/2026-08-16-atlas-org-substrate-design.md):
this module supersedes team_service, which is now a shim over it so the gateway
routes, cockpit Teams tab and `atlas team *` CLI keep working unchanged.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
import uuid
from typing import Any, Optional

NAME_CAP = 200
DESCRIPTION_CAP = 2000
GOAL_TEMPLATE_CAP = 4000
CHARTER_CAP = 4000
RATIONALE_MIN = 40
RATIONALE_CAP = 2000

TIERS = ("chief", "manager", "worker")
LIFECYCLES = ("ephemeral", "standing", "dissolved")


class OrgLifecycleConflict(ValueError):
    """Typed domain conflict for an unsafe org lifecycle transition."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    return {d[0]: row[i] for i, d in enumerate(cursor.description)}


# --- reads -----------------------------------------------------------------


def get_member(conn: sqlite3.Connection, member_id: str) -> Optional[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM members WHERE id=?", (member_id,))
    row = cur.fetchone()
    return _row_to_dict(cur, row) if row else None


def list_members(
    conn: sqlite3.Connection,
    *,
    department_id: Optional[str] = None,
    include_dissolved: bool = False,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if department_id is not None:
        clauses.append("department_id=?")
        params.append(department_id)
    if not include_dissolved:
        clauses.append("lifecycle != 'dissolved'")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    cur = conn.execute(
        f"SELECT * FROM members {where} ORDER BY display_order ASC, name ASC",  # noqa: S608
        params,
    )
    return [_row_to_dict(cur, row) for row in cur.fetchall()]


def chief(conn: sqlite3.Connection) -> Optional[dict[str, Any]]:
    cur = conn.execute(
        "SELECT * FROM members WHERE tier='chief' AND lifecycle != 'dissolved' LIMIT 1"
    )
    row = cur.fetchone()
    return _row_to_dict(cur, row) if row else None


def get_department(
    conn: sqlite3.Connection, department_id: str
) -> Optional[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM departments WHERE id=?", (department_id,))
    row = cur.fetchone()
    if row is None:
        return None
    dept = _row_to_dict(cur, row)
    members = list_members(conn, department_id=department_id)
    live = {m["id"] for m in members}
    # Orphan promotion (FounderOS hierarchy.ts:28): a member whose manager has
    # left surfaces at the department root instead of disappearing from the
    # chart along with the edge that used to hold it.
    for member in members:
        if member["parent_member_id"] not in live:
            member["parent_member_id"] = None
    dept["members"] = members
    dept["addressable"] = any(m["tier"] == "manager" for m in members)
    return dept


def list_departments(
    conn: sqlite3.Connection, *, include_dissolved: bool = False
) -> list[dict[str, Any]]:
    where = "" if include_dissolved else "WHERE lifecycle != 'dissolved'"
    cur = conn.execute(
        f"SELECT id FROM departments {where} ORDER BY display_order ASC, name ASC"  # noqa: S608
    )
    ids = [row[0] for row in cur.fetchall()]
    out = []
    for department_id in ids:
        dept = get_department(conn, department_id)
        if dept is not None:
            out.append(dept)
    return out


# --- invariants ------------------------------------------------------------


def check_invariants(conn: sqlite3.Connection) -> list[str]:
    """Every structural rule the org must satisfy. Empty list means healthy.

    Returned rather than raised: this is called from a CLI health command and
    from tests, and a caller that wants one violation to be fatal can raise on
    the first element. Invariant 2 is scoped to departments that HOLD members —
    `create_department` and `appoint_manager` are separate operations, so a
    freshly created department legitimately has no manager and is instead
    reported as not addressable.
    """
    violations: list[str] = []

    chiefs = conn.execute(
        "SELECT id, department_id, parent_member_id FROM members"
        " WHERE tier='chief' AND lifecycle != 'dissolved'"
    ).fetchall()
    if len(chiefs) != 1:
        violations.append(f"expected exactly one chief, found {len(chiefs)}")
    for chief_id, department_id, parent_id in chiefs:
        if department_id is not None or parent_id is not None:
            violations.append(
                f"chief {chief_id} must have no department and no parent"
            )

    rows = conn.execute(
        "SELECT department_id, COUNT(*) FROM members"
        " WHERE tier='manager' AND lifecycle != 'dissolved'"
        " AND department_id IS NOT NULL GROUP BY department_id"
    ).fetchall()
    for department_id, count in rows:
        if count != 1:
            violations.append(
                f"department {department_id} has {count} managers, expected 1"
            )
    for department_id, in conn.execute(
        "SELECT DISTINCT department_id FROM members"
        " WHERE lifecycle != 'dissolved' AND department_id IS NOT NULL"
    ).fetchall():
        managers = conn.execute(
            "SELECT COUNT(*) FROM members WHERE department_id=? AND tier='manager'"
            " AND lifecycle != 'dissolved'",
            (department_id,),
        ).fetchone()[0]
        if managers == 0:
            violations.append(
                f"department {department_id} holds members but has no manager"
            )

    strays = conn.execute(
        "SELECT w.id FROM members w JOIN members p ON p.id = w.parent_member_id"
        " WHERE w.tier='worker' AND w.lifecycle != 'dissolved'"
        " AND p.lifecycle != 'dissolved'"
        " AND (p.tier != 'manager' OR p.department_id IS NOT w.department_id)"
    ).fetchall()
    for (member_id,) in strays:
        violations.append(
            f"worker {member_id} is not parented to a manager in its own department"
        )
    return violations


def set_department_members(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    department_id: str,
    member_ids: list[str],
) -> dict[str, Any]:
    """Replace a department's roster and ordering in one transaction."""
    if not member_ids:
        raise ValueError("a department must have at least one member")
    if len(set(member_ids)) != len(member_ids):
        raise ValueError("duplicate member_id in roster")
    now = _now()
    with lock:
        with conn:
            if conn.execute(
                "SELECT 1 FROM departments WHERE id=?", (department_id,)
            ).fetchone() is None:
                raise ValueError(f"department {department_id!r} not found")
            for member_id in member_ids:
                if conn.execute(
                    "SELECT 1 FROM members WHERE id=?", (member_id,)
                ).fetchone() is None:
                    raise ValueError(f"member {member_id!r} not found")
            conn.execute(
                "UPDATE members SET department_id=NULL, updated_at=?"
                " WHERE department_id=?",
                (now, department_id),
            )
            for position, member_id in enumerate(member_ids):
                conn.execute(
                    "UPDATE members SET department_id=?, display_order=?, updated_at=?"
                    " WHERE id=?",
                    (department_id, position, now, member_id),
                )
            conn.execute(
                "UPDATE departments SET updated_at=? WHERE id=?", (now, department_id)
            )
    dept = get_department(conn, department_id)
    assert dept is not None
    return dept
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_service.py -q`
Expected: PASS, 6 tests.

- [ ] **Step 5: Rewrite `team_service.py` as a shim**

Replace the whole file. Every exported name keeps its signature; `teams`→`departments` and `agent_presets`→`members` in the SQL; the roster reads `members.department_id` instead of the frozen `team_members`.

```python
"""Compatibility shim over org_service — `teams` are now `departments`.

Approach A supersedes teams with the org substrate (0039). The gateway's team
routes shell out to `atlas team *`, the cockpit Teams tab consumes them, and
team_run_worker resolves a roster through `get_team`. None of those should
change for a schema rename, so this module keeps its entire public surface and
translates. Slice 4 inverts the IA and retires it.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
import uuid
from typing import Any, Optional

from atlas_runtime.org_service import (
    DESCRIPTION_CAP,
    GOAL_TEMPLATE_CAP,
    NAME_CAP,
    OrgLifecycleConflict,
    get_department,
    list_departments,
    set_department_members,
)

# Retained name: callers catch TeamLifecycleConflict by this name.
TeamLifecycleConflict = OrgLifecycleConflict


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    return {d[0]: row[i] for i, d in enumerate(cursor.description)}


def create_preset(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    name: str,
    role_label: str,
    goal_template: str,
    description: str = "",
    model: Optional[str] = None,
    provider: Optional[str] = None,
    mode: str = "joined",
) -> dict[str, Any]:
    name = (name or "").strip()
    role_label = (role_label or "").strip()
    goal_template = (goal_template or "").strip()
    if not name:
        raise ValueError("preset name must be non-empty")
    if not role_label:
        raise ValueError("preset role_label must be non-empty")
    if not goal_template:
        raise ValueError("preset goal_template must be non-empty")
    if mode not in ("joined", "detached"):
        raise ValueError(f"invalid preset mode: {mode!r}")
    name = name[:NAME_CAP]
    member_id = f"preset-{uuid.uuid4()}"
    now = _now()
    with lock:
        with conn:
            if conn.execute(
                "SELECT 1 FROM members WHERE name=?", (name,)
            ).fetchone() is not None:
                raise ValueError(f"a preset named {name!r} already exists")
            conn.execute(
                "INSERT INTO members(id, name, role_label, description,"
                " goal_template, model, provider, mode, created_at, updated_at,"
                " tier, lifecycle, created_by, rationale, display_order)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,'worker','standing','operator','',0)",
                (
                    member_id, name, role_label, description[:DESCRIPTION_CAP],
                    goal_template[:GOAL_TEMPLATE_CAP], model, provider, mode,
                    now, now,
                ),
            )
    preset = get_preset(conn, member_id)
    assert preset is not None
    return preset


def get_preset(conn: sqlite3.Connection, preset_id: str) -> Optional[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM members WHERE id=?", (preset_id,))
    row = cur.fetchone()
    return _row_to_dict(cur, row) if row else None


def list_presets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT * FROM members WHERE lifecycle != 'dissolved' ORDER BY name ASC"
    )
    return [_row_to_dict(cur, row) for row in cur.fetchall()]


def update_preset(
    conn: sqlite3.Connection, lock: threading.Lock, preset_id: str, **fields: Any
) -> dict[str, Any]:
    allowed = {
        "name", "role_label", "description", "goal_template", "model",
        "provider", "mode",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"cannot update fields: {sorted(unknown)}")
    updates: list[str] = []
    params: list[Any] = []
    for key, value in fields.items():
        if key == "mode" and value not in ("joined", "detached"):
            raise ValueError(f"invalid preset mode: {value!r}")
        if key in ("name", "role_label", "goal_template") and not str(value or "").strip():
            raise ValueError(f"preset {key} must be non-empty")
        updates.append(f"{key}=?")
        params.append(value)
    if not updates:
        raise ValueError("at least one field must be provided")
    updates.append("updated_at=?")
    params.append(_now())
    params.append(preset_id)
    with lock:
        with conn:
            if conn.execute(
                "SELECT 1 FROM members WHERE id=?", (preset_id,)
            ).fetchone() is None:
                raise ValueError(f"preset {preset_id!r} not found")
            conn.execute(
                f"UPDATE members SET {', '.join(updates)} WHERE id=?",  # noqa: S608
                params,
            )
    preset = get_preset(conn, preset_id)
    assert preset is not None
    return preset


def delete_preset(
    conn: sqlite3.Connection, lock: threading.Lock, preset_id: str
) -> bool:
    """Refuses to delete a member that still belongs to a department."""
    with lock:
        with conn:
            row = conn.execute(
                "SELECT department_id FROM members WHERE id=?", (preset_id,)
            ).fetchone()
            if row is not None and row[0]:
                raise ValueError(
                    "preset is still a member of one or more teams; remove it"
                    " from those rosters first"
                )
            cur = conn.execute("DELETE FROM members WHERE id=?", (preset_id,))
            return cur.rowcount == 1


def create_team(
    conn: sqlite3.Connection, lock: threading.Lock, *, name: str, description: str = ""
) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("team name must be non-empty")
    name = name[:NAME_CAP]
    department_id = f"team-{uuid.uuid4()}"
    now = _now()
    with lock:
        with conn:
            if conn.execute(
                "SELECT 1 FROM departments WHERE name=?", (name,)
            ).fetchone() is not None:
                raise ValueError(f"a team named {name!r} already exists")
            conn.execute(
                "INSERT INTO departments(id, name, description, created_at,"
                " updated_at, charter, lifecycle, created_by, rationale,"
                " last_active_at, display_order)"
                " VALUES (?,?,?,?,?,'','standing','operator','',?,0)",
                (department_id, name, description[:DESCRIPTION_CAP], now, now, now),
            )
    team = get_team(conn, department_id)
    assert team is not None
    return team


def get_team(conn: sqlite3.Connection, team_id: str) -> Optional[dict[str, Any]]:
    return get_department(conn, team_id)


def list_teams(
    conn: sqlite3.Connection, *, include_archived: bool = False
) -> list[dict[str, Any]]:
    return list_departments(conn, include_dissolved=include_archived)


def update_team(
    conn: sqlite3.Connection, lock: threading.Lock, team_id: str, **fields: Any
) -> dict[str, Any]:
    allowed = {"name", "description"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"cannot update fields: {sorted(unknown)}")
    updates: list[str] = []
    params: list[Any] = []
    for key, value in fields.items():
        if key == "name" and not str(value or "").strip():
            raise ValueError("team name must be non-empty")
        updates.append(f"{key}=?")
        params.append(value)
    if not updates:
        raise ValueError("at least one field must be provided")
    updates.append("updated_at=?")
    params.append(_now())
    params.append(team_id)
    with lock:
        with conn:
            if conn.execute(
                "SELECT 1 FROM departments WHERE id=?", (team_id,)
            ).fetchone() is None:
                raise ValueError(f"team {team_id!r} not found")
            conn.execute(
                f"UPDATE departments SET {', '.join(updates)} WHERE id=?",  # noqa: S608
                params,
            )
    team = get_team(conn, team_id)
    assert team is not None
    return team


def delete_team(conn: sqlite3.Connection, lock: threading.Lock, team_id: str) -> bool:
    with lock:
        with conn:
            run = conn.execute(
                "SELECT status FROM team_runs WHERE team_id=? LIMIT 1", (team_id,)
            ).fetchone()
            if run is not None:
                code = (
                    "team_has_active_run"
                    if run[0] in ("queued", "running")
                    else "team_has_history"
                )
                message = (
                    "team has an active run; cancel it before archiving the team"
                    if code == "team_has_active_run"
                    else "team has historical runs and cannot be physically"
                    " deleted; archive it"
                )
                raise OrgLifecycleConflict(code, message)
            conn.execute(
                "UPDATE members SET department_id=NULL WHERE department_id=?",
                (team_id,),
            )
            try:
                cur = conn.execute("DELETE FROM departments WHERE id=?", (team_id,))
            except sqlite3.IntegrityError as exc:
                raise OrgLifecycleConflict(
                    "team_dependency_conflict",
                    "team has dependent records and cannot be physically deleted",
                ) from exc
            return cur.rowcount == 1


def archive_team(
    conn: sqlite3.Connection, lock: threading.Lock, team_id: str
) -> dict[str, Any]:
    now = _now()
    with lock:
        with conn:
            if conn.execute(
                "SELECT 1 FROM departments WHERE id=?", (team_id,)
            ).fetchone() is None:
                raise ValueError(f"team {team_id!r} not found")
            conn.execute(
                "UPDATE departments SET archived_at=COALESCE(archived_at, ?),"
                " updated_at=? WHERE id=?",
                (now, now, team_id),
            )
    team = get_team(conn, team_id)
    assert team is not None
    return team


def set_team_members(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    team_id: str,
    preset_ids: list[str],
) -> dict[str, Any]:
    return set_department_members(conn, lock, team_id, preset_ids)


__all__ = [
    "create_preset", "get_preset", "list_presets", "update_preset",
    "delete_preset", "create_team", "get_team", "list_teams", "update_team",
    "delete_team", "archive_team", "TeamLifecycleConflict", "set_team_members",
]
```

- [ ] **Step 6: Run the whole suite green**

Run: `cd services/agent-runtime && python -m pytest tests/ -q`
Expected: PASS. Every test that failed at the end of Task 2 must now pass **without being edited**. If a team test needs editing, the shim is wrong — fix the shim, not the test.

- [ ] **Step 7: Commit**

```bash
git add services/agent-runtime/atlas_runtime/org_service.py services/agent-runtime/atlas_runtime/team_service.py services/agent-runtime/tests/test_org_service.py
git commit -m "feat(org): the standing structure, with teams kept working over it"
```

---

## Task 4: The runtime binding — `actors.member_id` and caller authority

The authority rules in the mutation contract are unenforceable until a running process can say which member it is. `team_run_worker.py:133` already holds the member row and throws the id away.

**Files:**
- Modify: `services/agent-runtime/atlas_runtime/actor_service.py` (`spawn_actor`)
- Modify: `services/agent-runtime/atlas_runtime/team_run_worker.py:133-141`
- Modify: `services/agent-runtime/atlas_runtime/org_service.py` (append)
- Modify: `services/agent-runtime/tests/test_org_service.py` (append)

**Interfaces:**
- Consumes: `get_member`, `chief` from Task 3.
- Produces:
  - `spawn_actor(..., member_id: Optional[str] = None)` — keyword-only, defaults to None so no existing caller changes.
  - `org_service.caller_authority(conn, *, actor_id: str | None = None, run_id: str | None = None, operator: bool = False) -> str` returning `'operator' | 'chief' | 'manager' | 'worker'` (a tool call knows its run, not its actor — see Task 8)
  - `org_service.touch_department(conn, lock, member_id) -> None`

- [ ] **Step 1: Write the failing test (append to `tests/test_org_service.py`)**

```python
def test_spawning_a_team_member_records_which_member_it_is(
    db: sqlite3.Connection, lock: threading.Lock, run_id: str
) -> None:
    from atlas_runtime import actor_service

    _seed_org(db)
    actor, _ = actor_service.spawn_actor(
        db, lock, parent_run_id=run_id, goal="Read the essays.",
        role="reader", member_id="m-w1",
    )
    stored = db.execute(
        "SELECT member_id FROM actors WHERE id=?", (actor["id"],)
    ).fetchone()
    assert stored[0] == "m-w1"


def test_authority_defaults_to_worker_when_no_member_context(
    db: sqlite3.Connection, lock: threading.Lock, run_id: str
) -> None:
    """Every cockpit, mission and CLI run today. A run with no org context
    must not be able to restructure the org."""
    from atlas_runtime import actor_service

    _seed_org(db)
    actor, _ = actor_service.spawn_actor(
        db, lock, parent_run_id=run_id, goal="Do a thing.",
    )
    assert org_service.caller_authority(db, actor_id=actor["id"]) == "worker"
    assert org_service.caller_authority(db, actor_id=None) == "worker"


def test_authority_resolves_the_members_tier(
    db: sqlite3.Connection, lock: threading.Lock, run_id: str
) -> None:
    from atlas_runtime import actor_service

    _seed_org(db)
    for member_id, expected in (("m-chief", "chief"), ("m-mgr", "manager")):
        actor, _ = actor_service.spawn_actor(
            db, lock, parent_run_id=run_id, goal="Lead.", member_id=member_id,
            idempotency_key=f"key-{member_id}",
        )
        assert org_service.caller_authority(db, actor_id=actor["id"]) == expected


def test_operator_flag_beats_the_actor_lookup(db: sqlite3.Connection) -> None:
    _seed_org(db)
    assert org_service.caller_authority(db, operator=True) == "operator"


def test_spawning_stamps_the_departments_activity_clock(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    db.execute("UPDATE departments SET last_active_at=NULL WHERE id='d1'")
    db.commit()
    org_service.touch_department(db, lock, "m-w1")
    stamped = db.execute(
        "SELECT last_active_at FROM departments WHERE id='d1'"
    ).fetchone()[0]
    assert stamped is not None


def test_touch_department_is_a_noop_for_a_member_without_one(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    org_service.touch_department(db, lock, "m-chief")  # chief has no department
    org_service.touch_department(db, lock, "does-not-exist")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_service.py -q -k "member_id or authority or activity or noop"`
Expected: FAIL — `TypeError: spawn_actor() got an unexpected keyword argument 'member_id'`.

- [ ] **Step 3: Add `member_id` to `spawn_actor`**

In `actor_service.py`, add the keyword-only parameter after `session_id` and include the column in the `INSERT`:

```python
def spawn_actor(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    parent_run_id: str,
    goal: str,
    mode: str = "joined",
    role: str = "worker",
    model: Optional[str] = None,
    parent_actor_id: Optional[str] = None,
    session_id: Optional[str] = None,
    # Which standing member this process IS. `role` is a free-text label and
    # cannot answer that; without this column every tier rule in the org
    # mutation contract is a sentence rather than a check. Optional because
    # most runs have no org context, and NULL resolves to worker authority.
    member_id: Optional[str] = None,
    workspace_root: Optional[str] = None,
    depth: int = 1,
    idempotency_key: Optional[str] = None,
    wakeup_parent: bool = False,
) -> tuple[dict[str, Any], bool]:
```

Find the `INSERT INTO actors(...)` statement in the same function and add `member_id` to the column list and `member_id` to the parameter tuple, in the same position.

- [ ] **Step 4: Append authority resolution to `org_service.py`**

```python
# --- the runtime binding ---------------------------------------------------

AUTHORITY_NONE = "worker"


def caller_authority(
    conn: sqlite3.Connection,
    *,
    actor_id: Optional[str] = None,
    run_id: Optional[str] = None,
    operator: bool = False,
) -> str:
    """Which tier is calling: 'operator' | 'chief' | 'manager' | 'worker'.

    `operator=True` is set by the CLI and the cockpit action paths, which act
    with the operator's own authority and are the only callers permitted to
    promote.

    Everything else resolves through `actors.member_id`. A tool call knows its
    run and not its actor, so `run_id` resolves the actor through
    `actors.child_run_id` — the row actor_worker sets when it starts the child.

    A NULL member_id — every cockpit chat, mission and CLI-started run today —
    resolves to `worker`, which holds no mutation authority. That default is
    deliberate: a run with no organisational context must not be able to
    restructure the organisation, and failing open here would hand that power
    to every run in the system.
    """
    if operator:
        return "operator"
    if not actor_id and run_id:
        row = conn.execute(
            "SELECT id FROM actors WHERE child_run_id=?", (run_id,)
        ).fetchone()
        actor_id = row[0] if row else None
    if not actor_id:
        return AUTHORITY_NONE
    row = conn.execute(
        "SELECT m.tier FROM actors a JOIN members m ON m.id = a.member_id"
        " WHERE a.id=? AND m.lifecycle != 'dissolved'",
        (actor_id,),
    ).fetchone()
    if not row or row[0] not in TIERS:
        return AUTHORITY_NONE
    return str(row[0])


def touch_department(
    conn: sqlite3.Connection, lock: threading.Lock, member_id: Optional[str]
) -> None:
    """Stamp the member's department as active now — the reaper's only clock.

    Best-effort and never raises: a spawned actor is already running, and the
    idle clock is bookkeeping. Called at the spawn site rather than derived
    later, because 'when did this department last do anything' cannot be
    recovered from a world that has moved on.
    """
    if not member_id:
        return
    try:
        with lock:
            with conn:
                conn.execute(
                    "UPDATE departments SET last_active_at=?"
                    " WHERE id = (SELECT department_id FROM members WHERE id=?)"
                    " AND id IS NOT NULL",
                    (_now(), member_id),
                )
    except sqlite3.Error:
        return
```

- [ ] **Step 5: Pass the member id at the one spawn site**

In `services/agent-runtime/atlas_runtime/team_run_worker.py`, at the `spawn_actor` call (line ~133):

```python
                actor, created = actor_service.spawn_actor(
                    conn, lock,
                    parent_run_id=parent_run_id,
                    goal=goal,
                    mode="joined",
                    role=member["role_label"],
                    # The member row is in hand here and nowhere later. Carrying
                    # the id is what makes this process attributable to a
                    # standing member — for authority, and for the promotion
                    # arithmetic that counts a department's runs.
                    member_id=member["id"],
                    model=member.get("model"),
                    idempotency_key=f"{team_run_id}:{round_no}:{member['id']}",
                )
                org_service.touch_department(conn, lock, member["id"])
                if created:
                    run_actor(conn, lock, actor["id"])
```

Add `org_service` to the module import at line 26:

```python
from atlas_runtime import org_service, team_run_service, team_service, verification_gate
```

- [ ] **Step 6: Run the tests**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_service.py tests/test_team_run_worker.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/agent-runtime/atlas_runtime/actor_service.py services/agent-runtime/atlas_runtime/team_run_worker.py services/agent-runtime/atlas_runtime/org_service.py services/agent-runtime/tests/test_org_service.py
git commit -m "feat(org): a running actor now says which member it is"
```

---

## Task 5: The mutation contract

**Files:**
- Modify: `packages/atlas-core/atlas_core/schemas/core.py:319`
- Modify: `services/agent-runtime/atlas_runtime/surface_events.py`
- Modify: `services/agent-runtime/atlas_runtime/org_service.py` (append)
- Create: `services/agent-runtime/tests/test_org_mutations.py`

**Interfaces:**
- Consumes: `caller_authority` (Task 4).
- Produces:
  - `create_department(conn, lock, *, name, charter, rationale, authority, run_id=None) -> dict`
  - `appoint_manager(conn, lock, *, department_id, name, role_label, goal_template, rationale, authority, run_id=None, model=None) -> dict`
  - `hire(conn, lock, *, department_id, name, role_label, goal_template, parent_member_id, rationale, authority, actor_department_id=None, run_id=None, model=None) -> dict`
  - `dissolve(conn, lock, *, target_kind, target_id, reason, authority, actor_department_id=None, run_id=None) -> dict`
  - `OrgAuthorityError(ValueError)`
  - `MUTATION_CAP_PER_RUN = 10`

- [ ] **Step 1: Register the audit event types first**

In `packages/atlas-core/atlas_core/schemas/core.py`, inside the `event_type` Literal (before the closing `]` at line ~319):

```python
        # The org restructured itself: a department created, a manager
        # appointed, a worker hired, a module equipped, something dissolved or
        # promoted. Carries the acting tier and the stated rationale, so an org
        # ATLAS invented mid-run is answerable afterwards.
        "org_mutation",
        # What the idle reaper WOULD dissolve. Report-only: the event is the
        # whole output, and the operator applies it with `atlas org reap --apply`.
        "org_reap_candidates",
```

In `services/agent-runtime/atlas_runtime/surface_events.py`, beside `"self_extension": "tool_result",`:

```python
    "org_mutation": "tool_result",
    "org_reap_candidates": "tool_result",
```

- [ ] **Step 2: Write the failing test**

```python
"""Who may restructure the org, and what it costs."""
from __future__ import annotations

import json
import sqlite3
import threading

import pytest

from atlas_runtime import org_service

from .test_org_service import _seed_org  # reuse the seeded org


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    return threading.Lock()


def test_chief_creates_an_ephemeral_department(
    db: sqlite3.Connection, lock: threading.Lock, run_id: str
) -> None:
    _seed_org(db)
    dept = org_service.create_department(
        db, lock, name="Research", charter="Find out what is true.",
        rationale="The mission needs standing research capacity beyond one run.",
        authority="chief", run_id=run_id,
    )
    assert dept["lifecycle"] == "ephemeral"
    assert dept["created_by"] == "chief"
    assert dept["origin_run_id"] == run_id


def test_a_worker_cannot_create_a_department(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    with pytest.raises(org_service.OrgAuthorityError):
        org_service.create_department(
            db, lock, name="Shadow", charter="c",
            rationale="A worker should not be able to do this at all, ever.",
            authority="worker",
        )


def test_a_manager_cannot_create_a_department(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    with pytest.raises(org_service.OrgAuthorityError):
        org_service.create_department(
            db, lock, name="Shadow", charter="c",
            rationale="A manager staffs its own department and shapes nothing else.",
            authority="manager",
        )


def test_a_manager_hires_only_into_its_own_department(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    other = org_service.create_department(
        db, lock, name="Outreach", charter="Reach out.",
        rationale="Somewhere else entirely, to hire into and be refused.",
        authority="chief",
    )
    with pytest.raises(org_service.OrgAuthorityError):
        org_service.hire(
            db, lock, department_id=other["id"], name="Intruder",
            role_label="worker", goal_template="Work.",
            parent_member_id="m-mgr", authority="manager",
            actor_department_id="d1",
        )


def test_a_rationale_is_required_and_must_say_something(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    with pytest.raises(ValueError):
        org_service.create_department(
            db, lock, name="Thin", charter="c", rationale="because",
            authority="chief",
        )


def test_every_mutation_emits_its_audit_event(
    db: sqlite3.Connection, lock: threading.Lock, run_id: str
) -> None:
    _seed_org(db)
    org_service.create_department(
        db, lock, name="Research", charter="Find out what is true.",
        rationale="The mission needs standing research capacity beyond one run.",
        authority="chief", run_id=run_id,
    )
    rows = db.execute(
        "SELECT data FROM audit_events WHERE run_id=? AND event_type='org_mutation'",
        (run_id,),
    ).fetchall()
    assert len(rows) == 1
    payload = json.loads(rows[0][0])
    assert payload["operation"] == "create_department"
    assert payload["authority"] == "chief"
    assert payload["rationale"].startswith("The mission needs")


def test_the_per_run_cap_refuses_the_next_mutation(
    db: sqlite3.Connection, lock: threading.Lock, run_id: str
) -> None:
    _seed_org(db)
    for i in range(org_service.MUTATION_CAP_PER_RUN):
        org_service.create_department(
            db, lock, name=f"Dept {i}", charter="c",
            rationale="Restructuring competes with work; this run is spending its budget.",
            authority="chief", run_id=run_id,
        )
    with pytest.raises(org_service.OrgAuthorityError) as exc:
        org_service.create_department(
            db, lock, name="One Too Many", charter="c",
            rationale="Restructuring competes with work; this run is spending its budget.",
            authority="chief", run_id=run_id,
        )
    assert "cap" in str(exc.value).lower()


def test_dissolve_marks_state_and_never_deletes(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    org_service.dissolve(
        db, lock, target_kind="department", target_id="d1",
        reason="No longer needed.", authority="operator",
    )
    row = db.execute(
        "SELECT lifecycle, archived_at FROM departments WHERE id='d1'"
    ).fetchone()
    assert row[0] == "dissolved"
    assert row[1] is not None


def test_dissolving_a_department_dissolves_its_ephemeral_members(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    db.execute("UPDATE members SET lifecycle='ephemeral' WHERE id='m-w1'")
    db.execute("UPDATE members SET lifecycle='ephemeral' WHERE id='m-mgr'")
    db.commit()
    org_service.dissolve(
        db, lock, target_kind="department", target_id="d1",
        reason="Experiment over.", authority="chief",
    )
    lifecycles = dict(
        db.execute(
            "SELECT id, lifecycle FROM members WHERE department_id='d1'"
        ).fetchall()
    )
    assert lifecycles == {"m-mgr": "dissolved", "m-w1": "dissolved"}


def test_standing_members_block_dissolution_and_the_error_says_what_to_do(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)  # m-mgr and m-w1 are standing
    with pytest.raises(org_service.OrgLifecycleConflict) as exc:
        org_service.dissolve(
            db, lock, target_kind="department", target_id="d1",
            reason="Cleaning up.", authority="chief",
        )
    assert "reassign" in str(exc.value).lower()
    assert exc.value.code == "department_has_standing_members"
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_mutations.py -q`
Expected: FAIL with `AttributeError: module 'atlas_runtime.org_service' has no attribute 'create_department'`.

- [ ] **Step 4: Append the mutations to `org_service.py`**

```python
# --- mutations -------------------------------------------------------------

# Restructuring competes with work. The real economy (a budget shared with
# messages) is slice 2's; a flat per-run cap is the precedent `materialize`
# already set, and slice 1 must not forward-depend on an unbuilt slice.
MUTATION_CAP_PER_RUN = 10


class OrgAuthorityError(ValueError):
    """The caller's tier does not permit this mutation."""


def _require(authority: str, allowed: tuple[str, ...], operation: str) -> None:
    if authority not in allowed:
        raise OrgAuthorityError(
            f"{operation} requires {' or '.join(allowed)}; caller is {authority!r}"
        )


def _check_rationale(rationale: str) -> str:
    rationale = (rationale or "").strip()
    if len(rationale) < RATIONALE_MIN:
        raise ValueError(
            f"a rationale of at least {RATIONALE_MIN} characters is required:"
            " what this department or member is for, and why it did not already"
            " exist"
        )
    return rationale[:RATIONALE_CAP]


def _check_cap(conn: sqlite3.Connection, run_id: Optional[str]) -> None:
    if not run_id:
        return
    spent = conn.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=? AND event_type='org_mutation'",
        (run_id,),
    ).fetchone()[0]
    if spent >= MUTATION_CAP_PER_RUN:
        raise OrgAuthorityError(
            f"org mutation cap reached for this run ({MUTATION_CAP_PER_RUN});"
            " restructuring competes with the work the run was started for"
        )


def _emit_mutation(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: Optional[str],
    operation: str,
    authority: str,
    target_kind: str,
    target_id: str,
    rationale: str,
) -> None:
    """The durable half of a mutation. Fail-open: the row is already written.

    `org_mutation` must be registered in the AuditEvent Literal AND the
    surface_events kind map before this ever runs — an unregistered type fails
    pydantic validation inside this try and disappears without a trace.
    """
    if not run_id:
        return
    try:
        from atlas_runtime import audit_service  # noqa: PLC0415

        audit_service.emit(
            conn, lock,
            run_id=run_id,
            event_type="org_mutation",
            tool_name="atlas_org",
            data={
                "operation": operation,
                "authority": authority,
                "target_kind": target_kind,
                "target_id": target_id,
                "rationale": rationale,
            },
        )
    except Exception:  # noqa: BLE001 — bookkeeping never fails a mutation
        return


def create_department(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    name: str,
    charter: str,
    rationale: str,
    authority: str,
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    _require(authority, ("operator", "chief"), "create_department")
    rationale = _check_rationale(rationale)
    _check_cap(conn, run_id)
    name = (name or "").strip()[:NAME_CAP]
    if not name:
        raise ValueError("department name must be non-empty")
    department_id = f"dept-{uuid.uuid4()}"
    now = _now()
    with lock:
        with conn:
            if conn.execute(
                "SELECT 1 FROM departments WHERE name=?", (name,)
            ).fetchone() is not None:
                raise ValueError(f"a department named {name!r} already exists")
            conn.execute(
                "INSERT INTO departments(id, name, description, created_at,"
                " updated_at, charter, lifecycle, created_by, origin_run_id,"
                " rationale, last_active_at, display_order)"
                " VALUES (?,?,'',?,?,?,'ephemeral',?,?,?,?,0)",
                (
                    department_id, name, now, now, charter[:CHARTER_CAP],
                    "operator" if authority == "operator" else "chief",
                    run_id, rationale, now,
                ),
            )
    _emit_mutation(
        conn, lock, run_id=run_id, operation="create_department",
        authority=authority, target_kind="department", target_id=department_id,
        rationale=rationale,
    )
    dept = get_department(conn, department_id)
    assert dept is not None
    return dept


def _insert_member(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    department_id: Optional[str],
    name: str,
    role_label: str,
    goal_template: str,
    tier: str,
    parent_member_id: Optional[str],
    created_by: str,
    rationale: str,
    run_id: Optional[str],
    model: Optional[str],
) -> str:
    name = (name or "").strip()[:NAME_CAP]
    role_label = (role_label or "").strip()
    goal_template = (goal_template or "").strip()[:GOAL_TEMPLATE_CAP]
    if not name:
        raise ValueError("member name must be non-empty")
    if not role_label:
        raise ValueError("member role_label must be non-empty")
    if not goal_template:
        raise ValueError("member goal_template must be non-empty")
    member_id = f"member-{uuid.uuid4()}"
    now = _now()
    with lock:
        with conn:
            if conn.execute(
                "SELECT 1 FROM members WHERE name=?", (name,)
            ).fetchone() is not None:
                raise ValueError(f"a member named {name!r} already exists")
            position = conn.execute(
                "SELECT COALESCE(MAX(display_order) + 1, 0) FROM members"
                " WHERE department_id IS ?",
                (department_id,),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO members(id, name, role_label, description,"
                " goal_template, model, provider, mode, created_at, updated_at,"
                " department_id, tier, parent_member_id, lifecycle, created_by,"
                " origin_run_id, rationale, display_order)"
                " VALUES (?,?,?,'',?,?,NULL,'joined',?,?,?,?,?,'ephemeral',?,?,?,?)",
                (
                    member_id, name, role_label, goal_template, model, now, now,
                    department_id, tier, parent_member_id, created_by, run_id,
                    rationale, position,
                ),
            )
    return member_id


def appoint_manager(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    department_id: str,
    name: str,
    role_label: str,
    goal_template: str,
    rationale: str,
    authority: str,
    run_id: Optional[str] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    _require(authority, ("operator", "chief"), "appoint_manager")
    rationale = _check_rationale(rationale)
    _check_cap(conn, run_id)
    existing = conn.execute(
        "SELECT id FROM members WHERE department_id=? AND tier='manager'"
        " AND lifecycle != 'dissolved'",
        (department_id,),
    ).fetchone()
    if existing is not None:
        raise OrgLifecycleConflict(
            "department_already_has_a_manager",
            f"department {department_id} already has manager {existing[0]};"
            " dissolve or reassign it before appointing another",
        )
    head = chief(conn)
    if head is None:
        raise OrgLifecycleConflict(
            "no_chief", "the organisation has no chief to parent a manager to"
        )
    member_id = _insert_member(
        conn, lock, department_id=department_id, name=name, role_label=role_label,
        goal_template=goal_template, tier="manager", parent_member_id=head["id"],
        created_by="operator" if authority == "operator" else "chief",
        rationale=rationale, run_id=run_id, model=model,
    )
    _emit_mutation(
        conn, lock, run_id=run_id, operation="appoint_manager",
        authority=authority, target_kind="member", target_id=member_id,
        rationale=rationale,
    )
    member = get_member(conn, member_id)
    assert member is not None
    return member


def hire(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    department_id: str,
    name: str,
    role_label: str,
    goal_template: str,
    parent_member_id: str,
    rationale: str,
    authority: str,
    actor_department_id: Optional[str] = None,
    run_id: Optional[str] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    _require(authority, ("operator", "chief", "manager"), "hire")
    if authority == "manager" and actor_department_id != department_id:
        raise OrgAuthorityError(
            "a manager staffs only its own department"
            f" (caller is in {actor_department_id!r}, target is {department_id!r})"
        )
    rationale = _check_rationale(rationale)
    _check_cap(conn, run_id)
    parent = get_member(conn, parent_member_id)
    if parent is None or parent["tier"] != "manager":
        raise ValueError("parent_member_id must resolve to a manager")
    if parent["department_id"] != department_id:
        raise ValueError("the parent manager must be in the same department")
    member_id = _insert_member(
        conn, lock, department_id=department_id, name=name, role_label=role_label,
        goal_template=goal_template, tier="worker",
        parent_member_id=parent_member_id,
        created_by="operator" if authority == "operator" else authority,
        rationale=rationale, run_id=run_id, model=model,
    )
    _emit_mutation(
        conn, lock, run_id=run_id, operation="hire", authority=authority,
        target_kind="member", target_id=member_id, rationale=rationale,
    )
    member = get_member(conn, member_id)
    assert member is not None
    return member


def dissolve(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    target_kind: str,
    target_id: str,
    reason: str,
    authority: str,
    actor_department_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """State, never DELETE — runs and evidence reference these rows forever.

    `target_kind` is explicit rather than inferred from the id so a caller
    cannot dissolve a department by passing an id it believed was a member's.
    """
    if target_kind not in ("department", "member"):
        raise ValueError("target_kind must be 'department' or 'member'")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("dissolution requires a stated reason")
    _check_cap(conn, run_id)
    now = _now()

    if target_kind == "department":
        _require(authority, ("operator", "chief"), "dissolve department")
        standing = conn.execute(
            "SELECT COUNT(*) FROM members WHERE department_id=?"
            " AND lifecycle='standing'",
            (target_id,),
        ).fetchone()[0]
        if standing:
            raise OrgLifecycleConflict(
                "department_has_standing_members",
                f"department {target_id} holds {standing} standing member(s);"
                " reassign them to another department first, then dissolve",
            )
        with lock:
            with conn:
                conn.execute(
                    "UPDATE departments SET lifecycle='dissolved',"
                    " archived_at=COALESCE(archived_at, ?), updated_at=?"
                    " WHERE id=?",
                    (now, now, target_id),
                )
                # Cascade: an ephemeral member exists to serve its department
                # and has nowhere to stand once it is gone.
                conn.execute(
                    "UPDATE members SET lifecycle='dissolved', updated_at=?"
                    " WHERE department_id=? AND lifecycle='ephemeral'",
                    (now, target_id),
                )
    else:
        _require(authority, ("operator", "chief", "manager"), "dissolve member")
        member = get_member(conn, target_id)
        if member is None:
            raise ValueError(f"member {target_id!r} not found")
        if authority == "manager":
            if member["department_id"] != actor_department_id:
                raise OrgAuthorityError("a manager dissolves only its own crew")
            if member["tier"] != "worker":
                raise OrgAuthorityError("a manager may not dissolve a manager or the chief")
        with lock:
            with conn:
                conn.execute(
                    "UPDATE members SET lifecycle='dissolved', updated_at=?"
                    " WHERE id=?",
                    (now, target_id),
                )

    _emit_mutation(
        conn, lock, run_id=run_id, operation="dissolve", authority=authority,
        target_kind=target_kind, target_id=target_id, rationale=reason,
    )
    if target_kind == "department":
        result = get_department(conn, target_id)
    else:
        result = get_member(conn, target_id)
    assert result is not None
    return result
```

- [ ] **Step 5: Run the tests**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_mutations.py -q`
Expected: PASS, 10 tests.

- [ ] **Step 6: Commit**

```bash
git add packages/atlas-core/atlas_core/schemas/core.py services/agent-runtime/atlas_runtime/surface_events.py services/agent-runtime/atlas_runtime/org_service.py services/agent-runtime/tests/test_org_mutations.py
git commit -m "feat(org): tiered authority over a contract that can refuse the caller"
```

---

## Task 6: Promotion, the reaper, and config knobs

**Files:**
- Modify: `packages/atlas-core/atlas_core/schemas/control_plane.py`
- Modify: `services/agent-runtime/atlas_runtime/org_service.py` (append)
- Modify: `services/agent-runtime/atlas_runtime/runtime_daemon.py:99-111`
- Create: `services/agent-runtime/tests/test_org_lifecycle.py`

**Interfaces:**
- Consumes: `dissolve`, `_emit_mutation` (Task 5).
- Produces:
  - `OrgConfig(reap_idle_days: int = 14, promote_min_runs: int = 3)` on `AtlasConfig.org`
  - `promotion_evidence(conn, department_id) -> dict` with keys `runs`, `verified`, `contradicted`, `eligible`
  - `promote(conn, lock, *, target_kind, target_id, authority, run_id=None) -> dict`
  - `reap_candidates(conn, *, now=None) -> list[dict]`
  - `reap(conn, lock, *, apply: bool = False, run_id=None) -> list[dict]`

- [ ] **Step 1: Add the config model**

In `packages/atlas-core/atlas_core/schemas/control_plane.py`, after `ContextConfig`:

```python
class OrgConfig(_FrozenControlPlaneModel):
    # An ephemeral department idle beyond this many days becomes a reap
    # candidate. Report-only in slice 1: the reaper lists, the operator applies.
    reap_idle_days: int = Field(default=14, ge=1)
    # Completed runs attributed to a department before the gate may promote it
    # ephemeral -> standing. Attribution is actors.member_id -> department_id.
    promote_min_runs: int = Field(default=3, ge=1)
```

And on `AtlasConfig` (line ~319), after `modules`:

```python
    org: OrgConfig = Field(default_factory=OrgConfig)
```

- [ ] **Step 2: Write the failing test**

```python
"""Promotion is earned from the gate's own record; the reaper only reports."""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading

import pytest

from atlas_runtime import org_service

from .test_org_service import _seed_org


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    return threading.Lock()


def _attribute_run(
    conn: sqlite3.Connection, *, run_id: str, member_id: str, state: str
) -> None:
    """One completed run attributed to a member, with a gate verdict.

    `runs.mission_id` is NOT NULL with an FK to missions, and the schema is
    (id, mission_id, session_id, status, started_at, finished_at, summary) —
    see infra/migrations/0001_core.sql:15. The actor's `parent_run_id` also
    needs a real run, so the mission is reused for both.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    mission_id = f"mission-{run_id}"
    conn.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at,"
        " updated_at) VALUES (?,?,'','pending','',?,?)",
        (mission_id, f"m-{run_id}", now, now),
    )
    conn.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at,"
        " finished_at, summary) VALUES (?,?,NULL,'completed',?,?,'')",
        (run_id, mission_id, now, now),
    )
    conn.execute(
        "INSERT INTO actors(id, parent_run_id, idempotency_key, role, goal,"
        " status, created_at, updated_at, member_id, child_run_id)"
        " VALUES (?,?,?,'worker','g','completed',?,?,?,?)",
        (f"actor-{run_id}", run_id, f"key-{run_id}", now, now, member_id, run_id),
    )
    conn.execute(
        "INSERT INTO audit_events(id, run_id, event_type, timestamp, data)"
        " VALUES (?,?,'verification_verdict',?,?)",
        (f"ev-{run_id}", run_id, now, json.dumps({"state": state})),
    )
    conn.commit()


def test_promotion_needs_one_verified_and_no_contradiction(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='ephemeral' WHERE id='d1'")
    for i, state in enumerate(("verified", "unverified", "no_mutations")):
        _attribute_run(db, run_id=f"run-{i}", member_id="m-w1", state=state)
    evidence = org_service.promotion_evidence(db, "d1")
    assert evidence["runs"] == 3
    assert evidence["verified"] == 1
    assert evidence["contradicted"] == 0
    assert evidence["eligible"] is True


def test_all_unverified_does_not_promote(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    """A department that never had anything checked has earned nothing."""
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='ephemeral' WHERE id='d1'")
    for i in range(3):
        _attribute_run(db, run_id=f"run-{i}", member_id="m-w1", state="unverified")
    assert org_service.promotion_evidence(db, "d1")["eligible"] is False


def test_one_contradiction_blocks_promotion(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='ephemeral' WHERE id='d1'")
    for i, state in enumerate(("verified", "verified", "contradicted")):
        _attribute_run(db, run_id=f"run-{i}", member_id="m-w1", state=state)
    assert org_service.promotion_evidence(db, "d1")["eligible"] is False


def test_a_run_with_no_member_context_counts_for_nobody(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='ephemeral' WHERE id='d1'")
    _attribute_run(db, run_id="run-x", member_id="m-w1", state="verified")
    db.execute("UPDATE actors SET member_id=NULL WHERE id='actor-run-x'")
    db.commit()
    assert org_service.promotion_evidence(db, "d1")["runs"] == 0


def test_the_chief_may_not_promote(db: sqlite3.Connection, lock: threading.Lock) -> None:
    """Promotion is the operator's boundary — the whole point of the ladder."""
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='ephemeral' WHERE id='d1'")
    db.commit()
    with pytest.raises(org_service.OrgAuthorityError):
        org_service.promote(
            db, lock, target_kind="department", target_id="d1", authority="chief"
        )


def test_operator_promotion_records_who_promoted(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='ephemeral' WHERE id='d1'")
    db.commit()
    org_service.promote(
        db, lock, target_kind="department", target_id="d1", authority="operator"
    )
    row = db.execute(
        "SELECT lifecycle, promoted_by, promoted_at FROM departments WHERE id='d1'"
    ).fetchone()
    assert row[0] == "standing"
    assert row[1] == "operator"
    assert row[2] is not None


def test_gate_promotion_records_the_gate(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='ephemeral' WHERE id='d1'")
    for i, state in enumerate(("verified", "verified", "verified")):
        _attribute_run(db, run_id=f"run-{i}", member_id="m-w1", state=state)
    org_service.promote(
        db, lock, target_kind="department", target_id="d1", authority="gate"
    )
    assert db.execute(
        "SELECT promoted_by FROM departments WHERE id='d1'"
    ).fetchone()[0] == "gate"


def test_gate_promotion_refuses_without_the_evidence(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='ephemeral' WHERE id='d1'")
    db.commit()
    with pytest.raises(org_service.OrgLifecycleConflict):
        org_service.promote(
            db, lock, target_kind="department", target_id="d1", authority="gate"
        )


def _age_department(conn: sqlite3.Connection, department_id: str, days: int) -> None:
    stale = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    ).isoformat()
    conn.execute(
        "UPDATE departments SET last_active_at=? WHERE id=?", (stale, department_id)
    )
    conn.commit()


def test_reap_lists_an_idle_ephemeral_department(db: sqlite3.Connection) -> None:
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='ephemeral' WHERE id='d1'")
    _age_department(db, "d1", 30)
    assert [c["id"] for c in org_service.reap_candidates(db)] == ["d1"]


def test_reap_never_lists_a_standing_department(db: sqlite3.Connection) -> None:
    _seed_org(db)
    _age_department(db, "d1", 365)
    assert org_service.reap_candidates(db) == []


def test_reap_skips_a_department_with_a_live_actor(
    db: sqlite3.Connection, lock: threading.Lock, run_id: str
) -> None:
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='ephemeral' WHERE id='d1'")
    _age_department(db, "d1", 30)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO actors(id, parent_run_id, idempotency_key, role, goal,"
        " status, created_at, updated_at, member_id)"
        " VALUES ('actor-live',?, 'k-live','worker','g','running',?,?,'m-w1')",
        (run_id, now, now),
    )
    db.commit()
    assert org_service.reap_candidates(db) == []


def test_reap_falls_back_to_created_at_when_never_active(
    db: sqlite3.Connection,
) -> None:
    """A department created seconds ago has not spawned yet and is not idle."""
    _seed_org(db)
    db.execute(
        "UPDATE departments SET lifecycle='ephemeral', last_active_at=NULL"
        " WHERE id='d1'"
    )
    db.commit()
    assert org_service.reap_candidates(db) == []


def test_reap_reports_and_does_not_dissolve(
    db: sqlite3.Connection, lock: threading.Lock, run_id: str
) -> None:
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='ephemeral' WHERE id='d1'")
    db.execute("UPDATE members SET lifecycle='ephemeral' WHERE department_id='d1'")
    _age_department(db, "d1", 30)
    reported = org_service.reap(db, lock, run_id=run_id)
    assert [c["id"] for c in reported] == ["d1"]
    assert db.execute(
        "SELECT lifecycle FROM departments WHERE id='d1'"
    ).fetchone()[0] == "ephemeral"
    events = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id=? AND"
        " event_type='org_reap_candidates'",
        (run_id,),
    ).fetchone()[0]
    assert events == 1


def test_reap_apply_dissolves(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    db.execute("UPDATE departments SET lifecycle='ephemeral' WHERE id='d1'")
    db.execute("UPDATE members SET lifecycle='ephemeral' WHERE department_id='d1'")
    _age_department(db, "d1", 30)
    org_service.reap(db, lock, apply=True)
    assert db.execute(
        "SELECT lifecycle FROM departments WHERE id='d1'"
    ).fetchone()[0] == "dissolved"
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_lifecycle.py -q`
Expected: FAIL — `AttributeError: module 'atlas_runtime.org_service' has no attribute 'promotion_evidence'`.

- [ ] **Step 4: Append lifecycle to `org_service.py`**

```python
# --- lifecycle: promotion and the reaper -----------------------------------


def _org_config() -> Any:
    from atlas_runtime import config_service  # noqa: PLC0415

    try:
        return config_service.load_config().org
    except Exception:  # noqa: BLE001 — defaults must not depend on a readable config
        from atlas_core.schemas.control_plane import OrgConfig  # noqa: PLC0415

        return OrgConfig()


def promotion_evidence(
    conn: sqlite3.Connection, department_id: str
) -> dict[str, Any]:
    """What the gate's own record says this department has earned.

    The gate emits `no_mutations | verified | contradicted | unverified |
    exempt` — there is no `fail`, and requiring every run to be `verified`
    would make promotion unreachable, because `unverified` and `exempt` are the
    normal outcome for a department that writes documents. So: enough runs, at
    least one checked and passing, and nothing refuted.

    A run reaches a department only through actors.member_id — a run with no
    member context is attributed to nobody and counts toward no promotion.
    """
    cfg = _org_config()
    rows = conn.execute(
        "SELECT ae.data FROM audit_events ae"
        " JOIN runs r  ON r.id = ae.run_id"
        " JOIN actors a ON a.child_run_id = r.id"
        " JOIN members m ON m.id = a.member_id"
        " WHERE m.department_id = ? AND ae.event_type = 'verification_verdict'"
        "   AND r.status IN ('completed','succeeded')",
        (department_id,),
    ).fetchall()
    states: list[str] = []
    for (data,) in rows:
        try:
            payload = json.loads(data) if data else {}
        except (TypeError, ValueError):
            continue
        state = payload.get("state")
        if isinstance(state, str):
            states.append(state)
    verified = sum(1 for s in states if s == "verified")
    contradicted = sum(1 for s in states if s == "contradicted")
    eligible = (
        len(states) >= cfg.promote_min_runs and verified >= 1 and contradicted == 0
    )
    return {
        "department_id": department_id,
        "runs": len(states),
        "verified": verified,
        "contradicted": contradicted,
        "required_runs": cfg.promote_min_runs,
        "eligible": eligible,
    }


def promote(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    target_kind: str,
    target_id: str,
    authority: str,
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """ephemeral -> standing. The operator's boundary; the chief may not cross it.

    The chief creates and dissolves. Letting it also promote would let ATLAS
    make its own inventions permanent on the operator's machine, which is the
    one thing the ladder exists to prevent.
    """
    if target_kind not in ("department", "member"):
        raise ValueError("target_kind must be 'department' or 'member'")
    if authority not in ("operator", "gate"):
        raise OrgAuthorityError(
            f"promotion is the operator's decision; caller is {authority!r}"
        )
    table = "departments" if target_kind == "department" else "members"
    if authority == "gate":
        if target_kind != "department":
            raise OrgAuthorityError("the gate promotes departments, not members")
        evidence = promotion_evidence(conn, target_id)
        if not evidence["eligible"]:
            raise OrgLifecycleConflict(
                "promotion_not_earned",
                f"{target_id} has {evidence['runs']} attributed run(s),"
                f" {evidence['verified']} verified, {evidence['contradicted']}"
                f" contradicted; needs >= {evidence['required_runs']} runs,"
                " at least one verified and none contradicted",
            )
    now = _now()
    with lock:
        with conn:
            row = conn.execute(
                f"SELECT lifecycle FROM {table} WHERE id=?", (target_id,)  # noqa: S608
            ).fetchone()
            if row is None:
                raise ValueError(f"{target_kind} {target_id!r} not found")
            if row[0] == "dissolved":
                raise OrgLifecycleConflict(
                    "cannot_promote_dissolved",
                    f"{target_id} is dissolved and cannot be promoted",
                )
            conn.execute(
                f"UPDATE {table} SET lifecycle='standing', updated_at=?"  # noqa: S608
                + (", promoted_at=?, promoted_by=?" if table == "departments" else "")
                + " WHERE id=?",
                (now, now, authority, target_id) if table == "departments"
                else (now, target_id),
            )
    _emit_mutation(
        conn, lock, run_id=run_id, operation="promote", authority=authority,
        target_kind=target_kind, target_id=target_id,
        rationale=f"promoted to standing by {authority}",
    )
    result = (
        get_department(conn, target_id)
        if target_kind == "department"
        else get_member(conn, target_id)
    )
    assert result is not None
    return result


def reap_candidates(
    conn: sqlite3.Connection, *, now: Optional[datetime.datetime] = None
) -> list[dict[str, Any]]:
    """Ephemeral departments idle past the threshold, with nothing running.

    Three guards, each catching a different way this would be wrong:
    a standing department is the operator's org and is never a candidate; a
    department with a queued or running actor is in use right now whatever its
    clock says; and a department that has never spawned falls back to
    `created_at`, because a department created seconds ago is new, not idle.
    """
    cfg = _org_config()
    moment = now or datetime.datetime.now(datetime.timezone.utc)
    cutoff = (moment - datetime.timedelta(days=cfg.reap_idle_days)).isoformat()
    rows = conn.execute(
        "SELECT d.id, d.name, COALESCE(d.last_active_at, d.created_at) AS idle_since"
        " FROM departments d"
        " WHERE d.lifecycle='ephemeral'"
        "   AND COALESCE(d.last_active_at, d.created_at) < ?"
        "   AND NOT EXISTS ("
        "     SELECT 1 FROM actors a JOIN members m ON m.id = a.member_id"
        "      WHERE m.department_id = d.id AND a.status IN ('queued','running'))"
        " ORDER BY idle_since ASC",
        (cutoff,),
    ).fetchall()
    return [
        {"id": row[0], "name": row[1], "idle_since": row[2], "cutoff": cutoff}
        for row in rows
    ]


def reap(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    apply: bool = False,
    run_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Report what is reapable; dissolve only when explicitly applied.

    Report-only by default because nothing in ATLAS un-dissolves a department.
    Automatic dissolution is a later decision, taken once the idle clock has
    been watched against real usage — the discipline the scratchpad sweep
    earned the hard way.
    """
    candidates = reap_candidates(conn)
    if candidates and run_id:
        try:
            from atlas_runtime import audit_service  # noqa: PLC0415

            audit_service.emit(
                conn, lock, run_id=run_id, event_type="org_reap_candidates",
                tool_name="atlas_org",
                data={
                    "applied": apply,
                    "count": len(candidates),
                    "departments": [c["id"] for c in candidates],
                },
            )
        except Exception:  # noqa: BLE001 — reporting never fails the caller
            pass
    if apply:
        for candidate in candidates:
            dissolve(
                conn, lock, target_kind="department", target_id=candidate["id"],
                reason=f"idle since {candidate['idle_since']}; reaped",
                authority="operator", run_id=run_id,
            )
    return candidates
```

Add `import datetime` and `import json` to the module imports if not already present (`datetime` is; add `json`).

- [ ] **Step 5: Run the tests**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_lifecycle.py -q`
Expected: PASS, 14 tests.

- [ ] **Step 6: Report reap candidates on the daemon startup hook**

In `services/agent-runtime/atlas_runtime/runtime_daemon.py`, after the scratchpad sweep block (line ~111):

```python
    # Startup is also when the org's idle clock is worth reading: nothing is
    # mid-run, so a department with no live actor is genuinely idle. Report
    # only — this never dissolves anything (org_service.reap).
    try:
        from atlas_runtime import org_service

        candidates = org_service.reap_candidates(server.conn)  # type: ignore[attr-defined]
        if candidates:
            logging.getLogger(__name__).info(
                "org: %d ephemeral department(s) idle past the threshold; "
                "`atlas org reap` to review", len(candidates),
            )
    except Exception:  # noqa: BLE001
        pass
```

Add `import logging` at the top of the file if absent.

- [ ] **Step 7: Commit**

```bash
git add packages/atlas-core/atlas_core/schemas/control_plane.py services/agent-runtime/atlas_runtime/org_service.py services/agent-runtime/atlas_runtime/runtime_daemon.py services/agent-runtime/tests/test_org_lifecycle.py
git commit -m "feat(org): promotion earned from the gate's record, and a reaper that only reports"
```

---

## Task 7: Module equipping and the narrowing rule

**Files:**
- Modify: `services/agent-runtime/atlas_runtime/module_service.py`
- Modify: `services/agent-runtime/atlas_runtime/org_service.py` (append `equip`)
- Modify: `services/agent-runtime/atlas_runtime/context_service.py`
- Create: `services/agent-runtime/tests/test_org_equipping.py`

**Interfaces:**
- Consumes: `_require`, `_emit_mutation`, `_check_cap` (Task 5).
- Produces:
  - `org_service.equip(conn, lock, *, department_id, module_id, authority, actor_department_id=None, run_id=None) -> dict`
  - `org_service.equipped_module_ids(conn, department_id) -> set[str]`
  - `module_service.active_manifests(conn, *, department_id: str | None = None)`
  - `module_service.active_context_blocks(conn, *, terms=(), token_budget=…, department_id: str | None = None)`
  - `context_service.assemble_context(..., department_id: str | None = None)`

- [ ] **Step 1: Write the failing test**

```python
"""Equipping narrows what a department reaches. It never widens it."""
from __future__ import annotations

import json
import sqlite3
import threading

import pytest

from atlas_runtime import module_service, org_service

from .test_org_service import _seed_org


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    return threading.Lock()


def _install_module(conn: sqlite3.Connection, module_id: str) -> None:
    now = "2026-08-16T00:00:00+00:00"
    manifest = {
        "id": module_id,
        "name": module_id.title(),
        "capabilities": {"context": []},
    }
    conn.execute(
        "INSERT INTO modules(id, name, status, missing, manifest_json,"
        " installed_at, updated_at) VALUES (?,?,'active',0,?,?,?)",
        (module_id, module_id.title(), json.dumps(manifest), now, now),
    )
    conn.commit()


def test_a_run_with_no_member_context_still_sees_every_active_module(
    db: sqlite3.Connection,
) -> None:
    """The regression this rule exists to prevent.

    Almost no run has a member context — cockpit chat, missions and the CLI all
    resolve member_id NULL. Scoping unconditionally would delete the module
    surface from every one of them.
    """
    _seed_org(db)
    _install_module(db, "outreach")
    _install_module(db, "admissions")
    ids = {m["id"] for m in module_service.active_manifests(db)}
    assert ids == {"outreach", "admissions"}
    ids_explicit_none = {
        m["id"] for m in module_service.active_manifests(db, department_id=None)
    }
    assert ids_explicit_none == {"outreach", "admissions"}


def test_a_department_reaches_only_what_it_is_equipped_with(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    _install_module(db, "outreach")
    _install_module(db, "admissions")
    org_service.equip(
        db, lock, department_id="d1", module_id="admissions", authority="chief"
    )
    ids = {m["id"] for m in module_service.active_manifests(db, department_id="d1")}
    assert ids == {"admissions"}


def test_equipping_cannot_grant_what_activation_withheld(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    _install_module(db, "outreach")
    org_service.equip(
        db, lock, department_id="d1", module_id="outreach", authority="chief"
    )
    db.execute("UPDATE modules SET status='inactive' WHERE id='outreach'")
    db.commit()
    assert module_service.active_manifests(db, department_id="d1") == []


def test_equipping_an_uninstalled_module_is_refused(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    with pytest.raises(ValueError):
        org_service.equip(
            db, lock, department_id="d1", module_id="not-installed",
            authority="chief",
        )


def test_a_module_that_goes_missing_leaves_its_row_and_is_filtered_on_read(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    _install_module(db, "outreach")
    org_service.equip(
        db, lock, department_id="d1", module_id="outreach", authority="chief"
    )
    db.execute("UPDATE modules SET missing=1 WHERE id='outreach'")
    db.commit()
    assert module_service.active_manifests(db, department_id="d1") == []
    assert org_service.equipped_module_ids(db, "d1") == {"outreach"}


def test_a_manager_equips_only_its_own_department(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    _install_module(db, "outreach")
    with pytest.raises(org_service.OrgAuthorityError):
        org_service.equip(
            db, lock, department_id="d1", module_id="outreach",
            authority="manager", actor_department_id="d-other",
        )


def test_a_worker_cannot_equip(db: sqlite3.Connection, lock: threading.Lock) -> None:
    _seed_org(db)
    _install_module(db, "outreach")
    with pytest.raises(org_service.OrgAuthorityError):
        org_service.equip(
            db, lock, department_id="d1", module_id="outreach", authority="worker"
        )


def test_doctrine_follows_equipment(
    db: sqlite3.Connection, lock: threading.Lock, tmp_path
) -> None:
    """The context-budget win: a member stops paying for doctrine it cannot act on."""
    now = "2026-08-16T00:00:00+00:00"
    _seed_org(db)
    doctrine = tmp_path / "compliance.md"
    doctrine.write_text("Never send without a human.", encoding="utf-8")
    manifest = {
        "id": "outreach",
        "name": "Outreach",
        "source_path": str(tmp_path),
        "capabilities": {
            "context": [
                {"path": "compliance.md", "inject": "always", "max_tokens": 200}
            ]
        },
    }
    db.execute(
        "INSERT INTO modules(id, name, status, missing, manifest_json,"
        " installed_at, updated_at) VALUES ('outreach','Outreach','active',0,?,?,?)",
        (json.dumps(manifest), now, now),
    )
    db.commit()
    unscoped = module_service.active_context_blocks(db)
    assert len(unscoped) == 1
    scoped = module_service.active_context_blocks(db, department_id="d1")
    assert scoped == []
    org_service.equip(
        db, lock, department_id="d1", module_id="outreach", authority="chief"
    )
    assert len(module_service.active_context_blocks(db, department_id="d1")) == 1
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_equipping.py -q`
Expected: FAIL — `TypeError: active_manifests() got an unexpected keyword argument 'department_id'`.

- [ ] **Step 3: Append `equip` to `org_service.py`**

```python
# --- equipping -------------------------------------------------------------


def equipped_module_ids(conn: sqlite3.Connection, department_id: str) -> set[str]:
    """Every module id equipped to a department, including missing ones.

    Deliberately unfiltered: this is the equipment RECORD. Filtering by what is
    currently installed and active happens on read in module_service, so a
    module that goes missing and comes back does not silently lose its posting.
    """
    rows = conn.execute(
        "SELECT module_id FROM department_modules WHERE department_id=?",
        (department_id,),
    ).fetchall()
    return {row[0] for row in rows}


def equip(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    department_id: str,
    module_id: str,
    authority: str,
    actor_department_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """Post a module to a department. Narrows reach; never widens it.

    Global activation stays the operator's authorization boundary — it is what
    makes injecting module doctrine as trust="operator" honest. Equipping
    cannot grant what activation withheld.
    """
    _require(authority, ("operator", "chief", "manager"), "equip")
    if authority == "manager" and actor_department_id != department_id:
        raise OrgAuthorityError("a manager equips only its own department")
    _check_cap(conn, run_id)
    now = _now()
    with lock:
        with conn:
            if conn.execute(
                "SELECT 1 FROM departments WHERE id=?", (department_id,)
            ).fetchone() is None:
                raise ValueError(f"department {department_id!r} not found")
            # Refused at write time: equipping something that is not installed
            # records an intention rather than a capability.
            if conn.execute(
                "SELECT 1 FROM modules WHERE id=?", (module_id,)
            ).fetchone() is None:
                raise ValueError(
                    f"module {module_id!r} is not installed; install it before"
                    " equipping a department with it"
                )
            conn.execute(
                "INSERT OR REPLACE INTO department_modules(department_id,"
                " module_id, equipped_at, equipped_by) VALUES (?,?,?,?)",
                (department_id, module_id, now, authority),
            )
    _emit_mutation(
        conn, lock, run_id=run_id, operation="equip", authority=authority,
        target_kind="department", target_id=department_id,
        rationale=f"equipped module {module_id}",
    )
    return {"department_id": department_id, "module_id": module_id, "equipped_at": now}
```

- [ ] **Step 4: Add the narrowing to `module_service.py`**

Replace `active_manifests` (line 597) and extend `active_context_blocks` (line 675):

```python
def active_manifests(
    conn: sqlite3.Connection, *, department_id: Optional[str] = None
) -> list[dict[str, Any]]:
    """Parsed manifests of active, present modules, ordered by id.

    `department_id=None` — the caller has no member context — returns every
    active module, which is what every cockpit, mission and CLI run gets and
    what they got before departments existed. Passing a department NARROWS to
    the modules equipped to it: activation is still the gate, equipping is a
    filter inside it, and equipping can never widen reach beyond activation.
    """
    out: list[dict[str, Any]] = []
    rows = conn.execute(
        "SELECT manifest_json FROM modules"
        " WHERE status='active' AND missing=0 AND manifest_json != ''"
        " ORDER BY id"
    ).fetchall()
    equipped: Optional[set[str]] = None
    if department_id is not None:
        from atlas_runtime import org_service  # noqa: PLC0415 — avoid an import cycle

        equipped = org_service.equipped_module_ids(conn, department_id)
    for (manifest_json,) in rows:
        try:
            manifest = json.loads(manifest_json)
        except json.JSONDecodeError:
            continue
        if not isinstance(manifest, dict) or not manifest.get("id"):
            continue
        if equipped is not None and manifest["id"] not in equipped:
            continue
        out.append(manifest)
    return out
```

Then in `active_context_blocks`, add the parameter and thread it through:

```python
def active_context_blocks(
    conn: sqlite3.Connection,
    *,
    terms: tuple[str, ...] = (),
    token_budget: int = DEFAULT_MODULE_CONTEXT_BUDGET,
    department_id: Optional[str] = None,
) -> list[dict[str, Any]]:
```

and change the loop header from `for manifest in active_manifests(conn):` to:

```python
    for manifest in active_manifests(conn, department_id=department_id):
```

- [ ] **Step 5: Thread the department through `context_service.py`**

Add the parameter to `assemble_context` (line 196), after `run_id`:

```python
    run_id: str | None = None,
    # The department whose equipment scopes module doctrine. None keeps the
    # pre-org behaviour exactly: every active module's doctrine, as before.
    department_id: str | None = None,
```

And at line ~289, pass it:

```python
    if ctx_cfg.inject_module_context and ctx_cfg.module_token_budget:
        module_lines, module_sources = _module_doctrine_lines(
            conn, terms=tuple(terms), token_budget=ctx_cfg.module_token_budget,
            department_id=department_id,
        )
```

Add the same keyword to `_module_doctrine_lines` and forward it to `active_context_blocks`.

- [ ] **Step 6: Run the tests**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_equipping.py tests/test_module_service.py tests/test_context_service.py -q`
Expected: PASS. The module and context suites must pass **unmodified** — that is the proof the default did not change.

- [ ] **Step 7: Commit**

```bash
git add services/agent-runtime/atlas_runtime/module_service.py services/agent-runtime/atlas_runtime/org_service.py services/agent-runtime/atlas_runtime/context_service.py services/agent-runtime/tests/test_org_equipping.py
git commit -m "feat(org): a department is equipped by modules, and pays only for what it can use"
```

---

## Task 8: The `atlas_org` tool and the `atlas org` CLI

**Files:**
- Create: `services/agent-runtime/atlas_runtime/org_bridge.py`
- Modify: `services/agent-runtime/atlas_runtime/agents/native.py:848`
- Modify: `services/agent-runtime/atlas_runtime/cli/main.py`
- Create: `services/agent-runtime/tests/test_org_bridge.py`

**Interfaces:**
- Consumes: every `org_service` mutation and read.
- Produces: `org_bridge.TOOL_SCHEMA`, `org_bridge.ensure_org_bridge() -> bool`, `org_bridge.atlas_org_tool(args=None, *, task_id=None, parent_agent=None, **framework) -> str` (the Hermes handler), and `org_bridge.handle(conn, lock, payload: dict, *, run_id: str | None, actor_id: str | None) -> str` (JSON, the testable core).

A new agent-facing tool changes the cached prompt prefix. **The golden hashes live in three places** and the third fails alone if missed.

- [ ] **Step 1: Write the failing test**

```python
"""The agent's one org tool: bounded ops, authority resolved from the actor."""
from __future__ import annotations

import json
import sqlite3
import threading

import pytest

from atlas_runtime import org_bridge

from .test_org_service import _seed_org


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    return threading.Lock()


def test_the_schema_is_one_generic_tool(db: sqlite3.Connection) -> None:
    assert org_bridge.TOOL_SCHEMA["name"] == "atlas_org"
    ops = org_bridge.TOOL_SCHEMA["parameters"]["properties"]["op"]["enum"]
    assert set(ops) == {
        "chart", "describe", "create_department", "appoint_manager", "hire",
        "equip", "dissolve",
    }
    assert "promote" not in ops


def test_chart_returns_the_standing_structure(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    _seed_org(db)
    out = json.loads(
        org_bridge.handle(db, lock, {"op": "chart"}, run_id=None, actor_id=None)
    )
    assert [d["name"] for d in out["departments"]] == ["Admissions"]


def test_a_run_with_no_member_context_is_refused_a_mutation(
    db: sqlite3.Connection, lock: threading.Lock, run_id: str
) -> None:
    _seed_org(db)
    out = json.loads(
        org_bridge.handle(
            db, lock,
            {
                "op": "create_department", "name": "Shadow", "charter": "c",
                "rationale": "A run with no org context must not restructure the org.",
            },
            run_id=run_id, actor_id=None,
        )
    )
    assert out["ok"] is False
    assert "worker" in out["error"]


def test_an_unknown_op_is_refused_by_name(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    out = json.loads(
        org_bridge.handle(db, lock, {"op": "promote"}, run_id=None, actor_id=None)
    )
    assert out["ok"] is False
    assert "promote" in out["error"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_bridge.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'atlas_runtime.org_bridge'`.

- [ ] **Step 3: Write `org_bridge.py`**

```python
"""Hermes-facing org bridge — the `atlas_org` tool.

One generic tool over every org operation, following `atlas_module` rather than
seven separate tools: a new operation needs no new registration.

`promote` is deliberately absent from the schema. The chief creates and
dissolves; making an invention permanent on the operator's machine is the
operator's decision, and a tool the agent cannot see is a boundary it cannot
argue with.

Authority is resolved from the calling actor's `member_id`, never from model
input — an agent cannot claim to be the chief. A run with no member context
resolves to `worker` and every mutation is refused.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from typing import Any, Optional

from atlas_runtime import org_service

logger = logging.getLogger(__name__)

_bridge_lock = threading.Lock()
_registered = False

TOOL_SCHEMA = {
    "name": "atlas_org",
    "description": (
        "Your organisation: departments, the members in them, and who reports "
        "to whom. op=chart to see the standing structure, op=describe for one "
        "department. If the work needs standing capacity that does not exist, "
        "op=create_department then op=appoint_manager then op=hire — a "
        "department you invent is ephemeral and fully functional, and becomes "
        "permanent only if the operator or the verification gate promotes it. "
        "op=equip posts an installed module to a department, which is also what "
        "scopes that department's doctrine. op=dissolve retires something you "
        "created. Every mutation requires a rationale and is capped per run: "
        "restructuring competes with the work you were started for."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": [
                    "chart", "describe", "create_department", "appoint_manager",
                    "hire", "equip", "dissolve",
                ],
                "description": "Org operation.",
            },
            "department_id": {"type": "string", "description": "Target department."},
            "member_id": {"type": "string", "description": "Target member."},
            "module_id": {"type": "string", "description": "Module to equip."},
            "name": {"type": "string", "description": "Name (create/appoint/hire)."},
            "charter": {
                "type": "string",
                "description": "What this department stands responsible for.",
            },
            "role_label": {"type": "string", "description": "Role (appoint/hire)."},
            "goal_template": {
                "type": "string",
                "description": "The standing goal this member runs with.",
            },
            "parent_member_id": {
                "type": "string",
                "description": "The manager a hired worker reports to.",
            },
            "target_kind": {
                "type": "string",
                "enum": ["department", "member"],
                "description": "What op=dissolve targets. Explicit, never inferred.",
            },
            "target_id": {"type": "string", "description": "What op=dissolve targets."},
            "rationale": {
                "type": "string",
                "description": (
                    "Why this structure is needed and why it did not already "
                    "exist. At least 40 characters. Recorded permanently."
                ),
            },
            "reason": {"type": "string", "description": "Why (op=dissolve)."},
        },
        "required": ["op"],
    },
}

_KNOWN_ARGS = set(TOOL_SCHEMA["parameters"]["properties"])


def _err(message: str) -> str:
    return json.dumps({"ok": False, "error": message})


def handle(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    payload: dict[str, Any],
    *,
    run_id: Optional[str],
    actor_id: Optional[str],
) -> str:
    op = str(payload.get("op") or "").strip()
    if op not in TOOL_SCHEMA["parameters"]["properties"]["op"]["enum"]:
        return _err(
            f"unknown op {op!r};"
            f" expected one of {TOOL_SCHEMA['parameters']['properties']['op']['enum']}"
        )
    authority = org_service.caller_authority(conn, actor_id=actor_id, run_id=run_id)
    actor_department_id: Optional[str] = None
    row = conn.execute(
        "SELECT m.department_id FROM actors a JOIN members m ON m.id=a.member_id"
        " WHERE a.id=? OR a.child_run_id=?",
        (actor_id or "", run_id or ""),
    ).fetchone()
    actor_department_id = row[0] if row else None
    try:
        if op == "chart":
            return json.dumps(
                {"ok": True, "departments": org_service.list_departments(conn)}
            )
        if op == "describe":
            dept = org_service.get_department(conn, str(payload.get("department_id")))
            if dept is None:
                return _err("department not found")
            return json.dumps({"ok": True, "department": dept})
        if op == "create_department":
            dept = org_service.create_department(
                conn, lock,
                name=str(payload.get("name") or ""),
                charter=str(payload.get("charter") or ""),
                rationale=str(payload.get("rationale") or ""),
                authority=authority, run_id=run_id,
            )
            return json.dumps({"ok": True, "department": dept})
        if op == "appoint_manager":
            member = org_service.appoint_manager(
                conn, lock,
                department_id=str(payload.get("department_id") or ""),
                name=str(payload.get("name") or ""),
                role_label=str(payload.get("role_label") or ""),
                goal_template=str(payload.get("goal_template") or ""),
                rationale=str(payload.get("rationale") or ""),
                authority=authority, run_id=run_id,
            )
            return json.dumps({"ok": True, "member": member})
        if op == "hire":
            member = org_service.hire(
                conn, lock,
                department_id=str(payload.get("department_id") or ""),
                name=str(payload.get("name") or ""),
                role_label=str(payload.get("role_label") or ""),
                goal_template=str(payload.get("goal_template") or ""),
                parent_member_id=str(payload.get("parent_member_id") or ""),
                rationale=str(payload.get("rationale") or ""),
                authority=authority, actor_department_id=actor_department_id,
                run_id=run_id,
            )
            return json.dumps({"ok": True, "member": member})
        if op == "equip":
            result = org_service.equip(
                conn, lock,
                department_id=str(payload.get("department_id") or ""),
                module_id=str(payload.get("module_id") or ""),
                authority=authority, actor_department_id=actor_department_id,
                run_id=run_id,
            )
            return json.dumps({"ok": True, "equipped": result})
        result = org_service.dissolve(
            conn, lock,
            target_kind=str(payload.get("target_kind") or ""),
            target_id=str(payload.get("target_id") or ""),
            reason=str(payload.get("reason") or ""),
            authority=authority, actor_department_id=actor_department_id,
            run_id=run_id,
        )
        return json.dumps({"ok": True, "dissolved": result})
    except org_service.OrgAuthorityError as exc:
        return _err(str(exc))
    except org_service.OrgLifecycleConflict as exc:
        return json.dumps({"ok": False, "error": str(exc), "code": exc.code})
    except ValueError as exc:
        return _err(str(exc))


def _shared_state() -> tuple[Any, Optional[threading.Lock]]:
    try:
        import atlas_audit  # noqa: PLC0415

        return atlas_audit.get_connection(), atlas_audit.get_lock()
    except Exception:  # noqa: BLE001
        return None, None


def atlas_org_tool(
    args: Optional[dict[str, Any]] = None,
    *,
    task_id: Optional[str] = None,
    parent_agent: Any = None,
    **framework: Any,
) -> str:
    """Hermes plugin handler for `atlas_org`; returns a JSON string."""
    from atlas_runtime import scratchpad_bridge  # noqa: PLC0415

    if args is None:
        args = {key: value for key, value in framework.items() if key in _KNOWN_ARGS}
    if not isinstance(args, dict):
        return _err("atlas_org arguments must be an object")
    conn, lock = _shared_state()
    if conn is None or lock is None:
        return _err("org unavailable: no ATLAS connection bound")
    run_id, _session_id = scratchpad_bridge._binding(parent_agent, task_id)
    return handle(conn, lock, args, run_id=run_id or None, actor_id=None)


def ensure_org_bridge() -> bool:
    """Register the org tool with the foundation, once. Fail-open.

    Same mechanics as ensure_scratchpad_bridge (scratchpad_bridge.py:272):
    direct PluginContext registration, D-001 safe, and a no-op when the
    foundation is not importable.
    """
    global _registered  # noqa: PLW0603
    with _bridge_lock:
        if _registered:
            return True
        try:
            from atlas_runtime.subagent_service import _foundation_on_path  # noqa: PLC0415

            if not _foundation_on_path():
                return False
            from hermes_cli.plugins import (  # noqa: PLC0415
                PluginContext,
                PluginManifest,
                get_plugin_manager,
            )

            manifest = PluginManifest(
                name="atlas_org",
                version="0.1.0",
                description="ATLAS organisation substrate (registered in-process)",
                source="atlas-runtime",
            )
            ctx = PluginContext(manifest, get_plugin_manager())
            ctx.register_tool(
                name="atlas_org",
                toolset="atlas",
                schema=TOOL_SCHEMA,
                handler=atlas_org_tool,
                description=str(TOOL_SCHEMA["description"]),
            )
            _registered = True
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("org bridge registration skipped: %s", exc)
            return False
```

**Why `actor_id` is always None here:** `scratchpad_bridge._binding` returns `(run_id, session_id)` — the harness hands a tool no actor id. That is why Task 4's `caller_authority` takes `run_id` and resolves the actor through `actors.child_run_id`, and why `handle` passes both.

- [ ] **Step 4: Register it in `native.py`**

At line ~851, beside the other bridges:

```python
                from atlas_runtime import module_bridge, org_bridge, scratchpad_bridge  # noqa: PLC0415

                module_bridge.ensure_module_bridge()
                scratchpad_bridge.ensure_scratchpad_bridge()
                # The standing organisation. A run only gets mutation authority
                # if its actor is bound to a member, so this is inert for the
                # cockpit and CLI runs that make up most traffic.
                org_bridge.ensure_org_bridge()
```

- [ ] **Step 5: Add the `atlas org` CLI**

In `cli/main.py`, beside the other sub-apps (line ~90):

```python
org_app = typer.Typer(name="org", help="Departments, members, promotion, and the idle reaper.")
app.add_typer(org_app, name="org")


@org_app.command("chart")
def org_chart() -> None:
    """Print the standing organisation."""
    from atlas_runtime import org_service

    conn = _get_connection()
    typer.echo(json.dumps(org_service.list_departments(conn), indent=2))


@org_app.command("check")
def org_check() -> None:
    """Report every structural invariant violation. Exits 1 if any."""
    from atlas_runtime import org_service

    conn = _get_connection()
    violations = org_service.check_invariants(conn)
    for violation in violations:
        typer.echo(f"[violation] {violation}")
    if violations:
        raise typer.Exit(code=1)
    typer.echo("[ok] org invariants hold")


@org_app.command("promote")
def org_promote(
    target_id: str,
    kind: str = typer.Option("department", "--kind"),
) -> None:
    """Promote ephemeral -> standing with the operator's own authority."""
    from atlas_runtime import org_service

    conn, lock = _get_connection(), _get_lock()
    result = org_service.promote(
        conn, lock, target_kind=kind, target_id=target_id, authority="operator"
    )
    typer.echo(json.dumps(result, indent=2))


@org_app.command("evidence")
def org_evidence(department_id: str) -> None:
    """What the gate's record says this department has earned."""
    from atlas_runtime import org_service

    conn = _get_connection()
    typer.echo(json.dumps(org_service.promotion_evidence(conn, department_id), indent=2))


@org_app.command("reap")
def org_reap(
    apply: bool = typer.Option(False, "--apply", help="Dissolve the candidates."),
) -> None:
    """List ephemeral departments idle past the threshold. Dissolves only with --apply."""
    from atlas_runtime import org_service

    conn, lock = _get_connection(), _get_lock()
    candidates = org_service.reap(conn, lock, apply=apply)
    if not candidates:
        typer.echo("no reap candidates")
        return
    for candidate in candidates:
        typer.echo(f"{candidate['id']}  {candidate['name']}  idle since {candidate['idle_since']}")
    typer.echo(f"{'dissolved' if apply else 'candidates'}: {len(candidates)}")
```

`_get_connection()` (`cli/main.py:511`) applies pending migrations on first use per process; `_get_lock()` (`cli/main.py:523`) returns the module-level singleton. Both already exist — do not add new helpers.

- [ ] **Step 6: Regenerate the prompt goldens in all THREE places**

A new agent-facing tool changes the cached prefix hash. Run the suite and update:

1. `services/agent-runtime/tests/golden/prompts/*.json` (5 files)
2. `services/agent-runtime/tests/fixtures/prompt_golden_matrix.json` (108 cases)
3. `services/agent-runtime/tests/fixtures/quality_thresholds.json` → `prompt_cache_prefix_hashes` (3 entries)

Run: `cd services/agent-runtime && python -m pytest tests/test_prompt_golden_matrix.py tests/test_rag_quality.py -q`
Expected: FAIL first with hash mismatches; update each fixture to the reported actual value, then PASS. The third file is checked only by `test_rag_quality.py` and will fail alone if missed.

- [ ] **Step 7: Run the tests**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_bridge.py tests/test_prompt_golden_matrix.py tests/test_rag_quality.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add services/agent-runtime/atlas_runtime/org_bridge.py services/agent-runtime/atlas_runtime/agents/native.py services/agent-runtime/atlas_runtime/cli/main.py services/agent-runtime/tests/test_org_bridge.py services/agent-runtime/tests/golden services/agent-runtime/tests/fixtures
git commit -m "feat(org): one org tool the agent can reach, and an org the operator can inspect"
```

---

## Task 9: `test_every_member_is_runnable`, and the full verification pass

The headline invariant, ported from FounderOS `tests/seed.test.ts:37`. ATLAS has no equivalent today: a cockpit surface can display a member the runtime cannot spawn.

**Files:**
- Modify: `services/agent-runtime/tests/test_org_service.py` (append)
- Modify: `docs/superpowers/specs/2026-08-16-atlas-org-substrate-design.md` (status line)

- [ ] **Step 1: Write the test**

```python
def test_every_member_is_runnable(db: sqlite3.Connection) -> None:
    """No larp: every member on the chart resolves to something spawnable.

    Configuration validity ONLY — this must never open a socket. `provider
    status` reports config shape, not reachability, and the freellmapi sidecar
    is down by default; a runnability test that touches the network fails CI
    whenever the sidecar is off, and the tempting fix is to weaken the test.
    """
    _seed_org(db)
    known_providers = {None, "", "anthropic", "openai", "freellmapi", "codex",
                       "claude_code", "native"}
    for member in org_service.list_members(db):
        assert member["goal_template"].strip(), (
            f"member {member['id']} has no goal template and cannot be spawned"
        )
        assert member["role_label"].strip(), (
            f"member {member['id']} has no role label"
        )
        assert member["mode"] in ("joined", "detached"), (
            f"member {member['id']} has mode {member['mode']!r}"
        )
        assert member["provider"] in known_providers, (
            f"member {member['id']} names unknown provider {member['provider']!r}"
        )
        assert member["tier"] in org_service.TIERS


def test_a_member_with_an_empty_goal_template_fails_the_runnable_check(
    db: sqlite3.Connection,
) -> None:
    """The guard has to be able to fail, or it guards nothing."""
    _seed_org(db)
    db.execute("UPDATE members SET goal_template='' WHERE id='m-w1'")
    db.commit()
    with pytest.raises(AssertionError):
        test_every_member_is_runnable(db)
```

- [ ] **Step 2: Run it**

Run: `cd services/agent-runtime && python -m pytest tests/test_org_service.py -q -k runnable`
Expected: PASS, 2 tests.

- [ ] **Step 3: Run every suite**

Run each and record the actual counts:

```bash
cd services/agent-runtime && python -m pytest tests/ -q
cd packages/atlas-core && python -m pytest tests/ -q
cd ../.. && ruff check .
```

Expected: all green, ruff clean. The Rust and cockpit suites need no change (the gateway shells out to the CLI), but run them to confirm:

```bash
cd native/atlas-core-rs && cargo test -p atlas-gateway
cd apps/cockpit && npm test
```

- [ ] **Step 4: Verify the live database took the migration**

The autonomous loop applies `0039` to `~/.atlas/atlas.db` within ~2h of the file existing. Confirm the backfill landed as the Task 1 probe predicted:

```bash
python -c "import sqlite3,pathlib,os; p=pathlib.Path(os.environ.get('ATLAS_HOME', pathlib.Path.home()/'.atlas'))/'atlas.db'; c=sqlite3.connect(f'file:{p}?mode=ro', uri=True); print('departments', c.execute('SELECT COUNT(*) FROM departments').fetchone()[0]); print('members', c.execute('SELECT COUNT(*) FROM members').fetchone()[0]); print('clones', c.execute(\"SELECT COUNT(*) FROM members WHERE rationale LIKE 'migration clone%'\").fetchone()[0]); print('chief', c.execute(\"SELECT COUNT(*) FROM members WHERE tier='chief'\").fetchone()[0])"
```

Expected: the clone count matches Task 1's prediction exactly. If it does not, stop and reconcile before continuing — the backfill saw data the probe did not.

Then: `atlas org check` → `[ok] org invariants hold`.

- [ ] **Step 5: Update the spec status**

In `docs/superpowers/specs/2026-08-16-atlas-org-substrate-design.md`, change the status line to:

```markdown
**Status:** sections 1–5 APPROVED · IMPLEMENTED (slice 1 complete)
```

- [ ] **Step 6: Commit**

```bash
git add services/agent-runtime/tests/test_org_service.py docs/superpowers/specs/2026-08-16-atlas-org-substrate-design.md
git commit -m "test(org): every member on the chart resolves to something that can run"
```

---

## Deviations from the approved spec

Two, both found while writing the plan against the real schema. Neither changes a decision; both correct the spec's DDL.

1. **`members` gains a `rationale` column that §1's DDL did not list.** Backfill rule 2 requires cloned rows to record `rationale = 'migration clone from preset <id>'`, and §2 requires a rationale on every created member. There was nowhere to put it. `0039` adds it (`NOT NULL DEFAULT ''`).
2. **`team_members` is frozen, not dropped.** §1 rule 4 says "dropped only after the backfill is verified by test." The plan keeps the table permanently in `0039` and defers the drop to a later migration, because it is the only record of the pre-migration roster — and dropping it in the migration that reads it removes the ability to check the backfill against the live database afterwards, which is exactly what §5's dry-run discipline is for. Nothing reads it after `0039`.

## Deliberately out of scope

Named so a later reader does not treat them as oversights:

- **Slices 2–5.** Addressing, mailboxes, the permission matrix, the delegation runtime, `/org` and the visual system. Slice 5 depends on nothing and can start in parallel at any time.
- **Dropping `team_members`.** Frozen by `0039`, not dropped: it is the only record of the pre-migration roster and the only way to re-check the backfill against the live database afterwards. A later migration removes it.
- **Automatic reaping.** Report-only until the idle clock has been watched against real usage.
- **Per-member module equipping.** Departments only (YAGNI).
- **Department project scope.** Slice 4's decision; `0039` does not preclude it — `departments.scope_id` is an additive `ALTER` with a NULL default.
- **A cockpit org surface.** Slice 4. The CLI (`atlas org chart|check|evidence|promote|reap`) is the operator surface for this slice.
