# Chat Actor Workspace — Execution Log

## Goal

Repair the durable actor regression and deliver a three-zone Chat cockpit with
live child activity, preserved future file-tree space, model/function routing,
and a persistent four-message prompt queue.

## Waves Executed

### Wave 1: Runtime repair

- Hidden Windows worker executable/flags — done.
- Parent-run surface session authority — done.
- Pre-execution child-run binding — done.
- Configured durable actor model routing — done.

### Wave 2: Chat behavior

- Four-item persisted FIFO queue with promote/edit/delete — done.
- Exactly-once drain after a live turn settles — done.
- Redundant raw `atlas_actor` tool card suppression — done.
- Real child audit stream projection in the actor overlay — done.

### Wave 3: Three-zone interface

- Reserved 200px left file-tree rail — done.
- Definite-height independent transcript scroller — done.
- 400px sparse actor workspace and compact drawer — done.
- Primary/actor/curator/auxiliary/judge model mesh — done.
- Luminous composer focus/send treatment and reduced-motion fallback — done.

### Wave 4: Evidence and cleanup

- Removed bundled `example-hello` module — done in `158f10e`.
- Added actor, queue, model routing, concurrency warning, persistence, and
  Windows launch regression coverage — done.
- Wide and narrow rendered QA plus scroll measurement — done.

## Verification

- [x] Agent runtime: 918 passed, 1 skipped.
- [x] Shared atlas-core: 97 passed.
- [x] WebUI: 129 passed.
- [x] TypeScript check and production build passed.
- [x] Bundle budget passed (`Chat` 31.64 KB raw / 10.08 KB gzip).
- [x] ESLint and Ruff passed.
- [x] `git diff --check` passed.
- [x] Playwright wide/narrow pixels inspected.
- [x] Transcript measured `702px client / 2305px scroll / 1603px offset /
  overflow-y:auto`.

## Commits

- `e1a1594`: `fix(actor): restore hidden integrated workers`
- `9693b97`: `feat(chat): build three-zone actor workspace`

## Principal Files

- `services/agent-runtime/atlas_runtime/actor_worker.py`: hidden Windows launch
  and routed runtime instantiation.
- `services/agent-runtime/atlas_runtime/actor_service.py`: surface authority and
  live child binding.
- `services/web-ui-react/src/routes/Chat.tsx`: queue dispatch and three-zone host.
- `services/web-ui-react/src/components/chat/ChatActorWorkspace.tsx`: actor rail
  and live stream.
- `services/web-ui-react/src/components/chat/ChatModelRouter.tsx`: role-based
  registry/config overlay.
- `services/web-ui-react/src/components/chat/QueuedChatComposer.tsx`: queue and
  polished input.
- `services/web-ui-react/src/app.css`: responsive cockpit and interaction states.
