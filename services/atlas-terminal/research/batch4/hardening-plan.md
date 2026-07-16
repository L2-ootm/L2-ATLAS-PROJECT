# Atlas-Terminal Hardening Plan

## Phase 1: Fix Event Shape (30 min)
- atlasFetch.ts handleEventStream: wrap events in GlobalEvent envelope
- Add retry: 3000 header
- Update atlasFetch.test.ts SSE assertions

## Phase 2: Wire Bootstrap Stubs (1-2 hrs)
- /vcs: git branch read
- /session/status: real idle/busy from adapter
- /project: gateway project query
- /question + /question/never-ask: gateway settings
- Remove /experimental/resource stub

## Phase 3: Error Handling (2-3 hrs)
- ensureSurface retry (2 attempts, 1s backoff)
- Gateway request timeout (AbortSignal.timeout 15s)
- Stream heartbeat timeout (60s inactivity)
- Normalize 502 responses

## Phase 4: Test Coverage (3-4 hrs)
- Target: 50+ tests (from 7)
- New: adapter unit tests, command routing, permission flow, session lifecycle, SSE parsing

## Phase 5: Donor Cleanup (30-45 min)
- ~30 meaningful renames in 6 non-vendor files
- ~40 vendor attribution comments left untouched
- 1 runtime constant left untouched

## Total: 7-10 hours across 5 phases
