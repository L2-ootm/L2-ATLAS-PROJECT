# WebUI Stack Spike — SvelteKit/Svelte 5 vs Next.js/React

Date: 2026-06-06
Resolution: D-006 (WebUI framework)
Phase: 3 — Research Closure

## 1. Context and Constraints

Purpose: resolve D-006 (WebUI framework undecided).

Locked decisions constraining this spike:
- D-005 (no Electron; cockpit served from local HTTP server or FastAPI static mount — no bundled desktop runtime)
- D-007 (CRM is v2, not evaluated here)
- D-009 (STT/TTS out of scope)

The cockpit serves Phase 8 requirements COCKPIT-01 through COCKPIT-06. COCKPIT-06 (< 2s load on localhost) is a hard constraint influencing the bundle size criterion.

## 2. Candidates

Two candidates only:
- SvelteKit 2.63.0 / Svelte 5.56.2 (with @sveltejs/adapter-static 3.0.10 for non-Node deployment)
- Next.js 16.2.7 / React 19.2.7

Electron is explicitly excluded per D-005.

## 3. Scoring Criteria

Five criteria with weights:

### Criterion 1 — Realtime SSE audit stream (Weight: HIGH)

The cockpit must display a real-time audit event stream (COCKPIT-02, COCKPIT-03). Source: FastAPI's /runs/{id}/events SSE endpoint. Measure: footguns when browser EventSource connects directly to FastAPI (bypassing frontend framework server). Note the Next.js buffering issue — route handlers buffer the response until handler returns unless `dynamic = 'force-dynamic'` and `X-Accel-Buffering: no` headers are set. SvelteKit with adapter-static has no server in the SSE path at all.

### Criterion 2 — L2 code reuse (Weight: MEDIUM)

D-006 rationale notes L2 has existing Next.js muscle/code. Measure: developer familiarity, not component portability, since the cockpit is a greenfield operator UI, not a port.

### Criterion 3 — Bundle size / initial load (Weight: HIGH)

COCKPIT-06 requires < 2s load on localhost. SvelteKit compiles to vanilla JS (typical < 15 KB JS on initial page); Next.js ships React runtime (~45 KB) plus hydration bundle (~200–300 KB for a simple app). Both meet the < 2s bar on localhost, but SvelteKit has more headroom for future feature growth.

### Criterion 4 — Polish ceiling (Weight: MEDIUM)

Cockpit must feel like mission control, not generic admin CRUD. React's larger UI component ecosystem (shadcn/ui, Radix) vs Svelte's smaller ecosystem. Note Svelte 5 rune-based fine-grained reactivity advantage for dense real-time UIs (no virtual DOM reconciliation).

### Criterion 5 — Deployment model (Weight: HIGH)

D-005 mandates no Electron. Cockpit served from FastAPI StaticFiles mount (MVP) or Rust sidecar static files (v2). SvelteKit adapter-static produces pure HTML/CSS/JS. Next.js requires a Node.js server process. A third process (Node.js) alongside FastAPI + Rust sidecar adds operational complexity.

## 4. Scoring Table

| Criterion | Weight | SvelteKit/Svelte 5 | Next.js/React | Notes |
|-----------|--------|-------------------|----------------|-------|
| Realtime SSE from FastAPI | HIGH | 4 | 4 | Both work via direct browser EventSource. Next.js has documented buffering pitfall if a route handler is mistakenly used as proxy. SvelteKit adapter-static has no server to tempt proxy usage. |
| L2 code reuse | MEDIUM | 2 | 5 | L2 has existing React code and developer muscle. Cockpit is greenfield — familiarity advantage is real but bounded. |
| Bundle size / < 2s load | HIGH | 5 | 3 | SvelteKit: ~15 KB JS baseline. Next.js: ~200-300 KB. Both meet COCKPIT-06 on localhost; SvelteKit has more growth headroom. |
| Polish ceiling / operator UI | MEDIUM | 4 | 4 | React has larger component library ecosystem. Svelte 5 runes provide fine-grained reactivity ideal for dense real-time dashboards. Wash. |
| Deployment (no Node server) | HIGH | 5 | 2 | adapter-static: pure HTML/CSS/JS, no Node process. Next.js requires persistent Node server or constrained `output: 'export'`. |
| **Weighted total** | | **~4.3** | **~3.3** | HIGH-weight criteria (SSE, bundle, deployment) favor SvelteKit. |

Weighted total calculation: HIGH=3, MEDIUM=2. SvelteKit: (4×3 + 2×2 + 5×3 + 4×2 + 5×3) / (3+2+3+2+3) = 56/13 ≈ 4.3. Next.js: (4×3 + 5×2 + 3×3 + 4×2 + 2×3) / 13 = 43/13 ≈ 3.3.

## 5. Framework Recommendation

Recommendation: SvelteKit/Svelte 5 with @sveltejs/adapter-static.

SvelteKit/Svelte 5 is the stronger technical fit based on weighted scores (~4.3 vs ~3.3). The decisive criteria are:
- Deployment model (no Node.js process, D-005 compliant with adapter-static)
- Bundle size (directly addresses COCKPIT-06)

The L2 code reuse disadvantage (score 2 vs 5) is real but bounded: the cockpit is a greenfield operator UI consuming a typed API; no existing L2 React components are being ported.

Decision: D-006 locked as SvelteKit/Svelte 5.

A build spike (1-day prototype) is NOT required because the scoring criteria are objective and the performance gap is measurable from public benchmarks. However, a spike WOULD be warranted if the implementing developer has zero Svelte 5 experience and wants to validate the learning curve before Phase 8 begins.

## 6. Architecture Notes for Phase 8

Key patterns:
- Project location: apps/cockpit/
- Adapter: @sveltejs/adapter-static (pages: 'build', assets: 'build', fallback: 'index.html')
- SSE pattern: browser EventSource connects directly to FastAPI's /runs/{id}/events — do NOT proxy through SvelteKit server endpoints (adapter-static has no server; server endpoints are forbidden)
- CORS: configure FastAPI to allow http://localhost:5173 in development
- Type sharing: use model_json_schema() output from Phase 2 Pydantic models to generate TypeScript types — do not duplicate manually
- Route structure: missions/+page.svelte (COCKPIT-01, 05), missions/[id]/+page.svelte (COCKPIT-02, 03), wiki/+page.svelte (COCKPIT-04)

## 7. Security Note

The cockpit serves sensitive audit data including LLM call records and tool call payloads. Phase 8 planning MUST include ASVS V2 (authentication) and V4 (access control) for the cockpit's authentication boundary. This is out of scope for Phase 3 but is flagged here as a mandatory Phase 8 security concern.

## 8. Assumptions and Open Questions

Three assumptions from the research phase:

**A1 — L2 has meaningful React code**: D-006 rationale says "L2 has existing Next.js muscle/code." This was scored as developer familiarity, not component portability. If L2 has minimal React code, the reuse advantage for Next.js is weaker and the SvelteKit win is even clearer.

**A2 — FastAPI StaticFiles mount is the intended static serving mechanism**: The spike assumes cockpit static files are served via FastAPI's StaticFiles mount for MVP, with the Rust sidecar serving them in v2. If a different static server is planned, adapter selection advice may need adjustment.

**A3 — Next.js `output: 'export'` has meaningful constraints**: The spike assumes Next.js static export has constraints on dynamic routes that would affect cockpit routing. If Next.js export mode has improved since research, the deployment score gap may narrow — but the Node.js process requirement remains the primary disadvantage.

## 9. Sources

- npm registry: svelte 5.56.2, @sveltejs/kit 2.63.0, @sveltejs/adapter-static 3.0.10, next 16.2.7, react 19.2.7
- svelte.dev/docs/kit/adapter-static — official static adapter documentation
- github.com/sveltejs/kit — official SvelteKit repository
- github.com/vercel/next.js/discussions/48427 — Next.js SSE buffering issue
- devmorph.dev/blogs/sveltekit-vs-nextjs-16-performance-benchmarks-2026 — bundle size benchmarks
- pkgpulse.com/blog/sveltekit-vs-nextjs-2026-full-stack-comparison — framework comparison
- betterstack.com/community/guides/scaling-nodejs/sveltekit-vs-nextjs/ — framework comparison
- sveltetalk.com/posts/building-real-time-sveltekit-apps-with-server-sent-events — SSE pattern
- github.com/amirtds/svelte-fastapi-dashboard — Svelte + FastAPI SSE reference
