---
created: 2026-07-17T01:14:57.201Z
completed: 2026-07-17
title: Build live actor workspace and queued chat composer
area: ui
files:
  - services/web-ui-react/src/routes/Chat.tsx
  - services/web-ui-react/src/components/chat/ChatActorWorkspace.tsx
  - services/web-ui-react/src/components/chat/ChatModelRouter.tsx
  - services/web-ui-react/src/components/chat/QueuedChatComposer.tsx
---

## Result

Chat now preserves a structural left rail for the future unbound/bound file
tree, contains the transcript in its own definite-height scroller, and uses a
larger right actor workspace. All durable actors remain visible; more than ten
active actors produces a recommendation rather than a hard total limit.

Actor rows open a lifecycle/child-run overlay backed by real surface audit
events. The footer opens role-based model routing for Chat, actors, curator,
auxiliary tasks, and goal judgement. Durable workers apply the configured actor
route.

The composer accepts four persisted FIFO follow-ups during a live turn, with
promote-next, edit, delete, cancel, and automatic exactly-once dispatch at the
next settled boundary. Wide and narrow layouts, reduced motion, focus effects,
model routing, queue drain, child tool projection, and scroll containment were
verified by automated tests and Playwright.

## Evidence

- Agent runtime: 918 passed, 1 skipped.
- Shared atlas-core: 97 passed.
- WebUI: 129 passed plus production build/bundle budget and ESLint.
- Ruff and `git diff --check`: clean.
- Playwright scroll probe: 702px client height, 2305px scroll height, 1603px
  reachable scroll offset, `overflow-y: auto`.
- Design and forensics:
  `.planning/ultra/ULTRADESIGN-chat-three-zone-cockpit-contract.md` and
  `.planning/ultra/ULTRAREVIEW-durable-actor-ui-regressions.md`.
