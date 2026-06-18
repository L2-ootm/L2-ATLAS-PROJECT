# PAGES-SPEC — ATLAS Cockpit, full page set (build-from-scratch)

Companion to `ULTRAPLAN-assets-and-IA.md`. This is the **verbose, build-ready** specification
for every surface in the redesigned cockpit, in the celestial-heraldic system on the L2
Topographic substrate. Each page declares: purpose, data sources (see `HARNESS-WIRING.md`),
layout/primary surface, components, the three mandatory states (loading/empty/error), motion
and topo-reactive behavior (see `UX-VISUAL-SPEC.md`), and acceptance.

Global laws carried into every page:
- **Dark-luxe craft.** Depth from tone + bronze hairlines, never floating glass-card grids.
  One focal element per surface. Stage, not blank void.
- **The system states; it never asks.** Mono labels are declarations. Data is mono + `tabular-nums`.
- **Three states always.** Skeleton (preserves layout) · empty (seal + serif headline + next action)
  · offline (honest gateway banner). No blank regions, ever.
- **Topo is the connective tissue.** Every surface tags `data-topo` so the terrain glows in the
  semantic color of what the cursor touches. Inputs are topo-reactive (typing = authorship).
- **2px radii · one curve `cubic-bezier(0.22,1,0.36,1)` · ivory text · Cinzel display · mono data.**

---

## Navigation shell — pillared rail

The sidebar groups routes under the thesis pillars, each with a mono section header in bronze
and a hairline divider. Collapsed: icon-only with the section dividers preserved as bronze ticks.

```
◆ ATLAS               (mark + engraved wordmark; collapses to mark)
  OBSERVATORY    /
─ MISSION ─
  Missions       /missions
  Runs           /runs
─ AUDIT ─
  Ledger         /audit
─ STRUCTURE ─
  Codex          /wiki
  Models         /models
  Integrations   /integrations
─ SYSTEM ─
  System         /system
  ◦ gateway status dot · BY L2 SYSTEMS
```

`modules.ts` becomes a grouped registry: `Section[] = { pillar, items: Module[] }`. The active
item shows a celestial glow-rail; the active pillar header brightens. ⌘K opens the command palette
(launch mission · jump to run · search codex · go to page).

---

## 1. Observatory — `/` (home)

**Purpose.** The operator's first glance: is the system healthy, what is running, what just happened,
where do I go. The brand stage lives here.

**Data.** `listMissions`, `listModels`, `listWikiPages`, `checkHealth`; (next) a recent-runs feed.

**Layout.**
- **Hero stage** (shipped): starfield + Operator-Atlas emblem (right, masked) + engraved ATLAS
  wordmark + bronze eyebrow + serif thesis line. One focal object. `data-topo="atlas"`.
- **Stat rail** (shipped): single hairline band, 4 cells (Missions/Running/Models/Codex), tabular
  numbers, em-dash on offline, skeleton on load.
- **Two columns**: `ActiveMissions` (live + recent, hairline rows) | `SystemStatus` (gateway/db/health).
- **Recent activity** band (next): last N run/audit events as a compact terminal-tinted feed.

**States.** Shipped. Empty = seal + "The titan stands ready…". Offline = honest banner.

**Motion.** Emblem holds still (the bearer is steady); starfield twinkles slow; astrolabe machinery
turns. Stat cells lift on hover with a celestial topo bloom.

**Acceptance.** Reads as a running system at a glance; no dead cells; brand visible in pixels.

---

## 2. Missions — `/missions`

**Purpose.** The mission portfolio. Scan, filter, open, and create missions.

**Data.** `listMissions(limit)`. Create → `createMission(title, intent)` (gateway → `atlas` CLI).

**Layout.** A **mission table** rendered as hairline rows (not cards): each row = index · title ·
intent (truncated) · status badge · updated-at (mono, relative). Column header is mono/bronze.
Top bar: a topo-reactive **search/filter input** + status filter chips + a primary **"New Mission"**
button (celestial, click-spark confirm). Right-aligned count ("12 MISSIONS").

**Create flow.** Modal over a dimmed plasma scrim: title + intent fields (both topo-reactive
inputs; the terrain behind blooms violet — AI authorship — as you type the intent). Submit shows
click-spark + optimistic row insert; failure rolls back with an inline error preserving input.

**States.** Loading = skeleton rows. Empty = seal + "No missions yet — author the first." + the New
Mission CTA. Error = inline banner with retry, input preserved.

**Acceptance.** Create→appear round-trips against the live gateway; filter is instant; row hover
glows `info`.

---

## 3. Mission detail — `/missions/:id`

**Purpose.** The mission cockpit: its intent, its runs, and the controls to launch/cancel.

**Data.** `getMission(id)` → `{ mission, runs }`. Launch → `startRun(id)`. Cancel → `cancelRun(id)`
(note: cancels ALL active runs of the mission — surface that explicitly in the confirm).

**Layout.**
- **Intent header band**: mission title (Cinzel-adjacent weight), status badge, project, created/updated
  (mono). The intent prose in a liquid-glass slab over the terrain.
- **Lifecycle rail**: a horizontal run-lifecycle indicator (pending→running→succeeded/failed/partial).
- **Run list**: hairline rows, each linking to `/runs/:id`, with status badge + started/finished +
  duration (mono). A **"Launch run"** primary action (celestial, click-spark); **Cancel** is a
  destructive secondary with an explicit "halts every running run of this mission" confirm.

**States.** Loading = header + rows skeleton. Empty (no runs) = "No runs yet — launch the first."
Error/404 = "Mission not found" with a path back to /missions.

**Acceptance.** Launch creates a run and routes to its live stream; cancel reflects within one poll.

---

## 4. Runs — `/runs`

**Purpose.** Cross-mission activity stream: what the system is doing now and did recently.

**Data.** (Gap — see `HARNESS-WIRING.md §Gaps`) no list-all-runs endpoint today; interim = aggregate
from `listMissions` → `getMission` runs, or add `GET /v1/runs`. Live ones marked with `LiveBadge`.

**Layout.** A live feed: hairline rows = run id (mono) · mission title · status · started (relative) ·
duration. Running rows carry a pulsing celestial `LiveBadge` and a glow-border. Status filter chips.

**States.** Loading skeleton · empty "No runs recorded yet." · offline banner.

**Acceptance.** Running rows visibly live; clicking opens the run timeline.

---

## 5. Run detail — `/runs/:id` — **THE SHOWPIECE**

**Purpose.** The live audit timeline of a single run — the proof surface of the AUDIT thesis. This is
the most cinematic operator screen.

**Data.** `getRun(id)` for the header; **`GET /v1/runs/{id}/stream` (SSE)** for live events — this
endpoint exists in the gateway and is currently unused by the UI (api.ts polls `getRunEvents`).
Wire SSE for LIVE runs, fall back to `getRunEvents(after, limit)` cursor pagination for history.

**Layout.**
- **Run header band**: run id, mission link, status, started/finished, duration; a `LiveBadge` +
  **electric/glow-border** around the whole stage while status === running.
- **Audit timeline**: vertical event stream over a restrained **faulty-terminal CRT texture**
  (scanline shader, low opacity, behind the log only). Each `SseEventRow` = timestamp (mono) ·
  event_type chip · tool_name · duration_ms · policy_result chip (color = semantic: tool=info,
  policy-deny=bad, model=violet). New events arrive with a blur-in + a **topo `sonarPing`** at the
  row's position in the ambient field ("a thing happened").
- **Cursor pagination** for backfill; auto-scroll pinned to head while live, releases on manual scroll.

**States.** Connecting = skeleton timeline + "ESTABLISHING STREAM…". Empty (no events) = "No audit
events yet." Stream error = inline "STREAM LOST — RETRYING" with backoff; falls back to polling.

**Motion.** LIVE = glow-border breathing; each event = sonar ping + blur-in; terminal scanlines drift.

**Acceptance.** A running run streams events live via SSE with visible per-event signal; reconnects
on drop; history paginates; reduced-motion drops to static rows.

---

## 6. Ledger — `/audit` — **NEW (the differentiator)**

**Purpose.** "Every action accounted for." A unified, filterable explorer across **all** runs' audit
events — the operator's forensic ledger. Nothing in the current cockpit offers this.

**Data.** (Gap) needs `GET /v1/audit/events?after&limit&type&policy&tool&run&since` (cursor paginated,
filterable). Interim: derive by fanning out run events. Document as a required gateway endpoint.

**Layout.** A dense, monospace **event ledger table**: cursor · timestamp · run (link) · event_type ·
tool_name · duration_ms · policy_result. A **filter rail** (event_type, policy_result, tool, time
window, free text). Row click opens a **detail drawer** showing the structured `data` JSON
(pretty-printed, collapsible) + provenance. Keyboard navigable (j/k, enter). Saved-filter chips.

**States.** Loading skeleton table · empty "No events match these filters." (with a clear-filters
action) · offline banner. Large-result guard: virtualized rows, cursor "load more".

**Acceptance.** Filter by policy=deny shows only denied actions across every run; drawer shows the
exact event payload; pagination is stable on the rowid cursor.

---

## 7. Codex — `/wiki`

**Purpose.** The memory/knowledge foundation: search, read, and trace provenance of wiki/memory pages.

**Data.** `listWikiPages`, `searchWiki(q)`, `getWikiPage(slug)` (incl. provenance), create/update.

**Layout.** Two-column browser: left = topo-reactive **FTS search** + page list (hairline rows,
updated-at); right = **markdown viewer** in a liquid-glass reading slab with **gradual-blur** scroll
edges; a **ProvenancePanel** (run_id / operator / source / sensitivity / written_at) as a bronze-
framed sidecar. Kills the old blank "SELECT A PAGE" void with a real empty state.

**States.** No selection = seal + "Select a page, or search the codex." Empty search = "No pages
match '<q>'." Loading = skeleton list + viewer. Offline banner.

**Acceptance.** FTS returns ranked snippets; provenance renders; markdown is readable on glass.

---

## 8. Models — `/models`

**Purpose.** The model registry: what models are known, their providers, and routing/health posture.

**Data.** `listModels()` (degrades to empty on 404/503). Fields: model_id, provider, source,
first/last_seen, active; tier/health/policy derived client-side when absent.

**Layout.** A registry table (hairline rows): model_id (mono) · provider · tier · health dot ·
last_seen. An alt ambient substrate here (dot-field / line-waves) to distinguish it from the mission
surfaces. A routing note explaining task-class routing (D-017).

**States.** Empty (no registry) = graceful "Model registry empty or unavailable." Offline banner.

**Acceptance.** Active/inactive and health read at a glance; graceful degrade verified.

---

## 9. Integrations — `/integrations` — **NEW**

**Purpose.** Adapter/tool/sidecar health and posture (read-only-by-default; approval gates). The
operator's view of what ATLAS is wired to (LLM adapters, Twenty CRM sidecar, MCP tools, FreeLLMAPI).

**Data.** (Gap) needs an integrations/tools registry endpoint (e.g. `GET /v1/integrations`). Interim:
static manifest + live `checkHealth` for the gateway. Document as required.

**Layout.** A status board of **integration rows** (not a card grid): name · kind (adapter/sidecar/
tool/MCP) · connection state dot · last check · posture (read-only / approval-gated). Each expands to
show endpoint, auth mode, and recent errors. Bronze-framed, calm.

**States.** Loading skeleton · empty "No integrations configured." · per-row error detail.

**Acceptance.** Connection state is live and honest; read-only posture is visible.

---

## 10. System — `/system` — **NEW (+ About)**

**Purpose.** Gateway/version/health/env, mock-mode banner, and the brand About — where the full
Operator-Atlas emblem lives at rest.

**Data.** `checkHealth()` (status/db); build/version (compile-time constant); env flags (mock mode).

**Layout.**
- **Health panel**: gateway online, db ok, latency; version + build hash (mono).
- **Environment panel**: gateway URL, mock-mode banner if active, feature flags.
- **About band**: `emblem-full.webp` centered on a starfield stage, the brand narrative ("THE
  OPERATOR ATLAS — Bearing Complexity Through Structure"), the three pillars, "BY L2 SYSTEMS",
  and an attribution line (foundation derived from Hermes, MIT — see de-brand phase).

**States.** Offline = the health panel itself becomes the offline story (this page is partly an
offline-diagnostic surface). Always renders (no hard dependency on the gateway).

**Acceptance.** Tells the operator exactly what they're connected to; About renders the emblem at
hero fidelity.

---

## Global: Command palette (⌘K)

**Purpose.** Operator speed. Launch a mission, jump to a run by id, search the codex, navigate.

**Behavior.** ⌘K / Ctrl-K opens a centered command modal over a plasma scrim. A single topo-reactive
input (typing blooms the terrain violet); results grouped (Actions · Missions · Runs · Codex · Go to).
Arrow/enter to execute. Esc/scrim to close. `bits-ui`/`cmdk`-class primitive, restyled to the system.

**Acceptance.** Reachable from every page; keyboard-only operable; sub-100ms result render.

---

## Build waves (recap)

1. Pillared nav + `modules.ts` sections. 2. Missions + Mission detail. 3. Runs + Run detail (SSE).
4. Audit Ledger (+ endpoint). 5. Codex + Models + Integrations. 6. System/About. 7. ⌘K + polish.
Each wave: real states, topo-reactive inputs, build/lint/Playwright green before the next.
