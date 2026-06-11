# QA Validation Index

## Purpose

This index tracks validation records for each phase. Committed summaries and
evidence live here. Generated artifacts (coverage XML, binary snapshots,
runtime logs) belong in ignored `artifacts/` or local caches — never
committed.

## Authority

Validation records in this directory are the authoritative evidence that a
phase's success criteria were met. Each record must include:
- The exact command(s) run and their outcome
- Pass/fail status per success criterion
- Date of validation
- Validator (model or operator)

## Evidence Rules

- Evidence must cite exact commands and actual output, not paraphrased claims.
- Coverage numbers must cite the pytest/cargo report line.
- Binary size checks must cite `ls -lh` or `Get-Item` output.
- Contract tests must cite schema version and validation result.
- Generated/runtime artifacts do not belong in `docs/qa/` — only committed
  summaries and evidence records do.

## Where Generated Artifacts Go

| Artifact type | Location |
|---|---|
| Committed validation summaries | `docs/qa/` (this directory) |
| Coverage HTML/XML reports | `artifacts/` (gitignored) or local pytest cache |
| Binary snapshots | `artifacts/` (gitignored) |
| Runtime logs | `artifacts/` or `.atlas/logs/` (gitignored) |

## Current Validation Records

| Phase | File | Status | Date |
|---|---|---|---|
| 4 | [phase-04-state-review-2026-06-07.md](phase-04-state-review-2026-06-07.md) | Pass | 2026-06-07 |
| 4 | [phase-04-redaction-fix-recheck-2026-06-07.md](phase-04-redaction-fix-recheck-2026-06-07.md) | Pass | 2026-06-07 |

## Phase 7 Validation Targets

Phase 7 (API Gateway, Rust) validation must confirm:

1. **Build** — `cargo build -p atlas-gateway --release` exits 0; release
   binary size < 20 MB (D-022 budget).
2. **Endpoint contract tests** — All routes in `GET /v1/missions`,
   `GET /v1/runs/{id}`, `GET /v1/runs/{id}/events`, `GET /v1/runs/{id}/stream`,
   `GET /v1/wiki/pages`, `GET /v1/wiki/search`, `POST /missions`,
   `POST /missions/{id}/run` return expected status codes on happy path and
   one error case each.
3. **SSE latency** — `GET /v1/runs/{id}/stream` delivers the first event
   within 500 ms for a terminal run (rowid cursor poll ≤ 500 ms per D-022).
4. **JSON Schema compatibility (D-012)** — Response field names match the
   Pydantic model field names exported via `model_json_schema()`. No silent
   drift between the Python schema source of truth and Rust response shapes.
   Verified by `tests/contract.rs`.
5. **Budget checks (D-022)** — Idle RSS < 80 MB confirmed via process
   monitor with no active requests; release binary < 20 MB.

Validation evidence for Phase 7 should be written to
`docs/qa/phase-07-validation-YYYY-MM-DD.md` when Phase 7 is marked complete.
