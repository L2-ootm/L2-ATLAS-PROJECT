# ULTRAREVIEW: TUI Streaming Duplication & Formatting Loss (v2)

**Date:** 2026-07-12
**Trigger:** User reports persistent text duplication and formatting loss in atlas-terminal TUI after streaming completes. Prior fixes (6 iterations) did not resolve it.

---

## Symptom

After an assistant response finishes streaming, the TUI shows:
1. **Text duplication** — tail content of one paragraph repeats at the start of the next
2. **Formatting loss** — bold/markdown markers visible as raw text, or styled text briefly flashes then reverts

Screenshot evidence: "What's on your mind?, debug, automate, research, and communicate across platforms." followed by "What's on your mind?" — the end of paragraph 3 is concatenated with the start of paragraph 5.

---

## Data Flow (complete chain, with file:line proof)

### Hop 1: SSE stream delivers audit frames

`services/atlas-terminal/src/adapter/gateway.ts:161-168` — `streamRun()` consumes `GET /v1/runs/{id}/stream` (text/event-stream), invokes `onEvent` callback per frame.

### Hop 2: Adapter translates frames to bus events

`services/atlas-terminal/src/adapter/chat.ts:368-471` — `onRunEvent()` handles three critical frame types in sequence:

```
llm_delta  → appends text to streaming entry, emits 'message.part.delta'  (line 441)
llm_call   → overwrites entry.text with authoritative textOrSummary, emits 'message.part.updated' (line 461)
end        → sets assistant.info.time.completed, emits 'message.updated' (line 371)
```

**Proof of text overwrite:** `chat.ts:460` — `entry.part.text = textOrSummary` replaces the delta-accumulated text with the server's post-processed text. Comment at line 456: "post-processing like think-block stripping can differ from the raw stream".

### Hop 3: EventBus delivers synchronously

`services/atlas-terminal/src/adapter/events.ts:43-48` — `EventBus.emit()` iterates listeners synchronously. No async scheduling.

### Hop 4: SDK bridges EventBus → SolidJS store

`services/atlas-terminal/src/main.tsx:61` — Local mode subscribes directly: `handle.bus.subscribe((event) => handler(toGlobalEvent(event)))`.

`services/atlas-terminal/src/tui/context/sdk.tsx:48-73` — **THE CRITICAL BRIDGE.** `handleEvent()` queues events and flushes in batches:

```typescript
// sdk.tsx:62-73
const handleEvent = (event: GlobalEvent) => {
  queue.push(event)
  const elapsed = Date.now() - last
  if (timer) return                    // already deferred
  if (elapsed < 16) {
    timer = setTimeout(flush, 16)      // batch with future events
    return
  }
  flush()                              // flush immediately
}
```

```typescript
// sdk.tsx:48-60
const flush = () => {
  const events = queue
  queue = []
  batch(() => {                         // SolidJS batch
    for (const event of events) {
      emitter.emit("event", event)      // delivers to sync.tsx handler
    }
  })
}
```

**ROOT CAUSE 1 — Event batching split:**
If the last delta event was > 16ms before the `llm_call` event, `flush()` runs immediately for `llm_call` (with just that event). The `end` event then arrives, sees `elapsed < 16` (since `last` was just set by the flush), and gets deferred via `setTimeout(flush, 16)`. This splits the two events into SEPARATE SolidJS batches, causing TWO render passes:
- **Pass 1:** content updates to reconciled text, `streaming` still `true`
- **Pass 2 (16ms later):** `streaming` flips to `false`

If the last delta was < 16ms before `llm_call`, both events are queued together and flushed in one batch (one render pass). The 16ms window is a coin flip depending on stream cadence.

### Hop 5: Store updates reactive state

`services/atlas-terminal/src/tui/context/sync.tsx:831-10110` — `message.part.updated` handler: `setStore("part", messageID, index, reconcile(part))`.

`services/atlas-terminal/src/tui/context/sync.tsx:121-6110` — `message.updated` handler: `setStore("message", sid, aid, index, reconcile(info))`.

### Hop 6: SolidJS reactivity drives TextPart

`services/atlas-terminal/src/tui/routes/session/index.tsx:1560-1603` — `TextPart` passes:
```tsx
<markdown
  streaming={!props.message.time.completed}
  content={props.part.text.trim()}
  ...
/>
```

### Hop 7: opentui MarkdownRenderable processes updates

`node_modules/@opentui/core/index-fedv7szb.js`:

- **Line 9251-9258:** `content` setter → `updateBlocks()` (no force, `trailingUnstable=2`)
- **Line 9310-9316:** `streaming` setter → `updateBlocks(true)` (force, `trailingUnstable=0`)
- **Line 9155-9196:** `parseMarkdownIncremental()` — reuses stable tokens, re-lexes trailing `trailingUnstable` tokens
- **Line 9849-9951:** `updateBlocks(forceTableRefresh)` — diffs tokens against `_blockStates`, reuses/patches/destroys blocks

### Hop 8: Child CodeRenderables have hardcoded streaming

`node_modules/@opentui/core/index-fedv7szb.js`:

- **Line 9477-9493:** `createMarkdownCodeRenderable()` — hardcodes `streaming: true`
- **Line 9510-9519:** `applyMarkdownCodeRenderable()` — hardcodes `renderable.streaming = true`
- **Line 9521-9530:** `applyCodeBlockRenderable()` — correctly propagates `renderable.streaming = this._streaming`

**ROOT CAUSE 2 — Prose blocks never exit streaming mode:**
After the parent `MarkdownRenderable.streaming` flips to `false`, `updateBlocks(true)` refreshes all blocks. But `applyMarkdownCodeRenderable` (line 9518) forces child prose `CodeRenderable.streaming = true`. This means:

- `CodeRenderable.content` setter (line 4178) early-returns: `if (this._streaming && !this._drawUnstyledText && this._filetype) return;` — the text buffer is NOT updated
- The block continues showing stale styled content from the previous highlight pass
- A new async `startHighlight()` (line 4290) eventually resolves, but with a delay
- During this delay, the old styled text (possibly from a different content snapshot) is visible

**Contrast:** Fenced code blocks use `applyCodeBlockRenderable` which sets `renderable.streaming = this._streaming` — they correctly exit streaming mode.

### Hop 9: Block matching during double updateBlocks

When both content and streaming change (in one or two render passes):

1. **First `updateBlocks()`** (from content setter, no force):
   - `parseMarkdownIncremental(content, parseState, trailingUnstable=2)` — last 2 tokens re-lexed
   - Token boundaries may differ from the final state
   - Blocks are matched by `token === token` (reference) then `tokenRaw === token.raw` (string)
   - Blocks that changed are destroyed and recreated as fresh `CodeRenderable`

2. **Second `updateBlocks(true)`** (from streaming setter, force):
   - `parseMarkdownIncremental(content, parseState, trailingUnstable=0)` — all tokens stable
   - Different token boundaries than step 1 (trailing tokens now stable)
   - `shouldForceRefresh = true` — ALL blocks get `updateBlockRenderable` called
   - Blocks that changed between step 1 and step 2 are destroyed and recreated AGAIN

**ROOT CAUSE 3 — Double updateBlocks produces intermediate visible state:**
The first `updateBlocks()` may produce paragraph tokens with overlapping raw content (the incremental parser's trailing unstable zone). These become the visible block state. The second `updateBlocks(true)` corrects them, but the intermediate state was already painted to the terminal for up to 16ms (or one frame). This is the "glitch" — text appears, then same text again starting mid-line.

---

## Why Prior Fixes Failed

### Fix iterations 1-5: Data-layer fixes
Proved clean by direct audit-DB reads — the adapter and store produce correct data. The duplication is a rendering-layer issue.

### Fix iteration 6: Component swap (`<Show when={completed}>`)
Unmounted a plain `<text>` during streaming and mounted a fresh `<markdown>` at completion. Failed because:
- Fresh `CodeRenderable` with `_hadInitialContent=false`, `_drawUnstyledText=false`, `_streaming=true` renders NOTHING until async highlight resolves (line 4279-4288: `_shouldRenderTextBuffer = false`)
- No retry path for the single async highlight pass → raw `**` markers if highlight fails/arrives late
- Visible blank-then-appear flash at turn completion

### Fix iteration 7 (current): Streaming toggle (`streaming={!completed}`)
Correct per opentui contract for the top-level `<markdown>`, but:
- Child prose `CodeRenderable` instances are forced back to `streaming=true` by `applyMarkdownCodeRenderable` (line 9518)
- Double `updateBlocks` at completion produces intermediate visible state
- Event batching split can cause two render passes, making the intermediate state visible for 16ms

---

## Fix Recommendations (ordered by risk/impact)

### R1 (Adapter): Batch reconcile + completed into one event

**File:** `services/atlas-terminal/src/adapter/chat.ts`

Emit `time.completed` as part of the `message.part.updated` from `llm_call`, or add a flag to the `llm_call` event that the store handler uses to also set `completed`. This ensures both changes land in the same SolidJS batch regardless of EventBus timing.

**Risk:** Low. Only changes event emission shape, not data.
**Impact:** Eliminates the two-render-pass scenario entirely.

### R2 (opentui vendor): Propagate parent streaming to child prose blocks

**File:** `node_modules/@opentui/core/index-fedv7szb.js` lines 9510-9519

Change `applyMarkdownCodeRenderable` to set `renderable.streaming = this._streaming` instead of hardcoding `true`. This matches the pattern in `applyCodeBlockRenderable` (line 9529).

**Risk:** Medium. Vendored compiled code — needs to be patched and tracked across updates.
**Impact:** Child prose blocks correctly exit streaming mode at completion, allowing clean text buffer updates.

### R3 (TextPart): Delay streaming toggle by one tick

**File:** `services/atlas-terminal/src/tui/routes/session/index.tsx`

Use a `createEffect` that delays the streaming flip by one microtask after `completed` becomes truthy. This ensures the content update from reconcile is fully processed before the streaming setter fires.

**Risk:** Low. Purely local timing fix.
**Impact:** Prevents double `updateBlocks` from overlapping with the content change.

### R4 (TextPart): Keep streaming=true permanently, finalize on unmount

**File:** `services/atlas-terminal/src/tui/routes/session/index.tsx`

Never flip `streaming` to false during the message's lifetime. Instead, on message removal or session switch, the component unmounts and the renderable is destroyed. This avoids the double `updateBlocks` entirely.

**Risk:** Low. Matches the original `streaming={true}` behavior that was visually smooth.
**Impact:** Trades correct trailing-token finalization (which is only needed for table rendering) for visual stability. Prose-only messages are unaffected.

---

## Recommended Approach

**Combine R1 + R2:**
1. R1 ensures reconcile + completed are always in the same SolidJS batch → one render pass → one `updateBlocks` call sequence
2. R2 ensures child prose blocks correctly exit streaming mode → clean text buffer update → no stale styled text

If R2 cannot be applied (vendored code), R1 + R3 is the fallback: batch the events, and delay the streaming toggle to avoid the double updateBlocks.

---

## Files Touched

| File | Lines | Role |
|------|-------|------|
| `services/atlas-terminal/src/adapter/chat.ts` | 368-471 | Event emission: reconcile + completed |
| `services/atlas-terminal/src/tui/context/sdk.tsx` | 48-73 | Event batching: 16ms window |
| `services/atlas-terminal/src/tui/context/sync.tsx` | 121-6110, 831-10110 | Store: message + part updates |
| `services/atlas-terminal/src/tui/routes/session/index.tsx` | 1560-1603 | TextPart: streaming toggle |
| `node_modules/@opentui/core/index-fedv7szb.js` | 9477-9519, 4173-4288 | MarkdownRenderable child blocks |

## Verification

Cannot be verified from this environment (no interactive TUI). Requires operator UAT:
1. Send "hey who are you" — verify no text duplication after completion
2. Verify bold/markdown formatting renders correctly (no raw `**` markers)
3. Verify no flash/blank/gap at turn completion
4. Test with long multi-paragraph responses to stress the trailing unstable zone
5. Test with fenced code blocks to ensure they still work correctly
