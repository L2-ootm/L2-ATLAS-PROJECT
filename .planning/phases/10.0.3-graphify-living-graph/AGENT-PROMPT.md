# Graphify Refinement — Agent Prompt

**Use this prompt to continue work on the Graphify knowledge graph view.**

---

## Current Task

Stabilize the ATLAS Graphify knowledge graph view. The graph renders real Obsidian data — not mock. The existing connections, clusters, categories, and document relationships are real and must be preserved. Your job is to fix known issues, improve polish, and prepare the architecture for future visual effects.

Do NOT redesign the page. Do NOT rebuild the graph system. Do NOT start a parallel implementation.

## Reference Documents (Read Before Starting)

- `.planning/phases/10.0.3-graphify-living-graph/GAP-ANALYSIS.md` — full gap inventory (15 gaps identified)
- `.planning/phases/10.0.3-graphify-living-graph/SPEC.md` — design specification (entity model, storage, visuals)
- `.planning/phases/10.0.3-graphify-living-graph/CONTEXT.md` — system context (related systems, visual language, files)
- `.planning/phases/10.0.3-graphify-living-graph/PHASE.md` — phase plan (8 work packages, dependencies)

## Branch

Work on the current branch (`feat/cockpit-p3-glass-p4`). Do not create a new branch for this refinement pass.

---

## Current Implementation Context

### Key Files

| File | Lines | Role |
|------|-------|------|
| `services/web-ui-react/src/routes/Graph.tsx` | 943 | Main graph view. 3d-force-graph (Three.js), UnrealBloom post-processing, electricity particles, Storm Activity lightning overlay, minimap (secondary WebGL renderer, 168x116px, ~15fps), node search, inspector panel, 4 scope tabs (Global/Projects/Obsidian/Agent Context[LOCKED]), graph statistics, zoom controls. |
| `services/web-ui-react/src/lib/api.ts:260-304` | 44 | API client. `getGraph(scope, force)` with per-scope session cache. Types: GraphNode, GraphLink, GraphData, GraphScope. |
| `services/web-ui-react/src/topo/topoEngine.ts` | — | SVG contour renderer (marching squares). Separate system from graph. Used as background in TopoField, GlassTopo, TopoInput, RunDetail. NOT connected to graph visualization. |
| `services/web-ui-react/src/components/Lightning.tsx` | — | WebGL FBM noise shader. Full-screen effect. Used as "Storm Activity" toggle overlay on graph. This is the disabled "cloud/fog" — it renders in screen space, not world space. |
| `services/web-ui-react/src/lib/glass.ts` | — | SVG feDisplacementMap refraction. Glass panels with frosted backdrop. |
| `services/web-ui-react/src/components/GlassTopo.tsx` | — | Frosted glass over topo field. Used on hero surfaces. |
| `services/web-ui-react/src/lib/tokens.css` | — | Design tokens: ATLAS palette, void tones, foreground hierarchy, topo glow colors, typography (Inter, Cinzel, Cormorant Garamond, JetBrains Mono), motion curves. |
| `services/web-ui-react/package.json` | — | Deps: three ^0.184.0, 3d-force-graph ^1.80.0, three-spritetext ^1.10.0, ogl ^1.0.11 (installed, unused), React 19, Vite 8, Tailwind v4. |

### Architecture Notes

- The graph is a **3D force-directed layout** rendered via `3d-force-graph` (Three.js wrapper).
- The minimap is a **secondary WebGL renderer** — same scene, different camera, compressed view. It does NOT use 2D canvas projection.
- The `Lightning` component is a **full-screen shader** — it does not have access to Three.js world coordinates. This is why it felt "fixed to the viewport."
- `ogl` is installed but never imported. It could be used for a lighter 2D WebGL graph if needed.
- The topo engine is a separate SVG system — it does not interact with the 3D graph.

---

## Visual Direction (Do Not Change)

The visual language is correct. Preserve it:

- **Canvas:** dark navy / black (`--l2-void-page: #0B0D12`)
- **Background:** bronze topographic contours (topo engine)
- **Nodes:** category-based coloring (see below)
- **Edges:** glowing, color-coded by link type
- **Bloom:** UnrealBloom post-processing (strength 0.72, threshold 0.5, radius 0.3)
- **Shell:** ATLAS Operator Cockpit — integrated, not standalone
- **Left panel:** controls, legend, search, toggles
- **Stats panel:** node/edge/community counts
- **Minimap:** bottom-right, compressed graph view

### Category Color Rules (Semantics — Never Change Hue)

| Category | Hue | CSS/Visual |
|----------|-----|------------|
| Phase | soft blue / indigo | `#4F8BFF` (atlas-celestial) |
| Roadmap / State | cyan | `#46F0E0` (atlas-cyan) |
| Research | teal | `#00CED1` |
| Prep | violet / purple | `#A17BFF` (atlas-violet) |
| Report | yellow / gold | `#FFD700` |
| Folder | bronze / amber | `#B08A57` (atlas-bronze) |
| Decision | violet (matches prep) | `#A17BFF` |
| Note / fallback | current neutral/accent | `--l2-fg-2` or atlas-celestial |

Activity intensity is shown through: brightness, glow intensity, halo size, node scale, pulse speed, edge brightness, edge pulse density, fog density, activity rings.

**Never use heat-map coloring.** Never shift the base hue based on activity.

---

## Refinement Priorities (Execute In Order)

Only proceed to the next item if the current item is stable. Do not rush through all items.

### Priority 1: Minimap Fix

The minimap exists but does not correctly represent the main graph layout/viewport.

**Current state:** Secondary WebGL renderer at 168x116px, ~15fps. Renders same scene from far-back camera. No viewport overlay. Aspect ratio may not match main graph.

**Requirements:**
- Use the same graph layout/positions as the main graph (already does — don't break this)
- Show the full graph in a compressed view
- Reflect the real global shape of the graph
- Show current viewport/camera region as a visible overlay rectangle
- Update when user pans, zooms, or orbits
- Optionally reflect selected/hovered nodes (highlight in minimap)
- Keep lightweight — reduce render frequency to 10fps max
- Do NOT render an unrelated decorative graph

**Approach:** Fix the existing secondary WebGL renderer:
1. Add a viewport rectangle overlay (project main camera frustum onto minimap camera)
2. Match minimap aspect ratio to main graph container
3. Sync camera position bidirectionally (minimap click → navigate main graph)
4. Reduce render frequency via throttled requestAnimationFrame (10fps)
5. Add viewport rectangle as a Three.js LineSegments or CSS overlay

If WebGL minimap proves too complex after 30min of effort, fall back to 2D canvas projection of node positions (cheaper, more accurate, different approach).

### Priority 2: Cloud/Fog Foundation

The old cloud/fog was disabled because it looked bad. It was screen-fixed (viewport-anchored) instead of world-anchored.

**Do NOT re-enable the Lightning component as fog.** It is a full-screen shader with no world-coordinate access.

**Requirements:**
- Fog must be anchored to graph/world coordinates, not screen coordinates
- Fog moves with the graph when camera moves
- Fog belongs to active clusters or hot graph regions
- Fog is translucent, subtle, and branded (ATLAS palette)
- Feels like "knowledge mist / consultation density," not realistic weather
- No flicker, jitter, heavy volumetric effects, or excessive opacity
- Toggleable with the existing "Storm Activity" control
- Drive fog intensity through stable/smoothed activity scores (if available) or static cluster density

**Approach (try in order):**
1. **Three.js sprites/particles inside ForceGraph3D scene** — inherently world-anchored, moves with camera. Create a Points object with additive blending, positioned at cluster centroids. Color by cluster category. Opacity proportional to node density in cluster. This is the preferred approach.
2. **Screen-space shader with camera-uniform injection** — pass Three.js camera position/projection to Lightning shader as uniforms. More complex, but keeps the existing shader.
3. If both fail, use a simple CSS radial-gradient overlay anchored to the graph container (least accurate, but functional).

**Parameters (starting point):**
- Particle count: 50-100 per cluster (not thousands)
- Particle size: 15-40px (screen-space size via `sizeAttenuation: true`)
- Opacity: 0.05-0.15 (very subtle)
- Color: cluster category hue at low saturation
- Blend mode: AdditiveBlending
- Update frequency: 1x per second (not per-frame)

### Priority 3: Interaction Refinement

Current drag/orbit/click behavior feels weird. Sources: orbit controls fighting node drag, clicks becoming drags, violent spring-back.

**State Machine:**

```
IDLE ──pointer down──→ CHECK_TARGET
  │                      │
  │                   on node → DRAG_NODE
  │                   on empty → PAN
  │
DRAG_NODE ──pointer up──→ SETTLE ──200ms──→ IDLE
  │                       │
  │                    if <5px movement + <200ms → CLICK (select node)
  │                    if >5px movement → DRAG_COMPLETE (no click)
  │
PAN ──pointer up──→ IDLE
  │
  └──right-click drag / two-finger──→ ORBIT
```

**Implementation:**
- Separate pointer event handlers for each state
- On DRAG_NODE: disable OrbitControls, stabilize force simulation (increase `damping`, reduce `alphaDecay`)
- On DRAG_NODE release: smoothly restore OrbitControls, let simulation settle naturally (don't reset positions)
- On CLICK: select node, open inspector, fly camera to node
- On PAN: orbit camera (default OrbitControls behavior)
- Prevent: orbit during DRAG_NODE, click after DRAG_NODE (>5px or >200ms), pan during HOVER
- Drag feel: responsive but weighted — node follows pointer with slight lag (0.1-0.2 lerp)
- Settlement: after release, simulation warms up gradually (alpha: 0.3 → 0 over 2s), no violent spring-back

**Key config:**
```typescript
// ForceGraph config for stable drag
damping: 0.1,          // higher = less jitter during drag
alphaDecay: 0.02,      // lower = slower settlement after drag
alphaMin: 0.001,       // stop simulation when settled
velocityDecay: 0.4,    // higher = less overshoot
```

### Priority 4: Text Contrast & Readability

Audit all text elements in the graph view. Fix readability without breaking the dark premium aesthetic.

**Elements to audit:**
- Left panel: section headers, legend labels, toggle labels, search placeholder
- Graph statistics panel: numbers, labels
- Top tabs: active/inactive/disabled states
- Minimap: any text (should be minimal)
- Node inspector: kind, label, path, neighbor list
- Interaction hint (bottom center)
- Search results
- Tooltip text on nodes

**Rules:**
- Keep the premium dark ATLAS look — do NOT make everything bright white
- Primary text: `--l2-fg-1: #EDEAE0` (ivory) on dark backgrounds
- Secondary text: `--l2-fg-2: #9BA0AD` (muted)
- Disabled text: `--l2-fg-3: #565C6B` (ghost)
- Minimum contrast ratio: 4.5:1 for body text, 3:1 for large text
- Active tab: full ivory + bottom border glow
- Disabled tab: ghost color + reduced opacity + "coming soon" tooltip
- Legend labels: match their category color for the dot, use fg-1 for text

### Priority 5: Subtle Edge Activity Foundations

Only if Priorities 1-4 are stable. Do NOT implement full lightning/storm effects.

**Permitted now:**
- Subtle edge brightness variation (brighter = more recent reference)
- Tiny traveling signal particles on non-contains edges (1-2 particles, slow speed)
- Edge shimmer on recently active paths (opacity oscillation)
- Node pulse intensity variation (if activity data available, otherwise skip)

**NOT permitted now:**
- Full lightning arcs
- Storm escalation
- Dense particle systems
- Flash effects

**Edge particle config (if implementing):**
```typescript
linkDirectionalParticles: 1-2,      // not 3 (current value)
linkDirectionalParticleWidth: 1.5,  // thinner
linkDirectionalParticleSpeed: 0.005, // slower
linkDirectionalParticleColor: match link color at 60% opacity
```

### Future Storm Behavior (Architecture Only — Do Not Implement)

Prepare the architecture so later phases can add:
- Lightning arcs inside hot clusters
- Edge signal bursts
- Storm escalation around heavily queried clusters
- Flashes around highly consulted nodes
- Denser local fog around frequently used knowledge regions

This means: keep visual effects config-driven, not hardcoded. Store effect parameters in a config object that can be extended later.

---

## Architecture Guidelines

### Separation of Concerns

Separate these concerns in the code. Currently most are tangled inside Graph.tsx (943 lines):

1. **Graph data state** — nodes, links, scope, loading, error
2. **Graph layout/physics state** — force simulation config, alpha, cooling
3. **Camera/viewport state** — position, zoom, orbit target
4. **Interaction state** — IDLE/HOVER/DRAG_NODE/PAN/ORBIT/CLICK
5. **Minimap projection logic** — camera sync, viewport overlay, click navigation
6. **Visual effects state** — bloom params, fog params, particle params, pulse state
7. **Category styling config** — color map, size map, label map (centralized, not scattered)
8. **Activity styling config** — brightness mapping, glow mapping, fog intensity mapping

### File Extraction Targets

Keep Graph.tsx as a single file for now, but extract these into separate modules:

- `src/graph/GraphVisualConfig.ts` — category colors, activity mapping, effect parameters, all constants
- `src/graph/GraphMinimap.tsx` — minimap component (currently inline)
- `src/graph/GraphFog.tsx` — fog/storm component (new)
- `src/graph/GraphInteraction.ts` — interaction state machine logic
- `src/graph/GraphEffects.ts` — bloom, particle, pulse effect configs

### Performance Rules

The graph may grow (real Obsidian data). Avoid:
- Expensive per-frame React state updates (use refs for animation state)
- Unnecessary rerenders (memoize components, use React.memo)
- Recomputing layout too often (let force simulation cool naturally)
- Particle/fog systems that scale badly (cap particle count, throttle updates)
- Minimap recalculation every frame (throttle to 10fps)

Prefer:
- `useRef` for animation state (not `useState`)
- `requestAnimationFrame` for visual updates (not React re-renders)
- Canvas/WebGL layers where appropriate (minimap could be 2D canvas)
- Throttled/smoothed updates (don't react to every mouse event)
- Config-driven visual effects (centralized params, not scattered hardcoded values)

### Do NOT Over-Refactor

The goal is polish, not rewrite. If the current implementation is tangled, separate concerns enough to support future work — but don't rewrite Graph.tsx from scratch. Incremental extraction is fine. Full rewrites are not.

---

## Verification

After completing each priority, verify:

1. **Type check:** `cd services/web-ui-react && npx tsc --noEmit`
2. **Build:** `cd services/web-ui-react && npx vite build`
3. **Manual visual checks:**
   - Category colors match the spec table above
   - Minimap viewport overlay tracks camera position
   - Fog moves with graph (not fixed to screen)
   - Drag/orbit/click don't conflict
   - Text is readable at all sizes
4. **Performance:** Graph renders at 60fps with current data volume. No jank on drag/orbit.
5. **Playwright screenshots:** Capture before/after for each priority item.

## Checkpoint

After completing the current task (or hitting a blocker), write a checkpoint to:

```
.planning/phases/10.0.3-graphify-living-graph/CHECKPOINT.md
```

Format:
```markdown
# Checkpoint — [date]

## What Was Done
- [list of changes]

## Files Changed
- [file paths with brief description of change]

## Graphify Touched
Yes/No — if yes, what was changed

## Known Issues
- [any bugs, regressions, or incomplete items]

## Stability Assessment
Stable / Unstable — do NOT proceed to next priority if unstable

## Next Steps
- [what should happen next]
```

Do NOT begin the next priority item if stability assessment is "Unstable."
