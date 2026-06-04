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

### Next step

1. Clone/pin Hermes foundation externally or under `foundation/`.
2. Run Hermes foundation audit.
3. Run deep audit of `L2-Atlas/src/atlas_core` modules and produce extraction candidates:
   - mission parser/task model;
   - policy engine;
   - JSONL logger;
   - heartbeat/pulse;
   - shell/CLI harness;
   - skill registry.
