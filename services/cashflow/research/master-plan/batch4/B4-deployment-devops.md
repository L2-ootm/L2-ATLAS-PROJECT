# B4: Deployment & DevOps Plan — L2 Cashflow

## 1. Vercel Deployment

### 1.1 Project Architecture

- **Framework**: Next.js 14+ (App Router)
- **Runtime**: Node.js 20 (Vercel default)
- **Build**: Output mode — static export where possible, server-rendered for dynamic pages

### 1.2 ISR (Incremental Static Regeneration)

| Page Type | ISR Strategy | Revalidation |
|-----------|-------------|--------------|
| Dashboard overview | ISR | 60s (near real-time) |
| Report pages | ISR | 300s (5 min) |
| Transaction lists | Dynamic (SSR) | — |
| Settings/config | Dynamic (SSR) | — |
| Public pages | Static | On-demand revalidation |

```ts
// app/dashboard/[tenantId]/page.tsx
export const revalidate = 60; // ISR — revalidate every 60 seconds
```

- **On-demand revalidation**: `revalidatePath()` / `revalidateTag()` after mutations
- **Edge caching**: Vercel CDN serves ISR pages globally with low latency

### 1.3 Serverless Functions

| Function | Route | Runtime | Max Duration |
|----------|-------|---------|-------------|
| Webhook receiver | `/api/webhooks/*` | Node.js | 30s |
| Report generation | `/api/reports/*` | Node.js | 60s |
| Import/export | `/api/import/*` | Node.js | 120s (Pro plan) |
| Cron jobs | Vercel Cron | Node.js | 60s |

### 1.4 Environment Management

Three Vercel environments with branch-based promotion:

| Environment | Branch | Supabase Project | Purpose |
|------------|--------|-----------------|---------|
| **Development** | `develop` | `cashflow-dev` | Active development |
| **Preview** | PR branches | `cashflow-dev` | PR preview deployments |
| **Production** | `main` | `cashflow-prod` | Live system |

**Environment variables** managed in Vercel dashboard, per-environment:

```
DATABASE_URL          # Supabase connection string (pooled)
DIRECT_URL            # Supabase direct connection (for migrations)
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
SENTRY_DSN
UNLEASH_URL
UNLEASH_SERVER_KEY
REDIS_URL             # Optional — for caching layer
```

---

## 2. Database Migrations

### 2.1 Prisma Migrate Deploy

**Primary command**: `npx prisma migrate deploy`

- Applies all pending migrations in order
- No interactive prompts — suitable for CI/CD
- Exits non-zero on failure — CI pipeline catches issues

### 2.2 Advisory Locks

Prisma's `migrate deploy` uses PostgreSQL advisory locks internally:

```sql
-- Prisma acquires this lock before running migrations
SELECT pg_advisory_lock(12345);
-- Runs migrations in order
-- Releases lock on completion
```

For custom migration scripts, explicitly acquire locks:

```sql
BEGIN;
SELECT pg_advisory_lock(12345);

-- Migration DDL here
ALTER TABLE "CashflowEntry" ADD COLUMN "category" TEXT;

SELECT pg_advisory_unlock(12345);
COMMIT;
```

### 2.3 Zero-Downtime Migration Strategy

| Migration Type | Strategy | Example |
|---------------|----------|---------|
| Add column | Add with default, backfill async, add NOT NULL constraint | Add `category` column |
| Rename column | Add new → copy data → update code → drop old | Rename `amount` → `value` |
| Add index | `CREATE INDEX CONCURRENTLY` | Add index on `tenant_id` |
| Drop column | Deploy code first, then drop column in next deploy | Remove `deprecated_field` |
| Add constraint | Add as `NOT VALID`, then `VALIDATE CONSTRAINT` | Add FK constraint |

**Backfill pattern for large tables**:

```sql
-- 1. Add column (instant)
ALTER TABLE "CashflowEntry" ADD COLUMN "category" TEXT DEFAULT 'uncategorized';

-- 2. Backfill in batches (async, outside migration)
-- Done via background job, not in migrate deploy
-- Batch size: 1000 rows, sleep 100ms between batches

-- 3. After backfill complete, add NOT NULL
ALTER TABLE "CashflowEntry" ALTER COLUMN "category" SET NOT NULL;
```

### 2.4 Migration CI/CD

```yaml
# .github/workflows/migrate.yml
- name: Run migrations
  run: npx prisma migrate deploy
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

- Migrations run on every deploy (before app starts)
- If migration fails, deploy is aborted
- **No rollback** — forward-only migrations with compensating migrations

---

## 3. Supabase Management

### 3.1 Project Setup

| Setting | Dev | Production |
|---------|-----|-----------|
| Plan | Free | Pro ($25/mo) |
| DB size | 500 MB limit | 8 GB included |
| Connections | 60 | 200 |
| Edge Functions | 500K/mo | 2M/mo |
| Auth users | Unlimited | Unlimited |
| Storage | 1 GB | 100 GB |

**Provisioning**: Create via Supabase Dashboard or CLI:

```bash
# Supabase CLI for local dev
supabase init
supabase start  # Local Supabase stack via Docker
supabase db push  # Push local schema to cloud
```

### 3.2 Row-Level Security (RLS) Policies

All tables have RLS enabled. Core policy pattern:

```sql
-- Enable RLS on every table
ALTER TABLE "CashflowEntry" ENABLE ROW LEVEL SECURITY;

-- Tenant isolation: users only see their own tenant's data
CREATE POLICY "tenant_isolation" ON "CashflowEntry"
  FOR ALL
  USING ("tenant_id" = (SELECT current_setting('app.current_tenant')::uuid));

-- Admin bypass (service role)
CREATE POLICY "admin_bypass" ON "CashflowEntry"
  FOR ALL
  TO service_role
  USING (true);
```

**Multi-tenant isolation** enforced at DB level via `app.current_tenant` session variable, set by middleware:

```ts
// lib/supabase/middleware.ts
await supabase.rpc('set_tenant_context', { p_tenant_id: tenantId });
```

### 3.3 Edge Functions

| Function | Trigger | Purpose |
|----------|---------|---------|
| `webhook-handler` | HTTP | Process bank webhooks |
| `scheduled-cleanup` | Cron | Archive old data |
| `notify-alerts` | Database webhook | Send alerts on thresholds |

### 3.4 Storage

| Bucket | Access | Purpose |
|--------|--------|---------|
| `imports` | Authenticated | CSV/Excel upload staging |
| `exports` | Authenticated | Generated reports |
| `avatars` | Public read | Tenant/user avatars |

RLS policies on storage:

```sql
-- Users can only access their tenant's folder
CREATE POLICY "tenant_folder_access" ON storage.objects
  FOR ALL
  USING (bucket_id = 'imports' AND (storage.foldername(name))[1] = current_setting('app.current_tenant'));
```

---

## 4. Feature Flags

### 4.1 Unleash OSS Setup

**Self-hosted Unleash** via Docker Compose (or deploy to Railway/Fly.io):

```yaml
# docker-compose.yml (Unleash)
services:
  unleash:
    image: unleashorg/unleash-server:latest
    ports:
      - "4242:4242"
    environment:
      DATABASE_URL: postgresql://unleash:password@db:5432/unleash
      INIT_ADMIN_API_TOKENS: '[]'
    depends_on:
      - db
```

**Integration with Next.js**:

```ts
// lib/feature-flags.ts
import { initialize } from 'unleash-client';

const unleash = initialize({
  url: process.env.UNLEASH_URL!,
  appName: 'cashflow',
  customHeaders: { Authorization: process.env.UNLEASH_SERVER_KEY! },
});

export function isEnabled(flag: string, context: { tenantId: string }): boolean {
  return unleash.isEnabled(flag, { userId: context.tenantId });
}
```

### 4.2 Per-Tenant Module Toggling

```json
// Unleash feature flag definition
{
  "name": "module.inventory",
  "enabled": true,
  "strategies": [
    {
      "name": "gradualRollout",
      "parameters": {
        "percentage": 25,
        "groupId": "module.inventory"
      }
    },
    {
      "name": "userWithId",
      "parameters": {
        "userIds": "tenant-uuid-1,tenant-uuid-2"
      }
    }
  ]
}
```

**Flag naming convention**: `module.<name>`, `experiment.<name>`, `release.<name>`

### 4.3 Gradual Rollout Strategy

| Phase | % Rollout | Duration | Gate |
|-------|----------|----------|------|
| Internal testing | 0% (explicit tenants) | 1 week | No critical bugs |
| Beta | 10% | 2 weeks | Error rate < 0.1% |
| Gradual | 25% → 50% → 75% | 1 week each | Metrics within bounds |
| GA | 100% | — | All criteria met |

---

## 5. CI/CD Pipeline

### 5.1 GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  lint-and-type:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck

  test:
    runs-on: ubuntu-latest
    needs: lint-and-type
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: cashflow_test
        ports: ['5432:5432']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci
      - run: npx prisma migrate deploy
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/cashflow_test
      - run: npm test
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/cashflow_test

  deploy-staging:
    if: github.ref == 'refs/heads/develop'
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}

  deploy-production:
    if: github.ref == 'refs/heads/main'
    needs: test
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: '--prod'

  migrate-production:
    if: github.ref == 'refs/heads/main'
    needs: deploy-production
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx prisma migrate deploy
        env:
          DATABASE_URL: ${{ secrets.PROD_DATABASE_URL }}
```

### 5.2 Test Gates

| Gate | Tool | Threshold |
|------|------|-----------|
| Linting | ESLint + Prettier | 0 errors, 0 warnings |
| Type checking | TypeScript | 0 errors |
| Unit tests | Vitest | 80% coverage |
| Integration tests | Vitest + test DB | All passing |
| E2E tests | Playwright | Critical path passing |
| Security audit | `npm audit` | 0 high/critical |
| Bundle size | `@next/bundle-analyzer` | < 250 KB first load |

### 5.3 Deployment Automation

- **Auto-deploy staging** on push to `develop`
- **Auto-deploy production** on push to `main` (after all gates pass)
- **Manual promotion** for production: GitHub Environment approval required
- **Rollback**: Vercel instant rollback via dashboard or CLI (`vercel rollback`)

---

## 6. Environment Management

### 6.1 Dev/Staging/Production Parity

| Aspect | Dev | Staging | Production |
|--------|-----|---------|-----------|
| Database | Supabase Free | Supabase Free | Supabase Pro |
| Data | Seed + synthetic | Mirror of prod (anonymized) | Real data |
| Feature flags | All enabled | Gradual rollout | Controlled rollout |
| Monitoring | Console only | Sentry dev | Sentry prod + Analytics |
| Rate limiting | Disabled | Enabled | Enabled |
| Email | Log only | Mailtrap | Resend/SendGrid |

### 6.2 Seed Data

```bash
# Local development seed
npx prisma db seed

# Staging seed (anonymized production snapshot)
# Run weekly via GitHub Actions cron
npx tsx scripts/seed-staging.ts
```

Seed script generates:
- 3 demo tenants
- 50 users across tenants
- 10,000 cashflow entries per tenant (last 12 months)
- Sample categories, budgets, reports

### 6.3 Environment Variables

Managed via:
- **Vercel**: Per-environment variables in dashboard
- **Local**: `.env.local` (gitignored), `.env.example` (committed)
- **Secrets rotation**: Quarterly rotation schedule, tracked in ops calendar

---

## 7. Monitoring & Observability

### 7.1 Vercel Analytics

- **Web Vitals**: LCP, FID, CLS tracked automatically
- **Custom metrics**: Dashboard load time, API response time
- **Speed Insights**: Per-page performance data

### 7.2 Sentry Error Tracking

```ts
// instrumentation.ts
import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.VERCEL_ENV,
  tracesSampleRate: 0.1, // 10% in production
  replaysSessionSampleRate: 0.01,
  replaysOnErrorSampleRate: 1.0,
});
```

**Alert routing**:
- Critical errors → Slack #cashflow-alerts
- Warning errors → Sentry dashboard only
- Performance degradation → PagerDuty (if on-call)

### 7.3 Custom Metrics

```ts
// lib/metrics.ts
import { Stats } from 'node:statsd'; // or Datadog agent

export const metrics = {
  reportGeneration: (duration: number) =>
    stats.histogram('cashflow.report.generation_ms', duration),
  importRows: (count: number) =>
    stats.increment('cashflow.import.rows', count),
  apiLatency: (route: string, duration: number) =>
    stats.histogram('cashflow.api.latency_ms', duration, [`route:${route}`]),
};
```

### 7.4 Uptime Monitoring

- **BetterUptime** or **Checkly** for synthetic monitoring
- Monitor: `/api/health`, `/api/health/db`, `/api/health/redis`
- Alert on: > 5s response time, 2+ consecutive failures

---

## 8. Backup & Disaster Recovery

### 8.1 Supabase Backups

| Plan | Backup Type | Retention | Recovery |
|------|------------|-----------|----------|
| Free | Daily | 7 days | Dashboard restore |
| Pro | Daily + PITR | 7 days (daily), 7 days (PITR) | Point-in-time restore |

**PITR (Point-in-Time Recovery)**:
- Available on Pro plan
- Recovery window: configurable (7–30 days)
- Recovery point: any second within window
- RPO: 0 (with continuous WAL archiving)

### 8.2 RPO/RTO Targets

| Scenario | RPO | RTO | Strategy |
|----------|-----|-----|----------|
| Accidental data deletion | 0 (PITR) | < 15 min | PITR restore |
| Database corruption | 0 (PITR) | < 30 min | PITR + app restart |
| Full DB failure | < 24h (daily backup) | < 2h | Restore from backup |
| Region outage | < 1h (replication) | < 1h | Supabase failover |
| Complete data loss | < 24h | < 4h | Cross-region restore |

### 8.3 Backup Schedule

```
Daily backup:        02:00 UTC (Supabase automatic)
WAL archiving:       Continuous (PITR)
Schema backup:       Every deploy (Prisma migrate history)
Seed data:           Version controlled in repo
```

### 8.4 Disaster Recovery Runbook

1. **Assess**: Determine scope of data loss/corruption
2. **Communicate**: Notify stakeholders via Slack
3. **Restore**: Use PITR to restore to last known good state
4. **Verify**: Run data integrity checks
5. **Resume**: Restart application services
6. **Post-mortem**: Document root cause, add preventive measures

---

## 9. Cost Estimation

### 9.1 Monthly Cost Projection (100 tenants, 1000 users)

| Service | Plan | Monthly Cost | Notes |
|---------|------|-------------|-------|
| **Vercel** | Pro | $20 | 1 team member, 100 GB bandwidth |
| **Vercel** | Additional bandwidth | $0–20 | Overage at $40/100 GB |
| **Supabase** | Pro | $25 | 8 GB DB, 100 GB storage |
| **Supabase** | Additional storage | $0–10 | Overage at $0.125/GB |
| **Redis** (Upstash) | Pay-per-use | $0–10 | 10K commands/day |
| **Sentry** | Team | $26 | 50K events/month |
| **Unleash OSS** | Self-hosted | $0–15 | Railway/Fly.io hosting |
| **GitHub Actions** | Free tier | $0 | 2000 min/month |
| **BetterUptime** | Starter | $20 | 5 monitors |
| **Domain + DNS** | Cloudflare | $0–5 | Free tier sufficient |
| **Email (Resend)** | Pro | $20 | 50K emails/month |
| **TOTAL** | | **$126–161/mo** | |

### 9.2 Cost at Scale (1000 tenants, 10K users)

| Service | Monthly Cost |
|---------|-------------|
| Vercel Pro | $20 + $40 bandwidth |
| Supabase Pro | $25 + $30 usage |
| Redis | $10–20 |
| Sentry Team | $80 |
| Monitoring | $20 |
| Email | $40 |
| **TOTAL** | **$225–285/mo** |

---

## 10. Scaling Strategy

### 10.1 Upgrade Triggers

| Metric | Threshold | Action |
|--------|-----------|--------|
| DB connections | > 80% of plan limit | Upgrade Supabase plan |
| DB storage | > 70% of plan limit | Upgrade plan or archive old data |
| Edge Function invocations | > 80% of plan limit | Upgrade plan or optimize |
| Vercel bandwidth | > 80 GB/month | Upgrade to Vercel Pro (already) |
| API p99 latency | > 500ms | Add Redis cache layer |
| Error rate | > 0.1% | Investigate + add monitoring |
| Active tenants | > 500 | Consider dedicated DB |

### 10.2 When to Add Redis

**Add Redis when**:
- Dashboard load time > 2s consistently
- Same queries hit DB > 100 times/minute
- Rate limiting needed for API endpoints
- Session store needed for > 1000 concurrent users

**Redis use cases for Cashflow**:
```ts
// Cache expensive aggregation queries
const cacheKey = `dashboard:${tenantId}:${period}`;
const cached = await redis.get(cacheKey);
if (cached) return JSON.parse(cached);

const data = await db.cashflowEntry.aggregate({ ... });
await redis.set(cacheKey, JSON.stringify(data), 'EX', 300); // 5 min TTL
```

### 10.3 When to Consider Dedicated DB

**Migrate from Supabase to dedicated PostgreSQL when**:
- > 1000 tenants with high write throughput
- Need custom PostgreSQL extensions (e.g., TimescaleDB for time-series)
- Compliance requires dedicated infrastructure
- Connection pooling becomes bottleneck (> 200 connections)

**Migration path**: Supabase → AWS RDS / Neon / PlanetScale

### 10.4 Horizontal Scaling

- **Vercel**: Automatic (serverless, scales to zero and to thousands)
- **Supabase**: Vertical scaling (plan upgrades), read replicas for reporting
- **Edge Functions**: Automatic scaling within plan limits

---

## 11. Runbook

### 11.1 Common Issues

#### Application won't deploy

```bash
# Check Vercel build logs
vercel logs <deployment-url>

# Common fixes:
# 1. TypeScript errors — run `npx tsc --noEmit` locally
# 2. Missing env vars — check Vercel dashboard
# 3. Prisma generate failed — check prisma schema
```

#### Database connection errors

```bash
# Check connection pool status
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"

# If near limit, check for connection leaks
# Common cause: missing connection cleanup in API routes
```

#### Migration failed

```bash
# Check migration status
npx prisma migrate status

# If stuck in partial state:
# 1. Check pg_stat_activity for locks
psql $DATABASE_URL -c "SELECT * FROM pg_locks WHERE NOT granted;"

# 2. If advisory lock held, wait or kill the process
psql $DATABASE_URL -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE query LIKE '%prisma%';"

# 3. Manually fix the schema if needed, then:
npx prisma migrate resolve --rolled-back <migration_name>
# or
npx prisma migrate resolve --applied <migration_name>
```

#### High error rate

```bash
# Check Sentry for new error clusters
# Check Vercel function logs for 5xx errors
vercel logs --follow

# If database-related:
# 1. Check Supabase dashboard for connection count
# 2. Check for slow queries in Supabase SQL Editor
# 3. Scale up if needed
```

#### Slow dashboard loads

```bash
# Check Vercel Analytics for performance degradation
# Check if ISR cache is being invalidated too frequently
# Check Redis cache hit rate (if implemented)

# Quick wins:
# 1. Add pagination to large data queries
# 2. Implement virtual scrolling for transaction lists
# 3. Add Redis caching for aggregation queries
```

### 11.2 Rollback Procedure

```bash
# Instant Vercel rollback
vercel rollback

# Or via GitHub Actions
gh run list --workflow=ci.yml  # Find last successful deploy
gh run rerun <run-id>

# Database rollback (if needed)
# 1. Revert code deployment first
# 2. Then run compensating migration
npx prisma migrate deploy  # Apply compensating migration
```

### 11.3 Emergency Contacts

| Role | Contact | When to Escalate |
|------|---------|-----------------|
| Platform lead | Davi | Architecture decisions, cost overruns |
| Supabase support | Dashboard ticket | DB issues, performance degradation |
| Vercel support | Dashboard ticket | Deploy failures, edge function issues |

---

## 12. Effort Estimate

| Component | Setup (hours) | Maintenance (hours/month) | Complexity |
|-----------|--------------|--------------------------|------------|
| Vercel project setup | 2 | 1 | Low |
| Prisma migrations strategy | 4 | 2 | Medium |
| Supabase project setup | 4 | 2 | Medium |
| RLS policies | 8 | 2 | High |
| Edge Functions | 6 | 2 | Medium |
| Feature flags (Unleash) | 8 | 1 | Medium |
| CI/CD pipeline | 8 | 2 | Medium |
| Environment management | 4 | 2 | Low |
| Sentry integration | 2 | 1 | Low |
| Custom monitoring | 4 | 2 | Medium |
| Uptime monitoring | 2 | 1 | Low |
| Backup verification | 2 | 1 | Low |
| Documentation/runbook | 6 | 1 | Low |
| **TOTAL** | **60 hours** | **20 hours/month** | — |

**Timeline**: ~2 weeks of focused work for initial setup, then ongoing maintenance.

---

## Appendix A: Deployment Checklist

### Pre-deploy

- [ ] All tests passing locally
- [ ] TypeScript compiles without errors
- [ ] ESLint passes
- [ ] Prisma schema generates cleanly
- [ ] Environment variables documented
- [ ] Migration tested on dev database

### Deploy

- [ ] Merge to `develop` (staging deploy)
- [ ] Verify staging deployment
- [ ] Run smoke tests on staging
- [ ] Merge to `main` (production deploy)
- [ ] Verify production deployment
- [ ] Run production smoke tests

### Post-deploy

- [ ] Monitor error rates for 1 hour
- [ ] Check Sentry for new errors
- [ ] Verify database connections stable
- [ ] Check Vercel Analytics for performance
- [ ] Update deployment log

---

## Appendix B: Infrastructure Diagram

```
                    ┌─────────────────────────────────────┐
                    │           GitHub Actions            │
                    │   CI/CD · Tests · Deploy            │
                    └──────────┬──────────┬───────────────┘
                               │          │
                    ┌──────────▼──┐  ┌────▼──────────┐
                    │   Vercel    │  │   Supabase    │
                    │  (Next.js)  │  │  (PostgreSQL) │
                    │             │  │  + Auth        │
                    │  ISR/SSR    │  │  + Storage     │
                    │  Edge Fn    │  │  + RLS         │
                    └──────┬──────┘  └───────┬───────┘
                           │                 │
              ┌────────────┼─────────────────┤
              │            │                 │
    ┌─────────▼──┐  ┌─────▼────┐  ┌────────▼────────┐
    │  Unleash   │  │  Redis   │  │    Sentry       │
    │ (Feature   │  │ (Cache)  │  │  (Error Track)  │
    │  Flags)    │  │          │  │                 │
    └────────────┘  └──────────┘  └─────────────────┘
```

---

*Generated for L2 Cashflow — Production Deployment Infrastructure*
*Date: 2026-07-10*
*Status: Production-ready design*
