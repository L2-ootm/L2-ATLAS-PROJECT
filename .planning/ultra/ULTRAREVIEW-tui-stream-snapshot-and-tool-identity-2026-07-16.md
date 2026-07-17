# ULTRAREVIEW — TUI stream snapshot and tool identity regression

Date: 2026-07-16

## Root cause 1: emitted parts were live mutable references

Exact failure point: `services/atlas-terminal/src/adapter/events.ts`, `EventBus.emit`.

`ChatAdapter.appendPart()` emitted the same `DonorPart` object that it retained and
mutated as `llm_delta` chunks arrived. The TUI store therefore observed the part's
text changing before it processed the corresponding `message.part.delta`.

R5's offset guard correctly required:

```text
store text length == delta offset
```

But the shared reference had already advanced the store-visible text. Legitimate
deltas were rejected as duplicates. This produced the screenshot's isolated first
character and missing streamed answer.

### Proof

- The audit database for run `d90b7237-494c-460a-a724-8311114ca174` contains a
  clean, ordered `llm_delta` sequence and complete `llm_call` final text.
- A regression test now proves that the initial emitted assistant text part remains
  `""` after later chunks and that the final emitted snapshot is `"Hello, world"`.
- The repair clones event properties at the EventBus boundary, making emitted and
  replayed events historical snapshots.

## Root cause 2: native tool identity was read from the wrong field

Exact failure point: `services/atlas-terminal/src/adapter/chat.ts`,
`ChatAdapter.onRunEvent`.

Native runtime audit rows carry tool identity in `data.call_id`, while the adapter
only read top-level `tool_call_id`. It generated a fresh donor ID for every
`tool_requested` event, then could not match `tool_completed` to the running part.
Arguments were similarly stored under `data.arguments`, while the adapter looked
for `data.input`.

Consequences:

1. legitimate repeated `session_search` calls looked identical (`[summary=]`);
2. completion events could not settle their corresponding rows;
3. the `freellmapi` provider engagement receipt appeared as a fake tool call.

### Proof

The exact screenshot run contains three distinct `session_search` calls:

- browse all sessions;
- inspect one session around message 0;
- search for `Command Center goal model migration`.

Each has a distinct nested `data.call_id` and arguments. The new regression test
uses this runtime event shape and verifies one settled tool part with preserved
arguments and output, while the provider engagement marker is suppressed.

## Repair

- Snapshot all EventBus payloads with `structuredClone`.
- Resolve call identity from top-level `tool_call_id` or nested `data.call_id`.
- Resolve tool inputs from `data.input` or `data.arguments`.
- Resolve completion output from `summary`, `result`, or `text`.
- Suppress runtime/provider engagement rows that are receipts, not invocations.

## Verification

- `services/atlas-terminal`: 59 tests passed; `bunx tsc --noEmit` passed.
- `services/web-ui-react`: 78 tests passed; production build and bundle budget passed.
