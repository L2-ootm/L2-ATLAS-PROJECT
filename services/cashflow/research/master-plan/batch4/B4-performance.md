# B4: Performance Optimization — Production Readiness

**Scope**: L2 Cashflow service  
**Date**: 2026-07-10  
**Status**: PLANNING  

---

## Current State Analysis

| Dimension | Status | Impact |
|-----------|--------|--------|
| Database | SQLite (dev) / Supabase PostgreSQL (prod) | SQLite single-writer; no indexes beyond PK |
| Caching | None | Every request hits DB directly |
| Materialized Views | None | All 6 RPC functions compute aggregations live |
| Connection Pooling | Direct Supabase client | No pool control, no RLS optimization |
| N+1 Queries | Critical | `getLocalEnterpriseContext()` fetches ALL rows then filters in JS |
| Background Jobs | None | SPED generation, bulk imports block the event loop |
| CDN / Assets | Vercel defaults only | No API response compression, no asset fingerprinting |
| Monitoring | `console.error` only | No metrics, no alerting, no SLOs |
| Load Testing | None | No baseline performance data |

---

## 1. Database Indexing

### 1.1 Composite Indexes for Hot Queries

The RPC functions in `supabase/schema.sql` all filter on `client_id + to_char(created_at, 'YYYY-MM')`. This pattern prevents index usage because `to_char()` wraps the column in a function. The fix is a functional index + a date-range approach.

```sql
-- Composite index for usage_events: the single most queried table
-- Covers: P&L, Cost Explorer, Forecast, Operational Report, Commercial Report
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usage_events_client_month
  ON usage_events (client_id, (to_char(created_at, 'YYYY-MM')));

-- Covering index for cost aggregations (avoids heap fetch for cost_brl)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usage_events_cost_covering
  ON usage_events (client_id, created_at)
  INCLUDE (cost_brl, cost_usd, input_tokens, output_tokens,
           cache_hit_tokens, cache_miss_tokens, model_name, user_id);

-- Billing events: filtered by client + event_type + month
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_billing_events_client_type_month
  ON billing_events (client_id, event_type, (to_char(created_at, 'YYYY-MM')));

-- Plus subscriptions: active lookup per client
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_plus_subs_client_status
  ON plus_subscriptions (client_id, status)
  WHERE status = 'active';

-- Invoice line items: period aggregation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invoice_line_items_client_period
  ON invoice_line_items (client_id, period_start, period_end);

-- Contracts: active contract lookup (most common join)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_client_status
  ON contracts (client_id, status)
  WHERE status = 'active';

-- Audit log: time-range queries on the audit screen
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_created
  ON audit_log (created_at DESC);

-- Research jobs: status + priority queue
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_research_jobs_status_priority
  ON research_jobs (status, priority, created_at);
```

### 1.2 Partial Indexes

```sql
-- Only index active client_accounts (most queries filter status = 'active')
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_client_accounts_active
  ON client_accounts (id, name)
  WHERE status = 'active';

-- Only index pending invoices (overdue check, due-soon check)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invoices_pending
  ON Invoice (clientId, dueDate)
  WHERE status = 'pendente';

-- Only index pending research jobs (queue processing)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_research_jobs_pending
  ON research_jobs (created_at, priority)
  WHERE status = 'pending';
```

### 1.3 GIN Indexes for JSONB

```sql
-- metadata_json on usage_events (currently TEXT, migrate to JSONB first)
ALTER TABLE usage_events ALTER COLUMN metadata_json TYPE jsonb
  USING CASE WHEN metadata_json = '' OR metadata_json IS NULL THEN NULL
             ELSE metadata_json::jsonb END;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usage_events_metadata_gin
  ON usage_events USING gin (metadata_json jsonb_path_ops);

-- details_json on audit_log
ALTER TABLE audit_log ALTER COLUMN details_json TYPE jsonb
  USING CASE WHEN details_json = '' OR details_json IS NULL THEN NULL
             ELSE details_json::jsonb END;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_details_gin
  ON audit_log USING gin (details_json jsonb_path_ops);
```

### 1.4 SQLite Indexes (Local Dev)

```sql
-- better-sqlite3: add indexes for local dev parity
CREATE INDEX IF NOT EXISTS idx_sqlite_usage_client_date
  ON usage_events (client_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_sqlite_usage_model
  ON usage_events (model_name, cost_brl);

CREATE INDEX IF NOT EXISTS idx_sqlite_invoice_status_date
  ON Invoice (status, dueDate);

CREATE INDEX IF NOT EXISTS idx_sqlite_expense_date
  ON Expense (date, clientId);

CREATE INDEX IF NOT EXISTS idx_sqlite_partner_tx_date
  ON PartnerTransaction (partnerId, date);
```

---

## 2. Materialized Views

### 2.1 Trial Balance

```sql
CREATE MATERIALIZED VIEW mv_trial_balance AS
SELECT
  client_id,
  (to_char(created_at, 'YYYY-MM')) AS period,
  SUM(cost_brl) AS total_cost,
  SUM(input_tokens) AS total_input_tokens,
  SUM(output_tokens) AS total_output_tokens,
  SUM(cache_hit_tokens) AS total_cache_hits,
  SUM(cache_miss_tokens) AS total_cache_misses,
  COUNT(*) AS event_count,
  COUNT(DISTINCT user_id) AS unique_users,
  COUNT(DISTINCT model_name) AS models_used
FROM usage_events
GROUP BY client_id, (to_char(created_at, 'YYYY-MM'));

CREATE UNIQUE INDEX ON mv_trial_balance (client_id, period);
```

### 2.2 P&L Summary

```sql
CREATE MATERIALIZED VIEW mv_client_pnl AS
SELECT
  ue.client_id,
  (to_char(ue.created_at, 'YYYY-MM')) AS period,
  c.monthly_fee_brl AS contracted_revenue,
  c.min_margin_brl AS min_margin,
  c.ai_budget_hard_cap_brl AS budget_cap,
  SUM(ue.cost_brl) AS ai_cost,
  c.monthly_fee_brl - SUM(ue.cost_brl) AS gross_margin,
  CASE WHEN c.monthly_fee_brl > 0
    THEN ((c.monthly_fee_brl - SUM(ue.cost_brl)) / c.monthly_fee_brl) * 100
    ELSE 0 END AS margin_pct
FROM usage_events ue
JOIN contracts c ON c.client_id = ue.client_id AND c.status = 'active'
GROUP BY ue.client_id, (to_char(ue.created_at, 'YYYY-MM')),
         c.monthly_fee_brl, c.min_margin_brl, c.ai_budget_hard_cap_brl;

CREATE UNIQUE INDEX ON mv_client_pnl (client_id, period);
```

### 2.3 Balance Sheet

```sql
CREATE MATERIALIZED VIEW mv_balance_sheet AS
SELECT
  be.client_id,
  (to_char(be.created_at, 'YYYY-MM')) AS period,
  SUM(CASE WHEN be.event_type = 'payment_received' THEN be.amount_brl ELSE 0 END) AS gross_revenue,
  SUM(CASE WHEN be.event_type = 'payment_received' THEN be.gateway_fee_brl ELSE 0 END) AS gateway_fees,
  SUM(CASE WHEN be.event_type = 'payment_received' THEN be.net_amount_brl ELSE 0 END) AS net_revenue,
  SUM(CASE WHEN be.event_type = 'payment_received' THEN be.l2_share_brl ELSE 0 END) AS l2_share,
  SUM(CASE WHEN be.event_type = 'payment_received' THEN be.client_share_brl ELSE 0 END) AS client_share,
  COUNT(CASE WHEN be.event_type = 'payment_received' THEN 1 END) AS payment_count
FROM billing_events be
GROUP BY be.client_id, (to_char(be.created_at, 'YYYY-MM'));

CREATE UNIQUE INDEX ON mv_balance_sheet (client_id, period);
```

### 2.4 Refresh Strategy

```sql
-- Refresh function: called by background job after new data ingestion
CREATE OR REPLACE FUNCTION refresh_materialized_views()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_trial_balance;
  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_client_pnl;
  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_balance_sheet;
END;
$$;
```

**Refresh triggers**:
- After batch webhook ingestion (every 5 minutes or after 100 events)
- After billing event processing
- Manual refresh via admin endpoint
- `CONCURRENTLY` avoids read locks during refresh

---

## 3. Caching Layers

### 3.1 Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Next.js    │────▶│  Redis       │────▶│  PostgreSQL  │
│  API Layer  │     │  L1 Cache    │     │  (Supabase)  │
└─────────────┘     └──────────────┘     └──────────────┘
       │
       ▼
┌──────────────┐
│  CDN Edge    │
│  (Vercel)    │
└──────────────┘
```

### 3.2 Redis Configuration

```yaml
# redis.conf (production)
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### 3.3 Cache Keys and TTLs

| Key Pattern | TTL | Invalidation | Description |
|-------------|-----|--------------|-------------|
| `session:{userId}` | 30min | On login/logout | User session data |
| `pnl:{clientId}:{period}` | 5min | On usage event insert | P&L computation |
| `cost_explorer:{clientId}:{period}` | 5min | On usage event insert | Cost explorer data |
| `billing:{clientId}:{period}` | 10min | On billing event | Billing metrics |
| `forecast:{clientId}:{period}` | 2min | On usage event insert | Forecast (time-sensitive) |
| `report:commercial:{clientId}:{period}` | 15min | On billing/usage event | Commercial report |
| `report:operational:{clientId}:{period}` | 5min | On usage event insert | Operational report |
| `financial_summary` | 1min | On any CRUD | MCP financial summary |
| `model_rates:{provider}` | 24h | On rate card update | Model rate cards |
| `active_contracts` | 10min | On contract update | Active contract list |

### 3.4 Cache Implementation

```typescript
// lib/cache.ts
import Redis from 'ioredis';

const redis = new Redis(process.env.REDIS_URL!, {
  maxRetriesPerRequest: 3,
  retryDelayOnFailover: 100,
  lazyConnect: true,
});

export async function cached<T>(
  key: string,
  ttlSeconds: number,
  compute: () => Promise<T>
): Promise<T> {
  const hit = await redis.get(key);
  if (hit) return JSON.parse(hit);

  const value = await compute();
  await redis.setex(key, ttlSeconds, JSON.stringify(value));
  return value;
}

export function invalidatePattern(pattern: string): Promise<void> {
  return redis.keys(pattern).then(keys => {
    if (keys.length > 0) return redis.del(...keys);
  });
}

// Usage after webhook ingestion:
// await invalidatePattern(`pnl:${clientId}:*`);
// await invalidatePattern(`cost_explorer:${clientId}:*`);
// await invalidatePattern(`forecast:${clientId}:*`);
```

---

## 4. Connection Pooling

### 4.1 PgBouncer Configuration

```ini
# pgbouncer.ini
[databases]
cashflow = host=aws-0-us-east-1.pooler.supabase.com port=5432 dbname=postgres

[pgbouncer]
pool_mode = transaction
max_client_conn = 100
default_pool_size = 20
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 5
server_idle_timeout = 300
client_idle_timeout = 0
```

### 4.2 Why Transaction Pooling

Supabase uses RLS (Row-Level Security). Transaction pooling works because:
- Each Supabase request sets `SET LOCAL role = 'authenticated'` at the start
- RLS policies evaluate per-statement within the transaction
- Connection release happens after the HTTP response, which is after the transaction

### 4.3 Pool Sizing Formula

```
pool_size = (num_cpu_cores * 2) + effective_spindle_count
For Next.js on Vercel: pool_size = 10-20 (serverless functions, not long-lived)
For background workers: pool_size = 5 (dedicated, predictable load)
```

### 4.4 Supabase Client Configuration

```typescript
// lib/supabase.ts — add pool-aware settings
import { createClient } from '@supabase/supabase-js';

export function getSupabaseClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    {
      db: {
        schema: 'public',
      },
      global: {
        headers: { 'x-cashflow-version': '2.0' },
      },
    }
  );
}
```

---

## 5. Query Optimization

### 5.1 N+1 Elimination

**Critical issue** in `lib/db/enterprise.ts:getLocalEnterpriseContext()`:

```typescript
// BEFORE (N+1 — fetches ALL rows, filters in JS)
const clients = await clientRepo.getAll();           // ALL clients
const usage = (await usageRepo.getAll(500)).filter(  // ALL usage, filter in JS
  (event) => clientIds.has(event.client_id) && eventMatchesMonth(event, period)
);
const invoices = (await invoiceRepo.getAll()).filter(  // ALL invoices, filter in JS
  (invoice) => clientIds.has(invoice.clientId) && ...
);
```

**Fix — add targeted repository methods**:

```typescript
// lib/repositories/types.ts — add new methods
interface IUsageRepository {
  // ...existing...
  getByClientAndPeriod(clientId: string, period: string): Promise<UsageEvent[]>;
  getAggregateByClientAndPeriod(clientId: string, period: string): Promise<UsageAggregate>;
}

interface IInvoiceRepository {
  // ...existing...
  getByClientAndPeriod(clientId: string, period: string): Promise<Invoice[]>;
}
```

```typescript
// lib/repositories/sqlite/usage.ts — add optimized query
async getByClientAndPeriod(clientId: string, period: string): Promise<UsageEvent[]> {
  return db
    .prepare(
      `SELECT * FROM usage_events
       WHERE client_id = ? AND to_char(created_at, 'YYYY-MM') = ?
       ORDER BY created_at DESC`
    )
    .all(clientId, period) as UsageEvent[];
}

async getAggregateByClientAndPeriod(clientId: string, period: string) {
  return db.prepare(
    `SELECT
       SUM(cost_brl) as total_cost,
       SUM(input_tokens) as total_input,
       SUM(output_tokens) as total_output,
       SUM(cache_hit_tokens) as cache_hit,
       SUM(cache_miss_tokens) as cache_miss,
       COUNT(*) as event_count
     FROM usage_events
     WHERE client_id = ? AND to_char(created_at, 'YYYY-MM') = ?`
  ).get(clientId, period);
}
```

```typescript
// lib/repositories/supabase/usage.ts — same pattern
async getByClientAndPeriod(clientId: string, period: string): Promise<UsageEvent[]> {
  const supabase = getSupabaseClient();
  const { data, error } = await supabase
    .from('usage_events')
    .select('*')
    .eq('client_id', clientId)
    .gte('created_at', `${period}-01`)
    .lt('created_at', `${period}-32`)
    .order('created_at', { ascending: false });
  if (error) throw error;
  return data as UsageEvent[];
}
```

### 5.2 RPC Function Optimization

The current RPC functions in `schema.sql` use `to_char(created_at, 'YYYY-MM')` which prevents index usage. Replace with date-range comparisons:

```sql
-- BEFORE (function call prevents index usage)
WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix

-- AFTER (range scan uses index)
WHERE client_id = p_client_id
  AND created_at >= (p_month_prefix || '-01')::timestamp
  AND created_at < (p_month_prefix || '-01')::timestamp + interval '1 month'
```

### 5.3 Eager Loading

```typescript
// lib/db/enterprise.ts — consolidate getLocalEnterpriseContext
async function getLocalEnterpriseContext(
  requestedClientId: string, year: number, month: number
): Promise<LocalEnterpriseContext> {
  const period = monthPrefix(year, month);

  // Parallel fetch with targeted queries (not getAll)
  const [client, usage, invoices] = await Promise.all([
    clientRepo.getById(requestedClientId),
    usageRepo.getByClientAndPeriod(requestedClientId, period),
    invoiceRepo.getByClientAndPeriod(requestedClientId, period),
  ]);

  return { client, usage, invoices, period, contract: buildContract(client) };
}
```

### 5.4 Query Analysis

Add `EXPLAIN ANALYZE` logging for slow queries:

```typescript
// lib/db/query-logger.ts
export function logSlowQuery(query: string, durationMs: number, params?: any[]) {
  if (durationMs > 100) { // threshold: 100ms
    console.warn(`[SLOW QUERY ${durationMs}ms]`, query.slice(0, 200), params);
  }
}
```

---

## 6. Background Jobs

### 6.1 Heavy Operations to Offload

| Operation | Current | Proposed |
|-----------|---------|----------|
| SPED generation | Synchronous, blocks event loop | BullMQ job, webhook on completion |
| Bulk CSV import | Synchronous, O(n) DB writes | Batch insert job, progress SSE |
| Materialized view refresh | Manual/none | Scheduled job every 5min |
| PDF report generation | Synchronous jspdf | Background job, email on complete |
| Audit log aggregation | None | Nightly rollup job |
| Usage event cost calculation | On insert | Deferred batch (every 30s) |

### 6.2 BullMQ Configuration

```typescript
// lib/jobs/queue.ts
import { Queue, Worker } from 'bullmq';
import Redis from 'ioredis';

const connection = new Redis(process.env.REDIS_URL!, {
  maxRetriesPerRequest: null,
});

export const spedQueue = new Queue('sped-generation', { connection });
export const importQueue = new Queue('bulk-import', { connection });
export const refreshQueue = new Queue('mv-refresh', { connection });

// Worker: SPED generation
const spedWorker = new Worker('sped-generation', async (job) => {
  const { clientId, period } = job.data;
  const sped = await generateSPED(clientId, period);
  await uploadToStorage(sped, `sped/${clientId}/${period}.txt`);
  await notifyClient(clientId, 'sped-ready', { period });
}, { connection, concurrency: 2 });

// Worker: Materialized view refresh
const refreshWorker = new Worker('mv-refresh', async () => {
  await supabase.rpc('refresh_materialized_views');
}, { connection, concurrency: 1 });

// Scheduler: refresh every 5 minutes
import { QueueScheduler } from 'bullmq';
new QueueScheduler('mv-refresh', { connection });
```

### 6.3 Progress via Server-Sent Events

```typescript
// app/api/import/route.ts
export async function POST(request: Request) {
  const file = await request.formData();
  const job = await importQueue.add('process', { file }, {
    removeOnComplete: true,
    attempts: 3,
  });
  return NextResponse.json({ jobId: job.id });
}

// app/api/import/progress/[jobId]/route.ts
export async function GET(req, { params }) {
  const stream = new ReadableStream({
    start(controller) {
      const worker = new Worker('bulk-import', null);
      worker.on('progress', (job) => {
        controller.enqueue(`data: ${JSON.stringify(job.progress)}\n\n`);
      });
    },
  });
  return new Response(stream, {
    headers: { 'Content-Type': 'text/event-stream' },
  });
}
```

---

## 7. CDN and Asset Optimization

### 7.1 Static Asset Caching

```typescript
// next.config.ts
const config: NextConfig = {
  // ...existing...
  headers: async () => [
    {
      source: '/_next/static/:path*',
      headers: [
        { key: 'Cache-Control', value: 'public, max-age=31536000, immutable' },
      ],
    },
    {
      source: '/api/:path*',
      headers: [
        { key: 'Cache-Control', value: 'no-store, max-age=0' },
      ],
    },
    {
      source: '/favicon.ico',
      headers: [
        { key: 'Cache-Control', value: 'public, max-age=86400' },
      ],
    },
  ],
};
```

### 7.2 API Response Compression

```typescript
// middleware/compression.ts
import { NextResponse } from 'next/server';

export function middleware(request: NextRequest) {
  const response = NextResponse.next();
  // Vercel handles Brotli/gzip at the edge automatically
  // For self-hosted: add compression middleware
  if (process.env.NODE_ENV === 'production') {
    response.headers.set('X-Content-Type-Options', 'nosniff');
    response.headers.set('X-Frame-Options', 'DENY');
  }
  return response;
}
```

### 7.3 Font and Image Optimization

```typescript
// next.config.ts — add image optimization
images: {
  formats: ['image/avif', 'image/webp'],
  minimumCacheTTL: 60 * 60 * 24 * 30, // 30 days
},
```

---

## 8. Monitoring

### 8.1 Prometheus Metrics

```typescript
// lib/metrics.ts
import { Registry, Counter, Histogram, Gauge } from 'prom-client';

const register = new Registry();

// Request metrics
export const httpRequestDuration = new Histogram({
  name: 'cashflow_http_request_duration_seconds',
  help: 'Duration of HTTP requests',
  labelNames: ['method', 'route', 'status'],
  buckets: [0.01, 0.05, 0.1, 0.5, 1, 2, 5],
  registers: [register],
});

export const httpRequestTotal = new Counter({
  name: 'cashflow_http_requests_total',
  help: 'Total HTTP requests',
  labelNames: ['method', 'route', 'status'],
  registers: [register],
});

// Database metrics
export const dbQueryDuration = new Histogram({
  name: 'cashflow_db_query_duration_seconds',
  help: 'Duration of database queries',
  labelNames: ['operation', 'table'],
  buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1],
  registers: [register],
});

// Business metrics
export const webhookEventsProcessed = new Counter({
  name: 'cashflow_webhook_events_total',
  help: 'Total webhook events processed',
  labelNames: ['client_id', 'event_type'],
  registers: [register],
});

export const activeWebhookQueue = new Gauge({
  name: 'cashflow_webhook_queue_size',
  help: 'Current webhook processing queue size',
  registers: [register],
});

// Financial metrics
export const totalCostBRL = new Gauge({
  name: 'cashflow_total_cost_brl',
  help: 'Total AI cost in BRL by client',
  labelNames: ['client_id', 'period'],
  registers: [register],
});

export const cacheHitRate = new Gauge({
  name: 'cashflow_cache_hit_rate',
  help: 'Cache hit rate percentage',
  labelNames: ['client_id'],
  registers: [register],
});

// Cache metrics
export const cacheOperations = new Counter({
  name: 'cashflow_cache_operations_total',
  help: 'Cache hit/miss/invalidation counts',
  labelNames: ['operation', 'key_pattern'],
  registers: [register],
});

export { register };
```

### 8.2 Custom Financial Metrics

```typescript
// lib/metrics/financial.ts
export const marginBreaches = new Counter({
  name: 'cashflow_margin_breach_total',
  help: 'Number of times margin fell below minimum',
  labelNames: ['client_id', 'severity'],
  registers: [register],
});

export const budgetConsumption = new Gauge({
  name: 'cashflow_budget_consumption_pct',
  help: 'Budget consumption percentage',
  labelNames: ['client_id', 'budget_type'],
  registers: [register],
});

export const costPerToken = new Gauge({
  name: 'cashflow_cost_per_1k_tokens_brl',
  help: 'Cost per 1000 tokens in BRL',
  labelNames: ['model_name'],
  registers: [register],
});

export const projectedMonthlyCost = new Gauge({
  name: 'cashflow_projected_monthly_cost_brl',
  help: 'Projected monthly cost based on current run rate',
  labelNames: ['client_id'],
  registers: [register],
});
```

### 8.3 Alerting Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| HTTP p99 latency | > 500ms | > 2000ms | Scale up / investigate |
| DB query p95 | > 100ms | > 500ms | Add index / optimize query |
| Cache hit rate | < 80% | < 50% | Review TTL / key design |
| Webhook queue depth | > 100 | > 1000 | Add workers |
| Margin breach | Yellow (warning) | Red (hard cap) | Notify client / throttle |
| Disk usage (SQLite) | > 80% | > 95% | Archive old data |
| Redis memory | > 80% | > 95% | Increase limit / evict |
| Error rate | > 1% | > 5% | Page on-call |

### 8.4 Health Endpoint

```typescript
// app/api/health/route.ts
export async function GET() {
  const checks = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    version: process.env.APP_VERSION || '0.1.0',
    database: await checkDatabase(),
    redis: await checkRedis(),
    uptime: process.uptime(),
  };

  const healthy = checks.database === 'ok' && checks.redis === 'ok';
  return NextResponse.json(checks, { status: healthy ? 200 : 503 });
}
```

---

## 9. Load Testing

### 9.1 k6 Script — Financial API

```javascript
// tests/load/financial-api.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 10 },   // ramp up
    { duration: '5m', target: 50 },   // sustained load
    { duration: '1m', target: 100 },  // peak
    { duration: '2m', target: 50 },   // cool down
    { duration: '1m', target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<2000'],
    http_req_failed: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';

export default function () {
  // Scenario 1: Dashboard load (P&L + Cost Explorer)
  const pnlRes = http.get(`${BASE_URL}/api/pnl?clientId=tds&year=2026&month=7`);
  check(pnlRes, { 'pnl status 200': (r) => r.status === 200 });
  check(pnlRes, { 'pnl < 500ms': (r) => r.timings.duration < 500 });

  sleep(0.5);

  // Scenario 2: Webhook ingestion (high throughput)
  const webhookPayload = JSON.stringify({
    client_id: 'tds',
    event_type: 'api_call',
    model_name: 'gpt-4o',
    input_tokens: 1500,
    output_tokens: 500,
    cost_brl: 0.15,
  });

  const webhookRes = http.post(`${BASE_URL}/api/webhooks/tokens`, webhookPayload, {
    headers: { 'Content-Type': 'application/json' },
  });
  check(webhookRes, { 'webhook accepted': (r) => r.status === 201 });

  sleep(0.2);

  // Scenario 3: Report generation
  const reportRes = http.get(`${BASE_URL}/api/reports/commercial?clientId=tds&year=2026&month=7`);
  check(reportRes, { 'report status 200': (r) => r.status === 200 });

  sleep(1);
}
```

### 9.2 Locust Script — Bulk Operations

```python
# tests/load/bulk_import.py
from locust import HttpUser, task, between

class CashflowUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def load_dashboard(self):
        self.client.get("/api/pnl?clientId=tds&year=2026&month=7")

    @task(5)
    def ingest_webhook(self):
        self.client.post("/api/webhooks/tokens", json={
            "client_id": "tds",
            "event_type": "api_call",
            "model_name": "gpt-4o",
            "input_tokens": 1500,
            "output_tokens": 500,
            "cost_brl": 0.15,
        })

    @task(1)
    def generate_report(self):
        self.client.get("/api/reports/operational?clientId=tds&year=2026&month=7")

    @task(1)
    def forecast(self):
        self.client.get("/api/forecast?clientId=tds&year=2026&month=7")
```

### 9.3 Load Test Scenarios

| Scenario | VUs | Duration | Target p95 | Notes |
|----------|-----|----------|------------|-------|
| Normal traffic | 10-20 | 10min | < 200ms | Baseline |
| Peak hour | 50-100 | 5min | < 500ms | End-of-month reporting |
| Webhook burst | 200 | 2min | < 100ms | Simulated AI traffic spike |
| Report generation | 5 | 5min | < 2s | Heavy aggregation queries |
| Bulk import | 1 | 10min | N/A | 10k rows CSV import |
| Mixed workload | 50 | 15min | < 300ms | Realistic production mix |

---

## 10. Effort Estimate

| # | Area | Priority | Effort (days) | Dependencies | Risk |
|---|------|----------|---------------|--------------|------|
| 1 | Database indexing | P0 | 2 | None | Low — non-breaking, immediate benefit |
| 2 | N+1 query elimination | P0 | 3 | Repository interface changes | Medium — affects local + Supabase paths |
| 3 | Materialized views | P0 | 2 | Indexes from #1 | Low — additive |
| 4 | Caching layer (Redis) | P1 | 4 | Redis infra, invalidation logic | Medium — stale data risk |
| 5 | Connection pooling | P1 | 1 | PgBouncer setup | Low — config only |
| 6 | Background jobs (BullMQ) | P1 | 5 | Redis, worker infra | Medium — new failure mode |
| 7 | Query optimization (RPC) | P1 | 2 | None | Low — SQL-only changes |
| 8 | Monitoring (Prometheus) | P2 | 3 | Metrics infra | Low — additive |
| 9 | CDN / asset optimization | P2 | 1 | Vercel config | Low |
| 10 | Load testing | P2 | 3 | All above complete | Low — read-only |
| **Total** | | | **26** | | |

### Execution Order

```
Week 1: Indexes (#1) + N+1 fix (#2) + Materialized Views (#3)
Week 2: Redis caching (#4) + Connection pooling (#5) + RPC optimization (#7)
Week 3: Background jobs (#6) + Monitoring (#8)
Week 4: CDN (#9) + Load testing (#10) + Tuning
```

### Expected Impact

| Metric | Before | After (target) |
|--------|--------|-----------------|
| Dashboard load time | 2-5s | < 300ms |
| P&L query time | 1-3s | < 100ms (cached), < 200ms (uncached) |
| Webhook ingestion | 50-100ms | < 20ms (with queue) |
| Concurrent users | ~10 | 100+ |
| Report generation | 5-10s | < 1s (cached) |
| Cache hit rate | 0% | > 85% |
| DB connection wait | N/A | < 10ms (p95) |

---

## Appendix: Migration Checklist

```markdown
- [ ] Add composite indexes (CONCURRENTLY for zero-downtime)
- [ ] Add partial indexes for active records
- [ ] Add GIN indexes for JSONB columns
- [ ] Migrate metadata_json / details_json from TEXT to JSONB
- [ ] Create materialized views with UNIQUE indexes
- [ ] Deploy Redis instance (Upstash / Railway / self-hosted)
- [ ] Implement cache layer with invalidation
- [ ] Add PgBouncer or Supabase connection pooler config
- [ ] Refactor getLocalEnterpriseContext to use targeted queries
- [ ] Add getByClientAndPeriod to all repositories
- [ ] Optimize RPC functions to use date ranges instead of to_char
- [ ] Deploy BullMQ workers for SPED / import / refresh
- [ ] Add Prometheus metrics to API routes
- [ ] Create /health endpoint
- [ ] Write k6 load test scripts
- [ ] Run baseline load test before optimization
- [ ] Run load test after each optimization phase
- [ ] Document SLO targets and alerting rules
```
