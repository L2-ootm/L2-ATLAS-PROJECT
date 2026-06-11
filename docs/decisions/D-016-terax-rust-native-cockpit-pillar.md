# D-016 — Terax as Rust-native desktop cockpit pillar

Date: 2026-06-08
Status: Accepted as reference pillar, not direct product adoption

## Decision

ATLAS will treat Terax AI as a major reference pillar for the native desktop/operator cockpit layer.

Terax is not the ATLAS runtime, brain, memory layer, CRM, or knowledge engine. It is a high-signal donor/reference for the local-first, Rust-backed, lightweight desktop surface that ATLAS ultimately needs.

## Rationale

Terax aligns with several ATLAS architectural instincts:

- Rust/Tauri native shell instead of Electron-style bloat.
- Lightweight binary and low idle/runtime footprint as a product constraint.
- Native PTY control for real operator execution.
- Cross-platform Windows/Linux/macOS/WSL handling.
- AI as a native primitive, not a bolt-on chat panel.
- Local-first provider configuration and OS keychain storage.
- Approval-gated file/shell/agent tooling.
- Integrated terminal, editor, git, file explorer, and web-preview surfaces.

This strongly supports the ATLAS direction: fast local operator cockpit, audit-first, policy-governed, and able to run real tasks without turning into a bloated web app.

## Relationship to Odysseus

Odysseus and Terax cover different reference zones:

- Odysseus: broad self-hosted AI workspace, product concepts, threat-model lessons, admin/non-admin capabilities, multi-surface operations, cookbook/integration ideas.
- Terax: Rust-native lightweight desktop implementation, PTY/session mechanics, local operator surfaces, keychain/security patterns, cross-platform shell details.

Combined lesson: ATLAS should not copy either project wholesale. ATLAS should combine Odysseus' operational/workspace ambition with Terax's native, lightweight, Rust-backed execution surface.

## ATLAS adaptation

ATLAS should rebuild these concepts in its own terms:

1. Native cockpit shell
   - Tauri/Rust or equivalent Rust-first shell.
   - Local IPC boundary with explicit capabilities.
   - Windows-first verification because the primary development host is Windows.

2. Operator execution surfaces
   - Terminal sessions, mission run panel, artifact/file context, approval prompts, git/diff viewer, local preview.
   - These surfaces must emit ATLAS AuditEvents and attach artifacts to runs.

3. Policy and credential model
   - OS keychain for credentials.
   - Workspace authorization before file, shell, git, or network actions.
   - No direct credential exposure to webview UI state.

4. Runtime boundary
   - ATLAS runtime remains mission/run/wiki/audit oriented.
   - Terax-style UI surfaces call ATLAS APIs/events, not the other way around.

## Risks

- Direct vendoring would inherit fast-moving upstream churn.
- Terminal-first UX is not sufficient for ATLAS' mission-first cockpit.
- Desktop permissions can become dangerous without formal capability scoping.
- Apache-2.0 attribution/NOTICE obligations must be preserved if code is reused.

## Follow-up

Create a Phase 4.5 / native cockpit architecture bridge before Phase 6 if Claude is being used to consolidate donor projects. The phase should document Terax + Odysseus together, update architecture docs, and produce a concrete Phase 8 cockpit spike plan.
