# Session Navigator and Stream Visuals

## Intent

Give the dedicated Chat page and Console workbench one coherent session index
without conflating durable operator conversations with the gateway's short-lived
execution surface leases.

## Session model

- A browser-local catalog stores shared metadata: session id, owning surface,
  title, agent, last activity, and binding.
- Chat and Console retain separate payload schemas because their state shapes are
  materially different.
- Unbound sessions appear directly under `UNBOUND`.
- Bound sessions appear inside collapsible folder/project groups.
- Selecting a row on the current surface restores it in place. Selecting a row
  owned by the other surface records its active id and routes to that page.
- New sessions inherit the current binding; `NEW UNBOUND` explicitly clears it.
- Live Console provider state wins over a debounced stored snapshot while a turn
  is active, preserving continuations across route remounts.

The catalog is intentionally localStorage-backed for this iteration. Gateway
surface sessions are permission/execution leases and are not a durable,
user-browsable conversation store.

## Streaming visuals

`StreamReveal` is shared by Chat and Console. It:

- paces coarse network chunks into a smoother visible prefix;
- renders that prefix through live Markdown;
- restarts a restrained scan-line/frontier effect when new chunks arrive;
- honors reduced-motion preferences;
- exposes effect enabled state, reveal speed, signal intensity, and auto-follow
  in Control > Visuals.

Auto-follow remains attached while the viewport is within 180 px of the bottom.
Scrolling farther away detaches it; the jump-to-latest control reattaches it.

## Verification

- WebUI Vitest: 94/94 passing.
- ESLint: clean with zero warnings.
- TypeScript: clean.
- Production Vite build: passing.
- Bundle budgets: passing.
- `git diff --check`: clean.

## Operator UAT

1. Open Chat and Console and verify both session buttons show the same catalog.
2. Create unbound and folder-bound sessions, switch among them, and reload.
3. Select a session owned by the other surface and verify routing/restoration.
4. Stream Markdown with lists/code and tune Control > Visuals while observing it.
5. Stay near the bottom and confirm follow; scroll upward and confirm it detaches.

## Continuation: session-first run history and compact evidence

- The Runs route groups persisted runs by their real `session_id`, not by a title
  or time-window heuristic. Each session expands into prompt/run rows that link to
  the existing evidence detail.
- Legacy runs with no session id are intentionally isolated rather than collapsed
  into a synthetic global session.
- Adjacent model deltas are grouped only in the UI projection. Tool boundaries,
  status transitions, and another run terminate a group; raw audit rows are never
  rewritten or discarded.
- Control > Storage exposes the existing retention-deadline purge with confirmation.
  Automatic scheduling and arbitrary date filters remain planned until backed by a
  transactional preview and scheduler contract.
