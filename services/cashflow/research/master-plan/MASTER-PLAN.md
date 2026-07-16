# MASTER-PLAN.md — L2 Cashflow Modular Platform

> Synthesized 2026-07-10 from 5 research batches (42 findings, 590+ sources)
> Current state: Next.js 16 + React 19 + SQLite/Supabase (17 tables), internal L2 FinOps tool
> Target state: Universal modular cashflow platform (42 modules, 7 layers, multi-tenant SaaS)

---

## 1. Executive Summary

L2 Cashflow is a full rewrite from an internal AI FinOps tool into a universal modular financial platform targeting Brazilian SMBs (19M+ MEIs, 6M+ MEs). The platform will deliver 42 modules across 7 layers — Core, Compliance, Operations, Advanced, Industry, Integrations, and Automation — built on Next.js (prototype) with planned Rust cementation, PostgreSQL with RLS multi-tenancy, Drizzle ORM, and Inngest for background processing. The critical path runs Auth → General Ledger → Tax Engine → NFe/SPED → Transfer Pricing → Marketplace (5 dependency levels). Total estimated effort is 50-66 weeks (12-16 months) for the full 42-module platform, with a functional MVP (15 modules) achievable in 22-30 weeks (5-7 months). The platform differentiates through cashflow-first UX, Brazil-native compliance (NFe, NFS-e, SPED, eSocial, Pix), open-source core with plugin marketplace, and PLG-driven acquisition via invoice-as-viral-vector.

---

## 2. Vision

**A modular, open-core financial platform that makes cashflow management accessible to every Brazilian business — from a solo MEI issuing their first NFS-e to a multi-entity enterprise consolidating IFRS statements.**

Core principles:
- **Cashflow-first**: Financial visibility without requiring accounting expertise
- **Brazil-native**: Deep compliance (NFe, NFS-e, SPED, eSocial, Simples Nacional) built in, not bolted on
- **Modular**: 42 independently activatable modules — pay only for what you use
- **Open core**: Core financial modules open-source (AGPL); compliance and industry modules drive revenue
- **PLG-driven**: Invoice-as-viral-vector — every invoice sent is an acquisition channel

---

## 3. Phased Roadmap

### Phase 1: Foundation & Infrastructure

**Goal**: Establish the technical foundation — auth, data layer, core ledger, and plugin skeleton.

| Module | Effort | Complexity | Dependencies |
|--------|--------|------------|-------------|
| Auth + RBAC | 11 days | M | None |
| Chart of Accounts | 7 days | M | None |
| General Ledger | 23.5 days | XL | COA |
| DB Migration (Drizzle ORM) | 5 days | M | None |
| Plugin System Skeleton | 10 days | M | None |
| Event Sourcing Prototype | 7 days | M | GL |
| Multi-Tenancy (RLS) | 9-14 days | M | None |

**Phase effort**: ~60-77 days (12-15 weeks with 2 devs)

**Dependencies**: None — this is the foundation.

**Key risks**:
- R1 (SQLite → PostgreSQL migration): full rewrite, not migration. Mitigation: schema evolution prototype before module dev.
- R2 (Event sourcing adoption): 1-week timebox. Fallback to CRUD + audit_log.
- R3 (Plugin system complexity): start with DB-driven module registry, not full SDK.

**Deliverables**:
- PostgreSQL schema with RLS multi-tenancy
- Double-entry GL with three-layer enforcement (SQL CHECK, trigger, TypeScript)
- Auth with 5 roles (admin, accountant, viewer, ap_clerk, ar_clerk)
- TOML manifest parser + dynamic import loader
- Event sourcing prototype (journal entries only)

---

### Phase 2: Core Financial Modules

**Goal**: Deliver the transactional core — AP/AR, invoicing, payments, and expenses.

| Module | Effort | Complexity | Dependencies |
|--------|--------|------------|-------------|
| Fiscal Year | 2 days | S | GL |
| Accounts Payable | 20 days | L | GL, COA |
| Accounts Receivable | 20 days | L | GL, COA |
| Invoicing | 17 days | L | AR, GL |
| Expenses | 5 days | M | AP, GL |
| Payments (initial) | 20 days | XL | AP, AR, GL |

**Phase effort**: ~84 days (17 weeks with 2 devs)

**Dependencies**: Phase 1 complete (GL, Auth, COA).

**Key risks**:
- R28 (Feature creep): strict module isolation, maximum 3 parallel streams.
- Existing Invoice table needs FULL replacement (flat model can't support accrual accounting).
- Payment allocation engine: FIFO/partial/overpayment handling.

**Deliverables**:
- Full AP/AR with state machine (draft → finalized → sent → paid → voided)
- Invoice generation with line items
- Payment execution (Pix, boleto basics)
- Expense tracking with categorization
- Fiscal year management with period locks

---

### Phase 3: Compliance & Tax

**Goal**: Deliver Brazil-specific tax compliance — the competitive moat.

| Module | Effort | Complexity | Dependencies |
|--------|--------|------------|-------------|
| Tax Engine | 40-55 days | XL | GL, AP, COA |
| NFS-e (São Paulo first) | 40 days | XL | Tax Engine, Invoicing |
| NFe (SEFAZ integration) | 35 days | XL | Tax Engine, Invoicing |
| SPED Generation | 36-46 days | XL | Tax Engine, GL, FY |
| eSocial (S-1200, S-1299) | 30 days | L | Tax Engine, Auth |
| Digital Certificate Mgmt | 5-7 days | M | None |
| ST/DIFAL Calculation | 4-5 days | M | NFe |

**Phase effort**: ~160-218 days (32-44 weeks with 2 devs)

**Dependencies**: Phase 2 complete (GL, AP, Invoicing).

**Key risks**:
- R6 (CBS/IBS tax reform): build tax engine as rule-based config with effective dates, not hardcoded logic.
- R7 (SPED format changes): schema version tracking + golden master tests.
- R8 (NFS-e municipal fragmentation): prioritize top 100 municipalities.
- R16 (Compliance domain knowledge gap): engage licensed contador as consultant.
- R18 (SEFAZ API availability): abstraction layer with retry + circuit breakers.

**Deliverables**:
- Tax engine with versioned rules (IRPJ, CSLL, INSS, Simples Nacional, PIS/COFINS)
- NFS-e for São Paulo (ABRASF 2.03), extensible to top 10 cities
- NFe 4.00 with SEFAZ SOAP client (SVRS first)
- SPED: EFD-Contribuições, EFD-ICMS/IPI, ECD, ECF
- eSocial: S-1200 (remuneração) + S-1299 (fechamento)
- LGPD consent management (parallel track)

---

### Phase 4: Payments & Reconciliation

**Goal**: Complete the payment ecosystem — bank reconciliation, gateway integrations, and banking connectivity.

| Module | Effort | Complexity | Dependencies |
|--------|--------|------------|-------------|
| Bank Reconciliation | 40-50 days | L | GL, Payments, COA |
| Payment Gateways | 55 days | L | Payments, Invoicing, Auth |
| Banking Integration | 40 days | XL | Bank Rec, Payments, Auth |
| Advanced Payments | 30 days | L | Payments, Invoicing |

**Phase effort**: ~165-175 days (33-35 weeks with 2 devs)

**Dependencies**: Phase 2 complete (Payments, Invoicing). Can run in parallel with Phase 3.

**Key risks**:
- R20 (Payment gateway reliability): multi-gateway from day 1, idempotency keys.
- R19 (Open Finance API instability): Belvo for MVP, OFX fallback.
- Matching confidence: 60% amount + 25% date + 15% description.

**Deliverables**:
- Bank reconciliation with automated matching rules
- 4 payment gateways: Asaas, PagSeguro, Mercado Pago, Stripe
- Banking integration via Belvo (account aggregation)
- OFX/QFX/CNAB 240/400 import
- Recurring billing engine
- Payment scheduling with batch processing

---

### Phase 5: Advanced & Multi-Entity

**Goal**: Enterprise-grade features — multi-entity consolidation, analytics, and security hardening.

| Module | Effort | Complexity | Dependencies |
|--------|--------|------------|-------------|
| Multi-Entity | 70-95 days | XL | GL, COA, Auth, FY |
| Analytics/BI | 40 days | L | GL, COA |
| Security Hardening | 29 person-weeks | L | Auth, RLS |
| Performance Optimization | 20 days | M | All modules |
| Audit Trail Enhancement | 5 days | M | Auth, GL |

**Phase effort**: ~200-230 days (40-46 weeks with 2 devs)

**Dependencies**: Phase 3 complete (Tax Engine for multi-entity IC reconciliation).

**Key risks**:
- R4 (Performance at scale): PgBouncer, composite indexes, materialized views.
- R24 (PCI DSS scope): tokenization only, never touch raw card data.
- R26 (LGPD compliance): retention policies by data type, cryptographic erasure.
- R27 (Penetration testing): third-party test before GA.

**Deliverables**:
- Multi-entity with Master COA + override pattern
- Intercompany reconciliation with staggered close
- Consolidation pipeline (collect → translate → eliminate → NCI → aggregate → validate)
- DuckDB embedded OLAP + Metabase SDK
- 10 pre-built financial KPIs
- Envelope encryption (AES-256-GCM) for PII
- PCI SAQ A-EP compliance
- Critical N+1 fixes, index optimization

---

### Phase 6: Growth & Marketplace

**Goal**: Launch the marketplace ecosystem, PLG engine, and onboarding experience.

| Module | Effort | Complexity | Dependencies |
|--------|--------|------------|-------------|
| Marketplace SDK | 30 days | XL | Plugin System |
| Marketplace Seeding (15-20 plugins) | 40 days | L | SDK |
| PLG Engine | 15 days | M | Invoicing |
| Onboarding Wizard | 15 days | M | COA, Auth |
| Pricing Implementation | 10 days | M | Auth, Billing |

**Phase effort**: ~110 days (22 weeks with 2 devs)

**Dependencies**: Phase 1 (Plugin System), Phase 2 (Invoicing for PLG).

**Key risks**:
- R11 (Pricing validation): run pricing survey with 50-100 Brazilian business owners.
- R12 (Market fit): validate "cashflow-first" resonates with target market.
- R14 (Go-to-market): decide target segment before building onboarding.
- R30 (Onboarding complexity): start with 3-5 COA templates.

**Deliverables**:
- Plugin SDK with extension points, sandboxed data access, event system, SemVer
- 15-20 seed plugins (first-party)
- Invoice-as-viral-vector PLG (each invoice = acquisition channel)
- 5-step onboarding wizard (<5 min to first invoice)
- Pricing: Free/R$79/R$199/R$499 + add-ons
- Plugin certification: Community/Verified/Certified tiers

---

### Phase 7: Optimization & Scale

**Goal**: Production hardening, full test suite, and international expansion prep.

| Module | Effort | Complexity | Dependencies |
|--------|--------|------------|-------------|
| Full Test Suite | 118 hours | M | All modules |
| Performance Load Testing | 10 days | M | All modules |
| Deployment Hardening | 12 days | M | All modules |
| Multi-Currency | 30 days | L | GL, Payments, FY |
| International Expansion Prep | 20 days | L | Multi-Currency |

**Phase effort**: ~80-100 days (16-20 weeks with 2 devs)

**Dependencies**: Phases 1-6 complete.

**Key risks**:
- R5 (Next.js 16 maturity): pin versions, test upgrades in branch.
- R13 (QuickBooks/Xero entering Brazil): move fast on Brazil-native features.
- R25 (SOC 2 timeline): start collecting evidence from day 1.

**Deliverables**:
- Vitest unit/integration + Playwright E2E test suite
- Load tests with 100K journal entries, 10 tenants
- Zero-downtime migrations (expand-contract pattern)
- ~$126-161/mo production infrastructure (Supabase Pro + Vercel Pro + Sentry)
- Multi-currency with FX rate sources (BCB, ECB, Fed)
- Data residency architecture (BR, EU, US)
- Rust cementation of financial engine (per D-022)

---

## 4. Critical Path

```
PHASE 1 (Weeks 1-15)
│
├─ Auth ──────────────────────────────────────────────────────┐
├─ Chart of Accounts ──→ General Ledger ──────────────────────┤
├─ DB Migration ──────────────────────────────────────────────┤
├─ Plugin Skeleton ───────────────────────────────────────────┤
└─ Event Sourcing Prototype ──────────────────────────────────┤
                                                              │
PHASE 2 (Weeks 16-32)                                        │
│                                                             │
├─ Fiscal Year ───────────────────────────────────────────────┤
├─ Accounts Payable ──────────────────────────────────────────┤
├─ Accounts Receivable ──→ Invoicing ─────────────────────────┤
├─ Expenses ──────────────────────────────────────────────────┤
└─ Payments ──────────────────────────────────────────────────┤
                                                              │
PHASE 3 (Weeks 33-76) ◄── CRITICAL PATH (longest chain)     │
│                                                             │
├─ Tax Engine ──→ NFS-e ──→ SEFAZ/Government APIs ───────────┤
│              ├─→ NFe ────→ ─────────────────────────────────┤
│              ├─→ SPED ───→ ─────────────────────────────────┤
│              ├─→ eSocial ─→ ─────────────────────────────────┤
│              └─→ ST/DIFAL ─→ ────────────────────────────────┤
└─ Digital Certificates ──────────────────────────────────────┤
                                                              │
PHASE 4 (Weeks 33-67) ◄── PARALLEL with Phase 3             │
│                                                             │
├─ Bank Reconciliation ───────────────────────────────────────┤
├─ Payment Gateways ──────────────────────────────────────────┤
├─ Banking Integration ───────────────────────────────────────┤
└─ Advanced Payments ─────────────────────────────────────────┤
                                                              │
PHASE 5 (Weeks 77-122)                                       │
│                                                             │
├─ Multi-Entity ──→ Transfer Pricing (terminal) ─────────────┤
├─ Analytics/BI ──────────────────────────────────────────────┤
├─ Security Hardening ────────────────────────────────────────┤
└─ Performance ───────────────────────────────────────────────┤
                                                              │
PHASE 6 (Weeks 47-68) ◄── PARALLEL with Phase 4-5           │
│                                                             │
├─ Marketplace SDK ──→ Marketplace Plugins ──→ (terminal) ──┤
├─ PLG Engine ────────────────────────────────────────────────┤
├─ Onboarding Wizard ─────────────────────────────────────────┤
└─ Pricing ───────────────────────────────────────────────────┤
                                                              │
PHASE 7 (Weeks 123-142)                                      │
│                                                             │
├─ Test Suite ────────────────────────────────────────────────┤
├─ Load Testing ──────────────────────────────────────────────┤
├─ Deployment ────────────────────────────────────────────────┤
├─ Multi-Currency ──→ International Prep ──→ (terminal) ─────┤
└─ Rust Cementation ──────────────────────────────────────────┘

CRITICAL PATH: Auth → GL → Tax Engine → NFe/SPED → Multi-Entity → Marketplace
CHAIN LENGTH: 5 modules, 5 dependency levels
MINIMUM TIMELINE: ~142 weeks (solo) → ~50-66 weeks (2-3 devs, parallel phases)
```

---

## 5. Resource Requirements

### Team Composition

| Role | Count | Skills | Phase Allocation |
|------|-------|--------|-----------------|
| **Lead Developer** | 1 | Full-stack, financial systems, architecture | All phases |
| **Backend Developer** | 1-2 | TypeScript, PostgreSQL, API design | Phases 1-7 |
| **Compliance Specialist** | 1 (consultant) | Brazilian tax law, SPED, NFe, eSocial | Phases 3-4 |
| **Rust Developer** | 1 (part-time) | Rust, axum, financial computations | Phases 5-7 |
| **UX/Design** | 1 (part-time) | SaaS onboarding, financial dashboards | Phases 5-6 |

**Minimum viable team**: 2 full-time developers + 1 compliance consultant
**Optimal team**: 3-4 developers + 1 compliance consultant + 1 part-time designer

### Budget Estimate (Annual)

| Category | Monthly | Annual | Notes |
|----------|---------|--------|-------|
| Developer salaries (2-3) | R$30-50k | R$360-600k | Market rate for senior devs |
| Compliance consultant | R$5-10k | R$60-120k | Licensed contador, part-time |
| Infrastructure | R$1-2k | R$12-24k | Supabase Pro + Vercel Pro + Sentry |
| Penetration test | — | R$15-25k | One-time, before GA |
| Legal review | — | R$10-20k | Terms of Service, LGPD, compliance disclaimers |
| **Total Year 1** | — | **R$457-809k** | — |
| **Total Year 2** | — | **R$280-500k** | Reduced (SOC 2 audit adds R$100-200k) |

### Infrastructure Costs

| Service | Tier | Monthly | Purpose |
|---------|------|---------|---------|
| Supabase | Pro | ~$25 | PostgreSQL + Auth + RLS |
| Vercel | Pro | ~$20 | Next.js hosting + edge functions |
| Sentry | Team | ~$26 | Error tracking + performance |
| Inngest | Free/Pro | $0-50 | Background jobs (100K events/mo free) |
| Domain + SSL | — | ~$5 | DNS, certificates |
| **Total** | — | **~$76-126/mo** | — |

---

## 6. Risk Register — Top 10

| # | Risk | Prob | Impact | Category | Mitigation |
|---|------|------|--------|----------|------------|
| 1 | **CBS/IBS tax reform timeline uncertainty** (R6) | H | H | Compliance | Rule-based tax config with effective dates; defer PIS/COFINS/ICMS to Phase 2; engage tax consultant |
| 2 | **SQLite → PostgreSQL is a full rewrite** (R1) | H | H | Technical | Schema evolution prototype first; contract-first interfaces; expand-contract migration pattern |
| 3 | **Plugin system complexity exceeds capacity** (R3) | H | H | Technical | Start with DB module registry; lifecycle hooks in Phase 2; defer marketplace until 10+ modules stable |
| 4 | **Brazilian compliance domain knowledge gap** (R16) | H | H | Resource | Engage licensed contador; use open-source SPED/NFe libs as reference; validate against SEFAZ validators |
| 5 | **Pricing not validated with real users** (R11) | H | H | Business | Run pricing survey with 50-100 Brazilian business owners; start freemium; price compliance modules as revenue driver |
| 6 | **Payments + Reconciliation is 142 days** (B2) | H | M | Technical | Split into 4 sub-phases; bank rec can start with manual import; auto-matching deferred to Phase 4 |
| 7 | **General Ledger has 28 downstream dependents** (B1) | M | H | Technical | GL quality above all else; three-layer double-entry enforcement; event sourcing for audit trail |
| 8 | **Target market decision unresolved** (B2) | H | M | Strategic | Start with MEIs and micro-businesses (< R$80k/year); simplest compliance, largest segment |
| 9 | **Developer count vs 42-module scope** (R15) | H | H | Resource | Phase ruthlessly; MVP = 15 modules; industry modules deferred until core + compliance stable |
| 10 | **SEFAZ API availability** (R18) | H | H | Integration | Abstraction layer with retry + circuit breakers; queue submissions during downtime; EPEC contingency |

---

## 7. Success Metrics

### Phase-Level KPIs

| Phase | KPI | Target |
|-------|-----|--------|
| Phase 1 | GL posts balanced journal entries | 100% test coverage on double-entry enforcement |
| Phase 1 | Multi-tenant data isolation | Zero cross-tenant data leaks in RLS tests |
| Phase 2 | Invoice creation to payment | End-to-end flow works for 3 payment methods |
| Phase 2 | AP/AR state machine | All state transitions covered by tests |
| Phase 3 | NFS-e transmission (SP) | Successfully transmit to SEFAZ-SP homologação |
| Phase 3 | SPED file validation | Pass SEFAZ validation tools (SPEDValida) |
| Phase 3 | Tax calculation accuracy | Match contador manual calculations for 10 test cases |
| Phase 4 | Bank reconciliation match rate | >80% auto-match for standard transactions |
| Phase 4 | Payment gateway success rate | >99.5% for Pix, >98% for boleto |
| Phase 5 | Multi-entity consolidation | Correct elimination of IC balances across 3 entities |
| Phase 5 | Dashboard load time | <2s for P&L, <5s for consolidated reports |
| Phase 6 | Plugin installation success | 100% of seed plugins install and activate |
| Phase 6 | Onboarding completion | >60% complete 5-step wizard |
| Phase 7 | Test coverage | >80% unit, >60% integration |
| Phase 7 | Deployment uptime | 99.9% during beta |

### Overall Platform KPIs

| Metric | Target | Timeline |
|--------|--------|----------|
| Time to first invoice | <5 minutes | Phase 6 |
| Activation rate | >40% (trial → first invoice) | Phase 6 |
| Conversion rate | >5% (free → paid) | Phase 6 |
| Net Dollar Retention | >120% | Phase 7 |
| Monthly infrastructure cost | <$200/mo for 100 tenants | Phase 7 |
| Tax calculation accuracy | 100% vs manual contador | Phase 3 |
| SPED validation pass rate | 100% against SEFAZ tools | Phase 3 |
| Plugin ecosystem | 15-20 seed plugins | Phase 6 |

---

## 8. Decision Log

| ID | Decision | Rationale | Trade-off | Date |
|----|----------|-----------|-----------|------|
| D-001 | PostgreSQL + RLS for multi-tenancy | Best for <10K tenants; managed via Supabase; no per-tenant DB overhead | Less isolation than dedicated DB; PgBouncer requires SET app.tenant_id per transaction | 2026-07-10 |
| D-002 | Drizzle ORM over raw SQL | Type-safe, supports SQLite + PostgreSQL from same schema; migration tooling built-in | Adds abstraction layer; Drizzle is younger than Prisma/Knex | 2026-07-10 |
| D-003 | Next.js prototype → Rust cementation | D-022 compliance; prototype in TS, cement in Rust; repo pattern isolates data access | Two runtimes to maintain during transition; Rust devs are rare in Brazil | 2026-07-10 |
| D-004 | Inngest for background jobs | Zero Redis dependency; event-driven; built-in step functions; free tier covers MVP | Vendor dependency; cost at scale; learning curve | 2026-07-10 |
| D-005 | NFS-e before NFe | Services-first market; NFS-e simpler (fewer item types); São Paulo first | Delays e-commerce/retail customers | 2026-07-10 |
| D-006 | MEI/ME as initial target | Largest segment (19M+ MEIs); simplest compliance; fastest time-to-market | Delays enterprise revenue; lower ARPU | 2026-07-10 |
| D-007 | Open-core model | Core (GL, COA, invoicing) under AGPL; compliance modules proprietary | Builds community while maintaining revenue; marketplace economics | 2026-07-10 |
| D-008 | Event sourcing for journal entries only | Append-only audit trail; fallback CRUD if no value; prototype 1-week timebox | Partial adoption creates architectural confusion if not committed | 2026-07-10 |
| D-009 | Hybrid tiered + per-module pricing | Free/R$79/R$199/R$499 + add-ons; compliance modules as revenue driver | Requires pricing validation; Brazil SMBs pay 40-60% less than US | 2026-07-10 |
| D-010 | Shared DB + RLS (not dedicated per tenant) | Simpler ops; PgBouncer transaction pooling; add dedicated option for enterprise in Phase 3+ | Less isolation; RLS bugs affect all tenants | 2026-07-10 |

---

## 9. Open Questions

| # | Question | Priority | How to Resolve |
|---|----------|----------|----------------|
| 1 | **Market validation**: Do Brazilian micro/small businesses want a modular cashflow platform? | HIGH | Interview 30-50 Brazilian business owners |
| 2 | **CBS/IBS exact transition rates**: When will Receita Federal publish complete regulation? | HIGH | Subscribe to Receita Federal consultation responses; engage tax consultant |
| 3 | **Pricing final**: What price point maximizes adoption × revenue? | HIGH | Run pricing survey with 50-100 Brazilian business owners |
| 4 | **Open-source percentage**: How much of the platform is open-source? | HIGH | Core (GL, COA, invoicing) = AGPL; compliance = proprietary |
| 5 | **NFS-e municipal priority**: Which 100 municipalities to prioritize? | MEDIUM | Start with top 20 by GDP; expand based on user demand |
| 6 | **Real-time collaboration**: Do users need Yjs/CRDTs? | LOW | Default "no" for Phase 1; most SMBs have 1-2 finance users |
| 7 | **Plugin ecosystem viability**: Will third-party developers build plugins? | MEDIUM | Build core first; attract with open-source + clear SDK docs; seed with 15-20 first-party |
| 8 | **Supabase vs self-hosted PostgreSQL**: When to offer self-hosting? | MEDIUM | Start with Supabase; design PostgreSQL adapter interface for future self-hosting |
| 9 | **Rust migration timing**: When to start cementing components? | MEDIUM | Build and validate in TS first; migrate module-by-module; gateway and CLI are first candidates |
| 10 | **SEFAZ homologação access**: Do we have testing environment access? | HIGH | Register with SVRS homologação; procurement of A1 certificates for dev |

---

## Appendix A: Module Count Summary

| Layer | Modules | Complexity |
|-------|---------|------------|
| Core | 10 | 2 XL, 4 L, 3 M, 1 S |
| Compliance | 6 | 3 XL, 1 L, 1 M, 1 S |
| Operations | 5 | 1 L, 3 M, 1 S |
| Advanced | 9 | 2 XL, 5 L, 2 M |
| Industry | 8 | 2 XL, 5 L, 1 M |
| Integrations | 6 | 2 XL, 3 L, 1 M |
| Automation | 5 | 3 L, 2 M |
| **Total** | **42** | **10 XL, 14 L, 12 M, 6 S** |

## Appendix B: Effort Summary by Batch

| Batch | Scope | Days | Weeks |
|-------|-------|------|-------|
| Batch 1 | Foundation analysis | 29-40 weeks total gap | 29-40 |
| Batch 2 | Core modules | ~240 days | ~48 |
| Batch 3 | Compliance & integrations | ~292-317 days | ~58-63 |
| Batch 4 | Advanced & infrastructure | ~310-335 days | ~62-67 |
| Batch 5 | Growth & synthesis | ~110 days | ~22 |
| **Total** | **All 42 modules** | **~952-1002 days** | **~190-200 weeks (solo)** |

**With 2-3 devs and parallel phases**: 50-66 weeks (12-16 months)

---

*This master plan should be reviewed monthly. Update phase gates as modules complete. Re-evaluate risk register quarterly.*
