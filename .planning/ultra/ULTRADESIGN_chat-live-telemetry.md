# ULTRADESIGN — ATLAS live orchestration telemetry

Date: 2026-07-16
Primary Taste mode: Dashboards (density 7, motion 5)
References: Linear for surface hierarchy and precision; Composio for a sparse
developer-infrastructure signal field.

## Design contract

### Palette and material

- Keep ATLAS's tuned near-black/topographic canvas.
- Use brightness-step surfaces and hairlines; no new shadow ladder.
- Emerald means live execution, celestial blue means routing/inspection,
  bronze means taxonomy. Color remains scarce outside state changes.

### Typography

- Existing display face for workspace titles.
- Existing sans for readable goals and narration.
- Mono only for actor IDs, tools, phases, pulse counts, and model routes.

### Layout

- Preserve the future file-tree reserve on the left.
- Increase the desktop actor rail to a 430–480 px inspection slab.
- Put a signal field above the actor lists so the first glance answers what is
  executing now; keep lists below for precise selection/history.
- Increase the actor dialog to a true inspection workspace, not a compact card.

### Components and behavior

- Each active actor is a signal node. A new actor tool event remounts one
  transform/opacity pulse keyed by event sequence.
- Actor rows expose current tool, phase, and pulse count and open the same live
  inspection dialog as the signal node.
- `delegate_task` and `atlas_actor` use a dedicated orchestration dispatch card
  with goal, operation, actor count, and live/terminal state.
- Model Mesh becomes a larger footer instrument with explicit routing scope.

### Motion

- Motion encodes event arrival only: one expanding pulse per new tool event,
  restrained live-node breathing, and weighted modal entry.
- No decorative perpetual fields beyond active status.
- `prefers-reduced-motion` removes pulses and transitions without removing data.

### Guardrails

- No purple AI gradient, glass-card spam, decorative orbs, or nested chrome.
- No limit on actor count; warn above ten concurrent actors.
- Keep wide, laptop, drawer, and touch layouts legible and operable.
- Do not let actor telemetry or auto-follow steal transcript scroll control.

## Rendered result

- Desktop grid: 210 px future file-tree reserve, flexible transcript, 460 px
  actor workspace; 160/flexible/420 at laptop width.
- Live actor workspace: event-keyed signal field, active/recent rows, immediate
  allocation signals, and a 980 px inspection dialog with current signal plus
  chronological child-run telemetry.
- Dedicated `delegate_task` / `atlas_actor` control-plane card and a 70 px Model
  Mesh footer instrument replace generic compact tool treatment.
- Playwright inspection passed at 1920×1080 and 900×1000, including active
  actors, the detail dialog, and the narrow actor drawer.
