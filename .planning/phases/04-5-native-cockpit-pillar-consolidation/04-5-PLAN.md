# 04-5-PLAN.md — Phase 4.5 Native Cockpit Pillar Consolidation

**Phase:** 4.5
**Type:** Architecture bridge — documentation and strategy only
**Date:** 2026-06-08

---

## Goal

Lock the native cockpit strategy before Phase 6/7/8 execution. Produce deep audits of Terax and Odysseus as ATLAS reference pillars, and publish a concrete native cockpit architecture strategy.

---

## Tasks

### Task 1 — Fix STATE.md planning drift

**Status:** Complete

The body of STATE.md contained stale language: "Next: Execute Phase 5 Wave 0 (`05-01-PLAN.md`) after committing/stashing research docs". Phase 5 is complete (4/4 plans). The body now correctly reads: "Next: Discuss and plan Phase 6 (LLM Wiki Runtime). Phase 4.5 architecture bridge complete."

---

### Task 2 — Create Phase 4.5 planning directory

**Status:** Complete

Created:
- `.planning/phases/04-5-native-cockpit-pillar-consolidation/CONTEXT.md`
- `.planning/phases/04-5-native-cockpit-pillar-consolidation/04-5-PLAN.md` (this file)
- `.planning/phases/04-5-native-cockpit-pillar-consolidation/04-5-VALIDATION.md`
- `.planning/phases/04-5-native-cockpit-pillar-consolidation/04-5-SUMMARY.md` (after completion)

---

### Task 3 — Terax deep audit

**Status:** Complete

Created `docs/research/TERAX_DEEP_AUDIT.md`.

Source: intake at `docs/imports/TERAX_AI_INTAKE_2026-06-08.md`, inspected commit `8200938397ec31f89119bec808a3355d80e90d0e`.

Coverage: license, stack, architecture, Rust/Tauri backend surface, frontend surface, PTY model, WSL/Windows notes, provider/keychain/security, ATLAS adaptation map, risks, final classification.

---

### Task 4 — Odysseus audit

**Status:** Complete

Created `docs/research/ODYSSEUS_AUDIT.md`.

Note: Odysseus repo was not cloned or deeply inspected. The audit is based on the reference note at `docs/research/ODYSSEUS_REFERENCE_NOTE.md`, project context, and architectural analysis. A commit SHA could not be pinned without a clone. The audit flags this limitation and classifies it accordingly.

---

### Task 5 — Native cockpit strategy

**Status:** Complete

Created `docs/architecture/NATIVE_COCKPIT_STRATEGY.md`.

Covers: ATLAS runtime boundary, native cockpit shell boundary, IPC/API bridge, capability model, credential/keychain policy, audit-event requirements, minimum Phase 8 cockpit surfaces, Windows-first validation, anti-bloat rationale.

---

### Task 6 — Phase 8 CONTEXT.md update

**Status:** Complete

Updated `.planning/phases/08-cockpit/CONTEXT.md` to reflect native-first direction. Phase 8 is no longer framed as a generic web cockpit only.

---

### Task 7 — Decision records

**Status:** Complete (no new decision required)

D-016 already captures the Terax reference pillar decision in full. No duplicate decision is warranted. D-015 covers FreeLLMAPI. No D-017 is needed for this phase.

---

### Task 8 — Validation

**Status:** Complete

- `python -m pytest packages/atlas-core/tests -q` → 33 passed
- `python -m pytest services/agent-runtime/tests -q` → 44 passed
- `git status --short` → only untracked docs and scripts; no regressions

---

## Constraints

- No vendoring of Terax or Odysseus.
- No Phase 6, 7, or 8 implementation.
- No CRM/Pulse/channels scope expansion.
- ATLAS core preserved: mission/run lifecycle, audit event bus, policy, wiki, Hermes/GSD discipline.
