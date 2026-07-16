# B4 — Testing Strategy Master Plan

> L2 Cashflow: financial correctness is a legal requirement. Every test decision below is driven by that constraint.

---

## 0. Current State

- **No test framework installed.** `package.json` has zero test dependencies.
- **Tech stack**: Next.js 16, TypeScript, better-sqlite3, Supabase JS, React 19.
- **Critical financial paths**: MEI tax calculation (`lib/tax.ts`), AI usage cost normalization (`lib/engine/normalizer.ts`), cash flow projections (`lib/forecast.ts`), degradation engine (`lib/engine/degradation.ts`), billing events, invoice management.
- **Database**: 17+ tables with foreign key constraints, SQLite dev / Supabase production.

---

## 1. Test Pyramid

```
                    ┌───────────┐
                    │  E2E (5%) │  Playwright — critical user flows
                    ├───────────┤
                    │ Integration│  API + DB + module wiring (15%)
                    ├───────────┤
                    │   Unit    │  Pure functions, calculations, logic (80%)
                    └───────────┘
```

| Layer | Target Coverage | Speed | Run Frequency |
|-------|----------------|-------|---------------|
| Unit | >90% on `lib/` | <5s total | Every commit |
| Integration | >80% on API routes + repos | <30s | Every PR |
| E2E | 100% on critical flows | <3min | Nightly + pre-merge |

---

## 2. Unit Testing Financial Calculations

### 2.1 Decimal Arithmetic

**Problem identified**: `lib/tax.ts` uses `number` (IEEE 754 float) for currency. `lib/engine/normalizer.ts` divides tokens by `1_000_000` and multiplies by rate — floating point accumulation risk.

**Action items**:
- Introduce `decimal.js` as a dependency for all money calculations.
- Wrap every monetary value in a `Money` type that enforces decimal arithmetic.
- All existing `number` money fields in types (`amount`, `monthlyPayment`, `costUsd`, `costBrl`, etc.) remain `number` at the API boundary but must use `Decimal` internally.

### 2.2 Test Framework Setup

```bash
# Install
bun add -d vitest @vitest/coverage-v8
```

**`vitest.config.ts`**:
```ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'html'],
      thresholds: {
        statements: 85,
        branches: 80,
        functions: 85,
        lines: 85,
      },
      include: ['lib/**/*.ts'],
      exclude: ['lib/**/*.test.ts', 'lib/repositories/sqlite/**/*.ts'],
    },
    include: ['lib/**/*.test.ts'],
  },
});
```

### 2.3 Parameterized Tests

Every financial function gets a table-driven test file. Pattern:

```ts
// lib/tax.test.ts
import { describe, it, expect } from 'vitest';
import { calculateMEITax } from './tax';

describe('calculateMEITax', () => {
  const cases = [
    { month: 1, expected: { alert: 'ok', percentUsed: expect.closeTo(10.52, 1) } },
    { month: 8, expected: { alert: 'warning', percentUsed: expect.closeTo(84.21, 1) } },
    { month: 10, expected: { alert: 'danger', percentUsed: expect.closeTo(100, 0) } },
    { month: 12, expected: { alert: 'danger', remaining: 0 } },
  ];

  it.each(cases)('month $month → $expected.alert', ({ month, expected }) => {
    const monthlyRevenue = 7000;
    const result = calculateMEITax(monthlyRevenue, month);
    expect(result).toMatchObject(expected);
  });
});
```

### 2.4 Property-Based Testing

Install `fast-check` for invariant testing:

```bash
bun add -d fast-check
```

Key properties to verify:

| Function | Property |
|----------|----------|
| `calculateMEITax` | `percentUsed` is always in `[0, 100]` |
| `calculateMEITax` | `remaining` is always `>= 0` |
| `calculateMEITax` | `alert` transitions monotonic: ok → warning → danger |
| `generateCashFlowProjection` | `projections.length === months` |
| `generateCashFlowProjection` | `cumulativeBalance` is cumulative sum of `estimatedProfit` |
| `getMonthComparison` | result length === numMonths |
| `calculateUsageCost` | `costBrl === costUsd * appliedFxRate` |
| `calculateUsageCost` | all costs `>= 0` |

Example:

```ts
import * as fc from 'fast-check';
import { calculateMEITax } from './tax';

it('percentUsed is always in [0, 100]', () => {
  fc.assert(
    fc.property(
      fc.float({ min: 0, max: 1_000_000 }),
      fc.integer({ min: 1, max: 12 }),
      (monthlyRevenue, month) => {
        const result = calculateMEITax(monthlyRevenue, month);
        expect(result.percentUsed).toBeGreaterThanOrEqual(0);
        expect(result.percentUsed).toBeLessThanOrEqual(100);
      }
    )
  );
});
```

### 2.5 Boundary / Edge Cases to Cover

For `calculateMEITax`:
- `monthlyRevenue = 0` → `percentUsed = 0`, alert = ok
- `monthlyRevenue = LIMITE_ANUAL_MEI / 12` (exactly at limit) → 100%
- `monthlyRevenue > LIMITE_ANUAL_MEI / 12` → capped at 100%
- `currentMonth = 0` → edge handling (is this valid?)

For `calculateUsageCost`:
- `inputTokens = 0, outputTokens = 0` → `costUsd = 0`
- `cacheHitTokens + cacheMissTokens > 0` → cache pricing path
- `modelId` not found → fallback rate applied
- `fxRateUsdBrl` override vs env default
- Large token counts (100M+) → no overflow

For `generateCashFlowProjection`:
- Empty `activeClients` → zero revenue
- No recurring expenses → zero avgRecurring
- `months = 0` → empty projections, `avgMonthlyProfit = 0`
- Cross-year boundary (e.g., startMonth = "2026-11", months = 6)

---

## 3. Golden Master Testing

### 3.1 What and Why

Financial reports must match expected outputs exactly. Golden master (snapshot) tests capture the authoritative output and fail on any drift.

### 3.2 Snapshot Targets

| Module | Snapshot Type | Update Policy |
|--------|--------------|---------------|
| `lib/forecast.ts` | `generateCashFlowProjection` output for fixed input | Manual review only |
| `lib/forecast.ts` | `getMonthComparison` output for fixed input | Manual review only |
| `lib/tax.ts` | `calculateMEITax` for known inputs | Manual review only |
| `lib/engine/normalizer.ts` | `calculateUsageCost` for known rate cards | Manual review only |
| Invoice PDF generation | Rendered PDF bytes hash | Manual review only |

### 3.3 Implementation

```ts
// lib/__golden_masters__/forecast.master.test.ts
import { generateCashFlowProjection } from '../forecast';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import path from 'path';

const MASTER_DIR = path.join(__dirname, 'snapshots');

it('forecast matches golden master', () => {
  const result = generateCashFlowProjection(FIXED_CLIENTS, FIXED_EXPENSES, '2026-01', 6);
  const snapshotPath = path.join(MASTER_DIR, 'forecast-6month.json');
  
  if (!existsSync(snapshotPath)) {
    writeFileSync(snapshotPath, JSON.stringify(result, null, 2));
    return; // First run: create baseline
  }
  
  const master = JSON.parse(readFileSync(snapshotPath, 'utf-8'));
  expect(result).toEqual(master);
});
```

### 3.4 Golden Master Update Workflow

1. Intentional change → developer runs `UPDATE_GOLDEN_MASTERS=1 vitest` to regenerate.
2. CI runs without the env var → fails if output changed.
3. PR must include the updated snapshot file + justification in the PR description.

---

## 4. Integration Testing

### 4.1 Module Interaction Tests

Test the wiring between modules that individually are correct but may break at boundaries:

| Interaction | What Breaks |
|-------------|-------------|
| `degradation.ts` → `supabase` + `dispatcher.ts` | Wrong Supabase query shape; webhook not called on threshold |
| `normalizer.ts` → `supabase` rate cards | Missing rate card → fallback triggered; wrong column names |
| `repositories/` → `db/index.ts` | Schema mismatch, missing foreign key behavior |
| `forecast.ts` → `types` | Amount fields as strings vs numbers |

### 4.2 Database Integration Tests

Use an **in-memory SQLite** database (not `dev.db`) for isolation:

```ts
import Database from 'better-sqlite3';
import { initDB } from '../db/index';

let db: Database.Database;

beforeEach(() => {
  db = new Database(':memory:');
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  // Run schema creation on the in-memory DB
  initDB(db); // Refactor needed: initDB must accept a db param
});
```

**Required refactor**: `lib/db/index.ts` currently hardcodes the database path and auto-initializes. Must be refactored to accept an injected `Database` instance for testing.

Test cases:
- CRUD operations on all repository implementations
- Foreign key cascade behavior (delete client → invoices deleted)
- Constraint violations (duplicate PK, null NOT NULL fields)
- Migration safety: additive schema changes don't break existing data

### 4.3 API Endpoint Tests

Next.js 16 App Router API routes — test with `fetch` against a running dev server or with `NextRequest`/`NextResponse` mocking:

```ts
// app/api/engine/evaluate/route.test.ts
import { createMocks } from 'node-mocks-http'; // or vitest approach
import { POST } from './route';

it('returns 400 when userId missing', async () => {
  const request = new Request('http://localhost/api/engine/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ clientId: 'c1' }),
  });
  const response = await POST(request as any);
  expect(response.status).toBe(400);
});

it('returns 401 in production without auth header', async () => {
  process.env.NODE_ENV = 'production';
  // ... test unauthorized access
});
```

API route test matrix:

| Route | Method | Test Cases |
|-------|--------|------------|
| `/api/engine/evaluate` | POST | Missing fields → 400; No auth → 401 (prod); Valid → 200 |
| `/api/tokens` | GET/POST | Token CRUD |
| `/api/webhooks/tokens` | POST | Webhook signature validation |
| `/api/mcp` | POST | MCP protocol compliance |
| `/api/atlas` | POST | Atlas integration |

---

## 5. Contract Testing

### 5.1 Repository Interface Contracts

Every repository implementation (`sqlite/`, `supabase/`) must satisfy its interface. Test once, run against both:

```ts
// lib/repositories/__contracts__/invoice.contract.test.ts
import type { IInvoiceRepository } from '../types';

export function invoiceRepositoryContract(repo: IInvoiceRepository) {
  describe('IInvoiceRepository contract', () => {
    it('create + getById round-trips', async () => { /* ... */ });
    it('getByStatus filters correctly', async () => { /* ... */ });
    it('getOverdue returns only overdue invoices', async () => { /* ... */ });
    it('delete removes the record', async () => { /* ... */ });
    it('update persists changes', async () => { /* ... */ });
  });
}

// Run against both:
import { SQLiteInvoiceRepository } from '../sqlite/invoice';
import { SupabaseInvoiceRepository } from '../supabase/invoice';

invoiceRepositoryContract(new SQLiteInvoiceRepository(/* inject db */));
// invoiceRepositoryContract(new SupabaseInvoiceRepository(/* inject client */));
```

### 5.2 Webhook Contract

`dispatcher.ts` sends payloads to L2 Atlas. Contract:

```ts
// lib/webhooks/__contracts__/dispatcher.contract.test.ts
it('sends correct payload shape', async () => {
  const mockFetch = vi.fn().mockResolvedValue({ ok: true, status: 200 });
  vi.stubGlobal('fetch', mockFetch);
  
  await dispatchWebhook('user.degraded', { user_id: 'u1' });
  
  const [url, options] = mockFetch.mock.calls[0];
  const payload = JSON.parse(options.body);
  
  expect(payload).toMatchObject({
    id: expect.stringMatching(/^whk_/),
    timestamp: expect.any(String),
    event: 'user.degraded',
    source: 'l2-cashflow',
    data: { user_id: 'u1' },
  });
});
```

---

## 6. E2E Testing

### 6.1 Framework

Playwright for browser-based E2E. Install:

```bash
bun add -d @playwright/test
npx playwright install chromium
```

### 6.2 Critical User Flows (Priority Order)

| Flow | Steps | Why Critical |
|------|-------|-------------|
| Invoice creation → payment → reconciliation | Create client → create invoice → mark paid → verify status | Core revenue tracking |
| Expense tracking with recurring | Create recurring expense → verify monthly projection includes it | Affects P&L |
| Partner wallet balance | Injection → withdrawal → verify balance | Direct money movement |
| Degradation trigger | Simulate usage → exceed hard cap → verify webhook sent | Prevents cost overruns |
| Cash flow forecast | Input clients + expenses → verify 6-month projection | Decision-critical output |
| Tax calculation end-to-end | MEI revenue input → DAS value + alert status | Legal compliance |

### 6.3 E2E Test Structure

```
tests/e2e/
  invoice-lifecycle.spec.ts
  expense-recurring.spec.ts
  partner-wallet.spec.ts
  degradation-engine.spec.ts
  cashflow-forecast.spec.ts
  tax-calculation.spec.ts
```

### 6.4 Test Environment

- Dedicated `e2e.db` SQLite database, seeded before each test suite.
- `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` point to a test project.
- Webhook URLs mocked or pointed to a local listener.

---

## 7. Performance Testing

### 7.1 Scenarios

| Scenario | What to Measure | Threshold |
|----------|----------------|-----------|
| Month-end closing | Bulk invoice status updates (1000+) | <2s |
| Bulk expense import | Insert 5000 expenses via API | <5s |
| Forecast generation | 100 clients, 12-month projection | <500ms |
| Usage cost calculation | 100k usage events sum for user | <1s |
| API cold start | First request after idle | <3s |
| Database query performance | Complex JOIN across 5 tables | <200ms |

### 7.2 Tool

Use `vitest` bench mode or a standalone script with `performance.now()`:

```ts
import { bench, describe } from 'vitest';
import { generateCashFlowProjection } from '../forecast';

describe('forecast performance', () => {
  const manyClients = Array.from({ length: 100 }, (_, i) => ({
    id: `c${i}`, name: `Client ${i}`, service: 'dev',
    monthlyPayment: 1000 + i * 100, startDate: '2025-01-01',
    active: true, notes: '',
  }));

  bench('100 clients, 12 months', () => {
    generateCashFlowProjection(manyClients, [], '2026-01', 12);
  });
});
```

---

## 8. Security Testing

### 8.1 OWASP ZAP Automation

Add to CI (nightly):

```yaml
# .github/workflows/security.yml
zap-scan:
  runs-on: ubuntu-latest
  steps:
    - name: ZAP Baseline Scan
      uses: zaproxy/action-baseline@v0.12.0
      with:
        target: ${{ secrets.STAGING_URL }}
        rules_file_name: '.zap/rules.tsv'
        fail_action: true
```

### 8.2 Targeted Security Tests

| Vector | Test | Priority |
|--------|------|----------|
| Auth bypass | `/api/engine/evaluate` without Bearer token in production | CRITICAL |
| SQL injection | Parameterized query verification in all repositories | CRITICAL |
| XSS | Client names rendered in React (auto-escaped, but verify) | MEDIUM |
| Webhook SSRF | `dispatchWebhook` URL validation — prevent internal network access | HIGH |
| IDOR | Partner wallet access — can user A access user B's balance? | HIGH |
| Rate limiting | API endpoints — no rate limiting currently, flag as risk | MEDIUM |
| Secret exposure | `.env` files, `CRON_SECRET`, `L2_ATLAS_API_KEY` not leaked in logs | HIGH |

### 8.3 Manual Penetration Testing Checklist

- [ ] Test all API endpoints with malformed JSON bodies
- [ ] Attempt privilege escalation on partner wallet operations
- [ ] Verify Supabase Row Level Security policies are active in production
- [ ] Test webhook replay attacks (duplicate `X-Webhook-Id`)
- [ ] Verify HTTPS enforcement on all endpoints
- [ ] Test for timing attacks on auth header comparison

---

## 9. Compliance Testing

### 9.1 SPED Schema Validation

When SPED (Sistema Publico de Escrituracao Digital) output is implemented:

```ts
// lib/sped/__tests__/schema-validation.test.ts
import { validateSPEDFile } from '../schema';

it('SPED file matches official XSD schema', () => {
  const output = generateSPEDFile(fixedData);
  const errors = validateSPEDFile(output);
  expect(errors).toHaveLength(0);
});

it('rejects invalid CNPJ format', () => {
  const data = { cnpj: '123' };
  const errors = validateSPEDFile(data);
  expect(errors).toContainEqual(expect.stringContaining('CNPJ'));
});
```

### 9.2 NFe XML Validation

```ts
it('NFe XML passes schema validation', () => {
  const xml = generateNFeXML(invoiceData);
  const result = validateNFeXML(xml);
  expect(result.valid).toBe(true);
});
```

### 9.3 Tax Calculation Verification

Cross-reference against known-good values from Receita Federal:

```ts
it('DAS MEI value matches official 2025 value', () => {
  expect(getDASValue()).toBe(71.60);
});

it('annual limit matches Receita Federal 2025', () => {
  // LIMITE_ANUAL_MEI = 81000 for 2024/2025
  const result = calculateMEITax(6750, 12); // 6750 * 12 = 81000
  expect(result.percentUsed).toBeCloseTo(100, 0);
  expect(result.remaining).toBe(0);
});
```

---

## 10. Test Data Management

### 10.1 Fixtures

Static data in `lib/__fixtures__/`:

```
lib/__fixtures__/
  clients.ts       — 5 standard clients with known monthly payments
  expenses.ts      — Recurring + one-time expenses
  invoices.ts      — Pending, paid, overdue invoices
  rate-cards.ts    — Known model rate cards for cost calculation
  partners.ts      — Artur + Davi wallets with known balances
```

### 10.2 Factories

Dynamic generators using `fast-check` or manual factories:

```ts
// lib/__factories__/client.factory.ts
import { Client } from '../types';

export function buildClient(overrides: Partial<Client> = {}): Client {
  return {
    id: `client-${Date.now()}`,
    name: 'Test Client',
    service: 'Desenvolvimento',
    monthlyPayment: 3000,
    startDate: '2026-01-01',
    contractMonths: 12,
    active: true,
    notes: '',
    ...overrides,
  };
}

export function buildInvoice(overrides: Partial<Invoice> = {}): Invoice {
  return {
    id: `inv-${Date.now()}`,
    clientId: 'client-1',
    clientName: 'Test Client',
    description: 'Monthly service',
    amount: 3000,
    issueDate: '2026-07-01',
    dueDate: '2026-07-10',
    paidDate: null,
    status: 'pendente',
    ...overrides,
  };
}
```

### 10.3 Synthetic Data Generation

For performance and stress tests:

```ts
// lib/__factories__/bulk.factory.ts
export function generateBulkExpenses(count: number): Expense[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `exp-${i}`,
    clientId: i % 3 === 0 ? null : `client-${i % 5}`,
    category: EXPENSE_CATEGORIES[i % EXPENSE_CATEGORIES.length],
    description: `Expense ${i}`,
    amount: Math.round(Math.random() * 5000 * 100) / 100,
    date: `2026-${String((i % 12) + 1).padStart(2, '0')}-${String((i % 28) + 1).padStart(2, '0')}`,
    recurring: i % 4 === 0,
  }));
}
```

---

## 11. CI/CD Integration

### 11.1 Test Gates

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: bun install
      - run: bun run test:unit
      - run: bun run test:coverage

  integration:
    runs-on: ubuntu-latest
    needs: unit
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: bun install
      - run: bun run test:integration

  e2e:
    runs-on: ubuntu-latest
    needs: integration
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: bun install
      - run: npx playwright install --with-deps chromium
      - run: bun run test:e2e

  security:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: ZAP Baseline Scan
        uses: zaproxy/action-baseline@v0.12.0
        with:
          target: ${{ secrets.STAGING_URL }}
```

### 11.2 Coverage Thresholds

Enforced in CI via `vitest.config.ts` thresholds. PRs that drop below thresholds are blocked.

| Metric | Minimum | Target |
|--------|---------|--------|
| Statements | 85% | 90% |
| Branches | 80% | 85% |
| Functions | 85% | 90% |
| Lines | 85% | 90% |

### 11.3 Parallel Test Execution

```ts
// vitest.config.ts
export default defineConfig({
  test: {
    // Vitest runs test files in parallel by default
    // Use pool: 'forks' for better isolation with SQLite
    pool: 'forks',
    poolOptions: {
      forks: {
        singleFork: false, // Each test file gets its own process
      },
    },
  },
});
```

### 11.4 npm Scripts

Add to `package.json`:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:unit": "vitest run --project unit",
    "test:integration": "vitest run --project integration",
    "test:e2e": "playwright test",
    "test:coverage": "vitest run --coverage",
    "test:watch": "vitest",
    "test:bench": "vitest bench",
    "test:update-golden": "UPDATE_GOLDEN_MASTERS=1 vitest run"
  }
}
```

---

## 12. Effort Estimate

### 12.1 Initial Setup (One-Time)

| Task | Hours | Notes |
|------|-------|-------|
| Test framework setup (vitest + playwright) | 4h | Config, scripts, CI pipeline |
| Refactor `lib/db/index.ts` for testability | 6h | Inject db instance, decouple init |
| Factory/fixture foundation | 8h | All entity factories, seed scripts |
| Golden master baseline creation | 4h | Capture authoritative outputs |
| CI/CD pipeline | 6h | GitHub Actions, coverage gates |
| **Subtotal** | **28h** | |

### 12.2 Per Test Type — Initial Authoring

| Test Type | Hours | Files |
|-----------|-------|-------|
| Unit: `tax.ts` | 3h | 1 test file |
| Unit: `normalizer.ts` | 4h | 1 test file + mock Supabase |
| Unit: `forecast.ts` | 3h | 1 test file |
| Unit: `utils.ts` | 1h | 1 test file |
| Unit: `degradation.ts` | 4h | 1 test file + mocks |
| Unit: `dispatcher.ts` | 2h | 1 test file |
| Integration: repositories | 12h | 6 test files (one per repo) |
| Integration: API routes | 8h | 5 test files |
| E2E: critical flows | 16h | 6 spec files |
| Golden masters | 4h | 4 snapshot files |
| Contract tests | 6h | 4 contract suites |
| **Subtotal** | **63h** | |

### 12.3 Ongoing Maintenance (Per Sprint)

| Activity | Hours/Sprint | Frequency |
|----------|-------------|-----------|
| Write tests for new features | 4h | Every feature |
| Update golden masters after intentional changes | 1h | As needed |
| Fix flaky tests | 2h | As needed |
| Review coverage reports | 1h | Weekly |
| Security scan review | 1h | Weekly |
| **Subtotal** | **~9h/sprint** | |

### 12.4 Total First 3 Months

| Category | Hours |
|----------|-------|
| Setup + initial authoring | 91h |
| Ongoing (3 sprints) | 27h |
| **Total** | **~118h** |

---

## 13. Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| No existing tests — everything is greenfield | High effort upfront | Start with highest-risk: `tax.ts`, `normalizer.ts` |
| SQLite vs Supabase behavior divergence | Integration tests pass locally but fail in prod | Contract tests; Supabase integration tests in CI against test project |
| Flaky E2E tests from Supabase latency | CI noise, developer fatigue | Mock Supabase in E2E; use real only in nightly |
| Golden master drift after intentional changes | False failures | Documented update workflow with env var |
| IEEE 754 rounding in financial calcs | Incorrect amounts — legal risk | `decimal.js` adoption; property-based tests for invariants |

---

## 14. Implementation Order

1. **Week 1**: Install vitest, create `vitest.config.ts`, refactor `lib/db/index.ts`, write unit tests for `tax.ts` and `normalizer.ts`.
2. **Week 2**: Unit tests for `forecast.ts`, `utils.ts`, `dispatcher.ts`, `degradation.ts`. Create factories.
3. **Week 3**: Integration tests for repositories + API routes. Golden master baselines.
4. **Week 4**: Contract tests. E2E setup + first 3 critical flows.
5. **Week 5**: Remaining E2E flows. CI pipeline. Coverage gates.
6. **Week 6**: Security testing setup. Performance benchmarks. Review and harden.

---

## 15. Key Refactors Required Before Testing

| File | Refactor | Why |
|------|----------|-----|
| `lib/db/index.ts` | Accept injected `Database` instance | In-memory SQLite for tests |
| `lib/engine/normalizer.ts` | Accept Supabase client as param | Mock in unit tests |
| `lib/engine/degradation.ts` | Accept Supabase client + dispatcher as params | Mock in unit tests |
| `lib/webhooks/dispatcher.ts` | Accept `fetch` as param or use `vi.stubGlobal` | Mock in tests |

These refactors are small, non-breaking, and necessary for testability. They follow the dependency injection pattern and make the code more maintainable regardless of testing.

---

*Document generated: 2026-07-10. Review quarterly or when major financial features are added.*
