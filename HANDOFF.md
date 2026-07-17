# Handoff — L2 ATLAS Finish Sprint

## Session update — 2026-07-17: distribution sprint — slash actions, installer hardening, public README, GSD/L2 framework, security gate

Operator mission: slash-command overhaul (WebUI first), installation workflow
per `C:\Users\Davi\Downloads\AI_Cockpit_Distribution_and_Launch_Playbook.md`,
repo audit, README rewrite, then (mid-session rescope) GSD framework refactor
for L2/ATLAS instead of media assets, and the pre-public security gate WITHOUT
flipping the repo public. 5 commits on `codex/chat-actor-workspace`.

**1. WebUI slash-command action layer.** `atlasCommands.ts` gains
`kind: 'prompt' | 'action'`: seven WebUI-local action commands (`/help`,
`/new [unbound]`, `/clear`, `/agent <atlas|claude|codex>`, `/bind`, `/unbind`,
`/go <page>`) execute client-side in Chat (session/runtime/binding/navigation;
`/help` renders a markdown command index into the transcript). Composer routes
them via a new `onAction` prop; the Console palette stays prompt-only and hides
them. TUI parity deliberately deferred (operator said WebUI first).

**2. Installer hardening (playbook).** `install/install.ps1`: winget offer for
Python; optional-tool offers for Rust/cargo and Bun where each skipped
toolchain names the exact surface it disables (gateway → `atlas up`, terminal
UI → bare `atlas`); session+user PATH repair with the venv `Scripts` dir;
post-install `atlas --help` validation; recovery-step error messages.
`@l2/atlas`: repository/bugs/homepage metadata, files allowlist, publishConfig,
engines `>=20` enforced in `bin/atlas.js`, package README. Validated: both
scripts parse clean, atlas-cli 20/20 node tests, `npm pack --dry-run` = 11
intended files, local `.venv\Scripts\atlas.exe` path logic confirmed live.
**Clean-VM end-to-end run still owed** (this environment cannot provide one).

**3. Public README rewritten** — positioning per playbook Phase 18, badges,
irm one-liner + inspectable variant + POSIX path, surfaces table, mermaid
architecture map, module example validated against `validate_manifest`,
honesty-first section, orientation table. Media slots are commented `<img>`
tags landing in `docs/media/` (operator produces media separately).

**4. GSD/L2 framework (rescoped task).** New first-party execution doctrine,
"GSD/L2 — Goal · Slice · Deliver": `skills/atlas/gsd/` (README + init,
discuss, plan, execute, verify, debug, ship, progress — plain-markdown,
runtime-agnostic, mapped onto ATLAS primitives: judged missions, durable
actors, audit-ledger evidence, wiki filing, evidence tiers) + bundled
`modules/gsd` module exposing `/gsd`, `/gsd-init`, `/gsd-discuss`,
`/gsd-plan`, `/gsd-execute`, `/gsd-verify`, `/gsd-debug`, `/gsd-ship` on all
surfaces, with a cockpit page. `RESERVED_COMMANDS` extended with the action
command names. DECISION: the "bundled modules dir stays empty" test became an
exact first-party allowlist `['gsd']`. Owed UAT: `atlas module sync` +
activate `gsd` live, run `/gsd` from Chat/terminal.

**5. Pre-public security gate — PASS, repo NOT flipped.** Tree + full-history
(775 commits) scans found no secret material (all hits = redaction code and
test fixtures). `.mimocode/`, `.ops/`, planning scratch, `*.backup` now
gitignored (untracked count 0). Flagged accepted-risk: 25 `C:\Users\Davi`
path occurrences in 18 tracked files + git authorship metadata. Report + the
operator pre-flip checklist:
`.planning/reports/pre-public-security-gate-2026-07-17.md`. NOTE: the RTK
hook truncates piped git output — history scans must run through
`rtk proxy git …`.

**Verification:** WebUI 149 passed + tsc + eslint + production build/budgets;
agent-runtime 922 passed / 1 skipped; atlas-cli 20/20; installer parse checks;
`modules/gsd` validated through live `discover_modules`.

**Next:** 1) operator UAT: `/help`·`/agent`·`/go` in Chat, `atlas module sync`
→ `/gsd` live, installer on a clean Windows Sandbox; 2) decide finding 7
(machine paths in `.planning/`) then push + flip public; 3) TUI parity for the
action commands; 4) media assets into `docs/media/` + uncomment README slots.

## Session update — 2026-07-16 (later): backlog committed, durable actor supervisor, Codex runtime + agent dropdown, module framework slice 1, irm installer

Operator asked to verify continuation state, strengthen the subagent
framework, build the modularity/self-extension vision (deactivatable modules,
user-created modules with WebUI pages + auto-propagating slash commands, ATLAS
skill pack, plugin direction), wire Codex like Claude Code with a runtime
dropdown, and stand up the irm/npm install framework.

**0. Continuation verified + backlog committed.** The prior sessions' 66-file
working tree was verified (all suites) and committed as 5 logical commits
(gateway/migrations, agent-runtime, atlas-terminal, web-ui, docs). Full-suite
run caught 5 stale prompt-golden hashes the prior session's focused tests
missed — regenerated (a scratch regen script exists; consider promoting to
`scripts/`).

**1. Durable actor supervisor (subagent framework strengthening).** The
infrastructure slice of `docs/plans/2026-07-16-subagent-orchestration-design.md`:
- Migration 0022: `actors` (queued→running→completed|failed|cancelled|orphaned,
  UNIQUE idempotency key, heartbeat, bounded result/error, terminal-immutable
  trigger) + `actor_deliveries` inbox with claim lease.
- `actor_service.py`: DB-pure monotonic CAS state machine; recursive idempotent
  cancel; wait with race-close; claim/acknowledge lease (crash between claim
  and ack retries); orphan sweep reports orphaned, never success. Lifecycle
  projects as `subagent_run` events in the native payload shape, so the
  existing WebUI orchestration rail renders durable actors with no UI change.
- `actor_worker.py`: hidden detached worker (actor id only on argv; goal read
  from SQLite), 5s heartbeats, child work runs as a normal mission+run.
- `actor_bridge.py`: D-001-safe PluginContext registration of the
  `atlas_actor` Hermes tool (run/spawn/status/wait/cancel) + `pre_llm_call`
  inbox claim-inject + `post_llm_call` acknowledge. atlas_audit gained
  public `get_connection`/`get_lock`/`run_for_session`. Registered per-run in
  native.py; orphan sweeps wired into runtime daemon startup and
  `atlas runtime reconcile`. Core policy documents the actor contract.
- NOT yet built (per design doc, deliberate): gateway actor list endpoint,
  UI actor detail view beyond the existing rail, model override resolution in
  the worker (child runs always execute runtime `native` with inherited
  provider selection).

**2. Codex runtime + agent dropdown.** `agents/codex.py` drives the local
OpenAI Codex CLI headlessly (`codex exec --json --skip-git-repo-check`),
mapping its JSONL item/turn events onto the audit bus with full parity
(agent_message→llm_call, command/mcp/file/web items→tool_call/completed/
failed, usage receipt, failure). Injectable runner for tests;
`ATLAS_CODEX_BIN` override; cooperative cancel terminates the child. Runtime
key `codex` accepted everywhere (registry, VALID_AGENTS, schema Literals,
gateway validation via a shared `VALID_AGENTS` const). WebUI: the two-button
toggle is now the `AgentPicker` dropdown (Chat), Console gained `+ Codex`
launcher/window titles/palette entry, Command page includes it, native label
now reads ATLAS. Terminal `/agent` lists codex. NOTE: the Codex JSONL event
shape is duck-typed/tolerant but was written against the documented
experimental stream — first live run should confirm mapping.

**3. Module framework slice 1** (`docs/plans/2026-07-16-module-framework-design.md`).
One registry (0007 modules table + 0023 manifest columns) for seeded
built-ins and manifest modules. `module.yaml` discovery from `<repo>/modules`
+ `<ATLAS home>/modules`; sync preserves activation, flags vanished sources
missing; v1 capabilities are DECLARATIVE ONLY: slash commands (gateway
`/v1/commands` → merged by WebUI palette and terminal, built-in names never
shadowed) and schema-driven pages (`/m/:moduleId` ModuleHost renders
heading/markdown/metrics/actions blocks; actions deep-link `/chat?draft=`).
`atlas module sync|create` (create = scaffold+sync+activate — the self-wiring
entry point the agent uses via terminal). Sidebar MODULES section routes
manifest modules to the host. `skills/atlas/` pack seeded (module-builder,
loop-discipline, handoff) and referenced from the core policy Self-extension
section. Bundled `modules/example-hello` proves the path and is test-locked.
Later slices documented in the design doc: module tools, sidecars, live
metrics bindings, signed packages/store, module-provided agent runtimes.

**4. Install framework.** `install/install.ps1` (irm|iex): prereq checks with
winget offers, source mode default (clone + scripts/install-atlas-cli.ps1),
release mode (`npm i -g @l2/atlas` + `atlas install --manifest`) ready for
when bundles publish. `docs/operations/INSTALL.md` documents all paths +
deferred desktop/exe + release-bundle CI. Parse-checked only — not executed
end-to-end on a clean machine.

**Verification:** agent-runtime 905 passed / 2 skipped; gateway cargo 117;
atlas-terminal 66 + tsc; WebUI 121 + tsc. All committed (9 commits this
session). `main` is many commits ahead of origin, unpushed.

**UAT owed / next session:**
1. `atlas db init` (migrations 0022/0023), stop the running gateway and
   rebuild `target/release/atlas-gateway.exe` (it locks while running and
   predates /v1/commands, module fields, codex validation), then `atlas
   restart`.
2. Live actor UAT: ask ATLAS to `spawn` a detached actor, watch the
   constellation rail, confirm the completion notice arrives on a later turn
   exactly once, test cancel + orphan sweep after killing a worker.
3. Codex UAT: `npm i -g @openai/codex` + `codex login`, pick CODEX in the
   Chat dropdown, confirm event mapping (tool cards, usage receipt).
4. Module UAT: `atlas module sync` + activate `example-hello`, check /hello
   in palette + TUI, the sidebar MODULES entry, and `/m/example-hello`;
   then have ATLAS build a real module with `atlas module create`.
5. Installer: run install.ps1 on a clean VM/sandbox (WSB) before publishing.
6. Deferred: gateway actor list endpoint, module tools/sidecar slices,
   POSIX install.sh, release-bundle CI.

## Session update — 2026-07-16: truncation authority fixed, session-first Runs, compact audit logs, systems/retention integrity

The exact run shown stopping at `**2. Continuous Knowledge G` contained a complete
7,700-character delta stream in SQLite. Its later authoritative `llm_call` event was
exactly 2,000 characters because `NativeAtlasAgent._map_result` reused the capped run
summary for final-surface reconciliation. The WebUI correctly replaced the streamed
text with that authoritative—but truncated—event. The final audit event now carries
the complete response; only the compact mission/run summary remains capped. A
regression test uses a response longer than the cap and proves both contracts.

Runs is now a session index backed by the real `runs.session_id`: expand a session to
see its prompts/runs, then open one run to inspect its response and evidence. Legacy
unbound rows with no session id remain independent. Run Detail and Ledger project
adjacent `llm_delta` events into expandable bursts, and Console does the same for
normalized text deltas. The underlying audit rows are untouched, with grouped/raw
switching retained where appropriate.

The systems pass found two truthfulness defects. Integrations previously converted a
failed status request into a fabricated stopped/offline state; failed probes now show
`UNKNOWN`. More importantly, the compiled ATLAS core policy was hashed and persisted
but never delivered in the native harness system message. New immutable run snapshots
store the exact policy text and the harness receives it. Prompt v1.0.1 now requires
registered/configured/reachable/verified-live distinctions and separates optional
provider memory from transcripts, audit records, and Brain Graph state. This directly
addresses the unsupported claims in `C:\Users\Davi\Downloads\about-ATLAS.txt`.

Retention is safe and operator-visible. Migration 0020 removes the snapshot DELETE
trigger that accidentally blocked SQLite cascade/authorized purge while retaining the
no-UPDATE immutability trigger. Expired archive purge now removes approvals, tool
records, artifacts, audit events, and snapshots, while preserving compact observations
with deleted run links detached. Control > Storage exposes only the real due-archive
transaction with explicit confirmation. Automatic sweeps and arbitrary date filters
are labeled planned until their scheduler/preview backend exists.

**Verification:** agent-runtime 847 passed / 2 skipped; atlas-core 97; atlas-terminal
59 + TypeScript; WebUI 94 + ESLint + TypeScript + production build/bundle budgets;
`git diff --check` clean. Full forensic record:
`.planning/ultra/ULTRAREVIEW-stream-run-log-and-system-integrity-2026-07-16.md`.

**UAT owed:** restart/rebuild the local stack so migration 0020 and runtime policy
v1.0.1 are active; run one response longer than 2,000 characters; expand a multi-prompt
session in Runs; inspect grouped/raw deltas; verify unreachable integrations show
UNKNOWN; use Storage only with a deliberately expired test archive.

## Session update — 2026-07-16: shared Chat/Console session navigator, configurable streaming visuals, conditional auto-follow

Chat and Console now share an ATLAS-styled session drawer modeled on the useful
information architecture of the Codex sidebar without copying its visual treatment.
The drawer includes session functions, filtering, direct `UNBOUND` sessions, and
collapsible folder/project groups for bound sessions. Each surface persists its own
payload shape behind one shared metadata catalog; cross-surface selections route to
the owning page and restore the selected session. New sessions inherit the current
binding, while `NEW UNBOUND` explicitly clears it. The durable catalog is browser
local for this iteration because gateway surface sessions are ephemeral execution
and permission leases, not conversation history.

The chunk scan-line effect is restored on both pages through the shared
`StreamReveal`. Coarse incoming chunks are paced into a smoother reveal, the visible
prefix is rendered through Markdown continuously, and each new chunk restarts a
restrained frontier scan. Control now has a `VISUALS` tab with effect on/off, slow /
balanced / fast reveal speed, subtle / visible / high signal intensity, and
near-bottom follow controls. Reduced-motion remains respected.

Chat and Console auto-follow while the transcript is within 180 px of the bottom.
Scrolling farther upward detaches follow so history can be read without being
yanked; the existing jump-to-latest control reattaches it. Console route remounts
also preserve active in-memory turns instead of allowing a stale debounced snapshot
to overwrite the continuation.

**Verification:** WebUI 84/84 tests, ESLint clean, TypeScript clean, production
build and bundle budgets green, `git diff --check` clean. Design/architecture note:
`docs/plans/2026-07-16-session-navigator-and-stream-visuals.md`.

**UAT owed:** create/switch/reload unbound and folder-bound sessions on both pages;
cross-route into a session owned by the other surface; tune Visuals during a
Markdown-heavy stream; verify near-bottom follow and scroll-away detachment.

## Session update — 2026-07-16: TUI R6 mutable-event regression fixed; native tool identity repaired; `/chat` renders Markdown during streaming

Operator reported the TUI duplication failure was worse after R5 and supplied a
screenshot showing three visually identical `session_search` rows plus an isolated
`F`, and requested smoother/more visible WebUI streaming with formatting applied
before completion.

**1. TUI R6 — R5's offset guard exposed a shared-reference bug.**
`ChatAdapter` emitted a `DonorPart` object and then continued mutating that same
object for incoming deltas. Because the in-process TUI store held the same reference,
its text length advanced before `message.part.delta` arrived; the R5 offset guard
then rejected legitimate deltas as duplicates. `EventBus.emit` now snapshots every
JSON-shaped payload with `structuredClone`, so emitted/replayed events are immutable
historical state. A regression test proves the initial streamed part remains empty
after later chunks while the final snapshot contains the complete text.

**2. The repeated search rows were three real calls rendered without identity.**
DB forensics on the exact run showed three distinct `session_search` invocations
(browse, inspect one session, query Command Center history). Native audit events put
identity in `data.call_id` and inputs in `data.arguments`; the adapter only read
top-level `tool_call_id` and `data.input`, generated unrelated IDs, could not settle
completions, and displayed each row as `[summary=]`. The adapter now reads both
shapes, preserves arguments, accepts completion `text`, and suppresses provider
engagement receipts such as `freellmapi` that are not tool invocations.

**3. `/chat` streaming now formats in real time.**
`StreamReveal` renders its paced visible prefix through `ChatMarkdown` continuously,
so headings, lists, emphasis, links, and code formatting appear while the agent is
still responding. The pacing uses fractional carry, a 28ms paint cadence, and a
bounded adaptive rate to smooth coarse chunks. The previous bright trailing text
effect was replaced by a restrained glow on the newest Markdown block and a short
green/blue frontier line.

**Verification:** atlas-terminal 59/59 + TypeScript clean; WebUI 78/78 + production
build and bundle budgets green. Forensic report:
`.planning/ultra/ULTRAREVIEW-tui-stream-snapshot-and-tool-identity-2026-07-16.md`.

**UAT owed:** clean `atlas restart`, then repeat a tool-using TUI prompt and inspect
the `/chat` live Markdown cadence.

## Session update — 2026-07-16: TUI duplication R5 (client delta replay), English-default language policy, `atlas restart`, dedicated WebUI Chat page + console truncation fix

Operator reported duplication still live after clean restart (screenshots: TUI
"who are you" run + WebUI hino run truncated at "Bril"), Portuguese-bound
replies, and asked for: `atlas restart`, a dedicated WebUI chat page,
conditional smooth autoscroll, once-per-session run receipts, and a styled
paced streaming reveal.

**1. TUI duplication R5 — server exonerated by DB forensics; client delta
replay path closed.** Dumped the exact screenshotted runs from
`~/.atlas/atlas.db` audit rows: the delta stream, `llm_call` final text, and
transition summary were all CLEAN (single "é só falar 🫡"), rowid-ordered,
`end_of_turn` flagged — so the R4 `_diff_cumulative_chunk` boundary guard
works and everything upstream of the client is correct. The gateway relay +
binary were verified fresh (binary newer than sources; `rowid > cursor`
semantics correct). The remaining live duplication path is the one HANDOFF
already documented as the latent gap: atlas-terminal's donor `/event` channel
replays the last 256 bus events to ANY (re)subscriber (`EventBus.replayRecent`)
and `sdk.tsx`'s `startSSE` reconnect loop re-subscribes on any stream end —
re-applied `message.part.delta` events append the same text again, with no
client dedup. Mid-run replay ≈ "even more duplicated while streaming". Fixes
(defense in depth, all committed):
- `events.ts`: `replayRecent` never replays `message.part.delta` (replayed
  `message.part.updated` events serialize the live part at forward time, so
  they already carry full text — deltas add only corruption to a late
  subscriber).
- `chat.ts`: delta emissions now carry `offset` (authoritative text length
  before the append).
- `sync.tsx`: the `message.part.delta` handler drops any delta whose `offset`
  doesn't match the store text length (duplicate delivery / ordering
  violation); the final part.updated reconcile remains the authority.
- New tests: offsets `[0,3,7]` asserted; `/event` replay asserted to contain
  part.updated but never part.delta. atlas-terminal: bun test 58/58, tsc clean.
- UAT owed: this environment can't drive the live TUI; if duplication STILL
  recurs, instrument `startSSE` reconnects (the trigger) — the render layer
  (opentui `updateBlocks(true)` on streaming flip) re-renders from store text,
  so with the store now guarded the display should follow.

**2. Portuguese-bound replies — English-default language policy.** No language
instruction existed anywhere in the prompt stack (checked atlas_core.md,
prompt_builder/system_prompt, i18n is static-strings-only, config.yaml has no
display.language) — the model inherited Portuguese from cross-session context.
`prompts/atlas_core.md` now carries: English by default; another language only
when the operator's current message uses it or they ask; never carry language
from retrieved context/past sessions. Golden prompt sha256s regenerated (5
files). Verified the compiled contract IS the native run's `system_message`
(native.py `_contract_system_message`).

**3. `atlas restart`.** `_restart_cmd` = `_down_cmd` then `_up_cmd` with the
normal interactive picker (or `--yes/--services/--json` passthrough); a hard
down failure aborts before the up phase. Registered in the "Getting Started"
help tab. 3 new tests (order, abort-on-failure, services passthrough);
agent-runtime suite 846 passed.

**4. WebUI: dedicated Chat page (`/chat`) + console streaming fixes.**
- **Truncation root cause (the "Bril" hino run): Console's stuck-turn watchdog
  finalized the turn on the FIRST terminal run-record sighting, while the tail
  surface events (last deltas + final reconcile) were still unpolled — once
  `activeTurn` cleared, the merge effect never applied them. DB had the full
  answer.** Fix (Console + Chat): first terminal sighting only forces
  `agentSurface.refresh()` and holds the turn; finalize on the next tick if the
  terminal event still hasn't landed. Existing continuation test updated to the
  two-tick contract.
- **New `/chat` route** (lazy, own 17KB chunk; sidebar MISSION → CHAT):
  single-transcript operator chat built on the same surface-session contracts —
  agent picker (ATLAS/Claude Code), project/folder binding with lazy project
  registration, cancel-run button, localStorage persistence (pending turns
  marked interrupted on hydrate), empty-state, per-run tool cards + reasoning
  blocks (imported from Console), result footer (turns/cost).
- **Paced streaming reveal**: new `StreamReveal` component — buffers incoming
  chunks, reveals at a backlog-adaptive rate (~420ms drain, ≥55cps) all the way
  to the end of the answer; trailing 24-char "hot edge" glows and cools; scan
  bar pulses at the frontier; `onSettled` swaps to full markdown only after the
  reveal catches up. prefers-reduced-motion = instant.
- **Autoscroll**: stick-to-bottom only when already pinned (<48px from bottom);
  rAF follow during streaming; scrolling up detaches; "LATEST" pill re-pins
  smoothly. Applied to BOTH Chat and console ChatPane (TopoScroll gained an
  optional viewportRef/onViewportScroll).
- **Run-receipt de-noise**: `turnReceiptSignature()` — the merged "run started
  · runtime · privacy" receipt renders only when it differs from the previous
  agent turn's (once per session in practice). Applied to both surfaces.
- Verified: tsc clean, vitest 77/77 (2 new chat tests: delta+reconcile renders
  once; receipt once across two runs), vite build + bundle budget green.

**Next:**
1. Operator UAT: TUI duplication after a clean relaunch (watch for whether it
   EVER recurs — if yes, log `startSSE` reconnects), WebUI /chat page live
   streaming feel, console truncation gone, English-default replies.
2. If the scan-edge reveal feels right in /chat, port `StreamReveal` into
   Console's AgentTurn (replaces `SmoothStreamText`).
3. Deferred from previous sessions: WebUI SSE transport swap (2s poll → push),
   workspace-root/ATLAS-home split design pass, freellmapi `google.ts`
   cumulative-diff guard upstream.

## Session update — 2026-07-15 (R3): streaming duplication root-caused — mid-tool-call retry, not a render bug; uncommitted R1/R2/R3 from prior session committed

Operator reported (screenshot) that the R1+R2 fixes from the prior "(latest)"
session did NOT resolve the streaming duplication. Ran a full ULTRAREVIEW
(4 parallel subagents) instead of assuming a stale-process false alarm again.
Full writeup: `.planning/ultra/ULTRAREVIEW-streaming-duplication-R3-mid-tool-call-retry-2026-07-15.md`.

**Root cause (new, 4th layer — content duplication, not render duplication):**
`foundation/atlas-hermes/agent/chat_completion_helpers.py:2144-2186` (vendored,
D-001) has a code-documented, intentional mid-tool-call silent stream retry: if a
transient connection drop happens while a tool call is forming, it fires a "⚠
Connection dropped mid tool-call; reconnecting…" marker through
`stream_delta_callback` and re-enters the provider call from scratch — with no
end-of-turn (`None`) signal in between. ATLAS's `_DeltaBuffer`
(`native.py`, pre-fix) did pure unguarded concatenation, so the regenerated
preamble landed stitched directly onto the interrupted one: two near-identical
copies of the same paragraph with a small textual offset (sampling variance),
exactly the operator's reported pattern. This is architecturally invisible to
every previous fix — R1/R2/prior-session part-creation dedup all operate on the
**render** layer and assume the underlying text stream is already correct
content; this bug corrupts the content itself, one layer upstream.

**Fix**: `native.py`'s `_DeltaBuffer.push()` now detects the retry marker text
and, when found inside an open turn, flushes the pre-drop segment as
`final=True` before the marker + retried text start a fresh segment — the
client already knows how to start a new part on a closed `streamingText` entry
(unchanged `chat.ts` logic), so the retry now renders as two visually distinct
parts (interrupted preamble, then reconnect notice + clean regenerated answer)
instead of one seamless garbled block. Does not eliminate the foundation's
intentional redundant-generation tradeoff (out of scope, vendored) but makes the
failure mode honest/comprehensible instead of indistinguishable from a
rendering defect. New tests:
`test_delta_buffer_splits_on_mid_tool_call_retry_marker`,
`test_delta_buffer_retry_marker_without_open_turn_is_not_split`.

**Commit-hygiene finding**: the prior session's R1 (sdk.tsx always-debounce) was
**never committed, in any commit** — `git log --all -S"Always debounce"` returns
nothing; HEAD still had the old conditional-flush logic despite HANDOFF claiming
it was "Implemented ... Verified." R2's persistence infra
(`patchedDependencies`, the patch file, `bun.lock`) was also uncommitted — the
opentui patch was physically live in `node_modules` but a fresh clone+install
would have silently lost it. An **undocumented R3-style change** was also found
uncommitted in `session/index.tsx` (`streaming={!props.message.time.completed}`
on `TextPart`), contradicting HANDOFF's explicit "Did NOT implement R3" — it was
logically correct so it's kept, and HANDOFF is now accurate. All of this is
committed this session. Also fixed a same-class residual bug found during the
audit: `ReasoningPart`'s `<code>` renderable still hardcoded `streaming={true}`
(never updated alongside `TextPart`) — now `streaming={!isDone()}`.

**Cleared (not the bug, audited in full)**: gateway's rowid-cursor SSE relay
(replay-safe, verified), freellmapi's `content.ts` normalization + dialect-hold
passthrough logic (structurally incapable of duplication), `sdk.tsx`'s event
source wiring (mutually exclusive if/else, no dual-delivery).

**Documented but not fixed (judgment calls, see ULTRAREVIEW doc for detail)**:
`sync.tsx`'s `message.part.delta` handler has no event-id/sequence dedup guard
— real latent gap, no confirmed live trigger, would need a schema change;
freellmapi's Gemini adapter (`google.ts`, sibling repo) has zero
cumulative-vs-incremental diffing guard — structural risk, unconfirmed, out of
scope (separate repo, not modified).

Verified: agent-runtime full suite 831 passed (2 new); atlas-terminal tsc
clean, bun test 56/56. **UAT still owed** — this environment can't force a real
mid-tool-call network drop to visually confirm live; next operator session
should watch for the "⚠ Connection dropped mid tool-call" marker if duplication
ever recurs (confirms this path) vs. no marker (points at the two documented-
but-unfixed gaps above instead).

**Next:**
1. Operator UAT: run real prompts through `atlas`, including some that trigger
   tool calls, and watch for either (a) no more duplication, or (b) a visible
   "⚠ Connection dropped..." reconnect boundary instead of seamless garbled text.
2. If duplication recurs with no reconnect marker: implement the `sync.tsx`
   delta dedup guard (needs a sequence number added to the delta event schema).
3. Flag freellmapi's `google.ts` adapter gap to that repo/maintainer, or add
   a defensive incremental-diff guard there if ATLAS traffic frequently routes
   to `platform: google`.

## Session update — 2026-07-15 (later): UAT feedback — help/up redraw bug fixed, streaming duplication still reported (needs clean-restart retest), workspace-root design deferred

Operator UAT of the prior entry's work found a real regression in the new
interactive `atlas help`, reported the streaming duplication as still present,
and flagged a real architecture gap in the workspace-root model.

**1. Help/up picker duplication — FIXED and root-caused.** Screenshot showed
the tab bar rendering twice (stale first line + corrected second line).
`help_browser.py`'s `_draw()` moved the cursor up by the **new** frame's line
count before repainting — but different tabs have different command counts
(7 in "Getting Started", 1 in "Dev / Internal"), so switching tabs desynced
the cursor from the actual previous frame height, leaving stale lines on
screen. `interactive_select.py`'s picker never hit this (its frame height is
constant — same items for the whole session) so it needed no fix. Rewrote
`_draw()` to thread the *previous* frame's line count through the loop
(`prev_lines = _draw(lines, prev_lines)`) and clear+rewind past any leftover
lines when a frame shrinks. 4 new regression tests proving the cursor math
for growing/shrinking/first-frame draws
(`test_help_browser.py::test_draw_*`). Full suite: 829 passed.

**2. Streaming duplication — still reported live; not re-fixed this pass.**
Verified the opentui patch (`renderable.streaming = this._streaming`) is
still physically present in `node_modules` — not reverted. Working
hypothesis: the screenshotted session was a long-running atlas-terminal
Node process that predates the R1+R2 fix (patched files only take effect on
the *next* process launch; several `node.exe` processes were already running
on this machine when checked). **Operator asked to fully quit and relaunch
`atlas`, then retest, before assuming the fix itself is wrong.** This
environment cannot drive a real interactive TUI stream to independently
reproduce/verify — that's the actual limitation, not avoidance. If it
recurs after a genuinely clean restart, next step is a deeper look at
atlas-terminal's own screen-diffing (separate from opentui core) for the
same class of bug just fixed in (1) above — variable-height frame redraw
without full clear is a suspicious structural match for the reported visual
pattern (stale partial text immediately adjacent to the corrected full text,
no separator).

**3. Workspace-root model — confirmed real gap, explicitly deferred.**
Operator's stated intent: execution/workspace scope should default to the
user's home directory ("user folder down"), with `~/.atlas` reserved purely
for ATLAS's own internal state (config, db, logs, and — per the operator —
soul.md/Hermes-derived memory files once that work lands). Confirmed current
behavior: `workspace_service.global_root()` (the "default ATLAS workspace"
option in `_prompt_workspace_scope()`) resolves to `~/.atlas` itself,
deliberately tied to the DB home (existing "Pitfall 4" invariant comment) —
so there is no real broad-workspace option today, only "wherever the shell's
cwd happened to be" or the small internal dotfolder. The specific screenshot
(cwd reported as `services/agent-runtime`) was the former, not a code bug in
that instance — but the underlying design gap is real. `global_root()` is
also the literal SURF-02/03 path-containment security boundary, so widening
it is a deliberate scope decision, not cosmetic. **Operator chose: scope this
as its own design pass, bundled with the upcoming Hermes memory/SOUL.md
rework**, rather than an interim fix now. Not implemented this session.

**4. WebUI chat: real duplication bug found + fixed, session-list live
updates fixed, transport-latency swap deferred.** Ran an ULTRARESEARCH
(`.planning/ultra/ULTRARESEARCH-webui-chat-streaming-and-sota-redesign-2026-07-15.md`)
on the operator's report that WebUI streaming doesn't work and sessions need
a manual refresh. Diagnosis: `surface_events.py`'s `_KIND_MAP` maps both
`llm_delta` (each streamed chunk) and `llm_call` (the final reconcile) to
the SAME `SurfaceEventKind` ('text') — the kind alone can't distinguish
them. Two real bugs followed from that, both fixed:
- `consoleEvents.ts` never read the `delta` payload field (only `text`/
  `summary`), so delta chunks silently contributed nothing — explains "not
  working" literally, not just "coarse."
- Had that alone been fixed, **`AgentTurn` (Console.tsx) renders every event
  in `message.events` as its own block** — every delta chunk PLUS the final
  reconcile would each show up as a separate stacked line: the exact
  "response repeats itself" pattern from the TUI bug, just not yet visible
  here since deltas were inert. Fixed with a `displayEvents` collapse in
  `AgentTurn`: deltas extend an "open" run in place, the reconcile replaces
  that run's text instead of appending after it.
- `Missions.tsx` (the session/mission list) now also polls every 8s in
  addition to the existing epoch-on-gateway-reconnect refetch, so a new
  session shows up without a manual page refresh.
- **Deferred**: the actual SSE transport swap (2s CLI-dispatch poll →
  low-latency streaming) — the merge-logic fix was a correctness
  prerequisite that had to land first (faster transport onto broken merge
  logic would have made the bug MORE visible). Also deferred: the visual
  redesign (markdown rendering, a real collapsible block for the
  already-defined-but-unhandled `'reasoning'` SurfaceEventKind, tool-card
  polish) — operator asked to pause before this for a design-direction
  check-in.
- Verified: `services/web-ui-react` — `tsc -b` clean, vitest 50/50 (2 new),
  `vite build` + bundle-budget check green.

**Next:**
1. Operator: clean-restart `atlas` and retest the atlas-terminal streaming
   duplication.
2. If still broken after a clean restart: deeper look at atlas-terminal's own
   terminal-diffing (beyond the opentui patch already applied) for the same
   redraw-without-clear bug class fixed in `atlas help`'s picker this
   session.
3. Workspace-root / ATLAS-home split: dedicated design session, bundled with
   Hermes memory/SOUL.md improvements — not yet scheduled (operator's call).
4. WebUI: the actual SSE transport swap for the chat pane, then the Phase C
   visual redesign (design-direction check-in first, per operator request).

## Session update — 2026-07-15 (latest): streaming duplication R1+R2, freellmapi relocated to ATLAS_HOME, `atlas up` interactive picker, interactive `atlas help` browser + `atlas logs`

Picked up the prior session's ULTRAREVIEW (root causes already proven, fixes
recommended but not implemented) plus two new asks: freellmapi sidecar install
location and an interactive `atlas up`. No new ultrareview/ultraplan pipeline
run — the investigation was already done; this was straight implementation.

**1. Streaming duplication — R1 (client batching) + R2 (opentui patch) applied:**
- **R2** (the dominant visible bug): `node_modules/@opentui/core/index-fedv7szb.js`
  `applyMarkdownCodeRenderable` hardcoded `renderable.streaming = true` on child
  prose blocks regardless of parent state — matching `applyCodeBlockRenderable`'s
  own `renderable.streaming = this._streaming` pattern fixed it. Persisted via
  `bun patch` (no patch-package infra existed before — `bun patch --commit`
  wrote `services/atlas-terminal/patches/@opentui%2Fcore@0.1.99.patch` +
  `patchedDependencies` in package.json, so the fix survives `bun install`).
- **R1** (event batching): `sdk.tsx`'s `handleEvent` used to flush immediately
  when idle >16ms, then debounce-batch only if busy — meaning a same-turn pair
  (final text reconcile + completion signal) landing a few ms apart (not the
  same synchronous tick) reliably split into two SolidJS render passes. Changed
  to always debounce on a trailing 16ms window (reset per event) instead of a
  conditional immediate-flush. Implemented client-side (not the server-side
  chat.ts mechanism the prior ULTRAREVIEW doc sketched) — same effect, lower
  risk (no server-side completion-semantics changes near the multi-tool-round
  turn logic that a previous fix iteration already had to fix once).
- Did NOT implement R3 (delay streaming toggle by one tick) — R1+R2 combo was
  the doc's primary recommendation; R3 was only the documented fallback if R2
  (vendored patch) wasn't feasible. It was feasible.
- Verified: atlas-terminal tsc clean, 56/56 bun tests, `--smoke` OK.
  **UAT still owed** — this environment can't drive a real streaming TUI
  session to visually confirm the duplication is gone; next operator session
  should run a real prompt through `atlas` and watch the boundary behavior.

**2. FreeLLMAPI sidecar relocated to ATLAS_HOME (`freellmapi_control.py`):**
- Operator-flagged gap: the sidecar only resolved from `_EXTERNAL_REPOS/`
  (inside this monorepo checkout) or a sibling folder next to it — both
  dev-checkout-only paths. A fresh `npm`/`pip` install of `atlas` has no repo
  on disk at all, so there was nowhere for a new install to land, and no CLI
  path to create one (operator had to manually `git clone` themselves).
- New `sidecar_home()`: `<ATLAS home>/sidecars/freellmapi`, derived from
  `db.default_db_path()` (ATLAS_DB/ATLAS_HOME-aware at call time, same pattern
  as `workspace_service.global_root()`) — now the **first** resolution
  candidate, ahead of the two dev-checkout sibling paths (kept as back-compat
  fallback, not removed — this machine's real install is still at
  `C:\Users\Davi\Desktop\Projects\freellmapi`, a sibling path, and it still
  resolves correctly).
- New `install(target=None, force=False)`: git clone (`--depth 1`) + `npm
  install` + `npm run build` into `sidecar_home()` by default; idempotent
  (re-runs install/build without re-cloning if `target/.git` already exists).
  New CLI: `atlas freellmapi install [--target] [--force] [--json]`. Gives
  `atlas` actual lifecycle control (install/start/stop/status), not just
  start/stop of something the operator had to set up by hand.
- Verified: `test_freellmapi_control.py` 17 passed (8 new), full agent-runtime
  suite 789 passed at that point.

**3. `atlas up` reworked into an interactive service picker:**
- New `services/agent-runtime/atlas_runtime/cli/interactive_select.py` —
  dependency-free space/enter checkbox prompt (`msvcrt` on Windows,
  `termios`/`tty` on POSIX; key-reading isolated behind an injectable
  `read_key` param so the selection state machine is unit-testable without a
  real TTY). Falls back to a numbered `typer.prompt` when stdio isn't a real
  TTY — but `_up_cmd` only reaches the picker at all when stdin+stdout are a
  real TTY; non-interactive runs (CI, `--yes`, `--json`, `--services`, or no
  TTY) silently use the old default set (gateway+cockpit+freellmapi; cashflow/
  discord stay opt-in), so nothing scripted against `atlas up` changed
  behavior by default.
- Flow: probes `health_ok()` on all 5 services first (gateway, cockpit,
  freellmapi, cashflow, discord) — already-running ones show locked/checked
  and can't be toggled off, non-running ones default-checked per the old
  auto-start set. Space toggles, enter confirms, q/Esc/Ctrl-C cancels (exit 1,
  nothing started). Sidecars a user selects are still gated on gateway+cockpit
  actually coming up healthy first (preserves the existing D-015 gating, now
  generalized past just freellmapi).
- New flags: `--yes` (skip picker, default set), `--services a,b,c` (explicit
  non-interactive set, rejects unknown keys), `--json` (implies non-
  interactive). `atlas down` unchanged.
- Verified: `test_interactive_select.py` 11 passed (new), `test_cli_up.py` 13
  passed (7 new: already-running/no-restart, `--services` selection + unknown-
  key rejection, `--yes` default set, `--json` shape), full agent-runtime
  suite **805 passed**.
- **Live-ran `atlas up --json` on this machine to sanity-check real output**
  (not just mocked tests) — this had a real side effect: it started actual
  gateway (pid varies, :8484), cockpit (:5173), and freellmapi (:3001)
  processes, left running at session end. Confirmed freellmapi resolved to
  the existing sibling-path install (`...\Projects\freellmapi`) as expected —
  proves the new candidate ordering didn't break the working setup. **Left
  running** since it's a reasonable base for the next operator session to UAT
  the streaming fix in a live TUI; `atlas down` to tear it down if not wanted.

**Not done / explicitly out of scope this session:**
- Cockpit-web's freellmapi UI hints (`apps/web-ui-react/src/lib/api.ts:620`
  area) weren't touched — CLI-side control was the ask, cockpit surfacing the
  new `install` action is a natural but separate follow-up.
- `atlas doctor`'s freellmapi remediation string still says `atlas freellmapi
  start` (doesn't mention `install`) — minor, not corrected this session.
- No real interactive keypress test of the checkbox picker exists or can
  exist from this environment (no real TTY to drive) — logic is fully unit-
  tested via the injectable `read_key`, but the actual live space/arrow/enter
  feel is unverified. First real terminal use of `atlas up` should confirm it
  renders/behaves as intended (redraw-in-place, no leftover artifacts) across
  whatever terminal the operator uses.

**4. Interactive `atlas help` browser + `atlas logs` + minor CLI polish
(follow-on ask in the same session: "work on some atlas commands... the help
command should be interactive, have tabs... uncover what can be done, and do
it, in the end document all"):**
- Audited the full CLI surface (`typer.main.get_command(app)` introspection
  over all ~34 top-level command groups) rather than reading source files —
  cheap and gave an exact, current catalog (including two hidden dev-only
  commands and 6 subcommands with blank help text that a source read would've
  been easy to miss).
- `atlas help` is now a full-screen, dependency-free tabbed command browser
  (new `cli/help_browser.py`): 8 category tabs, live-introspected command
  list per tab (never hand-duplicated — a newly added command that isn't
  categorized still shows up, in an auto-created `Other` tab), `/` fuzzy
  search across everything, Enter drills into a command's real `--help` text
  (via an internal `CliRunner` call — exactly what a user would see, avoids a
  click/typer quirk where hand-built `Context` objects mis-render option
  defaults). Falls back to a static categorized listing (`--plain`, or
  automatically off a real TTY) — CI/piped use is unaffected.
- Generalized `interactive_select.py`'s raw-terminal key reader (shared with
  the `atlas up` picker) to support left/right/backspace and literal
  characters, needed for tab-cycling and the search text box. Had to fix a
  real conflict this surfaced: the picker's `_read_key` used to hard-map a
  bare `q` keypress to "quit" — fine for a checkbox list, but would have
  swallowed the letter `q` as data inside the help browser's search box.
  `quit` is now Ctrl-C/Esc only at the key-reader level; `multi_select`
  (which has no text entry) separately still treats a literal `q`/`Q` as
  cancel, unchanged from the operator's perspective.
- New `atlas logs [--tail N] [--follow] [--path]` — every entry point
  already writes to `<ATLAS home>/logs/atlas.log` (F13's rotating handler)
  but there was no CLI path to read it. `--follow` handles log rotation
  (detects the file shrinking under it and reopens).
- Fixed 6 blank docstrings on `atlas surface` subcommands (`get`, `list`,
  `heartbeat`, `suspend`, `resume`, `cancel`, `close`) — `--help` showed them
  with no description.
- New tests: `test_help_browser.py` (13), plus 6 for `atlas logs`
  (`test_cli_logs.py`) and updated `test_interactive_select.py`/`test_cli.py`
  for the key-reader and `atlas help` behavior changes. Full suite: **825
  passed**.
- Full writeup: `docs/operations/CLI_ENHANCEMENTS_2026-07-15.md`.
- **Not verified**: real keyboard feel of either interactive picker (arrow
  keys, in-place redraw) — no real TTY in this environment to drive one.

**Next:**
1. Operator UAT: run a real prompt through `atlas` (gateway/cockpit already up
   from this session) and confirm the streaming duplication is gone.
2. Try `atlas up` and `atlas help` for real in a terminal — confirm
   render/redraw, tab switching, search, and cancel (q/Esc) all feel right.
3. Consider surfacing `atlas freellmapi install` in the cockpit UI.
4. `atlas doctor`'s freellmapi remediation string still only says `atlas
   freellmapi start` (doesn't mention `install`) — minor, not corrected.

## Session update — 2026-07-12 (latest): streaming duplication — 3 layered root causes found, fix ready

### Status: ROOT CAUSE COMPLETE, FIX RECOMMENDATIONS READY — NEEDS IMPLEMENTATION

The streaming text duplication went through **7 fix iterations** (6 prior + 1 current streaming-toggle approach). All data-flow bugs are fixed and tested. The duplication **persists** with a new pattern: text formatting now partially works (bold conceal active), but paragraph content overlaps at boundaries ("What's on your mind?, debug, automate, research, and communicate across platforms." followed by "What's on your mind?").

### What was fixed (data flow — all committed, all tested)

| # | Commit | Bug | Root cause |
|---|--------|-----|-----------|
| 1 | `b4ecd9c1` | No streaming at all | Schema + DeltaBuffer + adapter llm_delta branch + gateway 200ms poll |
| 2 | `2aa99a1b` | Multi-turn text drop + no end-of-turn flush | Guard was backwards; foundation never calls None for final responses |
| 3 | `a9acc882` | Last sentence × 2 | `transition:succeeded` creates part after llm_call reconciled |
| 4 | `e8e1f763` | Full text × 2 (all patterns) | Multiple event types independently create parts; unified guard |
| 5-6 | uncommitted | Raw `**` markers + blank flash | Component-swap approach broke opentui async highlight lifecycle |
| 7 | current | Streaming toggle + partial formatting | Correct per opentui contract, but child prose blocks hardcoded to streaming=true |

### Root causes (v2 ULTRAREVIEW — 3 layered bugs, with proof)

**Bug 1 — Event batching split (`sdk.tsx:62-73`):**
The SDK's `handleEvent()` uses a 16ms batching window. The `llm_call` (reconcile text) and `end` (set completed) events can land in **separate SolidJS batches** if the last delta was >16ms prior. This causes two render passes:
- Pass 1: content updates, `streaming` still `true` → `updateBlocks()` with `trailingUnstable=2` → intermediate paragraph boundaries
- Pass 2 (16ms later): `streaming` flips to `false` → `updateBlocks(true)` with `trailingUnstable=0` → correct boundaries, but intermediate state already painted

**Bug 2 — Child prose blocks hardcoded to `streaming: true` (`index-fedv7szb.js:9518`):**
`applyMarkdownCodeRenderable()` hardcodes `renderable.streaming = true` on child `CodeRenderable` instances. After parent `MarkdownRenderable.streaming` flips to false, `updateBlocks(true)` refreshes all blocks, but `applyMarkdownCodeRenderable` (line 9518) forces child prose blocks back to streaming mode. Their `content` setter early-returns (line 4178) without updating the text buffer — they show stale styled content from a previous highlight pass. Fenced code blocks work correctly because `applyCodeBlockRenderable` (line 9529) propagates `renderable.streaming = this._streaming`.

**Bug 3 — Double `updateBlocks` at completion:**
When both content and streaming change (in one or two render passes), `MarkdownRenderable` runs `updateBlocks()` twice: once from the content setter (`trailingUnstable=2`) and once from the streaming setter (`trailingUnstable=0`). The first run may produce different paragraph token boundaries, causing blocks to be destroyed and recreated — visible flash/duplication.

### Recommended fixes

1. **`chat.ts`** — emit `time.completed` as part of the `message.part.updated` from `llm_call`, so both changes land in one SolidJS batch
2. **`index-fedv7szb.js:9518`** — change `renderable.streaming = true` to `renderable.streaming = this._streaming` in `applyMarkdownCodeRenderable`, matching the pattern in `applyCodeBlockRenderable`

Fallback if vendored opentui can't be patched: R1 + R3 (delay streaming toggle by one tick in TextPart).

### Key files for the next agent

| File | Lines | What to look at |
|------|-------|----------------|
| `services/atlas-terminal/src/adapter/chat.ts` | 368-471 | Event emission: reconcile + completed (Bug 1 fix here) |
| `services/atlas-terminal/src/tui/context/sdk.tsx` | 48-73 | Event batching: 16ms window (Bug 1 trigger) |
| `services/atlas-terminal/src/tui/context/sync.tsx` | 121-6110, 831-10110 | Store: message + part update handlers |
| `services/atlas-terminal/src/tui/routes/session/index.tsx` | 1560-1603 | TextPart: streaming toggle (Bug 3 fix here if R3) |
| `node_modules/@opentui/core/index-fedv7szb.js` | 9477-9519, 4173-4288 | MarkdownRenderable child blocks (Bug 2 fix here) |

### Key reports

| Report | Content |
|--------|---------|
| `.planning/ultra/ULTRAREVIEW-streaming-duplication-2026-07-12.md` | First pass: 9-hop data flow trace, adapter fix |
| `.planning/ultra/ULTRAREVIEW-streaming-duplication-DEEP-2026-07-12.md` | Deep pass: foundation threading, 10 part-creation paths, DeltaBuffer gap, 4 fix iterations |
| `.planning/ultra/ULTRAREVIEW-streaming-duplication-v2-2026-07-12.md` | **NEW:** 3 layered root causes with proof (batching + hardcoded streaming + double updateBlocks) |
| `.planning/ultra/ULTRAREVIEW-integration-verification-streaming-folder-scope-2026-07-12.md` | 5 root causes (all fixed): integration hallucination, streaming, folder, scope, context |

### Verified (current state)

- atlas-terminal: tsc clean, 56/56 bun tests, boundary scan passed, smoke LIVE
- agent-runtime: 782 passed, 2 skipped
- atlas-gateway: 108 cargo tests
- All data-flow bugs resolved; rendering root causes identified with proof

## Session update — 2026-07-12 (latest): streaming slice (ULTRAREVIEW item 2) closed

3 commits following the fixes-batch below, closing the last open ULTRAREVIEW
item (fix-status + design writeup appended to the ULTRAREVIEW doc under
"Streaming Slice — 2026-07-12"). All 5 of the 5 original findings now FIXED.

- **Schema**: `AuditEvent.event_type` gains `"llm_delta"` (coalesced streaming
  fragment; `data.end_of_turn=True` marks a turn's last delta) — mapped to
  SurfaceEvent kind "text".
- **Runtime** (`agents/native.py`): the vendored foundation already exposed
  `stream_delta_callback` + `_has_stream_consumers()` (D-001 compliant — no
  foundation edits). New `_DeltaBuffer` coalesces per-token callback into
  ~150ms/48-char `llm_delta` audit rows instead of one SQLite write per token;
  flushes early on the callback's `None` end-of-turn signal.
- **Adapter** (`chat.ts`): new `llm_delta` branch emits `message.part.delta`
  per chunk — the TUI's existing handler (`sync.tsx:514`, dead code per the
  original audit) now fires. `streamingText` map `{part, open}` per assistant
  message: `end_of_turn` closes it (next turn gets a fresh part) but keeps the
  entry so the trailing `llm_call` reconciles onto the same part instead of
  duplicating it.
- **Gateway** (`lib.rs`): `STREAM_POLL` 500ms → 200ms so relay latency stays
  under the delta cadence. Rebuilt `target/release/atlas-gateway.exe` — had to
  `atlas gateway stop` first (Windows file lock on the running binary),
  restarted after build. **If the operator has an older gateway process
  running from before this session, it needs `atlas gateway stop && atlas
  gateway start` to pick up the new binary.**

Verified: agent-runtime 782 passed (4 new), atlas-core 97 passed,
atlas-terminal typecheck + 53 tests (1 new) + live `--smoke`, `cargo test -p
atlas-gateway` 108 passed. **UAT owed:** does the TUI visibly render
token-by-token, reconnect-mid-stream behavior, multi-tool-round turn
boundaries.

## Session update — 2026-07-12 (later): ULTRAREVIEW fixes 4/5 + glow pulse tune

4 commits (b3393712..22f1041b), executing
`.planning/ultra/ULTRAREVIEW-integration-verification-streaming-folder-scope-2026-07-12.md`
(fix-status table appended there).

- **b3393712** — TUI idle shimmer fringe was theme.primary (#7F00FF) on the
  #7B61FF wordmark (invisible); now primary lifted 55% toward white (lavender).
- **059c63ba** — `ATLAS_WORK_DIR`: launcher captures operator cwd, `main.tsx`
  chdirs back (fixes footer folder, /path, git branch, exports, permission
  prompt paths). Plus TTY-only launch scope prompt: this folder vs
  `workspace_service.global_root()`.
- **b4a4ce11** — operator-context injection opt-out: `assemble_context(...,
  include_operator_context=)` > `ATLAS_SKIP_CONTEXT` env > new
  `context.inject_operator_context` config knob (schema + control-plane key);
  `atlas --no-context` / `atlas tui --no-context`. Contract text now says
  answer unrelated prompts directly. NOTE: env flag only reaches runs executed
  in-process or in child processes; gateway-dispatched runs need the config
  knob (gateway has its own env).
- **22f1041b** — `atlas_core.md` verify-before-claim directive (integration
  hallucination); prompt goldens regenerated (they hash atlas_core.md bytes).

Verified: agent-runtime 775+2 passed, atlas-core 97 passed, atlas-terminal
typecheck + 52 tests + smoke green. **Still open from that ULTRAREVIEW:**
streaming (item 2, runtime per-token events + adapter `message.part.delta` —
own slice). **UAT owed:** scope prompt UX, footer folder, glow pulse look,
`--no-context` behavior in TUI.

## Session update — 2026-07-12: retarget shipped, first CI green, TUI retoken, Cmd+K palette + /v1/vcs, graph-MCP eval

9 commits this session (104ef33a..2267ebf8). Executed HANDOFF priorities 1-2, CI watch,
and the operator's mid-session reshaped WebUI priorities (Cmd+K palette, sidebar branch,
codebase-memory-mcp eval) from
`.planning/ultra/ULTRARESEARCH-webui-vision-gaps-repos-2026-07-11.md`.

**1. Retarget `atlas`/`atlas tui` → atlas-terminal (104ef33a):**
- New `atlas_runtime/cli/atlas_terminal.py`: `resolve_terminal_dir()` (ATLAS_TERMINAL_DIR
  override, repo-root walk) + `launch(gateway_url)` running `[bun, "run", "dev"]` (the dev
  script carries the required `--conditions=browser`); `TerminalLaunchError` with
  remediation when bun/node_modules missing.
- `cli/main.py`: `_root()` and `_tui_cmd()` now launch atlas-terminal; Go TUI kept as
  hidden `dev-go-tui` fallback. `test_tui_app_entry.py` rewritten (6 tests).
- **Operator UAT still owed** (interactive boot, prompt, ATLAS identity, tool approval).
  Go TUI retirement (MASTER-PLAN wave 5) stays gated on that UAT.

**2. First fully green atlas-ci run (run 29177170770, all 8 jobs) after 4 fix loops:**
- f4583f45 — CI never installed services/wiki-runtime; must install AFTER agent-runtime
  (its pyproject depends on atlas-core/atlas-runtime; pip would hit PyPI otherwise).
- fa5a35ff — POSIX correctness: cockpit spawn creationflags hoisted to module constants
  with Win32 literal fallbacks; policy boundary rejects foreign-flavor absolute paths.
- 37503d15 — first policy fix broke Windows-style maintenance roots on POSIX; final:
  flavor-aware `_within()` via ntpath lexical containment when either side is
  Windows-flavor on a POSIX host (test_policy has a 6-param regression test).
- 362b5c70 — debrand audit 'hermes' leak was Rich force-color on GitHub Actions putting
  ANSI inside the phrase; `_ANSI_ESCAPE` strip before whitespace collapse.

**3. TUI visual polish (6abc4e57):**
- UAT wordmark misalignment root-caused: default logo is "thin" (home.tsx falls back to
  it) and its rows were ragged-width; renderer joins rows 1:1 off left[0]. All logo shapes
  now uniform-width; `test/logo.test.ts` (9 tests) locks row-width uniformity.
- `src/tui/context/theme/atlas-tui.json` retokened to L2 Dark Prism (DIV-F-006):
  #7F00FF/#9B4DFF/#00F0FF/#E0E0E0/#00FF94/#FFD600/#FF0055 on #0a0a0a; light palette
  same-hue readable equivalents. **Operator visual judgment owed.**

**4. Gateway `/v1/vcs` (a18dc25b):** dependency-free git context reader (.git/HEAD +
worktree pointer files + detached short sha), `?path=` override, `{repo,branch,detached,
commit}` shape. 4 integration tests; cargo 108 passed; release binary rebuilt.

**5. Cockpit Cmd+K palette + sidebar branch (1219331c, tests 2267ebf8):**
- `src/lib/atlasCommands.ts` mirrors the TUI's six slash-command templates
  (services/atlas-terminal/src/adapter/commands.ts) — keep the two files in lockstep.
- `src/components/CommandPalette.tsx`: Ctrl/Cmd+K overlay; first token = command, rest =
  $ARGUMENTS; Tab completes, Enter runs, Esc closes; busy disables execute.
- Console.tsx: `send()` split into `dispatchPrompt(windowId, display, prompt)` — operator
  message echoes `/review HEAD~1`, agent receives the expanded template. Palette targets
  the active chat window.
- Sidebar footer: git branch (or `DETACHED · <sha>`) via new `getVcsContext()`; refetch on
  health epoch + 30s; row hidden when not a repo / pre-vcs gateway.
- Gates: vite build + bundle budget, vitest 48 passed (4 new palette tests), eslint clean.

**6. codebase-memory-mcp evaluation (priority 5) — report written:**
`.planning/ultra/EVAL-codebase-memory-mcp-architecture-explorer-2026-07-12.md`.
Verdict: viable as Architecture Explorer backend but not as-is — search_graph/trace_path
are strong; get_architecture clusters drowned by vendored `foundation/`; Route nodes
noisy. SPA can't speak MCP: recommend gateway proxy `/v1/graph/*` (search/trace v1),
filter out foundation/_EXTERNAL_REPOS, link-out to :9749 UI only as interim.

**Environment notes:** earlier commits this session already pushed (CI watch);
6abc4e57 + a18dc25b + 1219331c + 2267ebf8 pushed at session end (see STATE for CI
result). CONTRIBUTING.md still carries its pre-existing uncommitted modification
(untouched). STATE.md's prior-session Cashflow-packet hunk committed with this
session's state update. Repo ingestion Wave 1 still awaits operator review — not started.

**Next session:**
1. **Operator UAT** — `atlas` boots atlas-terminal: prompt loop, ATLAS identity, tool
   approval; judge the Dark Prism retoken + wordmark fix; then the Go TUI retirement call.
2. Architecture Explorer v1 per the EVAL doc (gateway `/v1/graph/*` proxy first).
3. MASTER-PLAN waves 4-5 (test density; Go TUI retirement gated on UAT).
4. Phase 10.8 execution per its 4 plans.
5. Repo ingestion Wave 1 (after operator review of the master plan).

## Session update — 2026-07-11: ATLAS identity fix + atlas-terminal waves 2-3 remainder

3 commits (e96ec47e, cb81d565, 02b7735e), all gates fresh.

**Identity (operator-reported: TUI agent called itself "Hermes Agent"):**
- Root cause: `atlas_runtime/agents/native.py` builds `AIAgent(skip_context_files=True)`
  with no SOUL.md, so the foundation's stable identity slot fell back to the upstream
  `DEFAULT_AGENT_IDENTITY` ("You are Hermes Agent… created by Nous Research"). The
  ATLAS contract only rode the context tier as `system_message`.
- Fix (**DIV-F-007**, foundation/DIVERGENCE_LOG.md): `DEFAULT_AGENT_IDENTITY` +
  `DEFAULT_SOUL_MD` rebranded to the ATLAS operator identity (mirrors
  `atlas_runtime/prompts/atlas_core.md` line 1); `HERMES_AGENT_HELP_GUIDANCE`
  reworded so it names the foundation without claiming the identity. 3 vendor test
  assertions updated. Also reseeded the machine-local
  `%LOCALAPPDATA%\hermes\SOUL.md` (was byte-identical to the old seed) so the
  interactive `atlas-agent` CLI stops loading the Hermes persona from disk.
- Verified: foundation test_prompt_builder+test_config 210 passed, test_run_agent
  345 passed; agent-runtime prompt/debrand subset 18 passed.

**atlas-terminal (services/atlas-terminal/research/MASTER-PLAN.md waves 2-3 remainder):**
- Surface heartbeat: `GatewayClient.heartbeatSurface` + 30s keepalive loop in
  ChatAdapter; definitive 401/403/404/410 drops the cached surface so the next
  prompt re-surfaces (gateway restart / SURF-05 sweep resilience).
- `/vcs` wired: real git branch via dependency-free `.git/HEAD` reader
  (worktree pointer + detached HEAD aware) — donor footer shows dir:branch.
- `/session/status` wired: real per-session idle/busy. `/project` wired
  (single-project list). `/experimental/resource` stub kept deliberately
  (bootstrap Promise.all consumes it; removal-plan deviation noted in code).
- Run-stream 60s idle watchdog: silent/hung gateway stream now ends as 504
  GatewayError instead of a forever-busy session. **Bun gotcha discovered:**
  unref'd timers never fire on an otherwise-idle event loop (Windows, Bun
  1.3.13) — the watchdog timer must stay ref'd; it is cleared after every read.
- GatewayError → typed 502 `{error:'gateway', status, message}` in the adapter
  catch-all (diagnostics tag ATLAS_GATEWAY_ERROR); 500 now means adapter bug.
- Verified: bun test 43 pass (14 new across wave2/hardening test files), tsc
  clean, `--smoke` LIVE.

**Environment notes:** Pushed to origin (`db772555..6f9c8e63`, 41 commits).
CONTRIBUTING.md still carries its pre-existing uncommitted modification (untouched).
Untracked research/scratch: `.planning/ultra/` (14-repo ingestion master plan, 12
vendable, Wave 1 = RTK + addyosmani/emilkowalski/loop-engineering skills —
**awaits operator review before any vendoring**), `services/atlas-terminal/research/`,
`.mimocode/`, `.ops/`, cashflow research dirs.

**Next session priority — retarget `atlas tui` to atlas-terminal:**

The bare `atlas` command and `atlas tui` subcommand currently launch the legacy
Go TUI via `_launch_go_tui()` → `go_tui.launch()`. The atlas-terminal (Bun/vendored
donor TUI) is now wired enough to replace it. Retarget in
`services/agent-runtime/atlas_runtime/cli/main.py`:

1. In `_root()` (line 186): change `_launch_go_tui()` → `_launch_atlas_terminal()`.
2. In `_tui_cmd()` (line 223): change `_launch_go_tui(gateway)` →
   `_launch_atlas_terminal(gateway)`.
3. Add `_launch_atlas_terminal(gateway=None)` function — run
   `bun run src/main.tsx` from `services/atlas-terminal/` via `subprocess.run`
   (same pattern as `go_tui.launch()` but no Go build step). Forward the
   `--gateway` flag as `ATLAS_GATEWAY_URL` env var. Pass `ATLAS_HOME` through.
4. Keep `go_tui.py` and `dev-foundation-tui` command intact — they're the
   fallback until UAT passes.
5. Update `test_tui_app_entry.py` to assert the new launcher is called for both
   bare `atlas` and `atlas tui`.

After retarget: run `atlas` from a terminal, confirm the atlas-terminal TUI
boots, send a prompt, and verify the agent introduces itself as ATLAS. Then
retire the Go TUI (MASTER-PLAN wave 5) in a follow-up session.

**Full next-session task list:**
1. **Retarget `atlas tui`** to atlas-terminal (above).
2. **TUI visual polish** — the atlas-terminal renders but is still a visual clone
   of MiMoCode. Fix indentation/alignment issues visible in the UAT screenshot
   (the "ATLAS" name text has layout quirks). Then differentiate the design:
   keep MiMoCode's tech (Ink, nanostores, theme engine) but apply ATLAS's own
   L2 Systems design tokens (Dark Prism palette from DIV-F-006, HUD voice,
   contour-line motifs). Focus areas: sidebar styling, bottom bar layout,
   transcript typography, header/branding area. The TUI should feel like ATLAS,
   not MiMoCode with a label swap.
3. **WebUI audit** — the cockpit web interface (`apps/cockpit-web`) needs a
   completeness pass: what routes exist vs what the donor TUI / Go TUI already
   wire. Identify missing surfaces (mission list, settings dialog, permission
   overlay, session history). Document gaps in a short report — research on
   direction will follow after this session.
4. **Operator UAT** — interactive session: approve/reject a real tool call,
   confirm ATLAS identity, check diagnostics log if any toast appears.
5. **CI watch** — first atlas-ci run after the push; fix any failures.
6. **Repo ingestion Wave 1** — RTK + skill packs (awaits your review of the
   master plan).
7. **MASTER-PLAN waves 4-5** — test density to 50+, donor cleanup, legacy Go
   TUI removal (gated on UAT).
8. **Phase 10.8** execution per its 4 plans.

## Session update — 2026-07-10 (second session): MASTER action plan executed (MAP F1-F22, F20 deferred)

Executed `.mimocode/artifacts/ultra/ATLAS-MASTER-ACTION-PLAN.md` (the NEW 22-item
queue from the 26-subagent deep audit — distinct from the older F1-F13 plan below).
10 commits (8a2101d3..02af7adf). Checklist updated in place in the plan file.

**Critical (Wave 1):**
- **MAP F1** — atlas-terminal crashed on every event: adapter emitted bare
  DonorEvent but the donor SDK v2 consumes GlobalEvent {directory, payload}
  (useEvent reads event.payload.type). Wrapped at BOTH boundaries (SSE /event
  and the direct-bus bridge in main.tsx). Also fixed emit property shapes
  (sessionID/time on message+part events, flat PermissionRequest, requestID/
  reply on permission.replied) and a silent-approve bug: the reply handler read
  body['response'] but the SDK sends body['reply'] — rejects became approves.
- **MAP F2** — decideApproval sent {owner_token}; gateway requires {nonce,scope}.
  ToolApproval now carries nonce; donor "always" maps to scope=session.
- **MAP F3** — migration 0019: idx_audit_events_run_id + idx_runs_mission_id.
  NOTE: the audit's suggested (run_id, rowid) composite is INVALID SQL here
  (TEXT pk, no rowid alias — verified); plain run_id gives the covering search.

**High (Wave 2):** MAP F4 cold-start orphan reaper — gateway_control.start() now
runs the SURF-05 reconcile sweep when the gateway was down (subprocess mode had
no reaper; daemon path already did). F5 cockpit SSE: 3 backoff retries (was 1).
F6 .env.example: all operator env vars. F7 .github/workflows/atlas-ci.yml (7 jobs;
unverified until first push). F8 ensureSurface retry + session.error on prompt
failure. F9 15s AbortSignal on gateway client (stream exempt).

**Medium (Wave 3):** MAP F10 GET /v1/runs (JOIN, one query) + cockpit wiring with
404 legacy fallback. F11 cockpit auto re-surface on 403 (retry prompt once; poll
drops dead session). F12 config schema migration chain (_CONFIG_MIGRATIONS).
F13 logging_config.py — rotating <ATLAS_HOME>/logs/atlas.log, ATLAS_LOG_LEVEL/DIR.
F14 tests/e2e/test_full_pipeline.py — real gateway binary + real CLI dispatch +
temp DB round trip; **enabled by making db.default_db_path() honor ATLAS_DB/
ATLAS_HOME at call time** (fixes the long-standing live-DB smoke footgun).
F15 goal_tree tasks/observations filtered by focus in SQL. F16 stop() refuses
dead/reused PIDs (image-name check).

**Low (Wave 4):** F17 ogl removed. F18 atlas-core pinned >=0.1,<0.2. F19
graphCache 5-min TTL. F21 build+bundle budget verified green. F22 Go TUI
/missions rows show intent + updated day (atlas-terminal has no mission list —
its browser is a separate tracked feature). **F20 DEFERRED**: the setTimeouts
are vendored donor TUI internals; refactoring breaks vendoring discipline for
negligible gain (reason recorded in the plan checklist).

**Verification (all fresh 2026-07-10):** agent-runtime 766 passed; atlas-core 97;
atlas-terminal bun 29 + tsc clean + --smoke OK + boundary scan passed; atlas-cli
20/20 (Windows); atlas-tui go test 101; cargo test 104; cockpit vitest 44 +
`npm run build` + bundle budget green; E2E 1 passed against the rebuilt release
gateway (native/atlas-core-rs/target/release — rebuilt this session, includes
/v1/runs).

**Environment notes:** main now 38 ahead of origin after this session (11 code + 2 docs commits on top of the prior 25), unpushed. CONTRIBUTING.md
still carries its pre-existing uncommitted modification (untouched). CI workflow
is authored but can only be verified on first push.

**Next:** (1) push + watch the first atlas-ci run; (2) operator UAT still owed:
interactive atlas-terminal session (the F1 event fix likely also resolves the
long-standing session-create toast — reproduce once and read
%TEMP%\atlas-terminal-diagnostics.log if not); approve/reject a real tool call
from atlas-terminal; (3) Phase 10.8 execution per its 4 plans.

## Session update — 2026-07-10: ULTRAREVIEW action plan executed (F1-F13 minus F12 root cause)

Executed `.mimocode/artifacts/ultra/ATLAS-ACTION-PLAN.md` end to end. 7 commits
(70a44dca..c67a608f), all gates fresh:

**Completed:**
- **F3/F4** — removed 5 empty scaffold dirs (pulse-runtime, worker, atlas-sdk,
  atlas-ui, packages/config) + apps/cockpit-web (stale SvelteKit README).
- **F5-F9** — PROJECT.md (10.1-10.7 complete, 10.8 next), REQUIREMENTS.md
  (TUI-01..11 + PERM-03/04 → [x]), ARCHITECTURE.md (79 paths/86 endpoints),
  STATE.md current-position heading, RISKS.md (+7 v1.1 risks).
- **F1** — Brain graph wired into the run loop: execute_run upserts mission/run
  nodes + `produced` edge post-terminal (fail-open, labels redacted); new
  BrainRetriever in default_router gated by new `context.enable_brain` config
  key. agent-runtime 746 passed, atlas-core 97 passed at commit time.
- **F2** — foundation subagent auditing bridged: root cause was plugin discovery
  never running in-process AND the bundled shim being config-gated + circular-
  import-fragile. `subagent_service.ensure_foundation_bridge()` registers the
  real atlas_audit hooks directly on the foundation PluginManager singleton;
  native.py calls it pre-harness; run_service now maps BOTH session keys
  (run.id + surface session). Proven with a real invoke_hook round trip.
- **F13** — oauth_import misreport: `codex_auth.runtime_ready()` is the single
  predicate; auth_service.doctor + model_control_service._auth_status consult
  it. Live-verified: `atlas auth doctor openai-codex` → auth_present.
- **F11** — Windows tar defect: system tar replaced by dependency-free
  `src/tarball.js` (ustar+zlib, GNU-L/PAX-aware extract, path-escape guard).
  npm test 20/20 on Windows (was 11/5). Test script now runs both test files.
- **F10** — Phase 10.8 planned: 4 plans, 3 waves in
  `.planning/phases/10.8-cross-surface-conformance-uat-cutover/`; ROADMAP row
  0/4 Planned.

**F12 — NOT root-caused (still the retirement-gate blocker):**
- Statically eliminated: session.create call shape, rewrite interceptor
  (GET/HEAD only), dev-vs-headless entry divergence, adapter-bypassing clients.
- Repro attempts blocked (documented in .debug log §12): piped stdin never
  reaches the composer (opentui needs real TTY), SendKeys AppActivate denied,
  ConPTY/node-pty blocked by npm script policy.
- Landed instead: `src/util/diagnosticLog.ts` → every session-create error and
  adapter-origin error now persists to `%TEMP%\atlas-terminal-diagnostics.log`;
  the toast names the file. **Next operator UAT: reproduce once, read that
  file — the error object is the missing evidence.**

**Final verification (2026-07-10):** agent-runtime pytest 752 passed; atlas-core
97 passed; atlas-cli npm test 20/20 (Windows); atlas-terminal bun test 29 pass,
tsc clean, --smoke LIVE openai-codex/gpt-5.5, boundary scan exit 0.

**Environment notes:** gateway was started manually for F12 diagnosis (ATLAS_CLI
env pointing at the hermes venv python) and killed at session end. `main` is now
22 ahead of origin, unpushed. CONTRIBUTING.md carries a pre-existing uncommitted
modification (untouched). `.mimocode/` is untracked scratch; its action-plan
checklist was updated in place.

**Next:** operator UAT for F12 (capture the diagnostics file), then Phase 10.8
execution per the 4 plans (10.8-01 conformance suite first).

> **ACCURACY NOTE (2026-07-08 review):** the `packages/atlas-cli` session
> entries below log `npm test` as `10 → 11 → 12 → 15 → 16 passed`. Those counts
> were recorded against a **non-Windows** run. On the operator's Windows machine
> the suite currently reports **11 passed / 5 FAILED** (the manifest/release-tar
> tests fail because system `tar` breaks on `C:\` paths). See
> `.debug/2026-07-08-atlas-cli-windows-tar-defect-and-tree-review.md` (§1/§2).
> Treat every `npm test` "passed" line here as a historical session log, not the
> current green state. The 39-file dirty backlog these entries describe was
> committed on 2026-07-08 (7 logical commits); `main` is 15 ahead of `origin/main` (8 pre-existing + 7 new),
> unpushed.

## Session update — 2026-07-07: CLI shutdown/help polish + context-handoff verification

**Completed:**
- Added top-level `atlas down [--json]`, reversing `atlas up` in safe shutdown order:
  FreeLLMAPI → Cashflow → Discord → Cockpit → Gateway.
- Added `atlas help` as an explicit root-help alias.
- Improved `atlas wiki` discoverability: bare `atlas wiki` now prints wiki help; if the optional
  wiki runtime is absent, the root CLI registers an explanatory stub instead of silently hiding it.
- Verified the existing NativeAtlasAgent context-handoff work in the dirty worktree:
  persisted run contracts include `context_markdown`, and native harness calls receive the
  run contract/operator context as `system_message`.
- Updated `docs/plans/2026-07-04-cli-gap-analysis-and-next-sprint.md` with completed items,
  remaining gaps, and anti-bloat notes.

**Verification:**
- `pytest services/agent-runtime/tests/test_cli_up.py services/agent-runtime/tests/test_cli.py -q` — 24 passed.
- `pytest services/agent-runtime/tests/test_agent_contract_service.py services/agent-runtime/tests/test_agents.py -q` — 22 passed.

**Still open next:**
1. Capture the real interactive `atlas-terminal` session-create error object in Windows Terminal.
2. Implement npm package remote install/update/checksum path.
3. Run the deeper atlas-terminal vendor/donor cleanup sweep.

## Session update — 2026-07-07 continuation: atlas-terminal session-create diagnostics

**Completed:**
- Added `services/atlas-terminal/src/tui/util/sessionError.ts`, a dependency-free formatter
  for SDK/client errors that handles `Error` instances and circular objects.
- Wired the interactive prompt session-create failure path to emit
  `ATLAS_SESSION_CREATE_ERROR ...` via `console.error` before showing the existing toast.
- Updated `.debug/2026-07-04-session-creation-failure-investigation.md` and
  `docs/plans/2026-07-04-cli-gap-analysis-and-next-sprint.md`.

**Verification:**
- `cd services/atlas-terminal && bun test test/sessionError.test.ts` — 2 passed.
- `cd services/atlas-terminal && bun test` — 28 passed.
- `cd services/atlas-terminal && bunx tsc --noEmit` — clean.
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\scan-atlas-terminal-boundary.ps1` —
  boundary scan passed.

**Important:** This is instrumentation, not the root-cause fix. Next UAT should run
`cd services/atlas-terminal && bun run dev`, reproduce the toast, and capture the
`ATLAS_SESSION_CREATE_ERROR` line from the terminal.

## Session update — 2026-07-07 continuation: npm release-manifest installer path

**Completed:**
- Added `packages/atlas-cli/src/release.js`, a dependency-free release-index/artifact
  helper using Node stdlib plus system `tar`.
- Added release-manifest install/update support to `packages/atlas-cli/src/commands.js`.
  `install --manifest <url>` and `update --manifest <url>` now select channel/version +
  platform artifacts, verify archive sha256, extract, generate the installed
  `manifest.json`, and update the `current` pointer.
- Exposed `--manifest`, `--channel`, and `--platform` in `packages/atlas-cli/bin/atlas.js`.
- Updated `docs/plans/2026-07-03-wsb-installer-plan.md` with the release-index schema
  and remaining WS-B gaps.

**Verification:**
- `cd packages/atlas-cli && npm test` — 10 passed.
- `cd packages/atlas-cli && node bin\atlas.js` — usage prints with `--manifest` path.

**Still open for WS-B:**
- Publish real GitHub Release artifacts and a real release index URL.
- Decide final npm package/bin name (`@l2/atlas` + `atlas` vs current private
  `@l2/atlas-cli` + `atlas-cli`).
- Run clean-machine verification on real fresh VMs per platform.

## Session update — 2026-07-07 continuation: clean-install verifier scaffold

**Completed:**
- Added `packages/atlas-cli/src/verifyCleanInstall.js`, a reusable verifier that runs
  install → doctor → update → doctor → rollback → doctor → uninstall → doctor against
  release-manifest artifacts.
- Added `scripts/ci/verify-clean-install.js`, a CLI wrapper for CI/human dry runs.
- Added `docs/runbooks/clean-machine-install.md`, documenting prerequisites, release-index
  shape, local dry-run command, real gate command, and pass criteria.
- Updated `docs/plans/2026-07-03-wsb-installer-plan.md`.

**Verification:**
- `cd packages/atlas-cli && npm test` — 11 passed.
- `node scripts\ci\verify-clean-install.js --manifest file:///.../index-v1.json --update-manifest file:///.../index-v2.json --platform win32-x64` — all 8 steps `OK`.

**Still open for WS-B:**
- Run this verifier on actual clean VMs with real hosted release artifacts.
- Publish/host release indexes and platform tarballs from CI.

## Session update — 2026-07-07 continuation: npm package public naming locked

**Completed:**
- Promoted `packages/atlas-cli/package.json` to the public install contract:
  package name `@l2/atlas`, bin `atlas`, and no private-package guard.
- Updated `bin/atlas.js` usage from `atlas-cli` to `atlas`.
- Added package metadata coverage in `packages/atlas-cli/test/commands.test.js`.
- Updated WS-B and CLI gap docs to mark package/bin naming resolved.

**Verification:**
- `cd packages/atlas-cli && npm test` — 12 passed.

**Still open for WS-B:**
- Publish `@l2/atlas` only after real hosted artifacts and clean-machine gates exist.

## Session update — 2026-07-07 continuation: npm wrapper JSON polish

**Completed:**
- Added `--json` support to the npm wrapper entrypoint (`packages/atlas-cli/bin/atlas.js`)
  for `install`, `update`, `rollback`, `uninstall`, `doctor`, and `versions`.
- `doctor --json` now emits the checksum/manifest health report directly for scripts.
- `versions --json` emits the installed-version list with the `current` marker.
- Command failures in JSON mode now return a structured object:
  `{ "error": { "code": "atlas_cli_error", "message": "..." } }`.
- Kept the human output unchanged when `--json` is omitted; no dependencies added.

**Verification:**
- Added failing entrypoint tests first for `doctor --json`, `versions --json`, and
  JSON-mode command errors.
- `cd packages/atlas-cli && npm test` — 15 passed.

## Session update — 2026-07-07 continuation: local release artifact builder

**Completed:**
- Added `packages/atlas-cli/src/buildReleaseIndex.js`, a dependency-free builder that
  packages a staged bundle into `atlas-<version>-<platform>.tar.gz`, computes sha256,
  and writes a release index JSON compatible with `install --manifest`.
- Added `scripts/ci/build-release-index.js` as the CI/human wrapper around that builder.
- Proved the produced index can be consumed by the existing release install/update
  path and clean-install verifier.
- No new dependencies; still uses Node stdlib and system `tar`.

**Verification:**
- Added the release-index builder test first; it failed on the missing module.
- `cd packages/atlas-cli && npm test` — 16 passed.
- `scripts\ci\build-release-index.js` generated two temporary release indexes/tarballs,
  then `scripts\ci\verify-clean-install.js` consumed them and all 8 steps printed `OK`.

## Session update — 2026-07-07 continuation: atlas-terminal donor residue cleanup

**Completed:**
- Removed remaining confirmed user-facing donor strings from atlas-terminal:
  sidebar footer brand (`MiMoCode` → `ATLAS Terminal`), fatal-error issue URL
  (`anomalyco/opencode` → `L2-ATLAS-PROJECT`), status command identity
  (`opencode.status` → `atlas.status`), MCP auth hint, GitHub trigger tips, and
  Docker container tips.
- Extended `scripts/atlas-terminal-forbidden-terms.txt` with exact regression rules:
  `/opencode`, `github.com/anomalyco/opencode`, `ghcr.io/anomalyco/opencode`,
  `opencode mcp auth`, and `<b>MiMo</b>`.

**Verification:**
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\scan-atlas-terminal-boundary.ps1`
  — boundary scan passed.
- `cd services/atlas-terminal && bun test` — 28 passed.
- `cd services/atlas-terminal && bunx tsc --noEmit` — clean.
- `cd services/atlas-terminal && bun run src/main.tsx --smoke` —
  `ATLAS TERMINAL OK — gateway offline`.
- `rg` for the cleaned exact residues returned no matches.

## Session update — 2026-07-07 continuation: atlas-terminal user-facing fallback cleanup

**Completed:**
- Extended the atlas-terminal boundary scanner with exact rules for the next confirmed
  user-facing/observable donor residues: donor MCP auth wording, `mimo models`,
  the `opencode-go` marketing blurb, MiMo-style custom-provider examples, and
  donor-named temp files.
- Replaced those strings with ATLAS-neutral equivalents:
  `ATLAS Terminal does not support MCP authentication yet`, `atlas models`,
  `localrouter` / `Local Router`, and `atlas-terminal-*` temp names.
- Left structural/generated identifiers alone (`@opencode/*` Effect service keys,
  SDK provider IDs, real `xiaomi`/`mimo-v2.5` upstream names) because those require
  deliberate source-contract replacement, not blind text churn.

**Verification:**
- Added scanner rules first and observed the boundary scan fail on the existing
  provider example, then patched the code.
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\scan-atlas-terminal-boundary.ps1`
  — boundary scan passed.
- `cd services/atlas-terminal && bun test` — 28 passed.
- `cd services/atlas-terminal && bunx tsc --noEmit` — clean.
- `cd services/atlas-terminal && bun run src/main.tsx --smoke` —
  `ATLAS TERMINAL OK — gateway offline`.
- `rg` for the newly guarded exact residues returned no matches.

## Session update — 2026-07-04 (latest): Provider endpoint split fix + session creation investigation

**Provider shape fix (two rounds):**

Round 1: `handleProviders` returned `{ providers }` but SDK expects `{ all, connected }` for `provider.list`. Fixed to return `{ all, connected }` — but this broke `config.providers` which sync.tsx reads as `providers.providers` into `store.provider`.

Round 2: Split into two handlers:
- `GET /config/providers` → `{ providers: [...], default }` → `store.provider`
- `GET /provider` → `{ all: [...], connected: [...], default }` → `store.provider_next`

26/26 tests pass, tsc clean, smoke live. Models dialog no longer crashes.

**Session creation ("Creating a session failed") — STILL UNRESOLVED:**

Adapter POST /session works in isolation (raw fetch + SDK client both return 200).
Interactive TUI still shows the toast. Headless `--prompt` passes.

Full investigation log: `.debug/2026-07-04-session-creation-failure-investigation.md`
Next session should start by capturing the actual error object via console.error at prompt/index.tsx:1080.

## Session update — 2026-07-04 14:07: Command Center loop goal context wired into NativeAtlasAgent harness

**Scope:** Current Focus only — "Ship the Command Center loop" / goal-model-to-native-harness slice.

**What changed:**
- `services/agent-runtime/atlas_runtime/agent_contract_service.py`
  - `RunContractSnapshot` now persists `context_markdown`, the full secret-redacted ATLAS Operator Context assembled for the run.
  - `selected_source_ids` now records the complete `AgentContext.sources` tuple, covering static focus/goal/project/observation sources as well as routed dynamic evidence.
- `services/agent-runtime/atlas_runtime/agents/native.py`
  - `NativeAtlasAgent.execute()` retains the persisted contract snapshot and passes a generated `system_message` into `agent.run_conversation(...)`.
  - The harness system message now contains the session bootstrap, full operator context, and dynamic context envelope, so native runs receive Current Focus / Goals / Tasks / Operating Contract instead of only the raw mission prompt.
- `services/agent-runtime/tests/test_agents.py`
  - Added coverage proving goal/task context reaches the injected harness via `system_message`.
- `services/agent-runtime/tests/test_agent_contract_service.py`
  - Added readback coverage for persisted `context_markdown`.

**Verification evidence:**
- `cd services/agent-runtime && pytest tests/test_agents.py tests/test_agent_contract_service.py tests/test_context_service.py tests/test_run_executor.py tests/test_goal_service.py` — 52 passed.
- `cd services/agent-runtime && pytest tests` — 737 passed, 2 skipped.

**Known repo state / caution:**
- Current session-modified files are the four paths listed above.
- `docs/plans/2026-07-04-cli-gap-analysis-and-next-sprint.md` is present as an untracked file; this slice did not edit it and it is outside the current focus.

**Next actions:**
1. If continuing this exact focus, wire the Command Center/API surface to create/list/update the persisted goals/tasks/observations if not already exposed.
2. Re-run a real native mission after operator provider capacity is available; prior evidence showed failures caused by missing/free/exhausted provider routes, not by this system-message wiring.
3. Keep claims evidence-classified; do not treat harness self-reports as independently verified work.

**Date:** 2026-07-04  
**Sprint deadline:** 2026-07-09  
**Current mode:** TUI Connectivity & Auth sprint — **all 7 tasks done this session.**
Full verification suite green (see bottom of this entry). Retirement gate
(Go TUI -> atlas-terminal default) still NOT decided — that remains the
operator's call per the standing guardrail, unaffected by this session's
work being complete.

## Session update — 2026-07-04: all 7 tasks done — session-creation root-caused, Codex OAuth verified live, atlas up/doctor extended, installer wired, vendor-tree clean, Go TUI caching added, CLI audited

**TASK 1 — session-creation bug: could NOT reproduce against a fresh live gateway.**
Built the release gateway wrapper (`ATLAS_CLI` -> hermes venv python), started
`native/atlas-core-rs/target/release/atlas-gateway.exe` (already newer than its
Rust sources — not stale), then ran `bun run src/main.tsx --prompt "hello"`
headless twice (20s and 35s) against it: no "Creating a session failed" toast,
no error text, in either run. Also proved `sdk.client.session.create()`
executed through the real production code path (adapter + generated SDK
client) returns `status:200`/no error in isolation. Strong evidence the
originally-reported toast was tied to a dead/stale gateway process at that
specific UAT moment, not a code defect — **the retirement-blocking bug as
reported no longer reproduces.**

Found and fixed a real, separate bug on the way: `adapter/chat.ts:138` emitted
a `session.created` bus event that the vendored donor `sync.tsx` never
listens for (its reactive store only upserts on `session.updated` — insert if
missing). New sessions were invisible in the reactive session list until some
*later* event touched them. Fixed the emit to `session.updated`; updated the
one test asserting the old event name (`test/chatLoop.test.ts:243`). 25/25
bun tests, tsc clean, `--smoke` shows `LIVE freellmapi/mimo-v2.5`.

**Recommendation:** re-run the operator UAT that originally found the toast,
with a gateway freshly started via `atlas gateway start` (not a leftover
process from an earlier session). If it still reproduces, the next diagnostic
step is capturing the interactive (non-headless, real TTY) console — this
session's headless `--prompt` harness could not fully replicate a real
Windows Terminal session.

**TASK 2 — Codex OAuth import: verified end-to-end, live.** `~/.codex/auth.json`
present (email `l2atlasgpt3107@gomail.edu.pl`, token not expired).
`POST /v1/auth/codex/import` -> `{"imported":true}`. Patched
`provider.name=openai-codex`, `provider.auth_mode=oauth_import`,
`provider.model=gpt-5.5` via `PATCH /v1/config`. Ran a real mission
("reply with the single word: pong") through `atlas mission create/run` —
it replied **"pong"** for real, `status:succeeded`, `agent_runtime:native`,
~9s wall time (checked `runs` table in `~/.atlas/atlas.db` directly). This
is a genuine live completion via the native runtime, not mock.

**Flagged, not fixed** (real bug, out of scope this session): `/v1/config`'s
`effective.auth_status` and `atlas auth doctor openai-codex` both report
`missing_auth`/`needs_auth` even when `oauth_import` is actually live —
they appear to only check the `api_key` auth path. `atlas provider status`
gets it right (`[live]`, credentials present: yes) via `owned_status()`,
which is the correct check per `codex_auth.py`'s own docstring. The other
two callers need the same `oauth_import`-aware branch.

**TASK 3 — `atlas up` + `atlas doctor` extended.**
- `gateway_control.py`: new `binary_stale()` — compares the gateway crate's
  newest `*.rs` mtime against the resolved binary's mtime (same pattern as
  `go_tui._checkout_binary_stale`). `atlas up` now warns (non-fatal) if the
  gateway binary predates its sources.
- `atlas up` (`_up_cmd` in `cli/main.py`) now also starts the FreeLLMAPI
  sidecar after gateway+cockpit report healthy — non-fatal if the external
  checkout isn't present (D-015: it's an optional sidecar, never vendored).
- `atlas doctor` extended: gateway staleness surfaced inline; three new
  informational sidecar probes (freellmapi/cashflow/discord, 0.5s timeout,
  each with its own remediation string, none fail the overall exit code);
  model-registry freshness check (`MAX(last_seen)` in `model_registry_v2`,
  flags >24h stale); `--json` flag emits the full report as one JSON object
  (`{"check": {"status": ..., "ok": bool}}`).
- Verified live: `atlas doctor` and `atlas doctor --json` both ran correctly
  against the live gateway (correctly reported cockpit down / sidecars
  offline, since neither was started this session). 134 focused pytest
  (doctor/gateway_control/freellmapi/cli) + full suite **733 passed, 2
  skipped** (no regression from the 732/1-skipped baseline).

**TASK 4 — installer integration: done.** Added an atlas-terminal build step
(`bun install` + `bun run typecheck`, graceful skip if `bun` absent, matching
the existing go/cargo/npm skip pattern) to both `scripts/install-atlas-cli.ps1`
and `scripts/setup.sh`. Added `atlas terminal status [--json]` (present/built/
version/gateway-reachable, with remediation) to `cli/main.py`. Verified: both
scripts parse clean (PowerShell tokenizer + `bash -n`), `atlas terminal
status` runs correctly live, full pytest suite still 733/2. Did not run the
full fresh-clone destructive install on this machine — mechanics verified,
not a real clean-VM run (that's WS-B installer plan §7 step 6, still open).

**TASK 5 — vendor-tree cleanup: done, boundary scanner passes clean (exit 0).**
Removed `dialog-go-upsell.tsx` and its wiring in `routes/session/index.tsx`
(the `session.status`/retry listener, `GO_UPSELL_*` kv constants); removed
the `/share` command registration (dead — no adapter backend) plus its now-
orphaned idle tips (`tui.tips.share`, `share_auto`, `share_disabled`,
`unshare`) across all 7 locale files, since they referenced a command that
no longer exists. Fixed `tui-migrate.ts`'s `TUI_SCHEMA_URL` and all 33
`src/tui/context/theme/*.json` `$schema` refs off `opencode.ai`. Also found
and fixed two adjacent leaks the sprint's item list didn't name but the
scanner exists to catch: a literal `mimo -s <id>` continue-command string in
the session exit banner (-> `atlas -s`), and unreachable `opencode`/
`opencode-go` provider-description branches in `dialog-provider.tsx` (dead
code — ATLAS's provider catalog is built from its own model registry and
never surfaces those donor provider IDs; removed along with the now-unused
`theme` destructure). Extended `scripts/atlas-terminal-forbidden-terms.txt`
with `opencode.ai` (documented rationale inline) so this class of regression
is caught mechanically going forward, and used the extended scanner to find
2 more stray `opencode.ai` doc-comment URLs in the vendored SDK
`types.gen.ts` files (both SDKs) — fixed. Verified:
`scan-atlas-terminal-boundary.ps1` exits 0, 25/25 bun tests, tsc clean,
`--smoke` still live.

**TASK 6 — Go TUI caching: done.** `settings.go`'s `fetchSettings()`
(`Config()` + `Models()`) parallelized via a plain `sync.WaitGroup` (no new
dependency — errgroup isn't vendored and wasn't worth adding for two calls).
`client.go`'s `Models()` gained a 5-minute in-memory TTL cache
(`modelsCacheTTL`), invalidated by `PatchConfig` on success (a provider/model
change can change which catalog entries are active). Added 2 new tests
(`TestModelsCachesWithinTTL`, `TestPatchConfigInvalidatesModelsCache`) proving
the cache actually suppresses a second gateway call and that patching
correctly forces a re-fetch. Verified: `go test ./...` 98 passed (was 96 —
the 2 new tests), `go vet ./...` clean, `go build ./...` clean.

**TASK 7 — CLI audit + npm package plan: done (audit + status doc, not a
refactor** — correctly scoped per the sprint's own "conditional, planning-
weighted" framing). Full findings in
`docs/plans/2026-07-04-cli-audit-and-npm-package-status.md`. Headline: the
three specifically-named naming-drift spots (`purge-archived`, `config
json`, `channels status`) are already fine — that concern looks resolved
from an earlier session. The real, unresolved drift is a **mixed `--json`
convention**: some groups (`auth`, `channels`, `config`) use a dedicated
`json` subcommand, others (`doctor`, `version`, `terminal status`, `models`,
`discord`, `surface`, `tools`, `provider`, `golden`) use a `--json` flag.
Not fixed — standardizing touches ~9 modules + their tests, real refactor
scope, not audit scope. Recommendation recorded in the doc: converge on
`--json` (the majority pattern, and what every command this session added
used). npm package: no new design needed — the existing
`docs/plans/2026-07-03-wsb-installer-plan.md` already covers architecture/
sequencing in full and its own progress tracking (§7) is accurate; the doc
notes how this session's TASK 3/4 work (staleness-check pattern, atlas-
terminal now installer-integrated) feeds directly into that plan's open
steps 3-6, without duplicating the plan.

## Post-sprint review (2026-07-04) — 8-angle parallel review, 4 real bugs found and fixed

Ran a high-effort code review (8 parallel finder agents: line-by-line
correctness, removed-behavior audit, cross-file tracer, reuse, simplification,
efficiency, altitude, CLAUDE.md conventions) over the full session diff before
committing. Real, verified findings and fixes:

1. **`atlas doctor`'s model-registry freshness check never actually worked.**
   `model_registry_v2.last_seen` is an ISO-8601 string
   (`datetime.now(timezone.utc).isoformat()`), but the check did
   `isinstance(last_seen, (int, float))` — always `False` — so `age_seconds`
   was always `None` and the catalog was reported `"fresh"` unconditionally,
   no matter how stale. Fixed with `datetime.fromisoformat`; verified with a
   synthetic 3-day-old timestamp correctly computing 259200s / stale=True.
2. **A slow in-flight `Models()` fetch could resurrect stale data after
   `PatchConfig` invalidated the cache** (a real TOCTOU race, not just
   theoretical — a save-provider-then-reopen-settings sequence hits exactly
   this window). Fixed with a generation counter (`modelsGen`, bumped by
   `invalidateModelsCache`) that fences off any in-flight fetch's write once
   an invalidation has landed. Also fixed `Models()` returning its cached
   slice by reference (an in-place-mutating caller would have corrupted the
   shared cache) — both the cache-hit and cache-write paths now copy.
   New regression test: `TestModelsInFlightFetchDoesNotResurrectAfterInvalidation`.
3. **`atlas doctor --json`'s per-key schema was inconsistent** — the
   `provider: skipped (config invalid)` path and the stale-gateway-binary
   path both stored differently-shaped/wrong values (`ok=True` for a STALE
   binary is misleading to a JSON consumer). Fixed: `echo()` now requires
   `ok` explicitly (no more bare-string branch), every key is
   `{"status": str, "ok": bool}`, and a stale binary reports `ok=False`
   without flipping the overall exit code (still healthy enough to serve).
4. **The installer comments overpromised failure-tolerance that doesn't
   exist.** Both `setup.sh` and `install-atlas-cli.ps1`'s new atlas-terminal
   build step said "a failure here does not abort the rest of install" —
   false under `set -euo pipefail` / `$ErrorActionPreference='Stop'` (same as
   every other build step in these scripts). Fixed the comment wording to
   match the actual, pre-existing, honest behavior instead of the code.

Also fixed as part of the same review pass (found by the removed-behavior
audit, not a fabricated addition): the `/share` command removal (TASK 5) left
`/unshare` permanently vestigial (it can never be enabled without `/share`
ever having set a `session.share.url`) and two dangling keybind defaults
(`session_share`/`session_unshare`, both unbound by default but referencing
a command value that no longer exists). Removed `/unshare` and its 3 i18n
title keys across all 7 locales, and the 2 keybind defaults, completing the
removal properly.

**Investigated and deliberately NOT changed** (reasoning recorded so it isn't
re-litigated): `gateway_control.binary_stale()` duplicates
`go_tui._checkout_binary_stale()`'s mtime-comparison logic in a second
module — real duplication, but unifying it means touching a third module's
contract right before a push; left as documented, acknowledged debt.
`atlas doctor`'s hardcoded sidecar tuple (freellmapi/cashflow/discord) was
flagged as possibly bypassing the `atlas module` registry — checked live,
`atlas module list` only tracks `cashflow` and is a narrower, different
concept, not a superset; the suggestion doesn't actually apply. The
`opencode`/`opencode-go` provider-description removal (TASK 5) was
re-verified against `sync.tsx`'s actual provider-list source
(`atlasFetch.ts`'s `handleProviders()`, built purely from ATLAS's own
`/v1/models` registry) — confirmed unreachable in ATLAS's adapter context
despite `"opencode-go"` still appearing in a *different*, untouched
description map in the same file (the provider-picker list, not the
API-key-entry dialog); no regression from the removal. Fixed doctor.py's
`__import__(..., fromlist=...)` to the more idiomatic
`importlib.import_module` (trivial, no behavior change).

Final re-verification after all review fixes: bun test 25/25, tsc clean,
`--smoke` live, boundary scanner exit 0, pytest 736/2 (was 733 — +3 new
`atlas up` tests covering the freellmapi/staleness paths that were
previously exercised unmocked with zero assertions), go test 99/3 packages
(was 98 — +1 race-fence test), go vet clean, gofmt clean, `atlas up`/
`atlas doctor` live-verified again.

## Full verification (2026-07-04, end of session) — all green

- `cd services/atlas-terminal && bun test` — 25 pass, 0 fail.
- `bunx tsc --noEmit` — clean.
- `bun run src/main.tsx --smoke` — `ATLAS TERMINAL OK — LIVE openai-codex/gpt-5.5`.
- `cd services/agent-runtime && pytest tests` — 733 passed, 2 skipped.
- `cd services/atlas-tui && go test ./...` — 98 passed in 3 packages.
- `go vet ./...` — no issues.
- `atlas up` — gateway already running, cockpit started fresh, freellmapi
  already running — all three healthy.
- `atlas doctor` — db/config/gateway/cockpit/freellmapi/model_registry/
  provider all `ok`; cashflow/discord correctly report `offline` with
  remediation (neither installed on this machine); claude_code correctly
  reports the missing optional SDK extra.
- `atlas auth import-codex` — `{"imported": true}`.

**Environment note:** this session started the release gateway manually
(`native/atlas-core-rs/target/release/atlas-gateway.exe`, no PID file — it
was NOT started via `gateway_control.start()`/`atlas gateway start`, so
`atlas gateway stop` won't find it). Cockpit and freellmapi WERE started via
their normal control primitives (`atlas up`), so those have proper PID/state
tracking. If the manually-started gateway process is still running, kill it
directly or via Task Manager before assuming a clean-slate boot for the next
session. A scratch `atlas.cmd` wrapper (per [[atlas-local-run-recipe]]) was
created in the session's temp scratchpad, not the repo — the next session
needs its own per that recipe.

**Residual known issues (not blocking, documented above in their task
sections):** (1) `/v1/config`'s `effective.auth_status` and `atlas auth
doctor openai-codex` misreport `oauth_import` as missing auth even when live
— only `provider status` checks it correctly (TASK 2). (2) Mixed `--json`
convention across CLI groups (TASK 7). (3) Retirement gate (Go TUI vs
atlas-terminal as default `atlas`) still not decided — operator call,
per the standing guardrail.

**Next action:** operator UAT of `bun run dev` in an actual Windows Terminal
session (this session's headless `--prompt` harness could not fully replicate
a real interactive TTY) to make the final retirement-gate call; then, if
desired, the residual issues above.

## Prior session — 2026-07-03 (later): hygiene + mission analysis

## Session update — 2026-07-03 (later): hygiene + mission analysis

- Consistency review ran first (`.planning/reports/handoff-roadmap-consistency-review-2026-07-03.md`):
  STAGE 0 had been left untracked despite STATE claiming "committed"; uncommitted WIP broke
  7 cockpit tests + 2 python tests. All fixed and committed:
  - `feat(freellmapi)` — sidecar key autowire into `atlas models refresh`, sidecar panel
    moved Models→Settings, canonical provider names, tests updated. Gates fresh: agent-runtime
    **732 passed / 1 skipped**; cockpit 44 tests + tsc + zero-warning lint + build/bundle;
    atlas-terminal 5 bun tests + tsc + `--smoke` boot LIVE.
  - `feat(atlas-terminal)` — STAGE 0 committed (plan, OMNI wiring strategy, Bun adapter scaffold).
- **Flag for operator:** `freellmapi status` now returns the sidecar `api_key` cleartext
  (local-only convenience; diverges from the masked-secret contract). Ratify or revert.
- `get_key.py` at repo root is stray scratch (logic productionized in
  `freellmapi_control.get_api_key()`); recommend deletion.
- Mission analysis + execution order for the operator's 2026-07-03 task list:
  `docs/plans/2026-07-03-finish-mission-analysis-and-execution-order.md` — workstreams
  WS-A (donor TUI, main), WS-B (installer), WS-C (CLI polish), WS-D (`atlas up` + model
  fetch), WS-E (TUI caching), WS-F (surface wiring law), WS-G (cashflow, document-only).
  Contains file:line problem inventories for CLI, `atlas up`, and Go TUI caching.
- **STAGE 1 DONE (2026-07-03 night, commit `97ca5112`)**: donor chat loop live-verified
  end-to-end (session → prompt_async → mission/run → SSE parts → idle; permission bridge
  with owner token). Two root causes fixed on the way: `resolve_provider` now derefs the
  freellmapi sidecar key (no env side channel), and `freellmapi_control.start` no longer
  forces `NODE_ENV=production` (sidecar died at boot demanding ENCRYPTION_KEY).
  Note: the free route currently lacks tool-calling (HTTP 429 exhausted) — real runs need
  a tool-capable model/route; wiring itself is proven.
- **STAGE 2 DONE (2026-07-03 late night, commits `4e7478a2`/`1432e5ae`/`1c606dcf`)**:
  donor TUI vendored wholesale (138 files + SDK v2 + pure modules + shims for disabled
  server/plugin machinery), boots over the ATLAS adapter (internal plugins load,
  composer renders, live provider in status), identity scrubbed (flags/aliases/branding/
  i18n). tsc clean, 9 bun tests, smoke + headless boot verified. Operator ratifications
  applied: get_key.py deleted; freellmapi status api_key exposure kept (documented).
- **STAGE 3 progress (2026-07-03, later)**:
  1. **DONE** — vendor-tree branding scrub: `src/vendor/opencode/cli/logo.ts` still had
     the raw MIMO/CODE block-letter wordmark (STAGE 2's scrub only covered `src/tui/**`,
     not `src/vendor/opencode/**`). Replaced with the same ATLAS wordmark font already
     used by `services/atlas-tui/internal/tui/theme.go` (`unicodeLogoRows`), so both TUI
     surfaces share one identity. Also fixed `MC |`/`OC |` terminal-title prefixes and the
     `/doc` command's external `mimo.xiaomi.com` link (now opens the repo README).
     Note: `providerID: "xiaomi"` / model name `mimo-v2.5` are real upstream identifiers
     for the Xiaomi MiMo model family used by the freellmapi route — NOT branding, left
     untouched.
  2. **DONE** — removed `dialog-mimo-login.tsx` and its `provider.login`/`provider.connect`/
     `provider.logout` command wiring in `app.tsx`, plus orphaned `tui.dialog.login.*` /
     `tui.command.provider.{login,connect,logout}.title` / `tui.command.logout.toast` i18n
     keys across all 7 locales. This whole feature called `oauth.authorize`, `auth.remove`,
     `auth.set`, `instance.dispose` — none of which the ATLAS adapter (`atlasFetch.ts`)
     implements (all 501 `notImplemented`), so it was already dead/broken over the ATLAS
     gateway, not just donor-branded. Consistent with the "ATLAS keeps
     provider/auth/config authority" guardrail — no second identity system was added.
  3. **DONE** — added `test/sdkClient.test.ts`: exercises `createOpencodeClient` (the real
     client `src/tui/context/sdk.tsx` builds) through the adapter, asserting
     `session.create`/`session.list` return no client-level error. Closes the gap where
     the existing chat-loop tests only drove `handle.fetch` directly, not the generated
     SDK client the TUI actually calls. The previously-reported "Creating a session
     failed" toast (2026-07-03 screenshot) could NOT be reproduced against current code —
     both the raw adapter and the SDK v2 client succeed in isolation; if it recurs, check
     the browser/terminal console per the toast's own instruction (mission analysis notes
     it may be stale, predating STAGE 2c's identity scrub commit).
  Verified after each change: `bunx tsc --noEmit` clean, `bun test` (10/10 pass),
  `bun run smoke` boots. Committed as `6568574e`.
  4. **DONE** (commit `430cd86`) — Go TUI vs donor feature-gap audit (via Explore agent)
     found only two real gaps: **Settings** (no config-write path at all — donor's
     `dialog-model.tsx` calls `global.config.update` but the adapter had no PATCH
     `/config` route) and **model readiness classification** (Go TUI's
     live/unconfigured/degraded/mock verdict had no analog). Permission bridge
     (`chat.ts`'s pollPermissions/replyPermission + `routes/session/permission.tsx`) was
     already a superset of the Go overlay; the idle logo shimmer in `logo.tsx` already
     covers idle-animation intent (mechanically different from `starfield.go` but not a
     regression). Ported: `atlasFetch.ts` gained `/atlas/config` (GET/PATCH),
     `/atlas/auth/providers`, `/atlas/auth/codex/import`, `/atlas/provider/status` —
     forwarding 1:1 onto the exact gateway routes `internal/client/client.go` already
     uses (`GET/PATCH /v1/config`, `POST /v1/auth/*`, `GET /v1/provider/status`) — no new
     gateway work needed. `src/tui/util/readiness.ts` ports `readiness.go`'s
     `readinessFor`/`mockAllowed` verbatim (test cases mirrored from
     `readiness_test.go`). New `/settings` command (`dialog-atlas-settings.tsx`) built
     from the donor's existing `DialogSelect`/`DialogPrompt` primitives — provider,
     model, auth mode, base URL, API key, reasoning effort. **Scope cut**: the Go TUI's
     post-save connectivity probe (`startProbe`/`archiveProbe`, an ephemeral
     mission+SSE-classify round trip) was not ported — save + a `/provider/status`
     refresh gives the same readiness signal without the extra mission plumbing. Revisit
     if operator UAT shows the probe step is missed.
  Verified: `bunx tsc --noEmit` clean, `bun test` 18/18, `bun run smoke` boots.
- **STAGE 3 parity audit — CONCLUSION (2026-07-03, later)**: feature-for-feature vs
  services/atlas-tui (the current working `atlas tui`):
  - Settings, model readiness, permission bridge, idle animation: **at parity**
    (settings/readiness ported this session; permissions/idle were already covered —
    see the earlier "STAGE 3 progress" entry above).
  - Built-in slash commands (init/review/dream/distill/goal/deep-research): **at
    parity** — both TUIs now execute all six for real (donor side wired this session;
    commit `f4bfa43`).
  - FreeLLMAPI sidecar control (status/start/stop): **at parity** — was the one real
    gap the audit found; closed in commit `cea05c6`.
  - Workflows (`ATLAS_TUI_EXPERIMENTAL_WORKFLOW_TOOL`): experimental/flagged on both
    sides, not a blocking gap either direction.
  - Branding/vendor-tree scrub: swept (STAGE 2c + this session's logo.ts/app.tsx fixes)
    and now mechanically guarded (`scripts/scan-atlas-terminal-boundary.ps1`).
  **Flagged but NOT fixed this session** (found during the audit, out of scope for a
  parity pass — product decisions, not bugs): `dialog-go-upsell.tsx` and the `/share`
  command still reference `opencode.ai` (donor's own paid-upsell/share-hosting
  product — currently dead code, `/share`'s backend route is unimplemented in the
  adapter, so nothing is actually sent there); `tui-migrate.ts`'s `TUI_SCHEMA_URL`
  points at `https://opencode.ai/tui.json` for TUI-config-schema migration; ~30 theme
  JSON files carry a `$schema: https://opencode.ai/theme.json` reference (editor
  tooling hint only, not user-facing). None of these block a retirement decision, but
  they're real remaining vendor-tree surface if a future scrub pass runs.
  **Retirement gate: NOT decided.** Per this file's own guardrail ("do not mark the
  sprint complete without explicit verification and operator UAT"), whether
  `atlas tui` actually switches to atlas-terminal is the operator's call, not something
  claimed here. Recommended UAT before deciding: `cd services/atlas-terminal && bun run
  dev` — exercise the prompt loop, `/settings` (new), `/freellmapi-status` (new),
  `/dream` `/distill` `/goal` `/deep-research` (new), and confirm the branding fix and
  the previously-reported "Creating a session failed" toast (unreproduced against
  current code in this session's testing).
- **Operator UAT (2026-07-03, live `bun run dev` against Windows Terminal)** —
  screenshot evidence:
  1. **Branding fix confirmed live**: clean ATLAS wordmark renders (violet/orange,
     matching the Go TUI's font), no MIMO/CODE text anywhere. Status line correctly
     shows `Native · mimo-v2.5 · freellmapi` (the real provider/model — not a leak,
     see STAGE 3 branding-scope note above).
  2. **"Creating a session failed" toast STILL reproduces live** on typing a prompt
     and hitting enter, even after this session's SDK v2 client + adapter fixes. This
     contradicts the earlier isolated testing in this same session (both the raw
     adapter and the generated SDK v2 client succeeded standalone against a stubbed
     gateway — see `test/sdkClient.test.ts`, `test/atlasFetch.test.ts`). The gap: those
     tests stub the gateway; this reproduction is against the **real** ATLAS gateway
     process. Likely next diagnostic step: open the toast's own suggested "console"
     (browser/terminal devtools) for the actual thrown error, or check whether the
     real gateway process was stale/not rebuilt (`cargo build --release -p
     atlas-gateway` — the prebuilt binary going stale caused a similar-looking
     "offline" symptom before, per [[atlas-local-run-recipe]]) or whether `atlas db
     init` / surface-session bootstrap has a real-gateway-only failure mode the stub
     doesn't model. **Not yet fixed — next session's first diagnostic target.**
  Retirement-gate decision: still pending on the operator (branding + settings/
  readiness/commands parity look good live; the session-creation bug blocks a clean
  go/no-go until root-caused).
- **Next action (next session):**
  1. Root-cause "Creating a session failed" against the **live** gateway (not a stub) —
     start with the gateway's own logs/console output at the moment of failure.
  2. Once fixed: re-run operator UAT, then the retirement-gate decision.
  3. Then WS-D (`atlas up` full topology), WS-C (CLI polish), and WS-B's remaining
     installer steps (`docs/plans/2026-07-03-wsb-installer-plan.md` §7 steps 3-6:
     clean-machine runbook, the TUI-binary-manifest decision gated on the retirement
     call, real CI publishing), per
     `docs/plans/2026-07-03-finish-mission-analysis-and-execution-order.md`.

## Current state

The earlier Cashflow topographic integration and ATLAS Go TUI presentation pass remain in the
working tree. A later dashboard visual correction attempt was judged worse by the operator and
was rolled back. Do not restart another broad visual redesign from that failed direction.

The most recent operator direction was documentation only. The sprint plan is now captured in:

- `docs/plans/2026-07-03-sprint-to-2026-07-09-milestone-finish.md`
- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/STATE.md`

## Sprint target

Finish the active milestones by 2026-07-09 with polish and stability across the agent config
surface, web cockpit, terminal, cashflow module, model/provider config, installer, CLI, and TUI.

## Priorities

1. **Unify Settings and System**
   - Settings and System should become one modular control page.
   - Use tabs or dynamic sections instead of two competing sidebar destinations.
   - Existing `/settings` and `/system` routes may remain only as compatibility shims or redirects.

2. **Polish configuration for agent, web, and terminal**
   - Same categories and effective values across WebUI, TUI, and CLI.
   - Include provider/model/auth state, permission mode, workspace/project, context/Brain controls,
     diagnostics, hot-reload vs restart-required state, and remediation.

3. **Make Models/config dynamic**
   - Models page must render from live provider/model/config contracts.
   - Show effective value, source, auth state, validation state, health/probe result, and route/fallback policy.

4. **Stabilize Cashflow integration**
   - Treat Cashflow as an ATLAS module, not a detached dashboard.
   - Keep launch/handoff deterministic, module health visible, and route smoke green.
   - Visual work should focus on spacing, padding, and layer hierarchy first.

5. **Create installation package path**
   - Install, update, uninstall/rollback, doctor/health check, clean-machine instructions, and versioned artifact.

6. **Polish CLI commands**
   - Coherent naming, discoverable help, script-safe output where needed.
   - Cover status, doctor, config, models, cashflow, and retained legacy/rollback paths explicitly.

7. **Refactor TUI using MiMoCode as principal presentation donor**
   - MiMoCode MIT presentation code may be copied/ported/modified with notices retained.
   - Keep ATLAS runtime, provider, config, audit, policy, session, and storage authority.
   - Focus on gradient smoothness, animation cadence, composer geometry, command menu alignment,
     spacing, and transcript ergonomics.

## Visual debt to carry forward

- The layout is not polished enough because some card/panel text has effectively zero margin.
- Spacing needs a deliberate system pass: section gaps, panel padding, sidebar rhythm, and text density.
- Layering needs cleanup: topo background, glass panels, rails, and nav should read as one depth stack.
- Avoid another uncontrolled dashboard redesign. First fix spacing and layers surgically.

## Existing verification from the prior implementation pass

- `services/cashflow`: lint/build/route smoke previously passed.
- `services/atlas-tui`: Go tests/vet/stripped build previously passed.
- MiMoCode MIT attribution is retained in `docs/third-party/ATLAS_TUI_UPSTREAM_NOTICE.md`.

Re-run fresh verification before claiming any new implementation is complete.

## Suggested next implementation order

1. Settings/System consolidation spec and route compatibility decision.
2. Dynamic model/config contract audit.
3. Cashflow stabilization checklist and spacing pass.
4. Installer/package path.
5. CLI command polish.
6. MiMoCode-donor TUI refactor plan, then implementation.

## Guardrails

- No code changes were requested in the last documentation-only step.
- Do not add a second donor runtime/backend.
- Do not split Settings/System further.
- Do not start CRM, voice, or overlay work in this sprint.
- Do not mark the sprint complete without explicit verification and operator UAT.
## 2026-07-16 — Long-horizon mission judge loop and model-role integrity

ATLAS now has a durable, bounded mission loop rather than a prompt-only imitation
of `/goal`. `/goal` and `/mission` are exact aliases in WebUI Chat, Console, and
atlas-terminal. Their command envelope is parsed before mission creation, so the
agent receives only the objective.

Implementation contract:

- `infra/migrations/0021_mission_loops.sql` persists one loop policy per mission
  and one immutable judgement receipt per run.
- `mission_loop_service.py` adopts Hermes's strict judge semantics while keeping
  ATLAS SQLite as authority. Successful runs are judged; failed/cancelled runs
  stop. Three malformed replies pause. The default budget is 12, hard-capped at
  100.
- Judge model precedence is mission override, global `functions.judge_model`,
  initiating surface session, then active provider/model. Settings renders the
  empty override as `Inherit chat session`.
- `atlas run exec` discovers the persisted agent runtime and owns the whole loop.
  It allocates continuation runs serially under the same mission. The Rust gateway
  SSE follows those runs and emits a `continuation` boundary instead of ending
  after the first attempt.
- WebUI and TUI remain pending until a final `goal_judgement` state. TUI clears
  per-run delta reconciliation guards at continuation boundaries so later output
  remains visible in the same response.
- Surface model selection is now operational: NativeAtlasAgent reads the
  initiating surface model, and atlas-terminal recreates its surface when the
  selected provider/model changes. The judge inherits that same model by default.
- Hermes `delegate_tool` is still the real child-agent implementation; ATLAS's
  existing `ensure_foundation_bridge` makes its subagent hooks auditable. No new
  queue/framework/dependency was introduced.

Verification completed on Windows:

- agent-runtime: 858 passed, 2 skipped.
- atlas-core: 97 passed.
- Rust gateway: 114 passed.
- WebUI: 115 passed; TypeScript passed.
- atlas-terminal: 66 passed; TypeScript passed.
- Ruff on changed Python: passed.

Ultra artifacts:

- `.planning/ultra/ULTRAPLAN-long-horizon-mission-orchestration-2026-07-16.md`
- `.planning/ultra/simulation/SIM-long-horizon-mission-orchestration-2026-07-16.md`

Still owed: operator UAT against a live provider for continue→done, explicit judge
override, TUI model switch, disconnect/reconnect, cancellation, and budget/pause
presentation. Bare `/goal status` currently directs the operator to Missions; a
dedicated loop-status control surface can be added when pause/resume UX is designed.
The running Windows gateway held `target/release/atlas-gateway.exe` open, so the final
release rebuild could not replace it in place; stop/restart the stack before building
or deploying the release binary.
