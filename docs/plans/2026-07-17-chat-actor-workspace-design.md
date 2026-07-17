# Chat actor workspace and queued composer

**Status:** accepted from operator references on 2026-07-17  
**Surface:** `services/web-ui-react` Chat  
**Primary style:** Taste `dashboards`  
**References:** ATLAS Dark Prism, Linear surface hierarchy, Codex queued composer

## Intent

Turn Chat's unused right-hand space into an operational actor workspace and
allow the operator to keep writing while a turn runs. The result should feel
like one focused cockpit, not a chat transcript with a dashboard attached.

## Approaches considered

1. **Local projection over the existing surface stream — selected.** Fold actor
   lifecycle events already delivered to Chat, and keep a four-item prompt
   queue in the chat snapshot. This adds no transport, dependency, or daemon.
2. Add actor-list and child-stream gateway endpoints. This could expose the
   child's complete transcript, but duplicates the existing event projection
   before the product has proven that full child tokens are required.
3. Embed actor cards inside every parent turn only. This exists today and is
   useful as provenance, but it cannot use the available workspace or provide
   a stable place to inspect parallel work.

The selected slice keeps inline orchestration provenance while making the
right rail the persistent operational view. Its detail overlay is an honest
live lifecycle stream: status, current tool, tool count, model, topology, and
duration. A later gateway slice can add full child transcript content without
changing the component contract.

## Layout

- Wide (`>= 1180px`): transcript and actor rail share the main panel. The rail
  is 280–320px, separated by a hairline, with actors as compact rows rather
  than nested cards.
- Medium: rail becomes a 240px inspection strip.
- Narrow (`< 900px`): rail collapses behind a compact `ACTORS n` trigger; the
  actor detail remains a modal drawer.
- The composer spans the transcript column. Queued prompts form a shallow
  stack directly above it, matching the Codex reference's spatial model.

## Actor workspace

- Fold immutable surface events last-write-wins for current actor state and
  retain ordered lifecycle steps per actor for the overlay.
- Show all actors; there is no total/lifetime display cap.
- Count active actors separately from completed actors. Above ten active in
  parallel, show a non-blocking efficiency warning. Never prevent spawning.
- Actor rows expose phase, short goal, current tool, model, depth, joined vs.
  detached, tool count, and elapsed duration when available.
- Clicking a row opens a right-side overlay with the live lifecycle timeline.
  Escape, backdrop click, and an explicit close button dismiss it.

## Composer and queue

- The textarea remains enabled while the current turn streams.
- `Enter` sends immediately when idle and queues when busy; `Shift+Enter`
  inserts a newline.
- Maximum queue length is four. At capacity, the draft is preserved and an
  inline message explains that one queued item must be removed first.
- Queue rows can be promoted to next, moved one position, edited back into the
  draft, or deleted. Promotion never interrupts the active run.
- When a turn settles, the first queued prompt dispatches exactly once through
  the existing `submitPrompt` path. Queue state is stored with the chat
  snapshot so reloads preserve operator intent.
- Runtime/provider selection moves into the lower workspace controls, next to
  the active session model identity. It is disabled only while a turn runs.

## Visual contract

- Preserve ATLAS's tuned off-black canvas, topo field, serif page title, Inter
  body, and JetBrains Mono operational labels.
- Use brightness-step surfaces and one-pixel hairlines; no new gradients,
  drop-shadow tiers, or decorative cards.
- Keep emerald for live/success state, celestial blue for operator actions,
  bronze for caution, and magenta/red for cancel/error only.
- Composer radius: 10–12px; queue stack radius decreases upward so the layers
  read as one object. Actor rows use 4–6px radii and mostly dividers.
- Motion is stateful: queue insertion/reordering, breathing live dots, and the
  drawer entrance. Respect `prefers-reduced-motion`.

## Budgets

- New runtime dependencies: **0**.
- Queue cap: **4 prompts**.
- Actor display cap: **none**; warning threshold: **>10 active**.
- Existing surface buffer remains **500 events**.
- No additional polling loop; reuse the provider's two-second refresh.
- Wide-layout breakpoint must not introduce horizontal page scroll.

## Verification

- Component tests cover idle send, busy queue, capacity preservation,
  automatic FIFO dispatch, promotion, edit, deletion, actor folding, warning,
  drawer lifecycle, and narrow-layout trigger.
- Run WebUI unit tests, TypeScript, lint, production build, and bundle budget.
- Inspect at desktop, laptop, tablet, and phone widths against real running
  ATLAS data; verify focus, Escape, keyboard submission, and reduced motion.

