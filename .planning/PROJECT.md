# PROJECT — L2 ATLAS

## What This Is

L2 ATLAS is an AI Company Operating Cockpit: a system for managing autonomous agents, persistent knowledge, channels, integrations, CRM-like relationships, and operational missions.

**Core value:** A serious, auditable AI operating system for technical founders, AI operators, and small high-context teams — not a visual agent builder or chat-with-files product.

**Technology foundation:** Enhanced NousResearch Hermes (Python, MIT, v0.14.0) as the runtime substrate. ATLAS adds the product/operator layer: mission model, audit event bus, LLM Wiki, cockpit UI, skill governance, and a Rust-native sidecar track.

## Current Milestone: v1.0 — Operator Cockpit MVP

**Goal:** Ship the first closed operator loop — create mission → run through enhanced ATLAS/Hermes runtime → capture audit trail → file artifacts to LLM Wiki → display in web cockpit.

**Target features:**
- Hermes foundation clone & extension-point audit
- Core domain schemas (Pydantic v2) + SQLite migration
- Research closure (WebUI framework decision, CRM/Pulse intake)
- ATLAS event bus + audit core
- Mission & run lifecycle (create/execute/cancel/complete)
- LLM Wiki runtime (ingest/query/update/lint)
- API gateway (FastAPI)
- Web operator cockpit (mission management, run monitoring, wiki browser)
- Skill inventory & classification

## Architecture

**Layer separation (locked — AGENTS.md):**
1. Raw sources (immutable)
2. Compiled wiki/memory (LLM Wiki + SQLite)
3. Runtime execution (enhanced Hermes + ATLAS services)
4. Cockpit UI (web + native later)

**Repo layout (D-011):**
```
foundation/          Hermes vendoring pointer
packages/atlas-core/ Pydantic schemas + shared contracts
services/            agent-runtime, wiki-runtime, pulse-runtime (later)
apps/                api, web cockpit
infra/migrations/    SQLite schema
native/              Rust sidecar (later)
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

## Active Requirements

See `.planning/REQUIREMENTS.md` for full REQ-ID list.

Summary: 30 requirements across FOUNDATION, SCHEMA, RUNTIME, WIKI, AUDIT, COCKPIT, SKILLS, RESEARCH categories.

## Source Assets

- `NousResearch/hermes-agent` — Hermes foundation (MIT, v0.14.0, SHA e8b9369a9d2df36139a5055cae3ed3c15691e03e)
- `L2-Atlas/src/atlas_core` — donor modules (mission_control, execution/policy, logging/jsonl_logger, runtime)
- `L2-atlas-hermes` — recovery/snapshot discipline reference
- `L2-BOT` — Discord/channel harness reference
- `l2-agent-skills`, OpenClaw/GSD — skill sources

## Non-Negotiables

- No secrets or raw personal data in this repo.
- No destructive modification of existing source repos.
- No Electron default.
- No CRM or WhatsApp production integration before runtime loop works.
- No native overlay before runtime loop works.
- All autonomous actions are auditable (reason + input + action + output + verification).

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

_Last updated: 2026-06-08 — Phase 5 complete: Mission & Run Lifecycle. RUNTIME-01/02/04/05/06/07 verified. 44 tests green, 85% branch coverage. Phase 6 (LLM Wiki Runtime) is next._
