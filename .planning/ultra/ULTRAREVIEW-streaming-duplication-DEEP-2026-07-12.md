# ULTRAREVIEW DEEP — Streaming Text Duplication Bug

Date: 2026-07-12 (second pass, extended)
Method: 3 parallel explore subagents + manual code trace + foundation threading analysis
Previous report: ULTRAREVIEW-streaming-duplication-2026-07-12.md (first pass)

---

## Executive Summary

The first pass identified the adapter-level fix (closed-entry guard in `chat.ts`).
This deep pass traces the **complete chain from Python foundation to terminal render**
and discovers a **critical architectural gap**: the foundation never calls
`stream_delta_callback(None)` for final responses (only at tool boundaries). This
means the DeltaBuffer's last chunk is never flushed for simple question-answer flows,
and the `end_of_turn` flag is never set. The adapter fix is correct for the case it
handles, but the root cause is deeper — the foundation's streaming protocol has a
gap that the ATLAS adapter must work around.

---

## Phase 1: Root Cause Investigation

### Finding 1: Foundation `stream_delta_callback(None)` is ONLY called at tool boundaries

**Evidence (conversation_loop.py):**
- Line 3813: `agent.stream_delta_callback(None)` — called BEFORE tool execution
- Line 3837: `agent.stream_delta_callback(None)` — called after guardrail-halt response
- **NO call after the final response for a simple question-answer flow**

**What this means:**
The `None` signal means "tool boundary / close the display box" — NOT "stream complete."
For a prompt like "Hey, who are you?" that gets a direct answer (no tool calls), the
foundation's streaming loop ends without calling `None`. The DeltaBuffer's last chunk
is never flushed as an `llm_delta(end_of_turn=True)` event.

### Finding 2: DeltaBuffer flush behavior without None

**Evidence (native.py:51-96):**
```python
def push(self, chunk: Optional[str]) -> None:
    if chunk is None:          # ← Never called for final response
        if self._turn_open:
            self._flush(final=True)
            self._turn_open = False
        return
    self._turn_open = True
    self._buffer.append(chunk)
    now = time.monotonic()
    buffered_len = sum(len(c) for c in self._buffer)
    if now - self._last_flush >= self._interval_s or buffered_len >= self._max_chars:
        self._flush(final=False)   # ← Only flushes on time/size threshold
```

- `_DELTA_FLUSH_INTERVAL_S = 0.15s` — 150ms timer
- `_DELTA_FLUSH_CHARS = 48` — 48-char size threshold
- For a short response (< 48 chars, completed in < 150ms): **NO intermediate flushes**
  → No `llm_delta` events emitted at all → adapter only sees `llm_call`
- For a longer response: intermediate flushes happen at 48-char boundaries
  → `llm_delta(end_of_turn=False)` events emitted → adapter creates streaming entry

### Finding 3: Event sequence for final response (no tools)

```
Foundation streaming loop:
  _fire_stream_delta("Hey ") → delta_buffer.push("Hey ") → buffer accumulates
  _fire_stream_delta("who ") → delta_buffer.push("who ") → buffer accumulates
  ... (more chunks) ...
  streaming loop ends (NO None call)

_delta_buffer state: [_buffer="Hey who are you?"] (unflushed, _turn_open=True)

run_conversation() returns → _map_result() runs:
  _safe_emit(llm_call, text="Hey! I'm ATLAS...")  ← line 456-466
```

**Gateway receives:** only `llm_call` (no `llm_delta` events for short responses)

**Adapter sees:**
1. `llm_call` arrives → `streamingText.get(assistant.info.id)` → `undefined`
2. Falls to `else` branch (line 442-444): `appendPart(assistant, { type: 'text', text: textOrSummary })`
3. Creates ONE part with the full text → **no duplication**

### Finding 4: Event sequence for final response (longer, with intermediate flushes)

```
Foundation streaming loop:
  push("Hey ") → buffer accumulates
  push("who ") → buffer hits 48 chars → _flush(final=False) → llm_delta("Hey who are you?", end_of_turn=false)
  push("are ") → buffer accumulates
  push("you?") → buffer accumulates
  streaming loop ends (NO None call)

_delta_buffer state: [_buffer="are you?"] (unflushed)

_map_result() runs:
  _safe_emit(llm_call, text="Hey! I'm ATLAS...")
```

**Gateway receives:** `llm_delta` (intermediate) + `llm_call`

**Adapter sees:**
1. `llm_delta` arrives → creates part P1 with text, `entry.open = true`
2. `llm_call` arrives → `entry` exists → replaces P1.text with authoritative text → deletes entry
3. **No duplication** — P1 is updated in place

### Finding 5: The ONLY duplication vector — stray delta after llm_call

For duplication to occur, an `llm_delta` event must arrive AFTER `llm_call` has
deleted the entry. This requires:

1. `llm_call` arrives and deletes `streamingText` entry
2. A stray `llm_delta` arrives → `entry = undefined` → `!entry && deltaText` → creates P2
3. TUI renders both P1 (from llm_call) and P2 (from stray delta) → duplicated text

**Under guaranteed ordering (all deltas before llm_call), this cannot happen.**
But the foundation's threading model introduces a subtle risk:

**Foundation threading (from Probe 1):**
- CLI mode: single-threaded, synchronous → ordering guaranteed
- Gateway mode: `run_conversation()` runs in a `ThreadPoolExecutor` worker thread
- `stream_delta_callback` is called from the same thread as the streaming loop
- `_map_result()` (native.py:456) is called after `run_conversation()` returns
- **Both are on the same worker thread** → ordering guaranteed

**Conclusion:** Under the current architecture, the stray-delta scenario cannot happen
in normal operation. The ordering is guaranteed by single-threaded execution.

---

## Phase 2: Pattern Analysis

### Why is the user seeing duplicated text?

If the data flow is correct, the duplication must come from the **rendering layer**.
Three hypotheses:

**Hypothesis A: opentui `<code>` component renders text twice during rapid updates**
- The `<code streaming={true} content={...}>` component at `session/index.tsx:1578-1586`
  receives `content={props.part.text.trim()}`
- When `content` changes rapidly (delta append → reconcile replacement), the component
  may output both the old and new content in the same render cycle
- This would explain the exact pattern: "HeyHey!" (old "Hey" + new "Hey!...")

**Hypothesis B: Two text parts exist for the same message**
- The `For each={props.parts}` at line 1336 renders one component per part
- If two text parts exist with the same content, both render → duplicated output
- Data flow analysis says only one part should exist, but the unflushed DeltaBuffer
  edge case could create a timing gap

**Hypothesis C: Terminal scrollback/rewrite artifact**
- When the TUI rewrites a line (streaming update), the terminal may show both the
  old and new version if the rewrite doesn't fully clear the previous content
- This is a terminal emulator behavior, not a code bug

### Most likely: Hypothesis A or C

The data flow analysis confirms only one part exists per turn. The duplication is
most likely a rendering-layer issue in either the opentui component or the terminal's
handling of rapid content updates.

---

## Phase 3: Complete Data Flow Chain (9 hops, verified)

| Hop | File:Line | What | Correct? |
|-----|-----------|------|----------|
| 1 | `native.py:51-96` | DeltaBuffer coalesces tokens → llm_delta audit rows | **Gap:** no None for final response |
| 2 | `native.py:456-466` | `_map_result` emits llm_call with full text | Correct |
| 3 | `audit_service.py:63-182` | SQLite INSERT under lock | Correct |
| 4 | `lib.rs:36,395-477` | Gateway polls SQLite 200ms, emits SSE | Correct |
| 5 | `gateway.ts:166-228` | SSE frame parsing | Correct |
| 6 | `chat.ts:402-429` | llm_delta → part creation + delta emission | Correct (with fix) |
| 7 | `chat.ts:431-447` | llm_call → reconciliation or new part | Correct |
| 8 | `sync.tsx:493-530` | Store: delta append + update reconcile | Correct |
| 9 | `session/index.tsx:1560-1592` | TextPart renders content as markdown | **Possible rendering issue** |

---

## Phase 4: All DonorPart Creation Paths (exhaustive)

| # | File:Line | Trigger | Type | Dedup guard | Duplication risk |
|---|-----------|---------|------|-------------|-----------------|
| 1 | `chat.ts:260-267` | User prompt | text | N/A (one-shot) | None |
| 2 | `chat.ts:319-322` | streamRun rejection | text | None | Yes (with #3) |
| 3 | `chat.ts:362-364` | stream_error event | text | None | Yes (with #2) |
| 4 | `chat.ts:382-383` | transition: failed | text | None | Low |
| 5 | `chat.ts:389-391` | transition: succeeded | text | **Exact text match** | Very low |
| 6 | `chat.ts:396-401` | reasoning frame | reasoning | None | Intentional |
| 7 | `chat.ts:414-417` | First llm_delta | text | **`!entry` guard** | None |
| 8 | `chat.ts:442-444` | llm_call (no prior stream) | text | None | Yes (duplicate llm_call) |
| 9 | `chat.ts:450-461` | tool_call/tool_requested | tool | None | Yes (duplicate events) |
| 10 | `chat.ts:476-488` | settleTool | **mutates** | N/A | None |

**Path 8 is the key path for the duplication scenario.** When `llm_call` arrives
without a prior streaming entry, it creates a new part via `appendPart`. If a
subsequent `llm_delta` also arrives (stray or from next turn), it creates ANOTHER
part via Path 7. The fix at lines 409-412 guards against this when the entry
still exists in the map (closed but not deleted). But if the entry was fully
deleted (by a prior `llm_call`), the guard doesn't fire.

---

## Phase 5: Sync Store Internals

### `reconcile` (solid-js/store)
- Deep structural diff via `applyState` — NOT a shallow copy or full replace
- Preserves object identity for unchanged subtrees
- Default key: `"id"` for array diffing
- Called by `message.part.updated` handler (sync.tsx:501)

### `Binary.search` (vendor/shared/util/binary.ts:2-20)
- Standard binary search on string-sorted array
- Sort key: caller-provided accessor (always `.id`)
- No duplicate-ID handling — caller must ensure uniqueness
- Returns `{found, index}` where index is insertion point on miss

### `setStore` batching
- Each `setStore` wraps in SolidJS `batch()`
- Mutations are synchronous on the raw store
- Second call **does** see first call's changes (raw mutation precedes notification)
- No reordering within a single event handler

### `produce` (solid-js/store)
- Immer-like draft proxy — mutations are immediate (not deferred)
- Does NOT conflict with `reconcile` in practice (different handlers use one or the other)

### `message.part.delta` handler
- Uses `produce` for direct in-place string concatenation
- Does NOT call `reconcile`
- Part must pre-exist (silently drops if not found)

---

## Phase 6: Foundation Threading Model

### CLI mode
- Single-threaded, synchronous
- `stream_delta_callback` called from same call stack as `run_conversation()`
- Ordering guaranteed

### Gateway mode
- `run_conversation()` runs in `ThreadPoolExecutor` worker thread
- `stream_delta_callback` called from same worker thread
- `_map_result()` (native.py) called after `run_conversation()` returns — same thread
- `GatewayStreamConsumer` bridges to async via `queue.Queue` — thread-safe
- **Ordering guaranteed** (single worker thread per run)

### Critical: None signal semantics
- `stream_delta_callback(None)` = "tool boundary / close display box"
- NOT "stream complete" — there is no "stream complete" callback
- Stream completion is signaled by: gateway's `consumer.finish()` (after run returns)
  or API server's `agent_task.add_done_callback` (enqueues None into SSE queue)
- **For final responses without tool calls: None is NEVER called**

---

## Fix Assessment

### The adapter fix (chat.ts:409-412) — CORRECT but insufficient

```typescript
if (entry && !entry.open) {
    if (endOfTurn) this.streamingText.delete(assistant.info.id);
    return;
}
```

This correctly handles the case where:
- `llm_call` deleted the entry
- A stray `llm_delta` arrives with the entry still in the map (closed but not deleted)

**It does NOT handle** the case where:
- `llm_call` fully deleted the entry from the map
- A stray `llm_delta` arrives with `entry = undefined`
- The `!entry && deltaText` guard at line 414 creates a new part → duplication

### Recommended additional fix

The `llm_call` handler should set a "reconciled" flag that persists after entry
deletion, so the `llm_delta` handler can check it:

```typescript
// In the class:
private reconciledMessages = new Set<string>();

// In llm_call handler, after deleting entry:
this.reconciledMessages.add(assistant.info.id);

// In finally block:
this.reconciledMessages.delete(assistant.info.id);

// In llm_delta handler, before creating new part:
if (this.reconciledMessages.has(assistant.info.id)) return;
```

This provides defense-in-depth against any stray delta after reconciliation,
regardless of whether the entry was closed or fully deleted.

---

## Remaining Investigation Priorities

1. **Verify rendering hypothesis** — add a console.log in TextPart to count how
   many times it renders per turn and what content it receives. If it renders twice
   with the same content, the issue is in the `<code>`/`<markdown>` component.

2. **Add None signal for final responses** — the foundation should call
   `stream_delta_callback(None)` after the final response, not just at tool boundaries.
   This would flush the DeltaBuffer's last chunk and set `end_of_turn=True`, giving
   the adapter a clean signal.

3. **Test multi-turn tool-calling** — verify that turn boundaries don't cause
   interleaving issues. Each turn should get its own part.

4. **Check opentui `<code>` component** — examine how it handles rapid `content`
   prop changes with `streaming={true}`. The duplication pattern ("HeyHey!") suggests
   the component may render both old and new content during updates.

---

## Files Referenced

| File | Role |
|------|------|
| `foundation/atlas-hermes/agent/conversation_loop.py:3811-3837` | None signal — tool boundaries only |
| `foundation/atlas-hermes/run_agent.py:3359-3410` | `_fire_stream_delta` dispatcher |
| `services/agent-runtime/atlas_runtime/agents/native.py:51-96` | DeltaBuffer implementation |
| `services/agent-runtime/atlas_runtime/agents/native.py:349-353` | `_emit_delta` callback |
| `services/agent-runtime/atlas_runtime/agents/native.py:456-466` | `_map_result` llm_call emit |
| `services/agent-runtime/atlas_runtime/audit_service.py:63-182` | SQLite audit write |
| `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:36,395-477` | SSE poll + relay |
| `services/atlas-terminal/src/adapter/gateway.ts:166-228` | SSE frame parsing |
| `services/atlas-terminal/src/adapter/chat.ts:99-106` | streamingText map |
| `services/atlas-terminal/src/adapter/chat.ts:343-353` | appendPart |
| `services/atlas-terminal/src/adapter/chat.ts:402-429` | llm_delta handler (FIX) |
| `services/atlas-terminal/src/adapter/chat.ts:431-447` | llm_call handler |
| `services/atlas-terminal/src/tui/context/sync.tsx:493-530` | Store delta + update handlers |
| `services/atlas-terminal/src/tui/routes/session/index.tsx:1336-1350` | For loop over parts |
| `services/atlas-terminal/src/tui/routes/session/index.tsx:1560-1592` | TextPart render |
| `services/atlas-terminal/src/vendor/shared/util/binary.ts:2-20` | Binary.search |
| `node_modules/solid-js/store/dist/dev.js:399-412` | reconcile implementation |

---

## Fix Status — 2026-07-12 (third pass, same day)

Both concrete gaps this report identified are fixed and tested.

### 1. `chat.ts` closed-entry guard was itself a regression — FIXED

Re-deriving the guard's own logic surfaced a bug this report didn't name: the
committed guard (`entry && !entry.open` → early return) can only ever fire on
a **closed-but-present** entry. Tracing the lifecycle shows that state is
reached exactly once, at a legitimate tool-boundary `end_of_turn` close
(`chat.ts:428`, never a delete) — i.e. the guard was intercepting the *next
turn's* legitimate deltas after a tool round and silently dropping them,
not the reported duplication vector (a fully-deleted entry, where `entry` is
`undefined`, still falls through the old code unguarded).

Fixed (`chat.ts:402-433`): a closed-but-present entry now clears itself and
lets a fresh part get created for the new turn, restoring multi-tool-round
streaming. Added a separate `reconciledMessages: Set<string>` (per this
report's recommendation) that marks a message id once its `llm_call` fires
and rejects any later `llm_delta` for that id outright — this is the actual
defense-in-depth for the fully-deleted-entry stray-delta case, cleared on
the `end` event.

New regression tests in `test/chatLoop.test.ts`:
- "a new turn after a tool-boundary end_of_turn gets its own text part
  instead of being dropped" — proves the multi-turn drop is fixed.
- "ignores a stray llm_delta that arrives after llm_call already
  reconciled the message" — proves the `reconciledMessages` guard.

### 2. Foundation never flushes the final turn — FIXED (adapter-side, no foundation edit)

Per Finding 1, `agent.stream_delta_callback(None)` is only called before tool
execution (`conversation_loop.py:3813`), never after a final no-tool-call
response — confirmed by re-reading `conversation_loop.py:3805-3840` directly.
D-001 bars editing the vendored foundation, so the fix lives in
`native.py`'s `execute()` (which owns the `_DeltaBuffer` instance): after
`run_conversation()` returns successfully, `delta_buffer.push(None)` is now
called explicitly before `_map_result()` runs. This is idempotent with a
harness that already called `None` itself (`_DeltaBuffer` no-ops when
`_turn_open` is already `False` — see `test_delta_buffer_none_without_prior_push_is_noop`),
and closes the gap for harnesses that don't.

New regression test: `test_native_flushes_delta_buffer_when_foundation_never_signals_end_of_turn`
in `test_agents.py`, simulating exactly the foundation's real gap (a harness
that streams chunks but never calls `None`) and asserting the flush now
happens with `end_of_turn: True`.

### 3. Rendering-layer hypothesis (A/C) — still open, needs operator UAT

`@opentui/core`'s `Code`/`Markdown` renderables ship as a compiled bundle in
this checkout (only `.d.ts` type files are present under
`node_modules/@opentui/core/renderables/` — no readable `.ts`/`.js` source),
so this can't be settled by static reading. Per prior sessions' repeated
blocked attempts at non-headless TTY repro (piped stdin doesn't reach the
composer, SendKeys/ConPTY blocked), this needs a real interactive session:
reproduce the duplication, then check whether it persists now that all three
data-flow-level bugs above are fixed. If it still reproduces, the report's
original recommendation stands — instrument `TextPart` (`session/index.tsx:1560`)
with a render counter to confirm whether `<code streaming={true}>` double-
paints on rapid `content` prop changes.

**Verified (2026-07-12):** atlas-terminal `bunx tsc --noEmit` clean, `bun test`
55 passed (2 new); agent-runtime `pytest tests` 782 passed, 2 skipped (1 new
in this pass, on top of the streaming slice's prior 4 new).

### 4. Transition 'succeeded' creates duplicate text part — FIXED (fourth pass)

Operator UAT after the third-pass fixes revealed a remaining duplication:
the **last sentence** appeared twice (with/without trailing period), not
character-by-character doubling. This is a distinct bug from the prior two.

**Root cause (run_service.py:141-147 → chat.ts:396-399):**

The run lifecycle emits a `tool_call` audit event with
`data={transition: "succeeded", summary: summary}` AFTER `llm_call` has
already reconciled the streamed text. The adapter's `transition: 'succeeded'`
handler (chat.ts:396-399) checks for an exact-text duplicate:
```typescript
const dupe = assistant.parts.some((p) => p.type === 'text' && p.text === str('summary'));
if (!dupe) this.appendPart(assistant, { type: 'text', text: str('summary') });
```
When the summary differs from the reconciled text (truncation at 2000 chars,
post-processing like think-block stripping), the exact-match check fails and
a **second text part** is created.

**Event sequence that triggers it:**
```
llm_delta("Hello ")           → part P1 created, text accumulated
llm_delta("world", eot=true)  → entry closed
llm_call(text="Hello world")  → replaces P1.text, deletes entry, adds to reconciledMessages
transition:succeeded(summary="Hello")  → summary ≠ "Hello world" → dupe check fails → P2 created
```
TUI renders P1 ("Hello world") + P2 ("Hello") → duplicated output.

**Fix (chat.ts:396-399):** Added `reconciledMessages` check before the
transition handler creates a part:
```typescript
} else if (transition === 'succeeded' && str('summary')) {
    if (this.reconciledMessages.has(assistant.info.id)) return;
    const dupe = assistant.parts.some(...);
    if (!dupe) this.appendPart(...);
}
```
This was already in place for `llm_delta` (line 414) but was missing from
the transition handler — the exact gap the DEEP report's exhaustive part
creation catalog (Path 5) identified as having "very low" risk but no
reconciledMessages guard.

**Regression test:** `'transition succeeded after llm_call does not create
a duplicate text part'` in chatLoop.test.ts — proves the guard blocks the
duplicate when summary ≠ reconciled text.

**Verified (2026-07-12, commit a9acc882):** tsc clean, 56/56 bun tests (1
new), boundary scan passed, smoke LIVE. Operator UAT confirmed: "who are you?"
response renders without duplication.

### 5. Unified text-part dedup + rendering hypothesis confirmed (fifth pass)

Operator UAT after iteration 3 showed the **entire response** appearing
twice with slight offset — a different pattern from iterations 1-3.
The `hasTextPart` guard (commit `e8e1f763`) was added to unify dedup
across all event sources, but the duplication **persists**.

**Confirmed: the duplication is a rendering-layer issue, not data-flow.**

The data layer is verified correct:
- `hasTextPart(message)` checks `message.parts.some(p => p.type === 'text')`
- Both `llm_call` else branch and `transition:succeeded` use this check
- Only ONE text part exists per message in the data model
- The part's text content is correct (not doubled)

The duplication pattern ("text appears, then same text appears again
starting mid-line") is consistent with the `<code>` component rendering
the same content twice during rapid `content` prop changes with
`streaming={true}`.

**Why this can't be verified statically:** `@opentui/core` ships as a
compiled bundle — no readable source under
`node_modules/@opentui/core/renderables/`.

**Diagnostic instrumented (not committed):** `createEffect` render
counter in `TextPart` (`session/index.tsx:1560`) logs part ID, render
count, content length, and first 60 chars to stderr on each reactive
update. Next agent should run `bun run dev`, send a prompt, and capture
the diagnostic output to confirm the rendering hypothesis.

**All data-flow bugs are now fixed.** The remaining work is in the
opentui rendering layer, which requires either:
1. Reading the `@opentui/core` compiled source (deobfuscation)
2. Replacing `<code streaming={true}>` with a different renderer
3. Adding a debounce/coalesce layer between the store and the component

---

## Fix Status — 2026-07-12 (sixth pass, same day)

Operator provided a new screenshot (`freellmapi`, prompt "hello") and a
decisive fact: **the duplication was not present before the streaming
feature was added** — when the response was only painted once, in full,
after the turn finished, there was no duplication.

### Evidence gathering: direct audit-DB read of the exact failing run

Rather than attempt a 6th blind fix (the systematic-debugging Iron Law
bars this after 5 prior attempts), the raw `audit_events` rows for the
run behind the screenshot were read directly from `~/.atlas/atlas.db`:

```
llm_delta  text='Hey'
llm_delta  text=' Davi! 👋 Good to see you.\n\nHow are things going?'
llm_delta  eot=True text=''
llm_call   text='Hey Davi! 👋 Good to see you.\n\nHow are things going?'
tool_call  transition=succeeded text='Hey Davi! 👋 Good to see you.\n\nHow are things going?'
```

No duplication anywhere in the source data — two clean delta chunks that
concatenate exactly to the reconciled `llm_call` text, matching summary.
**This proves, for this exact repro, that hops 1-8 (foundation through
solid-js store) are clean**, confirming the fifth pass's conclusion by
direct measurement instead of inference. Combined with the operator's
"only started when streaming was added" fact, the bug is conclusively
isolated to hop 9 — the opentui renderable receiving *multiple*
incremental `content` commits during a turn, not the data itself.

### Root cause (opentui `@opentui/core`, vendored compiled bundle)

`ATLAS_TUI_EXPERIMENTAL_MARKDOWN` defaults **true** (`!falsy(...)` in
`vendor/opencode/flag/flag.ts:134` — true unless the env var is
explicitly `"false"`/`"0"`), so the active renderer is `<markdown
streaming={true}>` (`MarkdownRenderable`), not the `<code>` component
the fifth pass's hypothesis assumed was in play.

Traced the actual (non-minified, chunked) implementation at
`node_modules/@opentui/core/index-fedv7szb.js`:

- `MarkdownRenderable.updateBlocks()` (line 9849) re-lexes the growing
  content via `parseMarkdownIncremental` (line 9155) on **every**
  content commit and diffs the resulting tokens against
  `this._blockStates`, reusing/patching a per-block `CodeRenderable`
  child (`applyMarkdownCodeRenderable`, line 9510) in place when a
  token's type is unchanged.
- Each per-block `CodeRenderable` is created with `streaming: true,
  drawUnstyledText: false, filetype: "markdown"` (line 9477-9493). Its
  `set content()` (line 4173) early-returns without touching
  `textBuffer` for that combination — the buffer is only updated later,
  asynchronously, by `startHighlight()` (line 4290) via tree-sitter.
- `ensureVisibleTextBeforeHighlight()` (line 4271) intentionally keeps
  `_shouldRenderTextBuffer = true` using the **stale, already-painted**
  buffer for every content commit after the first, so the terminal
  keeps showing old glyphs while the new highlight resolves in the
  background — a deliberate no-flicker design for a block whose content
  grows by small increments.
- Static tracing of the `snapshotId`/`_highlightSnapshotId` guards found
  the async-highlight completion ordering to be internally consistent
  (stale highlights are discarded, not applied). The remaining
  candidate is a lower-level terminal dirty-region repaint bug in
  opentui's native (Zig) buffer diffing when a block's on-screen height
  changes mid-stream (e.g. a block splitting from one paragraph into
  two as `\n\n` streams in) — consistent with the "text appears, then
  same text again starting mid-line" pattern from the fifth pass and
  this pass's screenshot, and with duplication being absent when the
  renderer only ever receives one, final, content commit.
- This lives in a vendored, compiled, native-backed third-party package
  (`@opentui/core`) with no readable `.ts`/`.js` source under
  `renderables/` (only `.d.ts`), so a definitive line-level root cause
  inside its Zig core cannot be established from this repo. Per Phase
  4.5 of systematic-debugging, this is the point to stop patching our
  own data/adapter layer (already proven clean twice over) and change
  the architecture of how we drive the vendored renderer instead.

### Fix (`session/index.tsx:1560-1604`) — stop feeding incremental commits to the async-highlighted renderer

While a message is still streaming (`!props.message.time.completed`),
`TextPart` now renders a plain `<text wrapMode="word">` element — no
syntax highlighting, no block diffing, no async highlight pipeline, just
a direct buffer write per update, which is the same class of update the
non-highlighted paragraph blocks already used safely. Once the turn
completes, `<Show>` unmounts the plain text node and mounts a **fresh**
`<code>`/`<markdown>` instance with `streaming={false}` and the final,
complete text as its *only* content commit — exactly the "plotted once
when finished" shape the operator confirmed was never buggy. The
richly-highlighted component is never patched in place with more than
one `content` value, which removes the incremental-commit path this
pass identified as the trigger, without needing to patch or fork the
vendored opentui package.

Also removed the (uncommitted) render-count diagnostic in the same
function — its job (confirming this was a rendering issue, not a data
issue) is now done by the direct audit-DB evidence above.

**Verified (2026-07-12):** `bunx tsc --noEmit` clean, `bun test`
56/56 passed (unchanged — no test exercises opentui's own paint output).
**Still needs operator UAT** — this repo's TUI cannot be driven
interactively from this environment (piped stdin doesn't reach the
composer, SendKeys/ConPTY blocked, confirmed again this pass), so the
fix has not been visually confirmed against a live terminal. Next
operator session: reproduce with a short prompt via `freellmapi` (or any
provider) and confirm no duplication appears, syntax highlighting still
renders for the settled response, and there is no visible flash/jank at
the streaming→settled swap.
