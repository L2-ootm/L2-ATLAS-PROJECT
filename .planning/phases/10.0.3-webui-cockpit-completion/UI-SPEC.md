# UI-SPEC — ATLAS Identity & Cockpit Redesign (Phase 10.0.3)

> Design contract. The cockpit is **Svelte 5 + SvelteKit + Tailwind v4 + custom `--l2-*` /
> `--atlas-*` tokens**, dark-only, WebView2-safe (no APIs Edge/Chromium WebView2 lacks).
> Status: **living** — folds in operator UI references; brand direction approved at gate
> 2026-06-16 (palette locked, all 3 logo variants, proceed).

## 1. Concept — "ATLAS bears the world"

The titan carries the operational weight — missions, audit, autonomy — so the operator doesn't.
This is the L2 black-box thesis (*"the machine carries complexity, the human receives clarity"*)
made literal. The cockpit's **topographic terrain is the world ATLAS bears**; the logo's globe is
a contour sphere drawn in that same language. Surface calm, depth alive. The system states; it
never asks. It must look like a running system that costs a billion dollars.

## 2. Visual register & acceptance bar

Register: **product-ui** on the L2 **Topographic** system (primary), Dark Prism atmosphere as
support. Blade Runner 2049 / datacenter, never a SaaS landing page.

**Acceptance bar (operator-set, L2 minimum):** the cockpit must reach the motion/material quality
of the React Bits reference set. Captured with source code in `.planning/research/ui-effects/`:

| Reference | Diegetic ATLAS use (signal, not decoration) | Port |
|---|---|---|
| border-glow / electric-border | **Live/streaming** surfaces (active run, SSE), primary-action focus | CSS conic-gradient border + SVG turbulence; `use:glowBorder` action |
| fluid-glass | Every elevated panel (the liquid-glass slab) | `GlassPanel` upgrade: specular top, inner light, saturate; optional SVG displacement |
| gradual-blur | Depth at scroll edges, hero base, long-list fades | progressive `backdrop-filter` mask stack (`GradualBlur.svelte`) |
| blur-text | Heading reveal on route/section enter | per-token blur→sharp transition (`BlurReveal.svelte`), reduced-motion safe |
| click-spark | Confirmation on primary/destructive actions | canvas spark burst `use:clickSpark` |
| soft-aurora / color-bends | Dashboard/hero ambient brand glow (bronze+celestial) | OGL/GLSL background, low opacity, behind content |
| side-rays / laser-flow | Hero / empty-state focal accent (sparing) | OGL/GLSL; one per surface max |
| line-waves / dot-field | Alt ambient substrate for specific surfaces (e.g. models) | OGL/GLSL or canvas |
| faulty-terminal | Run/audit stream texture (CRT scanline vibe) — restrained | GLSL shader behind the event log |
| metallic-paint | The brand emblem / wordmark hero treatment | WebGL image shader on the generated emblem |
| pixel-card | Mission/model card hover dissolve (optional accent) | canvas pixel grid on hover |

**Guardrails:** one focal effect per surface; effects carry information or are cut; honor
`prefers-reduced-motion` (drop to static); never let atmosphere hurt readability (difference-blend
labels on terrain, glass elevation for data); 2px radii default; one motion curve
`cubic-bezier(0.22,1,0.36,1)`.

`ogl` and `three` are framework-agnostic — GLSL shaders from the references port **verbatim** into
Svelte `onMount` hosts. framer-motion/gsap → Svelte transitions or `motion-one`.

## 3. Tokens

L2 core unchanged (`--l2-void-*`, `--l2-electric-violet` #7F00FF, `--l2-cyber-blue` #00F0FF,
status colors, spacing/radii/motion). **ATLAS signature added** (`tokens.css`):
`--atlas-bronze` #E0A94E, `--atlas-bronze-deep` #9C6B2E, `--atlas-celestial` #4A5DBF,
`--atlas-celestial-deep` #1E2660, plus `-soft/-glow` variants and `--l2-topo-glow-atlas`.

**Role law (non-negotiable):** **bronze = identity/brand** (logo, hero, wordmark accent) ·
**violet+cyan = system/telemetry/interactive** (CTAs, focus, active, live) · **status colors
unchanged**. Warm titan bears the cool machine-world.

## 4. Typography

Inter (body) · JetBrains Mono (all data/labels, `tabular-nums`, uppercase 0.2em labels) ·
Orbitron (display/wordmark). Wordmark: `ATL` + bronze `A` + `S`, 0.26em tracking. Data is mono or
it's wrong. Labels are the system speaking, never a question.

## 5. Logo system (shipped)

`AtlasMark.svelte` — borne / axis / bracket × color / currentColor. `AtlasLockup.svelte` —
ATLAS-forward + "BY L2 SYSTEMS" endorsement. `favicon.svg` (fixed 0-byte break). Illustrative
emblem: operator-generated from `output/brand/atlas-emblem-prompt.md`, cut + integrated for
dashboard/splash, metallic-paint treatment.

## 6. Shell (shipped, evolving)

Living terrain (`TopoField` + `topoEngine.ts`) behind everything; semantic glow by `data-topo`;
scroll parallax; reduced-motion safe. Sidebar: ATLAS mark+wordmark header, mono nav, cyan active
glow-rail, gateway status dot, L2 endorsement. Next: glowBorder on active nav, blur-reveal header.

## 7. Components

Custom HUD/topographic surfaces in Svelte (GlassPanel, HudLabel, StatusBadge, LiveBadge, rows,
timeline). `shadcn-svelte`/bits-ui for accessible primitives only (dialog, dropdown, tabs,
tooltip, command palette). New shared: `GlassPanel` (fluid upgrade), `GlowBorder`, `GradualBlur`,
`BlurReveal`, `clickSpark` action, `EmptyState` / `LoadingState` / `ErrorState`.

## 8. Per-page intents (the wave)

- **dashboard (new, home)** — operator HUD: active mission, recent runs, integration health,
  latest artifacts/wiki, system status. Bronze/celestial aurora hero + emblem. Highest polish.
- **missions** (list + detail) — mission table → fluid-glass rows, status badges, create modal
  with click-spark confirm; detail = run list + lifecycle.
- **runs** (list + detail) — detail is the showpiece: SSE audit stream over a restrained
  faulty-terminal texture, electric/glow border while LIVE, run timeline.
- **wiki** — 2-col browser; kills the blank "SELECT A PAGE" void with a real EmptyState; FTS
  search; markdown viewer with gradual-blur scroll edges.
- **models** — registry table; dot-field/line-waves alt substrate; graceful degrade.
- **integrations (new)** — adapter/tool health, read-only-by-default posture, approval gates.
- **settings / system-health (new)** — gateway/version/health, env, mock-mode banner.
- **artifact-browser (new)** — distinct surface; artifact list + preview, provenance.

Every page: real **error / loading / empty** states. No blank voids.

## 9. Verification

`npm run build` green · run + Playwright snapshots of every route to `output/playwright/` ·
`/gsd-ui-review` 6-pillar audit → resolve BLOCK/FLAG · favicon renders · contrast + keyboard +
reduced-motion + responsive pass · effects degrade to static under reduced-motion.
