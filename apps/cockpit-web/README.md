# apps/cockpit-web

Phase 8 — ATLAS Operator Cockpit (web-first, native-portable).

- Stack: SvelteKit 2 / Svelte 5 with `@sveltejs/adapter-static` (D-006).
- Consumes the Phase 7 Rust gateway (`native/atlas-core-rs/crates/
  atlas-gateway/`) over REST + SSE on 127.0.0.1 — no SSR, no `+server.ts`
  endpoints, no direct DB access.
- Native-portability constraints (D-021): this exact app is wrapped
  unchanged by the Phase 10 Tauri shell; avoid browser APIs unsupported by
  WebView2.
- v1.0 surfaces: mission list/detail/create, run timeline, live audit
  stream, wiki browser. No CRM, no auth (single operator, loopback).
- Branding: L2 Systems design system (Dark Prism / Topographic) — see the
  cockpit UI spec when Phase 8 planning starts.

Renamed from `apps/web` (empty scaffold) per PRODUCTION_REPO_STRUCTURE §4.1;
`apps/api` was removed — the gateway is a Rust crate, not a web app (D-022).
Implementation starts only after Phase 7 readiness gates pass
(`docs/plans/PHASE_7_8_READINESS.md`).
