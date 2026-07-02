# ATLAS TUI Chat-First Redesign — Product Intent

**Date:** 2026-07-01
**Status:** Implemented 2026-07-01; interactive operator UAT pending
**Reference:** MiMoCode interaction hierarchy and terminal ergonomics, transformed into an
ATLAS-native experience
**Trigger:** First operator UAT of the Go/BubbleTea TUI failed product acceptance

## 1. Acceptance correction

The current Go TUI is contract-complete but not product-complete. It successfully exercises
gateway, provider, mission, stream, and permission APIs, but presents them as an operator
dashboard rather than an AI-agent workspace. The operator cannot begin by simply typing to an
agent, real-provider absence is reduced to a header label, and the transcript is visually
subordinate to status panels.

The first UAT also exposed a release-path defect: `atlas` resolved a source-checkout executable
built on 2026-06-28 while the source and scoped approval client had changed on 2026-06-30. The
stale binary still contained the retired global approval route. Passing source tests therefore
did not prove that the executable launched by the operator matched the tested source.

This document supersedes any claim that the current TUI has reached the intended
“opencode/MiMo-grade” experience. The Go/BubbleTea and shared-runtime architecture remains
accepted; its information architecture and interaction model do not.

## 2. Product north star

Opening `atlas` should feel like entering a capable agent conversation, not inspecting an admin
console.

The default path is:

1. Open ATLAS.
2. Type immediately.
3. Submit a request.
4. Watch the agent reason, retrieve context, call tools, request permission, and respond.
5. Continue the same conversation without managing missions or runs.

Missions, runs, provider profiles, permissions, context, subagents, and audit identity remain
real system concepts. They should appear when useful, not dominate the idle screen.

## 3. Experience states

### 3.1 Unconfigured first launch

If no real provider can execute, ATLAS presents a focused onboarding card in the composer area.
It lists available paths—Codex OAuth import, Claude Code, API key, or FreeLLMAPI—with one clear
recommended action and honest remediation.

ATLAS must not silently treat mock output as an agent conversation. Mock mode is an explicit
developer/test choice, visually persistent and impossible to confuse with a live model.

### 3.2 Configured idle

The idle screen uses a centered ATLAS identity and a large, already-focused composer. A compact
line shows the active mode, model, workspace, and permission profile. Secondary hints expose
settings, commands, attachments, subagents, and session history without surrounding the
composer with dashboard boxes.

Typing works immediately. No `n` shortcut is required.

### 3.3 Active conversation

After the first submission, the UI transitions to:

- a large scrollable transcript on the left;
- a persistent composer at the bottom;
- an optional contextual sidebar on the right;
- a compact status/footer line.

User messages, assistant text, reasoning summaries, retrieval, tool calls/results, diffs,
subagent activity, errors, and terminal outcomes have distinct readable treatments. Internal
mission/run identifiers remain available through details or commands, not in the primary flow.

Each new prompt continues the visible session. The adapter may map turns to internal
mission/run records, but that implementation detail must not fracture the conversational UX.

### 3.4 Permission required

A blocking approval appears inline at the point of the relevant tool call and, when the sidebar
is open, in the owned queue. It shows:

- requested action and trusted risk class;
- redacted arguments and normalized target;
- workspace/project boundary;
- server-authored policy reason and source;
- once/session/durable choices when permitted;
- deny and expiry behavior.

Keyboard focus moves deliberately to the decision. Foreign, stale, expired, terminal, or
hardline-denied requests never expose an allow action.

### 3.5 Settings and operational views

Provider settings, session history, missions, permissions, context, and diagnostics are
overlays, drawers, or command-palette destinations. They do not permanently occupy the
conversation canvas.

## 4. Information architecture

### Primary surface

- Transcript
- Composer
- Current agent/mode/model
- Current workspace
- Current permission profile
- Active work/interrupt state

### Contextual sidebar

- Session identity and context use
- Loaded project/operator instructions
- Active retrieval sources
- Subagents and tasks
- Owned pending approvals
- MCP/tool connectivity

The sidebar is hidden on first launch, optional on wide terminals, and an overlay on narrow
terminals.

### Secondary overlays

- Provider and authentication
- Model selection
- Permission profile
- Session/history switcher
- Mission/run inspector
- Command palette
- Help and diagnostics

## 5. Interaction contract

- The composer is focused at launch and after every completed turn.
- `Enter` submits; `Shift+Enter` or a configurable equivalent inserts a newline.
- `Esc` cancels an overlay or returns focus to the composer.
- `Ctrl+C` first cancels active agent work, then exits only when idle or deliberately repeated.
- `Tab` changes the agent mode/focus only when that action is visible and understandable.
- `/` opens commands; `@` attaches files/context; `$` addresses a subagent or task.
- Settings, history, and permission shortcuts remain discoverable in the footer and command
  palette.
- Mouse support may complement, never replace, complete keyboard operation.

Exact bindings may adapt to BubbleTea and terminal limitations, but the behavior above is the
acceptance contract.

## 6. Agent and provider behavior

The TUI remains a thin adapter over the Rust gateway and shared Python runtime. It must not gain
a second policy engine, provider resolver, permission store, agent loop, or conversation
database.

Before accepting a prompt, the UI obtains an explicit execution readiness state:

- `live`: selected provider/auth can execute;
- `unconfigured`: operator action is required;
- `degraded`: selected provider failed and remediation is available;
- `mock`: explicitly enabled development mode.

Availability alone does not silently change the selected provider. The operator chooses or
confirms Codex OAuth, Claude Code, API key, or FreeLLMAPI. Once chosen, the same selection is
visible in the composer and server-authored run provenance.

The visible conversation is one surface session. Reconnect/resume restores transcript,
workspace, model/provider, permission profile, cursor, and active/terminal work without
duplicating a turn.

## 7. Visual direction

The reference quality is MiMoCode’s hierarchy, calm, density, and chat-first transition—not its
name, logo, assets, copy, or exact trade dress.

ATLAS should use:

- a near-black full-canvas background;
- restrained Electric Violet, Cyber Blue, and semantic status accents;
- one strong composer surface rather than several equal boxes;
- generous negative space while idle and efficient density while active;
- subtle ATLAS-native ambient detail that never competes with text;
- consistent alignment, readable wrapping, and stable terminal resize behavior;
- ASCII-safe and no-color fallbacks with the same information hierarchy.

The visual system must remain usable at 80×24 and become richer—not merely wider—on large
terminals.

## 8. Release-path integrity

The executable launched by `atlas` is part of the tested product.

Future implementation must:

- build the source-checkout executable during the verification workflow;
- expose a version/build commit in the TUI and `--version`;
- fail verification when the resolved executable predates or differs from tested source;
- test launcher resolution order using the actual built artifact;
- prove retired route strings are absent from the resolved binary;
- keep installed and source-development paths behaviorally identical.

`go test ./...` and `go build ./...` without replacing the resolved executable are insufficient
release evidence.

## 9. Acceptance criteria

The redesign is accepted only when:

1. A new operator can type and submit without learning a compose shortcut.
2. No real-provider configuration produces onboarding, never a misleading agent reply.
3. A configured provider completes a real conversational turn with visible streaming.
4. A second prompt continues the same visible session.
5. Tool, retrieval, diff, subagent, failure, cancellation, and completion events render inline.
6. An owned permission can be approved or denied entirely by keyboard at the relevant tool call.
7. Stale or foreign approvals never appear actionable.
8. Idle, active, permission-blocked, failed, and resumed states match the chat-first hierarchy.
9. 80×24 ASCII, standard Windows Terminal, and wide-terminal snapshots remain legible.
10. Interactive Windows Terminal UAT confirms typing, streaming, resize, focus, `Ctrl+C`,
    reconnect, settings, and permission behavior.
11. The executable resolved by `atlas` is the exact artifact covered by tests and static scans.
12. No new runtime/framework is introduced; BubbleTea/Bubbles/Lipgloss remain sufficient.

## 10. Non-goals

- Copying MiMoCode source, branding, decorative assets, or exact screen composition.
- Moving runtime, provider, policy, or broker authority into Go.
- Making every cockpit/mission-management feature permanently visible.
- Adding a terminal graphics framework, embedded browser, or parallel message bus.
- Hiding model/provider failure behind optimistic UI.
- Treating a beautiful static snapshot as proof of real agent interaction.

## 11. Deferred implementation shape

When implementation is authorized, plan it as gated slices:

1. Release-artifact integrity and failing executable-level tests.
2. Provider readiness/onboarding and prohibition of implicit mock conversation.
3. Chat-first shell, focused composer, responsive transcript, and contextual sidebar.
4. Persistent session/turn flow over existing shared contracts, extending contracts only where
   continuation cannot be represented honestly.
5. Inline tools, permissions, subagents, context, commands, and operational overlays.
6. Snapshot, real-provider, real-terminal, cancellation, reconnect, and accessibility UAT.

No slice is complete solely because its API contract or snapshot test passes.
