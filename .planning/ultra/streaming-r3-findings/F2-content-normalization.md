# F2 — content.ts normalization + proxy.ts dialect-hold duplication audit

Repo: `C:\Users\Davi\Desktop\Projects\freellmapi`
Scope: `server/src/lib/content.ts` (full file, 113 lines) + all call sites of
`normalizeOutboundContent`/`sanitizeResponse` across `server/src` + the dialect
hold/passthrough transition in `server/src/routes/proxy.ts` (~lines 1409-1598).

## Verdict

**No duplication mechanism found in either `content.ts` or the proxy.ts
dialect-hold/passthrough transition.** Both functions are pure field-level
mutators that never concatenate/re-append content, and both are provably
idempotent. The passthrough transition is structurally single-flush by
construction (one-way mode transition + `continue` ordering). This file (F2)
clears its scope; the duplication bug is not here.

---

## 1. `content.ts` — what the two functions actually do

### `sanitizeResponse<T>` (`server/src/lib/content.ts:72-86`)

```ts
export function sanitizeResponse<T>(payload: T): T {
  const p = payload as { model?: unknown; choices?: unknown };
  if (!p || typeof p !== 'object') return payload;
  if (p.model != null && typeof p.model !== 'string') p.model = String(p.model);
  if (Array.isArray(p.choices)) {
    for (const choice of p.choices) {
      if (!choice || typeof choice !== 'object') continue;
      const c = choice as { finish_reason?: unknown; message?: { tool_calls?: unknown }; delta?: { tool_calls?: unknown } };
      if (c.finish_reason === undefined) c.finish_reason = null;
      if (c.message && typeof c.message === 'object' && c.message.tool_calls === null) delete c.message.tool_calls;
      if (c.delta && typeof c.delta === 'object' && c.delta.tool_calls === null) delete c.delta.tool_calls;
    }
  }
  return payload;
}
```

It touches exactly three fields: `model` (coerce to string), `finish_reason`
(default undefined→null), and `tool_calls` (delete if literally `null`). **It
never reads or writes `delta.content` / `message.content` at all.** There is
no code path in this function that can produce, append to, or duplicate
text content — it is textually impossible, `content` is never referenced.

### `normalizeOutboundContent<T>` (`server/src/lib/content.ts:98-112`)

```ts
export function normalizeOutboundContent<T>(payload: T): T {
  const choices = (payload as { choices?: unknown })?.choices;
  if (!Array.isArray(choices)) return payload;
  for (const choice of choices) {
    const delta = (choice as { delta?: { content?: unknown } })?.delta;
    if (delta && Array.isArray(delta.content)) {
      delta.content = contentToString(delta.content);
    }
    const message = (choice as { message?: { content?: unknown } })?.message;
    if (message && Array.isArray(message.content)) {
      message.content = contentToString(message.content);
    }
  }
  return payload;
}
```

This is a **replace-in-place**, not an append: `delta.content = contentToString(delta.content)`
is a straight assignment that overwrites the array with its stringified
form; it does not concatenate the new string onto anything pre-existing.
It also only fires when `Array.isArray(delta.content)` is true — for the
normal case (upstream sends `delta.content` as a plain string, which is the
overwhelming majority of providers/chunks), this function is a no-op that
returns `payload` untouched at line 100 (`if (!Array.isArray(choices)) return payload`)
or, if choices exist but content is already a string, the inner `if` at
line 103/107 simply never executes for that choice. Confirmed against the
existing test `server/src/__tests__/lib/content.test.ts:118`:
`expect(normalizeOutboundContent(chunk).choices[0].delta.content).toBe('already a string')`.

`contentToString` itself (`content.ts:14-34`) is a pure array→string
flattener (`.map(...).join('')`); it does not read `delta.content` from
anywhere else or merge in prior state — it operates only on the array value
passed to it.

**Conclusion for step 2:** neither function has any logic that strips
think-blocks/reasoning tags/markdown and re-appends the transformed version
alongside the original — that class of transform (strip + reassign
duplicating original) does not exist anywhere in `content.ts`. The only
"transform" is array→string coercion via straight assignment.

## 2. Idempotency check (step 3)

**Call sites (exhaustive grep of `server/src`):**

- `server/src/routes/proxy.ts:1501-1502` — streaming path, one call each per chunk:
  ```ts
  normalizeOutboundContent(chunk);
  sanitizeResponse(chunk);
  ```
- `server/src/routes/proxy.ts:1724` — non-stream path, single composed call:
  ```ts
  res.json(sanitizeResponse(normalizeOutboundContent(result)));
  ```
- `server/src/__tests__/lib/content.test.ts` — test-only call sites (not production code).

No other file in `server/src` imports or calls either function. There is
exactly one call of each per chunk on the streaming path and exactly one
composed call on the non-stream path — **no double-call site exists in the
codebase today.**

Idempotency, if it mattered (defense in depth):

- `sanitizeResponse` — re-running is a no-op on the second pass: `model` is
  already a string (guard `typeof p.model !== 'string'` fails), `finish_reason`
  is already `null`/set (guard `=== undefined` fails), and `tool_calls` was
  already deleted so `c.delta.tool_calls === null` is false (property absent
  ⇒ `undefined`, not `null`). **Confirmed idempotent** — also directly
  asserted by the existing test at `content.test.ts:142-146` (`out1`/`out2`
  double-sanitize check).
- `normalizeOutboundContent` — after the first call, `delta.content` is a
  string, so `Array.isArray(delta.content)` is false on any subsequent call
  and the branch never re-executes. **Confirmed idempotent.**

Both functions mutate in place and return the same object reference
(explicitly documented in the file's own comments at `content.ts:71` and
implied at `content.ts:95-97`), which is safe specifically because each SSE
frame is parsed fresh from JSON — but this is moot here since no double-call
exists.

## 3. Dialect-hold / passthrough transition audit (step 4)

Full relevant block: `server/src/routes/proxy.ts:1409-1598`. State declared
fresh per stream attempt (inside the per-request `if (stream)` branch, not
shared across retries/closures):

```
1416  let mode: 'undecided' | 'passthrough' | 'dialect' = 'undecided';
1417  let heldText = '';
```

Six total mutation sites for `heldText`/`mode` in the whole file (verified
by grep across proxy.ts — no other writers exist):

```
1520  if (mode === 'passthrough') {
1521    writeChunk({ ...anyChunk, choices: [{ ...choice, delta: { ...choice.delta, tool_calls: undefined }, finish_reason: null }] });
1522    continue;
1523  }
1525  heldText += text;
1526  if (mode === 'dialect') continue;
1528  const probe = heldText.trimStart();
1529  if (startsWithDialectMarker(probe)) {
1530    mode = 'dialect';
1531  } else if (!couldBecomeDialectMarker(probe) || probe.length > 256) {
1532    mode = 'passthrough';
1533    flushHeaders();
1534    writeChunk(mkChunk({ content: heldText }, null));
1535    heldText = '';
1536  }
1537  // else: still a strict prefix of a marker — keep holding.
```

and the end-of-stream flush:

```
1573  const hasText = headerSent || heldText.trim().length > 0;
...
1582  if (heldText.length > 0) {
1583    writeChunk(mkChunk({ content: heldText }, null));
1584  }
```

**Why double-send is structurally impossible here:**

1. `mode` is a one-way state machine: `'undecided' → 'dialect'` or
   `'undecided' → 'passthrough'`. Nothing in the file ever assigns `mode`
   back to `'undecided'` or from `'passthrough'` to anything else — grep
   confirms only two assignment sites (1530, 1532), both originating from
   the `'undecided'` branch (which is only reachable when `mode !== 'passthrough'`
   and `mode !== 'dialect'`, since dialect mode's own branch `continue`s at
   line 1526 before reaching the probe logic).
2. Line 1520's `mode === 'passthrough'` check runs **before** line 1525
   (`heldText += text`) in per-chunk order, and it unconditionally
   `continue`s. So the instant `mode` becomes `'passthrough'`, every
   subsequent chunk's text is written directly via `writeChunk` at line 1521
   and **never reaches line 1525** — `heldText` cannot accumulate any
   content that was already streamed via the passthrough branch.
3. At the exact moment `mode` transitions to `'passthrough'` (line 1532),
   `heldText` is flushed once (line 1534) and immediately reset to `''`
   (line 1535), in the same synchronous block, before the loop proceeds to
   the next chunk. There is no `await`/yield point between the reset and
   the next chunk's processing that could race.
4. Consequently, by the time the stream ends, if `mode === 'passthrough'`
   was ever reached, `heldText` is provably `''` (nothing after line 1535
   writes to it again — line 1525 is unreachable once `mode === 'passthrough'`
   per point 2). So the end-of-stream check at line 1582
   (`if (heldText.length > 0)`) is false whenever the mid-stream flush
   (line 1534) already fired. The two flush sites are **mutually
   exclusive by construction**, not by incidental runtime luck.
5. The only way `heldText.length > 0` at line 1582 is if `mode` stayed
   `'undecided'` the entire stream (never resolved before the provider's
   `[DONE]`/finish_reason — e.g. a very short response under 256 chars that
   never got a `couldBecomeDialectMarker` rejection) or `mode === 'dialect'`
   (accumulate-only mode, by design never streamed mid-flight, only
   rescued/flushed once at the end, optionally rewritten via
   `heldText = rescue.cleanText` at line 1568 — still a single write, single
   flush). Neither path double-sends.

**Conclusion for step 4:** the ordering (`passthrough` check before
`heldText += text`) is a deliberate and correct guard. No code path writes
already-passthrough-streamed content into `heldText` for a later re-flush,
and no code path flushes `heldText` more than once per stream attempt.

## Scope note / what this file does NOT rule out

This audit only covers `content.ts` and the proxy.ts dialect-hold/passthrough
block. It does not rule out duplication introduced downstream of the
proxy (e.g. in the consuming client's own buffer-accumulation code, or in
`route.provider.streamChatCompletion` / the individual provider adapters
upstream of line 1452, which were not in scope for this pass). Given the
example duplicated text showed a `V` / capital-letter split
("**V**Vamo testar!... uma análise completa do stat**e**amo testar!"), the
duplication looks like a client-side re-render/re-concat bug (two overlapping
copies of the same growing buffer) rather than a byte pattern consistent
with anything `sanitizeResponse`/`normalizeOutboundContent` could produce —
those functions never touch `delta.content` value except a straight
array→string replace, and the dialect-hold logic is single-flush by
construction as shown above.
