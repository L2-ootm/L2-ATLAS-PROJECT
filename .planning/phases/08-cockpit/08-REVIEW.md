---
phase: 08-cockpit
reviewed: 2026-06-12T00:00:00Z
depth: standard
files_reviewed: 34
files_reviewed_list:
  - native/atlas-core-rs/crates/atlas-gateway/src/db.rs
  - native/atlas-core-rs/crates/atlas-gateway/src/lib.rs
  - services/web-ui/src/lib/api.ts
  - services/web-ui/src/lib/components/CreateMissionModal.svelte
  - services/web-ui/src/lib/components/GlassPanel.svelte
  - services/web-ui/src/lib/components/HudLabel.svelte
  - services/web-ui/src/lib/components/LiveBadge.svelte
  - services/web-ui/src/lib/components/MissionRow.svelte
  - services/web-ui/src/lib/components/ModelRow.svelte
  - services/web-ui/src/lib/components/ProvenancePanel.svelte
  - services/web-ui/src/lib/components/RunTimeline.svelte
  - services/web-ui/src/lib/components/Sidebar.svelte
  - services/web-ui/src/lib/components/SseEventRow.svelte
  - services/web-ui/src/lib/components/StatusBadge.svelte
  - services/web-ui/src/lib/components/WikiPageForm.svelte
  - services/web-ui/src/lib/components/WikiPageList.svelte
  - services/web-ui/src/lib/components/WikiPageViewer.svelte
  - services/web-ui/src/lib/index.ts
  - services/web-ui/src/lib/modules.ts
  - services/web-ui/src/lib/ui-state.svelte.ts
  - services/web-ui/src/routes/+layout.svelte
  - services/web-ui/src/routes/+layout.ts
  - services/web-ui/src/routes/+page.svelte
  - services/web-ui/src/routes/missions/+page.svelte
  - services/web-ui/src/routes/missions/[id]/+page.svelte
  - services/web-ui/src/routes/models/+page.svelte
  - services/web-ui/src/routes/runs/+page.svelte
  - services/web-ui/src/routes/runs/[id]/+page.svelte
  - services/web-ui/src/routes/wiki/+page.svelte
  - services/web-ui/src/lib/tokens.css
  - services/web-ui/svelte.config.js
  - services/web-ui/vite.config.ts
  - services/wiki-runtime/atlas_wiki/cli/main.py
  - services/wiki-runtime/atlas_wiki/wiki_service.py
findings:
  critical: 4
  warning: 11
  info: 12
  total: 27
status: fixes_applied
fixes:
  resolved: [CR-01, CR-02, CR-03, CR-04, WR-01, WR-02, WR-03, WR-04, WR-05, WR-06, WR-07, WR-08, WR-09, WR-10, WR-11, IN-01, IN-02, IN-04, IN-07, IN-08, IN-10, IN-11]
  deferred: [IN-03, IN-05, IN-06, IN-09, IN-12]
  verified: svelte-check 0 errors; cargo test 26/26; pytest 31/31; npm build ok; live browser re-test of CR-01/CR-03/CR-04 (0 console errors)
---

# Phase 8: Code Review Report

**Reviewed:** 2026-06-12
**Depth:** standard
**Files Reviewed:** 34
**Status:** issues_found

## Summary

Reviewed the Phase 8 cockpit: SvelteKit/Svelte 5 web UI (`services/web-ui`), the axum gateway additions in `atlas-gateway` (wiki/model/cancel handlers, SSE stream, hand-rolled CORS), and the two Python wiki-runtime files. The markdown renderer's XSS posture is sound (escape-first, no attribute injection paths survive). The SQL layer is parameterized throughout.

Four critical defects were found, all reachable through normal operator flows: a reactive infinite loop in the wiki search debounce that crashes the wiki surface on first keystroke, an SSE reconnect path that re-streams from cursor 0 and crashes the run page via duplicate keyed-each keys, a slug-normalization contract break between the gateway and the atlas CLI that turns successful wiki creates into 500s, and a duplicate-slug crash in the wiki list. The warnings cluster around SSE lifecycle (event-name collision with transport errors, end-of-stream race), the write-dispatch path (no timeout, argument injection via positional args), and type-contract drift between `api.ts` and gateway JSON.

## Critical Issues

### CR-01: Wiki search debounce $effect reads and writes its own dependency — infinite reactive loop

**File:** `services/web-ui/src/routes/wiki/+page.svelte:24,38-62`
**Issue:** `debounceTimer` is declared as `$state(0)` and the `$effect` both reads it (`if (debounceTimer) clearTimeout(...)`) and writes it (`debounceTimer = window.setTimeout(...)`). In Svelte 5, writing to state that the same effect read makes the effect re-run. The first keystroke into the search box triggers: run → clear old timer → set new timer id (new value) → invalidate → re-run → clear the timer just set → set another → … This loops until Svelte aborts with `effect_update_depth_exceeded`, crashing the wiki surface. The debounce also never fires because each iteration clears the previous timer.
**Fix:** The timer handle is not view state — make it a plain module variable:
```svelte
let debounceTimer: ReturnType<typeof setTimeout> | undefined;

$effect(() => {
	const q = searchQuery;
	clearTimeout(debounceTimer);
	if (!q.trim()) {
		searchResults = null;
		return;
	}
	debounceTimer = setTimeout(async () => {
		try {
			searchResults = (await searchWiki(q)).results;
		} catch {
			searchResults = [];
		}
	}, 300);
	return () => clearTimeout(debounceTimer);
});
```

### CR-02: SSE retry re-streams from cursor 0 — duplicate events and duplicate keyed-each keys crash the run page

**File:** `services/web-ui/src/routes/runs/[id]/+page.svelte:131-228,570` (also `services/web-ui/src/lib/api.ts:118,134-137`)
**Issue:** Neither the initial `EventSource` nor the 2s retry passes `?after={cursor}` even though the gateway supports it and the page tracks event cursors. On any transport interruption (gateway restart, blip), the retry replays every event from rowid 0; `addEvent` appends them all, so `events` contains duplicate `cursor` values, and `{#each filteredEvents as evt (evt.cursor)}` (line 570) hits duplicate keys — a runtime `each_key_duplicate` error in dev and broken/duplicated DOM in prod. The gateway's own error path makes this worse: when it emits a named `error` event and closes the stream, the client's `error` listener (line 169) sets a banner but does not close the source, so `onerror` fires next and triggers the same replay-from-0 retry. `api.ts streamRun` has the identical missing-`after` defect and additionally never closes the source on error, letting the browser's built-in auto-reconnect replay from 0 indefinitely.
**Fix:** Track the max cursor seen and resume from it on every (re)connect:
```ts
let lastCursor = 0; // update in addEvent: lastCursor = Math.max(lastCursor, evt.cursor)
const source = new EventSource(
	`${GATEWAY}/v1/runs/${encodeURIComponent(runId)}/stream?after=${lastCursor}`
);
```
As defense-in-depth, make `addEvent` drop events with `evt.cursor <= lastCursor`. Apply the same to the retry path and to `streamRun` in api.ts (or delete `streamRun` — see WR-03).

### CR-03: wiki_create reads back the raw slug, but the CLI normalizes it — successful creates return 500

**File:** `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:444-465` (root cause interaction: `services/wiki-runtime/atlas_wiki/wiki_service.py:237`)
**Issue:** `update_wiki_page` normalizes the slug (`slug.lower().strip().replace(" ", "-")`) and the CLI echoes the normalized slug to stdout. But `wiki_create` discards `dispatch_atlas`'s return value and reads back `db::get_wiki_page(&path, &slug)` with the *original* request slug. Any slug containing uppercase or spaces (e.g. `My Page`) is written to the DB as `my-page`, the read-back misses, and the handler returns 500 `"wiki page 'My Page' created but not found in db"`. The frontend then shows "PAGE SAVE FAILED" and keeps the page out of the list even though the write succeeded — retries silently bump the page version. The form (`WikiPageForm.svelte`) performs no slug normalization or format validation either.
**Fix:** Use the CLI's stdout (the canonical normalized slug) for the read-back:
```rust
let canonical = dispatch_atlas(
    &state.atlas_cmd,
    &["wiki", "update", &slug, "--title", &title, "--body", &content],
).await?;
let found = blocking(move || db::get_wiki_page(&path, &canonical)).await?;
```
Additionally validate/normalize slug client-side in `WikiPageForm.svelte` so the URL the operator sees matches what was stored.

### CR-04: Creating a wiki page with an existing slug produces duplicate keys in the page list

**File:** `services/web-ui/src/routes/wiki/+page.svelte:99-109`; `services/web-ui/src/lib/components/WikiPageList.svelte:39`
**Issue:** The gateway POST `/v1/wiki/pages` is an upsert (the CLI's `wiki update` creates or updates), so creating a page whose slug already exists succeeds with 201. `handleFormSaved` in create mode unconditionally prepends: `pages = [page, ...pages]`. The list now contains two entries with the same slug, and `{#each pages as page (page.slug)}` throws `each_key_duplicate`, crashing the wiki surface. There is no client- or server-side uniqueness check.
**Fix:** Dedupe on save regardless of mode:
```ts
function handleFormSaved(page: WikiPageDetail) {
	const existing = pages.some((p) => p.slug === page.slug);
	pages = existing
		? pages.map((p) => (p.slug === page.slug ? page : p))
		: [page, ...pages];
	activePage = page;
	showForm = false;
}
```
Consider also having the gateway return 409 (or 200 instead of 201) when POST targets an existing slug.

## Warnings

### WR-01: SSE poll terminates with events still unsent (read-order race)

**File:** `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:274-297`
**Issue:** Each poll calls `db::list_events` and then `db::run_status` on two separate connections. Events written between the two reads, with the status flipping to terminal before the status read, are never streamed: the poll sees `had_events == false` and a terminal status, emits `end`, and sets `done = true`. The tail of a run's audit trail can be silently dropped from the live stream (it remains retrievable via `/events`, but the cockpit never fetches it).
**Fix:** After observing a terminal status, do one final `list_events` pass (or require two consecutive empty polls after terminal status) before emitting `end`.

### WR-02: Gateway SSE event named `error` collides with EventSource transport errors

**File:** `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:305-318`; `services/web-ui/src/routes/runs/[id]/+page.svelte:169-177`; `services/web-ui/src/lib/api.ts:134-137`
**Issue:** `addEventListener('error', ...)` receives both the gateway's named `error` events (with `data`) and the browser's native transport-error events (no `data`). The client cannot distinguish them: a transport blip lands in the message handler, `JSON.parse(undefined)` throws, and the user sees "STREAM ERROR — unknown gateway error" followed immediately by the `onerror` reconnect banner. The gateway also closes the stream after a named `error` without the client closing the source, feeding the CR-02 replay path.
**Fix:** Rename the gateway event to something unreserved, e.g. `.event("stream_error")`, and update both client listeners.

### WR-03: api.ts `streamRun` is broken and unused (dead code with wrong contract)

**File:** `services/web-ui/src/lib/api.ts:112-139`
**Issue:** (a) `onEnd(evt.data ?? 'SUCCEEDED')` passes the raw JSON string `{"status":"..."}` while the signature promises a status string; (b) the error handler claims "reconnecting in 2s" but implements no reconnect, and does not `close()`, so the browser auto-reconnects without `after` and replays all events (duplicate delivery); (c) no caller exists — `runs/[id]/+page.svelte` reimplements SSE inline, so two divergent SSE implementations now exist.
**Fix:** Either fix `streamRun` (parse end data, support `after`, close on error) and make the run page use it, or delete it. One SSE implementation, not two.

### WR-04: Cancel flow: optimistic `PARTIAL` status is never reconciled, and cancel is mission-wide

**File:** `services/web-ui/src/routes/runs/[id]/+page.svelte:263-285`
**Issue:** `confirmCancel` sets `run.status = 'PARTIAL'` with a comment "will be corrected by SSE end event" — then immediately calls `closeSse()`, guaranteeing the correction never arrives. The displayed status, `finished_at`, and elapsed time remain whatever the optimistic guess was, even if the backend recorded a different terminal status. Separately, the endpoint cancels *all* running runs of the mission (CLI `mission cancel` loops every running run), which the single-run "CANCEL RUN" button does not convey.
**Fix:** After a successful cancel, re-fetch the run (`run = (await getRun(run.id)).run`) instead of guessing, then close the stream. Update the confirmation copy to state that all active runs of the mission are halted (or add a run-scoped cancel to the CLI/gateway).

### WR-05: `dispatch_atlas` has no timeout — a hung CLI hangs the HTTP request forever

**File:** `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:344-368`
**Issue:** `cmd.output().await` waits indefinitely. If the `atlas` CLI blocks (DB lock contention with WAL writers, stuck import, prompt on stdin), every POST handler awaiting it hangs with no bound, and the cockpit's save/launch buttons spin forever with no error surfaced.
**Fix:** Wrap in `tokio::time::timeout(Duration::from_secs(30), cmd.output())` and map elapsed timeouts to `ApiError::Internal("atlas command timed out")`, killing the child process.

### WR-06: Argument injection into the atlas CLI via positional path/body parameters

**File:** `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:405-408,451-453,492-495,531` 
**Issue:** User-controlled values (`slug`, `mission_id`, run `id`) are passed as *positional* CLI arguments with no `--` separator and no validation. A value beginning with `-` (e.g. slug `--help`, URL path `/v1/missions/--help/run`) is parsed by typer/click as an option: `--help` exits 0 printing help text, which the gateway then treats as a successful dispatch; crafted values like `--body=x` can override the flagged options that follow, corrupting what gets written. There is no shell so this is not command injection, but it lets request data alter CLI semantics. Empty slugs are also accepted (`POST {"slug": ""}` creates a page with an empty slug, unreachable via the detail route).
**Fix:** Insert `--` before positional user data in every `dispatch_atlas` call (e.g. `&["mission", "run", "--", &mission_id]`) and reject empty/whitespace slugs, titles, and ids with `ApiError::BadRequest` before dispatching.

### WR-07: `listModels` swallows every gateway error — 500s render as "MODEL REGISTRY EMPTY"

**File:** `services/web-ui/src/lib/api.ts:221-237`; `services/web-ui/src/routes/models/+page.svelte:22-33`
**Issue:** The catch matches `msg.includes('GATEWAY ERROR')`, which matches *every* non-2xx response produced by `apiFetch` (including 400/500), and `'Failed to fetch'` is Chromium-specific (Firefox network errors say "NetworkError…"). Net effect: genuine gateway failures display the empty-registry state ("Ensure the Phase 7 gateway is running…") instead of an error, while the page's GATEWAY OFFLINE error branch is unreachable in Chromium and only reachable for Firefox network errors. The intended "degrade on 404/503 only" behavior is not what is implemented.
**Fix:** Make `apiFetch` throw a typed error carrying `status`, then degrade only for `status === 404 || status === 503`; rethrow everything else (including network `TypeError`) so the page shows its error banner.

### WR-08: Type-contract drift between api.ts and gateway JSON

**File:** `services/web-ui/src/lib/api.ts:160-166,201-214`; `native/atlas-core-rs/crates/atlas-gateway/src/db.rs:165-185,278`
**Issue:** (a) `ModelEntry.active` is typed `number` ("1 = active, 0 = inactive") but `db.rs:278` emits a JSON **boolean** (`row.get::<_, i64>(5)? != 0`); current code only uses truthiness so it works by luck — any `active === 1` comparison would silently fail. (b) `searchWiki` is typed `Promise<{ results: WikiPage[] }>` but the gateway's search rows contain `slug/title/snippet/score/updated_at` — no `created_at` (which `WikiPage` declares required) and two fields (`snippet`, `score`) that the type hides; the wiki search UI consequently hardcodes `—` in the SCORE column (wiki/+page.svelte:238) despite the score being present in the payload.
**Fix:** Change `active: boolean`; add a `WikiSearchResult { slug; title; snippet; score; updated_at }` type for `searchWiki` and render the real score/snippet.

### WR-09: `exportJsonl` — unhandled promise rejection and silent truncation

**File:** `services/web-ui/src/routes/runs/[id]/+page.svelte:288-312,448`
**Issue:** `onclick={exportJsonl}` invokes an async function whose `getRunEvents` calls can reject (gateway down, 503). There is no try/catch, so failures become unhandled rejections and the operator gets no feedback — the export just doesn't happen. The `MAX_ITERATIONS = 100` guard also silently truncates exports beyond ~20k events with no warning in the output, undermining the audit-export purpose.
**Fix:** Wrap the body in try/catch surfacing the error in the UI (reuse `streamError` or a dedicated banner), and append a sentinel line or alert when the iteration cap is hit.

### WR-10: `ingest_source` copies into `wiki_dir/raw/` without creating the directory

**File:** `services/wiki-runtime/atlas_wiki/wiki_service.py:151-152`; `services/wiki-runtime/atlas_wiki/cli/main.py:53-64`
**Issue:** `_get_wiki_dir()` creates only `wiki_dir` itself ("so index/log writes never fail"), but `ingest_source` does `shutil.copy2` into `wiki_dir / "raw" / ...`. On a fresh checkout or a fresh `ATLAS_WIKI_DIR`, `raw/` does not exist, `copy2` raises `FileNotFoundError`, which is not caught by the CLI's `except ValueError` — the operator gets a raw traceback and exit via unhandled exception.
**Fix:** `raw_dest.parent.mkdir(parents=True, exist_ok=True)` before the copy.

### WR-11: `fts_quote` strips quotes instead of escaping; quote-only queries can 503; semantics diverge from CLI search

**File:** `native/atlas-core-rs/crates/atlas-gateway/src/db.rs:155-163`
**Issue:** (a) `t.replace('"', "")` deletes quote characters rather than escaping them (`""` doubling, as the Python side does at `wiki_service.py:324`), silently changing the query. (b) A query consisting only of `"` characters yields the token `""` — an empty/odd FTS phrase that SQLite can reject, surfacing as a 503 `db_error` for a plain search input. (c) The gateway ANDs individually-quoted tokens while the Python CLI quotes the whole input as a single phrase — the same query returns different results through the two surfaces that are supposed to share one store.
**Fix:** Mirror the CLI: `format!("\"{}\"", query.replace('"', "\"\""))` as a single phrase (or keep per-token but escape via doubling and filter out tokens that become empty), and map FTS syntax errors to 400 rather than 503.

## Info

### IN-01: Duplicate handler functions

**File:** `services/web-ui/src/routes/wiki/+page.svelte:65-87`
**Issue:** `handleSelectPage` and `handleSelectFromSearch` are byte-identical.
**Fix:** Delete one; pass the same handler to both call sites.

### IN-02: Cancel bypasses the API client; `GATEWAY` constant duplicated

**File:** `services/web-ui/src/routes/runs/[id]/+page.svelte:13,267`
**Issue:** The page hardcodes its own `GATEWAY` constant and issues a raw `fetch` for cancel instead of adding `cancelRun()` to `api.ts`, so error formatting and base-URL handling diverge from every other call.
**Fix:** Add `cancelRun(missionId)` to api.ts and remove the local constant.

### IN-03: Navigation via `window.location.href` instead of SvelteKit `goto`

**File:** `services/web-ui/src/lib/components/MissionRow.svelte:33,46,108`; `services/web-ui/src/routes/missions/[id]/+page.svelte:51,298,304,337`
**Issue:** Full page reloads on every row click — loses SPA navigation, refetches the entire bundle, and defeats client-side routing.
**Fix:** `import { goto } from '$app/navigation'` and use `goto(...)`.

### IN-04: `loadFullTrail` comment overstates the cap

**File:** `services/web-ui/src/routes/runs/[id]/+page.svelte:248`
**Issue:** Comment claims "up to 1000 * 20 = 20000 events" but `getRunEvents` is called without `limit`, so the gateway default of 200 applies — the actual cap is ~4000 events, silently truncated before the 500-row DOM slice.
**Fix:** Pass an explicit `limit` (api.ts `getRunEvents` would need the param) or correct the comment.

### IN-05: Runs index page hardcodes "NO RUNS INITIATED"

**File:** `services/web-ui/src/routes/runs/+page.svelte:30-32`
**Issue:** The text claims no runs exist regardless of actual state; the page fetches nothing. Misleading for an operator with active runs.
**Fix:** Either fetch and list recent runs or reword to a neutral "Select a run from a mission detail page."

### IN-06: Remote Google Fonts import in tokens.css

**File:** `services/web-ui/src/lib/tokens.css:6`
**Issue:** The loopback-only cockpit depends on `fonts.googleapis.com` at runtime — fonts fail offline and every page load leaks usage to a third party.
**Fix:** Self-host the three font families (e.g. `@fontsource` packages).

### IN-07: `lint` contradiction rule is subject-blind; redundant exception tuple

**File:** `services/wiki-runtime/atlas_wiki/wiki_service.py:356,471-490`
**Issue:** `cross_page_contradiction` matches any `version is X` regardless of subject, so "Python version is 3.12" vs "Node version is 20" is flagged as a contradiction; it also emits one finding per prior distinct value (noisy). Separately, `except (ImportError, Exception)` is redundant — `Exception` subsumes `ImportError`.
**Fix:** Capture the subject preceding "version is" in the regex and compare per-subject; use `except Exception`.

### IN-08: CORS middleware minor correctness gaps

**File:** `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:583-616`
**Issue:** (a) `headers.insert(VARY, "Origin")` overwrites any handler-set Vary value (use `append` or merge); (b) responses to disallowed/absent origins carry no `Vary: Origin`, which can poison shared caches; (c) every OPTIONS request short-circuits to 204 before routing, so a future non-CORS OPTIONS handler would be unreachable. Loopback bind makes all of these low-impact today.
**Fix:** Always set `Vary: Origin` (append), and only short-circuit OPTIONS when an `Access-Control-Request-Method` header is present.

### IN-09: CreateMissionModal — Escape only works once focus is inside; no focus trap

**File:** `services/web-ui/src/lib/components/CreateMissionModal.svelte:48-63`
**Issue:** The `onkeydown` listener is on the overlay div (`tabindex="-1"`, never focused), so Escape does nothing until the user clicks a field. No autofocus and no focus trap for an `aria-modal` dialog.
**Fix:** Use `<svelte:window onkeydown={...}>` gated on `open`, and autofocus the title input on open.

### IN-10: `Content-Type: application/json` on GET requests forces needless preflights

**File:** `services/web-ui/src/lib/api.ts:56-60`
**Issue:** `apiFetch` attaches the JSON content-type header to every request including GETs, making each GET a non-simple CORS request requiring an OPTIONS preflight round-trip.
**Fix:** Set the header only when `init?.body` is present.

### IN-11: Elapsed time frozen for live runs

**File:** `services/web-ui/src/routes/runs/[id]/+page.svelte:61,73-84`
**Issue:** `elapsedText` derives from `Date.now()` which is not reactive; for a RUNNING run the displayed elapsed time is fixed at page-load time, despite sitting next to a LIVE badge.
**Fix:** Add a 1s `setInterval` updating a `$state` tick that the derived reads while `isActive`.

### IN-12: Build config suppresses prerender failures

**File:** `services/web-ui/svelte.config.js:11-16`
**Issue:** `strict: false` plus `handleHttpError: 'warn'` and `handleUnseenRoutes: 'warn'` means broken routes/links surface only as build-log warnings, never failing CI.
**Fix:** Once the route set stabilizes, drop `strict: false` and switch handlers to `'fail'` (keeping the SPA `fallback` for dynamic `[id]` routes).

---

_Reviewed: 2026-06-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
