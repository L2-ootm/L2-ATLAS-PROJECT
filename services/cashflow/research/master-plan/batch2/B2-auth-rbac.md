# B2: Auth + RBAC — Implementation Plan

> L2 Cashflow · Authentication, Authorization, and Multi-Tenant Security

---

## 1. Auth Architecture Decision

### Options Evaluated

| Option | Pros | Cons |
|--------|------|------|
| **NextAuth.js (Auth.js v5)** | Native Next.js 16 App Router, JWT + session adapters, OAuth + Credentials, huge ecosystem | Self-hosted auth logic, manual user/role management |
| **Clerk** | Drop-in UI, built-in RBAC, SSO, MFA out-of-box | Vendor lock-in, per-user pricing, external dependency |
| **Supabase Auth** | Already in stack, RLS native, JWT auto-includes `user_id` + `tenant_id` | Limited RBAC (needs custom claims), no built-in role management UI |
| **Custom (jose + cookies)** | Full control, zero dependencies, minimal surface | High implementation effort, security burden |

### Decision: **Supabase Auth + jose for JWT extension**

**Rationale:**
- Supabase is already the data backend — using its auth avoids a second auth provider.
- Supabase Auth handles OAuth (Google, GitHub), email/password, magic links, and SSO natively.
- JWT claims can be extended via `auth.users` metadata + a `user_profiles` table for role/tenant binding.
- Supabase RLS policies use `auth.uid()` and custom JWT claims for row-level security — zero middleware needed for data access.
- `jose` library for server-side JWT verification when reading cookies outside Supabase client.
- No additional vendor. No per-user pricing. Self-hosted auth data.

**Tradeoff:** Supabase Auth's built-in RBAC is limited. We solve this with a `user_profiles` table that maps users to roles and tenants, and a thin middleware layer that enriches the JWT with role/permissions at session creation.

---

## 2. User Model

### New Tables

```sql
-- 2.1. user_profiles: extends Supabase auth.users with app-specific data
CREATE TABLE IF NOT EXISTS user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  full_name TEXT,
  avatar_url TEXT,
  tenant_id TEXT REFERENCES client_accounts(id) ON DELETE SET NULL,
  role TEXT NOT NULL DEFAULT 'viewer',
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  last_login_at TIMESTAMP WITH TIME ZONE
);

-- 2.2. role_permissions: maps roles to permission strings
CREATE TABLE IF NOT EXISTS role_permissions (
  role TEXT NOT NULL,
  permission TEXT NOT NULL,
  PRIMARY KEY (role, permission)
);

-- 2.3. user_sessions: tracks active sessions for invalidation
CREATE TABLE IF NOT EXISTS user_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  tenant_id TEXT REFERENCES client_accounts(id),
  token_hash TEXT NOT NULL,
  ip_address TEXT,
  user_agent TEXT,
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  revoked_at TIMESTAMP WITH TIME ZONE
);

-- 2.4. api_keys: programmatic access
CREATE TABLE IF NOT EXISTS api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  tenant_id TEXT REFERENCES client_accounts(id),
  name TEXT NOT NULL,
  key_hash TEXT NOT NULL,
  key_prefix TEXT NOT NULL,          -- first 8 chars for display
  scopes TEXT[] NOT NULL DEFAULT '{}',
  rate_limit INTEGER DEFAULT 1000,   -- requests per hour
  expires_at TIMESTAMP WITH TIME ZONE,
  last_used_at TIMESTAMP WITH TIME ZONE,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  revoked_at TIMESTAMP WITH TIME ZONE
);

-- 2.5. Extend audit_log for Supabase (if not already)
CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  user_email TEXT,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  details_json JSONB,
  ip_address TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### User Profile Fields

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID | FK to `auth.users` (Supabase Auth) |
| `email` | TEXT | Denormalized for query speed |
| `full_name` | TEXT | Display name |
| `avatar_url` | TEXT | Profile picture |
| `tenant_id` | UUID | Primary tenant association (multi-tenant) |
| `role` | TEXT | Primary role (`admin`, `accountant`, `viewer`, `ap_clerk`, `ar_clerk`) |
| `active` | BOOLEAN | Soft-disable without deleting |
| `last_login_at` | TIMESTAMPTZ | Audit trail |

---

## 3. RBAC Roles

### Role Hierarchy

```
admin (full access)
  └── accountant (read + write on financial modules)
        └── ap_clerk (accounts payable only)
        └── ar_clerk (accounts receivable only)
        └── viewer (read-only)
```

### Role Definitions

| Role | Description | Modules |
|------|-------------|---------|
| `admin` | Full system access, user management, settings | All |
| `accountant` | Financial operations, reports, invoicing | Invoices, Expenses, Reports, Dashboard, Clients, Contracts |
| `ap_clerk` | Accounts payable only | Expenses, Invoices (outgoing only) |
| `ar_clerk` | Accounts receivable only | Invoices (incoming), Clients, Contracts |
| `viewer` | Read-only access to all modules | All (read-only) |

---

## 4. Permission Model

### Permission String Format

```
<module>:<action>
```

### Modules

| Module | Description |
|--------|-------------|
| `dashboard` | Dashboard and overview |
| `invoices` | Invoice management (in + out) |
| `expenses` | Expense tracking |
| `clients` | Client management |
| `contracts` | Contract management |
| `reports` | Reports and analytics |
| `enterprise` | Enterprise/FinOps features |
| `partners` | Partner wallets and transactions |
| `settings` | System settings, user management |
| `audit` | Audit log viewing |

### Actions

| Action | Description |
|--------|-------------|
| `read` | View data |
| `write` | Create/update data |
| `delete` | Delete data |
| `export` | Export/download data |
| `admin` | Manage settings, users, roles |

### Full Permission Matrix

```sql
INSERT INTO role_permissions (role, permission) VALUES
-- admin: everything
('admin', 'dashboard:read'), ('admin', 'dashboard:write'),
('admin', 'invoices:read'), ('admin', 'invoices:write'), ('admin', 'invoices:delete'), ('admin', 'invoices:export'),
('admin', 'expenses:read'), ('admin', 'expenses:write'), ('admin', 'expenses:delete'), ('admin', 'expenses:export'),
('admin', 'clients:read'), ('admin', 'clients:write'), ('admin', 'clients:delete'), ('admin', 'clients:export'),
('admin', 'contracts:read'), ('admin', 'contracts:write'), ('admin', 'contracts:delete'), ('admin', 'contracts:export'),
('admin', 'reports:read'), ('admin', 'reports:export'),
('admin', 'enterprise:read'), ('admin', 'enterprise:write'),
('admin', 'partners:read'), ('admin', 'partners:write'), ('admin', 'partners:delete'),
('admin', 'settings:read'), ('admin', 'settings:write'), ('admin', 'settings:admin'),
('admin', 'audit:read'),

-- accountant: financial operations
('accountant', 'dashboard:read'),
('accountant', 'invoices:read'), ('accountant', 'invoices:write'), ('accountant', 'invoices:export'),
('accountant', 'expenses:read'), ('accountant', 'expenses:write'), ('accountant', 'expenses:export'),
('accountant', 'clients:read'), ('accountant', 'clients:write'),
('accountant', 'contracts:read'), ('accountant', 'contracts:write'),
('accountant', 'reports:read'), ('accountant', 'reports:export'),
('accountant', 'enterprise:read'),
('accountant', 'partners:read'),

-- ap_clerk: accounts payable
('ap_clerk', 'dashboard:read'),
('ap_clerk', 'expenses:read'), ('ap_clerk', 'expenses:write'),
('ap_clerk', 'invoices:read'),
('ap_clerk', 'clients:read'),

-- ar_clerk: accounts receivable
('ar_clerk', 'dashboard:read'),
('ar_clerk', 'invoices:read'), ('ar_clerk', 'invoices:write'), ('ar_clerk', 'invoices:export'),
('ar_clerk', 'clients:read'), ('ar_clerk', 'contracts:read'),
('ar_clerk', 'reports:read'),

-- viewer: read-only
('viewer', 'dashboard:read'),
('viewer', 'invoices:read'),
('viewer', 'expenses:read'),
('viewer', 'clients:read'),
('viewer', 'contracts:read'),
('viewer', 'reports:read'),
('viewer', 'enterprise:read'),
('viewer', 'partners:read');
```

---

## 5. API Key Management

### Generation Flow

1. User requests new API key via Settings > API Keys.
2. Server generates a random 32-byte key via `crypto.randomBytes(32)`.
3. Key is hashed with SHA-256 for storage (`key_hash`). The raw key is shown **once** to the user.
4. A `key_prefix` (first 8 chars) is stored for display/identification.
5. Key is inserted into `api_keys` table with scopes, rate limit, and optional expiry.

### Key Format

```
l2cf_live_<base64url-encoded-32-bytes>
```

- `l2cf_` prefix for identification
- `live_` indicates production key (vs `test_` for sandbox)

### Scoping

Each API key has explicit `scopes` array matching the permission format:
```json
["invoices:read", "invoices:write", "expenses:read"]
```

### Rotation

1. User creates a new key.
2. Old key is marked `revoked_at` (not deleted — audit trail).
3. User updates integrations to use new key.
4. After grace period (configurable, default 7 days), old key is hard-deleted.

### Revocation

- Immediate revocation: sets `revoked_at = NOW()` and `active = false`.
- All requests with revoked key return `401 Invalid API Key`.

### Rate Limiting

- Per-key rate limit stored in `api_keys.rate_limit` (default: 1000 req/hour).
- Tracked via Redis or in-memory sliding window (per-instance).
- Exceeded: `429 Too Many Requests` with `Retry-After` header.

---

## 6. JWT Design

### Claims Structure

Supabase Auth provides base JWT with `sub` (user ID), `aud`, `exp`, `iat`. We extend with custom claims via a database function that runs on login.

```json
{
  "sub": "uuid-of-user",
  "aud": "authenticated",
  "exp": 1720000000,
  "iat": 1719996400,
  "role": "authenticated",
  "app_metadata": {},
  "user_metadata": {},
  "email": "user@example.com",

  // Custom claims (injected via Supabase hook or user_profiles lookup)
  "user_id": "uuid-of-user",
  "tenant_id": "uuid-of-tenant",
  "role": "accountant",
  "permissions": [
    "dashboard:read",
    "invoices:read",
    "invoices:write",
    "expenses:read",
    "expenses:write"
  ]
}
```

### JWT Enrichment Strategy

Supabase doesn't natively support custom JWT claims in the access token. Two approaches:

**Option A: Supabase JWT Hook (recommended)**
- Create a Supabase Edge Function or database webhook that intercepts token refresh.
- Injects `tenant_id`, `role`, and `permissions` into the JWT `user_metadata` or custom claim namespace.
- Client receives enriched token automatically.

**Option B: Server-side session enrichment**
- Next.js middleware reads the Supabase JWT, looks up `user_profiles` + `role_permissions`, and attaches enriched data to the request context.
- Simpler to implement but adds a DB query per request (cached via `unstable_cache` or Redis).

**Selected: Option B** — simpler, no Edge Function dependency, and the DB query is cheap (single row + indexed permission lookup).

### Token Signing

- Access token: Supabase-managed (HS256 with Supabase JWT secret).
- Refresh token: Supabase-managed (stored in httpOnly cookie).

---

## 7. Session Management

### Token Expiry

| Token | Lifetime | Storage |
|-------|----------|---------|
| Access token | 1 hour | Memory / JS variable |
| Refresh token | 7 days | httpOnly, secure, SameSite=Lax cookie |
| API key | Configurable (default: no expiry) | Server-side only |

### Refresh Flow

1. Client checks access token expiry before API calls.
2. If expired (or about to expire), calls `/api/auth/refresh`.
3. Server validates refresh token cookie, issues new access token.
4. If refresh token is expired → redirect to login.

### Session Invalidation

- **Logout**: Revokes refresh token in Supabase, clears cookie, logs audit event.
- **Force logout (admin)**: Sets `revoked_at` on all user sessions in `user_sessions` table.
- **Password change**: Invalidates all other sessions for the user.
- **Role change**: Next token refresh picks up new permissions (no forced logout needed).

### Concurrent Sessions

- Track active sessions in `user_sessions` table.
- Admin can view and revoke individual sessions.
- Maximum concurrent sessions configurable per role (default: 5).

---

## 8. Multi-Tenant Auth + RLS

### Tenant Association

- Each `user_profiles` row has a `tenant_id` pointing to `client_accounts`.
- JWT carries `tenant_id` claim.
- Users belong to exactly one primary tenant (for now — future: multi-tenant support).

### RLS Policies

Supabase RLS policies use the JWT's `tenant_id` claim for row-level isolation:

```sql
-- Example: invoices RLS
CREATE POLICY "tenant_isolation" ON invoice
  FOR ALL
  USING (clientId = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

-- Or using auth.uid() for user-specific isolation
CREATE POLICY "user_tenant_access" ON invoice
  FOR SELECT
  USING (
    clientId IN (
      SELECT tenant_id FROM user_profiles WHERE id = auth.uid()
    )
  );
```

### RLS Enable/Disable

- **Supabase mode**: RLS enabled on all tenant-scoped tables.
- **SQLite mode**: RLS not applicable — tenant isolation enforced at the application layer via query filters.

### Middleware Integration

```typescript
// lib/auth/middleware.ts
export async function withAuth(handler: Function) {
  return async (req: NextRequest) => {
    const session = await getSession(req);
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    // Attach tenant context for RLS
    const enrichedReq = Object.assign(req, {
      userId: session.userId,
      tenantId: session.tenantId,
      role: session.role,
      permissions: session.permissions,
    });

    return handler(enrichedReq);
  };
}

export function requirePermission(permission: string) {
  return async (req: NextRequest) => {
    const session = await getSession(req);
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!session.permissions.includes(permission) && !session.permissions.includes('*')) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }
    return null; // pass through
  };
}
```

---

## 9. Audit Logging

### Events to Log

| Event | Action String | Details |
|-------|---------------|---------|
| Login (success) | `auth.login` | method (password, oauth, magic_link), ip, user_agent |
| Login (failure) | `auth.login_failed` | reason, email attempted, ip |
| Logout | `auth.logout` | session_id |
| Password change | `auth.password_change` | ip |
| Role changed | `auth.role_changed` | old_role, new_role, changed_by |
| User created | `auth.user_created` | email, role, created_by |
| User deactivated | `auth.user_deactivated` | user_id, deactivated_by |
| API key created | `auth.api_key_created` | key_name, scopes |
| API key revoked | `auth.api_key_revoked` | key_name, revoked_by |
| Permission denied | `auth.forbidden` | required_permission, endpoint |
| Session revoked | `auth.session_revoked` | user_id, revoked_by |

### Audit Log Schema (Supabase)

```sql
CREATE TABLE IF NOT EXISTS auth_audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  user_email TEXT,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL DEFAULT 'auth',
  entity_id TEXT,
  details JSONB,
  ip_address TEXT,
  user_agent TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_auth_audit_log_user ON auth_audit_log(user_id);
CREATE INDEX idx_auth_audit_log_action ON auth_audit_log(action);
CREATE INDEX idx_auth_audit_log_created ON auth_audit_log(created_at DESC);
```

### Audit Helper

```typescript
// lib/auth/audit.ts
export async function logAuthEvent(params: {
  userId?: string;
  email?: string;
  action: string;
  entityId?: string;
  details?: Record<string, unknown>;
  ip?: string;
  userAgent?: string;
}) {
  // Insert into auth_audit_log via Supabase client
  // Non-blocking: fire-and-forget with error logging
}
```

---

## 10. Setup Wizard Integration

### First-User Flow

1. User opens the app for the first time (no `user_profiles` exist).
2. Redirected to `/setup` wizard.
3. Steps:
   - **Step 1**: Create owner account (email + password via Supabase Auth).
   - **Step 2**: Profile info (full name).
   - **Step 3**: Tenant setup (create or join `client_accounts`).
   - **Step 4**: First user is automatically assigned `admin` role.
4. After setup, redirect to dashboard.

### Implementation

```typescript
// app/setup/route.ts
export async function GET() {
  // Check if any user_profiles exist
  const { count } = await supabase.from('user_profiles').select('*', { count: 'exact', head: true });
  if (count && count > 0) {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }
  // Show setup wizard
}

// After first user creation
export async function POST(request: Request) {
  const { email, password, fullName, tenantName } = await request.json();

  // 1. Create Supabase Auth user
  const { data: authUser, error } = await supabase.auth.admin.createUser({
    email, password, email_confirm: true
  });

  // 2. Create tenant (client_accounts)
  const tenant = await createClientAccount({ id: crypto.randomUUID(), name: tenantName });

  // 3. Create user_profile with admin role
  await supabase.from('user_profiles').insert({
    id: authUser.user.id,
    email,
    full_name: fullName,
    tenant_id: tenant.id,
    role: 'admin',
  });

  // 4. Log audit event
  await logAuthEvent({ userId: authUser.user.id, action: 'auth.user_created', details: { role: 'admin' } });

  // 5. Create session + redirect
}
```

### Subsequent Invites (Admin)

Admin can invite users via Settings > Users:
1. Enter email + select role.
2. System creates `user_profiles` row (inactive until first login).
3. Sends invite email (Supabase Auth invite).
4. Invitee sets password, profile becomes active.

---

## 11. API Endpoints

### Auth Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/auth/session` | None (returns current session) | Get current user session |
| `POST` | `/api/auth/login` | None | Email/password login |
| `POST` | `/api/auth/logout` | Required | Logout, invalidate session |
| `POST` | `/api/auth/refresh` | Refresh token cookie | Refresh access token |
| `POST` | `/api/auth/setup` | None (first-run only) | Create initial admin |
| `POST` | `/api/auth/invite` | Admin | Invite new user |
| `GET` | `/api/auth/oauth/:provider` | None | Initiate OAuth flow |
| `GET` | `/api/auth/oauth/callback` | None | OAuth callback |

### User Management (Admin)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/users` | Admin | List all users in tenant |
| `GET` | `/api/users/:id` | Admin | Get user details |
| `PATCH` | `/api/users/:id` | Admin | Update user (role, active) |
| `DELETE` | `/api/users/:id` | Admin | Deactivate user |
| `POST` | `/api/users/:id/reset-password` | Admin | Send password reset |

### Role Management (Admin)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/roles` | Admin | List roles with permissions |
| `GET` | `/api/roles/:role/permissions` | Admin | Get permissions for role |
| `PATCH` | `/api/roles/:role` | Admin | Update role permissions |

### API Key Management

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/api-keys` | Required | List user's API keys |
| `POST` | `/api/api-keys` | Required | Create new API key |
| `DELETE` | `/api/api-keys/:id` | Required | Revoke API key |

### Audit (Admin)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/audit` | Admin | Query audit log (filters: action, user, date range) |

### Pages

| Path | Auth | Description |
|------|------|-------------|
| `/login` | None | Login page |
| `/setup` | None (first-run) | Setup wizard |
| `/settings/users` | Admin | User management UI |
| `/settings/roles` | Admin | Role management UI |
| `/settings/api-keys` | Required | API key management UI |
| `/settings/audit` | Admin | Audit log viewer |

---

## 12. Effort Estimate

| Sub-Feature | Files | Estimate |
|-------------|-------|----------|
| **DB schema + migrations** | `supabase/schema.sql`, `lib/db/migrations/` | 0.5 day |
| **User profile model + repository** | `lib/repositories/*/user-profile.ts`, `lib/types.ts` | 0.5 day |
| **Auth middleware** | `lib/auth/middleware.ts`, `lib/auth/session.ts` | 1 day |
| **Login/logout endpoints** | `app/api/auth/login/route.ts`, `app/api/auth/logout/route.ts` | 1 day |
| **Setup wizard** | `app/setup/page.tsx`, `app/api/auth/setup/route.ts` | 1 day |
| **RBAC permission engine** | `lib/auth/permissions.ts`, `lib/auth/rbac.ts` | 1 day |
| **API key management** | `lib/auth/api-keys.ts`, `app/api/api-keys/` | 1 day |
| **JWT enrichment (session context)** | `lib/auth/jwt.ts`, `lib/auth/middleware.ts` | 0.5 day |
| **Audit logging** | `lib/auth/audit.ts`, `app/api/audit/` | 0.5 day |
| **User management endpoints** | `app/api/users/`, `app/api/roles/` | 1 day |
| **Settings pages (users, roles, API keys)** | `app/settings/` | 1.5 days |
| **Frontend auth integration** | `lib/auth/client.ts`, layout guards, nav updates | 1 day |
| **RLS policies (Supabase)** | `supabase/schema.sql` | 0.5 day |
| **Tests** | `__tests__/auth/` | 1 day |
| **Total** | | **~11 days** |

### Priority Order

1. **Phase 1 (MVP)** — 3 days: DB schema, auth middleware, login/logout, setup wizard, session context
2. **Phase 2 (RBAC)** — 3 days: permission engine, user management, role management, settings pages
3. **Phase 3 (API Keys)** — 2 days: key generation, scoping, rate limiting, management UI
4. **Phase 4 (Audit + Polish)** — 3 days: audit logging, RLS policies, tests, edge cases

---

## 13. File Structure

```
lib/auth/
├── middleware.ts          # withAuth(), requirePermission()
├── session.ts             # getSession(), createSession()
├── permissions.ts         # checkPermission(), getPermissionsForRole()
├── rbac.ts                # RBAC matrix, role definitions
├── api-keys.ts            # generateKey(), validateKey(), revokeKey()
├── jwt.ts                 # JWT enrichment, token helpers
├── audit.ts               # logAuthEvent()
└── types.ts               # Session, User, Permission types

app/
├── login/page.tsx         # Login page
├── setup/page.tsx         # First-run setup wizard
├── settings/
│   ├── users/page.tsx     # User management (admin)
│   ├── roles/page.tsx     # Role management (admin)
│   ├── api-keys/page.tsx  # API key management
│   └── audit/page.tsx     # Audit log viewer (admin)
├── api/
│   ├── auth/
│   │   ├── login/route.ts
│   │   ├── logout/route.ts
│   │   ├── refresh/route.ts
│   │   ├── session/route.ts
│   │   ├── setup/route.ts
│   │   ├── invite/route.ts
│   │   └── oauth/[provider]/route.ts
│   ├── users/
│   │   ├── route.ts
│   │   └── [id]/route.ts
│   ├── roles/
│   │   ├── route.ts
│   │   └── [role]/route.ts
│   ├── api-keys/
│   │   ├── route.ts
│   │   └── [id]/route.ts
│   └── audit/route.ts
```

---

## 14. Environment Variables

```env
# Supabase Auth (existing)
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx
SUPABASE_SERVICE_ROLE_KEY=eyJxxx   # For admin operations (user creation, etc.)

# Auth
NEXTAUTH_SECRET=                  # For JWT signing (if using NextAuth hybrid)
AUTH_COOKIE_NAME=auth-session     # Session cookie name
AUTH_COOKIE_DOMAIN=               # Cookie domain
SESSION_MAX_AGE=3600              # Access token lifetime (seconds)
REFRESH_MAX_AGE=604800            # Refresh token lifetime (seconds)
MAX_CONCURRENT_SESSIONS=5         # Per-user session limit

# API Keys
API_KEY_RATE_LIMIT=1000           # Requests per hour per key
API_KEY_GRACE_PERIOD_DAYS=7       # Days before revoked keys are deleted
```

---

## 15. Security Considerations

- **Password hashing**: Handled by Supabase Auth (bcrypt).
- **CSRF**: Next.js App Router handles CSRF for server actions. API routes use SameSite cookies.
- **Rate limiting**: Applied to login endpoint (5 attempts per minute per IP), API keys (per-key limit).
- **Brute force**: Account lockout after 10 failed attempts (Supabase Auth built-in).
- **Audit trail**: Every auth event logged. Tamper-evident via append-only table.
- **Key rotation**: API keys have optional expiry. Users encouraged to rotate quarterly.
- **Session fixation**: New session ID on every login. Old sessions invalidated on password change.
- **HTTPS only**: All auth cookies set with `Secure` flag. Redirect HTTP to HTTPS.
