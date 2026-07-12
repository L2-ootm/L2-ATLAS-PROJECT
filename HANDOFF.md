# Handoff — L2 ATLAS Finish Sprint

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
