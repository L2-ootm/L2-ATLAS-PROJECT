# Phase 8: Operator Cockpit (Web-First, Native-Portable)

**Phase number:** 8
**Name:** Operator Cockpit (SvelteKit web app, built native-portable for the v1.1 Tauri shell)
**Status:** Pending

---

## Goal

Ship the first operator cockpit — a SvelteKit/Svelte 5 web app (D-006) served against the Phase 7 API on `127.0.0.1` — providing mission management, real-time run monitoring, audit trail viewing, wiki browsing, and a read-only provider/model panel.

**Sequencing update (2026-06-10, D-021 §1):** Phase 8 is web-first. The Tauri/Rust native shell, previously folded into this phase by the Phase 4.5 reframing, is now **Phase 10 (Native Cockpit Shell, v1.1)** — it wraps this same app unchanged. Phase 8 is built under native-portability constraints so that port is zero-rework:

- adapter-static only, no SSR runtime;
- no browser APIs unsupported by WebView2;
- all API traffic to `127.0.0.1` (REST + SSE);
- no OS-privileged features (PTY, keychain, native dialogs) — those are Phase 10 scope.

`docs/architecture/NATIVE_COCKPIT_STRATEGY.md` remains the definitive spec for the Phase 10 shell.

---

## Requirements Covered

| REQ-ID | Description |
|--------|-------------|
| COCKPIT-01 | User can view a list of missions (with status, created timestamp) from the web cockpit |
| COCKPIT-02 | User can view the real-time audit event stream for an active run |
| COCKPIT-03 | User can view the full audit trail for a completed run |
| COCKPIT-04 | User can browse and search wiki pages from the cockpit |
| COCKPIT-05 | User can create and launch a mission from the cockpit UI |
| COCKPIT-06 | Cockpit loads in < 2 seconds on a local machine (no Electron startup tax) |

---

## Success Criteria

1. `npm run dev` (or equivalent) starts the cockpit dev server and renders the mission list page without errors.
2. Mission list page loads and displays all missions from the API with status badges.
3. Mission create form submits to the API and the new mission appears in the list without page reload.
4. Run detail page renders a real-time streaming audit event log via SSE (new events appear without manual refresh).
5. Wiki browser shows a searchable list of pages and renders page content.
6. Cockpit initial page load completes in < 2 seconds (measured with devtools network throttle disabled, localhost).
7. No Electron dependency in package.json.
8. Cockpit renders without errors in latest Chrome and Firefox.

---

## Key Decisions Applicable

- **D-021** (accepted 2026-06-10): web-first Phase 8; native shell is Phase 10 (v1.1); four surfaces in v1.0; CRM panel is Phase 11.
- **D-005** (locked): No Electron. The eventual native shell (Phase 10) uses Tauri 2.
- **D-006** (locked): SvelteKit/Svelte 5 with adapter-static. Do not re-open the framework debate.
- **D-009** (locked): No voice or overlay features.
- **D-007** (locked): No CRM UI surface in this phase (CRM panel = Phase 11 per D-021).
- **D-004** (locked): LLM Wiki is first-class — the wiki browser must support create/update from the cockpit.
- **D-016** (locked): Terax remains the implementation reference pillar **for Phase 10** (architecture-level only — no React/Zustand UI reuse, per D-021 §5).
- **D-017** (accepted): The provider/model panel exposes the ATLAS model registry (`GET /models`, Phase 7 API), never raw provider credentials.
- **D-018** (locked): The cockpit controls the evolved ATLAS/Hermes foundation runtime via the Phase 7 API.
- **D-019** (accepted): Memory inspection in v1.0 is satisfied by the wiki browser + provenance view; the full Surface 7 spec moves to Phase 10.
- Architecture rule: Cockpit consumes Phase 7 API only (REST + SSE). No direct SQLite access from the frontend.
- Branding (D-021 §8): the cockpit is the flagship L2/ATLAS-branded surface — use the L2 Systems design system. The operator never sees Hermes/FreeLLMAPI/Twenty branding.

## Cockpit Surfaces (Phase 8 — four, no more)

1. Mission list/detail + create form.
2. Run timeline and real-time audit event stream (SSE), including full trail for completed runs.
3. Wiki browser + FTS search, with page create/update and provenance view.
4. Provider/model settings surface — **read-only in v1.0**: model registry view (from Phase 7 API), health indicators, routing policy display, and audit visibility for which model handled a run. Keychain-backed key management, allow/deny mutation controls, and manual refresh move to Phase 10.

### Deferred to Phase 10 (Native Cockpit Shell, v1.1)

- Terminal pane bound to a Run ID (ConPTY/PTY).
- Native approval prompt surface (v1.0 uses an in-app approval modal if needed).
- OS keychain key management.
- Full memory inspection surface (Surface 7: retrieval diagnostics, correction interface, graph view).
- Tauri IPC capability model, CSP nonces, `docs/security/COCKPIT_THREAT_MODEL.md` gate.

## Pre-Work Required Before Phase 8 Implementation

1. Phase 7 API complete (REST + **SSE streaming endpoint** — Phase 7 must include `GET /runs/{id}/events/stream`).
2. L2 Systems design tokens available to the SvelteKit app.

(Former pre-work items — Tauri 2 build validation, `portable-pty` ConPTY prototype, cockpit threat model — move to Phase 10 pre-work.)

---

## What NOT to Build

- Do not add Electron — D-005 is locked.
- Do not build the Tauri shell, PTY, keychain, or native dialogs in this phase — that is Phase 10.
- Do not violate the native-portability constraints (no SSR runtime, no WebView2-incompatible APIs) — the Phase 10 port must be zero-rework.
- Do not add user authentication or login screens — v1.0 is single-operator local.
- Do not build CRM, contact, or opportunity views — Phase 11 (D-021).
- Do not build a Pulse/briefing dashboard — Phase 12.
- Do not add STT/TTS/voice — D-009 locked.
- Do not add global hotkeys or system-level overlay — v2.0.
- Do not add multi-tab or multi-window orchestration — keep UI scope minimal.
- Do not build a visual agent builder or drag-and-drop workflow designer — ATLAS is a serious operator tool, not a no-code builder.
- Do not copy Odysseus workspace sprawl — four surfaces in Phase 8.
- Keep the cockpit functional and auditable, not decorative. Prioritize data density and correctness over visual polish.
