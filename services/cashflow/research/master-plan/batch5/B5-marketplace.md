# B5 — Plugin Marketplace Seeding Plan

> L2 Cashflow Modular Platform · Generated 2026-07-10
> Strategy: seed with 18 essential plugins, 0% commission initially, SDK for third-party developers

---

## 1. Essential Plugins — Priority Order

### Tier 1 — Core Financial (must ship before marketplace launch)

| # | Plugin | Priority | Why |
|---|--------|----------|-----|
| 1 | **tax-engine** | P0 | Brazilian tax calculation (ICMS, ISS, PIS, COFINS, IRPJ, CSLL). Already planned in B2; first real module. |
| 2 | **banking-integration** | P0 | OFX import, bank API sync (Itaú, Bradesco, Santander). Without this, reconciliation is manual. |
| 3 | **payment-gateways** | P0 | Stripe, PagSeguro, Mercado Pago, PIX. Enables online payment collection. |
| 4 | **cashflow-forecast** | P0 | 30/60/90-day projections based on historical patterns. Core value prop. |
| 5 | **chart-of-accounts** | P0 | Brazilian PCGA mapping. Foundation for GL, tax, and reporting. |

### Tier 2 — Compliance & Reporting (ship within 2 weeks of launch)

| # | Plugin | Priority | Why |
|---|--------|----------|-----|
| 6 | **sped-generation** | P1 | SPED Contábil + Fiscal file generation. Required by Brazilian law. |
| 7 | **esocial** | P1 | Employee social security filings. Mandatory for businesses with payroll. |
| 8 | **nfe-nfse** | P1 | NF-e and NFS-e issuance. Invoice compliance. |
| 9 | **general-ledger** | P1 | Double-entry GL with journal entries. Core accounting. |
| 10 | **accounts-payable** | P1 | AP management, payment scheduling, vendor tracking. |

### Tier 3 — Productivity (ship within 4 weeks of launch)

| # | Plugin | Priority | Why |
|---|--------|----------|-----|
| 11 | **accounts-receivable** | P2 | AR tracking, dunning, aging reports. |
| 12 | **reconciliation** | P2 | Bank statement matching, auto-reconciliation rules. |
| 13 | **notifications** | P2 | Email/WhatsApp/SMS alerts for payments, deadlines, anomalies. |
| 14 | **multi-entity** | P2 | Hold-level consolidation, intercompany transactions. |

### Tier 4 — Analytics & Intelligence (ship within 8 weeks)

| # | Plugin | Priority | Why |
|---|--------|----------|-----|
| 15 | **analytics-dashboard** | P3 | Custom KPI dashboards, drill-downs, trend analysis. |
| 16 | **budget-vs-actual** | P3 | Budget tracking with variance analysis. |
| 17 | **document-scanner** | P3 | OCR for receipts and invoices, auto-categorization. |
| 18 | **audit-trail** | P3 | Immutable change log for all financial operations. |

### Build Order Rationale

```
Week 1-4:   Tier 1 (P0) — core platform works
Week 5-6:   Tier 2 (P1) — compliance complete
Week 7-10:  Tier 3 (P2) — productivity layer
Week 11-16: Tier 4 (P3) — intelligence layer
```

Each tier depends on the previous. `chart-of-accounts` is foundational; `tax-engine` depends on it; `sped-generation` depends on both.

---

## 2. Plugin SDK Design

### Extension Points

```typescript
// lib/plugins/sdk.ts — Developer-facing SDK

export interface PluginSDK {
  // Data access
  db: ModuleDatabase;              // namespaced, sandboxed
  readOnly: ReadOnlyAPI;           // read-only access to core tables

  // Event system
  events: EventBus;               // publish/subscribe

  // UI extension
  ui: UIExtension;                 // register pages, widgets, sidebar items

  // API extension
  api: APIExtension;               // register REST routes

  // Settings
  settings: SettingsAPI;           // persistent key-value store

  // Lifecycle
  lifecycle: LifecycleAPI;         // register hooks

  // Utilities
  logger: Logger;                  // prefixed, structured logging
  config: PlatformConfig;          // read-only platform info
  storage: StorageAPI;             // file storage (images, exports)
  http: HTTPClient;                // outbound HTTP with rate limiting
}
```

### Sandboxed Data Access

```typescript
// Core table read-only access — plugins can query but not write
export interface ReadOnlyAPI {
  clients: {
    list: (filter?: ClientFilter) => Promise<Client[]>;
    getById: (id: string) => Promise<Client | null>;
  };
  invoices: {
    list: (filter?: InvoiceFilter) => Promise<Invoice[]>;
    getById: (id: string) => Promise<Invoice | null>;
  };
  expenses: {
    list: (filter?: ExpenseFilter) => Promise<Expense[]>;
    getById: (id: string) => Promise<Expense | null>;
  };
  accounts: {
    list: (filter?: AccountFilter) => Promise<Account[]>;
  };
}

// Write access — plugins can only write to their own namespace
export interface ModuleDatabase {
  query: (sql: string, params?: unknown[]) => Promise<unknown[]>;
  execute: (sql: string, params?: unknown[]) => Promise<void>;
  transaction: <T>(fn: (tx: Transaction) => Promise<T>) => Promise<T>;
}
```

### Event System

```typescript
export interface EventBus {
  // Publish an event
  publish: <T>(eventType: string, payload: T) => void;

  // Subscribe to an event
  subscribe: (eventType: string, handler: EventHandler) => void;

  // Unsubscribe
  unsubscribe: (eventType: string, handler: EventHandler) => void;
}

// Standard platform events
export type PlatformEvents = {
  // Financial
  'invoice.created': InvoiceCreatedPayload;
  'invoice.paid': InvoicePaidPayload;
  'invoice.overdue': InvoiceOverduePayload;
  'expense.created': ExpenseCreatedPayload;
  'payment.completed': PaymentCompletedPayload;
  'bank.sync.completed': BankSyncCompletedPayload;

  // Lifecycle
  'client.created': ClientCreatedPayload;
  'client.updated': ClientUpdatedPayload;
  'fiscal.year.closed': FiscalYearClosedPayload;

  // Custom events
  'plugin.event': unknown;  // plugins can define custom events
};
```

### Versioning: SemVer

```
cashflow.toml version field follows SemVer (MAJOR.MINOR.PATCH)

- MAJOR: Breaking changes to plugin API or data schema
- MINOR: New features, backward-compatible
- PATCH: Bug fixes, backward-compatible

Platform compatibility:
  min_platform_version = "0.5.0"  # SemVer range (npm semver syntax)

Dependency resolution:
  "chart-of-accounts" = ">=0.1.0"  # SemVer range enforced at load time
```

### SDK Package Distribution

```json
// Published as npm package for developers
{
  "name": "@cashflow/plugin-sdk",
  "version": "0.1.0",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "exports": {
    ".": "./dist/index.js",
    "./types": "./dist/types.js",
    "./testing": "./dist/testing.js"
  }
}
```

---

## 3. Marketplace UI

### Page Structure

```
/marketplace
├── /marketplace                    # Browse all plugins
├── /marketplace/categories         # Category browser
├── /marketplace/plugin/:slug       # Plugin detail page
├── /marketplace/developer          # Developer portal
├── /marketplace/developer/submit   # Submit a plugin
└── /marketplace/installed          # Manage installed plugins
```

### Search & Discovery

```typescript
export interface MarketplaceFilters {
  query?: string;                    // full-text search
  category?: PluginCategory;         // filter by category
  pricing?: 'free' | 'paid' | 'freemium';
  rating?: number;                   // minimum rating
  sort?: 'popular' | 'newest' | 'rating' | 'name';
  compatible?: string;               // platform version
}

export type PluginCategory =
  | 'accounting'           # GL, AP, AR, chart of accounts
  | 'tax-compliance'       # SPED, eSocial, NF-e, tax engine
  | 'banking'              # Bank sync, reconciliation
  | 'payments'             # Gateways, PIX, boleto
  | 'analytics'            # Dashboards, reports, forecasting
  | 'productivity'         # Notifications, automation
  | 'integrations'         # External API connectors
  | 'security'             # Audit, compliance, access control
  | 'industry';            # Vertical-specific (construction, retail, etc.)
```

### Plugin Detail Page

```
┌─────────────────────────────────────────────────────────────┐
│  [Plugin Icon]  Tax Engine  v1.2.0  ★★★★½ (128)  Free     │
│  by L2 Systems · Last updated 2 days ago                    │
├─────────────────────────────────────────────────────────────┤
│  [Install]  [Source Code]  [Documentation]                  │
├────────────────────┬────────────────────────────────────────┤
│  Screenshots       │  Description                          │
│  [img1] [img2]     │  Brazilian tax calculation engine...  │
│                    │                                        │
│                    │  Features:                            │
│                    │  - ICMS, ISS, PIS, COFINS             │
│                    │  - State-specific rules               │
│                    │  - Real-time calculation              │
├────────────────────┴────────────────────────────────────────┤
│  Compatibility: Cashflow ≥ 0.5.0 | Platform: Web, API      │
│  Dependencies: chart-of-accounts ≥ 0.1.0                   │
│  Permissions: db_read, db_write, event_publish              │
├─────────────────────────────────────────────────────────────┤
│  Reviews                                                    │
│  ★★★★★  "Finally, automated tax calculation for Brazil!"   │
│  — Maria S., Accounting Firm · 2 weeks ago                  │
│                                                             │
│  ★★★★☆  "Works well, needs more state-specific rules"      │
│  — João P., SME Owner · 1 month ago                        │
└─────────────────────────────────────────────────────────────┘
```

### Ratings & Reviews

```sql
CREATE TABLE plugin_reviews (
  id            TEXT PRIMARY KEY,
  plugin_id     TEXT NOT NULL,
  user_id       TEXT NOT NULL,
  rating        INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  title         TEXT,
  body          TEXT,
  helpful_count INTEGER DEFAULT 0,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (plugin_id) REFERENCES marketplace_plugins(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(plugin_id, user_id)  -- one review per user per plugin
);

CREATE TABLE plugin_ratings (
  plugin_id     TEXT PRIMARY KEY,
  avg_rating    REAL NOT NULL DEFAULT 0,
  total_ratings INTEGER NOT NULL DEFAULT 0,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (plugin_id) REFERENCES marketplace_plugins(id) ON DELETE CASCADE
);
```

### Featured Listings

```typescript
export interface FeaturedListing {
  pluginId: string;
  position: number;        // 1-5 on homepage
  banner?: string;         // custom banner image
  startAt: Date;
  endAt: Date;
  reason: string;          // 'editorial', 'promotion', 'new'
}

// Homepage sections:
// 1. Hero banner (1 featured plugin)
// 2. "Essentials" — curated by L2 (all Tier 1-2 plugins)
// 3. "New & Noteworthy" — recently added, sorted by install date
// 4. "Popular" — sorted by install count (30-day window)
// 5. "By Category" — horizontal scroll per category
```

---

## 4. Plugin Quality Assurance

### Automated Checks

```typescript
// CI pipeline for every plugin submission
export interface QA checks {
  manifestValidation: {
    required: ['module.name', 'module.version', 'module.min_platform_version'];
    semverValid: boolean;
    permissionsDeclared: boolean;
  };
  codeQuality: {
    noEval: true;              // no eval(), no Function()
    noProcessExit: true;       // no process.exit()
    noFileSystem: true;        // no fs.read/write outside sandbox
    noNetwork: true;           // no http/https (unless external_api=true)
    noChildProcess: true;      // no child_process
    noDynamicImport: true;     // no dynamic import() to unknown paths
  };
  testCoverage: {
    minimum: 80;               // percentage
    required: ['register', 'lifecycle'];
  };
  typeCheck: {
    strict: true;              // TypeScript strict mode
    noAny: true;               // no `any` types
  };
  bundleSize: {
    maxKB: 500;                // max plugin bundle size
  };
  securityScan: {
    noSecrets: true;           // no hardcoded API keys, tokens
    noSqlInjection: true;      // parameterized queries only
    noXSS: true;               // sanitized output
  };
}
```

### Sandbox Testing

```typescript
// Test runner for plugin validation
export class PluginSandbox {
  async validate(plugin: PluginSubmission): Promise<ValidationResult> {
    // 1. Install in isolated environment
    const sandbox = await this.createSandbox();

    // 2. Run manifest validation
    const manifest = await sandbox.validateManifest(plugin.manifest);

    // 3. Run plugin in sandbox
    const instance = await sandbox.install(plugin);

    // 4. Execute test suite
    const testResults = await sandbox.runTests(instance);

    // 5. Check resource usage
    const resources = await sandbox.measureResources(instance);

    // 6. Attempt to access restricted APIs
    const securityResults = await sandbox.testPermissions(instance);

    return {
      passed: manifest.valid && testResults.passed && securityResults.passed,
      manifest,
      tests: testResults,
      resources,
      security: securityResults,
    };
  }
}
```

### Manual Review

For paid plugins and plugins requesting elevated permissions:

1. **Code review** — L2 team reviews source code
2. **Security audit** — check for vulnerabilities
3. **UX review** — verify UI follows platform guidelines
4. **Performance review** — ensure no resource leaks
5. **Documentation review** — verify README, changelog, API docs

### Certification Levels

| Level | Requirements | Badge | Benefits |
|-------|-------------|-------|----------|
| **Basic** | Passes automated checks | ✓ | Listed in marketplace |
| **Verified** | + Manual review, 80%+ test coverage | ✓✓ | Featured placement, priority support |
| **Premium** | + Security audit, SLA commitment | ✓✓✓ | Premium badge, co-marketing |

---

## 5. Developer Portal

### Documentation Structure

```
/docs/developer
├── /getting-started          # Quick start guide
│   ├── /hello-world          # First plugin in 10 minutes
│   ├── /project-setup        # SDK installation, config
│   └── /manifest-guide       # cashflow.toml reference
├── /concepts
│   ├── /lifecycle            # Plugin lifecycle hooks
│   ├── /permissions          # Permission model
│   ├── /events               # Event system
│   ├── /database             # Scoped database access
│   └── /routing              # API and UI routes
├── /api-reference
│   ├── /plugin-sdk           # Full SDK API docs
│   ├── /module-context       # Context object reference
│   ├── /events               # Event catalog
│   └── /platform-events      # Standard events list
├── /guides
│   ├── /testing              # Writing tests for plugins
│   ├── /publishing           # Submitting to marketplace
│   ├── /monetization         # Pricing strategies
│   └── /best-practices       # Code patterns, error handling
├── /changelog                # SDK version history
└── /support                  # Forum, Discord, email
```

### Code Samples

```typescript
// examples/hello-world-plugin/cashflow.toml
[module]
name = "hello-world"
version = "0.1.0"
description = "A minimal example plugin"
author = "Your Name"
license = "MIT"
min_platform_version = "0.5.0"

[module.permissions]
db_write = false
db_read = true
event_subscribe = true

[contributes.ui]
"/hello" = "Hello World"

[contributes.sidebar]
name = "Hello"
href = "/hello"
icon = "Hand"position = 99
```

```typescript
// examples/hello-world-plugin/index.ts
import type { PluginSDK } from '@cashflow/plugin-sdk';

export default {
  register(sdk: PluginSDK) {
    // Subscribe to events
    sdk.events.subscribe('invoice.created', async (event) => {
      sdk.logger.info('New invoice:', event.payload.invoiceId);
    });

    // Register a UI page
    sdk.ui.registerPage('/hello', {
      component: () => import('./pages/HelloPage'),
      label: 'Hello World',
    });
  },
};
```

### Sandbox Environment

```typescript
// Developer sandbox — test plugins before submission
export class DeveloperSandbox {
  // Provision a temporary Cashflow instance
  async provision(): Promise<SandboxInstance> {
    return {
      url: `https://sandbox-${uuid()}.cashflow.dev`,
      apiKey: generateApiKey(),
      expiresIn: '24h',
      features: ['all'],
    };
  }

  // Deploy plugin to sandbox
  async deploy(instance: SandboxInstance, plugin: PluginPackage): Promise<void> {
    // Upload plugin files
    // Run manifest validation
    // Install and enable
    // Run smoke tests
  }

  // Get test results
  async getResults(instance: SandboxInstance): Promise<TestResults> {
    // Return test output, logs, metrics
  }
}
```

---

## 6. Revenue Model

### Phase 1: Marketplace Launch (Months 1-6)

```
Commission: 0%
Goal: Attract developers, build catalog
Target: 50+ plugins, 1000+ installs
```

### Phase 2: Growth (Months 7-12)

```
Commission: 10% on paid plugins only
Free plugins: always 0%
Goal: Sustainable marketplace economics
Target: 200+ plugins, 10,000+ installs
```

### Phase 3: Scale (Year 2+)

```
Commission: 15% on paid plugins
Premium placement fees: optional
API usage fees: for high-volume integrations
Goal: Marketplace self-sustaining
Target: 500+ plugins, 50,000+ installs
```

### Revenue Projections

| Period | Plugins | Avg Revenue/Plugin | Gross GMV | Commission (15%) |
|--------|---------|-------------------|-----------|-------------------|
| Month 6 | 50 | R$0 (all free) | R$0 | R$0 |
| Month 12 | 200 | R$50/mo | R$10,000/mo | R$1,500/mo |
| Year 2 | 500 | R$80/mo | R$40,000/mo | R$6,000/mo |
| Year 3 | 1000 | R$120/mo | R$120,000/mo | R$18,000/mo |

---

## 7. Plugin Monetization Models

### Model Comparison

| Model | Best For | Revenue Stability | Developer Appeal |
|-------|----------|-------------------|------------------|
| **Free** | Core features, community tools | None | High (volume) |
| **One-time purchase** | Niche tools, compliance modules | Medium | Medium |
| **Subscription (monthly)** | Active-maintenance plugins | High | High |
| **Freemium** | Plugins with basic + premium tiers | High | High |
| **Usage-based** | API integrations, high-volume tools | Variable | Medium |

### Recommendations by Plugin Type

| Plugin Type | Recommended Model | Pricing Range |
|-------------|-------------------|---------------|
| Tax compliance (SPED, eSocial) | Subscription | R$49-199/mo |
| Banking integration | Subscription + usage | R$29-99/mo + R$0.10/sync |
| Payment gateways | Transaction fee | 0.5-1% per transaction |
| Analytics dashboards | Freemium | Free (3 dashboards) / R$29/mo (unlimited) |
| Notification services | Usage-based | R$0.05/SMS, R$0.02/WhatsApp |
| Document scanning | Freemium | Free (10 scans/mo) / R$19/mo (unlimited) |
| Industry verticals | Subscription | R$99-499/mo |
| Open source tools | Free + sponsorship | R$0 (sponsor button) |

### Freemium Strategy

```typescript
export interface FreemiumTier {
  free: {
    features: string[];       // list of free features
    limits: {
      maxRecords: number;     // e.g., 100 invoices/mo
      maxUsers: number;       // e.g., 1 user
      maxApiCalls: number;    // e.g., 1000/mo
    };
  };
  paid: {
    features: string[];       // all features
    price: number;            // monthly BRL
    trialDays: number;        // free trial period
  };
}
```

---

## 8. Governance

### Deprecation Policy

```
1. ANNOUNCE: Deprecation notice published 6 months before removal
2. WARN: Deprecation warnings in plugin logs and developer portal
3. DISABLE: Deprecated features disabled by default (opt-in to keep)
4. REMOVE: Feature removed from platform
5. MIGRATE: Migration guide provided for affected plugins
```

### Breaking Change Management

```
MAJOR version bump required when:
- Plugin API changes (new required parameters, removed endpoints)
- Event payload structure changes
- Database schema changes (new required columns)
- Permission model changes
- SDK interface changes

Migration path:
1. Deprecation period: 3 months
2. Backward-compatible adapter provided
3. Migration script available
4. Documentation updated
5. Developer notification sent
```

### Compatibility Matrix

```sql
CREATE TABLE compatibility_matrix (
  plugin_id       TEXT NOT NULL,
  plugin_version  TEXT NOT NULL,
  platform_min    TEXT NOT NULL,     -- minimum platform version
  platform_max    TEXT,              -- maximum platform version (null = no max)
  dependencies    TEXT NOT NULL,     -- JSON: {"plugin-id": ">=version"}
  status          TEXT NOT NULL,     -- 'supported' | 'deprecated' | 'unsupported'
  notes           TEXT,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (plugin_id, plugin_version)
);
```

### Plugin Lifecycle States

```
draft → submitted → review → approved → published
                                          ↓
                              deprecated → removed

Review states:
- pending: awaiting automated checks
- in_review: manual review in progress
- changes_requested: developer needs to fix issues
- approved: ready to publish
- rejected: does not meet quality standards
```

---

## 9. Ecosystem Growth

### Developer Outreach

| Channel | Strategy | Timeline |
|---------|----------|----------|
| **GitHub** | Open-source SDK, example plugins, contribution guides | Launch |
| **Discord** | Developer community, Q&A, announcements | Launch |
| **Blog** | Tutorials, case studies, plugin highlights | Monthly |
| **YouTube** | Video tutorials, webinars, conference talks | Monthly |
| **Twitter/X** | Product updates, developer spotlights | Weekly |
| **Meetups** | Local developer events in São Paulo, Belo Horizonte | Quarterly |

### Hackathons

```
Quarterly hackathons:
- Theme: "Build a Cashflow Plugin"
- Prizes: R$5,000 / R$3,000 / R$2,000 (1st/2nd/3rd)
- Duration: 48 hours
- Judging: Code quality, innovation, business value
- Output: New plugins added to marketplace
```

### Co-Marketing

```
- Plugin of the Month: featured in newsletter, social media
- Case Studies: success stories from plugin developers
- Partner Program: certified developers get priority support
- Conference Sponsorship: speak at Brazilian tech/accounting events
- Integration Partners: co-develop with banks, payment providers
```

### Community Programs

| Program | Description | Benefit |
|---------|-------------|---------|
| **First Plugin Grant** | R$1,000 for first published plugin | Encourages new developers |
| **Bug Bounty** | R$100-1,000 for security issues | Improves marketplace security |
| **Documentation Bounty** | R$50-200 for doc improvements | Better developer experience |
| **Beta Tester** | Early access to new features | Better testing coverage |

---

## 10. API Endpoints

### Marketplace API

```yaml
# Plugin Discovery
GET    /api/marketplace/plugins                    # List all plugins (with filters)
GET    /api/marketplace/plugins/:slug              # Get plugin details
GET    /api/marketplace/plugins/:slug/versions     # List plugin versions
GET    /api/marketplace/plugins/:slug/reviews      # Get plugin reviews
GET    /api/marketplace/plugins/featured           # Get featured plugins
GET    /api/marketplace/categories                 # List categories
GET    /api/marketplace/search?q=...               # Search plugins

# Plugin Management (authenticated)
POST   /api/marketplace/install                    # Install a plugin
DELETE /api/marketplace/uninstall/:slug            # Uninstall a plugin
POST   /api/marketplace/enable/:slug               # Enable a plugin
POST   /api/marketplace/disable/:slug              # Disable a plugin
PUT    /api/marketplace/plugins/:slug/settings      # Update plugin settings

# Reviews & Ratings (authenticated)
POST   /api/marketplace/plugins/:slug/reviews      # Submit a review
PUT    /api/marketplace/plugins/:slug/reviews/:id  # Update a review
DELETE /api/marketplace/plugins/:slug/reviews/:id  # Delete a review
POST   /api/marketplace/plugins/:slug/helpful       # Mark review as helpful

# Developer API
POST   /api/marketplace/developer/register          # Register as developer
POST   /api/marketplace/developer/plugins           # Submit a plugin
PUT    /api/marketplace/developer/plugins/:slug      # Update plugin metadata
GET    /api/marketplace/developer/plugins/:slug/stats # Get plugin analytics
GET    /api/marketplace/developer/earnings           # Get earnings report
POST   /api/marketplace/developer/plugins/:slug/versions  # Publish new version
```

### Plugin Installation Flow

```
1. User clicks "Install" on marketplace page
2. POST /api/marketplace/install { pluginId: "tax-engine", version: "1.2.0" }
3. Server validates:
   - Plugin exists and is published
   - Version is compatible with platform
   - Dependencies are satisfied
   - User has permission to install plugins
4. Server downloads plugin package
5. Server validates manifest
6. Server runs automated QA checks
7. Server writes to plugin_modules (status='installed')
8. Server runs migrations
9. Server enables plugin (status='enabled')
10. Server loads plugin and registers routes/events
11. Response: { success: true, plugin: {...}, warnings: [] }
```

---

## 11. Effort Estimates

### Component Breakdown

| Component | Effort (person-days) | Dependencies |
|-----------|---------------------|--------------|
| **SDK Core** | 15 | Plugin system (B2) |
| **Marketplace DB Schema** | 3 | None |
| **Marketplace API** | 10 | Schema |
| **Marketplace UI** | 12 | API |
| **Search & Filtering** | 5 | API, schema |
| **Review System** | 5 | API, schema |
| **Developer Portal** | 8 | SDK docs |
| **Sandbox Environment** | 10 | SDK core |
| **QA Pipeline** | 8 | Sandbox |
| **Certification System** | 3 | QA pipeline |
| **Payment Integration** | 10 | Payment gateways plugin |
| **Featured Listings** | 3 | API, UI |
| **Analytics Dashboard** | 5 | API |
| **Documentation** | 8 | All above |
| **Total (MVP)** | **105** | — |

### Timeline

```
Month 1:  SDK Core + DB Schema + Marketplace API (28 days)
Month 2:  Marketplace UI + Search + Reviews (22 days)
Month 3:  Developer Portal + Sandbox + QA (26 days)
Month 4:  Payment + Featured + Analytics + Docs (26 days)
Month 5:  Testing + Polish + Launch (3 days buffer)
```

### Team Size Recommendation

| Role | Count | Focus |
|------|-------|-------|
| Backend Engineer | 2 | SDK, API, QA pipeline, payment |
| Frontend Engineer | 2 | Marketplace UI, developer portal |
| DevOps | 1 | Sandbox environment, CI/CD |
| Technical Writer | 1 | Documentation, tutorials |
| **Total** | **6** | 105 person-days / ~17.5 working days/person |

### Per-Plugin Build Estimate

| Plugin | Effort (days) | Rationale |
|--------|---------------|-----------|
| tax-engine | 8 | Complex tax rules, state-specific |
| banking-integration | 10 | Multiple bank APIs, OFX parsing |
| payment-gateways | 8 | Multiple providers, security critical |
| cashflow-forecast | 6 | Algorithm-heavy, fewer integrations |
| chart-of-accounts | 5 | Foundational, well-defined PCGA rules |
| sped-generation | 7 | Complex file format, compliance critical |
| esocial | 7 | Government API, XML generation |
| nfe-nfse | 6 | XML generation, digital certificates |
| general-ledger | 5 | Double-entry accounting, standard |
| accounts-payable | 5 | Standard AP functionality |
| accounts-receivable | 4 | Standard AR functionality |
| reconciliation | 6 | Matching algorithms, bank formats |
| notifications | 4 | Multi-channel, simple logic |
| multi-entity | 8 | Consolidation, intercompany |
| analytics-dashboard | 6 | Charts, drill-downs, exports |
| budget-vs-actual | 4 | Comparison logic, reports |
| document-scanner | 6 | OCR integration, classification |
| audit-trail | 3 | Simple logging, immutable |
| **Total** | **108** | — |

---

## 12. Summary

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Initial commission | 0% | Maximize developer adoption |
| Commission at scale | 15% | Industry standard, sustainable |
| Plugin distribution | npm packages | Standard, versioned, dependency management |
| Manifest format | TOML | Consistent with B2 plugin system |
| Review system | 1 review/user/plugin | Prevents manipulation |
| QA pipeline | Automated + manual | Balance speed and quality |
| Certification | 3 tiers | Incentivize quality |

### Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Low developer adoption | High | 0% commission, grants, hackathons |
| Poor plugin quality | High | Automated QA, sandbox testing, certification |
| Security vulnerabilities | Critical | Sandbox isolation, permission model, code review |
| Plugin conflicts | Medium | Dependency resolution, compatibility matrix |
| Marketplace discoverability | Medium | Search, categories, featured listings |

### Success Metrics (Year 1)

| Metric | Target |
|--------|--------|
| Total plugins | 200+ |
| Active developers | 50+ |
| Monthly installs | 10,000+ |
| Average rating | 4.0+ |
| Plugin coverage | 90% of common use cases |
| Developer NPS | 50+ |

---

## 13. File Structure

```
services/cashflow/
├── lib/plugins/sdk/                    # Developer SDK
│   ├── index.ts                        # Main exports
│   ├── types.ts                        # Type definitions
│   ├── testing.ts                      # Test harness
│   └── package.json                    # npm package config
├── app/marketplace/
│   ├── page.tsx                        # Browse plugins
│   ├── categories/page.tsx             # Category browser
│   ├── plugin/[slug]/page.tsx          # Plugin detail
│   ├── installed/page.tsx              # Installed plugins
│   └── developer/
│       ├── page.tsx                    # Developer dashboard
│       └── submit/page.tsx             # Submit plugin
├── lib/marketplace/
│   ├── schema.ts                       # DB schema
│   ├── api.ts                          # Marketplace API
│   ├── search.ts                       # Search & filtering
│   ├── reviews.ts                      # Review system
│   ├── qa.ts                           # QA pipeline
│   ├── sandbox.ts                      # Sandbox environment
│   └── payments.ts                     # Payment processing
├── docs/developer/
│   ├── getting-started.md              # Quick start
│   ├── sdk-reference.md                # SDK docs
│   ├── publishing.md                   # Submission guide
│   └── best-practices.md               # Patterns
└── plugins/                            # Essential plugins
    ├── tax-engine/
    ├── banking-integration/
    ├── payment-gateways/
    └── ...
```
