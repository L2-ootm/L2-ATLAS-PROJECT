# ULTRAREVIEW — Chat stream interleaving and scroll capture

Date: 2026-07-16
Scope: WebUI chat transcript, native audit projection, actor telemetry

## Root cause 1 — metadata checkpoints erase streamed prefixes

**Failure point:** `services/web-ui-react/src/lib/consoleEvents.ts:60-76,110-117`

`llm_call` and `llm_delta` audit rows both normalize to surface kind `text`.
The projector only distinguishes rows carrying `delta`; a metadata-only
`llm_call` therefore falls through as `{ type: "text", text: undefined }`.

`ChatAgentTurn` then interprets that synthetic empty `text` as the
authoritative reconcile and replaces the open delta block with `undefined`.
The next real delta starts a new block, leaving only the suffix visible.

### Persisted proof

The operator's latest completed native run contains this ordered sequence:

```text
llm_delta  "\n\nLet"
llm_delta  " me read the rest of barrowman.rs and the remaining"
llm_call   <provider/model/usage metadata; no text>
llm_delta  " core physics files."
```

The database therefore has the complete sentence. The screenshot shows only
`core physics files.`, which is exactly the suffix after the metadata row.
The same fingerprint repeats for `ator/mass_calculator files.` and
`stage configuration.`.

### Repair contract

- Project metadata-only text events as non-rendering `telemetry`, never `text`.
- Ignore telemetry inside transcript grouping.
- Close a streamed narration block at an actual tool-call boundary.
- Preserve the final text reconcile for the final assistant block.

## Root cause 2 — continuous auto-follow wins the scroll race

**Failure point:** `services/web-ui-react/src/routes/Chat.tsx:499-511`

While a run is busy, a perpetual `requestAnimationFrame` loop writes
`scrollTop = scrollHeight`. An upward wheel gesture can be overwritten before
the browser emits `scroll` and before `pinnedRef` becomes false.

### Repair contract

- Remove frame-by-frame scroll writes.
- Follow only when transcript content changes and the viewport is pinned.
- Mark upward wheel/touch/thumb-drag intent as unpinned synchronously.
- Keep the explicit `LATEST` action as the only way to resume after pausing.

## Related issue — meaningless runtime receipts

Tool-call surface rows without a tool or a recognized transition/runtime
currently become the literal status `runtime event`. These are audit telemetry,
not operator-facing copy. They should use the same non-rendering telemetry
projection while real run/runtime/privacy receipts remain visible.

## Verification targets

1. Interleaved delta → metadata → delta renders one complete sentence.
2. Generic telemetry does not produce `RUNTIME EVENT` rows.
3. Upward user intent remains stable while more stream events arrive.
4. Final reconcile still replaces the final provisional delta exactly once.

## Resolution evidence

- Metadata-only model rows now project as `telemetry`; both Chat and Console
  consume a shared display fold that ignores telemetry and closes narration at
  real tool boundaries.
- The busy-turn animation-frame scroll writer was removed. `TopoScroll` now
  reports wheel-up, touch, and thumb-drag ownership before scroll events fire.
- Orchestration lifecycle projection maps timeouts to a failed terminal state,
  creates a provisional allocation node before the first heartbeat, and lets a
  matching terminal actor lifecycle settle the dispatch card if its join
  receipt is delayed.
- Regression coverage: metadata-interleaved deltas, provisional dispatch,
  lifecycle settlement, timeout terminal mapping, and viewport user intent.
