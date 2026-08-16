# FounderOS-DEMO — full teardown

**Source:** `github.com/Bennettxai/FounderOS-DEMO` @ `main`, downloaded 2026-08-16
(688 KB archive). MIT. Every quote and value below is read from the source, not
from the README's description of itself.

**Purpose of this document:** capture the structure, the mechanics, and the
visual system precisely enough that ATLAS can adopt the parts worth adopting
without re-reading the repo. It is a teardown, not an endorsement — §8 records
what the README claims that the code does not do.

---

## 1. What it is, mechanically

A Next.js 14 App Router application, TypeScript, server components by default,
backed by a local `better-sqlite3` file (`data/founder-os.db`, WAL) that
auto-seeds on first touch. No auth, no API keys required, no external services
needed to render every page. `npm run dev` → `http://localhost:4100`.

| Layer | Count | Notes |
|---|---|---|
| Routes (`app/*/page.tsx`) | 17 + nested | plus ~30 API route groups |
| Components | 66 | largest: `KnowledgeGraph.tsx` at 112 KB |
| Lib modules | 80 | largest: `seed.ts` at 80 KB, `db.ts` at 38 KB |
| Tests | ~90 files | Vitest, one file per module |
| Connectors | 25 | `lib/connectors/*.ts` |

Stack: Next 14 · TypeScript · Tailwind · better-sqlite3 · Zod · Vitest ·
Vercel AI SDK · d3-force · lucide-react · simple-icons.

---

## 2. The load-bearing rule: "larp-first, real-ready"

This is the single most transferable idea in the repo. From `CLAUDE.md`:

> This is the load-bearing design rule. v1 looks alive because of rich seeded
> data, but every page and API route reads through the repository layer — never
> query SQLite directly from a page or route.

The four-file contract:

- `lib/data.ts` — `getDb()` app singleton; seeds on first touch
- `lib/db.ts` — `openDb()` + typed repos (`departments`, `agents`, `metrics`, `tools`, …)
- `lib/seed.ts` — all seeded content, nothing else
- `lib/schemas.ts` — Zod schemas validate every row **on the way OUT of the DB**

> Swapping seeded tables for live sources is a repo-level change. Keep it that
> way: new data = new repo method + Zod schema + seed entry + test.

**Why it matters for ATLAS.** The demo is architecturally identical to
production; only the repository implementations differ. That is what lets a
cold visitor see a working system in one command. ATLAS today has the inverse
property: a cold visitor gets "Failed to fetch" unless the gateway is up, the
cockpit is on :5173, and a provider is configured.

### The anti-larp test

`lib/seed.ts:48`:

> The roster IS the runtime — every row here maps 1:1 to a RuntimeAgent in
> `lib/agents/real.ts` (enforced by `tests/seed.test.ts`). No larp agents.

`tests/seed.test.ts:37` — `test('every seeded agent maps to a real runtime agent — no larp')`
iterates the seeded roster and asserts `runtimeIds.has(agent.id)`.

This is a one-test guard that makes it structurally impossible to add a
decorative agent to the UI. ATLAS has no equivalent invariant: cockpit surfaces
can display things the runtime cannot execute.

---

## 3. The org / department model

### Schema

`departments` (`lib/db.ts:69`):

```sql
CREATE TABLE IF NOT EXISTS departments (
  id      TEXT PRIMARY KEY,
  name    TEXT NOT NULL,
  slug    TEXT NOT NULL UNIQUE,
  tagline TEXT NOT NULL DEFAULT '',
  color   TEXT NOT NULL,
  "order" INTEGER NOT NULL
);
```

`agents` (`lib/db.ts:77`, plus two later `ALTER TABLE` migrations at `db.ts:327-328`):

```sql
CREATE TABLE IF NOT EXISTS agents (
  id            TEXT PRIMARY KEY,
  department_id TEXT NOT NULL REFERENCES departments(id),
  name          TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT '',
  status        TEXT NOT NULL,   -- active | idle | training | planned
  tier          TEXT NOT NULL,   -- lead | specialist | worker
  description   TEXT NOT NULL DEFAULT '',
  model         TEXT NOT NULL DEFAULT '',
  tools         TEXT NOT NULL DEFAULT '[]'
);
ALTER TABLE agents ADD COLUMN parent_id TEXT;              -- nullable
ALTER TABLE agents ADD COLUMN instance TEXT DEFAULT 'builtin';
```

Zod (`lib/schemas.ts:17`) with the two fields that carry the whole model:

```ts
// parentId nests sub-agents under the agent doing the delegating;
// instance names the runtime that will host this agent ('builtin' today,
// an OpenClaw/Claude Code instance name once the dedicated host is live).
parentId: z.string().nullable().default(null),
instance: z.string().min(1).default('builtin'),
```

`instance` is the interesting one: it is the binding from an org-chart box to
the OS process that will host it. Today every value is `'builtin'`; the column
exists so the org chart is already shaped for a distributed runtime.

### Tree construction — `lib/hierarchy.ts` (56 lines, the whole model)

```ts
const TIER_ORDER: Record<Agent['tier'], number> = { lead: 0, specialist: 1, worker: 2 };
```

Three types only: `AgentNode { agent, children }`, `DepartmentNode { department, roots }`,
`Hierarchy { departments, totalAgents, activeAgents }`.

The one non-obvious rule, `hierarchy.ts:28`:

```ts
// An agent whose parent left the roster surfaces at the root rather than vanishing
.filter((a) => (a.parentId !== null && ids.has(a.parentId) ? a.parentId : null) === parentId)
```

Orphans promote to root instead of disappearing. Sort is tier-then-name.
`buildHierarchy` sorts departments by `order`, groups agents by `departmentId`,
and counts actives. Pure functions, no DB access, trivially testable.

### The seeded organisation

Six departments (`lib/seed.ts:39`), colours are greys because the Monolith theme
forbids decorative colour:

| id | name | tagline | order |
|---|---|---|---|
| `dept-sales` | Sales | Pipeline and deals. | 1 |
| `dept-marketing-growth` | Marketing/Growth | Publishing, content, attention. | 2 |
| `dept-tech` | TECH | AI & automations · G-Brain. | 3 |
| `dept-finance` | Finances | Every processor, one view. | 4 |
| `dept-comms` | Communications | Gmail, WhatsApp, Slack → one feed. | 5 |
| `dept-clients` | Clients | Every client, onboarded and served. | 6 |

The seed comment states the tiering rule:

> Top-level agents (`parentId` null) are INSTANCE slots — each one is what
> becomes its own OpenClaw Hermes / Claude Code process on the dedicated host
> (`instance` records that binding). Worker rows underneath them do one specific
> task each and sit at the bottom of the hierarchy.

Example lead (`seed.ts:58`) — note `model` is a description of the composition
strategy, not a model id:

```ts
{
  id: 'conductor', departmentId: 'dept-tech', name: 'Conductor',
  role: 'Broadcast & Orchestration', status: 'active', tier: 'lead',
  description: 'Fans your message out to every agent at once and checks which
                instance hosts (OpenClaw, Ollama, tmux) are available…',
  model: 'fan-out runtime',
  tools: ['broadcast', 'openclaw', 'tmux'],
  parentId: null, instance: 'builtin',
}
```

Other leads use `model: 'aggregate of workers'` — `comms-agent`, `social-agent`,
`sales-agent`, `data-agent`. A lead is defined by what it aggregates.

### Human personnel is a separate, thin layer

`lib/personnel.ts` (741 bytes) — `Personnel { id, name, role, department }`,
two records (Marco, Head of Sales; Nadia, Head of Growth & Marketing), one
function `headForDepartment()`. Explicitly excluded from the force graph;
it renders in panels only. Humans and agents are deliberately *not* the same
entity.

### The `/org` view — `app/org/page.tsx` (311 lines)

Vertical composition, top to bottom:

1. **Operator** — name + `OPERATOR` eyebrow, then a 24px vertical hairline.
2. **AI Head row** — `SystemCard(G-Brain) ── ConductorCard ── SystemCard(Comms Feed)`,
   joined by 40px horizontal hairlines. The Conductor is pulled out of the tree
   (`agents.filter(a => a.id !== 'conductor')`) so it occupies its own slot.
3. **Trunk** — a 40px vertical hairline down to a horizontal rail.
4. **Department rail** — `mx-36` (half a 288px column) so the rail runs exactly
   centre-to-centre and every connector meets it. Each department is a `w-72`
   column; `.org-connector::before` draws the 16px stub upward into the rail.
5. **Per department**: name → life-area chip → 64px spark tile (tinted by life
   area) → *crew* (lead agents as full-width cards showing name, status dot,
   `instance` chip, role) → *pills* (workers as rounded 2-col pills, indented
   10px per depth) → *Agent Tools* (deduped union of every `tools[]` in the
   subtree).

Two overlay lenses on the same data, both pure view state:

- **Venture lens** (`?venture=`) — `dimFor(id)` drops non-member agents to
  `opacity-20`; members get a coloured border and glow. Same roster, same DB.
- **Life areas** — `lifeAreaForDepartment(id)` tints each department by which
  part of life it serves, with a legend strip.

Responsive tiers: gaps widen `gap-4 → wide:gap-8 → ultra:gap-12`, and the
department column only acquires a card border/background at `wide:` and up.

`CLAUDE.md` marks the page **"markup frozen — do not restructure"** and notes it
inherits tokens through Tailwind classes only. It also still uses two legacy
aliases (`os-raised`, `os-border-bright`) kept alive in `tailwind.config.ts`
specifically so `/org` never needed editing during the theme revamp.

---

## 4. Runtime

`lib/agents/runtime.ts` is 91 lines. The entire agent contract:

```ts
export type RuntimeAgent = {
  id: string; name: string; description: string; departmentId: string;
  run(): Promise<AgentRunResult>;
  respond?(message: string): Promise<AgentRunResult>;   // conversational entry
  chatTools?(): LlmToolSpec[];                          // read-only connector wrappers
};
```

`createRuntime(db, agents)` builds a `Map` registry and exposes three methods:

- `list()`
- `run(id)` — times the call, catches throws into `{ ok: false, summary }`,
  persists an `AgentRun` row. Failure is a record, never an exception escaping.
- `broadcast(message)` — inserts a `broadcasts` row, then `Promise.all` over the
  whole registry: each agent uses `respond()` if it has one, else falls back to
  `run()`. Every reply is persisted to `broadcast_replies`.

That is the whole orchestration layer. There is no planner, no goal tree, no
verification, no session continuity. Compare with ATLAS's `team_run_service.py`,
`session_continuity.py`, and `verification_gate` — ATLAS is several layers
deeper here.

Supporting tables: `agent_runs`, `agent_messages`, `agent_tasks`, `agent_crons`,
`broadcasts`, `broadcast_replies`.

### Connector honesty contract

25 connectors under `lib/connectors/`, each returning a `ConnectorStatus` of
`connected | not_configured | error` — `CLAUDE.md` says "never fake
'connected'". `lib/creds.ts` resolves credentials from `process.env` first, then
canonical files on disk at runtime, and the doctrine is explicit: **never copy
secret values into the repo**. `/integrations` renders the live board.

---

## 5. Information architecture

`lib/nav.ts` is the single source of truth. Its header states the invariant:

> The Sidebar renders these groups in order; the CommandPalette derives its
> digit (1–9) shortcuts from the same visible order, so the two can never drift
> apart again.

| Group | Items |
|---|---|
| **Operate** | Home · Comms · Funnel · Workflows · Social · Content · Finances |
| **Agents** | Agents · Tasks · Skills · Org Chart |
| **Intelligence** | G-Brain |
| **System** | Connections · Roadmap · Analytics · Reference Model |
| **Variants** | Personas |

`NAV_ORDER` is the concatenation; `DIGIT_VIEWS = NAV_ORDER.slice(0, 9)`.

**The structural observation.** Group 1 is the work. Groups 2–4 are the machine.
The work is on top and outnumbers the machine 7:6. ATLAS inverts this: `MISSION`
(7 items: Command, Missions, Runs, Sessions, Chat, Console, Teams), `AUDIT` (1),
`STRUCTURE` (7), `SYSTEM` (1) — sixteen items, all of them machine.

### Shell

`app/layout.tsx`: `<Sidebar/>` fixed left · `.os-shell` content column with
`ml-[232px]` and `margin-right: var(--conductor-w, 0px)` · `<Topbar/>` sticky
breadcrumb + ⌘K · `<CommandPalette/>` · `<ConductorPanel/>` right-hand dock.

Width tiers: `max-w-[1280px]` laptop → `wide:max-w-[1760px]` (≥1800px) →
`ultra:max-w-none` (≥2200px). Padding scales `px-8 → wide:px-10 → ultra:px-12`.

Command palette content is *derived*, not hand-written: `buildCommands()` in
`layout.tsx:42` unions `NAV_COMMANDS` with a row per agent (`db.agents.all()`)
and per tool (`db.tools.all()`). Adding an agent adds a palette entry for free.
It also carries `localhost:` and `web` hinted entries for external apps.

### Sidebar behaviour (`components/Sidebar.tsx`, 238 lines)

Collapsed 56px / default 232px / drag-resizable 190–420px, persisted to
`localStorage`, publishing `--sidebar-w` on `documentElement` so the shell reads
one source of truth. Collapsed state replaces group headings with hairline
dividers so icon runs still read as groups. Collapsed hover labels render
`position: fixed` outside the scrolling nav — the comment explains why:
"any scrolling ancestor clips an absolutely positioned child". Footer polls
`/api/connections` and shows `{up}/{total} systems live` next to a pulsing dot,
plus `window.location.host` read client-side "so a deployed instance never
claims to be localhost".

---

## 6. The visual system — how it looks the way it does

This is a small, strictly-enforced system, not a large one. Five mechanisms
carry the whole look.

### 6.1 One token layer, two consumers

Every colour is a CSS custom property on `:root[data-theme=…]` in
`app/globals.css`. `tailwind.config.ts` defines `os.*` colours that *read those
vars*:

```ts
os: { bg: 'var(--bg)', surface: 'var(--surface)', border: 'var(--border)',
      hairline: 'var(--hairline)', text: 'var(--text)', muted: 'var(--text-2)',
      dim: 'var(--text-3)', accent: 'var(--accent)', ink: 'var(--accent-ink)',
      ok: 'var(--ok)', warn: 'var(--warn)', err: 'var(--err)', … }
```

Consequence: **one `data-theme` flip on `<html>` re-themes every `os-*` class at
once**, and SVG/`color-mix()` code that needs raw values can use `var()`
directly. Six themes, zero per-theme component code.

`app/layout.tsx` injects `THEME_INIT_SCRIPT` in `<head>` — "apply the persisted
theme before first paint — no dark↔light flash."

### 6.2 Six themes, one motion constant

Themes: `dark` (phosphor), `light` (warm paper), `midnight` (navy), `ember`
(coal/orange), `mono` (**default**, Monolith Signal), `mono-light` (Daylight).

The one theme-independent token, on a bare `:root`, with the reason recorded:

```css
:root { --ease: cubic-bezier(0.32, 0.72, 0, 1); }
/* These must live on a bare :root: scoping them to one theme silently kills
   every var(--ease) animation on the others. */
```

Default theme, `mono` (also on bare `:root` "so a pre-script or no-JS load
already renders Monolith"):

```css
--bg: #0a0a0a;  --bg-2: #0a0a0a;
--surface: #0a0a0a;      /* boxes are gone — surfaces flatten to bg */
--surface-2: #141414;    /* hover fill */
--surface-3: #1c1c1c;
--border: #242424;       /* structural rules */
--border-strong: #3a3a3a;
--hairline: #1c1c1c;     /* row dividers */
--text: #f2f2f2;  --text-2: #9c9c9c;  --text-3: #5c5c5c;
--accent: #f2f2f2;       /* accent IS white */
--accent-soft: rgba(242,242,242,0.06);
--accent-line: rgba(242,242,242,0.25);
--ok: #2fd36f;  --warn: #ffb000;  --err: #ff2d3f;   /* the only three colors */
--glow: none;            /* glows are dead */
--grid: transparent;     /* background grid is dead */
```

The doctrine comment above it: *"white/grey structure on bare black, boxes
flattened, zero glow/grid, and a strict traffic-light rule — colour only ever
means status: green good · yellow degraded · red bad."*

Contrast with `dark`, which keeps a phosphor identity: `--bg: #050807`,
`--accent: #3df08c`, `--glow: 0 0 24px rgba(61,240,140,0.18)`,
`--grid: rgba(228,239,230,0.018)`.

The discipline that makes six themes survivable: **status colours stay semantic
across every theme.** `light` shifts its accent cool→warm (`#c96442`) but keeps
`--ok` green, with the reason in a comment: "so a live system still reads
'green' in both themes".

Independent sub-palettes exist for visualisation and are themed separately:
`--brain-1/2/3` (knowledge graph), `--funnel-hot/warm/cold` +
`--funnel-s0..s6` (seven acquisition wedges), `--kg-tool`. Mono neutralises them
to a grey ramp and keeps exactly one green (conversion).

### 6.3 Typography and geometry

- **One typeface.** JetBrains Mono via `next/font/google`, weights 400/500/600/700.
  `tailwind.config.ts` points *both* `font-sans` and `font-mono` at
  `var(--font-mono)`. The comment: "Space Grotesk is retired."
- **Radii are zero.** `borderRadius: { 'sm-t': '0px', 'md-t': '0px', 'lg-t': '0px' }`
  — class names kept so no component needed editing; only the values went sharp.
- **A fixed type scale, all uppercase, all tracked out:**

| Element | Spec |
|---|---|
| Page title (`PageHeader`) | 25px / 700 / uppercase / `tracking-[0.06em]` / `leading-[1.1]` |
| Eyebrow | 9.5px / uppercase / `tracking-[0.32em]`, `::before { content: '//' }` |
| Section label (`Label`) | 10px / 700 / uppercase / `tracking-[0.26em]` / `text-os-dim` |
| Badge | 9.5px / uppercase / `tracking-[0.14em]` |
| Nav item | 13.5px / 500 |
| Nav group heading | 9px / uppercase / `tracking-[0.18em]` |
| Sidebar wordmark | 13px / 700 / `tracking-[0.14em]` |
| Footer / mono meta | 10px |

  Nothing between 13.5px and 25px exists. The whole interface is small text and
  one large title, which is most of why it reads as instrumentation.
- **`PageHeader` refuses subtitles**, and says why: *"No descriptions under
  titles — Alex built it, he knows what it does."*

### 6.4 Six primitives, then stop

`components/terminal.tsx` is 132 lines and server-component-safe ("no state, no
handlers"). It exports `Dot`, `Badge`, `Label`, `SectionHead`, `Kbd`, `Spark`,
plus `dotState()`.

`dotState` is the piece worth stealing outright — a single map from *domain*
vocabulary to *visual* vocabulary:

```ts
const DOT_FOR: Record<string, DotState> = {
  connected: 'ok', active: 'ok', ok: 'ok',
  available: 'warn', warn: 'warn', training: 'warn', idle: 'warn',
  error: 'err', fail: 'err',
  not_configured: 'off', planned: 'off', off: 'off',
};
```

Every subsystem's status vocabulary funnels through one function, so a connector,
an agent, and a tool all render identically. `Badge` tones are built with
`color-mix(in oklab, var(--ok) 35%, transparent)` for the border and `9%` for the
fill — one formula, applied to whichever semantic token, so a new tone is one
line.

`Label` renders `LABEL  count ————` — the trailing `<span className="h-px flex-1 bg-os-border" />`
rule that fills remaining width is the repeating motif that makes sections read
as a technical document rather than a web page.

`Spark` is a 40-line inline SVG sparkline: polyline at `strokeWidth 1.5` plus a
polygon fill at `opacity 0.1`, both `var(--accent)`. No charting library.

### 6.5 Motion doctrine

Stated as a rule and then obeyed everywhere: **"machinery, not mascots."**

```css
.emblem { transition: none; }
.group:hover .emblem, .hoverable:hover .emblem { transform: none; filter: none; }
```

- **Hover is border-colour only.** `.hoverable` transitions `border-color` and
  `background-color` at 0.15s; `:active` drops to 0.06s. Nothing lifts, nothing
  scales, no shadows on cards.
- **Status dots are 6×6px squares, `border-radius: 0`.** The "pulse" is an LED
  blink using `steps(1)`, not an easing curve:
  ```css
  @keyframes led-blink { 0%,70%,100% { opacity: 1 } 85% { opacity: 0.25 } }
  ```
  `.dot.off` is transparent with a 1px border — an unlit LED, not a grey one.
- **View entrance is transform-only:** `@keyframes view-in { from { transform: translateY(8px) } }`
  at 0.24s. The comment gives the reason: "so content is never hidden if
  animations are throttled or reduced-motion is on."
- **Overlays are two staged animations:** scrim `overlay-in` 0.22s opacity, then
  panel `panel-in` 0.3s `var(--ease)` with a 0.05s delay,
  `translateY(16px) scale(0.98)` → rest. "Opening must never read as a blank snap."
- **The caret** `::after { content: '▌' }` blinks at 1.1s `steps(1)` in accent.
- **Every single animation block has a `@media (prefers-reduced-motion: reduce)`
  counterpart.** There are no exceptions in the file.

The one place motion is allowed to be expressive is the Conductor emblem, and it
is scoped to a `.thinking` class: a conic-gradient "comet" sweep
(`transparent → accent 35% at 34deg → accent at 82deg → transparent at 104deg`)
masked to a 3px ring, a radial halo scaling 0.7→2 while fading, and a 1.05×
core breathe whose `box-shadow` inset ring shifts toward accent at mid-cycle.
Idle, it is completely still.

### 6.6 Density and layout craft

- Background is two `repeating-linear-gradient`s at 48px making a grid — set
  from `var(--grid)`, which mono zeroes to `transparent`.
- Scrollbars are restyled: 10px, square thumb of `--border-strong` with a 3px
  `--bg` border so it reads as an inset track.
- `::selection` inverts to `--accent` / `--accent-ink`.
- Org connectors are 1px `::before` pseudo-elements, not borders or SVG.
- Heavy visualisations lazy-load via `next/dynamic({ ssr: false })` behind
  **dimension-matched skeletons**, and there is a test enforcing it
  (`tests/code-splitting.test.ts`).

---

## 7. What ATLAS should take, ranked

1. **The `dotState()` funnel** — one map from every subsystem's status vocabulary
   to four visual states. Smallest change, largest consistency gain.
2. **The roster-is-the-runtime test** — an invariant that fails CI when a cockpit
   surface can display something the runtime cannot execute.
3. **The org model** — `department`, `tier` (lead/specialist/worker),
   `parent_id`, `instance`, plus a ~60-line pure `hierarchy.ts`. Additive to
   ATLAS's existing `team_service.py`; the orphan-promotes-to-root rule is worth
   copying verbatim.
4. **Nav as single source of truth** deriving both sidebar *and* command palette,
   with palette rows generated from live data (agents, tools).
5. **Zero-config seeded mode** behind the same repository interfaces.
6. **The token indirection** — Tailwind colours that read CSS vars, so themes are
   a single attribute flip. ATLAS's `app.css` is 84 KB in one file; this is the
   structure that would let it shrink.
7. **`PageHeader` discipline** — one title size, no subtitles, `//` eyebrow.

Deliberately **not** to copy:

- The business verticals (Comms/Funnel/Social/Finances) — that is Bennett's
  business domain. ATLAS's equivalent is the module framework
  (`modules/admissions`, `modules/outreach`, `modules/gsd`), which should render
  *as* departments rather than having departments hardcoded.
- Human personnel as a first-class table — two rows and one function is not a
  system, and ATLAS has no human roster to model.
- `KnowledgeGraph.tsx` at 112 KB. They have the same single-file bloat problem
  ATLAS has in `Console.tsx` (89 KB).

---

## 8. What the README claims that the code does not do

Recorded so nobody plans against a feature that is not there.

- **"Optimal Engine — governed memory runtime, Source → Signal → Claim → Fact →
  Memory, facts require promotion through review gates."** This exists **only in
  `README.md`**. `grep` for `Signal.*Claim`, `Claim.*Fact`, `promotion gate`, or
  `Optimal Engine` across `lib/` and `app/` returns **zero matches**.
  `lib/memory-core.ts` (22.5 KB) is something else entirely: its own docstring
  describes it as graph distillation plus a "cinematic camera" —
  `distillMemoryGraph`, `cameraRect`, `lerpRect`, `forceLayout`,
  `assignLinkClusters` — i.e. viewport easing for the `/brain` visualisation.
  **ATLAS is materially ahead here**: provenance grades A–D and the five-verdict
  verification gate are shipped code, not a README section.
- **Production architecture** (Railway, managed DB, live connectors, scheduled
  agents) is explicitly described as not present in this repo.
- **Orchestration depth.** "Conductor / Pillars / Workers" is an *organisational*
  hierarchy rendered in the UI. The runtime underneath is a `Map` registry with
  `run()` and a `Promise.all` broadcast — no planning, no delegation, no
  verification, no session continuity.
- All demo names, companies, financial figures and social numbers are placeholder.

The honest one-line summary: **FounderOS is a thick, disciplined surface over a
thin engine. ATLAS is a thick engine under a developer-shaped surface.** The
work is to give ATLAS the surface discipline without pretending the engine
comparison runs the other way.
