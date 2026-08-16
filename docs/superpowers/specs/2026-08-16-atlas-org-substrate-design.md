# ATLAS Org Substrate — design (slice 1 of 5)

**Date:** 2026-08-16
**Status:** section 1 APPROVED by operator · sections 2–5 DRAFTED, NOT REVIEWED
**Research input:** `docs/research/2026-08-16-founderos-teardown.md`
**Approach:** A — the org supersedes teams (chosen over additive, chosen over projection)

---

## 0. Why this exists

The operator's read: ATLAS is a thick engine under a developer-shaped surface;
FounderOS-DEMO is a thick, disciplined surface over a thin engine. The gap that
makes ATLAS *feel* small is not engine depth — it is that ATLAS has no
organisational layer. It has runs, actors, teams-as-flat-rosters, and no notion
of who is standing responsible for what.

This slice builds that layer. It is the foundation for four more.

### Program decomposition

| # | Slice | Depends on | Status |
|---|---|---|---|
| **1** | **Org substrate** — departments, members, tiers, reporting lines, charters, lifecycle, mutation contract | — | **this spec** |
| 2 | Communication plane — addressing, permission matrix, manager-granted channels, mailboxes, budget/depth/fanout | 1 | not started |
| 3 | Delegation runtime — chief→manager→crew decomposition, evidence roll-up through the manager boundary | 1, 2 | not started |
| 4 | Org surface + IA inversion — `/org`, department pages, work-shaped nav | 1–3 | not started |
| 5 | Visual system — token indirection, `dotState` funnel, primitives, `app.css` breakup | **none** | independent, may run in parallel |

### Operator constraints captured during brainstorming

Recorded verbatim in substance, because they are the requirements:

1. **A department is not a module.** A module is capability — doctrine, records,
   workflows, MCP tools — installable and creatable on demand, disposable by
   design. A department is organisation: who is on the team, who manages whom,
   what they stand responsible for. A department may be *equipped by* modules.
2. **The communication topology is a graph, not a tree**, with an asymmetric top:
   chief addresses managers only; a manager addresses its own crew and other
   managers when needed; workers address other workers laterally and address
   managers to report work or request context.
3. **Containment is a merge, not a single policy** — manager-granted channels
   *and* depth/fanout caps *and* a message budget, plus audit observability.
4. **Nothing is hardcoded.** If ATLAS decides mid-run that a different structure
   fits, it builds the new departments itself.
5. **Ephemeral by nature, permanent if earned.** A department that proves out
   becomes an official standing department on this operator's machine.

---

## 1. Entity model — APPROVED

### What exists today

| Table | Shape | Kind |
|---|---|---|
| `agent_presets` | `id, name, role_label, description, goal_template, model, provider, mode, created_at, updated_at` | durable config |
| `teams` | `id, name, description, created_at, updated_at, archived_at` | durable config |
| `team_members` | `team_id, preset_id, position` | flat ordered roster |
| `actors` | `id, parent_run_id NOT NULL, parent_actor_id, role, depth, status, pid, heartbeat_at, …` | **per-run process** |

The structural finding that shapes the whole design:

> **A member is who works here. An actor is what a member becomes while running.**

`actors` is a process table, not a roster — `parent_run_id` is `NOT NULL` and it
carries `pid`/`heartbeat_at`/a `queued→running→completed` lifecycle. It already
has `parent_actor_id` and `depth`, so the *per-run* delegation tree exists.
What is missing is the *standing* structure above it. `actors` is untouched by
this slice.

Mapping to FounderOS: their `agents` row ≈ our `agent_presets`; their in-memory
`RuntimeAgent` ≈ our `actors`. They have no equivalent of the org layer either —
their `/org` chart is display over a flat `Map`.

### Migration (additive ALTER, then RENAME — nothing breaks mid-flight)

```sql
-- departments (was: teams)
ALTER TABLE teams ADD COLUMN charter       TEXT NOT NULL DEFAULT '';
ALTER TABLE teams ADD COLUMN lifecycle     TEXT NOT NULL DEFAULT 'ephemeral'
     CHECK (lifecycle IN ('ephemeral','standing','dissolved'));
ALTER TABLE teams ADD COLUMN created_by    TEXT NOT NULL DEFAULT 'operator'
     CHECK (created_by IN ('operator','chief','manager'));
ALTER TABLE teams ADD COLUMN origin_run_id TEXT REFERENCES runs(id);
ALTER TABLE teams ADD COLUMN rationale     TEXT NOT NULL DEFAULT '';
ALTER TABLE teams ADD COLUMN promoted_at   TEXT;
ALTER TABLE teams ADD COLUMN promoted_by   TEXT;   -- 'operator' | 'gate'
ALTER TABLE teams ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0;
ALTER TABLE teams RENAME TO departments;

-- members (was: agent_presets)
ALTER TABLE agent_presets ADD COLUMN department_id    TEXT REFERENCES departments(id);
ALTER TABLE agent_presets ADD COLUMN tier             TEXT NOT NULL DEFAULT 'worker'
     CHECK (tier IN ('chief','manager','worker'));
ALTER TABLE agent_presets ADD COLUMN parent_member_id TEXT REFERENCES agent_presets(id);
ALTER TABLE agent_presets ADD COLUMN lifecycle        TEXT NOT NULL DEFAULT 'ephemeral'
     CHECK (lifecycle IN ('ephemeral','standing','dissolved'));
ALTER TABLE agent_presets ADD COLUMN created_by       TEXT NOT NULL DEFAULT 'operator'
     CHECK (created_by IN ('operator','chief','manager'));
ALTER TABLE agent_presets ADD COLUMN origin_run_id    TEXT REFERENCES runs(id);
ALTER TABLE agent_presets ADD COLUMN display_order    INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agent_presets RENAME TO members;

-- equipping: a department is equipped BY modules; it is not one
CREATE TABLE IF NOT EXISTS department_modules (
  department_id TEXT NOT NULL REFERENCES departments(id),
  module_id     TEXT NOT NULL,
  equipped_at   TEXT NOT NULL,
  equipped_by   TEXT NOT NULL,
  PRIMARY KEY (department_id, module_id)
);
CREATE INDEX IF NOT EXISTS idx_members_department ON members(department_id);
CREATE INDEX IF NOT EXISTS idx_members_parent     ON members(parent_member_id);
CREATE INDEX IF NOT EXISTS idx_departments_lifecycle ON departments(lifecycle);
```

The existing `archived_at` on `teams` becomes the dissolution timestamp;
`TeamLifecycleConflict` is retained (renamed `OrgLifecycleConflict`).

### Backfill rules — must be explicit, never a silent pick

1. `team_members.position` → `members.display_order`.
2. **A preset belonging to more than one team must be cloned**, one copy per
   department, because a member belongs to exactly one department. Cloned rows
   keep `origin_run_id` NULL and record `rationale = 'migration clone from
   preset <id>'`.
3. Every pre-existing team and preset migrates as `lifecycle='standing'` — they
   predate the ephemeral concept and the operator already relies on them.
4. `team_members` is dropped only after the backfill is verified by test.
5. A synthetic `chief` member is created if none exists.

### Invariants — enforced in `org_service.py`, each with a test

1. Exactly one `tier='chief'`; its `department_id` and `parent_member_id` are NULL.
2. Each department has exactly one `tier='manager'`, whose parent is the chief.
3. A worker's `parent_member_id` resolves to a manager **in the same department**.
4. **Orphan promotion** — a member whose parent has left surfaces at department
   root rather than vanishing. Ported verbatim from FounderOS `hierarchy.ts:28`;
   it is why their chart never silently loses an agent.
5. A department cannot be dissolved while it holds `standing` members —
   raises `OrgLifecycleConflict`.

### Provenance and promotion

`created_by` + `origin_run_id` + `rationale` appear on both tables so that when
ATLAS invents a department mid-run, the record of who created it and why is
queryable. This is the same doctrine as memory provenance: quality is assigned
by origin, never by the writer.

Promotion `ephemeral → standing` is **earned, not declared**:

- **gate-earned** — N completed runs attributed to the department with zero
  `fail` verdicts from the verification gate (`promoted_by='gate'`), or
- **operator-declared** — explicit promotion (`promoted_by='operator'`).

The chief may create and dissolve, but **may not promote**. Promotion is the
operator's boundary.

---

## 2. Mutation contract — DRAFTED, NOT REVIEWED

How ATLAS restructures itself at runtime. Exposed as one bounded tool surface,
following the `atlas_module` single-generic-tool precedent rather than five
separate tools.

| Operation | Caller | Effect |
|---|---|---|
| `create_department(name, charter, rationale)` | chief | new `lifecycle='ephemeral'` department |
| `appoint_manager(department_id, …)` | chief | one manager, parent = chief |
| `hire(department_id, name, role_label, goal_template, model, parent_member_id)` | manager (own dept only) | new ephemeral worker |
| `equip(department_id, module_id)` | chief, manager (own dept) | row in `department_modules` |
| `dissolve(target_id, reason)` | chief (dept), manager (own workers) | `lifecycle='dissolved'`, `archived_at` set |
| `promote(target_id)` | **operator or gate only** | `ephemeral → standing` |

Rules:

1. **Authority is tiered.** The chief shapes departments and appoints managers.
   A manager staffs only its own department. A worker cannot mutate the org.
2. **Every mutation emits an audit event.** New audit event types require three
   edits in ATLAS or the emit fails silently — that is a known trap and each new
   type must be registered in all three places before the first emit.
3. **Mutation is budgeted.** Restructuring competes with work under the same
   economy as messages (slice 2). An agent cannot spend a run reorganising.
4. **Nothing is hard-deleted.** Runs and evidence reference departments forever;
   dissolution is a state, not a `DELETE`.

**Open question for review:** does an ephemeral department created mid-run
survive the run by default, or must it be explicitly kept? Current draft says it
survives (so it can accumulate the evidence needed for promotion) and is reaped
if it goes idle — see §3.

---

## 3. Lifecycle and disposal — DRAFTED, NOT REVIEWED

```
                 promote (gate or operator)
   ephemeral ──────────────────────────────► standing
       │                                        │
       │ reaper: idle > N days, never promoted  │ dissolve (operator/chief,
       │                                        │  blocked while standing
       ▼                                        ▼  members remain)
                        dissolved  ◄────────────
```

- **ephemeral** — fully functional, addressable, runnable. Rendered in a
  separate "forming" band on the org chart so the standing org stays legible.
- **standing** — the operator's official org on this machine. Survives reaping.
- **dissolved** — `archived_at` set, history retained, excluded from addressing.

A reaper dissolves ephemeral departments idle beyond a threshold with no
promotion. Threshold is an open question — draft default 14 days, tunable.

---

## 4. Module equipping — DRAFTED, NOT REVIEWED

A department's effective capability is the union of its equipped modules'
declared doctrine, records, workflows, and MCP tools. Module capability v2
already declares all four, so equipping is a join, not a new contract.

- Equipping is per **department**, not per member. A member inherits its
  department's equipment. Per-member equipping is deliberately deferred (YAGNI).
- The existing generic `atlas_module` tool is scoped to the calling member's
  department, so a worker in Admissions cannot reach Outreach's module surface
  without a granted channel (slice 2).
- Equipping is a mutation: audited and budgeted like the rest.

---

## 5. Testing — DRAFTED, NOT REVIEWED

The headline test is ported from FounderOS `tests/seed.test.ts:37`
(*"every seeded agent maps to a real runtime agent — no larp"*), which is the
single best idea in that repository:

> **`test_every_member_is_runnable`** — iterate every non-dissolved member and
> assert it resolves to a configuration the runtime can actually spawn (valid
> provider, model, goal template). Fails CI if the org chart can display
> someone who cannot work.

ATLAS has no such invariant today; cockpit surfaces can show what the runtime
cannot execute. This test closes that hole permanently.

Additional required tests:

| Test | Guards |
|---|---|
| one-chief, manager-per-department, worker-parent-in-same-department | invariants 1–3 |
| orphan promotes to department root | invariant 4 |
| dissolve with standing members raises `OrgLifecycleConflict` | invariant 5 |
| preset in two teams clones on migration | backfill rule 2 |
| pre-existing teams migrate as `standing` | backfill rule 3 |
| gate-earned vs operator-declared promotion sets `promoted_by` correctly | promotion |
| chief cannot call `promote` | authority |
| worker cannot call any mutation | authority |
| every mutation emits its audit event (all three registration points) | §2 rule 2 |

---

## 6. Open questions for the next session

1. Reaper threshold and promotion threshold N — pick defaults, make tunable.
2. Do ephemeral departments appear in the default org chart, or only in the
   "forming" band? (Draft: forming band.)
3. Is the chief a `members` row or a singleton service concept? (Draft: a row,
   so the same addressing rules apply uniformly in slice 2.)
4. Does a department carry project scope, or is project a pure view lens over
   one company org? Operator leaned toward "ATLAS builds new departments *and
   workspaces* as needed", which suggests scope is real — **deferred to slice 4**,
   but slice 1's schema must not preclude it.
5. Naming: `members` vs `staff` vs `roster`. Draft uses `members`.

---

## 7. What was deliberately NOT done

`infra/migrations/0038_org_substrate.sql` was **not written**. The autonomous
loop applies migration files to the live `~/.atlas/atlas.db` within ~2h of the
file existing, before any commit or review. Sections 2–5 are unreviewed, so
shipping the DDL now would mutate the live database against an unfinished
design. The SQL in §1 is ready to lift verbatim once §§2–5 are approved.
