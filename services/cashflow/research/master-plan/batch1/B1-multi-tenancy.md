# B1: Multi-Tenancy Architecture — L2 Cashflow

> Design document for converting L2 Cashflow from single-tenant to multi-tenant SaaS.
> Current state: SQLite (dev) / Supabase PostgreSQL (prod), repository pattern with interface abstraction.

---

## Current State Summary

- **ORM/Client**: Supabase JS client via singleton `getSupabaseClient()`
- **Repository pattern**: `IClientRepository`, `IExpenseRepository`, etc. with SQLite and Supabase implementations
- **Tables**: `client`, `expense`, `invoice`, `partner_wallet`, `partner_transaction`, `client_accounts`, `contracts`, `plans`, `usage_events`, `model_rate_cards`, `search_rate_cards`, `research_jobs`, `invoice_line_items`, `plus_subscriptions`, `billing_events`
- **No auth middleware**: No tenant context propagation mechanism exists
- **No tenant_id**: All tables are global; `client_accounts` is the L2 client (not a tenant)
- **RPC functions**: 6 server-side aggregation functions (`get_cost_explorer_metrics`, `get_client_pnl`, etc.)

---

## 1. Tenant Model Decision

### Recommendation: Shared Database + Shared Schema + PostgreSQL RLS

| Criterion | Shared Schema (RLS) | Schema-per-Tenant | Database-per-Tenant |
|---|---|---|---|
| Ops cost at 1000 tenants | Single DB, single migration | 1000 schema migrations | 1000 database provisions |
| Supabase fit | Native RLS support | Custom tooling needed | Not practical on Supabase |
| Query complexity | `SET app.current_tenant` + RLS auto-filters | Cross-tenant queries need `search_path` | Full connection switching |
| Migration overhead | 1 migration run | 1 migration x 1000 schemas | 1 migration x 1000 databases |
| Backup/restore | Single pg_dump | Per-schema export | Per-database export |
| Isolation guarantee | RLS enforced at DB level | Schema-level | Database-level |
| Cost per tenant | Shared compute + storage | Shared compute, isolated storage | Dedicated compute |

**Why shared schema wins for L2 Cashflow:**
- Supabase provides native RLS — no custom enforcement layer needed
- Current schema is ~15 tables — manageable in a single namespace with `tenant_id` prefixing
- The existing `client_accounts` table already models L2's business clients; this IS the tenant entity
- Migration path is straightforward: add `tenant_id` column, backfill, enable RLS
- For <10,000 tenants, shared schema performs well with proper indexing

### Schema Extension

```sql
-- Core tenant table (promote from client_accounts)
CREATE TABLE tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,           -- subdomain: "escola-abc"
  name TEXT NOT NULL,
  legal_name TEXT,
  cnpj TEXT,
  plan TEXT DEFAULT 'free',            -- free | pro | enterprise
  status TEXT DEFAULT 'active',        -- active | suspended | deleted
  settings JSONB DEFAULT '{}',         -- tenant-specific config
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Plan feature definitions
CREATE TABLE plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,           -- free | pro | enterprise
  features JSONB NOT NULL DEFAULT '{}',
  limits JSONB NOT NULL DEFAULT '{}',
  price_brl NUMERIC DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Seed default plans
INSERT INTO plans (name, features, limits, price_brl) VALUES
  ('free', '{"modules": ["clients", "invoices", "expenses"]}', '{"max_users": 5, "max_events_per_month": 1000}', 0),
  ('pro', '{"modules": ["clients", "invoices", "expenses", "contracts", "usage", "forecast"]}', '{"max_users": 50, "max_events_per_month": 50000}', 299),
  ('enterprise', '{"modules": ["*"]}', '{"max_users": -1, "max_events_per_month": -1}', 999);
```

---

## 2. Tenant Identification

### Three-layer identification strategy:

#### Layer 1: JWT Claim (Primary — API calls)
```typescript
// Supabase Auth JWT custom claims
interface TenantJWT {
  sub: string;           // user UUID
  tenant_id: string;     // tenant UUID
  tenant_slug: string;   // for subdomain routing
  role: string;          // admin | user | viewer
  plan: string;          // free | pro | enterprise
}
```

**How it works:**
- Supabase Auth supports custom JWT claims via `auth.jwt()` function
- Set `tenant_id` claim in the JWT when user signs in
- RLS policies use `auth.jwt() ->> 'tenant_id'` to enforce isolation
- Application reads `tenant_id` from the verified JWT — never trusts client input

#### Layer 2: Subdomain (UI routing)
```
https://escola-abc.cashflow.l2.com.br  → tenant_slug = "escola-abc"
```

**How it works:**
- Next.js middleware reads `x-forwarded-host` or `host` header
- Extracts subdomain, validates against `tenants.slug`
- Redirects to auth if no session; sets tenant context in session

#### Layer 3: API Key / Header (External integrations)
```
X-Tenant-ID: <uuid>
Authorization: Bearer <api_key>
```

**When to use:**
- Webhook receivers (e.g., payment gateway callbacks)
- MCP server connections
- External API consumers (partner integrations)

### Implementation

```typescript
// lib/tenant/context.ts
export interface TenantContext {
  tenantId: string;
  tenantSlug: string;
  userId: string;
  role: 'admin' | 'user' | 'viewer';
  plan: string;
}

// Middleware extracts tenant from JWT
export function extractTenantFromJWT(payload: any): TenantContext {
  return {
    tenantId: payload.tenant_id,
    tenantSlug: payload.tenant_slug,
    userId: payload.sub,
    role: payload.role || 'user',
    plan: payload.plan || 'free',
  };
}
```

---

## 3. Data Isolation

### 3.1 PostgreSQL RLS Policies

Every tenant-scoped table gets an RLS policy. The pattern:

```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE client ENABLE ROW LEVEL SECURITY;
ALTER TABLE expense ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice ENABLE ROW LEVEL SECURITY;
-- ... all other tables

-- Policy: tenants can only see their own rows
CREATE POLICY tenant_isolation ON client
  FOR ALL
  USING (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid)
  WITH CHECK (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid);

-- Policy: admin/service_role bypasses RLS
CREATE POLICY admin_bypass ON client
  FOR ALL
  USING (auth.role() = 'service_role');
```

### 3.2 Application-Level Filtering (Defense in Depth)

RLS is the primary enforcement. Application layer adds safety:

```typescript
// lib/repositories/supabase/base.ts
abstract class TenantScopedRepository {
  protected tenantId: string;

  constructor(tenantId: string) {
    this.tenantId = tenantId;
  }

  // Every query automatically includes tenant_id
  protected scopeQuery(query: any) {
    return query.eq('tenant_id', this.tenantId);
  }
}

// Usage in repository
export class SupabaseClientRepository extends TenantScopedRepository {
  async getAll(): Promise<Client[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await this.scopeQuery(
      supabase.from('client').select('*')
    ).order('created_at', { ascending: false });
    if (error) throw error;
    return data || [];
  }
}
```

### 3.3 Connection Pooling Implications

- **Supabase pooler**: Uses PgBouncer — `SET app.current_tenant` is per-connection and resets on checkout
- **Solution**: Use Supabase's `postgrest.rpc()` for tenant-scoped operations, or pass `tenant_id` as a parameter
- **Avoid**: Connection-level state (`SET app.current_tenant`) with pooled connections — it leaks across requests
- **Better**: Embed `tenant_id` in every RPC call as a parameter, enforced by RLS via JWT

### 3.4 Cross-Tenant Query Isolation

```sql
-- Service role queries bypass RLS (for admin/consolidated views)
-- Must be explicitly used — never from client-facing code
SET role = 'service_role';
SELECT * FROM usage_events WHERE tenant_id = $1;
RESET role;
```

---

## 4. Tenant Lifecycle

### 4.1 Creation

```typescript
// lib/tenant/provisioning.ts
export async function provisionTenant(input: {
  slug: string;
  name: string;
  legalName?: string;
  cnpj?: string;
  plan?: string;
}) {
  const supabase = getSupabaseClient();

  // 1. Create tenant record
  const { data: tenant, error: tenantErr } = await supabase
    .from('tenants')
    .insert({
      slug: input.slug,
      name: input.name,
      legal_name: input.legalName,
      cnpj: input.cnpj,
      plan: input.plan || 'free',
      status: 'active',
    })
    .select()
    .single();
  if (tenantErr) throw tenantErr;

  // 2. Create default admin user
  // (handled by Supabase Auth — invite flow)

  // 3. Seed default data (optional templates)
  // ... contract templates, default settings, etc.

  return tenant;
}
```

### 4.2 Suspension

```sql
-- Soft suspend: mark tenant, RLS continues to work
UPDATE tenants SET status = 'suspended' WHERE id = $1;

-- Hard block: custom middleware rejects all requests
-- In middleware: if tenant.status !== 'active', return 403
```

**Suspended tenant behavior:**
- All API requests return 403 with `TENANT_SUSPENDED` error
- Data is preserved but inaccessible
- Admin can reactivate without data loss

### 4.3 Deletion (Soft Delete + Data Retention)

```sql
-- Soft delete: preserve data for compliance, mark for eventual purge
UPDATE tenants SET
  status = 'deleted',
  settings = jsonb_set(settings, '{deleted_at}', to_jsonb(now()))
WHERE id = $1;

-- Scheduled job: after retention period (e.g., 90 days), hard delete
-- 1. Export data to cold storage (S3/GCS)
-- 2. Delete all tenant rows
-- 3. Delete tenant record
```

### 4.4 Data Export

```typescript
// Export all tenant data as JSON (GDPR/LGPD compliance)
export async function exportTenantData(tenantId: string): Promise<TenantExport> {
  const supabase = getSupabaseClient();

  const [clients, expenses, invoices, usage, contracts] = await Promise.all([
    supabase.from('client').select('*').eq('tenant_id', tenantId),
    supabase.from('expense').select('*').eq('tenant_id', tenantId),
    supabase.from('invoice').select('*').eq('tenant_id', tenantId),
    supabase.from('usage_events').select('*').eq('tenant_id', tenantId),
    supabase.from('contracts').select('*').eq('tenant_id', tenantId),
  ]);

  return {
    exportedAt: new Date().toISOString(),
    tenantId,
    data: {
      clients: clients.data,
      expenses: expenses.data,
      invoices: invoices.data,
      usageEvents: usage.data,
      contracts: contracts.data,
    },
  };
}
```

---

## 5. Plan-Based Feature Gating

### 5.1 Plan Definition

```sql
CREATE TABLE plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,
  features JSONB NOT NULL DEFAULT '{}',
  limits JSONB NOT NULL DEFAULT '{}',
  price_brl NUMERIC DEFAULT 0,
  billing_cycle TEXT DEFAULT 'monthly',
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### 5.2 Feature Gating Middleware

```typescript
// lib/tenant/feature-gate.ts
export const PLAN_FEATURES = {
  free: ['clients', 'invoices', 'expenses'],
  pro: ['clients', 'invoices', 'expenses', 'contracts', 'usage', 'forecast', 'reports'],
  enterprise: ['*'], // all modules
} as const;

export const PLAN_LIMITS = {
  free: { max_users: 5, max_events_per_month: 1000, max_clients: 10 },
  pro: { max_users: 50, max_events_per_month: 50000, max_clients: 100 },
  enterprise: { max_users: -1, max_events_per_month: -1, max_clients: -1 },
} as const;

export function hasFeature(plan: string, module: string): boolean {
  const features = PLAN_FEATURES[plan as keyof typeof PLAN_FEATURES];
  if (!features) return false;
  return features.includes('*') || features.includes(module);
}

export function isOverLimit(plan: string, metric: string, current: number): boolean {
  const limits = PLAN_LIMITS[plan as keyof typeof PLAN_LIMITS];
  if (!limits) return true;
  const limit = limits[metric as keyof typeof limits];
  if (limit === -1) return false; // unlimited
  return current >= limit;
}
```

### 5.3 Usage Enforcement

```typescript
// Middleware checks plan limits before allowing operations
export async function enforcePlanLimits(tenantId: string, module: string) {
  const tenant = await getTenant(tenantId);

  // Feature check
  if (!hasFeature(tenant.plan, module)) {
    throw new PlanFeatureError(`Module '${module}' requires ${requiredPlan(module)} plan`);
  }

  // Usage limit check (for high-frequency operations)
  if (module === 'usage_events') {
    const currentMonth = getCurrentMonth();
    const eventCount = await countEventsThisMonth(tenantId, currentMonth);
    if (isOverLimit(tenant.plan, 'max_events_per_month', eventCount)) {
      throw new PlanLimitError('Monthly event limit reached');
    }
  }
}
```

---

## 6. Cross-Tenant Operations

### 6.1 Holding Company / Consolidated Views

For L2 as the operator — viewing all tenants:

```typescript
// lib/tenant/admin.ts
// Uses service_role to bypass RLS
export async function getConsolidatedReport(monthPrefix: string) {
  const supabase = getSupabaseServiceClient(); // service_role key

  const { data, error } = await supabase.rpc('get_consolidated_report', {
    p_month_prefix: monthPrefix,
  });
  if (error) throw error;
  return data;
}
```

```sql
-- Consolidated RPC: runs with service_role, bypasses RLS
CREATE OR REPLACE FUNCTION get_consolidated_report(p_month_prefix TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER  -- runs as owner, bypasses RLS
AS $$
DECLARE
  v_summary JSONB;
  v_by_tenant JSONB;
BEGIN
  -- Total across all tenants
  SELECT row_to_json(t)::jsonb INTO v_summary
  FROM (
    SELECT
      COUNT(DISTINCT tenant_id) as active_tenants,
      SUM(cost_brl) as total_ai_cost,
      COUNT(DISTINCT user_id) as total_active_users,
      SUM(input_tokens + output_tokens) as total_tokens
    FROM usage_events
    WHERE to_char(created_at, 'YYYY-MM') = p_month_prefix
  ) t;

  -- Per-tenant breakdown
  SELECT COALESCE(jsonb_agg(row_to_json(t)), '[]'::jsonb) INTO v_by_tenant
  FROM (
    SELECT
      tenant_id,
      SUM(cost_brl) as cost,
      COUNT(DISTINCT user_id) as users,
      SUM(input_tokens + output_tokens) as tokens
    FROM usage_events
    WHERE to_char(created_at, 'YYYY-MM') = p_month_prefix
    GROUP BY tenant_id
    ORDER BY cost DESC
  ) t;

  RETURN jsonb_build_object('summary', v_summary, 'byTenant', v_by_tenant);
END;
$$;
```

### 6.2 Tenant Switching (Admin)

```typescript
// Admin can impersonate a tenant for support
export async function impersonateTenant(adminUserId: string, targetTenantId: string) {
  // 1. Verify admin role
  const admin = await getUser(adminUserId);
  if (admin.role !== 'super_admin') throw new Error('Unauthorized');

  // 2. Create temporary session with target tenant context
  const impersonationToken = createImpersonationToken({
    original_user: adminUserId,
    tenant_id: targetTenantId,
    expires_in: '1h',
  });

  return impersonationToken;
}
```

---

## 7. Schema Migration Strategy

### 7.1 Zero-Downtime Migration Pattern

**Phase 1: Add nullable `tenant_id` column (backward-compatible)**
```sql
ALTER TABLE client ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE expense ADD COLUMN tenant_id UUID REFERENCES tenants(id);
-- ... all tables

-- Backfill existing data to first/default tenant
UPDATE client SET tenant_id = (SELECT id FROM tenants LIMIT 1);
UPDATE expense SET tenant_id = (SELECT id FROM tenants LIMIT 1);
-- ... all tables

-- Make NOT NULL after backfill
ALTER TABLE client ALTER COLUMN tenant_id SET NOT NULL;
```

**Phase 2: Enable RLS (after all data is backfilled)**
```sql
ALTER TABLE client ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON client
  FOR ALL USING (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid);
```

**Phase 3: Update application code**
- Update repositories to accept and propagate `tenantId`
- Update RPC functions to accept `tenant_id` parameter
- Update middleware to extract tenant from JWT

### 7.2 Migration Tooling

Use Supabase CLI migrations with versioned SQL files:

```
supabase/migrations/
  20260710000000_add_tenants_table.sql
  20260710000001_add_tenant_id_columns.sql
  20260710000002_backfill_tenant_id.sql
  20260710000003_enable_rls.sql
  20260710000004_add_rls_policies.sql
  20260710000005_update_rpc_functions.sql
```

### 7.3 Multi-Tenant Migration (If Moving to Schema-per-Tenant Later)

Not applicable for initial implementation. If needed later:

```sql
-- Template migration that runs across all tenant schemas
DO $$
DECLARE
  tenant_schema TEXT;
BEGIN
  FOR tenant_schema IN SELECT slug FROM tenants WHERE status = 'active'
  LOOP
    EXECUTE format('ALTER TABLE %I.client ADD COLUMN IF NOT EXISTS new_col TEXT', tenant_schema);
  END LOOP;
END;
$$;
```

---

## 8. Backup and Restore

### 8.1 Per-Tenant Backup Capability

```typescript
// lib/tenant/backup.ts
export async function createTenantBackup(tenantId: string): Promise<string> {
  const supabase = getSupabaseServiceClient();

  // 1. Export all tenant data
  const exportData = await exportTenantData(tenantId);

  // 2. Upload to cold storage (S3/GCS)
  const backupKey = `backups/${tenantId}/${new Date().toISOString().split('T')[0]}.json`;
  await uploadToStorage(backupKey, JSON.stringify(exportData, null, 2));

  // 3. Record backup metadata
  await supabase.from('tenant_backups').insert({
    tenant_id: tenantId,
    backup_key: backupKey,
    size_bytes: JSON.stringify(exportData).length,
    created_at: new Date().toISOString(),
  });

  return backupKey;
}
```

### 8.2 Restore from Backup

```typescript
export async function restoreTenantBackup(tenantId: string, backupKey: string) {
  // 1. Download backup from storage
  const backupData = await downloadFromStorage(backupKey);

  // 2. Begin transaction
  const supabase = getSupabaseServiceClient();

  // 3. Delete existing tenant data
  await supabase.from('client').delete().eq('tenant_id', tenantId);
  await supabase.from('expense').delete().eq('tenant_id', tenantId);
  // ... all tables

  // 4. Insert backup data
  for (const [table, rows] of Object.entries(backupData.data)) {
    if (rows && rows.length > 0) {
      await supabase.from(table).insert(rows.map(r => ({ ...r, tenant_id: tenantId })));
    }
  }
}
```

### 8.3 Automated Backup Schedule

- Daily backups for active tenants (pg_dump + S3)
- Weekly backups for suspended tenants
- Monthly backups for deleted tenants (retention compliance)
- Backup retention: 30 days active, 90 days deleted

---

## 9. Cost Model

### 9.1 Infrastructure Cost Per Tenant

| Component | Free Tier | Pro Tier | Enterprise Tier |
|---|---|---|---|
| **Compute** | Shared (no dedicated) | Shared | Dedicated (optional) |
| **Storage** | ~10 MB (5 clients, 100 invoices) | ~100 MB (100 clients, 10K invoices) | ~1 GB+ |
| **Bandwidth** | ~100 MB/month | ~2 GB/month | ~20 GB/month |
| **AI Tokens** | 1,000/month | 50,000/month | Unlimited |
| **DB Connections** | Pooled | Pooled | Pooled + dedicated |

### 9.2 Cost Estimation Formula

```
Cost per tenant = 
  (storage_mb × storage_rate)
  + (bandwidth_gb × bandwidth_rate)
  + (ai_cost_per_token × tokens_used)
  + (compute_fraction × compute_rate)
  + (backup_storage × backup_rate)
```

### 9.3 Supabase Pricing Impact

- **Free tier**: 500 MB database, 1 GB bandwidth, 50K MAU — ~50-100 free tenants
- **Pro tier** ($25/month): 8 GB database, 100 GB bandwidth, 100K MAU — ~200-500 pro tenants
- **Team tier** ($599/month): 100 GB database, 2 TB bandwidth — ~2000+ enterprise tenants

### 9.4 Revenue vs Cost Target

- Free tier: Acquisition cost (no revenue, minimal infra)
- Pro tier: R$299/month — target R$50-100 infrastructure cost (60-80% margin)
- Enterprise tier: R$999+/month — target R$200-400 infrastructure cost (60-80% margin)

---

## 10. Migration from Single-Tenant

### 10.1 Zero-Downtime Migration Steps

**Step 1: Create `tenants` table and seed default tenant**
```sql
-- Migration: 20260710_add_tenants.sql
CREATE TABLE tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  plan TEXT DEFAULT 'enterprise',  -- existing tenant gets enterprise
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Seed: existing single-tenant becomes first tenant
INSERT INTO tenants (slug, name, plan) VALUES
  ('default', 'L2 Cashflow Default', 'enterprise');
```

**Step 2: Add nullable `tenant_id` to all tables**
```sql
-- Migration: 20260710_add_tenant_id.sql
-- All columns nullable initially — zero downtime

ALTER TABLE client ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE expense ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE invoice ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE partner_wallet ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE partner_transaction ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE client_accounts ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE contracts ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE plans ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE usage_events ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE research_jobs ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE invoice_line_items ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE plus_subscriptions ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE billing_events ADD COLUMN tenant_id UUID REFERENCES tenants(id);
```

**Step 3: Backfill existing data (background job)**
```sql
-- Migration: 20260710_backfill.sql
-- Run as background job, not blocking

DO $$
DECLARE
  default_tenant_id UUID;
BEGIN
  SELECT id INTO default_tenant_id FROM tenants WHERE slug = 'default';

  UPDATE client SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
  UPDATE expense SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
  UPDATE invoice SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
  UPDATE partner_wallet SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
  UPDATE partner_transaction SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
  UPDATE client_accounts SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
  UPDATE contracts SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
  UPDATE plans SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
  UPDATE usage_events SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
  UPDATE research_jobs SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
  UPDATE invoice_line_items SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
  UPDATE plus_subscriptions SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
  UPDATE billing_events SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
END;
$$;
```

**Step 4: Add NOT NULL constraint + indexes**
```sql
-- Migration: 20260710_finalize_schema.sql

-- Add NOT NULL after backfill
ALTER TABLE client ALTER COLUMN tenant_id SET NOT NULL;
-- ... repeat for all tables

-- Add composite indexes for tenant-scoped queries
CREATE INDEX idx_client_tenant ON client(tenant_id);
CREATE INDEX idx_expense_tenant ON expense(tenant_id);
CREATE INDEX idx_invoice_tenant ON invoice(tenant_id);
CREATE INDEX idx_usage_events_tenant ON usage_events(tenant_id);
CREATE INDEX idx_usage_events_tenant_date ON usage_events(tenant_id, created_at);
-- ... repeat for all frequently queried tables
```

**Step 5: Enable RLS**
```sql
-- Migration: 20260710_enable_rls.sql

ALTER TABLE client ENABLE ROW LEVEL SECURITY;
ALTER TABLE expense ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice ENABLE ROW LEVEL SECURITY;
-- ... all tables

-- Tenant isolation policies
CREATE POLICY tenant_isolation ON client FOR ALL
  USING (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid)
  WITH CHECK (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid);
-- ... repeat for all tables
```

### 10.2 Application Code Changes

**Phase 1: Thread tenant through (backward-compatible)**
```typescript
// Update repository interfaces to accept optional tenantId
interface IClientRepository {
  getAll(tenantId?: string): Promise<Client[]>;
  getById(id: string, tenantId?: string): Promise<Client | null>;
  // ...
}

// Supabase implementation uses tenantId
class SupabaseClientRepository implements IClientRepository {
  async getAll(tenantId?: string): Promise<Client[]> {
    const supabase = getSupabaseClient();
    let query = supabase.from('client').select('*');
    if (tenantId) {
      query = query.eq('tenant_id', tenantId);
    }
    const { data, error } = await query.order('created_at', { ascending: false });
    if (error) throw error;
    return (data || []).map(rowToClient);
  }
}
```

**Phase 2: Middleware tenant extraction**
```typescript
// app/middleware.ts
import { NextResponse } from 'next/server';

export function middleware(request) {
  const host = request.headers.get('host') || '';
  const subdomain = host.split('.')[0];

  // Validate subdomain against tenants table
  // Set tenant context in request headers or JWT
  // Forward to API routes

  return NextResponse.next({
    headers: {
      'x-tenant-slug': subdomain,
    },
  });
}
```

### 10.3 Rollback Strategy

If migration fails:
1. Disable RLS: `ALTER TABLE client DISABLE ROW LEVEL SECURITY;`
2. Drop tenant_id columns: `ALTER TABLE client DROP COLUMN tenant_id;`
3. Restore from backup

### 10.4 Timeline

| Phase | Duration | What |
|---|---|---|
| Schema + backfill | 1-2 days | Add tenant_id, backfill, indexes |
| RLS policies | 1 day | Enable RLS, write policies |
| Repository refactor | 2-3 days | Thread tenant through all repos |
| RPC function updates | 1-2 days | Update 6 RPC functions |
| Auth/JWT integration | 2-3 days | Supabase Auth custom claims |
| Testing + validation | 2-3 days | RLS audit, cross-tenant isolation tests |
| **Total** | **9-14 days** | |

---

## Appendix: Table-to-Tenant Mapping

| Table | tenant_id Required | Notes |
|---|---|---|
| `tenants` | N/A | This IS the tenant table |
| `plans` | No | Global plan definitions |
| `client` | Yes | Legacy clients per tenant |
| `expense` | Yes | |
| `invoice` | Yes | |
| `partner_wallet` | Yes | |
| `partner_transaction` | Yes | |
| `client_accounts` | Yes | Becomes alias for tenants |
| `contracts` | Yes | |
| `usage_events` | Yes | High volume — needs composite index |
| `model_rate_cards` | No | Global rate cards |
| `search_rate_cards` | No | Global rate cards |
| `research_jobs` | Yes | |
| `invoice_line_items` | Yes | |
| `plus_subscriptions` | Yes | |
| `billing_events` | Yes | |

---

## Appendix: RLS Policy Template

```sql
-- Template for adding RLS to any table
-- Replace {TABLE_NAME} with actual table name

-- 1. Add tenant_id column (if not already added)
ALTER TABLE {TABLE_NAME} ADD COLUMN tenant_id UUID REFERENCES tenants(id);

-- 2. Enable RLS
ALTER TABLE {TABLE_NAME} ENABLE ROW LEVEL SECURITY;

-- 3. Create tenant isolation policy
CREATE POLICY tenant_isolation_{TABLE_NAME} ON {TABLE_NAME}
  FOR ALL
  USING (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid)
  WITH CHECK (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid);

-- 4. Create admin bypass policy (for service_role)
CREATE POLICY admin_bypass_{TABLE_NAME} ON {TABLE_NAME}
  FOR ALL
  USING (auth.role() = 'service_role');

-- 5. Add index
CREATE INDEX idx_{TABLE_NAME}_tenant ON {TABLE_NAME}(tenant_id);
```
