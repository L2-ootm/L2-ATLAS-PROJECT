# ATLAS TUI Chat-First Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dashboard-first, stale-artifact-prone Go TUI with a tested chat-first agent
surface that refuses implicit mock conversations and keeps operational controls contextual.

**Architecture:** Keep Go as a thin BubbleTea adapter over the existing Rust/Python contracts.
One surface session is the visible conversation; each submitted turn may create an internal
mission/run, while the TUI aggregates normalized events into one transcript. Provider readiness
is derived from server status and never reimplemented as credential logic.

**Tech Stack:** Go 1.26, BubbleTea/Bubbles/Lipgloss, Python Typer launcher, Rust gateway HTTP/SSE.
No new dependencies.

---

### Task 1: Resolved executable integrity

**Files:**
- Modify: `services/agent-runtime/atlas_runtime/cli/go_tui.py`
- Modify: `services/agent-runtime/tests/test_go_tui_launcher.py`
- Modify: `services/atlas-tui/main.go`
- Create: `services/atlas-tui/version_test.go`

- [ ] **Step 1: Write failing launcher tests**

Add tests proving a stale source-checkout binary triggers `go build -trimpath -o <binary> .`,
an up-to-date binary does not rebuild, and the resulting command remains argv-only.

- [ ] **Step 2: Verify RED**

Run:
`python -m pytest services/agent-runtime/tests/test_go_tui_launcher.py -q`

Expected: stale-checkout test fails because `resolve_binary()` currently returns the stale file.

- [ ] **Step 3: Implement source freshness and build identity**

Compare the checkout executable mtime against `.go`, `go.mod`, and `go.sum`. Rebuild only when
missing/stale. Add `--version` to the Go entry point with `version` and `commit` variables settable
by `-ldflags`.

- [ ] **Step 4: Verify GREEN**

Run the Python launcher tests and `go test ./...`.

### Task 2: Explicit execution readiness

**Files:**
- Create: `services/atlas-tui/internal/tui/readiness.go`
- Create: `services/atlas-tui/internal/tui/readiness_test.go`
- Modify: `services/atlas-tui/internal/tui/model.go`

- [ ] **Step 1: Write failing readiness tests**

Cover `live`, `unconfigured`, `degraded`, and explicit `mock` projections from
`client.ProviderStatus`. Assert that submit is blocked when `MockMode` is true unless
`ATLAS_TUI_ALLOW_MOCK=1`.

- [ ] **Step 2: Verify RED**

Run:
`go test ./internal/tui -run 'Readiness|SubmitBlocksImplicitMock'`

Expected: failure because no readiness projection or submit gate exists.

- [ ] **Step 3: Implement minimal readiness projection**

Create a render-only `executionReadiness` value. On implicit mock submission, retain the draft,
open provider settings/onboarding, and display server remediation. Never auto-select credentials.

- [ ] **Step 4: Verify GREEN**

Run focused tests, then `go test ./internal/tui`.

### Task 3: Chat-first shell

**Files:**
- Create: `services/atlas-tui/internal/tui/chat_view.go`
- Create: `services/atlas-tui/internal/tui/chat_view_test.go`
- Modify: `services/atlas-tui/internal/tui/model.go`
- Modify: `services/atlas-tui/internal/tui/theme.go`

- [ ] **Step 1: Write failing interaction and render tests**

Assert:

- composer is focused on launch;
- idle view contains a centered ATLAS composer and no provider/missions/permissions dashboard;
- typing routes directly to the composer;
- `Enter` submits and `Ctrl+J` inserts a newline;
- active view contains transcript, persistent composer, compact status, and optional sidebar;
- 80×24 ASCII and 140×40 Unicode lines fit.

- [ ] **Step 2: Verify RED**

Run:
`go test ./internal/tui -run 'ChatFirst|Idle|Composer|ActiveConversation'`

Expected: failures against the dashboard-first view and mission focus.

- [ ] **Step 3: Implement the chat-first renderer and focus model**

Make composer the default focus. Render idle and active states separately. Remove permanent mode,
mission, and permission panels from `View`; expose them through settings, sidebar, and commands.
Use ATLAS/L2 signal colors, angular surfaces, restrained ambient contour glyphs, and no decorative
animation loop.

- [ ] **Step 4: Verify GREEN**

Run focused tests and `go test ./internal/tui`.

### Task 4: Visible conversation and commands

**Files:**
- Create: `services/atlas-tui/internal/tui/commands.go`
- Create: `services/atlas-tui/internal/tui/commands_test.go`
- Modify: `services/atlas-tui/internal/tui/model.go`
- Modify: `services/atlas-tui/internal/tui/events.go`

- [ ] **Step 1: Write failing turn-flow tests**

Assert that submitting appends a user turn immediately, streamed events append to the same
transcript, completion returns focus to composer, and a second submission preserves prior turns.
Cover `/settings`, `/missions`, `/permissions`, `/sidebar`, `/help`, and `/quit`.

- [ ] **Step 2: Verify RED**

Run:
`go test ./internal/tui -run 'Conversation|SlashCommand'`

- [ ] **Step 3: Implement turn aggregation and command routing**

Retain the existing create-mission/start-run/SSE path as internal mechanics. Add transcript roles
and command results without adding storage or runtime authority.

- [ ] **Step 4: Verify GREEN**

Run focused tests and the complete Go suite.

### Task 5: Inline ownership and cancellation

**Files:**
- Modify: `services/atlas-tui/internal/tui/model.go`
- Modify: `services/atlas-tui/internal/tui/overlay.go`
- Modify: `services/atlas-tui/internal/tui/overlay_test.go`
- Modify: `services/atlas-tui/internal/client/client_test.go`

- [ ] **Step 1: Write failing behavior tests**

Assert an owned approval becomes a blocking inline/overlay decision, foreign ownership is rejected
by the client, and `Ctrl+C` cancels the active surface before a later idle `Ctrl+C` exits.

- [ ] **Step 2: Verify RED**

Run:
`go test ./internal/tui ./internal/client -run 'Approval|Cancel'`

- [ ] **Step 3: Implement cancellation and inline decision context**

Use existing owner-token and nonce routes. Add no new action endpoint or policy logic.

- [ ] **Step 4: Verify GREEN**

Run focused tests and the complete Go suite.

### Task 6: Executable-level verification and handoff

**Files:**
- Modify: `services/atlas-tui/README.md`
- Modify: `.planning/STATE.md`
- Create: `.planning/phases/10.8-cross-surface-conformance-uat-cutover/10.8-TUI-CORRECTION.md`

- [ ] **Step 1: Build the exact source-checkout executable**

Run:
`go build -trimpath -ldflags "-s -w -X main.version=dev -X main.commit=<HEAD>" -o atlas-tui.exe .`

- [ ] **Step 2: Verify the resolved artifact**

Run `atlas-tui.exe --version`, scan it for retired global approval mutation paths, and launch it
against the live gateway in a real terminal.

- [ ] **Step 3: Run full gates**

Run Go fmt/vet/test/build; launcher Python tests; runtime regressions; gateway API/contract tests;
ASCII/Unicode render tests; and `git diff --check`.

- [ ] **Step 4: Update evidence and commit**

Record exact test totals, executable identity, provider readiness behavior, visual states, and any
remaining environment-gated UAT honestly. Do not mark Phase 10.8 complete unless its broader
cross-surface criteria also pass.
