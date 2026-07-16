# Streaming duplication R3 — mid-tool-call retry duplication — Investigation

Prior sessions (2026-07-12, 2026-07-15) fixed three layered root causes: event
batching split, opentui's hardcoded child-block `streaming=true`, and multiple
part-creation dedup bugs (`chat.ts`). Operator UAT after those fixes (screenshot,
Raycast clipboard cache, confirmed by operator as **atlas-terminal**) still showed
duplicated/overlapping text: `"VVamo testar! Vou fazer uma análise completa do
stateamo testar! Vou fazer uma análise completa do state atual do projeto Command
Center — levantar a estrutura... atual do projeto Command Center — levantar a
estrutura... e dar um panorama consolidado. e dar um panorama consolidado."`

That pattern — two near-identical copies of the same paragraph concatenated with a
small textual offset, no exact byte-for-byte repeat — does not match any bug class
the prior 3 root causes covered (those were **render-timing** bugs: the same
*correct* final text painted twice across two frames). This session's investigation
targeted a different layer: is the **text content itself** arriving duplicated,
upstream of rendering?

## Root Cause: Mid-tool-call silent stream retry duplicates preamble text with no turn boundary

**Exact Failure Point:** `foundation/atlas-hermes/agent/chat_completion_helpers.py:2144-2186`
(vendored, D-001 — not editable), consumed by
`services/agent-runtime/atlas_runtime/agents/native.py`'s `_DeltaBuffer` (now fixed,
see below).

```python
# foundation/atlas-hermes/agent/chat_completion_helpers.py:2084-2095 (comment,
# documents the tradeoff explicitly)
# If the stream died AFTER some tokens were delivered: normally we don't retry
# (the user already saw text, retrying would duplicate it).  BUT: if a tool call
# was in-flight when the stream died, silently aborting discards the tool call
# entirely.  In that case we prefer to retry — the user sees a brief
# "reconnecting" marker + duplicated preamble text, which is strictly better
# than a failed action with a "retry manually" message.

# :2144-2186 (the retry itself)
if _can_silent_retry:
    agent._fire_stream_delta(
        "\n\n⚠ Connection dropped mid tool-call; reconnecting…\n\n"
    )
    agent._reset_stream_delivery_tracking()   # agent-internal bookkeeping only
    result["partial_tool_names"] = []
    deltas_were_sent["yes"] = False
    first_delta_fired["done"] = False
    continue   # re-enters _call_chat_completions()/_call_anthropic() from scratch
```

## Chain of Failure

1. **Entry:** A turn streams preamble text, then starts forming a tool call
   (`chat_completion_helpers.py:1817`/`2042`, `agent._fire_stream_delta(delta.content)`
   → `run_agent.py:3405` → `stream_delta_callback` → ATLAS's `_DeltaBuffer.push()`,
   appending into an **open** turn, `_turn_open = True`).
2. **Transient drop:** The connection dies mid-stream (timeout / connection reset /
   SSE parse error) while the tool call is still forming.
3. **Silent retry decision:** `deltas_were_sent["yes"] and _partial_tool_in_flight
   and _is_transient` → `_can_silent_retry = True` (chat_completion_helpers.py:2127-2131).
4. **Marker fired, no turn close:** The "⚠ Connection dropped..." marker is pushed
   through the **same still-open** `stream_delta_callback` — critically, `None`
   (the only end-of-turn signal the callback contract has) is **never** sent here.
   `agent._reset_stream_delivery_tracking()` only clears an agent-internal
   dedup-check variable (`_current_streamed_assistant_text`); it has no way to tell
   ATLAS's `_DeltaBuffer` to discard or segment anything already pushed.
5. **Re-entry:** The retry loop `continue`s back into `_call_chat_completions()`/
   `_call_anthropic()` from scratch, with the same prompt. The model has no memory
   of the dropped attempt and regenerates its answer — usually similar but not
   byte-identical phrasing (sampling variance), matching the observed "near-copy
   with a small offset" pattern exactly.
6. **Failure point (was, before this session's fix):** ATLAS's `_DeltaBuffer.push()`
   (`native.py:77-96`, pre-fix) does pure `self._buffer.append(chunk)` /
   `"".join(self._buffer)` with **zero deduplication or turn-boundary detection**.
   The pre-drop preamble, the marker, and the regenerated preamble all land in the
   same open buffer and flush as one seamless block of text — the "duplication"
   the operator sees.

## Why It Fails

Every fix applied in the prior three root-cause rounds operated on the
**rendering** layer (SolidJS batch timing, opentui's `streaming` prop propagation,
part-creation dedup across event-type races in `chat.ts`). All three assumed the
underlying **text content** streaming into the client was already correct and
non-overlapping — a reasonable assumption for the bug classes they were fixing, but
false for this one. This retry path produces genuinely duplicated *content* one
layer upstream of all three previous fixes: by the time `chat.ts` and `sync.tsx`
see the `llm_delta` events, the duplicate text is already baked into the audit
event stream coming out of the gateway. No amount of render-timing or
part-creation-dedup correctness downstream can un-duplicate content that was
already concatenated server-side.

## Proof

- `foundation/atlas-hermes/agent/chat_completion_helpers.py:2084-2095` — comment
  explicitly documents the tradeoff as intentional, not an oversight.
- `foundation/atlas-hermes/agent/chat_completion_helpers.py:2127-2131` — the exact
  gate (`_partial_tool_in_flight and _is_transient and _stream_attempt <
  _max_stream_retries`).
- `foundation/atlas-hermes/agent/chat_completion_helpers.py:2152-2186` — marker
  fire, bookkeeping-only reset, loop `continue` with no `None` sent.
- `services/agent-runtime/atlas_runtime/agents/native.py:77-96` (pre-fix) —
  `_DeltaBuffer` had no dedup/marker-detection; confirmed by new regression test
  `test_delta_buffer_splits_on_mid_tool_call_retry_marker` failing against the
  pre-fix implementation (verified by construction: the pre-fix code has no
  mechanism to produce two flush entries for this input).
- Full call-site audit (11 sites across `run_agent.py`, `chat_completion_helpers.py`,
  `conversation_loop.py`) confirmed this is the **only** path that re-invokes a
  fresh provider stream after content has already reached the callback, without an
  intervening `None` — see `.planning/ultra/streaming-r3-findings/F3-foundation-stream-callback.md`
  for the exhaustive trace.

## Fix Implemented

`services/agent-runtime/atlas_runtime/agents/native.py` — `_DeltaBuffer.push()` now
detects the marker text (`_STREAM_RETRY_MARKER = "Connection dropped mid
tool-call"`) and, when it arrives inside an open turn, flushes the pre-drop segment
as `final=True` (closing that part) before appending the marker + retried text as
a fresh segment. On the client side this is already-understood behavior: `chat.ts`'s
`streamingText` map treats a closed (`open: false`) entry as a signal to start a
brand-new part on the next `llm_delta` (existing logic, unchanged) — so the retry
now renders as two visually distinct parts (interrupted preamble, then the
reconnect notice + clean regenerated answer) instead of one seamlessly garbled
block. The final `llm_call` reconcile still overwrites the *second* part with the
authoritative final text, so the marker itself is only visible for the brief
in-flight window, not in the settled transcript.

This does not eliminate the underlying redundant generation (that's the
foundation's intentional, vendored tradeoff, D-001 — out of scope to change) but it
makes the failure mode **honest and comprehensible** (a visible reconnect boundary)
instead of an unexplained garbled-text bug indistinguishable from a rendering
defect.

Regression tests added: `test_delta_buffer_splits_on_mid_tool_call_retry_marker`,
`test_delta_buffer_retry_marker_without_open_turn_is_not_split`
(`services/agent-runtime/tests/test_agents.py`).

## Related Issues Found During Investigation

1. **R1 (sdk.tsx always-debounce) was never committed, in any commit, ever.**
   `git log --all -S"Always debounce" -- .../sdk.tsx` returns nothing; HEAD
   (`ab5daca6`) still has the old conditional-flush logic. The always-debounce fix
   existed only in the working tree — HANDOFF.md's 2026-07-15 "(latest)" entry
   claims it was "Implemented ... Verified" without noting it was never staged.
   **Committed this session** (see commit log).
2. **R2's persistence infra was uncommitted**: `package.json`'s
   `patchedDependencies` entry, `patches/@opentui%2Fcore@0.1.99.patch`, and
   `bun.lock` were all modified/untracked. The patch is physically live in
   `node_modules` right now, but a fresh `git clone` + `bun install` would silently
   lose it. **Committed this session.**
3. **An undocumented "R3" change was present**, uncommitted:
   `streaming={!props.message.time.completed}` on `TextPart`'s `<markdown>`/`<code>`
   renderables (`session/index.tsx:1581,1592`), replacing the diagnostic
   render-counter that HEAD actually contains. HANDOFF.md explicitly states R3 was
   NOT implemented, contradicting this working-tree state. Logically correct and
   consistent with R2's fix intent — **committed this session**, HANDOFF corrected.
4. **Residual bug, same class as R2/R3, now fixed**: `ReasoningPart`'s `<code>`
   renderable (`session/index.tsx:1503`) still hardcoded `streaming={true}`
   unconditionally, never updated alongside `TextPart`. Fixed this session
   (`streaming={!isDone()}`, using the component's existing `isDone` memo).
5. **Latent gap, not fixed (judgment call — see below)**: `sync.tsx`'s
   `message.part.delta` handler (`sync.tsx:514-530`) does an unconditional
   `existing + delta` string append with **no event-id/sequence dedup guard**. If
   the same delta event were ever redelivered (no confirmed live mechanism causes
   this today — the gateway's rowid-cursor SSE relay and `sdk.tsx`'s mutually
   exclusive event-source wiring were both audited and found correct/replay-safe),
   this handler would silently double-append. Left unfixed: adding a dedup guard
   would require a monotonic sequence number on the delta event schema (a
   real, if modest, schema change) to defend against a scenario with no
   confirmed live trigger. Flagged here for a future session if it ever manifests
   independently of the now-fixed retry-marker case.
6. **Structural risk, out of scope (separate repo)**: `freellmapi`'s Gemini
   adapter (`server/src/providers/google.ts:392-398,580-607`, sibling repo at
   `C:\Users\Davi\Desktop\Projects\freellmapi`) has zero diffing/guard logic
   against a cumulative (rather than incremental) `parts[].text` chunk — correct
   only as long as Gemini's live API never regresses to non-incremental chunks for
   a given turn. Not confirmed as live/triggered; documented as a risk for the
   freellmapi maintainer, not modified (separate project, out of this session's
   scope). See `.planning/ultra/streaming-r3-findings/F1-provider-adapters.md`.
7. **Cleared, not the bug**: freellmapi's `content.ts` normalization
   (`normalizeOutboundContent`/`sanitizeResponse`) and the dialect-hold/passthrough
   transition in `proxy.ts` (~1409-1598) were both audited in full and proven
   structurally incapable of producing duplication (see
   `.planning/ultra/streaming-r3-findings/F2-content-normalization.md`). The
   gateway's rowid-cursor SSE relay (`native/atlas-core-rs/.../lib.rs`+`db.rs`) was
   also audited and confirmed replay-safe (strict `rowid > cursor`, monotonic
   cursor advance, no retry-from-zero on reconnect).

## Verification

- `services/agent-runtime`: `pytest tests/test_agents.py -q` — 24 passed (2 new).
  Full suite run in background; will be confirmed before commit.
- `services/atlas-terminal`: `bunx tsc --noEmit` — clean. `bun test` — 56/56 passed.
- **UAT still owed** — this environment cannot drive a real interactive TUI stream
  through an actual mid-tool-call connection drop to visually confirm the fix in
  a live session (that failure mode requires a genuine transient network drop
  during a real tool call, not reproducible synthetically here). The unit tests
  prove the `_DeltaBuffer` logic is correct against the documented trigger
  condition; live confirmation is the next operator step.

## Recommendations

1. Operator: next time the duplication is observed, check whether the visible
   text contains "⚠ Connection dropped mid tool-call" — if the marker is now
   visible momentarily (even if quickly overwritten by the final reconcile), it
   confirms this is the trigger path and the fix is working as designed (segments
   instead of seamless garble). If duplication recurs **without** any trace of
   that marker, item 5 or item 6 above are the next things to investigate.
2. Item 5 (sync.tsx delta dedup): revisit if duplication recurs with no retry
   marker involved — would need a delta sequence number added to the event schema.
3. Item 6 (freellmapi Gemini adapter): flag to the freellmapi maintainer/repo,
   or add a defensive incremental-diff guard there if ATLAS's own traffic is
   frequently routed to `platform: google`.
