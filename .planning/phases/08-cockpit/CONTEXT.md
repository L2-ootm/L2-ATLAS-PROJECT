# Phase 8: WebUI Operator Cockpit

**Phase number:** 8
**Name:** WebUI Operator Cockpit
**Status:** Pending

---

## Goal

Ship the first web-based operator cockpit — mission management, real-time run monitoring, audit trail viewer, and wiki browser — in the framework decided by the Phase 3 spike.

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
4. Run detail page renders a real-time streaming audit event log (new events appear without manual refresh).
5. Wiki browser shows a searchable list of pages and renders page content.
6. Cockpit initial page load completes in < 2 seconds (measured with devtools network throttle disabled, localhost).
7. No Electron dependency in package.json.
8. Cockpit renders without errors in latest Chrome and Firefox.

---

## Key Decisions Applicable

- **D-006** (resolved by Phase 3): Use the framework recommended by WEBUI_STACK_SPIKE.md. Do not re-open the SvelteKit vs Next.js debate here.
- **D-005** (locked): No Electron — the cockpit is a web app served locally; no Electron bundling.
- **D-009** (locked): STT/TTS/overlay is not a first MVP blocker — do not add voice or overlay features.
- **D-007** (locked): No CRM UI surface in this phase.
- **D-004** (locked): LLM Wiki is first-class — the wiki browser must support create/update from the cockpit, not just read-only browsing (COCKPIT-04 requirement).
- COCKPIT-06 performance gate: < 2 seconds initial load on localhost. Measure with devtools; if exceeded, optimize before marking phase complete. No server-side rendering heroics needed — this is local operator tooling.
- Architecture rule: Cockpit consumes Phase 7 API only. No direct SQLite access from the frontend.

---

## What NOT to Build

- Do not build a mobile or native app — that is v2.0 (NATIVE track).
- Do not add Electron — D-005 is locked.
- Do not add user authentication or login screens — v1.0 is single-operator local.
- Do not build CRM, contact, or opportunity views — that is v2.0.
- Do not build a Pulse/briefing dashboard — that is v2.0.
- Do not add multi-tab or multi-window orchestration — keep UI scope minimal.
- Do not build a visual agent builder or drag-and-drop workflow designer — ATLAS is a serious operator tool, not a no-code builder.
- Keep the cockpit functional and auditable, not decorative. Prioritize data density and correctness over visual polish.
