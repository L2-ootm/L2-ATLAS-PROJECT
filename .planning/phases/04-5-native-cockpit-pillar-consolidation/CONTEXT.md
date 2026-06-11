# Phase 4.5: Native Cockpit Pillar Consolidation

**Phase number:** 4.5 (architecture bridge — not a full build phase)
**Status:** Complete
**Date:** 2026-06-08

---

## Purpose

Lock the native cockpit direction before Phase 6/7/8 proceed. Phase 8 was previously specified as a generic web cockpit. That framing must be corrected before wiki, API, and cockpit build phases accumulate decisions that are hard to reverse.

This is not a build phase. It produces architecture documents, deep audits, and a strategic brief that Phase 8 planning must use as input.

---

## Trigger

Terax AI was identified as a high-signal reference for a Rust-native desktop operator cockpit. Odysseus was identified as a product/security reference. Both require a formal audit before Phase 8 uses them as design input. Without this bridge, Phase 8 would likely default to a generic SvelteKit web app — correct for Phase 7 API consumption but insufficient for the native operator shell ATLAS requires.

---

## Key Decisions Already Locked

- **D-005**: Rust-first native, no Electron.
- **D-006**: SvelteKit/Svelte 5 for the web UI layer — remains valid for cockpit web surfaces.
- **D-016**: Terax accepted as Rust-native desktop cockpit reference pillar.

---

## Pillars

| Pillar | Role |
|--------|------|
| Terax AI (`crynta/terax-ai`) | Implementation reference: Tauri/Rust shell, PTY/session, keychain, approval flows, cross-platform native |
| Odysseus (`pewdiepie-archdaemon/odysseus`) | Product/security reference: workspace ambition, threat model, admin/non-admin capability discipline |
| Hermes/OpenClaw/GSD | Runtime execution: tools, skills, orchestration, workflow discipline |
| ATLAS core | Mission/run lifecycle, audit event bus, policy, wiki/memory — the brain that does not change |

---

## What This Phase Does NOT Do

- Does not vendor Terax.
- Does not copy Odysseus code.
- Does not start Phase 6, 7, or 8 implementation.
- Does not broaden scope to CRM/Pulse/channels.
- Does not touch running services or secrets.

---

## Outputs

1. `docs/research/TERAX_DEEP_AUDIT.md` — full Terax code audit with ATLAS adaptation map.
2. `docs/research/ODYSSEUS_AUDIT.md` — Odysseus architecture and product audit.
3. `docs/architecture/NATIVE_COCKPIT_STRATEGY.md` — definitive native cockpit strategy for Phase 8.
4. `.planning/phases/08-cockpit/CONTEXT.md` updated with native-first direction.
5. STATE.md corrected (stale "Execute Phase 5 Wave 0" language removed).
6. `.planning/phases/04-5-native-cockpit-pillar-consolidation/` planning artifacts.
