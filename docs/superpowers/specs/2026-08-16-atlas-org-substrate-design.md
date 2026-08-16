# ATLAS Org Substrate — design (slice 1 of 5)

**Date:** 2026-08-16
**Status:** sections 1–5 APPROVED by operator · awaiting spec review gate
**Research input:** `docs/research/2026-08-16-founderos-teardown.md`
**Approach:** A — the org supersedes teams (chosen over additive, chosen over projection)
**Migration:** `0039_org_substrate.sql` (0038 is taken by `0038_brain_node_provenance.sql`)

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

## 1. Entity model

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
What is missing is the *standing* structure above it.

Mapping to FounderOS: their `agents` row ≈ our `agent_presets`; their in-memory
`RuntimeAgent` ≈ our `actors`. They have no equivalent of the org layer either —
their `/org` chart is display over a flat `Map`.

`actors` gains exactly one column in this slice (`member_id`, §2) and is
otherwise untouched.

### Migration (additive ALTER, then RENAME — nothing breaks mid-flight)

```sql
-- departments (was: teams)
ALTER TABLE teams ADD COLUMN charter        TEXT NOT NULL DEFAULT '';
ALTER TABLE teams ADD COLUMN lifecycle      TEXT NOT NULL DEFAULT 'ephemeral'
     CHECK (lifecycle IN ('ephemeral','standing','dissolved'));
ALTER TABLE teams ADD COLUMN created_by     TEXT NOT NULL DEFAULT 'operator'
     CHECK (created_by IN ('operator','chief','manager'));
ALTER TABLE teams ADD COLUMN origin_run_id  TEXT REFERENCES runs(id);
ALTER TABLE teams ADD COLUMN rationale      TEXT NOT NULL DEFAULT '';
ALTER TABLE teams ADD COLUMN promoted_at    TEXT;
ALTER TABLE teams ADD COLUMN promoted_by    TEXT;   -- 'operator' | 'gate'
ALTER TABLE teams ADD COLUMN last_active_at TEXT;   -- the reaper's clock (§3)
ALTER TABLE teams ADD COLUMN display_order  INTEGER NOT NULL DEFAULT 0;
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

-- the runtime binding: which member this process is (§2)
ALTER TABLE actors ADD COLUMN member_id TEXT REFERENCES members(id);

-- equipping: a department is equipped BY modules; it is not one
CREATE TABLE IF NOT EXISTS department_modules (
  department_id TEXT NOT NULL REFERENCES departments(id),
  module_id     TEXT NOT NULL,          -- deliberately no FK; see §4
  equipped_at   TEXT NOT NULL,
  equipped_by   TEXT NOT NULL,
  PRIMARY KEY (department_id, module_id)
);
CREATE INDEX IF NOT EXISTS idx_members_department   ON members(department_id);
CREATE INDEX IF NOT EXISTS idx_members_parent       ON members(parent_member_id);
CREATE INDEX IF NOT EXISTS idx_departments_lifecycle ON departments(lifecycle);
CREATE INDEX IF NOT EXISTS idx_actors_member        ON actors(member_id);
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
6. `departments.last_active_at` backfills to `updated_at`, so no migrated
   department reads as idle-since-forever on the first reap.

### Invariants — enforced in `org_service.py`, each with a test

1. Exactly one `tier='chief'`; its `department_id` and `parent_member_id` are NULL.
2. A department **holding any members** has exactly one `tier='manager'`, whose
   parent is the chief. A department created but not yet staffed has none —
   `create_department` and `appoint_manager` are separate operations — and is
   not addressable until a manager is appointed.
3. A worker's `parent_member_id` resolves to a manager **in the same department**.
4. **Orphan promotion** — a member whose parent has left surfaces at department
   root rather than vanishing. Ported verbatim from FounderOS `hierarchy.ts:28`;
   it is why their chart never silently loses an agent.
5. A department cannot be dissolved while it holds `standing` members —
   raises `OrgLifecycleConflict`, whose message names the reassign-first path.

### Provenance and promotion

`created_by` + `origin_run_id` + `rationale` appear on both tables so that when
ATLAS invents a department mid-run, the record of who created it and why is
queryable. This is the same doctrine as memory provenance: quality is assigned
by origin, never by the writer.

Promotion `ephemeral → standing` is **earned, not declared**:

- **gate-earned** (`promoted_by='gate'`) — the department has at least
  `org.promote_min_runs` (default **3**) completed runs attributed to it, of
  which **at least one is `verified`** and **none is `contradicted`**; or

  A run is *attributed to* a department through the §2 binding:
  `actors.member_id → members.department_id`. A run with no member context is
  attributed to nothing and counts toward no department's promotion.
- **operator-declared** (`promoted_by='operator'`) — explicit promotion.

The gate's vocabulary is `no_mutations | verified | contradicted | unverified |
exempt` (`verification_gate.py:70`). There is no `fail` verdict, and requiring
every run to be `verified` would make promotion unreachable: `unverified` and
`exempt` are the normal outcome for a department that writes documents, and the
gate is reporting-only by design. The rule above says the useful thing — this
department has done work someone checked, and nothing it claimed was refuted.

The chief may create and dissolve, but **may not promote**. Promotion is the
operator's boundary.

---

## 2. Mutation contract

How ATLAS restructures itself at runtime. Exposed as one bounded tool surface,
following the `atlas_module` single-generic-tool precedent rather than five
separate tools.

### The runtime binding — who is calling

The operation table below assigns authority by tier, and until this slice
nothing at runtime could answer *which member is calling*. `actors`
(`0022_actors.sql`) carries a free-text `role` defaulting to `'worker'` and no
member link. The single place in the codebase where a member becomes an actor is
`team_run_worker.py:133-141`, which passes `role=member["role_label"]` and drops
`member['id']` — the member row is in hand and thrown away.

So `actors.member_id` is written there, at the one site where both rows exist,
for the same reason `team_chat_messages.sender_status` is written at append time:
deriving it later reads a world that has moved on.

```python
# team_run_worker.py:133
actor_service.spawn_actor(
    ...,
    role=member["role_label"],
    member_id=member["id"],      # was dropped
)

org_service.caller_authority(actor) -> 'operator' | 'chief' | 'manager' | 'worker'
```

Resolution rules:

- An actor with `member_id` resolves to that member's `tier`.
- **`member_id IS NULL` resolves to `worker`** — no mutation authority. This is
  the case for every cockpit chat, mission and CLI run today, and the safe
  default: a run with no org context cannot restructure the org.
- Operator-driven paths (CLI, cockpit action) resolve to `operator`.

Spawning also stamps `departments.last_active_at` for the member's department —
the same call site, and the only thing that makes §3's reaper implementable.

### Operations

| Operation | Caller | Effect |
|---|---|---|
| `create_department(name, charter, rationale)` | chief | new `lifecycle='ephemeral'` department |
| `appoint_manager(department_id, …)` | chief | one manager, parent = chief |
| `hire(department_id, name, role_label, goal_template, model, parent_member_id)` | manager (own dept only) | new ephemeral worker |
| `equip(department_id, module_id)` | chief, manager (own dept) | row in `department_modules` |
| `dissolve(target_kind, target_id, reason)` | chief (`department`), manager (`member`, own crew only) | `lifecycle='dissolved'`, `archived_at` set |
| `promote(target_kind, target_id)` | **operator or gate only** | `ephemeral → standing` |

`target_kind` is `'department' | 'member'` and is explicit rather than inferred
from the id, so a caller cannot dissolve a department by passing an id it
believed was a member's.

Rules:

1. **Authority is tiered**, and checkable — see the binding above. The chief
   shapes departments and appoints managers. A manager staffs only its own
   department. A worker cannot mutate the org.
2. **Every mutation emits an audit event.** A new audit event type must be
   registered in the `AuditEvent.event_type` Literal
   (`packages/atlas-core/atlas_core/schemas/core.py:319`) *and* the
   `surface_events.py` kind map, before the first emit site. An unregistered
   type fails pydantic validation inside a fail-open emit and disappears
   silently.
3. **Mutation is capped per run** — a flat cap in this slice, following the
   `materialize` 5-per-run precedent. The real economy (a shared message and
   mutation budget) is slice 2's; slice 1 must not forward-depend on it.
4. **Nothing is hard-deleted.** Runs and evidence reference departments forever;
   dissolution is a state, not a `DELETE`.

**Resolved:** an ephemeral department created mid-run **survives the run** and is
reaped only when idle. A department that dies with its run can never accumulate
the evidence promotion requires, which would make the ephemeral→standing ladder
dead on arrival.

---

## 3. Lifecycle and disposal

```
                 promote (gate or operator)
   ephemeral ──────────────────────────────► standing
       │                                        │
       │ reaper: idle > N days, never promoted  │ dissolve (operator/chief,
       │  (report-only; operator applies)       │  blocked while standing
       ▼                                        ▼  members remain)
                        dissolved  ◄────────────
```

- **ephemeral** — fully functional, addressable, runnable. Rendered in a
  separate "forming" band on the org chart so the standing org stays legible.
- **standing** — the operator's official org on this machine. Survives reaping.
- **dissolved** — `archived_at` set, history retained, excluded from addressing.

### The reaper

Hosted on the daemon startup hook (`runtime_daemon.py`), the same place
`scratchpad_service.sweep(startup=True)` runs, plus a CLI surface:

```
atlas org reap            # lists candidates, dissolves nothing
atlas org reap --apply    # the operator pulls the trigger
```

**Report-only in this slice.** The startup hook computes candidates and records
them as an audit event; it never dissolves. Automatic dissolution is a later
decision, taken once the idle clock has been observed against real usage — the
same discipline the scratchpad sweep earned: destructive automatic behaviour
ships only after the lifecycle is proven closed, and nothing today un-dissolves
a department.

Safety rules, each with a test:

- Never reap a department with a **non-terminal actor** (`queued`/`running`).
- When `last_active_at` is NULL, fall back to `created_at` — a department
  created seconds ago has not spawned yet and must not read as idle.
- Never reap `standing` or already-`dissolved` departments.

### Cascade

- Dissolving a department **dissolves its ephemeral members**.
- **Standing members block dissolution** (invariant 5). The operator's path is
  *reassign, then dissolve*, and `OrgLifecycleConflict` says so rather than
  raising bare.

### Thresholds

Config knobs, not constants — the `ATLAS_CONVERSATION_TOKEN_BUDGET` pattern:

| Knob | Default | Meaning |
|---|---|---|
| `org.reap_idle_days` | 14 | idle threshold for reap candidacy |
| `org.promote_min_runs` | 3 | completed runs required for gate promotion |

---

## 4. Module equipping

A department's effective capability is the union of its equipped modules'
declared doctrine, records, workflows, and MCP tools. Module capability v2
already declares all four, so equipping is a join, not a new contract.

- Equipping is per **department**, not per member. A member inherits its
  department's equipment. Per-member equipping is deliberately deferred (YAGNI).
- Equipping is a mutation: audited and capped like the rest.

### The narrowing rule

Equipping **narrows, never widens**:

> A module is reachable when it is globally active **and** (the caller has no
> member context **or** it is equipped to the caller's department).

Global activation stays the operator's authorization boundary. That is what
makes injecting module doctrine as `<module-doctrine trust="operator">` honest
(capability v2, decision 4); equipping cannot grant what activation withheld.

The `or the caller has no member context` half is load-bearing, not a
convenience. Almost no run has a member context today — cockpit chat, missions
and CLI all resolve `member_id = NULL`. Scoping unconditionally would remove the
outreach module from every surface that currently uses it.

### Doctrine follows equipment

`active_context_blocks()` takes an optional `department_id`:

```python
active_context_blocks(department_id=None)              # today's behaviour, unchanged
active_context_blocks(department_id="dept_admissions") # only equipped modules
```

This makes equipping a context-budget win rather than bookkeeping: an Admissions
worker stops spending `context.module_token_budget` (1,800) on Outreach
compliance doctrine it cannot act on.

### Dangling equipment

`department_modules.module_id` carries **no FK**, matching how module records
outlive deactivation. The rules instead:

- Equipping a module that is not installed is **refused at write time**.
- A module that later goes `missing` leaves its row in place and is filtered on
  read.

---

## 5. Testing

The headline test is ported from FounderOS `tests/seed.test.ts:37`
(*"every seeded agent maps to a real runtime agent — no larp"*), which is the
single best idea in that repository:

> **`test_every_member_is_runnable`** — iterate every non-dissolved member and
> assert it resolves to a configuration the runtime can actually spawn: a valid
> provider name, a non-empty `goal_template`, a model that resolves to a
> default. Fails CI if the org chart can display someone who cannot work.

**It must never touch the network.** `provider status` reports configuration
shape, not reachability, and the freellmapi sidecar is down by default. A
runnability test that opens a socket fails CI whenever the sidecar is off, and
the tempting fix is to weaken the test.

ATLAS has no such invariant today; cockpit surfaces can show what the runtime
cannot execute. This test closes that hole permanently.

### Required tests

| Test | Guards |
|---|---|
| **a run with no member context still sees every active module** | the §4 narrowing hazard — the most important new test |
| spawning a team member populates `actors.member_id`; `caller_authority(NULL)` → worker → mutation refused | §2 binding |
| a departmental member's brief carries only equipped doctrine | §4 |
| one-chief, manager-per-department, worker-parent-in-same-department | invariants 1–3 |
| orphan promotes to department root | invariant 4 |
| dissolve with standing members raises `OrgLifecycleConflict` naming reassign-first | invariant 5, §3 cascade |
| dissolving a department dissolves its ephemeral members | §3 cascade |
| `reap()` dry-run mutates nothing; skips non-terminal actors; falls back to `created_at` when `last_active_at` is NULL | §3 reaper |
| ≥1 `verified` + 0 `contradicted` promotes; all-`unverified` does not; one `contradicted` blocks | §3 promotion arithmetic |
| preset in two teams clones on migration | backfill rule 2 |
| pre-existing teams migrate as `standing` | backfill rule 3 |
| gate-earned vs operator-declared promotion sets `promoted_by` correctly | promotion |
| chief cannot call `promote` | authority |
| worker cannot call any mutation | authority |
| the per-run mutation cap refuses the N+1th mutation | §2 rule 3 |
| an unstaffed department has no manager and is not addressable | invariant 2 |
| every mutation emits its audit event (Literal + surface map + emit site) | §2 rule 2 |

### The check that cannot be a unit test

Backfill rule 2 — a preset belonging to two teams must clone — is a real-data
condition. A fresh fixture contains exactly the rows whoever wrote it thought of,
and this repository's own record is that three passes of unit tests missed what
one real run found in seconds.

So `0039` additionally requires a **read-only dry-run against a copy of the live
`~/.atlas/atlas.db`**, run and its findings reported **before the migration file
is committed**. Not CI — a probe, in the shape of the verification-gate backfill.

---

## 6. Decided during review, and the one deferral

| Question | Resolution |
|---|---|
| Reaper threshold, promotion N | `org.reap_idle_days=14`, `org.promote_min_runs=3`, both config knobs (§3) |
| Do ephemeral departments appear on the default org chart? | No — a separate "forming" band, so the standing org stays legible |
| Is the chief a `members` row or a singleton service concept? | A row, so slice 2's addressing rules apply uniformly with no special case |
| Naming: `members` vs `staff` vs `roster` | `members` |
| Does an ephemeral department survive its run? | Yes; reaped only when idle (§2) |

**Deferred — department project scope.** Whether a department carries project
scope, or `project` is a pure view lens over one company org, is slice 4's
decision. The operator leaned toward "ATLAS builds new departments *and*
workspaces as needed", which suggests scope is real. Slice 1's schema must not
preclude it: adding `departments.scope_id` later is an additive `ALTER` with a
NULL default, and nothing in this slice keys on a department being globally
unique by name.

---

## 7. What is deliberately NOT done

`infra/migrations/0039_org_substrate.sql` is **not written by this spec**. The
autonomous loop applies migration files to the live `~/.atlas/atlas.db` within
~2h of the file existing, before any commit or review. The DDL in §1 is ready to
lift verbatim during implementation, after the live-DB dry-run in §5.

The number is `0039`, not `0038` — `0038_brain_node_provenance.sql` shipped last
session and is already applied to the live database.
