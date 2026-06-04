# STATE — L2 ATLAS

## 2026-06-04

### Completed

- Project skeleton created at `C:/Users/Davi/Desktop/Projects/L2-ATLAS-PROJECT`.
- Git initialized.
- Initial `README.md`, `AGENTS.md`, `.planning/PROJECT.md`, `.planning/RISKS.md` created.
- Initial ATLAS wiki created with `SCHEMA.md`, `index.md`, and `log.md`.
- Product thesis created at `docs/vision/PRODUCT_THESIS.md`.
- System overview created at `docs/architecture/SYSTEM_OVERVIEW.md`.
- L2 legacy consolidation map created at `docs/imports/L2_ATLAS_LEGACY_CONSOLIDATION_MAP.md`.
- Deep research backlog created at `docs/research/DEEP_RESEARCH_BACKLOG.md`.

### Findings from L2-Atlas

Reusable ideas/features:

- Mission Control markdown/Obsidian operating surface.
- Safe execution policy model: workspace policy, command policy, executor, JSONL logger.
- CLI/shell harness.
- Pulse/heartbeat loop.
- Skills registry concept.
- Future voice/STT/TTS/overlay roadmap.

### Findings from L2-atlas-hermes

Reusable ideas/features:

- Role split: ATLAS = reasoning/policy/operating layer; Hermes = execution substrate.
- Recovery/snapshot discipline.
- Redaction/security rules.
- Project pointers and skills index model.

### Current decision

Do not merge old repos wholesale. Extract concepts and modules deliberately.

### Research intake — 2026-06-04

Moved and classified completed research reports from Downloads into:

`docs/research/raw-reports/`

Created:

- `docs/research/2026-06-04_RESEARCH_SYNTHESIS.md`
- `docs/decisions/2026-06-04_DECISION_REGISTER.md`
- `docs/plans/2026-06-04_NEXT_ACTION_PLAN.md`

Key decisions:

- Hermes foundation will be enhanced directly.
- SQLite/WAL/FTS5/sqlite-vec is MVP datastore direction.
- LLM Wiki is first-class.
- Rust-native desktop sidecar; Electron is not default.
- WebUI framework still requires spike.
- CRM/Pulse/Channels dedicated research is still missing.

## 2026-06-04 (implementation-start planning)

### Completed

- Verified repo state: clean tree at `782062d`.
- Audited all committed planning/architecture/research/decision docs.
- Identified the real Hermes foundation from the local install:
  - upstream `https://github.com/NousResearch/hermes-agent.git`;
  - license **MIT**; version `0.14.0`; tag `v2026.5.16-1302-ge8b9369a9`;
  - pinned SHA `e8b9369a9d2df36139a5055cae3ed3c15691e03e`;
  - Python-primary, **monolithic** (`cli.py` ~685KB, `run_agent.py` ~202KB);
  - local install at `AppData/Local/hermes/hermes-agent` holds secrets/state — must NOT be vendored.
- Confirmed `L2-Atlas/src/atlas_core` donor modules (mission_control, execution, logging, runtime, skills).
- Wrote implementation-start plan: `docs/plans/2026-06-04_CLAUDE_IMPLEMENTATION_START_PLAN.md`.

### Contradictions/risks surfaced

- C1: three conflicting repo layouts across synthesis/foundation/system-overview docs → resolved by proposed **D-011**.
- C2: schema-language ambiguity (TS-style `packages/.../src/schemas` vs Python runtime) → proposed **D-012** (Pydantic source of truth).
- C3: `NATIVE_APP_STRATEGY.md` presupposes Next.js while D-006 is open → patched in plan Task 8.
- R1: Hermes monolithic core → divergence policy must be plugin/hook-first.
- R2: Hermes install contains secrets → clone fresh from upstream only.

### Progress (implementation-start plan)

- ✅ Ratified **D-011** (canonical layout) and **D-012** (Pydantic schema source of truth) — committed `a7eca00`.
- ✅ **Task 1** — `docs/foundation/HERMES_FOUNDATION_PIN.md` written; Hermes pinned (MIT, v0.14.0, SHA `e8b9369a9…`) — committed `eed9049`.
- ⏭️ Next: **Task 2** (fresh clone at pinned SHA + secret-scan), then Tasks 3–10.
- Note: GSD workflow to be set up next to drive Tasks 2–10 as extensive phases.

### Next step

Continue `docs/plans/2026-06-04_CLAUDE_IMPLEMENTATION_START_PLAN.md`, in order:

1. ~~Task 1 — pin Hermes.~~ done.
2. Task 2 — fresh clone at pinned SHA into `_EXTERNAL_REPOS/hermes-agent` (+ secret-scan gate).
3. Tasks 3–4 — Hermes extension-point audit + L2-Atlas extraction plan.
4. Task 5 — ratify D-011 (layout) and D-012 (Pydantic schemas).
5. Tasks 6–7 — core Pydantic schemas + `infra/migrations/0001_core.sql`.
6. Tasks 8–9 — WebUI spike doc + CRM/Pulse/Channels intake brief.
7. Task 10 — phase-close: update STATE/RISKS/decisions, verify pre-code gate.

Only after this gate: implement the first MVP loop (mission → enhanced runtime → audit → artifact → wiki → cockpit).
