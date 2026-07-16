# Batch 4 Summary: Advanced & Infrastructure

## Key Findings

### Multi-Entity (B4-multi-entity.md)
- 70-95 days, Master COA + override pattern
- Explicit IC account mapping (not auto-detection)
- Staggered close with IC reconciliation gate
- Consolidation pipeline: collect→translate→eliminate→NCI→aggregate→validate

### Analytics/BI (B4-analytics-bi.md)
- DuckDB for embedded OLAP (zero-ops, in-process)
- Metabase SDK + Cube.js complementary pair
- 10 pre-built financial KPIs
- WebSocket for live dashboards with 30s polling fallback

### Security (B4-security-hardening.md)
- 29 person-weeks across 4 phases
- PCI SAQ A-EP via tokenization (card data never touches servers)
- Envelope encryption (AES-256-GCM) for PII
- LGPD deletion via cryptographic erasure

### Performance (B4-performance.md)
- Critical N+1 in `getLocalEnterpriseContext()` — top priority
- All 6 RPC functions prevent index usage with `to_char()` — replace with date ranges
- `usage_events` highest-ROI index: covering index with INCLUDE clause
- Zero indexes beyond primary keys in current schema

### Testing (B4-testing-strategy.md)
- 118 hours total (28h setup + 63h authoring + 27h/3mo maintenance)
- 6-week rollout plan
- `lib/db/index.ts` needs DI for testability (currently hardcoded)
- All monetary values use `number` (IEEE 754) — decimal.js is legal-risk mitigation
- Zero test framework currently installed

### Deployment/DevOps (B4-deployment-devops.md)
- ~$126-161/mo for production (Supabase Pro + Vercel Pro + Sentry)
- Unleash OSS for feature flags (self-hosted, no per-seat cost)
- 60 hours initial setup + 20 hours/month maintenance
- Zero-downtime migrations: add column → backfill → add constraint

## Batch 4 Subtotal
- Multi-Entity: 70-95 days
- Analytics/BI: ~40 days (estimated)
- Security: 29 person-weeks (~145 days)
- Performance: ~20 days (estimated)
- Testing: 118 hours (~24 days)
- Deployment: 60 hours (~12 days)
- **Batch 4 subtotal: ~310-335 days (~62-67 weeks)**
