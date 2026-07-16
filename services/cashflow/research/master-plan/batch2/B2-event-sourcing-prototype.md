# B2 — Event Sourcing Prototype Design: Journal Entries

> Date: 2026-07-10 · Timebox: 1 week · Fallback: Traditional CRUD
> Decision: Prototype event sourcing for journal entries to validate audit trail benefit vs complexity (R2 mitigation)

---

## 1. Scope

**In scope**: Journal entries ONLY — the single most audit-sensitive financial entity.

**Out of scope**: All other financial data (invoices, payments, expenses, bank transactions, chart of accounts, contacts, settings). These use traditional CRUD regardless of event sourcing outcome.

**Rationale**: Journal entries are the atomic unit of double-entry bookkeeping. Every financial transaction eventually produces journal entries. An append-only event log for entries provides:
- Complete audit trail (who changed what, when, why)
- Point-in-time reconstruction of ledger state
- Tamper-evident record for compliance (SPED, Receita Federal audits)
- Foundation for multi-GAAP adjustment layers (IFRS 15/16/17/18)

**What this prototype proves**: Whether the audit trail and replay capability justify the added complexity of event sourcing over a simpler `journal_entries` table with an `audit_log`.

---

## 2. Event Store Schema

The event store is a PostgreSQL table. No external event bus for the prototype — keep it simple.

```sql
-- Core event store
CREATE TABLE journal_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id    UUID NOT NULL,           -- journal entry ID
    event_type      VARCHAR(100) NOT NULL,   -- e.g. 'journal_entry.created'
    event_version   INTEGER NOT NULL,        -- optimistic concurrency version
    event_data      JSONB NOT NULL,          -- event payload
    metadata        JSONB DEFAULT '{}',      -- tenant_id, user_id, ip, idempotency_key
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    -- Optimistic concurrency: one event per version per aggregate
    UNIQUE (aggregate_id, event_version)
);

-- Indexes for the prototype
CREATE INDEX idx_journal_events_aggregate ON journal_events (aggregate_id, event_version);
CREATE INDEX idx_journal_events_type ON journal_events (event_type, created_at);
CREATE INDEX idx_journal_events_metadata ON journal_events USING GIN (metadata jsonb_path_ops);
```

### Schema Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Primary key** | UUID | Multi-tenant safe, no sequence contention, D-005 compliant |
| **aggregate_id** | UUID | Maps to `journal_entry_id`. One journal entry = one aggregate |
| **event_version** | INTEGER | Monotonic per aggregate. Starts at 1, increments by 1 |
| **event_data** | JSONB | Flexible payload. Events differ in shape (created has lines, posted has posting_date) |
| **metadata** | JSONB | Audit context: tenant_id, user_id, ip_address, idempotency_key |
| **UNIQUE constraint** | (aggregate_id, version) | Enforces optimistic concurrency at the DB level |

### Why Not Redis Streams (Yet)

The tech stack decision (B1-tech-stack) recommends Redis Streams for production event bus. The prototype uses PostgreSQL as the event store because:
1. No extra infrastructure to learn or operate
2. Supabase supports it natively (shared DB + RLS later)
3. PostgreSQL's JSONB is sufficient for event payloads
4. The UNIQUE constraint handles concurrency without custom logic
5. Migration to Redis Streams later is straightforward: read from PG, write to Redis

---

## 3. Event Types

Three event types cover the journal entry lifecycle:

### `journal_entry.created`
Fired when a new journal entry is drafted (before posting). Contains the full entry with lines.

```json
{
  "event_type": "journal_entry.created",
  "event_data": {
    "entry_id": "uuid-123",
    "entry_date": "2026-07-10",
    "description": "Venda de consultoria - Cliente X",
    "reference": "NF-2026-001",
    "lines": [
      {
        "account_code": "1.1.01.01",
        "account_name": "Banco Itaú",
        "debit": 5000.00,
        "credit": 0.00,
        "description": "Recebimento via Pix"
      },
      {
        "account_code": "3.1.01.01",
        "account_name": "Receita de Consultoria",
        "debit": 0.00,
        "credit": 5000.00,
        "description": "Receita bruta"
      }
    ],
    "status": "DRAFT",
    "currency": "BRL",
    "created_by": "user-uuid-456"
  },
  "metadata": {
    "tenant_id": "tenant-789",
    "user_id": "user-uuid-456",
    "idempotency_key": "idem-uuid-abc"
  }
}
```

### `journal_entry.posted`
Fired when the entry is posted to the general ledger (becomes immutable).

```json
{
  "event_type": "journal_entry.posted",
  "event_data": {
    "entry_id": "uuid-123",
    "posting_date": "2026-07-10",
    "posted_by": "user-uuid-456",
    "fiscal_period": "2026-07",
    "is_final": true
  },
  "metadata": {
    "tenant_id": "tenant-789",
    "user_id": "user-uuid-456"
  }
}
```

### `journal_entry.voided`
Fired when a posted entry is voided (reversal entry created, original marked voided).

```json
{
  "event_type": "journal_entry.voided",
  "event_data": {
    "entry_id": "uuid-123",
    "voided_by": "user-uuid-456",
    "void_reason": "Duplicate entry — invoice was cancelled",
    "reversal_entry_id": "uuid-456",
    "voided_at": "2026-07-11T10:30:00Z"
  },
  "metadata": {
    "tenant_id": "tenant-789",
    "user_id": "user-uuid-456"
  }
}
```

### Future Event Types (Not in Prototype)

- `journal_entry.amended` — correction entries (compensating entries)
- `journal_entry.approved` — approval workflow integration
- `journal_entry.reconciled` — bank reconciliation link

---

## 4. Aggregate Root: JournalEntry Class

The aggregate root is the single object responsible for validating and applying events. It reconstructs its state by replaying all events for its `aggregate_id`.

```typescript
// lib/events/aggregates/JournalEntry.ts

interface JournalEntryState {
  entryId: string;
  entryDate: string;
  description: string;
  reference?: string;
  lines: JournalLine[];
  status: 'DRAFT' | 'POSTED' | 'VOIDED';
  currency: string;
  createdBy: string;
  postingDate?: string;
  fiscalPeriod?: string;
  voidReason?: string;
  reversalEntryId?: string;
  version: number;
}

interface JournalLine {
  accountCode: string;
  accountName: string;
  debit: number;
  credit: number;
  description?: string;
}

class JournalEntry {
  private state: JournalEntryState;
  private uncommittedEvents: Event[] = [];

  constructor() {
    this.state = {
      entryId: '',
      entryDate: '',
      description: '',
      lines: [],
      status: 'DRAFT',
      currency: 'BRL',
      createdBy: '',
      version: 0,
    };
  }

  // --- Command methods (validate + emit) ---

  create(entry: CreateEntryCommand): void {
    // Validation
    if (entry.lines.length < 2) {
      throw new Error('Journal entry requires at least 2 lines');
    }
    const totalDebit = entry.lines.reduce((sum, l) => sum + l.debit, 0);
    const totalCredit = entry.lines.reduce((sum, l) => sum + l.credit, 0);
    if (Math.abs(totalDebit - totalCredit) > 0.01) {
      throw new Error(`Debits (${totalDebit}) != Credits (${totalCredit})`);
    }

    this.apply({
      event_type: 'journal_entry.created',
      event_data: {
        entry_id: entry.entryId,
        entry_date: entry.entryDate,
        description: entry.description,
        reference: entry.reference,
        lines: entry.lines,
        status: 'DRAFT',
        currency: entry.currency || 'BRL',
        created_by: entry.createdBy,
      },
    });
  }

  post(postingDate: string, fiscalPeriod: string, postedBy: string): void {
    if (this.state.status !== 'DRAFT') {
      throw new Error(`Cannot post entry in status ${this.state.status}`);
    }

    this.apply({
      event_type: 'journal_entry.posted',
      event_data: {
        entry_id: this.state.entryId,
        posting_date: postingDate,
        posted_by: postedBy,
        fiscal_period: fiscalPeriod,
        is_final: true,
      },
    });
  }

  void(voidedBy: string, reason: string, reversalEntryId: string): void {
    if (this.state.status !== 'POSTED') {
      throw new Error(`Cannot void entry in status ${this.state.status}`);
    }

    this.apply({
      event_type: 'journal_entry.voided',
      event_data: {
        entry_id: this.state.entryId,
        voided_by: voidedBy,
        void_reason: reason,
        reversal_entry_id: reversalEntryId,
        voided_at: new Date().toISOString(),
      },
    });
  }

  // --- Event application (pure state mutation) ---

  private apply(event: Omit<Event, 'event_version' | 'created_at'>): void {
    this.state.version++;
    const versionedEvent = { ...event, event_version: this.state.version };
    this.routeEvent(versionedEvent);
    this.uncommittedEvents.push(versionedEvent);
  }

  private routeEvent(event: Event): void {
    switch (event.event_type) {
      case 'journal_entry.created':
        this.state.entryId = event.event_data.entry_id;
        this.state.entryDate = event.event_data.entry_date;
        this.state.description = event.event_data.description;
        this.state.reference = event.event_data.reference;
        this.state.lines = event.event_data.lines;
        this.state.status = 'DRAFT';
        this.state.currency = event.event_data.currency;
        this.state.createdBy = event.event_data.created_by;
        break;
      case 'journal_entry.posted':
        this.state.status = 'POSTED';
        this.state.postingDate = event.event_data.posting_date;
        this.state.fiscalPeriod = event.event_data.fiscal_period;
        break;
      case 'journal_entry.voided':
        this.state.status = 'VOIDED';
        this.state.voidReason = event.event_data.void_reason;
        this.state.reversalEntryId = event.event_data.reversal_entry_id;
        break;
    }
  }

  // --- Reconstruction from events ---

  static fromEvents(events: Event[]): JournalEntry {
    const entry = new JournalEntry();
    for (const event of events) {
      entry.routeEvent(event);
      entry.state.version = event.event_version;
    }
    return entry;
  }

  getState(): Readonly<JournalEntryState> {
    return { ...this.state };
  }

  getUncommittedEvents(): Event[] {
    return [...this.uncommittedEvents];
  }

  clearUncommittedEvents(): void {
    this.uncommittedEvents = [];
  }
}
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **State reconstruction** | `fromEvents()` static factory | Replays events in order, builds state. Standard event sourcing pattern |
| **Validation** | In command methods, NOT in event handler | Commands enforce invariants; events are facts that already happened |
| **Version tracking** | Per-aggregate counter | Enables optimistic concurrency (UNIQUE constraint catches conflicts) |
| **Balance check** | In `create()`, not in `apply()` | Validate before emitting. Events that already happened are assumed valid |
| **Event data** | JSONB-friendly objects | No strong typing on stored events — the aggregate handles deserialization |

---

## 5. Optimistic Concurrency

**Mechanism**: The `UNIQUE(aggregate_id, event_version)` constraint on `journal_events` table.

**How it works**:
1. Client reads the aggregate (replays events → current version = N)
2. Client issues a command (e.g., `post()`) → the aggregate emits an event with version N+1
3. Application tries to INSERT the event with `event_version = N+1`
4. If another client already inserted version N+1, the UNIQUE constraint rejects the INSERT
5. Application catches the constraint violation, re-reads the aggregate, and retries or returns an error

```typescript
// lib/events/store/EventStore.ts

async function appendEvents(
  events: Event[],
  expectedVersion: number
): Promise<void> {
  // The UNIQUE(aggregate_id, event_version) constraint handles concurrency.
  // If expectedVersion doesn't match the DB state, INSERT fails.
  for (const event of events) {
    const result = await db.insert('journal_events', {
      event_id: crypto.randomUUID(),
      aggregate_id: event.aggregate_id,
      event_type: event.event_type,
      event_version: event.event_version,
      event_data: event.event_data,
      metadata: event.metadata || {},
    });
    // If result is a unique violation, another writer got there first
  }
}
```

**Conflict resolution options** (pick one for the prototype):
- **Fail fast**: Return 409 Conflict to the user. Let them refresh and retry.
- **Last writer wins**: Re-read, rebase, retry. Risky for financial data — not recommended.
- **Pessimistic lock**: SELECT FOR UPDATE on the aggregate. Adds latency but eliminates conflicts.

**Recommendation**: Fail fast. Journal entries are short-lived in draft status. Concurrent edits to the same draft are rare.

---

## 6. Snapshot Strategy

Replaying all events from the beginning becomes slow as the event count grows. Snapshots store a materialized state at a specific version, allowing replay to start from the snapshot instead of event #1.

### Snapshot Table

```sql
CREATE TABLE journal_entry_snapshots (
    aggregate_id    UUID NOT NULL,
    snapshot_version INTEGER NOT NULL,  -- version at time of snapshot
    snapshot_data   JSONB NOT NULL,     -- materialized JournalEntryState
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (aggregate_id, snapshot_version)
);
```

### When to Create Snapshots

**Rule: Every N events per aggregate (default N=50)**.

Journal entries are relatively short-lived aggregates:
- Created → Posted → possibly Voided
- Most entries have 3-5 events (created, posted, maybe amended)
- At 50 events per snapshot, an entry with 20 events would never snapshot

**Practical threshold**: For the prototype, snapshot after the aggregate reaches 50 events. In production, tune based on actual event volume per entry.

### Snapshot + Replay Flow

```typescript
async function loadAggregate(aggregateId: string): Promise<JournalEntry> {
  // 1. Try to load latest snapshot
  const snapshot = await db.query(
    'SELECT * FROM journal_entry_snapshots WHERE aggregate_id = $1 ORDER BY snapshot_version DESC LIMIT 1',
    [aggregateId]
  );
  
  if (snapshot) {
    // 2. Load events AFTER the snapshot version
    const events = await db.query(
      'SELECT * FROM journal_events WHERE aggregate_id = $1 AND event_version > $2 ORDER BY event_version',
      [aggregateId, snapshot.snapshot_version]
    );
    
    // 3. Rebuild from snapshot + remaining events
    return JournalEntry.fromSnapshotAndEvents(snapshot.snapshot_data, events);
  }
  
  // 4. No snapshot — replay all events
  const allEvents = await db.query(
    'SELECT * FROM journal_events WHERE aggregate_id = $1 ORDER BY event_version',
    [aggregateId]
  );
  
  return JournalEntry.fromEvents(allEvents);
}
```

### Snapshot Frequency Analysis

| Events per aggregate | Without snapshot | With snapshot (every 50) | Improvement |
|---------------------|------------------|--------------------------|-------------|
| 10 | 10 reads | 10 reads (no snapshot yet) | 0% |
| 50 | 50 reads | 1 snapshot + 0 events = 1 read | 98% |
| 100 | 100 reads | 1 snapshot + 50 events = 51 reads | 49% |
| 200 | 200 reads | 3 snapshots + 50 events = 53 reads | 73% |

**For journal entries**: Most will have <10 events. Snapshots are a safety net, not a performance requirement for the prototype.

---

## 7. Projection: Materialized View for Account Balances

Projections transform event streams into queryable read models. The primary projection for journal entries is account balances.

### Materialized View

```sql
-- Current account balances (refreshed on new journal_entry.posted events)
CREATE MATERIALIZED VIEW mv_account_balances AS
SELECT 
    je.metadata->>'tenant_id' AS tenant_id,
    jel.account_code,
    jel.account_name,
    SUM(jel.debit) AS total_debits,
    SUM(jel.credit) AS total_credits,
    SUM(jel.debit) - SUM(jel.credit) AS net_balance,
    MAX(je.event_version) AS last_event_version,
    NOW() AS refreshed_at
FROM journal_events je,
     jsonb_to_recordset(je.event_data->'lines') AS jel(
         account_code TEXT,
         account_name TEXT,
         debit NUMERIC(15,2),
         credit NUMERIC(15,2)
     )
WHERE je.event_type = 'journal_entry.posted'
GROUP BY je.metadata->>'tenant_id', jel.account_code, jel.account_name;

-- Unique index for REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX idx_mv_account_balances 
ON mv_account_balances (tenant_id, account_code);
```

### Refresh Strategy

```sql
-- Refresh triggered after new journal_entry.posted events
-- Option 1: Periodic (simple, acceptable for prototype)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_account_balances;

-- Option 2: Event-driven (production)
-- In the event handler after journal_entry.posted:
--   1. Update the materialized view incrementally (not full refresh)
--   2. Or: trigger a background job to refresh
```

### Incremental Projection (Production Pattern)

For production, avoid full materialized view refresh. Instead, maintain a projection table that gets updated incrementally:

```sql
CREATE TABLE account_balance_projections (
    tenant_id       UUID NOT NULL,
    account_code    VARCHAR(50) NOT NULL,
    account_name    VARCHAR(100) NOT NULL,
    total_debits    NUMERIC(15,2) DEFAULT 0,
    total_credits   NUMERIC(15,2) DEFAULT 0,
    net_balance     NUMERIC(15,2) GENERATED ALWAYS AS (total_debits - total_credits) STORED,
    last_event_id   UUID,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (tenant_id, account_code)
);
```

When a `journal_entry.posted` event is applied:
```sql
UPDATE account_balance_projections
SET 
    total_debits = total_debits + $new_debits,
    total_credits = total_credits + $new_credits,
    last_event_id = $event_id,
    updated_at = NOW()
WHERE tenant_id = $tenant_id AND account_code = $account_code;
```

---

## 8. Replay Capability

Replay reconstructs the state of any journal entry at any point in time. This is the core audit trail benefit.

### Full Replay: Reconstruct Ledger State at Time T

```sql
-- Get all posted journal entries up to a specific timestamp
SELECT DISTINCT ON (aggregate_id)
    aggregate_id,
    event_data
FROM journal_events
WHERE event_type = 'journal_entry.posted'
  AND created_at <= '2026-07-10T15:00:00Z'
ORDER BY aggregate_id, event_version DESC;
```

### Partial Replay: Single Entry History

```sql
-- Full event history for one journal entry
SELECT event_type, event_version, event_data, metadata, created_at
FROM journal_events
WHERE aggregate_id = 'uuid-123'
ORDER BY event_version;
```

### Replay for Compliance Audit

```sql
-- Who changed entry X, when, and why?
SELECT 
    event_type,
    event_version,
    metadata->>'user_id' AS changed_by,
    metadata->>'ip_address' AS from_ip,
    created_at,
    CASE event_type
        WHEN 'journal_entry.created' THEN 'Created draft'
        WHEN 'journal_entry.posted' THEN 'Posted to ledger'
        WHEN 'journal_entry.voided' THEN 'Voided: ' || event_data->>'void_reason'
    END AS action_description
FROM journal_events
WHERE aggregate_id = 'uuid-123'
ORDER BY event_version;
```

### Replay Use Cases

| Use Case | Query | Value |
|----------|-------|-------|
| **Audit trail** | Full event history for an entry | Who changed what, when, from where |
| **Point-in-time balance** | All posted entries up to timestamp T | Balance sheet at any historical date |
| **Regulatory audit** | All entries in a fiscal period | SPED ECD book validation |
| **Dispute resolution** | Entry history with user metadata | Prove a transaction was legitimate |
| **Debugging** | Event replay from creation to current state | Find where an entry went wrong |
| **Data migration** | Replay events into new schema | Rebuild state in a different system |

---

## 9. CQRS Integration

CQRS (Command Query Responsibility Segregation) separates write operations (commands → event store) from read operations (queries → materialized views).

### Write Side (Commands → Event Store)

```
User Action → API Route → Command Handler → Aggregate → Event Store
                                                    ↓
                                              (events persisted)
```

```typescript
// lib/commands/handlers/PostJournalEntry.ts

async function handlePostJournalEntry(command: PostJournalEntryCommand): Promise<void> {
  // 1. Load aggregate from event store
  const entry = await loadAggregate(command.entryId);
  
  // 2. Execute command (validates + emits event)
  entry.post(command.postingDate, command.fiscalPeriod, command.postedBy);
  
  // 3. Persist uncommitted events (optimistic concurrency via UNIQUE constraint)
  await appendEvents(entry.getUncommittedEvents(), entry.getState().version);
  
  // 4. Clear uncommitted events
  entry.clearUncommittedEvents();
  
  // 5. Trigger projection refresh (async, non-blocking)
  await triggerBalanceProjectionRefresh(command.tenantId);
}
```

### Read Side (Queries → Materialized Views)

```
User Query → API Route → Query Handler → Materialized View / Read Model
                                                ↓
                                          (fast read, no computation)
```

```typescript
// lib/queries/handlers/GetAccountBalances.ts

async function handleGetAccountBalances(tenantId: string): Promise<AccountBalance[]> {
  // Read from materialized view — fast, pre-computed
  return db.query(
    'SELECT * FROM mv_account_balances WHERE tenant_id = $1 ORDER BY account_code',
    [tenantId]
  );
}
```

### CQRS Data Flow

```
┌─────────────────────────────────────────────────────┐
│                    WRITE SIDE                        │
│                                                      │
│  POST /api/v1/journal-entries                        │
│       ↓                                              │
│  Command Handler                                     │
│       ↓                                              │
│  JournalEntry.create() → validate → emit event       │
│       ↓                                              │
│  Event Store (journal_events table)                  │
│       ↓                                              │
│  Event Bus (LISTEN/NOTIFY → projection updater)      │
│                                                      │
└─────────────────────────────────────────────────────┘
                         ↓
              ┌──────────────────┐
              │   EVENT BUS      │
              │   (PG NOTIFY)    │
              └──────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│                    READ SIDE                         │
│                                                      │
│  Projection Handler                                  │
│       ↓                                              │
│  mv_account_balances (materialized view)             │
│  mv_trial_balance (materialized view)                │
│  mv_journal_entries_read (materialized view)         │
│       ↓                                              │
│  GET /api/v1/account-balances                        │
│  GET /api/v1/journal-entries                         │
│  GET /api/v1/trial-balance                           │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Event Bus: PostgreSQL LISTEN/NOTIFY

The tech stack decision chose PG LISTEN/NOTIFY for MVP. Here's how it connects write → read:

```sql
-- After inserting a new journal_event, notify projections
NOTIFY journal_events_channel, '{"event_type":"journal_entry.posted","aggregate_id":"uuid-123"}';
```

```typescript
// Projection listener
const client = await pg.connect();
await client.query('LISTEN journal_events_channel');
client.on('notification', async (msg) => {
  const payload = JSON.parse(msg.payload);
  if (payload.event_type === 'journal_entry.posted') {
    await refreshAccountBalances(payload.aggregate_id);
  }
});
```

---

## 10. Fallback Plan: Traditional CRUD

If event sourcing proves too complex during the 1-week prototype, fall back to a traditional schema with an audit log.

### Fallback Schema

```sql
-- Traditional journal entries table (no event sourcing)
CREATE TABLE journal_entries (
    entry_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    entry_date      DATE NOT NULL,
    description     TEXT NOT NULL,
    reference       VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'DRAFT', -- DRAFT, POSTED, VOIDED
    currency        VARCHAR(3) DEFAULT 'BRL',
    fiscal_period   VARCHAR(7), -- YYYY-MM
    posting_date    DATE,
    created_by      UUID NOT NULL REFERENCES users(id),
    posted_by       UUID REFERENCES users(id),
    voided_by       UUID REFERENCES users(id),
    void_reason     TEXT,
    reversal_entry_id UUID REFERENCES journal_entries(entry_id),
    version         INTEGER DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Journal entry lines (double-entry bookkeeping)
CREATE TABLE journal_entry_lines (
    line_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id        UUID NOT NULL REFERENCES journal_entries(entry_id),
    account_code    VARCHAR(50) NOT NULL,
    account_name    VARCHAR(100) NOT NULL,
    debit           NUMERIC(15,2) DEFAULT 0,
    credit          NUMERIC(15,2) DEFAULT 0,
    description     TEXT,
    line_order      INTEGER NOT NULL,
    
    CHECK (debit >= 0 AND credit >= 0),
    CHECK (debit > 0 OR credit > 0),
    UNIQUE (entry_id, line_order)
);

-- Audit log (append-only, separate from main table)
CREATE TABLE journal_audit_log (
    audit_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id        UUID NOT NULL,
    action          VARCHAR(50) NOT NULL, -- CREATED, POSTED, VOIDED, UPDATED
    changed_by      UUID NOT NULL,
    changed_at      TIMESTAMPTZ DEFAULT NOW(),
    old_values      JSONB,
    new_values      JSONB,
    ip_address      INET,
    idempotency_key VARCHAR(100)
);

-- Concurrency control
CREATE UNIQUE INDEX idx_je_version ON journal_entries (entry_id, version);
```

### Fallback Pros and Cons

| Aspect | Event Sourcing | Traditional CRUD + Audit Log |
|--------|---------------|------------------------------|
| **Audit trail** | Complete event history, replayable | Audit log captures before/after snapshots |
| **Replay** | Full point-in-time reconstruction | Partial — only snapshots, not every change |
| **Complexity** | Higher (aggregate, event store, projections) | Lower (standard CRUD + separate audit table) |
| **Query performance** | Requires materialized views | Direct table queries with indexes |
| **Multi-GAAP** | Natural (adjustment layers = event streams) | Requires separate adjustment tables |
| **Compliance** | Tamper-evident append-only log | Audit log is append-only but separate |
| **Developer velocity** | Slower initially, faster for audit-heavy features | Faster initially, slower for audit features |

### Decision Criteria: Keep or Fall Back

**Keep event sourcing if**:
- The team can build a working aggregate + event store in <3 days
- Replay produces correct results for all test cases
- The audit trail provides clear value over the audit_log table
- The CQRS projection refresh is performant (<200ms)

**Fall back to CRUD if**:
- The aggregate logic takes >4 days to stabilize
- Optimistic concurrency causes frequent conflicts in testing
- The team finds the event replay pattern confusing
- The audit log table already satisfies compliance requirements

---

## 11. Success Criteria

What metrics determine if event sourcing is worth keeping?

### Quantitative Criteria

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Prototype completion** | All 3 event types working in <5 days | Calendar tracking |
| **Event write latency** | <50ms for single event append | Benchmark with `pgbench` or Vitest |
| **Aggregate load time** | <100ms for entry with <20 events | Benchmark `loadAggregate()` |
| **Replay accuracy** | 100% match between replay state and latest snapshot | Automated test: create entry, apply events, compare |
| **Projection refresh** | <500ms for balance materialized view refresh | Benchmark `REFRESH MATERIALIZED VIEW CONCURRENTLY` |
| **Optimistic concurrency** | Correct conflict detection (no silent overwrites) | Test with concurrent writes |
| **Audit trail completeness** | Every state change captured as an event | Code review: no direct state mutations outside aggregate |

### Qualitative Criteria

| Criterion | Evaluation Method |
|-----------|-------------------|
| **Team comprehension** | Can the team explain event sourcing to a new developer in <15 minutes? |
| **Debugging experience** | Is it easier to debug a failed journal entry with event replay than without? |
| **Compliance value** | Does the event store satisfy a simulated Receita Federal audit request? |
| **Code readability** | Is the aggregate code cleaner than equivalent CRUD with audit log? |
| **Migration readiness** | How easy is it to add a new event type (e.g., journal_entry.amended)? |

### Go/No-Go Decision Matrix

| Score | Decision | Action |
|-------|----------|--------|
| **7/7 quantitative + 4/5 qualitative** | GO — keep event sourcing | Use as production pattern for journal entries |
| **5-6 quantitative + 3-4 qualitative** | CONDITIONAL — keep with caveats | Simplify: drop snapshots, use simpler projection |
| **<5 quantitative OR <3 qualitative** | NO-GO — fall back to CRUD | Use traditional schema + audit_log table |

---

## 12. Time Budget: 1-Week Prototype

### Day 1: Foundation (Event Store + Aggregate)

| Task | Hours | Deliverable |
|------|-------|-------------|
| Create `journal_events` table in Supabase | 1 | SQL migration |
| Implement `JournalEntry` aggregate class | 3 | TypeScript class with `create()`, `post()`, `void()` |
| Implement `EventStore.append()` and `EventStore.load()` | 2 | Event persistence and loading |
| Unit tests: aggregate lifecycle (create → post → void) | 2 | 10+ test cases |
| **Day 1 checkpoint**: Aggregate works in isolation | — | Tests pass |

### Day 2: CQRS Read Side (Materialized Views)

| Task | Hours | Deliverable |
|------|-------|-------------|
| Create `mv_account_balances` materialized view | 1 | SQL |
| Implement projection refresh trigger (PG LISTEN/NOTIFY) | 2 | Event bus + projection handler |
| Implement query handlers (GetAccountBalances, GetJournalEntries) | 2 | Read-side API |
| Unit tests: projection refresh, query correctness | 2 | 8+ test cases |
| **Day 2 checkpoint**: Write → event store → projection → read works end-to-end | — | Integration test passes |

### Day 3: Optimistic Concurrency + Snapshot

| Task | Hours | Deliverable |
|------|-------|-------------|
| Test UNIQUE constraint concurrency handling | 1 | Concurrent write test |
| Implement conflict detection and error handling | 1 | 409 Conflict response |
| Implement snapshot creation (every 50 events) | 1 | Snapshot table + logic |
| Implement `loadAggregate()` with snapshot support | 1 | Snapshot-aware loading |
| Stress test: 100 concurrent writes, verify no data corruption | 2 | Load test results |
| **Day 3 checkpoint**: Concurrency works, snapshots work | — | All tests pass |

### Day 4: Replay + Audit Trail

| Task | Hours | Deliverable |
|------|-------|-------------|
| Implement full replay: reconstruct entry at any point in time | 2 | Replay function + tests |
| Implement audit trail query: full event history per entry | 1 | Query + test |
| Implement point-in-time balance query | 1 | Query + test |
| Create seed data: 1000 journal entries with varied events | 1 | Seed script |
| Performance test: replay 1000 entries, measure time | 1 | Benchmark results |
| **Day 4 checkpoint**: Replay works, audit trail is complete | — | All tests pass |

### Day 5: API Routes + Integration

| Task | Hours | Deliverable |
|------|-------|-------------|
| Wire up Next.js API routes to event store | 2 | POST/GET endpoints |
| Wire up Server Actions for journal entry operations | 2 | Form handling |
| End-to-end test: create → post → query → void → replay | 2 | Playwright or Vitest E2E |
| **Day 5 checkpoint**: Full user flow works through API | — | E2E test passes |

### Day 6: Evaluation + Documentation

| Task | Hours | Deliverable |
|------|-------|-------------|
| Run all success criteria benchmarks | 2 | Results table |
| Write ADR (Architecture Decision Record) for event sourcing | 2 | ADR document |
| Document fallback path (CRUD schema ready if needed) | 1 | Fallback schema |
| Code review of all prototype code | 1 | Review findings |
| **Day 6 checkpoint**: Evaluation complete, decision documented | — | Go/No-Go decision |

### Day 7: Buffer + Hardening

| Task | Hours | Deliverable |
|------|-------|-------------|
| Fix any issues found in Day 6 review | 3 | Bug fixes |
| Add edge case tests (empty entry, single line, future date) | 2 | 15+ additional test cases |
| Final demo: replay an entry's full history | 1 | Demo script |
| **Day 7 checkpoint**: Prototype complete, decision finalized | — | Ready for production decision |

### Total Effort

| Phase | Hours |
|-------|-------|
| Foundation + Aggregate | 8 |
| CQRS + Projections | 7 |
| Concurrency + Snapshots | 6 |
| Replay + Audit | 6 |
| API + Integration | 6 |
| Evaluation | 6 |
| Buffer + Hardening | 6 |
| **Total** | **45 hours** (~1 week full-time) |

---

## Appendix A: File Structure (Prototype)

```
lib/
  events/
    aggregates/
      JournalEntry.ts          # Aggregate root
    store/
      EventStore.ts            # Event persistence (PG)
      SnapshotStore.ts         # Snapshot persistence
    projections/
      AccountBalanceProjection.ts  # Balance materialized view refresh
      EventListener.ts         # PG LISTEN/NOTIFY handler
    types.ts                   # Event, Aggregate interfaces
  commands/
    handlers/
      CreateJournalEntry.ts
      PostJournalEntry.ts
      VoidJournalEntry.ts
  queries/
    handlers/
      GetJournalEntry.ts       # Load from event store
      GetAccountBalances.ts    # Read from materialized view
      GetAuditTrail.ts         # Full event history
  api/
    journal-entries/
      route.ts                 # Next.js API route
      [id]/
        route.ts               # GET/PATCH single entry
        events/
          route.ts             # GET event history

supabase/
  migrations/
    20260710_journal_events.sql         # Event store table
    20260710_mv_account_balances.sql    # Materialized view
    20260710_journal_entry_snapshots.sql # Snapshot table

tests/
  events/
    JournalEntry.test.ts       # Aggregate unit tests
    EventStore.test.ts         # Persistence tests
    Replay.test.ts             # Replay accuracy tests
    Concurrency.test.ts        # Optimistic concurrency tests
```

---

## Appendix B: Key References

- **Risk R2**: Event sourcing adoption risk (B1-risks-blockers.md)
- **Tech stack**: PG LISTEN/NOTIFY for MVP event bus (B1-tech-stack.md §3)
- **Existing patterns**: Repository abstraction in `lib/repositories/` (B1-gap-analysis.md §1.2)
- **Security report**: Journal entry schema with RLS, indexes, partitioning (REPORT-SECURITY-OPS.md §2)
- **F17**: Test patterns for journal entry balancing, contract testing, performance benchmarks
- **F14**: PostgreSQL indexing strategies for journal entry queries

---

*This prototype document should be reviewed against the actual prototype implementation. Update success criteria thresholds based on real benchmark results.*
