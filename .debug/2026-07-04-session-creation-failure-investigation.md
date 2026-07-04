# atlas-terminal "Creating a session failed" — Full Investigation Log

**Status:** UNRESOLVED — blocks daily-driver use of atlas-terminal
**First seen:** 2026-07-03 operator UAT
**Last reproduced:** 2026-07-04 (current session)
**Impact:** TUI renders, composer accepts input, but submitting a prompt shows toast "Creating a session failed. Open console for more details."

---

## 1. Error location in source

`src/tui/component/prompt/index.tsx:1075-1091`:

```typescript
let sessionID = props.sessionID
if (sessionID == null) {
  const res = await sdk.client.session.create({ workspace: props.workspaceID })

  if (res.error) {
    console.log("Creating a session failed:", res.error)
    toast.show({
      message: "Creating a session failed. Open console for more details.",
      variant: "error",
    })
    return true
  }

  sessionID = res.data.id
}
```

The SDK client wraps responses as `{ data, error }`. When `res.error` is truthy, the toast fires.

## 2. What the SDK client does

`sdk.client.session.create()` calls `POST /session` through the generated SDK client (`src/sdk/v2/gen/sdk.gen.ts:1790`), which goes through:

1. `createClient` interceptor chain (`src/sdk/v2/gen/client/client.gen.ts:68-233`)
2. Response interceptor in `src/sdk/v2/client.ts:80-86` that throws if content-type is `text/html`
3. JSON body parsing at line 168-173

If fetch itself throws (network error), the client catches it and returns `{ error: ... }` (line 108-116).

## 3. Adapter-side handler

`src/adapter/atlasFetch.ts:337-341` (current line numbers after split):

```typescript
if (path === '/session' && method === 'POST') {
    const body = await readBody();
    const title = typeof body['title'] === 'string' && body['title'] ? body['title'] : 'New session';
    return json(chat.createSession(title));
}
```

`chat.createSession()` in `src/adapter/chat.ts:125-140` is pure local state — no gateway call. Returns a `DonorSession` object. This function has never failed in any test.

## 4. What we tested

| Test | Result |
|------|--------|
| Raw adapter `POST /session` (direct fetch) | 200 OK, valid session object |
| SDK client `session.create({})` (through createOpencodeClient) | `{ hasError: false, hasData: true }` |
| Headless `bun run src/main.tsx --prompt "hello"` | Passes (no toast) |
| Interactive TUI `bun run dev` → type prompt → enter | FAILS with toast |
| `bun test` (26 tests including adapter + SDK client) | All pass |

## 5. What we know

- The adapter code is correct — it creates sessions locally and returns valid JSON
- The SDK client processes the response correctly in isolation
- The headless `--prompt` harness passes
- The interactive TUI fails consistently

## 6. What we DON'T know

- **The actual error object** — `console.log("Creating a session failed:", res.error)` prints to the TUI's internal console, not to the terminal stdout. The "Open console for more details" instruction references a donor-feature (the opencode debug console) that may not be wired in the ATLAS adapter.

- **Whether the error is a fetch failure, response parse error, or SDK interceptor throw** — we can't distinguish these without seeing `res.error`.

- **Whether the interactive TUI's fetch path differs from headless** — the `--prompt` flag bypasses the interactive session flow. The interactive path goes through `prompt/index.tsx` which has a different initialization sequence.

## 7. Likely root cause hypotheses (ranked)

### H1: Gateway binary is stale or a leftover process is serving stale responses
The most common recurring failure mode in STATE.md history. If the gateway process from a previous session is still running but its state is corrupted, POST /session could return a non-JSON response (e.g., an error page), which the SDK client's response interceptor would catch as an error.

**How to verify:** Kill all atlas-gateway processes, rebuild with `cargo build --release -p atlas-gateway`, restart with `atlas gateway start`, then retry.

### H2: The SDK client's response interceptor throws on the adapter's response format
The interceptor at `src/sdk/v2/client.ts:80-86` throws if content-type is `text/html`. If the adapter's error handler (`atlasFetch.ts` catch block at line 380) returns an error page instead of JSON, this would trigger.

**How to verify:** Add a temporary `console.log` inside the adapter's catch block to see if it fires.

### H3: The `workspace` query parameter causes a routing mismatch
The SDK sends `POST /session?workspace=...`. The adapter strips query params via `new URL(url, 'http://donor.local').pathname`. This should work, but there could be an edge case with how the SDK client constructs the URL.

**How to verify:** Log the actual URL the SDK client sends before it reaches the adapter.

### H4: The SSE event stream must be connected before session creation works
The adapter's session creation is local, but the donor TUI's sync layer may require events from the SSE stream before it considers the session valid. If the SSE connection isn't established before the user types a prompt, the session might be created but the reactive store doesn't see it.

**How to verify:** Check if `GET /event` is connected before the prompt submission.

## 8. Next diagnostic steps (for future session)

1. **Capture the actual error:** Add `console.error("SESSION_CREATE_ERROR:", JSON.stringify(res.error))` at prompt/index.tsx:1080 and run `bun run dev` — the error will appear in the terminal where `bun run dev` is running.

2. **Check gateway process state:** Run `atlas gateway status` before launching the TUI. If "online", kill and restart it fresh.

3. **Test with a clean gateway:** Kill all node/bun/atlas-gateway processes, rebuild gateway, `atlas gateway start`, then `bun run dev`.

4. **Trace the actual fetch:** Temporarily add logging inside the adapter's `atlasFetch` catch block to see if the error originates from the adapter or the SDK client.

5. **Compare headless vs interactive:** The `--prompt` flag creates a session via a different code path (`src/main.tsx:32-34` passes `args.prompt`). The interactive path goes through `prompt/index.tsx:1077`. Check if `props.workspaceID` or `props.sessionID` has an unexpected value in the interactive case.

## 9. Files to inspect in next session

- `src/tui/component/prompt/index.tsx` — lines 1075-1091 (session creation)
- `src/tui/app.tsx` — how the prompt component gets its props (sessionID, workspaceID)
- `src/tui/context/sync.tsx` — how store.session and store.provider are populated
- `src/adapter/atlasFetch.ts` — the POST /session handler + catch block
- `src/adapter/chat.ts` — createSession method
- `src/sdk/v2/client.ts` — response interceptor (line 80-86)
- `src/sdk/v2/gen/client/client.gen.ts` — the request/response handling (line 68-233)

## 10. Commit history

- `db772555` — STAGE 3 sprint (claimed fix via chat.ts session.created → session.updated)
- `cdc6019` — Split /config/providers vs /provider endpoints
- Current HEAD — both fixes applied, session creation still fails interactively
