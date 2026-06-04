# D-012 — Schema source of truth: Pydantic v2

Date: 2026-06-04
Status: **locked** (ratified before Task 6).

## Context

`NEXT_ACTION_PLAN.md` step 4 targeted `packages/atlas-core/src/schemas/` — a JS/TS-monorepo
idiom (`src/`). But the entire runtime is Python: the Hermes foundation
(`NousResearch/hermes-agent`, Python-primary) and the L2-Atlas donor modules are Python.
Authoring schemas in TypeScript as the source of truth for a Python runtime creates a
dual-maintenance trap and a serialization seam at the hottest path (audit events).

## Decision

**Pydantic v2 models are the single source of truth**, located at
`packages/atlas-core/atlas_core/schemas/`.

- Cross-language consumers (TS web cockpit, Rust native sidecar) consume **emitted JSON Schema**
  (`model_json_schema()`), never hand-written duplicates.
- The SQLite DDL (`infra/migrations/0001_core.sql`) is generated to **mirror** these models —
  column names and enums match the Pydantic fields exactly; the DDL is not authored independently.

## Rationale

- The runtime that writes/reads these objects most (audit-first event capture, D-002) is Python.
- JSON Schema is the neutral bridge to TS and Rust without a second authoring surface.
- Keeping DDL downstream of the models prevents schema drift between code and storage.

## Consequences

- Task 6 writes Pydantic models; Task 7 DDL must match field names 1:1.
- L2-Atlas data-carrying modules (`runtime/models.py`, `mission_control/task_model.py`,
  `logging/jsonl_logger.py`) are reconciled *into* these Pydantic schemas, not ported as a
  parallel model set (closes the second-model risk flagged in the extraction plan).
- The `src/` path from `NEXT_ACTION_PLAN.md` is dropped in favor of the Python package path.
