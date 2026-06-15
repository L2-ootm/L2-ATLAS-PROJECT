# PROJECT — L2 ATLAS

## What This Is

L2 ATLAS is an AI Company Operating Cockpit: a system for managing autonomous agents, persistent knowledge, channels, integrations, CRM-like relationships, and operational missions.

**Core value:** A serious, auditable AI operating system for technical founders, AI operators, and small high-context teams — not a visual agent builder or chat-with-files product.

**Technology foundation:** ATLAS is an L2-owned operator cockpit/runtime built by evolving the Hermes Agent foundation (vendored at `foundation/atlas-hermes/`, MIT, v0.14.0) into an ATLAS-branded harness, then adding mission, audit, policy, wiki, memory, router, gateway, and cockpit layers around that evolved foundation (D-018).

## Current State

**v1.0 — Operator Cockpit MVP: SHIPPED 2026-06-15** (tag `v1.0`). The first closed
operator loop is live: create mission → run through the ATLAS runtime (vendored Hermes
foundation) → structured audit trail → LLM Wiki → web cockpit. 34/34 requirements
complete; assisted manual operator UAT passed (`APPROVED_FOR_V1_ARCHIVE`). See
`.planning/MILESTONES.md` and `.planning/milestones/v1.0-*`.

Delivered surfaces: vendored Hermes foundation (audit + extension surfaces) · Pydantic
v2 + SQLite (WAL/FTS5) data contract · audit-first event bus · mission/run lifecycle ·
LLM Wiki runtime · Rust `atlas-gateway` (axum/rusqlite, SSE, loopback-only) · SvelteKit
operator cockpit · classified skill packs + public hardening (fonts self-hosted; unsafe
default skills quarantined). Pre-public-publish follow-ups tracked in
`docs/operations/PUBLIC_RELEASE_HARDENING.md §4`.

## Next Milestone: v1.1 — Native Cockpit Shell

**Goal:** Wrap the Phase 8 cockpit in a Tauri 2 / Rust native shell — PTY/terminal pane,
OS keychain, native approvals, IPC capability model, threat-model gate (D-021 §2).
Scope is defined via `/gsd-new-milestone`.

## Architecture

**Layer separation (locked — AGENTS.md):**
1. Raw sources (immutable)
2. Compiled wiki/memory (LLM Wiki + SQLite)
3. Runtime execution (enhanced Hermes + ATLAS services)
4. Cockpit UI (web + native later)

**Repo layout (D-011, amended by D-022 + PRODUCTION_REPO_STRUCTURE.md):**
```
foundation/          vendored Hermes-derived ATLAS foundation (+ ATTRIBUTION, DIVERGENCE_LOG)
packages/atlas-core/ Pydantic schemas + shared contracts
services/            agent-runtime, wiki-runtime, pulse-runtime (later)
apps/cockpit-web/    Phase 8 SvelteKit cockpit (apps/api removed — gateway is Rust, D-022)
infra/migrations/    SQLite schema
native/atlas-core-rs Rust workspace (atlas-gateway crate; future crates/ promotion)
wiki/                persistent markdown KB
```

## Key Decisions

| ID | Decision | Status |
|---|---|---|
| D-001 | Hermes foundation used directly (not black-box) | locked |
| D-002 | Audit-first runtime — every action emits structured events | locked |
| D-003 | SQLite/WAL/FTS5/sqlite-vec for MVP datastore | locked |
| D-004 | LLM Wiki is first-class runtime (not RAG-only) | locked |
| D-005 | Rust-first native desktop; Electron is negative baseline | locked |
| D-006 | WebUI framework: SvelteKit/Svelte 5 with adapter-static | locked |
| D-007 | CRM not first surface (after mission/run/audit/wiki/cockpit) | locked |
| D-008 | Skills must be classified before shipping as ATLAS-grade | locked |
| D-009 | STT/TTS/overlay is differentiator, not first MVP blocker | locked |
| D-010 | CRM/Pulse/Channels deep-dive research still needed | open |
| D-011 | Canonical repo layout: foundation/packages/services/apps/infra | locked |
| D-012 | Pydantic v2 is schema source of truth; emit JSON Schema for TS/Rust | locked |
| D-021 | Web-first Phase 8; native shell = Phase 10 (v1.1); canonical phase numbering; 6-layer memory canon; two-layer branding (L2 brand = experience layer + vendored Hermes foundation, sidecars stay upstream); FreeLLMAPI fork triggers | accepted |
| D-022 | Rust-first cementation: all new components Rust; Phase 7 gateway is Rust (axum/rusqlite); Python confined to Hermes foundation surface, LLM adapters, scripts; L0–L5 port ladder; budgets (CLI <100ms/<50MB, daemon <80MB idle) | accepted |

## Requirements

**v1.0 — Validated (shipped):** all 34 v1.0 REQ-IDs across FOUNDATION, SCHEMA, RUNTIME,
WIKI, AUDIT, COCKPIT, SKILLS, RESEARCH. Archived at
`.planning/milestones/v1.0-REQUIREMENTS.md`.

**v1.1+ — Active:** defined via `/gsd-new-milestone` (NATIVE-01..03 are candidates;
PULSE/CRM deferred to v2.0). A fresh `.planning/REQUIREMENTS.md` is created at that point.

## Source Assets

- `NousResearch/hermes-agent` — Hermes foundation (MIT, v0.14.0, SHA e8b9369a9d2df36139a5055cae3ed3c15691e03e)
- `L2-Atlas/src/atlas_core` — donor modules (mission_control, execution/policy, logging/jsonl_logger, runtime)
- `L2-atlas-hermes` — recovery/snapshot discipline reference
- `L2-BOT` — Discord/channel harness reference
- `l2-agent-skills`, GSD/imported skill packs — skill sources

## Non-Negotiables

- No secrets or raw personal data in this repo.
- No destructive modification of existing source repos.
- No Electron default.
- No CRM or WhatsApp production integration before runtime loop works.
- No native overlay before runtime loop works.
- All autonomous actions are auditable (reason + input + action + output + verification).
- Branding is two-layer (D-021): L2/ATLAS brand applies to the experience layer and the vendored Hermes-derived foundation only; infrastructure sidecars (FreeLLMAPI, Twenty) are never forked or rebranded — Twenty (AGPL + trademark) must never be embedded.
- Rust-first (D-022): every new infrastructure component is Rust; no new Python service code outside the exception buckets (Hermes foundation surface, LLM adapters, throwaway scripts); native components ship with measured budgets.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-progress`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Update traceability in REQUIREMENTS.md
3. New requirements emerged? → Add with next REQ-ID
4. Decisions to log? → Add to docs/decisions/ and update table above

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Archive milestone artifacts
3. Update Context with current state

_Last updated: 2026-06-15 after v1.0 milestone — Operator Cockpit MVP shipped and
archived (tag `v1.0`). All 10 phases (1–9.5) complete; 34/34 requirements validated;
assisted manual operator UAT passed (`APPROVED_FOR_V1_ARCHIVE`, with F1 remote-fonts
fixed in-session). Next: `/gsd-new-milestone` to scope v1.1 (Native Cockpit Shell)._
