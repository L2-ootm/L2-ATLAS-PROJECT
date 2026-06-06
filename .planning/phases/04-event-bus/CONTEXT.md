# Phase 4: ATLAS Event Bus & Audit Core

**Phase number:** 4
**Name:** ATLAS Event Bus & Audit Core
**Status:** Pending

---

## Goal

Wire a structured audit event bus into the Hermes runtime so every important action emits a durable AuditEvent — the audit-first requirement that all observability builds on.

---

## Requirements Covered

| REQ-ID | Description |
|--------|-------------|
| RUNTIME-03 | Every LLM call, tool call, subagent run, approval, external action, and artifact emits a structured AuditEvent row in the database |
| AUDIT-01 | User can retrieve the full ordered audit trail for any Run from the API |
| AUDIT-02 | Audit trail is exportable as JSONL (one event per line, all fields present) |

---

## Success Criteria

1. ATLAS event bus module exists at `services/agent-runtime/atlas_core/event_bus.py` (or equivalent per D-011 layout).
2. Running a Hermes tool call via ATLAS produces at minimum one ToolCall row in the SQLite database.
3. Running a mock LLM call via ATLAS produces an AuditEvent row of kind `llm_call`.
4. `GET /runs/{id}/events` returns a correctly ordered list of AuditEvent records.
5. Exporting a run's audit trail as JSONL produces valid JSONL (one JSON object per line, all required fields present).
6. All audit writes are transactional — partial failures do not leave orphaned event rows.
7. No in-core edits to Hermes cli.py or run_agent.py required (verified by git diff showing no changes to those files, or a divergence decision record exists if edits were unavoidable).

---

## Key Decisions Applicable

- **D-001** (locked): Hermes used directly — event bus attaches via plugin/hook, not subprocess.
- **D-002** (locked): Every runtime action emits structured audit events (LLM call, tool call, subagent, approval, external action, artifact, wiki update, memory change, failure, retry).
- **D-003** (locked): SQLite/WAL is the datastore — audit writes use WAL mode for concurrency safety.
- **D-011** (locked): Canonical repo layout — event bus lives in `services/agent-runtime/`.
- Divergence policy: If in-core Hermes edits prove unavoidable, create a docs/decisions/ record with classification before merging.
- Phase 1 audit verdict: The YES/NO on event bus attachment without cli.py edits is the primary input to this phase — act on that verdict.

---

## Hard Blockers from Prior Phases

These must be resolved before any Phase 4 task writes AuditEvent.data, ToolCall.args, or ToolCall.result to SQLite:

| ID | Source | Blocker |
|----|--------|---------|
| HB-04-01 | Phase 02 REVIEW.md [CRITICAL] | `SECRET_PATTERNS` in `atlas_core/schemas/core.py` does not match JSON key-value notation. Current patterns only catch `key=value` (URL querystring) and `Bearer <token>`. A payload like `{"token": "sk-abc123"}` or `{"api_key": "xyz"}` passes through unredacted. **Fix before first AuditEvent.data write:** add JSON pattern `(?i)"(token|api[_-]?key|secret|password)"\s*:\s*"([^"]+)"` with replacement `"\1": "[REDACTED]"` (preserves valid JSON structure). |
| HB-04-02 | Phase 02 independent review | SQLite has no enum constraints on `status`, `kind`, and similar TEXT columns. Pydantic is the only write-boundary guard. Any raw SQL path that bypasses the model layer can store invalid enum values silently. All audit writes in this phase must go through the Pydantic model layer, not raw INSERT strings with unchecked literals. |

---

## What NOT to Build

- Do not implement the mission state machine (create/run/cancel) — that is Phase 5.
- Do not implement the wiki pipeline — that is Phase 6.
- Do not build the full REST API endpoints — that is Phase 7 (AUDIT-01 success criterion here refers to the internal service layer retrieving events, not a full HTTP endpoint).
- Do not implement the cockpit UI — that is Phase 8.
- Do not add CRM or Pulse event types — those are v2.0.
- Keep event bus scope to: emit, persist, retrieve (ordered), export JSONL. No consumer fanout, no webhooks.
