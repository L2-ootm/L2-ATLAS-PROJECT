# Phase 2: Core Domain Schemas & SQLite Migration

**Phase number:** 2
**Name:** Core Domain Schemas & SQLite Migration
**Status:** Pending

---

## Goal

Establish the Pydantic v2 domain model and SQLite schema as the single authoritative data contract — the foundation every other phase builds on.

---

## Requirements Covered

| REQ-ID | Description |
|--------|-------------|
| SCHEMA-01 | Pydantic v2 models for Mission, Run, AuditEvent, ToolCall, Artifact, Source, WikiPage with correct fields, enums, FK relationships |
| SCHEMA-02 | SQLite migration 0001_core.sql applies on fresh DB (WAL mode, foreign keys enforced, FTS5 index created) |
| SCHEMA-03 | model_json_schema() emits valid JSON Schema for all core Pydantic models (D-012 TS/Rust bridge) |

---

## Success Criteria

1. `packages/atlas-core/atlas_core/schemas/core.py` exists with Mission, Run, AuditEvent, ToolCall, Artifact, Source, WikiPage as Pydantic v2 models.
2. `from atlas_core.schemas.core import Mission` succeeds in a clean Python 3.11 environment.
3. `Mission.model_json_schema()` emits valid JSON Schema with all fields present.
4. `infra/migrations/0001_core.sql` applies on a fresh SQLite `:memory:` DB without errors; all 7 tables created (missions, runs, audit_events, tool_calls, artifacts, sources, wiki_pages).
5. FTS5 virtual table created (or blocked state documented with sqlite build note).
6. Column names in DDL match Pydantic field names 1:1 (no silent drift).

---

## Key Decisions Applicable

- **D-003** (locked): SQLite/WAL/FTS5/sqlite-vec is MVP datastore. No Postgres.
- **D-012** (locked): Pydantic v2 is single schema source of truth; JSON Schema for TS/Rust; SQLite DDL mirrors models.
- **D-011** (locked): Canonical repo layout — schemas live at `packages/atlas-core/atlas_core/schemas/core.py`; migrations at `infra/migrations/`.
- Module extraction plan from Phase 1 identifies which atlas_core donor modules to port/rewrite — use it to validate field names and relationships.

---

## What NOT to Build

- Do not implement any service logic, CLI commands, or API endpoints — that is Phases 4–7.
- Do not wire up the event bus or database connection pool — that is Phase 4.
- Do not build the wiki service or ingest pipeline — that is Phase 6.
- Do not add CRM/Pulse models — those are v2.0 (out of scope).
- Do not add sqlite-vec loading logic here — just ensure the schema has the right column types for vector storage.
- Keep this phase to pure data contracts: models + migration DDL only.
