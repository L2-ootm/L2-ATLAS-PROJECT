# Phase 5: Mission & Run Lifecycle

**Phase number:** 5
**Name:** Mission & Run Lifecycle
**Status:** Pending

---

## Goal

Implement the core mission state machine — create, execute, complete, cancel — backed by the audit event bus, with a working CLI and unit-tested service layer.

---

## Requirements Covered

| REQ-ID | Description |
|--------|-------------|
| RUNTIME-01 | User can create a Mission (title + intent) via CLI or API and see it persisted in the database |
| RUNTIME-02 | User can execute a Mission and have it processed by the enhanced ATLAS/Hermes runtime loop |
| RUNTIME-04 | A completed Run shows final status (succeeded/failed), start/finish timestamps, and a summary |
| RUNTIME-05 | User can cancel a running Mission and see a partial audit trail in the database |
| RUNTIME-06 | Subagents are governed: role, model tier, allowed tools, autonomy level, token budget captured per AuditEvent row |
| RUNTIME-07 | Policy engine enforces cross-platform workspace/command safety (not Windows-only PowerShell) |

---

## Success Criteria

1. `atlas mission create --title "Test" --intent "..."` persists a Mission row and prints the mission ID.
2. `atlas mission run <id>` starts execution, creates a Run row, emits task.started AuditEvent.
3. A completed run transitions to `succeeded` or `failed` status with finish timestamp and summary.
4. `atlas mission cancel <id>` stops an active run and transitions it to `failed`; partial audit trail is preserved.
5. Subagent assignment creates an AuditEvent of kind `subagent_run` with role, model tier, tool allowlist, and token budget in the payload.
6. Policy engine rejects a command outside the workspace boundary and emits an AuditEvent of kind `failure`.
7. Policy engine works on Linux (bash) and Windows (PowerShell) paths — confirmed by two test runs.
8. All service layer functions have unit tests (≥ 80% branch coverage on mission_service.py and run_service.py).

---

## Key Decisions Applicable

- **D-001** (locked): Hermes runtime used directly — mission execution goes through the enhanced Hermes runtime loop, not a wrapper subprocess.
- **D-002** (locked): Audit-first — every state transition (created, started, succeeded, failed, cancelled) emits an AuditEvent.
- **D-003** (locked): SQLite/WAL is the datastore — all mission/run state persisted there.
- **D-006** (open at phase start, closed by Phase 3): Policy engine must work cross-platform; do not hardcode PowerShell or bash paths.
- **D-008** (locked): Skills must be classified before ATLAS-grade use — the policy engine should enforce allowed-tools lists, not permit unclassified skill execution.
- Phase 4 event bus is a hard dependency — mission lifecycle emits via the event bus, not raw SQL inserts.

---

## What NOT to Build

- Do not build the wiki ingest or update pipeline — that is Phase 6.
- Do not build the REST API layer — that is Phase 7.
- Do not build the cockpit UI — that is Phase 8.
- Do not implement CRM entity linkage to missions — that is v2.0.
- Do not implement Pulse/heartbeat missions — that is v2.0.
- Keep the CLI minimal: create, run, cancel, status. No interactive TUI, no dashboard.
- Do not implement subagent spawning in production at this phase — a mock/stub subagent that emits the correct AuditEvent is sufficient to satisfy RUNTIME-06.
