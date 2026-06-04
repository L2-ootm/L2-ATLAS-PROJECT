# Phase 7: API Gateway

**Phase number:** 7
**Name:** API Gateway
**Status:** Pending

---

## Goal

Expose all mission, run, audit, and wiki operations via a typed REST API so the cockpit and future integrations have a stable interface.

---

## Requirements Covered

This phase has no exclusively owned REQ-IDs. It is the API infrastructure layer that makes Phase 8 (cockpit) possible. All domain REQ-IDs are owned by their originating phases (RUNTIME by Phase 5, WIKI by Phase 6, AUDIT by Phase 4, COCKPIT by Phase 8).

Phase 7 satisfies the API surface required by COCKPIT-01..06 (Phase 8) — without a stable API, the cockpit cannot be built.

---

## Success Criteria

1. FastAPI server starts with `uvicorn atlas_api.main:app` and serves the OpenAPI spec at `/docs`.
2. `POST /missions` creates a mission; `GET /missions` returns a paginated list.
3. `POST /missions/{id}/run` starts a run; `GET /runs/{id}` returns run status.
4. `GET /runs/{id}/events` returns ordered AuditEvent list with all fields.
5. `GET /wiki/pages` returns a paginated page list; `GET /wiki/search?q=` returns FTS5 results.
6. All endpoints return proper HTTP status codes (201 create, 200 ok, 404 not found, 422 validation error).
7. OpenAPI schema matches the Pydantic response models (no manual schema drift).
8. Integration tests cover all 8 endpoints (happy path + one error case each).

---

## Key Decisions Applicable

- **D-012** (locked): Pydantic v2 is schema source of truth — FastAPI uses Pydantic response models directly; no manual OpenAPI schema authoring.
- **D-011** (locked): Canonical repo layout — API app lives at `apps/api/` or `services/` per layout decision.
- **D-003** (locked): SQLite is the datastore — API layer calls service layer (Phases 5–6), does not query SQLite directly.
- **D-007** (locked): CRM is not first surface — do not add CRM endpoints here.
- Architecture rule: API is a thin HTTP adapter over the service layer. Business logic stays in services (Phase 5: mission_service.py, Phase 6: wiki_service.py). No logic in route handlers.

---

## What NOT to Build

- Do not build the cockpit frontend — that is Phase 8.
- Do not add CRM, Pulse, or Channels endpoints — those are v2.0.
- Do not add authentication/authorization middleware — ATLAS v1.0 is single-operator local, no auth required.
- Do not add WebSocket endpoints here — real-time streaming for the cockpit is Phase 8 work (or a minimal SSE endpoint added in Phase 8 if needed).
- Do not add admin or multi-tenant endpoints — out of scope for v1.0.
- Do not duplicate service layer logic in route handlers — API routes must delegate directly to Phase 5/6 service functions.
