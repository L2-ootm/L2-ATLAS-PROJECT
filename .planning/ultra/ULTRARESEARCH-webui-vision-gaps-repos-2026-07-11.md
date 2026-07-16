# ULTRARESEARCH — WebUI Vision, Gaps & Repo Integration

**Date:** 2026-07-11
**Mode:** ultraresearch (3 parallel subagents)
**Status:** Synthesized from 3 angle-specific investigations

---

## 1. Current WebUI State (16 routes, all functional)

| Route | Component | Health |
|-------|-----------|--------|
| `/` | Dashboard | Functional — live telemetry |
| `/command` | Command | Functional — focus/goals/tasks (1055 lines) |
| `/missions` | Missions | Functional — list/create/filter |
| `/missions/:id` | MissionDetail | Functional — detail/run/archive/retry |
| `/runs` | Runs | Functional — cross-mission feed |
| `/runs/:id` | RunDetail | Functional — live SSE + audit |
| `/console` | Console | Functional — full chat (2181 lines) |
| `/graph` | Graph | Functional — 3D knowledge graph |
| `/projects` | Projects | Functional — CRUD + register |
| `/cashflow` | Cashflow | Functional — financial dashboard |
| `/audit` | Ledger | Functional — forensic audit |
| `/wiki` | Codex | Functional — wiki + FTS |
| `/models` | Models | Functional — registry + FreeLLMAPI |
| `/integrations` | Integrations | Functional — posture board |
| `/discord` | Discord | Functional — sidecar |
| `/control` | Control | Functional — settings/channels |
| `*` | Migrating | **Stub** — placeholder |

**Gateway endpoints with NO WebUI page:** VCS/git context, slash commands (/init, /review, /dream, /distill, /goal, /deep-research).

**Design system:** 6 semantic tones, 4 font families, void palette, glass surfaces, topographic field engine, SVG refraction glass, cursor-reactive border glow. No component docs, no animation tokens, no responsive breakpoints.

---

## 2. Final Product Vision

### What ATLAS WebUI is

A **celestial instrument panel** where an operator reads, steers, and audits autonomous AI work. Not a chat window with sidebars. A cockpit with gauges.

### Three-pillar information architecture

- **MISSION** — intent, execution, outcome (Command, Missions, Runs)
- **AUDIT** — traceability, forensics, compliance (Ledger)
- **STRUCTURE** — knowledge, relationships, configuration (Codex, Graphify, Projects, Models)

Chat (Console) is a surface, not the product.

### 5 Design Principles

1. **Controlled Light on Expensive Material.** Blue-temperature void backgrounds. Bronze filigree as identity-only accent. Accents are points of light (cyan, violet, celestial blue), never fog or gradient washes.
2. **Instrument, Not Decoration.** Every pixel earns its place by conveying state. HUD labels, data values, status indicators.
3. **Audit by Default.** If it happened, it is traceable. Event rows are dense and scannable, timestamps monospaced with tabular-nums.
4. **Celestial-Heraldic, Not Generic Dark Mode.** Compass stars at hairline corners. Astrolabe globes as marks. Cinzel for the wordmark. Engraved astronomical cartography, not Tailwind-default dark.
5. **Multi-Surface, One Runtime.** TUI, WebUI, and future native shell share the same session, config, events, and permission protocols.

---

## 3. TUI Parity Gaps

| TUI Feature | WebUI Status |
|-------------|--------------|
| 6 slash commands (`/init`, `/review`, `/dream`, `/distill`, `/goal`, `/deep-research`) | **Missing** — no command palette in Console |
| VCS git branch read | **Missing** — no git context displayed |
| Session busy/idle status | **Missing** — no visual indicator |
| FreeLLMAPI sidecar control | Covered |
| Provider/auth settings | Covered |
| Chat + permissions | Covered |

---

## 4. Top 5 Priority Gaps

1. **No slash command palette in Console** — TUI's 6 commands unreachable from WebUI. Add `Cmd+K` launcher.
2. **No git branch / VCS context** — Neither dashboard nor layout shows active branch.
3. **No design system docs** — 15+ custom visual components with no prop docs or Storybook.
4. **Dashboard telemetry is thin** — Missing active run cost/tokens, pending approval count, active surfaces.
5. **Settings/Control UX confusion** — Routes `/control`, `/system`, `/settings` hierarchy unclear.

---

## 5. Repo Integration — New WebUI Surfaces

| Rank | Repo | New Surface | Impact | Feasibility |
|------|------|-------------|--------|-------------|
| 1 | **codebase-memory-mcp** (30.2k) | Architecture Explorer, Impact Analysis, Dependency Health, Cross-Service Map | Very High | High |
| 2 | **OmniRoute** (15.7k) | Provider Health Dashboard, Cost Tracker, Model Comparison, Routing Rules Editor | High | Medium |
| 3 | **page-agent** (26.1k) | Automation Replay Viewer, Page State Inspector, Screenshot Gallery | High | Medium |
| 4 | **emilkowalski/skills** (10.1k) | Design Audit Dashboard, Animation Review, Apple HIG Compliance Score | Medium | High |
| 5 | **meetily** (23.2k) | Meeting Timeline, Action Item Extractor, Meeting Summary Card | Medium | Low (v2.0) |

### Key insight: codebase-memory-mcp has a built-in graph-ui directory — ATLAS could embed or fork its 3D visualization for the Architecture Explorer surface. This is the highest-impact, highest-feasibility integration.

---

## 6. Recommended WebUI Evolution Path

### Phase A: Parity (next session)
- Add `Cmd+K` command palette to Console (6 TUI commands)
- Show git branch in Layout sidebar
- Clean up Settings/Control hierarchy

### Phase B: Design differentiation (v1.2)
- Apply L2 Dark Prism tokens to TUI (already planned for atlas-terminal visual polish)
- Add animation token set to WebUI (from emilkowalski skills)
- Build component documentation (Storybook or inline MDX)

### Phase C: Unique surfaces (v1.2–v1.3)
- Architecture Explorer (codebase-memory-mcp integration)
- Provider Health Dashboard (OmniRoute integration)
- Dashboard enrichment (active run cost, pending approvals, active surfaces)

### Phase D: Advanced surfaces (v2.0)
- Automation Replay (page-agent)
- Meeting Intelligence (meetily)
- Full routing rules editor (OmniRoute)

---

*Research complete. 3 subagents, 3 angles, synthesized into unified vision.*
