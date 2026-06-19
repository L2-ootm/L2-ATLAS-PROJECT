# Graphify Refinement Pass — Checkpoint

**Date:** 2026-06-19
**Branch:** feat/cockpit-p3-glass-p4
**Scope:** Stabilize + polish the existing Graphify view. No redesign, no rebuild.

---

## Pre-pass: current task completed first

Before the refinement, the in-flight task (multi-scope graph + visual fixes) was
finished and committed:

- `2f918d9` — multi-scope graph_service (atlas/global/projects/obsidian), CLI
  `--scope`, gateway `?scope=`, per-scope client cache, live tabs, secondary 3D
  minimap, brighter electricity, storm made visible. Graphify **was** the task.
- App was stable (tsc + build clean, all tabs render) before starting the pass.

---

## What was done (refinement pass)

Executed priorities **P1–P4** in order. P5 deferred (per "only if stable" + the
directive's "defer full storm/lightning").

### Architecture (separation of concerns)
- **`src/graph/GraphVisualConfig.ts`** (new) — single source of truth for
  category colors (exact spec hues), palette fallback, link/particle colors,
  node sizing, bloom + force constants, text tokens.
- **`src/graph/GraphFog.ts`** (new) — `attachFog(scene, nodes, getSimNodes)`
  world-anchored fog, self-contained, returns a cleanup fn.

### P1 — Minimap
- Matches the **main container aspect ratio** (was fixed 168×116).
- **Viewport rectangle overlay** (CSS div) projecting the main camera target into
  minimap space; size scales with camera distance. Verified: shrinks on zoom.
- **Click-to-navigate**: minimap click unprojects to a world point and translates
  the main camera to look at it.
- Throttled to **~10fps** (was ~15fps).
- Still a true secondary 3D viewport (renders the main scene from a fitted camera).

### P2 — Cloud/Fog (replaced, not re-enabled)
- Removed the screen-space Lightning/CSS storm (the viewport-fixed cloud).
- New fog = additive **THREE.Sprites at cluster centroids inside the graph scene**
  → moves/parallaxes with the camera (world-anchored).
- Density-driven, smoothed opacity (0.04–0.10), per-cluster scale **capped** so a
  wide cluster doesn't become a dome. Recomputes centroids **1×/sec**, not per
  frame. Toggled by **Storm Activity**.

### P3 — Interaction
- Switched to **OrbitControls** with damping (`dampingFactor` 0.12) — smoother,
  less "weird" than the default trackball.
- Force tuning via config: `d3VelocityDecay` 0.4, `d3AlphaDecay` 0.02,
  `cooldownTime` 12s → responsive drag, settles without violent spring-back.
- Node-drag vs orbit vs click are handled by 3d-force-graph's built-in pointer
  routing (a full custom IDLE/DRAG/PAN state machine was NOT introduced — see
  Known issues).

### P4 — Text contrast
- Centralized text tokens (`TEXT.primary/secondary/ghost`).
- Active tab → full ivory + bottom-border glow; live tab → secondary; disabled
  tab → ghost (keeps tooltip). Bumped legend/count-chip/hint/updated rows from
  the dim `--l2-fg-3` to `#9BA0AD` and nudged tiny font sizes up.

### Category colors (semantic, unchanged-hue rule honored)
Phase `#4F8BFF`, Roadmap/State `#46F0E0`, Research `#00CED1`, Prep/Decision
`#A17BFF`, Report `#FFD700`, Folder/root `#B08A57`, note fallback neutral.
Unknown folder-slug kinds → deterministic palette (stable, not heat).

---

## Files changed
- `services/web-ui-react/src/graph/GraphVisualConfig.ts` (new)
- `services/web-ui-react/src/graph/GraphFog.ts` (new)
- `services/web-ui-react/src/routes/Graph.tsx` (config wiring, minimap, fog effect, physics, contrast)
- `services/web-ui-react/src/components/Lightning.tsx` — now **unused** (left in tree; not deleted)

**Graphify touched:** Yes (this pass is entirely Graphify).

---

## Verification
- `npx tsc --noEmit` — clean.
- `npx vite build` — clean (Graph chunk code-split, main bundle unchanged).
- Live (Playwright, gateway + vite running):
  - Global/Projects/Obsidian tabs load real data.
  - Minimap matches aspect; viewport rect shrinks + tracks on zoom.
  - Fog is world-anchored, contained per-cluster, subtle.
  - Contrast improved on tabs/legend/stats.

---

## Known issues / unfinished
- **P5 (edge activity) deferred** — existing directional particles are the
  foundation; no new pulses/arcs added yet (kept stable per directive).
- **Interaction state machine** not formally extracted — relying on
  3d-force-graph's built-in drag/orbit routing. If click-vs-drag still feels off
  in use, a dedicated `GraphInteraction.ts` state machine is the next step.
- **Minimap component not extracted** to `GraphMinimap.tsx` (kept inline to limit
  risk); fog + config were extracted. Further extraction deferred.
- `Lightning.tsx` is now dead code; safe to remove in a later tidy.
- Fog intensity is density-driven (a stand-in for real activity/consultation
  scores, which require runtime wiring — out of scope here).

---

## Stability assessment
**STABLE.** Type-checks, builds, all scopes render, no console errors observed,
effects are throttled/capped and config-driven. Safe to continue from here.

## Next steps (future phase)
1. Extract `GraphMinimap.tsx` + `GraphInteraction.ts` if interaction needs a
   formal state machine.
2. P5 subtle edge pulses (1–2 particles, shimmer on recent paths).
3. Wire fog/glow intensity to real activity (access counts) once available.
4. Then the larger GAP-ANALYSIS items (runtime entities, Agent Context tab).
