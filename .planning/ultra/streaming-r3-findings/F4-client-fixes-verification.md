# F4 — Client Fixes Verification (R1 debounce, R2 opentui patch, R3 streaming toggle, sync.tsx delta/reconcile)

Date: 2026-07-15
Scope: verify only, no fixes applied.

## Summary of the timeline discrepancy (headline finding)

**R1 (sdk.tsx always-debounce) has never been committed to git, in any commit, ever.**
`git log --all -S"Always debounce" -- services/atlas-terminal/src/tui/context/sdk.tsx`
returns zero commits. `git log` on the file shows only 4 commits total
(4e7478a2, 1c606dcf, db772555, ab5daca6); none of them touch the
conditional-flush → always-debounce logic. HEAD's `sdk.tsx` still has the
**old** "flush immediately when idle >16ms, debounce only if busy" logic
verbatim (`git show HEAD:...sdk.tsx`, lines ~42-73 of the committed blob).
The always-debounce version exists **only in the current uncommitted working
tree**. HANDOFF.md's "(latest)" 2026-07-15 entry claims R1 was "Implemented
... Verified: atlas-terminal tsc clean, 56/56 bun tests" — that work was
done but the code was never staged/committed.

**R2's persistence infrastructure is also uncommitted**, even though the
patch is physically live in `node_modules` right now:
- `services/atlas-terminal/package.json`'s `patchedDependencies` block is an
  uncommitted addition (`git diff HEAD -- package.json` shows the 3-line
  addition; not in HEAD).
- `services/atlas-terminal/patches/@opentui%2Fcore@0.1.99.patch` is
  **untracked** (`git status --short` shows `??`).
- `services/atlas-terminal/bun.lock` is modified/uncommitted.
So R2 works today, but a fresh `git clone` + `bun install` would silently
lose it (no patch would apply — `patchedDependencies` isn't in HEAD).

**A previously-undocumented "R3" fix is also present, uncommitted, in
`session/index.tsx`**: `streaming={!props.message.time.completed}` on both
the `<markdown>` and `<code>` renderables inside `TextPart` (lines 1581 and
1592). HANDOFF.md's "(latest)" entry explicitly states "Did NOT implement R3
(delay streaming toggle by one tick)" and the later "(later)" UAT-feedback
entry only describes adding a diagnostic `console.error` render-counter (which
is what HEAD actually contains — `git show HEAD:...index.tsx` confirms the
diagnostic block and hardcoded `streaming={true}` are what's committed). The
working tree has since **replaced** that diagnostic block with the R3-style
fix and a new comment explaining the rationale (persistent-instance
tree-sitter highlighting retries), but this change is not reflected anywhere
in HANDOFF.md. It is unclear which session made this edit or whether it was
tested.

**Practical implication for whether the fixes are "live":** atlas-terminal
has no build step — `package.json`'s `dev`/`smoke` scripts run
`bun run --conditions=browser src/main.tsx` directly against the TS source
tree. Git commit status does not gate runtime behavior here; whatever is on
disk in the working tree executes on the next process launch. So R1 and the
undocumented R3 change **are** live for any freshly-started `atlas` process
right now, despite being uncommitted — HANDOFF.md's operator guidance ("clean
restart and retest") is directionally correct, but the actual reason a stale
process wouldn't see the fix is that Node/Bun caches the loaded module in
memory per-process, not a build artifact — same effective symptom, different
mechanism than what HANDOFF describes.

---

## 1. R1 debounce logic correctness — VERIFIED CORRECT, no bug found

File: `services/atlas-terminal/src/tui/context/sdk.tsx` (current working tree, lines 42-73).

```
let queue: GlobalEvent[] = []
let timer: Timer | undefined

const flush = () => {
  if (queue.length === 0) return
  const events = queue
  queue = []
  timer = undefined
  batch(() => { for (const event of events) emitter.emit("event", event) })
}

const handleEvent = (event: GlobalEvent) => {
  queue.push(event)
  if (timer) clearTimeout(timer)
  timer = setTimeout(flush, 16)
}
```

- Every call to `handleEvent` unconditionally clears any pending timer and
  starts a fresh 16ms one — true trailing-edge debounce, timer correctly
  reset per event (sdk.tsx:71-72).
- `flush()` drains the entire queue in one `batch()` call, so all events
  accumulated during the quiet window land in a single SolidJS render pass —
  this is the intended fix for the "final reconcile + completion signal in
  separate render passes" bug.
- No bypass path exists: `handleEvent` is the only entry point into the
  queue, called from exactly two places — the SSE `for await` loop
  (sdk.tsx:97) and `props.events.subscribe(handleEvent)` (sdk.tsx:114). Both
  go through the same debounce; neither has a conditional immediate-flush
  fast path (that fast path was the pre-fix bug and has been fully removed,
  not left as a dead/alternate branch).
- No race: JS is single-threaded: the `setTimeout` callback (`flush`) cannot
  execute concurrently with `handleEvent`; `timer = undefined` inside
  `flush()` happens before events are emitted, so if a batched event handler
  synchronously re-entered `handleEvent` it would correctly arm a new timer
  rather than colliding with the in-flight flush. No re-entrancy bug found.
- One additional flush site: `startSSE()`'s reconnect-loop boundary
  (sdk.tsx:100-101) does `if (timer) clearTimeout(timer); if (queue.length >
  0) flush()` when the event stream itself closes (not a normal debounce
  tick) — this is a forced flush before backoff/retry, not a bypass of the
  16ms window during normal operation. Correct as written.

**Conclusion: R1's logic is sound. If R1 is genuinely running in the process
the operator tested, it is not the source of continued duplication.**

## 2. R1 uncommitted status — see headline section above.
`git diff HEAD -- services/atlas-terminal/src/tui/context/sdk.tsx` shows the
full replacement of the `last`/`elapsed<16` conditional-flush logic with the
always-debounce version. This is the R1 fix itself, sitting unstaged. HEAD
(`ab5daca6`, and all prior commits) still has the old logic.

## 3. R2 opentui patch — PHYSICALLY APPLIED and correct; infra uncommitted

- `node_modules/@opentui/core/index-fedv7szb.js:9518` — confirmed on disk:
  `renderable.streaming = this._streaming;` inside `applyMarkdownCodeRenderable`
  (function starts at line 9510). Matches the sibling
  `applyCodeBlockRenderable` (line 9504: `streaming: this._streaming`).
  **Not** the old hardcoded `= true`.
- `services/atlas-terminal/patches/@opentui%2Fcore@0.1.99.patch` exists on
  disk and its content matches exactly: a one-line diff changing
  `renderable.streaming = true;` → `renderable.streaming = this._streaming;`
  at the same line. Confirmed correct patch content.
- `package.json:47-49` has the `patchedDependencies` entry pointing at that
  patch file — but see headline section: this entry is itself uncommitted.
- **Caveat**: `applyMarkdownCodeRenderable` is called from three call sites
  in the vendored opentui bundle (index-fedv7szb.js:9813, 9841, 9972,
  9997/via rerenderBlocks) for markdown "table" and "code"-type token
  fallback paths, all of which now correctly read `this._streaming`. R2 is
  correctly and completely applied.

## 4. Other `streaming={true}` hardcoding not covered by R2/R3

File: `services/atlas-terminal/src/tui/routes/session/index.tsx`

- `TextPart` (lines 1579-1598, the assistant response body): now correctly
  wired as `streaming={!props.message.time.completed}` on both the
  `<markdown>` (line 1581) and `<code>` (line 1592) branches. This is the
  undocumented "R3" change described above — logically consistent with R2's
  fix (drives `this._streaming` false once the message completes) and with
  the intent described in HANDOFF's R3 sketch ("delay streaming toggle").
- **`ReasoningPart`'s `<code>` renderable at line 1503 still hardcodes
  `streaming={true}` unconditionally** — this was NOT updated alongside
  TextPart. The component already computes `isDone = createMemo(() =>
  props.part.time.end !== undefined)` (line 1473) and uses it elsewhere
  (line 1493, 1495), so wiring `streaming={!isDone()}` would be a trivial,
  consistent fix — but it hasn't been done. Because R2's patch makes
  `applyMarkdownCodeRenderable` respect `this._streaming`, and this prop is
  always `true` here, the reasoning/"Thought" block's prose code-renderable
  is still permanently in streaming mode, i.e. it still has the *precondition*
  for the same flash-at-completion / duplicate-paint class of bug R2+R3
  fixed for the main text body. Whether this is visually the bug the
  operator is currently reporting is unverified from static analysis alone
  (the operator's report describes normal chat responses, not thinking
  blocks) — flagged as a residual inconsistency, not confirmed as the live
  bug.

## 5. sync.tsx delta vs. reconcile handlers

File: `services/atlas-terminal/src/tui/context/sync.tsx`

- `message.part.updated` (lines 493-512): on a found part, does
  `setStore("part", messageID, index, reconcile(event.properties.part))`
  (line 501). `reconcile` is solid-js's store reconciler — it diffs the
  incoming part object against the existing one and patches only changed
  keys, but the incoming object is treated as the **complete, final**
  value — this is a full value replacement semantically, not an append.
  **No append/duplication risk in this handler** — verified.
- `message.part.delta` (lines 514-529): on a found part, does
  `(part[field] as string) = (existing ?? "") + event.properties.delta`
  (line 526) — an unconditional string append, keyed only by
  `event.properties.partID` + `event.properties.field`. **There is no
  event-id, sequence number, or offset check anywhere in this handler** —
  if the same `message.part.delta` GlobalEvent were ever delivered twice
  (SSE reconnect replay without a resume cursor, an upstream at-least-once
  redelivery, or a bug elsewhere that pushes the same event into the sdk.tsx
  queue twice), this handler would silently double-append that delta's text
  with no guard. This is a **real, unmitigated latent risk** for
  duplication, structurally independent of R1/R2/R3, though it was not
  possible from static analysis to confirm whether it is the actual
  mechanism behind the operator's still-reported bug. It is a distinct
  hazard from the already-fixed `chat.ts` dedup bugs (commits `a9acc882`,
  `e8e1f763`), which operate on a different layer (whole **text-part
  creation** dedup guarding against `llm_call` vs `transition:succeeded`
  vs `llm_delta` creating a second *part*) and do not address delta-level
  replay within an already-existing part.

## Answers to the verification questions

1. **R1 logic correct?** Yes — clean trailing debounce, no bypass, no race.
2. **R1 live?** Present only in the uncommitted working tree; HEAD never had
   it. Because atlas-terminal runs `bun run src/main.tsx` directly (no
   build step), the working-tree file is what executes on next launch, so
   it is functionally live for a fresh process — but not committed, not
   durable, and not what HANDOFF.md's history implies (it implies this was
   already committed after the "(latest)" session).
3. **R2 physically applied?** Yes, confirmed byte-for-byte in
   `node_modules/@opentui/core/index-fedv7szb.js:9518`. Patch file content
   matches. `patchedDependencies` entry present in the working tree but
   **uncommitted** (`package.json`, `patches/`, `bun.lock` all
   modified/untracked) — a fresh install would not reproduce it.
4. **Any other streaming=true leak?** Yes — `ReasoningPart`'s `<code>` at
   index.tsx:1503, never updated to use `!isDone()`.
5. **sync.tsx delta/reconcile safe?** Reconcile handler is safe (full
   replace). Delta handler has no dedup/sequence guard and would
   double-append if a delta event were ever redelivered — unverified
   whether this occurs in practice, but it is a real structural gap.
