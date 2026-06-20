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

## Performance — graph load latency (known, non-critical)

The first time a scope opens there's a visible delay before the graph appears.
Documented here per operator request; not fixed yet.

**Cause (in order of cost):**
1. **Gateway cold scan.** `GET /v1/graph?scope=` dispatches the `atlas graph
   build --scope …` CLI, which spawns a Python process and walks the markdown
   tree (global ≈ 790 nodes is the heaviest). This is the dominant cost. It only
   happens once per scope per session — `api.getGraph()` caches the result
   client-side, so re-opening a tab is instant (REBUILD forces a rescan).
2. **Graph JS chunk.** The lazy `/graph` route pulls `3d-force-graph` + `three`
   + bloom (~1.37 MB / 370 KB gzip). First navigation parses this.
3. **First-frame WebGL + force warmup.** Renderer/bloom init plus the d3 force
   sim settling before `zoomToFit`.

**Workaround options (when we pick this up):**
- **Gateway-side cache / persist.** Cache the built `{nodes,links}` per scope on
  the gateway with a TTL (or persist to disk keyed by a content hash of the
  source tree), so the CLI scan is skipped on warm hits. Biggest win.
- **Background prefetch.** Kick off `getGraph('global')` on app/dashboard mount
  so the default scope is already cached by the time the user opens Graphify.
- **Incremental / cheaper scan.** Cap or memoize the markdown walk; skip
  unchanged files via mtime.
- The chunk is already code-split; could be `modulepreload`ed from the nav.

## Stability assessment
**STABLE.** Type-checks, builds, all scopes render, no console errors observed,
effects are throttled/capped and config-driven. Safe to continue from here.

## Follow-up pass (2026-06-20) — storm/atmosphere iteration

Operator review drove a second visual iteration on top of the stabilize pass:

- **Storm clouds enhanced, then removed.** Tried (a) brighter breathing fog
  domes → read as "silly" glowing orbs; (b) procedural multi-puff smoke at
  cluster centroids → read as "out of place" floating blobs when zoomed in.
  Conclusion: the per-cluster sprite-fog approach doesn't land. **`GraphFog.ts`
  deleted.** Storm Activity now toggles lightning only.
- **Lightning added** (`GraphLightning.ts`, kept). Bright additive jagged bolts +
  endpoint/midpoint discharge flashes, struck between nearby nodes inside the
  densest clusters, flashing/decaying ~360 ms; bloom makes them glow. Config-
  driven (`LIGHTNING` block). Confirmed firing live.
- **Ambient auto-orbit** — OrbitControls `autoRotate` (speed `0.32`) around the
  fitted center; user drag overrides and it resumes (`FORCE.autoRotateSpeed`).
- **Minimap follows rotation** — root cause: auto-rotate moves the camera, not
  the nodes, but the minimap rendered from a fixed front camera. Fixed: aim the
  minimap camera along the main camera's view direction, pulled back to fit.

## Deferred — bring back to the graph later (operator-requested backlog)

Explicitly parked for a future graph pass; do NOT treat as lost:

- **Atmosphere / smoke, refined.** Re-approach so it reads as real volumetric
  fog, not sprite blobs. Candidate techniques: screen-space raymarched fog,
  `THREE.FogExp2` scene fog, a shader nebula plane behind the graph, or a true
  particle/volumetric system — anchored to the graph, never floating.
- **Full "storm"** — coordinated storm state (clouds + lightning + density swell)
  that escalates with activity, not just isolated bolts.
- **Heat-map cloud overlay** — an *activity* heat layer (consultation/access
  density) as a toggle, distinct from and never replacing the semantic category
  colors (category hue rule still holds).
- "…and a lot more" (operator) — living-graph visuals from GAP-ANALYSIS:
  node pulse/breathe, curved/dendrite links, synaptic flashes, activity-driven
  intensity once the runtime graph engine exists.

## Deferred — Console page

- **Console polish + full wiring** parked for a future time (operator). Only the
  **free-mode close-window bug** was fixed this pass (pointer-capture on the
  header swallowed the X click; the close button now stops `pointerdown`/
  `mousedown` from reaching the drag handler).

## Next steps (future phase)
1. Extract `GraphMinimap.tsx` + `GraphInteraction.ts` if interaction needs a
   formal state machine.
2. P5 subtle edge pulses (1–2 particles, shimmer on recent paths).
3. Wire fog/glow intensity to real activity (access counts) once available.
4. Then the larger GAP-ANALYSIS items (runtime entities, Agent Context tab).
