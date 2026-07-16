# ULTRARESEARCH — WebUI chat streaming gap + industry-grade redesign

**Date:** 2026-07-15
**Trigger:** Operator report — web cockpit chat doesn't stream tokens (unlike
the atlas-terminal TUI), new sessions only appear after a manual browser
refresh, and the chat UI should be redesigned to industry-grade/SOTA quality
(thinking dropdowns, pretty tool-use, polished formatting).
**Scope:** `services/web-ui-react` only (the live cockpit — `apps/cockpit-web`
was removed in an earlier session).

---

## 1. Root causes (proof-based)

### 1a. Chat doesn't stream — polling, not SSE, and existing SSE is unwired

`AgentSurfaceProvider.tsx:270-291` runs a 2s `setInterval` calling `refresh()`
(`:84-118`), which does a plain GET `apiFetch` to
`/v1/surface-sessions/{id}/events?after_seq=` (`api.ts:473-481`).
`Console.tsx:245-276` renders whatever full-value events land in that 2s
window — there is no per-token delta consumption in the chat pane at all.
`Console.tsx:285-318` additionally layers an 8s watchdog poller for stuck
turns. Net: chat text updates in ~2s chunks, never token-by-token.

**The SSE client already exists and works** — `useRunStream.ts:79-152` opens
a real `EventSource` against `GET /v1/runs/{id}/stream` (`api.ts:806-808`,
proper reconnect/backoff) — but it's wired **only** into `RunDetail.tsx` (the
standalone run/audit detail page). `Console.tsx` never imports it. This is a
wiring gap, not a missing capability — the hard part (a working SSE hook with
reconnect) is already built and proven elsewhere in this same codebase.

Cross-reference, `services/atlas-terminal` (the TUI, confirmed working):
`gateway.ts:166-211` `streamRun()` reads the identical
`GET /v1/runs/{id}/stream`; `chat.ts:419-440` consumes `llm_delta` events and
appends `data.delta` to a live text part — genuine token-by-token streaming.
The web cockpit has no equivalent `llm_delta` consumer for chat turns.

**Gateway-side:** `native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:2687`
`surface_events` is a plain GET, not SSE — there is no
`/v1/surface-sessions/{id}/stream` route. The run-level stream
(`/v1/runs/{id}/stream`) is the one real-time channel that exists today.

### 1b. New sessions require manual refresh — no live subscription, no broadcast

`Missions.tsx:36-46` refetches only on `useEffect(() => void refresh(), [epoch])`.
`epoch` (`useGatewayHealth.ts:10-40`) increments **only on an offline→online
reconnect transition** (`:31`) — not on any steady interval. If the gateway
never drops, `epoch` never changes post-mount, so the session/mission list is
effectively fetch-once. `Sidebar.tsx:53,74` does poll every 30s, but only for
module-nav/VCS branch — not sessions/missions.

Gateway-side: the route table (`lib.rs:2636-2736`) has no
"session/mission created" broadcast endpoint at all. The gap is on both ends:
no client subscription AND no server broadcast to subscribe to.

### 1c. Chat rendering gaps (component-level)

Components: `Console.tsx` — `ChatPane` (:1003), `AgentTurn` (:1386),
`ToolCallCard` (:1330), `MessageBubble` (:1458).

| Capability | Current state |
|---|---|
| Thinking/reasoning block | `surfaceContracts.ts:3` defines a `'reasoning'` `SurfaceEventKind`; `consoleEvents.ts:63-71` passes it through — but `AgentTurn`'s render switch (`Console.tsx:1407-1446`) has **no case for it**. Falls to the generic fallback, rendered identically to unhandled kinds like `retry`/`retrieval`/`task`. No collapsible treatment exists. |
| Tool-call/result rendering | **Already solid** — `ToolCallCard` (`:1330-1384`) has collapsible headers, a running/done/failed status dot, a bespoke `DiffView` for edit/write tools, JSON `<pre>` fallback. Good foundation, needs visual polish only. |
| Markdown/code formatting | **None.** `MessageBubble` renders `{message.body}` as raw text (`:1488`); `AgentTurn` text events render `{event.text}` raw (`:1409-1413`). Zero markdown/remark/rehype/highlight/shiki dependency in `package.json` (confirmed via grep). |

---

## 2. Industry-pattern reference (ChatGPT / Claude.ai / Perplexity-class chat UIs)

Established patterns worth matching, none of which require novel invention:

1. **Token streaming with a subtle trailing cursor/pulse** while a turn is in
   flight; text settles (cursor disappears) on completion — exactly the
   `streaming` boolean toggle pattern atlas-terminal already uses, just needs
   a web equivalent.
2. **Reasoning/thinking rendered as a collapsed-by-default, distinctly
   styled block** (dimmer text, a "Thinking" or brain-icon label, expand/
   collapse chevron) — separate visual register from the final answer, never
   competing with it for attention.
3. **Tool calls as compact cards**: icon + tool name + one-line status,
   expandable to see full input/output/diff — ATLAS already has the bones of
   this in `ToolCallCard`; the gap is markdown/code-block polish inside it
   and visual consistency with the rest of the redesign.
4. **Markdown rendering with fenced-code syntax highlighting + a copy
   button per block** — table/list/heading support, since agent responses
   routinely include all of these.
5. **Auto-scroll that respects the user** — pin to bottom while streaming
   unless the user has scrolled up to read history, then don't yank them
   back down.
6. **Live-updating session/thread list** without requiring a refresh —
   table stakes for a multi-surface product where sessions can be created
   from the TUI, Discord, or the cockpit itself.

---

## 3. Proposed phased approach

Sequencing matters: streaming plumbing should land before UI polish, since
polish work (thinking dropdowns, markdown) needs to render against a live
token stream to be verified properly, not just static mock data.

### Phase A — Wire real streaming into the chat pane (highest leverage, most contained)
- Extend `Console.tsx`'s turn-rendering to consume `useRunStream`/
  `openRunStream` (already built, already proven in `RunDetail.tsx`) instead
  of / in addition to the 2s poll for the active turn.
- Requires checking whether `/v1/runs/{id}/stream` already emits `llm_delta`-
  equivalent events on the gateway side for the cockpit's session model, or
  whether that needs the same `llm_delta` SurfaceEventKind mapping
  atlas-terminal's adapter already does — this is the one open question
  needing a closer read of the gateway's stream payload shape before coding.
- Risk: low-medium. Reuses proven infrastructure; main work is wiring, not
  invention.

### Phase B — Live session/mission list updates
- Simplest fix: change `Missions.tsx`'s refetch trigger from
  "epoch-on-reconnect-only" to a steady short poll (e.g. 5-10s, matching
  `Sidebar.tsx`'s existing 30s pattern) — no gateway changes needed, ships
  fast.
- Better fix (larger scope): add a gateway broadcast SSE route for
  session/mission lifecycle events, subscribed to directly — true live
  update, no polling latency, but requires a new gateway route + Rust work.
- Recommend shipping the simple poll fix first, keep the broadcast route as
  a fast-follow if 5-10s latency isn't good enough in practice.

### Phase C — Chat UI redesign (thinking dropdowns, markdown, tool-use polish)
- Add a markdown renderer (react-markdown + remark-gfm is the standard
  choice; syntax highlighting via rehype-highlight or shiki) — first new
  frontend dependency for this concern, reasonable for a chat UI.
- Add the missing `'reasoning'` case in `AgentTurn`'s render switch: a
  collapsed-by-default block, distinct styling from the answer.
- Polish `ToolCallCard`'s existing structure to match the new markdown/
  formatting system rather than rebuilding it.
- This is a `frontend-design`/`ui-ux-pro-max`-skill-territory visual pass —
  recommend a short design-direction check-in (palette/typography/motion
  already established via the L2 Dark Prism system used elsewhere) before
  writing component code, so the result matches the rest of the product
  rather than reinventing a one-off style.

---

## Execution update (2026-07-15, same day) — Phase A + B shipped

Operator approved "Implement Phase A+B now, pause before C." Phase A's
investigation surfaced something more important than the transport-latency
issue it set out to fix:

**Real duplication bug found and fixed (not just transport wiring).**
`surface_events.py`'s `_KIND_MAP` maps BOTH `llm_delta` (each ~150ms streamed
chunk, payload `{delta: "..."}`) and `llm_call` (the turn's final reconcile,
payload `{text: "..."}`) to the same `SurfaceEventKind` — `'text'`. The kind
alone can't tell them apart. Two consequences, both fixed:

1. `consoleEvents.ts`'s `surfaceConsoleEvent()` only ever read `text`/
   `summary` from the payload — never `delta` — so delta chunks silently
   contributed nothing (explains "streaming not working": not broken
   exactly, just completely inert). Fixed: a payload with `delta` but no
   `text`/`summary` now projects to a synthetic client-side `'text_delta'`
   type, distinct from the final `'text'` reconcile.
2. **`AgentTurn` (Console.tsx) renders every event in `message.events` as
   its own block.** Had (1) been fixed naively — just making delta chunks
   carry their text — every chunk PLUS the final reconcile would each render
   as a separate stacked `<div>`: the exact "response repeats itself"
   pattern reported for the TUI, just not yet observed here because deltas
   were inert. Fixed with a `displayEvents` memo in `AgentTurn` that
   collapses a streaming run's deltas + its eventual reconcile into ONE
   block (extend in place while open; replace-not-append on reconcile),
   marking runs `_open`/closed so an unrelated later round's text is never
   mistaken for the same run.
3. `ConsoleMessage.body`/`streamDeltaStart` fixed the same way at the
   secondary level (the watchdog fallback path at `Console.tsx:314` reads
   `message.body` directly), for consistency even though `AgentTurn` (not
   `MessageBubble`) is what actually renders for agent turns today.

**Not done**: the actual transport swap (2s CLI-dispatch poll →
`useRunStream`-style low-latency SSE) — deferred. The merge-logic fix was a
correctness prerequisite that had to land first regardless (wiring faster
transport onto broken merge logic would have made the bug MORE visible, not
fixed it). The transport swap is nontrivial integration (the active run's
raw `/v1/runs/{id}/stream` AuditEvents vs. the session-scoped, Python-
projected `SurfaceEvent` stream `AgentSurfaceProvider` currently polls;
approvals/heartbeat still need the existing REST polling regardless) and
deserves its own focused pass.

**Phase B — session/mission list live updates**: `Missions.tsx` now also
polls every 8s (`MISSIONS_POLL_MS`, matching `Sidebar.tsx`'s existing 30s
pattern) in addition to the epoch-on-reconnect refetch, so a session/mission
created elsewhere shows up without a manual page refresh.

**Verified**: `services/web-ui-react` — `tsc -b` clean, vitest 50/50 passed
(2 new: `consoleStreaming.test.tsx`, `missions.test.tsx`), `vite build` +
bundle-budget check both green.

**Still open / Phase C not started**: the actual SSE transport wiring
(above); the visual redesign (markdown rendering, a real collapsible
thinking block for the already-defined-but-unhandled `'reasoning'` kind,
tool-card polish) — paused per operator request for a design-direction
check-in before writing component code.

## Sources

All findings sourced from a live Explore-agent read of this repository on
2026-07-15 (not external — this is an internal architecture investigation).
File:line citations above are the evidence trail; no claim in this document
is unsourced.
