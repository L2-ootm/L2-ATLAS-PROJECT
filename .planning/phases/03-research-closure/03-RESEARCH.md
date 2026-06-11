# Phase 3: Research Closure — WebUI Spike & CRM Intake - Research

**Researched:** 2026-06-05
**Domain:** Frontend framework selection (SvelteKit/Svelte 5 vs Next.js/React) + CRM/Pulse/Channels v2 scoping
**Confidence:** HIGH (WebUI criteria), MEDIUM (CRM open questions)

> Supersession note (2026-06-11): every "FastAPI" reference below is
> historical. D-022 makes the Phase 7 gateway a Rust binary (axum +
> rusqlite); read "FastAPI" as "the ATLAS Rust gateway". The SvelteKit /
> adapter-static / EventSource conclusions remain valid — the cockpit talks
> to the same REST+SSE contract regardless of gateway implementation.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-005 (locked): Desktop/native layer is Rust-first, no Electron. WebUI spike must NOT evaluate Electron.
- D-007 (locked): CRM is NOT first implementation surface — research scopes it for v2, not v1.
- D-009 (locked): STT/TTS/overlay is not a first MVP blocker — do not scope it into this research.
- D-005 means the cockpit will be served from a local HTTP server or remote — account for this in WebUI comparison.

### Claude's Discretion
- Framework recommendation within {SvelteKit/Svelte 5, Next.js/React} — both are in scope.
- Document structure and scoring methodology for WEBUI_STACK_SPIKE.md.
- Open question taxonomy for CRM_PULSE_CHANNELS_DEEP_DIVE.md.
- Specific patch wording for NATIVE_APP_STRATEGY.md C3 inconsistency.

### Deferred Ideas (OUT OF SCOPE)
- CRM implementation details, schema, or v1 feature set.
- STT/TTS/overlay research (D-009).
- Electron as a bundling path (D-005).
- Rust native sidecar implementation details.
- Multi-tenant SaaS, billing, Postgres (post-dogfood only).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RESEARCH-01 | WebUI stack spike document comparing SvelteKit/Svelte 5 vs Next.js/React against cockpit requirements, ending in a concrete recommendation (resolves D-006) | Framework versions verified via npm registry; SSE/realtime patterns researched via WebSearch + official docs; deployment adapter options confirmed; scoring criteria derived from COCKPIT requirements |
| RESEARCH-02 | CRM/Pulse/Channels deep-dive research document with open questions and MVP boundary defined | CRM architecture patterns researched; existing backlog items R5/R6/R7 from DEEP_RESEARCH_BACKLOG.md synthesized; v2 scope boundary derived from D-007 and priority order in decision register |
</phase_requirements>

---

## Summary

Phase 3 is a pure documentation/research phase — no application code. It produces two research documents and patches one architecture document. The work is writing-heavy and decision-oriented, not implementation-heavy.

**RESEARCH-01 (D-006 resolution):** The WebUI spike document must compare SvelteKit/Svelte 5 against Next.js/React on five concrete cockpit criteria. Research shows the frameworks have meaningfully different performance profiles and SSE ergonomics. SvelteKit/Svelte 5 has a clear technical edge for this use case (smaller bundles, simpler SSE, no Next.js buffering pitfalls, cleaner deployment model for a Rust-served backend). The decision can be made by document comparison alone — no build spike required — because the criteria are well-defined and the performance gap on bundle size/load time is objectively measurable from public benchmarks. The planner should create a task that writes WEBUI_STACK_SPIKE.md with a scored table and a concrete recommendation.

**RESEARCH-02 (D-010 closure):** The CRM/Pulse/Channels intake is a scoping exercise, not an implementation design. The DEEP_RESEARCH_BACKLOG.md already defines R5 (Pulse), R6 (CRM/Twenty), and R7 (WhatsApp/Channels) as open questions. The deep-dive document must capture: what is known from prior research, what is not known and why it matters, and a defensible MVP boundary that keeps these features in v2 without leaving the decision space undefined. The planner should create a task that writes this document from existing project knowledge plus the framework established by this research.

**C3 inconsistency patch:** `docs/architecture/NATIVE_APP_STRATEGY.md` line 16 currently reads "Next.js or similarly excellent web stack" in the WebUI preferred stack table. This must be updated to reflect D-006's open status (or the post-spike recommendation once D-006 is resolved). The patch is a single-line edit; plan it as a dependent task after the spike document is complete and D-006 is resolved.

**Primary recommendation:** Write WEBUI_STACK_SPIKE.md first (it resolves D-006), then update D-006 in the decision register, then patch NATIVE_APP_STRATEGY.md, then write CRM_PULSE_CHANNELS_DEEP_DIVE.md. All tasks are independent of each other except the NATIVE_APP_STRATEGY.md patch, which should run after D-006 is resolved.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Realtime audit event stream (COCKPIT-02) | Browser / Client | API / Backend (FastAPI SSE source) | Browser EventSource consumes SSE from FastAPI; no SSR needed for streaming |
| Mission list / status display (COCKPIT-01) | Frontend Server (SSR optional) | Browser / Client | Static-renderable on load; hydration handles updates |
| Wiki browser + search (COCKPIT-04) | Browser / Client | API / Backend | Client-side fetch from FastAPI wiki endpoints |
| Mission create form (COCKPIT-05) | Browser / Client | API / Backend | POST to FastAPI; no SSR form action required |
| Initial page load performance (COCKPIT-06, < 2s) | CDN / Static | Browser / Client | Served from local HTTP (Rust sidecar or FastAPI static mount); bundle size is the lever |
| Framework selection decision | — | — | Scope of this phase |
| CRM/Pulse v2 scoping | — | — | Document only; no tier assignment yet |

---

## Standard Stack

### RESEARCH-01: WebUI Framework Candidates

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| svelte | 5.56.2 [VERIFIED: npm registry] | UI compiler + reactivity | Ships vanilla JS; no runtime framework overhead |
| @sveltejs/kit | 2.63.0 [VERIFIED: npm registry] | Full-stack framework on top of Svelte | File-based routing, server endpoints, adapters |
| @sveltejs/adapter-static | 3.0.10 [VERIFIED: npm registry] | Build to static HTML/CSS/JS for non-Node servers | Required when serving from Rust backend or FastAPI static mount |
| @sveltejs/adapter-node | 5.5.4 [VERIFIED: npm registry] | Build to Node.js server (optional if Node.js is acceptable) | Alternative to adapter-static if a Node server is tolerable |
| next | 16.2.7 [VERIFIED: npm registry] | React full-stack framework (alternative candidate) | Dominant React meta-framework; existing L2 muscle |
| react | 19.2.7 [VERIFIED: npm registry] | UI library (alternative candidate) | Powers Next.js; 13M weekly downloads |

### Supporting (SvelteKit path)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| vite | (bundled in @sveltejs/kit) | Dev server + build tool | Included automatically via SvelteKit |
| TypeScript | (project choice) | Type safety | Svelte 5 has first-class TS support |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SvelteKit | Next.js/React | Larger bundle; more hiring pool; more React component libraries; SSE has documented buffering pitfalls; Vercel-optimized by default |
| adapter-static | adapter-node | Node server adds a dependency but enables SvelteKit server-side load functions for data fetching |

**Installation (SvelteKit path):**
```bash
npm create svelte@latest apps/cockpit
cd apps/cockpit && npm install
npm install -D @sveltejs/adapter-static  # if serving from Rust/FastAPI static mount
```

**Installation (Next.js path):**
```bash
npx create-next-app@latest apps/cockpit --typescript
```

---

## Package Legitimacy Audit

> slopcheck was unavailable at research time. All packages verified via npm registry existence and official source repos. Tag: [ASSUMED] does not apply here — all packages confirmed via authoritative registries and official GitHub organizations.

| Package | Registry | Age | Source Repo | Disposition |
|---------|----------|-----|-------------|-------------|
| svelte | npm | ~8 yrs (2016) | github.com/sveltejs/svelte | Approved |
| @sveltejs/kit | npm | ~4 yrs (2021) | github.com/sveltejs/kit | Approved |
| @sveltejs/adapter-static | npm | ~4 yrs | github.com/sveltejs/kit (monorepo) | Approved |
| @sveltejs/adapter-node | npm | ~4 yrs | github.com/sveltejs/kit (monorepo) | Approved |
| next | npm | ~9 yrs (2016) | github.com/vercel/next.js | Approved |
| react | npm | ~11 yrs (2015) | github.com/facebook/react | Approved |
| react-dom | npm | ~11 yrs (2015) | github.com/facebook/react | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was not available in this environment. All packages were verified by npm registry existence (`npm view <pkg> version`) and confirmed via official GitHub organizations (sveltejs, vercel, facebook). Download volumes (Svelte: ~5M/wk, Next.js: ~6.5M/wk, React: ~13M/wk) further confirm legitimacy. [ASSUMED] tag not required — all established, well-documented packages.*

---

## Architecture Patterns

### System Architecture Diagram

```
Operator Browser
  │
  ├── GET /  → static HTML/JS (served by FastAPI or Rust sidecar static mount)
  │
  ├── fetch() → FastAPI REST endpoints
  │     └── GET /runs/{id}/events  (SSE stream)
  │           └── EventSource in browser → incremental AuditEvent rows
  │
  └── fetch() → GET /missions, POST /missions, GET /wiki/pages, etc.
                 └── FastAPI Phase 7 API Gateway
```

**Deployment topology (no Electron, D-005):**

```
[Rust sidecar process]
  ├── spawns FastAPI (uvicorn)     → port 8000
  ├── serves cockpit static files  → port 8001 (or FastAPI mounts /static)
  └── IPC channel (future v2)

[Browser]
  └── http://localhost:8001  →  cockpit static HTML/JS
                                  └── fetch/EventSource → http://localhost:8000
```

Two valid deployment topologies for local-only serving:
1. FastAPI serves both API and static cockpit files from a single port (simplest for MVP).
2. Rust sidecar serves static files on a separate port; FastAPI is pure API. (Better separation; required later for v2 native features.)

### Recommended Project Structure

```
apps/cockpit/
├── src/
│   ├── lib/
│   │   ├── api.ts          # typed wrappers over FastAPI endpoints
│   │   └── eventStream.ts  # EventSource wrapper for SSE audit stream
│   ├── routes/
│   │   ├── +layout.svelte  # nav shell
│   │   ├── missions/
│   │   │   ├── +page.svelte        # mission list (COCKPIT-01, COCKPIT-05)
│   │   │   └── [id]/
│   │   │       └── +page.svelte    # run detail + audit stream (COCKPIT-02, COCKPIT-03)
│   │   └── wiki/
│   │       └── +page.svelte        # wiki browser (COCKPIT-04)
├── static/
├── svelte.config.js         # adapter-static or adapter-node
└── package.json
```

### Pattern 1: SSE Audit Stream in SvelteKit (Client-side EventSource)

**What:** Browser opens an EventSource to FastAPI's `/runs/{id}/events` endpoint. No SvelteKit server involved — the browser connects directly to FastAPI.

**When to use:** When the realtime stream source is FastAPI (not SvelteKit's own server). This is the correct pattern for ATLAS (FastAPI backend, SvelteKit as pure frontend).

```typescript
// Source: SvelteKit docs + FastAPI SSE docs pattern
// apps/cockpit/src/lib/eventStream.ts

export function connectAuditStream(runId: string, onEvent: (event: AuditEvent) => void) {
  const source = new EventSource(`http://localhost:8000/runs/${runId}/events`);
  source.onmessage = (e) => {
    onEvent(JSON.parse(e.data) as AuditEvent);
  };
  source.onerror = () => source.close();
  return () => source.close(); // cleanup fn
}
```

```svelte
<!-- apps/cockpit/src/routes/missions/[id]/+page.svelte -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { connectAuditStream } from '$lib/eventStream';
  import type { AuditEvent } from '$lib/types';

  let { data } = $props();
  let events = $state<AuditEvent[]>([]);
  let disconnect: () => void;

  onMount(() => {
    disconnect = connectAuditStream(data.runId, (ev) => {
      events = [...events, ev];
    });
  });
  onDestroy(() => disconnect?.());
</script>
```

### Pattern 2: SvelteKit adapter-static for Rust/FastAPI serving

**What:** Build cockpit to pure HTML/CSS/JS with no Node.js server dependency. FastAPI or Rust sidecar serves the files as static assets.

**When to use:** MVP local deployment where no Node.js process should be running in production.

```javascript
// Source: SvelteKit official docs — adapter-static
// apps/cockpit/svelte.config.js
import adapter from '@sveltejs/adapter-static';

export default {
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: 'index.html'  // SPA fallback for client-side routing
    })
  }
};
```

```python
# In FastAPI Phase 7 app — serve cockpit static files
# Source: FastAPI static files docs [ASSUMED pattern]
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="apps/cockpit/build", html=True), name="cockpit")
```

### Pattern 3: Next.js SSE — known buffering issue

**What:** Next.js App Router SSE requires explicit `dynamic = 'force-dynamic'` and `X-Accel-Buffering: no` headers to prevent route handler buffering. Failure to set these causes events to be batched and delivered late.

**When relevant:** If Next.js is chosen, every SSE route handler needs this boilerplate. Since ATLAS proxies SSE from FastAPI (no Next.js route handler needed for pure frontend), this pitfall is less severe — but it appears in tutorials and could be mistakenly applied.

**Correct ATLAS pattern with Next.js:** Use the browser's native `EventSource` pointed at `http://localhost:8000/runs/{id}/events` directly. Do NOT proxy through a Next.js route handler.

### Anti-Patterns to Avoid

- **Proxying SSE through the frontend framework's server:** Adds latency, requires careful buffering headers (Next.js), loses benefits of direct FastAPI SSE. Connect browser EventSource directly to FastAPI.
- **Using Electron as a packaging mechanism:** Violates D-005. The cockpit is served from a local HTTP server or remote; no Electron.
- **Adding a Node.js server process for production:** If using adapter-static, the build output is self-contained HTML/CSS/JS. No Node.js server needed unless adapter-node is explicitly chosen.
- **Installing a React component library for the cockpit:** Adds significant bundle weight. SvelteKit's smaller runtime makes a bespoke operator UI achievable without a component library for v1.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE client reconnection logic | Custom EventSource wrapper with exponential backoff | Browser native EventSource | Native EventSource already handles reconnection; custom wrappers add bugs |
| File-based routing | Manual router | SvelteKit's built-in routing | SvelteKit routes are just files; zero config needed |
| Build tooling | Custom webpack/rollup config | Vite (bundled in SvelteKit) | Vite is already configured; no custom build setup needed |
| TypeScript + Svelte integration | Manual tsconfig | `npx sv create` scaffolding | Generates correct tsconfig for Svelte 5 runes |
| API type sharing | Manual type duplication | `model_json_schema()` output from Phase 2 | Phase 2 Pydantic models emit JSON Schema; use that to generate TypeScript types |

**Key insight:** The cockpit is a frontend consuming a typed API. The entire stack reduces to: SvelteKit routes → typed fetch calls → FastAPI → SQLite. The domain complexity lives in Phase 4–7, not in the cockpit framework.

---

## Common Pitfalls

### Pitfall 1: Next.js SSE Buffering
**What goes wrong:** EventSource events arrive in batches instead of individually; run detail page appears to hang then update all at once.
**Why it happens:** Next.js App Router route handlers buffer the response until the handler function returns. `export const dynamic = 'force-dynamic'` and correct ReadableStream return pattern are required.
**How to avoid:** In ATLAS, browser EventSource connects directly to FastAPI — no Next.js route handler is in the path. If a Next.js API route is ever added for SSE, apply the buffering fix.
**Warning signs:** Audit events arrive in batches; delay between emission and display.

### Pitfall 2: SvelteKit adapter-static + server endpoints
**What goes wrong:** SvelteKit server endpoints (files named `+server.ts`) do not exist after a static build. The build fails or endpoints return 404 at runtime.
**Why it happens:** adapter-static prerenders everything to HTML/CSS/JS; there is no server to handle server endpoints.
**How to avoid:** With adapter-static, all data fetching must use client-side `fetch()` to the FastAPI backend. Do not create `+server.ts` endpoints in the cockpit — they belong in FastAPI (Phase 7).
**Warning signs:** `npm run build` errors about "server-only modules"; 404 on endpoint routes.

### Pitfall 3: CORS between SvelteKit dev server and FastAPI
**What goes wrong:** `EventSource` and `fetch()` calls fail with CORS errors in development when SvelteKit dev server runs on port 5173 and FastAPI on port 8000.
**Why it happens:** Browsers block cross-origin requests unless the server sets CORS headers.
**How to avoid:** Configure FastAPI CORS middleware to allow `http://localhost:5173` in development. In production (static build served from same origin), CORS is not an issue.
**Warning signs:** Console errors: "CORS policy: No 'Access-Control-Allow-Origin' header".

### Pitfall 4: D-006 inconsistency propagating forward
**What goes wrong:** Future planning tasks reference a specific WebUI framework before D-006 is resolved, creating accidental lock-in.
**Why it happens:** NATIVE_APP_STRATEGY.md already contains "Next.js" in the preferred stack table (C3 inconsistency). If left unpatched, it reads as a decision.
**How to avoid:** The NATIVE_APP_STRATEGY.md patch is a hard dependency before any Phase 8 planning begins. Plan it as a task within this phase.
**Warning signs:** NATIVE_APP_STRATEGY.md line 16 still reads "Next.js or similarly excellent web stack" after this phase closes.

### Pitfall 5: CRM intake becoming implementation design
**What goes wrong:** CRM_PULSE_CHANNELS_DEEP_DIVE.md drifts into schema design, API surface definition, or v1 feature decisions — violating D-007.
**Why it happens:** It is tempting to answer CRM questions by designing the solution.
**How to avoid:** The document must end with open questions + MVP boundary, not with answers. The research brief is the product, not the design.
**Warning signs:** The document contains table DDL, API endpoint definitions, or v1 feature flags.

---

## Code Examples

### C3 Inconsistency: Exact Line to Patch

```markdown
# CURRENT (line 16 of docs/architecture/NATIVE_APP_STRATEGY.md):
| WebUI | perfect cockpit/dashboard | Next.js or similarly excellent web stack |

# PATCH (after D-006 is resolved):
| WebUI | perfect cockpit/dashboard | [framework per D-006 spike] |

# OR (if patching before spike completes):
| WebUI | perfect cockpit/dashboard | TBD — see D-006 (spike in Phase 3) |
```

### D-006 Format in Decision Register

Current entry structure (from `docs/decisions/2026-06-04_DECISION_REGISTER.md`):

```markdown
## D-006 — WebUI framework not locked yet

Decision: WebUI framework remains undecided between SvelteKit/Svelte 5 and Next.js/React.
...
Status: open.

Required next action:
- create `docs/research/WEBUI_STACK_SPIKE.md` comparing SvelteKit vs Next.js.
```

After this phase, update to:

```markdown
## D-006 — WebUI framework

Decision: [SvelteKit/Svelte 5 | Next.js/React] — per WEBUI_STACK_SPIKE.md.

Status: locked.

See: docs/research/WEBUI_STACK_SPIKE.md
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Svelte 4 reactive declarations (`$:`) | Svelte 5 runes (`$state`, `$derived`, `$effect`) | Oct 2024 | Explicit reactivity; no magic assignments; better TypeScript inference |
| SvelteKit `load()` returning stores | SvelteKit + Svelte 5 `$props()` in components | Svelte 5 GA | Components receive data as typed props; no writable stores from load |
| Next.js Pages Router | Next.js App Router (stable since Next 13) | 2023 | RSC by default; SSE requires explicit `ReadableStream` return pattern |
| create-react-app | Vite + React or Next.js | 2023 (CRA deprecated) | No CRA in 2026 — all new React projects use Vite or Next.js |
| Tauri 1.x | Tauri 2.x (mobile support, improved security) | Late 2024 | Relevant if Tauri is chosen as thin shell for cockpit (D-005 allows as last resort) |

**Deprecated/outdated:**
- `create-react-app`: officially deprecated; do not use for Phase 8 if Next.js is chosen.
- Svelte 4 `{#await}` + store patterns: still work but Svelte 5 runes are the forward path.
- SvelteKit `invalidate()` for SSE simulation: use native EventSource instead.

---

## RESEARCH-01 Pre-Analysis: Framework Comparison Scoring

> This section gives the planner the factual basis for the scored comparison document. The spike document (WEBUI_STACK_SPIKE.md) will elaborate these into a full table.

### Criterion 1: Realtime Audit Stream (SSE/WebSocket from FastAPI)

**SvelteKit:** Browser EventSource connects directly to FastAPI. SvelteKit's server is not in the SSE path when using adapter-static. Clean pattern, no buffering issues, no special configuration. [CITED: sveltetalk.com/posts/building-real-time-sveltekit-apps-with-server-sent-events, github.com/amirtds/svelte-fastapi-dashboard]

**Next.js:** Browser EventSource also connects directly to FastAPI — Next.js server is not in the SSE path. However, Next.js SSE documentation and community examples frequently introduce a Next.js route handler as an SSE proxy, creating the buffering pitfall. Risk of a future developer adding a route handler and introducing the bug. The direct-to-FastAPI pattern works correctly. [CITED: github.com/vercel/next.js/discussions/48427]

**Edge:** SvelteKit is cleaner — fewer footguns, no proxy temptation. Tie if both teams understand the direct-to-FastAPI pattern.

### Criterion 2: L2 Code Reuse

**SvelteKit:** L2 has existing Next.js/React code. SvelteKit components are not reusable with React. Rewrite cost applies.
**Next.js:** Existing L2 React components, hooks, and API wrapper patterns can be ported with lower friction.

**Edge:** Next.js wins on existing muscle memory. Quantify as: existing L2 React code is portable; existing L2 Svelte code is minimal or nonexistent. [ASSUMED — based on D-006 rationale in decision register citing "L2 has existing Next.js muscle/code"]

### Criterion 3: Bundle Size / Initial Load (COCKPIT-06: < 2s)

**SvelteKit/Svelte 5:** Compiles to vanilla JS; no runtime framework shipped. Typical bundle 30-65% smaller than equivalent Next.js. A static SvelteKit landing page commonly delivers under 15 KB of JS. [CITED: devmorph.dev/blogs/sveltekit-vs-nextjs-16-performance-benchmarks-2026, pkgpulse.com/blog/sveltekit-vs-nextjs-2026-full-stack-comparison]

**Next.js/React:** React runtime is ~45 KB before any application code. Next.js baseline bundle (with RSC hydration) is typically 200-300 KB for a simple app. [CITED: betterstack.com/community/guides/scaling-nodejs/sveltekit-vs-nextjs/]

**Edge:** SvelteKit wins clearly. For a local-served cockpit where < 2s initial load is a hard requirement (COCKPIT-06), SvelteKit's compiler advantage is directly relevant. The 2s target is easily met by both on localhost, but SvelteKit has more headroom for future feature growth without degrading load time.

### Criterion 4: Polish Ceiling (Operator-grade UI)

**SvelteKit:** Svelte 5 runes provide fine-grained reactivity ideal for dense dashboards. Smaller community component library ecosystem than React, but operator-grade UIs typically require bespoke components anyway. CSS scoping is built-in.

**Next.js:** React has the largest component library ecosystem (shadcn/ui, Radix, etc.). For an operator cockpit, this is less relevant than it would be for a consumer app — bespoke components are expected.

**Edge:** Slight Next.js/React advantage on available UI primitives if shadcn/ui or Radix is desired. Slight SvelteKit advantage on reactive performance for dense real-time event lists (no virtual DOM reconciliation).

### Criterion 5: Deployment Model (no Electron, D-005)

**SvelteKit:** `adapter-static` produces pure HTML/CSS/JS servable by any HTTP server — including FastAPI's `StaticFiles` mount or a Rust sidecar. No Node.js process required in production. [CITED: svelte.dev/docs/kit/adapter-static]

**Next.js:** Requires a Node.js server process (or Vercel edge). No equivalent of adapter-static for a pure static export that supports dynamic routes correctly. `next export` has been removed; `output: 'export'` exists but with constraints on dynamic routes and image optimization. [ASSUMED — based on Next.js docs; verify if `output: 'export'` covers all cockpit routes]

**Edge:** SvelteKit wins clearly for this deployment model. Serving from FastAPI static mount or Rust sidecar without a Node.js process is straightforward with adapter-static. Next.js requires a persistent Node.js server — a third process alongside FastAPI and the Rust sidecar.

### Summary Scoring (1–5, 5 = better for ATLAS cockpit)

| Criterion | SvelteKit/Svelte 5 | Next.js/React | Weight |
|-----------|-------------------|----------------|--------|
| Realtime SSE from FastAPI | 4 | 4 | HIGH |
| L2 code reuse | 2 | 5 | MEDIUM |
| Bundle size / < 2s load | 5 | 3 | HIGH |
| Polish ceiling / operator UI | 4 | 4 | MEDIUM |
| Deployment (no Node server) | 5 | 2 | HIGH |
| **Weighted total** | **~4.3** | **~3.3** | |

**Research conclusion for the spike document:** SvelteKit/Svelte 5 is the stronger technical fit. The deployment model advantage (no Node.js process required) is decisive given D-005. The bundle size advantage directly addresses COCKPIT-06. The L2 code reuse disadvantage is real but bounded — the cockpit is a greenfield UI consuming a typed API, not a port of existing L2 React code.

**Whether a build spike is needed:** A build spike (1-day prototype) would answer: "How long does it take an L2 developer unfamiliar with Svelte 5 to build the mission list + EventSource audit stream pages?" The document comparison can make a framework recommendation without the build spike; the spike would only be needed if the team has zero Svelte experience and wants to validate learning curve before committing. Include this decision gate in WEBUI_STACK_SPIKE.md.

---

## RESEARCH-02 Pre-Analysis: CRM/Pulse/Channels Scope

### What Is Known from Prior Research

From `docs/research/2026-06-04_RESEARCH_SYNTHESIS.md` and `DEEP_RESEARCH_BACKLOG.md`:

**CRM (R6):**
- Research recommends NOT forking Twenty CRM.
- Start with minimal AI-native CRM primitives: Contact, Organization, Opportunity, linked to wiki/missions.
- Twenty CRM 2.0 architecture reference: MCP server native, TypeScript SDK, PostgreSQL — too heavy for ATLAS v1 SQLite stack. [CITED: twenty.com, productcool.com/product/twenty-2-0]
- Core data model minimum: Contact (name, email, org, notes, mission_ids), Organization (name, contacts), Opportunity (org, status, value, mission_ids).

**Pulse (R5):**
- Pulse = periodic briefing: repo state, inboxes, deadlines, wiki health.
- Heartbeat monitors on cron → emit AuditEvents.
- Depends on: AuditEvent bus (Phase 4), Wiki runtime (Phase 6), Mission/Run lifecycle (Phase 5).
- Pulse cannot be scoped for v1 because its inputs (audit stream, wiki) do not exist until Phase 6.

**Channels (R7 — WhatsApp/Discord/other):**
- L2-BOT has Discord/channel management patterns. [CITED: DEEP_RESEARCH_BACKLOG.md R7]
- WhatsApp has ToS risk — any integration requires explicit decision on API path (official Meta API vs. unofficial Baileys).
- Listed as "too risky before runtime is proven" in REQUIREMENTS.md out-of-scope section.
- Channels research must answer: which path is ToS-safe, what approval flow is required for outbound messages, and how conversations are logged without privacy violation.

### Open Questions for CRM_PULSE_CHANNELS_DEEP_DIVE.md

The document must surface and structure these questions — not answer them:

**CRM open questions:**
1. Should ATLAS CRM link to missions by mission_id FK, or should CRM entities be wiki pages with a `crm:` namespace?
2. What is the minimum viable Contact schema that doesn't constrain future extension (Twenty-style metadata fields)?
3. Should CRM records be audited via the AuditEvent bus, or have a separate change log?
4. Does ATLAS CRM need duplicate detection at v2, or is that post-v2?
5. What import path enables populating the CRM from existing contacts (CSV, Google Contacts, vCard)?

**Pulse open questions:**
1. What exactly triggers a Pulse briefing — time schedule, mission completion, or explicit request?
2. What is the output format: markdown wiki page, push notification, CLI print, or all three?
3. What data sources does Pulse aggregate: wiki freshness, open missions, calendar (if integrated), repo state?
4. How does Pulse interact with the audit stream — does it produce AuditEvents, consume them, or both?

**Channels open questions:**
1. Which messaging channels are in v2 scope: WhatsApp only, Discord only, or both?
2. For WhatsApp: official Meta Business API vs unofficial client library — which is ToS-safe for the target use case?
3. What is the approval flow for outbound channel messages — does every message require human approval or only first contact?
4. How are channel conversations stored: as wiki pages, as AuditEvents, or in a separate channels table?
5. What privacy model governs conversation storage and retention?

### MVP Boundary for v2

**In scope for v2:**
- CRM: Contact + Organization + Opportunity models in SQLite with AuditEvent linkage (CRM-01, CRM-02 from REQUIREMENTS.md Future section).
- Pulse: periodic briefing of repo state + wiki health (PULSE-01, PULSE-02).
- Channels: one channel integration (TBD which) with explicit human-approval gate for outbound.

**Out of scope for v2:**
- Multi-tenant CRM, billing linkage, Postgres migration.
- More than one channel integration simultaneously.
- Automated outbound messaging without approval.
- Full WhatsApp conversation history import.

---

## Environment Availability

> Phase 3 is docs-only (no code execution). The only environment requirement is a text editor and git. No external service availability check required.

| Dependency | Required By | Available | Notes |
|------------|------------|-----------|-------|
| git | All doc writes + commits | Yes | Active repo |
| Text editor / Write tool | Document creation | Yes | Claude Write tool |
| npm view | Package version verification | Yes | Used during research |

**No blocking dependencies.**

---

## Validation Architecture

> Phase 3 produces documentation only. There is no application code to test. Validation is structural (file existence + content completeness), not automated test execution.

### Phase Requirements → Validation Map

| Req ID | Behavior | Test Type | Validation |
|--------|----------|-----------|------------|
| RESEARCH-01 | WEBUI_STACK_SPIKE.md exists with scored comparison + concrete recommendation | Manual verification | File exists at `docs/research/WEBUI_STACK_SPIKE.md`; contains scored table; ends with recommendation or spike definition |
| RESEARCH-01 | D-006 updated in decision register | Manual verification | `docs/decisions/2026-06-04_DECISION_REGISTER.md` D-006 section reads "Status: locked" or "spike required" |
| RESEARCH-01 | NATIVE_APP_STRATEGY.md C3 patched | Manual diff | Line 16 no longer reads "Next.js or similarly excellent web stack" |
| RESEARCH-02 | CRM_PULSE_CHANNELS_DEEP_DIVE.md exists with open questions + MVP boundary | Manual verification | File exists at `docs/research/CRM_PULSE_CHANNELS_DEEP_DIVE.md`; contains open questions section; contains MVP boundary section; contains no DDL or API endpoint definitions |

### Wave 0 Gaps
None — no test infrastructure is needed for a documentation phase.

---

## Security Domain

> security_enforcement is enabled. Phase 3 is a documentation/research phase. No code is written; no user input is processed; no authentication or cryptographic operations are performed. ASVS categories are not applicable to documentation authoring tasks.

| ASVS Category | Applies | Rationale |
|---------------|---------|-----------|
| V2 Authentication | No | No auth surfaces introduced |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | No access control surfaces |
| V5 Input Validation | No | No user input |
| V6 Cryptography | No | No cryptographic operations |

**Security note for WEBUI_STACK_SPIKE.md:** The spike document should note that the cockpit serves sensitive audit data. Phase 8 planning must include ASVS V2/V4 for the cockpit's authentication boundary. This is out of scope for Phase 3 but should be flagged as a Phase 8 security concern in the spike document.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | L2 has existing Next.js/React code ("L2 existing Next.js muscle/code") | Framework Comparison — L2 Code Reuse | If L2 has minimal React code, the reuse advantage for Next.js is weaker; SvelteKit win is clearer |
| A2 | FastAPI's `StaticFiles` mount is the intended static serving mechanism for MVP | Deployment Pattern | If a different static server is planned, adapter selection advice may need adjustment |
| A3 | `next export` / `output: 'export'` has meaningful constraints on dynamic routes that affect cockpit routing | Framework Comparison — Deployment | If Next.js export mode has improved, the deployment score gap may narrow |

**If this table is empty:** It is not — three assumptions remain. A1 should be confirmed by checking the L2 codebase; A2 and A3 should be verified when writing the spike document.

---

## Open Questions

1. **Does L2 have meaningful React component code that would transfer to the cockpit?**
   - What we know: D-006 rationale says "L2 has existing Next.js muscle/code" but does not quantify.
   - What's unclear: Whether this means reusable components or just developer familiarity.
   - Recommendation: The spike document author should grep the L2 codebase for React components before scoring the "L2 code reuse" criterion.

2. **Will the cockpit be served from the same port as FastAPI, or a separate static server?**
   - What we know: D-005 says no Electron; local HTTP server is the stated model.
   - What's unclear: Whether FastAPI serves static files or a separate process (Rust sidecar) does.
   - Recommendation: Default to FastAPI `StaticFiles` mount for MVP (simplest); document the Rust sidecar path as the v2 architecture.

3. **What is the CRM record linkage model — FK to missions or wiki namespace?**
   - What we know: CRM-01/CRM-02 in requirements say "audit trail linkage" and "linkable to missions."
   - What's unclear: Whether this means mission_id FK column or wiki-page-based entity representation.
   - Recommendation: The CRM_PULSE_CHANNELS_DEEP_DIVE.md should explicitly list this as an open question with both options documented.

---

## Sources

### Primary (HIGH confidence)
- `docs/decisions/2026-06-04_DECISION_REGISTER.md` — D-001 through D-013 (project decisions)
- `docs/architecture/NATIVE_APP_STRATEGY.md` — C3 inconsistency location confirmed (line 16)
- `docs/research/DEEP_RESEARCH_BACKLOG.md` — R5, R6, R7 scope definitions
- `docs/research/2026-06-04_RESEARCH_SYNTHESIS.md` — cross-report CRM/Pulse/Channels state
- npm registry (`npm view svelte version`, `npm view @sveltejs/kit version`, etc.) — verified current versions
- svelte.dev/docs/kit/adapter-static — static adapter documentation [CITED]
- github.com/sveltejs/kit (official repo) — confirmed package legitimacy

### Secondary (MEDIUM confidence)
- devmorph.dev/blogs/sveltekit-vs-nextjs-16-performance-benchmarks-2026 — bundle size benchmarks [cited, publication date confirms 2026]
- pkgpulse.com/blog/sveltekit-vs-nextjs-2026-full-stack-comparison — framework comparison
- betterstack.com/community/guides/scaling-nodejs/sveltekit-vs-nextjs/ — framework comparison
- github.com/vercel/next.js/discussions/48427 — Next.js SSE buffering issue (official repo discussion)
- sveltetalk.com/posts/building-real-time-sveltekit-apps-with-server-sent-events — SSE pattern
- github.com/amirtds/svelte-fastapi-dashboard — Svelte + FastAPI SSE reference implementation

### Tertiary (LOW confidence — for awareness only)
- npmtrends.com download counts (not fetched directly; referenced from WebSearch summary)
- twenty.com architecture description (from WebSearch summary; not fetched directly)

---

## Metadata

**Confidence breakdown:**
- Standard stack (framework versions): HIGH — verified via npm registry
- Framework comparison scoring: MEDIUM-HIGH — performance claims from multiple concordant sources; L2 code reuse score is ASSUMED
- Architecture patterns: HIGH — SSE patterns from official FastAPI + SvelteKit docs; adapter-static from official SvelteKit docs
- CRM/Pulse/Channels open questions: MEDIUM — derived from existing project research docs; no external CRM architecture source fetched
- Pitfalls: HIGH — Next.js SSE buffering from official repo discussion; adapter-static server endpoint issue from official docs

**Research date:** 2026-06-05
**Valid until:** 2026-09-05 (stable frameworks; SvelteKit 3 is in next-channel, not latest; Next.js 17 not yet released)
