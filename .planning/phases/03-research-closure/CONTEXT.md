# Phase 3: Research Closure — WebUI Spike & CRM Intake

**Phase number:** 3
**Name:** Research Closure — WebUI Spike & CRM Intake
**Status:** Pending

---

## Goal

Close the two open research gaps (D-006 WebUI framework, D-010 CRM/Pulse research) so no build phase encounters an unresolved architectural fork.

---

## Requirements Covered

| REQ-ID | Description |
|--------|-------------|
| RESEARCH-01 | WebUI stack spike document comparing SvelteKit/Svelte 5 vs Next.js/React, ending in concrete recommendation (resolves D-006) |
| RESEARCH-02 | CRM/Pulse/Channels deep-dive research document with open questions and MVP boundary defined |

---

## Success Criteria

1. `docs/research/WEBUI_STACK_SPIKE.md` exists with scored comparison of SvelteKit/Svelte 5 vs Next.js/React against cockpit-specific criteria (realtime stream, L2 code reuse, bundle size, polish ceiling).
2. Spike ends in a concrete framework recommendation OR a defined 1-day build spike that would objectively decide it.
3. `NATIVE_APP_STRATEGY.md` no longer presupposes Next.js (C3 inconsistency patched).
4. `docs/research/CRM_PULSE_CHANNELS_DEEP_DIVE.md` exists with defined open questions, MVP boundary, and a research brief ready for a future deep-dive agent.
5. D-006 updated to "spike complete / recommendation: [framework]" or "spike required."

---

## Key Decisions Applicable

- **D-006** (open): WebUI framework — SvelteKit/Svelte 5 vs Next.js/React. This phase resolves it.
- **D-007** (locked): CRM is NOT first implementation surface — the deep-dive here scopes it for v2, not v1.
- **D-009** (locked): STT/TTS/overlay is not a first MVP blocker — do not scope it into this research.
- **D-010** (open): CRM/Pulse/Channels research missing. This phase produces the intake brief.
- **D-005** (locked): Desktop/native layer is Rust-first, no Electron — the WebUI spike must account for this (no bundling Electron as a path to desktop).
- C3 inconsistency: `NATIVE_APP_STRATEGY.md` previously presupposed Next.js — patch it as part of this phase.

---

## What NOT to Build

- Do not write any application code — this is a research and documentation phase only.
- Do not make a final CRM implementation decision — just define open questions and MVP boundary.
- Do not scope Pulse/heartbeat monitors for v1 — document them for v2 intake only.
- Do not build a prototype for either WebUI framework — the spike is a document comparison, not a running app.
- Do not resolve D-010 by designing a CRM schema — that is v2.0 work.
