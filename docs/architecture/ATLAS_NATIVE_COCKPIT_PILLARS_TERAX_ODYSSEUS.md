# ATLAS Native Cockpit Pillars — Terax + Odysseus

Date: 2026-06-08

## Executive conclusion

ATLAS has a stronger architecture path now:

- **Hermes/OpenClaw/GSD** provide agent runtime, skills, workflows, tools, orchestration, and execution discipline.
- **ATLAS core** provides mission/run lifecycle, audit events, policy, wiki/memory, source registry, and product-specific operating model.
- **Odysseus** provides reference ambition for a broad local AI workspace and security/threat-model lessons.
- **Terax** provides the strongest current reference for a Rust-native, lightweight, AI-native desktop operator surface.

The combination is extremely valuable because it avoids the two common failures:

1. a powerful AI workspace that becomes bloated and unreliable;
2. a fast terminal app that never becomes a real mission-control system.

ATLAS should combine the best lessons: Odysseus-level ambition, Terax-level native performance, Hermes-level operational tooling, and ATLAS-level audit/policy/memory.

## Why Terax changes the cockpit direction

Terax is already close to the implementation style ATLAS wanted:

- Rust/Tauri backend.
- Native PTY backend with `portable-pty`.
- Cross-platform Windows/Linux/macOS and WSL awareness.
- Lightweight binary target and dependency discipline.
- Terminal-first operator surface.
- Embedded CodeMirror editor.
- File explorer, git/source-control, commit graph, diffs.
- Web preview for local servers.
- AI provider configuration, local/offline models, BYOK, keychain storage.
- Agentic tools with approval gating.
- Project memory file equivalent to `AGENTS.md`/`CLAUDE.md`.

For ATLAS, this means the desktop cockpit does not need to start from a blank theoretical UI. It can be designed around already-proven primitives, but rebuilt around ATLAS mission/run semantics.

## Why Odysseus still matters

Odysseus remains useful because it explores the broader AI workspace surface:

- self-hosted AI workspace concepts;
- admin vs non-admin capabilities;
- multiple external surfaces treated as untrusted context;
- cookbook/integration patterns;
- threat-model discipline;
- local-first operational ambition.

But Odysseus also shows what ATLAS must avoid:

- broad surface area before operational stability;
- web/service-oriented sprawl;
- shell/filesystem power without enough sandboxing;
- context/prompt bloat;
- layout/runtime fragility.

## Combined design principle

ATLAS native cockpit should be:

```text
Odysseus ambition + Terax native speed + Hermes tooling + ATLAS audit/policy/wiki
```

Not:

```text
Terax fork + Odysseus clone + random AI tools
```

## Product boundary

### ATLAS brain/runtime

Owns:

- Mission model.
- Run lifecycle.
- Audit event bus.
- ToolCall, Artifact, Source, WikiPage records.
- Policy decisions.
- Model/provider routing decisions.
- Wiki/memory updates.
- Skills and workflow execution.
- Cron/subagent lifecycle.

### Native cockpit shell

Owns:

- Local terminal panes.
- Mission/run views.
- Approval prompts.
- File context picker.
- Git/diff viewer.
- Local preview pane.
- Notifications.
- Provider/settings UI.
- Native credential UX.

### IPC/API bridge

Owns:

- Typed local communication between cockpit and ATLAS runtime.
- Capability-scoped actions.
- Correlation IDs.
- Backpressure/event streaming.
- Current-user-only local transport security.

## High-value Terax extraction targets

| Terax concept | ATLAS adaptation |
| --- | --- |
| Rust/Tauri shell | Native cockpit shell with ATLAS branding and mission-first UX |
| Native PTY sessions | Operator terminal panes tied to Run IDs and AuditEvents |
| Shell markers/cwd tracking | Run-aware command timeline and artifact capture |
| WSL/local workspace switching | Workspace/environment policy dimension |
| OS keychain | Provider and external-service credential storage |
| AI tool approval flow | ATLAS approval tickets and audit events |
| File explorer context attach | Source/artifact attachment to missions/runs/wiki |
| CodeMirror editor/diffs | Artifact/code review and AI edit review surface |
| Git panel/commit graph | Evidence/source-control pane for implementation runs |
| Web preview | Local app preview tied to validation runs |
| Agent notifications | Run/subagent attention system |

## High-value Odysseus extraction targets

| Odysseus concept | ATLAS adaptation |
| --- | --- |
| Threat model | Formal ATLAS cockpit threat model before broad desktop powers |
| Admin/non-admin capabilities | Capability profiles for operator, agent, local services |
| External context hardening | Untrusted-source labels and prompt-injection controls |
| Workspace/cookbook ambition | Future curated module catalog, not MVP bloat |
| Self-hosted workspace pattern | Local-first deployment posture |

## Phase 4.5 purpose

Phase 4.5 should act as an architecture bridge, not a full build phase.

It should produce:

1. `docs/architecture/NATIVE_COCKPIT_STRATEGY.md`
2. `docs/research/TERAX_DEEP_AUDIT.md`
3. `docs/research/ODYSSEUS_AUDIT.md` if missing or incomplete
4. `docs/decisions/D-016-terax-rust-native-cockpit-pillar.md` updates if needed
5. `.planning/phases/08-cockpit/08-RESEARCH.md` or equivalent Phase 8 research input
6. A concrete cockpit spike plan with minimum surfaces:
   - mission list/detail;
   - run timeline/audit stream;
   - terminal pane bound to a run;
   - approval prompt surface;
   - file/artifact context panel.

## Non-negotiables

- Do not vendor Terax blindly.
- Do not copy Odysseus architecture blindly.
- Do not expand CRM/Pulse/channels in this phase.
- Do not start Phase 8 implementation yet unless explicitly requested.
- Preserve current ATLAS core direction: audit-first, mission-first, policy-governed, Rust-first where permanence matters.
- If any source code is copied, preserve license obligations and record exact source path/commit.

## Strategic verdict

Terax plus Odysseus materially strengthens the ATLAS plan.

The correct move is a short Phase 4.5 architecture bridge that locks the native cockpit strategy before Phase 6/7/8 proceed too far. Phase 6 can still build wiki runtime, but Phase 8 should no longer be treated as a generic web cockpit. It should become a Rust-native operator cockpit strategy with web UI pieces only where they serve the native shell.
