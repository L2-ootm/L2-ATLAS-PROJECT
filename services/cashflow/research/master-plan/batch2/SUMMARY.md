# Batch 2 Summary: Core Module Implementation

## Key Findings

### GL + COA (B2-gl-implementation.md)
- 23.5 days total, 5 weeks solo or 3 weeks with 2 devs
- Three layers of double-entry enforcement (SQL CHECK, trigger, TypeScript)
- Partial event sourcing (append-only journal log) over full event sourcing
- Dual-write bridge for legacy migration
- 5 blockers before GL can start

### AP/AR + Invoicing (B2-ap-ar-invoicing.md)
- 57 dev-days across 3 parallel streams (~8 weeks)
- State machine: draft → finalized → sent → paid → voided
- Payment allocation engine with FIFO/partial/overpayment
- Existing Invoice table needs FULL replacement (flat model can't support accrual accounting)
- Three-way matching deferred to Wave 3

### Payments + Reconciliation (B2-payments-reconciliation.md)
- 142 days (16 weeks) across 4 phases — this is the largest module
- Pix integration needs provider adapter pattern (Asaas/PagSeguro/Gerencianet)
- Boleto barcode layouts are bank-specific (5 banks documented)
- Matching confidence: 60% amount + 25% date + 15% description
- Payment status machine: 9 states, 4 terminal states

### Plugin System (B2-plugin-system.md)
- TOML manifests + dynamic JS/TS imports + module registry (4 tables)
- Kahn's topological sort for dependency resolution
- Module-scoped table namespace `{module}__{table}`
- Hot-reload via dynamic import() + module cache invalidation

### Event Sourcing Prototype (B2-event-sourcing-prototype.md)
- 45 hours across 7 days, journal entries ONLY
- UNIQUE(aggregate_id, version) for optimistic concurrency
- Fallback CRUD schema with audit_log as drop-in replacement
- Go/No-Go matrix: 7/7 quantitative + 4/5 qualitative criteria

### Auth + RBAC (B2-auth-rbac.md)
- Supabase Auth + jose (already in stack, native RLS integration)
- 5 roles: admin, accountant, viewer, ap_clerk, ar_clerk
- 20+ API endpoints, ~11 days in 4 phases
- SQLite mode: application-level tenant isolation; Supabase mode: native RLS

## Cumulative Effort (Batch 1+2)
- GL + COA: 23.5 days
- AP/AR + Invoicing: 57 days
- Payments + Reconciliation: 142 days
- Auth + RBAC: 11 days
- Event Sourcing Prototype: 7 days (1 week timebox)
- **Batch 2 subtotal: ~240 days (~48 weeks)**
