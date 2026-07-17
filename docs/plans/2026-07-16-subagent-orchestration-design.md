# ATLAS Subagent Orchestration and Agent Constellation

Date: 2026-07-16
Status: implementation contract

## Outcome

ATLAS exposes one actor protocol across WebUI Chat, Console, and the terminal:

- `run`: spawn a child and join it;
- `spawn`: return a stable handle immediately and let the parent continue;
- `status`: inspect one child without consuming its result;
- `wait`: join an existing child with a bounded timeout;
- `cancel`: idempotently stop one child and its descendants.

Hermes remains the child reasoning/tool runtime. ATLAS owns actor durability,
process supervision, completion delivery, audit projection, and presentation.

## Considered approaches

1. Change Hermes `delegate_task` to support background mode. This is compact but
   breaks D-001's upstream-mergeable foundation boundary and couples ATLAS state
   to a large synchronous function.
2. Detach Python threads inside the parent run. This is cheap but children die
   when the per-prompt worker exits and cannot survive a gateway restart.
3. Persist actors in ATLAS SQLite and launch a dedicated actor worker. This is
   the selected design. It reuses Hermes through ATLAS's existing adapter,
   survives parent completion, and keeps every mutation queryable and auditable.

## State model

The record is deliberately flat and serializable:

`queued -> running -> completed | failed | cancelled | orphaned`

Every actor has a stable ID, parent run/session/actor IDs, role, goal, selected
model, mode, PID, heartbeat, bounded result/error, and timestamps. A unique
idempotency key identifies the spawn mutation. Duplicate tool delivery returns
the existing actor instead of starting another child.

Terminal transitions are monotonic. Repeated completion or cancellation is a
no-op. On startup, stale `queued`/`running` rows whose workers no longer exist
become `orphaned`; they are never silently reported as successful.

Completion delivery is a separate durable inbox record. Delivery uses a short
claim lease. A pre-model hook claims pending results and injects a compact,
structured completion notice; the post-model hook acknowledges it. A crash
before acknowledgement releases the lease for retry. Explicit `wait` consumes
the same delivery, preventing a later duplicate injection.

## Runtime flow

1. The parent calls the ATLAS actor tool with `run` or `spawn`.
2. The plugin captures the current run/tool-call identity from the existing
   Hermes hook context and performs an idempotent actor insert.
3. A hidden actor worker is launched with only the actor ID on argv. The goal is
   read from SQLite, avoiding command-line leakage and quoting failures.
4. The worker marks `running`, heartbeats, resolves the requested or inherited
   model, and drives a Hermes child in the owning workspace.
5. Progress is projected as actor lifecycle events. Completion atomically writes
   the terminal actor state and one pending delivery.
6. `run`/`wait` blocks only at the tool boundary. `spawn` returns immediately,
   allowing the parent to keep working. A later safe model boundary receives the
   completion through the inbox.

## Antifragility and idempotency

- Stable actor IDs are allocated before launch and become visible before detach.
- Spawn is keyed by parent run + tool call; retries cannot duplicate work.
- Worker launch failure becomes a durable failed actor, not a missing response.
- Heartbeats distinguish slow work from a dead worker.
- Waiting subscribes/polls after an initial read and rechecks immediately to
  close the completion race.
- Cancellation recursively targets descendants and is safe to repeat.
- Completion and delivery use monotonic compare-and-set transitions.
- Raw child output is bounded; full evidence remains in normal audit/run data.
- No queue framework, ORM, or new dependency is introduced.

## Visual contract: Agent Constellation

The UI direction combines ATLAS Topographic with dashboard density and Linear's
quiet product precision.

- Palette: existing void/surface ladder; cyber blue for active flow, violet for
  AI allocation, signal green for verified completion, amber for wait/stale,
  crimson for failure only.
- Header: hidden at zero actors. With activity, show a 28px constellation glyph,
  up to four orbit nodes, `N ACTIVE`, and a one-shot terminal pulse. Clicking it
  opens the existing session utility area rather than adding permanent chrome.
- Transcript: a single orchestration rail, not nested generic cards. The parent
  node anchors the rail; children branch below with role/model, compact goal,
  mode (`JOINED` or `DETACHED`), current tool, duration, and result disclosure.
- Motion: 200ms weighted state changes. Running nodes carry a slow scan wake;
  detached edges are dashed and continue beyond the parent turn; waiting pulls
  the edge taut; terminal nodes cool to stillness. Reduced-motion keeps the
  topology and removes travel/orbit animation.
- Console windows: the title bar shows only the glyph and active count. The full
  rail remains in the transcript so window headers stay draggable and calm.
- Copy is declarative: `ACTOR ALLOCATED`, `3 ACTIVE`, `WAITING`, `RESULT
  DELIVERED`. No celebratory language or emoji.

## Budgets

- No new runtime dependency.
- Header animation: transform/opacity only; at most four animated nodes.
- No always-running animation when there are no active actors.
- Actor list endpoint: session-scoped, latest 100 rows, target under 20 ms local.
- Heartbeat writes: no faster than once every 5 seconds per actor.
- Stored result/error preview: bounded to 16 KiB / 2 KiB.
- Actor worker startup target: under 1 second before `running` is persisted.

## Verification

- Unit tests for duplicate spawn, monotonic terminal transitions, wait races,
  repeated cancel, lease retry/ack, and restart orphan reconciliation.
- Integration test proving `spawn` returns before completion and a later parent
  model boundary receives exactly one result.
- Surface projection tests for all actor states and out-of-order events.
- WebUI tests for header visibility/count, reduced motion, joined/detached rails,
  terminal result disclosure, and Chat/Console parity.
- Browser inspection at desktop and narrow widths, followed by a release gateway
  rebuild and health check.
