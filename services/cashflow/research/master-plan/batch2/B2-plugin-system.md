# B2 — Plugin System Skeleton

> L2 Cashflow Modular Platform · Generated 2026-07-10
> Decision D-022 scope: dynamic JS/TS imports + TOML manifests for MVP

---

## 1. Module Manifest Format

Every module ships a `cashflow.toml` at its package root. The loader reads this before importing code.

```toml
# cashflow.toml — L2 Cashflow Module Manifest (v1)

[module]
name = "tax-engine"
version = "0.1.0"
description = "Brazilian tax calculation engine (ICMS, ISS, PIS, COFINS)"
author = "L2 Systems"
license = "MIT"
min_platform_version = "0.2.0"

[module.permissions]
db_write = true
db_read = true
event_publish = true
event_subscribe = true
register_routes = true
register_sidebar = false

# Dependencies — resolved at install time, enforced at load time
[dependencies]
"chart-of-accounts" = ">=0.1.0"
"general-ledger" = ">=0.1.0"
"accounts-payable" = ">=0.1.0"

# Optional dependencies — enhance functionality, not blocking
[dependencies.optional]
"fiscal-year" = ">=0.1.0"

# What this module contributes to the platform
[contributes]

# API routes the module registers
[contributes.routes]
"/api/tax/calculate" = "POST"
"/api/tax/breakdown" = "GET"
"/api/tax/rules" = "GET"
"/api/tax/rules/:id" = "PUT"

# UI pages the module registers (Next.js App Router paths)
[contributes.ui]
"/enterprise/tax" = "Tax Engine"
"/enterprise/tax/rules" = "Tax Rules"
"/enterprise/tax/breakdown/:id" = "Tax Breakdown"

# Sidebar navigation items
[contributes.sidebar]
name = "Tax Engine"
href = "/enterprise/tax"
icon = "Calculator"
position = 40
group = "enterprise"

# Events this module subscribes to (handler = method name)
[contributes.events_subscribe]
"invoice.created" = "onInvoiceCreated"
"invoice.paid" = "onInvoicePaid"
"payment.completed" = "onPaymentCompleted"

# Events this module publishes
[contributes.events_publish]
"tax.calculated" = "TaxCalculatedPayload"
"tax.rule.updated" = "TaxRuleUpdatedPayload"
"tax.return.generated" = "TaxReturnGeneratedPayload"

# Database migrations
[contributes.db]
migration_dir = "migrations"
namespace = "tax_engine"  # tables prefixed with this

# Lifecycle hooks
[lifecycle]
pre_init = "preInit"
post_init = "postInit"
activate = "activate"
deactivate = "deactivate"
uninstall = "uninstall"
```

### Manifest Schema Validation

At install time, the loader validates the manifest against a JSON Schema derived from the above structure. Required fields: `module.name`, `module.version`, `module.min_platform_version`. Validation happens before any code is imported.

---

## 2. Module Registry

The registry is a database table tracking every installed module's state and metadata.

### Schema

```sql
CREATE TABLE IF NOT EXISTS plugin_modules (
  id            TEXT PRIMARY KEY,            -- e.g. "tax-engine"
  name          TEXT NOT NULL,               -- display name
  version       TEXT NOT NULL,               -- semver
  description   TEXT,
  author        TEXT,
  license       TEXT,
  status        TEXT DEFAULT 'disabled',     -- installed | enabled | disabled | error
  manifest_json TEXT NOT NULL,               -- full cashflow.toml serialized as JSON
  installed_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  enabled_at    DATETIME,
  disabled_at   DATETIME,
  last_error    TEXT,
  load_order    INTEGER DEFAULT 0,           -- topological sort position
  checksum      TEXT NOT NULL,               -- SHA-256 of module directory
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plugin_dependencies (
  module_id     TEXT NOT NULL,               -- the dependent module
  dependency_id TEXT NOT NULL,               -- the required module
  version_range TEXT NOT NULL,               -- semver range
  optional      INTEGER DEFAULT 0,           -- 0 = required, 1 = optional
  PRIMARY KEY (module_id, dependency_id),
  FOREIGN KEY (module_id) REFERENCES plugin_modules(id) ON DELETE CASCADE,
  FOREIGN KEY (dependency_id) REFERENCES plugin_modules(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS plugin_settings (
  module_id     TEXT NOT NULL,
  key           TEXT NOT NULL,
  value_json    TEXT NOT NULL,
  PRIMARY KEY (module_id, key),
  FOREIGN KEY (module_id) REFERENCES plugin_modules(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plugin_migrations (
  id            TEXT PRIMARY KEY,            -- "tax-engine__001"
  module_id     TEXT NOT NULL,
  version       TEXT NOT NULL,
  applied_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  checksum      TEXT NOT NULL,
  FOREIGN KEY (module_id) REFERENCES plugin_modules(id) ON DELETE CASCADE
);
```

### Registry API

```typescript
// lib/plugins/registry.ts
export interface PluginRegistry {
  install(manifest: PluginManifest): Promise<void>;
  uninstall(moduleId: string): Promise<void>;
  enable(moduleId: string): Promise<void>;
  disable(moduleId: string): Promise<void>;
  getEnabled(): Promise<InstalledModule[]>;
  getAll(): Promise<InstalledModule[]>;
  updateSetting(moduleId: string, key: string, value: unknown): Promise<void>;
  recordMigration(moduleId: string, version: string, checksum: string): Promise<void>;
}
```

---

## 3. Module Loader

The loader reads manifests, resolves dependencies, and dynamically imports module code at startup.

### Load Order

```
1. Scan plugin_modules table for status='enabled'
2. Build dependency graph from plugin_dependencies
3. Topological sort (Kahn's algorithm)
4. Cycle detection — abort if circular dependency found
5. For each module in sorted order:
   a. Validate version compatibility of all dependencies
   b. Resolve module entry point from manifest
   c. Dynamic import the module
   d. Call lifecycle.pre_init()
   e. Register routes, sidebar items, event listeners
   f. Run pending migrations
   g. Call lifecycle.post_init()
```

### Dynamic Import Strategy

```typescript
// lib/plugins/loader.ts

import path from 'path';

interface ModuleInstance {
  id: string;
  manifest: PluginManifest;
  exports: PluginModule;
  registered: boolean;
}

// Module resolution: npm package or local path
function resolveModulePath(moduleId: string, manifest: PluginManifest): string {
  // Strategy 1: npm package — modules published as @cashflow/mod-{name}
  // Strategy 2: local modules — loaded from ./plugins/{name}/
  // Strategy 3: workspace packages — for monorepo development

  const localPath = path.join(process.cwd(), 'plugins', moduleId);
  if (fs.existsSync(path.join(localPath, 'cashflow.toml'))) {
    return localPath;
  }
  return `@cashflow/mod-${moduleId}`;
}

export class PluginLoader {
  private instances = new Map<string, ModuleInstance>();

  async loadAll(): Promise<void> {
    const enabled = await registry.getEnabled();
    const sorted = this.topologicalSort(enabled);
    const errors: Array<{ moduleId: string; error: Error }> = [];

    for (const module of sorted) {
      try {
        await this.loadModule(module);
      } catch (err) {
        errors.push({ moduleId: module.id, error: err as Error });
        await registry.setError(module.id, (err as Error).message);
        // Don't abort — load remaining modules that don't depend on this one
      }
    }

    if (errors.length > 0) {
      console.error(`[PluginLoader] ${errors.length} module(s) failed to load:`,
        errors.map(e => e.moduleId).join(', '));
    }
  }

  private async loadModule(module: InstalledModule): Promise<void> {
    const entryPoint = resolveModulePath(module.id, module.manifest);
    const mod = await import(entryPoint);

    // Validate exports match manifest contract
    if (typeof mod.default?.register !== 'function') {
      throw new Error(`Module ${module.id} missing default export with register()`);
    }

    const instance: ModuleInstance = {
      id: module.id,
      manifest: module.manifest,
      exports: mod.default,
      registered: false,
    };

    // Pre-init hook
    if (instance.exports.lifecycle?.pre_init) {
      await instance.exports.lifecycle.pre_init(createModuleContext(module.id));
    }

    // Register contributions
    this.registerRoutes(module.id, module.manifest.contributes.routes);
    this.registerUI(module.id, module.manifest.contributes.ui);
    this.registerSidebar(module.id, module.manifest.contributes.sidebar);
    await this.registerEventHandlers(module.id, module.manifest.contributes.events_subscribe);

    instance.registered = true;
    this.instances.set(module.id, instance);

    // Post-init hook
    if (instance.exports.lifecycle?.post_init) {
      await instance.exports.lifecycle.post_init(createModuleContext(module.id));
    }
  }
}
```

### Plugin Module Contract

Every module must export a default object matching this interface:

```typescript
// lib/plugins/types.ts

export interface PluginModule {
  register(ctx: ModuleContext): void;
  lifecycle?: {
    pre_init?: (ctx: ModuleContext) => Promise<void>;
    post_init?: (ctx: ModuleContext) => Promise<void>;
    activate?: (ctx: ModuleContext) => Promise<void>;
    deactivate?: (ctx: ModuleContext) => Promise<void>;
    uninstall?: (ctx: ModuleContext) => Promise<void>;
  };
}

export interface ModuleContext {
  moduleId: string;
  db: ModuleDatabase;           // namespaced DB access
  events: ModuleEventBus;       // scoped event emitter
  settings: ModuleSettings;     // key-value settings
  logger: ModuleLogger;         // prefixed logger
  config: PlatformConfig;       // read-only platform config
}
```

---

## 4. Lifecycle Hooks

Each hook fires at a specific point in the module lifecycle.

### Hook Timeline

```
INSTALL
  → Read & validate cashflow.toml
  → Write to plugin_modules (status=installed)
  → Run initial migrations
  → Call lifecycle.pre_init()

ENABLE
  → Load module code (dynamic import)
  → Register routes, sidebar, events
  → Call lifecycle.pre_init()
  → Call lifecycle.post_init()
  → Set status=enabled

DISABLE
  → Call lifecycle.deactivate()
  → Unregister routes, sidebar, events
  → Unload module (remove from instances map)
  → Set status=disabled

UNINSTALL
  → Call lifecycle.deactivate()
  → Call lifecycle.uninstall()
  → Drop module namespace tables (optional, user confirms)
  → Remove from plugin_modules
  → Remove from plugin_dependencies

DEACTIVATE (user-initiated disable)
  → Call lifecycle.deactivate()
  → Remove event listeners
  → Keep registered routes/UI but mark as inactive
```

### Hook Semantics

| Hook | When | Can Do | Cannot Do |
|------|------|--------|-----------|
| `pre_init` | Before routes/events registered | Validate config, set up DB schema, emit events | Access other module APIs (not yet loaded) |
| `post_init` | After all modules loaded | Call other modules, register event listeners, start background tasks | Register new routes (too late) |
| `activate` | Module transitions disabled→enabled | Re-register listeners, resume background tasks | Modify DB schema |
| `deactivate` | Module transitions enabled→disabled | Stop background tasks, drain queues | Destroy data |
| `uninstall` | Module removed from platform | Clean up data, remove DB tables | Access other modules |

### Startup Sequence (Full)

```
Platform boot
  → initDB() (existing)
  → PluginRegistry.init()
  → PluginLoader.loadAll()
    → For each enabled module (topological order):
      → pre_init()
      → register routes/sidebar/events
      → post_init()
  → Start Express/Next.js server
  → Emit "platform.ready" event
```

---

## 5. Dependency Resolution

### Algorithm: Kahn's Topological Sort with Cycle Detection

```typescript
// lib/plugins/resolver.ts

interface DependencyGraph {
  nodes: Map<string, Set<string>>;  // moduleId → set of dependencies
  inDegree: Map<string, number>;
}

export function resolveLoadOrder(
  modules: InstalledModule[],
  dependencies: PluginDependency[]
): string[] {
  // Build adjacency list
  const graph: DependencyGraph = {
    nodes: new Map(),
    inDegree: new Map(),
  };

  for (const mod of modules) {
    graph.nodes.set(mod.id, new Set());
    graph.inDegree.set(mod.id, 0);
  }

  // Add edges: A depends on B → B must load before A
  for (const dep of dependencies) {
    if (!dep.optional && graph.nodes.has(dep.module_id)) {
      graph.nodes.get(dep.dependency_id)!.add(dep.module_id);
      graph.inDegree.set(dep.module_id, (graph.inDegree.get(dep.module_id) || 0) + 1);
    }
  }

  // Kahn's algorithm
  const queue: string[] = [];
  for (const [id, degree] of graph.inDegree) {
    if (degree === 0) queue.push(id);
  }

  const sorted: string[] = [];
  while (queue.length > 0) {
    const current = queue.shift()!;
    sorted.push(current);

    for (const dependent of graph.nodes.get(current) || []) {
      const newDegree = (graph.inDegree.get(dependent) || 1) - 1;
      graph.inDegree.set(dependent, newDegree);
      if (newDegree === 0) queue.push(dependent);
    }
  }

  // Cycle detection
  if (sorted.length !== modules.length) {
    const remaining = modules
      .map(m => m.id)
      .filter(id => !sorted.includes(id));
    throw new PluginError(
      `Circular dependency detected among: ${remaining.join(', ')}`
    );
  }

  return sorted;
}
```

### Version Compatibility Check

```typescript
import semver from 'semver';

export function checkVersionCompatibility(
  moduleId: string,
  dependencyId: string,
  range: string,
  installedVersion: string
): boolean {
  if (!semver.satisfies(installedVersion, range)) {
    console.error(
      `[PluginResolver] ${moduleId} requires ${dependencyId}@${range}, ` +
      `but ${installedVersion} is installed`
    );
    return false;
  }
  return true;
}
```

---

## 6. Event Bus

### MVP: In-Process EventEmitter

```typescript
// lib/plugins/events.ts

import { EventEmitter } from 'events';

export interface PluginEvent {
  type: string;
  source: string;      // moduleId that published it
  timestamp: string;   // ISO 8601
  payload: unknown;
  correlationId?: string;
}

type EventHandler = (event: PluginEvent) => Promise<void> | void;

class PluginEventBus {
  private emitter = new EventEmitter();
  private handlers = new Map<string, Map<string, EventHandler>>(); // event → (moduleId → handler)
  private eventLog: PluginEvent[] = [];  // ring buffer for debugging

  constructor() {
    this.emitter.setMaxListeners(100); // 42 modules × ~3 events each
  }

  /**
   * Subscribe a module to an event type.
   * Each module can register one handler per event type.
   */
  subscribe(eventType: string, moduleId: string, handler: EventHandler): void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Map());
    }
    this.handlers.get(eventType)!.set(moduleId, handler);

    this.emitter.on(eventType, async (event: PluginEvent) => {
      try {
        await handler(event);
      } catch (err) {
        console.error(
          `[EventBus] Handler error in ${moduleId} for ${eventType}:`, err
        );
        // Emit error event so other modules can react
        this.publish('event.handler_error', '__system__', {
          eventType,
          moduleId,
          error: (err as Error).message,
        });
      }
    });
  }

  /**
   * Publish an event to all subscribers.
   */
  publish(eventType: string, source: string, payload: unknown): void {
    const event: PluginEvent = {
      type: eventType,
      source,
      timestamp: new Date().toISOString(),
      payload,
      correlationId: `evt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    };

    // Ring buffer (keep last 1000 events)
    this.eventLog.push(event);
    if (this.eventLog.length > 1000) this.eventLog.shift();

    this.emitter.emit(eventType, event);
  }

  /**
   * Unsubscribe a module from all events (called on disable/uninstall).
   */
  unsubscribeModule(moduleId: string): void {
    for (const [eventType, handlers] of this.handlers) {
      handlers.delete(moduleId);
    }
    this.emitter.removeAllListeners();
    // Re-register remaining handlers
    for (const [eventType, handlers] of this.handlers) {
      for (const [id, handler] of handlers) {
        this.emitter.on(eventType, handler);
      }
    }
  }

  /**
   * Get recent events for debugging/audit.
   */
  getRecentEvents(limit = 50): PluginEvent[] {
    return this.eventLog.slice(-limit);
  }
}

export const pluginEvents = new PluginEventBus();
```

### Upgrade Path: Redis Streams

When the platform needs cross-process event routing (separate Rust service + Next.js), swap the implementation:

```typescript
// lib/plugins/events-redis.ts
// Implements the same PluginEventBus interface
// Uses Redis XADD/XREAD for persistence + consumer groups

export class RedisPluginEventBus implements PluginEventBus {
  private redis: Redis;

  constructor(redisUrl: string) {
    this.redis = new Redis(redisUrl);
  }

  async publish(eventType: string, source: string, payload: unknown): Promise<void> {
    await this.redis.xadd(
      `events:${eventType}`,
      '*',  // auto-generate ID
      'source', source,
      'payload', JSON.stringify(payload),
      'timestamp', new Date().toISOString()
    );
  }

  async subscribe(eventType: string, moduleId: string, handler: EventHandler): Promise<void> {
    const group = 'cashflow-plugins';
    const consumer = `mod-${moduleId}`;
    const stream = `events:${eventType}`;

    // Create group if not exists
    try {
      await this.redis.xgroup('CREATE', stream, group, '0', 'MKSTREAM');
    } catch { /* group exists */ }

    // Read loop
    const readStream = async () => {
      while (true) {
        const results = await this.redis.xreadgroup(
          'GROUP', group, consumer,
          'COUNT', 10, 'BLOCK', 5000,
          'STREAMS', stream, '>'
        );
        if (!results) continue;

        for (const [, messages] of results) {
          for (const [id, fields] of messages) {
            const event: PluginEvent = {
              type: eventType,
              source,
              timestamp: fields[fields.indexOf('timestamp') + 1],
              payload: JSON.parse(fields[fields.indexOf('payload') + 1]),
            };
            await handler(event);
            await this.redis.xack(stream, group, id);
          }
        }
      }
    };

    readStream(); // background loop
  }
}
```

---

## 7. Module-Scoped Database

Each module gets its own table namespace to prevent schema collisions.

### Naming Convention

All tables created by a module are prefixed: `{namespace}__{table_name}`

Example: `tax_engine__rules`, `tax_engine__calculations`, `tax_engine__returns`

### Migration System

```typescript
// lib/plugins/db.ts

import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';
import { db } from '../db';

export class ModuleDatabase {
  constructor(private moduleId: string, private namespace: string) {}

  /**
   * Run pending migrations for this module.
   * Migrations live in plugins/{moduleId}/migrations/*.sql
   * Named: 001_create_rules.sql, 002_add_rates.sql, etc.
   */
  async runMigrations(): Promise<void> {
    const migrationDir = path.join(
      process.cwd(), 'plugins', this.moduleId, 'migrations'
    );

    const applied = db.prepare(
      'SELECT id, version FROM plugin_migrations WHERE module_id = ?'
    ).all(this.moduleId) as Array<{ id: string; version: string }>;

    const appliedVersions = new Set(applied.map(a => a.version));

    let files: string[];
    try {
      files = (await fs.readdir(migrationDir))
        .filter(f => f.endsWith('.sql'))
        .sort();
    } catch {
      return; // no migrations directory
    }

    for (const file of files) {
      const version = file.replace('.sql', '');
      if (appliedVersions.has(version)) continue;

      const sql = await fs.readFile(path.join(migrationDir, file), 'utf-8');

      // Replace generic table references with namespaced ones
      const namespaced = sql.replace(/CREATE TABLE (\w+)/g, `CREATE TABLE IF NOT EXISTS ${this.namespace}__$1`);

      db.exec(namespaced);

      const checksum = crypto.createHash('sha256').update(sql).digest('hex');
      db.prepare(
        'INSERT INTO plugin_migrations (id, module_id, version, checksum) VALUES (?, ?, ?, ?)'
      ).run(`${this.moduleId}__${version}`, this.moduleId, version, checksum);

      console.log(`[PluginDB] Applied migration ${file} for ${this.moduleId}`);
    }
  }

  /**
   * Drop all tables for this module (used during uninstall).
   */
  async dropAllTables(): Promise<void> {
    const tables = db.prepare(
      "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?"
    ).all(`${this.namespace}__%`) as Array<{ name: string }>;

    for (const table of tables) {
      db.exec(`DROP TABLE IF EXISTS ${table.name}`);
      console.log(`[PluginDB] Dropped table ${table.name}`);
    }
  }

  /**
   * Execute a query scoped to this module's namespace.
   * Validates table names to prevent namespace escape.
   */
  query(sql: string, params?: unknown[]): unknown[] {
    this.validateTableAccess(sql);
    return db.prepare(sql).all(params || []);
  }

  private validateTableAccess(sql: string): void {
    // Block cross-namespace access
    const tableRefs = sql.match(/(?:FROM|JOIN|INTO|UPDATE)\s+(\w+)/gi) || [];
    for (const ref of tableRefs) {
      const tableName = ref.split(/\s+/).pop()!;
      // Allow system tables and own namespace
      if (
        !tableName.startsWith(this.namespace + '__') &&
        !['plugin_modules', 'plugin_dependencies', 'plugin_settings',
          'plugin_migrations', 'audit_log'].includes(tableName)
      ) {
        throw new Error(
          `[PluginDB] Module ${this.moduleId} cannot access table ${tableName}. ` +
          `Use the platform API or register a dependency on the owning module.`
        );
      }
    }
  }
}
```

### Migration File Example

```sql
-- plugins/tax-engine/migrations/001_create_rules.sql

CREATE TABLE IF NOT EXISTS rules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  tax_type TEXT NOT NULL,
  rate REAL NOT NULL,
  state_code TEXT,
  active INTEGER DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 8. Module-Scoped Routing

Modules register API routes and UI routes through the manifest.

### API Route Registration

```typescript
// lib/plugins/router.ts

import { NextRequest, NextResponse } from 'next/server';

// Module-registered route handlers
const routeHandlers = new Map<string, {
  method: string;
  handler: (req: NextRequest, ctx: ModuleContext) => Promise<NextResponse>;
  moduleId: string;
}>();

export function registerModuleRoute(
  moduleId: string,
  path: string,
  method: string,
  handler: (req: NextRequest, ctx: ModuleContext) => Promise<NextResponse>
): void {
  const key = `${method.toUpperCase()} ${path}`;
  routeHandlers.set(key, { method, handler, moduleId });
}

// Dynamic route matching
export async function handleModuleRoute(
  req: NextRequest,
  pathname: string
): Promise<NextResponse | null> {
  const method = req.method;
  const ctx = createModuleContext(
    Array.from(routeHandlers.values())
      .find(r => r.method === method && matchRoute(r.method, pathname))?.moduleId || ''
  );

  // Try exact match first, then parameterized
  for (const [key, route] of routeHandlers) {
    if (route.method !== method) continue;
    if (matchRoute(key.split(' ')[1], pathname)) {
      return route.handler(req, ctx);
    }
  }

  return null; // no module route matched
}

function matchRoute(pattern: string, pathname: string): boolean {
  // /api/tax/rules/:id matches /api/tax/rules/123
  const regex = pattern.replace(/:(\w+)/g, '(?<$1>[^/]+)');
  return new RegExp(`^${regex}$`).test(pathname);
}
```

### UI Route Registration

Modules contribute Next.js pages. At build time, the platform generates a route manifest.

```typescript
// lib/plugins/ui-routes.ts

export interface UIRoute {
  path: string;
  label: string;
  moduleId: string;
  position: number;
  group?: string;
}

// Generated at build time from all enabled module manifests
export const moduleUIRoutes: UIRoute[] = [
  // Populated by build step that reads all cashflow.toml files
];
```

### Build-Time Route Generation

A prebuild script scans all enabled modules and generates the route manifest:

```typescript
// scripts/generate-plugin-routes.ts

import { readdir } from 'fs/promises';
import path from 'path';
import TOML from '@iarna/toml';

async function generateRoutes() {
  const pluginDir = path.join(process.cwd(), 'plugins');
  const routes: UIRoute[] = [];

  const dirs = await readdir(pluginDir, { withFileTypes: true });
  for (const dir of dirs) {
    if (!dir.isDirectory()) continue;
    const manifestPath = path.join(pluginDir, dir.name, 'cashflow.toml');
    const content = await readFile(manifestPath, 'utf-8').catch(() => null);
    if (!content) continue;

    const manifest = TOML.parse(content) as PluginManifest;
    if (!manifest.contributes?.ui) continue;

    for (const [routePath, label] of Object.entries(manifest.contributes.ui)) {
      routes.push({
        path: routePath,
        label,
        moduleId: manifest.module.name,
        position: manifest.contributes.sidebar?.position || 100,
        group: manifest.contributes.sidebar?.group,
      });
    }
  }

  // Write to generated file
  await writeFile(
    path.join(process.cwd(), 'lib/plugins/generated-routes.ts'),
    `export const moduleUIRoutes = ${JSON.stringify(routes, null, 2)};`
  );
}
```

---

## 9. Module-Scoped Sidebar

The existing `Sidebar.tsx` uses a hardcoded `navigation` array. Modules inject items dynamically.

### Sidebar Registration

```typescript
// lib/plugins/sidebar.ts

export interface SidebarItem {
  name: string;
  href: string;
  icon: string;           // Lucide icon name
  position: number;       // sort order
  group?: string;         // 'main' | 'enterprise' | null
  moduleId: string;
}

class PluginSidebarRegistry {
  private items: SidebarItem[] = [];

  register(item: SidebarItem): void {
    this.items.push(item);
    this.items.sort((a, b) => a.position - b.position);
  }

  unregister(moduleId: string): void {
    this.items = this.items.filter(i => i.moduleId !== moduleId);
  }

  getItems(): SidebarItem[] {
    return [...this.items];
  }
}

export const pluginSidebar = new PluginSidebarRegistry();
```

### Sidebar Integration

Modify `Sidebar.tsx` to merge static and plugin-provided items:

```typescript
// components/Sidebar.tsx (modification)

import { pluginSidebar, SidebarItem } from '@/lib/plugins/sidebar';

const staticNavigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  // ... existing items
];

export default function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Merge static + plugin sidebar items
  const pluginItems = pluginSidebar.getItems();
  const allNavigation = [
    ...staticNavigation.map(item => ({ ...item, position: staticNavigation.indexOf(item) })),
    ...pluginItems.map(item => ({
      name: item.name,
      href: item.href,
      icon: getIcon(item.icon),  // map string to Lucide component
      position: item.position,
    })),
  ].sort((a, b) => a.position - b.position);

  // ... render with allNavigation instead of navigation
}
```

### Icon Resolution

```typescript
// lib/plugins/sidebar.ts

import * as LucideIcons from 'lucide-react';

export function getIcon(iconName: string): React.ComponentType<{ size: number }> {
  const Icon = (LucideIcons as Record<string, React.ComponentType<{ size: number }>>)[iconName];
  if (!Icon) {
    console.warn(`[Sidebar] Unknown icon: ${iconName}, falling back to Circle`);
    return LucideIcons.Circle;
  }
  return Icon;
}
```

---

## 10. Security

### Module Permission Model

Every module declares required permissions in its manifest. The registry enforces these at runtime.

### Permission Declarations

```toml
[module.permissions]
db_read = true          # Can read from any table
db_write = true         # Can write to its own namespace only
event_publish = true    # Can publish events
event_subscribe = true  # Can subscribe to events
register_routes = true  # Can register API routes
register_sidebar = false # Cannot add sidebar items
external_api = false    # Cannot make outbound HTTP calls
file_access = false     # Cannot read/write arbitrary files
```

### Sandbox Enforcement

```typescript
// lib/plugins/sandbox.ts

export function createModuleContext(moduleId: string): ModuleContext {
  const moduleDb = new ModuleDatabase(moduleId, moduleId.replace(/-/g, '_'));

  return {
    moduleId,
    db: {
      query: (sql, params) => moduleDb.query(sql, params),
      // db_write operations go through a transaction log for audit
    },
    events: {
      publish: (type, payload) => {
        pluginEvents.publish(type, moduleId, payload);
      },
      subscribe: (type, handler) => {
        pluginEvents.subscribe(type, moduleId, handler);
      },
    },
    settings: {
      get: (key) => getModuleSetting(moduleId, key),
      set: (key, value) => setModuleSetting(moduleId, key, value),
    },
    logger: createModuleLogger(moduleId),
    config: {
      getPlatformVersion: () => PLATFORM_VERSION,
      getBackendType: () => activeBackend,
    },
  };
}

// API route middleware — enforce permission checks
export function withPluginAuth(
  handler: (req: NextRequest, ctx: ModuleContext) => Promise<NextResponse>,
  requiredPermission: string
) {
  return async (req: NextRequest, ctx: ModuleContext) => {
    const manifest = registry.getModuleManifest(ctx.moduleId);
    if (!manifest?.module.permissions[requiredPermission as keyof typeof manifest.module.permissions]) {
      return NextResponse.json(
        { error: `Module ${ctx.moduleId} lacks permission: ${requiredPermission}` },
        { status: 403 }
      );
    }
    return handler(req, ctx);
  };
}
```

### Data Access Rules

1. **Module tables are namespaced** — a module can only query its own tables via `ctx.db`
2. **Cross-module data access** — modules access other modules' data through published APIs, not direct table queries
3. **Core tables are read-only** — modules can read Client, Invoice, Expense tables via the repository layer, but cannot write to them directly
4. **Audit trail** — all module database writes are logged to `plugin_audit_log`

```sql
CREATE TABLE IF NOT EXISTS plugin_audit_log (
  id          TEXT PRIMARY KEY,
  module_id   TEXT NOT NULL,
  action      TEXT NOT NULL,
  table_name  TEXT NOT NULL,
  row_id      TEXT,
  old_value   TEXT,
  new_value   TEXT,
  user_id     TEXT,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 11. Hot-Reload

Modules can be loaded/unloaded without server restart for development and live configuration changes.

### Hot-Reload Mechanism

```typescript
// lib/plugins/hot-reload.ts

import chokidar from 'chokidar';

class PluginHotReloader {
  private watcher: chokidar.FSWatcher | null = null;
  private pluginDir: string;

  constructor(pluginDir: string) {
    this.pluginDir = pluginDir;
  }

  start(): void {
    this.watcher = chokidar.watch(
      path.join(this.pluginDir, '**/cashflow.toml'),
      { ignoreInitial: true, depth: 2 }
    );

    this.watcher.on('change', async (filePath) => {
      const moduleId = this.extractModuleId(filePath);
      console.log(`[HotReload] Manifest changed: ${moduleId}`);
      await this.reloadModule(moduleId);
    });

    this.watcher.on('add', async (filePath) => {
      const moduleId = this.extractModuleId(filePath);
      console.log(`[HotReload] New module detected: ${moduleId}`);
      // Don't auto-install — require explicit enable
    });
  }

  private async reloadModule(moduleId: string): Promise<void> {
    const instance = loader.getInstance(moduleId);
    if (!instance) return;

    // 1. Deactivate
    if (instance.exports.lifecycle?.deactivate) {
      await instance.exports.lifecycle.deactivate(createModuleContext(moduleId));
    }
    pluginEvents.unsubscribeModule(moduleId);

    // 2. Clear module from Node cache
    const modulePath = resolveModulePath(moduleId, instance.manifest);
    this.clearModuleCache(modulePath);

    // 3. Re-import and re-register
    await loader.loadModule(await registry.get(moduleId));

    console.log(`[HotReload] ${moduleId} reloaded successfully`);
  }

  private clearModuleCache(modulePath: string): void {
    // Clear require/import cache for this module and its sub-modules
    const resolved = require.resolve(modulePath);
    delete require.cache[resolved];

    // Clear dynamic import cache
    Object.keys(require.cache).forEach(key => {
      if (key.startsWith(resolved)) {
        delete require.cache[key];
      }
    });
  }

  stop(): void {
    this.watcher?.close();
  }
}
```

### Limitations

- **Hot-reload does NOT apply to**:
  - Database schema changes (require migration re-run)
  - Route changes (Next.js routing is static at build time for file-system routes)
  - Module dependencies graph changes (require full restart)
- **Safe to hot-reload**:
  - Event handler logic
  - Business logic within handlers
  - Settings/configuration
  - Non-route code changes

### Full Restart Required When

- New module installed (needs route manifest regeneration)
- Module dependency graph changes
- Manifest permissions change
- Migration files modified

---

## 12. Testing Modules in Isolation

### Test Harness

```typescript
// lib/plugins/testing.ts

import { createModuleContext, ModuleContext } from './sandbox';

export interface ModuleTestHarness {
  ctx: ModuleContext;
  emit: (eventType: string, payload: unknown) => Promise<void>;
  getPublishedEvents: (eventType?: string) => PluginEvent[];
  callRoute: (method: string, path: string, body?: unknown) => Promise<Response>;
  getSidebarItems: () => SidebarItem[];
}

export async function createTestHarness(moduleId: string): Promise<ModuleTestHarness> {
  // Use in-memory database for tests
  const testDb = new InMemoryDatabase();
  const testEvents = new PluginEventBus();

  const ctx: ModuleContext = {
    moduleId,
    db: {
      query: (sql, params) => testDb.query(sql, params),
      exec: (sql) => testDb.exec(sql),
    },
    events: {
      publish: (type, payload) => testEvents.publish(type, moduleId, payload),
      subscribe: (type, handler) => testEvents.subscribe(type, moduleId, handler),
    },
    settings: {
      get: (key) => testDb.getSetting(moduleId, key),
      set: (key, value) => testDb.setSetting(moduleId, key, value),
    },
    logger: {
      info: () => {},
      warn: () => {},
      error: () => {},
    },
    config: {
      getPlatformVersion: () => '0.2.0-test',
      getBackendType: () => 'local',
    },
  };

  return {
    ctx,
    emit: async (type, payload) => testEvents.publish(type, '__test__', payload),
    getPublishedEvents: (type) => testEvents.getRecentEvents(100)
      .filter(e => !type || e.type === type),
    callRoute: async (method, path, body) => {
      const req = new NextRequest(`http://localhost${path}`, {
        method,
        body: body ? JSON.stringify(body) : undefined,
      });
      const handler = routeHandlers.get(`${method} ${path}`);
      if (!handler) throw new Error(`No route: ${method} ${path}`);
      return handler.handler(req, ctx);
    },
    getSidebarItems: () => pluginSidebar.getItems()
      .filter(i => i.moduleId === moduleId),
  };
}
```

### Example Module Test

```typescript
// plugins/tax-engine/__tests__/tax-engine.test.ts

import { describe, it, expect, beforeEach } from 'vitest';
import { createTestHarness } from '../../../lib/plugins/testing';
import taxEngine from '../index';

describe('tax-engine', () => {
  let harness: Awaited<ReturnType<typeof createTestHarness>>;

  beforeEach(async () => {
    harness = await createTestHarness('tax-engine');
    taxEngine.register(harness.ctx);
  });

  describe('event handling', () => {
    it('calculates tax when invoice is created', async () => {
      await harness.emit('invoice.created', {
        invoiceId: 'INV-001',
        amount: 1000,
        clientId: 'CLIENT-001',
        items: [{ description: 'Service', amount: 1000 }],
      });

      const events = harness.getPublishedEvents('tax.calculated');
      expect(events).toHaveLength(1);
      expect(events[0].payload).toMatchObject({
        invoiceId: 'INV-001',
        totalTax: expect.any(Number),
      });
    });
  });

  describe('API routes', () => {
    it('returns tax breakdown', async () => {
      // Seed test data
      harness.ctx.db.query(
        "INSERT INTO tax_engine__rules (id, name, tax_type, rate) VALUES ('r1', 'ISS', 'iss', 0.05)"
      );

      const res = await harness.callRoute('GET', '/api/tax/breakdown?invoiceId=INV-001');
      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.rules).toHaveLength(1);
    });
  });

  describe('sidebar', () => {
    it('registers navigation item', () => {
      const items = harness.getSidebarItems();
      expect(items).toHaveLength(1);
      expect(items[0].href).toBe('/enterprise/tax');
    });
  });
});
```

### Test Database Strategy

| Test Type | Database | Isolation Level |
|-----------|----------|----------------|
| Unit tests | In-memory SQLite | Per-test (fresh DB) |
| Integration tests | Temp file SQLite | Per-test-suite |
| E2E tests | Local dev SQLite | Shared (reset between runs) |
| Module isolation tests | In-memory SQLite + mock repos | Per-test |

---

## 13. Implementation Phases

### Phase 1 — Skeleton (Week 1)

- [ ] Plugin manifest parser (TOML → typed object)
- [ ] Plugin registry table schema + CRUD operations
- [ ] Module loader with dynamic import
- [ ] Basic lifecycle hooks (pre_init, post_init)
- [ ] In-memory event bus

**Deliverable**: Can install, enable, disable a hello-world module.

### Phase 2 — Routes & Sidebar (Week 2)

- [ ] API route registration from manifest
- [ ] UI route generation (build step)
- [ ] Sidebar integration (merge static + plugin items)
- [ ] Module-scoped database with migration runner
- [ ] Permission declarations and enforcement

**Deliverable**: Module adds routes, sidebar item, and its own DB tables.

### Phase 3 — Dependencies & Hot-Reload (Week 3)

- [ ] Dependency resolution (topological sort + cycle detection)
- [ ] Version compatibility checks
- [ ] Hot-reload for module code changes
- [ ] Module testing harness
- [ ] First real module: `tax-engine` (migrated from monolith)

**Deliverable**: Modules can depend on each other, hot-reload works, test harness available.

### Phase 4 — Production Hardening (Week 4)

- [ ] Redis Streams upgrade path for event bus
- [ ] Audit logging for module operations
- [ ] Module health checks and error recovery
- [ ] Module marketplace discovery (read-only for now)
- [ ] Documentation and module development guide

**Deliverable**: Production-ready plugin system.

---

## 14. File Structure

```
services/cashflow/
├── lib/
│   └── plugins/
│       ├── types.ts              # PluginModule, ModuleContext, PluginManifest types
│       ├── manifest.ts           # TOML parser + validator
│       ├── registry.ts           # PluginRegistry (DB operations)
│       ├── loader.ts             # PluginLoader (dynamic import)
│       ├── resolver.ts           # Dependency resolution
│       ├── events.ts             # In-process EventEmitter
│       ├── events-redis.ts       # Redis Streams upgrade
│       ├── db.ts                 # ModuleDatabase (scoped queries)
│       ├── router.ts             # API route registration
│       ├── ui-routes.ts          # UI route generation
│       ├── sidebar.ts            # Sidebar registration
│       ├── sandbox.ts            # Permission enforcement
│       ├── hot-reload.ts         # File watcher
│       ├── testing.ts            # Test harness
│       └── generated-routes.ts   # Build-time generated
├── plugins/                      # Module packages
│   ├── tax-engine/
│   │   ├── cashflow.toml
│   │   ├── index.ts
│   │   └── migrations/
│   │       └── 001_create_rules.sql
│   ├── notifications/
│   │   ├── cashflow.toml
│   │   ├── index.ts
│   │   └── migrations/
│   └── cashflow-forecast/
│       ├── cashflow.toml
│       ├── index.ts
│       └── migrations/
├── scripts/
│   └── generate-plugin-routes.ts # Build script
└── plugins.test.ts               # Integration tests for plugin system
```

---

## 15. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Manifest format | TOML | Readable, widely supported, used by Cargo/Python/Rust ecosystems |
| Module resolution | Local directory + npm package | Dev speed (local) + marketplace (npm) |
| Database isolation | Table namespace prefix | Simple, zero-config, SQLite/PG compatible |
| Event bus MVP | In-process EventEmitter | Zero dependencies, instant, single-process is fine for MVP |
| Hot-reload scope | Code only, not routes/schemas | Safe boundary — route changes need build, schema changes need migrations |
| Permission model | Manifest declarations | Declarative, auditable, enforceable at runtime |
| Dependency resolution | Kahn's topological sort | Standard, efficient O(V+E), handles cycles explicitly |
| Testing approach | In-memory SQLite + mock context | Fast, isolated, deterministic |

---

## 16. Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Module crashes host process | High | Phase 3 adds worker_threads isolation; Phase 3 adds WASM sandbox |
| Circular dependencies | Medium | Kahn's algorithm detects and reports cycles at load time |
| Module namespace collisions | Low | Prefix all tables, validate at install time |
| Hot-reload memory leaks | Medium | Track event listeners, force cleanup on unload |
| Stale route manifests | Medium | Build-time generation, prebuild script in package.json |
| Module permission escalation | High | Manifest-only permissions, no runtime override, audit logging |
