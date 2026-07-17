# Chat Three-Zone Cockpit — Design Contract

## Diagnosis

- Product: operator workspace / AI cockpit.
- Density: high-information workspace with quiet peripheral rails.
- Mood: technical, restrained, luminous at interaction boundaries only.
- Primary risks: transcript scroll containment, loss of future file-tree space,
  cramped actor telemetry, and confusing runtime selection with model routing.

## Contract

```yaml
palette:
  background: "existing ATLAS ink / topo field"
  surface: "rgba(5, 8, 14, 0.86)"
  primary: "var(--atlas-celestial)"
  activity: "var(--atlas-emerald)"
  accent: "var(--atlas-bronze)"
  text: "existing l2 foreground scale"
typography:
  display: "existing ATLAS display face"
  body: "Inter"
  mono: "JetBrains Mono"
spacing: { scale: "4px", rhythm: "8px" }
layout:
  desktop: "200px reserved file rail / fluid transcript / 400px actor rail"
  compact: "file rail removed first; actor rail becomes a drawer below 980px"
motion: { level: "subtle", easing: "var(--l2-ease)" }
radius: { sm: "2px", md: "5px", lg: "8px" }
shadows:
  composer: "focused edge glow, no decorative bloom"
  overlay: "deep elevation plus one celestial border"
components:
  transcript: "definite-height independent TopoScroll viewport"
  file_reserve: "intentionally empty structural rail for future tree"
  actor_workspace: "larger, sparse rows; child stream in overlay"
  model_router: "role tabs + searchable registry + optimistic config patch"
  composer: "stacked FIFO queue, luminous focus edge, circular send/stop controls"
```

## Behavioral Rules

- Preserve the left rail even while empty; it is structural, not accidental
  whitespace.
- The transcript alone scrolls. The composer and both rails remain fixed inside
  the Chat panel.
- The actor rail shows all actors and only warns above ten active; it never
  imposes a total actor ceiling.
- The bottom actor control opens model routing for primary chat, durable actors,
  curator, auxiliary tasks, and goal judgement. It is not an agent-runtime
  picker.
- Model mutations are disabled during a live turn and use the existing registry
  plus optimistic config revision.
- Narrow layouts remove the empty reserve and move actors into a drawer without
  changing queue or transcript behavior.

## Do / Do Not

- Do use fine rules, restrained scan light, and status color only where state is
  meaningful.
- Do preserve keyboard Escape, visible focus, reduced motion, and text overflow
  containment.
- Do not add dependencies, decorative orbs, glass-on-glass nesting, or fake
  actor token streams.
