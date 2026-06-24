# ADR Index — D-001 … D-023

Authority: ADRs are canonical (see `docs/README.md`). Later ADRs amend
earlier ones where noted.

| ID | Title | Status | File |
|---|---|---|---|
| D-001 | Hermes foundation used directly (not black-box) | locked | `2026-06-04_DECISION_REGISTER.md` |
| D-002 | Audit-first runtime — every action emits structured events | locked | `2026-06-04_DECISION_REGISTER.md` |
| D-003 | SQLite/WAL/FTS5/sqlite-vec MVP datastore | locked | `2026-06-04_DECISION_REGISTER.md` |
| D-004 | LLM Wiki is first-class runtime (not RAG-only) | locked | `2026-06-04_DECISION_REGISTER.md` |
| D-005 | Rust-first native desktop; no Electron | locked | `2026-06-04_DECISION_REGISTER.md` |
| D-006 | WebUI: SvelteKit/Svelte 5 + adapter-static | locked | `2026-06-04_DECISION_REGISTER.md` |
| D-007 | CRM after mission/run/audit/wiki/cockpit | locked | `2026-06-04_DECISION_REGISTER.md` |
| D-008 | Skills classified before shipping | locked | `2026-06-04_DECISION_REGISTER.md` |
| D-009 | STT/TTS/overlay after runtime loop | locked | `2026-06-04_DECISION_REGISTER.md` |
| D-010 | CRM/Pulse/Channels research intake | complete | `2026-06-04_DECISION_REGISTER.md` |
| D-011 | Canonical repo layout | locked, amended by D-022 + `architecture/PRODUCTION_REPO_STRUCTURE.md` (apps/api removed; gateway = Rust crate; apps/web → apps/cockpit-web) | `2026-06-04_D011_repo_layout.md` |
| D-012 | Pydantic v2 schema source of truth; JSON Schema export for TS/Rust | locked | `2026-06-04_D012_schema_source_of_truth.md` |
| D-013 | Language strategy: prototype Python, cement Rust | locked; timing resolved by D-022 | `D-013-language-strategy.md` |
| D-014 | turbovec local semantic retrieval | spike only | `D-014-turbovec-local-semantic-retrieval-spike.md` |
| D-015 | FreeLLMAPI sidecar gateway (sidecar-first, fork last) | accepted | `D-015-freellmapi-sidecar-gateway.md` |
| D-016 | Terax = Rust-native cockpit reference pillar (not vendor) | accepted; shell timing → Phase 10 per D-021 | `D-016-terax-rust-native-cockpit-pillar.md` |
| D-017 | AI router connector strategy (model_registry + model_router) | accepted | `D-017-ai-router-connector-strategy.md` |
| D-018 | Hermes-first foundation: evolve, never wrap or route through | accepted | `D-018-hermes-first-foundation-strategy.md` |
| D-019 | Diverse agent memory framework (6 layers) | accepted | `D-019-diverse-agent-memory-framework.md` |
| D-020 | Twenty CRM = external sidecar pillar (AGPL, never embedded) | accepted | `D-020-twenty-crm-foundation-layer.md` |
| D-021 | v1.0 sequencing + branding consolidation (web-first Phase 8; two-layer branding; canonical numbering) | accepted | `D-021-v1-sequencing-branding-and-contradiction-resolution.md` |
| D-022 | Rust-first cementation (Rust gateway Phase 7; Python exception buckets; L0–L5 ladder; budgets) | accepted | `D-022-rust-first-cementation-policy.md` |
| D-023 | One ATLAS agent, multi-surface workbench; ATLAS-native donor-derived TUI; shared session/config/events; surface-scoped approvals; versioned prompt/Brain context | accepted | `D-023-atlas-multi-surface-agent-contract.md` |

## Runtime divergence decisions (Hermes integration surface)

| ID | Title | File |
|---|---|---|
| DIV-001 | System prompt augmentation | `DIV-001-system-prompt-augmentation.md` |
| DIV-002 | Artifact capture | `DIV-002-artifact-capture.md` |
| DIV-003 | Hermes state write path | `DIV-003-hermes-state-write-path.md` |
| DIV-004 | turn_id propagation | `DIV-004-turn-id-propagation.md` |

Foundation-tree divergences (DIV-F-001…) live in
`foundation/DIVERGENCE_LOG.md`, not here.
