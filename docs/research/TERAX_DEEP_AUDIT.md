# Terax AI — Deep Audit for ATLAS

**Date:** 2026-06-08
**Auditor:** Phase 4.5 architecture bridge
**Source repo:** https://github.com/crynta/terax-ai
**Inspected commit SHA:** `8200938397ec31f89119bec808a3355d80e90d0e`
**Audit method:** Source tree inspection via intake document and module-level analysis at pinned commit. Code not vendored.

---

## License

**Apache-2.0** (confirmed; all four ATLAS reference pillars carry permissive licenses — see note below)

**Reference pillar license summary (Phase 4.5, 2026-06-08 confirmation):**

| Pillar | License | Status |
|--------|---------|--------|
| Terax AI | Apache-2.0 | Confirmed at SHA `8200938…` |
| Odysseus | MIT | Confirmed at SHA `8449bae…` via GitHub API |
| Hermes Agent | MIT | Confirmed at SHA `e8b9369…` (Phase 1 audit) |
| FreeLLMAPI | MIT | Confirmed at SHA `43415fd` / current `bfea8a8…` |

All four pillars carry permissive licenses. No copyleft obligation on ATLAS as a product. Attribution required in distributions containing copied code.

Implications for Terax (Apache-2.0):
- Permissive. Allows use, modification, and redistribution in proprietary projects.
- Attribution required: any distributed product that incorporates Terax-derived code must include the original copyright notice and a copy of the Apache-2.0 license.
- NOTICE file: if Terax maintains a NOTICE file, its contents must be reproduced in ATLAS distributions.
- Patent grant included: contributors grant a patent license for their contributions.
- Action required before any code reuse: create `docs/legal/TERAX_NOTICE.md` recording the source SHA, Apache-2.0 attribution, and any copied paths.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Desktop shell | Tauri 2 |
| Backend language | Rust |
| Frontend language | TypeScript / React 19 |
| Build tool | Vite |
| Terminal renderer | xterm.js (WebGL renderer) |
| Code editor | CodeMirror 6 |
| AI SDK | Vercel AI SDK v6 |
| Styling | Tailwind CSS v4 |
| UI components | shadcn/ui |
| State management | Zustand |
| PTY backend | `portable-pty` crate (Rust) |
| Credential storage | OS keychain (via Tauri plugin) |

---

## Architecture Summary

Terax uses a standard Tauri 2 split architecture:

- **Rust backend** (`src-tauri/`): handles all OS-privileged operations — PTY spawning, shell execution, filesystem access, network proxying, keychain, workspace authorization.
- **React frontend** (`src/`): renders terminal panes, editor, file explorer, source control panel, agent side-panel, provider settings, and web preview.
- **IPC boundary**: frontend communicates to backend via Tauri `invoke()` commands. Backend pushes events to frontend via Tauri event system.
- **No server**: everything is local. No cloud dependency for core operation.

The product is terminal-first. The agent panel is a side-panel augmenting a terminal/editor workspace, not a mission-control system.

---

## Rust/Tauri Backend Surface Map

| Module | Location | Function |
|--------|----------|----------|
| PTY management | `src-tauri/src/modules/pty/` | Spawn PTY sessions via `portable-pty`. Handle ConPTY on Windows, Unix PTY on Linux/macOS. Shell detection, resize, cwd tracking via shell markers. Background process persistence. |
| Shell operations | `src-tauri/src/modules/shell/` | One-shot command execution (agent tools: bash, file ops). Persistent agent shell with background log capture. |
| Workspace auth | `src-tauri/src/modules/workspace.rs` | Per-workspace authorization registry. Controls which shell, git, spawn, and network operations are permitted. WSL/local environment switching. |
| Network/proxy | `src-tauri/src/modules/net.rs` | HTTP proxy for AI provider calls from the frontend. SSRF guard: only whitelisted endpoints allowed. Request logging for audit capability. |
| Secrets/keychain | `src-tauri/src/modules/secrets.rs` | Read/write to OS keychain (Windows Credential Store, macOS Keychain, libsecret on Linux). API keys never written to disk. |
| Git operations | `src-tauri/src/modules/git/` | Shell out to git CLI. Parse status, log, diff, staged changes. Commit, push, branch operations. |
| Plugin/extension | `src-tauri/` plugin surface | Standard Tauri plugin model. Capabilities declared in `tauri.conf.json`. |

### PTY/Session Model Notes

- Sessions are managed as Tauri-side state (Arc/Mutex map from session ID to PTY handle).
- Each PTY has: session ID, PID, shell type, cwd, resize channel, stdin/stdout channels.
- Shell marker integration: shell writes special OSC sequences or markers on prompt boundaries; Terax parses these to know command start/end, exit code, and new cwd. This enables run-aware command capture.
- Background processes: when a user starts a long-running command, Terax detaches and streams output to a background log, with a notification when the process finishes.
- On Windows: uses ConPTY via the `portable-pty` Windows backend. WSL is detected and session is created inside WSL via `wsl.exe` invocation with ConPTY tunneling.
- Resize events propagate correctly to both ConPTY (Windows) and Unix PTY (Linux/macOS).

### WSL/Windows Notes

- Terax explicitly handles WSL: workspace switching detects if the current project is inside a WSL path or a Windows path and adjusts shell invocation accordingly.
- ConPTY is used instead of WinPTY — ConPTY is the modern Windows API introduced in Windows 10 1903 and is what Windows Terminal uses. This is the correct choice for ATLAS.
- File path translation between Windows and WSL paths is handled at the workspace level.
- Git credentials: Windows Credential Manager is used, which is shared with WSL Git when configured.

### Provider/Keychain/Security Notes

- API keys are stored in the OS keychain, not in app storage or environment variables.
- The frontend never directly holds an API key; it requests the backend to make provider calls.
- The net.rs SSRF guard maintains a per-workspace allowlist of permitted AI provider endpoints; arbitrary URLs cannot be proxied.
- Secret-path deny list: certain filesystem paths are blocked from being attached as file context (e.g., `.env`, SSH keys, keychain databases).
- Workspace authorization: each workspace has an authorization record that must be granted before shell/git/spawn operations proceed. This is analogous to ATLAS policy checks but without a persistent audit log.
- IPC surface: all Tauri commands are typed. The webview cannot execute arbitrary native code; it can only call declared commands.

---

## Frontend Surface Map

| Module | Location | Function |
|--------|----------|----------|
| Terminal | `src/modules/terminal/` | xterm.js terminal panes. Mounting, lifecycle, background stream UX. Multiple tabs. WebGL renderer for performance. |
| Editor | `src/modules/editor/` | CodeMirror 6 embedded editor. AI diff views. File open/save. |
| Source control | `src/modules/source-control/` | Staged/unstaged file list. Per-file diff viewer. Commit UI. |
| Git history | `src/modules/git-history/` | Commit graph. Branch visualization. Per-commit diff. |
| Agents | `src/modules/agents/` | Agent notification surface. External coding-agent detection. Agent run tracking. |
| Settings | `src/modules/settings/` | Provider configuration (API keys, model selection, local/remote). |
| AI side-panel | `src/` (root agent panel) | Chat/command interface. Project context, slash commands, voice input (if enabled), agentic tool display, approval prompts. |

---

## ATLAS Adaptation Map

| Terax concept | ATLAS adaptation | Priority |
|---------------|-----------------|----------|
| Tauri/Rust shell binary | ATLAS native cockpit binary. Rust backend, Tauri webview packaging, local IPC server | Phase 8 spike |
| `portable-pty` PTY sessions | Terminal panes in the cockpit, each bound to a Run ID and emitting AuditEvents | Phase 8 |
| Shell marker/cwd tracking | Run-aware command timeline: each command boundary → ToolCall record | Phase 8 |
| WSL/local switching | Workspace policy dimension: Windows vs WSL vs Linux paths, environment-scoped policy | Phase 8 |
| OS keychain (`secrets.rs`) | Provider credential storage. Never expose keys to webview state. | Phase 8 |
| AI tool approval flow | ATLAS ApprovalRequest/Grant/Deny with AuditEvent of kind `approval`. Richer than Terax: includes policy context, risk level, diff preview. | Phase 8 |
| File explorer context attach | Source/Artifact attachment to missions, runs, wiki pages | Phase 8 |
| CodeMirror editor/diffs | Artifact review surface and AI-edit confirmation pane | Phase 8 |
| Git panel/commit graph | Evidence/source pane for implementation runs | Phase 8 |
| Web preview | Local app preview for validation runs | Phase 8 |
| Agent notification | Run/subagent attention system | Phase 8 |
| SSRF guard (`net.rs`) | Restrict cockpit's outbound HTTP to ATLAS API loopback + explicitly whitelisted external endpoints | Phase 8 |
| Workspace auth registry | ATLAS workspace-scoped policy: before shell/file/git ops, check policy engine | Phase 4/5 already (policy.py) |
| `TERAX.md` project memory | Replace with ATLAS source registry, compiled wiki, mission logs, and policy files | N/A (already different) |
| Agent side-panel | Mission/run orchestration view, not generic AI chat | Phase 8 |

---

## What to Copy Conceptually

1. **Tauri 2 as the desktop packaging layer** — proven, non-Electron, WebView-based, Rust-backed. ATLAS should use the same model.
2. **`portable-pty` for PTY sessions** — production-proven, cross-platform, Windows ConPTY correct. Do not reimplement.
3. **OS keychain for all credentials** — the Terax pattern of never holding keys in frontend state is the correct policy for ATLAS.
4. **Per-workspace authorization registry** — enforce before any shell/git/network action, not after.
5. **SSRF guard on the AI proxy** — any outbound AI call goes through a backend proxy with URL allowlist, not directly from the webview.
6. **Shell marker integration for command boundary detection** — necessary for ATLAS run-aware command capture.
7. **Background process streaming UX** — ATLAS runs are long; the operator needs output streamed with a notification on completion.
8. **Typed IPC boundary** — all commands declared in Tauri capability config; webview cannot escape into arbitrary native code.

---

## What NOT to Copy

1. **Terax product architecture (terminal-first)** — ATLAS is mission-first. The terminal is a surface, not the product.
2. **Generic AI side-panel** — ATLAS does not want a chat panel. It wants mission/run orchestration with audit, policy, and state machine.
3. **`TERAX.md` project memory** — ATLAS has a superior memory model: compiled wiki, source registry, mission logs, and policy documents. No plain text "memory file".
4. **Developer-tool features** (web preview as primary feature, code editor as primary feature) — ATLAS uses these as supporting surfaces for execution runs, not as first-class product pillars.
5. **Zustand global state** — ATLAS cockpit state should be driven by the ATLAS API (SSE/WebSocket for live data), not by a client-side store that can drift from backend truth.
6. **Vercel AI SDK** — ATLAS model/provider routing lives in the ATLAS runtime (Python service), not in the frontend. The cockpit calls the ATLAS API, not provider APIs directly.
7. **Fast-moving upstream**: Terax is actively developed. Do not track it as a dependency. Audit at a pinned SHA, extract concept/pattern, rebuild in ATLAS.

---

## License/NOTICE Implications

- Apache-2.0 allows use in ATLAS (commercial or otherwise) without copyleft obligation.
- If any Terax source file is copied (even conceptually-adapted): create `docs/legal/TERAX_NOTICE.md`, record the original file path, the SHA, the copyright notice from the Terax repository, and the Apache-2.0 license reference.
- If Terax ships a NOTICE file at the inspected SHA, its contents must be reproduced in any ATLAS distribution that contains derived code.
- "Conceptually adapted" (pattern learned, then reimplemented) does not require attribution under Apache-2.0, but recording the source in a divergence document is good operational hygiene.

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Terax upstream moves fast; patterns become stale | Medium | Pin audit SHA; re-audit before Phase 8 implementation starts |
| Desktop permissions (PTY, filesystem, shell) are dangerous without formal capability scoping | High | ATLAS policy engine must gate all cockpit-initiated operations before execution |
| Windows ConPTY/WSL handling has edge cases (path translation, signal propagation) | Medium | Validate on Windows 11 + WSL2 before claiming Windows support in Phase 8 |
| Apache-2.0 NOTICE obligation missed | Low | Track in `docs/legal/TERAX_NOTICE.md` before any code is copied |
| xterm.js WebGL renderer has known performance regressions with large scrollback | Low | Set scrollback limit; offload scrollback storage to ATLAS audit log |
| Tauri IPC throughput not suitable for high-frequency streaming | Medium | Use SSE/WebSocket for audit event streams; use Tauri IPC only for control messages |

---

## Final Classification

**Classification: Rust-native desktop cockpit implementation reference pillar.**

- Use as: design reference, pattern donor, proof of concept for Tauri/Rust/PTY approach.
- Do not use as: ATLAS runtime, memory layer, plugin host, or vendored dependency.
- Re-audit at: the commit SHA pinned in Phase 8 plan before any code extraction.
- License gate: Apache-2.0. Attribution/NOTICE required if code is copied.
- Confidence in classification: High. The stack, architecture, and implementation philosophy are well-aligned with ATLAS native cockpit goals.
