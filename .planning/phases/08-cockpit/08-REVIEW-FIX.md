---
phase: 08
review: 08-REVIEW.md
status: fixed
fixed_commit: fec2297
scope: critical + warning
info_findings: deferred
verified: 2026-06-12
---

# Phase 08 — Code Review Fix Report

All 4 Critical and 11 Warning findings from `08-REVIEW.md` were resolved in
commit `fec2297` (gsd-code-fixer). Info findings (12) are deferred — none are
operator-facing defects.

## Finding → Resolution

| Finding | Resolution |
|---------|------------|
| CR-01 wiki search debounce `$state` loop | Timer demoted to plain variable; effect cleanup added |
| CR-02 SSE replay duplicates crash keyed each | Connect with `?after={lastCursor}`; cursor dedupe guard on insert |
| CR-03 wiki_create slug normalization mismatch | Gateway reads CLI's echoed canonical slug; form normalizes client-side |
| CR-04 upsert create duplicates slug-keyed list | `handleFormSaved` dedupes by slug |
| WR SSE end-event drops tail events | Final `list_events` drain after terminal status |
| WR SSE `error` event name collision | Renamed to `stream_error` (gateway + client) |
| WR broken/unused `streamRun` | Reworked: cursor resume, stream_error listener |
| WR cancel optimistic PARTIAL never reconciled | Reconciles via stream_error/end instead of closing its own SSE |
| WR `dispatch_atlas` no timeout | 30s timeout + `kill_on_drop` |
| WR argument injection via positional args | `--` separator + empty/dash-prefixed value rejection |
| WR `listModels` swallows 500s | `ApiError` class with status; only degrades on absence, not server errors |
| WR `ModelEntry.active` number vs boolean | Typed boolean; `searchWiki` typed `WikiSearchResult` (snippet/score) |
| WR `exportJsonl` unhandled rejection/truncation | Error state surfaced; no silent truncation |
| WR `ingest_source` missing `raw/` dir | `mkdir(parents=True)` before copy |
| WR `fts_quote` strips instead of escaping | Aligned with CLI phrase semantics |

## Post-fix verification (orchestrator)

- `npm run check`: 0 errors, 0 warnings
- `npm run build`: exit 0
- `cargo test -p atlas-gateway`: 26 passed
- `pytest` wiki-runtime: 31 passed; agent-runtime: 54 passed
- Browser: wiki search keystroke (previously crashing) filters correctly;
  all four surfaces sweep with 0 console errors against the live gateway.
