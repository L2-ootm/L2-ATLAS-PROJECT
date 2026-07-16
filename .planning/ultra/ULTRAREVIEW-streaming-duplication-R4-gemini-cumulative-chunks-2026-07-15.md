# Streaming duplication R4 — Gemini cumulative-chunk forwarding — Investigation

Operator reported the duplication bug **still occurring** after the R3 fix
(commits `230e7dba`, `13643f7a`) landed. New evidence (screenshot via
Raycast clipboard, `atlas-terminal`, `freellmapi` badge visible, "Build ·
auto" footer): the duplicated message —

```
Qual deles você quer atacar? Ou tem outra parada na cabeça? não fecha
Qual deles você quer atacar? Ou tem outra parada na cabeça?
```

— has **no tool call in flight**. R3's fix (`native.py`'s `_DeltaBuffer`
marker-split) only triggers on the foundation's mid-tool-call silent-retry
path, which requires `_partial_tool_in_flight`. A plain conversational
response with no tool call cannot hit that path — this is a **different,
previously-unconfirmed bug class**.

## Root Cause: freellmapi's Gemini adapter forwards cumulative stream chunks as if they were incremental OpenAI-style deltas

**Exact Failure Point (pre-fix):**
`C:\Users\Davi\Desktop\Projects\freellmapi\server\src\providers\google.ts:583-607`

```typescript
const text = extractText(parts);          // full text of THIS chunk's parts
// ...
yield {
  choices: [{ delta: { content: text } }],  // forwarded as if incremental
  finish_reason: null,
}
```

Gemini's `streamGenerateContent` (`API_BASE.../models/{id}:streamGenerateContent?alt=sse`)
does not guarantee each chunk's `candidates[0].content.parts[].text` is a
disjoint incremental fragment — some response modes (observed here) resend
the full text accumulated so far in each successive chunk. `extractText()`
returns that chunk's text verbatim; the provider then yields it directly as
`delta.content` in an OpenAI-compatible `chat.completion.chunk`, which by
contract must be a true incremental delta. Every downstream consumer
(ATLAS's foundation `stream_delta_callback`, `native.py`'s `_DeltaBuffer`,
`chat.ts`'s `streamingText` accumulator, `sync.tsx`'s `existing + delta`
append) trusts that contract and blindly concatenates — reproducing
Gemini's own cumulative restatement as visible duplicated/overlapping text.

## Chain of Failure

1. **Entry:** Gemini streams `candidates[0].content.parts[].text` chunks
   where a later chunk restates some/all of an earlier chunk's text plus
   new content (cumulative-mode chunking), rather than only new text.
2. **No diff at the adapter boundary:** `google.ts`'s streaming generator
   (`chatCompletion`, ~line 530-624) extracts `text` per chunk and yields it
   unmodified as `delta.content` — no tracking of what was already sent on
   this stream.
3. **Contract violation propagates unchecked:** the OpenAI-compatible
   `chat.completion.chunk` format's `delta.content` field is a documented
   incremental-append contract; freellmapi is the single normalization
   boundary between Gemini's REST API and every OpenAI-shaped consumer, and
   it did not enforce that contract for this provider.
4. **ATLAS trusts the contract everywhere downstream:** `chat_completion_helpers.py`
   → `agent._fire_stream_delta(delta.content)` → `native.py`'s
   `_DeltaBuffer.push()` (pure append, `self._buffer.append(chunk)`) →
   `chat.ts`'s `llm_delta` handler (`entry.part.text = (entry.part.text ??
   "") + deltaText`) → `sync.tsx`'s `message.part.delta` handler (`part[field]
   = existing + delta`) — five independent layers, all correctly implementing
   "append is safe because deltas are incremental," none of which is wrong
   given that assumption.
5. **Failure point:** the assumption was false for this provider under this
   response mode. Each of the prior three fix rounds (R1: rendering-timing,
   R2: opentui `streaming` prop, R3: mid-tool-call retry marker) correctly
   fixed real bugs in their respective layers, but none of them could have
   caught this — the duplicate *content* is already baked into the delta
   stream before it reaches any ATLAS-owned code.

## Why It Fails

This is a **provider-adapter contract violation**, not a bug in ATLAS's
rendering, event bus, or retry logic. It is the mirror image of the R3
finding: R3 was ATLAS's own vendored foundation intentionally breaking the
"no content before a turn boundary" contract for tool-call safety; R4 is an
external proxy (freellmapi, a sibling project, not vendored/D-001-covered)
unintentionally breaking the "delta.content is incremental" contract for a
subset of Gemini responses. Both land in the same visible symptom
(duplicated/overlapping text) because every consumer downstream is a plain
`append`, by design — that's correct once, cheap, and simple, but it has no
error-correction if any upstream layer violates the contract it depends on.

## Proof

- `freellmapi/server/src/providers/google.ts:591-606` (pre-fix) — `text`
  from `extractText(parts)` yielded as `delta.content` with zero comparison
  against previously-yielded text on the same stream.
- The R3 report (`.planning/ultra/ULTRAREVIEW-streaming-duplication-R3-mid-tool-call-retry-2026-07-15.md`,
  "Related Issues" item 6) had already flagged this exact file/mechanism as
  an **unconfirmed structural risk** — this session's new screenshot
  (no tool call present) is the confirming trigger that distinguishes it
  from R3's mechanism.
- `services/atlas-terminal/src/tui/context/sync.tsx:526` is **byte-identical**
  to the MiMo-Code donor's equivalent line (`_EXTERNAL_REPOS/mimo-code/packages/opencode/src/cli/cmd/tui/context/sync.tsx:526`)
  — confirming the append-only delta handler is not an ATLAS-introduced
  regression; MiMo-Code's own TUI carries the same "trust the delta
  contract" design. MiMo-Code doesn't need dedup here because *its* server
  is the sole, first-party source of truth for its own chunking — it never
  faces a third-party proxy normalizing a provider that violates the
  contract. ATLAS's architecture inserts freellmapi as an extra hop with
  its own normalization responsibility, and that hop is where the guarantee
  broke.
- `services/atlas-terminal/src/adapter/chat.ts` was read in full
  (`onRunEvent`, `streamingText` map, `reconciledMessages` guard,
  `hasTextPart` structural check) — already contains defense from three
  prior fix rounds; no additional bug found there for the no-tool-call path.
  `services/atlas-terminal/src/adapter/gateway.ts`'s `streamRun()` — single
  `fetch`, no retry/replay loop, ruled out as a redelivery source.
- `services/atlas-terminal/src/sdk/v2/gen/core/serverSentEvents.gen.ts` —
  a generic SDK-generated SSE client with `Last-Event-ID` resumption; grep
  confirmed `native/atlas-core-rs` (the Rust gateway) never reads
  `Last-Event-ID`, but this client is not on the `/v1/runs/{id}/stream`
  path atlas-terminal actually uses for chat (that's `gateway.ts`'s
  `streamRun()`, a plain non-retrying fetch) — ruled out as contributing to
  this bug, flagged as a latent risk if this SDK client is ever wired to a
  reconnecting consumer without cursor-aware server support.

## Fix Implemented

`freellmapi/server/src/providers/google.ts`:

1. Added `diffCumulativeText(previousText, chunkText)` (exported for direct
   unit testing) — normalizes a chunk against everything already sent on
   this stream:
   - First chunk (`previousText === ''`): forwarded unchanged.
   - Cumulative chunk (`chunkText.startsWith(previousText)`): sliced down to
     just the new suffix.
   - Exact repeat or strict-prefix chunk: dropped (`null`, no new content).
   - Genuinely incremental chunk (no overlap): forwarded unchanged — this
     preserves existing behavior for the common case and for every existing
     test in `google.test.ts`.
2. The streaming generator now tracks `previousText` across the loop and
   yields `diffCumulativeText(previousText, rawText)` instead of `rawText`
   directly; `previousText` accumulates only the genuinely-new suffix.

This makes freellmapi's Gemini adapter honor the same incremental-delta
contract every other provider adapter (`openai-compat`, `cohere`,
`cloudflare`) already satisfies natively, at the one normalization boundary
where it belongs — fixing the bug for **every** consumer of freellmapi
(atlas-terminal, web-ui-react, and any other ATLAS surface), not just the
TUI, without touching ATLAS-owned rendering code again.

Regression tests added (`freellmapi/server/src/__tests__/providers/google.test.ts`):
- `diffCumulativeText` unit tests (first chunk, cumulative diff, incremental
  passthrough, exact-repeat drop, strict-prefix drop).
- `streams: diffs cumulative chunks down to the true incremental delta` —
  an end-to-end streaming test reproducing the operator's exact reported
  text, asserting the joined output is the clean single copy, not doubled.

## Verification

- `freellmapi/server`: `npx tsc --noEmit` — clean.
- `freellmapi/server`: `npx vitest run src/__tests__/providers/google.test.ts`
  — 22/22 passed (6 new).
- **UAT still owed** — this environment cannot drive a live Gemini
  streaming response through freellmapi to visually confirm in a running
  `atlas-terminal`/web-ui-react session. Next operator step: reproduce a
  Gemini-routed ("auto" mode picking Google) chat turn and confirm no
  duplication.

## Related Issues / Recommendations

1. **Implemented (operator correction): a symmetric defensive guard now
   also lives in ATLAS's own `_DeltaBuffer`
   (`services/agent-runtime/atlas_runtime/agents/native.py`).** Initial
   judgment was to fix only at freellmapi's boundary and treat a second
   guard in ATLAS as speculative complexity for an already-fixed path.
   Operator correction: freellmapi is a sidecar to ATLAS — ATLAS is the
   party responsible for the tokens it consumes and must not trust any
   upstream provider mesh member (freellmapi today, potentially others
   later) to always honor the incremental-delta contract. The freellmapi
   fix alone is a patch on one sidecar; ATLAS owning the normalization at
   its actual consumption boundary (`_DeltaBuffer.push()`) is the correct
   architectural placement and the single choke point protecting every
   surface (atlas-terminal, web-ui-react) regardless of which upstream
   sends malformed deltas.

   Added `_diff_cumulative_chunk(previous_text, chunk_text)` — the same
   diff-to-new-suffix logic as freellmapi's `diffCumulativeText`, ported to
   Python. `_DeltaBuffer` now tracks `self._turn_text` (raw cumulative text
   for the currently-open turn) and normalizes every incoming chunk against
   it before buffering; `_turn_text` resets on turn close (`None`) and on
   the R3 retry-marker split, so cross-turn text never gets diffed against
   an unrelated prior turn's accumulated text. All 7 pre-existing
   `_DeltaBuffer` tests pass unmodified; 3 new regression tests added
   (`test_delta_buffer_diffs_cumulative_chunk_to_new_suffix`,
   `test_delta_buffer_drops_exact_repeat_chunk`,
   `test_delta_buffer_resets_cumulative_tracking_across_turns`) in
   `services/agent-runtime/tests/test_agents.py`. Full suite:
   `pytest tests/test_agents.py -q` — 27 passed.

   Both fixes now stand: freellmapi normalizes at the provider-adapter
   boundary (correct place to fix *that* provider's non-conformance), and
   ATLAS normalizes again at its own consumption boundary (correct place
   to defend against *any* upstream, including future ones, misbehaving
   the same way). Neither is redundant — they're two different trust
   boundaries.
2. **freellmapi's other providers were not audited in this session** —
   `openai-compat`, `cohere`, `cloudflare`, `aihorde` all have their own
   streaming generators; this session confirmed (via `google.test.ts`'s
   existing coverage) they were already assumed incremental and untouched.
   If duplication is ever observed on a non-Gemini route, re-run this same
   diff-based audit against that provider's file.
3. **This is a sibling repo (`freellmapi`), not vendored into
   L2-ATLAS-PROJECT** — the fix was committed to the source repo directly.
   Confirm freellmapi's deployed/running instance picks up this change
   (restart the server process) before expecting the fix to take effect in
   a live ATLAS session.

## MiMo-Code comparison (what the operator asked to investigate)

MiMo-Code's own TUI client-side delta handling (`sync.tsx`) is unmodified
from donor and offers no special dedup — and doesn't need to, because
MiMo-Code's own first-party server is the sole source of truth for its own
chunking and never faces a third-party multi-provider proxy translating a
provider that violates the incremental-delta contract. ATLAS's
architecture — a first-party TUI/web client, consuming ATLAS's own gateway
audit stream, ultimately sourced from a *third-party normalization proxy*
(freellmapi) fronting multiple heterogeneous provider APIs — has an extra
trust boundary MiMo-Code's design doesn't have. The lesson generalized: any
adapter that translates a foreign streaming API into an OpenAI-compatible
incremental-delta contract is the correct and only place to enforce that
contract; every downstream layer should (and, per the byte-identical
`sync.tsx` comparison, correctly does) trust it unconditionally rather than
re-implementing defensive diffing at every consumption point.
