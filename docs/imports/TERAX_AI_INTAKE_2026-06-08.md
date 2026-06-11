# Terax AI Intake for ATLAS

Source: https://github.com/crynta/terax-ai
Cloned commit inspected: `8200938397ec31f89119bec808a3355d80e90d0e`
License: Apache-2.0
Stack: Tauri 2, Rust, React 19, TypeScript, Vite, xterm.js, CodeMirror 6, Vercel AI SDK v6, Tailwind v4, shadcn/ui, Zustand

## Positioning

Terax is a lightweight terminal-first AI-native development workspace. It should not be adopted as-is. It is useful as a reference/base donor for an ATLAS cockpit that needs local-first operator tooling, native terminal control, agent execution surfaces, file/editor context, provider routing, and approval-gated automation.

## ATLAS-relevant pillars

1. Native operator shell
   - Multi-tab PTY terminal with WebGL rendering.
   - Native PTY backend via Rust and `portable-pty`.
   - Windows, Linux, macOS, and WSL awareness.
   - Shell integration for cwd and command-boundary markers.

2. Agent execution surface
   - AI side-panel with project context, files, slash commands, voice, and agentic tools.
   - File read/write/edit, grep/glob, bash execution, plan mode, approval gating, background processes.
   - Custom agents with system prompts and restricted tool subsets.
   - Project memory through `TERAX.md`, analogous to `AGENTS.md` and `CLAUDE.md`.

3. Local-first desktop shell
   - Tauri 2 architecture keeps OS access in Rust and UI in React.
   - API keys stored in OS keychain, not browser storage.
   - No telemetry and no account requirement.
   - Small binary target, with performance as a product constraint.

4. Development cockpit primitives
   - Embedded CodeMirror editor.
   - File explorer with direct context attachment to AI.
   - Source control panel, staged changes, commit graph, per-file diffs.
   - Web preview for local dev servers.

5. Security and permissions pattern
   - IPC boundary between webview and Rust commands.
   - Workspace authorization registry for shell/git/spawn operations.
   - SSRF guard for AI HTTP proxy.
   - Secret-path deny list and OS keychain use.
   - Approval flow for agent tools.

## What to rebuild in ATLAS terms

- Keep the concept of a native operator cockpit, not the Terax product boundary.
- Replace `TERAX.md` memory with ATLAS source registry, compiled wiki, memory policies, and mission logs.
- Replace generic AI side-panel with mission/run orchestration, audit trails, model routing, and persistent task state.
- Keep terminal/editor/git/web-preview primitives as local execution surfaces.
- Treat agent tools as ATLAS-governed capabilities with policies, budgets, approvals, and artifact capture.
- Preserve keychain/local-first principles for credentials.
- Rebuild branding, UX hierarchy, and architecture around ATLAS operations, not terminal-only developer workflow.

## Candidate extraction map

| Terax area | ATLAS use |
| --- | --- |
| `src-tauri/src/modules/pty` | Native PTY/session model, shell markers, Windows ConPTY lessons |
| `src-tauri/src/modules/shell` | One-shot and persistent agent shell patterns, background logs |
| `src-tauri/src/modules/workspace.rs` | Workspace authorization and WSL/local environment switching |
| `src-tauri/src/modules/net.rs` | Provider HTTP proxy and SSRF guard pattern |
| `src-tauri/src/modules/secrets.rs` | OS keychain credential storage pattern |
| `src-tauri/src/modules/git` | Source control command surface and parsing patterns |
| `src/modules/terminal` | Mounted terminal lifecycle and background streaming UX |
| `src/modules/editor` | AI diffs and editor panes |
| `src/modules/source-control`, `src/modules/git-history` | Commit/diff cockpit primitives |
| `src/modules/agents` | Agent notification and external coding-agent detection concepts |
| `src/modules/settings` | Provider/settings UX pattern |

## Integration recommendation

Use Terax as a donor/reference pillar for an ATLAS desktop cockpit spike, not as the foundation runtime. ATLAS should remain a mission-oriented platform with Hermes/OpenClaw-style runtime concepts, wiki/memory, skills, channels, cron, and subagents. Terax contributes the native desktop/operator surface and cross-platform PTY lessons.

Recommended path:

1. Create an ATLAS cockpit spike with Tauri 2 + React + Rust.
2. Prototype four minimal surfaces: terminal, mission log, file context, and agent run panel.
3. Port only patterns after security review, not whole modules blindly.
4. Keep a divergence document for every borrowed idea: source, adapted design, ATLAS-specific changes, and verification.
5. Validate Windows first because the primary development host is Windows and Terax has explicit ConPTY/WSL handling.

## Risks

- Terax is young and fast-moving, so direct vendoring would create maintenance drag.
- Product scope is terminal-first, while ATLAS scope is mission/operations-first.
- Desktop packaging/security details require careful review before real credentials or broad filesystem access.
- Apache-2.0 is permissive, but attribution and NOTICE obligations must be preserved if code is reused.

## Immediate ATLAS planning decision

Classify Terax as: **desktop cockpit and native operator-surface pillar**.

Do not classify it as: full ATLAS runtime, CRM, memory layer, or knowledge engine.

## Rust/lightweight significance

Terax is especially valuable because it is already built in the direction ATLAS wanted: Rust-backed, native, small, fast, local-first, and cross-platform. This matters more than the feature checklist alone. The implementation philosophy is aligned with ATLAS' anti-bloat constraint:

- OS access stays in Rust/Tauri instead of browser code.
- PTY/session handling is native and performance-sensitive.
- The app treats small binary size and low overhead as product requirements.
- Windows/WSL handling is not an afterthought.
- Credentials live in the OS keychain.
- AI/tooling is integrated without requiring a cloud account or telemetry posture.

This makes Terax a stronger reference than a generic Electron AI workspace.

## Combined Terax + Odysseus read

Terax and Odysseus should be treated as complementary pillars:

- **Terax:** native Rust desktop cockpit mechanics, terminal/editor/git/file/provider surfaces, lightweight execution shell.
- **Odysseus:** broad AI workspace ambition, threat-model lessons, admin/non-admin capability separation, untrusted-context discipline.

ATLAS should combine the two at the concept level only:

```text
Odysseus ambition + Terax native speed + Hermes tooling + ATLAS audit/policy/wiki
```

The deeper combined strategy is documented in:

`docs/architecture/ATLAS_NATIVE_COCKPIT_PILLARS_TERAX_ODYSSEUS.md`

Decision record:

`docs/decisions/D-016-terax-rust-native-cockpit-pillar.md`
