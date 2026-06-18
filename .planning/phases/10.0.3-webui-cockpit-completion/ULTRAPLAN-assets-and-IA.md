# ULTRAPLAN — ATLAS Brand Assets + Cockpit Page Architecture

Implementation-ready. Design context is locked (celestial-heraldic on the L2 Topographic
system: Cinzel display, bronze filigree, celestial blue, ivory text, dark-luxe craft).
Brand decision locked: **vivid-blue "celestial" emblem is primary; bronze = precious filigree.**

---

## PART A — Brand asset pipeline

### A.0 Source inventory (`brand/atlas/`, all 1122×1402 RGB)
- `source/emblem-celestial-primary.png` — **primary hero emblem** (titan + glowing globe + circuit-temple + baked wordmark). PRIMARY.
- `source/emblem-bronze-primary.png` — austere/gold variant. Secondary / marketing.
- `sheets/board-celestial-mark-system.png` — primary, stacked, seal, monogram, wordmark.
- `sheets/board-celestial-app-icons.png` — favicon/app-icon studies.
- `sheets/brand-sheet-master.png` — master sheet; clean lockup row at bottom (emblem · stacked · seal · AP monogram · wordmark).
- `sheets/board-bronze-*` (×3) — bronze explorations. Archive/reference.

### A.1 Principle — photographic for brand moments, vector for tiny marks
Photographic emblems do **not** downscale to 16–32px. Therefore:
- **Large brand moments** (hero, splash, About, big empty states) → processed photographic PNG/WebP.
- **Tiny marks** (favicon, collapsed-nav, inline) → keep the crisp **code-drawn** `AtlasMark` + SVG favicon already shipped (vector, sharp at any size).
This is the professional split and satisfies "fit where they fit."

### A.2 Processing steps (Python/PIL 12.2, script `brand/atlas/process.py`)
1. **Black→transparent + trim** on `emblem-celestial-primary.png`:
   - luminance-keyed alpha (near-black `#0B0D12`/`#000` → transparent), soft threshold to keep the fine linework glow, then autocrop to content bbox.
   - Output `emblem-full` (whole, incl. wordmark) and `emblem-figure` (top ~0–63% = titan+globe, no baked wordmark).
2. **Crop sub-marks** from `brand-sheet-master.png` bottom lockup row + `board-celestial-mark-system.png`:
   - `seal` (circular "ATLAS PROJECT · MISSION · AUDIT · STRUCTURE" seal) → black→transparent + trim.
   - (Monogram/stacked optional; code mark already covers nav.)
3. **Export web sizes** (WebP, q=90, + PNG fallback) into `services/web-ui-react/src/brand/assets/`:
   - `emblem-figure.webp` @ ~1100px tall (hero/splash, retina).
   - `emblem-full.webp` @ ~1200px tall (About/splash).
   - `seal.webp` @ ~640px (empty states).
   - Keep file weight sane (< ~250 KB each via WebP).
4. **Favicon/app-icon**: keep `public/favicon.svg` (vector). Add PNG app-icons for Tauri/installer from a clean square crop of the globe/seal: 32, 180 (apple-touch), 512, 1024 → `public/icons/`.

### A.3 Consumption map
| Asset | Where | Treatment |
|---|---|---|
| `emblem-figure.webp` | Dashboard hero focal (right counterweight), replaces code astrolabe | celestial-screen blend, opacity ~0.9, mask-faded edges |
| `emblem-full.webp` | Boot/splash + `/system` About panel | centered, full |
| `seal.webp` | Large empty states (no missions, no results) | centered, opacity ~0.85 |
| code `AtlasMark` (kept) | Sidebar (expanded + collapsed), inline | vector |
| `favicon.svg` (kept) + `icons/*.png` | Browser tab + Tauri app icon | vector + raster set |

---

## PART B — Page architecture from scratch (operator IA)

**Thesis:** MISSION / AUDIT / STRUCTURE. Organize navigation around the operator's loop and
the three pillars, not a flat feature list. Gateway surfaces: missions(+runs), runs(+audit-events/SSE),
wiki(FTS+provenance), models, health.

### Nav model — pillared rail
```
OBSERVATORY      /                 (overview / home)
── MISSION ──
  Missions       /missions         portfolio + create
  Mission        /missions/:id     mission cockpit
  Runs           /runs             live activity stream / history
  Run            /runs/:id         SSE audit timeline (showpiece)
── AUDIT ──
  Ledger         /audit            NEW unified audit-event explorer (filterable)
── STRUCTURE ──
  Codex          /wiki             memory/wiki: FTS search + provenance
  Models         /models           registry + routing + health
  Integrations   /integrations     NEW adapters/tools/sidecars health (read-only)
── SYSTEM ──
  System         /system           NEW gateway/version/health/env + About (emblem)
```
Global: **Command palette (⌘K)** — launch mission, jump to run, search codex. Operator speed.

### Per-page spec
| Route | Purpose | Primary surface | Key components |
|---|---|---|---|
| `/` Observatory | System-at-a-glance, launch point | celestial hero stage + telemetry rails | Hero(emblem), StatRail, ActiveMissions, RecentRuns, SystemStatus |
| `/missions` | Mission portfolio | hairline mission table | MissionRow, StatusBadge, CreateMissionModal(click-spark), filters |
| `/missions/:id` | Mission cockpit | intent header + run lifecycle | IntentPanel, RunList, LaunchRun, lifecycle timeline |
| `/runs` | Cross-mission activity | live run stream | RunRow, LiveBadge, status filter |
| `/runs/:id` | **Showpiece** — live audit | SSE event timeline over faulty-terminal texture | SseEventRow, GlowBorder(LIVE), RunTimeline, tool/policy chips |
| `/audit` **NEW** | "Every action accounted for" | filterable event ledger (cursor paginated) | EventLedger, filters(event_type/policy_result/tool/time), detail drawer |
| `/wiki` Codex | Memory foundation | 2-col browser + FTS | SearchBar, PageList, PageViewer(gradual-blur edges), ProvenancePanel |
| `/models` | Model registry | registry table | ModelRow, provider/health, routing note, graceful-degrade empty |
| `/integrations` **NEW** | Adapter/tool/sidecar health | status board | IntegrationCard, connection state, approval-gate posture |
| `/system` **NEW** | Gateway/version/health/env + About | spec sheet + brand About | HealthPanel, EnvPanel, AboutEmblem(emblem-full), version |

### Global states (every page)
Real **skeleton / empty / offline** — never blank. Empty states use `seal.webp` + a serif headline +
a next-action. Offline = honest gateway banner. (Pattern already shipped on Observatory.)

### Build order (waves)
1. **Assets** (Part A) → emblem-figure into Observatory hero; seal into empty states.
2. **Pillared nav** — restructure `modules.ts` into grouped sections; Sidebar renders pillar headers.
3. **Mission pillar** — `/missions`, `/missions/:id`, `/runs`, `/runs/:id` (real data, restyle Svelte logic).
4. **Audit Ledger** `/audit` (NEW) — the differentiator surface.
5. **Structure** — `/wiki` Codex, `/models`, `/integrations` (NEW).
6. **System/About** `/system` (NEW) — emblem-full lands here.
7. **Command palette** (⌘K) + polish/motion/a11y, then verify (build, lint, Playwright, ui-review).

### Verification gates
`tsc 6` + `eslint 10` clean · `vite 8` build green · Playwright snapshot every route ·
contrast/keyboard/reduced-motion · favicon + emblem render · offline degrade.
