# Plan 01-03 Summary — Divergence Decision Stubs

**Phase:** 01 — Hermes Foundation Clone & Extension Audit
**Plan:** 01-03 (Wave 3)
**Status:** Complete
**Commit:** 4562d0f
**REQ-ID:** FOUND-03

## Deliverables

| File | Classification | Disposition |
|------|---------------|-------------|
| `docs/decisions/DIV-001-system-prompt-augmentation.md` | ATLAS-only | No in-core edit — AGENTS.md context-file path |
| `docs/decisions/DIV-002-artifact-capture.md` | plugin-tool | No in-core edit — `post_tool_call` name-filter |
| `docs/decisions/DIV-003-hermes-state-write-path.md` | plugin-tool | No in-core edit — parallel DB joined on `session_id` |
| `docs/decisions/DIV-004-turn-id-propagation.md` | plugin-tool | No in-core edit — use `task_id` as correlation key |

## Key Finding

All 4 friction points resolve WITHOUT in-core Hermes edits. The divergence policy preference order (plugin > tool > hook > skill > ATLAS-only > in-core) was respected. Phase 4 has clear action items per stub.

## Verification

- 4 DIV-*.md files exist in `docs/decisions/` ✅
- Each contains `Classification:` and `Disposition:` fields ✅
- Hermes clone tree unmodified ✅
- Each stub references specific files from `_EXTERNAL_REPOS/hermes-agent/` ✅
