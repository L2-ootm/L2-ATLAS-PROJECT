---
created: 2026-07-17T01:14:57.201Z
title: Build live actor workspace and queued chat composer
area: ui
files:
  - services/web-ui-react/src/routes/Chat.tsx:494
  - services/web-ui-react/src/components/agent/AgentPicker.tsx:32
  - services/web-ui-react/src/test/chatPage.test.tsx:123
---

## Problem

The Chat surface leaves a large right-hand region unused while active subagents
are compressed into the orchestration rail inside the transcript. Operators can
see that work exists, but cannot inspect a child's live activity without losing
the main conversation context. The composer is disabled while a turn streams,
so follow-up intent must be held outside ATLAS until the current agent finishes.
The current concurrency presentation also risks turning a safety recommendation
into an arbitrary hard product limit.

## Solution

Design and implement a restrained actor workspace in the existing right-hand
space. Show active/recent subagents with minimalist status, elapsed time, model,
current tool, and compact progress. Clicking an actor opens an overlay/drawer
with its live event stream, goal, parent/child relationship, tool activity,
result, cancellation, and audit evidence. Use the lower portion for contextual
model/provider controls and actor-level actions. Keep the main orchestration rail
as the compact transcript summary.

Remove any arbitrary total-subagent ceiling while preserving explicit resource
and recursion safeguards. Recommend fewer than 10 concurrently active actors in
the UI and policy; above that threshold warn and require intentional operator
confirmation rather than silently refusing all larger trees. Distinguish total
durable actors from simultaneous worker concurrency.

Replace the disabled busy composer with an ordered queue inspired by Codex's
bottom composer. Accept up to four pending messages while the current turn is
running. Render each queued item as a compact editable row with reorder,
redirect/force-next, delete, and overflow actions. After a turn completes, send
the next item exactly once in order. A force-next action injects the selected
message at the next safe request boundary; it must not duplicate or corrupt the
active turn. The composer should retain attachment/access controls,
model/provider selection, microphone/stop state, keyboard accessibility, mobile
fallback, reconnect persistence, and explicit queue/full/error states.

Acceptance coverage must include ordering, the four-item bound, deletion and
reordering, force-next behavior, reconnect/replay idempotency, cancellation,
actor overlay live updates, more-than-ten warning behavior, reduced motion, and
responsive layouts.
