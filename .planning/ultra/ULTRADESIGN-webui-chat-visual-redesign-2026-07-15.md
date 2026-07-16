# ULTRADESIGN — Web UI Chat Visual Redesign (Console markdown + reasoning)

Date: 2026-07-15 (executed 2026-07-16)
Scope: `services/web-ui-react` — Console chat rendering only. No state-management,
session, persistence, or folder-binding code touched.

## What shipped

1. **`src/components/ChatMarkdown.tsx`** — markdown renderer for chat prose.
   `react-markdown` + `remark-gfm` + `rehype-highlight`, styled entirely with
   inline style objects on the existing L2 Dark Prism tokens. Fenced code
   blocks get an icon-only copy-to-clipboard button (Check/Copy lucide icons,
   1.4s copied state).
2. **`ReasoningBlock`** (in `Console.tsx`) — collapsed-by-default "THINKING"
   block for the `'reasoning'` surface event kind, which previously fell
   through to the generic activity-event fallback. Chevron toggle is the exact
   `ToolCallCard` pattern (ChevronDown/ChevronRight, same header button style).
3. **Wiring** — `AgentTurn` text events, `MessageBubble` agent bodies, and
   `ToolCallCard` OUTPUT (prose-shaped only) now render through `ChatMarkdown`.

## Design contract decisions

### Palette — no new hex colors
- Body prose: `var(--l2-fg-1)`; secondary/reasoning prose: `var(--l2-fg-2)`;
  labels/chrome: `var(--l2-fg-3)`.
- Inline code + links + blockquote rail: `var(--atlas-celestial)` and the
  existing `rgba(74,93,191,…)` celestial tint family (same as `toolCardStyle`).
- Surfaces: `rgba(5,6,10,…)` code-block wells and `rgba(13,16,24,…)` chrome,
  both lifted verbatim from `toolPreStyle` / `toolCardStyle`.
- Hairlines: `rgba(237,234,224,0.06–0.14)`, the file's existing hairline ink.
- Syntax highlighting: **no stock highlight.js CSS theme imported.** A stock
  theme (e.g. atom-one-dark) hardcodes its own background/foreground hexes and
  would fight the token system. Instead `hljs-*` token colors are declared
  once in `src/app.css` (scoped under `.hljs`), mapped to the existing
  palette: celestial for keywords, emerald tint for strings, warn yellow for
  numbers/literals, violet for titles/functions, cyan for attrs/types, fg-3
  italics for comments.

### Typography
- Prose inherits Inter; matches `agentTextStyle` metrics (13.5px / 1.58).
- All code, labels ("THINKING", table headers) use `var(--l2-font-mono)` with
  the file's letter-spacing conventions (0.14em labels).
- Headings step 18 → 12.5px; h1 in chat deliberately maxes near body-plus,
  not page-title scale — chat answers must not out-shout the cockpit chrome.

### Radius / motion / state
- 2px radii everywhere (code blocks, tables, reasoning block, copy button).
- No new animation; expand/collapse is instant, same as ToolCallCard.
- `data-topo="muted"` on ReasoningBlock (existing semantic-state attribute).

### Reasoning block
- Collapsed by default; dim (`opacity: 0.85`), dashed hairline border to read
  as "scaffolding, not answer"; Brain icon + mono "THINKING" label in fg-3.
- Body renders through ChatMarkdown at 12.5px fg-2, max-height 320 scroll.

### Tool-card OUTPUT heuristic
`looksLikeProse()`: JSON-parseable text (starts `{`/`[`) → mono `<pre>`;
otherwise markdown only if it carries visible markdown structure (heading,
fence, list, bold, table). Raw command output / file dumps stay mono. Edits
(`isEdit`) always keep DiffView. ToolCallCard's status/collapse logic and
DiffView's diff logic are untouched.

## Deviations from the letter of the contract (and why)

1. **No `highlight.js/styles/*.css` import** — deliberate, see palette above.
   The contract allowed "a minimal custom override using existing color
   tokens if the stock theme clashes"; that option was taken (`.hljs` rules in
   `src/index.css`).
2. **Curated grammar subset instead of lowlight `common`** — 17 languages
   (ts/js, python, rust, go, c/cpp/csharp, java, bash, json, yaml, xml/html,
   css, sql, diff, markdown) with aliases, instead of rehype-highlight's
   default 37. Bundle discipline; unknown languages degrade to unhighlighted
   mono, still correct.
3. **`vendor-markdown` manual chunk in `vite.config.ts`** — the markdown stack
   (~329KB raw / ~101KB gzip) blew the 350KB entry budget when bundled into
   the entry chunk. Split into its own chunk following the existing
   `vendor-react`/`vendor-force-graph` pattern; entry returned to 344KB raw /
   84KB gzip (green). **No budget threshold was changed.**
4. **Operator/system bubbles got `whiteSpace: 'pre-wrap'`** — multi-line
   operator input previously collapsed to one line; markdown work made the
   asymmetry obvious. One-property fix, no layout change otherwise.
5. **`MessageBubble` markdown applies to agent-role bodies only** — operator
   text stays verbatim (an operator typing `*` literally should see `*`);
   system boot messages contain Windows paths that markdown could mangle.

## Verification (all from `services/web-ui-react`)

- `npm run check` — exit 0.
- `npx vitest run` — 58 passed, 0 failed (incl. new `chatMarkdown.test.tsx`,
  7 tests; `reasoningBlock.test.tsx`, 3 tests; all pre-existing suites green,
  `consoleStreaming`/event-merge logic untouched).
- `npm run build` (tsc + vite + bundle:check) — exit 0, no BUDGET violations.

## Files

- Added: `src/components/ChatMarkdown.tsx`, `src/test/chatMarkdown.test.tsx`,
  `src/test/reasoningBlock.test.tsx`
- Modified: `src/routes/Console.tsx` (render-layer only), `src/app.css`
  (`.hljs` token colors), `vite.config.ts` (vendor-markdown chunk),
  `package.json` / `package-lock.json` (react-markdown, remark-gfm,
  rehype-highlight)

---

## Addendum (2026-07-16): operator design pass ("temper")

Four signal-carrying touches applied on top of the redesign, each traceable to
L2 doctrine (PHILOSOPHY.md / EFFECTS.md):

1. **Streaming inference wake** (effect catalog #9) — while an agent turn is
   pending, a 2px left rail beside the turn runs a slow emerald traveling wave
   (`.atlas-inference-wake`, 2.6s, the one easing curve). It exists only while
   generating and resolves to stillness on completion — Law 5: nothing stays
   lit without cause.
2. **System receipts** — system-role messages (boot/binding notices) render as
   flat mono ledger lines with a bronze hairline, not conversation bubbles.
   HUD discipline: the system states; it does not chat.
3. **Binding truth** — the chat header badge shows the bound directory's tail
   name (full path on hover) instead of a no-information "BOUND".
4. **Transmit affordance** — send button brightens on approach, presses with
   weight, dims while a turn is in flight; the disabled composer speaks the
   system voice ("Turn in progress — streaming").

Plus: Console route is now lazy-loaded (same pattern as Graph), moving the
markdown stack out of the eager path — entry chunk 349.7KB → 289.8KB
(60KB budget headroom restored), Console 61.5KB lazy chunk.
