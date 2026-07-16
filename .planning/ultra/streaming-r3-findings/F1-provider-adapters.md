# F1 — Provider Adapter Cumulative-Delta Audit

Repo: `C:\Users\Davi\Desktop\Projects\freellmapi`
Scope: `server/src/providers/*.ts` — does any adapter's `streamChatCompletion()` (or the
shared SSE reader it delegates to) emit `delta.content` values that are cumulative
(full-text-so-far) or overlapping with previously-emitted text, rather than strictly
incremental?

Files in `server/src/providers/`:
- `base.ts` — abstract base class + shared `readSseStream()` helper
- `google.ts` — Gemini (native format, translated)
- `openai-compat.ts` — generic adapter for ~20 registered platforms that speak
  true OpenAI-wire SSE (Groq, Cerebras, NVIDIA NIM, Mistral, OpenRouter, GitHub
  Models, Zhipu, HuggingFace Router, Ollama Cloud, Kilo, Pollinations, LLM7,
  OpenCode Zen, OVH, Agnes, Reka, SiliconFlow, Routeway, BazaarLink, AINative,
  `custom`) — see `server/src/providers/index.ts:15-289`
- `cohere.ts` — Cohere via its OpenAI-compatibility endpoint
- `cloudflare.ts` — Cloudflare Workers AI via its OpenAI-compatible endpoint
- `aihorde.ts` — AI Horde (no real upstream streaming)

## Per-adapter findings

### 1. `base.ts:120-172` — `BaseProvider.readSseStream()` (shared by openai-compat, cohere, cloudflare)

```ts
// server/src/providers/base.ts:151-163
for (const line of lines) {
  const trimmed = line.trim();
  if (!trimmed || !trimmed.startsWith('data: ')) continue;
  const data = trimmed.slice(6);
  if (data === '[DONE]') return;
  try {
    const chunk = JSON.parse(data) as ChatCompletionChunk;
    if (chunk.choices?.some(c => c.finish_reason != null)) sawFinishReason = true;
    yield chunk;
  } catch {
    // Skip malformed chunks
  }
}
```

This is a **pure passthrough**: it parses each upstream SSE `data:` line as an
already-OpenAI-shaped `ChatCompletionChunk` and yields it verbatim. There is no
tracking of previously-seen text and no diffing logic anywhere in this method —
by design, because it assumes the upstream is already emitting correct,
incremental OpenAI-format `delta.content`.

**Verdict: incremental-safe by construction, IF and only if upstream is honest.**
This method performs zero validation that `delta.content` is actually
incremental/non-overlapping. It is a structural risk multiplier: any one of the
~20 platforms wired through `openai-compat.ts` (many of which are third-party
*aggregators-of-aggregators* — e.g. OpenRouter, Kilo Gateway, HuggingFace Router,
BazaarLink, Routeway, AINative — that may themselves proxy non-OpenAI-native
backends such as Gemini/Vertex through their own translation layer) could emit
cumulative or overlapping text in `delta.content` and this code would forward it
unmodified straight to the ATLAS client. This is not a bug in freellmapi's own
code, but it is a real, undefended risk surface. See "Overall assessment" below.

### 2. `openai-compat.ts:205-257` — `OpenAICompatProvider.streamChatCompletion()`

Builds the upstream request with `stream: true` and, on success, does:

```ts
// server/src/providers/openai-compat.ts:256
yield* this.readSseStream(res);
```

No local translation of content at all — same passthrough characteristics as
`base.ts` above. Covers Groq, Cerebras, NVIDIA NIM, Mistral, OpenRouter, GitHub
Models, Zhipu, HuggingFace Router, Ollama Cloud, Kilo, Pollinations, LLM7,
OpenCode Zen, OVH, Agnes, Reka, SiliconFlow, Routeway, BazaarLink, AINative, and
`custom` (see `server/src/providers/index.ts`).

**Verdict: incremental-safe by construction (no local cumulative-emission bug);
risk is entirely inherited from whichever upstream aggregator is selected for a
given request.**

### 3. `cohere.ts:80-122` — `CohereProvider.streamChatCompletion()`

```ts
// server/src/providers/cohere.ts:121
yield* this.readSseStream(res);
```

Identical passthrough pattern, hitting Cohere's own OpenAI-compatibility endpoint
(`https://api.cohere.ai/compatibility/v1`). No translation/diff logic.

**Verdict: incremental-safe by construction; same inherited-trust caveat, but
Cohere's own compat endpoint is a first-party OpenAI shim (lower risk than a
third-party aggregator-of-aggregators).**

### 4. `cloudflare.ts:80-124` — `CloudflareProvider.streamChatCompletion()`

```ts
// server/src/providers/cloudflare.ts:123
yield* this.readSseStream(res);
```

Same passthrough pattern, hitting Cloudflare Workers AI's own OpenAI-compatible
endpoint. No translation/diff logic.

**Verdict: incremental-safe by construction; same inherited-trust caveat as
Cohere (first-party compat shim).**

### 5. `google.ts:486-640` — `GoogleProvider.streamChatCompletion()` (Gemini)

This is the adapter that has to translate a genuinely different wire format
(Gemini's native `streamGenerateContent?alt=sse`, which returns
`candidates[0].content.parts[].text`) into OpenAI's `delta.content` shape — i.e.
exactly the pattern the task description flagged as the classic risk (Google
Gemini streaming is often assumed to be cumulative).

```ts
// server/src/providers/google.ts:392-398
function extractText(parts: GeminiPart[] | undefined): string | null {
  if (!parts) return null;
  const text = parts
    .map(p => p.text ?? '')
    .join('');
  return text.length > 0 ? text : null;
}
```

```ts
// server/src/providers/google.ts:580-607 (inside streamChatCompletion's read loop)
const candidate = chunk.candidates?.[0];
const parts = candidate?.content?.parts ?? [];
const text = extractText(parts);
...
if ((text && text.length > 0) || toolCalls.length > 0) {
  ...
  yield {
    ...
    choices: [{
      index: 0,
      delta: {
        ...(text ? { content: text } : {}),
        ...
      },
      finish_reason: null,
    }],
  };
}
```

`extractText()` joins the `parts[].text` of the **current SSE chunk only** — it
has no reference to, and does not concatenate with, any previously-seen text.
There is no accumulator variable (`fullText`, `previousLength`, `.slice(...)`,
etc.) anywhere in this method. It simply re-emits whatever `parts[].text` the
current chunk carried as `delta.content`, once, per chunk.

This is **only correct** if Gemini's `streamGenerateContent` SSE chunks are
themselves already incremental (each event's `parts[].text` is the *new* text
since the last event, not the full text-so-far). Gemini's real API does behave
this way (each streamed `GenerateContentResponse` carries an incremental slice,
not the accumulated candidate), and the adapter's own test suite encodes exactly
that assumption and passes against it:

```ts
// server/src/__tests__/providers/google.test.ts:370-384
it('streams text deltas and emits a final stop chunk', async () => {
  const sseLines = [
    'data: {"candidates":[{"content":{"parts":[{"text":"Hel"}]}}]}\n\n',
    'data: {"candidates":[{"content":{"parts":[{"text":"lo"}]}}]}\n\n',
    'data: {"candidates":[{"content":{"parts":[]},"finishReason":"STOP"}]}\n\n',
  ];
  ...
  const text = chunks.map(c => c.choices[0].delta.content ?? '').join('');
  expect(text).toBe('Hello');   // "Hel" + "lo", not "Hel" + "Hello"
});
```

If Gemini ever sent a cumulative chunk (e.g. `"Hel"` then `"Hello"`), this test
would fail (`"HelHello"` ≠ `"Hello"`), and — critically — the production code
has no defense against that case either: `extractText()` would happily forward
the cumulative `"Hello"` chunk as a second `delta.content`, producing exactly the
"Hel" + "Hello" duplication pattern matching the reported bug symptom.

**Verdict: NOT cumulative today under the tested/assumed Gemini contract, but
FRAGILE — there is zero diffing/guard logic. If Gemini's live API ever emits a
non-incremental (cumulative or overlapping) chunk for any candidate — a known
occurrence for some Gemini model/tool-call combinations and thinking-token
interleavings in the wild — this code has no mechanism to detect or correct it
and would leak the duplication straight through to the client.** This is the
adapter most structurally exposed to the bug pattern described in the task, even
though no direct evidence in this codebase proves it is *currently* misbehaving
against real Gemini traffic (only synthetic/mocked SSE was inspected here).

### 6. `aihorde.ts:168-189` — `AIHordeProvider.streamChatCompletion()`

```ts
// server/src/providers/aihorde.ts:174-188
async *streamChatCompletion(...): AsyncGenerator<ChatCompletionChunk> {
  const data = await this.chatCompletion(apiKey, messages, modelId, options, quotaContext);
  const choice = data.choices?.[0];
  const content = typeof choice?.message?.content === 'string' ? choice.message.content : '';
  const base = { ... };
  yield { ...base, choices: [{ index: 0, delta: { role: 'assistant' }, finish_reason: null }] };
  if (content) {
    yield { ...base, choices: [{ index: 0, delta: { content }, finish_reason: null }] };
  }
  yield { ...base, choices: [{ index: 0, delta: {}, finish_reason: choice?.finish_reason ?? 'stop' }] };
}
```

Not real streaming at all — makes one blocking `chatCompletion()` call and
synthesizes exactly 3 SSE frames: role, one single content delta carrying the
**entire** response text, then a finish frame. The full content is emitted
exactly **once**.

**Verdict: incremental-safe (trivially — no possibility of duplication since
there is only one content-bearing chunk).**

## Overall assessment

No provider adapter in `server/src/providers/` contains code that actively
*computes* a cumulative-and-forwards-as-delta bug (i.e., none of them accumulate
text into a running buffer and then emit the running buffer as `delta.content`).
So there is no "confirmed buggy" adapter with a smoking-gun cumulative-emission
line.

However, two structural risk points stand out, ranked by likelihood of being the
actual root cause of the reported ATLAS duplication:

1. **`google.ts:392-398,580-607` (extractText / streamChatCompletion) — suspected,
   not confirmed.** The adapter performs a naive per-chunk join of `parts[].text`
   with no cumulative-vs-incremental guard and no `.slice(previousLength)` diff
   logic anywhere in the file. It is correct only as long as Gemini's live SSE
   stream never regresses to sending a cumulative or overlapping `parts[].text`
   for a later chunk in the same turn. Given the reported bug reproduces as two
   overlapping copies of the same paragraph (a classic cumulative-chunk symptom)
   and Gemini is the one adapter here translating a genuinely non-OpenAI-native
   streaming format, this is the highest-suspicion adapter if the affected
   ATLAS session was routed to `platform: 'google'`.

2. **`base.ts:120-172` `readSseStream()`, used verbatim by `openai-compat.ts`,
   `cohere.ts`, and `cloudflare.ts` — undefended passthrough, not a
   freellmapi-authored bug.** These three adapters (and the ~20 platforms wired
   through `OpenAICompatProvider`, notably third-party aggregators like
   OpenRouter, Kilo Gateway, HuggingFace Router, BazaarLink, Routeway, AINative)
   perform zero content-diffing because they assume the upstream already speaks
   correct incremental OpenAI SSE. If any of those upstream shims is itself
   wrapping a non-OpenAI-native backend and translates it incorrectly
   (cumulative-into-delta), freellmapi would forward that duplication unmodified.
   This can't be pinned to one file/line as "the bug" — it's an inherited-trust
   gap across the whole `openai-compat.ts` fleet — but it is real and
   undefended.

**No adapter should be described as "confirmed buggy" from static reading alone.**
To confirm which of the two above is the actual root cause, the next step (out of
scope for this task) would be to capture the raw upstream SSE bytes for the
specific failing ATLAS turn and check whether `platform` in `_routed_via` was
`google` (case 1) or one of the `openai-compat` platforms (case 2), then diff
consecutive raw `parts[].text` / `delta.content` values from the actual upstream
response.
