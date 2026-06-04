# L2 ATLAS Decision Register

Date: 2026-06-04

## D-001 — Hermes foundation, not black-box routing

Decision: ATLAS will enhance the Hermes framework foundation directly.

Rationale:
- Hermes already provides the agent loop, tools, skills, memory, gateway, cron, MCP, profiles, delegation, sessions, and CLI/TUI base.
- A black-box wrapper would lose too much audit/control/context integration.

Status: locked.

## D-002 — Audit-first runtime

Decision: Every important runtime action must emit structured events and audit records.

Objects to audit:
- LLM calls;
- tool calls;
- subagent runs;
- approvals;
- external actions;
- artifacts;
- wiki updates;
- memory changes;
- failures and retries.

Status: locked.

## D-003 — SQLite-first MVP datastore

Decision: MVP should use SQLite/WAL/FTS5/sqlite-vec before Postgres/pgvector.

Rationale:
- lower operational cost;
- local-first;
- matches Hermes state store pattern;
- fast enough for dogfood and design partners;
- avoids premature SaaS complexity.

Status: locked for MVP; revisit for SaaS.

## D-004 — LLM Wiki is first-class

Decision: ATLAS knowledge runtime must use persistent LLM Wiki plus search/memory, not RAG-only.

Required files:
- `SCHEMA.md`;
- `index.md`;
- `log.md`;
- raw immutable sources;
- generated/maintained wiki pages.

Status: locked.

## D-005 — Rust-native desktop, no Electron default

Decision: Desktop sidecar/overlay layer is Rust-first. Electron is not the default and should be treated as negative baseline.

Preferred candidates:
- Slint for polished native surfaces;
- egui for internal/debug tools;
- Tauri only as thin shell for WebUI if useful;
- custom wgpu only for specialized rendering.

Status: locked.

## D-006 — WebUI framework not locked yet

Decision: WebUI framework remains undecided between SvelteKit/Svelte 5 and Next.js/React.

Rationale:
- research recommends SvelteKit;
- L2 has existing Next.js muscle/code;
- decision requires spike against cockpit requirements.

Status: open.

Required next action:
- create `docs/research/WEBUI_STACK_SPIKE.md` comparing SvelteKit vs Next.js.

## D-007 — CRM later, not first surface

Decision: CRM/relationship runtime is important but not the first implementation surface.

MVP priority:
1. enhanced runtime;
2. mission/run/audit;
3. LLM Wiki;
4. cockpit;
5. pulse;
6. minimal CRM primitives.

Status: locked for MVP.

## D-008 — Skill polishing before shipping

Decision: Existing Hermes/OpenClaw/L2 skills must be classified and polished before becoming ATLAS-grade.

Skill classes:
- core;
- operator;
- l2-internal;
- personal/private;
- experimental;
- deprecated.

Status: locked.

## D-009 — Native voice/overlay is differentiator, not first blocker

Decision: STT/TTS/overlay is a major differentiator, but runtime and cockpit loop ship first.

Status: locked.

## D-010 — Missing CRM/Pulse/Channels research

Decision: A dedicated CRM/Pulse/Channels report still needs to be run; existing reports only partially cover it.

Status: open.

## D-011 — Canonical repo layout

Decision: Polyglot monorepo (`foundation/`, `packages/atlas-core`, `services/*`, `apps/*`, `infra/`, `native/`). Resolves the three conflicting layouts across the planning docs.

See: `docs/decisions/2026-06-04_D011_repo_layout.md`.

Status: locked.

## D-012 — Schema source of truth

Decision: Pydantic v2 models in `packages/atlas-core/atlas_core/schemas/` are the single source of truth; emit JSON Schema for TS/Rust; SQLite DDL mirrors the models.

See: `docs/decisions/2026-06-04_D012_schema_source_of_truth.md`.

Status: locked.
