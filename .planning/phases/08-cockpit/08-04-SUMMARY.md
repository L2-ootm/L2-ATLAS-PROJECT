---
phase: "08-cockpit"
plan: "04"
subsystem: "web-ui"
tags: ["sveltekit", "svelte5", "sse", "eventsource", "run-detail", "audit-stream"]
dependency_graph:
  requires:
    - "08-01 (GlassPanel, HudLabel, StatusBadge, api.ts scaffold)"
    - "08-02 (gateway cancel endpoint: POST /v1/missions/{id}/cancel)"
  provides:
    - "services/web-ui/src/routes/runs/[id]/+page.svelte — run detail with real-time SSE"
    - "services/web-ui/src/lib/components/SseEventRow.svelte — audit event row component"
    - "services/web-ui/src/lib/components/LiveBadge.svelte — pulsing LIVE connection indicator"
    - "services/web-ui/src/lib/components/RunTimeline.svelte — horizontal 2px progress bar"
  affects:
    - "services/web-ui SPA — /runs/[id] route now fully implemented"
tech_stack:
  added: []
  patterns:
    - "Native EventSource with addEventListener for typed SSE events (audit/end/error)"
    - "Single-retry reconnect pattern: one setTimeout(2000) on onerror, then static error"
    - "DOM cap: Array.slice(-500) on every insert to enforce 500-row limit"
    - "Auto-scroll: requestAnimationFrame + scrollHeight - scrollTop - clientHeight < 100 guard"
    - "Svelte 5 $derived with helper functions to satisfy TypeScript null-narrowing"
    - "JSONL export: paginated getRunEvents loop + Blob + createObjectURL anchor click"
key_files:
  created:
    - "services/web-ui/src/lib/components/SseEventRow.svelte"
    - "services/web-ui/src/lib/components/LiveBadge.svelte"
    - "services/web-ui/src/lib/components/RunTimeline.svelte"
    - "services/web-ui/src/routes/runs/[id]/+page.svelte"
  modified:
    - "services/web-ui/src/routes/runs/+page.svelte"
decisions:
  - "D-08-04-eventsource-direct: Used native EventSource directly (not api.ts streamRun wrapper) to maintain fine-grained control over onerror vs end event distinction and single-retry reconnect logic"
  - "D-08-04-derived-helpers: Svelte 5 $derived with run !== null && run.status check fails TypeScript narrowing; extracted checkIsActive/checkIsTerminal/getTimelineProgress as plain functions called inside $derived"
  - "D-08-04-sse-event-row-role: Changed role=row (table semantics) to role=button with tabindex=0 and keyboard handler on SseEventRow — the expand-on-click interaction requires button semantics for a11y"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-12"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 1
---

# Phase 08 Plan 04: Run Detail + SSE Audit Stream Summary

**One-liner:** Run detail page with native EventSource SSE stream (COCKPIT-02), full audit trail viewer for completed runs (COCKPIT-03), DOM-capped 500-row event list with auto-scroll, inline cancel confirmation, JSONL export, and three sub-components (SseEventRow, LiveBadge, RunTimeline) all passing strict TypeScript check with 0 errors 0 warnings.

---

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | SseEventRow, LiveBadge, RunTimeline components | 2c22c60 | SseEventRow.svelte, LiveBadge.svelte, RunTimeline.svelte |
| 2 | Run detail route with SSE stream, DOM cap, cancel flow, and JSONL export | 9ba01d3 | runs/[id]/+page.svelte, runs/+page.svelte |

---

## Verification Results

- `npm run check`: **0 errors, 0 warnings** (svelte-check 4.2.x, TypeScript strict, Svelte 5)
- `npm run build`: **exits 0**, static output written to `build/`

**SseEventRow:**
- grid-template-columns: "90px 100px 1fr" — PASS
- rgba(0,240,255,0.5) timestamp color — PASS
- 120 char truncation — PASS
- expanded $state with toggle — PASS
- role="button" tabindex=0 keyboard handler — PASS

**LiveBadge:**
- 1.5s pulse animation — PASS
- role="status" — PASS
- rgba(0,240,255,0.12) background — PASS
- renders nothing when connected=false — PASS

**RunTimeline:**
- height: 2px — PASS
- #00F0FF running, #00FF94 succeeded, #FF0055 failed — PASS
- shimmer animation for running state — PASS

**runs/[id]/+page.svelte:**
- EventSource — PASS
- scrollTop auto-scroll — PASS
- 500 DOM cap (slice) — PASS
- CONFIRM CANCEL inline banner — PASS
- role="log" aria-live="polite" — PASS
- STREAM INTERRUPTED copy + 2000ms reconnect delay — PASS
- EXPORT JSONL + createObjectURL — PASS
- SseEventRow/LiveBadge/RunTimeline imports — PASS

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SseEventRow role="row" triggers a11y error**
- **Found during:** Task 1 (npm run check)
- **Issue:** `role="row"` on a non-table element with onclick requires `tabindex` for keyboard focus; also semantically incorrect since this is not inside a table/grid context
- **Fix:** Changed to `role="button"` with `tabindex="0"`, added `onkeydown` handler for Enter/Space, added `aria-label`. This satisfies Svelte 5's a11y linter and is semantically correct for a clickable row that expands payload.
- **Files modified:** SseEventRow.svelte
- **Commit:** 2c22c60

**2. [Rule 1 - Type] Svelte 5 $derived does not narrow Run | null via `run !== null &&` inline**
- **Found during:** Task 2 (npm run check)
- **Issue:** TypeScript strict mode reports "Property 'status' does not exist on type 'never'" inside `$derived(run !== null && run.status === ...)` — the reactive macro prevents the type narrowing that a plain `if` block would provide
- **Fix:** Extracted `checkIsActive(r: Run | null)`, `checkIsTerminal(r: Run | null)`, `getTimelineProgress(r: Run | null)` as typed helper functions; `$derived` calls these helpers. TypeScript narrows correctly inside the explicit `if (!r) return` guard.
- **Files modified:** runs/[id]/+page.svelte
- **Commit:** 9ba01d3

---

## Threat Surface Scan

All threat mitigations from the plan's threat model are implemented:

| Threat ID | Mitigation Status |
|-----------|------------------|
| T-08-12 | Payload rendered as Svelte text binding (not innerHTML) — Svelte auto-escapes |
| T-08-13 | Hard DOM cap enforced: `events = events.slice(events.length - 500)` on every insert |
| T-08-14 | JSONL export is operator-initiated, no server-side exposure |
| T-08-15 | Single retry only (`reconnectAttempted` flag); if retry fails, static error copy shown |

No new trust boundaries beyond the plan's threat model.

---

## Known Stubs

None. Both COCKPIT-02 (real-time SSE) and COCKPIT-03 (completed run full trail) are fully wired. The `runs/+page.svelte` navigational stub is intentional — the primary entry point to runs is from mission detail (/missions/[id]).

---

## Self-Check: PASSED

- [x] services/web-ui/src/lib/components/SseEventRow.svelte — FOUND
- [x] services/web-ui/src/lib/components/LiveBadge.svelte — FOUND
- [x] services/web-ui/src/lib/components/RunTimeline.svelte — FOUND
- [x] services/web-ui/src/routes/runs/[id]/+page.svelte — FOUND
- [x] Commit 2c22c60 — Task 1 (sub-components)
- [x] Commit 9ba01d3 — Task 2 (run detail route)
- [x] npm run check: 0 errors 0 warnings
- [x] npm run build: exits 0
