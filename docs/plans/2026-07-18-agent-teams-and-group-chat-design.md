# ATLAS Agent Presets, Teams, and Group Chat

Date: 2026-07-18
Status: implementation contract (Phase 1+2 this session; Phase 3 deferred)

## Outcome

Two distinct, persistent structures, as requested:

- **Agent preset** — a single reusable agent configuration (role label, goal
  template, model, provider, mode). Quick-launch one agent from Chat without
  retyping its brief every time.
- **Team** — a named, ordered roster of presets. Invoking a team starts a
  **team run**: every member is spawned as a real `actors` row (existing
  durable actor supervisor, unchanged) and the members exchange messages
  through a shared, ordered, cursor-consumed log — a group chat — instead of
  a strict parent/child delegate hierarchy.

Both persist in SQLite next to missions/actors, survive restarts, and are
reusable across missions (long-term structure, per your answer that presets
and rosters serve different purposes and should not be collapsed into one
table).

## Considered approaches for group chat

1. **New process supervisor for concurrent agent turns.** Most "realistic"
   simulation of agents talking over each other, but it means building a
   second actor_worker.py-class supervisor, a new scheduler, and new failure
   modes (races, partial writes) from scratch. Large, risky, duplicates
   infrastructure that already exists and is tested.
2. **Round-robin team run reusing the existing actor supervisor.** Each
   member's turn is one ordinary `spawn_actor` + `wait_for_actor` call
   (already idempotent, crash-safe, cancellable, audited). Turns are
   sequential by design — no two members write concurrently — which is also
   the simplest correct answer to "nice buffer logic": a single-writer,
   append-only, sequence-numbered log with a per-member read cursor. Selected.
3. **Client-side orchestration (frontend polls and re-triggers each member).**
   Rejected: puts a durability-critical loop in a browser tab; dies on tab
   close/reload; no server-side source of truth for whose turn it is.

Approach 2 costs one new lightweight service (`team_chat_service.py`) plus a
thin orchestrator (`team_run_service.py`) that composes two functions the
actor supervisor already exposes. No new process model.

## Data model (migration 0028)

```sql
agent_presets(id, name UNIQUE, role_label, description, goal_template,
              model, provider, mode DEFAULT 'joined', created_at, updated_at)

teams(id, name UNIQUE, description, created_at, updated_at)

team_members(team_id, preset_id, position, PRIMARY KEY(team_id, preset_id))

team_runs(id, team_id, parent_run_id REFERENCES runs(id), mission_id,
          status CHECK(queued|running|completed|failed|cancelled),
          max_rounds DEFAULT 6, current_round DEFAULT 0,
          created_at, started_at, finished_at, updated_at)

team_chat_messages(id, team_run_id, seq (monotonic per team_run),
                    round, sender_actor_id NULL (NULL = orchestrator/user),
                    sender_role, target DEFAULT 'all' ('all' or a role_label
                    for an @mention), content, created_at)
```

`team_chat_messages.seq` is the buffer's ordering primitive; each member's
actor goal is built from every row with `seq > <member's last consumed seq>`
and `target IN ('all', <member's role_label>)` — the same claim-cursor shape
`actor_deliveries` already uses, at table scope instead of per-row lease
(no concurrent claimants exist by construction: one member runs at a time).

## Runtime flow (team_run_service.start_team_run)

1. Validate the team has ≥1 member; create a `team_runs` row (`queued`).
2. Seed round 0 with the user's kickoff message as one `team_chat_messages`
   row (`sender_actor_id=NULL`, `target='all'`).
3. For `round` in `1..max_rounds`, for each member in `position` order:
   a. Build the member's inbox: unseen messages targeted at it or `all`.
   b. `spawn_actor(goal=preset.goal_template + rendered inbox, role=role_label,
      model=preset.model, mode='joined', session_id=team_run's session)`.
   c. `wait_for_actor(...)` (existing bounded-timeout join).
   d. Parse the result for a leading `@role_label:` prefix (simple, no new
      dependency) to set `target`; default `all`. Insert one
      `team_chat_messages` row with the actor's result as `content`.
   e. A member replying literally `DONE` (case-insensitive, whole message)
      ends the run early as `completed`.
4. Exhausting `max_rounds` without `DONE` ends the run as `completed` anyway
   (bounded by design, mirrors the iteration-budget fail-safe fixed earlier
   this session — a team run can never loop forever).

This function runs on the same detached-worker thread pattern actors already
use (`actor_worker.py`), so team runs survive the triggering HTTP request
and are resumable/inspectable the same way actors are.

## Gateway API

- `GET/POST /v1/agent-presets`, `PATCH/DELETE /v1/agent-presets/{id}`
- `GET/POST /v1/teams`, `PATCH/DELETE /v1/teams/{id}`,
  `PUT /v1/teams/{id}/members` (replace roster + ordering)
- `POST /v1/teams/{id}/run` (mission_id, kickoff message) → `team_runs` row
- `GET /v1/team-runs/{id}`, `GET /v1/team-runs/{id}/messages`

## Frontend

- New `/teams` route (STRUCTURE pillar, mirrors `/skills`): preset library
  (create/edit/delete) and team roster builder (drag-order or up/down,
  add/remove presets).
- Chat: a team picker next to the existing model router; starting a team run
  renders the shared log as a group-chat transcript (reuses the existing
  actor detail stream's visual language — sender chips instead of a single
  child stream) inside `ChatActorWorkspace`.

## Deferred to Phase 3 (documented, not built this session)

- **Mid-run steering** (injecting a message into an already-running actor
  instead of waiting for its turn to end) requires the vendored Hermes
  foundation to accept input mid-`run_conversation` — a foundation-boundary
  capability question (D-001: ATLAS never edits the foundation) that needs
  its own investigation before design, not a rushed bolt-on.
- **True concurrent cross-talk** (two members composing at once) requires
  approach 1 above; only worth the cost if round-robin proves too slow/rigid
  in practice.
- **@-mention routing from the live Chat composer into a running team** — the
  data model already supports `target=<role_label>`; wiring it into the
  composer is straightforward once Phase 3's steering primitive exists.

## Budgets

- No new runtime dependency (reuses existing actor supervisor, sqlite3, axum).
- `max_rounds` defaults to 6, capped at 20 server-side (mirrors the
  iteration-budget fail-safe philosophy: bounded by construction).
- Team run messages capped at 4 KiB each (mirrors `actors.goal` GOAL_CAP style).

## Verification plan

- `team_chat_service`: cursor/buffer correctness (unseen-only, target
  filtering), monotonic seq, ordering.
- `team_run_service`: round-robin sequencing, early `DONE` exit, max_rounds
  bound, idempotent restart-after-crash (reuses actor idempotency).
- Gateway: CRUD contract tests for presets/teams/members, team-run start/read.
- WebUI: Teams page CRUD, Chat team picker + group-chat transcript rendering.
