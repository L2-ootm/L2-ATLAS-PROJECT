# UX-VISUAL-SPEC — the reactive plasma layer

The brand and structure are landing. This document specifies the **reactive, material, and motion
layer** that makes the cockpit feel *alive and plasmatic* rather than a static dark theme: a more
present topographic field, liquid-glass that lets the topo glow bleed through fluidly, and
**inputs whose terrain reacts to typing**. It is the application of the L2 EFFECTS doctrine
(`L2-Systems-Design-System/EFFECTS.md`, `topo_plasma.css`) to the ATLAS cockpit, using the
**already-ported engine** (`src/topo/topoEngine.ts`) whose API exposes exactly the hooks we need.

> Engine API already in the app: `setHover(x,y,color)`, `endHover()`, `pushTrail(x,y,color)`,
> `sonarPing(x,y,color)`, `clearTrail()`, `destroy()`. Nothing new to port — this is wiring + craft.

---

## 1. The Five Laws (carried verbatim from L2 EFFECTS)

1. **Effects carry information, or they are deleted.** A glow = *something is here, of this kind.*
   A ripple = *a thing happened.* If you can't name the signal, it's decoration — and decoration is debt.
2. **Presence creates topology.** Cursor bulges the field; **typing = authorship** — the caret drags
   a comet of glow behind the letters (*"you are making this"*).
3. **Brightness is recency/intensity.** Newest source is brightest; older sources decay. Light has a
   head and a tail. Heat maps to time.
4. **Color is semantic context — never theme, never position.** `good/info/warn/bad/brand/atlas`.
   A field validating green; an error pulsing crimson; an AI action blooming violet. The terrain is
   a live legend.
5. **Nothing stays lit without cause; the system cools.** Every effect decays to the resting lattice.
   Stillness is the truthful default; light is *earned*, moment to moment.

Non-negotiable constraints: **one shared rAF per field, stops itself when idle** (`raf=null`);
**contrast first** — labels on terrain use `mix-blend-mode: difference`, readable content sits on
liquid glass above the field; **one material (glow), one curve `cubic-bezier(0.22,1,0.36,1)`.**

---

## 2. Where the topo lives (presence map)

Today the topo is a single dim ambient background. Make it **layered and contextual** — present
where the operator acts, recessed where they read:

| Surface | Topo treatment |
|---|---|
| App background (all pages) | Ambient field, dim (`glowOpacity ~.32`, `opacity .5`), parallax on scroll (shipped) |
| Hero / empty stages | Brighter local field + starfield; the focal object (emblem/seal) sits in a liquid-glass vitrine so the glow halos it |
| **Inputs (search, intent, ⌘K, wiki edit)** | **Dedicated per-input topo field**; typing pushes a glow comet (see §4) |
| Live run timeline | Each arriving event fires a `sonarPing` in the ambient field at the row's y |
| Stat/nav hover | `setHover` blooms the field in the cell's semantic color (info/good/brand) |
| Status surfaces | Field glow color tracks state: gateway online = `good`, offline = `bad` |

The terrain becomes the connective tissue: the same living surface under brand, data, and input —
glowing in the meaning of whatever is touched.

---

## 3. Plasmatic glassmorphism (the material)

"Liquid glass" today is a flat translucent panel. Upgrade it to a **plasma-lit glass** so the topo
glow underneath reads as fluid light refracted through the slab — without hurting legibility.

**`GlassPanel` / `PlasmaGlass` recipe:**
- **Base:** `background: linear-gradient(180deg, rgba(21,24,32,.62), rgba(11,13,18,.62))` over the
  field; `backdrop-filter: blur(14px) saturate(1.35)`. The blur lets the topo glow diffuse through
  as soft plasma rather than a hard line.
- **Specular top edge:** a 1px `linear-gradient(90deg, transparent, ivory .08, transparent)` inner
  light + an optional bronze accent line for brand surfaces (shipped via `accent`).
- **Inner light / lift:** `box-shadow: inset 0 1px 0 rgba(237,234,224,.06), 0 1px 0 rgba(0,0,0,.5)`.
  Tint shadows to the page mood (navy-black), never generic black blur.
- **Glow bleed:** when the panel sits over an active topo region, a soft radial of the semantic color
  is allowed to bleed into the panel's lower edge (very low alpha) — the plasma "pushing up" through
  the glass. Implemented as a masked pseudo-layer driven by the field's current `data-topo` color.
- **Specular sweep (rare, earned):** a one-shot diagonal light sweep (`@keyframes atlas-sweep`,
  already defined) on a freshly-committed action (mission created, run launched) — filmic, not idle.
- **Displacement (optional, hero only):** a subtle SVG `feTurbulence` displacement on the hero glass
  for a liquid edge. Behind a perf budget; never on list rows.

Rule: **content that must be read sits on glass above the field; labels that ride the bare terrain
use `mix-blend-mode: difference`.** The plasma never wins against the words.

---

## 4. Typing-reactive inputs — `TopoInput` (the headline UX)

A first-class component: an input whose own topographic field reacts to authorship. This is L2 Law 2
made literal and is directly supported by the ported engine.

**Construction.**
- A small per-input `createTopoField({ host, cellSize ~10–14, restingOpacity .08, glowOpacity .4 })`
  behind a transparent `<input>/<textarea>` on a liquid-glass slab. Hundreds of cells, not thousands.
- On each keystroke: compute the caret x (canvas measureText of the value up to the caret) and call
  `pushTrail(caretX, midY, ctxColor)`. The engine decays the comet — brightest at the newest letter,
  fading over prior text (Law 3). On `clear`/submit: `clearTrail()`.
- On blur/idle: the field cools to rest and the rAF stops itself (Law 5; `raf=null`).
- **Validation tint (Law 4):** `ctxColor` *is* the live validation state — `info/neutral` while
  composing, snapping to `good` when valid, `bad` on error. The terrain becomes inline validation;
  no separate error text for the common case. AI-bound fields (mission intent, ⌘K) bloom `violet`
  (AI authorship / model decisions).
- **Idle erosion:** a focused-but-untouched field slowly flattens; resuming re-ignites it.

**Used by:** mission **intent** + **title** (create modal), Missions **filter/search**, **Codex FTS
search**, **Wiki page editor**, and the **⌘K command palette** input. Each declares its semantic color.

**Performance & a11y.** One rAF per focused field; killed on blur. `prefers-reduced-motion` → the
field renders a static resting lattice and validation falls back to a conventional inline message.
Never block input; the canvas is decorative and `aria-hidden`, the real `<input>` carries semantics.

---

## 5. Motion profile (filmic, restrained — dark-luxe)

- **One curve** everywhere: `cubic-bezier(0.22,1,0.36,1)`. Durations 80/150/250/400ms.
- **Reveals:** route/section enter = per-token **blur-in** on headings (`atlas-blur-in`), staggered.
- **Live:** running run = breathing **glow/electric-border**; each audit event = **sonar ping** +
  blur-in row. Gateway status dot pulses only while `checking`.
- **Confirmation:** primary/destructive actions = **click-spark** at the pointer + a one-shot
  specular sweep on the affected glass.
- **Ambient:** starfield twinkle (slow), astrolabe rotation (very slow), topo parallax on scroll.
- **Cooling:** everything decays to rest. No permanently-animated element without a live cause.
- **Reduced motion:** all of the above degrade to static; the field renders one resting frame.

---

## 6. Effect → surface assignment (acceptance matrix)

| Effect | Surface | Signal it carries |
|---|---|---|
| Typing comet (`pushTrail`) | every TopoInput | "you are authoring this" + validation state |
| Hover bloom (`setHover`) | stat rail, nav, rows | "this is here, of this kind" |
| Sonar ping (`sonarPing`) | run timeline, on event | "a thing just happened" |
| Glow/electric border | live run stage, primary focus | "this is live / this is the action" |
| Plasma glass bleed | elevated reading/data slabs | depth; the field is alive beneath |
| Faulty-terminal scanlines | run/audit log only, low opacity | "raw machine telemetry" |
| Click-spark + sweep | committed actions | "this is done" |
| Gradual-blur edges | long scroll content (Codex) | depth at the boundary |

Guardrails: **one focal effect per surface**; effects carry information or are cut; honor reduced
motion; never reduce legibility; 2px radii; bronze = brand filigree only; violet/cyan/celestial =
system/telemetry.

---

## 7. Build order (folds into the page waves)

1. **`PlasmaGlass`** upgrade to the shared panel (specular edge, inner light, glow bleed). Cheap,
   global lift — do first.
2. **`TopoInput`** component + `useTopoField` hook; adopt in the Missions filter and ⌘K first
   (highest-visibility), then intent/editor/search.
3. **`useRunStream`** + sonar-ping wiring on the Run timeline (with `HARNESS-WIRING §3`).
4. **GlowBorder / BlurReveal / GradualBlur / ClickSpark** React ports from the captured research
   (`.planning/research/ui-effects/`), applied per the matrix above.
5. Verify: 60fps on a mid laptop, rAF stops on idle/blur, reduced-motion static, contrast preserved.

This layer is what turns "a very nice dark theme" into "a living instrument."
