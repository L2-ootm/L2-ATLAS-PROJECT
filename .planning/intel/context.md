# Project Context (ingest-docs merge — 2026-06-04)

Sources: STATE.md, PROJECT.md, RESEARCH_SYNTHESIS.md, ODYSSEUS_REFERENCE_NOTE.md

---

## What was done before this ingest

- Project skeleton created, git initialized, initial planning docs committed.
- D-011 and D-012 ratified (canonical layout + Pydantic schema source of truth).
- Task 1 of CLAUDE_IMPLEMENTATION_START_PLAN.md complete: HERMES_FOUNDATION_PIN.md written and committed.
- Hermes upstream identified: NousResearch/hermes-agent, MIT, v0.14.0, SHA e8b9369a9d2df36139a5055cae3ed3c15691e03e.
- Six research reports ingested and synthesized into RESEARCH_SYNTHESIS.md.
- 12 decision records (D-001 through D-012) registered.
- 3 architecture docs, 1 product thesis, 1 legacy consolidation map, 1 capabilities plan in place.

## Immediate next work (before ingest)

Tasks 2–10 from CLAUDE_IMPLEMENTATION_START_PLAN.md:
- Task 2: Clone Hermes fresh at pinned SHA + secret-scan gate
- Task 3: Hermes extension-point audit → HERMES_FOUNDATION_AUDIT.md
- Task 4: L2-Atlas module extraction plan → L2_ATLAS_MODULE_EXTRACTION_PLAN.md
- Task 5: Already done (D-011/D-012 ratified)
- Task 6: Pydantic domain schemas → packages/atlas-core/atlas_core/schemas/core.py
- Task 7: SQLite migration → infra/migrations/0001_core.sql
- Task 8: WebUI stack spike → WEBUI_STACK_SPIKE.md
- Task 9: CRM/Pulse/Channels intake brief
- Task 10: Phase-close state + risks update

## Product positioning (from PRODUCT_THESIS.md)

Wedge: technical founders / AI operators / small high-context teams.
Differentiation: closed daily operation loop (sources → briefing → missions → approved actions → audit → closing brief).
NOT: another visual agent builder, chat-with-files, generic CRM.

## MVP loop (from README, SYSTEM_OVERVIEW)

create mission → run through enhanced ATLAS/Hermes runtime → capture event/audit log → produce artifact → file into LLM Wiki → display in cockpit
