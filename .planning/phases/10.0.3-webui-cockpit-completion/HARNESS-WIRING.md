# HARNESS-WIRING — connecting the cockpit to the real ATLAS harness

How the React cockpit (`services/web-ui-react`) wires to the live system. Source of truth for the
gateway contract, the read/write split, SSE streaming, mock vs. real, and the **endpoint gaps** the
new pages require. Grounded in the actual gateway crate
`native/atlas-core-rs/crates/atlas-gateway/src/lib.rs`.

---

## 1. Topology

```
React SPA (web-ui-react, static dist)
        │  fetch / EventSource → http://127.0.0.1:8484
        ▼
atlas-gateway (Rust, axum + rusqlite)            D-022: first native crate
        ├─ READS  → direct SQLite (WAL, FTS5)    fast, no process spawn
        └─ WRITES → dispatch `atlas` CLI         contract boundary; CLI is the only writer
        ▼
SQLite (missions, runs, audit_events, wiki, model_registry)  ← also written by the agent loop
```

- **Read path:** gateway queries SQLite directly and returns JSON. Cheap, synchronous.
- **Write path:** gateway shells out to the `atlas` CLI (`tokio::process::Command`), which performs
  the mutation and writes audit events. The UI never writes SQLite directly. This keeps every
  mutation audited and policy-checked through one contract (D-022).
- **Live path:** runs emit `audit_events`; the gateway exposes an **SSE stream** over a rowid poll.

`api.ts` already targets `GATEWAY = http://127.0.0.1:8484` and is framework-agnostic (ported verbatim).

---

## 2. Confirmed gateway endpoints (live today)

| Method | Path | UI binding (`api.ts`) | Notes |
|---|---|---|---|
| GET | `/health` | `checkHealth()` | `{ status, db }`; powers SystemStatus + offline detection |
| GET | `/v1/missions?limit` | `listMissions()` | `{ missions, count }` |
| POST | `/v1/missions` | `createMission(title,intent)` | write → `atlas` CLI |
| GET | `/v1/missions/{id}` | `getMission()` | `{ mission, runs }` |
| POST | `/v1/missions/{id}/run` | `startRun()` | write → CLI; returns `{ run }` |
| POST | `/v1/missions/{id}/cancel` | `cancelRun()` | write → CLI; **cancels ALL active runs of the mission** |
| GET | `/v1/runs/{id}` | `getRun()` | `{ run }` |
| GET | `/v1/runs/{id}/events?after&limit` | `getRunEvents()` | cursor (rowid) pagination |
| GET | `/v1/runs/{id}/stream` | **UNUSED** | **SSE** live event stream — wire for Run detail |
| GET | `/v1/wiki/pages?limit` | `listWikiPages()` | |
| POST | `/v1/wiki/pages` | `createWikiPage()` | write → CLI |
| GET | `/v1/wiki/pages/{slug}` | `getWikiPage()` | incl. provenance |
| PUT | `/v1/wiki/pages/{slug}` | `updateWikiPage()` | write → CLI |
| GET | `/v1/wiki/search?q&limit` | `searchWiki()` | FTS5 ranked snippets |
| GET | `/v1/models` | `listModels()` | degrades on 404/503 |

---

## 3. SSE — wire the live run stream (highest-value wiring)

The Run-detail showpiece must consume `GET /v1/runs/{id}/stream` instead of polling.

**Add to `api.ts`:**
```ts
// Returns an EventSource for a run's live audit stream. Caller owns teardown.
export function openRunStream(id: string): EventSource {
  return new EventSource(`${GATEWAY}/v1/runs/${encodeURIComponent(id)}/stream`);
}
```

**Consumption pattern (`useRunStream` hook):**
- On mount for a LIVE run: open `EventSource`; `onmessage` → parse `AuditEvent`, append, sonar-ping.
- Track `lastCursor`; on error/close, `EventSource` auto-retries; after N failures fall back to
  `getRunEvents(after=lastCursor)` polling and surface "STREAM LOST — RETRYING".
- For a finished run: skip SSE, page history via `getRunEvents` cursor.
- Teardown: `es.close()` in cleanup. WebView2 supports `EventSource`.
- Reduced-motion: still stream; drop the ping/blur animation to static append.

This is the single most impactful wiring upgrade and unblocks the AUDIT thesis surface.

---

## 4. Mock vs. real (degradation contract)

- **Gateway down** → every fetch rejects → pages render the **offline state** (Observatory already
  does this via `Promise.allSettled` + all-rejected check). No errors thrown to the user.
- **Endpoint/table absent** (404/503) on `listModels` → empty registry, not an error (existing).
- **Mock mode** (env flag, surfaced on `/system`): allow a `VITE_GATEWAY` override + an optional
  in-memory fixture provider behind the same `api.ts` signatures, so the UI can be developed and
  Playwright-shot without a live harness. Keep fixtures behind a build-time flag; never ship mock
  data as real.

---

## 5. Endpoint GAPS — new pages need new gateway surface

These are required (or interim-worked-around) for the new IA. Each should become a gateway PR,
keeping the **read=SQLite / write=CLI** split.

| Need | Page | Proposed endpoint | Interim |
|---|---|---|---|
| List all runs (cross-mission) | Runs `/runs` | `GET /v1/runs?limit&status&after` | fan-out `listMissions`→`getMission` |
| Cross-run audit explorer | Ledger `/audit` | `GET /v1/audit/events?after&limit&type&policy&tool&run&since` | fan-out run events (bounded) |
| Integrations/tools registry | Integrations | `GET /v1/integrations` (name/kind/state/posture) | static manifest + `checkHealth` |
| Model routing/health detail | Models | extend `/v1/models` with tier/health/policy | derive client-side (today) |
| Version/build/env | System | `GET /v1/system` (version, build, flags) | compile-time constant + `checkHealth` |

**Cursor discipline.** All list/stream endpoints paginate on the monotonic `audit_events.rowid`
(`cursor`) — stable identity, no offset drift. The Ledger and Run timeline both rely on it.

---

## 6. Wiring order (matches PAGES-SPEC build waves)

1. **Now (no gateway change):** Missions, Mission detail, Codex, Models — already-bound endpoints.
2. **SSE:** add `openRunStream` + `useRunStream`; Run detail goes live.
3. **Gateway PRs (parallel track):** `/v1/runs`, `/v1/audit/events`, `/v1/integrations`, `/v1/system`.
   Until merged, the corresponding pages use the documented interim sources and show a small
   "interim data" note in dev only.
4. **Local-run recipe** (memory: `atlas-local-run-recipe`): boot gateway + cockpit for UAT; the
   gateway binary may be stale and need a rebuild (`cargo build -p atlas-gateway`).

---

## 7. Acceptance

- Run detail streams live events over SSE against a real running run; reconnects on drop; falls back
  to polling; teardown leaks nothing (no dangling EventSource).
- Every page degrades to its offline state with the gateway down — zero uncaught errors.
- Writes (create mission, launch/cancel run, wiki edit) round-trip through the CLI and appear on
  next read; the audit ledger shows the resulting events.
- No direct SQLite access from the UI; `GATEWAY` is the only data origin (override via `VITE_GATEWAY`).
