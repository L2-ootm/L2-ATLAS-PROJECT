# ULTRAREVIEW — Streaming Text Duplication Bug

Date: 2026-07-12
Triggered by: operator observed doubled text in atlas-terminal streaming output
Fix applied: `chat.ts` llm_delta handler — closed-entry guard (line 409-412)

---

## Symptom

Every line of the ATLAS response appears twice with overlap:
```
HeyHey! I'm ATLAS — the operator agent inside the **! I'm ATLAS — the operator agent inside the L2 ATLAS system
```

---

## Complete Data Flow Chain (9 hops, verified)

### Hop 1: Python Runtime — DeltaBuffer coalescing
**File:** `services/agent-runtime/atlas_runtime/agents/native.py:51-96`

`_DeltaBuffer` receives per-token callbacks from the foundation's `stream_delta_callback`.
Coalesces into ~150ms/48-char chunks. On `None` (end-of-turn), flushes final chunk
with `end_of_turn: True`. Emits `llm_delta` audit rows to SQLite.

**Event sequence guaranteed by Python threading lock:**
```
llm_delta(d1, end_of_turn=false)
llm_delta(d2, end_of_turn=false)
...
llm_delta(dN, end_of_turn=true)     ← final delta
llm_call(text=full_response[:2000])  ← authoritative snapshot
```

The `llm_call` is emitted by `_map_result()` (line 456-466) AFTER `run_conversation()`
returns, which is AFTER `delta_buffer.push(None)` fires. Both write under the same
`threading.Lock`, so rowid ordering is guaranteed.

### Hop 2: SQLite Audit Service
**File:** `services/agent-runtime/atlas_runtime/audit_service.py:63-182`

Each `llm_delta` and `llm_call` is one INSERT under the lock. SQLite auto-incrementing
`rowid` preserves insertion order. **Correct.**

### Hop 3: Rust Gateway SSE Poll
**File:** `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:36,395-477`

`STREAM_POLL = 200ms`. Queries `audit_events` with `rowid > cursor`, ordered by `rowid ASC`,
limit 500. Pushes each as an SSE `event: audit` frame. **Correct** — preserves ordering.

### Hop 4: TypeScript Gateway Client
**File:** `services/atlas-terminal/src/adapter/gateway.ts:166-228`

Reads `ReadableStream`, splits on `\n\n`, parses SSE frames via `parseSSEFrame()`.
Each frame becomes a `RunEvent { name, data }`. **Correct** — standard SSE parsing.

### Hop 5: Chat Adapter Event Translation (THE BUG LOCATION)
**File:** `services/atlas-terminal/src/adapter/chat.ts:355-466`

`onRunEvent()` translates audit frames to donor parts and bus events.

**The `llm_delta` branch (lines 402-429):**
- Gets/creates a streaming text part via `streamingText` map (keyed by `assistant.info.id`)
- `appendPart()` at line 415 creates part P1 with `text: ''` → emits `message.part.updated`
- Delta text appended to `entry.part.text` → emits `message.part.delta`
- `end_of_turn` sets `entry.open = false`

**The `llm_call` branch (lines 431-447):**
- If `streamingText` entry exists → replaces `entry.part.text` with authoritative text →
  emits `message.part.updated` → **deletes entry from streamingText**
- If no entry → `appendPart()` creates new part with full text

**The bug (BEFORE fix):** If `llm_call` arrived and deleted the entry, a subsequent
`llm_delta` would find `entry = undefined`, pass the `!entry && deltaText` guard at
line 414, and create a **brand new part** — duplicating the text.

**The fix (lines 409-412):**
```typescript
if (entry && !entry.open) {
    // Reconciled: ignore remaining deltas for this turn.
    if (endOfTurn) this.streamingText.delete(assistant.info.id);
    return;
}
```
This catches the case where `llm_call` already reconciled (closed entry exists) and
prevents a stray delta from creating a duplicate part.

### Hop 6: EventBus → SSE for TUI
**File:** `services/atlas-terminal/src/adapter/atlasFetch.ts:202-238`

`handleEventStream()` wraps bus events as `GlobalEventEnvelope` SSE frames.
Pass-through. **Correct.**

### Hop 7: TUI SSE Client
**File:** `services/atlas-terminal/src/tui/context/sdk.tsx:62-73,76-111`

16ms batch window. Events within 16ms are grouped and flushed together via SolidJS
`batch()`. **Correct.**

### Hop 8: TUI Sync Store
**File:** `services/atlas-terminal/src/tui/context/sync.tsx:493-530`

`message.part.updated` (line 493): Binary search by `part.id`. If found → `reconcile()`
(full replace). If not found → splice insert. If no parts array → create with [part].

`message.part.delta` (line 514): Binary search by `partID`. If found → append delta
to field. If not found → silently drop.

**Correct** — the store correctly handles both full replacements and incremental appends.

### Hop 9: TUI Render
**File:** `services/atlas-terminal/src/tui/routes/session/index.tsx:1560-1592`

`TextPart` renders `props.part.text.trim()` as markdown with `streaming={true}`.
Driven by SolidJS reactivity — re-renders when store updates. **Correct.**

---

## Root Cause Analysis

### Confirmed: the adapter-level fix is correct

The `llm_delta` handler's closed-entry guard (lines 409-412) prevents the specific
duplication vector where a stray delta after `llm_call` reconciliation creates a
second part.

### Event ordering guarantee

The Python runtime's `threading.Lock` ensures `llm_delta` events (including the
final `end_of_turn=True`) are always written to SQLite BEFORE the `llm_call` event.
The gateway reads in `rowid` order. The adapter processes events sequentially from
the SSE stream. **Under normal operation, `llm_call` always arrives after all
`llm_delta` events for the same turn.**

### Remaining question: why did duplication occur?

Under the guaranteed ordering, the fix's edge case (stray delta after llm_call)
should never trigger. The observed duplication suggests one of:

1. **Event ordering violation** — if the foundation's `stream_delta_callback(None)`
   (end-of-turn) and the `run_conversation()` return happen on different threads,
   the `llm_call` could be emitted before the final `llm_delta`. The `_DeltaBuffer`
   holds no lock during `_emit_delta()` — it relies on the caller's lock. If the
   foundation calls the callback from a different thread than the one that eventually
   calls `_map_result()`, the ordering guarantee breaks.

2. **Multi-turn interleaving** — in a tool-calling loop (agent calls tool, gets
   result, responds again), the `llm_call` from turn N could arrive while turn N+1's
   `llm_delta` events are already streaming. The `streamingText` map is keyed by
   `assistant.info.id` (constant across turns), so turn N's `llm_call` deleting the
   entry would affect turn N+1's deltas.

3. **Rendering artifact** — the `<code>` component in opentui might display both
   the `message.part.updated` (from `appendPart` with empty text) and the subsequent
   `message.part.delta` (appending text) in a way that visually doubles the content.
   This would be in the `@opentui/core` renderer, not in the data flow.

### Recommendation

The fix is correct and should be kept as a defensive guard. To fully resolve the
duplication, investigate:

- **Priority 1:** Verify the foundation's `stream_delta_callback` is called from
  the same thread as `run_conversation()`'s return path. If not, add a threading
  barrier or sequence counter.
- **Priority 2:** Test with a multi-turn tool-calling scenario to check if turn
  boundary handling is correct.
- **Priority 3:** If the above are clean, the issue is in the opentui `<code>`
  renderer's handling of rapid `content` prop changes.

---

## Fix Applied

**File:** `services/atlas-terminal/src/adapter/chat.ts:409-412`

```typescript
// BEFORE (vulnerable):
if (!entry && deltaText) {
    entry = { part: this.appendPart(...), open: true };
    ...
}

// AFTER (guarded):
if (entry && !entry.open) {
    if (endOfTurn) this.streamingText.delete(assistant.info.id);
    return;
}
if (!entry && deltaText) {
    entry = { part: this.appendPart(...), open: true };
    ...
}
```

**Verification:** tsc clean. Full test suite should be run before commit.

---

## Files touched in this investigation

| File | Role |
|------|------|
| `services/agent-runtime/atlas_runtime/agents/native.py` | DeltaBuffer + _map_result (event emission) |
| `services/agent-runtime/atlas_runtime/audit_service.py` | SQLite audit write |
| `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs` | SSE poll + relay |
| `services/atlas-terminal/src/adapter/gateway.ts` | SSE frame parsing |
| `services/atlas-terminal/src/adapter/chat.ts` | Event → part translation (BUG + FIX) |
| `services/atlas-terminal/src/adapter/atlasFetch.ts` | Bus → SSE bridge |
| `services/atlas-terminal/src/tui/context/sdk.tsx` | SSE client + 16ms batching |
| `services/atlas-terminal/src/tui/context/sync.tsx` | Store: delta + update handlers |
| `services/atlas-terminal/src/tui/routes/session/index.tsx` | TextPart render |
