# L2 ATLAS Legacy Consolidation Map

Date: 2026-06-04

## Purpose

Consolidate useful ideas/features from existing L2 Atlas-family repos into one coherent L2 ATLAS product without blindly merging code.

## Source repos inspected in this pass

- `C:/Users/Davi/Desktop/Projects/L2-Atlas`
- `C:/Users/Davi/Desktop/Projects/L2-atlas-hermes`

## L2-Atlas useful assets

### 1. Mission Control / Markdown OS

Existing idea:

- Markdown/Obsidian as human-editable mission surface.
- `L2_MISSION_CONTROL.md` with explicit `@atlas` tasks.
- ATLAS reads, proposes, executes, updates task state, logs execution.

How it maps into new L2 ATLAS:

- Becomes `wiki + missions` layer.
- Markdown remains a first-class interface, but the new cockpit UI becomes the main visual surface.
- The same mission model should exist in DB and Markdown, with sync rules.

Import classification: **core concept + possible parser/runtime donor**.

### 2. Safe local execution policies

Existing implementation:

- `WorkspacePolicy`
- `CommandPolicyEngine`
- `PowerShellExecutor`
- `JsonlLogger`
- deterministic safe command execution;
- blocked-command/security tests.

How it maps:

- Becomes part of `services/agent-runtime` or `packages/atlas-core/policies`.
- Needs adaptation from Windows/PowerShell-only to cross-platform policy abstraction.
- Hermes already has approval/security primitives; ATLAS should add product-grade policy/audit model around them.

Import classification: **module donor**.

### 3. JSONL logging / observability

Existing implementation:

- execution logs in JSONL;
- command, stdout, stderr, exit code, duration, timestamp.

How it maps:

- Becomes `AuditEvent`, `ToolCall`, `RunEvent` schema.
- Must be displayed in cockpit.
- Must support export and forensic review.

Import classification: **module donor**.

### 4. Interactive shell / CLI harness

Existing implementation:

- `atlas shell`
- `atlas chat`
- `/status`, `/context`, mission commands.

How it maps:

- New L2 ATLAS can preserve CLI as power-user/operator interface.
- Web cockpit is primary for market; CLI remains useful for local/dev mode.

Import classification: **module donor / dev interface**.

### 5. Skills registry

Existing implementation:

- local skill examples;
- skill manifest/registry/loader.

How it maps:

- Merge conceptually with Hermes skills.
- Avoid building a second incompatible skill system.
- ATLAS should define a skill/procedure layer that can wrap Hermes skills, GSD and imported skills, and L2-specific runbooks.

Import classification: **concept donor**.

### 6. Pulse / heartbeat

Existing implementation:

- Mission Control pulse/heartbeat loop.
- `atlas heartbeat once`.

How it maps:

- Becomes `services/pulse-runtime`.
- Generalizes beyond Mission Control: repo state, inboxes, deadlines, integrations, CRM, wiki health.

Import classification: **core concept donor**.

### 7. Voice / STT / TTS roadmap

Existing spec includes future:

- wake word;
- local STT;
- TTS;
- Whisper / Parakeet / ONNX;
- DirectML/ONNX acceleration where viable.

How it maps:

- Becomes `voice-interface` module after Operator Cockpit MVP.
- Should integrate with Hermes STT/TTS providers first.
- Real-time STT and seamless overlays become premium/native-client features, not first web MVP.

Import classification: **roadmap / research track**.

### 8. UI overlays / seamless native interaction

Existing user vision:

- native Linux agent;
- UI overlays;
- seamless interaction;
- real-time model/STT interaction;
- visual ideas from L2 Atlas family.

How it maps:

- Create future `apps/desktop-overlay` or `services/native-shell` track.
- Initial product should define contracts first: command palette, overlay events, capture context, action suggestions.
- Do not block web cockpit MVP on overlay work.

Import classification: **future module / differentiator**.

## L2-atlas-hermes useful assets

### 1. Role split

Existing model:

- ATLAS = reasoning, policy, operating layer.
- Hermes = local execution substrate: tools, skills, memory, scheduling, messaging, file ops.
- L2-BOT = Discord management harness.

This is exactly the right foundation for the new product.

Import classification: **architecture rule**.

### 2. Recovery/snapshot discipline

Existing model:

- sanitized operating model;
- restore runbooks;
- project pointers;
- skill indexes;
- redacted config notes;
- encrypted snapshots only with approval.

How it maps:

- Becomes `Admin / Recovery / Export` product module.
- Critical for trust: no raw Hermes DB dumps in product repo.

Import classification: **security/recovery module donor**.

## Consolidation decision

The new L2 ATLAS should absorb **concepts and selected modules**, not entire old repos.

Recommended extraction order:

1. Mission model and task-state contracts.
2. Audit/log schemas.
3. Policy engine concepts.
4. Pulse/heartbeat loop.
5. Hermes role-split/recovery model.
6. Skill/runbook registry concepts.
7. Voice/overlay specs as future track.

## Do not import yet

- raw runtime logs;
- secrets;
- old session databases;
- Windows-specific PowerShell executor as-is;
- voice/overlay code before interface contracts exist;
- UI experiments without product design review.
