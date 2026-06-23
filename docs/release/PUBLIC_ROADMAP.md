# ATLAS Public Roadmap

> **ATLAS v0.1 — Open Research Preview.** This roadmap is directional, not a commitment.

**DRAFT — operator reviews before publishing (e.g. to GitHub Discussions / README).**

## Shipped in v0.1

- Mission control + run lifecycle (native + local Claude Code runtimes)
- Audit-first event bus + live SSE stream + cross-run Ledger
- Artifact persistence + LLM Wiki (Codex) with provenance, FTS5 + semantic search
- Memory router (budget-aware, secret-redacted) + model registry/task-class routing
- Rust API gateway (read=SQLite / write=CLI, D-022)
- Web cockpit: Observatory, Missions, Runs, Ledger, Codex, Models, Integrations, System
- Extensible Tool Manifest v0 (manifest + adapter, policy chokepoint, approval-gated writes)
- Golden workflows: Repo Triage, Research Brief, approval-gated Self-Review + quality gate

## Near-term candidates (post-v0.1, unordered, subject to feedback)

- **Live-LLM golden runs** beyond mock-mode determinism (eval harness for non-deterministic output)
- **`web_fetch`-backed Research Brief** (public-web research variant, SSRF-guarded)
- **Cockpit polish:** ⌘K command palette, a dedicated Artifact Browser surface
- **Gateway endpoints** to retire interim client-side fan-outs (`/v1/runs`, `/v1/audit/events`, `/v1/integrations`)
- **More tool adapters** on the Manifest v0 surface (community-contributable)
- **Foundation de-brand** (hermes→atlas) completion

## Longer-horizon (paused during the wedge)

- Native operator shell (Tauri 2 + PTY), ATLAS TUI, owned auth store (v1.1, paused)
- CRM via Twenty, Pulse monitor, STT/TTS voice, floating run-status HUD (v2.0, planned)

## How to influence this

Open a GitHub Discussion or issue with your use case. v0.1 is explicitly a feedback-seeking
preview around **auditability, reliability, and extensibility**.
