# Cross-Page Control-Plane Doctrine

**Date:** 2026-07-30  
**Status:** accepted from the Phase 10.8 handoff and operator autonomy directive  
**Starting surface:** Skills  

## Outcome

Cockpit management pages must expose operational truth, not only editable
widgets. The shared doctrine is:

1. fast enough to use at catalog scale;
2. explicit about discovered, configured, enabled, and effective state;
3. failure-atomic and conflict-aware when changing state;
4. attributable through durable, searchable receipts;
5. reversible through the same validated mutation path.

The first delivery applies that doctrine to Skills and introduces reusable
receipt UI rather than a Skills-only audit widget. Later deliveries reuse the
same receipt presentation and the existing Audit/Evidence Plane.

## Measured Skills Baseline

The installed 0.1.5 gateway was restarted and measured on the target Windows
workstation:

| Metric | Observed |
|---|---:|
| Discovered skills | 86 |
| JSON payload | 75,207 bytes |
| Five request times | 818, 1,584, 735, 1,591, 734 ms |
| Median | 818 ms |
| Maximum | 1,591 ms |

The main delay is not React filtering. Every `GET /api/skills` starts a new
`atlas skills list --json` process, imports the Python runtime and Hermes skill
parser, recursively reads every `SKILL.md`, then returns the complete catalog.
The page also renders every matching card and recomputes category counts with a
scan per category.

The existing tier write is atomic at the final file replacement but has no
cross-process lock, expected-state conflict check, durable audit receipt,
reason, or rollback affordance. It also accepts an unknown skill ID into the
override file.

## Cross-Page Findings Matrix

Priority is based on mutation risk, operator frequency, and how much existing
infrastructure can be reused.

| Priority | Surface | Performance | State/edit contract | Audit/reversal gap | Direction |
|---|---|---|---|---|---|
| P0 | Skills | Full process + full recursive scan on every read; full card DOM | Tier is an immediate global override; discovered/configured/effective are conflated | No actor/reason/receipt/history/undo; no conflict guard | Gateway cache, bounded rendering, locked expected-state write, durable receipt, immediate rollback |
| P1 | Provider Settings / Models | Parallel reads are reasonable; model catalog may grow | Revisioned config patch already gives conflict safety and effective-source metadata | Cockpit hides most source metadata and the durable `config_change` receipt; no visible undo | Reuse receipt UI; expose configured/effective source and changed revision |
| P1 | Control: channels, modules, sidecars | Polling composes several subprocess-backed calls | Immediate global toggles mix configuration with observed runtime state | Sparse reason/history/rollback presentation; partial failures collapse to banners | Standard mutation state, reason, receipt, and reconcile-after-write contract |
| P1 | Discord | Polling and guild structure are bounded per selection | Strong propose → approve → execute state machine | Approval history exists, but rollback varies by Discord action | Treat as reference approval pattern; add compensating-action guidance, not fake rollback |
| P2 | Teams / presets | Whole lists; acceptable at current scale | CRUD and run lifecycle are explicit | History is fragmented across cards/run evidence; delete/archive distinctions need consistent receipts | Reuse receipt/history presentation and truthful destructive-state labels |
| P2 | Projects / Missions / Graph scopes | Bounded lists except graph rendering | Direct CRUD with localized validation | Actor/reason and before/after are not consistently visible; rollback depends on resource | Adopt shared receipt UI; add resource-specific compensation only where safe |
| P2 | Ledger / Evidence Inspector | Already cursor/range bounded | Read-only, owner-authorized | Fresh-session missing ownership is mislabeled as gateway failure | Preserve as audit authority; distinguish “no owning session” from offline |
| P3 | Sessions / Runs / Integrations | Server-bounded or composed read-only views | Observational | No direct mutation rollback requirement | Keep read-only; improve provenance links when shared receipts exist |

## Considered Approaches

### 1. Frontend-only optimization

Memoize filters, render fewer cards, and show an optimistic toast. This is the
smallest diff, but it leaves the 0.7–1.6 second subprocess scan, unsafe
concurrent writes, and absent durable receipts untouched. Rejected.

### 2. Shared cache + audited mutation receipt

Cache the parsed catalog in the Rust gateway with bounded freshness and explicit
cache metadata. Invalidate after a successful tier mutation. Make the Python
mutation path validate the skill, lock the override store, reject stale
expected state, emit a masked `config_change` audit event, and return its ID.
Render a reusable receipt with before/after, actor surface, timestamp, reason,
and one-click rollback through the same guarded endpoint. Add bounded card
rendering and memoized indexes in React.

This is the selected approach. It fixes the measured bottleneck and establishes
the smallest reusable control-plane pattern without a new event bus, database,
or dependency.

### 3. Rust/SQLite skill registry migration

Persist the entire catalog, provenance, revisions, and history in SQLite and
make Rust the scanner. This is the strongest long-term model, but it duplicates
the Hermes parser or adds a new YAML dependency and expands the cutover blast
radius. Deferred until catalog mutation extends beyond loading tiers.

## Selected Contract

### Read

`GET /api/skills` keeps the current `skills` array and adds metadata:

- `total`;
- `catalog_generated_at`;
- `cache_status` (`fresh` or `refreshed`);
- `cache_ttl_seconds`.

The Rust gateway holds a per-command cache. A normal read inside the TTL returns
without starting Python. A tier write invalidates the matching cache only after
the CLI reports success. The frontend keeps the last successful module-level
snapshot so navigation back to Skills can render immediately while revalidating.

### Write

`PUT /api/skills/tier` accepts:

- `id`;
- `tier`;
- `expected_tier`;
- `reason`;
- `source_surface`.

The Python service:

1. scans to prove the skill exists;
2. acquires the owner-local tier-store lock;
3. reloads the current override while locked;
4. rejects an expected-tier mismatch without writing;
5. durably replaces the override map;
6. emits a redacted `config_change` event on the synthetic operator run;
7. returns a receipt containing event ID, skill identity, before/after tier,
   actor surface, reason, and timestamp.

If the file commit succeeds but audit persistence fails, the response states
that the tier is committed and requires reconciliation. It must never report a
clean failure that invites an unsafe blind retry.

### UI

A shared `ControlReceipt` component renders resource, action, actor, timestamp,
reason, before/after values, and audit event ID. Skills uses it after every
change. `Undo` sends the receipt’s `before` tier through the same API with the
current `after` tier as its expected state.

The page distinguishes:

- discovered source (`ATLAS`, `HERMES`, third party);
- configured loading tier;
- effective enabled state;
- catalog freshness.

Search/category indexes are memoized. Only the first bounded page of cards is
mounted; “Show more” grows the window without a new dependency.

## Verification

- Python unit tests cover legacy override reads, lock-safe writes, unknown IDs,
  expected-state conflicts, durable receipt emission, and audit-failure truth.
- Rust API tests cover cache hits, TTL metadata, invalidation after mutation,
  structured receipt pass-through, and failed writes preserving the cache.
- React tests cover bounded initial rendering, source/effective labels,
  successful receipt display, conflict/failure truth, and guarded undo.
- Performance acceptance on the installed stack:
  - warm `GET /api/skills` p95 below 50 ms;
  - initial DOM at most 36 skill cards;
  - no full catalog refetch after a successful tier write;
  - no false success on any non-2xx mutation response.

## Next Reuse

After Skills is green, apply `ControlReceipt` to Provider Settings and Models,
where the backend already emits revisioned masked `config_change` events. Then
standardize Control page lifecycle/toggle mutations. Discord remains the
approval reference implementation; Ledger remains the durable audit explorer.
