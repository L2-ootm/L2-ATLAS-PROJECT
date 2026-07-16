# F3 — Foundation `stream_delta_callback` invocation trace

Scope: `foundation/atlas-hermes/agent/chat_completion_helpers.py`,
`foundation/atlas-hermes/agent/conversation_loop.py`,
`foundation/atlas-hermes/run_agent.py`. Read-only investigation, no foundation
edits (D-001).

Consumer context: `services/agent-runtime/atlas_runtime/agents/native.py`
registers `stream_delta_callback=delta_buffer.push` where `_DeltaBuffer.push`
(native.py:77-96) does pure `self._buffer.append(chunk)` /
`"".join(self._buffer)` — **zero dedup**, flush-on-size/interval, and a hard
flush on `chunk is None` (end-of-turn). Anything pushed through the callback
twice for the same turn renders twice, verbatim, in the final text.

## Call-site inventory (actual invocations, not registrations)

### run_agent.py — the shared dispatch primitives

All `chat_completion_helpers.py` streaming code funnels through these two
`AIAgent` methods; they are the only places that actually touch
`self.stream_delta_callback` as a callable in run_agent.py.

1. **`run_agent.py:3300`** — `cb(think_tail)` inside
   `_reset_stream_delivery_tracking()` (run_agent.py:3279-3318). Flushes text
   the think-scrubber was holding back (an unresolved partial `<tag` at the
   tail of the previous chunk) through `[stream_delta_callback,
   _stream_callback]`. This text was **never previously delivered** — the
   scrubber withheld it — so this is a first delivery, not a duplicate.
2. **`run_agent.py:3314`** — `cb(tail)`, same function, same reasoning, for
   the context-scrubber's held-back tail.
3. **`run_agent.py:3405`** — `cb(text)` inside `_fire_stream_delta()`
   (run_agent.py:3359-3410). This is the single real dispatch point for all
   "normal" incremental text — every `_fire_stream_delta(...)` call in
   chat_completion_helpers.py bottoms out here. Loops over
   `[self.stream_delta_callback, self._stream_callback]` and calls each with
   the (scrubbed) `text` argument. Argument is always an incremental chunk,
   never a cumulative/full response — callers pass raw `delta.content` /
   `text` straight from the provider's SSE chunk.

`_reset_stream_delivery_tracking()` is called from two places:
`conversation_loop.py:1186` (top of the **outer** per-attempt retry loop, run
once per `while retry_count < max_retries` iteration) and
`chat_completion_helpers.py:2163` (inside the **inner** mid-tool-call silent
retry — see finding below). Both reset `agent._current_streamed_assistant_text
= ""`, an *agent-internal* bookkeeping var used only for
`_interim_content_was_streamed()` dedup checks against `interim_assistant_callback`.
**It does not, and cannot, tell ATLAS's `_DeltaBuffer` to discard anything
already pushed through `stream_delta_callback`.**

### chat_completion_helpers.py — provider streaming loops

4. **`chat_completion_helpers.py:1597`** (`_bedrock_call`/`_on_text`) —
   `agent._fire_stream_delta(text)`. Bedrock Converse text delta. Incremental.
5. **`chat_completion_helpers.py:1817`** (`_call_chat_completions`, main
   per-chunk loop) — `agent._fire_stream_delta(delta.content)`, fired only
   when `not tool_calls_acc` (pure-text portion of the turn, before any tool
   call has started accumulating). Incremental — one OpenAI SSE chunk's
   `delta.content`.
6. **`chat_completion_helpers.py:1830-1832`** (same loop, `elif` branch) —
   ```python
   elif agent.stream_delta_callback:
       try:
           agent.stream_delta_callback(delta.content)
           agent._record_streamed_assistant_text(delta.content)
   ```
   Fires when `tool_calls_acc` is already non-empty (content chunk arrives
   after a tool call has started forming — mixed content+tool-call turn).
   **Calls `agent.stream_delta_callback` directly, bypassing
   `_fire_stream_delta`** — so this path skips the think-scrubber and
   context-scrubber state machines that every other delta goes through. Still
   incremental (raw `delta.content` from the current chunk), and mutually
   exclusive with site 5 for any given chunk (`if`/`elif` on the same `delta`),
   so it does not itself double-fire a chunk. Flagged as a secondary
   correctness concern (scrubber bypass — reasoning tags spanning this
   boundary won't be caught) but not the duplication bug.
7. **`chat_completion_helpers.py:2042`** (`_call_anthropic`,
   `content_block_delta`/`text_delta`) — `agent._fire_stream_delta(text)`.
   Incremental, gated on `not has_tool_use`.
8. **`chat_completion_helpers.py:2152-2155`** (inner retry handler inside
   `_call()`) — `agent._fire_stream_delta("\n\n⚠ Connection dropped mid
   tool-call; reconnecting…\n\n")`. New literal text (the seam marker), not a
   re-push of prior content by itself — but see verdict below for what
   happens immediately after.
9. **`chat_completion_helpers.py:2420`** — `agent._fire_stream_delta(_warn)`,
   the "⚠ Stream stalled mid tool-call (...); the action was not executed."
   message appended once to `_partial_text` when a stream dies with a
   dropped tool call and the outer wrapper builds a length-truncated stub.
   New text, fired once.

### conversation_loop.py

10. **`conversation_loop.py:3811-3813`** —
    ```python
    if agent.stream_delta_callback:
        try:
            agent.stream_delta_callback(None)
    ```
    End-of-turn signal fired **before tool execution begins**, once the
    assistant message (possibly with streamed preamble content) has been
    finalized. This is the only place in the traced files that sends `None`
    for a "normal" (non-final, tool-call) turn — confirmed by
    `native.py`'s own comment: "the foundation only signals
    `stream_delta_callback(None)` at tool boundaries (never after a final,
    no-tool-call response)". Native.py compensates by pushing its own
    trailing `None` after `run_conversation()` returns.
11. **`conversation_loop.py:3834-3837`** (tool-guardrail halt path) —
    ```python
    if final_response:
        agent._safe_print(f"\n{final_response}\n")
        if agent.stream_delta_callback:
            try:
                agent.stream_delta_callback(final_response)
                agent.stream_delta_callback(None)
    ```
    `final_response` here is `agent._toolguard_controlled_halt_response(decision)`
    — a **newly synthesized** halt/explanation message, not a re-derivation
    of text that was streamed earlier in the turn. The stream display was
    already flushed via `stream_delta_callback(None)` at site 10 immediately
    before tool execution started, so by the time this fires the buffer's
    prior turn content is a separate, already-closed segment (in ATLAS's
    `_DeltaBuffer` terms: a prior `None` closed `_turn_open`, this call
    reopens it, appends the halt text, then closes it again). Not a
    duplicate of previously-buffered text; a legitimately new closing turn
    for the halt explanation.

No other call site in these three files invokes
`stream_delta_callback`/`_fire_stream_delta` with a full/cumulative
`final_response`-shaped variable. In particular:
`conversation_loop.py`'s many `final_response = ...` assignments (partial
stream recovery at line 3934-3944, prior-turn-content fallback at
3958-3971, empty-response terminal at 4178, truncated-parts join at
4216-4217, `_handle_max_iterations` at 4321, footer append at 4443, hook
override at 4465) are **never** pushed back through
`stream_delta_callback`/`_fire_stream_delta`. They only populate the
`final_response` key of the dict `run_conversation()` returns
(conversation_loop.py:4568) to the caller (native.py), which reads it purely
for the `RunOutcome`/audit summary (`native.py:461`) — not for display. So the
"stream deltas, then also push the assembled full text once more as a
completeness check" pattern hypothesized in the task does **not** exist as a
literal safety-net call anywhere in these three files.

## Verdict: yes, one call path can double-emit text for a single turn

**Site: `chat_completion_helpers.py:2084-2186`, the mid-tool-call silent
stream retry inside `interruptible_streaming_api_call()`'s `_call()`.**

Sequence for a single assistant turn where the model streams some preamble
text, then starts a tool call, then the connection drops transiently
(timeout / connection reset / SSE parse error — the code explicitly checks
for these):

1. Attempt N: `_call_chat_completions()` (or `_call_anthropic()`) streams
   preamble tokens via site 5/7 (`agent._fire_stream_delta(delta.content)`)
   — these reach `stream_delta_callback` → ATLAS's `_DeltaBuffer.push()` →
   appended to `self._buffer`, `_turn_open = True`.
2. A tool call starts forming (`tool_calls_acc` non-empty,
   `partial_tool_names` populated), then the stream dies with a transient
   error mid-flight.
3. The exception handler at line 2096-2131 detects
   `deltas_were_sent["yes"] and _partial_tool_in_flight and _is_transient
   and _stream_attempt < _max_stream_retries` → `_can_silent_retry = True`.
4. Line 2152-2155: fires `agent._fire_stream_delta("\n\n⚠ Connection dropped
   mid tool-call; reconnecting…\n\n")` — reaches the same callback, same
   open turn (no `None` in between).
5. Line 2163: `agent._reset_stream_delivery_tracking()` — resets only the
   agent-internal `_current_streamed_assistant_text` bookkeeping.
   **`stream_delta_callback` itself is never told to discard or reset
   anything** — there is no "clear" primitive in the callback contract, only
   `text` and `None` (end-of-turn).
6. Line 2169-2171 zero the local accumulators (`partial_tool_names`,
   `deltas_were_sent`, `first_delta_fired`) and `continue` — the `for
   _stream_attempt in range(_max_stream_retries + 1)` loop re-enters
   `_call_chat_completions()`/`_call_anthropic()` **from scratch**, with the
   same `api_kwargs` (same prompt/messages — the model has no memory of the
   dropped attempt). `content_parts` is freshly re-initialized
   (`chat_completion_helpers.py:1754`).
7. The model regenerates its answer from the top. Its new preamble — likely
   semantically similar to attempt N's, often near-identical phrasing with
   minor token-level differences (temperature/sampling variance) — streams
   again through site 5/7 (`agent._fire_stream_delta`), reaching the *same
   still-open* `_DeltaBuffer` turn and getting appended **after** the
   attempt-N preamble and the "⚠ Connection dropped..." marker.
8. No `None` fires between steps 1 and 7 — the ATLAS buffer's `_turn_open`
   stays `True` throughout, so `"".join(self._buffer)` at the eventual flush
   contains: `[attempt-N preamble] + "\n\n⚠ Connection dropped mid
   tool-call; reconnecting…\n\n" + [attempt-N+1 preamble (re-generated,
   textually similar)] + ...` — concatenated with zero deduplication.

This is a code-acknowledged, intentional tradeoff, not an oversight — the
comment directly above (chat_completion_helpers.py:2084-2095) states: *"If
the stream died AFTER some tokens were delivered: normally we don't retry
(the user already saw text, retrying would duplicate it). BUT: if a tool call
was in-flight when the stream died, silently aborting discards the tool call
entirely. In that case we prefer to retry — the user sees a brief
'reconnecting' marker + duplicated preamble text, which is strictly better
than a failed action with a 'retry manually' message."*

This matches the observed symptom closely: two near-identical "attempts" at
the same answer concatenated back-to-back with a small textual offset (the
regenerated attempt rarely reproduces the dropped attempt's phrasing
character-for-character). The one mismatch with the reported symptom is that
this path also injects a visible `⚠ Connection dropped mid tool-call;
reconnecting…` marker between the two copies — if the observed bug reports
showed no such marker, either (a) it was present but not mentioned/rendered
distinctly by the UI, or (b) a second, still-undiscovered duplication path
exists outside these three files (e.g., in the ATLAS-side rendering/dedup
layer already covered by prior ULTRAREVIEW sessions in this repo, or in a
provider (freellmapi) that itself replays SSE data after a proxy-side
reconnect — outside foundation code and outside this investigation's scope).

**Guardrail confirmed absent elsewhere:** the *outer* per-attempt retry loop
(`conversation_loop.py:1136` `while retry_count < max_retries`, resetting via
`_reset_stream_delivery_tracking()` at line 1186) is **not** a duplication
risk by itself: `interruptible_streaming_api_call()` never raises an
exception back to that outer loop when `deltas_were_sent["yes"]` is True — in
that case it always returns a length-truncated stub
(`chat_completion_helpers.py:2394-2451`, `PARTIAL_STREAM_STUB_ID`) built from
already-delivered text, and conversation_loop's truncation/continuation
machinery (`truncated_response_parts`, lines 4216-4219) *continues* the
response rather than re-streaming it from scratch. The exception only
propagates to the outer loop (`raise result["error"]` at line 2452) when
`deltas_were_sent["yes"]` is False — i.e., nothing had been streamed yet, so
an outer-loop retry there is safe. The **only** path that re-invokes a fresh
provider stream after text has already reached the callback, without an
intervening `None`, is the inner mid-tool-call silent retry documented above.

## Summary table

| # | File:Line | Fires with | Incremental or cumulative | Duplicate risk |
|---|---|---|---|---|
| 1 | run_agent.py:3300 | held-back scrubber tail | incremental (first delivery) | no |
| 2 | run_agent.py:3314 | held-back scrubber tail | incremental (first delivery) | no |
| 3 | run_agent.py:3405 | `_fire_stream_delta` dispatch | incremental | no (dispatch point, not source) |
| 4 | chat_completion_helpers.py:1597 | Bedrock text delta | incremental | no |
| 5 | chat_completion_helpers.py:1817 | chat_completions text delta | incremental | **yes, when re-entered by retry (see #8)** |
| 6 | chat_completion_helpers.py:1830-1832 | content after tool-call started | incremental (scrubber-bypass) | no (secondary scrubber-bypass concern only) |
| 7 | chat_completion_helpers.py:2042 | Anthropic text_delta | incremental | **yes, when re-entered by retry (see #8)** |
| 8 | chat_completion_helpers.py:2152-2155 | "⚠ Connection dropped..." marker | new literal text | triggers the re-entry into #5/#7 without a `None` in between — **root cause of the duplication path** |
| 9 | chat_completion_helpers.py:2420 | "⚠ Stream stalled..." marker | new literal text | no (fired once) |
| 10 | conversation_loop.py:3811-3813 | `None` | end-of-turn signal | n/a |
| 11 | conversation_loop.py:3834-3837 | guardrail halt message + `None` | new synthesized text, not a re-push | no |

## Files inspected
- `foundation\atlas-hermes\agent\chat_completion_helpers.py`
- `foundation\atlas-hermes\agent\conversation_loop.py`
- `foundation\atlas-hermes\run_agent.py`
- `services\agent-runtime\atlas_runtime\agents\native.py` (consumer context only)
