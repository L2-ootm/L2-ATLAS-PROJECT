# Native App Strategy — Rust First

## Decision

L2 ATLAS should not use a bloated Electron-first desktop stack.

The desktop/native layer should be **Rust-first**, fast, low-latency, and designed like a serious local operator runtime.

## Product surfaces

ATLAS has multiple surfaces, each optimized for its job:

| Surface | Purpose | Preferred stack |
|---|---|---|
| CLI/TUI | developer/operator power interface | enhanced Hermes CLI + Rust/Python where appropriate |
| WebUI | perfect cockpit/dashboard | SvelteKit/Svelte 5 — see D-006 and docs/research/WEBUI_STACK_SPIKE.md |
| Native desktop | seamless local app, overlay, voice, hotkeys, OS context | Rust-first native app |
| Server/API | workspace/runtime backend | enhanced Hermes Python foundation + ATLAS services |
| Mobile later | monitoring/approval/inbox | later, not MVP |

## Desktop stack preference

Preferred investigation order:

1. Rust native app with `egui`, `iced`, `slint`, or custom `wgpu` UI.
2. Rust backend + very thin webview only if it keeps performance and UX excellent.
3. Tauri only if it behaves as a lightweight shell and does not compromise UX.
4. Electron is a negative baseline, not the default.

## Why Rust native

- lower memory footprint;
- faster startup;
- better OS integration;
- reliable global hotkeys;
- lower-latency overlays;
- better background daemon story;
- stronger distribution story for serious local software;
- fits future Linux/Windows native runtime.

## Native capabilities target

- global command palette;
- real-time STT control;
- local wake/hotkey activation;
- floating overlay / sidecar UI;
- approval prompts over current work;
- run-status HUD;
- local context capture with explicit permission;
- OS notifications;
- background daemon supervisor;
- secure local IPC with ATLAS runtime.

## WebUI standard

The WebUI must be excellent, not generic admin CRUD.

It should feel like:

- mission control;
- AI operations dashboard;
- knowledge cockpit;
- agent observability console;
- CRM/inbox/workflow command center.

The WebUI is the best surface for complex dashboards, graphs, settings, CRM, source review, and audit logs.

## Native vs WebUI boundary

Native desktop handles immediacy:

- voice;
- overlay;
- hotkeys;
- OS context;
- notifications;
- quick approvals.

WebUI handles depth:

- dashboards;
- mission design;
- wiki navigation;
- CRM;
- run history;
- integrations;
- analytics.

## Implication for MVP

Do not build native desktop first unless the runtime loop is ready.

MVP order:

1. Enhanced Hermes/ATLAS runtime.
2. WebUI cockpit.
3. Wiki/runtime/audit.
4. Rust native sidecar spike.
5. Real-time STT/overlay module.

## Research required

Create a dedicated research output comparing:

- Rust `egui`;
- Rust `iced`;
- Slint;
- Tauri thin shell;
- custom `wgpu`;
- system tray/global hotkeys;
- Windows/Linux overlay APIs;
- audio capture/STT pipelines;
- secure IPC patterns.
